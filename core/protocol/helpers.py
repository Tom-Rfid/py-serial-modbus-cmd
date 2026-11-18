"""
core/protocol/helpers.py — Fonctions raccourcies et compatibilité.

    build_query / build_response / decode : protocole par défaut (générique intégré),
        ou celui passé en dernier argument
    summary(decoded)        : résumé d'une ligne
    color_segments(decoded) : couleurs des champs pour l'affichage
    ProtocolConfig          : ordre des octets seul (anciens scripts, core.commands)
"""
from dataclasses import dataclass

from .crc import crc16_modbus
from .protocol import Protocol
from .default import DEFAULT_PROTOCOL


@dataclass
class ProtocolConfig:
    """Ordre des octets seul (compatibilité : utilisé par core.commands et les anciens scripts).

    Par défaut big endian (octet de poids fort en premier, « ordre réseau »), CRC compris.
    """
    byte_order: str = "big"
    crc_order: str = "big"

    def pack(self, value, size, order=None):
        return value.to_bytes(size, order or self.byte_order)

    def unpack(self, raw, order=None):
        return int.from_bytes(raw, order or self.byte_order)

    def crc_bytes(self, data):
        return crc16_modbus(data).to_bytes(2, self.crc_order)


def _protocol(p):
    return p if isinstance(p, Protocol) else DEFAULT_PROTOCOL


def build_query(request_id, command_id, data=b"", protocol=None):
    return _protocol(protocol).build_query(request_id, command_id, data)


def build_response(request_id, error=0, data=b"", protocol=None):
    return _protocol(protocol).build_response(request_id, error, data)


def decode(frame, kind, protocol=None):
    return _protocol(protocol).decode(frame, kind)


def color_segments(d):
    """Couleurs d'une trame décodée : [(début, longueur, tag)].

    Tag : couleur du fichier de conf (hdr, cmd, crc, na) ; "err" pour un octet fixe ou un
    CRC faux ; "perr_ok" / "perr_ko" pour le code d'erreur à 0 / non nul. Rien tant que
    la trame n'est pas complète. (Même fonction dans js/src/core/protocol/colors.ts.)
    """
    if not d.complete:
        return []
    out = []
    for f in d.fields:
        tag = _tag(f)
        if f.raw and tag:
            out.append((f.start, len(f.raw), tag))
    return out


def _tag(f):
    if f.role == "error":
        return "perr_ok" if f.value == 0 else "perr_ko"
    if f.ok is False:
        return "err"
    return f.color


def summary(d):
    """Résumé d'une ligne. Ex. « réponse #5 · erreur 0 · 3 o · CRC OK »."""
    parts = [d.kind + request_id_text(d)]
    cid = d.by_role("command_id")
    if cid is not None:
        parts.append(f"cmd 0x{cid.value:0{cid.hex_digits}X}")
    if d.error is not None:
        parts.append(f"erreur {d.error}")
    parts.extend(data_and_status(d))
    return " · ".join(parts)


def request_id_text(d):
    """« #0x05 » : REQUEST ID en hexa sur la taille du champ, ou '' s'il n'y en a pas."""
    rid = d.by_role("request_id")
    return f" #0x{rid.value:0{rid.hex_digits}X}" if rid is not None else ""


def data_and_status(d):
    """Fin commune des résumés : taille des données, puis « CRC OK » ou les problèmes."""
    return [text for text, _ in status_parts(d)]


def status_parts(d):
    """Comme data_and_status, avec pour chaque morceau ok = False s'il signale un problème
    (affiché en rouge dans le moniteur) : [("4 o", True), ("HCRC incorrect", False)]."""
    parts = []
    data = d.by_role("data")
    if data is not None or d.length is not None:
        parts.append((f"{len(data.raw) if data else 0} o", True))
    if d.ok:
        parts.append(("CRC OK" if d.crc_ok else "OK", True))
    else:
        problems = list(d.errors)
        if d.complete and d.extra:
            problems.append(f"{len(d.extra)} octet(s) en trop")
        parts.append((", ".join(problems), False))
    return parts
