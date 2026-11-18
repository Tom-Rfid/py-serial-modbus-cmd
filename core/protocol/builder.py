"""
core/protocol/builder.py — Construction d'une trame à partir de la description du protocole.

    build_frame(protocol, layout, data, {"request_id": 5, "command_id": 4})

layout : liste des champs de la variante de trame à construire (Protocol.layout()).

Étapes :
    1. chaque champ présent est écrit dans l'ordre, à la position courante (comptée en
       bits) : valeur fixe, longueur calculée, valeur fournie, données, octets non lus,
       place réservée pour les CRC
    2. les CRC sont calculés en dernier, sur la trame déjà écrite
"""
from .bits import covered_bytes, is_byte_aligned, write_bits
from .fields import crc_range


def build_frame(protocol, layout, data=b"", values=None):
    """Trame complète. Lève ValueError si une valeur ne tient pas dans son champ."""
    values = dict(values or {})
    data = bytes(data)
    ctx = _Context(protocol, layout, data, values)
    out = bytearray()
    cursor = 0                          # position courante, en bits
    placed = {}                         # nom -> (premier octet, nombre d'octets) des champs écrits
    crc_specs = []
    for spec in layout:
        if not spec.present or not _condition_met(ctx, spec):
            continue
        bits = 8 * len(data) if spec.role == "data" else spec.bits
        if spec.role == "data":
            _check_data_size(spec, data)
        _grow(out, cursor + bits)
        _write_field(ctx, spec, out, cursor, bits)
        placed[spec.name] = covered_bytes(cursor, bits)
        if spec.role == "crc":
            crc_specs.append(spec)
        cursor += bits
    _write_crcs(protocol, out, crc_specs, placed)
    return bytes(out)


class _Context:
    """Ce qu'il faut pour écrire une trame : protocole, champs de la variante, données,
    valeurs fournies, et valeurs déjà écrites (pour les champs « copy »)."""

    def __init__(self, protocol, layout, data, values):
        self.protocol, self.layout, self.data, self.values = protocol, layout, data, values
        self.by_name = {f.name: f for f in layout}
        self.written = {}


def _grow(out, bits):
    """Agrandit le tampon pour contenir `bits` bits."""
    needed = (bits + 7) // 8
    if len(out) < needed:
        out.extend(bytes(needed - len(out)))


def _check_data_size(spec, data):
    if spec.bits is not None and 8 * len(data) != spec.bits:
        raise ValueError(f"{spec.name} : {spec.bits // 8} octet(s) attendus, {len(data)} fournis")


def _write_field(ctx, spec, out, cursor, bits):
    """Écrit un champ à la position `cursor` (un CRC reste à zéro, calculé ensuite)."""
    protocol = ctx.protocol
    start = cursor // 8
    if spec.role == "data":
        out[start:start + len(ctx.data)] = ctx.data
    elif spec.role == "crc":
        return
    elif spec.role == "na":
        _write_na(spec, out, cursor, bits, protocol.bit_order)
    else:
        value = _numeric_value(ctx, spec)
        ctx.written[spec.name] = value
        maximum = (1 << bits) - 1
        if not 0 <= value <= maximum:
            raise ValueError(f"{spec.name} : {value} hors limites (0 à {maximum})")
        if is_byte_aligned(cursor, bits):
            out[start:start + bits // 8] = protocol.pack(value, bits // 8, spec.order)
        else:
            write_bits(out, cursor, bits, value, protocol.bit_order)


def _write_na(spec, out, cursor, bits, bit_order):
    """Octets non lus : "fill" ; en bits, fill 0 -> bits à 0, autre valeur -> bits à 1."""
    if is_byte_aligned(cursor, bits):
        start = cursor // 8
        out[start:start + bits // 8] = bytes([spec.fill]) * (bits // 8)
    else:
        write_bits(out, cursor, bits, (1 << bits) - 1 if spec.fill else 0, bit_order)


def _numeric_value(ctx, spec):
    """Valeur d'un champ numérique : fixe, calculée, recopiée, fournie (par rôle ou par nom), ou par défaut."""
    if spec.role == "value":
        return spec.value
    if spec.role == "length":
        return length_of(ctx, spec)
    if spec.role == "copy":
        return ctx.written.get(spec.same_as, 0)
    default = spec.default if spec.role == "field" else 0
    return int(ctx.values.get(spec.role, ctx.values.get(spec.name, default)))


def _write_crcs(protocol, out, crc_specs, placed):
    for spec in crc_specs:
        start, size = placed[spec.name]
        a, b = crc_range(spec, placed, start)
        value = spec.algo.compute(out[a:b])
        out[start:start + size] = value.to_bytes(size, spec.order or protocol.byte_order)


def length_of(ctx, spec):
    """Valeur d'un champ longueur : somme des tailles des champs comptés ("of"), en octets."""
    return sum(_bits_in_frame(ctx, name) for name in spec.of) // 8


def _bits_in_frame(ctx, name):
    """Taille d'un champ dans la trame construite, en bits (0 s'il est absent)."""
    spec = ctx.by_name[name]
    if not spec.present or not _condition_met(ctx, spec):
        return 0
    return 8 * len(ctx.data) if spec.role == "data" else spec.bits


def _condition_met(ctx, spec):
    """Condition "if" du champ (vraie s'il n'y en a pas)."""
    if not spec.cond:
        return True
    target = ctx.by_name[spec.cond]
    if not target.present:
        return False
    if target.role == "data":
        return bool(ctx.data)
    if target.role == "length":
        return length_of(ctx, target) > 0
    if target.role in ("value", "crc", "na", "copy"):
        return True
    return bool(ctx.values.get(target.role, ctx.values.get(target.name, target.default)))
