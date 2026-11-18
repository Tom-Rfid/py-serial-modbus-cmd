#!/usr/bin/env python3
"""
Génère tests/protocol_vectors.json : contrat entre le moteur de protocole Python
(core/protocol.py) et sa version TypeScript (js/src/core/protocol.ts).

Pour chaque protocole (fichiers de protocols/ + structures d'essai ci-dessous) :
    - trames construites (ou erreur attendue)
    - trames décodées : champs, contrôles, erreurs, octets en trop, couleurs
Plus les valeurs de contrôle des CRC et des fichiers de conf invalides.

    python tools/gen_protocol_vectors.py
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.frames import to_hex  # noqa: E402
from core.jsonc import loads  # noqa: E402
from core.protocol import (  # noqa: E402
    CRC_PRESETS, QUERY, RESPONSE, GENERIC, Protocol, ProtocolError, color_segments,
)

KINDS = {QUERY: "tx", RESPONSE: "rx"}

# Structures d'essai : tailles 0 à 4, CRC 8 / 16 / 32, plages, DATA fixe ou « le reste »
SYNTHETIC = [
    {"name": "RID 16 bits, sans COMMAND ID, CRC32 sur tout", "byte_order": "big", "crc": {"c": "crc32"},
     "tx": [{"name": "SYNC", "size": 2, "value": "0xAA55", "color": "hdr"},
            {"name": "RID", "size": 2, "role": "request_id", "color": "hdr"},
            {"name": "CMD", "size": 0, "role": "command_id"},
            {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "c", "color": "crc"}],
     "rx": [{"name": "SYNC", "size": 2, "value": "0xAA55", "color": "hdr"},
            {"name": "RID", "size": 2, "role": "request_id", "color": "hdr"},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "c", "over": [0, "end"], "color": "crc"}]},
    {"name": "Trame fixe, CRC8 sur octets 0 à 10", "crc": {"c": "crc8"},
     "tx": [{"name": "STX", "size": 1, "value": 2, "color": "hdr"},
            {"name": "DATA", "role": "data", "size": 10},
            {"name": "CRC", "role": "crc", "algo": "c", "over": [0, 10], "color": "crc"}],
     "rx": [{"name": "STX", "size": 1, "value": 2, "color": "hdr"},
            {"name": "DATA", "role": "data", "size": 10},
            {"name": "CRC", "role": "crc", "algo": "c", "over": [0, 10], "color": "crc"}]},
    {"name": "Octets non lus (NA), plusieurs", "crc": {"c": "crc16_modbus"},
     "tx": [{"name": "SOF", "size": 1, "value": "0x7E", "color": "hdr"},
            {"name": "RES1", "size": 2, "role": "na"},
            {"name": "RID", "size": 1, "role": "request_id", "color": "hdr"},
            {"name": "RES2", "size": 1, "role": "NA", "fill": "0xFF"},
            {"name": "CMD", "size": 2, "role": "command_id", "color": "cmd"},
            {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "c", "color": "crc"}],
     "rx": [{"name": "SOF", "size": 1, "value": "0x7E", "color": "hdr"},
            {"name": "RES1", "size": 2, "role": "na", "fill": 170},
            {"name": "RID", "size": 1, "role": "request_id", "color": "hdr"},
            {"name": "ST", "size": 1, "role": "error"},
            {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
            {"name": "DATA", "role": "data"},
            {"name": "PAD", "size": 3, "role": "na", "if": "DATA"},
            {"name": "CRC", "role": "crc", "algo": "c", "color": "crc"}]},
    {"name": "Placement at / after / end, couleur hexa",
     "tx": [{"name": "CRC", "role": "crc", "algo": "sum16", "at": "end", "color": "#FF8800"},
            {"name": "DATA", "role": "data", "after": "LEN"},
            {"name": "CMD", "size": 2, "role": "command_id", "at": 4, "color": "cmd"},
            {"name": "RID", "size": 1, "role": "request_id", "after": "SOF"},
            {"name": "LEN", "size": 1, "role": "length", "of": "DATA", "after": "CMD"},
            {"name": "SOF", "size": 1, "value": "0x7E", "at": "start", "color": "hdr"}],
     "rx": [{"name": "SOF", "size": 1, "value": "0x7E", "at": 0, "color": "hdr"},
            {"name": "RID", "size": 1, "role": "request_id", "at": 1},
            {"name": "ST", "size": 1, "role": "error", "at": 3},
            {"name": "LEN", "size": 1, "role": "length", "of": "DATA", "at": 4},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "crc8", "at": "end"}]},
    {"name": "Champs en bits (msb) : exception Modbus, LENb / atb / atO", "byte_order": "big",
     "tx": [{"name": "VER", "LENb": 3, "value": 2, "color": "hdr"},
            {"name": "TYPE", "LENb": 5, "role": "command_id", "color": "cmd"},
            {"name": "FLAG", "LENb": 1, "role": "field", "atb": 12, "default": 1},
            {"name": "RID", "LENO": 1, "role": "request_id", "atO": 2},
            {"name": "LEN", "LENb": 8, "role": "length", "of": "DATA"},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "crc16_modbus", "order": "little", "color": "crc"}],
     "rx": [{"name": "ESCLAVE", "size": 1, "role": "field"},
            {"name": "EXCEPTION", "LENb": 1, "role": "error"},
            {"name": "FONCTION", "LENb": 7, "role": "command_id"},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "crc16_modbus", "order": "little"}]},
    {"name": "Champs en bits (lsb)", "bit_order": "lsb",
     "tx": [{"name": "A", "LENb": 3, "value": 5},
            {"name": "B", "LENb": 9, "role": "command_id"},
            {"name": "C", "LENb": 4, "role": "request_id"},
            {"name": "DATA", "role": "data"},
            {"name": "S", "role": "crc", "algo": "xor8"}],
     "rx": [{"name": "A", "LENb": 3, "value": 5},
            {"name": "E", "LENb": 5, "role": "error"},
            {"name": "C", "LENb": 4, "role": "request_id"},
            {"name": "N", "LENb": 4, "role": "na", "fill": 1},
            {"name": "DATA", "role": "data"},
            {"name": "S", "role": "crc", "algo": "xor8"}]},
    {"name": "Variantes M-Bus, champ copie, sens des valeurs",
     "tx": {"variants": [
         {"name": "Courte", "fields": [{"name": "START", "size": 1, "value": "0x10", "color": "hdr"},
                                       {"name": "C", "size": 1, "role": "command_id", "color": "cmd"},
                                       {"name": "A", "size": 1, "role": "request_id"},
                                       {"name": "CS", "role": "crc", "algo": "sum8", "over": ["C", "A"]},
                                       {"name": "STOP", "size": 1, "value": "0x16"}]},
         {"name": "Longue", "fields": [{"name": "START", "size": 1, "value": "0x68"},
                                       {"name": "L", "size": 1, "role": "length", "of": ["C", "A", "CI", "DATA"]},
                                       {"name": "L2", "size": 1, "role": "copy", "same_as": "L"},
                                       {"name": "START2", "size": 1, "value": "0x68"},
                                       {"name": "C", "size": 1, "role": "command_id"},
                                       {"name": "A", "size": 1, "role": "request_id"},
                                       {"name": "CI", "size": 1, "role": "field", "default": "0x51",
                                        "values": {"0x51": "Envoi de données", "0x72": {"fr": "Réponse", "en": "Response"}}},
                                       {"name": "DATA", "role": "data"},
                                       {"name": "CS", "role": "crc", "algo": "sum8", "over": ["C", "DATA"]},
                                       {"name": "STOP", "size": 1, "value": "0x16"}]}]},
     "rx": {"variants": [
         {"name": "Accusé", "fields": [{"name": "ACK", "size": 1, "value": "0xE5", "color": "hdr"}]},
         {"name": "Longue", "fields": [{"name": "START", "size": 1, "value": "0x68"},
                                       {"name": "L", "size": 1, "role": "length", "of": ["C", "A", "CI", "DATA"]},
                                       {"name": "L2", "size": 1, "role": "copy", "same_as": "L"},
                                       {"name": "START2", "size": 1, "value": "0x68"},
                                       {"name": "C", "size": 1, "role": "command_id"},
                                       {"name": "A", "size": 1, "role": "request_id"},
                                       {"name": "CI", "size": 1, "role": "error", "values": {"0": "OK"}},
                                       {"name": "DATA", "role": "data"},
                                       {"name": "CS", "role": "crc", "algo": "sum8", "over": ["C", "DATA"]},
                                       {"name": "STOP", "size": 1, "value": "0x16"}]}]}},
    {"name": "Modbus ASCII (codage hexa ASCII)", "byte_order": "big",
     "encoding": {"type": "ascii_hex", "start": ":", "end": "\r\n"},
     "tx": [{"name": "ESCLAVE", "size": 1, "role": "request_id"},
            {"name": "FONCTION", "size": 1, "role": "command_id"},
            {"name": "DATA", "role": "data"},
            {"name": "LRC", "role": "crc", "algo": "sum8_2c"}],
     "rx": [{"name": "ESCLAVE", "size": 1, "role": "request_id"},
            {"name": "EXCEPTION", "LENb": 1, "role": "error"},
            {"name": "FONCTION", "LENb": 7, "role": "command_id"},
            {"name": "DATA", "role": "data"},
            {"name": "LRC", "role": "crc", "algo": "sum8_2c"}]},
    {"name": "Longueur incluant le CRC, champ libre, ordre par champ",
     "crc": {"k": {"width": 16, "poly": "0x1021", "init": 0, "refin": True, "refout": True, "xorout": 0}},
     "tx": [{"name": "M", "size": 1, "value": 1, "color": "hdr"},
            {"name": "ADR", "size": 1, "role": "field", "default": 7},
            {"name": "CID", "size": 3, "role": "command_id", "order": "big", "color": "cmd"},
            {"name": "L", "size": 1, "role": "length", "of": ["DATA", "CRC"]},
            {"name": "DATA", "role": "data"},
            {"name": "CRC", "role": "crc", "algo": "k", "over": ["M", "DATA"], "color": "crc"}],
     "rx": [{"name": "M", "size": 1, "value": 1, "color": "hdr"},
            {"name": "ST", "size": 1, "role": "error"},
            {"name": "L", "size": 2, "role": "length", "of": "DATA"},
            {"name": "DATA", "role": "data"},
            {"name": "S", "role": "crc", "algo": "sum8", "if": "DATA", "over": ["DATA", "DATA"]}]},
]

DATAS = ["", "01", "01 02 03 04 05 06 07 08 09 0A"]
VALUE_SETS = [
    {"request_id": 0, "command_id": 0, "error": 0},
    {"request_id": 5, "command_id": 0x80000004, "error": 4, "ADR": 9},
    {"request_id": 255, "command_id": 7, "error": 0},
]
ERROR_VALUES = [{"request_id": -1}, {"request_id": 0x10000}, {"command_id": 0x100000000}, {"error": 256}]

INVALID = [
    ({"tx": []}, "liste de champs"),
    ({"byte_order": "milieu"}, "byte_order"),
    ({"tx": [{"name": "A", "size": 5}]}, "0 à 4"),
    ({"tx": [{"name": "A", "size": 1, "role": "truc"}]}, "rôle"),
    ({"tx": [{"name": "A", "size": 1}, {"name": "A", "size": 1}]}, "double"),
    ({"tx": [{"name": "C", "role": "crc", "algo": "inconnu"}]}, "CRC 'inconnu'"),
    ({"tx": [{"name": "C", "role": "crc", "algo": "crc8", "size": 2}]}, "incompatible"),
    ({"tx": [{"name": "C", "role": "crc", "algo": "crc8", "over": [0, "X"]}]}, "inconnu 'X'"),
    ({"tx": [{"name": "D", "role": "data"}, {"name": "L", "size": 1, "role": "length", "of": "D"}]}, "précéder"),
    ({"tx": [{"name": "M", "size": 1, "value": 300}]}, "ne tient pas"),
    ({"crc": {"x": {"width": 12}}}, "8, 16 ou 32"),
    ({"tx": [{"name": "A", "size": 1, "color": "rose"}]}, "couleur"),
    ({"tx": [{"name": "A", "role": "na"}]}, "\"size\" manquant"),
    ({"tx": [{"name": "A", "size": 1, "role": "na", "fill": 256}]}, "fill"),
    ({"tx": [{"name": "A", "size": 2, "at": 0}, {"name": "B", "size": 1, "at": 1}]}, "déjà occupé"),
    ({"tx": [{"name": "D", "role": "data", "at": 0}, {"name": "B", "size": 1, "at": 3}]}, "taille fixe"),
    ({"tx": [{"name": "A", "size": 1, "after": "B"}, {"name": "B", "size": 1, "after": "A"}]}, "circulaire"),
    ({"tx": [{"name": "A", "size": 1, "after": "Z"}]}, "inconnu 'Z'"),
    ({"tx": [{"name": "A", "size": 1, "at": 1, "after": "B"}, {"name": "B", "size": 1}]}, "ensemble"),
    ({"tx": [{"name": "A", "size": 1, "at": -1}]}, "numéro d'octet"),
    ({"tx": [{"name": "A", "LENb": 4}, {"name": "D", "role": "data"}]}, "octet entier"),
    ({"tx": [{"name": "A", "LENb": 12}]}, "il manque 4 bit(s)"),
    ({"tx": [{"name": "L", "size": 1, "role": "length", "of": "C"}, {"name": "C", "LENb": 4},
             {"name": "E", "LENb": 4}]}, "ensemble des octets entiers (4 bits)"),
    ({"tx": [{"name": "A", "size": 1, "LENb": 8}]}, "une seule taille"),
    ({"tx": [{"name": "A", "size": 1, "atb": -1}]}, "numéro de bit"),
    ({"tx": [{"name": "A", "size": 1, "at": 1, "atb": 8}]}, "une seule position"),
    ({"tx": [{"name": "C", "role": "crc", "algo": "crc8", "LENb": 4}]}, "nombre entier d'octets"),
    ({"tx": [{"name": "A", "LENb": 4, "atb": 0}, {"name": "B", "LENb": 4, "atb": 2}]}, "le bit 2 est déjà occupé"),
    ({"bit_order": "milieu"}, "bit_order"),
    ({"tx": [{"name": "A", "size": 1, "role": "copy"}]}, "same_as"),
    ({"tx": [{"name": "A", "size": 1, "role": "copy", "same_as": "B"}, {"name": "B", "size": 1}]}, "précéder"),
    ({"tx": {"variants": [{"name": "X", "fields": [{"name": "A", "size": 1}]},
                          {"name": "X", "fields": [{"name": "A", "size": 1}]}]}}, "variantes en double"),
    ({"tx": {"variants": []}}, "variants"),
    ({"encoding": {"type": "base64"}}, "encoding"),
    ({"tx": [{"name": "A", "LENb": 4}, {"name": "B", "LENb": 4, "if": "A"}]}, "conditionnel"),
]


def decoded_json(d):
    return {
        "complete": d.complete, "ok": d.ok, "errors": d.errors, "extra": to_hex(d.extra), "variant": d.variant,
        "fields": [{"name": f.name, "start": f.start, "raw": to_hex(f.raw), "value": f.value,
                    "ok": f.ok, "note": f.note, "role": f.role, "meaning": f.meaning} for f in d.fields],
        "segments": [list(s) for s in color_segments(d)],
    }


def corruptions(frame):
    """Variantes abîmées d'une trame : octet changé au début / au milieu / à la fin, tronquée, octet en trop."""
    out = []
    for i in (0, len(frame) // 2, len(frame) - 1):
        f = bytearray(frame)
        f[i] ^= 0xFF
        out.append(bytes(f))
    out += [frame[:-1], frame[:len(frame) // 2], frame + b"\x00"]
    return out


def _build_inputs(p, kind):
    """(variante, données, valeurs) à construire : chaque variante, chaque jeu de données et de valeurs."""
    for variant in p.variant_names(kind) or [None]:
        for data in DATAS:
            for values in VALUE_SETS:
                yield variant, data, values


def protocol_case(conf, file=None):
    p = Protocol(conf)
    case = {"name": p.name, "file": file, "conf": conf, "build": [], "decode": [], "matches": []}
    for kind, key in KINDS.items():
        for variant, data, values in _build_inputs(p, kind):
            raw = bytes.fromhex(data)
            if True:
                entry = {"kind": key, "data": data, "values": values, "variant": variant}
                try:
                    frame = p.build(kind, raw, values, variant=variant)
                except ValueError:
                    entry["error"] = True
                    case["build"].append(entry)
                    continue
                entry["frame"] = to_hex(frame)
                case["build"].append(entry)
                for f in [frame] + corruptions(frame):
                    case["decode"].append({"kind": key, "frame": to_hex(f), **decoded_json(p.decode(f, kind))})
                    case["matches"].append({"kind": key, "frame": to_hex(f), "result": p.matches(f, kind)})
        for values in ERROR_VALUES:
            try:
                p.build(kind, b"", values)
                ok = True
            except ValueError:
                ok = False
            case["build"].append({"kind": key, "data": "", "values": values, "variant": None,
                                  **({} if ok else {"error": True}),
                                  **({"frame": to_hex(p.build(kind, b"", values))} if ok else {})})
    case["main_crc"] = to_hex(p.crc_bytes(bytes.fromhex("01 03 00 00 00 0A")))
    case["max_request_id"] = p.max_value(QUERY, "request_id")
    return case


def main():
    protocols = []
    for path in sorted((ROOT / "protocols").glob("*.json")):
        conf = loads(path.read_text(encoding="utf-8"))      # commentaires // acceptés
        protocols.append(protocol_case(conf, path.name))
    for conf in SYNTHETIC:
        protocols.append(protocol_case(conf))
    invalid = []
    for change, msg in INVALID:
        conf = copy.deepcopy(GENERIC)
        conf.update(change)
        try:
            Protocol(conf)
            raise SystemExit(f"devrait être invalide : {change}")
        except ProtocolError as e:
            assert msg in str(e), (msg, str(e))
            invalid.append({"conf": conf, "message": str(e)})
    out = {
        "_comment": "Généré par tools/gen_protocol_vectors.py — ne pas modifier à la main.",
        "crc_check": {name: c.compute(b"123456789") for name, c in CRC_PRESETS.items()},
        "protocols": protocols,
        "invalid": invalid,
    }
    path = ROOT / "tests" / "protocol_vectors.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    n = sum(len(p["build"]) + len(p["decode"]) for p in protocols)
    print(f"{path.relative_to(ROOT)} : {len(protocols)} protocoles, {n} cas, {len(invalid)} confs invalides")


if __name__ == "__main__":
    main()
