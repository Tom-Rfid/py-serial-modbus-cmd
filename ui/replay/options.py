"""
ui/replay/options.py — Rythme du replay et timeout de réponse.

    (•) Temps d'origine [x1]  ( ) Délai fixe [200] ms   Timeout [500] ms  [x] Comparer  [ ] Décoder

« Décoder » : une ligne cliquée dans le tableau est chargée dans l'onglet Protocole (TX dans la
Requête, RX dans la Réponse, cadre rempli sur fond gris foncé).
"""
import tkinter as tk
from tkinter import ttk

from core.trace import replay_delays

from .constants import SPEEDS
from ui.i18n import _
from ui.tooltip import ToolTip


class PlaybackOptions(ttk.Frame):
    def __init__(self, master, timeout_ms, on_change):
        """on_change() : rythme modifié (les délais affichés sont recalculés)."""
        super().__init__(master)
        self.mode = tk.StringVar(value="original")
        self.speed = tk.StringVar(value="x1")
        self.fixed_ms = tk.StringVar(value="200")
        self.timeout_var = tk.StringVar(value=str(int(timeout_ms)))
        self.compare = tk.BooleanVar(value=True)
        self.decode = tk.BooleanVar(value=False)
        self._build_rhythm(on_change)
        self._build_checks()

    def _build_rhythm(self, on_change):
        ttk.Radiobutton(self, text=_("Temps d'origine"), variable=self.mode, value="original",
                        command=on_change).pack(side="left")
        cb = ttk.Combobox(self, textvariable=self.speed, values=list(SPEEDS), state="readonly", width=5)
        cb.pack(side="left", padx=(4, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: on_change())
        ttk.Radiobutton(self, text=_("Délai fixe"), variable=self.mode, value="fixed",
                        command=on_change).pack(side="left")
        entry = ttk.Entry(self, textvariable=self.fixed_ms, width=5)
        entry.pack(side="left", padx=2)
        entry.bind("<FocusOut>", lambda e: on_change())
        entry.bind("<Return>", lambda e: on_change())
        ttk.Label(self, text="ms").pack(side="left")

    def _build_checks(self):
        # Timeout : délai max entre l'envoi d'une requête et sa réponse ; sert aussi
        # d'attente après la dernière requête, avant de conclure.
        ttk.Label(self, text="Timeout").pack(side="left", padx=(10, 2))
        ttk.Entry(self, textvariable=self.timeout_var, width=5).pack(side="left")
        ttk.Label(self, text="ms").pack(side="left", padx=(2, 10))
        ttk.Checkbutton(self, text=_("Comparer"), variable=self.compare).pack(side="left")
        decode = ttk.Checkbutton(self, text=_("Décoder"), variable=self.decode)
        decode.pack(side="left", padx=(10, 0))
        ToolTip(decode, _("Ligne cliquée chargée dans l'onglet Protocole : TX dans la Requête, RX dans la "
                          "Réponse (cadre sur fond gris foncé)"))

    # ------------------------------------------------------------------
    # Valeurs
    # ------------------------------------------------------------------
    def timeout_ms(self):
        """Timeout saisi (ms), 500 si la saisie est invalide."""
        return _number(self.timeout_var.get(), 500.0, minimum=1.0)

    def fixed_delay_ms(self):
        """Délai fixe saisi (ms) : sert aussi d'écart pour une ligne ajoutée (+ Ajouter)."""
        return _number(self.fixed_ms.get(), 200.0, minimum=0.0)

    def delays(self, ex_list):
        """Délai (ms) avant chaque envoi, selon le rythme choisi."""
        fixed = _number(self.fixed_ms.get(), 200.0, minimum=0.0)
        return replay_delays(ex_list, self.mode.get(), SPEEDS[self.speed.get()], fixed)


def _number(text, default, minimum):
    try:
        return max(minimum, float(text.replace(",", ".")))
    except ValueError:
        return default
