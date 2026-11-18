"""
core/commands/physical.py — Valeurs physiques : facteur, offset, décimales, plages min / max (du JSON ou du type).
"""
from ..frames import parse_int
from .types import _int_spec, _is_enum, _num, _type, bcd_length

def _factor(fdef):
    return _num(fdef, "factor", 1.0)


def _offset(fdef):
    return _num(fdef, "offset", 0.0)


def decimals(fdef):
    """Nombre de décimales pour afficher la valeur physique.

    "decimals" dans le JSON s'il est donné, sinon déduit du facteur et de
    l'offset : factor 0.1 -> 1 décimale, factor 0.01 -> 2, factor 1 -> 0.
    """
    if fdef.get("decimals") is not None:
        return int(fdef["decimals"])
    n = 0
    for x in (_factor(fdef), _offset(fdef)):
        text = repr(float(x))
        if "e-" in text:                        # ex. 1e-05
            n = max(n, int(text.split("e-")[1]))
        elif "." in text and not text.endswith(".0"):
            n = max(n, len(text.split(".")[1]))
    return n


def parse_number(text):
    """Saisie -> nombre. Accepte 12, 0x0C, 0b1100, 12.5 et 12,5 (virgule française)."""
    try:
        return parse_int(text)
    except ValueError:
        try:
            return float(str(text).strip().replace(",", "."))
        except ValueError:
            raise ValueError(f"'{text}' n'est pas un nombre")


def format_physical(fdef, value, with_unit=True):
    """Valeur physique -> texte avec le bon nombre de décimales (et l'unité) : '12.5 mW'."""
    if _type(fdef) == "f32" and fdef.get("decimals") is None:
        text = f"{value:g}"             # flottant : précision naturelle (1.5, 0.001...)
    else:
        n = decimals(fdef)
        text = f"{value:.{n}f}" if n else str(int(round(value)))
    unit = (fdef.get("unit") or "") if with_unit else ""
    return f"{text} {unit}".strip()


def type_range(fdef):
    """Plage permise par le type, en unité PHYSIQUE (après facteur et offset).

    Ex. uint8 avec factor 0.1 -> (0.0, 25.5). None pour un flottant, un choix,
    un booléen, du texte ou de l'hexa.
    """
    if _type(fdef) == "bcd":
        lo, hi = 0, 10 ** (2 * bcd_length(fdef)) - 1
    else:
        spec = _int_spec(_type(fdef))
        if not spec or _is_enum(fdef) or fdef.get("bits"):
            return None
        size, signed = spec[0], spec[1]
        lo, hi = (-(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1) if signed else (0, (1 << (8 * size)) - 1)
    a, b = lo * _factor(fdef) + _offset(fdef), hi * _factor(fdef) + _offset(fdef)
    return min(a, b), max(a, b)         # un facteur négatif inverse l'ordre


def effective_range(fdef):
    """Plage réellement appliquée, en unité physique : (min, max, origine_min, origine_max).

    "min" / "max" du JSON s'ils sont renseignés, sinon les limites du type
    (calculées par type_range). Origine : "json", "type" ou None (pas de limite).
    """
    tr = type_range(fdef)
    lo = fdef.get("min")
    hi = fdef.get("max")
    lo_src, hi_src = ("json" if lo is not None else None), ("json" if hi is not None else None)
    if lo is None and tr:
        lo, lo_src = tr[0], "type"
    if hi is None and tr:
        hi, hi_src = tr[1], "type"
    return (None if lo is None else float(lo)), (None if hi is None else float(hi)), lo_src, hi_src


