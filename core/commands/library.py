"""
core/commands/library.py — Bibliothèque : commandes (Command), recherche (Library), lecture et vérification des Msg_*.json.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from ..frames import parse_int
from ..jsonc import load_file
from ..messages import group_from_filename, message_files
from .types import FORMATS, OTHER_TYPES, _count, _enum_spec, _int_spec, _is_enum, _num, _scalar_size, _type, field_size
from .encode import encode_field, encode_fields

@dataclass
class Command:
    """Une commande du protocole.

    Clés facultatives d'un Msg_*.json (en plus de name, id, tx, rx, presets) :
        name_en / description_en : textes en anglais (interface en anglais)
        group      : catégorie (ex. "LAS", "COM") ; texte lisible dans "categories" du protocole
        variant    : format de trame à utiliser pour la requête (protocole à variantes : M-Bus, Profibus)
        header     : valeurs des champs d'en-tête de la requête, par nom ou rôle : {"CI": "0x50"}
        match      : valeurs de champs "tx" qui distinguent des commandes au même COMMAND ID
                     (Modbus : même fonction 03, registres différents) : {"register": "0x0010"}
        attributes : champs libres affichés avec la description : {"access": "R", "level": "expert"}
        hidden     : true = commande masquée : absente des listes de l'onglet Protocole (sauf case
                     « Masquées » cochée) mais toujours reconnue au décodage des trames.
                     Sert aux commandes obsolètes, internes ou commentées dans le code de l'appareil.
                     Peut aussi être mis au niveau du fichier ("hidden": true) pour toutes ses commandes.
    """
    name: str
    id: int                                     # COMMAND ID
    group: str = ""
    description: str = ""
    tx: List[dict] = field(default_factory=list)       # champs de DATA de la requête
    rx: List[dict] = field(default_factory=list)       # champs de DATA de la réponse
    presets: List[dict] = field(default_factory=list)  # [{"name": ..., "values": {...}}]
    name_en: str = ""
    description_en: str = ""
    variant: str = ""
    header: Dict[str, object] = field(default_factory=dict)
    match: Dict[str, object] = field(default_factory=dict)
    attributes: Dict[str, object] = field(default_factory=dict)
    id_digits: int = 8                          # chiffres hexa du COMMAND ID affiché ("0x03" -> 2)
    hidden: bool = False                        # commande masquée dans les listes (reconnue au décodage)

    @property
    def label(self):
        """Texte affiché dans la liste : 'WRITE / Écrire consigne (0x06)'."""
        prefix = f"{self.group} / " if self.group else ""
        return f"{prefix}{self.name} (0x{self.id:0{self.id_digits}X})"

    def text(self, language="fr"):
        """(nom, description) dans la langue choisie ; repli sur le français."""
        if language == "en":
            return self.name_en or self.name, self.description_en or self.description
        return self.name, self.description

    def attributes_text(self):
        """« access = R · level = expert », ou ''."""
        return " · ".join(f"{k} = {v}" for k, v in self.attributes.items())


def tx_matches(cmd, data, cfg=None):
    """True si les octets DATA d'une requête ont les valeurs "match" de la commande."""
    offset = 0
    for fdef in cmd.tx:
        if fdef["name"] in cmd.match:
            expected = encode_field(fdef, cmd.match[fdef["name"]], cfg) if cfg else encode_field(fdef, cmd.match[fdef["name"]])
            if bytes(data[offset:offset + len(expected)]) != expected:
                return False
        size = field_size(fdef)
        if size is None:
            break
        offset += size
    return True


def header_matches(cmd, fields):
    """True si les champs d'en-tête décodés {nom ou rôle: valeur} ont les valeurs "header" de la commande."""
    for key, value in cmd.header.items():
        if key in fields and fields[key] != parse_int(value):
            return False
    return True


def distinct(a, b):
    """Deux commandes au même COMMAND ID se distinguent-elles (match, header ou variante) ?"""
    def differ(x, y):
        return bool(x) and bool(y) and x != y
    return differ(a.match, b.match) or differ(a.header, b.header) or differ(a.variant, b.variant)


