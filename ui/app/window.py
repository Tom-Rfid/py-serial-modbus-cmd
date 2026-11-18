"""
ui/app/window.py — Classe App : création des panneaux et placement.

Données détenues par l'application
    proto    : protocole requête / réponse en cours (core.protocol.Protocol), lu dans protocols/
    messages : messages JSON chargés ; values : valeurs saisies {position: {paramètre: valeur}}
    link     : la liaison série ou TCP (core.link_switch.LinkSwitch)
    settings : les réglages mémorisés (core.settings.Settings)
    recorder : trace en cours d'enregistrement, ou None

Flux principaux
    - sélection d'un message  -> ParamsPanel.show()
    - envoi                   -> link.write() -> journal TX, trace, timeout de réponse
    - réception               -> thread de lecture -> link.events -> poll_link() -> moniteur,
                                 onglet Protocole, trace, replay
    - flèche « → Replay »     -> trame insérée dans la trace du panneau Replay
"""
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.protocol import DEFAULT_PROTOCOL
from core.link_switch import LinkSwitch
from core.serial_link import SerialLink
from core.tcp_link import TcpLink
from core.edition import load_edition, port_options, window_title
from core.settings import Settings
from ui.color_dialog import ColorDialog
from ui.i18n import LANGUAGES, _
from ui.icon import set_window_icon
from ui.com_panel import ComPanel
from ui.messages_panel import MessagesPanel
from ui.monitor_panel import MonitorPanel
from ui.params_panel import ParamsPanel
from ui.protocol import ProtocolPanel
from ui.replay import ReplayPanel
from ui.theme import THEME

from .layout import DEFAULT_GEOMETRY, LayoutMixin, fix_treeview_tag_colors
from .messages import MessagesMixin
from .protocol import ProtocolMixin
from .sending import POLL_MS, SendingMixin
from .traces import TracesMixin


