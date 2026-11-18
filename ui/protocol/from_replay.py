"""
ui/protocol/from_replay.py — Une ligne du Replay chargée dans l'onglet Protocole.

    - ligne TX (requête du protocole en cours) : chargée dans la Requête, comme si on l'avait
      saisie : commande retrouvée d'après son COMMAND ID, REQUEST ID, DATA (brute, les champs
      montrent son décodage). Modifiable puis renvoyable.
    - ligne RX, ou TX qui n'est pas une requête complète du protocole : décodée dans la Réponse.

Le cadre rempli passe sur le fond gris foncé du Replay (highlight.py) ; les deux cadres
reviennent en gris clair dès qu'on choisit une nouvelle commande dans CMD TX.
"""
from core.frames import to_hex
from core.protocol import QUERY, RESPONSE

from .constants import MANUAL
from .highlight import BoxHighlight, setup_styles


class FromReplayMixin:
    def _init_highlight(self):
        """À appeler une fois les cadres Requête et Réponse construits."""
        setup_styles(self)
        self._tx_highlight = BoxHighlight(self._query_box)
        self._rx_highlight = BoxHighlight(self._response_box)
        self._loading_frame = False     # True pendant le chargement : la commande change sans
                                        # que ce soit un choix de l'utilisateur

    def load_from_replay(self, direction, data):
        """Ligne du Replay (direction "TX" ou "RX", octets) chargée dans la Requête ou la Réponse."""
        if direction == "TX" and self.load_query_frame(data):
            self._show_loaded(tx=True)
            return
        self.show_for_decode(data, QUERY if direction == "TX" else RESPONSE)
        self._show_loaded(tx=False)

    def _show_loaded(self, tx):
        """Fond gris foncé sur le cadre qui vient d'être rempli, gris clair sur l'autre."""
        self._tx_highlight.set(tx)
        self._rx_highlight.set(not tx)

    def clear_highlight(self):
        """Les deux cadres reviennent en gris clair (nouvelle commande choisie dans CMD TX)."""
        if self._loading_frame:
            return
        self._tx_highlight.set(False)
        self._rx_highlight.set(False)

    # ------------------------------------------------------------------
    # Requête
    # ------------------------------------------------------------------
    def load_query_frame(self, data):
        """Met une requête complète du protocole en cours dans la partie Requête.
        Retourne False si ce n'en est pas une (elle sera décodée dans la Réponse)."""
        if not self.proto.matches(data, QUERY):
            return False
        d = self.proto.decode(data, QUERY)
        if not d.complete:
            return False
        raw = d.data.raw if d.data else b""
        self._loading_frame = True
        try:
            self._select_command_for(d)
            if d.request_id is not None:
                self.rid_var.set(self._rid_hex(d.request_id))
            if self.cmd is not None:
                self._set_raw_data(raw)
            else:
                self._set_manual(d, raw)
            if d.variant and d.variant in self.proto.variant_names(QUERY):
                self.variant_var.set(d.variant)
            self.update_query()
        finally:
            self._loading_frame = False
        return True

    def _select_command_for(self, d):
        """Commande de la bibliothèque qui correspond à la trame (visible dans CMD TX), sinon
        saisie manuelle."""
        cmd = self._find_command(d)
        label = cmd.label if cmd is not None and cmd.label in self._cmd_labels else MANUAL
        self.cmd_choice.set(label)
        self._on_command()

    def _set_raw_data(self, raw):
        """DATA de la trame gardée telle quelle (DATA brute) : les champs montrent son décodage."""
        if raw:
            self.raw_data[self.cmd.label] = raw
        else:
            self.raw_data.pop(self.cmd.label, None)

    def _set_manual(self, d, raw):
        """Saisie manuelle : COMMAND ID et DATA en hexa."""
        if d.command_id is not None:
            self.cmd_var.set(self._cmd_hex(d.command_id))
        self.data_var.set(to_hex(raw))
