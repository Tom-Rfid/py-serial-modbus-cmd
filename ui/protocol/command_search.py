"""
ui/protocol/command_search.py — Liste « CMD TX » : recherche en tapant et commandes favorites.

Recherche
    - un clic dans le champ sélectionne tout le texte : on tape directement la recherche ;
    - la liste des propositions s'ouvre sous le champ dès la première lettre (le curseur reste
      dans le champ) : ↑ / ↓ pour s'y déplacer, Entrée ou clic pour choisir ;
    - champ vidé : toutes les commandes sont proposées ; en quittant le champ (ou Échap), la
      commande en cours réapparaît ;
    - mots cherchés dans le nom, la catégorie et le COMMAND ID (« 0x1E » trouve 0x0000001E et
      son Set 0x8000001E) ; points et _ ignorés (« gdd » trouve « G.D.D. »).
Favoris
    - bouton ☆ / ★ à droite de la liste : ajoute / retire la commande en cours des favoris ;
    - sous CMD TX, liste des favoris (3 lignes visibles, défilement au-delà), affichée s'il y en
      a au moins un : un clic choisit la commande ;
    - mémorisés dans settings.json ("favorite_commands"), par protocole.
"""
import tkinter as tk
from tkinter import ttk

from .constants import MANUAL
from ui.i18n import _

MAX_SUGGESTIONS = 12        # lignes visibles de la liste des propositions
FAVORITES_VISIBLE = 3       # lignes visibles de la liste des favoris


