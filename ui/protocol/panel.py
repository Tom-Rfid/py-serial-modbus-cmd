"""
ui/protocol/panel.py — Classe ProtocolPanel : création de l'onglet, choix du protocole.

La partie Requête est dans query.py (recherche et favoris de CMD TX : command_search.py), la
partie Réponse dans response.py. Les champs de DATA se modifient directement dans le tableau
de la trame (widgets.py). Ligne du Replay chargée dans la Requête ou la Réponse : from_replay.py
(cadre rempli sur fond gris foncé : highlight.py).

Le séparateur Requête / Réponse se place tout seul pour que les deux tableaux se voient en
entier (_fit_panes) ; déplacé à la main, il reste où on l'a mis jusqu'au prochain changement
du nombre de lignes d'un tableau.
"""
import tkinter as tk
from tkinter import ttk

from core.commands import Library
from core.protocol import DEFAULT_PROTOCOL, QUERY

from .constants import AUTO, GREY, MANUAL, RAW
from .command_search import CommandSearchMixin
from .from_replay import FromReplayMixin
from .query import QueryMixin
from .response import ResponseMixin
from ui.i18n import _

RX_MIN_HEIGHT = 170     # hauteur minimale gardée pour la Réponse quand la place manque (px)


class ProtocolPanel(QueryMixin, CommandSearchMixin, ResponseMixin, FromReplayMixin, ttk.Frame):
    def __init__(self, master, settings, on_send, on_protocol=None, on_to_replay=None, on_save=None):
        """
        settings                 : core.settings.Settings
        on_send(data, label)     : envoie des octets, retourne False en cas d'échec
        on_protocol(fichier)     : un autre protocole est choisi dans la liste
        on_to_replay(data, label): flèche « → Replay » (trame vers la ligne sélectionnée du replay)
        on_save(message, fichier) : bouton « Sauvegarder… » : message de protocole à ajouter à
                                   l'onglet Manuel (core/request_message.py)
        """
        super().__init__(master, padding=8)
        self.settings = settings
        self.on_send = on_send
        self.on_protocol = on_protocol
        self.on_to_replay = on_to_replay
        self.on_save = on_save
        self._init_state()
        self._build_protocol_row()
        # Requête / Réponse redimensionnables (séparateur mémorisé par l'application)
        self.panes = ttk.PanedWindow(self, orient="vertical")
        self.panes.pack(fill="both", expand=True)
        self._query_box = self._build_query_box(self.panes)
        self._response_box = self._build_response_box(self.panes)
        self.panes.add(self._query_box, weight=1)
        self.panes.add(self._response_box, weight=1)
        self._init_highlight()          # ligne du Replay chargée : cadre sur fond gris foncé
        # Un tableau change de hauteur, ou la fenêtre change de taille : séparateur replacé
        self.query_table.on_resize = self._fit_panes
        self.decode_table.on_resize = self._fit_panes
        self.panes.bind("<Configure>", self._on_panes_resize, add="+")
        self._panes_height = 0
        self._fit_pending = False
        self._build_form()
        self.update_query()

    def _init_state(self):
        self.proto = DEFAULT_PROTOCOL   # protocole en cours (core.protocol.Protocol), fourni par set_protocol
        self.lib = Library()            # commandes + erreurs, fournie par l'application (set_library)
        self.cmd = None                 # commande sélectionnée, None = saisie manuelle
        self.tx_values = {}             # valeurs saisies par commande : {libellé: {champ: texte}}
        self.raw_data = {}              # DATA brute saisie dans le tableau, par commande : {libellé: octets}
        self.sent = {}                  # REQUEST ID -> commande des requêtes envoyées (réponse « Auto »)
        self._sending_cmd = None        # commande de la requête en cours d'envoi depuis l'onglet
        self._frame = None              # dernière requête construite (octets), None si invalide
        self._proto_files = {}          # libellé de la liste des protocoles -> nom de fichier

    # ------------------------------------------------------------------
    # Séparateur Requête / Réponse
    # ------------------------------------------------------------------
    def _on_panes_resize(self, event):
        """Hauteur de la zone Requête / Réponse changée (fenêtre redimensionnée) : on replace."""
        if event.height != self._panes_height:
            self._panes_height = event.height
            self._fit_panes()

    def _fit_panes(self):
        """Demande de placer le séparateur (une seule fois, quand Tk a fini ses calculs)."""
        if not self._fit_pending:
            self._fit_pending = True
            self.after_idle(self._place_sash)

    def _place_sash(self):
        """Séparateur placé pour que la Requête ait la hauteur qu'elle demande (tableau en
        entier), la Réponse le reste. Si la place manque pour les deux, la Requête (celle
        qu'on modifie) passe d'abord ; la Réponse garde au moins RX_MIN_HEIGHT et défile."""
        self._fit_pending = False
        # Les hauteurs demandées remontent d'un widget à l'autre en plusieurs passes : on
        # laisse Tk finir ses calculs avant de les lire
        self.update_idletasks()
        total = self.panes.winfo_height()
        if total <= 1:
            return                          # pas encore affiché : <Configure> rappellera
        tx = self._query_box.winfo_reqheight()
        rx = self._response_box.winfo_reqheight()
        if tx + rx <= total:
            pos = tx                        # tout tient : la Réponse prend la place restante
        else:
            pos = min(tx, total - RX_MIN_HEIGHT)
            pos = max(pos, total // 2)      # très petite fenêtre : au moins moitié / moitié
        try:
            self.panes.sashpos(0, pos)
        except tk.TclError:                 # zone pas encore prête
            pass

    def _build_protocol_row(self):
        """Ligne du haut : liste des fichiers de protocols/ et description du protocole."""
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text=_("Protocole"), width=12).pack(side="left")
        self.proto_var = tk.StringVar()
        self.proto_cb = ttk.Combobox(row, textvariable=self.proto_var, state="readonly", width=34)
        self.proto_cb.pack(side="left")
        self.proto_cb.bind("<<ComboboxSelected>>", lambda e: self._on_protocol())
        self.proto_desc = ttk.Label(row, foreground=GREY)
        self.proto_desc.pack(side="left", padx=10)

    # ------------------------------------------------------------------
    # Protocole
    # ------------------------------------------------------------------
    @property
    def cfg(self):
        """Protocole en cours : structure des trames et ordre des octets (passé à core.commands)."""
        return self.proto

    def set_protocols(self, files, current):
        """Liste des fichiers de protocols/ : [(nom de fichier, Protocol ou message d'erreur)]."""
        self._proto_files = {}
        for name, p in files:
            if isinstance(p, str):
                label = _("⚠ {0} (invalide)").format(name)
            else:
                label = f"{p.name} ({name})"
            self._proto_files[label] = name
        self.proto_cb["values"] = list(self._proto_files)
        for label, name in self._proto_files.items():
            if name == current:
                self.proto_var.set(label)

    def _on_protocol(self):
        name = self._proto_files.get(self.proto_var.get())
        if name and self.on_protocol:
            self.on_protocol(name)

    def set_protocol(self, proto):
        """Nouveau protocole : libellés, champs actifs et trames recalculées."""
        self.proto = proto
        self.sent.clear()
        self.proto_desc.config(text=proto.description_en if proto.language == "en" and proto.description_en
                               else proto.description)
        self._label_field(self.rid_lbl, self.rid_entry, proto.spec(QUERY, "request_id"), "REQUEST ID")
        self._label_field(self.cmd_lbl, self.cmd_entry, proto.spec(QUERY, "command_id"), "COMMAND ID")
        self.rid_var.set(self._rid_hex(self._int_value(self.rid_var)))
        self.cmd_var.set(self._cmd_hex(self._int_value(self.cmd_var)))
        self._show_variants(proto.variant_names(QUERY))
        self._on_command()

    def _show_variants(self, names):
        """Liste « Format » des variantes de trame de la requête ; cachée s'il n'y en a qu'une."""
        self.variant_cb["values"] = names
        if names:
            if self.variant_var.get() not in names:
                self.variant_var.set(names[0])
            self.variant_lbl.pack(side="left", padx=(12, 0))
            self.variant_cb.pack(side="left", padx=4)
        else:
            self.variant_var.set("")
            self.variant_lbl.pack_forget()
            self.variant_cb.pack_forget()

    @staticmethod
    def _label_field(label, entry, spec, default_name):
        """Nom du champ dans le fichier de conf ; champ grisé s'il est absent du protocole."""
        label.config(text=spec.name if spec else default_name)
        entry.state(["!disabled"] if spec else ["disabled"])

    def _hex(self, role, value):
        """Valeur en hexa sur la taille du champ : 0x05 (1 octet), 0x00000004 (4 octets)."""
        spec = self.proto.spec(QUERY, role)
        digits = (spec.bits + 3) // 4 if spec else 2         # 2 chiffres par octet, ou selon les bits
        return f"0x{value:0{digits}X}"

    def _cmd_hex(self, value):
        return self._hex("command_id", value)

    def _rid_hex(self, value):
        return self._hex("request_id", value)

    @staticmethod
    def _int_value(var):
        """Entier saisi (décimal ou 0x..), 0 si la saisie est invalide."""
        try:
            return int(var.get().strip(), 0)
        except ValueError:
            return 0

    # ------------------------------------------------------------------
    # Bibliothèque de commandes
    # ------------------------------------------------------------------
    def set_library(self, lib):
        """Nouvelle bibliothèque (chargement ou bouton Recharger) : met à jour les listes."""
        self.lib = lib
        labels = [c.label for c in lib.visible(self.show_hidden.get())]
        self._update_hidden_check()
        self.set_command_labels([MANUAL] + labels)
        self.rx_cb["values"] = [AUTO, RAW] + labels
        # La commande sélectionnée peut avoir disparu ou changé : on la relit
        if self.cmd_choice.get() not in labels:
            self.cmd_choice.set(MANUAL)
        if self.rx_type.get() not in labels + [AUTO, RAW]:
            self.rx_type.set(AUTO)
        self.tx_values.clear()          # les définitions ont pu changer
        self._on_command()

    def _update_hidden_check(self):
        """Case « Masquées (n) » : affichée seulement si la bibliothèque a des commandes masquées."""
        count = self.lib.hidden_count()
        if count:
            self.hidden_chk.configure(text=_("Masquées ({0})").format(count))
            if not self.hidden_chk.winfo_ismapped():
                self.hidden_chk.pack(side="left", padx=(6, 0))
        else:
            self.hidden_chk.pack_forget()

    def _on_show_hidden(self):
        """Case « Masquées » cochée / décochée : listes refaites, choix mémorisé dans les réglages."""
        self.settings["show_hidden_commands"] = self.show_hidden.get()
        self.settings.save()
        choice, rx_choice, values = self.cmd_choice.get(), self.rx_type.get(), dict(self.tx_values)
        self.set_library(self.lib)
        self.tx_values.update(values)   # saisies conservées
        if choice in self._cmd_labels:
            self.cmd_choice.set(choice)
            self._on_command()
        if rx_choice in self.rx_cb["values"]:
            self.rx_type.set(rx_choice)
