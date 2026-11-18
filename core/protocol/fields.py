"""
core/protocol/fields.py — Description d'un champ de trame (lue dans le fichier de conf).

Un champ = un nom, une taille, un RÔLE et une couleur. Rôles :

    value       octet(s) fixe(s) vérifié(s) au décodage (ex. octet de synchro 0x7E)
    request_id  numéro de requête, recopié dans la réponse
    command_id  identifiant de la commande
    length      longueur calculée des champs listés dans "of" (souvent DATA)
    error       code d'erreur de la réponse (0 = pas d'erreur)
    crc         CRC ou somme sur une plage d'octets ("algo", "over")
    data        données de la commande (taille : length, fixe, ou le reste)
    field       autre champ numérique, valeur par défaut "default"
    na          octet(s) non lu(s) : ignorés au décodage, remplis avec "fill" à la construction
    copy        recopie d'un champ précédent ("same_as") : longueur répétée (M-Bus, Profibus)

Clés de lecture humaine (sans effet sur les octets) : "description", "description_en",
"values" (texte de chaque valeur : {"0": "OK", "1": {"fr": "…", "en": "…"}}), "category".
Une clé à null est ignorée : on peut garder toutes les clés dans le fichier, utilisées ou non.

Taille : en octets ("size", ou "LENO") ou en bits ("LENb") : "LENO": 1 = "LENb": 8.
Placement : par défaut, les champs se suivent dans l'ordre de la liste. Un champ peut
aussi être placé avec "at" / "atO" (numéro d'octet, "start" ou "end"), "atb" (numéro
de bit) ou "after" (après tel champ) : voir placement.py.
En interne, tailles et positions sont comptées en BITS.

Couleur : un nom (hdr, cmd, crc, na) ou directement une couleur "#RRGGBB".

Les vérifications de cohérence entre champs sont dans check_layout().
"""
import re
from dataclasses import dataclass
from typing import Optional, Union

from .common import ProtocolError, to_int
from .crc import CRC_PRESETS, Crc

ROLES = ("value", "request_id", "command_id", "length", "error", "crc", "data", "field", "na", "copy")
NUMERIC_ROLES = ("value", "request_id", "command_id", "length", "error", "field", "copy")
UNIQUE_ROLES = ("request_id", "command_id", "length", "error", "data")     # au plus un par sens
COLORS = ("hdr", "cmd", "crc", "na", None)
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")      # couleur donnée directement : "#FF8800"
PLACES = ("start", "end")                          # valeurs texte de "at"
MAX_BYTES = {"data": 0xFFFF, "na": 255}            # taille maximale par rôle ; 4 octets pour les autres
BYTE_SIZE_KEYS = ("size", "LENO", "LEN0")          # taille en octets ("LEN0" : faute de frappe tolérée)
BIT_SIZE_KEYS = ("LENb",)                          # taille en bits
BYTE_AT_KEYS = ("at", "atO", "at0")                # position en octets
BIT_AT_KEYS = ("atb",)                             # position en bits
WHOLE_BYTES = ("data", "crc")                      # rôles toujours en octets entiers


@dataclass
class FieldSpec:
    name: str
    role: str = "field"
    bits: Optional[int] = None          # taille en bits ; None = variable (DATA seulement)
    value: Optional[int] = None         # rôle value : valeur attendue
    default: int = 0                    # rôle field : valeur à la construction
    fill: int = 0                       # rôle na : octet écrit à la construction
    color: Optional[str] = None         # "hdr", "cmd", "crc", "na" ou None
    algo: Optional[Crc] = None          # rôle crc
    over: tuple = (0, "end")            # rôle crc : (début, fin) inclus
    cond: Optional[str] = None          # "if" : présent si ce champ est présent et non nul / non vide
    of: tuple = ()                      # rôle length : champs comptés
    order: Optional[str] = None         # ordre des octets propre au champ (sinon celui du protocole)
    at: Union[int, str, None] = None    # placement : BIT de départ, "start" ou "end"
    after: Optional[str] = None         # placement : juste après ce champ
    same_as: Optional[str] = None       # rôle copy : champ recopié
    description: str = ""               # texte libre (français)
    description_en: str = ""            # texte libre (anglais)
    values: Optional[dict] = None       # {valeur: texte ou {"fr": …, "en": …}} : sens de chaque valeur
    category: Optional[str] = None      # catégorie libre (voir "categories" du fichier)

    @property
    def present(self):
        """False pour un champ de taille 0 (gardé dans le fichier pour mémoire, mais absent)."""
        return self.bits != 0

    @property
    def size(self):
        """Taille en octets si elle est entière, sinon None (DATA variable, champ en bits)."""
        return self.bits // 8 if self.bits is not None and self.bits % 8 == 0 else None


