"""
core/commands/convert.py — DATA brute <-> valeurs saisissables, dans les deux sens.

Sert à l'onglet Manuel (messages de protocole) : on modifie DATA en hexa et les valeurs
converties suivent, ou on modifie une valeur et DATA est recalculée sur le bon nombre d'octets.

    split_data(defs, data, cfg)          -> [(champ, octets)], ou None si DATA ne correspond pas
    input_text(champ, octets, cfg, hexa) -> texte à afficher, relu tel quel par encode_field
    int_text(octets, order, hexa)        -> DATA lue comme un entier (sans définition de commande)
    int_bytes(texte, order, n)           -> entier saisi -> octets (au moins n octets)
    raw_guess(octets, order)             -> lectures possibles d'une DATA sans définition (RX)
"""
import math
import struct

from ..frames import parse_int, to_hex
from ..protocol import ProtocolConfig
from .decode import decode_field
from .physical import _factor, _offset, format_physical
from .types import _count, _int_spec, _is_enum, _order, _type, field_size


def split_data(defs, data, cfg=ProtocolConfig()):
    """Découpe DATA selon les champs : [(définition, octets)]. None si la longueur de DATA ne
    correspond pas exactement aux champs (trop courte, ou octets en trop)."""
    parts, pos = [], 0
    for fdef in defs:
        size = field_size(fdef)
        if size is None:                            # taille variable : le reste
            size = len(data) - pos
        raw = data[pos:pos + size]
        if len(raw) < size:
            return None
        parts.append((fdef, raw))
        pos += size
    return parts if pos == len(data) else None


def _plain_int(fdef):
    """Entier sans facteur, offset, liste de choix ni bits : affichable en hexa."""
    return (bool(_int_spec(_type(fdef))) and not _is_enum(fdef) and not fdef.get("bits")
            and _factor(fdef) == 1 and _offset(fdef) == 0)


plain_int = _plain_int          # nom public (interface : case Hexa active seulement pour ces champs)


def input_text(fdef, raw, cfg=ProtocolConfig(), hexa=False):
    """Octets d'un champ -> texte de saisie (relu par encode_field) : libellé du choix, nombre
    en unité réelle sans l'unité, texte, hexa… hexa=True : entier simple écrit 0x…, sur sa taille."""
    t = _type(fdef)
    count = _count(fdef)
    if not count:
        if t == "bool":
            return "1" if raw and raw[0] else "0"
        if _is_enum(fdef) or (_plain_int(fdef) and hexa) or fdef.get("bits"):
            size, signed, order = _int_spec(t) or (len(raw), False, None)
            v = int.from_bytes(raw, _order(order, cfg), signed=signed)
            if _is_enum(fdef):
                label = next((k for k, x in fdef["choices"].items() if parse_int(x) == v), None)
                if label is not None:
                    return label
            if hexa or fdef.get("bits"):
                return f"0x{v & ((1 << (8 * len(raw))) - 1):0{2 * len(raw)}X}"
            return str(v)
        if t == "ascii":
            return raw.rstrip(b"\x00").decode("latin-1")
        if t == "hex":
            return to_hex(raw)
    text, _raw, phys = decode_field(fdef, raw, cfg)
    if not count and phys is not None:
        return format_physical(fdef, phys, with_unit=False)
    if count and fdef.get("format") in ("ip", "mac"):
        return text
    if count:
        # « [1, 2] mm » -> « 1, 2 » ; tableau d'entiers simples en hexa si demandé
        size = len(raw) // count
        if hexa and _plain_int(fdef):
            items = [input_text(dict(fdef, count=None), raw[i * size:(i + 1) * size], cfg, True) for i in range(count)]
            return ", ".join(items)
        unit = fdef.get("unit") or ""
        inner = text.strip()
        if unit and inner.endswith(unit):
            inner = inner[:-len(unit)].strip()
        return inner.strip("[]")
    return text


def int_text(raw, order="little", hexa=False):
    """DATA lue comme un entier non signé (ordre du protocole) : '1500' ou '0x05DC'. '' si vide."""
    if not raw:
        return ""
    v = int.from_bytes(raw, order)
    return f"0x{v:0{2 * len(raw)}X}" if hexa else str(v)


def int_bytes(text, order="little", nbytes=0):
    """Entier saisi (décimal, 0x…, 0b…) -> octets, sur au moins `nbytes` octets (plus si la valeur
    ne tient pas). '' -> b''. Lève ValueError si la saisie n'est pas un entier positif."""
    text = str(text).strip()
    if not text:
        return b""
    v = parse_int(text)
    if v < 0:
        raise ValueError("valeur négative")
    need = max(1, (v.bit_length() + 7) // 8)
    return v.to_bytes(max(need, nbytes), order)


def raw_guess(raw, order="little"):
    """DATA sans définition (1 à 8 octets) -> lectures possibles, pour aider à l'interpréter :
    '1500 (0x05DC)', '… · signé -36' si le bit de poids fort est à 1, '… · float 75' pour 4 octets
    quand le flottant est vraisemblable. '' si vide ou plus de 8 octets."""
    if not raw or len(raw) > 8:
        return ""
    v = int.from_bytes(raw, order)
    parts = [f"{v} (0x{v:0{2 * len(raw)}X})"]
    s = int.from_bytes(raw, order, signed=True)
    if s != v:
        parts.append(f"signé {s}")
    if len(raw) == 4:
        f = struct.unpack("<f" if order == "little" else ">f", raw)[0]
        if math.isfinite(f) and (f == 0 or 1e-6 <= abs(f) < 1e9):
            parts.append(f"float {f:g}")
    return " · ".join(parts)
