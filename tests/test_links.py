"""Tests du découpage des trames, de la liaison TCP et du choix série / TCP."""
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.framing import FrameSplitter  # noqa: E402
from core.jsonc import loads, strip_comments  # noqa: E402
from core.link_switch import LinkSwitch  # noqa: E402
from core.serial_link import SerialLink  # noqa: E402
from core.tcp_link import TcpLink  # noqa: E402


class TestDecoupage(unittest.TestCase):
    def test_silence(self):
        s = FrameSplitter(gap_ms=20)
        self.assertEqual(s.feed(b"\xAA\x55", 0.0), [])
        self.assertEqual(s.feed(b"\x01", 0.010), [])           # 10 ms : même trame
        self.assertEqual(s.tick(0.040), [b"\xAA\x55\x01"])     # 30 ms de silence : finie
        self.assertEqual(s.tick(0.100), [])

    def test_delimiteur(self):
        s = FrameSplitter(gap_ms=1000, frame_end=b"\r\n")
        self.assertEqual(s.feed(b":0103\r\n:01", 0.0), [b":0103\r\n"])     # coupée sans attendre
        self.assertEqual(s.feed(b"04\r\n", 0.001), [b":0104\r\n"])
        self.assertEqual(s.flush(), b"")


class TestJsonCommentaires(unittest.TestCase):
    def test_commentaires(self):
        text = '{ // a\n "u": "http://x//y", /* b\n c */ "q": "\\"//" }'
        self.assertEqual(loads(text), {"u": "http://x//y", "q": '"//'})
        self.assertEqual(strip_comments("a /* x\ny */ b").count("\n"), 1)   # lignes conservées


class TestTcp(unittest.TestCase):
    def test_echange(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def server():
            conn, _ = srv.accept()
            data = conn.recv(100)
            conn.sendall(data[:2] + bytes.fromhex("00 00 00 03 01 83 02"))
            time.sleep(0.1)
            conn.close()

        threading.Thread(target=server, daemon=True).start()
        link = LinkSwitch(SerialLink(), TcpLink(), "tcp")
        link.gap_ms = 10
        link.connect("127.0.0.1", port)
        self.assertEqual(link.describe(), f"TCP 127.0.0.1:{port}")
        with self.assertRaises(ConnectionError):
            link.mode = "serial"                       # pas de changement pendant une connexion
        link.write(bytes.fromhex("00 07 00 00 00 06 01 03 00 00 00 0A"))
        self.assertEqual(link.events.get(timeout=2), ("rx", bytes.fromhex("00 07 00 00 00 03 01 83 02")))
        self.assertEqual(link.events.get(timeout=2)[0], "lost")       # le serveur ferme
        link.disconnect()
        srv.close()
        link.mode = "serial"
        self.assertEqual(link.links["serial"].gap_ms, 10)            # réglage commun aux deux liaisons

    def test_refus(self):
        with self.assertRaises(ConnectionError) as ctx:
            TcpLink().connect("127.0.0.1", 1)
        self.assertIn("127.0.0.1:1", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
