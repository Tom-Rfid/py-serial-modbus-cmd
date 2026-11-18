"""
ui/theme.py — Couleurs de l'interface, réglables (page « Couleurs… ») et mémorisées.

Toutes les zones colorées (moniteur, aperçus hexa, tableaux de trames, replay) lisent
leurs couleurs ici et s'abonnent aux changements : une couleur modifiée dans la page
de réglage s'applique tout de suite, partout.

    THEME.get("tx")                 -> "#1f5fbf"
    THEME.subscribe(fonction)       -> fonction() appelée maintenant puis à chaque changement
    THEME.update({"tx": "#0000FF"}) -> nouvelles couleurs

Les couleurs sont écrites "#RRGGBB". "cmd" peut être vide : le COMMAND ID garde alors
la couleur de la ligne (bleu en TX, violet en RX) et n'est qu'en gras.
"""
import re
import tkinter as tk
from ui.i18n import _

# Couleurs par défaut
DEFAULT_COLORS = {
    # Moniteur et replay
    "tx": "#1F5FBF",        # trames envoyées : bleu
    "rx": "#7B3FA0",        # trames reçues : violet
    "info": "#888888",      # informations : gris
    "error": "#C0392B",     # erreurs : rouge
    # Champs des trames (couleur choisie par "color" dans le fichier de protocole)
    "hdr": "#A8A8A8",       # en-tête : gris clair
    "cmd": "",              # commande : couleur de la ligne, en gras
    "crc": "#4FAE6F",       # CRC / checksum : vert pastel
    "na": "#C8C8C8",        # octets non lus : gris très clair, barré
    "err": "#C0392B",       # CRC ou octet fixe faux : rouge
    "perr_ok": "#B9E8C4",   # fond du code d'erreur à 0 : vert
    "perr_ko": "#F5A3A3",   # fond du code d'erreur non nul : rouge
}

# Présentation dans la page de réglage : (titre du groupe, [(clé, libellé)])
GROUPS = [
    (_("Moniteur et replay"), [
        ("tx", _("Trames envoyées (TX)")),
        ("rx", _("Trames reçues (RX)")),
        ("info", _("Informations")),
        ("error", _("Erreurs")),
    ]),
    (_("Champs des trames"), [
        ("hdr", _("En-tête « hdr » (octets fixes, adresse, numéro de requête)")),
        ("cmd", _("Commande « cmd » (vide : couleur de la ligne, en gras)")),
        ("crc", _("CRC / checksum « crc »")),
        ("na", _("Octets non lus « na »")),
        ("err", _("CRC ou octet fixe faux")),
        ("perr_ok", _("Fond du code d'erreur = 0")),
        ("perr_ko", _("Fond du code d'erreur non nul")),
    ]),
]
EMPTY_ALLOWED = {"cmd"}             # couleurs qui peuvent rester vides

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize(text):
    """'#ff8800' / 'ff8800' / ' #FF8800 ' -> '#FF8800' ; '' -> '' ; None si ce n'est pas une couleur."""
    text = (text or "").strip()
    if not text:
        return ""
    if not text.startswith("#"):
        text = "#" + text
    return text.upper() if HEX.match(text) else None


def readable_on(background):
    """Couleur de texte lisible sur ce fond : noir sur fond clair, blanc sur fond foncé."""
    r, g, b = (int(background[i:i + 2], 16) for i in (1, 3, 5))
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 140 else "#FFFFFF"


class Theme:
    def __init__(self):
        self.colors = dict(DEFAULT_COLORS)
        self._listeners = []

    def load(self, saved):
        """Couleurs mémorisées (settings["colors"]) ; les valeurs invalides sont ignorées."""
        self.colors = merge(saved)

    def get(self, key):
        return self.colors.get(key, DEFAULT_COLORS.get(key, ""))

    def update(self, colors):
        """Nouvelles couleurs : tous les abonnés sont prévenus."""
        self.colors = merge(colors)
        for fn in list(self._listeners):
            self._call(fn)

    def subscribe(self, fn):
        """Appelle fn() maintenant puis à chaque changement de couleurs. Un abonné dont le
        widget a été détruit est retiré automatiquement."""
        self._listeners.append(fn)
        self._call(fn)
        return fn

    def _call(self, fn):
        try:
            fn()
        except tk.TclError:                 # widget détruit
            if fn in self._listeners:
                self._listeners.remove(fn)


def merge(colors):
    """Couleurs par défaut, remplacées par celles de `colors` qui sont valides."""
    out = dict(DEFAULT_COLORS)
    for key, value in (colors or {}).items():
        if key not in DEFAULT_COLORS:
            continue
        value = normalize(value)
        if value or (value == "" and key in EMPTY_ALLOWED):
            out[key] = value
    return out


THEME = Theme()


def ensure_hex_tag(widget, tag):
    """Couleur donnée directement dans le fichier de protocole ("color": "#FF8800") :
    le tag du même nom est créé à la première utilisation (tk.Text ou ttk.Treeview)."""
    if tag and tag.startswith("#") and HEX.match(tag):
        widget.tag_configure(tag, foreground=tag)


_DATA_STYLE = []


def data_entry_style():
    """Style ttk des champs de saisie de DATA (octets bruts) : texte bleu, couleur des trames TX
    (suit la page « Couleurs… »). Retourne le nom du style, à passer à ttk.Entry(style=...)."""
    if not _DATA_STYLE:
        from tkinter import ttk
        style = ttk.Style()
        THEME.subscribe(lambda: style.configure("Data.TEntry", foreground=THEME.colors["tx"]))
        _DATA_STYLE.append(style)
    return "Data.TEntry"