def bits_text(bits):
    """'2 octet(s)' pour une taille entière en octets, sinon '12 bits'."""
    return f"{bits // 8} octet(s)" if bits % 8 == 0 else f"{bits} bits"


def position_text(bit):
    """« l'octet 3 » si la position tombe sur un octet, sinon « le bit 19 »."""
    return f"l'octet {bit // 8}" if bit % 8 == 0 else f"le bit {bit}"


def at_text(bit):
    """« à l'octet 3 » / « au bit 19 »."""
    return f"à l'octet {bit // 8}" if bit % 8 == 0 else f"au bit {bit}"


# --------------------------------------------------------------------------
# Lecture d'un champ
# --------------------------------------------------------------------------

def parse_field(d, crcs, kind):
    """Un élément de la liste "tx" ou "rx" -> FieldSpec. Lève ProtocolError si invalide.

    crcs : CRC nommés de la section "crc" ; kind : "tx" ou "rx" (pour les messages).
    """
    if not isinstance(d, dict) or not d.get("name"):
        raise ProtocolError(f"{kind} : chaque champ doit avoir un \"name\"")
    d = {k: v for k, v in d.items() if v is not None}       # clé à null = non utilisée
    where = f"{kind} : champ {d['name']!r}"
    f = FieldSpec(d["name"], _role(d, where))
    _read_common(f, d, where)
    _read_texts(f, d, where)
    if f.role == "crc":
        _read_crc(f, d, crcs, where)
    _read_bits(f, d, where)
    if f.role == "value":
        _read_value(f, d, where)
    elif f.role == "field":
        f.default = to_int(d.get("default", 0), f"{where} default")
    elif f.role == "length":
        _read_length(f, d, where)
    elif f.role == "na":
        _read_na(f, d, where)
    elif f.role == "copy":
        if "same_as" not in d:
            raise ProtocolError(f"{where} : \"same_as\" manquant (champ recopié)")
        f.same_as = str(d["same_as"])
    return f


def _read_texts(f, d, where):
    """Clés de lecture humaine : description(s), sens des valeurs, catégorie."""
    f.description = str(d.get("description", ""))
    f.description_en = str(d.get("description_en", ""))
    f.category = str(d["category"]) if "category" in d else None
    values = d.get("values")
    if values is None:
        return
    if not isinstance(values, dict):
        raise ProtocolError(f"{where} : values doit être un objet {{valeur: texte}}")
    f.values = {to_int(k, f"{where} values"): v for k, v in values.items()}


def value_text(texts, value, language="fr"):
    """Texte d'une valeur dans une table {valeur: texte ou {"fr", "en"}} ('' si absente)."""
    text = (texts or {}).get(value)
    if isinstance(text, dict):
        return str(text.get(language) or text.get("fr") or text.get("en") or "")
    return "" if text is None else str(text)


def _role(d, where):
    """Rôle du champ ; par défaut "value" si une valeur est donnée, sinon "field"."""
    role = str(d.get("role", "value" if "value" in d else "field")).lower()
    if role not in ROLES:
        raise ProtocolError(f"{where} : rôle '{role}' inconnu ({', '.join(ROLES)})")
    return role


def _read_common(f, d, where):
    """Clés valables pour tous les rôles : color, order, if, at, after."""
    f.color = d.get("color")
    if f.color not in COLORS and not (isinstance(f.color, str) and HEX_COLOR.match(f.color)):
        raise ProtocolError(f"{where} : couleur '{f.color}' inconnue (hdr, cmd, crc, na ou #RRGGBB)")
    if f.color is None and f.role == "na":
        f.color = "na"                          # octets non lus : gris très clair par défaut
    f.order = d.get("order")
    if f.order not in (None, "little", "big"):
        raise ProtocolError(f"{where} : order doit valoir little ou big")
    f.cond = d.get("if")
    _read_place(f, d, where)


def _read_place(f, d, where):
    """Placement : "at" / "atO" (octet, "start", "end"), "atb" (bit) ou "after" (nom d'un champ).

    La position est gardée en bits : "atO": 2 = "atb": 16.
    """
    keys = [k for k in BYTE_AT_KEYS + BIT_AT_KEYS if k in d]
    if keys and "after" in d:
        raise ProtocolError(f"{where} : \"at\" et \"after\" ne peuvent pas être utilisés ensemble")
    if len(keys) > 1:
        raise ProtocolError(f"{where} : une seule position ({', '.join(keys)})")
    if d.get("after") is not None:
        f.after = str(d["after"])
    if not keys or d[keys[0]] is None:
        return
    key, at = keys[0], d[keys[0]]
    if isinstance(at, str) and at.lower() in PLACES:
        f.at = at.lower()
        return
    unit = 1 if key in BIT_AT_KEYS else 8
    f.at = to_int(at, f"{where} {key}") * unit
    if f.at < 0:
        what = "de bit" if unit == 1 else "d'octet"
        raise ProtocolError(f"{where} : {key} doit être un numéro {what} (0, 1, 2…), \"start\" ou \"end\"")