class App(MessagesMixin, SendingMixin, ProtocolMixin, TracesMixin, LayoutMixin, tk.Tk):
    def __init__(self, base_dir):
        """base_dir : dossier du projet (contient msgLibrary/, protocols/ et settings.json)."""
        super().__init__()
        fix_treeview_tag_colors(self)
        self.minsize(950, 600)
        self._init_state(Path(base_dir))
        self.title(window_title(self.edition))
        set_window_icon(self, Path(base_dir) / self.edition["icon"])
        self.reset_old_layout()                         # disposition d'une ancienne version : oubliée
        self.geometry(self.settings["geometry"] or DEFAULT_GEOMETRY)
        self._build()
        self.reload_messages()                          # messages, protocole et commandes
        self.update_send_state()                        # boutons d'envoi grisés : pas encore connecté
        self.after(200, self.restore_layout)            # une fois la fenêtre affichée
        self.after(POLL_MS, self.poll_link)             # lecture des événements du port
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_state(self, base_dir):
        self.base_dir = base_dir
        self.library_dir = base_dir / "msgLibrary"
        self.messages_dir = self.library_dir / "msgManual"   # messages seuls de l'onglet Manuel
        self.lists_dir = self.library_dir / "msgList"        # listes de commandes des protocoles
        self.traces_dir = base_dir / "traces"
        self.protocols_dir = base_dir / "protocols"
        self.settings = Settings(base_dir / "settings.json")
        self.edition = load_edition(base_dir)   # version du logiciel : titre, icône, protocole par défaut
        THEME.load(self.settings["colors"])     # couleurs réglées (page « Couleurs… »)
        self.proto = DEFAULT_PROTOCOL           # remplacé par le fichier choisi (load_protocol)
        # Liaison série ou TCP (choix « Liaison » du panneau de connexion)
        self.link = LinkSwitch(SerialLink(), TcpLink(), self.settings["link"])
        self.link.gap_ms = float(self.settings["gap_ms"])
        self.messages = []                      # messages de l'onglet Manuel (fichiers Msg_*.json)
        self.values = {}
        self._seq_job = None                    # envoi en séquence en cours (after)
        self.recorder = None
        self._awaiting = {}                     # REQUEST ID -> minuterie des requêtes sans réponse

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self):
        # Zones redimensionnables :
        #   body  (vertical)   : haut / moniteur
        #   top   (horizontal) : onglets / panneau Replay (affiché par la case « ▶ Replay »)
        #   upper (horizontal) : dans l'onglet Manuel, messages / paramètres
        self.body = ttk.PanedWindow(self, orient="vertical")
        self.top = ttk.PanedWindow(self.body, orient="horizontal")
        self.tabs = ttk.Notebook(self.top)
        self.upper = ttk.PanedWindow(self.tabs, orient="horizontal")

        # Le moniteur est créé en premier : les autres panneaux écrivent dedans dès leur création
        self.monitor = self._build_monitor()
        self._build_manual_tab()
        self.protocol_panel = ProtocolPanel(self.tabs, self.settings, on_send=self.send_bytes,
                                            on_protocol=self.select_protocol, on_to_replay=self.to_replay,
                                            on_save=self.save_message)
        self.tabs.add(self.protocol_panel, text=_("Protocole"))
        self.tabs.add(self.upper, text=_("Manuel"))
        self.replay = self._build_replay()
        self._build_tab_corner()
        self.com = ComPanel(self, self.link, self.settings, log=self.monitor.log, on_change=self.on_link_change,
                            ports=port_options(self.edition))

        self.com.pack(fill="x", padx=6, pady=6)
        self.body.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.body.add(self.top, weight=1)
        self.body.add(self.monitor, weight=1)
        self.top.add(self.tabs, weight=1)

    def _build_monitor(self):
        return MonitorPanel(self.body, self.link.gap_ms,
                            on_gap_change=self.set_gap,
                            on_send_hex=lambda data: self.send_bytes(data, "manuel"),
                            crc_bytes=lambda data: self.proto.crc_bytes(data),
                            annotate=self.annotate,
                            decode=bool(self.settings["decode_protocol"]),
                            on_decode_change=self.set_decode,
                            style=self.style,
                            on_record=self.toggle_trace,
                            on_replay=self.open_replay,
                            timeout_ms=float(self.settings["rx_timeout_ms"]),
                            on_timeout_change=self.set_timeout,
                            traces_dir=self.traces_dir)

    def _build_manual_tab(self):
        """Onglet Manuel : messages JSON à gauche, paramètres du message à droite."""
        self.messages_panel = MessagesPanel(self.upper,
                                            on_select=self.select_message,
                                            on_send=self.send_message,
                                            on_send_selection=self.send_sequence,
                                            on_reload=self.reload_messages,
                                            on_load_files=self.load_files,
                                            on_remove=self.remove_files)
        self.params = ParamsPanel(self.upper, on_send=self.send_message, on_to_replay=self.manual_to_replay,
                                  build=self.build_message, lookup=self.command_for_message)
        self.upper.add(self.messages_panel, weight=1)
        self.upper.add(self.params, weight=2)

    def _build_replay(self):
        return ReplayPanel(self.top, send=self.send_bytes,
                           is_connected=lambda: self.link.connected,
                           traces_dir=self.traces_dir, log=self.monitor.log,
                           timeout_ms=float(self.settings["rx_timeout_ms"]),
                           describe=self.annotate, style=self.style,
                           on_decode=self.decode_in_protocol)

    def _build_tab_corner(self):
        """À droite de la rangée d'onglets : langue, bouton « Couleurs… » et case « ▶ Replay »."""
        corner = ttk.Frame(self.tabs)
        corner.place(relx=1.0, x=-4, y=0, anchor="ne")
        self.lang_var = tk.StringVar(value=LANGUAGES.get(self.settings["language"], LANGUAGES["fr"]))
        lang_cb = ttk.Combobox(corner, textvariable=self.lang_var, values=list(LANGUAGES.values()),
                               state="readonly", width=9)
        lang_cb.pack(side="left", padx=(0, 10))
        lang_cb.bind("<<ComboboxSelected>>", lambda e: self.change_language())
        ttk.Button(corner, text=_("Couleurs…"), command=self.open_colors).pack(side="left", padx=(0, 10))
        self.replay_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(corner, text=_("▶ Replay"), variable=self.replay_var,
                        command=lambda: self.show_replay(self.replay_var.get())).pack(side="left")

    # ------------------------------------------------------------------
    # Langue
    # ------------------------------------------------------------------
    def change_language(self, ask=True):
        """Langue choisie dans la liste : mémorisée ; SerialHex redémarre pour l'appliquer
        (les libellés sont créés une fois pour toutes au démarrage)."""
        code = next(k for k, v in LANGUAGES.items() if v == self.lang_var.get())
        if code == self.settings["language"]:
            return
        self.settings["language"] = code
        self.settings.save()
        question = (_("Redémarrer SerialHex maintenant pour changer de langue ?")
                    + "\n" + "Restart SerialHex now to change the language?")
        if ask and messagebox.askyesno("SerialHex", question, parent=self):
            self.restart()

    def restart(self):
        """Relance le programme (mêmes arguments), puis ferme cette fenêtre."""
        subprocess.Popen([sys.executable] + sys.argv, cwd=str(self.base_dir))
        self.on_close()

    # ------------------------------------------------------------------
    # Couleurs
    # ------------------------------------------------------------------
    def open_colors(self):
        """Bouton « Couleurs… » : page de réglage (une seule ouverte à la fois)."""
        dialog = getattr(self, "_color_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.lift()
            return
        self._color_dialog = ColorDialog(self, on_apply=self.set_colors)

    def set_colors(self, colors):
        """Nouvelles couleurs : appliquées partout et mémorisées."""
        THEME.update(colors)
        self.settings["colors"] = dict(THEME.colors)
        self.settings.save()
