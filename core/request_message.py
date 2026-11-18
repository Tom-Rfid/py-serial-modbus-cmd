"""
core/request_message.py — Messages « de protocole » de l'onglet Manuel.

Un message de protocole ne décrit pas les octets de la trame : il donne seulement ce que
l'onglet Protocole demande (REQUEST ID, COMMAND ID, DATA), et la trame est construite par le
protocole en cours (longueur, CRC d'en-tête et de DATA compris). Exemple :

    {
      "name": "access_level_service_GRANTED",
      "description": "Accès service",
      "request": {
        "request_id": 0,                  // facultatif (protocole sans REQUEST ID : absent)
        "command_id": "0x80010001",
        "data": "33 33 53 70 61 72 6B",   // hexa ; "" = pas de données
        "header": {"CI": "0x52"},         // facultatif : autres champs d'en-tête, par nom ou rôle
        "variant": "Longue"               // facultatif : format de trame (protocole à variantes)
      }
    }

Dans l'onglet Manuel, REQUEST ID, COMMAND ID et DATA s'affichent comme des paramètres
modifiables. Les messages sauvegardés depuis l'onglet Protocole (bouton « Sauvegarder… »)
sont écrits dans ce format (save_message_file), dans le fichier choisi
(msgLibrary/msgManual/Msg_Sauvegardes.json proposé).
"""
import json
import re
from pathlib import Path

from .frames import parse_hex, parse_int, to_hex
from .jsonc import load_file

SAVED_FILE = "Msg_Sauvegardes.json"     # fichier des messages sauvegardés (dossier msgLibrary/msgManual/)
SAVED_GROUP = "Sauvegardés"

# Paramètres affichés dans l'onglet Manuel pour un message de protocole
REQUEST_PARAMS = {
    "request_id": {"type": "int", "label": "REQUEST ID"},
    "command_id": {"type": "int", "label": "COMMAND ID"},
    "data": {"type": "hex", "label": "DATA (hexa)"},
}


def is_request(msg):
    """True pour un message de protocole (clé "request")."""
    return isinstance(msg, dict) and isinstance(msg.get("request"), dict)


def params_of(msg):
    """Paramètres affichés d'un message : ceux du JSON, ou REQUEST ID / COMMAND ID / DATA."""
    if not is_request(msg):
        return msg.get("params", {})
    req = msg["request"]
    return {k: v for k, v in REQUEST_PARAMS.items() if k != "request_id" or "request_id" in req}


def request_defaults(msg):
    """Valeurs de départ des paramètres d'un message de protocole (texte)."""
    req = msg["request"]
    values = {"command_id": str(req.get("command_id", "0x00")), "data": str(req.get("data", "") or "")}
    if "request_id" in req:
        rid = req["request_id"]
        values["request_id"] = f"0x{rid:02X}" if isinstance(rid, int) else str(rid)
    return values


def check_request(msg):
    """Vérifie un message de protocole au chargement. Lève ValueError si invalide."""
    req = msg["request"]
    if "command_id" not in req:
        raise ValueError("'request' : 'command_id' manquant")
    values = request_defaults(msg)
    for key in ("request_id", "command_id"):
        if key in values:
            try:
                parse_int(values[key])
            except ValueError:
                raise ValueError(f"{key} : '{values[key]}' n'est pas un nombre")
    try:
        parse_hex(values["data"])
    except ValueError:
        raise ValueError("data : hexa invalide")


def request_values(msg, values):
    """(valeurs d'en-tête {rôle ou nom: entier}, octets DATA, variante) d'après les saisies.
    Lève ValueError si une saisie est invalide."""
    req = msg["request"]
    header = {}
    for key, label in (("request_id", "REQUEST ID"), ("command_id", "COMMAND ID")):
        if key in values or (key == "command_id"):
            text = values.get(key, req.get(key, 0))
            try:
                header[key] = parse_int(text)
            except ValueError:
                raise ValueError(f"{label} : '{text}' n'est pas un nombre")
    for key, value in (req.get("header") or {}).items():
        header[key] = parse_int(value)
    try:
        data = parse_hex(values.get("data", req.get("data", "")) or "")
    except ValueError:
        raise ValueError("DATA : hexa invalide")
    return header, data, req.get("variant") or None


