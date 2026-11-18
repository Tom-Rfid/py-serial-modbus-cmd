"""
Vérifie que core/protocol.py produit toujours les résultats de tests/protocol_vectors.json
(mêmes vecteurs que les tests TypeScript : js/test/protocol.test.ts).

Après une modification VOULUE du moteur : python tools/gen_protocol_vectors.py

    python -m unittest discover tests
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.frames import to_hex  # noqa: E402
from core.protocol import CRC_PRESETS, QUERY, RESPONSE, Protocol, ProtocolError, color_segments  # noqa: E402

VECTORS = json.loads((ROOT / "tests" / "protocol_vectors.json").read_text(encoding="utf-8"))
KINDS = {"tx": QUERY, "rx": RESPONSE}


class TestProtocolVectors(unittest.TestCase):
    def test_crc(self):
        for name, value in VECTORS["crc_check"].items():
            self.assertEqual(CRC_PRESETS[name].compute(b"123456789"), value, name)

    def test_protocoles(self):
        for case in VECTORS["protocols"]:
            p = Protocol(case["conf"])
            with self.subTest(case["name"]):
                for b in case["build"]:
                    if b.get("error"):
                        with self.assertRaises(ValueError):
                            p.build(KINDS[b["kind"]], bytes.fromhex(b["data"]), b["values"], variant=b["variant"])
                    else:
                        frame = p.build(KINDS[b["kind"]], bytes.fromhex(b["data"]), b["values"], variant=b["variant"])
                        self.assertEqual(to_hex(frame), b["frame"])
                for c in case["decode"]:
                    d = p.decode(bytes.fromhex(c["frame"]), KINDS[c["kind"]])
                    got = {"complete": d.complete, "ok": d.ok, "errors": d.errors, "extra": to_hex(d.extra),
                           "variant": d.variant,
                           "fields": [{"name": f.name, "start": f.start, "raw": to_hex(f.raw), "value": f.value,
                                       "ok": f.ok, "note": f.note, "role": f.role, "meaning": f.meaning}
                                      for f in d.fields],
                           "segments": [list(s) for s in color_segments(d)]}
                    self.assertEqual(got, {k: c[k] for k in got}, c["frame"])
                for m in case["matches"]:
                    self.assertEqual(p.matches(bytes.fromhex(m["frame"]), KINDS[m["kind"]]), m["result"])
                self.assertEqual(to_hex(p.crc_bytes(bytes.fromhex("01 03 00 00 00 0A"))), case["main_crc"])

    def test_confs_invalides(self):
        for c in VECTORS["invalid"]:
            with self.assertRaises(ProtocolError) as ctx:
                Protocol(c["conf"])
            self.assertEqual(str(ctx.exception), c["message"])


if __name__ == "__main__":
    unittest.main()
