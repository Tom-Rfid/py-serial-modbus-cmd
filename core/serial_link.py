"""
core/serial_link.py — Accès au port série.

Rôle
    - lister les ports présents sur la machine
    - tester si un port est libre, occupé par un autre programme ou absent
    - ouvrir / fermer un port, envoyer des octets
    - lire en continu dans un thread et découper les octets reçus en trames
    - changer les réglages (vitesse, parité...) sans fermer le port

Communication avec l'interface
    Le thread de lecture ne touche jamais à l'interface (Tkinter ne le supporte
    pas). Il dépose des événements dans la file `SerialLink.events` :
        ("rx", bytes)       une trame reçue
        ("lost", message)   la liaison est tombée (câble retiré, erreur)
    L'interface vide cette file régulièrement depuis son propre thread
    (voir ui/app.py, App._poll_link).

Ce module ne dépend pas de Tkinter : il est utilisable dans un simple script.
"""
import os
import queue
import re
import threading
import time
from dataclasses import dataclass

import serial
from serial.tools import list_ports

from .framing import FrameSplitter
from .port_filter import BLUETOOTH_DEVICES, BLUETOOTH_HINTS, DEFAULT_PORT_FILTER, enabled_ids

# --------------------------------------------------------------------------
# Valeurs possibles des réglages
# --------------------------------------------------------------------------

# Vitesses proposées dans l'interface (une autre valeur peut être saisie)
BAUDRATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600,
             115200, 230400, 460800, 921600]

# Correspondance entre nos valeurs (simples, enregistrables en JSON)
# et les constantes de pyserial.
BYTESIZES = {5: serial.FIVEBITS, 6: serial.SIXBITS, 7: serial.SEVENBITS, 8: serial.EIGHTBITS}
PARITIES = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
            "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE}
STOPBITS = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE,
            "2": serial.STOPBITS_TWO}
FLOWS = ("none", "rtscts", "xonxoff")   # aucun, matériel (RTS/CTS), logiciel (XON/XOFF)

# États possibles d'un port (texte affiché tel quel dans l'interface)
FREE, BUSY, MISSING, ERROR = "libre", "occupé", "absent", "erreur"


# --------------------------------------------------------------------------
# Ports présents
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PortInfo:
    """Un port série présent sur la machine."""
    device: str         # nom système : "COM3", "/dev/ttyUSB0"
    description: str    # description du pilote : "USB-SERIAL CH340"
    vid: int = None     # identifiant USB du fabricant (None : port non USB)
    pid: int = None     # identifiant USB du produit
    hwid: str = ""      # identifiant matériel : "USB VID:PID=0403:6001 …", "BTHENUM\\{…}"

    def is_bluetooth(self):
        """True pour un port série sur Bluetooth (Windows : BTHENUM ; Linux : rfcomm ; macOS)."""
        text = f"{self.hwid} {self.description}".upper()
        return any(h in text for h in BLUETOOTH_HINTS) or self.device.startswith(BLUETOOTH_DEVICES)

    def matches(self, usb_ids):
        """True si (VID, PID) du port fait partie de usb_ids (ensemble de couples)."""
        return (self.vid, self.pid) in usb_ids

    def is_ftdi(self):
        """True pour un adaptateur FTDI du filtre par défaut."""
        return self.matches(enabled_ids(DEFAULT_PORT_FILTER))

    def label(self):
        """Texte affiché dans la liste : 'COM3 — USB-SERIAL CH340'."""
        if self.description in ("", "n/a", self.device):
            return self.device
        return f"{self.device} — {self.description}"


def _port_sort_key(p):
    """Clé de tri « naturel » : COM3 avant COM10 (un tri alphabétique ferait l'inverse)."""
    m = re.match(r"(.*?)(\d+)$", p.device)
    return (m.group(1), int(m.group(2))) if m else (p.device, 0)


def list_serial_ports(usb_ids=None, hide_bluetooth=False, only_ftdi=False):
    """Retourne la liste des ports présents (PortInfo), triée.

    usb_ids        : ensemble de (VID, PID) à garder (filtre de la case « FTDI ») ; None = tous
    hide_bluetooth : ports série sur Bluetooth retirés
    only_ftdi      : raccourci pour usb_ids = adaptateurs FTDI du filtre par défaut
    N'ouvre aucun port : peut être appelé souvent sans perturber les appareils.
    """
    ports = [PortInfo(p.device, p.description or "", getattr(p, "vid", None), getattr(p, "pid", None),
                      getattr(p, "hwid", "") or "")
             for p in list_ports.comports()]
    if only_ftdi:
        usb_ids = enabled_ids(DEFAULT_PORT_FILTER)
    if hide_bluetooth:
        ports = [p for p in ports if not p.is_bluetooth()]
    if usb_ids is not None:
        ports = [p for p in ports if p.matches(usb_ids)]
    return sorted(ports, key=_port_sort_key)


