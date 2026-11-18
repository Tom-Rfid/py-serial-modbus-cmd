"""
ui/replay/player.py — Moteur du replay : envoi des requêtes au rythme choisi, réception, verdicts.

Le joueur ne touche pas au tableau : il prévient le panneau par des rappels
    on_step(k)                              requête k en cours d'envoi
    on_result(k, reçu, latence, statut, explication)
    on_end(résumé)                          fin normale ; stop() pour arrêter avant
Une réponse est rattachée à la dernière requête envoyée.

Pas à pas (start_steps / step_next) : une requête par appel de step_next() (bouton Suivant) ;
son résultat s'affiche au bout du timeout, ou tout de suite si l'on passe à la suivante avant.
"""
import time

from core.trace import judge_exchange
from ui.i18n import _, tr


class ReplayPlayer:
    def __init__(self, widget, send, log):
        """widget : sert à programmer les étapes (after) ; send(data, label) -> bool ; log(texte, tag)."""
        self.widget, self.send, self.log = widget, send, log
        self.running = False
        self.step_mode = False      # pas à pas : une requête par clic sur Suivant
        self._next = 0              # pas à pas : prochain échange à envoyer
        self._job = None
        self._current = None        # index de l'échange en cours
        self._sent_at = {}          # échange -> instant d'envoi (s, horloge monotone)
        self._received = {}         # échange -> [(instant, octets)]
        self._results = {}          # échange -> statut

    def _begin(self, ex_list, timeout_ms, compare, on_step, on_result, on_end, step_mode):
        self.ex_list = ex_list
        self.timeout_ms, self.compare = timeout_ms, compare
        self.on_step, self.on_result, self.on_end = on_step, on_result, on_end
        self.running, self.step_mode = True, step_mode
        self._sent_at.clear()
        self._received.clear()
        self._results.clear()

    def start(self, ex_list, delays, timeout_ms, compare, on_step, on_result, on_end):
        """Replay continu, au rythme des délais."""
        self._begin(ex_list, timeout_ms, compare, on_step, on_result, on_end, step_mode=False)
        self.delays = delays
        self._job = self.widget.after(int(delays[0]), self._step, 0)

    # ------------------------------------------------------------------
    # Pas à pas
    # ------------------------------------------------------------------
    def start_steps(self, ex_list, first, timeout_ms, compare, on_step, on_result, on_end):
        """Pas à pas à partir de l'échange first : envoie la première requête tout de suite."""
        self._begin(ex_list, timeout_ms, compare, on_step, on_result, on_end, step_mode=True)
        self._first = self._next = first
        self.step_next()

    def step_next(self):
        """Bouton Suivant : conclut la requête en cours (si besoin) et envoie la suivante."""
        if not (self.running and self.step_mode):
            return
        if self._job:                               # réponse encore attendue : conclue maintenant
            self.widget.after_cancel(self._job)
            self._job = None
            self._step_done(self._current, last_check=False)
        if self._next >= len(self.ex_list):
            self._end_steps()
            return
        k = self._next
        self._next += 1
        if not self._send(k):
            return
        self._job = self.widget.after(int(self.timeout_ms), self._step_done, k)

    def _step_done(self, k, last_check=True):
        """Timeout de la requête k écoulé (ou Suivant cliqué avant) : résultat affiché."""
        self._job = None
        if not self.running or k is None:
            return
        self._finalize(k)
        self._current = None
        if last_check and self._next >= len(self.ex_list):
            self._end_steps()

    def _end_steps(self):
        self.running = self.step_mode = False
        self._current = None
        self.on_end(self.summary())

    @property
    def remaining(self):
        """Pas à pas : nombre de requêtes pas encore envoyées."""
        return len(self.ex_list) - self._next if self.step_mode else 0

    # ------------------------------------------------------------------
    # Envoi commun
    # ------------------------------------------------------------------
    def _send(self, k):
        """Envoie la requête k ; False (et arrêt) si l'envoi est impossible."""
        x = self.ex_list[k]
        self._current = k
        self._received[k] = []
        self._sent_at[k] = time.monotonic()
        self.on_step(k)
        label = f"replay {k + 1} : {x.tx.label}" if x.tx.label else f"replay {k + 1}"
        if not self.send(x.tx.data, label):
            self.log(_("Replay arrêté : envoi impossible"), "ERR")
            self.stop()
            return False
        return True

    def _step(self, k):
        """Conclut l'échange précédent, envoie la requête k, programme la suite."""
        self._job = None
        if not self.running:
            return
        if k > 0:
            self._finalize(k - 1)
        if not self._send(k):
            return
        if k + 1 < len(self.ex_list):
            self._job = self.widget.after(int(self.delays[k + 1]), self._step, k + 1)
        else:
            # Dernière requête : on laisse le temps aux dernières réponses d'arriver
            self._job = self.widget.after(int(self.timeout_ms), self._finish)

    def on_received(self, data):
        if self.running and self._current is not None:
            self._received.setdefault(self._current, []).append((time.monotonic(), data))

    def _finalize(self, k):
        x = self.ex_list[k]
        got = self._received.get(k, [])
        received = [((t - self._sent_at[k]) * 1000, d) for t, d in got]
        latency = received[0][0] if received else None
        if self.compare:
            status, why = judge_exchange([r.data for r in x.responses], received, self.timeout_ms)
        else:
            status, why = "", ""
        self._results[k] = status
        self.on_result(k, [d for _, d in got], latency, status, why)

    def _finish(self):
        self._job = None
        if self.running:
            self._finalize(len(self.ex_list) - 1)
        self.running = False
        self._current = None
        self.on_end(self.summary())

    def summary(self):
        """« 3 identique, 1 différent » (ou « terminé » sans comparaison)."""
        counts = {}
        for status in self._results.values():
            if status:
                counts[status] = counts.get(status, 0) + 1
        return ", ".join(f"{n} {tr(s)}" for s, n in counts.items()) or _("terminé")

    def stop(self):
        """Annule les envois restants. Retourne l'index de l'échange interrompu (ou None)."""
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        interrupted = self._current if self.running else None
        self.running = self.step_mode = False
        self._current = None
        return interrupted
