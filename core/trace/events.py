"""
core/trace/events.py — Une ligne de trace (TraceEvent) et les colonnes du fichier CSV.
"""
from dataclasses import dataclass


FIELDS = ["t_ms", "delta_ms", "dir", "len", "hex", "label"]


@dataclass
class TraceEvent:
    t_ms: float             # temps depuis le début de la trace
    direction: str          # "TX" ou "RX"
    data: bytes
    label: str = ""