def _classify(exc):
    """Traduit une erreur d'ouverture de port en (état, message lisible).

    Les messages d'erreur diffèrent selon le système, on cherche donc des
    mots-clés connus :
      Windows : "PermissionError(13, 'Accès refusé.')"           -> occupé
                "FileNotFoundError(2, '...introuvable.')"         -> absent
      Linux   : "Could not exclusively lock port ... [Errno 11]"  -> occupé
                "[Errno 2] No such file or directory"             -> absent
    """
    low = str(exc).lower()
    errno = getattr(exc, "errno", None)
    if errno in (13, 16) or any(k in low for k in (
            "permissionerror", "access is denied", "accès refusé", "busy",
            "exclusively lock", "resource temporarily unavailable")):
        return BUSY, "déjà utilisé par un autre programme"
    if errno == 2 or any(k in low for k in (
            "filenotfounderror", "cannot find", "introuvable", "no such file")):
        return MISSING, "introuvable (débranché ?)"
    return ERROR, str(exc)


def _new_serial(device, baudrate=9600, bytesize=8, parity="N", stopbits="1",
                flow="none", timeout=0.01):
    """Crée un objet Serial configuré mais PAS encore ouvert.

    On le configure avant open() pour que les réglages (et surtout l'état
    de DTR/RTS) soient appliqués dès l'ouverture.
    """
    s = serial.Serial()                 # sans argument : le port n'est pas ouvert
    s.port = device
    s.baudrate = int(baudrate)
    s.bytesize = BYTESIZES[int(bytesize)]
    s.parity = PARITIES[parity]
    s.stopbits = STOPBITS[str(stopbits)]
    s.rtscts = flow == "rtscts"
    s.xonxoff = flow == "xonxoff"
    # Timeout de lecture court : read() rend la main toutes les 10 ms au plus,
    # ce qui permet au thread de lecture de vérifier s'il doit s'arrêter.
    s.timeout = timeout
    # Timeout d'écriture : évite de bloquer indéfiniment si le contrôle de
    # flux empêche l'envoi (appareil qui ne lève jamais CTS, par exemple).
    s.write_timeout = 1
    # DTR / RTS inactifs à l'ouverture : sur beaucoup de cartes Arduino / ESP32,
    # ces lignes sont reliées au reset, les activer redémarrerait la carte.
    s.dtr = False
    s.rts = False
    if os.name == "posix":
        # Sous Windows, un port ne peut être ouvert que par un programme à la fois.
        # Sous Linux / macOS ce n'est pas le cas par défaut : on demande un accès
        # exclusif pour détecter qu'un autre programme l'utilise déjà.
        s.exclusive = True
    return s


def check_port(device):
    """Teste si un port peut être ouvert, puis le referme aussitôt.

    Retourne (état, message), état parmi FREE, BUSY, MISSING, ERROR.
    """
    s = _new_serial(device)
    try:
        s.open()
    except (serial.SerialException, OSError, ValueError) as e:
        return _classify(e)
    s.close()
    return FREE, "disponible"


# --------------------------------------------------------------------------
# Connexion
# --------------------------------------------------------------------------

