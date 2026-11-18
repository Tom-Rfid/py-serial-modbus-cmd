"""
core/protocol/decoder.py — Décodage d'une trame selon la description du protocole.

    decode_frame(protocol, layout, RESPONSE, octets) -> Decoded

layout : liste des champs de la variante de trame (Protocol.decode choisit la variante).

La position courante est comptée en bits (champs « LENb » / « atb »). Ne lève jamais
d'erreur : une trame tronquée ou invalide est décodée autant que possible, et les
problèmes sont listés dans Decoded.errors. Les CRC sont vérifiés une fois tous les
champs découpés.
"""
from ..frames import to_hex

from .bits import covered_bytes, is_byte_aligned, read_bits
from .decoded import Decoded, Field
from .fields import crc_range, value_text


def decode_frame(protocol, layout, kind, frame):
    frame = bytes(frame)
    d = Decoded(kind)
    cursor = 0                                          # position courante, en bits
    placed = {}
    crcs = []
    for i, spec in enumerate(layout):
        if not spec.present or (spec.cond and not _present(spec.cond, d)):
            continue
        bits = 8 * data_size(spec, i, layout, d, frame, cursor // 8) if spec.role == "data" else spec.bits
        if spec.role == "data" and bits == 0:
            continue                                    # pas de données : DATA absente
        start, size = covered_bytes(cursor, bits)
        if start + size > len(frame):
            _truncated(d, spec, start, frame[start:start + size], size)
            return d
        field = _decode_field(protocol, spec, frame, cursor, bits, d)
        if spec.role == "crc":
            crcs.append((spec, field))
        d.fields.append(field)
        placed[spec.name] = (start, size)
        cursor += bits
    _check_crcs(protocol, frame, crcs, placed, d)
    d.complete = True
    d.extra = frame[(cursor + 7) // 8:]
    return d


def _decode_field(protocol, spec, frame, cursor, bits, d):
    """Un champ complet : valeur numérique, contrôle d'une valeur fixe, note."""
    start, size = covered_bytes(cursor, bits)
    field = Field(spec.name, start, frame[start:start + size], role=spec.role, color=spec.color,
                  bit_start=cursor, bits=bits)
    if spec.role == "data":
        field.note = f"{size} octets"
    elif spec.role == "na":
        field.note = "non lu"
    elif spec.role != "crc":
        field.value = _value(protocol, spec, frame, cursor, bits)
        if spec.role == "value":
            _check_fixed(protocol, spec, field, d)
        elif spec.role == "copy":
            _check_copy(spec, field, d)
        field.meaning = value_text(spec.values, field.value, protocol.language)
    field.description = spec.description_en if protocol.language == "en" and spec.description_en else spec.description
    return field


def _check_copy(spec, field, d):
    """Un champ recopié doit valoir le champ d'origine (ex. longueur répétée)."""
    expected = d.get(spec.same_as)
    field.ok = field.value == expected
    if not field.ok:
        field.note = f"attendu {expected} (comme {spec.same_as})"
        d.errors.append(f"{spec.name} différent de {spec.same_as}")


def _value(protocol, spec, frame, cursor, bits):
    """Valeur : octet par octet (ordre des octets) si le champ est aligné, sinon bit par bit."""
    if is_byte_aligned(cursor, bits):
        start = cursor // 8
        return protocol.unpack(frame[start:start + bits // 8], spec.order)
    return read_bits(frame, cursor, bits, protocol.bit_order)


def _check_fixed(protocol, spec, field, d):
    field.ok = field.value == spec.value
    if field.ok:
        return
    if spec.bits % 8 == 0:
        field.note = f"attendu {to_hex(protocol.pack(spec.value, spec.bits // 8, spec.order))}"
    else:
        field.note = f"attendu 0b{spec.value:0{spec.bits}b}"
    d.errors.append(f"{spec.name} différent de 0x{spec.value:0{(spec.bits + 3) // 4}X}")


def _truncated(d, spec, start, raw, size):
    if spec.role == "data":
        d.fields.append(Field(spec.name, start, raw, role="data", color=spec.color,
                              note=f"{len(raw)}/{size} octets"))
        d.errors.append(f"données tronquées : {len(raw)} octets sur {size}")
    else:
        d.errors.append(f"trame tronquée : {spec.name} incomplet")


def _check_crcs(protocol, frame, crcs, placed, d):
    for spec, field in crcs:
        a, b = crc_range(spec, placed, field.start)
        expected = spec.algo.compute(frame[a:b]).to_bytes(spec.size, spec.order or protocol.byte_order)
        field.ok = field.raw == expected
        if not field.ok:
            field.note = f"attendu {to_hex(expected)}"
            d.errors.append(f"{spec.name} incorrect")


def _present(name, d):
    """Condition "if" au décodage : le champ nommé a été lu et n'est pas vide / nul."""
    f = next((x for x in d.fields if x.name == name), None)
    if f is None:
        return False
    if f.role == "data":
        return bool(f.raw)
    if f.value is not None and f.role != "value":
        return f.value != 0
    return True


def data_size(spec, i, layout, d, frame, pos):
    """Taille de DATA en octets : d'après le champ longueur, fixe, ou le reste de la trame."""
    length = next((x for x in layout if x.role == "length" and x.present and spec.name in x.of), None)
    if length is not None:
        return _size_from_length(spec, length, layout, d)
    if spec.bits is not None:
        return spec.bits // 8
    return _remaining_size(spec, i, layout, frame, pos)


def _size_from_length(spec, length, layout, d):
    value = d.get(length.name)
    if value is None:
        return 0
    others = sum(x.bits or 0 for x in layout if x.name in length.of and x.name != spec.name) // 8
    return max(0, value - others)


def _remaining_size(spec, i, layout, frame, pos):
    """Le reste de la trame, moins les champs qui suivent (ceux qui dépendent de DATA à part)."""
    after = [x for x in layout[i + 1:] if x.bits]
    fixed = sum(x.bits for x in after if x.cond != spec.name) // 8
    conditional = sum(x.bits for x in after if x.cond == spec.name) // 8
    rest = len(frame) - pos - fixed
    return rest - conditional if rest > conditional else 0
