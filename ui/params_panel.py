"""
ui/params_panel.py — Panneau « Paramètres » (onglet Manuel, à droite des messages).

Pour le message sélectionné :
    - génère un formulaire d'après la définition "params" du JSON
      (champ texte, liste déroulante pour enum, case à cocher pour bool) ;
      message de protocole ("request") : REQUEST ID, COMMAND ID et DATA modifiables
    - affiche la trame résultante en direct, checksum compris
    - envoie la trame une fois, ou périodiquement (« Répéter toutes les … ms »)

Les valeurs saisies sont écrites dans un dict fourni par l'application
(un dict par message) : elles sont conservées quand on change de message.
"""
import tkinter as tk
from tkinter import ttk

from core.commands import defaults, encode_field, field_size, input_text, int_bytes, int_text, is_choice, split_data, type_label
from core.frames import frame_segments, parse_hex, to_hex, TRUTHY
from core.messages import display_name
from core.request_message import is_request, params_of
from ui.hexview import HexView, message_segments
from ui.i18n import _, tr
from ui.theme import data_entry_style

DATA_TYPES = ("hex", "raw")             # octets bruts : en bleu, nombre d'octets affiché en direct

MONO = ("Consolas", 10)     # police à chasse fixe pour les saisies hexa / numériques


class ParamsPanel(ttk.Frame):
    def __init__(self, master, on_send, on_to_replay=None, build=None, lookup=None):
        """
        on_send(idx) -> bool : envoie le message idx, retourne False en cas d'échec
        on_to_replay(idx)    : flèche « → Replay » : la trame va dans la ligne sélectionnée du replay
        build(msg, values)   : (octets, segments de couleur) de la trame ; ValueError si invalide.
                               Par défaut : d'après "frame" (messages de protocole : fourni par
                               l'application, qui connaît le protocole en cours)
        lookup(msg, values)  : (commande de la bibliothèque ou None, protocol) pour un message de
                               protocole : sert à convertir DATA <-> valeurs (section « Valeur »)
        """
        super().__init__(master, padding=8)
        self.on_send = on_send
        self.on_to_replay = on_to_replay
        self.build = build or self._build_frame
        self.lookup = lookup
        self._vars = {}                 # nom du paramètre -> variable Tk
        self._conv = None               # section « Valeur » : commande, protocole, champs
        self._syncing = False           # True pendant une mise à jour croisée DATA <-> valeurs
        self.hexa_var = tk.BooleanVar(value=False)      # valeurs entières en hexa (sinon décimal)
        self.idx = None                 # position du message affiché
        self.msg = None                 # définition du message affiché
        self._counts = {}
        self.values = None              # valeurs de ses paramètres (dict partagé avec l'application)
        self._periodic_job = None       # identifiant de la prochaine exécution périodique (after)

        # --- En-tête : nom et description du message
        self.title_lbl = ttk.Label(self, font=("Segoe UI", 12, "bold"))
        self.title_lbl.pack(anchor="w")
        self.desc_lbl = ttk.Label(self, foreground="gray", wraplength=600, justify="left")
        self.desc_lbl.pack(anchor="w", pady=(2, 0))
        # Protocole pour lequel le fichier du message a été écrit (clé "protocol")
        self.proto_lbl = ttk.Label(self, foreground="gray")
        self.proto_lbl.pack(anchor="w", pady=(0, 8))

        # --- Formulaire, regénéré à chaque changement de message
        self.form = ttk.Frame(self)
        self.form.pack(fill="x", anchor="n")
        # --- Valeur convertie de DATA (messages de protocole) : regénérée avec le formulaire
        self.conv = ttk.Frame(self)
        self.conv.pack(fill="x", anchor="n")
        ttk.Separator(self).pack(fill="x", pady=8)

        # --- Aperçu de la trame
        ttk.Label(self, text=_("Trame :")).pack(anchor="w")
        # Trame en couleurs : octets fixes (en-tête) en gris, checksum en vert
        self.preview = HexView(self, height=2)
        self.preview.pack(fill="x", anchor="w", pady=(2, 8))

        # --- Boutons d'envoi
        act = ttk.Frame(self)
        act.pack(anchor="w")
        self.send_btn = ttk.Button(act, text=_("Envoyer"), command=self.send)
        self.send_btn.pack(side="left")
        if self.on_to_replay:
            ttk.Button(act, text=_("→ Replay"), command=self._to_replay).pack(side="left", padx=(4, 0))
        self.periodic_var = tk.BooleanVar()
        self.periodic_chk = ttk.Checkbutton(act, text=_("Répéter toutes les"), variable=self.periodic_var,
                                            command=self._toggle_periodic)
        self.periodic_chk.pack(side="left", padx=(16, 2))
        self.period_var = tk.StringVar(value="1000")
        ttk.Entry(act, textvariable=self.period_var, width=6).pack(side="left")
        ttk.Label(act, text="ms").pack(side="left", padx=2)

        self.clear()

    def set_send_enabled(self, enabled):
        """Envoyer et « Répéter » grisés tant que la liaison n'est pas connectée."""
        for w in (self.send_btn, self.periodic_chk):
            w.state(["!disabled"] if enabled else ["disabled"])

    # ------------------------------------------------------------------
    # Affichage d'un message
    # ------------------------------------------------------------------
    def clear(self):
        """Vide le panneau (aucun message sélectionné)."""
        self.stop_periodic()
        self.idx = self.msg = self.values = None
        for w in self.form.winfo_children():
            w.destroy()
        self._clear_conversion()
        self.title_lbl.config(text=_("Sélectionne un message"))
        self.desc_lbl.config(text="")
        self.proto_lbl.config(text="")
        self.preview.clear()

    def show(self, idx, msg, values, current_protocol=None):
        """Affiche le message `msg` (position `idx`).

        values : dict des valeurs courantes de ses paramètres. Le formulaire
                 le modifie directement : l'application retrouve les valeurs
                 saisies quand on revient sur ce message.
        """
        if idx == self.idx:
            return                      # déjà affiché : on ne regénère pas le formulaire
        self.stop_periodic()            # l'envoi périodique ne suit pas le changement de message
        self.idx, self.msg, self.values = idx, msg, values
        for w in self.form.winfo_children():
            w.destroy()
        self._counts = {}               # champ d'octets -> (libellé d'aide, texte de base)
        self._vars = {}
        self.title_lbl.config(text=display_name(msg))
        self.desc_lbl.config(text=msg.get("description", ""))
        self._show_protocol(msg.get("protocol"), current_protocol)

        params = params_of(msg)
        if not params:
            ttk.Label(self.form, text=_("(aucun paramètre)"), foreground="gray").grid(row=0, column=0, sticky="w")
        for row, (name, pdef) in enumerate(params.items()):
            var = self._add_field(row, name, pdef, values[name])
            self._vars[name] = var
            # À chaque modification du champ : mise à jour de la valeur et de l'aperçu.
            # n=name, v=var figent les valeurs de la boucle dans la fonction.
            var.trace_add("write", lambda *_, n=name, v=var: self._on_change(n, v))
        self.refresh_conversion()
        self.update_preview()

    def _show_protocol(self, made_for, current):
        """« Écrit pour : Modbus RTU », en orange si ce n'est pas le protocole en cours."""
        if not made_for:
            self.proto_lbl.config(text="")
            return
        names = [made_for] if isinstance(made_for, str) else list(made_for)
        other = current and current.lower() not in (n.lower() for n in names)
        text = _("Écrit pour : ") + ", ".join(names) + (_("  (protocole en cours : {0})").format(current) if other else "")
        self.proto_lbl.config(text=text, foreground="#d68910" if other else "gray")

    def _to_replay(self):
        if self.idx is not None and self.on_to_replay:
            self.on_to_replay(self.idx)

    def _add_field(self, row, name, pdef, value):
        """Ajoute une ligne du formulaire : libellé | champ | aide. Retourne la variable Tk du champ."""
        t = pdef.get("type", "u8")
        ttk.Label(self.form, text=pdef.get("label", name)).grid(row=row, column=0, sticky="w", pady=3)
        if t == "bool":
            var = tk.IntVar(value=1 if str(value).lower() in TRUTHY else 0)
            widget = ttk.Checkbutton(self.form, variable=var)
        elif t == "enum":
            var = tk.StringVar(value=str(value))
            widget = ttk.Combobox(self.form, textvariable=var, state="readonly", width=22,
                                  values=list(pdef["choices"]))
        else:
            var = tk.StringVar(value=str(value))
            # Octets bruts et texte : champ plus large (DATA d'un message de protocole…) ;
            # octets bruts en bleu, comme DATA dans les tableaux et l'aperçu
            style = data_entry_style() if t in DATA_TYPES else "TEntry"
            widget = ttk.Entry(self.form, textvariable=var, width=48 if t in ("hex", "raw", "ascii") else 24,
                               font=MONO, style=style)
        widget.grid(row=row, column=1, sticky="w", padx=8)
        hint = ttk.Label(self.form, text=self._hint(t, pdef), foreground="gray")
        hint.grid(row=row, column=2, sticky="w")
        if t in DATA_TYPES:
            self._counts[name] = (hint, self._hint(t, pdef))
            self._update_count(name, str(value))
        return var

    def _update_count(self, name, text):
        """Aide d'un champ d'octets : nombre d'octets en direct (DATA LENGTH recalculée à l'envoi)."""
        hint, base = self._counts[name]
        try:
            n = len(parse_hex(text))
        except ValueError:
            hint.config(text=f"{base}  ·  " + _("hexa invalide"), foreground="#c0392b")
            return
        count = _("{0} octet(s)").format(n)
        if self.msg is not None and is_request(self.msg):
            count += _(" → DATA LENGTH = {0}").format(n)
        hint.config(text=f"{base}  ·  {count}", foreground="gray")

    @staticmethod
    def _hint(t, pdef):
        """Texte d'aide à droite du champ : type, choix possibles, bornes, unité."""
        hint = t
        if t == "enum":
            hint = f"{pdef.get('size', 'u8')} : " + ", ".join(f"{k}={v}" for k, v in pdef["choices"].items())
        if "min" in pdef or "max" in pdef:
            hint += f"  [{pdef.get('min', '…')} – {pdef.get('max', '…')}]"
        if "unit" in pdef:
            hint += f"  {pdef['unit']}"
        return hint

    def _on_change(self, name, var):
        """Un champ a été modifié."""
        try:
            self.values[name] = var.get()
        except tk.TclError:
            return                      # valeur transitoire illisible : on attend la suivante
        if name in self._counts:
            self._update_count(name, str(self.values[name]))
        if self._conv is not None and not self._syncing:
            if name == "command_id":
                self.refresh_conversion()       # autre commande : autre conversion
            elif name == "data":
                self._data_to_values()
        self.update_preview()

    # ------------------------------------------------------------------
    # Valeur convertie de DATA (messages de protocole)
    # ------------------------------------------------------------------
    CONV_COLORS = {True: ("#dff3e4", "#2e9e5b"),     # conversion connue : fond vert, bord vert
                   False: ("#e1ecfa", "#1f5fbf")}    # pas de conversion : DATA lue comme un entier, bleu

    def _clear_conversion(self):
        for w in self.conv.winfo_children():
            w.destroy()
        self._conv = None

    def refresh_conversion(self):
        """Section « Valeur » d'un message de protocole : un champ par valeur de DATA (d'après la
        commande de la bibliothèque, au même COMMAND ID), en vert ; sans commande connue (ou sans
        champ), DATA lue comme un entier, en bleu. Les deux sens sont synchronisés en direct."""
        self._clear_conversion()
        if self.msg is None or not is_request(self.msg) or "data" not in self._vars:
            return
        cmd, cfg = self.lookup(self.msg, self.values) if self.lookup else (None, None)
        order = getattr(cfg, "byte_order", "little") or "little"
        defs = list(cmd.tx) if cmd is not None and cmd.tx else []
        known = bool(defs)
        bg, border = self.CONV_COLORS[known]

        head = ttk.Frame(self.conv)
        head.pack(fill="x", pady=(6, 2))
        ttk.Label(head, text=_("Valeur"), font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Checkbutton(head, text=_("Hexa"), variable=self.hexa_var,
                        command=self._data_to_values).pack(side="left", padx=(12, 0))
        if known:
            status = _("conversion : {0}").format(cmd.name)
        elif cmd is not None:
            status = _("pas de conversion pour « {0} » (pas de DATA décrite) : DATA lue comme un entier").format(cmd.name)
        else:
            status = _("pas de conversion (COMMAND ID inconnu du protocole en cours) : DATA lue comme un entier")
        ttk.Label(head, text=status, foreground=border).pack(side="left", padx=(12, 0))
        if known and cmd.presets:
            # Données prédéfinies de la commande ("presets") : remplissent les valeurs, donc DATA
            preset = ttk.Combobox(head, state="readonly", width=24,
                                  values=[p["name"] for p in cmd.presets])
            preset.set(_("Données prédéfinies…"))
            preset.bind("<<ComboboxSelected>>", lambda e: self._apply_preset(preset.get()))
            preset.pack(side="left", padx=(12, 0))

        grid = ttk.Frame(self.conv)
        grid.pack(fill="x")
        rows = []
        for i, fdef in enumerate(defs or [None]):
            label = (fdef.get("label") or fdef["name"]) if fdef else _("Entier (DATA)")
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            box = tk.Frame(grid, background=border, padx=2, pady=2)     # bord de couleur (tous thèmes)
            box.grid(row=i, column=1, sticky="w", padx=8)
            if fdef is not None and (is_choice(fdef) or fdef.get("type") == "bool"):
                values = list(fdef["choices"]) if is_choice(fdef) else ["0", "1"]
                widget = ttk.Combobox(box, textvariable=var, values=values, state="readonly", width=30)
                widget.bind("<<ComboboxSelected>>", lambda e: self._values_to_data())
            else:
                widget = tk.Entry(box, textvariable=var, width=34, font=MONO, background=bg,
                                  relief="flat", insertbackground="black")
                widget.bind("<KeyRelease>", lambda e: self._values_to_data())
            widget.pack()
            hint = ttk.Label(grid, foreground="gray", text=self._conv_hint(fdef))
            hint.grid(row=i, column=2, sticky="w")
            rows.append((fdef, var, hint))
        self._conv = {"cmd": cmd, "cfg": cfg, "order": order, "rows": rows, "known": known}
        self._data_to_values()

    def _apply_preset(self, name):
        """Données prédéfinies choisies : valeurs par défaut des champs, puis celles du preset."""
        cmd = self._conv["cmd"] if self._conv else None
        preset = next((p for p in cmd.presets if p["name"] == name), None) if cmd else None
        if preset is None:
            return
        values = {k: str(v) for k, v in defaults(cmd.tx).items()}
        values.update({k: str(v) for k, v in preset["values"].items()})
        self._syncing = True
        try:
            for fdef, var, _hint in self._conv["rows"]:
                var.set(values.get(fdef["name"], var.get()))
        finally:
            self._syncing = False
        self._values_to_data()

    @staticmethod
    def _conv_hint(fdef):
        """Aide d'un champ converti : type, unité, plage, choix."""
        if fdef is None:
            return _("entier non signé, ordre du protocole ; recalculé sur le nombre d'octets de DATA")
        parts = [type_label(fdef)]
        if is_choice(fdef):
            parts.append(", ".join(f"{k} = {v}" for k, v in fdef["choices"].items()))
        if fdef.get("unit"):
            parts.append(fdef["unit"])
        if fdef.get("min") is not None or fdef.get("max") is not None:
            parts.append(f"[{fdef.get('min', '…')} – {fdef.get('max', '…')}]")
        return "  ".join(parts)

    def _set_hint(self, hint, fdef, error=None):
        hint.config(text=(_("invalide : {0}").format(tr(error)) if error else self._conv_hint(fdef)),
                    foreground="#c0392b" if error else "gray")

    def _data_to_values(self):
        """DATA (hexa) modifiée : les valeurs converties suivent."""
        if self._conv is None:
            return
        try:
            raw = parse_hex(str(self.values.get("data", "")))
        except ValueError:
            for fdef, _var, hint in self._conv["rows"]:
                self._set_hint(hint, fdef, _("DATA : hexa invalide"))
            return
        hexa = self.hexa_var.get()
        self._syncing = True
        try:
            if not self._conv["known"]:
                fdef, var, hint = self._conv["rows"][0]
                var.set(int_text(raw, self._conv["order"], hexa))
                self._set_hint(hint, fdef)
                return
            parts = split_data([r[0] for r in self._conv["rows"]], raw, self._conv["cfg"])
            if parts is None:
                sizes = [field_size(r[0]) for r in self._conv["rows"]]
                expected = sum(sizes) if None not in sizes else None
                msg = (_("DATA de {0} octet(s), {1} attendu(s)").format(len(raw), expected) if expected is not None
                       else _("DATA de {0} octet(s) : ne correspond pas aux champs").format(len(raw)))
                for fdef, _var, hint in self._conv["rows"]:
                    self._set_hint(hint, fdef, msg)
                return
            for (fdef, var, hint), (_f, part) in zip(self._conv["rows"], parts):
                var.set(input_text(fdef, part, self._conv["cfg"], hexa))
                self._set_hint(hint, fdef)
        finally:
            self._syncing = False

    def _values_to_data(self):
        """Une valeur convertie modifiée : DATA est recalculée (sur le bon nombre d'octets)."""
        if self._conv is None or self._syncing:
            return
        try:
            if self._conv["known"]:
                data = b""
                for fdef, var, hint in self._conv["rows"]:
                    try:
                        data += encode_field(fdef, var.get(), self._conv["cfg"])
                        self._set_hint(hint, fdef)
                    except ValueError as e:
                        self._set_hint(hint, fdef, str(e))
                        return
            else:
                fdef, var, hint = self._conv["rows"][0]
                current = parse_hex(str(self.values.get("data", "")))
                try:
                    data = int_bytes(var.get(), self._conv["order"], len(current))
                    self._set_hint(hint, fdef)
                except ValueError as e:
                    self._set_hint(hint, fdef, str(e))
                    return
        except ValueError:
            return
        self._syncing = True                    # la saisie en cours n'est pas réécrite
        try:
            self._vars["data"].set(to_hex(data))
        finally:
            self._syncing = False

    def update_preview(self):
        """Recalcule et affiche la trame en couleurs. Une valeur invalide est affichée en rouge."""
        if self.msg is None:
            return
        try:
            data, segments = self.build(self.msg, self.values)
        except Exception as e:
            self.preview.show_error(_("Erreur : {0}").format(tr(str(e))))
            return
        self.preview.show(data, segments, _("   ({0} octets)").format(len(data)))

    @staticmethod
    def _build_frame(msg, values):
        """Trame d'après "frame" et "params" : (octets, segments de couleur)."""
        segs = frame_segments(msg, values)
        return b"".join(b for _, b in segs), message_segments(segs)

    # ------------------------------------------------------------------
    # Envoi
    # ------------------------------------------------------------------
    def send(self):
        """Bouton Envoyer. Retourne True si l'envoi a réussi."""
        return self.idx is not None and self.on_send(self.idx)

    def _toggle_periodic(self):
        """Case « Répéter » cochée / décochée."""
        if self._periodic_job:
            self.after_cancel(self._periodic_job)
            self._periodic_job = None
        if self.periodic_var.get():
            self._tick()

    def _tick(self):
        """Un envoi périodique, puis reprogrammation du suivant.

        On utilise after() de Tkinter plutôt qu'un thread : tout reste dans le
        thread de l'interface, sans risque d'accès concurrent.
        """
        self._periodic_job = None
        if not self.periodic_var.get():
            return
        if not self.send():
            # Échec (port déconnecté, valeur invalide) : on arrête la répétition
            self.periodic_var.set(False)
            return
        try:
            ms = max(10, int(self.period_var.get()))    # au moins 10 ms entre deux envois
        except ValueError:
            ms = 1000
        self._periodic_job = self.after(ms, self._tick)

    def stop_periodic(self):
        """Arrête l'envoi périodique (changement de message, déconnexion...)."""
        self.periodic_var.set(False)
        if self._periodic_job:
            self.after_cancel(self._periodic_job)
            self._periodic_job = None