class SerialLink:
    """Une liaison série : connexion, envoi, réception en tâche de fond.

    Utilisation :
        link = SerialLink()
        link.connect("COM3", 115200)
        link.write(b"\\xAA\\x55")
        kind, payload = link.events.get()   # ("rx", b"...") ou ("lost", "...")
        link.disconnect()
    """

    def __init__(self):
        self.ser = None                 # objet serial.Serial ouvert, ou None
        self.config = {}                # réglages de la connexion en cours
        self.events = queue.Queue()     # ("rx", bytes) | ("lost", message)
        self.gap_ms = 20.0              # silence (ms) qui marque la fin d'une trame reçue
        self.frame_end = None           # délimiteur de fin de trame (Modbus ASCII : b"\r\n"), ou None
        self.tx_bytes = 0               # octets envoyés depuis la connexion
        self.rx_bytes = 0               # octets reçus depuis la connexion
        self._stop = threading.Event()  # demande d'arrêt au thread de lecture
        self._thread = None             # thread de lecture

    @property
    def connected(self):
        """True si un port est ouvert."""
        return self.ser is not None and self.ser.is_open

    @property
    def port(self):
        """Nom du port connecté ("COM3"), ou None."""
        return self.config.get("port") if self.connected else None

    def describe(self):
        """Résumé de la connexion : 'COM3 @ 115200 8N1' (+ contrôle de flux s'il y en a un)."""
        c = self.config
        if not c:
            return ""
        text = f"{c['port']} @ {c['baudrate']} {c['bytesize']}{c['parity']}{c['stopbits']}"
        return text if c["flow"] == "none" else f"{text} {c['flow']}"

    def connect(self, port, baudrate, bytesize=8, parity="N", stopbits="1", flow="none"):
        """Ouvre le port et démarre la lecture.

        Lève ConnectionError avec un message lisible en cas d'échec
        (ex. "COM3 déjà utilisé par un autre programme").
        """
        if self.connected:
            self.disconnect()
        try:
            s = _new_serial(port, baudrate, bytesize, parity, stopbits, flow)
            s.open()
        except (serial.SerialException, OSError, ValueError) as e:
            raise ConnectionError(f"{port} {_classify(e)[1]}") from e
        # Jette ce qui a pu s'accumuler dans le tampon du pilote avant l'ouverture
        s.reset_input_buffer()
        self.ser = s
        self.config = dict(port=port, baudrate=int(baudrate), bytesize=int(bytesize),
                           parity=parity, stopbits=str(stopbits), flow=flow)
        self.tx_bytes = self.rx_bytes = 0
        self._stop.clear()
        # daemon=True : le thread ne bloque pas la fermeture du programme
        self._thread = threading.Thread(target=self._reader, args=(s,), daemon=True)
        self._thread.start()

    def disconnect(self):
        """Arrête la lecture et ferme le port. Sans effet si déjà déconnecté."""
        self._stop.set()                # demande au thread de s'arrêter
        s, self.ser = self.ser, None
        if s:
            try:
                s.cancel_read()         # débloque un read() en cours
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass
        # Attend la fin du thread (sauf si c'est lui qui appelle disconnect)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=0.5)
        self._thread = None

    def reconfigure(self, baudrate=None, bytesize=None, parity=None, stopbits=None, flow=None):
        """Change les réglages du port ouvert, sans le fermer.

        Seuls les arguments fournis (non None) sont modifiés.
        Lève ConnectionError si le port ou l'adaptateur refuse le réglage
        (certains adaptateurs USB n'acceptent pas tous les formats).
        """
        if not self.connected:
            return
        s = self.ser
        try:
            # pyserial applique chaque réglage immédiatement au port ouvert
            if baudrate is not None:
                s.baudrate = int(baudrate)
                self.config["baudrate"] = int(baudrate)
            if bytesize is not None:
                s.bytesize = BYTESIZES[int(bytesize)]
                self.config["bytesize"] = int(bytesize)
            if parity is not None:
                s.parity = PARITIES[parity]
                self.config["parity"] = parity
            if stopbits is not None:
                s.stopbits = STOPBITS[str(stopbits)]
                self.config["stopbits"] = str(stopbits)
            if flow is not None:
                s.rtscts = flow == "rtscts"
                s.xonxoff = flow == "xonxoff"
                self.config["flow"] = flow
        except Exception as e:      # SerialException, termios.error (Linux), ValueError...
            raise ConnectionError(f"réglage refusé par le port : {e}") from e

    def set_lines(self, dtr=None, rts=None):
        """Active / désactive les lignes de contrôle DTR et RTS (None = inchangé)."""
        if not self.connected:
            return
        if dtr is not None:
            self.ser.dtr = dtr
        if rts is not None:
            self.ser.rts = rts

    def write(self, data):
        """Envoie des octets. Lève ConnectionError en cas d'échec."""
        if not self.connected:
            raise ConnectionError("port non connecté")
        try:
            self.ser.write(data)
        except serial.SerialTimeoutException:
            # L'envoi n'a pas pu se faire en 1 s : en général un contrôle de
            # flux activé alors que l'appareil ne le gère pas.
            raise ConnectionError("délai d'écriture dépassé (contrôle de flux bloquant ?)")
        except (serial.SerialException, OSError) as e:
            # Erreur matérielle : on signale aussi la perte de liaison
            self.events.put(("lost", str(e)))
            raise ConnectionError(f"écriture impossible : {e}")
        self.tx_bytes += len(data)

    # ----------------------------------------------------------------------
    # Lecture en tâche de fond (exécutée dans un thread séparé)
    # ----------------------------------------------------------------------
    def _reader(self, s):
        """Boucle de lecture.

        Les octets arrivent par morceaux de taille quelconque. FrameSplitter les
        accumule et découpe les trames : silence de plus de `gap_ms` millisecondes,
        ou délimiteur de fin `frame_end` (Modbus ASCII) s'il est réglé.

            octets : AA 55 01 ......(silence > gap_ms)...... AA 55 02
            trames : [AA 55 01]                              [AA 55 02]
        """
        splitter = FrameSplitter(self.gap_ms, self.frame_end)
        while not self._stop.is_set():
            splitter.gap_ms, splitter.frame_end = self.gap_ms, self.frame_end   # réglages modifiables en route
            try:
                # Lit tout ce qui est disponible, ou attend au plus `timeout`
                # (10 ms) qu'un octet arrive.
                data = s.read(s.in_waiting or 1)
            except Exception as e:
                # Erreur de lecture : port fermé volontairement (on ignore)
                # ou perdu (câble retiré) -> on le signale à l'interface.
                if not self._stop.is_set():
                    self._publish([splitter.flush()])
                    self.events.put(("lost", str(e) or "erreur de lecture"))
                return
            self.rx_bytes += len(data)
            self._publish(splitter.feed(data, time.monotonic()))
        self._publish([splitter.flush()])       # arrêt demandé : on publie ce qui reste

    def _publish(self, frames):
        """Dépose les trames terminées (non vides) dans la file des événements."""
        for frame in frames:
            if frame:
                self.events.put(("rx", frame))
