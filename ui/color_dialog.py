"""
ui/color_dialog.py — Page « Couleurs » : réglage des couleurs du moniteur et des champs.

Pour chaque couleur :

    Trames envoyées (TX)   [■■■]  [#1F5FBF]  [Palette…]  [Défaut]

    - l'échantillon montre la couleur choisie (clic dessus = palette)
    - le code hexa se tape directement (#RRGGBB, ou RRGGBB) ; rouge tant qu'il est invalide
    - « Palette… » ouvre le sélecteur de couleur du système
    - « Défaut » remet la couleur d'origine

L'aperçu en bas montre des trames typiques avec les couleurs en cours de réglage.
« Appliquer » met à jour toute l'interface ; « OK » applique et ferme ; les couleurs
sont mémorisées dans settings.json.
"""
import tkinter as tk
from tkinter import colorchooser, ttk

from ui.hexview import apply_field_colors, hex_chunks
from ui.theme import DEFAULT_COLORS, EMPTY_ALLOWED, GROUPS, THEME, normalize
from ui.i18n import _

MONO = ("Consolas", 10)
RED = "#C0392B"

# Aperçu : (tag de ligne, texte avant, octets, segments, texte après)
PREVIEW = [
    ("TX", "TX [  7]  ", "A5 5A 05 00 10 00 64", [(0, 3, "hdr"), (3, 2, "cmd"), (6, 1, "crc")],
     _("   « requête #0x05 · Lire l'état »")),
    ("RX", "RX [  9]  ", "A5 5A 05 00 01 B9 01 F1 D1", [(0, 3, "hdr"), (3, 1, "perr_ok"), (5, 1, "crc"), (7, 2, "crc")],
     _("   => état = marche (1)")),
    ("RX", "RX [  6]  ", "A5 5A 06 02 00 28", [(0, 3, "hdr"), (3, 1, "perr_ko"), (5, 1, "err")],
     _("   CRC faux, erreur 2")),
    ("TX", "TX [  8]  ", "7E 00 00 05 09 01 AA 2D", [(0, 1, "hdr"), (1, 2, "na"), (7, 1, "crc")],
     _("   octets non lus")),
    ("INFO", "", "", [], _("Protocole : Modbus RTU (modbus_rtu.json)")),
    ("ERR", "", "", [], _("TIMEOUT : pas de réponse en 500 ms")),
]


class ColorDialog(tk.Toplevel):
    def __init__(self, master, on_apply):
        """on_apply(couleurs) : appelée par Appliquer / OK avec le dict {clé: "#RRGGBB"}."""
        super().__init__(master)
        self.title(_("SerialHex — Couleurs"))
        self.transient(master)
        self.resizable(False, False)
        self.on_apply = on_apply
        self.colors = dict(THEME.colors)        # couleurs en cours de réglage
        self.vars, self.swatches, self.entries = {}, {}, {}
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        for row, (title, items) in enumerate(GROUPS):
            self._build_group(body, title, items).grid(row=row, column=0, sticky="we", pady=(0, 8))
        self._build_preview(body).grid(row=len(GROUPS), column=0, sticky="we")
        self._build_buttons(body).grid(row=len(GROUPS) + 1, column=0, sticky="e", pady=(10, 0))
        self._refresh_preview()
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_group(self, parent, title, items):
        box = ttk.LabelFrame(parent, text=title, padding=6)
        for row, (key, label) in enumerate(items):
            self._build_row(box, row, key, label)
        return box

    def _build_row(self, box, row, key, label):
        """Une couleur : libellé, échantillon, code hexa, Palette…, Défaut."""
        ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
        swatch = tk.Label(box, width=6, relief="solid", borderwidth=1, cursor="hand2")
        swatch.grid(row=row, column=1, padx=(0, 6))
        swatch.bind("<Button-1>", lambda e, k=key: self._pick(k))
        var = tk.StringVar(value=self.colors[key])
        entry = tk.Entry(box, textvariable=var, width=10, font=MONO)
        entry.default_fg = entry.cget("foreground")         # couleur normale du texte
        entry.grid(row=row, column=2, padx=(0, 6))
        var.trace_add("write", lambda *_, k=key: self._on_typed(k))
        ttk.Button(box, text=_("Palette…"), command=lambda k=key: self._pick(k)).grid(row=row, column=3, padx=(0, 4))
        ttk.Button(box, text=_("Défaut"), command=lambda k=key: self.vars[k].set(DEFAULT_COLORS[k])).grid(row=row, column=4)
        self.vars[key], self.swatches[key], self.entries[key] = var, swatch, entry
        self._show_swatch(key)

    def _build_preview(self, parent):
        box = ttk.LabelFrame(parent, text=_("Aperçu"), padding=6)
        self.preview = tk.Text(box, height=len(PREVIEW), width=76, font=MONO, borderwidth=0,
                               highlightthickness=0, state="disabled", wrap="none")
        self.preview.pack(fill="x")
        return box

    def _build_buttons(self, parent):
        bar = ttk.Frame(parent)
        ttk.Button(bar, text=_("Tout par défaut"), command=self._all_defaults).pack(side="left", padx=(0, 20))
        ttk.Button(bar, text=_("Annuler"), command=self.destroy).pack(side="left")
        ttk.Button(bar, text=_("Appliquer"), command=self.apply).pack(side="left", padx=4)
        ttk.Button(bar, text="OK", command=self._ok).pack(side="left")
        return bar

    # ------------------------------------------------------------------
    # Saisie
    # ------------------------------------------------------------------
    def _on_typed(self, key):
        """Code hexa modifié : accepté s'il est valide (vide permis pour « cmd »)."""
        value = normalize(self.vars[key].get())
        valid = value is not None and (value != "" or key in EMPTY_ALLOWED)
        entry = self.entries[key]
        entry.config(foreground=entry.default_fg if valid else RED)
        if valid:
            self.colors[key] = value
            self._show_swatch(key)
            self._refresh_preview()

    def _pick(self, key):
        """Palette du système, ouverte sur la couleur actuelle."""
        current = self.colors[key] or THEME.get("tx")
        _rgb, chosen = colorchooser.askcolor(color=current, parent=self, title=_("Choisir une couleur"))
        if chosen:
            self.vars[key].set(chosen.upper())

    def _show_swatch(self, key):
        color = self.colors[key]
        if color:
            self.swatches[key].config(background=color, text="")
        else:
            self.swatches[key].config(background=self.cget("background"), text=_("ligne"))

    def _all_defaults(self):
        for key, value in DEFAULT_COLORS.items():
            self.vars[key].set(value)

    # ------------------------------------------------------------------
    # Aperçu et validation
    # ------------------------------------------------------------------
    def _refresh_preview(self):
        """Trames d'exemple, colorées avec les couleurs en cours de réglage."""
        text = self.preview
        for tag, key in (("TX", "tx"), ("RX", "rx"), ("INFO", "info"), ("ERR", "error")):
            text.tag_configure(tag, foreground=self.colors[key])
        apply_field_colors(text, MONO, self.colors)
        text.configure(state="normal")
        text.delete("1.0", "end")
        for line_tag, before, hexa, segments, after in PREVIEW:
            text.insert("end", before, (line_tag,))
            if hexa:
                for chunk, tags in hex_chunks(bytes.fromhex(hexa), segments, (line_tag,)):
                    text.insert("end", chunk, tags)
            text.insert("end", after + "\n", (line_tag,))
        text.configure(state="disabled")

    def apply(self):
        self.on_apply(dict(self.colors))

    def _ok(self):
        self.apply()
        self.destroy()
