"""
ui/replay/panel.py — Classe ReplayPanel : relie la trace (core.trace.TraceDocument),
les barres, le tableau, le détail de ligne et le moteur du replay.

    ┌ FileBar      [Ouvrir…] [Nouvelle] Nom [new_trace_…] .csv * [Enregistrer] [Enregistrer sous…] ┐
    │ analyse des temps                                                                    │
    │ PlaybackOptions  rythme, timeout, comparer                                           │
    │ EditBar      [+ Ajouter] [Supprimer] [Monter] [Descendre]  → : insère / remplace     │
    │ lecture          [⏭ Pas à pas]  [▶ Rejouer]  [■ Arrêter]   état du replay / messages │
    │ TraceTable   une ligne par ligne du fichier                                          │
    └ RowDetail    ligne sélectionnée : intervalle ↑ ↓, couleurs, décodage                 ┘

Tout le panneau est sur un fond gris un peu plus foncé (PANEL_BG) : styles « Replay.* ».
"""
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from core.frames import to_hex
from core.trace import TraceDocument, analyze, exchanges

from .constants import (ARROW_REPLACE, GREY, ICON_CURRENT, PANEL_BG, PLAY_GREEN, RED, RESULTS, STEP_BLUE,
                        STOP_RED)
from .detail import RowDetail
from .edit_bar import EditBar
from .file_bar import FileBar
from .options import PlaybackOptions
from .player import ReplayPlayer
from .table import TraceTable
from ui.i18n import _, tr
from ui.tooltip import ToolTip

# Classes ttk recolorées sur le fond du panneau (les boutons et le tableau gardent les leurs)
RESTYLED = ("TFrame", "TLabel", "TRadiobutton", "TCheckbutton", "TLabelframe")


