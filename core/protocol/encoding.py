"""
core/protocol/encoding.py — Codage de la trame sur la ligne (clé "encoding" du fichier).

Par défaut la trame est envoyée telle quelle (binaire). Avec

    "encoding": {"type": "ascii_hex", "start": ":", "end": "\\r\\n"}

chaque octet de la trame est écrit en deux caractères hexa ASCII, entre un caractère
de début et une fin de ligne : c'est Modbus ASCII. La trame 01 03 00 00 00 0A F2 part
sous la forme « :01030000000AF2\\r\\n ». Les champs, longueurs et CRC (LRC) portent sur
la trame binaire ; seul le transport change.
"""
import binascii

from .common import ProtocolError


class AsciiHex:
    def __init__(self, start=":", end="\r\n", lowercase=False):
        self.start = start.encode("latin-1")
        self.end = end.encode("latin-1")
        self.lowercase = bool(lowercase)

    def wrap(self, binary):
        """Trame binaire -> octets envoyés (début + hexa ASCII + fin)."""
        text = binascii.hexlify(bytes(binary)).decode("ascii")
        text = text.lower() if self.lowercase else text.upper()
        return self.start + text.encode("ascii") + self.end

    def unwrap(self, raw):
        """Octets reçus -> (trame binaire, problèmes, fin trouvée, octets après la fin)."""
        raw = bytes(raw)
        problems = []
        if not raw.startswith(self.start):
            return b"", [f"début de trame {_show(self.start)} absent"], False, b""
        body = raw[len(self.start):]
        index = body.find(self.end) if self.end else -1
        complete = index >= 0 or not self.end
        hex_part = body[:index] if index >= 0 else body
        extra = body[index + len(self.end):] if index >= 0 else b""
        if not complete:
            problems.append(f"fin de trame {_show(self.end)} absente")
        binary, bad = _hex_prefix(hex_part)
        if bad:
            problems.append("caractères hexa ASCII invalides")
        return binary, problems, complete, extra

    def prefix(self, raw):
        """Début d'une trame reçue -> (bon début ?, octets binaires déjà lisibles)."""
        raw = bytes(raw)
        if not raw.startswith(self.start):
            return self.start.startswith(raw), b""
        binary, _ = _hex_prefix(raw[len(self.start):])
        return True, binary

    def raw_segments(self, segments, binary_length):
        """Couleurs de la trame binaire -> couleurs des octets envoyés (2 caractères par octet)."""
        offset = len(self.start)
        out = [(0, offset, "hdr")] if offset else []
        out += [(offset + 2 * start, 2 * length, tag) for start, length, tag in segments]
        if self.end:
            out.append((offset + 2 * binary_length, len(self.end), "hdr"))
        return out


def _hex_prefix(text):
    """Le plus long début de `text` fait de paires de caractères hexa -> (octets, reste invalide ?)."""
    out = bytearray()
    for i in range(0, len(text) - 1, 2):
        try:
            out.append(int(text[i:i + 2].decode("ascii"), 16))
        except (ValueError, UnicodeDecodeError):
            return bytes(out), True
    return bytes(out), len(text) % 2 == 1


def _show(delimiter):
    """Délimiteur lisible : ':' , '\\r\\n'."""
    return repr(delimiter.decode("latin-1"))


def parse_encoding(conf):
    """Section "encoding" du fichier -> codage, ou None (binaire)."""
    spec = conf.get("encoding")
    if spec is None or spec == "binary" or (isinstance(spec, dict) and spec.get("type", "binary") == "binary"):
        return None
    if isinstance(spec, str):
        spec = {"type": spec}
    if not isinstance(spec, dict) or spec.get("type") != "ascii_hex":
        raise ProtocolError("encoding : type inconnu (binary ou ascii_hex)")
    return AsciiHex(str(spec.get("start", ":")), str(spec.get("end", "\r\n")), spec.get("lowercase", False))
