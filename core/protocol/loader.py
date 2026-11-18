"""
core/protocol/loader.py — Lecture des fichiers de protocole (dossier protocols/).
"""
import json
from pathlib import Path

from ..jsonc import load_file
from .common import ProtocolError
from .protocol import Protocol


def load_protocol(path):
    """Lit un fichier de protocole (commentaires // et /* */ acceptés). Lève ProtocolError
    avec un message lisible."""
    path = Path(path)
    try:
        conf = load_file(path)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"{path.name} : JSON invalide (ligne {e.lineno}) : {e.msg}") from None
    except OSError as e:
        raise ProtocolError(f"{path.name} : {e}") from None
    try:
        return Protocol(conf, path)
    except ProtocolError as e:
        raise ProtocolError(f"{path.name} : {e}") from None


def list_protocols(folder):
    """Fichiers de protocole d'un dossier : [(nom de fichier, Protocol ou message d'erreur)]."""
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            out.append((path.name, load_protocol(path)))
        except ProtocolError as e:
            out.append((path.name, str(e)))
    return out
