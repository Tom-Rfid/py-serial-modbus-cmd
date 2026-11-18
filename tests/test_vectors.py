"""
Vérifie que core/frames.py produit toujours les trames de tests/vectors.json.

    python -m unittest discover tests
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.frames import build_frame, defaults_for, to_hex  # noqa: E402

VECTORS = json.loads((ROOT / "tests" / "vectors.json").read_text(encoding="utf-8"))["cases"]


class TestVectors(unittest.TestCase):
    def test_vectors(self):
        """Chaque cas : trame identique à celle attendue, ou erreur si error=True."""
        for c in VECTORS:
            # subTest : en cas d'échec, le nom du cas fautif est affiché
            # et les autres cas sont quand même testés
            with self.subTest(c["name"]):
                values = {**defaults_for(c["message"]), **c["values"]}
                if c.get("error"):
                    with self.assertRaises(Exception):
                        build_frame(c["message"], values)
                else:
                    self.assertEqual(to_hex(build_frame(c["message"], values)), c["frame"])


if __name__ == "__main__":
    unittest.main()
