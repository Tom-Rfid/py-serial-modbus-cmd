"""
ui/app/protocol.py — Protocole en cours, bibliothèque de commandes, timeout de réponse.
"""
from core.commands import Library, load_library
from core.protocol import DEFAULT_PROTOCOL, QUERY, RESPONSE, ProtocolError, list_protocols, load_protocol
from ui.hexview import protocol_segments
from ui.i18n import _, language, tr


def translate_library(lib):
    """Interface en anglais : noms, descriptions et libellés des champs en anglais
    ("name_en", "description_en", "label_en" des Msg_*.json), quand ils existent."""
    for cmd in lib.commands:
        cmd.name, cmd.description = cmd.text("en")
        for fdef in cmd.tx + cmd.rx:
            if fdef.get("label_en"):
                fdef["label"] = fdef["label_en"]


class ProtocolMixin:
    # ------------------------------------------------------------------
    # Fichier de protocole et bibliothèque
    # ------------------------------------------------------------------
    def protocol_file(self):
        """Fichier de protocole à charger : celui choisi (settings.json), sinon celui de la
        version (edition.json, "default_protocol"), sinon le premier du dossier protocols/."""
        candidates = [self.settings["protocol"], self.edition["default_protocol"]]
        if self.protocols_dir.is_dir():
            candidates += sorted(p.name for p in self.protocols_dir.glob("*.json"))
        return next((name for name in candidates if name and (self.protocols_dir / name).is_file()), "")

    def load_protocol(self, filename):
        """Charge protocols/<filename>. En cas d'erreur, garde le protocole générique intégré et le signale."""
        files = list_protocols(self.protocols_dir) if self.protocols_dir.is_dir() else []
        self.protocol_panel.set_protocols(files, filename)
        try:
            if not filename:
                raise ProtocolError(_("aucun fichier dans protocols/"))
            proto = load_protocol(self.protocols_dir / filename)
        except ProtocolError as e:
            self.monitor.log(_("Protocole : {0} ; protocole générique intégré utilisé").format(tr(str(e))), "ERR")
            proto = DEFAULT_PROTOCOL
        self.proto = proto
        proto.language = language()                     # textes du fichier ("values", descriptions, erreurs)
        self.link.frame_end = proto.frame_end           # Modbus ASCII : trames coupées à CR LF
        self.protocol_panel.set_protocol(proto)
        algo, _order = proto.main_crc
        self.monitor.set_crc_name(algo.name if algo else "")
        self.monitor.log(_("Protocole : {0}").format(proto.name) + (f" ({filename})" if proto.path else ""), "INFO")

    def select_protocol(self, filename):
        """Autre protocole choisi dans l'onglet Protocole : chargé, mémorisé, commandes relues."""
        self.settings["protocol"] = filename
        self.clear_awaiting()
        self.load_protocol(filename)
        self.load_library()

    def load_library(self):
        """Commandes et codes d'erreur : dossier "commands" du fichier de protocole.

        Les Msg_*.json écrits pour un autre protocole (clé "protocol") sont ignorés.
        """
        folder = self.proto.commands_dir
        if folder is None and self.proto is DEFAULT_PROTOCOL:
            folder = self.lists_dir             # protocole intégré (fichier absent / invalide)
        lib = load_library(folder, self.proto.name) if folder else Library()
        lib.language = language()
        if lib.language == "en":
            translate_library(lib)
        lib.errors.update(self.proto.error_texts())     # codes d'erreur du fichier de protocole (langue choisie), prioritaires
        self.protocol_panel.set_library(lib)
        self.params.refresh_conversion()                # messages de protocole : conversion de DATA
        self.params.update_preview()                    # messages de protocole : trame du protocole en cours
        self._log_library(lib)

    def _log_library(self, lib):
        for name, err in lib.problems:
            self.monitor.log(_("{0} (protocole) : {1}").format(name, tr(str(err))), "ERR")
        # Fichiers écrits pour d'autres protocoles : une seule ligne (ils peuvent être nombreux)
        if len(lib.skipped) == 1:
            name, made_for = lib.skipped[0]
            self.monitor.log(_("{0} ignoré : écrit pour le protocole {1}").format(name, made_for), "INFO")
        elif lib.skipped:
            self.monitor.log(_("{0} fichier(s) de commandes ignoré(s) : écrits pour d'autres protocoles")
                             .format(len(lib.skipped)), "INFO")
        if lib.commands or lib.errors:
            self.monitor.log(_("Protocole : {0} commande(s), {1} code(s) d'erreur").format(len(lib.commands), len(lib.errors)), "INFO")
        if lib.hidden_count():
            # Commandes "hidden" : reconnues au décodage, absentes des listes sauf case « Masquées »
            self.monitor.log(_("Protocole : {0} commande(s) masquée(s), visibles avec la case « Masquées »")
                             .format(lib.hidden_count()), "INFO")

    # ------------------------------------------------------------------
    # Moniteur : résumé et couleurs des trames du protocole
    # ------------------------------------------------------------------
    @staticmethod
    def kind_of(direction):
        return QUERY if direction == "TX" else RESPONSE

    def annotate(self, direction, data):
        """Résumé protocole d'une trame (délégué à l'onglet Protocole), ou None."""
        return self.protocol_panel.describe_frame(direction, data)

    def style(self, direction, data):
        """Couleurs d'une trame du protocole (celles du fichier de conf), ou None."""
        kind = self.kind_of(direction)
        if not self.proto.matches(data, kind):
            return None
        return protocol_segments(self.proto.decode(data, kind), self.proto)

    # ------------------------------------------------------------------
    # Timeout de réponse
    # ------------------------------------------------------------------
    def await_reply(self, data, label):
        """Requête du protocole envoyée : on attend sa réponse au plus « Timeout réponse » ms.

        La réponse se reconnaît à son REQUEST ID ; un protocole sans REQUEST ID n'est pas surveillé.
        """
        if not self.proto.matches(data, QUERY):
            return
        d = self.proto.decode(data, QUERY)
        rid = d.request_id
        if not d.complete or rid is None:
            return
        self._cancel_await(rid)                 # même REQUEST ID renvoyé : on repart de zéro
        ms = float(self.settings["rx_timeout_ms"])
        self._awaiting[rid] = self.after(int(ms), self._reply_timeout, rid, label or _("requête #{0}").format(rid), ms)

    def reply_received(self, data):
        """Trame reçue : si c'est la réponse d'une requête surveillée, plus de timeout.

        Une réponse sans REQUEST ID (accusé E5 de M-Bus ou PROFIBUS) répond à la plus
        ancienne requête en attente."""
        if not self.proto.matches(data, RESPONSE):
            return
        rid = self.proto.decode(data, RESPONSE).request_id
        if rid is None and self._awaiting:
            rid = next(iter(self._awaiting))
        if rid is not None:
            self._cancel_await(rid)

    def _cancel_await(self, rid):
        job = self._awaiting.pop(rid, None)
        if job:
            self.after_cancel(job)

    def clear_awaiting(self):
        for rid in list(self._awaiting):
            self._cancel_await(rid)

    def _reply_timeout(self, rid, label, ms):
        """Pas de réponse à temps : ligne rouge dans le moniteur."""
        self._awaiting.pop(rid, None)
        self.monitor.log(_("TIMEOUT : pas de réponse en {0:.0f} ms à « {1} » (REQUEST ID 0x{2:02X})").format(ms, label, rid), "ERR")

    def set_timeout(self, ms):
        """Timeout de réponse modifié dans le moniteur."""
        self.settings["rx_timeout_ms"] = ms
