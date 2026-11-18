"""
ui/app/layout.py — Disposition de la fenêtre et fermeture.

    - panneau Replay à droite des onglets, affiché par la case « ▶ Replay » :
      masqué, les onglets prennent toute la largeur ; affiché, la moitié
    - séparateurs, taille de la fenêtre et affichage du replay mémorisés (settings.json)
"""
import tkinter as tk
from tkinter import ttk

DEFAULT_GEOMETRY = "1720x920"   # taille de la fenêtre au premier lancement
TOP_SHARE = 0.74                # part de la hauteur pour les onglets (le reste : moniteur)
LIST_SHARE = 0.3               # onglet Manuel : part de la largeur pour la liste des messages
MIN_LIST = 150                 # onglet Manuel : largeur minimale de la liste des messages (px)
LAYOUT_VERSION = 3              # à augmenter quand la disposition par défaut change


def fix_treeview_tag_colors(root):
    """Corrige un défaut de Tk 8.6.9 (Python 3.8 sous Windows) : les couleurs des lignes
    de tableau (tags) ne s'affichent pas. Sans effet sur les versions corrigées."""
    style = ttk.Style(root)

    def fixed(option):
        return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]

    style.map("Treeview", foreground=fixed("foreground"), background=fixed("background"))


class LayoutMixin:
    # ------------------------------------------------------------------
    # Panneau Replay
    # ------------------------------------------------------------------
    def show_replay(self, visible):
        """Affiche (moitié droite) ou masque le panneau Replay."""
        visible = bool(visible)
        self.replay_var.set(visible)
        shown = str(self.replay) in self.top.panes()
        if visible and not shown:
            self.top.add(self.replay, weight=1)
            # Le séparateur ne peut être posé qu'une fois le panneau placé par Tk
            self.after(60, self._place_replay_sash)
        elif not visible and shown:
            self._remember_replay_sash()
            self.top.forget(self.replay)
        self.settings["replay_visible"] = visible

    def _place_replay_sash(self):
        """Séparateur onglets / replay : position mémorisée, sinon le milieu."""
        self.update_idletasks()
        width = self.top.winfo_width()
        saved = (self.settings["sashes"] or {}).get("replay")
        pos = saved if saved and 200 < saved < width - 200 else width // 2
        try:
            self.top.sashpos(0, pos)
        except tk.TclError:
            pass

    def _remember_replay_sash(self):
        try:
            pos = self.top.sashpos(0)
        except tk.TclError:
            return
        if pos > 200:
            sashes = dict(self.settings["sashes"] or {})
            sashes["replay"] = pos
            self.settings["sashes"] = sashes

    # ------------------------------------------------------------------
    # Séparateurs
    # ------------------------------------------------------------------
    def reset_old_layout(self):
        """Taille et séparateurs mémorisés par une version à l'ancienne disposition : oubliés,
        pour que la nouvelle disposition par défaut s'applique (une seule fois)."""
        if int(self.settings.get("layout_version") or 0) < LAYOUT_VERSION:
            self.settings["geometry"] = ""
            self.settings["zoomed"] = False
            self.settings["sashes"] = {}
            self.settings["layout_version"] = LAYOUT_VERSION

    def restore_layout(self):
        """Remet les séparateurs du dernier lancement (premier lancement : TOP_SHARE en haut)."""
        self.update_idletasks()
        sashes = self.settings["sashes"] or {}
        if self.settings.get("zoomed"):
            try:
                self.state("zoomed")            # fenêtre maximisée (Windows)
            except tk.TclError:
                pass
            self.update_idletasks()
        try:
            self.body.sashpos(0, sashes.get("body") or int(self.body.winfo_height() * TOP_SHARE))
        except tk.TclError:
            pass
        if self.settings["replay_visible"]:
            self.show_replay(True)
        # Séparateur de l'onglet Protocole : posé à son premier affichage (un onglet
        # caché n'a pas encore de taille, le séparateur y serait remis à 0)
        self._proto_sash_done = False
        self._upper_sash_done = False
        self.tabs.bind("<<NotebookTabChanged>>", lambda e: self._restore_tab_sashes(), add="+")
        self._restore_tab_sashes()

    def _restore_tab_sashes(self):
        self._restore_protocol_sash()
        self._restore_upper_sash()

    def _restore_upper_sash(self):
        """Séparateur de l'onglet Manuel (liste des messages | paramètres), posé à son premier
        affichage : onglet caché au lancement (Protocole d'abord), il n'a pas encore de largeur
        et la liste des messages serait réduite à rien."""
        if self._upper_sash_done or self.tabs.select() != str(self.upper):
            return
        self._upper_sash_done = True

        def place():
            saved = (self.settings["sashes"] or {}).get("upper")
            width = self.upper.winfo_width()
            try:
                self.upper.sashpos(0, saved if saved and MIN_LIST < saved < width - MIN_LIST
                                   else max(MIN_LIST, int(width * LIST_SHARE)))
            except tk.TclError:
                pass
        self.after_idle(place)

    def _restore_protocol_sash(self):
        """Séparateur Requête / Réponse de l'onglet Protocole : placé d'après la hauteur des deux
        tableaux (ProtocolPanel._fit_panes), à son premier affichage ; plus mémorisé."""
        if self._proto_sash_done or self.tabs.select() != str(self.protocol_panel):
            return
        self._proto_sash_done = True
        self.protocol_panel._fit_panes()

    def save_layout(self):
        """Mémorise la taille de la fenêtre et la position des séparateurs."""
        try:
            zoomed = self.state() == "zoomed"
            self.settings["zoomed"] = zoomed
            if not zoomed:
                self.settings["geometry"] = self.geometry()
            sashes = dict(self.settings["sashes"] or {})   # zone jamais affichée : valeur gardée
            sashes["body"] = self.body.sashpos(0)
            if getattr(self, "_upper_sash_done", False) and self.upper.sashpos(0) > MIN_LIST:
                sashes["upper"] = self.upper.sashpos(0)     # onglet Manuel affiché : largeur réelle
            self.settings["sashes"] = sashes
            if self.replay_var.get():
                self._remember_replay_sash()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Réglages du moniteur et fermeture
    # ------------------------------------------------------------------
    def set_decode(self, enabled):
        """Case « Décoder protocole » du moniteur."""
        self.settings["decode_protocol"] = enabled

    def set_gap(self, ms):
        """Délai de fin de trame modifié dans le moniteur."""
        self.link.gap_ms = ms
        self.settings["gap_ms"] = ms

    def on_close(self):
        """Fermeture : trace modifiée à enregistrer ?, disposition, réglages, trace en cours, port."""
        if not self.replay.confirm_discard():      # « Annuler » : on ne ferme pas
            return
        self.replay.stop()
        self.save_layout()
        self.settings.save()
        if self.recorder:
            self.recorder.close()
        self.link.disconnect()
        self.destroy()