def specific(cmd):
    """True si la commande vise un cas précis de son COMMAND ID ("match", "header" ou "variant")."""
    return bool(cmd.match or cmd.header or cmd.variant)


def compatible(a, b):
    """Deux commandes au même COMMAND ID peuvent-elles cohabiter ?

    Oui si elles se distinguent (distinct), ou si l'une est précise et l'autre générique :
    la générique sert alors de repli au décodage (ex. Modbus : « Lire registres » de la
    liste standard, et « Lire consigne » d'un appareil, fonction 03 registre 0x0000)."""
    if a.hidden or b.hidden:
        return True
    if distinct(a, b):
        return True
    if specific(a) and specific(b):
        return False                    # précises toutes les deux, mais sur les mêmes valeurs
    return specific(a) != specific(b)


@dataclass
class Library:
    commands: List[Command] = field(default_factory=list)
    errors: Dict[int, object] = field(default_factory=dict)   # code d'erreur -> texte, ou {"fr": …, "en": …}
    problems: List[tuple] = field(default_factory=list)       # (fichier, message) des définitions invalides
    skipped: List[tuple] = field(default_factory=list)        # (fichier, protocole visé) des fichiers d'un autre protocole
    language: str = "fr"                                      # langue des textes (erreurs, noms des commandes)

    def by_id(self, command_id):
        """Première commande de ce COMMAND ID (une commande visible avant une masquée), ou None."""
        same = [c for c in self.commands if c.id == command_id]
        return _prefer_visible(same)[0] if same else None

    def visible(self, show_hidden=False):
        """Commandes à afficher dans les listes : toutes si show_hidden, sinon sans les masquées."""
        if show_hidden:
            return list(self.commands)
        return [c for c in self.commands if not c.hidden]

    def hidden_count(self):
        """Nombre de commandes masquées."""
        return sum(1 for c in self.commands if c.hidden)

    def find(self, command_id, data=None, cfg=None, fields=None, variant=None):
        """Commande d'après son COMMAND ID. Si plusieurs commandes l'ont, on départage par :
            - variant : format de trame décodé (M-Bus court / long…)
            - fields  : valeurs des champs d'en-tête décodés {nom ou rôle: valeur}, comparées
                        au "header" de chaque commande (M-Bus : même C, CI différent)
            - data    : octets DATA, comparés aux valeurs "match" (Modbus : même fonction,
                        registre différent)
        None si aucune commande ne convient."""
        same = _prefer_visible([c for c in self.commands if c.id == command_id])
        if len(same) <= 1:
            return same[0] if same else None
        if variant:
            same = [c for c in same if not c.variant or c.variant == variant] or same
        if fields:
            same = [c for c in same if header_matches(c, fields)] or same
        if data is not None:
            for c in same:
                if c.match and tx_matches(c, data, cfg):
                    return c
            same = [c for c in same if not c.match] or same
        return same[0]

    def by_label(self, label):
        return next((c for c in self.commands if c.label == label), None)

    def error_text(self, code):
        """Texte d'un code d'erreur dans la langue choisie, ou '' s'il n'est pas défini."""
        text = self.errors.get(code, "")
        if isinstance(text, dict):
            return str(text.get(self.language) or text.get("fr") or text.get("en") or "")
        return str(text)


SET_BIT = 0x80000000                    # bit de poids fort du COMMAND ID : Set (écriture)


def opcode_key(command_id):
    """Clé de tri d'un COMMAND ID : les 31 bits de poids faible (opcode) croissants, puis le Get
    (bit 31 à 0) avant le Set (bit 31 à 1) : 0x00000004, 0x80000004, 0x00000007, 0x80000007…
    Pour un COMMAND ID court (fonction Modbus 0x03, 0x06…), c'est simplement l'ordre croissant."""
    command_id = int(command_id) & 0xFFFFFFFF
    return command_id & ~SET_BIT, 1 if command_id & SET_BIT else 0


