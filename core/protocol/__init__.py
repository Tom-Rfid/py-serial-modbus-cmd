"""
core/protocol — Moteur de protocole configurable (trames requête / réponse).

La structure des trames n'est pas codée en dur : elle est décrite dans un fichier
de configuration JSON du dossier protocols/ (ex. protocols/modbus_rtu.json).
Toutes les options du fichier : docs/Francais/CONF_PROTOCOLE.md.

Organisation :
    common.py       QUERY, RESPONSE, ProtocolError
    crc.py          CRC 8 / 16 / 32 bits et sommes (Crc, CRC_PRESETS)
    fields.py       description d'un champ, vérifications du fichier
    decoded.py      résultat d'un décodage (Field, Decoded)
    builder.py      construction d'une trame
    decoder.py      décodage d'une trame
    protocol.py     classe Protocol (lit le fichier, construit, décode, reconnaît)
    loader.py       lecture des fichiers de protocols/
    default.py      protocole générique intégré (DEFAULT_PROTOCOL)
    helpers.py      fonctions raccourcies, couleurs, résumé

    from core.protocol import load_protocol, QUERY, RESPONSE
    p = load_protocol("protocols/modbus_rtu.json")
    d = p.decode(p.build_query(5, 4), QUERY)

Ce paquet ne dépend ni de l'interface ni du port série.
"""
from .common import KIND_KEYS, QUERY, RESPONSE, ProtocolError
from .crc import CRC_PRESETS, Crc, crc16_modbus
from .decoded import Decoded, Field
from .fields import COLORS, ROLES, FieldSpec
from .helpers import (ProtocolConfig, build_query, build_response, color_segments, data_and_status,
                      decode, request_id_text, status_parts, summary)
from .loader import list_protocols, load_protocol
from .protocol import Protocol
from .default import DEFAULT_PROTOCOL, GENERIC

__all__ = [
    "KIND_KEYS", "QUERY", "RESPONSE", "ProtocolError", "CRC_PRESETS", "Crc", "crc16_modbus",
    "Decoded", "Field", "COLORS", "ROLES", "FieldSpec", "ProtocolConfig", "build_query",
    "build_response", "color_segments", "data_and_status", "decode", "request_id_text", "status_parts", "summary", "list_protocols",
    "load_protocol", "Protocol", "DEFAULT_PROTOCOL", "GENERIC",
]
