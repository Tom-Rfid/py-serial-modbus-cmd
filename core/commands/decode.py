"""
core/commands/decode.py — Décodage : octets de DATA -> champs avec valeur physique, contrôle des plages, champs de bits.
"""
import struct
from dataclasses import dataclass
from typing import Optional

from ..frames import parse_int, to_hex
from ..protocol import ProtocolConfig
from .types import _count, _enum_spec, _int_spec, _is_enum, _order, _type, field_size
from .physical import _factor, _offset, format_physical

@dataclass
class DataField:
    """Un champ de DATA décodé."""
    name: str                       # libellé du champ
    start: int                      # position du premier octet DANS LA TRAME
    raw: bytes                      # octets du champ
    text: str = ""                  # valeur affichée : '12.5 mW', 'on (1)', '192.168.1.10'
    raw_value: Optional[int] = None # valeur brute entière (si numérique)
    ok: Optional[bool] = None       # False si hors min / max ou tronqué
    note: str = ""

    @property
    def span(self):
        end = self.start + len(self.raw) - 1
        return str(self.start) if end <= self.start else f"{self.start}-{end}"


def _decode_scalar(fdef, raw, cfg):
    """Octets d'UN élément -> (texte, valeur brute, valeur physique ou None)."""
    t = _type(fdef)
    if t == "bool":
        return ("1 (vrai)" if raw[0] else "0 (faux)"), raw[0], None
    if _is_enum(fdef):
        size, signed, order = _enum_spec(fdef)
        v = int.from_bytes(raw, _order(order, cfg), signed=signed)
        label = next((k for k, x in fdef["choices"].items() if parse_int(x) == v), None)
        return (f"{label} ({v})" if label is not None else f"{v} (inconnu)"), v, None
    if t == "ascii":
        return repr(raw.rstrip(b"\x00").decode("latin-1")), None, None
    if t == "hex":
        return to_hex(raw), None, None
    if t == "bcd":
        return _decode_bcd(fdef, raw, cfg)
    if t == "f32":
        rawf = struct.unpack("<f" if cfg.byte_order == "little" else ">f", raw)[0]
        phys = rawf * _factor(fdef) + _offset(fdef)
        return format_physical(fdef, phys), None, phys
    size, signed, order = _int_spec(t)
    v = int.from_bytes(raw, _order(order, cfg), signed=signed)
    phys = v * _factor(fdef) + _offset(fdef)
    return format_physical(fdef, phys), v, phys


def _decode_bcd(fdef, raw, cfg):
    """BCD -> (texte, valeur brute, valeur physique) ; un chiffre > 9 rend la valeur invalide."""
    ordered = bytes(raw) if _order(None, cfg) == "big" else bytes(raw)[::-1]
    digits = ordered.hex().upper()
    if not digits.isdigit():
        return f"{digits} (BCD invalide)", None, None
    v = int(digits)
    phys = v * _factor(fdef) + _offset(fdef)
    return format_physical(fdef, phys), v, phys


def bits_text(fdef, value, nbytes):
    """Champ de bits -> '0x... : nom du bit 0, nom du bit 5' (ou 'aucun').

    "bits" : {"0": "Internal error", "32": "..."} ; un bit à 1 sans nom est
    affiché « bit N ».
    """
    names = {parse_int(k): v for k, v in fdef["bits"].items()}
    active = [names.get(b, f"bit {b}") for b in range(nbytes * 8) if value >> b & 1]
    return f"0x{value:0{nbytes * 2}X} : " + (", ".join(active) if active else "aucun")


def decode_field(fdef, raw, cfg=ProtocolConfig()):
    """Octets d'un champ (tableau compris) -> (texte affiché, valeur brute, valeur physique ou None)."""
    count = _count(fdef)
    if not count:
        if fdef.get("bits"):
            size, signed, order = _int_spec(_type(fdef))
            v = int.from_bytes(raw, _order(order, cfg))
            return bits_text(fdef, v, len(raw)), v, None
        return _decode_scalar(fdef, raw, cfg)

    size = len(raw) // count
    parts = [_decode_scalar(fdef, raw[i * size:(i + 1) * size], cfg) for i in range(count)]

    if fdef.get("bits"):
        # Tableau de mots formant un seul champ de bits : mot 0 = bits 0..31, mot 1 = bits 32..63...
        total = sum(p[1] << (8 * size * i) for i, p in enumerate(parts))
        return bits_text(fdef, total, len(raw)), total, None
    fmt = fdef.get("format")
    if fmt == "ip":
        return ".".join(str(p[1]) for p in parts), None, None
    if fmt == "mac":
        return ":".join(f"{p[1]:02X}" for p in parts), None, None
    if parts[0][2] is not None:
        # Nombres : valeurs sans unité, puis l'unité une seule fois
        values = ", ".join(format_physical(fdef, p[2], with_unit=False) for p in parts)
        return f"[{values}] {fdef.get('unit') or ''}".strip(), None, None
    return "[" + ", ".join(p[0] for p in parts) + "]", None, None


def decode_fields(defs, data, cfg=ProtocolConfig(), base=0):
    """Découpe les octets `data` selon les champs `defs`.

    base : position de DATA dans la trame (pour afficher des positions absolues).
    Retourne (champs, erreurs) ; ne lève jamais d'erreur.
    """
    fields, errors = [], []
    pos = 0
    for fdef in defs:
        label = fdef.get("label") or fdef["name"]
        size = field_size(fdef)
        if size is None:                        # taille variable : prend le reste
            size = len(data) - pos
        raw = data[pos:pos + size]
        if len(raw) < size:
            fields.append(DataField(label, base + pos, raw, ok=False, note=f"tronqué ({len(raw)}/{size} o)"))
            errors.append(f"DATA trop courte pour '{label}'")
            return fields, errors
        text, raw_value, phys = decode_field(fdef, raw, cfg)
        f = DataField(label, base + pos, raw, text, raw_value)
        if phys is not None and ((fdef.get("min") is not None and phys < float(fdef["min"]))
                                 or (fdef.get("max") is not None and phys > float(fdef["max"]))):
            f.ok, f.note = False, f"hors plage [{fdef.get('min', '…')} – {fdef.get('max', '…')}]"
        if fdef.get("bits") and raw_value:
            f.ok = False                        # au moins un bit (erreur) actif
        if raw_value is not None and not fdef.get("bits") and not _is_enum(fdef) and (
                _factor(fdef) != 1 or _offset(fdef) != 0):
            f.note = f.note or f"brut {raw_value}"
        fields.append(f)
        pos += size
    if pos < len(data):
        rest = data[pos:]
        fields.append(DataField("(non décrit)", base + pos, rest, to_hex(rest), ok=False))
        errors.append(f"{len(rest)} octet(s) de DATA non décrits")
    return fields, errors


