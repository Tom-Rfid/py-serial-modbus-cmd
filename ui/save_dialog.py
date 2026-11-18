"""
ui/save_dialog.py — Fenêtre « Sauvegarder le message » : nom du message, et nom du fichier
proposé (Msg_<nom>.json) affiché en direct pendant la saisie.

    name = ask_message_name(parent, "Set access level")    # None si annulé
    file_name_for(name)                                     # 'Msg_Set_access_level.json'

Le fichier proposé est ensuite pré-rempli dans l'explorateur « Enregistrer sous », où on
peut encore le changer.
"""
import tkinter as tk
from tkinter import ttk

from core.request_message import file_name_for
from ui.i18n import _


class _NameDialog(tk.Toplevel):
    def __init__(self, parent, initial):
        super().__init__(parent)
        self.title(_("Sauvegarder le message"))
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=_("Nom du message (onglet Manuel) :")).grid(row=0, column=0, columnspan=3, sticky="w")
        self.var = tk.StringVar(value=initial)
        entry = ttk.Entry(body, textvariable=self.var, width=48)
        entry.grid(row=1, column=0, columnspan=3, sticky="we", pady=(2, 6))
        ttk.Label(body, text=_("Fichier proposé :")).grid(row=2, column=0, sticky="w")
        self.file_lbl = ttk.Label(body, font=("Consolas", 10))
        self.file_lbl.grid(row=2, column=1, columnspan=2, sticky="w", padx=(4, 0))
        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=3, sticky="e", pady=(10, 0))
        self.ok_btn = ttk.Button(buttons, text="OK", command=self._ok)
        self.ok_btn.pack(side="left", padx=4)
        ttk.Button(buttons, text=_("Annuler"), command=self.destroy).pack(side="left")
        self.var.trace_add("write", lambda *_: self._update())
        self._update()
        entry.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        entry.focus_set()
        entry.select_range(0, "end")
        self._center(parent.winfo_toplevel())

    def _center(self, top):
        """Fenêtre placée au centre de la fenêtre principale."""
        self.update_idletasks()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_reqwidth()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _update(self):
        """Nom du fichier en direct ; OK grisé tant que le nom est vide."""
        name = self.var.get().strip()
        self.file_lbl.config(text=file_name_for(name) if name else "")
        self.ok_btn.state(["!disabled"] if name else ["disabled"])

    def _ok(self):
        if self.var.get().strip():
            self.result = self.var.get().strip()
            self.destroy()


def ask_message_name(parent, initial=""):
    """Demande le nom du message (fenêtre modale). Retourne le nom, ou None si annulé."""
    dlg = _NameDialog(parent, initial)
    dlg.grab_set()
    parent.wait_window(dlg)
    return dlg.result
