"""
core/commands/encode.py — Encodage : valeurs saisies (unité physique) -> octets de DATA.
"""
import re
import struct

from ..frames import TRUTHY, parse_hex, parse_int
from ..protocol import ProtocolConfig
from .types import _bytes_length, _count, _enum_spec, _int_spec, _is_enum, _order, _type, bcd_length, type_label
from .physical import _factor, _offset, effective_range, format_physical, parse_number, type_range

def _encode_scalar(fdef, value, cfg):
    """Encode UN élément (valeur physique) en octets. Lève ValueError si invalide."""
    t = _type(fdef)
    if t == "bool":
        return bytes([1 if str(value).lower() in TRUTHY else 0])

    if _is_enum(fdef):
        choices = fdef["choices"]
        raw = parse_int(choices[value]) if value in choices else parse_int(value)     # "0xFF00" accepté
        size, signed, order = _enum_spec(fdef)
        return raw.to_bytes(size, _order(order, cfg), signed=signed)

    if t == "ascii":
        b = str(value).encode("latin-1")
        n = fdef.get("length")
        return b[:n].ljust(n, b"\x00") if n else b

    if t == "hex":                      # octets bruts (raw / hex), sans conversion
        b = parse_hex(value)
        n = _bytes_length(fdef)
        if n and len(b) != n:
            raise ValueError(f"{n} octet(s) attendu(s), {len(b)} saisi(s)")
        return b

    # Nombres : contrôle des bornes en unité physique, puis conversion en brut
    v = parse_number(value)
    if fdef.get("min") is not None and v < float(fdef["min"]):
        raise ValueError(f"{v:g} < min ({fdef['min']})")
    if fdef.get("max") is not None and v > float(fdef["max"]):
        raise ValueError(f"{v:g} > max ({fdef['max']})")
    raw = (v - _offset(fdef)) / _factor(fdef)

    if t == "f32":
        return struct.pack("<f" if cfg.byte_order == "little" else ">f", raw)
    if t == "bcd":
        return _encode_bcd(fdef, int(round(raw)), v, cfg)

    spec = _int_spec(t)
    if not spec:
        raise ValueError(f"type inconnu '{t}'")
    size, signed, order = spec
    raw = int(round(raw))
    lo, hi = (-(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1) if signed else (0, (1 << (8 * size)) - 1)
    if not lo <= raw <= hi:
        # Limites du type exprimées en unité physique, plus parlantes que le brut
        tlo, thi = type_range(fdef)
        raise ValueError(f"{v:g} hors limites du type {type_label(fdef)} "
                         f"({format_physical(fdef, tlo)} à {format_physical(fdef, thi)})")
    return raw.to_bytes(size, _order(order, cfg), signed=signed)


def split_items(fdef, value):
    """Découpe la saisie d'un tableau en éléments.

    format "ip"  : 192.168.1.10           (séparateur point)
    format "mac" : 00:1A:2B:3C:4D:5E      (hexa, séparateur : ou -)
    sinon        : 1, 2, 3  ou  1 2 3  ou  1;2;3
    """
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    text = str(value).strip()
    fmt = fdef.get("format")
    if fmt == "ip":
        return [x.strip() for x in text.split(".")]
    if fmt == "mac":
        return ["0x" + x for x in re.split(r"[:\-\s]+", text) if x]
    return [x for x in re.split(r"[,;\s]+", text) if x]


def _encode_bcd(fdef, raw, value, cfg):
    """Entier -> BCD sur "length" octets (12345678 -> 12 34 56 78 en big endian,
    78 56 34 12 en little endian comme en M-Bus)."""
    n = bcd_length(fdef)
    if not 0 <= raw < 10 ** (2 * n):
        raise ValueError(f"{value:g} hors limites du type {type_label(fdef)} (0 à {10 ** (2 * n) - 1})")
    digits = f"{raw:0{2 * n}d}"
    out = bytes(int(digits[i:i + 2], 16) for i in range(0, 2 * n, 2))      # « 12 » -> 0x12
    return out if _order(None, cfg) == "big" else out[::-1]


def encode_field(fdef, value, cfg=ProtocolConfig()):
    """Encode la valeur PHYSIQUE `value` d'un champ (tableau compris). Lève ValueError si invalide."""
    name = fdef.get("label") or fdef["name"]
    try:
        count = _count(fdef)
        if not count:
            return _encode_scalar(fdef, value, cfg)
        items = split_items(fdef, value)
        if len(items) != count:
            raise ValueError(f"{count} valeurs attendues, {len(items)} saisie(s)")
        return b"".join(_encode_scalar(fdef, item, cfg) for item in items)
    except (ValueError, KeyError, UnicodeEncodeError, struct.error, OverflowError) as e:
        raise ValueError(f"{name} : {e}") from None


def defaults(defs):
    """Valeurs par défaut (physiques) de chaque champ : {nom: valeur}."""
    out = {}
    for f in defs:
        count = _count(f)
        if f.get("default") is not None:
            out[f["name"]] = f["default"]
        elif _is_enum(f):
            first = next(iter(f["choices"]))
            out[f["name"]] = ", ".join([first] * count) if count else first
        elif _type(f) == "hex" and _bytes_length(f):
            out[f["name"]] = " ".join(["00"] * _bytes_length(f))     # raw de taille fixe : des 00
        elif _type(f) in ("ascii", "hex"):
            out[f["name"]] = ""
        elif count:
            # Tableau : n zéros, écrits au format du champ
            sep = {"ip": ".", "mac": ":"}.get(f.get("format"), ", ")
            zero = "00" if f.get("format") == "mac" else "0"
            out[f["name"]] = sep.join([zero] * count)
        else:
            # Pas de défaut : 0, ramené dans la plage si 0 n'y est pas
            lo, hi, _, _ = effective_range(f)
            v = 0
            if lo is not None and v < lo:
                v = lo
            if hi is not None and v > hi:
                v = hi
            out[f["name"]] = v
    return out


def encode_fields(defs, values, cfg=ProtocolConfig()):
    """Encode tous les champs, dans l'ordre de `defs`, en octets DATA.

    Les valeurs absentes de `values` prennent leur valeur par défaut.
    """
    vals = {**defaults(defs), **values}
    return b"".join(encode_field(f, vals[f["name"]], cfg) for f in defs)


