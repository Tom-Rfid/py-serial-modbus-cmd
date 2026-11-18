"""
ui/replay/table.py — Tableau de la trace : une ligne par ligne du fichier, cellules modifiables.

    - TX en bleu, RX en violet (couleurs du moniteur, réglables) ; fond orange / rouge / jaune selon le résultat
    - double-clic sur t, Dir, Octets ou Libellé : champ de saisie par-dessus la cellule
      (Entrée valide, Échap annule ; une saisie refusée laisse le champ ouvert)
"""
from tkinter import ttk

from core.frames import to_hex

from ui.theme import THEME

from .constants import COLUMNS, COL_KEYS, EDITABLE


class TraceTable(ttk.Frame):
    def __init__(self, master, on_edit, on_select, on_delete_key):
        """
        on_edit(row, key, text) -> message d'erreur ou None : une saisie est validée
        on_select(rows)         : la sélection a changé
        on_delete_key()         : touche Suppr
        """
        super().__init__(master)
        self.on_edit = on_edit
        self._editor = None
        self.tree = self._build_tree()
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(self.selected_rows()))
        self.tree.bind("<Delete>", lambda e: on_delete_key())

    def _build_tree(self):
        tree = ttk.Treeview(self, columns=COL_KEYS, show="headings", selectmode="extended")
        for key, title, width, _editable in COLUMNS:
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=20, anchor="center" if key == "icon" else "w",
                        stretch=key in ("hex", "res"))
        vsb = ttk.Scrollbar(self, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        # Texte : direction. Fond : résultat, ou ligne en cours.
        THEME.subscribe(lambda: (tree.tag_configure("TX", foreground=THEME.get("tx")),
                                 tree.tag_configure("RX", foreground=THEME.get("rx"))))
        tree.tag_configure("diff", background="#ffcc80")        # différent : orange
        tree.tag_configure("timeout", background="#f5a3a3")     # timeout : rouge
        tree.tag_configure("extra", background="#fff2b3")       # réponse en trop : jaune
        tree.tag_configure("current", background="#d6e6fb")     # en cours d'envoi
        return tree

    # ------------------------------------------------------------------
    # Contenu
    # ------------------------------------------------------------------
    def fill(self, events, select=None):
        """Réaffiche toutes les lignes. select : positions à sélectionner ensuite."""
        self.close_editor()
        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(events):
            self.tree.insert("", "end", iid=str(i), tags=(e.direction,), values=(
                "", i + 1, f"{e.t_ms:.1f}", e.direction, to_hex(e.data), e.label, "", "", "", ""))
        if select:
            self.select([i for i in select if 0 <= i < len(events)])

    def set(self, row, key, value):
        self.tree.set(str(row), key, value)

    def mark(self, row, direction, background=None):
        """Couleur d'une ligne : texte selon la direction, fond éventuel (diff, timeout, extra, current)."""
        self.tree.item(str(row), tags=(direction,) + ((background,) if background else ()))

    def select(self, rows):
        items = [str(r) for r in rows]
        self.tree.selection_set(items)
        if items:
            self.tree.see(items[0])

    def selected_rows(self):
        return sorted(int(i) for i in self.tree.selection())

    def see(self, row):
        self.tree.see(str(row))

    # ------------------------------------------------------------------
    # Saisie dans une cellule
    # ------------------------------------------------------------------
    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        key = COL_KEYS[int(self.tree.identify_column(event.x)[1:]) - 1]
        if row and key in EDITABLE:
            self.edit_cell(int(row), key)

    def edit_cell(self, row, key):
        """Ouvre un champ de saisie par-dessus la cellule."""
        self.close_editor()
        self.tree.see(str(row))
        self.update_idletasks()
        bbox = self.tree.bbox(str(row), key)
        if not bbox:
            return
        x, y, w, h = bbox
        editor = self._make_editor(row, key, self.tree.set(str(row), key))
        editor.place(x=x, y=y, width=max(w, 60), height=h)
        editor.focus_set()
        for sequence in ("<Return>", "<KP_Enter>", "<FocusOut>"):
            editor.bind(sequence, lambda e: self._commit(row, key))
        editor.bind("<Escape>", lambda e: self.close_editor())
        self._editor = editor

    def _make_editor(self, row, key, value):
        if key == "dir":
            editor = ttk.Combobox(self.tree, values=("TX", "RX"), state="readonly")
            editor.set(value)
            editor.bind("<<ComboboxSelected>>", lambda e: self._commit(row, key))
            return editor
        editor = ttk.Entry(self.tree, font=("Consolas", 10) if key == "hex" else None)
        editor.insert(0, value)
        editor.select_range(0, "end")
        return editor

    def _commit(self, row, key):
        if self._editor is None:
            return
        error = self.on_edit(row, key, self._editor.get())
        if error is None:
            self.close_editor()

    def close_editor(self):
        if self._editor is not None:
            editor, self._editor = self._editor, None
            editor.destroy()

    @property
    def editing(self):
        return self._editor is not None
