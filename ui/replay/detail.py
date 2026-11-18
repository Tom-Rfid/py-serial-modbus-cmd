"""
ui/replay/detail.py — Détail de la ligne sélectionnée (aide à la relecture d'une trame).

    Ligne 3 · TX · t 629.1 ms · depuis la précédente 227.0 ms · jusqu'à la suivante 62.3 ms   [Décoder dans Protocole]
    53 01 07 00 00 00 00 00 14 55        (couleurs du protocole)
    « requête #0x01 · Lire mesures · 4 o · CRC OK »  => valeurs converties
"""
from tkinter import ttk

from ui.hexview import HexView

from .constants import GREY
from ui.i18n import _, tr


class RowDetail(ttk.LabelFrame):
    def __init__(self, master, describe, style, on_decode):
        """
        describe(dir, data) -> (résumé ou [(morceau, ok)], [(valeur, ok)]) ou None : décodage du protocole
        style(dir, data)    -> segments de couleur, ou None
        on_decode(dir, data): bouton « Décoder dans Protocole »
        """
        super().__init__(master, text=_("Ligne sélectionnée"), padding=4)
        self.describe, self.style, self.on_decode = describe, style, on_decode
        self._current = None                    # (direction, octets) de la ligne affichée
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.info = ttk.Label(top, text="", foreground=GREY, wraplength=420, justify="left")
        self.info.pack(side="left")
        self.decode_btn = ttk.Button(top, text=_("Décoder dans Protocole"), command=self._decode)
        self.decode_btn.pack(side="right")
        self.hex = HexView(self, height=1)
        self.hex.pack(fill="x", pady=(2, 0))
        self.summary = ttk.Label(self, text="", wraplength=560, justify="left")
        self.summary.pack(fill="x")
        self.clear()

    def clear(self):
        self._current = None
        self.info.config(text=_("Cliquer une ligne : intervalle avec les lignes voisines et décodage"))
        self.hex.clear()
        self.summary.config(text="")
        self.decode_btn.state(["disabled"])

    def show(self, row, event, gaps):
        """row : position ; event : TraceEvent ; gaps : (écart au-dessus, écart au-dessous) en ms."""
        self._current = (event.direction, event.data)
        self.info.config(text=self._info_text(row, event, gaps))
        self.hex.show(event.data, self.style(event.direction, event.data) or [], _("   ({0} octets)").format(len(event.data)))
        self.summary.config(text=self._summary_text(event))
        self.decode_btn.state(["!disabled"])

    @staticmethod
    def _info_text(row, event, gaps):
        above, below = gaps
        parts = [_("Ligne {0}").format(row + 1), event.direction, _("t {0:.1f} ms").format(event.t_ms)]
        parts.append(_("depuis la précédente {0:.1f} ms").format(above) if above is not None else _("première ligne"))
        parts.append(_("jusqu'à la suivante {0:.1f} ms").format(below) if below is not None else _("dernière ligne"))
        if event.label:
            parts.append(event.label)
        return " · ".join(parts)

    def _summary_text(self, event):
        result = self.describe(event.direction, event.data)
        if not result:
            return _("(pas une trame du protocole en cours)")
        text, values = result if isinstance(result, tuple) else (result, [])
        if not isinstance(text, str):                   # morceaux [(texte, ok)]
            text = " · ".join(part for part, _ok in text)
        text = tr(text)
        if values:
            text += "   => " + "  |  ".join(v for v, _ in values)
        return text

    def _decode(self):
        if self._current:
            self.on_decode(*self._current)
