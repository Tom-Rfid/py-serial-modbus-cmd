"""
core/protocol/bits.py — Lecture et écriture de champs qui ne tombent pas sur des octets entiers.

Les bits de la trame sont numérotés à partir de 0, octet par octet. "bit_order" du
protocole dit dans quel sens on lit un octet :

    "msb" (défaut) : bit 0 = bit de poids FORT de l'octet 0 (comme les schémas de
                     spécification : « bits 0-2 : version, bits 3-7 : type »)
    "lsb"          : bit 0 = bit de poids FAIBLE de l'octet 0

Un champ de n bits est lu comme une suite de bits : en "msb", le premier bit lu est le
poids fort de la valeur ; en "lsb", le premier bit lu est le poids faible.
Les champs qui commencent et finissent sur des octets entiers sont lus octet par octet,
avec l'ordre des octets (byte_order / order) : ce module ne sert pas pour eux.
"""


def bit_at(frame, k, bit_order):
    """Valeur (0 ou 1) du bit numéro k de la trame."""
    byte = frame[k // 8]
    shift = 7 - k % 8 if bit_order == "msb" else k % 8
    return (byte >> shift) & 1


def read_bits(frame, start, count, bit_order):
    """Entier formé des bits start .. start+count-1."""
    value = 0
    for i in range(count):
        bit = bit_at(frame, start + i, bit_order)
        if bit_order == "msb":
            value = (value << 1) | bit
        else:
            value |= bit << i
    return value


def write_bits(buffer, start, count, value, bit_order):
    """Écrit `value` sur les bits start .. start+count-1 de `buffer` (bytearray assez long)."""
    for i in range(count):
        bit = (value >> (count - 1 - i)) & 1 if bit_order == "msb" else (value >> i) & 1
        k = start + i
        shift = 7 - k % 8 if bit_order == "msb" else k % 8
        if bit:
            buffer[k // 8] |= 1 << shift
        else:
            buffer[k // 8] &= ~(1 << shift) & 0xFF


def covered_bytes(start, count):
    """(premier octet, nombre d'octets) touchés par les bits start .. start+count-1."""
    first = start // 8
    last = (start + count - 1) // 8 if count else first - 1
    return first, last - first + 1


def is_byte_aligned(start, count):
    """True si le champ commence et finit sur des octets entiers."""
    return start % 8 == 0 and count % 8 == 0
