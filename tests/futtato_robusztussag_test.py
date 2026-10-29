#!/usr/bin/env python3
"""A futtato es a kliens robusztussagi javitasai (M13 elotti audit-pontok).

Ezt a fajlt Claude irta (lasd AI_USAGE.md), Dalma review-ja mellett.
Unity nelkul fut: a halozati reszt socketpair helyettesiti.

Futtatas:
    python3 tests/futtato_robusztussag_test.py
"""

from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

GYOKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GYOKER / "controllers"))

import baseline_line_follower as blf  # noqa: E402
import summarize_runs  # noqa: E402
from baseline_line_follower import (  # noqa: E402
    KERESES_LENGES_FOK,
    Allapot,
    FutasStatisztika,
    GatewayHiba,
    GatewayKliens,
    _szcenario_nev,
    akadaly_ellenorzes,
    egy_lepes_kereses,
)


def _kliens_paron(valaszolo) -> tuple[GatewayKliens, threading.Thread]:
    """GatewayKliens egy socketpair egyik vegen; a masikon `valaszolo(keres)` felel."""
    kliens_veg, szerver_veg = socket.socketpair()

    def szerver() -> None:
        hossz = int.from_bytes(szerver_veg.recv(4), "big")
        keres = json.loads(szerver_veg.recv(hossz).decode("utf-8"))
        valasz = valaszolo(keres)
        if valasz is not None:
            payload = json.dumps(valasz).encode("utf-8")
            szerver_veg.sendall(len(payload).to_bytes(4, "big") + payload)

    szal = threading.Thread(target=szerver, daemon=True)
    szal.start()
    kliens = GatewayKliens.__new__(GatewayKliens)
    kliens.socket = kliens_veg
    kliens.socket.settimeout(blf.VALASZ_TIMEOUT_S)
    kliens._szerver_veg = szerver_veg  # a teszt vegeig eletben tartjuk
    return kliens, szal


class SzcenarioNevTest(unittest.TestCase):
    def test_normal_nev(self) -> None:
        uzenet = {"message": "A rover visszaallt. scenario=stadium-train timescale=70"}
        self.assertEqual(_szcenario_nev(uzenet), "stadium-train")

    def test_ures_nev_nem_a_timescale(self) -> None:
        uzenet = {"message": "A rover visszaallt a kezdohelyzetbe. scenario= timescale=70"}
        self.assertEqual(_szcenario_nev(uzenet), "")

    def test_hianyzo_mezo(self) -> None:
        self.assertIsNone(_szcenario_nev({"message": "regi Unity, nincs mezo"}))


class ValaszEllenorzesTest(unittest.TestCase):
    def _kliens(self, valaszolo) -> GatewayKliens:
        kliens, _ = _kliens_paron(valaszolo)
        self.addCleanup(kliens._szerver_veg.close)
        self.addCleanup(kliens.socket.close)
        return kliens

    def test_sikeres_valasz_atmegy(self) -> None:
        kliens = self._kliens(
            lambda k: {"request_id": k["request_id"], "status": "completed", "state": "IDLE"}
        )
        self.assertEqual(kliens.kuld({"command": "observe"})["status"], "completed")

    def test_elutasitas_megallitja_a_futast(self) -> None:
        kliens = self._kliens(
            lambda k: {
                "request_id": k["request_id"],
                "status": "failed",
                "state": "ERROR",
                "error": {"code": 1300, "name": "INVALID_STATE", "message": "not IDLE"},
            }
        )
        with self.assertRaises(GatewayHiba) as ctx:
            kliens.kuld({"command": "move", "distance_m": 0.08, "max_speed": 0.2})
        self.assertIn("INVALID_STATE", str(ctx.exception))

    def test_mas_request_id_hiba(self) -> None:
        kliens = self._kliens(
            lambda k: {"request_id": "masik", "status": "completed", "state": "IDLE"}
        )
        with self.assertRaises(GatewayHiba):
            kliens.kuld({"command": "observe"})

    def test_timeout_ertheto_hibat_ad(self) -> None:
        eredeti = blf.VALASZ_TIMEOUT_S
        blf.VALASZ_TIMEOUT_S = 0.2
        try:
            kliens = self._kliens(lambda k: None)
            with self.assertRaises(ConnectionError) as ctx:
                kliens.kuld({"command": "turn", "angle_deg": 5.0, "max_angular_speed": 20.0})
            self.assertIn("turn", str(ctx.exception))
        finally:
            blf.VALASZ_TIMEOUT_S = eredeti


