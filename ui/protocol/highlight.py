"""
ui/protocol/highlight.py — Mise en évidence d'un cadre de l'onglet Protocole.

Quand une ligne du Replay est chargée dans l'onglet Protocole (case « Décoder » du replay, ou
bouton « Décoder dans Protocole »), le cadre qui la reçoit — Requête (TX) ou Réponse (RX) —
passe sur le même fond gris foncé que le panneau Replay : on voit tout de suite lequel a été
rempli. Il revient en gris clair quand on choisit une nouvelle commande dans l'onglet.

    hl = BoxHighlight(cadre)
    hl.set(True)     # fond gris foncé
    hl.set(False)    # fond d'origine
"""
from tkinter import ttk

# Même gris que le panneau Replay (ui/replay/constants.py : PANEL_BG)
HIGHLIGHT_BG = "#c9ced5"

# Classes ttk dont on change le fond (les boutons, listes et tableaux gardent le leur)
TTK_CLASSES = ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe")
STYLE_PREFIX = "Decoded."


def setup_styles(widget):
    """Styles « Decoded.* » : fond HIGHLIGHT_BG (à appeler une fois, avant BoxHighlight.set)."""
    s = ttk.Style(widget)
    for cls in TTK_CLASSES:
        s.configure(STYLE_PREFIX + cls, background=HIGHLIGHT_BG)
    s.configure(STYLE_PREFIX + "TLabelframe.Label", background=HIGHLIGHT_BG)
    s.map(STYLE_PREFIX + "TCheckbutton", background=[("active", HIGHLIGHT_BG)])
    s.map(STYLE_PREFIX + "TRadiobutton", background=[("active", HIGHLIGHT_BG)])


class BoxHighlight:
    """Fond gris foncé (ou d'origine) sur un cadre et tous ses cadres, libellés et cases."""

    def __init__(self, box):
        self.box = box
        self.on = False
        self._saved = {}            # widget -> style ttk (ou fond tk) d'origine

    def set(self, on):
        """Active / désactive la mise en évidence (rien à faire si l'état ne change pas)."""
        if on == self.on:
            return
        self.on = on
        if on:
            self._saved.clear()
            self._apply(self.box)
        else:
            self._restore()

    # ------------------------------------------------------------------
    def _apply(self, widget):
        """Fond gris foncé sur widget puis, récursivement, sur ses enfants."""
        cls = widget.winfo_class()
        if cls in TTK_CLASSES:
            self._saved[widget] = ("style", str(widget.cget("style")))
            widget.configure(style=STYLE_PREFIX + cls)
        elif cls == "Text":                             # trame hexa (HexView) : widget tk
            self._saved[widget] = ("background", widget.cget("background"))
            widget.configure(background=HIGHLIGHT_BG)
        for child in widget.winfo_children():
            self._apply(child)

    def _restore(self):
        """Remet le style ou le fond d'origine de chaque widget modifié."""
        for widget, (option, value) in self._saved.items():
            try:
                widget.configure(**{option: value})
            except Exception:                           # widget détruit entre-temps
                pass
        self._saved.clear()
