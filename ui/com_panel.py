"""
ui/com_panel.py — Panneau « Liaison » : port série ou TCP.

Affiche, de haut en bas :
    0. le type de liaison : Série ou TCP (Modbus TCP, passerelle série / Ethernet)
    1. série : le choix du port (ports présents uniquement) et son état : libre / occupé / absent
       TCP   : l'adresse et le port du serveur
    2. série : les réglages : vitesse, bits de données, parité, bits de stop, contrôle de flux
    3. le bouton Connecter / Déconnecter, l'état de la liaison, DTR / RTS, compteurs TX / RX

Fonctionnement
    - Toutes les 1,5 s, la liste des ports est relue pour détecter un adaptateur
      branché ou débranché. Cette relecture n'ouvre aucun port.
    - Le test « libre / occupé » ouvre brièvement le port : il n'est fait qu'à la
      sélection d'un port ou sur « Actualiser », pas en continu.
    - Un réglage modifié pendant la connexion est appliqué immédiatement au port.

Ce panneau ne connaît pas les autres panneaux : il écrit dans le journal via
la fonction `log` et prévient l'application via `on_change` (voir ui/app.py).
"""
from tkinter import ttk
import tkinter as tk

from core.link_switch import SERIAL, TCP
from core.serial_link import (BAUDRATES, STOPBITS, FREE, BUSY, MISSING,
                              list_serial_ports, check_port)
from core.edition import PORTS_DEFAULTS
from core.port_filter import enabled_ids
from ui.i18n import _, tr

# Libellés affichés <-> valeurs enregistrées dans settings.json
PARITY_LABELS = {"N": _("Aucune"), "E": _("Paire"), "O": _("Impaire"), "M": "Mark", "S": "Space"}
FLOW_LABELS = {"none": _("Aucun"), "rtscts": "RTS/CTS", "xonxoff": "XON/XOFF"}

# Couleurs des voyants
GREEN, RED, GREY, ORANGE, BLUE = "#1a8a3a", "#c0392b", "#999999", "#d68910", "#1f5fbf"
STATE_COLORS = {FREE: GREEN, BUSY: RED, MISSING: GREY}   # autre état -> ORANGE


def _key_of(mapping, label):
    """Retrouve la clé d'un libellé : _key_of(PARITY_LABELS, "Paire") -> "E"."""
    return next(k for k, v in mapping.items() if v == label)


DOT_FONT = ("Segoe UI", 13)           # voyant de la liaison
DOT_FONT_ON = ("Segoe UI", 22)        # voyant connecté : plus gros


