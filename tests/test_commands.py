"""
Tests de la bibliothèque de commandes (core/commands.py).

    python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.commands import (  # noqa: E402
    decode_fields, decimals, describe, effective_range, encode_field, encode_fields, field_size,
    load_library, parse_library_file, type_range,
)
from core.frames import to_hex  # noqa: E402
from core.messages import load_folder  # noqa: E402
from core.protocol import RESPONSE, ProtocolConfig, build_response, decode  # noqa: E402

POWER = {"name": "puissance", "type": "u16", "unit": "mW", "factor": 0.1, "min": 0, "max": 500}
VOLT = {"name": "tension", "type": "u16", "unit": "V", "factor": 0.001, "offset": 2.5}
TEMP = {"name": "température", "type": "i16", "unit": "°C", "factor": 0.01}


class TestConversion(unittest.TestCase):
    def test_facteur(self):
        self.assertEqual(to_hex(encode_field(POWER, "12.5")), "00 7D")      # 125, big endian (par défaut)
        self.assertEqual(to_hex(encode_field(POWER, "12,5")), "00 7D")      # virgule acceptée
        little = ProtocolConfig(byte_order="little")
        self.assertEqual(to_hex(encode_field(POWER, 12.5, little)), "7D 00")
        self.assertEqual(to_hex(encode_field({**POWER, "type": "u16le"}, 12.5)), "7D 00")   # ordre forcé

    def test_offset(self):
        self.assertEqual(to_hex(encode_field(VOLT, 3.3)), "03 20")          # (3.3 - 2.5) / 0.001 = 800
        fields, errors = decode_fields([VOLT], bytes.fromhex("03 20"))
        self.assertEqual((fields[0].text, fields[0].raw_value, errors), ("3.300 V", 800, []))

    def test_signe(self):
        self.assertEqual(to_hex(encode_field(TEMP, -5.25)), "FD F3")        # -525
        fields, _ = decode_fields([TEMP], bytes.fromhex("FD F3"))
        self.assertEqual(fields[0].text, "-5.25 °C")

    def test_bornes(self):
        with self.assertRaises(ValueError):
            encode_field(POWER, 600)                                        # > max physique
        with self.assertRaises(ValueError):
            encode_field({"name": "x", "type": "u8", "factor": 0.1}, 30)    # brut 300 > 255
        with self.assertRaises(ValueError):
            encode_field(POWER, "abc")

    def test_decimales(self):
        self.assertEqual([decimals(POWER), decimals(VOLT), decimals({"name": "n"})], [1, 3, 0])
        self.assertEqual(decimals({**POWER, "decimals": 3}), 3)

    def test_autres_types(self):
        defs = [{"name": "mode", "type": "enum", "choices": {"off": 0, "on": 1}},
                {"name": "actif", "type": "bool"},
                {"name": "nom", "type": "ascii", "length": 4},
                {"name": "f", "type": "f32"},
                {"name": "reste", "type": "hex"}]
        data = encode_fields(defs, {"mode": "on", "actif": True, "nom": "AB", "f": 1.5, "reste": "DE AD"})
        self.assertEqual(to_hex(data), "01 01 41 42 00 00 3F C0 00 00 DE AD")
        fields, errors = decode_fields(defs, data, base=7)
        self.assertEqual([f.text for f in fields], ["on (1)", "1 (vrai)", "'AB'", "1.5", "DE AD"])
        self.assertEqual(fields[0].span, "7")
        self.assertEqual(errors, [])

    def test_decodage_incomplet_ou_en_trop(self):
        fields, errors = decode_fields([POWER], b"\x01")
        self.assertIn("trop courte", errors[0])
        fields, errors = decode_fields([POWER], b"\x01\x00\xFF")
        self.assertEqual(fields[-1].name, "(non décrit)")
        fields, _ = decode_fields([POWER], (6000).to_bytes(2, "big"))        # 600 mW > max
        self.assertFalse(fields[0].ok)


class TestTableauxEtBits(unittest.TestCase):
    IP = {"name": "IP", "type": "u8", "count": 4, "format": "ip"}
    MAC = {"name": "MAC", "type": "U8", "count": 6, "format": "mac"}      # « U8 » accepté
    ERR = {"name": "errors", "type": "u32", "count": 2,
           "bits": {"0": "Internal error", "1": "Interlock", "32": "Head temperature"}}

    def test_ip(self):
        self.assertEqual(to_hex(encode_field(self.IP, "192.168.1.10")), "C0 A8 01 0A")
        self.assertEqual(decode_fields([self.IP], bytes.fromhex("C0 A8 01 0A"))[0][0].text, "192.168.1.10")
        with self.assertRaises(ValueError):
            encode_field(self.IP, "192.168.1")          # 3 valeurs au lieu de 4
        with self.assertRaises(ValueError):
            encode_field(self.IP, "192.168.1.300")      # 300 > 255

    def test_mac(self):
        self.assertEqual(to_hex(encode_field(self.MAC, "00:1A:2B:3C:4D:5E")), "00 1A 2B 3C 4D 5E")
        self.assertEqual(decode_fields([self.MAC], bytes.fromhex("00 1A 2B 3C 4D 5E"))[0][0].text, "00:1A:2B:3C:4D:5E")

    def test_tableau_de_flottants(self):
        f = {"name": "plage", "type": "f32", "count": 2, "unit": "mm"}
        data = encode_field(f, "-1000, 2500.5")
        self.assertEqual(decode_fields([f], data)[0][0].text, "[-1000, 2500.5] mm")

    def test_bits(self):
        # mot 0 = 0x00000003 (bits 0 et 1), mot 1 = 0x00000001 (bit 32), big endian : chaque mot
        # de 32 bits est écrit octet de poids fort en premier
        data = bytes.fromhex("00 00 00 03 00 00 00 01")
        fields, _ = decode_fields([self.ERR], data)
        self.assertEqual(fields[0].text, "0x0000000100000003 : Internal error, Interlock, Head temperature")
        self.assertFalse(fields[0].ok)                   # erreur active -> rouge
        fields, _ = decode_fields([self.ERR], bytes(8))
        self.assertTrue(fields[0].text.endswith(": aucun"))
        fields, _ = decode_fields([self.ERR], bytes.fromhex("80 00 00 00 00 00 00 00"))
        self.assertIn("bit 31", fields[0].text)          # bit sans nom


class TestTypesEtPlages(unittest.TestCase):
    def test_noms_de_types(self):
        # Noms de la documentation : uint8 / int16 / float, majuscules, U8[4]
        self.assertEqual(to_hex(encode_field({"name": "a", "type": "uint16"}, 258)), "01 02")
        self.assertEqual(to_hex(encode_field({"name": "a", "type": "INT8"}, -1)), "FF")
        self.assertEqual(to_hex(encode_field({"name": "a", "type": "float"}, 1.5)), "3F C0 00 00")
        self.assertEqual(to_hex(encode_field({"name": "a", "type": "uint16le"}, 258)), "02 01")
        ip = {"name": "ip", "type": "U8[4]", "format": "ip"}
        self.assertEqual(field_size(ip), 4)
        self.assertEqual(to_hex(encode_field(ip, "10.0.0.1")), "0A 00 00 01")

    def test_valeurs_null(self):
        # Structure complète avec des null : équivalent à « non renseigné »
        f = {"name": "a", "label": None, "type": "uint8", "count": 1, "unit": None, "factor": None,
             "offset": None, "min": None, "max": None, "default": None, "decimals": None,
             "format": None, "choices": None, "bits": None}
        self.assertEqual(to_hex(encode_field(f, 7)), "07")
        self.assertEqual(decode_fields([f], b"\x07")[0][0].text, "7")
        parse_library_file({"commands": [{"name": "x", "id": 1, "tx": [f], "rx": [f]}]})

    def test_plage_du_type(self):
        self.assertEqual(type_range({"name": "a", "type": "uint8"}), (0, 255))
        self.assertEqual(type_range({"name": "a", "type": "int16"}), (-32768, 32767))
        self.assertEqual(type_range({"name": "a", "type": "uint8", "factor": 0.1}), (0.0, 25.5))
        self.assertEqual(type_range({"name": "a", "type": "uint16", "factor": 0.001, "offset": 2.5}), (2.5, 68.035))
        self.assertIsNone(type_range({"name": "a", "type": "float"}))
        self.assertIsNone(type_range({"name": "a", "type": "uint8", "choices": {"off": 0}}))

    def test_plage_effective(self):
        f = {"name": "a", "type": "uint8", "factor": 0.5, "max": 100}
        self.assertEqual(effective_range(f), (0.0, 100.0, "type", "json"))
        self.assertEqual(effective_range({"name": "a", "type": "float"}), (None, None, None, None))

    def test_message_hors_type_en_unite_reelle(self):
        f = {"name": "p", "type": "uint8", "factor": 0.1, "unit": "mW"}
        with self.assertRaises(ValueError) as ctx:
            encode_field(f, 30)
        self.assertIn("0.0 mW à 25.5 mW", str(ctx.exception))

    def test_entier_avec_choix(self):
        f = {"name": "st", "type": "uint8", "choices": {"off": 0, "on": 1}}
        self.assertEqual(to_hex(encode_field(f, "on")), "01")
        self.assertEqual(decode_fields([f], b"\x00")[0][0].text, "off (0)")
        with self.assertRaises(ValueError):
            parse_library_file({"commands": [{"name": "x", "id": 1, "tx": [
                {"name": "a", "type": "float", "choices": {"x": 1}}]}]})

    def test_defaut_ramene_dans_la_plage(self):
        f = {"name": "v", "type": "uint16", "factor": 0.001, "offset": 2.5}   # plage 2.5 à 68.035
        self.assertEqual(to_hex(encode_fields([f], {})), "00 00")             # défaut 2.5 -> brut 0


class TestRaw(unittest.TestCase):
    """Type raw : octets bruts sans conversion ; "count" (ou RAW[n]) = nombre d'octets."""

    def test_raw_taille_fixe(self):
        f = {"name": "r", "type": "raw", "count": 3}
        self.assertEqual(field_size(f), 3)
        self.assertEqual(to_hex(encode_field(f, "01 02 03")), "01 02 03")
        self.assertEqual(to_hex(encode_fields([f], {})), "00 00 00")          # défaut : des 00
        with self.assertRaises(ValueError):
            encode_field(f, "01 02")                                        # 2 octets au lieu de 3
        fields, errors = decode_fields([f, {"name": "x", "type": "uint8"}], bytes.fromhex("AA BB CC 07"))
        self.assertEqual([(x.name, x.text) for x in fields], [("r", "AA BB CC"), ("x", "7")])

    def test_raw_notation_et_variable(self):
        self.assertEqual(field_size({"name": "r", "type": "RAW[2]"}), 2)
        self.assertIsNone(field_size({"name": "r", "type": "raw"}))         # variable : dernier champ
        fields, _ = decode_fields([{"name": "r", "type": "raw"}], bytes.fromhex("01 02 03 04"))
        self.assertEqual(fields[0].text, "01 02 03 04")
        with self.assertRaises(ValueError):
            parse_library_file({"commands": [{"name": "x", "id": 1, "tx": [
                {"name": "r", "type": "raw"}, {"name": "b", "type": "uint8"}]}]})


