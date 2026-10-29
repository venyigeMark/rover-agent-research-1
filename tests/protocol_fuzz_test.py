#!/usr/bin/env python3
"""Randomizált integrációs/fuzz tesztek a Rover Gateway v1 protokollhoz."""

from __future__ import annotations

import json
import math
import os
import random
import socket
import time
import unittest
from typing import Any
from uuid import uuid4


HOST = os.environ.get("ROVER_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("ROVER_GATEWAY_PORT", "8765"))
ROVID_TIMEOUT = float(os.environ.get("ROVER_GATEWAY_FUZZ_TIMEOUT", "2"))
RANDOM_ESETSZAM = int(os.environ.get("ROVER_GATEWAY_FUZZ_CASES", "30"))
MAXIMALIS_FRAME = 16 * 1024
SEED = int(os.environ.get("ROVER_GATEWAY_FUZZ_SEED", "20260726"))


def kodol(payload: str) -> bytes:
    adat = payload.encode("utf-8")
    if not 1 <= len(adat) <= MAXIMALIS_FRAME:
        raise ValueError("A tesztpayload mérete kívül esik a v1 frame-korláton.")
    return len(adat).to_bytes(4, "big", signed=False) + adat


def pontosan_fogad(kapcsolat: socket.socket, hossz: int) -> bytes:
    reszek: list[bytes] = []
    hatralevo = hossz
    while hatralevo:
        adat = kapcsolat.recv(hatralevo)
        if not adat:
            raise ConnectionError("A szerver a frame befejezése előtt bontott.")
        reszek.append(adat)
        hatralevo -= len(adat)
    return b"".join(reszek)


def valasz_fogad(kapcsolat: socket.socket) -> dict[str, Any]:
    prefix = pontosan_fogad(kapcsolat, 4)
    hossz = int.from_bytes(prefix, "big", signed=False)
    if not 1 <= hossz <= MAXIMALIS_FRAME:
        raise AssertionError(f"Érvénytelen válaszframe-méret: {hossz}")
    payload = pontosan_fogad(kapcsolat, hossz)
    valasz = json.loads(payload.decode("utf-8"))
    if not isinstance(valasz, dict):
        raise AssertionError("A válasz legfelső JSON-értéke nem objektum.")
    return valasz


def nyers_keres(payload: str, timeout: float = ROVID_TIMEOUT) -> dict[str, Any]:
    with socket.create_connection((HOST, PORT), timeout=timeout) as kapcsolat:
        kapcsolat.settimeout(timeout)
        kapcsolat.sendall(kodol(payload))
        return valasz_fogad(kapcsolat)


def parancs_timeout(adat: dict[str, Any]) -> float:
    """A parancs várható végrehajtási idejéhez igazított válasz-timeout."""
    command = adat.get("command")
    try:
        if command == "move":
            distance = float(adat["distance_m"])
            speed = float(adat["max_speed"])
            if math.isfinite(distance) and math.isfinite(speed):
                return min(max(2.0 + distance / max(speed, 0.05), 3.0), 15.0)
        elif command == "turn":
            angle = float(adat["angle_deg"])
            angular_speed = float(adat["max_angular_speed"])
            if math.isfinite(angle) and math.isfinite(angular_speed):
                return min(
                    max(2.0 + abs(angle) / max(angular_speed, 5.0), 3.0),
                    15.0,
                )
    except (KeyError, TypeError, ValueError):
        pass

    return ROVID_TIMEOUT


def keres(adat: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    payload = json.dumps(adat, ensure_ascii=False, separators=(",", ":"))
    return nyers_keres(payload, parancs_timeout(adat) if timeout is None else timeout)


def uj_keres(command: str, **parameterek: Any) -> dict[str, Any]:
    return {"request_id": str(uuid4()), "command": command, **parameterek}


def strukturalt_valasz_ellenorzese(teszt: unittest.TestCase, valasz: dict[str, Any]) -> None:
    teszt.assertIn(valasz.get("status"), {"accepted", "completed", "failed"})
    teszt.assertIn(valasz.get("state"), {"IDLE", "MOVING", "TURNING", "ERROR"})
    teszt.assertIn("request_id", valasz)
    if valasz["status"] == "failed":
        teszt.assertIsInstance(valasz.get("error"), dict)
        teszt.assertIsInstance(valasz["error"].get("code"), int)
        teszt.assertIsInstance(valasz["error"].get("name"), str)


def hibakod(valasz: dict[str, Any]) -> int | None:
    error = valasz.get("error")
    return error.get("code") if isinstance(error, dict) else None


def tavolsag(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt(sum((float(a[t]) - float(b[t])) ** 2 for t in ("x", "y", "z")))


class RoverGatewayProtocolFuzzTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                pass
        except OSError as hiba:
            raise unittest.SkipTest(
                f"A Unity Play Mode szerver nem érhető el: {HOST}:{PORT} ({hiba})"
            ) from hiba
        # Bemelegito keres hosszu timeouttal: a Play inditasa utani elso keres
        # (JIT, elso FixedUpdate-ek) tobb masodpercig is tarthat, es kulonben az
        # abece szerint elso teszt setUp-ja futna 2 s-os timeoutba (2026-10-26).
        keres(uj_keres("get_status"), timeout=30.0)

    def setUp(self) -> None:
        # A tesztek egymástól függetlenül álló roverrel induljanak.
        reset_valasz = keres(uj_keres("reset_error"), timeout=ROVID_TIMEOUT)
        strukturalt_valasz_ellenorzese(self, reset_valasz)
        if reset_valasz["status"] == "failed":
            self.assertEqual(hibakod(reset_valasz), 1300, reset_valasz)

        valasz = keres(uj_keres("stop"), timeout=ROVID_TIMEOUT)
        strukturalt_valasz_ellenorzese(self, valasz)

    def assertHiba(self, valasz: dict[str, Any], vart_kod: int) -> None:
        strukturalt_valasz_ellenorzese(self, valasz)
        self.assertEqual(valasz["status"], "failed", valasz)
        self.assertEqual(hibakod(valasz), vart_kod, valasz)

    def biztosit_idle_allapotot(self) -> None:
        statusz = keres(uj_keres("get_status"), timeout=ROVID_TIMEOUT)
        strukturalt_valasz_ellenorzese(self, statusz)
        if statusz.get("state") != "ERROR":
            return

        reset = keres(uj_keres("reset_error"), timeout=ROVID_TIMEOUT)
        strukturalt_valasz_ellenorzese(self, reset)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["state"], "IDLE", reset)

        stop = keres(uj_keres("stop"), timeout=ROVID_TIMEOUT)
        strukturalt_valasz_ellenorzese(self, stop)
        self.assertIn(stop["status"], {"accepted", "completed"}, stop)

    def test_elo_valaszok_megfelelnek_a_semanak(self) -> None:
        """2026-10-26: a valodi szerverkimenet a docs/protocol.schema.json szerint.

        Korabban a sema csak kezzel irt peldakon volt ellenorizve; a valodi
        valaszokban "error": {"code": 0, ...} allt null helyett, a message es a
        last_command_result mezot pedig a sema nem is ismerte.
        """
        try:
            import jsonschema
        except ImportError:
            self.skipTest("A jsonschema nincs telepitve (requirements-ci.txt).")
        from pathlib import Path

        sema = json.loads(
            (Path(__file__).resolve().parents[1] / "docs" / "protocol.schema.json").read_text(
                encoding="utf-8"
            )
        )
        sema.pop("oneOf", None)
        sema["$ref"] = "#/$defs/valasz"
        validator = jsonschema.Draft202012Validator(sema)
        self.biztosit_idle_allapotot()
        valaszok = [
            keres(uj_keres("observe"), timeout=ROVID_TIMEOUT),
            keres(uj_keres("get_status"), timeout=ROVID_TIMEOUT),
            keres(uj_keres("reset_position"), timeout=ROVID_TIMEOUT),
            keres(uj_keres("move", distance_m=0.05, max_speed=0.2)),
            keres(uj_keres("turn", angle_deg=5.0, max_angular_speed=20.0)),
            keres(uj_keres("get_status"), timeout=ROVID_TIMEOUT),
            keres(uj_keres("move", distance_m=5.0, max_speed=0.2), timeout=ROVID_TIMEOUT),
            nyers_keres('{"request_id":', ROVID_TIMEOUT),
        ]
        for valasz in valaszok:
            hibak = [h.message for h in validator.iter_errors(valasz)]
            self.assertEqual(hibak, [], valasz)
        self.assertIsNone(valaszok[0]["error"])
        self.assertIn("sim_time_s", valaszok[0])
        self.assertEqual(valaszok[5]["last_command_result"], "turn:completed")

    def test_move_randomizalt_tartomanyok(self) -> None:
        rng = random.Random(SEED)
        ertekek = [
            -math.inf,
            -1e30,
            -1.0,
            -0.0,
            0.0,
            0.009999,
            0.01,
            0.010001,
            0.05,
            0.50,
            1.0,
            1.999999,
            2.0,
            2.000001,
            1e30,
            math.inf,
            math.nan,
        ]

        esetek: list[tuple[float, float]] = [
            (0.01, 0.05),
            (2.0, 0.50),
            (0.01, 0.50),
            (2.0, 0.25),
        ]
        for _ in range(RANDOM_ESETSZAM):
            if rng.random() < 0.55:
                distance = rng.uniform(0.01, 2.0)
                # A 15 s-os szerver-timeout miatt csak biztosan befejezhető
                # érvényes párokat generálunk; a mezőhatárok fent külön szerepelnek.
                min_speed = max(0.05, distance / 10.0)
                speed = rng.uniform(min_speed, 0.50)
            else:
                distance = rng.choice(ertekek)
                speed = rng.choice(ertekek)
            esetek.append((distance, speed))

        for distance, speed in esetek:
            with self.subTest(distance_m=distance, max_speed=speed):
                self.biztosit_idle_allapotot()
                valasz = keres(uj_keres("move", distance_m=distance, max_speed=speed))
                strukturalt_valasz_ellenorzese(self, valasz)
                veges = math.isfinite(distance) and math.isfinite(speed)
                ervenyes = veges and 0.01 <= distance <= 2.0 and 0.05 <= speed <= 0.50
                if ervenyes:
                    self.assertIn(valasz["status"], {"accepted", "completed"}, valasz)
                else:
                    vart = 1202 if not veges else 1203
                    self.assertHiba(valasz, vart)

    def test_turn_randomizalt_tartomanyok(self) -> None:
        rng = random.Random(SEED + 1)
        ertekek = [
            -math.inf,
            -1e30,
            -181.0,
            -180.0,
            -1.0,
            -0.999999,
            0.0,
            0.999999,
            1.0,
            5.0,
            45.0,
            179.999,
            180.0,
            181.0,
            1e30,
            math.inf,
            math.nan,
        ]
        esetek: list[tuple[float, float]] = [
            (-180.0, 45.0),
            (180.0, 45.0),
            (-1.0, 5.0),
            (1.0, 5.0),
        ]
        for _ in range(RANDOM_ESETSZAM):
            if rng.random() < 0.55:
                abs_angle = rng.uniform(1.0, 180.0)
                angle = abs_angle if rng.random() < 0.5 else -abs_angle
                min_speed = max(5.0, abs_angle / 10.0)
                angular_speed = rng.uniform(min_speed, 45.0)
            else:
                angle = rng.choice(ertekek)
                angular_speed = rng.choice(ertekek)
            esetek.append((angle, angular_speed))

        for angle, angular_speed in esetek:
            with self.subTest(angle_deg=angle, max_angular_speed=angular_speed):
                self.biztosit_idle_allapotot()
                valasz = keres(uj_keres("turn", angle_deg=angle, max_angular_speed=angular_speed))
                strukturalt_valasz_ellenorzese(self, valasz)
                veges = math.isfinite(angle) and math.isfinite(angular_speed)
                ervenyes = (
                    veges and -180 <= angle <= 180 and abs(angle) >= 1 and 5 <= angular_speed <= 45
                )
                if ervenyes:
                    self.assertIn(valasz["status"], {"accepted", "completed"}, valasz)
                else:
                    vart = 1202 if not veges else 1203
                    self.assertHiba(valasz, vart)

    def test_hibas_es_csonka_json_mindig_strukturalt_hibat_ad(self) -> None:
        request_id = str(uuid4())
        extra_id = str(uuid4())
        dupla_id = str(uuid4())
        dupla_command_id = str(uuid4())
        dupla_szam_id = str(uuid4())
        fuzz_payloadok = [
            "{",
            "}",
            "[]",
            "null",
            "true",
            "123",
            '{"request_id":',
            '{"request_id":"x","command":"observe"}',
            '{"command":"observe"}',
            json.dumps({"request_id": request_id}),
            json.dumps({"request_id": request_id, "command": 123}),
            json.dumps({"request_id": request_id, "command": "move"}),
            json.dumps(
                {
                    "request_id": request_id,
                    "command": "move",
                    "distance_m": "1.0",
                    "max_speed": 0.2,
                }
            ),
            # A v1 zárt sémaként kezelendő: extra és duplikált mező is hiba.
            f'{{"request_id":"{extra_id}","command":"observe","extra":1}}',
            f'{{"request_id":"{dupla_id}","request_id":"{dupla_id}",' '"command":"observe"}',
            f'{{"request_id":"{dupla_command_id}","command":"observe",' '"command":"stop"}',
            f'{{"request_id":"{dupla_szam_id}","command":"move",'
            '"distance_m":0.2,"distance_m":0.3,"max_speed":0.2}',
        ]

        for payload in fuzz_payloadok:
            with self.subTest(payload=payload):
                kezdet = time.monotonic()
                valasz = nyers_keres(payload, timeout=ROVID_TIMEOUT)
                self.assertLess(time.monotonic() - kezdet, ROVID_TIMEOUT)
                strukturalt_valasz_ellenorzese(self, valasz)
                self.assertEqual(valasz["status"], "failed", valasz)

    def test_extra_es_duplikalt_mezok_hibakodja(self) -> None:
        extra_id = str(uuid4())
        extra = nyers_keres(f'{{"request_id":"{extra_id}","command":"observe","extra":1}}')
        self.assertHiba(extra, 1102)

        dupla_id = str(uuid4())
        dupla_request_id = nyers_keres(
            f'{{"request_id":"{dupla_id}","request_id":"{dupla_id}",' '"command":"observe"}'
        )
        self.assertHiba(dupla_request_id, 1103)

        dupla_command_id = str(uuid4())
        dupla_command = nyers_keres(
            f'{{"request_id":"{dupla_command_id}","command":"observe",' '"command":"stop"}'
        )
        self.assertHiba(dupla_command, 1103)

    def test_idempotens_move_nem_mozgat_ketszer(self) -> None:
        elotte = keres(uj_keres("observe"))["position"]
        request_id = str(uuid4())
        parancs = {
            "request_id": request_id,
            "command": "move",
            "distance_m": 0.10,
            "max_speed": 0.50,
        }
        payload = json.dumps(parancs, separators=(",", ":"))

        elso = nyers_keres(payload, timeout=parancs_timeout(parancs))
        elso_utan = keres(uj_keres("observe"))["position"]
        masodik = nyers_keres(payload, timeout=ROVID_TIMEOUT)
        masodik_utan = keres(uj_keres("observe"))["position"]

        self.assertEqual(elso, masodik)
        self.assertGreater(tavolsag(elotte, elso_utan), 0.05)
        self.assertLess(tavolsag(elso_utan, masodik_utan), 0.005)

    def test_masodik_move_moving_allapotban_1300(self) -> None:
        elso = uj_keres("move", distance_m=1.0, max_speed=0.10)
        elso_payload = json.dumps(elso, separators=(",", ":"))

        with socket.create_connection((HOST, PORT), timeout=ROVID_TIMEOUT) as kapcsolat:
            kapcsolat.settimeout(parancs_timeout(elso))
            kapcsolat.sendall(kodol(elso_payload))

            hatarido = time.monotonic() + ROVID_TIMEOUT
            while True:
                statusz = keres(uj_keres("get_status"), timeout=ROVID_TIMEOUT)
                if statusz.get("state") == "MOVING":
                    break
                if time.monotonic() >= hatarido:
                    self.fail(f"A rover nem került MOVING állapotba: {statusz}")
                time.sleep(0.02)

            masodik = keres(
                uj_keres("move", distance_m=0.10, max_speed=0.50), timeout=ROVID_TIMEOUT
            )
            self.assertHiba(masodik, 1300)
            self.assertEqual(masodik["error"]["name"], "COMMAND_NOT_ALLOWED_IN_STATE")

            # A hosszú első mozgást rögtön megszakítjuk, hogy a teszt gyors és izolált legyen.
            stop = keres(uj_keres("stop"), timeout=ROVID_TIMEOUT)
            self.assertIn(stop["status"], {"accepted", "completed"})
            valasz_fogad(kapcsolat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
