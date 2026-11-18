"""
core/trace/document.py — Trace ouverte dans l'onglet Replay : modification et enregistrement.

    doc = TraceDocument()
    doc.load("traces/essai.csv")
    doc.set_cell(0, "label", "Lire l'état")       # modification validée (ValueError si invalide)
    row = doc.insert_after(2, "TX", trame, "Lire mesures")   # t au milieu des lignes 2 et 3
    doc.rename("essai_v2")                          # FileExistsError si le nom est déjà pris
    doc.save()

Toutes les règles (validation des saisies, temps d'une ligne insérée, renommage)
sont ici, sans interface : elles sont testées dans tests/test_trace.py.
"""
from pathlib import Path

from ..frames import parse_hex
from .events import TraceEvent
from .files import load_trace, save_trace

EDITABLE = ("t", "dir", "hex", "label")     # colonnes modifiables
DEFAULT_STEP_MS = 100.0                     # écart d'une ligne ajoutée en fin de trace
FORBIDDEN = set('\\/:*?"<>|')               # caractères interdits dans un nom de fichier (Windows)


class TraceDocument:
    def __init__(self, folder="traces"):
        self.folder = Path(folder)      # dossier proposé pour une nouvelle trace
        self.path = None                # fichier ouvert (None : pas encore enregistré)
        self.events = []                # lignes, dans l'ordre affiché
        self.modified = False

    # ------------------------------------------------------------------
    # Fichier
    # ------------------------------------------------------------------
    @property
    def name(self):
        """Nom du fichier sans extension ('' pour une nouvelle trace)."""
        return self.path.stem if self.path else ""

    def load(self, path):
        """Ouvre un fichier (ValueError / OSError si illisible : le document ne change pas)."""
        events = load_trace(path)
        self.path, self.events, self.modified = Path(path), events, False

    def new(self):
        self.path, self.events, self.modified = None, [], False

    def save(self):
        """Écrit le fichier ouvert. ValueError s'il n'a pas encore de nom."""
        if self.path is None:
            raise ValueError("donner un nom à la trace avant de l'enregistrer")
        save_trace(self.path, self.events)
        self.modified = False

    def target(self, name):
        """Chemin du fichier pour un nom saisi ('essai' -> dossier/essai.csv). ValueError si le nom est invalide."""
        name = name.strip()
        if name.lower().endswith(".csv"):
            name = name[:-4]
        if not name:
            raise ValueError("nom de fichier vide")
        bad = sorted(set(name) & FORBIDDEN)
        if bad:
            raise ValueError(f"caractère(s) interdit(s) dans le nom : {' '.join(bad)}")
        folder = self.path.parent if self.path else self.folder
        return folder / f"{name}.csv"

    def save_as_name(self, name, overwrite=False):
        """Enregistre sous un nouveau nom, dans le même dossier, en RENOMMANT le fichier.

        - même nom que le fichier ouvert : simple enregistrement ;
        - nom déjà pris par un autre fichier : FileExistsError, sauf overwrite=True ;
        - sinon le nouveau fichier est écrit, puis l'ancien supprimé (renommage).
        Retourne le nouveau chemin.
        """
        target = self.target(name)
        if self.path is not None and target.resolve() == self.path.resolve():
            self.save()
            return target
        if target.exists() and not overwrite:
            raise FileExistsError(str(target))
        old = self.path
        save_trace(target, self.events)
        self.path, self.modified = target, False
        if old is not None and old.exists():
            old.unlink()
        return target

    def save_copy(self, path, overwrite=False):
        """« Enregistrer sous… » ailleurs : le document suit le nouveau fichier, l'ancien est gardé."""
        path = Path(path)
        if path.exists() and not overwrite and (self.path is None or path.resolve() != self.path.resolve()):
            raise FileExistsError(str(path))
        save_trace(path, self.events)
        self.path, self.modified = path, False
        return path

    # ------------------------------------------------------------------
    # Lignes
    # ------------------------------------------------------------------
    def gaps(self, row):
        """(écart avec la ligne du dessus, écart avec la ligne du dessous) en ms, None aux extrémités."""
        t = self.events[row].t_ms
        above = t - self.events[row - 1].t_ms if row > 0 else None
        below = self.events[row + 1].t_ms - t if row + 1 < len(self.events) else None
        return above, below

    def time_after(self, row):
        """Temps d'une ligne insérée après `row` : au milieu de l'intervalle avec la ligne
        suivante, ou 100 ms plus tard en fin de trace (0 si la trace est vide)."""
        if not self.events:
            return 0.0
        if row is None or row >= len(self.events) - 1:
            last = self.events[-1] if row is None else self.events[row]
            return last.t_ms + DEFAULT_STEP_MS
        return (self.events[row].t_ms + self.events[row + 1].t_ms) / 2

    def insert_after(self, row, direction, data, label="", step_ms=None):
        """Insère une ligne après `row` (None : à la fin). Retourne sa position.

        step_ms : la ligne arrive step_ms après celle du dessus (0 si la trace est vide), et les
        lignes suivantes sont décalées d'autant (leurs écarts sont gardés). Sans step_ms : au
        milieu de l'intervalle avec la ligne suivante (voir time_after)."""
        pos = len(self.events) if row is None else row + 1
        if step_ms is None:
            t = self.time_after(row)
        else:
            t = self.events[pos - 1].t_ms + step_ms if pos > 0 else 0.0
            for i in range(pos, len(self.events)):
                e = self.events[i]
                self.events[i] = TraceEvent(e.t_ms + step_ms, e.direction, e.data, e.label)
        self.events.insert(pos, TraceEvent(t, direction, bytes(data), label))
        self.modified = True
        return pos

    def set_events(self, events):
        """Nouvelle trace (pas encore de fichier) faite de ces événements."""
        self.path, self.events, self.modified = None, list(events), True

    def replace(self, row, direction, data, label=""):
        """Remplace le contenu d'une ligne (son temps est gardé)."""
        self.events[row] = TraceEvent(self.events[row].t_ms, direction, bytes(data), label)
        self.modified = True

    def delete(self, rows):
        """Supprime des lignes. Retourne la position à sélectionner ensuite (ou None)."""
        rows = sorted(set(rows))
        if not rows:
            return None
        for i in reversed(rows):
            del self.events[i]
        self.modified = True
        return min(rows[0], len(self.events) - 1) if self.events else None

    def move(self, row, step):
        """Monte (-1) ou descend (+1) une ligne : les deux lignes échangent leur contenu
        mais gardent leur temps (la trace reste dans l'ordre). Retourne la nouvelle position, ou None."""
        other = row + step
        if not (0 <= row < len(self.events) and 0 <= other < len(self.events)):
            return None
        a, b = self.events[row], self.events[other]
        self.events[row] = TraceEvent(a.t_ms, b.direction, b.data, b.label)
        self.events[other] = TraceEvent(b.t_ms, a.direction, a.data, a.label)
        self.modified = True
        return other

    def set_cell(self, row, key, text):
        """Modifie une cellule depuis un texte saisi. ValueError (message lisible) si invalide.

        Retourne True si la ligne a changé.
        """
        e = self.events[row]
        new = TraceEvent(e.t_ms, e.direction, e.data, e.label)
        text = text.strip()
        if key == "t":
            new.t_ms = _parse_time(text)
        elif key == "dir":
            new.direction = _parse_direction(text)
        elif key == "hex":
            new.data = _parse_bytes(text)
        elif key == "label":
            new.label = text
        else:
            raise ValueError(f"colonne non modifiable : {key}")
        if new == e:
            return False
        self.events[row] = new
        self.modified = True
        return True


def _parse_time(text):
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise ValueError("t doit être un nombre de ms") from None


def _parse_direction(text):
    direction = text.upper()
    if direction not in ("TX", "RX"):
        raise ValueError("Dir doit valoir TX ou RX")
    return direction


def _parse_bytes(text):
    try:
        data = parse_hex(text)
    except ValueError:
        raise ValueError("hexa invalide (ex. 53 00 04 00 …)") from None
    if not data:
        raise ValueError("au moins un octet")
    return data
