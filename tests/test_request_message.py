"""
Tests des messages « de protocole » de l'onglet Manuel (core/request_message.py) :
trame construite par le protocole en cours, sauvegarde depuis l'onglet Protocole.

    python -m unittest discover tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.frames import build_frame, defaults_for  # noqa: E402
from core.messages import display_name, load_folder, load_messages, merge_messages  # noqa: E402
from core.protocol import DEFAULT_PROTOCOL as GENERIC, QUERY  # noqa: E402
from core.request_message import (build_request, is_request, make_request_message, params_of,  # noqa: E402
                                  SAVED_FILE, file_name_for, find_saved, save_message, save_message_file, saved_file_name,
                                  unique_name)


class TestMessageDeProtocole(unittest.TestCase):
    MSG = make_request_message("Écrire l'état", 0x8010, b"\x01", request_id=5, protocol="Exemple", id_digits=4)

    def test_format(self):
        self.assertEqual(self.MSG["request"], {"request_id": 5, "command_id": "0x8010", "data": "01"})
        self.assertTrue(is_request(self.MSG))
        self.assertEqual(list(params_of(self.MSG)), ["request_id", "command_id", "data"])
        self.assertEqual(defaults_for(self.MSG), {"request_id": "0x05", "command_id": "0x8010", "data": "01"})
        with self.assertRaises(ValueError):            # pas de "frame" : construit par le protocole
            build_frame(self.MSG, {})

    def test_trame_du_protocole(self):
        values = defaults_for(self.MSG)
        frame = build_request(self.MSG, values, GENERIC, QUERY)
        self.assertEqual(frame, GENERIC.build_query(5, 0x8010, b"\x01"))     # CRC compris
        values.update(request_id="0x06", data="02 03")                    # modifiés dans l'onglet Manuel
        self.assertEqual(build_request(self.MSG, values, GENERIC, QUERY), GENERIC.build_query(6, 0x8010, b"\x02\x03"))
        values["data"] = "zz"
        with self.assertRaises(ValueError):
            build_request(self.MSG, values, GENERIC, QUERY)

    def test_sauvegarde(self):
        with tempfile.TemporaryDirectory() as folder:
            path, replaced = save_message(folder, self.MSG)
            self.assertFalse(replaced)
            other = make_request_message("Lire l'état", 0x0010, b"", request_id=1, id_digits=4)
            save_message(folder, other)
            changed = make_request_message("Écrire l'état", 0x8010, b"\x00", request_id=5, id_digits=4)
            _path, replaced = save_message(folder, changed)                # même nom : remplacé
            self.assertTrue(replaced)
            messages, errors = load_folder(folder)
            self.assertEqual(errors, [])
            self.assertEqual([(m["group"], m["name"], m["request"]["data"]) for m in messages],
                             [("Sauvegardés", "Écrire l'état", "00"), ("Sauvegardés", "Lire l'état", "")])
            self.assertTrue(path.read_text(encoding="utf-8").startswith("//"))

    def test_fichier_choisi(self):
        self.assertEqual(saved_file_name("Essais"), "Msg_Essais.json")
        self.assertEqual(saved_file_name("Msg_Essais.json"), "Msg_Essais.json")
        self.assertEqual(saved_file_name("banc.json"), "Msg_banc.json")
        self.assertEqual(file_name_for("Set access level"), "Msg_Set_access_level.json")
        self.assertEqual(file_name_for("a/b:c?"), "Msg_abc.json")
        self.assertEqual(file_name_for("  "), SAVED_FILE)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "Msg_Banc.json")
            save_message_file(path, self.MSG)
            self.assertIsNotNone(find_saved(path, "Écrire l'état"))
            self.assertIsNone(find_saved(path, "autre"))
            self.assertEqual(unique_name(path, "Écrire l'état"), "Écrire l'état (2)")
            self.assertEqual(unique_name(path, "autre"), "autre")
            messages, _errors = load_folder(folder)
            self.assertEqual(messages[0]["group"], "Sauvegardés")   # tout fichier créé par Sauvegarder…

    def test_doublons(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            save_message(a, self.MSG)
            save_message(b, self.MSG)                               # même message ailleurs
            other = make_request_message("Écrire l'état", 0x8010, b"\x09", request_id=5, id_digits=4)
            save_message_file(Path(b, "Msg_Autre.json"), dict(other, group="Sauvegardés"))
            first, _ = load_folder(a)
            second = load_messages(Path(b, SAVED_FILE))
            merged, added, same = merge_messages(first, second)      # identique : ignoré
            self.assertEqual((len(merged), added, same), (1, 0, 1))
            self.assertNotIn("display", merged[0])
            merged, added, same = merge_messages(merged, load_messages(Path(b, "Msg_Autre.json")))
            self.assertEqual((len(merged), added, same), (2, 1, 0))  # même nom, contenu différent
            self.assertEqual([display_name(m) for m in merged],
                             [f"Écrire l'état  [{SAVED_FILE}]", "Écrire l'état  [Msg_Autre.json]"])

    def test_chargement_refuse_un_message_invalide(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Msg_X.json").write_text(json.dumps({"messages": [
                {"name": "x", "request": {"data": "01"}}]}), encoding="utf-8")     # command_id manquant
            _messages, errors = load_folder(folder)
            self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