def build_request(msg, values, protocol, kind):
    """Trame d'un message de protocole, construite par `protocol` (core.protocol.Protocol).
    kind : QUERY (requête). Lève ValueError si une saisie est invalide."""
    header, data, variant = request_values(msg, values)
    if variant not in protocol.variant_names(kind):
        variant = None
    return protocol.build(kind, data, header, variant=variant)


def make_request_message(name, command_id, data=b"", request_id=None, header=None, variant=None,
                         description="", protocol="", id_digits=8):
    """Message de protocole prêt à écrire (dict)."""
    req = {}
    if request_id is not None:
        req["request_id"] = request_id
    req["command_id"] = f"0x{command_id:0{id_digits}X}"
    req["data"] = to_hex(data) if isinstance(data, (bytes, bytearray)) else str(data)
    if header:
        req["header"] = {k: (f"0x{v:X}" if isinstance(v, int) else v) for k, v in header.items()}
    if variant:
        req["variant"] = variant
    msg = {"name": name}
    if description:
        msg["description"] = description
    if protocol:
        msg["protocol"] = protocol
    msg["request"] = req
    return msg


def saved_file_name(name):
    """Nom de fichier de messages valide : préfixe Msg_ et extension .json ajoutés au besoin."""
    name = Path(name).name.strip()
    if not name.lower().endswith(".json"):
        name += ".json"
    if not name.startswith(("Msg_", "Message_")):
        name = "Msg_" + name
    return name


def file_name_for(message_name):
    """Fichier proposé pour un message : 'Set access level' -> 'Msg_Set_access_level.json'
    (espaces -> _, caractères interdits dans un nom de fichier retirés)."""
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", message_name).strip().replace(" ", "_").strip(".")
    return saved_file_name(stem or "Sauvegardes")


def _read_saved(path):
    """Contenu d'un fichier de messages ({"messages": [...]}), ou un fichier neuf."""
    path = Path(path)
    data = {"group": SAVED_GROUP, "messages": []}     # nouveau fichier : groupe « Sauvegardés »
    if path.is_file():
        loaded = load_file(path)
        if isinstance(loaded, dict) and isinstance(loaded.get("messages"), list):
            data = loaded
        elif isinstance(loaded, list):
            data = {"messages": loaded}
        else:
            raise ValueError(f"{path.name} : pas un fichier de messages (clé \"messages\")")
    return data


def find_saved(path, name):
    """Message de nom `name` déjà dans le fichier `path`, ou None."""
    try:
        data = _read_saved(path)
    except Exception:
        return None
    return next((m for m in data["messages"] if isinstance(m, dict) and m.get("name") == name), None)


def unique_name(path, name):
    """`name`, ou « name (2) », « name (3) »… s'il est déjà pris dans le fichier `path`."""
    n, candidate = 1, name
    while find_saved(path, candidate) is not None:
        n += 1
        candidate = f"{name} ({n})"
    return candidate


def save_message_file(path, msg):
    """Ajoute (ou remplace, même nom) un message dans le fichier `path`, créé au besoin.

    Retourne (chemin, remplacé). Les commentaires du fichier ne sont pas conservés : c'est un
    fichier écrit par SerialHex (on peut le renommer pour le garder tel quel).
    """
    path = Path(path)
    data = _read_saved(path)
    messages = data["messages"]
    replaced = False
    for i, m in enumerate(messages):
        if isinstance(m, dict) and m.get("name") == msg["name"]:
            messages[i] = msg
            replaced = True
            break
    if not replaced:
        messages.append(msg)
    head = ("// Messages sauvegardés depuis l'onglet Protocole (bouton « Sauvegarder… »).\n"
            "// Trame construite par le protocole en cours ; REQUEST ID, COMMAND ID et DATA\n"
            "// modifiables dans l'onglet Manuel. Voir docs/Francais/MESSAGES.md (messages de protocole).\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, replaced


def save_message(folder, msg, file_name=SAVED_FILE):
    """save_message_file dans folder/file_name (Msg_Sauvegardes.json par défaut)."""
    return save_message_file(Path(folder) / file_name, msg)
