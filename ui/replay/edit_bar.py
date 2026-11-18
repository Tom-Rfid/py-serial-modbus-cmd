"""
ui/replay/edit_bar.py — Barre d'édition de la trace et choix de la flèche « → Replay ».

    [+ Ajouter] [Supprimer] [Monter] [Descendre]   → : (•) insère après  ( ) remplace
"""
import tkinter as tk
from tkinter import ttk

from .constants import ARROW_INSERT, ARROW_REPLACE
from ui.i18n import _
from ui.tooltip import ToolTip


class EditBar(ttk.Frame):
    def __init__(self, master, on_add, on_delete, on_move):
        """on_move(step) : -1 = monter, +1 = descendre."""
        super().__init__(master)
        add_btn = ttk.Button(self, text=_("+ Ajouter"), command=on_add)
        add_btn.pack(side="left")
        ToolTip(add_btn, _("Ajoute une ligne TX après la sélection, « Délai fixe » ms après la ligne "
                           "du dessus (les lignes suivantes sont décalées d'autant)"))
        ttk.Button(self, text=_("Supprimer"), command=on_delete).pack(side="left", padx=4)
        ttk.Button(self, text=_("Monter"), command=lambda: on_move(-1)).pack(side="left")
        ttk.Button(self, text=_("Descendre"), command=lambda: on_move(1)).pack(side="left", padx=4)
        # Flèche « → Replay » des onglets Manuel et Protocole : insérer ou remplacer
        self.arrow = tk.StringVar(value=ARROW_INSERT)
        ttk.Label(self, text="→ :").pack(side="left", padx=(10, 2))
        self.insert_radio = ttk.Radiobutton(self, text=_("insère après"), variable=self.arrow, value=ARROW_INSERT)
        self.insert_radio.pack(side="left")
        ttk.Radiobutton(self, text=_("remplace"), variable=self.arrow, value=ARROW_REPLACE).pack(side="left")

    def arrow_mode(self):
        return self.arrow.get()
