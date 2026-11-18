"""
core/messages.py — Chargement des fichiers de messages.

Rôle
    Lire les fichiers msgLibrary/msgManual/Msg_<nom>.json, vérifier qu'ils sont
    valides et les fusionner en une seule liste de messages.

Règles
    - Un fichier par fonction : Msg_Sorties.json, Msg_Moteur.json...
      (l'ancien préfixe « Message_ » est encore accepté)
    - Le groupe affiché dans l'interface = le nom après « Msg_ »,
      sauf si le fichier précise "group" (utile pour les accents).
    - Un fichier invalide est signalé mais n'empêche pas les autres de charger.
    - Doublons (merge_messages) : un message identique à un message déjà chargé (même dans un
      autre groupe) est ignoré ;
      deux messages de même nom dans le même groupe mais différents sont gardés, et leur nom
      affiché est complété par le fichier d'origine (clé "display").
    - Clés ajoutées au chargement, commençant par « _ » ("_file" : fichier d'origine) ou
      "display" : jamais réécrites dans un fichier (merge_files).

Format détaillé des fichiers : docs/Francais/MESSAGES.md
"""
import json
from pathlib import Path

from .frames import build_frame, defaults_for
from .jsonc import load_file
from .request_message import check_request, is_request

# Préfixe obligatoire des fichiers de messages
MSG_PREFIX = "Msg_"
# Préfixes acceptés : le nouveau en premier, puis l'ancien (fichiers existants)
MSG_PREFIXES = (MSG_PREFIX, "Message_")


def _prefix_of(name):
    """Préfixe reconnu au début de `name`, ou None."""
    return next((p for p in MSG_PREFIXES if name.startswith(p)), None)


def group_from_filename(path):
    """Msg_Sorties.json -> 'Sorties' ; None si le nom ne commence pas par Msg_ (ou Message_)."""
    stem = Path(path).stem
    prefix = _prefix_of(stem)
    return stem[len(prefix):] if prefix else None


