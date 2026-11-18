"""
ui/protocol/query.py — Partie requête (TX) de l'onglet Protocole.

    - choix de la commande dans la bibliothèque (ou saisie manuelle)
    - données prédéfinies ("presets") ; en saisie manuelle, DATA en hexa
    - trame complète détaillée : les champs "tx" de DATA (en bleu) se modifient
      directement dans le tableau : colonne Valeur (valeur convertie, en unité réelle ou
      choix) ou colonne Hexa (octets bruts du champ) ; clic sur la cellule, ou double-clic
    - ligne DATA (en bleu) : DATA brute modifiable en hexa ; les champs affichent alors le
      décodage de ces octets (un champ modifié ensuite change ses octets dans la DATA brute ;
      données prédéfinies ou DATA vidée : retour aux valeurs des champs)
    - trame hexa sur toute la largeur, boutons Sauvegarder / Copier / Envoyer / « → Replay » dessous
"""
import tkinter as tk
from tkinter import ttk

from core.commands import (DataField, decode_fields, defaults, effective_range, encode_field, field_size,
                           field_type, format_physical, is_choice, type_label)
from core.frames import parse_hex, parse_int, to_hex
from core.protocol import QUERY
from core.request_message import make_request_message
from ui.hexview import HexView, protocol_segments
from ui.save_dialog import ask_message_name, file_name_for

from .constants import GREY, MANUAL, MANUAL_DATA, MONO, REPLAY_ARROW
from .widgets import FieldTable
from ui.tooltip import ToolTip
from ui.i18n import _, tr


