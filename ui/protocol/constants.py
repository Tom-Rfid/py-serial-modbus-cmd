"""
ui/protocol/constants.py — Libellés et couleurs de l'onglet Protocole.
"""
from core.protocol import QUERY, RESPONSE
from ui.i18n import _

MONO = ("Consolas", 10)
GREEN, RED, GREY = "#1a8a3a", "#c0392b", "gray"
KIND_LABELS = {QUERY: _("Requête"), RESPONSE: _("Réponse")}
MANUAL = _("(saisie manuelle : COMMAND ID et DATA en hexa)")
AUTO = _("Auto (d'après la requête envoyée)")
RAW = _("Brut (données non décodées)")
MANUAL_DATA = _("(saisie à la main)")
REPLAY_ARROW = _("→ Replay")
