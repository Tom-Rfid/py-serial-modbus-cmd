"""Tests de la traduction de l'interface (ui/i18n.py, ui/lang/en.json)."""
import ast
import os
import string
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui.i18n import _, language, set_language, tr  # noqa: E402


def ui_keys():
    """Tous les textes passés à _() dans ui/."""
    keys = set()
    for path in (ROOT / "ui").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
    return keys


class TestTraduction(unittest.TestCase):
    def setUp(self):
        set_language("en")

    def tearDown(self):
        set_language("fr")

    def test_langue(self):
        self.assertEqual(language(), "en")
        self.assertEqual(_("Envoyer"), "Send")
        self.assertEqual(_("Connecté : {0}").format("COM3"), "Connected: COM3")
        self.assertEqual(_("texte inconnu"), "texte inconnu")          # absent : reste en français
        set_language("fr")
        self.assertEqual(_("Envoyer"), "Envoyer")
        set_language("xx")                                              # inconnue : français
        self.assertEqual(language(), "fr")

    def test_tous_les_textes_sont_traduits(self):
        from ui.i18n import _state
        set_language("en")
        missing = sorted(k for k in ui_keys() if k not in _state["strings"])
        self.assertEqual(missing, [])

    def test_memes_champs_de_format(self):
        from ui.i18n import _state
        fmt = string.Formatter()
        for fr, en in _state["strings"].items():
            fields = lambda s: sorted(f for _, f, _, _ in fmt.parse(s) if f is not None)
            self.assertEqual(fields(fr), fields(en), fr)

    def test_messages_du_coeur(self):
        cases = {
            "réponse #0x05": "response #0x05",
            "erreur 1 (Commande inconnue)": "error 1 (Commande inconnue)",
            "HCRC incorrect": "HCRC wrong",
            "L (répété) différent de L": "L (répété) differs from L",
            "trame tronquée : DATA incomplet, 2 octet(s) en trop": "truncated frame: DATA incomplete, 2 extra byte(s)",
            "COM3 déjà utilisé par un autre programme": "COM3 already used by another program",
            "0x00 : aucun": "0x00 : none",
            "fin de trame '\\r\\n' absente": "frame end '\\r\\n' missing",
            "3 identique, 1 différent": "3 identical, 1 different",
            "modbus.json : rx [Normale] : champ 'L' : value ne tient pas sur 1 bit":
                "modbus.json: rx [Normale]: field 'L': value does not fit in 1 bit",
        }
        for fr, en in cases.items():
            self.assertEqual(tr(fr), en, fr)
        set_language("fr")
        self.assertEqual(tr("HCRC incorrect"), "HCRC incorrect")


if __name__ == "__main__":
    unittest.main()
