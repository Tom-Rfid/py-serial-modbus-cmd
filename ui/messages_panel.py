"""
ui/messages_panel.py — Panneau « Messages ».

Affiche la liste des messages chargés, rangés par groupe (un groupe par
fichier Msg_<fonction>.json), et permet :
    - clic          : afficher les paramètres du message (à droite, onglet Manuel)
    - double-clic   : envoyer le message
    - Ctrl/Maj+clic : sélection multiple, puis « Envoyer la sélection » avec un délai
    - Recharger     : relire le dossier msgLibrary/msgManual/ et les fichiers ajoutés
    - Charger…      : ajouter des fichiers JSON situés ailleurs (liste mémorisée)
    - Retirer       : retirer de la liste les fichiers ajoutés des messages sélectionnés

Le panneau ne charge ni n'envoie rien lui-même : il appelle les fonctions
fournies par l'application (voir ui/app.py).
"""
import tkinter as tk
from tkinter import ttk, filedialog
from core.messages import display_name
from ui.i18n import _


class MessagesPanel(ttk.Frame):
    def __init__(self, master, on_select, on_send, on_send_selection, on_reload, on_load_files, on_remove=None):
        """
        on_select(idx)                 : un message est sélectionné (idx = position dans la liste)
        on_send(idx)                   : double-clic sur un message
        on_send_selection(ids, delay)  : envoi en séquence, delay en ms
        on_reload()                    : relire le dossier msgLibrary/msgManual/
        on_load_files(paths)           : ajouter des fichiers JSON
        on_remove(ids)                 : retirer de la liste les fichiers ajoutés de ces messages
        """
        super().__init__(master, padding=4)
        self.on_select = on_select
        self.on_send = on_send
        self.on_send_selection = on_send_selection
        self.on_load_files = on_load_files

        # --- Barre du haut : titre + boutons
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text=_("Messages"), font=("Segoe UI", 10, "bold")).pack(side="left")
        if on_remove:
            ttk.Button(bar, text=_("Retirer"), command=lambda: self.selected_ids() and on_remove(self.selected_ids())
                       ).pack(side="right", padx=(4, 0))
        ttk.Button(bar, text=_("Charger…"), command=self._ask_files).pack(side="right")
        ttk.Button(bar, text=_("Recharger"), command=on_reload).pack(side="right", padx=4)

        # --- Arbre des messages
        # Identifiants des lignes : "g:<groupe>" pour un groupe, "<index>" pour un message
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, pady=4)
        self.tree = ttk.Treeview(frame, show="tree", selectmode="extended")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)

        # --- Barre du bas : envoi de la sélection
        seq = ttk.Frame(self)
        seq.pack(fill="x")
        ttk.Label(seq, text=_("Délai")).pack(side="left")
        self.delay_var = tk.StringVar(value="100")
        ttk.Entry(seq, textvariable=self.delay_var, width=6).pack(side="left", padx=2)
        ttk.Label(seq, text="ms").pack(side="left")
        self.send_sel_btn = ttk.Button(seq, text=_("Envoyer la sélection"), command=self._send_selection)
        self.send_sel_btn.pack(side="right")

    def set_messages(self, messages):
        """Remplace le contenu de l'arbre par la liste `messages`."""
        self.tree.delete(*self.tree.get_children())
        groups = {}                     # nom du groupe -> identifiant de sa ligne
        for idx, msg in enumerate(messages):
            parent = ""                 # "" = racine de l'arbre (message sans groupe)
            g = msg.get("group")
            if g:
                if g not in groups:
                    groups[g] = self.tree.insert("", "end", iid=f"g:{g}", text=g, open=True)
                parent = groups[g]
            # L'identifiant d'un message est sa position dans la liste
            self.tree.insert(parent, "end", iid=str(idx), text=display_name(msg))

    def set_send_enabled(self, enabled):
        """« Envoyer la sélection » grisé tant que la liaison n'est pas connectée."""
        self.send_sel_btn.state(["!disabled"] if enabled else ["disabled"])

    def select(self, idx):
        """Sélectionne et affiche le message idx (ex. message qui vient d'être sauvegardé)."""
        iid = str(idx)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)
            self.on_select(idx)

    def selected_ids(self):
        """Positions des messages sélectionnés (les lignes de groupe sont ignorées)."""
        return [int(i) for i in self.tree.selection() if not i.startswith("g:")]

    def _on_tree_select(self, _event=None):
        ids = self.selected_ids()
        if ids:
            self.on_select(ids[0])      # sélection multiple : on affiche le premier

    def _on_double_click(self, event):
        # On prend la ligne sous la souris (et pas la sélection, qui peut être multiple)
        iid = self.tree.identify_row(event.y)
        if iid and not iid.startswith("g:"):
            self.on_send(int(iid))

    def _send_selection(self):
        ids = self.selected_ids()
        if not ids:
            return
        try:
            delay = max(0, int(self.delay_var.get()))
        except ValueError:
            delay = 100                 # saisie invalide : valeur par défaut
            self.delay_var.set("100")
        self.on_send_selection(ids, delay)

    def _ask_files(self):
        """Bouton Charger… : choix d'un ou plusieurs fichiers JSON."""
        paths = filedialog.askopenfilenames(filetypes=[("JSON", "*.json"), (_("Tous"), "*.*")])
        if paths:
            self.on_load_files(paths)
