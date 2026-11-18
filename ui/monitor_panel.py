"""
ui/monitor_panel.py — Panneau « Moniteur ».

Journal horodaté de tout ce qui se passe sur la liaison :
    TX   (bleu)  trames envoyées
    RX   (violet) trames reçues
    INFO (gris)  connexions, chargement des messages...
    ERR  (rouge) erreurs

Contient aussi :
    - le réglage « Fin de trame après … ms de silence » (découpage des octets reçus)
    - « Décoder protocole » : résumé de chaque trame (requête / réponse, CRC OK...)
    - le champ « Hexa libre » pour envoyer des octets saisis à la main, avec un
      aperçu en couleurs de la trame qui partira et l'option « Calc auto CRC16 »
      (CRC16 Modbus calculé et ajouté en fin de trame)
    - l'export du journal en fichier texte
"""
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from core.frames import parse_hex, to_ascii
from core.trace import TraceEvent, save_trace
from ui.hexview import HexView, configure_tags, hex_chunks
from ui.theme import THEME, ensure_hex_tag
from ui.i18n import _, tr
from ui.tooltip import ToolTip

MONO = ("Consolas", 10)
# Couleur de chaque type de ligne (le tag est passé à log())
# Tag de ligne -> couleur du thème (ui/theme.py, page « Couleurs… »)
LINE_COLORS = {"TX": "tx", "RX": "rx", "INFO": "info", "ERR": "error"}