class KeresesNaplozasTest(unittest.TestCase):
    def test_spiral_lepes_a_move_parancsot_is_naplozza(self) -> None:
        class Stub:
            def kuld(self, parancs: dict[str, Any]) -> dict[str, Any]:
                if parancs["command"] == "observe":
                    oldal = {"white": False, "intensity": 0.0}
                    return {
                        "sensor_left": oldal,
                        "sensor_center": oldal,
                        "sensor_right": oldal,
                        "lidar_szektor_min": [5.0] * 6,
                    }
                return {"status": "completed"}

        class Naplo:
            def __init__(self) -> None:
                self.parancsok: list = []

            def rogzit(self, _lepes, _szenzor, parancsok, *_tobbi) -> None:
                self.parancsok.append(parancsok)

        naplo = Naplo()
        uj = egy_lepes_kereses(Stub(), FutasStatisztika(), [1], [len(KERESES_LENGES_FOK)], naplo, 0)
        self.assertIs(uj, Allapot.KERESES)
        self.assertEqual([p["command"] for p in naplo.parancsok[0]], ["turn", "move"])


class OsszesitoTest(unittest.TestCase):
    def test_regi_sorok_hianyzo_mezokkel_es_ures_sorral(self) -> None:
        with tempfile.TemporaryDirectory() as mappa:
            fajl = Path(mappa) / "runs.jsonl"
            fajl.write_text(
                '{"lepesek_szama": 10, "palyaelhagyas": false}\n\n'
                '{"parancsok_szama": 5, "vonalvesztesek_szama": 1, '
                '"akadaly_kerulesek_szama": 0, "palyaelhagyas": true}\n',
                encoding="utf-8",
            )
            eredeti = summarize_runs.NAPLO_FAJL
            summarize_runs.NAPLO_FAJL = fajl
            try:
                kimenet = StringIO()
                with redirect_stdout(kimenet):
                    summarize_runs.osszegez(30)
            finally:
                summarize_runs.NAPLO_FAJL = eredeti
        self.assertIn("Osszegzes (2 futas)", kimenet.getvalue())
        self.assertIn("Palyaelhagyasok:      1/2", kimenet.getvalue())

    def test_hianyzo_naplo(self) -> None:
        eredeti = summarize_runs.NAPLO_FAJL
        summarize_runs.NAPLO_FAJL = Path(tempfile.gettempdir()) / "nincs-ilyen-naplo.jsonl"
        try:
            kimenet = StringIO()
            with redirect_stdout(kimenet):
                summarize_runs.osszegez(30)
        finally:
            summarize_runs.NAPLO_FAJL = eredeti
        self.assertIn("Nincs osszegezheto futas", kimenet.getvalue())


def _reset(extra: str) -> dict:
    return {"message": "A rover visszaallt. scenario=x timescale=70 " + extra}


class AkadalyJelenletTest(unittest.TestCase):
    """Hibas train-meres: kikapcsolt TrackController mellett 0 akadallyal futott a meres."""

    TRAIN = "stadium-train-baseline-always-visible"

    def test_rendben(self) -> None:
        meta = akadaly_ellenorzes(_reset("obstacles=2 active=2 schedule=on"), self.TRAIN)
        self.assertEqual(meta, {"akadalyok": 2, "lathato_akadalyok_kezdetben": 2})

    def test_kikapcsolt_utemezes(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            akadaly_ellenorzes(_reset("obstacles=2 active=0 schedule=off"), self.TRAIN)
        self.assertIn("TrackController", str(ctx.exception))

    def test_hianyzo_lathato_akadaly(self) -> None:
        with self.assertRaises(RuntimeError):
            akadaly_ellenorzes(_reset("obstacles=2 active=1 schedule=on"), self.TRAIN)

    def test_regi_unity_mezok_nelkul(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            akadaly_ellenorzes({"message": "scenario=x timescale=70"}, self.TRAIN)
        self.assertIn("obstacles", str(ctx.exception))

    def test_idozitett_szcenario_kezdetben_nincs_lathato(self) -> None:
        meta = akadaly_ellenorzes(
            _reset("obstacles=2 active=0 schedule=on"), "stadium-train-baseline"
        )
        self.assertEqual(meta["lathato_akadalyok_kezdetben"], 0)

    def test_akadaly_nelkuli_szcenario(self) -> None:
        meta = akadaly_ellenorzes(
            _reset("obstacles=0 active=0 schedule=off"), "stadium-train-no-obstacles"
        )
        self.assertEqual(meta["akadalyok"], 0)


if __name__ == "__main__":
    unittest.main()
