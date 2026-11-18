"""
ui/protocol/response.py — Partie « Réponse (RX) / décodage » de l'onglet Protocole.

    - décodage des trames reçues (ou collées) : en-tête, code d'erreur, champs de DATA
    - type de réponse : Auto (d'après la requête envoyée), une commande, ou Brut
    - résumé des trames pour le moniteur (describe_frame)
"""
import tkinter as tk
from tkinter import ttk

from core.commands import DataField, decode_fields, describe, describe_parts, field_type, raw_guess
from core.frames import parse_hex, to_hex
from core.protocol import QUERY, RESPONSE

from .constants import AUTO, GREEN, KIND_LABELS, MONO, RAW, RED
from .widgets import FieldTable
from ui.i18n import _, tr


class ResponseMixin:
    def _build_response_box(self, parent):
        """Cadre « Réponse (RX) »."""
        box = ttk.LabelFrame(parent, text=_("Réponse (RX) / décodage"), padding=6)

        row = ttk.Frame(box)
        row.pack(fill="x")
        self.decode_var = tk.StringVar()
        self.kind_var = tk.StringVar(value=KIND_LABELS[RESPONSE])
        entry = ttk.Entry(row, textvariable=self.decode_var, font=MONO)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.decode_entry())
        ttk.Combobox(row, textvariable=self.kind_var, values=list(KIND_LABELS.values()),
                     state="readonly", width=9).pack(side="left", padx=4)
        ttk.Button(row, text=_("Décoder"), command=self.decode_entry).pack(side="left")

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text=_("Type de réponse")).pack(side="left")
        self.rx_type = tk.StringVar(value=AUTO)
        self.rx_cb = ttk.Combobox(row, textvariable=self.rx_type, state="readonly", values=[AUTO, RAW])
        self.rx_cb.pack(side="left", fill="x", expand=True, padx=4)
        self.rx_cb.bind("<<ComboboxSelected>>", lambda e: self.decode_entry())
        self.follow_rx = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text=_("Suivre les réponses reçues"), variable=self.follow_rx).pack(side="left")

        self.decode_summary = ttk.Label(box, text="", wraplength=640, justify="left")
        self.decode_summary.pack(anchor="w", pady=(4, 0))
        # Hauteur qui suit le nombre de lignes : toute la réponse décodée est visible
        self.decode_table = FieldTable(box, height=8, fit=(4, 40))
        self.decode_table.pack(fill="both", expand=True, pady=(2, 0))
        return box

    # ------------------------------------------------------------------
    # Bibliothèque et configuration
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    def on_sent(self, data):
        """Appelée par l'application pour CHAQUE trame envoyée (onglet, messages, hexa libre).

        Si c'est une requête valide, on retient REQUEST ID -> commande pour décoder
        la réponse quand elle arrivera (type de réponse « Auto »). La commande est celle
        choisie dans l'onglet si la trame vient de là, sinon celle du COMMAND ID (et des
        valeurs "match" de DATA). Protocole sans REQUEST ID : la dernière requête compte.
        """
        if not self.proto.matches(data, QUERY):
            return
        d = self.proto.decode(data, QUERY)
        if not d.complete or d.crc_ok is False:
            return
        cmd = self._sending_cmd or self._find_command(d)
        if cmd is not None or d.command_id is not None:
            self.sent[d.request_id] = cmd

    def _find_command(self, d):
        """Commande d'une trame d'après son COMMAND ID et, au besoin, les valeurs "match" de DATA."""
        if d.command_id is None:
            return None
        fields = {}
        for f in d.fields:
            if f.value is not None:
                fields[f.name] = fields[f.role] = f.value
        return self.lib.find(d.command_id, d.data.raw if d.data else b"", self.cfg, fields, d.variant)

    def _command_for(self, d, kind, auto_only=False):
        """Commande à utiliser pour décoder DATA, et comment elle a été trouvée.

        Requête : d'après son COMMAND ID. Réponse : selon « Type de réponse ».
        auto_only : ignore le choix manuel (utilisé pour le journal).
        """
        if kind == QUERY:
            return self._find_command(d), "COMMAND ID"
        choice = AUTO if auto_only else self.rx_type.get()
        if choice == RAW:
            return None, _("brut")
        if choice == AUTO:
            # La requête envoyée avec ce REQUEST ID, sinon le COMMAND ID de la réponse
            cmd = self.sent.get(d.request_id)
            if cmd is None and d.command_id is not None:
                cmd = self.lib.find(d.command_id)
            return cmd, "auto"
        return self.lib.by_label(choice), "manuel"

    def _decode_data(self, d, kind, cmd):
        """Champs de DATA décodés selon la commande, et problèmes rencontrés."""
        if cmd is None:
            return None, []
        defs = cmd.tx if kind == QUERY else cmd.rx
        if kind == RESPONSE and d.error:
            return None, []             # réponse en erreur : DATA n'a pas le format normal
        data_field = d.data
        if data_field is None:
            return None, ([f"données attendues ({len(defs)} champ(s)) mais pas de DATA"]
                          if defs and d.complete else [])
        fields, problems = decode_fields(defs, data_field.raw, self.cfg, base=data_field.start)
        self._add_raw_guesses(defs, fields)
        return fields, problems

    def _raw_fields(self, d):
        """DATA sans définition (commande inconnue ou sans champ) : une ligne avec ses lectures
        possibles (entier, signé, float), pour aider à l'interpréter. None si rien à proposer."""
        data_field = d.data
        if data_field is None or not data_field.raw:
            return None
        guess = raw_guess(data_field.raw, self.proto.byte_order or "little")
        if not guess:
            return None
        return [DataField(_("(non décrite)"), data_field.start, data_field.raw, guess)]

    def _add_raw_guesses(self, defs, fields):
        """Champ en octets bruts (hexa, sans conversion) : lectures possibles ajoutées au texte."""
        for fdef, f in zip(defs, fields):
            if field_type(fdef) == "hex" and f.raw:
                guess = raw_guess(f.raw, self.proto.byte_order or "little")
                if guess:
                    f.text = f"{f.text}  =  {guess}"

    def decode_entry(self):
        """Décode la trame du champ, comme requête ou réponse."""
        try:
            data = parse_hex(self.decode_var.get())
        except ValueError:
            self.decode_table.show(None)
            self.decode_summary.config(text=_("Hexa invalide"), foreground=RED)
            return
        if not data:
            self.decode_table.show(None)
            self.decode_summary.config(text="")
            return
        kind = QUERY if self.kind_var.get() == KIND_LABELS[QUERY] else RESPONSE
        d = self.proto.decode(data, kind)
        cmd, how = self._command_for(d, kind)
        fields, problems = self._decode_data(d, kind, cmd)
        if fields is None and not (kind == RESPONSE and d.error):
            fields = self._raw_fields(d)        # sans définition : lectures possibles de DATA
        self.decode_table.show(d, fields, self.lib)

        text = tr(describe(d, cmd, self.lib))
        if kind == RESPONSE:
            # Indique quelle définition a servi à décoder DATA, et comment elle a été choisie
            label = cmd.name if cmd else (_("aucune commande trouvée") if how == "auto" else _("brut"))
            text += _("   [type : {0}").format(label) + (f", {_(how)}" if how in ("auto", "manuel") else "") + "]"
        if problems:
            text += "   ⚠ " + ", ".join(tr(p) for p in problems)
        bad = not d.ok or problems or (fields and any(f.ok is False for f in fields)) or d.error
        self.decode_summary.config(text=text, foreground=RED if bad else GREEN)

    def show_for_decode(self, data, kind):
        """Affiche une trame dans la partie Réponse, décodée comme `kind` (bouton « Décoder
        dans Protocole » du replay). « Suivre les réponses reçues » est décoché pour que la
        trame reste affichée."""
        self.follow_rx.set(False)
        self.decode_var.set(to_hex(data))
        self.kind_var.set(KIND_LABELS[kind])
        self.decode_entry()

    def on_received(self, data):
        """Appelée par l'application pour chaque trame reçue."""
        if self.follow_rx.get():
            self.decode_var.set(to_hex(data))
            self.kind_var.set(KIND_LABELS[RESPONSE])
            self.decode_entry()

    MAX_VALUES = 8      # nombre maximal de champs de DATA affichés en fin de ligne du moniteur

    def describe_frame(self, direction, data):
        """Résumé pour le journal du moniteur, ou None si la trame n'est pas du protocole.

        TX = requête, RX = réponse (commande retrouvée d'après le REQUEST ID).
        Retourne (morceaux, valeurs) :
            morceaux : résumé découpé, [(texte, ok)] ; ok False = en rouge dans le moniteur
                       [("réponse #0x01", True), ("Lire mesures", True), ("erreur 0 (OK)", True),
                        ("4 o", True), ("CRC OK", True)]
                       Une réponse avec un code d'erreur non nul a son « erreur N (texte) » en rouge.
            valeurs  : [(texte, ok)] — un élément par champ de DATA, converti selon le
                       JSON (type, facteur, offset, unité, choix, bits) :
                       [("Température = 21.5 °C", True)] ; ok False = hors min/max ou bit d'erreur actif
        """
        kind = QUERY if direction == "TX" else RESPONSE
        if not self.proto.matches(data, kind):
            return None
        d = self.proto.decode(data, kind)
        cmd, _how = self._command_for(d, kind, auto_only=True)
        parts = [(tr(text), ok) for text, ok in describe_parts(d, cmd, self.lib)]
        fields, problems = self._decode_data(d, kind, cmd)
        if problems:
            parts.append((", ".join(tr(p) for p in problems), False))
        values = [(f"{f.name} = {tr(f.text)}" + (f" ({tr(f.note)})" if f.ok is False and f.note else ""),
                   f.ok is not False)
                  for f in (fields or [])[:self.MAX_VALUES]]
        if fields and len(fields) > self.MAX_VALUES:
            values.append((_("… {0} autre(s)").format(len(fields) - self.MAX_VALUES), True))
        return parts, values