class TestBibliotheque(unittest.TestCase):
    """Bibliothèque de commandes : fichiers d'essai de tests/data/ (appareil fictif)."""
    DATA = ROOT / "tests" / "data"

    def test_fichiers_d_essai(self):
        lib = load_library(self.DATA / "commands")
        self.assertEqual(lib.problems, [])
        self.assertEqual(len(lib.commands), 4)
        get, set_ = lib.by_id(0x0010), lib.by_id(0x8010)
        self.assertEqual((get.name, set_.name), ("Lire l'état", "Écrire l'état"))
        self.assertEqual(get.text("en")[0], "Read state")
        self.assertEqual(lib.by_id(0x0030).rx[0]["type"], "F32[2]")
        self.assertEqual(set_.label, "TEST / Écrire l'état (0x8010)")
        self.assertEqual([p["name"] for p in set_.presets], ["Marche", "Arrêt"])
        # les fichiers de commandes n'ajoutent pas de messages « frame »
        messages, errors = load_folder(self.DATA / "commands")
        self.assertEqual((messages, errors), ([], []))
        messages, errors = load_folder(self.DATA / "messages")
        self.assertEqual((len(messages), errors), (7, []))

    def test_ancien_prefixe_accepte(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Message_Ancien.json").write_text(json.dumps({"messages": [{"name": "a", "frame": ["01"]}]}))
            (Path(d) / "Msg_Nouveau.json").write_text(json.dumps({"messages": [{"name": "b", "frame": ["02"]}]}))
            messages, errors = load_folder(d)
        self.assertEqual([(m["group"], m["name"]) for m in messages], [("Ancien", "a"), ("Nouveau", "b")])

    def test_presets(self):
        lib = load_library(self.DATA / "commands")
        cmd = lib.by_id(0x8020)                          # Écrire l'adresse IP
        preset = cmd.presets[0]["values"]
        self.assertEqual(to_hex(encode_fields(cmd.tx, preset)), "C0 A8 01 64")
        with self.assertRaises(ValueError):
            parse_library_file({"commands": [{"name": "x", "id": 1, "tx": [{"name": "a"}],
                                              "presets": [{"name": "p", "values": {"b": 1}}]}]})

    def test_definitions_invalides(self):
        bad = [
            {"commands": [{"name": "x"}]},
            {"commands": [{"name": "x", "id": 1, "tx": [{"name": "a", "type": "u12"}]}]},
            {"commands": [{"name": "x", "id": 1, "tx": [{"name": "a", "type": "hex"}, {"name": "b"}]}]},
            {"commands": [{"name": "x", "id": 1, "tx": [{"name": "a", "factor": 0}]}]},
            {"commands": [{"name": "x", "id": 1, "tx": [{"name": "a", "max": 5, "default": 9}]}]},
        ]
        for data in bad:
            with self.assertRaises(ValueError):
                parse_library_file(data)

    def test_fichiers_d_un_autre_protocole(self):
        import json
        import tempfile
        cmd = {"name": "C", "id": "0x10", "tx": [], "rx": []}
        with tempfile.TemporaryDirectory() as folder:
            for name, proto in (("Msg_A.json", "Modbus RTU"), ("Msg_B.json", ["Autre", "Encore"]), ("Msg_C.json", None)):
                data = {"commands": [dict(cmd, id=hex(0x10 + len(name) + ord(name[4])))]}
                if proto:
                    data["protocol"] = proto
                Path(folder, name).write_text(json.dumps(data), encoding="utf-8")
            lib = load_library(folder, "modbus rtu")
            self.assertEqual(len(lib.commands), 2)                          # A (même protocole) et C (tous)
            self.assertEqual(lib.skipped, [("Msg_B.json", "Autre, Encore")])
            self.assertEqual(len(load_library(folder).commands), 3)         # sans protocole : tout est lu

    def test_commandes_masquees(self):
        """"hidden" : absente des listes (visible()), reconnue au décodage ; la visible passe
        avant la masquée au même COMMAND ID ; "hidden" au niveau du fichier vaut pour toutes."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Msg_A.json").write_text(json.dumps({"commands": [
                {"name": "Lire", "id": "0x10"},
                {"name": "Ancien nom", "id": "0x10", "hidden": True},      # même ID, sans conflit
                {"name": "Obsolète", "id": "0x20", "hidden": True},
            ]}), encoding="utf-8")
            Path(folder, "Msg_B.json").write_text(json.dumps({"hidden": True, "commands": [
                {"name": "Interne", "id": "0x30"},
                {"name": "Remise à zéro", "id": "0x40", "hidden": False},  # la commande l'emporte
            ]}), encoding="utf-8")
            lib = load_library(folder)
        self.assertEqual(lib.problems, [])
        self.assertEqual(len(lib.commands), 5)
        self.assertEqual(lib.hidden_count(), 3)
        self.assertEqual([c.name for c in lib.visible()], ["Lire", "Remise à zéro"])
        self.assertEqual(len(lib.visible(show_hidden=True)), 5)
        self.assertEqual(lib.by_id(0x10).name, "Lire")                     # visible prioritaire
        self.assertEqual(lib.find(0x10).name, "Lire")
        self.assertEqual(lib.by_id(0x20).name, "Obsolète")                 # masquée, mais reconnue
        self.assertEqual(lib.find(0x30).name, "Interne")
        # deux commandes visibles au même ID : toujours signalé
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Msg_C.json").write_text(json.dumps({"commands": [
                {"name": "A", "id": "0x10"}, {"name": "B", "id": "0x10"}]}), encoding="utf-8")
            self.assertEqual(len(load_library(folder).problems), 1)

    def test_describe(self):
        lib = load_library(self.DATA / "commands")
        cmd = lib.by_id(0x0010)
        d = decode(build_response(3, 0, b"\x01"), RESPONSE)
        self.assertEqual(describe(d, cmd, lib), "réponse #0x03 · Lire l'état · erreur 0 (OK) · 1 o · CRC OK")
        fields, _ = decode_fields(cmd.rx, b"\x01")
        self.assertEqual(fields[0].text, "marche (1)")
        d = decode(build_response(3, 1), RESPONSE)
        self.assertEqual(describe(d, None, lib), "réponse #0x03 · erreur 1 (Commande inconnue) · 0 o · CRC OK")
        lib.language = "en"
        self.assertEqual(lib.error_text(1), "Unknown command")

    def test_choix_en_hexa(self):
        f = {"name": "state", "type": "uint16", "choices": {"marche": "0xFF00", "arrêt": "0x0000"}}
        self.assertEqual(to_hex(encode_field(f, "marche")), "FF 00")
        self.assertEqual(decode_fields([f], bytes.fromhex("FF 00"))[0][0].text, "marche (65280)")

    def test_bcd(self):
        little = ProtocolConfig(byte_order="little")
        f = {"name": "id", "type": "bcd", "length": 4}
        self.assertEqual(to_hex(encode_field(f, 12345678, little)), "78 56 34 12")
        self.assertEqual(to_hex(encode_field(f, 12345678)), "12 34 56 78")          # big endian
        self.assertEqual(decode_fields([f], bytes.fromhex("78 56 34 12"), little)[0][0].text, "12345678")
        self.assertIn("BCD invalide", decode_fields([f], bytes.fromhex("7A 56 34 12"), little)[0][0].text)
        with self.assertRaises(ValueError):
            encode_field(f, 123456789)


class TestOrdreOpcode(unittest.TestCase):
    def test_cle(self):
        from core.commands import opcode_key
        ids = [0x8000002A, 0x00000004, 0x0000002A, 0x80000004, 0x00000003 | 0x80000000, 0x13000100]
        self.assertEqual([hex(i) for i in sorted(ids, key=opcode_key)],
                         ["0x80000003", "0x4", "0x80000004", "0x2a", "0x8000002a", "0x13000100"])

    def test_bibliotheque_rangee(self):
        import json, tempfile
        from core.commands import load_library
        with tempfile.TemporaryDirectory() as d:
            Path(d, "Msg_B.json").write_text(json.dumps({"commands": [
                {"name": "Set b", "id": "0x80000010"}, {"name": "Get a", "id": "0x00000002"}]}), encoding="utf-8")
            Path(d, "Msg_A.json").write_text(json.dumps({"commands": [
                {"name": "Get b", "id": "0x00000010"}, {"name": "Set a", "id": "0x80000002"}]}), encoding="utf-8")
            lib = load_library(d)
            self.assertEqual([c.name for c in lib.commands], ["Get a", "Set a", "Get b", "Set b"])


class TestConversionData(unittest.TestCase):
    """DATA brute <-> valeurs saisissables (onglet Manuel, messages de protocole)."""
    def test_aller_retour(self):
        from core.commands import encode_field, input_text, split_data
        from core.protocol import DEFAULT_PROTOCOL as P
        defs = [{"name": "mode", "type": "uint8", "choices": {"arret": 0, "marche": 1}},
                {"name": "consigne", "type": "int16", "factor": 0.1, "unit": "°C"},
                {"name": "registre", "type": "uint16"},
                {"name": "ip", "type": "uint8", "count": 4, "format": "ip"}]
        data = b"".join(encode_field(f, v, P) for f, v in zip(defs, ["marche", "23.5", "0x0102", "192.168.1.10"]))
        parts = split_data(defs, data, P)
        self.assertEqual([input_text(f, r, P) for f, r in parts], ["marche", "23.5", "258", "192.168.1.10"])
        self.assertEqual(input_text(defs[2], parts[2][1], P, hexa=True), "0x0102")
        for (f, r) in parts:
            for hexa in (False, True):
                self.assertEqual(encode_field(f, input_text(f, r, P, hexa), P), r)
        self.assertIsNone(split_data(defs, data[:-1], P))           # DATA trop courte
        self.assertIsNone(split_data(defs, data + b"\x00", P))      # octet en trop

    def test_entier_sans_commande(self):
        from core.commands import int_bytes, int_text
        self.assertEqual(int_text(bytes.fromhex("DC05"), "little"), "1500")
        self.assertEqual(int_text(bytes.fromhex("DC05"), "little", hexa=True), "0x05DC")
        self.assertEqual(int_text(bytes.fromhex("05DC"), "big"), "1500")
        self.assertEqual(int_bytes("0x5DC", "little", 2), bytes.fromhex("DC05"))
        self.assertEqual(int_bytes("1", "little", 2), bytes.fromhex("0100"))        # garde 2 octets
        self.assertEqual(int_bytes("70000", "little", 2), bytes.fromhex("701101"))  # ne tient pas : 3 octets
        self.assertEqual(int_bytes("", "little", 2), b"")
        with self.assertRaises(ValueError):
            int_bytes("abc")

    def test_lectures_possibles(self):
        from core.commands import raw_guess
        self.assertEqual(raw_guess(bytes.fromhex("DC05")), "1500 (0x05DC)")
        self.assertEqual(raw_guess(bytes.fromhex("FF")), "255 (0xFF) · signé -1")
        self.assertIn("float 75", raw_guess(bytes.fromhex("00009642")))
        self.assertEqual(raw_guess(b""), "")
        self.assertEqual(raw_guess(bytes(9)), "")


if __name__ == "__main__":
    unittest.main()
