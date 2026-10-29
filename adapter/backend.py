"""Rover backend absztrakcio (M12).

Ket megvalositas, azonos interfesszel:
- UnityTcpBackend: a v1 TCP/JSON protokollon beszel a Unity RoverGatewayServer-rel
- MockBackend:     memoriaban szimulalja a v1 protokoll allapotgepet, a stadion
                   alaku palyat es a szenzorokat - adapter-tesztekhez Unity nelkul

Az adapter felsobb retegei (orseg, MCP-szerver) csak a Backend interfeszt latjak,
es soha nem arulhatjak el az agentnek, melyik valosul meg mogotte.
"""

from __future__ import annotations

import json
import math
import socket
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

MAXIMALIS_FRAME_MERET = 65536

# v1 protokoll korlatai (docs/protocol.md)
MOVE_TAV_MIN, MOVE_TAV_MAX = 0.01, 2.00
MOVE_SEB_MIN, MOVE_SEB_MAX = 0.05, 0.50
TURN_SZOG_MIN_ABS, TURN_SZOG_MAX_ABS = 1.0, 180.0
TURN_SEB_MIN, TURN_SEB_MAX = 5.0, 45.0

# Palya-geometria a mock-hoz (stadium-train-baseline.json)
PALYA_EGYENES_HOSSZ_M = 12.0
PALYA_IV_SUGAR_M = 4.0
PALYA_VONAL_SZELESSEG_M = 0.18
SZENZOR_OLDALTAV_M = 0.3  # a Unity-jelenettel egyezoen (korabban 0.06)
LIDAR_SZEKTOR_SZAM = 6
LIDAR_MAX_HATOTAV_M = 10.0


