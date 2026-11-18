"""
Tests de la trace et du replay (core/trace.py).

    python -m unittest discover tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trace import (  # noqa: E402
    TraceRecorder, analyze, compare, compare_responses, exchanges, judge_exchange, load_trace, replay_delays,
    save_trace, TraceDocument, TraceEvent,
)


class FakeClock:
    """Horloge pilotée par le test (secondes)."""
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def record(path):
    """Trace type : 3 requêtes, réponses à 40 ms, 20 ms, et la dernière sans réponse."""
    clock = FakeClock()
    rec = TraceRecorder(path, clock=clock)
    rec.write("TX", bytes.fromhex("A5 5A 00"), "Lire l'état #0")
    clock.t += 0.040
    rec.write("RX", bytes.fromhex("A5 00 00 01"))
    clock.t += 0.260                           # TX suivant à 300 ms
    rec.write("TX", bytes.fromhex("A5 5A 01"), "Lire mesures #1")
    clock.t += 0.020
    rec.write("RX", bytes.fromhex("A5 01 00 04"))
    clock.t += 0.480                           # TX suivant à 800 ms
    rec.write("TX", bytes.fromhex("A5 02 09"))
    rec.close()
    return rec


class TestTrace(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "traces" / "essai.csv"     # dossier créé si besoin

    def tearDown(self):
        self.dir.cleanup()

    def test_enregistrement_et_relecture(self):
        rec = record(self.path)
        self.assertEqual(rec.count, 5)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "t_ms;delta_ms;dir;len;hex;label")
        self.assertEqual(lines[1], "0.0;0.0;TX;3;A5 5A 00;Lire l'état #0")
        self.assertEqual(lines[2], "40.0;40.0;RX;4;A5 00 00 01;")
        events = load_trace(self.path)
        self.assertEqual([(e.direction, round(e.t_ms)) for e in events],
                         [("TX", 0), ("RX", 40), ("TX", 300), ("RX", 320), ("TX", 800)])
        self.assertEqual(events[0].label, "Lire l'état #0")

    def test_analyse(self):
        record(self.path)
        events = load_trace(self.path)
        ex = exchanges(events)
        self.assertEqual([round(x.gap_ms) for x in ex], [0, 300, 500])
        self.assertEqual([x.latency_ms and round(x.latency_ms) for x in ex], [40, 20, None])
        a = analyze(events)
        self.assertEqual((a.n_tx, a.n_rx, a.unanswered, round(a.duration_ms)), (3, 2, 1, 800))
        self.assertEqual([round(v) for v in a.gaps], [300, 400, 500])
        self.assertEqual([round(v) for v in a.latencies], [20, 30, 40])
        self.assertIn("3 TX · 2 RX", a.text())

    def test_delais_de_replay(self):
        record(self.path)
        ex = exchanges(load_trace(self.path))
        self.assertEqual([round(d) for d in replay_delays(ex)], [0, 300, 500])
        self.assertEqual([round(d) for d in replay_delays(ex, speed=2)], [0, 150, 250])
        self.assertEqual(replay_delays(ex, mode="fixed", fixed_ms=50), [0.0, 50.0, 50.0])

    def test_sauvegarde_apres_modification(self):
        record(self.path)
        events = load_trace(self.path)
        events[1] = TraceEvent(events[1].t_ms, "RX", bytes.fromhex("A5 00 00 02"), "")
        events.insert(2, TraceEvent(150.0, "TX", bytes.fromhex("A5 05 07"), "ajoutée"))
        out = self.path.with_name("modif.csv")
        save_trace(out, events)
        again = load_trace(out)
        self.assertEqual([(e.direction, e.data, e.label) for e in again],
                         [(e.direction, e.data, e.label) for e in events])
        self.assertEqual(out.read_text(encoding="utf-8").splitlines()[3], "150.0;110.0;TX;3;A5 05 07;ajoutée")

    def test_delai_negatif(self):
        ev = [TraceEvent(100, "TX", b"\x01"), TraceEvent(50, "TX", b"\x02")]
        self.assertEqual(replay_delays(exchanges(ev)), [0.0, 0.0])

    def test_fichier_ecrit_a_la_main(self):
        # Virgule comme séparateur, commentaire, colonnes minimales, t_ms absent
        self.path.parent.mkdir(parents=True)
        self.path.write_text("# test\ndir,hex\nTX,A5 00\nRX,A5 01\n", encoding="utf-8")
        events = load_trace(self.path)
        self.assertEqual([(e.direction, e.data) for e in events], [("TX", b"\xA5\x00"), ("RX", b"\xA5\x01")])
        self.path.write_text("dir;hex\nZZ;00\n", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            load_trace(self.path)
        self.assertIn("ligne 2", str(ctx.exception))


class TestComparaison(unittest.TestCase):
    def test_compare(self):
        self.assertEqual(compare(b"\x01\x02", b"\x01\x02"), (True, "identique"))
        ok, why = compare(bytes.fromhex("A5 00 00 12 34"), bytes.fromhex("A5 00 00 12 35"))
        self.assertEqual((ok, why), (False, "octet 4 : attendu 34, reçu 35"))
        ok, why = compare(bytes.fromhex("A5 00 00 12 34"), bytes.fromhex("A5 00 04"))
        self.assertIn("longueur : attendu 5, reçu 3", why)
        self.assertIn("octet 2 : attendu 00, reçu 04", why)
        ok, why = compare(bytes.fromhex("01 02 03 04"), bytes.fromhex("01 FF FF 04"))
        self.assertEqual(why, "octets 1-2 : attendu 02 03, reçu FF FF")

    def test_compare_responses(self):
        a, b = bytes.fromhex("A5 00"), bytes.fromhex("A5 01")
        self.assertEqual(compare_responses([a], [a])[0], "identique")
        self.assertEqual(compare_responses([a], [b])[0], "différent")
        self.assertEqual(compare_responses([a], [])[0], "sans réponse")
        self.assertEqual(compare_responses([], [a])[0], "réponse en trop")
        self.assertEqual(compare_responses([], [])[0], "aucune attendue")
        status, why = compare_responses([a, a], [a])
        self.assertEqual(status, "différent")
        self.assertIn("2 trame(s) attendue(s), 1 reçue(s)", why)


class TestTimeout(unittest.TestCase):
    A, B = bytes.fromhex("A5 00"), bytes.fromhex("A5 01")

    def test_a_temps(self):
        self.assertEqual(judge_exchange([self.A], [(40, self.A)], 500), ("identique", ""))
        self.assertEqual(judge_exchange([self.A], [(40, self.B)], 500)[0], "différent")

    def test_timeout(self):
        self.assertEqual(judge_exchange([self.A], [], 500), ("timeout", "aucune réponse en 500 ms"))
        status, why = judge_exchange([self.A], [(620, self.A)], 500)
        self.assertEqual(status, "timeout")
        self.assertIn("arrivée après 620 ms", why)

    def test_sans_reponse_attendue(self):
        self.assertEqual(judge_exchange([], [], 500)[0], "aucune attendue")
        self.assertEqual(judge_exchange([], [(30, self.A)], 500)[0], "réponse en trop")
        self.assertEqual(judge_exchange([], [(900, self.A)], 500)[0], "aucune attendue")   # tardive ignorée


class TestDocument(unittest.TestCase):
    """Trace ouverte dans l'onglet Replay : modifications, intervalle, renommage."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.dir.name)
        record(self.folder / "essai.csv")
        self.doc = TraceDocument(self.folder)
        self.doc.load(self.folder / "essai.csv")

    def tearDown(self):
        self.dir.cleanup()

    def test_intervalle_et_insertion(self):
        d = self.doc
        self.assertEqual([round(x) if x is not None else None for x in d.gaps(0)], [None, 40])
        self.assertEqual([round(x) for x in d.gaps(1)], [40, 260])
        row = d.insert_after(1, "TX", b"\x01", "milieu")         # entre 40 et 300 ms
        self.assertEqual((row, round(d.events[row].t_ms)), (2, 170))
        row = d.insert_after(len(d.events) - 1, "TX", b"\x02")   # fin : +100 ms
        self.assertEqual(round(d.events[row].t_ms), 900)
        self.assertTrue(d.modified)

    def test_cellules(self):
        d = self.doc
        self.assertTrue(d.set_cell(0, "label", "Statut"))
        self.assertFalse(d.set_cell(0, "label", "Statut"))         # inchangé
        d.set_cell(0, "hex", "A5 00 05")
        d.set_cell(0, "dir", "rx")
        d.set_cell(0, "t", "1,5")
        self.assertEqual((d.events[0].data, d.events[0].direction, d.events[0].t_ms), (b"\xA5\x00\x05", "RX", 1.5))
        for key, text, msg in (("hex", "zz", "hexa invalide"), ("hex", "", "au moins"), ("t", "x", "nombre"),
                               ("dir", "AB", "TX ou RX")):
            with self.assertRaises(ValueError) as ctx:
                d.set_cell(1, key, text)
            self.assertIn(msg, str(ctx.exception))

    def test_deplacer_supprimer_remplacer(self):
        d = self.doc
        first = d.events[0]
        self.assertEqual(d.move(0, 1), 1)
        self.assertEqual((d.events[1].data, d.events[1].t_ms), (first.data, 40.0))   # le temps reste en place
        self.assertIsNone(d.move(0, -1))
        d.replace(2, "TX", b"\xAA", "remplacée")
        self.assertEqual((d.events[2].data, round(d.events[2].t_ms)), (b"\xAA", 300))
        self.assertEqual(d.delete([3, 4]), 2)
        self.assertEqual(len(d.events), 3)

    def test_renommer(self):
        d = self.doc
        d.set_cell(0, "label", "modifiée")
        new = d.save_as_name("essai_v2")
        self.assertEqual(new.name, "essai_v2.csv")
        self.assertFalse((self.folder / "essai.csv").exists())     # renommé, pas copié
        self.assertEqual(load_trace(new)[0].label, "modifiée")
        record(self.folder / "autre.csv")
        with self.assertRaises(FileExistsError):
            d.save_as_name("autre")
        d.save_as_name("autre.csv", overwrite=True)                # remplacement confirmé
        self.assertEqual(load_trace(self.folder / "autre.csv")[0].label, "modifiée")
        for bad in ("", "a/b", "x:y"):
            with self.assertRaises(ValueError):
                d.save_as_name(bad)

    def test_nouvelle_trace(self):
        d = TraceDocument(self.folder)
        d.new()
        with self.assertRaises(ValueError):
            d.save()
        d.insert_after(None, "TX", b"\xA5")
        self.assertEqual(d.events[0].t_ms, 0.0)
        self.assertEqual(d.save_as_name("neuve"), self.folder / "neuve.csv")


if __name__ == "__main__":
    unittest.main()