class ComPanel(ttk.LabelFrame):
    PORTS_REFRESH_MS = 1500     # période de détection des ports branchés / débranchés
    COUNTERS_REFRESH_MS = 300   # période de mise à jour des compteurs TX / RX

    def __init__(self, master, link, settings, log, on_change, ports=None):
        """
        link         : core.link_switch.LinkSwitch — la liaison (série ou TCP) pilotée par ce panneau
        settings     : core.settings.Settings — réglages lus au démarrage, mis à jour à chaque changement
        log          : fonction log(texte, tag) pour écrire dans le moniteur (tag = "INFO" ou "ERR")
        on_change    : fonction appelée à chaque connexion / déconnexion
        ports        : options de la liste des ports (edition.json, clé "ports", voir
                       core/edition.py) : hide_bluetooth, filter_label, filter_default, filter
        """
        super().__init__(master, text=_("Liaison"), padding=(8, 4))
        self.link = link
        self.settings = settings
        self.log = log
        self.on_change = on_change
        self.ports = []             # liste de PortInfo affichée dans la liste déroulante
        self.port_opts = dict(PORTS_DEFAULTS, **(ports or {}))
        self.usb_ids = enabled_ids(self.port_opts["filter"])       # (VID, PID) gardés par le filtre
        saved = settings.get("port_filter")
        self.ftdi_var = tk.BooleanVar(value=bool(self.port_opts["filter_default"]) if saved is None else bool(saved))

        self._build()
        self._update_state()
        # after_idle : la première détection est faite une fois la fenêtre affichée
        self.after_idle(self._startup)
        # Tâches périodiques (chacune se reprogramme elle-même)
        self.after(self.PORTS_REFRESH_MS, self._watch_ports)
        self.after(self.COUNTERS_REFRESH_MS, self._update_counters)

    # ------------------------------------------------------------------
    # Construction des widgets
    # ------------------------------------------------------------------
    def _build(self):
        """Panneau compact sur 2 lignes :
            ligne 1 : liaison (Série / TCP), port série (filtre FTDI) ou adresse TCP, état du port,
                      puis Connecter et l'état de la liaison
            ligne 2 : réglages du port série (vitesse, données, parité, stop, flux) | DTR, RTS, auto, compteurs
        """
        s = self.settings
        line1 = ttk.Frame(self)
        line1.pack(fill="x")
        line2 = ttk.Frame(self)
        line2.pack(fill="x", pady=(4, 0))

        # --- Ligne 1, à gauche : type de liaison
        ttk.Label(line1, text=_("Liaison"), width=8).pack(side="left")
        self.mode_var = tk.StringVar(value=self.link.mode)
        self.mode_btns = [ttk.Radiobutton(line1, text=text, value=mode, variable=self.mode_var, command=self._on_mode)
                          for mode, text in ((SERIAL, _("Série")), (TCP, "TCP"))]
        for b in self.mode_btns:
            b.pack(side="left", padx=(0, 6))

        # Série : choix du port + état du port (affiché par _show_mode)
        self.port_box = ttk.Frame(line1)
        ttk.Label(self.port_box, text="Port").pack(side="left", padx=(10, 4))
        self.port_cb = ttk.Combobox(self.port_box, state="readonly", width=34)
        self.port_cb.pack(side="left")
        # Un nouveau port choisi : on teste tout de suite s'il est libre
        self.port_cb.bind("<<ComboboxSelected>>", lambda e: self._on_port_selected())
        ttk.Button(self.port_box, text=_("Actualiser"), command=lambda: self.refresh_ports(check=True)).pack(side="left", padx=4)
        # Filtre : seulement les adaptateurs de la liste "filter" d'edition.json (FTDI par défaut)
        ttk.Checkbutton(self.port_box, text=self.port_opts["filter_label"], variable=self.ftdi_var,
                        command=self._on_ftdi).pack(side="left", padx=(2, 4))
        self.port_dot = ttk.Label(self.port_box, text="●", foreground=GREY)     # voyant d'état du port
        self.port_dot.pack(side="left", padx=(4, 2))
        # Largeur fixe : le bouton Connecter, placé juste après, ne bouge pas quand l'état change
        self.port_state = ttk.Label(self.port_box, text="", width=30)            # texte d'état du port
        self.port_state.pack(side="left")

        # TCP : adresse et port du serveur (affiché par _show_mode)
        self.tcp_box = ttk.Frame(line1)
        ttk.Label(self.tcp_box, text=_("Adresse")).pack(side="left", padx=(10, 4))
        self.host_var = tk.StringVar(value=str(s["tcp_host"]))
        ttk.Entry(self.tcp_box, textvariable=self.host_var, width=18).pack(side="left")
        ttk.Label(self.tcp_box, text="Port").pack(side="left", padx=(12, 4))
        self.tcp_port_var = tk.StringVar(value=str(s["tcp_port"]))
        ttk.Entry(self.tcp_box, textvariable=self.tcp_port_var, width=7).pack(side="left")
        ttk.Label(self.tcp_box, text=_("(502 = Modbus TCP)"), foreground=GREY).pack(side="left", padx=6)

        # Connecter et état de la liaison : juste après l'état du port (ou l'adresse TCP)
        self.link_box = ttk.Frame(line1)
        self.connect_btn = ttk.Button(self.link_box, text=_("Connecter"), width=14, command=self.toggle)
        self.connect_btn.pack(side="left", padx=(16, 0))
        self.link_dot = ttk.Label(self.link_box, text="●", foreground=GREY, font=DOT_FONT)
        self.link_dot.pack(side="left", padx=(10, 4))
        self.link_state = ttk.Label(self.link_box, text=_("Déconnecté"), font=("Segoe UI", 10, "bold"))
        self.link_state.pack(side="left")

        # --- Ligne 2, à droite : compteurs, connexion auto, DTR / RTS (placés de droite à gauche)
        self.counters = ttk.Label(line2, text="", foreground="gray")
        self.counters.pack(side="right")
        # Reconnexion automatique au dernier port au démarrage
        self.auto_var = tk.BooleanVar(value=bool(self.settings["auto_connect"]))
        ttk.Checkbutton(line2, text=_("Connexion auto au démarrage"), variable=self.auto_var,
                        command=self._on_auto).pack(side="right", padx=(0, 16))
        self.rts_var = tk.BooleanVar()
        self.dtr_var = tk.BooleanVar()
        self.rts_cb = ttk.Checkbutton(line2, text="RTS", variable=self.rts_var, command=self._apply_lines)
        self.rts_cb.pack(side="right", padx=(4, 16))
        self.dtr_cb = ttk.Checkbutton(line2, text="DTR", variable=self.dtr_var, command=self._apply_lines)
        self.dtr_cb.pack(side="right")

        # --- Ligne 2, à gauche : réglages du port série, initialisés depuis settings.json
        self.format_box = ttk.Frame(line2)
        self.baud_var = tk.StringVar(value=str(s["baudrate"]))
        self.bytesize_var = tk.StringVar(value=str(s["bytesize"]))
        self.parity_var = tk.StringVar(value=PARITY_LABELS.get(s["parity"], _("Aucune")))
        self.stop_var = tk.StringVar(value=str(s["stopbits"]))
        self.flow_var = tk.StringVar(value=FLOW_LABELS.get(s["flow"], _("Aucun")))

        # La vitesse est modifiable au clavier : appliquée sur Entrée ou en quittant le champ
        # (pas à chaque touche, sinon taper « 9600 » appliquerait 9, 96, 960...)
        baud_cb = self._field(self.format_box, _("Vitesse"), self.baud_var, [str(b) for b in BAUDRATES], 9,
                              editable=True, first=True)
        baud_cb.bind("<Return>", self._apply_format)
        baud_cb.bind("<FocusOut>", self._apply_format)
        self._field(self.format_box, _("Données"), self.bytesize_var, ["5", "6", "7", "8"], 3)
        self._field(self.format_box, _("Parité"), self.parity_var, list(PARITY_LABELS.values()), 8)
        self._field(self.format_box, "Stop", self.stop_var, list(STOPBITS), 4)
        self._field(self.format_box, _("Flux"), self.flow_var, list(FLOW_LABELS.values()), 9)
        self._show_mode()

    # ------------------------------------------------------------------
    # Type de liaison
    # ------------------------------------------------------------------
    def _list_ports(self):
        """Ports affichés : sans les ports Bluetooth (si demandé), filtrés si la case est cochée."""
        return list_serial_ports(usb_ids=self.usb_ids if self.ftdi_var.get() else None,
                                 hide_bluetooth=bool(self.port_opts["hide_bluetooth"]))

    def _on_ftdi(self):
        """Case de filtre (« FTDI ») : liste des ports filtrée ou non (choix mémorisé)."""
        self.settings["port_filter"] = self.ftdi_var.get()
        self.settings.save()
        self.refresh_ports(check=True)
        if self.ftdi_var.get() and not self.ports:
            self.log(_("Aucun adaptateur {0} branché (décocher « {0} » pour voir tous les ports)")
                     .format(self.port_opts["filter_label"]), "INFO")

    def _on_mode(self):
        """Série / TCP choisi : mémorisé, lignes du panneau adaptées."""
        try:
            self.link.mode = self.mode_var.get()
        except ConnectionError as e:            # connecté : on ne change pas de liaison
            self.log(str(e), "ERR")
            self.mode_var.set(self.link.mode)
            return
        self.settings["link"] = self.link.mode
        self.settings.save()
        self._show_mode()
        self._update_state()

    def _show_mode(self):
        """Série : port et réglages du port ; TCP : adresse et port du serveur."""
        self.link_box.pack_forget()             # replacé à la fin, après le port ou l'adresse
        if self.link.mode == TCP:
            self.port_box.pack_forget()
            self.format_box.pack_forget()
            self.tcp_box.pack(side="left")
        else:
            self.tcp_box.pack_forget()
            self.port_box.pack(side="left")
            self.format_box.pack(side="left")
        self.link_box.pack(side="left")

    def _field(self, parent, label, var, values, width, editable=False, first=False):
        """Ajoute un libellé + une liste déroulante. Retourne la liste déroulante.

        editable : True pour autoriser la saisie libre (vitesse), sinon choix imposé
        first    : True pour le premier champ de la ligne (aligné avec « Liaison »)
        """
        ttk.Label(parent, text=label, width=8 if first else None).pack(side="left", padx=(0 if first else 12, 4))
        cb = ttk.Combobox(parent, textvariable=var, values=values, width=width,
                          state="normal" if editable else "readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self._apply_format)
        return cb

    # ------------------------------------------------------------------
    # Ports
    # ------------------------------------------------------------------
    def selected_device(self):
        """Nom du port sélectionné ("COM3"), ou None."""
        i = self.port_cb.current()
        return self.ports[i].device if 0 <= i < len(self.ports) else None

    def _startup(self):
        """Première détection des ports : resélectionne le dernier port utilisé,
        et s'y reconnecte si « Connexion auto au démarrage » est cochée."""
        self.refresh_ports(check=True)
        if self.link.mode == TCP:
            if self.settings["auto_connect"]:
                self.connect()
            return
        last = self.settings["port"]
        if not last:
            return
        if last not in [p.device for p in self.ports]:
            self.log(_("Dernier port utilisé ({0}) absent").format(last), "INFO")
            return
        self.log(_("Dernier port utilisé : {0}").format(last), "INFO")
        if self.settings["auto_connect"]:
            self.connect()

    def _on_port_selected(self):
        """Port choisi dans la liste : mémorisé tout de suite (même sans connexion), puis testé."""
        dev = self.selected_device()
        if dev:
            self.settings["port"] = dev
            self.settings.save()
        self.check_selected()

    def _on_auto(self):
        self.settings["auto_connect"] = self.auto_var.get()
        self.settings.save()

    def refresh_ports(self, check=False):
        """Relit la liste des ports et garde la sélection si possible.

        Ordre de préférence pour la sélection : port connecté, port déjà
        sélectionné, dernier port utilisé (settings.json), sinon le premier.
        check=True : teste ensuite si le port sélectionné est libre.
        """
        wanted = self.link.port or self.selected_device() or self.settings["port"]
        self.ports = self._list_ports()
        devices = [p.device for p in self.ports]
        self.port_cb["values"] = [p.label() for p in self.ports]
        if wanted in devices:
            self.port_cb.current(devices.index(wanted))
        elif self.ports:
            self.port_cb.current(0)
        else:
            self.port_cb.set("")
        if check:
            self.check_selected()

    def check_selected(self):
        """Affiche si le port sélectionné est libre, occupé ou absent."""
        dev = self.selected_device()
        if not self.ports:
            self._set_port_state(_("aucun port détecté"), GREY)
        elif not dev:
            self._set_port_state("", GREY)
        elif dev == self.link.port:
            # Inutile de tester : c'est nous qui l'utilisons
            self._set_port_state(_("connecté (utilisé par SerialHex)"), BLUE)
        else:
            state, msg = check_port(dev)        # ouvre et referme brièvement le port
            self._set_port_state(f"{tr(state)} — {tr(msg)}", STATE_COLORS.get(state, ORANGE))

    def _set_port_state(self, text, color):
        self.port_state.config(text=text)
        self.port_dot.config(foreground=color)

    def _watch_ports(self):
        """Tâche périodique : détecte les ports branchés / débranchés et la perte du port connecté."""
        before = {p.device for p in self.ports}
        present = {p.device for p in list_serial_ports()}                    # tous les ports
        after = {p.device for p in self._list_ports()}
        if after != before:
            for d in sorted(after - before):
                self.log(_("Port détecté : {0}").format(d), "INFO")
            for d in sorted(before - after):
                self.log(_("Port retiré : {0}").format(d), "INFO")
            self.refresh_ports(check=True)
        # Le port connecté a disparu de la liste : adaptateur USB retiré
        if self.link.mode == SERIAL and self.link.connected and self.link.port not in present:
            self.on_lost(_("le port a disparu (câble débranché ?)"))
        self.after(self.PORTS_REFRESH_MS, self._watch_ports)   # reprogramme la tâche

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------
    def toggle(self):
        """Bouton Connecter / Déconnecter."""
        if self.link.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Ouvre le port sélectionné avec les réglages affichés (ou se connecte au serveur TCP)."""
        if self.link.mode == TCP:
            self._connect_tcp()
            return
        dev = self.selected_device()
        if not dev:
            self.log(_("Aucun port sélectionné"), "ERR")
            return
        try:
            fmt = self._read_format()
        except ValueError as e:                 # vitesse saisie invalide
            self.log(str(e), "ERR")
            return
        try:
            self.link.connect(dev, **fmt)
        except ConnectionError as e:            # port occupé, absent...
            self.log(_("Connexion impossible : {0}").format(tr(str(e))), "ERR")
            self.check_selected()
            return
        # À l'ouverture, DTR et RTS sont inactifs (voir core/serial_link.py)
        self.dtr_var.set(False)
        self.rts_var.set(False)
        # Mémorise le port et les réglages pour le prochain lancement
        self.settings.update(port=dev, **fmt)
        self.settings.save()
        self.log(_("Connecté : {0}").format(self.link.describe()), "INFO")
        self._update_state()
        self.check_selected()
        self.on_change()

    def _connect_tcp(self):
        """Connexion au serveur TCP saisi ; adresse et port mémorisés."""
        host = self.host_var.get().strip()
        try:
            port = int(self.tcp_port_var.get())
        except ValueError:
            self.log(_("Port TCP invalide : '{0}'").format(self.tcp_port_var.get()), "ERR")
            return
        try:
            self.link.connect(host, port)
        except ConnectionError as e:
            self.log(_("Connexion impossible : {0}").format(tr(str(e))), "ERR")
            return
        self.settings.update(tcp_host=host, tcp_port=port)
        self.settings.save()
        self.log(_("Connecté : {0}").format(self.link.describe()), "INFO")
        self._update_state()
        self.on_change()

    def disconnect(self, reason=None):
        """Ferme le port. `reason` : cause d'une déconnexion non demandée (journalisée en erreur)."""
        was = self.link.connected
        self.link.disconnect()
        if was or reason:
            self.log(_("Déconnecté : {0}").format(tr(str(reason))) if reason else _("Déconnecté"), "ERR" if reason else "INFO")
        self._update_state()
        self.refresh_ports(check=True)
        self.on_change()

    def on_lost(self, reason):
        """Appelée quand la liaison tombe (erreur de lecture, câble retiré...)."""
        if self.link.connected:
            self.disconnect(reason=_("perte de connexion — {0}").format(tr(str(reason))))

    def _update_state(self):
        """Met à jour le voyant, le texte d'état et active / désactive les commandes."""
        connected = self.link.connected
        if connected:
            self.link_dot.config(foreground=GREEN, font=DOT_FONT_ON)     # gros voyant vert
            self.link_state.config(text=_("Connecté — {0}").format(self.link.describe()))
            self.connect_btn.config(text=_("Déconnecter"))
            self.port_cb.config(state="disabled")       # on ne change pas de port en étant connecté
        else:
            self.link_dot.config(foreground=GREY, font=DOT_FONT)
            self.link_state.config(text=_("Déconnecté"))
            self.connect_btn.config(text=_("Connecter"))
            self.port_cb.config(state="readonly")
            self.counters.config(text="")
        # DTR / RTS ne sont utilisables qu'une fois connecté, en série
        for cb in (self.dtr_cb, self.rts_cb):
            cb.state(["!disabled"] if connected and self.link.mode == SERIAL else ["disabled"])
        # Pas de changement de liaison pendant une connexion
        for b in self.mode_btns:
            b.state(["disabled"] if connected else ["!disabled"])

    def _update_counters(self):
        """Tâche périodique : affiche les octets envoyés / reçus."""
        if self.link.connected:
            self.counters.config(text=_("TX {0} o   RX {1} o").format(self.link.tx_bytes, self.link.rx_bytes))
        self.after(self.COUNTERS_REFRESH_MS, self._update_counters)

    # ------------------------------------------------------------------
    # Réglages
    # ------------------------------------------------------------------
    def _read_format(self):
        """Lit les réglages affichés. Retourne un dict prêt pour link.connect / link.reconfigure.

        Lève ValueError si la vitesse saisie n'est pas un nombre valide.
        """
        try:
            baud = int(self.baud_var.get())
        except ValueError:
            raise ValueError(_("Vitesse invalide : '{0}'").format(self.baud_var.get()))
        if not 50 <= baud <= 4_000_000:
            raise ValueError(_("Vitesse hors limites : {0}").format(baud))
        return dict(
            baudrate=baud,
            bytesize=int(self.bytesize_var.get()),
            parity=_key_of(PARITY_LABELS, self.parity_var.get()),
            stopbits=self.stop_var.get(),
            flow=_key_of(FLOW_LABELS, self.flow_var.get()),
        )

    def _apply_format(self, _event=None):
        """Un réglage a changé : on le mémorise, et on l'applique au port si connecté."""
        try:
            fmt = self._read_format()
        except ValueError as e:
            self.log(str(e), "ERR")
            # Remet la dernière vitesse valide dans le champ
            self.baud_var.set(str(self.link.config.get("baudrate", self.settings["baudrate"])))
            return
        self.settings.update(fmt)
        self.settings.save()
        if not self.link.connected:
            return
        # Rien n'a changé (ex. Entrée sans modification) : on ne touche pas au port
        if all(self.link.config.get(k) == v for k, v in fmt.items()):
            return
        try:
            self.link.reconfigure(**fmt)
        except ConnectionError as e:
            self.log(str(e), "ERR")
            return
        self.log(_("Réglages appliqués : {0}").format(self.link.describe()), "INFO")
        self._update_state()

    def _apply_lines(self):
        """Cases DTR / RTS cochées ou décochées."""
        self.link.set_lines(dtr=self.dtr_var.get(), rts=self.rts_var.get())