class ReplayPanel(ttk.Frame):
    def __init__(self, master, send, is_connected, traces_dir, log, timeout_ms=500,
                 describe=None, style=None, on_decode=None):
        """
        send(data, label) -> bool : envoie une trame (même chemin que les autres envois)
        is_connected()    -> bool : le port est-il ouvert ?
        traces_dir        : dossier proposé pour ouvrir / enregistrer
        log(texte, tag)   : écrit dans le moniteur
        timeout_ms        : timeout de réponse proposé (celui du moniteur)
        describe, style   : décodage et couleurs du protocole (détail de ligne)
        on_decode(dir, data): bouton « Décoder dans Protocole »
        """
        _setup_styles(master)
        super().__init__(master, padding=(6, 0, 0, 0), style="Replay.TFrame")
        self.is_connected = is_connected
        self.log = log
        self.doc = TraceDocument(traces_dir)
        self.ex_list = []           # échanges (une requête TX + ses réponses RX)
        self.tx_rows = []           # échange k -> position de sa ligne TX
        self.player = ReplayPlayer(self, send, log)
        self._build(timeout_ms, describe or (lambda d, b: None), style or (lambda d, b: None),
                    on_decode or (lambda d, b: None))
        _restyle(self)
        self.refresh()

    def _build(self, timeout_ms, describe, style, on_decode):
        self.file_bar = FileBar(self, on_open=self.ask_open, on_new=self.new,
                                on_save=self.save, on_save_as=self.save_as)
        self.file_bar.pack(fill="x")
        self.analysis_lbl = ttk.Label(self, text="", foreground=GREY, wraplength=600, justify="left")
        self.analysis_lbl.pack(fill="x")
        self.options = PlaybackOptions(self, timeout_ms, on_change=self.update_delays)
        self.options.pack(fill="x", pady=4)
        self.edit_bar = EditBar(self, on_add=self.add_row, on_delete=self.delete_rows, on_move=self.move_row)
        self.edit_bar.pack(fill="x")
        self._build_play_bar()
        # Détail placé en bas AVANT le tableau : toujours visible, c'est le tableau qui rétrécit
        self.detail = RowDetail(self, describe, style, on_decode)
        self.detail.pack(side="bottom", fill="x", pady=(4, 0))
        self.table = TraceTable(self, on_edit=self.edit_cell, on_select=self._on_select,
                                on_delete_key=self.delete_rows)
        self.table.pack(fill="both", expand=True, pady=(4, 0))

    def _build_play_bar(self):
        """[▶ Rejouer] [⏭ Pas à pas / Suivant] [■ Arrêter] et la ligne d'état (messages du panneau).

        Pas à pas : le premier clic envoie la requête de la ligne sélectionnée (ou la première),
        chaque clic suivant (« ⏭ Suivant », ou F8) envoie la requête d'après."""
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 2))
        # Sous « insère après », un peu à droite ; Pas à pas (bleu), Rejouer (vert), Arrêter (rouge)
        self.step_btn = ttk.Button(bar, text=_("⏭ Pas à pas"), command=self.step, width=13, style="Step.TButton")
        self.step_btn.pack(side="left", padx=(150, 0))     # recalé sous « insère après » (_align_play_bar)
        self.edit_bar.insert_radio.bind("<Configure>", lambda e: self._align_play_bar(), add="+")
        ToolTip(self.step_btn, _("Pas à pas : envoie la requête de la ligne sélectionnée (ou la première), "
                                 "puis une requête par clic sur « ⏭ Suivant » (ou F8)"))
        self.start_btn = ttk.Button(bar, text=_("▶ Rejouer"), command=self.start, style="Play.TButton")
        self.start_btn.pack(side="left", padx=(14, 0))
        ToolTip(self.start_btn, _("Rejoue toute la trace au rythme choisi (temps d'origine ou délai fixe) "
                                  "et compare les réponses"))
        stop_btn = ttk.Button(bar, text=_("■ Arrêter"), command=self.stop, style="Stop.TButton")
        stop_btn.pack(side="left", padx=(14, 0))
        ToolTip(stop_btn, _("Arrête le replay ou le pas à pas"))
        self.bind_all("<F8>", lambda e: self.step() if self.winfo_ismapped() else None, add="+")
        # Ligne d'état sous les boutons, sur toute la largeur (messages longs du pas à pas)
        self.status_lbl = ttk.Label(self, text="", wraplength=600, justify="left")
        self.status_lbl.pack(fill="x", pady=(2, 0))

    def _align_play_bar(self):
        """Pas à pas / Rejouer / Arrêter commencent sous « insère après », un peu à droite."""
        x = self.edit_bar.insert_radio.winfo_x() + 16
        if x > 16:
            self.step_btn.pack_configure(padx=(x, 0))

    def say(self, text, error=False):
        """Message sur la ligne d'état (rouge pour une erreur)."""
        self.status_lbl.config(text=text, foreground=RED if error else "")

    def _set_running(self, running):
        self.start_btn.state(["disabled"] if running else ["!disabled"])
        stepping = running and self.player.step_mode
        self.step_btn.config(text=_("⏭ Suivant") if stepping else _("⏭ Pas à pas"))
        self.step_btn.state(["disabled"] if running and not stepping else ["!disabled"])

    # ------------------------------------------------------------------
    # État
    # ------------------------------------------------------------------
    @property
    def running(self):
        return self.player.running

    def refresh(self, select=None):
        """Recalcule les échanges et réaffiche tout (après chargement ou modification)."""
        events = self.doc.events
        self.ex_list = exchanges(events)
        self.tx_rows = [i for i, e in enumerate(events) if e.direction == "TX"]
        self.table.fill(events, select)
        # Nouvelle trace sans fichier : on garde le nom saisi, sinon new_trace_<date>
        name = self.doc.name or self.file_bar.name().strip() or default_name()
        self.file_bar.show(name, self.doc.modified)
        self.analysis_lbl.config(text=self._analysis_text())
        self.update_delays()
        self._on_select(self.table.selected_rows())

    def _analysis_text(self):
        if not self.doc.events:
            return ""
        if not self.ex_list:
            return _("Aucune requête (TX) : rien à rejouer.")
        return analyze(self.doc.events).text()

    def update_delays(self):
        """Affiche sur chaque ligne TX le délai appliqué avant son envoi."""
        if self.running:
            return
        delays = self.options.delays(self.ex_list)
        for k, delay in enumerate(delays):
            self.table.set(self.tx_rows[k], "delay", f"{delay:.0f}")
        if self.ex_list:
            self.say(_("{0} requête(s), environ {1:.1f} s").format(len(self.ex_list), sum(delays) / 1000))
        else:
            self.say("")

    def _changed(self, select=None):
        self.refresh(select)

    def _on_select(self, rows):
        """Ligne cliquée : détail (intervalle avec les voisines, couleurs, décodage)."""
        if len(rows) != 1 or rows[0] >= len(self.doc.events):
            self.detail.clear()
            return
        row = rows[0]
        self.detail.show(row, self.doc.events[row], self.doc.gaps(row))

    # ------------------------------------------------------------------
    # Fichier
    # ------------------------------------------------------------------
    def confirm_discard(self):
        """Modifications non enregistrées : demande quoi faire. Retourne False pour annuler."""
        if not self.doc.modified:
            return True
        answer = messagebox.askyesnocancel("Replay", _("La trace a été modifiée. Enregistrer les modifications ?"),
                                           parent=self)
        if answer is None:
            return False
        return self.save() if answer else True

    def ask_open(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, initialdir=self.doc.folder,
                                          filetypes=[(_("Trace CSV"), "*.csv"), (_("Tous"), "*.*")])
        if path:
            self.load(path)

    def load(self, path):
        """Charge une trace. Retourne False si le fichier est illisible."""
        self.stop()
        try:
            self.doc.load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("Replay", _("Trace illisible :\n{0}").format(tr(str(e))), parent=self)
            return False
        self.refresh()
        return True

    def new(self):
        """Bouton Nouvelle : trace vide, à remplir (+ Ajouter, flèches « → Replay »)."""
        if not self.confirm_discard():
            return
        self.stop()
        self.doc.new()
        self.file_bar.show("", False)               # refresh() propose new_trace_<date>
        self.refresh()

    def load_events(self, events, name):
        """Bouton « + Replay » du moniteur : ces trames deviennent une nouvelle trace (pas encore enregistrée)."""
        if not self.confirm_discard():
            return False
        self.stop()
        self.doc.set_events(events)
        self.file_bar.show(name, True)
        self.refresh()
        self.say(_("{0} trame(s) du moniteur : ▶ Rejouer ou ⏭ Pas à pas, Enregistrer pour garder la trace")
                 .format(len(events)))
        return True

    def save(self):
        """Bouton Enregistrer : sous le nom saisi (renomme le fichier si le nom a changé).

        Demande avant de remplacer un autre fichier. Retourne True si le fichier a été écrit.
        """
        name = self.file_bar.name()
        try:
            path = self._save_under(name, overwrite=False)
        except FileExistsError:
            if not messagebox.askyesno("Replay", _("{0} existe déjà.\nLe remplacer ?").format(Path(self.doc.target(name)).name),
                                       parent=self):
                return False
            path = self._save_under(name, overwrite=True)
        except (ValueError, OSError) as e:
            messagebox.showerror("Replay", _("Enregistrement impossible :\n{0}").format(tr(str(e))), parent=self)
            return False
        self.file_bar.show(self.doc.name, False)
        self.log(_("Trace enregistrée : {0}").format(path), "INFO")
        return True

    def _save_under(self, name, overwrite):
        if not name.strip():
            name = self.doc.name or default_name()
        return self.doc.save_as_name(name, overwrite=overwrite)

    def save_as(self):
        """Bouton Enregistrer sous… : copie dans un autre dossier ; l'original est gardé."""
        self.doc.folder.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(parent=self, initialdir=self.doc.folder,
                                            initialfile=(self.doc.name or "trace") + ".csv",
                                            defaultextension=".csv",
                                            filetypes=[(_("Trace CSV"), "*.csv"), (_("Tous"), "*.*")])
        if not path:
            return False
        try:
            self.doc.save_copy(path, overwrite=True)    # la boîte de dialogue a déjà demandé
        except OSError as e:
            messagebox.showerror("Replay", _("Enregistrement impossible :\n{0}").format(tr(str(e))), parent=self)
            return False
        self.file_bar.show(self.doc.name, False)
        self.log(_("Trace enregistrée : {0}").format(path), "INFO")
        return True

    # ------------------------------------------------------------------
    # Édition
    # ------------------------------------------------------------------
    def _can_edit(self):
        if self.running:
            self.say(_("Arrêter le replay pour modifier la trace"), error=True)
            return False
        return True

    def edit_cell(self, row, key, text):
        """Saisie validée dans une cellule. Retourne un message d'erreur, ou None si acceptée."""
        if not self._can_edit():
            return _("replay en cours")
        try:
            changed = self.doc.set_cell(row, key, text)
        except ValueError as e:
            self.say(_("Ligne {0} : {1}").format(row + 1, tr(str(e))), error=True)
            return str(e)
        if changed:
            self.table.close_editor()
            self._changed([row])
        return None

    def add_row(self):
        """+ Ajouter : ligne TX après la sélection, « Délai fixe » ms après la ligne du dessus
        (les suivantes sont décalées), avec les octets de la ligne du dessus ; la saisie des octets s'ouvre."""
        if not self._can_edit():
            return
        rows = self.table.selected_rows()
        after = rows[-1] if rows else (len(self.doc.events) - 1 if self.doc.events else None)
        data = self.doc.events[after].data if after is not None else b"\x00"     # trace vide : un octet à compléter
        # Temps : « Délai fixe » après la ligne du dessus (les lignes suivantes sont décalées d'autant)
        row = self.doc.insert_after(after, "TX", data, step_ms=self.options.fixed_delay_ms())
        self._changed([row])
        self.after_idle(lambda: self.table.edit_cell(row, "hex"))

    def delete_rows(self):
        if not self._can_edit():
            return
        nxt = self.doc.delete(self.table.selected_rows())
        if nxt is not None or not self.doc.events:
            self._changed([nxt] if nxt is not None else None)

    def move_row(self, step):
        if not self._can_edit():
            return
        rows = self.table.selected_rows()
        if len(rows) == 1:
            new = self.doc.move(rows[0], step)
            if new is not None:
                self._changed([new])

    def put_frame(self, data, label):
        """Flèche « → Replay » des onglets : trame insérée après la sélection (au milieu de
        l'intervalle), ou à la place de la ligne sélectionnée, selon le choix de la barre."""
        if not self._can_edit():
            return
        rows = self.table.selected_rows()
        if self.edit_bar.arrow_mode() == ARROW_REPLACE and rows:
            self.doc.replace(rows[0], "TX", data, label)
            row = rows[0]
        else:
            row = self.doc.insert_after(rows[-1] if rows else None, "TX", data, label)
        self._changed([row])
        self.say(_("Ligne {0} : {1}").format(row + 1, label or to_hex(data[:8])))

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------
    def _can_play(self):
        if not self.ex_list:
            messagebox.showinfo("Replay", _("Ouvrir d'abord une trace avec au moins une ligne TX."), parent=self)
            return False
        if not self.is_connected():
            messagebox.showwarning("Replay", _("Le port série n'est pas connecté."), parent=self)
            return False
        return True

    def step(self):
        """Bouton Pas à pas / Suivant (F8) : démarre le pas à pas, puis envoie la requête suivante."""
        if self.player.running:
            if self.player.step_mode:
                self.player.step_next()
            return
        if not self._can_play():
            return
        first = self._first_exchange(self.table.selected_rows())
        self.table.close_editor()
        self.refresh()                                  # efface les résultats précédents
        self.player.step_mode = True                    # bouton « Suivant » dès le premier envoi
        self._set_running(True)
        self.log(_("Replay pas à pas : {0}, requête {1} / {2}").format(
            self.doc.name or _('nouvelle trace'), first + 1, len(self.ex_list)), "INFO")
        self.player.start_steps(self.ex_list, first, self.options.timeout_ms(), self.options.compare.get(),
                                self._on_step, self._on_result, self._on_end)

    def _first_exchange(self, rows):
        """Échange de départ du pas à pas : celui de la ligne sélectionnée (TX ou réponse), sinon le premier."""
        if not rows:
            return 0
        before = [k for k, r in enumerate(self.tx_rows) if r <= rows[0]]
        return before[-1] if before else 0

    def start(self):
        if not self._can_play():
            return
        self.table.close_editor()
        self.refresh(self.table.selected_rows())          # efface les résultats précédents
        self._set_running(True)
        self.log(_("Replay : {0}, {1} requête(s)").format(self.doc.name or _('nouvelle trace'), len(self.ex_list)), "INFO")
        self.player.start(self.ex_list, self.options.delays(self.ex_list), self.options.timeout_ms(),
                          self.options.compare.get(), self._on_step, self._on_result, self._on_end)

    def on_received(self, data):
        """Appelée par l'application pour chaque trame reçue."""
        self.player.on_received(data)

    def _on_step(self, k):
        """Requête k en cours d'envoi : icône ▶ et fond bleu clair."""
        row = self.tx_rows[k]
        self.table.set(row, "icon", ICON_CURRENT)
        self.table.mark(row, "TX", "current")
        self.table.see(row)
        if self.player.step_mode:
            left = self.player.remaining
            self.say(_("Pas à pas {0} / {1}").format(k + 1, len(self.ex_list))
                     + (_(" : ⏭ Suivant (F8) pour la requête suivante") if left else _(" : dernière requête")))
        else:
            self.say(_("Replay {0} / {1}").format(k + 1, len(self.ex_list)))

    def _on_result(self, k, got, latency, status, why):
        """Résultat sur la ligne TX : réponse reçue, latence, verdict, icône, fond."""
        row = self.tx_rows[k]
        icon, background = RESULTS.get(status, ("", None))
        self.table.set(row, "got", ", ".join(to_hex(d) for d in got) or "—")
        self.table.set(row, "lat", f"{latency:.0f}" if latency is not None else "")
        self.table.set(row, "res", tr(status) + (f" : {tr(why)}" if why else ""))
        self.table.set(row, "icon", icon)
        self.table.mark(row, "TX", background)

    def _on_end(self, summary):
        self._set_running(False)
        self.say(_("Replay terminé : {0}").format(summary))
        self.log(_("Replay terminé : {0}").format(summary), "INFO")

    def stop(self):
        """Bouton Arrêter : annule les envois restants."""
        was_running = self.player.running
        interrupted = self.player.stop()
        if interrupted is not None:
            row = self.tx_rows[interrupted]
            self.table.set(row, "icon", "")
            self.table.mark(row, "TX")
        if was_running:
            self.say(_("Replay arrêté"))
            self.log(_("Replay arrêté"), "INFO")
        self._set_running(False)