def _read_crc(f, d, crcs, where):
    """Rôle crc : "algo" (nom de la section crc ou nom prêt à l'emploi) et "over"."""
    name = d.get("algo")
    if name is None:
        raise ProtocolError(f"{where} : \"algo\" manquant")
    f.algo = crcs.get(name) or CRC_PRESETS.get(name)
    if f.algo is None:
        raise ProtocolError(f"{where} : CRC '{name}' ni défini dans \"crc\" ni connu")
    over = d.get("over", [0, "end"])
    if not (isinstance(over, list) and len(over) == 2):
        raise ProtocolError(f"{where} : over doit être [début, fin]")
    f.over = tuple(over)


def _read_bits(f, d, where):
    """Taille : "size" / "LENO" en octets, ou "LENb" en bits. Obligatoire, sauf pour DATA
    (variable) et un CRC (taille de l'algorithme)."""
    byte_keys = [k for k in BYTE_SIZE_KEYS if d.get(k) is not None]
    bit_keys = [k for k in BIT_SIZE_KEYS if d.get(k) is not None]
    if len(byte_keys) + len(bit_keys) > 1:
        raise ProtocolError(f"{where} : une seule taille ({', '.join(byte_keys + bit_keys)})")
    if byte_keys:
        f.bits = 8 * to_int(d[byte_keys[0]], f"{where} {byte_keys[0]}")
    elif bit_keys:
        f.bits = to_int(d[bit_keys[0]], f"{where} {bit_keys[0]}")
    elif f.role == "crc":
        f.bits = f.algo.width
    elif f.role != "data":
        raise ProtocolError(f"{where} : \"size\" manquant (ou LENO / LENb)")
    if f.bits is not None:
        _check_bits(f, where)


def _check_bits(f, where):
    maximum = MAX_BYTES.get(f.role, 4)
    if not 0 <= f.bits <= 8 * maximum:
        raise ProtocolError(f"{where} : size doit valoir 0 à {maximum} octets ({8 * maximum} bits)")
    if f.role in WHOLE_BYTES and f.bits % 8:
        raise ProtocolError(f"{where} : un champ {f.role} doit faire un nombre entier d'octets")
    if f.role == "crc" and f.bits not in (0, f.algo.width):
        raise ProtocolError(f"{where} : size {f.bits // 8} incompatible avec {f.algo.name} ({f.algo.size} octet(s))")


def _read_value(f, d, where):
    if "value" not in d:
        raise ProtocolError(f"{where} : \"value\" manquant")
    f.value = to_int(d["value"], f"{where} value")
    if f.value >= 1 << f.bits:
        raise ProtocolError(f"{where} : value ne tient pas sur {bits_text(f.bits)}")


def _read_length(f, d, where):
    of = d.get("of")
    if of is None:
        raise ProtocolError(f"{where} : \"of\" manquant (champ(s) comptés, ex. \"DATA\")")
    f.of = (of,) if isinstance(of, str) else tuple(of)


def _read_na(f, d, where):
    f.fill = to_int(d.get("fill", 0), f"{where} fill")
    if not 0 <= f.fill <= 0xFF:
        raise ProtocolError(f"{where} : fill doit valoir 0 à 255 (un octet)")


# --------------------------------------------------------------------------
# Cohérence d'un sens (tx ou rx)
# --------------------------------------------------------------------------

def check_layout(fields, kind):
    """Vérifie l'ensemble des champs d'un sens. Lève ProtocolError au premier problème."""
    check_unique_names(fields, kind)
    _check_unique_roles(fields, kind)
    index = {f.name: i for i, f in enumerate(fields)}
    for i, f in enumerate(fields):
        _check_references(f, i, index, kind, fields)
    _check_variable_data(fields, index, kind)
    _check_alignment(fields, kind)
    _check_length_counts(fields, kind)


def check_unique_names(fields, kind):
    names = [f.name for f in fields]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ProtocolError(f"{kind} : noms en double : {', '.join(sorted(duplicates))}")


