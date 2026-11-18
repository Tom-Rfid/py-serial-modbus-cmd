"""
core/trace/analysis.py — Échanges (une requête et ses réponses), statistiques de temps, délais du replay.
"""
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from .events import TraceEvent


@dataclass
class Exchange:
    """Une requête envoyée et les trames reçues jusqu'à la requête suivante."""
    index: int
    tx: TraceEvent
    responses: List[TraceEvent] = field(default_factory=list)
    gap_ms: float = 0.0                 # temps depuis la requête précédente (0 pour la première)

    @property
    def latency_ms(self) -> Optional[float]:
        """Temps entre l'envoi et la première réponse, ou None sans réponse."""
        return self.responses[0].t_ms - self.tx.t_ms if self.responses else None


def exchanges(events):
    """Regroupe la trace en échanges. Les RX reçus avant le premier TX sont ignorés."""
    out = []
    for e in events:
        if e.direction == "TX":
            gap = e.t_ms - out[-1].tx.t_ms if out else 0.0
            out.append(Exchange(len(out), e, gap_ms=gap))
        elif out:
            out[-1].responses.append(e)
    return out


def _stats(values):
    """(min, moyenne, max) d'une liste, ou None si elle est vide."""
    return (min(values), statistics.mean(values), max(values)) if values else None


@dataclass
class Analysis:
    duration_ms: float
    n_tx: int
    n_rx: int
    gaps: Optional[tuple]               # écart entre deux envois : (min, moy, max) en ms
    latencies: Optional[tuple]          # latence de réponse : (min, moy, max) en ms
    unanswered: int                     # requêtes sans réponse

    def text(self):
        """Résumé d'une ligne pour l'interface."""
        def fmt(s):
            return "—" if s is None else f"{s[0]:.0f} / {s[1]:.0f} / {s[2]:.0f} ms"
        return (f"Durée {self.duration_ms / 1000:.2f} s · {self.n_tx} TX · {self.n_rx} RX · "
                f"écart entre envois (min / moy / max) {fmt(self.gaps)} · "
                f"latence de réponse {fmt(self.latencies)} · sans réponse : {self.unanswered}")


def analyze(events):
    ex = exchanges(events)
    return Analysis(
        duration_ms=(events[-1].t_ms - events[0].t_ms) if events else 0.0,
        n_tx=sum(e.direction == "TX" for e in events),
        n_rx=sum(e.direction == "RX" for e in events),
        gaps=_stats([x.gap_ms for x in ex[1:]]),
        latencies=_stats([x.latency_ms for x in ex if x.latency_ms is not None]),
        unanswered=sum(1 for x in ex if not x.responses),
    )


# --------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------

def replay_delays(ex_list, mode="original", speed=1.0, fixed_ms=100.0):
    """Délai (ms) à attendre AVANT chaque envoi lors du replay.

    mode "original" : écart d'origine entre deux requêtes, divisé par `speed`
                      (speed 2 = deux fois plus vite)
    mode "fixed"    : `fixed_ms` entre deux requêtes
    La première requête part immédiatement (délai 0). Un écart négatif (trace
    modifiée à la main, temps dans le désordre) compte pour 0.
    """
    delays = []
    for i, x in enumerate(ex_list):
        if i == 0:
            delays.append(0.0)
        elif mode == "fixed":
            delays.append(float(fixed_ms))
        else:
            delays.append(max(0.0, x.gap_ms / speed if speed > 0 else x.gap_ms))
    return delays


