#!/usr/bin/env python3
"""A protokoll JSON Schema ervenyessegenek es peldaival valo egyezesenek
ellenorzese (M12, a docs/protocol.schema.json-hoz).

Nem elo szervert tesztel, csak azt, hogy a sema maga ervenyes JSON Schema,
es hogy a v1 protokoll tipikus keres/valasz uzeneteit helyesen fogadja el,
illetve a korlaton kivuli ertekeket helyesen utasitja el.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("A jsonschema csomag nincs telepitve: pip install jsonschema", file=sys.stderr)
    raise SystemExit(1)

GYOKER = Path(__file__).resolve().parent.parent
SEMA_FAJL = GYOKER / "docs" / "protocol.schema.json"
UUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"

ERVENYES_KERESEK = [
    {"request_id": UUID, "command": "observe"},
    {"request_id": UUID, "command": "stop"},
    {"request_id": UUID, "command": "reset_position"},
    {"request_id": UUID, "command": "move", "distance_m": 0.5, "max_speed": 0.2},
    {"request_id": UUID, "command": "turn", "angle_deg": -30.0, "max_angular_speed": 20.0},
]
ERVENYTELEN_KERESEK = [
    {"request_id": UUID, "command": "fly"},
    {"request_id": "nem-uuid", "command": "observe"},
    {"request_id": UUID, "command": "move", "distance_m": 5.0, "max_speed": 0.2},
    {"request_id": UUID, "command": "move", "distance_m": 0.5},
    {"request_id": UUID, "command": "turn", "angle_deg": 30.0},
    {"request_id": UUID, "command": "observe", "ismeretlen_mezo": 1},
]
ERVENYES_VALASZOK = [
    {"request_id": UUID, "status": "completed", "state": "IDLE", "error": None},
    {
        "request_id": UUID,
        "status": "failed",
        "state": "IDLE",
        "error": {"code": 1203, "name": "VALUE_OUT_OF_RANGE", "message": "..."},
    },
    {
        "request_id": UUID,
        "status": "completed",
        "state": "IDLE",
        "position": {"x": 4.0, "y": 0.0, "z": 0.0},
        "speed": 0.0,
        "sensor_mode": "three",
        "sensor_center": {"white": True, "intensity": 1.0},
        "lidar_szektor_min": [10.0, 10.0, 2.5, 10.0, 10.0, 10.0],
        "collision_occurred": False,
        "collision_count": 0,
    },
    {
        "request_id": UUID,
        "status": "completed",
        "state": "IDLE",
        "error": None,
        "message": "A rover visszaallt. scenario=x timescale=70 obstacles=2 active=2 schedule=on",
        "sim_time_s": 12.5,
    },
    {
        "request_id": UUID,
        "status": "completed",
        "state": "IDLE",
        "error": None,
        "protocol_version": 1,
        "last_command_result": "move:completed",
        "sim_time_s": 3.0,
    },
    {
        "request_id": "",
        "status": "failed",
        "state": "IDLE",
        "error": {"code": 1104, "name": "INVALID_REQUEST_ID", "message": "..."},
        "message": "...",
    },
]
ERVENYTELEN_VALASZOK = [
    # a regi JsonUtility-kimenet: sikeres valasz nem-null hibaobjektummal
    {
        "request_id": UUID,
        "status": "completed",
        "state": "IDLE",
        "error": {"code": 0, "name": "", "message": ""},
    },
    # a last_command_result soha nem lehet a teljes valasz-JSON
    {
        "request_id": UUID,
        "status": "completed",
        "state": "IDLE",
        "last_command_result": '{"request_id":"x","status":"completed"}',
    },
    {"request_id": UUID, "status": "kesz", "state": "IDLE"},
    {"request_id": UUID, "status": "completed", "state": "FUTAS"},
    {"request_id": UUID, "status": "completed", "state": "IDLE", "sensor_mode": "ketto"},
]


def alsema(sema: dict, nev: str) -> dict:
    reszlet = copy.deepcopy(sema)
    reszlet.pop("oneOf", None)
    reszlet["$ref"] = f"#/$defs/{nev}"
    return reszlet


def main() -> int:
    sema = json.loads(SEMA_FAJL.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(sema)

    hibak = 0
    for nev, ervenyesek, ervenytelenek in (
        ("keres", ERVENYES_KERESEK, ERVENYTELEN_KERESEK),
        ("valasz", ERVENYES_VALASZOK, ERVENYTELEN_VALASZOK),
    ):
        validator = jsonschema.Draft202012Validator(alsema(sema, nev))
        for uzenet in ervenyesek:
            if not validator.is_valid(uzenet):
                hibak += 1
                print(f"HIBA: ervenyes {nev} elutasitva: {uzenet}", file=sys.stderr)
        for uzenet in ervenytelenek:
            if validator.is_valid(uzenet):
                hibak += 1
                print(f"HIBA: ervenytelen {nev} elfogadva: {uzenet}", file=sys.stderr)

    osszes = len(ERVENYES_KERESEK) + len(ERVENYTELEN_KERESEK)
    osszes += len(ERVENYES_VALASZOK) + len(ERVENYTELEN_VALASZOK)
    if hibak:
        print(f"{hibak} elteres a {osszes} peldabol.", file=sys.stderr)
        return 1
    print(f"OK: a protokoll-sema mind a {osszes} peldat helyesen kezeli.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