class Backend(Protocol):
    """Egy v1 protokoll-parancsot kuld es a nyers v1 valaszt adja vissza."""

    def kuld(self, parancs: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Unity TCP backend
# ---------------------------------------------------------------------------


class UnityTcpBackend:
    # A gateway parancs-timeoutja szimulacios idoben a varhato idotartam 1.5-szerese
    # + 2 s; az adapter leghosszabb mozgasa (1 m, 0.05 m/s) timescale 1 mellett igy
    # 32 s valos ido. A 90 s-os kliensoldali korlat csak a lefagyott Unityt fogja meg.
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, timeout_s: float = 90.0) -> None:
        self._socket = socket.create_connection((host, port), timeout=5)
        self._socket.settimeout(timeout_s)

    def kuld(self, parancs: dict[str, Any]) -> dict[str, Any]:
        keres = {"request_id": str(uuid4()), **parancs}
        payload = json.dumps(keres, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if not 1 <= len(payload) <= MAXIMALIS_FRAME_MERET:
            raise ValueError("A kimeno JSON tul nagy vagy ures.")
        self._socket.sendall(len(payload).to_bytes(4, "big", signed=False))
        self._socket.sendall(payload)
        hossz = int.from_bytes(self._pontosan_fogad(4), "big", signed=False)
        if not 1 <= hossz <= MAXIMALIS_FRAME_MERET:
            raise ConnectionError(f"Hibas valaszframe-meret: {hossz}")
        valasz = json.loads(self._pontosan_fogad(hossz).decode("utf-8"))
        # A valasznak a most kuldott kereshez kell tartoznia; egy elcsuszott
        # (korabbi kereshez tartozo) valasz rossz parancs eredmenyet adna az agentnek.
        if not isinstance(valasz, dict) or valasz.get("request_id") != keres["request_id"]:
            raise ConnectionError("A valasz nem a kuldott kereshez tartozik.")
        return valasz

    def _pontosan_fogad(self, hossz: int) -> bytes:
        reszek: list[bytes] = []
        hatralevo = hossz
        while hatralevo:
            adat = self._socket.recv(hatralevo)
            if not adat:
                raise ConnectionError("A kapcsolat varatlanul megszakadt.")
            reszek.append(adat)
            hatralevo -= len(adat)
        return b"".join(reszek)

    def close(self) -> None:
        self._socket.close()


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------


def _hiba(kod: int, nev: str, uzenet: str, allapot: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "state": allapot,
        "error": {"code": kod, "name": nev, "message": uzenet},
    }


def tavolsag_a_kozepvonaltol(x: float, z: float) -> float:
    """A stadion alaku palya kozepvonalatol mert tavolsag (m) - a javitott
    TrackController.TavolsagAKozepvonaltol Python-parja (felkorivek csak a
    sajat oldalukon ervenyesek)."""
    fel_hossz = PALYA_EGYENES_HOSSZ_M / 2.0
    r = PALYA_IV_SUGAR_M

    def egyenes(allando_x: float) -> float:
        zc = max(-fel_hossz, min(fel_hossz, z))
        return math.hypot(x - allando_x, z - zc)

    def felkor(kozep_z: float, irany: float) -> float:
        dz = z - kozep_z
        if dz * irany < 0:
            return math.inf
        return abs(math.hypot(x, dz) - r)

    return min(egyenes(r), egyenes(-r), felkor(-fel_hossz, -1.0), felkor(fel_hossz, 1.0))


@dataclass
class MockAkadaly:
    x: float
    z: float
    sugar_m: float = 0.4


@dataclass
class MockBackend:
    """Determinisztikus, memoriabeli rover a v1 protokollal.

    A rover a (PALYA_IV_SUGAR_M, 0) pontbol indul, +z iranyba nezve (a jobb
    oldali egyenesen, a vonalon). Nincs zaj, nincs fizika: a move/turn
    azonnal, "completed" statusszal lezarul (a Unity szerver is a parancs
    vegen valaszol).
    """

    akadalyok: list[MockAkadaly] = field(default_factory=list)
    x: float = PALYA_IV_SUGAR_M
    z: float = 0.0
    irany_fok: float = 0.0  # 0 = +z, pozitiv = oramutato jarasa szerint (Unity)
    allapot: str = "IDLE"
    utkozesek: int = 0
    parancsnaplo: list[dict[str, Any]] = field(default_factory=list)

    def kuld(self, parancs: dict[str, Any]) -> dict[str, Any]:
        self.parancsnaplo.append(dict(parancs))
        request_id = parancs.get("request_id", str(uuid4()))
        valasz = self._feldolgoz(parancs)
        return {"request_id": request_id, **valasz}

    def close(self) -> None:
        return None

    # --- parancsok -----------------------------------------------------------

    def _feldolgoz(self, p: dict[str, Any]) -> dict[str, Any]:
        cmd = p.get("command")
        if cmd == "observe":
            return {"status": "completed", "state": self.allapot, **self._observe()}
        if cmd == "get_status":
            return {"status": "completed", "state": self.allapot, "protocol_version": 1}
        if cmd == "stop":
            if self.allapot in ("MOVING", "TURNING"):
                self.allapot = "IDLE"
            return {"status": "completed", "state": self.allapot}
        if cmd == "move":
            return self._move(p)
        if cmd == "turn":
            return self._turn(p)
        if cmd == "reset_position":
            if self.allapot != "IDLE":
                return _hiba(
                    1300,
                    "COMMAND_NOT_ALLOWED_IN_STATE",
                    "reset_position only in IDLE",
                    self.allapot,
                )
            self.x, self.z, self.irany_fok = PALYA_IV_SUGAR_M, 0.0, 0.0
            # A Unity is nullazza az utkozesszamlalot resetkor (RoverGatewayServer).
            self.utkozesek = 0
            return {"status": "completed", "state": self.allapot}
        if cmd == "reset_error":
            if self.allapot != "ERROR":
                return _hiba(
                    1300, "COMMAND_NOT_ALLOWED_IN_STATE", "reset_error only in ERROR", self.allapot
                )
            self.allapot = "IDLE"
            self.x, self.z, self.irany_fok = PALYA_IV_SUGAR_M, 0.0, 0.0
            self.utkozesek = 0
            return {"status": "completed", "state": self.allapot}
        return _hiba(1200, "UNKNOWN_COMMAND", f"unknown command: {cmd!r}", self.allapot)

    def _szam(self, p: dict[str, Any], mezo: str) -> tuple[float | None, dict[str, Any] | None]:
        if mezo not in p:
            return None, _hiba(1102, "UNKNOWN_FIELD", f"missing field: {mezo}", self.allapot)
        ertek = p[mezo]
        if isinstance(ertek, bool) or not isinstance(ertek, (int, float)):
            return None, _hiba(1101, "INVALID_FIELD_TYPE", f"{mezo} must be a number", self.allapot)
        if not math.isfinite(ertek):
            return None, _hiba(1202, "NON_FINITE_VALUE", f"{mezo} must be finite", self.allapot)
        return float(ertek), None

    def _move(self, p: dict[str, Any]) -> dict[str, Any]:
        if self.allapot != "IDLE":
            return _hiba(1300, "COMMAND_NOT_ALLOWED_IN_STATE", "move only in IDLE", self.allapot)
        tav, hiba = self._szam(p, "distance_m")
        if hiba:
            return hiba
        seb, hiba = self._szam(p, "max_speed")
        if hiba:
            return hiba
        if not MOVE_TAV_MIN <= tav <= MOVE_TAV_MAX:
            return _hiba(
                1203,
                "VALUE_OUT_OF_RANGE",
                f"distance_m must be between {MOVE_TAV_MIN} and {MOVE_TAV_MAX}",
                self.allapot,
            )
        if not MOVE_SEB_MIN <= seb <= MOVE_SEB_MAX:
            return _hiba(
                1203,
                "VALUE_OUT_OF_RANGE",
                f"max_speed must be between {MOVE_SEB_MIN} and {MOVE_SEB_MAX}",
                self.allapot,
            )
        # Lepesenkent halad, akadalynal megall (utkozes)
        rad = math.radians(self.irany_fok)
        dx, dz = math.sin(rad), math.cos(rad)
        lepes = 0.01
        megtett = 0.0
        while megtett + 1e-9 < tav:
            uj_x, uj_z = self.x + dx * lepes, self.z + dz * lepes
            if any(math.hypot(uj_x - a.x, uj_z - a.z) < a.sugar_m for a in self.akadalyok):
                self.utkozesek += 1
                break
            self.x, self.z = uj_x, uj_z
            megtett += lepes
        return {"status": "completed", "state": self.allapot}

    def _turn(self, p: dict[str, Any]) -> dict[str, Any]:
        if self.allapot != "IDLE":
            return _hiba(1300, "COMMAND_NOT_ALLOWED_IN_STATE", "turn only in IDLE", self.allapot)
        szog, hiba = self._szam(p, "angle_deg")
        if hiba:
            return hiba
        seb, hiba = self._szam(p, "max_angular_speed")
        if hiba:
            return hiba
        if not TURN_SZOG_MIN_ABS <= abs(szog) <= TURN_SZOG_MAX_ABS:
            return _hiba(
                1203,
                "VALUE_OUT_OF_RANGE",
                f"abs(angle_deg) must be between {TURN_SZOG_MIN_ABS} and {TURN_SZOG_MAX_ABS}",
                self.allapot,
            )
        if not TURN_SEB_MIN <= seb <= TURN_SEB_MAX:
            return _hiba(
                1203,
                "VALUE_OUT_OF_RANGE",
                f"max_angular_speed must be between {TURN_SEB_MIN} and {TURN_SEB_MAX}",
                self.allapot,
            )
        self.irany_fok = (self.irany_fok + szog) % 360.0
        return {"status": "completed", "state": self.allapot}

    # --- szenzorok -----------------------------------------------------------

    def _szenzor(self, oldal_eltolas_m: float) -> dict[str, Any]:
        rad = math.radians(self.irany_fok)
        # jobbra mutato egysegvektor (a menetirany +90 fok)
        jx, jz = math.cos(rad), -math.sin(rad)
        sx, sz = self.x + jx * oldal_eltolas_m, self.z + jz * oldal_eltolas_m
        tav = tavolsag_a_kozepvonaltol(sx, sz)
        fel_szelesseg = PALYA_VONAL_SZELESSEG_M / 2.0
        if tav <= fel_szelesseg:
            intenzitas = 1.0
        else:
            intenzitas = max(0.0, 1.0 - (tav - fel_szelesseg) / 0.1)
        return {"white": intenzitas >= 0.5, "intensity": round(intenzitas, 3)}

    def _lidar(self) -> list[float]:
        szektorok = [LIDAR_MAX_HATOTAV_M] * LIDAR_SZEKTOR_SZAM
        for a in self.akadalyok:
            dx, dz = a.x - self.x, a.z - self.z
            tav = max(0.0, math.hypot(dx, dz) - a.sugar_m)
            if tav > LIDAR_MAX_HATOTAV_M:
                continue
            # relativ szog a menetiranyhoz (-180..180), 180 fokos elolso legyezo
            abszolut = math.degrees(math.atan2(dx, dz))
            relativ = (abszolut - self.irany_fok + 180.0) % 360.0 - 180.0
            if abs(relativ) > 90.0:
                continue
            idx = min(LIDAR_SZEKTOR_SZAM - 1, int((relativ + 90.0) / (180.0 / LIDAR_SZEKTOR_SZAM)))
            szektorok[idx] = min(szektorok[idx], round(tav, 3))
        return szektorok

    def _lidar_nyers(self) -> tuple[list[float], list[bool]]:
        # A mock nem futtat valodi raycastert: a nyers sugarakat a
        # szektor-minimumokbol szarmaztatja, szektoronkent azonos ertekkel.
        # Igy a "szektor minimuma == a hozza tartozo nyers sugarak minimuma"
        # invarians a mockban is pontosan teljesul, es a valasz alakja
        # megegyezik a Unity-evel. Valodi, sugarankenti geometriat csak a
        # Unity oldal ad.
        sugar_szektoronkent = 6  # Unity: 36 sugar / 6 szektor
        nyers: list[float] = []
        for ertek in self._lidar():
            nyers.extend([ertek] * sugar_szektoronkent)
        # A maszk jelentese pontosan ugyanaz, mint a Unity oldalon: true =
        # az adott sugar TALALT valamit a hatotavon belul. Nyilt palyan
        # tehat a legtobb sugar false, es ez nem szenzorhiba.
        return nyers, [e < LIDAR_MAX_HATOTAV_M for e in nyers]

    def _observe(self) -> dict[str, Any]:
        lidar_nyers, lidar_ervenyes = self._lidar_nyers()
        return {
            "position": {"x": round(self.x, 4), "y": 0.0, "z": round(self.z, 4)},
            "speed": 0.0,
            "sensor_mode": "three",
            "sensor_left": self._szenzor(-SZENZOR_OLDALTAV_M),
            "sensor_center": self._szenzor(0.0),
            "sensor_right": self._szenzor(SZENZOR_OLDALTAV_M),
            "lidar_szektor_min": self._lidar(),
            "lidar_nyers": lidar_nyers,
            "lidar_nyers_ervenyes": lidar_ervenyes,
            "collision_occurred": self.utkozesek > 0,
            "collision_count": self.utkozesek,
        }