def message_files(folder):
    """Liste les Msg_*.json (et anciens Message_*.json) d'un dossier, triés par nom.

    Le tri ignore les majuscules : Msg_0x0000002A_..._Get.json et ..._Set.json
    se suivent. Retourne une liste vide si le dossier n'existe pas.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    files = {p for prefix in MSG_PREFIXES for p in folder.glob(prefix + "*.json")}
    return sorted(files, key=lambda p: p.name.lower())


def load_messages(path):
    """Charge et valide UN fichier de messages.

    Formats acceptés :
      {"group": "...", "messages": [ {...}, {...} ]}   <- format normal
      [ {...}, {...} ]                                  <- liste seule
      {"name": "...", "frame": [...]}                   <- un seul message
    Un même fichier peut aussi contenir "commands" et "errors" (protocole,
    voir core/commands) : ces parties sont ignorées ici. La clé "protocol"
    (protocole pour lequel le fichier a été écrit) est recopiée dans chaque message.

    Retourne la liste des messages (dict), chacun complété par son "group".
    Lève ValueError (ou une erreur JSON) si le fichier est invalide.
    """
    data = load_file(path)                  # commentaires // et /* */ acceptés

    # Récupère la liste des messages selon le format du fichier
    if isinstance(data, dict) and "messages" in data:
        msgs = data["messages"]
    elif isinstance(data, list):
        msgs = data
    elif isinstance(data, dict) and "frame" in data:
        msgs = [data]
    elif isinstance(data, dict) and ("commands" in data or "errors" in data):
        # Fichier qui ne contient que des commandes du protocole et / ou des
        # codes d'erreur (lus par core/commands.py) : pas de message ici.
        msgs = []
    else:
        raise ValueError("format JSON non reconnu")

    # Groupe : "group" du fichier en priorité, sinon déduit du nom de fichier
    group = data.get("group") if isinstance(data, dict) else None
    group = group or group_from_filename(path)
    # Protocole pour lequel le fichier a été écrit (information, affichée dans l'onglet Manuel)
    protocol = data.get("protocol") if isinstance(data, dict) else None

    for m in msgs:
        if "name" not in m or ("frame" not in m and not is_request(m)):
            raise ValueError("chaque message doit avoir 'name' et 'frame'")
        # Un message peut forcer son propre groupe ; sinon il prend celui du fichier
        if group and "group" not in m:
            m["group"] = group
        if protocol and "protocol" not in m:
            m["protocol"] = protocol
        m["_file"] = Path(path).name            # fichier d'origine (doublons de nom)
        m["_path"] = str(Path(path).resolve())  # chemin complet (bouton Retirer de l'onglet Manuel)
        # On construit la trame avec les valeurs par défaut pour détecter
        # dès le chargement les erreurs de définition (paramètre manquant,
        # hexa invalide, type inconnu...) plutôt qu'au moment de l'envoi.
        try:
            if is_request(m):
                check_request(m)                # trame construite par le protocole en cours
            else:
                build_frame(m, defaults_for(m))
        except Exception as e:
            raise ValueError(f"message '{m['name']}' : {e}")
    return msgs


def load_folder(folder):
    """Charge tous les Msg_*.json d'un dossier.

    Retourne (messages, erreurs) :
      messages : liste de tous les messages valides, dans l'ordre des fichiers
      erreurs  : liste de (nom_fichier, message_erreur) pour les fichiers invalides
    """
    messages, errors = [], []
    for path in message_files(folder):
        try:
            messages, _added, _same = merge_messages(messages, load_messages(path))
        except Exception as e:
            errors.append((path.name, str(e)))
    return messages, errors


def clean(msg):
    """Message sans les clés ajoutées au chargement ("_file", "display")."""
    return {k: v for k, v in msg.items() if not k.startswith("_") and k != "display"}


def message_key(msg):
    """Contenu d'un message, pour repérer les doublons : le groupe (souvent déduit du nom du
    fichier) et les clés ajoutées au chargement ne comptent pas ; une copie d'un fichier sous
    un autre nom ne double donc pas la liste."""
    return json.dumps({k: v for k, v in clean(msg).items() if k != "group"}, sort_keys=True, ensure_ascii=False)


def merge_messages(messages, new):
    """Ajoute `new` à `messages` sans doublon.

    Retourne (liste, nombre ajouté, nombre ignoré car identique à un message déjà présent).
    Les messages de même nom dans le même groupe mais de contenu différent sont gardés :
    leur "display" (nom affiché) est complété par le fichier d'origine, ou numéroté.
    """
    keys = {message_key(m) for m in messages}
    out, added, same = list(messages), 0, 0
    for m in new:
        key = message_key(m)
        if key in keys:
            same += 1
            continue
        keys.add(key)
        out.append(m)
        added += 1
    label_duplicates(out)
    return out, added, same


def label_duplicates(messages):
    """Nom affiché ("display") des messages de même nom et même groupe."""
    by_name = {}
    for m in messages:
        m.pop("display", None)
        by_name.setdefault((m.get("group"), m["name"]), []).append(m)
    for (_group, name), same in by_name.items():
        if len(same) < 2:
            continue
        files = [m.get("_file") for m in same]
        distinct_files = len(set(files)) == len(files) and all(files)
        for n, m in enumerate(same, 1):
            m["display"] = f"{name}  [{m['_file']}]" if distinct_files else f"{name}  ({n})"


def display_name(msg):
    """Nom affiché d'un message dans l'onglet Manuel."""
    return msg.get("display") or msg["name"]


def merge_files(folder, out_path):
    """Fusionne tous les Msg_*.json du dossier dans un seul fichier `out_path`.

    Chaque message garde son groupe. Refuse de fusionner si un fichier est
    invalide (pour ne pas produire un fichier incomplet sans le savoir).
    Retourne le nombre de messages écrits.
    """
    messages, errors = load_folder(folder)
    if errors:
        raise ValueError("; ".join(f"{name} : {err}" for name, err in errors))
    Path(out_path).write_text(
        json.dumps({"messages": [clean(m) for m in messages]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(messages)
