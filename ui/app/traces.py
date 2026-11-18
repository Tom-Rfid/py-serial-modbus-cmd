"""
ui/app/traces.py — Enregistrement de trace et liens avec le panneau Replay.
"""
from datetime import datetime
from tkinter import filedialog

from core.trace import TraceRecorder
from ui.i18n import _, tr


class TracesMixin:
    def toggle_trace(self):
        """Bouton « ● Trace » du moniteur : démarre l'enregistrement dans un fichier, ou l'arrête."""
        if self.recorder:
            self._stop_trace()
        else:
            self._start_trace()

    def _start_trace(self):
        self.traces_dir.mkdir(exist_ok=True)
        default = f"trace_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path = filedialog.asksaveasfilename(initialdir=self.traces_dir, initialfile=default,
                                            defaultextension=".csv",
                                            filetypes=[(_("Trace CSV"), "*.csv"), (_("Tous"), "*.*")])
        if not path:
            return
        try:
            self.recorder = TraceRecorder(path)
        except OSError as e:
            self.monitor.log(_("Trace impossible : {0}").format(tr(str(e))), "ERR")
            return
        self.monitor.set_recording(path)
        self.monitor.log(_("Trace en cours : {0}").format(path), "INFO")

    def _stop_trace(self):
        rec, self.recorder = self.recorder, None
        rec.close()
        self.monitor.set_recording(None)
        self.monitor.log(_("Trace arrêtée : {0} trame(s) dans {1}").format(rec.count, rec.path), "INFO")
        # La trace s'ouvre dans le panneau Replay, sauf si une autre y est en cours de modification
        if not self.replay.running and not self.replay.doc.modified:
            self.replay.load(rec.path)
            self.show_replay(True)

    def open_replay(self):
        """Bouton « + Replay » du moniteur : les trames du moniteur deviennent une nouvelle trace
        du panneau Replay (rien n'est perdu : on demande avant de remplacer une trace modifiée).
        Sans trame, le panneau est seulement affiché."""
        self.show_replay(True)
        events = self.monitor.trace_events()
        if not events:
            return
        if self.replay.running:
            self.replay.say(_("Arrêter le replay pour modifier la trace"), error=True)
            return
        self.replay.load_events(events, f"moniteur_{datetime.now():%Y%m%d_%H%M%S}")

    def to_replay(self, data, label):
        """Flèche « → Replay » (onglets Manuel et Protocole) : la trame va dans la ligne
        sélectionnée du replay (insérée après, ou à la place, selon le choix du panneau)."""
        self.show_replay(True)
        self.replay.put_frame(data, label)

    def manual_to_replay(self, idx):
        """Flèche « → Replay » de l'onglet Manuel : trame du message idx avec ses valeurs."""
        msg = self.messages[idx]
        try:
            frame, _segments = self.message_frame(idx)
        except Exception as e:
            self.monitor.log(f"{msg['name']} : {e}", "ERR")
            return
        self.to_replay(frame, msg["name"])

    def decode_in_protocol(self, direction, data):
        """Bouton « Décoder dans Protocole » du replay : la trame est décodée dans l'onglet Protocole."""
        self.protocol_panel.show_for_decode(data, self.kind_of(direction))
        self.tabs.select(self.protocol_panel)