def _prefer_visible(commands):
    """Les commandes visibles si il y en a, sinon toutes (une commande masquée qui partage
    son COMMAND ID avec une visible, ex. ancien nom commenté, ne sert qu'en dernier recours)."""
    return [c for c in commands if not c.hidden] or commands


def _check_defs(defs, part):
    """Vérifie une liste de champs ("tx" ou "rx"). Lève ValueError si invalide."""
    names = set()
    for i, f in enumerate(defs):
        if "name" not in f:
            raise ValueError(f"{part} : un champ n'a pas de 'name'")
        where = f"{part}.{f['name']}"
        if f["name"] in names:
            raise ValueError(f"{part} : champ '{f['name']}' en double")
        names.add(f["name"])
        t = _type(f)
        if not _int_spec(t) and t not in OTHER_TYPES:
            raise ValueError(f"{where} : type inconnu '{f.get('type')}'")
        if t == "enum" and not f.get("choices"):
            raise ValueError(f"{where} : 'choices' manquant")
        if t == "enum" and not _enum_spec(f):
            raise ValueError(f"{where} : 'size' doit être un type entier")
        if f.get("choices") and not _is_enum(f):
            raise ValueError(f"{where} : 'choices' n'est possible que sur un entier")
        if _num(f, "factor", 1) == 0:
            raise ValueError(f"{where} : factor ne peut pas valoir 0")
        if f.get("count") is not None:
            if not isinstance(f["count"], int) or f["count"] < 1:
                raise ValueError(f"{where} : count doit être un entier >= 1")
        if _count(f):
            if _scalar_size(f) is None:
                raise ValueError(f"{where} : un tableau ne peut pas contenir d'éléments de taille variable")
        if f.get("format") and f["format"] not in FORMATS:
            raise ValueError(f"{where} : format inconnu '{f['format']}' ({', '.join(FORMATS)})")
        if f.get("bits") and not _int_spec(t):
            raise ValueError(f"{where} : 'bits' n'est possible que sur un entier")
        if field_size(f) is None and i != len(defs) - 1:
            raise ValueError(f"{where} : taille variable autorisée seulement pour le dernier champ")


def parse_library_file(data, path=""):
    """Lit la partie protocole d'un fichier JSON déjà chargé.

    Retourne (commandes, erreurs). Lève ValueError si une définition est invalide.
    """
    if not isinstance(data, dict):
        return [], {}
    group = data.get("group") or group_from_filename(path) or ""
    file_hidden = bool(data.get("hidden"))      # "hidden": true au niveau du fichier : toutes masquées
    commands = []
    for c in data.get("commands", []):
        if "name" not in c or "id" not in c:
            raise ValueError("chaque commande doit avoir 'name' et 'id'")
        cmd = _new_command(c, group, file_hidden)
        try:
            _check_defs(cmd.tx, "tx")
            _check_defs(cmd.rx, "rx")
            _check_match(cmd)
            encode_fields(cmd.tx, {})               # les valeurs par défaut doivent être valides
            for p in cmd.presets:                   # les données prédéfinies aussi
                if "name" not in p or "values" not in p:
                    raise ValueError("chaque preset doit avoir 'name' et 'values'")
                unknown = set(p["values"]) - {f["name"] for f in cmd.tx}
                if unknown:
                    raise ValueError(f"preset '{p['name']}' : champ(s) inconnu(s) {', '.join(sorted(unknown))}")
                try:
                    encode_fields(cmd.tx, p["values"])
                except ValueError as e:
                    raise ValueError(f"preset '{p['name']}' : {e}")
        except ValueError as e:
            raise ValueError(f"commande '{cmd.name}' : {e}")
        commands.append(cmd)
    errors = {parse_int(k): (v if isinstance(v, dict) else str(v)) for k, v in (data.get("errors") or {}).items()}
    return commands, errors


