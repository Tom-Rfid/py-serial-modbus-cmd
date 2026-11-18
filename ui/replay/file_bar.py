"""
ui/replay/file_bar.py — Barre « fichier » du panneau Replay.

    [Ouvrir…] [Nouvelle]  Nom : [essai______] .csv *  [Enregistrer] [Enregistrer sous…]

Le nom se modifie directement : « Enregistrer » (ou Entrée) enregistre sous ce nom,
en renommant le fichier ; le panneau demande avant de remplacer un fichier existant.
Le « * » signale des modifications non enregistrées.
"""
import tkinter as tk
from tkinter import ttk

from .constants import GREY, RED
from ui.i18n import _


class FileBar(ttk.Frame):
    def __init__(self, master, on_open, on_new, on_save, on_save_as):
        """on_save() lit le nom saisi avec name() ; les autres rappels n'ont pas d'argument."""
        super().__init__(master)
        ttk.Button(self, text=_("Ouvrir…"), command=on_open).pack(side="left")
        ttk.Button(self, text=_("Nouvelle"), command=on_new).pack(side="left", padx=(4, 10))
        ttk.Label(self, text=_("Nom")).pack(side="left")
        self.name_var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.name_var, width=24)
        entry.pack(side="left", padx=(4, 0), fill="x", expand=True)
        entry.bind("<Return>", lambda e: on_save())
        ttk.Label(self, text=".csv", foreground=GREY).pack(side="left")
        self.star = ttk.Label(self, text="", foreground=RED, width=2)
        self.star.pack(side="left")
        ttk.Button(self, text=_("Enregistrer"), command=on_save).pack(side="left", padx=(4, 0))
        ttk.Button(self, text=_("Enregistrer sous…"), command=on_save_as).pack(side="left", padx=4)

    def name(self):
        return self.name_var.get()

    def show(self, name, modified):
        """Nom du fichier ouvert (sans .csv) et indicateur de modification."""
        self.name_var.set(name)
        self.set_modified(modified)

    def set_modified(self, modified):
        self.star.config(text="*" if modified else "")
