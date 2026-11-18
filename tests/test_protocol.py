"""
Tests du moteur de protocole configurable (core/protocol.py).

    python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.frames import to_hex  # noqa: E402
from core.protocol import (  # noqa: E402
    CRC_PRESETS, DEFAULT_PROTOCOL, GENERIC, color_segments, QUERY, RESPONSE, Protocol, ProtocolConfig, ProtocolError,
    build_query, build_response, crc16_modbus, decode, list_protocols, load_protocol, summary,
)

ROOT = Path(__file__).resolve().parent.parent
CRC8 = CRC_PRESETS["crc8"]
CCITT = CRC_PRESETS["crc16_ccitt_false"]


def variant(**changes):
    """Copie du protocole générique intégré avec des modifications.

    Requête : SYNC A5 5A | SEQ | CMD (2) | LEN | HCRC (CRC8) | DATA | DCRC (CRC16 CCITT, si DATA)
    Réponse : SYNC A5 5A | SEQ | STATUS | LEN | HCRC | DATA | DCRC
    """
    import copy
    conf = copy.deepcopy(GENERIC)
    conf.update(changes)
    return conf


class TestCrc(unittest.TestCase):
    def test_reference_modbus(self):
        # Trame Modbus classique : 01 03 00 00 00 0A -> CRC C5 CD
        self.assertEqual(crc16_modbus(bytes.fromhex("01 03 00 00 00 0A")), 0xCDC5)
        self.assertEqual(to_hex(ProtocolConfig(crc_order="little").crc_bytes(bytes.fromhex("01 03 00 00 00 0A"))), "C5 CD")
        self.assertEqual(to_hex(ProtocolConfig().crc_bytes(bytes.fromhex("01 03 00 00 00 0A"))), "CD C5")

    def test_valeurs_de_controle(self):
        # Valeur de chaque CRC pour "123456789" (catalogue reveng)
        check = {"crc16_modbus": 0x4B37, "crc16_ccitt_false": 0x29B1, "crc16_xmodem": 0x31C3,
                 "crc16_kermit": 0x2189, "crc8": 0xF4, "crc8_maxim": 0xA1, "crc32": 0xCBF43926,
                 "crc32_mpeg2": 0x0376E6E7, "sum8": 0xDD, "sum8_2c": 0x23, "xor8": 0x31, "sum16": 0x01DD}
        for name, value in check.items():
            self.assertEqual(CRC_PRESETS[name].compute(b"123456789"), value, name)

    def test_crc_personnalise(self):
        # CRC16 CCITT décrit paramètre par paramètre : mêmes trames qu'avec le préréglage
        conf = variant(crc={"c": {"width": 16, "poly": "0x1021", "init": "0xFFFF",
                                  "refin": False, "refout": False, "xorout": 0}})
        for kind in ("tx", "rx"):
            conf[kind][-1] = dict(conf[kind][-1], algo="c")
        p = Protocol(conf)
        self.assertEqual(p.build_query(5, 4, b"\x01"), DEFAULT_PROTOCOL.build_query(5, 4, b"\x01"))


class TestQuery(unittest.TestCase):
    def test_sans_donnees(self):
        f = build_query(5, 0x0102, b"")
        self.assertEqual(len(f), 7)                                   # en-tête seul
        self.assertEqual(to_hex(f[:6]), "A5 5A 05 01 02 00")          # big endian (poids fort en premier)
        self.assertEqual(f[6], CRC8.compute(f[:6]))                   # CRC8 des octets 0 à 5
        d = decode(f, QUERY)
        self.assertTrue(d.ok)
        self.assertEqual((d.get("SEQ"), d.get("CMD"), d.get("LEN")), (5, 0x0102, 0))

    def test_avec_donnees(self):
        data = bytes.fromhex("01 02 03")
        f = build_query(1, 7, data)
        self.assertEqual(len(f), 7 + 3 + 2)
        self.assertEqual(f[7:10], data)
        self.assertEqual(f[10:], CCITT.compute(data).to_bytes(2, "big"))     # DCRC sur DATA seule
        d = decode(f, QUERY)
        self.assertTrue(d.ok)
        self.assertEqual([x.name for x in d.fields], ["SYNC", "SEQ", "CMD", "LEN", "HCRC", "DATA", "DCRC"])
        self.assertEqual([x.span for x in d.fields], ["0-1", "2", "3-4", "5", "6", "7-9", "10-11"])
        self.assertEqual(to_hex(f), "A5 5A 01 00 07 03 09 01 02 03 AD AD")

    def test_little_endian(self):
        p = Protocol(variant(byte_order="little"))
        f = build_query(0, 0x0102, b"", p)
        self.assertEqual(to_hex(f[:6]), "5A A5 00 02 01 00")
        self.assertTrue(decode(f, QUERY, p).ok)
        # Décodée avec le mauvais ordre : le SYNC ne correspond plus et les valeurs sont fausses
        self.assertEqual(decode(f, QUERY).get("CMD"), 0x0201)

    def test_limites(self):
        with self.assertRaises(ValueError):
            build_query(256, 1)
        with self.assertRaises(ValueError):
            build_query(0, 0x1_0000)


class TestDecode(unittest.TestCase):
    def test_reponse(self):
        f = build_response(5, 0, b"\xAA\xBB")
        self.assertEqual(len(f), 6 + 2 + 2)
        d = decode(f, RESPONSE)
        self.assertTrue(d.ok)
        self.assertEqual(summary(d), "réponse #0x05 · erreur 0 · 2 o · CRC OK")

    def test_crc_faux(self):
        f = bytearray(build_query(1, 2, b"\x10"))
        f[6] ^= 0xFF                                   # corrompt le HCRC
        d = decode(bytes(f), QUERY)
        self.assertFalse(d.ok)
        self.assertIn("HCRC incorrect", d.errors)
        crc = next(x for x in d.fields if x.name == "HCRC")
        self.assertFalse(crc.ok)
        self.assertTrue(crc.note.startswith("attendu "))

    def test_synchro_et_tronquee(self):
        d = decode(bytes.fromhex("A5 5B 01 00"), RESPONSE)
        self.assertIn("SYNC différent de 0xA55A", d.errors)
        self.assertFalse(d.complete)
        d = decode(build_response(1, 0, b"123")[:-3], RESPONSE)
        self.assertFalse(d.complete)

    def test_octets_en_trop(self):
        d = decode(build_response(1) + b"\x00", RESPONSE)
        self.assertTrue(d.complete)
        self.assertEqual(d.extra, b"\x00")
        self.assertFalse(d.ok)
        self.assertIn("1 octet(s) en trop", summary(d))

    def test_ne_leve_jamais(self):
        for raw in (b"", b"\xA5", bytes(range(30))):
            for kind in (QUERY, RESPONSE):
                decode(raw, kind)


class TestConf(unittest.TestCase):
    """Fichiers de protocols/ et autres structures de trame."""

    def test_tous_les_fichiers(self):
        for name, p in list_protocols(ROOT / "protocols"):
            self.assertIsInstance(p, Protocol, f"{name} : {p}")
            f = p.build_query(1, 2, b"\x01\x02\x03")
            self.assertTrue(p.decode(f, QUERY).ok, name)

    def test_roles(self):
        d = DEFAULT_PROTOCOL.decode(build_response(9, 0, b"\x01\x02"), RESPONSE)
        self.assertEqual((d.request_id, d.error, d.length, d.data.raw, d.crc_ok), (9, 0, 2, b"\x01\x02", True))
        self.assertIsNone(d.command_id)
        self.assertIsNone(DEFAULT_PROTOCOL.decode(build_response(9), RESPONSE).data)
        self.assertEqual([f.color for f in d.fields],
                         ["hdr", "hdr", None, None, "crc", None, "crc"])

    def test_request_id_2_octets_sans_command_id_crc32(self):
        # REQUEST ID sur 2 octets, pas de COMMAND ID, CRC32 sur toute la trame
        conf = {"name": "T", "byte_order": "big", "crc": {"c": "crc32"},
                "tx": [{"name": "SYNC", "size": 2, "value": "0xAA55"},
                       {"name": "RID", "size": 2, "role": "request_id"},
                       {"name": "CMD", "size": 0, "role": "command_id"},
                       {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
                       {"name": "DATA", "role": "data"},
                       {"name": "CRC", "role": "crc", "algo": "c"}],
                "rx": [{"name": "SYNC", "size": 2, "value": "0xAA55"},
                       {"name": "RID", "size": 2, "role": "request_id"},
                       {"name": "DATA", "role": "data"},
                       {"name": "CRC", "role": "crc", "algo": "c", "over": [0, "end"]}]}
        p = Protocol(conf)
        f = p.build_query(0x1234, 99, b"\x01\x02")
        self.assertEqual(to_hex(f[:7]), "AA 55 12 34 02 01 02")
        self.assertEqual(f[7:], CRC_PRESETS["crc32"].compute(f[:7]).to_bytes(4, "big"))
        d = p.decode(f, QUERY)
        self.assertTrue(d.ok)
        self.assertEqual((d.request_id, d.command_id, d.data.raw), (0x1234, None, b"\x01\x02"))
        self.assertEqual(p.max_value(QUERY, "request_id"), 0xFFFF)
        self.assertFalse(p.has(QUERY, "command_id"))
        # Réponse sans longueur : DATA = le reste de la trame moins le CRC
        r = p.build_response(0x1234, 0, b"\x10\x20\x30")
        d = p.decode(r, RESPONSE)
        self.assertTrue(d.ok)
        self.assertEqual(d.data.raw, b"\x10\x20\x30")

    def test_trame_fixe_crc8_sur_plage(self):
        # Trame fixe de 12 octets : CRC8 sur les octets 0 à 10
        conf = {"name": "Fixe", "crc": {"c": "crc8"},
                "tx": [{"name": "STX", "size": 1, "value": 2},
                       {"name": "DATA", "role": "data", "size": 10},
                       {"name": "CRC", "role": "crc", "algo": "c", "over": [0, 10]}],
                "rx": [{"name": "STX", "size": 1, "value": 2},
                       {"name": "DATA", "role": "data", "size": 10},
                       {"name": "CRC", "role": "crc", "algo": "c", "over": [0, 10]}]}
        p = Protocol(conf)
        f = p.build(QUERY, bytes(range(10)))
        self.assertEqual(len(f), 12)
        self.assertEqual(f[11], CRC_PRESETS["crc8"].compute(f[:11]))
        self.assertTrue(p.decode(f, RESPONSE).ok)
        with self.assertRaises(ValueError):
            p.build(QUERY, b"\x01")                        # taille fixe non respectée

    def test_longueur_incluant_le_crc(self):
        conf = variant()
        conf["tx"] = [{"name": "M", "size": 1, "value": 1},
                      {"name": "L", "size": 1, "role": "length", "of": ["DATA", "CRC"]},
                      {"name": "DATA", "role": "data"},
                      {"name": "CRC", "role": "crc", "algo": "sum8", "over": ["M", "DATA"]}]
        p = Protocol(conf)
        f = p.build(QUERY, b"\x05\x06")
        self.assertEqual(to_hex(f), "01 03 05 06 0F")
        self.assertTrue(p.decode(f, QUERY).ok)

    def test_champ_field_et_order(self):
        conf = variant()
        conf["tx"] = [{"name": "M", "size": 1, "value": 1},
                      {"name": "ADR", "size": 1, "role": "field", "default": 7},
                      {"name": "CID", "size": 2, "role": "command_id", "order": "big"},
                      {"name": "CRC", "role": "crc", "algo": "crc16_modbus"}]
        p = Protocol(conf)
        self.assertEqual(to_hex(p.build_query(0, 0x0102)[:4]), "01 07 01 02")
        self.assertEqual(to_hex(p.build(QUERY, ADR=9, command_id=1)[:4]), "01 09 00 01")

    def test_octets_non_lus(self):
        conf = variant()
        conf["tx"] = [{"name": "M", "size": 1, "value": 1},
                      {"name": "R1", "size": 2, "role": "na"},
                      {"name": "CID", "size": 1, "role": "command_id"},
                      {"name": "R2", "size": 1, "role": "NA", "fill": "0xFF"},
                      {"name": "CRC", "role": "crc", "algo": "sum8"}]
        p = Protocol(conf)
        f = p.build_query(0, 5)
        self.assertEqual(to_hex(f), "01 00 00 05 FF 05")
        # Octets non lus changés : ni erreur ni valeur, mais le CRC les couvre toujours
        g = bytearray(f)
        g[1] = 0x99
        g[5] = (g[5] + 0x99) & 0xFF
        d = p.decode(bytes(g), QUERY)
        self.assertTrue(d.ok)
        na = [x for x in d.fields if x.role == "na"]
        self.assertEqual([(x.name, x.value, x.note, x.color) for x in na],
                         [("R1", None, "non lu", "na"), ("R2", None, "non lu", "na")])
        self.assertEqual(d.command_id, 5)

    def test_placement_octet_after_end(self):
        conf = variant()
        # Liste dans le désordre : chaque champ dit où il va
        conf["tx"] = [{"name": "CRC", "role": "crc", "algo": "sum8", "at": "end"},
                      {"name": "DATA", "role": "data", "after": "LEN"},
                      {"name": "CMD", "size": 1, "role": "command_id", "at": 4},
                      {"name": "RID", "size": 1, "role": "request_id", "after": "SOF"},
                      {"name": "LEN", "size": 1, "role": "length", "of": "DATA", "after": "CMD"},
                      {"name": "SOF", "size": 1, "value": "0x7E", "at": "start"}]
        p = Protocol(conf)
        self.assertEqual([f.name for f in p.layouts[QUERY]],
                         ["SOF", "RID", "(octets 2-3)", "CMD", "LEN", "DATA", "CRC"])
        f = p.build_query(5, 9, b"\xAA")
        self.assertEqual(to_hex(f), "7E 05 00 00 09 01 AA " + to_hex(bytes([(0x7E + 5 + 9 + 1 + 0xAA) & 0xFF])))
        d = p.decode(f, QUERY)
        self.assertTrue(d.ok)
        self.assertEqual(d.fields[2].note, "non lu")

    def test_carte_des_octets(self):
        # Comme un tableau de spécification : chaque champ à son octet de départ
        conf = variant()
        conf["tx"] = [{"name": "CRC", "size": 2, "role": "crc", "algo": "crc16_modbus", "at": 6,
                       "over": [0, 5]},
                      {"name": "M", "size": 1, "value": "0x7E", "at": 0},
                      {"name": "CID", "size": 4, "role": "command_id", "at": 2}]
        p = Protocol(conf)
        self.assertEqual([f.name for f in p.layouts[QUERY]], ["M", "(octet 1)", "CID", "CRC"])
        self.assertEqual(len(p.build_query(0, 4)), 8)

    def test_placement_invalide(self):
        cases = [
            ([{"name": "A", "size": 2, "at": 0}, {"name": "B", "size": 1, "at": 1}], "déjà occupé"),
            ([{"name": "D", "role": "data", "at": 0}, {"name": "B", "size": 1, "at": 3}], "taille fixe"),
            ([{"name": "A", "size": 1, "after": "B"}, {"name": "B", "size": 1, "after": "A"}], "circulaire"),
            ([{"name": "A", "size": 1, "after": "Z"}], "after désigne un champ inconnu 'Z'"),
            ([{"name": "A", "size": 1, "at": 1, "after": "B"}, {"name": "B", "size": 1}], "ensemble"),
            ([{"name": "A", "size": 1, "at": "milieu"}], "entier attendu"),
        ]
        for tx, msg in cases:
            with self.assertRaises(ProtocolError) as ctx:
                Protocol(variant(tx=tx))
            self.assertIn(msg, str(ctx.exception), tx)

    def test_champs_en_bits_modbus_exception(self):
        # Fonction Modbus sur 7 bits + bit d'exception (poids fort) : 01 83 02 = exception 2 sur la fonction 3
        conf = {"name": "Modbus bits", "byte_order": "big",
                "tx": [{"name": "ESCLAVE", "size": 1, "role": "field", "default": 1},
                       {"name": "FONCTION", "size": 1, "role": "command_id"},
                       {"name": "DATA", "role": "data"},
                       {"name": "CRC", "role": "crc", "algo": "crc16_modbus", "order": "little"}],
                "rx": [{"name": "ESCLAVE", "size": 1, "role": "field"},
                       {"name": "EXCEPTION", "LENb": 1, "role": "error"},
                       {"name": "FONCTION", "LENb": 7, "role": "command_id"},
                       {"name": "DATA", "role": "data"},
                       {"name": "CRC", "role": "crc", "algo": "crc16_modbus", "order": "little"}]}
        p = Protocol(conf)
        f = p.build(RESPONSE, b"\x02", {"ESCLAVE": 1, "error": 1, "command_id": 3})
        self.assertEqual(to_hex(f[:3]), "01 83 02")
        d = p.decode(f, RESPONSE)
        self.assertTrue(d.ok)
        self.assertEqual((d.error, d.command_id, d.data.raw), (1, 3, b"\x02"))
        self.assertEqual([x.span for x in d.fields[:3]], ["0", "1.0", "1.1-1.7"])
        self.assertEqual(p.max_value(RESPONSE, "command_id"), 127)

    def test_bits_msb_lsb_et_atb(self):
        def proto(order):
            return Protocol({"name": "B", "bit_order": order,
                             "tx": [{"name": "VER", "LENb": 3, "value": 2},
                                    {"name": "TYPE", "LENb": 5, "role": "command_id"},
                                    {"name": "FLAG", "LENb": 1, "role": "field", "atb": 12, "default": 1},
                                    {"name": "X", "LENO": 1, "role": "field", "atO": 2, "default": "0xAB"}],
                             "rx": [{"name": "D", "role": "data"}]})
        p = proto("msb")
        self.assertEqual([f.name for f in p.layouts[QUERY]], ["VER", "TYPE", "(bits 8-11)", "FLAG", "(bits 13-15)", "X"])
        f = p.build_query(0, 0x15)
        self.assertEqual(to_hex(f), "55 08 AB")              # 010 10101 | 0000 1 000 | AB
        self.assertEqual(p.decode(f, QUERY).command_id, 0x15)
        q = proto("lsb")
        g = q.build_query(0, 0x15)
        self.assertEqual(to_hex(g), "AA 10 AB")              # VER=2 sur bits 0-2 (poids faible d'abord)
        d = q.decode(g, QUERY)
        self.assertTrue(d.ok)
        self.assertEqual(d.command_id, 0x15)

    def test_bits_invalides(self):
        cases = [
            ([{"name": "A", "LENb": 4}, {"name": "D", "role": "data"}], "commencer sur un octet entier"),
            ([{"name": "A", "LENb": 12}], "ne finit pas sur un octet entier (il manque 4 bit(s))"),
            ([{"name": "L", "size": 1, "role": "length", "of": "B"}, {"name": "B", "LENb": 8},
              {"name": "C", "LENb": 4}, {"name": "E", "LENb": 4}], None),
            ([{"name": "L", "size": 1, "role": "length", "of": "C"}, {"name": "C", "LENb": 4},
              {"name": "E", "LENb": 4}], "ensemble des octets entiers (4 bits)"),
            ([{"name": "L", "size": 1, "role": "length", "of": ["C", "E"]}, {"name": "C", "LENb": 4},
              {"name": "E", "LENb": 4}], None),
            ([{"name": "A", "size": 1, "LENb": 8}], "une seule taille"),
            ([{"name": "A", "LENb": 33}], "0 à 4 octets (32 bits)"),
            ([{"name": "A", "size": 1, "atb": -1}], "numéro de bit"),
            ([{"name": "A", "size": 1, "at": 1, "atb": 8}], "une seule position"),
            ([{"name": "C", "role": "crc", "algo": "crc8", "LENb": 4}], "nombre entier d'octets"),
        ]
        for tx, msg in cases:
            if msg is None:
                Protocol(variant(tx=tx))
                continue
            with self.assertRaises(ProtocolError) as ctx:
                Protocol(variant(tx=tx))
            self.assertIn(msg, str(ctx.exception), tx)

    def test_variantes_mbus(self):
        # M-Bus : accusé E5, trame courte 10 C A CS 16, trame longue 68 L L 68 C A CI DATA CS 16
        conf = {"name": "M-Bus", "rx": {"variants": [
            {"name": "Accusé", "fields": [{"name": "ACK", "size": 1, "value": "0xE5"}]},
            {"name": "Courte", "fields": [{"name": "START", "size": 1, "value": "0x10"},
                                          {"name": "C", "size": 1, "role": "command_id"},
                                          {"name": "A", "size": 1, "role": "field"},
                                          {"name": "CS", "role": "crc", "algo": "sum8", "over": ["C", "A"]},
                                          {"name": "STOP", "size": 1, "value": "0x16"}]},
            {"name": "Longue", "fields": [{"name": "START", "size": 1, "value": "0x68"},
                                          {"name": "L", "size": 1, "role": "length", "of": ["C", "A", "CI", "DATA"]},
                                          {"name": "L2", "size": 1, "role": "copy", "same_as": "L"},
                                          {"name": "START2", "size": 1, "value": "0x68"},
                                          {"name": "C", "size": 1, "role": "command_id"},
                                          {"name": "A", "size": 1, "role": "field"},
                                          {"name": "CI", "size": 1, "role": "field",
                                           "values": {"0x72": {"fr": "Réponse données variables", "en": "Variable data response"}}},
                                          {"name": "DATA", "role": "data"},
                                          {"name": "CS", "role": "crc", "algo": "sum8", "over": ["C", "DATA"]},
                                          {"name": "STOP", "size": 1, "value": "0x16"}]}]},
            "tx": [{"name": "START", "size": 1, "value": "0x10"}, {"name": "C", "size": 1, "role": "command_id"},
                   {"name": "A", "size": 1, "role": "field"},
                   {"name": "CS", "role": "crc", "algo": "sum8", "over": ["C", "A"]},
                   {"name": "STOP", "size": 1, "value": "0x16"}]}
        p = Protocol(conf)
        self.assertEqual(p.variant_names(RESPONSE), ["Accusé", "Courte", "Longue"])
        self.assertEqual(p.decode(b"\xE5", RESPONSE).variant, "Accusé")
        self.assertEqual(to_hex(p.build_query(0, 0x5B, b"") if False else p.build(QUERY, b"", command_id=0x5B, A=1)),
                         "10 5B 01 5C 16")                       # REQ_UD2 vers l'adresse 1
        long = p.build(RESPONSE, b"\x01\x02", {"command_id": 8, "A": 1, "CI": 0x72}, variant="Longue")
        self.assertEqual(to_hex(long[:7]), "68 05 05 68 08 01 72")
        d = p.decode(long, RESPONSE)
        self.assertEqual((d.variant, d.ok, d.data.raw), ("Longue", True, b"\x01\x02"))
        self.assertEqual(d.by_role("field").name, "A")
        self.assertEqual(next(f for f in d.fields if f.name == "CI").meaning, "Réponse données variables")
        p.language = "en"
        self.assertEqual(next(f for f in p.decode(long, RESPONSE).fields if f.name == "CI").meaning, "Variable data response")
        bad = bytearray(long)
        bad[2] = 6                                               # longueur répétée différente
        self.assertIn("L2 différent de L", p.decode(bytes(bad), RESPONSE).errors)
        with self.assertRaises(ValueError):
            p.build(RESPONSE, variant="Inconnue")

    def test_ascii_hex_modbus(self):
        conf = {"name": "Modbus ASCII", "byte_order": "big", "encoding": {"type": "ascii_hex", "start": ":", "end": "\r\n"},
                "tx": [{"name": "ESCLAVE", "size": 1, "role": "field", "default": 1},
                       {"name": "FONCTION", "size": 1, "role": "command_id"},
                       {"name": "DATA", "role": "data"},
                       {"name": "LRC", "role": "crc", "algo": "sum8_2c"}],
                "rx": [{"name": "ESCLAVE", "size": 1, "role": "field"},
                       {"name": "FONCTION", "size": 1, "role": "command_id"},
                       {"name": "DATA", "role": "data"},
                       {"name": "LRC", "role": "crc", "algo": "sum8_2c"}]}
        p = Protocol(conf)
        f = p.build_query(0, 3, bytes.fromhex("00 00 00 0A"))
        self.assertEqual(f, b":01030000000AF2\r\n")
        self.assertEqual(p.frame_end, b"\r\n")
        d = p.decode(f, QUERY)
        self.assertTrue(d.ok)
        self.assertEqual((d.command_id, d.binary), (3, bytes.fromhex("01 03 00 00 00 0A F2")))
        self.assertTrue(p.matches(b":01", QUERY))
        self.assertFalse(p.matches(b"01", QUERY))
        self.assertIn("fin de trame '\\r\\n' absente", p.decode(f[:-2], QUERY).errors)
        self.assertIn("début de trame ':' absent", p.decode(f[1:], QUERY).errors)
        segs = p.display_segments(d, color_segments(d))
        self.assertEqual(segs[0], (0, 1, "hdr"))

    def test_cles_a_null_et_textes(self):
        conf = variant()
        conf["tx"] = [{"name": "M", "size": 1, "role": "value", "value": 1, "at": None, "after": None,
                       "LENb": None, "color": None, "fill": None, "default": None, "description": "Début",
                       "description_en": "Start", "category": "COM"},
                      {"name": "CRC", "role": "crc", "algo": "sum8", "size": None, "over": None}]
        p = Protocol(conf)
        self.assertEqual(to_hex(p.build_query()), "01 01")
        f = p.layouts[QUERY][0]
        self.assertEqual((f.description, f.description_en, f.category), ("Début", "Start", "COM"))

    def test_couleur_hexa(self):
        conf = variant()
        conf["tx"] = [{"name": "M", "size": 1, "value": 1, "color": "#FF8800"}]
        p = Protocol(conf)
        self.assertEqual(color_segments(p.decode(b"\x01", QUERY)), [(0, 1, "#FF8800")])

    def test_appartenance(self):
        p = DEFAULT_PROTOCOL
        self.assertTrue(p.matches(b"\xA5\x5A\x00", RESPONSE))
        self.assertTrue(p.matches(b"\xA5", RESPONSE))                  # début de trame incomplet
        self.assertFalse(p.matches(b"\xAA\x55", RESPONSE))
        self.assertFalse(p.matches(b"", RESPONSE))
        sans = Protocol({"name": "x", "tx": [{"name": "D", "role": "data"}], "rx": [{"name": "D", "role": "data"}]})
        self.assertTrue(sans.matches(b"\x01", QUERY))

    def test_crc_principal(self):
        # CRC principal = premier CRC de la requête : HCRC, CRC8
        self.assertEqual(to_hex(DEFAULT_PROTOCOL.crc_bytes(bytes.fromhex("01 03 00 00 00 0A"))), "B9")

    def test_conf_invalide(self):
        bad = [
            ({"tx": []}, "liste de champs"),
            (variant(byte_order="milieu"), "byte_order"),
            (variant(tx=[{"name": "A", "size": 5}]), "0 à 4"),
            (variant(tx=[{"name": "A", "size": 1, "role": "truc"}]), "rôle"),
            (variant(tx=[{"name": "A", "size": 1}, {"name": "A", "size": 1}]), "double"),
            (variant(tx=[{"name": "C", "role": "crc", "algo": "inconnu"}]), "CRC 'inconnu'"),
            (variant(tx=[{"name": "C", "role": "crc", "algo": "crc8", "size": 2}]), "incompatible"),
            (variant(tx=[{"name": "C", "role": "crc", "algo": "crc8", "over": [0, "X"]}]), "inconnu 'X'"),
            (variant(tx=[{"name": "D", "role": "data"}, {"name": "L", "size": 1, "role": "length", "of": "D"}]),
             "précéder"),
            (variant(tx=[{"name": "M", "size": 1, "value": 300}]), "ne tient pas"),
            (variant(crc={"x": {"width": 12}}), "8, 16 ou 32"),
        ]
        for conf, msg in bad:
            with self.assertRaises(ProtocolError) as ctx:
                Protocol(conf)
            self.assertIn(msg, str(ctx.exception), conf)


if __name__ == "__main__":
    unittest.main()
