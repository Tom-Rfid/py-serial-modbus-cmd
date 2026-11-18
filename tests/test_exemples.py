"""
Tests des protocoles publics fournis avec la version Techmelec (Modbus, M-Bus, PROFIBUS)
et de leurs commandes d'exemple (appareils fictifs).

    python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.commands import decode_fields, load_library  # noqa: E402
from core.frames import build_frame, defaults_for, to_hex  # noqa: E402
from core.messages import load_folder  # noqa: E402
from core.protocol import QUERY, RESPONSE, load_protocol  # noqa: E402


class TestBibliothequeExemples(unittest.TestCase):
    """Fichiers d'exemple Modbus / M-Bus / PROFIBUS : chargement et commandes départagées."""

    def lib_of(self, name):
        p = load_protocol(ROOT / "protocols" / name)
        lib = load_library(p.commands_dir, p.name)
        self.assertEqual(lib.problems, [])
        return p, lib

    def test_modbus_match(self):
        p, lib = self.lib_of("modbus_rtu.json")
        a = lib.find(3, bytes.fromhex("00 00 00 02"), p)
        b = lib.find(3, bytes.fromhex("00 02 00 01"), p)
        self.assertEqual((a.name, b.name), ("Lire consigne et mode", "Lire puissance de sortie"))
        self.assertEqual(a.id_digits, 2)
        self.assertEqual(a.label, "READ / Lire consigne et mode (0x03)")
        self.assertEqual(a.text("en")[0], "Read setpoint and mode")

    def test_modbus_standard(self):
        """Msg_Modbus_Standard.json : toutes les fonctions publiques, génériques (sans "match")."""
        for name in ("modbus_rtu.json", "modbus_ascii.json", "modbus_tcp.json"):
            p, lib = self.lib_of(name)
            generic = {c.id for c in lib.commands if not c.match}
            self.assertEqual(generic, {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x0B, 0x0C,
                                       0x0F, 0x10, 0x11, 0x14, 0x15, 0x16, 0x17, 0x18, 0x2B}, name)
        p, lib = self.lib_of("modbus_rtu.json")
        # Registre sans commande précise : la commande générique sert de repli
        cmd = lib.find(3, bytes.fromhex("00 10 00 05"), p)
        self.assertEqual(cmd.name, "03 Lire registres de maintien")
        fields, errors = decode_fields(cmd.rx, bytes.fromhex("04 00 0A 01 02"), p)
        self.assertEqual(([f.text for f in fields][0], errors), ("4", []))
        self.assertEqual(lib.find(8, bytes.fromhex("00 00 A5 37"), p).name, "08 Diagnostic")
        self.assertEqual(lib.find(5, bytes.fromhex("00 0A FF 00"), p).name, "Commander relais d'alarme")
        self.assertEqual(lib.find(5, bytes.fromhex("00 01 FF 00"), p).name, "05 Écrire une bobine")

    def test_mbus_header_et_variante(self):
        p, lib = self.lib_of("mbus.json")
        cmd = lib.find(0x53, b"", p, {"CI": 0x52, "C": 0x53}, "Longue")
        self.assertEqual(cmd.name, "Sélection par adresse secondaire")
        self.assertEqual(lib.find(0x53, b"", p, {"CI": 0x50}).header, {"CI": "0x50"})

    def test_trames_de_reference(self):
        rtu = load_protocol(ROOT / "protocols" / "modbus_rtu.json")
        self.assertEqual(rtu.build_query(1, 3, bytes.fromhex("00 00 00 02")).hex(" ").upper(), "01 03 00 00 00 02 C4 0B")
        d = rtu.decode(bytes.fromhex("01 83 02 C0 F1"), RESPONSE)
        self.assertEqual((d.ok, d.variant, d.error), (True, "Exception", 2))
        ascii_ = load_protocol(ROOT / "protocols" / "modbus_ascii.json")
        self.assertEqual(ascii_.build_query(1, 3, bytes.fromhex("00 00 00 0A")), b":01030000000AF2\r\n")
        mbus = load_protocol(ROOT / "protocols" / "mbus.json")
        self.assertEqual(mbus.build(QUERY, b"", {"request_id": 5, "command_id": 0x5B}, variant="Courte").hex(" ").upper(),
                         "10 5B 05 60 16")

    def test_messages_de_l_onglet_manuel(self):
        messages, errors = load_folder(ROOT / "msgLibrary" / "msgManual")
        self.assertEqual((len(messages), errors), (21, []))
        # Trames Modbus RTU standard : CRC16 Modbus des exemples de la spécification
        frames = {m["name"]: to_hex(build_frame(m, defaults_for(m))) for m in messages}
        self.assertEqual(frames["Modbus 03 - lire registres de maintien"], "01 03 00 00 00 02 C4 0B")
        self.assertEqual(frames["Modbus 07 - lire état d'exception"], "01 07 41 E2")
        self.assertEqual(frames["Modbus 11 - identifiant esclave"], "01 11 C0 2C")
        self.assertEqual(frames["Modbus 2B - lire identification"], "01 2B 0E 01 00 70 77")


if __name__ == "__main__":
    unittest.main()
