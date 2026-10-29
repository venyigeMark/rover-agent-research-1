import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "controllers"))

import kor_metrika as km  # noqa: E402


def lepes(run_id, x, z, utkozes=0):
    return {
        "run_id": run_id,
        "privilegizalt_diagnosztika": {"position": {"x": x, "z": z}, "collision_count": utkozes},
    }


def kor_poziciok(hossz, sugar, lepes_m=0.08, korok=1.05):
    """A stadion kozepvonalan haladva, valamivel tobb mint egy kor."""
    fel = hossz / 2
    kerulet = 2 * hossz + 2 * math.pi * sugar
    pontok = []
    for i in range(int(korok * kerulet / lepes_m)):
        s = (i * lepes_m) % kerulet
        if s < hossz:
            pontok.append((sugar, -fel + s))
            continue
        s -= hossz
        if s < math.pi * sugar:
            a = s / sugar
            pontok.append((sugar * math.cos(a), fel + sugar * math.sin(a)))
            continue
        s -= math.pi * sugar
        if s < hossz:
            pontok.append((-sugar, fel - s))
            continue
        s -= hossz
        a = math.pi + s / sugar
        pontok.append((sugar * math.cos(a), -fel + sugar * math.sin(a)))
    return pontok


class GeometriaTest(unittest.TestCase):
    def test_tavolsag_a_palya_meretetol_fugg(self):
        self.assertAlmostEqual(km.tavolsag(4.5, 0.0, 14.0, 4.5), 0.0)
        self.assertAlmostEqual(km.tavolsag(4.5, 0.0, 12.0, 4.0), 0.5)
        self.assertAlmostEqual(km.tavolsag(0.0, 7.0 + 4.5, 14.0, 4.5), 0.0)

    def test_nincs_fantom_iv_a_palya_belsejeben(self):
        self.assertGreater(km.tavolsag(0.0, 2.0, 12.0, 4.0), 3.0)

    def test_szcenariobol_olvassa_a_meretet(self):
        geometria, forras = km.szcenario_geometria("stadium-test-holdout-always-visible")
        self.assertEqual(geometria, (14.0, 4.5, 0.16))
        self.assertEqual(forras, "stadium-test-holdout-always-visible")

    def test_ismeretlen_szcenario_alapertek(self):
        geometria, forras = km.szcenario_geometria("nincs-ilyen")
        self.assertEqual(geometria, km.ALAP_GEOMETRIA)
        self.assertEqual(forras, "alapertelmezett")


class SikerTest(unittest.TestCase):
    def futtat(self, palyaelhagyas, utkozes=0):
        with tempfile.TemporaryDirectory() as d:
            naplo = Path(d) / "kiserlet_naplo.jsonl"
            sorok = [
                lepes("r1", x, z, utkozes if i > 5 else 0)
                for i, (x, z) in enumerate(kor_poziciok(14.0, 4.5))
            ]
            naplo.write_text("".join(json.dumps(s) + "\n" for s in sorok))
            meta = Path(d) / "kiserlet_naplo_meta.jsonl"
            meta.write_text(
                json.dumps({"run_id": "r1", "scenario": "stadium-test-holdout-always-visible"})
                + "\n"
            )
            futas = Path(d) / "m09_runs.jsonl"
            futas.write_text(json.dumps({"run_id": "r1", "palyaelhagyas": palyaelhagyas}) + "\n")
            return km.kiertekel(naplo, futas, None)[0]

    def test_sikeres_futas(self):
        e = self.futtat(False)
        self.assertTrue(e["teljes_kor"])
        self.assertEqual(e["geometria"], "stadium-test-holdout-always-visible")
        self.assertGreater(e["vonalon_arany"], 0.95)
        self.assertTrue(e["sikeres"])

    def test_palyaelhagyas_nem_sikeres(self):
        self.assertFalse(self.futtat(True)["sikeres"])

    def test_utkozes_nem_sikeres(self):
        self.assertFalse(self.futtat(False, utkozes=1)["sikeres"])


if __name__ == "__main__":
    unittest.main()