def _new_command(c, group, file_hidden=False):
    """Command d'après sa définition JSON (les clés à null comptent comme absentes).
    file_hidden : valeur de "hidden" du fichier, utilisée si la commande n'a pas la sienne."""
    c = {k: v for k, v in c.items() if v is not None}
    raw_id = c["id"]
    digits = len(raw_id) - 2 if isinstance(raw_id, str) and raw_id.lower().startswith("0x") else 8
    return Command(name=c["name"], id=parse_int(raw_id), group=c.get("group", group),
                   description=c.get("description", ""), tx=c.get("tx", []), rx=c.get("rx", []),
                   presets=c.get("presets", []), name_en=c.get("name_en", ""),
                   description_en=c.get("description_en", ""), variant=c.get("variant", ""),
                   header=dict(c.get("header", {})), match=dict(c.get("match", {})),
                   attributes=dict(c.get("attributes", {})), id_digits=max(1, min(8, digits)),
                   hidden=bool(c.get("hidden", file_hidden)))


def _check_match(cmd):
    """Les valeurs "match" désignent des champs "tx" et doivent être valides. Le champ
    prend la valeur "match" par défaut (pour que la requête construite soit reconnue)."""
    names = {f["name"] for f in cmd.tx}
    for name, value in cmd.match.items():
        if name not in names:
            raise ValueError(f"match : champ '{name}' absent de tx")
        fdef = next(f for f in cmd.tx if f["name"] == name)
        try:
            encode_field(fdef, value)
        except ValueError as e:
            raise ValueError(f"match '{name}' : {e}")
        if fdef.get("default") is None:
            fdef["default"] = value


def made_for(data):
    """Protocole(s) pour lesquels un fichier Msg_*.json a été écrit (clé "protocol").

    "protocol": "Modbus RTU"  ou  ["Modbus RTU", "Modbus TCP"]  ; absent : tous protocoles.
    Retourne une liste de noms (vide = tous).
    """
    value = data.get("protocol") if isinstance(data, dict) else None
    if not value:
        return []
    return [value] if isinstance(value, str) else [str(v) for v in value]


def fits_protocol(data, protocol_name):
    """True si le fichier convient au protocole en cours (comparaison sans majuscules)."""
    names = made_for(data)
    if not names or not protocol_name:
        return True
    return protocol_name.lower() in (n.lower() for n in names)


def load_library(folder, protocol_name=None):
    """Charge les commandes et les erreurs de tous les Msg_*.json d'un dossier.

    protocol_name : protocole en cours ; les fichiers écrits pour un autre protocole
                    (clé "protocol") sont ignorés et listés dans lib.skipped.
    """
    lib = Library()
    seen = {}
    for path in message_files(folder):
        try:
            data = load_file(path)              # commentaires // et /* */ acceptés
            if not fits_protocol(data, protocol_name):
                if data.get("commands") or data.get("errors"):
                    lib.skipped.append((path.name, ", ".join(made_for(data))))
                continue
            commands, errors = parse_library_file(data, path)
        except Exception as e:
            lib.problems.append((path.name, str(e)))
            continue
        _add_commands(lib, commands, seen, path.name)
        lib.errors.update(errors)
    # Listes de l'onglet Protocole rangées par opcode (Get avant Set), et non par fichier ou nom.
    # Tri stable : des commandes au même COMMAND ID (match / header / variant) gardent l'ordre des fichiers.
    lib.commands.sort(key=lambda c: opcode_key(c.id))
    return lib


def _add_commands(lib, commands, seen, file_name):
    """Ajoute les commandes d'un fichier. Un COMMAND ID déjà pris est signalé et la commande
    ignorée, sauf si les deux commandes se distinguent par "match", "header" ou "variant",
    si l'une est précise et l'autre générique (repli, voir compatible), ou si l'une des deux
    est masquée ("hidden" : la visible est prioritaire au décodage)."""
    for c in commands:
        taken = seen.setdefault(c.id, [])
        clash = next((o for o in taken if not compatible(c, o)), None)
        if clash is not None:
            lib.problems.append((file_name, f"COMMAND ID 0x{c.id:0{c.id_digits}X} déjà utilisé par '{clash.name}'"
                                            " (\"match\", \"header\" ou \"variant\" différents pour les distinguer)"))
            continue
        taken.append(c)
        lib.commands.append(c)


