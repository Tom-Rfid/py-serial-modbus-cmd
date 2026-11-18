"""
core/commands/types.py — Types de champs : u8 / i16 / f32 / enum / ascii / hex..., tableaux, tailles, ordre des octets.
"""
import re

# Entiers : (taille en octets, signé). L'ordre des octets vient du réglage du
# protocole (little / big), sauf si le type le précise : u16be, i32le...
INTS = {"u8": (1, False), "i8": (1, True), "u16": (2, False), "i16": (2, True),
        "u32": (4, False), "i32": (4, True)}
# Types acceptés en plus des entiers (bcd : chiffres décimaux codés 2 par octet, M-Bus)
OTHER_TYPES = ("f32", "bool", "enum", "ascii", "hex", "bcd")
# Formats d'affichage / de saisie des tableaux
FORMATS = ("ip", "mac")

# Autres noms acceptés pour les types (colonne « Data format » de la documentation)
#   raw : octets bruts, sans conversion (= hex) ; "count" ou RAW[n] donne le nombre d'octets
TYPE_ALIASES = {"uint8": "u8", "uint16": "u16", "uint32": "u32",
                "int8": "i8", "int16": "i16", "int32": "i32",
                "float": "f32", "float32": "f32", "raw": "hex"}


def _parse_type(raw):
    """'U8[4]' -> ('u8', 4) ; 'uint16be' -> ('u16be', None) ; 'float' -> ('f32', None).

    Les majuscules sont acceptées, et la taille d'un tableau peut être écrite
    directement dans le type, comme dans la documentation (U8[4], F32[2]).
    """
    t = str(raw or "u8").strip().lower()
    count = None
    m = re.fullmatch(r"(.+?)\[(\d+)\]", t)
    if m:
        t, count = m.group(1), int(m.group(2))
    for suffix in ("be", "le"):                 # uint16be -> u16be
        if t.endswith(suffix) and t[:-2] in TYPE_ALIASES:
            t = TYPE_ALIASES[t[:-2]] + suffix
    return TYPE_ALIASES.get(t, t), count


def _type(fdef):
    """Type normalisé d'un champ : 'u8', 'u16be', 'f32', 'enum'..."""
    return _parse_type(fdef.get("type"))[0]


def _raw_count(fdef):
    """Valeur de "count" (ou du [n] du type), ou None."""
    c = fdef.get("count")
    if c is None:
        c = _parse_type(fdef.get("type"))[1]
    return None if c is None else int(c)


def _count(fdef):
    """Nombre d'éléments d'un tableau, None si ce n'est pas un tableau.

    Pour des octets bruts (raw / hex), "count" est le NOMBRE D'OCTETS, pas un
    tableau : voir _bytes_length.
    """
    if _type(fdef) == "hex":
        return None
    c = _raw_count(fdef)
    return c if c is not None and c > 1 else None


def _bytes_length(fdef):
    """Nombre d'octets d'un champ raw / hex / ascii : "length", sinon "count" (raw), sinon None (variable)."""
    if fdef.get("length") is not None:
        return int(fdef["length"])
    if _type(fdef) == "hex":
        return _raw_count(fdef)
    return None


def _num(fdef, key, default):
    """Valeur numérique d'une clé ; absente ou null -> `default`."""
    v = fdef.get(key)
    return default if v is None else float(v)


def _is_enum(fdef):
    """Liste de choix : type "enum", ou entier avec "choices" (ex. uint8 + choices)."""
    return _type(fdef) == "enum" or (bool(_int_spec(_type(fdef))) and bool(fdef.get("choices")))


# Noms publics, utilisés par l'interface
field_type = _type          # type normalisé
array_count = _count        # taille du tableau, ou None
is_choice = _is_enum        # champ à liste de choix


def _enum_spec(fdef):
    """(taille, signé, ordre) de l'entier qui porte un choix."""
    t = _type(fdef)
    return _int_spec(_parse_type(fdef.get("size") or "u8")[0] if t == "enum" else t)


def _int_spec(t):
    """'u16be' -> (2, False, 'big') ; 'u16' -> (2, False, None) ; autre -> None.

    None comme ordre = utiliser le réglage du protocole.
    """
    t = t.lower()
    for suffix, order in (("be", "big"), ("le", "little")):
        if t.endswith(suffix) and t[:-2] in INTS:
            size, signed = INTS[t[:-2]]
            return size, signed, order
    if t in INTS:
        size, signed = INTS[t]
        return size, signed, None
    return None


def _scalar_size(fdef):
    """Taille d'UN élément (sans tenir compte de "count"), None si variable."""
    t = _type(fdef)
    spec = _int_spec(t)
    if spec:
        return spec[0]
    if t == "f32":
        return 4
    if t == "bool":
        return 1
    if t == "enum":
        return _enum_spec(fdef)[0]
    if t in ("ascii", "hex"):
        return _bytes_length(fdef)
    if t == "bcd":                      # BCD : 2 chiffres par octet, "length" octets (4 par défaut)
        return bcd_length(fdef)
    raise ValueError(f"type inconnu '{t}'")


def field_size(fdef):
    """Taille d'un champ en octets (tableau compris), ou None si elle est variable."""
    size = _scalar_size(fdef)
    count = _count(fdef)
    return size * count if (count and size) else size


def bcd_length(fdef):
    """Nombre d'octets d'un champ BCD : "length", 4 par défaut (8 chiffres, numéro M-Bus)."""
    return int(fdef.get("length") or 4)


def _order(spec_order, cfg):
    """Ordre des octets d'un champ : celui du type s'il est précisé, sinon celui du protocole."""
    return spec_order or cfg.byte_order


def type_label(fdef):
    """Type lisible pour l'aide : 'uint8[4] ip', 'float', 'uint32[2] bits'."""
    text = str(fdef.get("type") or "u8").split("[")[0]
    if _count(fdef):
        text += f"[{_count(fdef)}]"
    elif _type(fdef) in ("hex", "ascii") and _bytes_length(fdef):
        text += f"[{_bytes_length(fdef)}]"
    elif _type(fdef) == "bcd":
        text += f"[{bcd_length(fdef)}]"
    if fdef.get("format"):
        text += f" {fdef['format']}"
    if fdef.get("bits"):
        text += " bits"
    return text