class MonitorPanel(ttk.Frame):
    # Nombre maximal de lignes conservées : au-delà, les plus anciennes sont supprimées
    # (sinon le journal grossirait sans fin et l'interface ralentirait).
    MAX_LINES = 5000

    def __init__(self, master, gap_ms, on_gap_change, on_send_hex,
                 crc_bytes, annotate=None, decode=True, on_decode_change=None,
                 style=None, on_record=None, on_replay=None,
                 timeout_ms=500, on_timeout_change=None, traces_dir=None):
        """
        gap_ms                 : valeur initiale du délai de fin de trame
        on_gap_change(ms)      : appelée quand l'utilisateur modifie ce délai
        on_send_hex(data)      : envoi des octets saisis dans « Hexa libre »
        crc_bytes(data)        : retourne les octets du CRC principal du protocole de `data`
                                 (crc_bytes(b"") donne sa taille)
                                 (dans l'ordre réglé dans l'onglet Protocole)
        annotate(dir, data)    : résumé protocole d'une trame, ou None si ce n'en est pas une ;
                                 peut aussi retourner (résumé, [(valeur convertie, ok)])
        decode                 : état initial de « Décoder protocole »
        on_decode_change(bool) : appelée quand « Décoder protocole » est coché / décoché
        style(dir, data)       : segments de couleur d'une trame [(début, longueur, tag)], ou None
                                 (en-tête en gris, COMMAND ID en gras, CRC en vert)
        on_record()            : bouton « ● Trace » (démarrer / arrêter l'enregistrement)
        on_replay()            : bouton « + Replay » (trames du moniteur -> nouvelle trace du panneau Replay)
        traces_dir             : dossier proposé par « Sauvegarder… » (trace CSV rejouable)
        timeout_ms             : valeur initiale du « Timeout réponse »
        on_timeout_change(ms)  : appelée quand l'utilisateur modifie ce timeout
        """
        super().__init__(master, padding=4)
        self.on_gap_change = on_gap_change
        self.on_send_hex = on_send_hex
        self.crc_bytes = crc_bytes
        self.annotate = annotate
        self.style = style
        self.traces_dir = traces_dir
        self.frames = []            # trames journalisées [(instant, "TX"/"RX", octets, libellé)] : Sauvegarder, + Replay

        # --- Barre d'options
        opts = ttk.Frame(self)
        opts.pack(fill="x")
        ttk.Label(opts, text=_("Moniteur"), font=("Segoe UI", 10, "bold")).pack(side="left")
        self.show_ascii = tk.BooleanVar(value=True)     # afficher la version texte des trames
        self.show_tx = tk.BooleanVar(value=True)        # afficher les trames envoyées
        self.autoscroll = tk.BooleanVar(value=True)     # suivre les dernières lignes
        ttk.Checkbutton(opts, text="ASCII", variable=self.show_ascii).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(opts, text=_("Afficher TX"), variable=self.show_tx).pack(side="left", padx=6)
        ttk.Checkbutton(opts, text=_("Défilement auto"), variable=self.autoscroll).pack(side="left")
        self.decode = tk.BooleanVar(value=decode)        # résumé protocole à côté des trames
        ttk.Checkbutton(opts, text=_("Décoder protocole"), variable=self.decode,
                        command=lambda: on_decode_change and on_decode_change(self.decode.get())
                        ).pack(side="left", padx=6)
        ttk.Label(opts, text=_("Fin de trame après")).pack(side="left", padx=(12, 2))
        self.gap_var = tk.StringVar(value=str(gap_ms))
        self.gap_var.trace_add("write", self._on_gap)   # appliqué à chaque modification
        ttk.Entry(opts, textvariable=self.gap_var, width=5).pack(side="left")
        ttk.Label(opts, text=_("ms de silence")).pack(side="left", padx=2)
        # Timeout de réponse : délai max entre une requête du protocole et sa réponse
        ttk.Label(opts, text=_("Timeout réponse")).pack(side="left", padx=(12, 2))
        self.timeout_var = tk.StringVar(value=str(int(timeout_ms)))
        self.timeout_var.trace_add("write", lambda *_: self._on_timeout(on_timeout_change))
        ttk.Entry(opts, textvariable=self.timeout_var, width=6).pack(side="left")
        ttk.Label(opts, text="ms").pack(side="left", padx=2)
        save_btn = ttk.Button(opts, text=_("Sauvegarder…"), command=self.save)
        save_btn.pack(side="right")
        ToolTip(save_btn, _("Enregistre les trames du moniteur : en trace CSV (.csv), rejouable dans le "
                            "panneau Replay (Ouvrir…), ou en texte (.txt), tel qu'affiché"))
        clear_btn = ttk.Button(opts, text=_("Effacer"), command=self.clear)
        clear_btn.pack(side="right", padx=4)
        ToolTip(clear_btn, _("Vide le moniteur (et les trames gardées pour Sauvegarder… et + Replay)"))
        # Trace (enregistrement horodaté TX / RX dans un fichier) et replay
        if on_replay:
            replay_btn = ttk.Button(opts, text=_("+ Replay"), command=on_replay)
            replay_btn.pack(side="right", padx=(12, 0))
            ToolTip(replay_btn, _("Copie les trames du moniteur (TX et RX, avec leurs temps) dans le panneau "
                                  "Replay, comme une nouvelle trace à rejouer. Sans trame : affiche le panneau"))
        if on_record:
            self.record_btn = ttk.Button(opts, text=_("● Trace"), command=on_record, width=16)
            self.record_btn.pack(side="right")
            ToolTip(self.record_btn, _("Enregistre au fil de l'eau chaque trame TX / RX dans un fichier "
                                       "de trace CSV ; à l'arrêt, la trace s'ouvre dans le panneau Replay"))

        # --- Zone de texte du journal (en lecture seule : state="disabled")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, pady=4)
        # Lignes non coupées (wrap="none") : barre horizontale pour voir la fin des lignes longues
        self.text = tk.Text(frame, font=MONO, height=10, wrap="none", state="disabled")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        sbx = ttk.Scrollbar(frame, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=sb.set, xscrollcommand=sbx.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        sbx.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        THEME.subscribe(self._apply_line_colors)
        # Déclarés après TX / RX : l'en-tête (gris) et le CRC (vert) gardent leur couleur
        configure_tags(self.text, MONO)

        # --- Champ « Hexa libre »
        # Placées en bas AVANT le journal dans l'ordre de placement (before=frame) :
        # si la fenêtre est petite, c'est le journal qui rétrécit, pas ces lignes.
        free = ttk.Frame(self)
        free.pack(side="bottom", fill="x", before=frame)
        ttk.Label(free, text=_("Hexa libre")).pack(side="left")
        self.free_var = tk.StringVar()
        entry = ttk.Entry(free, textvariable=self.free_var, font=MONO)
        entry.pack(side="left", fill="x", expand=True, padx=4)
        entry.bind("<Return>", lambda e: self._send_free())   # Entrée = Envoyer
        self.free_entry = entry
        # Case « Calc auto CRC » : le CRC principal du protocole (CRC16 pour Modbus RTU)
        # est calculé et ajouté à la fin à l'envoi
        self.add_crc = tk.BooleanVar(value=False)
        self.crc_check = ttk.Checkbutton(free, text=_("Calc auto CRC"), variable=self.add_crc,
                                         command=self._update_crc)
        self.crc_check.pack(side="left", padx=(4, 0))
        self.free_send = ttk.Button(free, text=_("Envoyer"), command=self._send_free)
        self.free_send.pack(side="left", padx=4)

        # Aperçu de la trame qui partira, en couleurs, mis à jour à chaque frappe :
        #   case cochée     : octets saisis + CRC calculé (derniers octets, en rouge)
        #   case décochée   : la trame telle que saisie / collée
        # Trame du protocole complète : en-tête gris, COMMAND ID gras, CRC vert (rouge si faux)
        self.free_preview = HexView(self, font=MONO, height=1)
        self.free_preview.pack(side="bottom", fill="x", before=free, pady=(2, 0))
        self.free_var.trace_add("write", lambda *_: self._update_crc())

    def set_send_enabled(self, enabled):
        """Hexa libre et son bouton Envoyer grisés tant que la liaison n'est pas connectée."""
        state = ["!disabled"] if enabled else ["disabled"]
        self.free_entry.state(state)
        self.free_send.state(state)

    # ------------------------------------------------------------------
    # Écriture dans le journal
    # ------------------------------------------------------------------
    def log(self, text, tag="INFO"):
        """Ajoute une ligne horodatée. tag : "TX", "RX", "INFO" ou "ERR" (fixe la couleur)."""
        self.log_chunks([(text, (tag,))])

    def log_chunks(self, chunks):
        """Ajoute une ligne horodatée faite de morceaux [(texte, tags)] de couleurs différentes."""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]     # heure à la milliseconde
        line_tags = chunks[0][1][:1] if chunks else ("INFO",)
        # Le widget est en lecture seule : on le déverrouille le temps d'écrire
        self.text.configure(state="normal")
        self.text.insert("end", f"{ts}  ", line_tags)
        for text, tags in chunks:
            for tag in tags:
                ensure_hex_tag(self.text, tag)  # couleur "#RRGGBB" du fichier de protocole
            self.text.insert("end", text, tags)
        self.text.insert("end", "\n", line_tags)
        # Supprime les lignes les plus anciennes au-delà de MAX_LINES
        excess = int(self.text.index("end-1c").split(".")[0]) - self.MAX_LINES
        if excess > 0:
            self.text.delete("1.0", f"{excess + 1}.0")
        self.text.configure(state="disabled")
        if self.autoscroll.get():
            self.text.see("end")

    def _apply_line_colors(self):
        for tag, key in LINE_COLORS.items():
            self.text.tag_configure(tag, foreground=THEME.get(key))

    def log_frame(self, direction, data, label="", segments=None):
        """Journalise une trame, en couleurs.

        direction : "TX" ou "RX"
        data      : octets de la trame
        label     : nom du message envoyé (affiché après la trame)
        segments  : couleurs [(début, longueur, tag)] ; sinon demandées à style()

        Exemple : TX [  5]  AA 55 01 00 01   |.U...|   ← Ping
        """
        self.frames.append((time.monotonic(), direction, bytes(data), label or ""))
        if len(self.frames) > self.MAX_LINES:
            del self.frames[0]
        if direction == "TX" and not self.show_tx.get():
            return
        if segments is None and self.style:
            segments = self.style(direction, data)
        base = (direction,)
        chunks = [(f"{direction} [{len(data):>3}]  ", base)]
        chunks += hex_chunks(data, segments, base)
        tail = ""
        if self.show_ascii.get():
            tail += f"   |{to_ascii(data)}|"
        if label:
            tail += f"   ← {label}"
        if tail:
            chunks.append((tail, base))
        values = []
        if self.decode.get() and self.annotate:
            note = self.annotate(direction, data)
            if isinstance(note, tuple):
                note, values = note
            chunks += self._note_chunks(note, base)
        # Valeurs converties (type, facteur, offset, unité) en fin de ligne :
        # en gras, couleur de la ligne (TX bleu, RX violet), ou rouge si hors min / max
        # ou bit d'erreur actif
        for i, (text, ok) in enumerate(values):
            chunks.append(("   => " if i == 0 else "  |  ", base))
            chunks.append((text, base + ("val" if ok else "err",)))
        self.log_chunks(chunks)

    @staticmethod
    def _note_chunks(note, base):
        """Résumé protocole « … » : texte simple, ou morceaux [(texte, ok)] dont ceux à
        ok False (erreur N non nulle, CRC faux…) sont écrits en rouge."""
        if not note:
            return []
        if isinstance(note, str):
            return [(f"   « {tr(note)} »", base)]
        chunks = [("   « ", base)]
        for i, (text, ok) in enumerate(note):
            if i:
                chunks.append((" · ", base))
            chunks.append((tr(text), base if ok else base + ("err",)))
        chunks.append((" »", base))
        return chunks

    def set_recording(self, path):
        """Met à jour le bouton de trace : path = fichier en cours d'enregistrement, ou None."""
        if hasattr(self, "record_btn"):
            self.record_btn.config(text=_("■ Arrêter la trace") if path else _("● Trace"))

    def clear(self):
        """Bouton Effacer."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.frames.clear()

    def trace_events(self):
        """Trames journalisées, en événements de trace (t_ms depuis la première)."""
        if not self.frames:
            return []
        t0 = self.frames[0][0]
        return [TraceEvent(round((t - t0) * 1000, 1), d, data, label) for t, d, data, label in self.frames]

    def save(self):
        """Bouton Sauvegarder… : trace CSV rejouable (par défaut) ou texte du journal (.txt)."""
        initialdir = None
        if self.traces_dir:
            Path(self.traces_dir).mkdir(parents=True, exist_ok=True)
            initialdir = str(self.traces_dir)
        path = filedialog.asksaveasfilename(parent=self, initialdir=initialdir,
                                            initialfile=f"moniteur_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                            defaultextension=".csv",
                                            filetypes=[(_("Trace CSV (rejouable)"), "*.csv"),
                                                       (_("Texte"), "*.txt"), (_("Tous"), "*.*")])
        if not path:
            return
        try:
            if Path(path).suffix.lower() == ".csv":
                events = self.trace_events()
                save_trace(path, events)
                self.log(_("{0} trame(s) sauvegardée(s) dans {1} : à ouvrir dans le panneau Replay")
                         .format(len(events), path), "INFO")
            else:
                Path(path).write_text(self.text.get("1.0", "end"), encoding="utf-8")
                self.log(_("Journal sauvegardé : {0}").format(path), "INFO")
        except OSError as e:
            messagebox.showerror(_("Moniteur"), str(e), parent=self)

    # ------------------------------------------------------------------
    # Saisies de l'utilisateur
    # ------------------------------------------------------------------
    def _on_gap(self, *_args):
        """Délai de fin de trame modifié. Les saisies invalides ou < 1 ms sont ignorées."""
        try:
            ms = float(self.gap_var.get())
        except ValueError:
            return
        if ms >= 1:
            self.on_gap_change(ms)

    def set_crc_name(self, name):
        """Nom du CRC principal du protocole choisi, affiché sur la case : « Calc auto CRC (crc16_modbus) »."""
        self.crc_check.config(text=_("Calc auto CRC ({0})").format(name) if name else _("Calc auto CRC"),
                              state="normal" if name else "disabled")
        if not name:
            self.add_crc.set(False)
        self._update_crc()

    def free_frame(self):
        """Trame qui partira avec « Envoyer » : octets saisis (+ CRC si la case est cochée).

        Lève ValueError si l'hexa saisi est invalide.
        """
        data = parse_hex(self.free_var.get())
        if data and self.add_crc.get():
            data += self.crc_bytes(data)
        return data

    def _update_crc(self):
        """Aperçu en couleurs de la trame qui partira."""
        try:
            data = self.free_frame()
        except ValueError:
            self.free_preview.show_error(_("hexa invalide"))
            return
        if not data:
            self.free_preview.clear()
            return
        # Modèle de couleurs du protocole, si c'est une trame complète...
        segments = list(self.style("TX", data) or []) if self.style else []
        suffix = _("   ({0} octets)").format(len(data))
        if self.add_crc.get():
            # ... et le CRC calculé automatiquement (derniers octets) en rouge
            n = len(self.crc_bytes(b""))
            segments.append((len(data) - n, n, "err"))
            suffix += _("   CRC calculé")
        self.free_preview.show(data, segments, suffix)

    def _on_timeout(self, callback):
        """Timeout de réponse modifié. Les saisies invalides ou < 1 ms sont ignorées."""
        try:
            ms = float(self.timeout_var.get().replace(",", "."))
        except ValueError:
            return
        if ms >= 1 and callback:
            callback(ms)

    def _send_free(self):
        """Envoie les octets du champ « Hexa libre » (AA 55 01, AA5501 ou 0xAA,0x55),
        suivis du CRC du protocole si la case est cochée."""
        try:
            data = self.free_frame()
        except ValueError:
            messagebox.showwarning("SerialHex", _("Hexa invalide (ex : AA 55 01 0D)"))
            return
        if data:
            self.on_send_hex(data)