class QueryMixin:
    def _build_query_box(self, parent):
        """Cadre de la requête (TX), sans titre pour gagner une ligne."""
        box = ttk.LabelFrame(parent, padding=6)

        # --- Choix de la commande
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text=_("CMD TX"), width=12).pack(side="left")
        self.cmd_choice = tk.StringVar(value=MANUAL)
        # Liste modifiable : taper filtre les commandes (nom, catégorie ou COMMAND ID), les
        # propositions s'ouvrent sous le champ ; ☆ / ★ : favoris (command_search.py)
        self.cmd_cb = ttk.Combobox(row, textvariable=self.cmd_choice, values=[MANUAL])
        self.cmd_cb.pack(side="left", fill="x", expand=True)
        ToolTip(self.cmd_cb, _("Taper pour chercher (nom, catégorie, COMMAND ID : « consigne », « READ », « 0x1E ») : "
                               "les propositions s'ouvrent ; ↑ ↓ puis Entrée, ou clic"))
        self._build_search(row, box)
        # Case « Masquées » : ajoute aux listes les commandes "hidden" (obsolètes, internes…).
        # Elles sont toujours reconnues au décodage, cochée ou non. Cachée s'il n'y en a pas.
        self.show_hidden = tk.BooleanVar(value=bool(self.settings.get("show_hidden_commands", False)))
        self.hidden_chk = ttk.Checkbutton(row, text=_("Masquées"), variable=self.show_hidden,
                                          command=self._on_show_hidden)

        # --- REQUEST ID, COMMAND ID, données prédéfinies, description ; Sauvegarder / Copier à droite
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(4, 0))
        self.rid_var = tk.StringVar(value="0x00")      # en hexa, sur la taille du champ
        self.cmd_var = tk.StringVar(value="0x00000000")
        self.auto_inc = tk.BooleanVar(value=True)
        # Libellés : noms des champs dans le fichier de conf (set_protocol)
        self.rid_lbl = ttk.Label(row, text="REQUEST ID", width=12)
        self.rid_lbl.pack(side="left")
        self.rid_entry = ttk.Entry(row, textvariable=self.rid_var, width=6, font=MONO)
        self.rid_entry.pack(side="left")
        # « REQ+ » : REQUEST ID incrémenté après chaque envoi réussi (légende en infobulle)
        req_plus = ttk.Checkbutton(row, text="REQ+", variable=self.auto_inc)
        req_plus.pack(side="left", padx=(4, 16))
        ToolTip(req_plus, _("auto req_id : REQUEST ID +1 après chaque envoi réussi (0xFF → 0x00)"))
        self.cmd_lbl = ttk.Label(row, text="COMMAND ID")
        self.cmd_lbl.pack(side="left")
        self.cmd_entry = ttk.Entry(row, textvariable=self.cmd_var, width=12, font=MONO)
        self.cmd_entry.pack(side="left", padx=4)
        # Envoyer à portée de main pour un Get (bit 31 du COMMAND ID à 0) : même action que le
        # bouton Envoyer du bas ; masqué pour un Set et en saisie manuelle (_update_get_send)
        self.get_send_btn = ttk.Button(row, text=_("Envoyer"), command=self.send_query)
        ToolTip(self.get_send_btn, _("Envoie la requête (Get), comme le bouton Envoyer en bas"))
        # Format de trame, pour un protocole à variantes (M-Bus : court / long ; Profibus : SD1 / SD2…).
        # Caché s'il n'y a qu'un format (set_protocol).
        self.variant_var = tk.StringVar()
        self.variant_lbl = ttk.Label(row, text="Format")
        self.variant_cb = ttk.Combobox(row, textvariable=self.variant_var, state="readonly", width=16)
        self.variant_cb.bind("<<ComboboxSelected>>", lambda e: self.update_query())
        # Sauvegarder… et Copier, tout à droite de la ligne (placés avant la description,
        # qui prend la place restante et se coupe si elle est trop longue)
        ttk.Button(row, text=_("Copier"), command=self._copy_query).pack(side="right", padx=(4, 0))
        if self.on_save:
            ttk.Button(row, text=_("Sauvegarder…"), command=self._save_query).pack(side="right")
        # Données prédéfinies ("presets" de la commande) : liste affichée seulement si la
        # commande en a (_build_form)
        self.preset_var = tk.StringVar(value=MANUAL_DATA)
        self.preset_cb = ttk.Combobox(row, textvariable=self.preset_var, state="readonly",
                                      values=[MANUAL_DATA], width=22)
        self.preset_cb.bind("<<ComboboxSelected>>", lambda e: self._on_preset())
        ToolTip(self.preset_cb, _("Données prédéfinies de la commande"))
        # Description de la commande (en gris, une seule ligne)
        self.desc_lbl = ttk.Label(row, foreground=GREY)
        self.desc_lbl.pack(side="left", padx=(12, 8), fill="x", expand=True)
        # DATA en hexa en saisie manuelle : modifiée dans la ligne DATA du tableau
        self.data_var = tk.StringVar()
        self.data_var.trace_add("write", lambda *_: self.update_query())
        for var in (self.rid_var, self.cmd_var):
            var.trace_add("write", lambda *_: self.update_query())

        # --- Trame complète détaillée : la hauteur du tableau suit son nombre de lignes, pour
        # que toute la trame soit visible. Les champs de DATA se modifient dans le tableau :
        # colonne Valeur (valeur convertie) ou Hexa (octets bruts du champ).
        self.query_table = FieldTable(box, height=8, fit=(4, 40))
        self.query_table.set_editor(self._edit_spec, self._on_cell_edit,
                                    hex_spec=self._hex_spec, on_hex_commit=self._on_hex_edit)
        self.query_table.pack(fill="both", expand=True, pady=(4, 0))
        self._build_query_bottom(box)
        return box

    def _build_query_bottom(self, box):
        """Bas du cadre, sur une seule ligne : trame hexa, puis Envoyer et « → Replay » à droite.
        Placé en bas AVANT le tableau (before=...) : toujours visible, c'est le tableau qui
        rétrécit si la place manque."""
        bottom = ttk.Frame(box)
        bottom.pack(side="bottom", fill="x", pady=(4, 0), before=self.query_table)
        # Boutons placés en premier, à droite : ils restent visibles
        if self.on_to_replay:
            ttk.Button(bottom, text=REPLAY_ARROW, command=self._query_to_replay).pack(side="right", padx=(4, 0))
        self.send_btn = ttk.Button(bottom, text=_("Envoyer"), command=self.send_query)
        self.send_btn.pack(side="right", padx=(8, 0))
        # Trame en couleurs (en-tête gris, COMMAND ID gras, CRC vert) : la place restante, et
        # autant de lignes qu'il faut (4 au plus) pour la voir en entier
        self.query_hex = HexView(bottom, height=1, max_lines=4)
        self.query_hex.pack(side="left", fill="x", expand=True)

    def _update_get_send(self):
        """Bouton Envoyer de la ligne COMMAND ID : visible pour une commande Get seulement."""
        is_get = self.cmd is not None and not (self.cmd.id & 0x80000000)
        if is_get and not self.get_send_btn.winfo_manager():
            self.get_send_btn.pack(side="left", padx=(8, 0), after=self.cmd_entry)
        elif not is_get and self.get_send_btn.winfo_manager():
            self.get_send_btn.pack_forget()

    def _on_command(self):
        """Commande choisie dans la liste : COMMAND ID et formulaire suivent. Les cadres Requête
        et Réponse reviennent en gris clair (s'ils montraient une ligne du Replay)."""
        self.clear_highlight()
        if self.cmd_choice.get() not in self._cmd_labels:
            self.cmd_choice.set(MANUAL)
        self._cmd_current = self.cmd_choice.get()
        self.cmd = self.lib.by_label(self.cmd_choice.get())
        self._update_get_send()
        self._refresh_favorites()
        if self.cmd:
            self.cmd_var.set(self._cmd_hex(self.cmd.id))
            self.cmd_entry.state(["readonly"])          # fixé par la commande
            self.desc_lbl.config(text=self._command_description(self.cmd))
            if self.cmd.variant in self.proto.variant_names(QUERY):
                self.variant_var.set(self.cmd.variant)  # format de trame imposé par la commande
        else:
            self.cmd_entry.state(["!readonly"])
            self.desc_lbl.config(text="")
        self.preset_var.set(MANUAL_DATA)
        self._build_form()
        self.update_query()

    def _build_form(self):
        """Liste des données prédéfinies : affichée (avant la description) seulement si la commande
        en a. DATA (champs, ou hexa brut en saisie manuelle) se modifie dans le tableau de la trame."""
        presets = [p["name"] for p in self.cmd.presets] if self.cmd else []
        if presets:
            self.preset_cb["values"] = [MANUAL_DATA] + presets
            self.preset_cb.pack(side="left", padx=(12, 0), before=self.desc_lbl)
        else:
            self.preset_cb.pack_forget()
        if self.cmd is not None:
            # Valeurs mémorisées pour cette commande, sinon valeurs par défaut du JSON
            self.tx_values.setdefault(self.cmd.label, {k: str(v) for k, v in defaults(self.cmd.tx).items()})

    # ------------------------------------------------------------------
    # Champs de DATA modifiés dans le tableau
    # ------------------------------------------------------------------
    DATA_IID = "data"                   # identifiant de la ligne DATA du tableau

    def _tx_field(self, iid):
        """Champ "tx" d'une ligne du tableau ("tx:<n>"), ou None."""
        if self.cmd is None or not str(iid).startswith("tx:"):
            return None
        i = int(str(iid)[3:])
        return self.cmd.tx[i] if i < len(self.cmd.tx) else None

    def _edit_spec(self, iid):
        """Éditeur d'une ligne : (texte actuel, choix possibles ou None) ; None si non modifiable."""
        if iid == self.DATA_IID:
            if self.cmd is None:
                return self.data_var.get(), None
            data, _errors = self._build_data()
            return to_hex(data), None
        fdef = self._tx_field(iid)
        if fdef is None:
            return None
        text = self.tx_values.get(self.cmd.label, {}).get(fdef["name"], "")
        if field_type(fdef) == "bool":
            return ("1" if text.lower() in ("1", "true", "on", "oui", "yes") else "0"), ["0", "1"]
        if is_choice(fdef):
            return text, list(fdef["choices"])
        return text, None

    def _on_cell_edit(self, iid, text):
        """Valeur saisie dans le tableau : mémorisée, menu repassé en « saisie à la main »."""
        if iid == self.DATA_IID:
            self._on_raw_edit(text)
            return
        fdef = self._tx_field(iid)
        if fdef is None:
            return
        self.tx_values.setdefault(self.cmd.label, {})[fdef["name"]] = text
        raw = self.raw_data.get(self.cmd.label)
        if raw is not None and not self._patch_raw(fdef, text, raw):
            self.raw_data.pop(self.cmd.label, None)    # taille différente : retour aux valeurs des champs
        self.preset_var.set(MANUAL_DATA)
        self.update_query()

    def _on_raw_edit(self, text):
        """DATA brute saisie (hexa) sur la ligne DATA. Commande : les champs affichent le décodage
        de ces octets ; DATA vidée = retour aux valeurs des champs. Saisie manuelle : champ Données."""
        try:
            raw = parse_hex(text)
        except ValueError:
            self.query_hex.show_error(_("Erreur : {0}").format(_("DATA : hexa invalide")))
            return
        if self.cmd is None:
            self.data_var.set(to_hex(raw))              # update_query via la trace
            return
        if raw:
            self.raw_data[self.cmd.label] = raw
        else:
            self.raw_data.pop(self.cmd.label, None)
        self.preset_var.set(MANUAL_DATA)
        self.update_query()

    def _hex_spec(self, iid):
        """Colonne Hexa d'un champ de DATA : ses octets bruts en hexa, ou None (non modifiable).
        La ligne DATA se modifie dans sa colonne Valeur (DATA complète en hexa)."""
        fdef = self._tx_field(iid)
        if fdef is None:
            return None
        part = self._field_bytes(fdef)
        return None if part is None else to_hex(part[1])

    def _field_bytes(self, fdef):
        """(DATA actuelle, octets du champ, position du champ dans DATA), ou None si DATA ne se
        découpe pas selon la commande."""
        data, _errors = self._build_data()
        fields, _problems = decode_fields(self.cmd.tx, data, self.cfg)
        i = self.cmd.tx.index(fdef)
        if i >= len(fields):
            return None
        return data, fields[i].raw, fields[i].start

    def _on_hex_edit(self, iid, text):
        """Octets bruts d'un champ saisis dans la colonne Hexa : remplacés dans DATA, qui devient
        une DATA brute (les champs montrent son décodage). Même taille obligatoire."""
        fdef = self._tx_field(iid)
        if fdef is None:
            return
        try:
            new = parse_hex(text)
        except ValueError:
            self.query_hex.show_error(_("Erreur : {0}").format(_("DATA : hexa invalide")))
            return
        part = self._field_bytes(fdef)
        if part is None:
            return
        data, old, start = part
        if len(new) != len(old):
            name = fdef.get("label") or fdef["name"]
            self.query_hex.show_error(_("Erreur : {0}").format(
                _("{0} : {1} octet(s) attendu(s)").format(name, len(old))))
            return
        self.raw_data[self.cmd.label] = data[:start] + new + data[start + len(old):]
        self.preset_var.set(MANUAL_DATA)
        self.update_query()

    def _patch_raw(self, fdef, text, raw):
        """Champ modifié alors que la DATA brute est saisie : ses octets sont remplacés dans la
        DATA brute (même taille). Retourne False si ce n'est pas possible."""
        fields, _problems = decode_fields(self.cmd.tx, raw, self.cfg)
        i = self.cmd.tx.index(fdef)
        if i >= len(fields):
            return False
        try:
            new = encode_field(fdef, text, self.cfg)
        except ValueError:
            return False
        start, old = fields[i].start, fields[i].raw
        if len(new) != len(old):
            return False
        self.raw_data[self.cmd.label] = raw[:start] + new + raw[start + len(old):]
        return True

    def _field_info(self, fdef):
        """Colonne Description d'un champ de DATA : 'float · 0 … 100 % · défaut 50'."""
        parts = [self._type_text(fdef)]
        lo, hi, _lo_src, _hi_src = effective_range(fdef)
        if lo is not None or hi is not None:
            fmt = lambda v: "" if v is None else format_physical(fdef, v, with_unit=False)
            parts.append(f"{fmt(lo)} … {fmt(hi)} {fdef.get('unit') or ''}".strip())
        default = self._default_text(fdef)
        if default:
            parts.append(_("défaut {0}").format(default))
        return " · ".join(parts)

    def _command_description(self, cmd):
        """Description de la commande (langue choisie), suivie de ses attributs libres."""
        _name, description = cmd.text(self.proto.language)
        category = self.proto.category_text(cmd.group) if cmd.group else ""
        if category and category != cmd.group:
            description = f"{category} — {description}"     # « Lecture — Lire consigne et mode »
        extra = cmd.attributes_text()
        return f"{description}   [{extra}]" if extra else description

    def _header_values(self):
        """Valeurs des champs d'en-tête : REQUEST ID, COMMAND ID, puis "header" de la commande."""
        values = {}
        if self.proto.has(QUERY, "request_id"):
            values["request_id"] = parse_int(self.rid_var.get())
        if self.proto.has(QUERY, "command_id"):
            values["command_id"] = parse_int(self.cmd_var.get())
        if self.cmd:
            for key, value in self.cmd.header.items():
                values[key] = parse_int(value)
        return values

    def _variant(self):
        """Format de trame choisi, ou None (protocole à un seul format)."""
        return self.variant_var.get() or None if self.proto.variant_names(QUERY) else None

    @staticmethod
    def _default_text(fdef):
        """Valeur par défaut du JSON, mise en forme ('12.5', 'on'...), ou '' si absente."""
        d = fdef.get("default")
        if d is None:
            return ""
        if isinstance(d, (int, float)) and not isinstance(d, bool) and not is_choice(fdef):
            return format_physical(fdef, d, with_unit=False)
        return str(d)

    @staticmethod
    def _type_text(fdef):
        """Type et conversion : 'uint16 ×0.1', 'uint8[4] ip', 'uint16 ×0.001 +2.5'."""
        text = type_label(fdef)
        factor, offset = fdef.get("factor"), fdef.get("offset")
        if factor not in (None, 1):
            text += f" ×{factor:g}" if isinstance(factor, (int, float)) else f" ×{factor}"
        if offset not in (None, 0):
            text += f" +{offset:g}" if isinstance(offset, (int, float)) else f" +{offset}"
        return text

    def _on_preset(self):
        """Données prédéfinies choisies : les champs prennent ces valeurs (modifiables ensuite)."""
        preset = next((p for p in self.cmd.presets if p["name"] == self.preset_var.get()), None) if self.cmd else None
        if preset is None:
            return                      # « saisie à la main » : on garde les valeurs actuelles
        values = {k: str(v) for k, v in defaults(self.cmd.tx).items()}
        values.update({k: str(v) for k, v in preset["values"].items()})
        self.tx_values[self.cmd.label] = values
        self.raw_data.pop(self.cmd.label, None)         # DATA brute saisie : oubliée
        self.update_query()

    # ------------------------------------------------------------------
    # Requête : calcul, envoi, copie
    # ------------------------------------------------------------------
    def _build_data(self):
        """Octets DATA et erreurs : (data, {n° du champ: message}).

        Commande : champs "tx" encodés ; un champ invalide est remplacé par sa valeur par défaut
        (ou des zéros) pour que la trame reste affichée, et signalé. DATA brute saisie sur la
        ligne DATA : ces octets tels quels. Saisie manuelle : hexa (ValueError si invalide).
        """
        if self.cmd is None:
            return parse_hex(self.data_var.get()), {}
        if self.cmd.label in self.raw_data:
            return self.raw_data[self.cmd.label], {}
        values = self.tx_values.setdefault(self.cmd.label, {k: str(v) for k, v in defaults(self.cmd.tx).items()})
        data, errors = b"", {}
        for i, fdef in enumerate(self.cmd.tx):
            try:
                data += encode_field(fdef, values.get(fdef["name"], ""), self.cfg)
            except ValueError as e:
                errors[i] = tr(str(e))
                data += self._placeholder(fdef)
        return data, errors

    def _placeholder(self, fdef):
        """Octets d'un champ invalide, le temps de l'affichage : valeur par défaut, sinon zéros."""
        try:
            return encode_field(fdef, defaults([fdef]).get(fdef["name"], ""), self.cfg)
        except ValueError:
            return bytes(field_size(fdef) or 0)

    def _data_rows(self, errors):
        """Lignes de DATA du tableau : identifiant (modifiable), description, erreur éventuelle."""
        if self.cmd is None:
            return None
        values = self.tx_values.get(self.cmd.label, {})
        rows = []
        for i, fdef in enumerate(self.cmd.tx):
            row = {"iid": f"tx:{i}", "desc": self._field_info(fdef)}
            if i in errors:
                row.update(value=values.get(fdef["name"], ""), check=_("invalide : {0}").format(errors[i]), ok=False)
            rows.append(row)
        return rows

    def _raw_row(self, data):
        """Ligne DATA du tableau (modifiable en hexa brut)."""
        if self.cmd is not None and self.cmd.label in self.raw_data:
            desc = _("DATA brute saisie : les champs montrent son décodage ; vider DATA = valeurs des champs")
        elif self.cmd is not None:
            desc = _("Octets des champs ci-dessous ; modifiable en hexa (DATA brute)")
        else:
            desc = _("Modifiable en hexa (comme le champ Données)")
        return {"iid": self.DATA_IID, "desc": desc, "check": _("{0} octet(s)").format(len(data))}

    def update_query(self):
        """Recalcule la requête et l'affiche (tableau + hexa)."""
        try:
            data, errors = self._build_data()
            frame = self.proto.build(QUERY, data, self._header_values(), variant=self._variant())
        except ValueError as e:
            self._frame = None
            self.query_table.show(None)
            self.query_hex.show_error(_("Erreur : {0}").format(tr(str(e))))
            return
        d = self.proto.decode(frame, QUERY)
        fields = None
        if self.cmd and d.data and d.data.raw:
            fields, _problems = decode_fields(self.cmd.tx, d.data.raw, self.cfg, base=d.data.start)
        elif self.cmd and self.cmd.tx:
            # DATA vide (champ en hexa encore vide…) : lignes affichées quand même, pour la saisie
            values = self.tx_values.get(self.cmd.label, {})
            fields = [DataField(f.get("label") or f["name"], d.data.start if d.data else 0, b"",
                                values.get(f["name"], "")) for f in self.cmd.tx]
        self.query_table.show(d, fields, data_rows=self._data_rows(errors), data_row=self._raw_row(data))
        if errors:                              # trame affichée pour corriger, mais pas envoyable
            self._frame = None
            first = next(iter(errors))
            self.query_hex.show_error(_("Erreur : {0}").format(
                f"{self.cmd.tx[first].get('label') or self.cmd.tx[first]['name']} : {errors[first]}"))
            return
        self._frame = frame
        self.query_hex.show(frame, protocol_segments(d, self.proto, data=True), _("   ({0} octets)").format(len(frame)))

    def send_query(self):
        """Bouton Envoyer. Avec « +1 », le REQUEST ID est incrémenté après un envoi réussi."""
        if self._frame is None:
            return False
        rid = self.proto.decode(self._frame, QUERY).request_id
        self._sending_cmd = self.cmd            # retenue par on_sent pour décoder la réponse
        ok = self.on_send(self._frame, self._query_label())
        self._sending_cmd = None
        if ok and rid is not None and self.auto_inc.get():
            maxi = self.proto.max_value(QUERY, "request_id")
            self.rid_var.set(self._rid_hex((rid + 1) % (maxi + 1)))      # 0xFF -> 0x00 sur 1 octet
        return ok

    def _query_label(self):
        """Libellé de la requête pour le journal et la trace : « Lire consigne et mode #0x01 »."""
        rid = self.proto.decode(self._frame, QUERY).request_id
        name = self.cmd.name if self.cmd else _("requête")
        return f"{name} #{self._rid_hex(rid)}" if rid is not None else name

    def _query_to_replay(self):
        """Flèche « → Replay » : la requête va dans la ligne sélectionnée du replay."""
        if self._frame is not None:
            self.on_to_replay(self._frame, self._query_label())

    def _save_query(self):
        """Bouton « Sauvegarder… » : la requête devient un message de l'onglet Manuel
        (REQUEST ID, COMMAND ID et DATA, trame recalculée par le protocole à l'envoi)."""
        if self._frame is None:
            return
        d = self.proto.decode(self._frame, QUERY)
        # Nom du message ; le fichier proposé (Msg_<nom>.json) s'affiche en direct
        name = ask_message_name(self, self.cmd.name if self.cmd else _("Requête"))
        if not name or not name.strip():
            return
        description = self._command_description(self.cmd) if self.cmd else ""
        command_id = d.command_id if d.command_id is not None else parse_int(self.cmd_var.get())
        digits = self.cmd.id_digits if self.cmd else max(2, len(self.cmd_var.get().strip()) - 2)
        msg = make_request_message(name.strip(), command_id, d.data.raw if d.data else b"",
                                   request_id=d.request_id, header=self.cmd.header if self.cmd else None,
                                   variant=self._variant(), description=description,
                                   protocol=self.proto.name, id_digits=digits)
        self.on_save(msg, file_name_for(msg["name"]))   # proposé dans l'explorateur, modifiable

    def set_send_enabled(self, enabled):
        """Envoyer grisé tant que la liaison n'est pas connectée (Copier / Sauvegarder restent actifs)."""
        for btn in (self.send_btn, self.get_send_btn):
            btn.state(["!disabled"] if enabled else ["disabled"])

    def _copy_query(self):
        """Bouton Copier : trame hexa dans le presse-papiers."""
        if self._frame is not None:
            self.clipboard_clear()
            self.clipboard_append(to_hex(self._frame))

    # ------------------------------------------------------------------
    # Réponse : décodage
