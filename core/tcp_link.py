"""
core/tcp_link.py — Liaison TCP (client) : Modbus TCP, passerelles série / Ethernet.

Même interface que SerialLink (core/serial_link.py) : l'interface peut utiliser l'une
ou l'autre sans changement (voir core/link_switch.py).

    link = TcpLink()
    link.connect("192.168.1.10", 502)
    link.write(bytes.fromhex("00 01 00 00 00 06 01 03 00 00 00 0A"))
    kind, payload = link.events.get()   # ("rx", b"...") ou ("lost", "...")
    link.disconnect()

Les octets reçus sont découpés en trames comme sur une liaison série : silence de
`gap_ms` ms, ou délimiteur `frame_end` (voir core/framing.py).
"""
import queue
import socket
import threading
import time

from .framing import FrameSplitter

DEFAULT_PORT = 502                      # port Modbus TCP
CONNECT_TIMEOUT_S = 3.0                 # délai maximal pour établir la connexion


def _reason(exc):
    """Message lisible d'une erreur de connexion."""
    if isinstance(exc, socket.timeout):
        return "pas de réponse (adresse ou réseau ?)"
    if isinstance(exc, ConnectionRefusedError):
        return "connexion refusée (port fermé ou serveur arrêté)"
    if isinstance(exc, socket.gaierror):
        return "adresse introuvable"
    return str(exc)


class TcpLink:
    def __init__(self):
        self.sock = None                # socket connecté, ou None
        self.config = {}                # {"host": ..., "port": ...}
        self.events = queue.Queue()     # ("rx", bytes) | ("lost", message)
        self.gap_ms = 20.0              # silence (ms) qui marque la fin d'une trame reçue
        self.frame_end = None           # délimiteur de fin de trame, ou None
        self.tx_bytes = 0
        self.rx_bytes = 0
        self._stop = threading.Event()
        self._thread = None

    @property
    def connected(self):
        return self.sock is not None

    @property
    def port(self):
        """« 192.168.1.10:502 » une fois connecté, sinon None."""
        return f"{self.config['host']}:{self.config['port']}" if self.connected else None

    def describe(self):
        """Résumé de la connexion : 'TCP 192.168.1.10:502'."""
        return f"TCP {self.config['host']}:{self.config['port']}" if self.config else ""

    def connect(self, host, port=DEFAULT_PORT, **_ignored):
        """Se connecte au serveur. Lève ConnectionError avec un message lisible."""
        if self.connected:
            self.disconnect()
        try:
            port = int(port)
            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S)
        except (OSError, ValueError) as e:
            raise ConnectionError(f"{host}:{port} {_reason(e)}") from e
        sock.settimeout(0.01)           # lecture non bloquante (10 ms), comme le port série
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)     # trames envoyées sans attendre
        self.sock = sock
        self.config = {"host": host, "port": port}
        self.tx_bytes = self.rx_bytes = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, args=(sock,), daemon=True)
        self._thread.start()

    def disconnect(self):
        self._stop.set()
        sock, self.sock = self.sock, None
        if sock:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=0.5)
        self._thread = None

    def reconfigure(self, **_ignored):
        """Vitesse, parité… : sans objet en TCP."""

    def set_lines(self, dtr=None, rts=None):
        """DTR / RTS : sans objet en TCP."""

    def write(self, data):
        if not self.connected:
            raise ConnectionError("non connecté")
        try:
            self.sock.sendall(data)
        except OSError as e:
            self.events.put(("lost", str(e)))
            raise ConnectionError(f"envoi impossible : {e}")
        self.tx_bytes += len(data)

    def _reader(self, sock):
        splitter = FrameSplitter(self.gap_ms, self.frame_end)
        while not self._stop.is_set():
            splitter.gap_ms, splitter.frame_end = self.gap_ms, self.frame_end
            try:
                data = sock.recv(4096)
                if not data:                # le serveur a fermé la connexion
                    raise ConnectionError("connexion fermée par l'appareil")
            except socket.timeout:
                data = b""
            except (OSError, ConnectionError) as e:
                if not self._stop.is_set():
                    self._publish([splitter.flush()])
                    self.events.put(("lost", str(e) or "erreur de lecture"))
                return
            self.rx_bytes += len(data)
            self._publish(splitter.feed(data, time.monotonic()))
        self._publish([splitter.flush()])

    def _publish(self, frames):
        for frame in frames:
            if frame:
                self.events.put(("rx", frame))
