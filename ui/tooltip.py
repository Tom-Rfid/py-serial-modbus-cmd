"""
ui/tooltip.py — Infobulle : petit texte affiché quand la souris reste sur un widget.

    ToolTip(widget, _("auto req_id : REQUEST ID +1 après chaque envoi"))
"""
import tkinter as tk


class ToolTip:
    DELAY_MS = 400                      # attente avant d'afficher l'infobulle

    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self._job = None
        self._win = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        self._job = None
        if self._win is not None or not self.widget.winfo_ismapped():
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._win = win = tk.Toplevel(self.widget)
        win.wm_overrideredirect(True)          # sans barre de titre
        win.wm_geometry(f"+{x}+{y}")
        tk.Label(win, text=self.text, background="#FFFFE0", relief="solid", borderwidth=1,
                 padx=6, pady=2, justify="left").pack()

    def _hide(self, _event=None):
        self._cancel()
        if self._win is not None:
            self._win.destroy()
            self._win = None
