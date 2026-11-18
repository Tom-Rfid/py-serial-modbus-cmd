"""
ui/app/sending.py — Envois, séquences et lecture des événements du port série.
"""
import queue

from core.frames import frame_segments, parse_int
from core.protocol import QUERY
from core.request_message import build_request, is_request
from ui.hexview import message_segments, protocol_segments
from ui.i18n import _, tr

POLL_MS = 30        # période (ms) de lecture des événements du port série


class SendingMixin:
    # ------------------------------------------------------------------
    # Envois
    # ------------------------------------------------------------------
    def send_bytes(self, data, label="", segments=None):
        """Envoie des octets, les journalise et les trace. Retourne False (erreur journalisée) en cas d'échec.

        segments : couleurs de la trame dans le moniteur ; sinon calculées par style().
        """
        try:
            self.link.write(data)
        except ConnectionError as e:
            self.monitor.log(_("Envoi impossible : {0}").format(tr(str(e))), "ERR")
            return False
        self.protocol_panel.on_sent(data)          # mémorise REQUEST ID -> commande (réponse « Auto »)
        self.monitor.log_frame("TX", data, label, segments)
        if self.recorder:
            self.recorder.write("TX", data, label)
        self.await_reply(data, label)
        return True

    def command_for_message(self, msg, values):
        """(commande de la bibliothèque, protocole en cours) d'un message de protocole, d'après son
        COMMAND ID saisi : sert à convertir DATA <-> valeurs dans l'onglet Manuel. (None, protocole)
        si le COMMAND ID est invalide ou inconnu du protocole en cours."""
        if not is_request(msg):
            return None, self.proto
        try:
            cid = parse_int(values.get("command_id", msg["request"].get("command_id", "")))
        except (ValueError, TypeError):
            return None, self.proto
        lib = getattr(self.protocol_panel, "lib", None)
        return (lib.by_id(cid) if lib is not None else None), self.proto

    def message_frame(self, idx):
        """(trame, segments de couleur) du message idx avec ses valeurs courantes. ValueError si invalide."""
        return self.build_message(self.messages[idx], self.values_for(idx))

    def build_message(self, msg, values):
        """(trame, segments de couleur ; DATA en bleu) d'un message de l'onglet Manuel.

        Message de protocole ("request") : trame construite par le protocole en cours (CRC compris) ;
        sinon d'après "frame" et "params". Lève ValueError si une valeur est invalide.
        """
        if is_request(msg):
            frame = build_request(msg, values, self.proto, QUERY)
            return frame, protocol_segments(self.proto.decode(frame, QUERY), self.proto, data=True)
        segs = frame_segments(msg, values)
        return b"".join(b for _, b in segs), message_segments(segs)

    def send_message(self, idx):
        """Construit la trame du message idx, puis l'envoie."""
        msg = self.messages[idx]
        try:
            frame, segments = self.message_frame(idx)
        except Exception as e:                  # valeur hors limites, hexa invalide...
            self.monitor.log(f"{msg['name']} : {e}", "ERR")
            return False
        return self.send_bytes(frame, msg["name"], segments)

    def send_sequence(self, ids, delay_ms):
        """Envoie plusieurs messages à la suite, séparés de delay_ms.

        Chaque envoi programme le suivant avec after() : l'interface reste réactive.
        La séquence s'arrête au premier échec.
        """
        self.cancel_sequence()

        def step(k):
            self._seq_job = None
            if k < len(ids) and self.send_message(ids[k]):
                self._seq_job = self.after(delay_ms, step, k + 1)

        step(0)

    def cancel_sequence(self):
        if self._seq_job:
            self.after_cancel(self._seq_job)
            self._seq_job = None

    # ------------------------------------------------------------------
    # Réception
    # ------------------------------------------------------------------
    def poll_link(self):
        """Tâche périodique : traite les événements déposés par le thread de lecture.

        Tkinter ne peut être utilisé que depuis son propre thread : le thread de
        lecture dépose donc les événements dans une file, vidée ici.
        """
        try:
            while True:
                kind, payload = self.link.events.get_nowait()
                if kind == "rx":
                    self.on_frame_received(payload)
                elif kind == "lost":
                    self.com.on_lost(payload)
        except queue.Empty:
            pass                                # plus rien à traiter pour l'instant
        self.after(POLL_MS, self.poll_link)

    def on_frame_received(self, data):
        """Une trame reçue est distribuée à tous ceux qui en ont besoin."""
        self.monitor.log_frame("RX", data)
        self.reply_received(data)
        self.protocol_panel.on_received(data)
        if self.recorder:
            self.recorder.write("RX", data)
        self.replay.on_received(data)

    def update_send_state(self):
        """Boutons d'envoi (onglets, moniteur) grisés tant que la liaison n'est pas connectée."""
        enabled = bool(self.link.connected)
        for panel in (self.monitor, self.params, self.messages_panel, self.protocol_panel):
            panel.set_send_enabled(enabled)

    def on_link_change(self):
        """Connexion ou déconnexion : à la déconnexion, on arrête les envois en cours."""
        self.update_send_state()
        if not self.link.connected:
            self.params.stop_periodic()
            self.cancel_sequence()