def default_name():
    """Nom proposé pour une nouvelle trace : new_trace_<date>_<heure>."""
    return f"new_trace_{datetime.now():%Y%m%d_%H%M%S}"


def _setup_styles(widget):
    """Styles du panneau : fond PANEL_BG, boutons de lecture colorés."""
    s = ttk.Style(widget)
    for cls in RESTYLED:
        s.configure(f"Replay.{cls}", background=PANEL_BG)
    s.configure("Replay.TLabelframe.Label", background=PANEL_BG)
    s.map("Replay.TRadiobutton", background=[("active", PANEL_BG)])
    s.map("Replay.TCheckbutton", background=[("active", PANEL_BG)])
    for name, color in (("Play", PLAY_GREEN), ("Step", STEP_BLUE), ("Stop", STOP_RED)):
        s.configure(f"{name}.TButton", foreground=color, font=("Segoe UI", 9, "bold"))
        s.map(f"{name}.TButton", foreground=[("disabled", GREY)])


def _restyle(widget):
    """Fond du panneau sur tous les cadres, libellés, cases et boutons radio (récursif)."""
    for child in widget.winfo_children():
        cls = child.winfo_class()
        if cls in RESTYLED:
            try:
                current = str(child.cget("style"))
                if not current or current == cls:
                    child.configure(style=f"Replay.{cls}")
            except Exception:
                pass
        _restyle(child)