def _check_unique_roles(fields, kind):
    for role in UNIQUE_ROLES:
        if sum(f.role == role and f.present for f in fields) > 1:
            raise ProtocolError(f"{kind} : un seul champ de rôle '{role}'")


def _check_references(f, i, index, kind, fields_by_index):
    """Les champs nommés par "if", "over" et "of" doivent exister (et "of" être après la longueur)."""
    if f.cond and f.cond not in index:
        raise ProtocolError(f"{kind} : champ {f.name!r} : \"if\" désigne un champ inconnu '{f.cond}'")
    if f.role == "crc":
        for p in f.over:
            if isinstance(p, str) and p != "end" and p not in index:
                raise ProtocolError(f"{kind} : champ {f.name!r} : over désigne un champ inconnu '{p}'")
    if f.role == "copy":
        if f.same_as not in index:
            raise ProtocolError(f"{kind} : champ {f.name!r} : same_as désigne un champ inconnu '{f.same_as}'")
        if index[f.same_as] > i:
            raise ProtocolError(f"{kind} : champ {f.name!r} : le champ recopié '{f.same_as}' doit le précéder")
        if fields_by_index[index[f.same_as]].role not in NUMERIC_ROLES:
            raise ProtocolError(f"{kind} : champ {f.name!r} : le champ recopié '{f.same_as}' doit être numérique")
    if f.role == "length":
        for name in f.of:
            if name not in index:
                raise ProtocolError(f"{kind} : champ {f.name!r} : of désigne un champ inconnu '{name}'")
            if index[name] < i:
                raise ProtocolError(f"{kind} : la longueur {f.name!r} doit précéder le champ {name!r}")


def _check_variable_data(fields, index, kind):
    """DATA « le reste de la trame » : les champs qui suivent doivent avoir une taille connue."""
    data = next((f for f in fields if f.role == "data" and f.present), None)
    if data is None or data.bits is not None or any(f.role == "length" for f in fields):
        return
    after = fields[index[data.name] + 1:]
    if any(f.bits is None for f in after):
        raise ProtocolError(f"{kind} : après une DATA de taille variable, les champs doivent avoir une taille fixe")


def _check_alignment(fields, kind):
    """Les champs en bits doivent se regrouper en octets entiers : DATA et les CRC commencent
    sur un octet, un champ conditionnel fait un nombre entier d'octets, la trame finit sur un octet."""
    phase = 0                                       # position dans l'octet en cours (0 à 7)
    for f in fields:
        if not f.present:
            continue
        if f.cond and f.bits and f.bits % 8:
            raise ProtocolError(f"{kind} : champ {f.name!r} : un champ conditionnel (if) doit faire un nombre entier d'octets")
        if f.role in WHOLE_BYTES and phase:
            raise ProtocolError(f"{kind} : champ {f.name!r} : doit commencer sur un octet entier "
                                f"(il commence au bit {phase} d'un octet)")
        phase = (phase + (f.bits or 0)) % 8
    if phase:
        raise ProtocolError(f"{kind} : la trame ne finit pas sur un octet entier (il manque {8 - phase} bit(s))")


def _check_length_counts(fields, kind):
    """Une longueur compte des octets : ensemble, les champs comptés doivent faire des octets
    entiers (un champ de 1 bit et un de 7 bits peuvent être comptés ensemble : Modbus TCP)."""
    by_name = {f.name: f for f in fields}
    for f in fields:
        if f.role != "length":
            continue
        total = sum(by_name[name].bits or 0 for name in f.of)
        if total % 8:
            raise ProtocolError(f"{kind} : champ {f.name!r} : les champs comptés par of doivent faire ensemble "
                                f"des octets entiers ({total} bits)")


# --------------------------------------------------------------------------
# Plage d'octets d'un CRC (utilisée à la construction et au décodage)
# --------------------------------------------------------------------------

def crc_range(spec, placed, crc_start):
    """Plage [a, b[ d'octets couverte par le CRC `spec`.

    placed    : {nom de champ: (premier octet, taille)} des champs présents dans la trame
    crc_start : position du CRC lui-même
    Début : entier (octet) ou nom de champ (son premier octet).
    Fin   : entier (octet, inclus), nom de champ (son dernier octet), ou "end"
            (dernier octet avant le CRC). Un champ absent (ex. DATA vide) donne une plage vide.
    """
    lo, hi = spec.over
    if isinstance(lo, str):
        if lo not in placed:
            return 0, 0
        a = placed[lo][0]
    else:
        a = lo
    if hi == "end":
        b = crc_start
    elif isinstance(hi, str):
        if hi not in placed:
            return 0, 0
        start, size = placed[hi]
        b = start + size
    else:
        b = hi + 1
    return a, max(a, b)
