"""
core/trace/recorder.py — Enregistrement au fil de l'eau des trames TX / RX dans un fichier CSV.
"""
import csv
import time
from pathlib import Path

from ..frames import to_hex
from .events import FIELDS


class TraceRecorder:
    """Enregistre les trames dans un fichier CSV, une ligne par trame.

        rec = TraceRecorder("traces/essai.csv")
        rec.write("TX", b"\\x01\\x03...", "Lire consigne et mode #0x01")
        rec.write("RX", b"\\x01\\x03...")
        rec.close()
    """

    def __init__(self, path, clock=time.monotonic):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._t0 = clock()
        self._last = 0.0
        self.count = 0
        # newline="" : le module csv gère lui-même les fins de ligne
        self._file = open(self.path, "w", encoding="utf-8", newline="")
        self._csv = csv.writer(self._file, delimiter=";")
        self._csv.writerow(FIELDS)
        self._file.flush()

    def write(self, direction, data, label=""):
        """Ajoute une trame. Écrite immédiatement sur le disque."""
        t = (self._clock() - self._t0) * 1000
        self._csv.writerow([f"{t:.1f}", f"{t - self._last:.1f}", direction, len(data), to_hex(data), label])
        self._file.flush()
        self._last = t
        self.count += 1

    def close(self):
        if not self._file.closed:
            self._file.close()


