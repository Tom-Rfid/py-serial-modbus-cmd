"""
ui/protocol/widgets.py — Widgets de l'onglet Protocole.

    FieldTable  : tableau d'une trame décodée, une ligne par champ ; certaines lignes
                  (champs de DATA de la requête) se modifient directement dans le tableau :
                  colonne Valeur (valeur convertie) ou colonne Hexa (octets bruts du champ).
                  Sa hauteur suit le nombre de lignes (fit) pour que toute la trame soit visible.
"""
import tkinter.font as tkfont
from tkinter import ttk

from core.frames import to_hex
from ui.theme import THEME, ensure_hex_tag

from .constants import GREEN, MONO
from ui.i18n import _, tr


class FieldTable(ttk.Frame):
    """Tableau d'une trame décodée : une ligne par champ.

        Octets | Champ          | Hexa   | Valeur            | Contrôle
        0-1    | SYNC           | A5 5A  | 42330 (0xA55A)    | OK
        3      | STATUS         | 00     | 0 (0x00)          | OK
        7-8    |   ↳ puissance  | 7D 00  | 12.5 mW           | brut 125
    """
    # Largeurs de départ (redimensionnables à la souris) ; seule la Description s'élargit
    # avec la fenêtre, pour qu'elle reste visible à droite
    COLUMNS = (("span", _("Octets"), 55), ("name", _("Champ"), 190), ("hex", "Hexa", 160),
               ("value", _("Valeur"), 210), ("check", _("Contrôle"), 110), ("desc", "Description", 300))
    STRETCH = ("desc",)

    def __init__(self, master, height=7, fit=None):
        """
        height : hauteur en lignes (fixe si fit est None)
        fit    : (min, max) : la hauteur suit le nombre de lignes affichées, entre min et max
        Attribut on_resize : fonction appelée quand la hauteur (en lignes) change.
        """
        super().__init__(master)
        self._fit = fit
        self.on_resize = None
        self.tree = ttk.Treeview(self, columns=[c[0] for c in self.COLUMNS], show="headings", height=height)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=40, anchor="w", stretch=key in self.STRETCH)
        # Couleurs des lignes (même code couleur que l'aperçu hexa et le moniteur)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold                                   # garder une référence à la police
        THEME.subscribe(self._apply_colors)                    # couleurs de la page « Couleurs… »
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._editor = None             # champ de saisie en cours (Entry / Combobox), ou None
        self._edit_spec = None          # fonction iid -> (texte, choix ou None), None si non modifiable
        self._edit_done = None          # fonction (iid, texte) appelée à la validation
        self._hex_spec = None           # idem pour la colonne Hexa (octets bruts du champ)
        self._hex_done = None

    # ------------------------------------------------------------------
    # Modification directe dans le tableau
    # ------------------------------------------------------------------
    def set_editor(self, spec, on_commit, hex_spec=None, on_hex_commit=None):
        """Rend certaines lignes modifiables.

        spec(iid)            -> (texte actuel, liste de choix ou None), ou None si la ligne
                                ne se modifie pas (colonne Valeur : valeur convertie)
        on_commit(iid, text) : valeur validée (Entrée, Tab, clic ailleurs, choix dans la liste)
        hex_spec(iid)        -> texte hexa actuel, ou None (colonne Hexa : octets bruts du champ)
        on_hex_commit(iid, text) : octets hexa validés
        Clic sur la colonne Valeur (ou Hexa) ou double-clic sur la ligne : édition ; Échap : annule.
        """
        self._edit_spec, self._edit_done = spec, on_commit
        self._hex_spec, self._hex_done = hex_spec, on_hex_commit
        self.tree.bind("<ButtonRelease-1>", self._on_click, add="+")
        self.tree.bind("<Double-1>", self._on_double, add="+")
        self.tree.bind("<Return>", lambda e: self._start_edit(self.tree.focus()), add="+")

    def _on_click(self, event):
        """Clic simple : édition si la cellule est dans la colonne Valeur ou Hexa."""
        column = self._column_at(event.x)
        if column in ("value", "hex"):
            self._start_edit(self.tree.identify_row(event.y), column)

    def _on_double(self, event):
        """Double-clic : colonne Hexa si c'est elle qui est cliquée, sinon colonne Valeur."""
        column = "hex" if self._column_at(event.x) == "hex" else "value"
        self._start_edit(self.tree.identify_row(event.y), column)

    def _column_at(self, x):
        """Clé de la colonne sous l'abscisse x ("value", "hex"…), ou None."""
        col = self.tree.identify_column(x)          # "#1", "#2"…
        keys = [c[0] for c in self.COLUMNS]
        try:
            return keys[int(col[1:]) - 1]
        except (ValueError, IndexError):
            return None

    def _cell_spec(self, iid, column):
        """(texte, choix ou None) de la cellule si elle se modifie, sinon None."""
        if column == "hex":
            if self._hex_spec is None:
                return None
            text = self._hex_spec(iid)
            return None if text is None else (text, None)
        if self._edit_spec is None:
            return None
        return self._edit_spec(iid)

    def _start_edit(self, iid, column="value"):
        """Ouvre un champ de saisie sur la cellule (Valeur ou Hexa) de la ligne iid, si modifiable."""
        if not iid:
            return
        spec = self._cell_spec(iid, column)
        if spec is None:
            return
        self._close_editor()
        self.tree.see(iid)
        self.tree.update_idletasks()
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, w, h = bbox
        text, choices = spec
        if choices:
            editor = ttk.Combobox(self.tree, values=choices, state="readonly")
            editor.set(text)
            editor.bind("<<ComboboxSelected>>", lambda e: self._commit(iid, column=column))
        else:
            editor = ttk.Entry(self.tree, font=MONO)
            editor.insert(0, text)
            editor.select_range(0, "end")
        editor.place(x=x, y=y, width=max(w, 140), height=h)
        editor.focus_set()
        editor.bind("<Return>", lambda e: self._commit(iid, column=column))
        editor.bind("<KP_Enter>", lambda e: self._commit(iid, column=column))
        editor.bind("<Tab>", lambda e: self._commit(iid, move=1, column=column) or "break")
        editor.bind("<Escape>", lambda e: self._close_editor())
        editor.bind("<FocusOut>", lambda e: self._commit(iid, column=column) if not choices else None)
        self._editor = editor

    def _commit(self, iid, move=0, column="value"):
        """Valide la saisie ; move=1 : passe ensuite à la ligne modifiable suivante (Tab),
        dans la même colonne."""
        if self._editor is None:
            return
        text = self._editor.get()
        self._close_editor()
        done = self._hex_done if column == "hex" else self._edit_done
        if done:
            done(iid, text)                     # le tableau est reconstruit (mêmes identifiants)
        if move:
            rows = [r for r in self.tree.get_children() if self._cell_spec(r, column) is not None]
            if iid in rows and rows.index(iid) + 1 < len(rows):
                self._start_edit(rows[rows.index(iid) + 1], column)
        elif self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)

    def _close_editor(self):
        if self._editor is not None:
            editor, self._editor = self._editor, None
            editor.destroy()

    def _apply_colors(self):
        """Couleurs des lignes, du thème (ordre de déclaration : le dernier tag l'emporte)."""
        c = THEME.colors
        self.tree.tag_configure("data", foreground=c["tx"])     # champs de DATA
        self.tree.tag_configure("hdr", foreground=c["hdr"])     # octets fixes, adresse, numéro de requête
        self.tree.tag_configure("cmd", font=self._bold, foreground=c["cmd"])   # COMMAND ID : gras
        self.tree.tag_configure("crc", foreground=c["crc"])     # CRC justes
        self.tree.tag_configure("na", foreground=c["na"])       # octets non lus
        self.tree.tag_configure("ok", foreground=GREEN)         # code d'erreur à 0
        self.tree.tag_configure("ko", foreground=c["err"])      # contrôle échoué

    @staticmethod
    def _value_text(f):
        """'126 (0x7E)' ; pour un champ en bits : '5 (0b101)' ; suivi du texte de la valeur
        ("values" du fichier de protocole) : '3 (0x03) Read Holding Registers'."""
        if f.value is None:
            return ""
        if f.bits is not None and f.bit_start is not None and (f.bits % 8 or f.bit_start % 8):
            text = f"{f.value} (0b{f.value:0{f.bits}b})"
        else:
            text = f"{f.value} (0x{f.value:0{f.hex_digits}X})"
        return f"{text} {f.meaning}" if getattr(f, "meaning", "") else text

    def show(self, decoded, data_fields=None, library=None, data_rows=None, data_row=None):
        """Affiche une trame décodée.

        decoded     : core.protocol.Decoded, ou None pour vider le tableau
        data_fields : champs de DATA décodés (core.commands.DataField), affichés
                      sous la ligne DATA ; None = DATA affichée en bloc
        library     : pour afficher le texte des codes d'erreur
        data_rows   : pour chaque champ de DATA, dict facultatif : "iid" (identifiant de la
                      ligne, utilisé par l'édition), "desc" (colonne Description), et pour un
                      champ invalide "value", "check" et "ok": False
        data_row    : ligne DATA modifiable (en bleu, octets bruts en hexa dans la colonne
                      Valeur) : dict "iid" et facultatifs "desc", "check" ; None = ligne DATA normale
        """
        self._close_editor()
        self.tree.delete(*self.tree.get_children())
        if decoded is None:
            self._fit_height()
            return
        data_shown = False
        for f in decoded.fields:
            if f.role == "data" and data_row is not None:
                self._insert_raw_data(f.span if f.raw else "", f.name, f.raw, data_row)
                data_shown = True
                if data_fields is not None:
                    self._insert_data_rows(data_fields, data_rows)
                continue
            value = self._value_text(f)
            check = "" if f.ok is None else ("OK" if f.ok else tr(f.note) or _("incorrect"))
            # Style du champ : couleur du fichier de conf (en-tête gris, COMMAND ID gras,
            # CRC vert) ; rouge si le contrôle échoue
            tag = ("ko",) if f.ok is False else ((f.color,) if f.color else ())
            if f.role == "error":
                # Code d'erreur : texte de la bibliothèque, rouge si différent de 0
                text = library.error_text(f.value) if library else ""
                check = text or ("OK" if f.value == 0 else _("erreur"))
                tag = ("ok",) if f.value == 0 else ("ko",)
            for t in tag:
                ensure_hex_tag(self.tree, t)    # couleur "#RRGGBB" du fichier de protocole
            hexa = to_hex(f.raw) if len(f.raw) <= 24 else to_hex(f.raw[:24]) + " …"
            self.tree.insert("", "end", values=(f.span, f.name, hexa, value, check or tr(f.note),
                                                getattr(f, "description", "")), tags=tag)
            if f.role == "data" and data_fields is not None:
                data_shown = True
                self._insert_data_rows(data_fields, data_rows)
        if data_row is not None and not data_shown:     # DATA vide absente de la trame : ligne quand même
            self._insert_raw_data("", "DATA", b"", data_row)
        if data_fields and not data_shown:          # trame sans champ DATA (DATA vide)
            self._insert_data_rows(data_fields, data_rows)
        if decoded.complete and decoded.extra:
            self.tree.insert("", "end", tags=("ko",),
                             values=("", _("EN TROP"), to_hex(decoded.extra), "", _("{0} octet(s)").format(len(decoded.extra))))
        self._fit_height()

    def _fit_height(self):
        """Hauteur du tableau = nombre de lignes (entre les bornes de fit) : toute la trame visible."""
        if self._fit is None:
            return
        low, high = self._fit
        rows = len(self.tree.get_children())
        wanted = max(low, min(high, rows))
        if int(self.tree.cget("height")) == wanted:
            return
        self.tree.configure(height=wanted)
        if self.on_resize:
            self.on_resize()

    def _insert_raw_data(self, span, name, raw, row):
        """Ligne DATA en bleu : octets bruts complets dans la colonne Valeur (modifiable en hexa)."""
        iid = row.get("iid")
        if iid and self.tree.exists(iid):
            iid = None
        hexa = to_hex(raw) if len(raw) <= 24 else to_hex(raw[:24]) + " …"
        tag = ("ko",) if row.get("ok") is False else ("data",)
        self.tree.insert("", "end", iid=iid, tags=tag,
                         values=(span, name, hexa, to_hex(raw), row.get("check", _("{0} octet(s)").format(len(raw))),
                                 row.get("desc", "")))

    def _insert_data_rows(self, data_fields, data_rows):
        """Lignes « ↳ champ » de DATA (en bleu), modifiables si data_rows leur donne un "iid"."""
        for i, d in enumerate(data_fields):
            extra = data_rows[i] if data_rows and i < len(data_rows) else {}
            ok = extra.get("ok", d.ok)
            dtag = ("ko",) if ok is False else ("data",)
            iid = extra.get("iid")
            if iid and self.tree.exists(iid):
                iid = None
            self.tree.insert("", "end", iid=iid, tags=dtag,
                             values=(d.span if d.raw else "", f"   ↳ {d.name}", to_hex(d.raw),
                                     extra.get("value", tr(d.text)), extra.get("check", tr(d.note)),
                                     extra.get("desc", "")))