class CommandSearchMixin:
    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_search(self, row, box):
        """Bindings de la liste CMD TX, bouton ☆, liste des propositions et liste des favoris."""
        cb = self.cmd_cb
        cb.bind("<<ComboboxSelected>>", lambda e: self._pick_command(self.cmd_choice.get()))
        cb.bind("<KeyRelease>", self._filter_commands)
        cb.bind("<Return>", lambda e: self._pick_first())
        cb.bind("<KP_Enter>", lambda e: self._pick_first())
        cb.bind("<Escape>", lambda e: self._restore_command())
        cb.bind("<Down>", lambda e: self._move_suggestion(1))
        cb.bind("<Up>", lambda e: self._move_suggestion(-1))
        cb.bind("<FocusIn>", lambda e: self.after_idle(self._select_all))
        cb.bind("<FocusOut>", lambda e: self.after(150, self._focus_left))
        self._cmd_labels = [MANUAL]     # liste complète (le menu peut être filtré)
        self._cmd_current = MANUAL      # commande choisie (réaffichée quand on quitte la saisie)

        # Bouton favori, juste à droite de la liste
        self.fav_btn = ttk.Button(row, text="☆", width=3, command=self._toggle_favorite)
        self.fav_btn.pack(side="left", padx=(4, 0), after=cb)

        # Propositions : liste posée sous le champ, par-dessus le reste (place)
        self._suggest = tk.Listbox(self, height=MAX_SUGGESTIONS, activestyle="dotbox", exportselection=False,
                                   takefocus=0, relief="solid", borderwidth=1)
        self._suggest.bind("<ButtonRelease-1>", lambda e: self._pick_suggestion())
        self._suggest_items = []

        # Favoris : sous CMD TX, 3 lignes visibles, défilement au-delà ; masqués s'il n'y en a pas
        self.fav_row = ttk.Frame(box)
        ttk.Label(self.fav_row, text=_("Favoris"), width=12).pack(side="left", anchor="n")
        frame = ttk.Frame(self.fav_row)
        frame.pack(side="left", fill="x", expand=True)
        self.fav_list = tk.Listbox(frame, height=FAVORITES_VISIBLE, exportselection=False, activestyle="none")
        self.fav_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.fav_list.yview)
        self.fav_list.configure(yscrollcommand=self.fav_scroll.set)
        self.fav_list.pack(side="left", fill="x", expand=True)
        self.fav_list.bind("<<ListboxSelect>>", lambda e: self._pick_favorite())
        self._fav_anchor = row          # la ligne des favoris se place juste après CMD TX

    # ------------------------------------------------------------------
    # Liste complète, filtre
    # ------------------------------------------------------------------
    def set_command_labels(self, labels):
        """Liste complète des commandes ([MANUAL] + libellés), menu non filtré."""
        self._cmd_labels = list(labels)
        self.cmd_cb["values"] = self._cmd_labels
        self._refresh_favorites()

    def _matches(self, label, words):
        """Tous les mots tapés se trouvent dans le libellé ; un mot « 0x… » est comparé au
        COMMAND ID (0x1E trouve 0x0000001E et son Set 0x8000001E)."""
        text = label.lower()
        compact = text.replace(".", "").replace("_", " ").replace("-", " ")     # « gdd » trouve « G.D.D. »
        cmd = self.lib.by_label(label) if label != MANUAL else None
        for w in words:
            if w.startswith("0x") and cmd is not None:
                try:
                    value = int(w, 16)
                except ValueError:
                    return False
                if value not in (cmd.id, cmd.id & 0x7FFFFFFF):
                    return False
            elif w not in text and w not in compact:
                return False
        return True

    def _filtered(self):
        words = self.cmd_choice.get().lower().split()
        if not words or self.cmd_choice.get() in self._cmd_labels:
            return list(self._cmd_labels)
        return [l for l in self._cmd_labels if self._matches(l, words)]

    def _filter_commands(self, event):
        """Saisie dans la liste : propositions filtrées, ouvertes sous le champ."""
        if event.keysym in ("Return", "KP_Enter", "Escape", "Tab", "Up", "Down", "Left", "Right",
                            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        found = self._filtered()
        self.cmd_cb["values"] = found or [_("(aucune commande)")]
        self._show_suggestions(found)

    def _select_all(self):
        """Clic dans le champ : tout le texte sélectionné, la frappe le remplace."""
        if str(self.tk.call("focus")) == str(self.cmd_cb):
            self.cmd_cb.selection_range(0, "end")
            self.cmd_cb.icursor("end")

    # ------------------------------------------------------------------
    # Propositions
    # ------------------------------------------------------------------
    def _show_suggestions(self, labels):
        lb = self._suggest
        self._suggest_items = list(labels)
        lb.delete(0, "end")
        for label in labels or [_("(aucune commande)")]:
            lb.insert("end", label)
        lb.configure(height=min(MAX_SUGGESTIONS, max(1, len(labels))))
        if labels:
            lb.selection_set(0)
            lb.activate(0)
        lb.place(in_=self.cmd_cb, x=0, rely=1.0, relwidth=1.0)
        lb.lift()

    def _hide_suggestions(self):
        self._suggest.place_forget()
        self._suggest_items = []

    def _move_suggestion(self, step):
        """↑ / ↓ : déplacement dans les propositions (le curseur reste dans le champ)."""
        if not self._suggest_items:
            self._show_suggestions(self._filtered())
            return "break"
        lb = self._suggest
        current = lb.curselection()
        i = (current[0] if current else -1) + step
        i = max(0, min(len(self._suggest_items) - 1, i))
        lb.selection_clear(0, "end")
        lb.selection_set(i)
        lb.activate(i)
        lb.see(i)
        return "break"

    def _pick_suggestion(self):
        sel = self._suggest.curselection()
        if sel and self._suggest_items:
            self._pick_command(self._suggest_items[sel[0]])

    def _pick_first(self):
        """Entrée : la proposition en surbrillance, sinon la première de la liste filtrée."""
        sel = self._suggest.curselection()
        if self._suggest_items and sel:
            self._pick_command(self._suggest_items[sel[0]])
            return "break"
        found = [l for l in self._filtered() if l in self._cmd_labels]
        if found:
            self._pick_command(found[0])
        else:
            self._restore_command()
        return "break"

    def _pick_command(self, label):
        """Commande choisie (liste, proposition, favori, Entrée) ; menu complet rétabli."""
        self._hide_suggestions()
        if label not in self._cmd_labels:
            self._restore_command()
            return
        self.cmd_cb["values"] = self._cmd_labels
        self.cmd_choice.set(label)
        self.cmd_cb.icursor("end")
        self.cmd_cb.selection_clear()
        self._on_command()

    def _restore_command(self):
        """Échap ou sortie du champ (vide ou non choisi) : la commande en cours réapparaît."""
        self._hide_suggestions()
        self.cmd_cb["values"] = self._cmd_labels
        if self.cmd_choice.get() != self._cmd_current:
            self.cmd_choice.set(self._cmd_current)

    def _focus_left(self):
        """Sortie du champ : ignorée si le focus est passé au menu déroulant ou aux propositions."""
        focus = str(self.tk.call("focus"))  # chemin Tk : le menu déroulant n'est pas un widget tkinter
        if not focus.startswith(str(self.cmd_cb)) and not focus.startswith(str(self._suggest)):
            self._restore_command()

    # ------------------------------------------------------------------
    # Favoris
    # ------------------------------------------------------------------
    def _favorites(self):
        """Favoris du protocole en cours (libellés), dans l'ordre d'ajout."""
        store = self.settings.get("favorite_commands") or {}
        return list(store.get(self.proto.name, []))

    def _save_favorites(self, labels):
        store = dict(self.settings.get("favorite_commands") or {})
        store[self.proto.name] = labels
        self.settings["favorite_commands"] = store
        self.settings.save()

    def _toggle_favorite(self):
        """☆ / ★ : la commande en cours entre dans les favoris, ou en sort."""
        if self.cmd is None:
            return
        favs = self._favorites()
        label = self.cmd.label
        if label in favs:
            favs.remove(label)
        else:
            favs.append(label)
        self._save_favorites(favs)
        self._refresh_favorites()

    def _refresh_favorites(self):
        """Liste des favoris (seulement ceux du protocole en cours qui existent encore) et ☆ / ★."""
        favs = [l for l in self._favorites() if l in self._cmd_labels]
        self.fav_list.delete(0, "end")
        for label in favs:
            self.fav_list.insert("end", label)
        self.fav_list.configure(height=max(1, min(FAVORITES_VISIBLE, len(favs))))
        if len(favs) > FAVORITES_VISIBLE:
            self.fav_scroll.pack(side="right", fill="y")
        else:
            self.fav_scroll.pack_forget()
        if favs and not self.fav_row.winfo_manager():
            self.fav_row.pack(fill="x", pady=(4, 0), after=self._fav_anchor)
        elif not favs and self.fav_row.winfo_manager():
            self.fav_row.pack_forget()
        current = self.cmd.label if self.cmd is not None else None
        self.fav_btn.config(text="★" if current in favs else "☆")
        self.fav_btn.state(["!disabled"] if self.cmd is not None else ["disabled"])
        if current in favs:
            i = favs.index(current)
            self.fav_list.selection_clear(0, "end")
            self.fav_list.selection_set(i)
            self.fav_list.see(i)

    def _pick_favorite(self):
        sel = self.fav_list.curselection()
        if sel:
            label = self.fav_list.get(sel[0])
            if label != self._cmd_current:
                self._pick_command(label)
