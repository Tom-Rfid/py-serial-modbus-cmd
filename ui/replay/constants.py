"""
ui/replay/constants.py — Couleurs, icônes et colonnes du panneau Replay.
"""
from ui.i18n import _
SPEEDS = {"x0.25": 0.25, "x0.5": 0.5, "x1": 1.0, "x2": 2.0, "x4": 4.0}

GREY = "gray"
RED = "#c0392b"
PANEL_BG = "#c9ced5"        # fond de tout le panneau Replay (un peu plus foncé que le reste)

# Boutons de lecture : couleur de l'icône / du texte
PLAY_GREEN = "#1e8e3e"
STEP_BLUE = "#1f5fbf"
STOP_RED = "#c0392b"

# Résultat d'un échange -> (icône, tag de fond de la ligne TX)
RESULTS = {
    "identique": ("✓", None),
    "aucune attendue": ("✓", None),
    "différent": ("≠", "diff"),
    "timeout": ("✗", "timeout"),
    "réponse en trop": ("+", "extra"),
}
ICON_CURRENT = "▶"          # ligne en cours d'envoi

# Colonnes du tableau : (clé, titre, largeur, modifiable)
COLUMNS = (
    ("icon", "", 26, False),
    ("n", "#", 36, False),
    ("t", "t (ms)", 64, True),
    ("dir", "Dir", 38, True),
    ("hex", _("Octets (hexa)"), 240, True),
    ("label", _("Libellé"), 140, True),
    ("res", _("Résultat"), 260, False),
    ("delay", _("Délai"), 54, False),
    ("got", _("Réponse reçue"), 200, False),
    ("lat", "Lat.", 44, False),
)
COL_KEYS = [c[0] for c in COLUMNS]
EDITABLE = [c[0] for c in COLUMNS if c[3]]

# Choix de la flèche « → Replay » des onglets Manuel et Protocole
ARROW_INSERT = "insert"
ARROW_REPLACE = "replace"
