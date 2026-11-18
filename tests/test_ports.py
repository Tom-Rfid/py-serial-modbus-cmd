"""
Tests de la liste des ports série (core/serial_link.py) : filtre des adaptateurs FTDI.

    python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import serial_link  # noqa: E402
from core.edition import load_edition, port_options  # noqa: E402
from core.port_filter import enabled_ids  # noqa: E402
from core.serial_link import PortInfo, list_serial_ports  # noqa: E402

PRESENTS = [
    SimpleNamespace(device="COM10", description="USB Serial Port", vid=0x0403, pid=0x6015),   # FTDI FT-X
    SimpleNamespace(device="COM3", description="USB-SERIAL CH340", vid=0x1A86, pid=0x7523),   # CH340
    SimpleNamespace(device="COM4", description="USB Serial Port", vid=0x0403, pid=0x6001),    # FTDI FT232R
    SimpleNamespace(device="COM1", description="Port de communication", vid=None, pid=None),  # port natif
    SimpleNamespace(device="COM5", description="FTDI inconnu", vid=0x0403, pid=0x1234),       # PID non listé
    SimpleNamespace(device="COM7", description="Lien série standard sur Bluetooth", vid=None, pid=None,
                    hwid="BTHENUM\\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0000"),     # Bluetooth
    SimpleNamespace(device="/dev/rfcomm0", description="n/a", vid=None, pid=None, hwid="n/a"),  # Bluetooth Linux
]


class TestFiltreFTDI(unittest.TestCase):
    def test_is_ftdi(self):
        self.assertTrue(PortInfo("COM4", "", 0x0403, 0x6001).is_ftdi())
        self.assertFalse(PortInfo("COM3", "", 0x1A86, 0x7523).is_ftdi())
        self.assertFalse(PortInfo("COM1", "").is_ftdi())

    def test_liste(self):
        with mock.patch.object(serial_link.list_ports, "comports", return_value=PRESENTS):
            tous = [p.device for p in list_serial_ports()]
            self.assertIn("COM7", tous)
            self.assertEqual([p.device for p in list_serial_ports(hide_bluetooth=True)],
                             ["COM1", "COM3", "COM4", "COM5", "COM10"])
            self.assertEqual([p.device for p in list_serial_ports(only_ftdi=True)], ["COM4", "COM10"])

    def test_bluetooth(self):
        self.assertTrue(PortInfo("COM7", "Standard Serial over Bluetooth link").is_bluetooth())
        self.assertTrue(PortInfo("COM8", "x", hwid="BTHENUM\\{…}").is_bluetooth())
        self.assertTrue(PortInfo("/dev/rfcomm0", "n/a").is_bluetooth())
        self.assertFalse(PortInfo("COM4", "USB Serial Port", 0x0403, 0x6001, "USB VID:PID=0403:6001").is_bluetooth())

    def test_liste_enable_disable(self):
        # "enabled": false retire un adaptateur ; VID / PID en texte hexa ou en nombre
        filtre = [{"name": "FT232R", "vid": "0x0403", "pid": "0x6001", "enabled": True},
                  {"name": "FT-X", "vid": 0x0403, "pid": 0x6015, "enabled": False},
                  {"name": "CH340", "vid": "0x1A86", "pid": "0x7523"},          # enabled absent = true
                  {"name": "incomplet", "vid": "0x0403"}]                       # ignoré
        ids = enabled_ids(filtre)
        self.assertEqual(ids, {(0x0403, 0x6001), (0x1A86, 0x7523)})
        with mock.patch.object(serial_link.list_ports, "comports", return_value=PRESENTS):
            self.assertEqual([p.device for p in list_serial_ports(usb_ids=ids, hide_bluetooth=True)],
                             ["COM3", "COM4"])

    def test_options_d_edition(self):
        # Sans clé "ports" : Bluetooth masqué, filtre FTDI décoché
        o = port_options({})
        self.assertEqual((o["hide_bluetooth"], o["filter_label"], o["filter_default"]), (True, "FTDI", False))
        self.assertEqual(len(enabled_ids(o["filter"])), 5)
        o = port_options(load_edition(ROOT))                    # edition.json de cette version
        self.assertTrue(o["hide_bluetooth"])


if __name__ == "__main__":
    unittest.main()
