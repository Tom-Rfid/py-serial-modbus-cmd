"""
core/trace/files.py — Lecture et écriture d'un fichier de trace complet.
"""
import csv
from pathlib import Path

from ..frames import parse_hex, to_hex
from .events import FIELDS, TraceEvent


def load_trace(path):
    """Lit un fichier de trace. Retourne la liste des TraceEvent, triée par temps.

    Accepte « ; » ou « , » comme séparateur. Les lignes sans t_ms sont espacées
    de 0 ms. Lève ValueError (avec le numéro de ligne) si une ligne est invalide.
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    delimiter = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    reader = csv.DictReader(lines, delimiter=delimiter)
    events = []
    for n, row in enumerate(reader, start=2):
        try:
            direction = (row.get("dir") or "").strip().upper()
            if direction not in ("TX", "RX"):
                raise ValueError(f"dir doit valoir TX ou RX, pas '{direction}'")
            t = row.get("t_ms")
            events.append(TraceEvent(
                t_ms=float(t.replace(",", ".")) if t and t.strip() else (events[-1].t_ms if events else 0.0),
                direction=direction,
                data=parse_hex(row.get("hex") or ""),
                label=(row.get("label") or "").strip(),
            ))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"ligne {n} : {e}") from None
    events.sort(key=lambda e: e.t_ms)           # tri stable : l'ordre du fichier est gardé à égalité
    return events


def save_trace(path, events):
    """Écrit les événements dans un fichier de trace (même format que TraceRecorder).

    Les lignes sont écrites dans l'ordre de la liste ; delta_ms est recalculé.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(FIELDS)
        last = events[0].t_ms if events else 0.0
        for e in events:
            w.writerow([f"{e.t_ms:.1f}", f"{e.t_ms - last:.1f}", e.direction, len(e.data),
                        to_hex(e.data), e.label])
            last = e.t_ms


