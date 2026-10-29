"""Biztonsagi reteg az agent es a rover backend koze (M12).

Feladatai (a kiiras M12 pontjai szerint):
- csak a szukseges muveleteket engedi at (observe, get_status, move, turn, stop,
  reset_position) - a reset_error es minden mas parancs le van tiltva.
  A reset_position az adapter szintjen engedelyezett, de az MCP-szerver NEM
  teszi ki agent-eszkozkent (lasd a metodus docstringjet);
- minden parametert a backend ELOTT validal: ervenytelen hivas nem jut el a
  roverhez, hanem rovid, egyertelmu hibauzenettel ter vissza (es fogyaszt a
  parancskeretbol, hogy egy hibas agent ne probalkozhasson korlatlanul);
- session-limitek: max parancsszam, max idotartam, max osszes megtett tavolsag;
  limit atlepesekor automatikus stop, es a session lezarul;
- backend-rejtes: a valaszbol eltavolitja a privilegizalt szimulator-mezoket
  (position, speed, collision_*), igy az agent nem tudja meg, hogy Unity vagy
  mock all mogotte. Kivetel az utkozesjelzes: az observe valaszaba bekerul egy
  collision_detected bool (volt-e utkozes az utolso observe ota), mert
  bumper/IMU egy valodi roveren is lenne - a kumulativ szamlalo tovabbra sem
  szivarog ki;
- a backend barmilyen hibaja (halozat, protokoll, dekodolas) egyseges
  ADAPTER_BACKEND_ERROR valaszt ad es lezarja a sessiont, hogy a kivetel
  szovegebol se lehessen a backend tipusara kovetkeztetni.

Az adapter sajat hibai (nem a v1 protokoll hibakodjai) "ADAPTER_" prefixszel
jelennek meg, hogy a naplobol egyertelmu legyen, hol akadt el a hivas.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from adapter.backend import (
    MOVE_SEB_MAX,
    MOVE_SEB_MIN,
    MOVE_TAV_MAX,
    MOVE_TAV_MIN,
    TURN_SEB_MAX,
    TURN_SEB_MIN,
    TURN_SZOG_MAX_ABS,
    TURN_SZOG_MIN_ABS,
    Backend,
)

ENGEDELYEZETT_PARANCSOK = ("observe", "get_status", "move", "turn", "stop", "reset_position")
# sim_time_s (2026-10-26): a szimulacios ido elarulna, hogy szimulator all mogotte.
ELREJTETT_MEZOK = ("position", "speed", "collision_occurred", "collision_count", "sim_time_s")
# Az utkozes-erzekelo (bumper/IMU) egy valodi roveren is letezne, ezert az agent
# megkapja - de csak "az utolso observe ota tortent-e utkozes" bool formaban, nem
# a szimulator kumulativ szamlalojakent (abbol statisztika lenne visszafejtheto).
UTKOZES_MEZO = "collision_detected"


@dataclass(frozen=True)
class SessionKorlatok:
    max_parancs: int = 300
    max_idotartam_s: float = 900.0
    max_ossz_tavolsag_m: float = 60.0
    # egyetlen move maximalis hossza az adapter szintjen (szigorubb a v1 2.0 m-nel):
    max_move_tav_m: float = 1.0


@dataclass
class SessionAllapot:
    kezdet: float = field(default_factory=time.monotonic)
    parancsok: int = 0
    ossz_tavolsag_m: float = 0.0
    lezarva: bool = False
    lezaras_oka: str | None = None
    elutasitott: int = 0
    utolso_utkozes_szamlalo: int = 0
    utkozes_az_utolso_parancs_ota: bool = False
    # Lezaraskor a rover nyugtazta-e a stopot (None: a session meg nyitott).
    stop_megerositve: bool | None = None


class BackendHiba(Exception):
    """A backend elerhetetlen vagy ertelmezhetetlen valaszt adott."""


def _adapter_hiba(nev: str, uzenet: str) -> dict[str, Any]:
    return {"status": "rejected", "error": {"code": nev, "message": uzenet}}


def _szam(ertek: Any, nev: str, lo: float, hi: float) -> tuple[float | None, dict[str, Any] | None]:
    if isinstance(ertek, bool) or not isinstance(ertek, (int, float)):
        return None, _adapter_hiba(
            "ADAPTER_INVALID_TYPE", f"{nev} must be a number, got {type(ertek).__name__}"
        )
    if not math.isfinite(ertek):
        return None, _adapter_hiba("ADAPTER_NON_FINITE", f"{nev} must be finite")
    if not lo <= ertek <= hi:
        return None, _adapter_hiba(
            "ADAPTER_OUT_OF_RANGE", f"{nev} must be between {lo} and {hi}, got {ertek}"
        )
    return float(ertek), None


class Orseg:
    def __init__(self, backend: Backend, korlatok: SessionKorlatok | None = None) -> None:
        self._backend = backend
        self.korlatok = korlatok or SessionKorlatok()
        self.session = SessionAllapot()

    # --- publikus muveletek ---------------------------------------------------

    def observe(self) -> dict[str, Any]:
        return self._vegrehajt({"command": "observe"})

    def move(self, distance_m: Any, max_speed: Any = 0.2) -> dict[str, Any]:
        tav, hiba = _szam(
            distance_m, "distance_m", MOVE_TAV_MIN, min(MOVE_TAV_MAX, self.korlatok.max_move_tav_m)
        )
        if hiba:
            return self._elutasit(hiba)
        seb, hiba = _szam(max_speed, "max_speed", MOVE_SEB_MIN, MOVE_SEB_MAX)
        if hiba:
            return self._elutasit(hiba)
        if self.session.ossz_tavolsag_m + tav > self.korlatok.max_ossz_tavolsag_m:
            return self._elutasit(
                _adapter_hiba(
                    "ADAPTER_DISTANCE_BUDGET",
                    f"this move would exceed the session distance budget "
                    f"({self.session.ossz_tavolsag_m:.2f} + {tav:.2f} > "
                    f"{self.korlatok.max_ossz_tavolsag_m} m)",
                )
            )
        valasz = self._vegrehajt({"command": "move", "distance_m": tav, "max_speed": seb})
        if valasz.get("status") == "completed":
            self.session.ossz_tavolsag_m += tav
        return valasz

    def turn(self, angle_deg: Any, max_angular_speed: Any = 30.0) -> dict[str, Any]:
        szog, hiba = _szam(angle_deg, "angle_deg", -TURN_SZOG_MAX_ABS, TURN_SZOG_MAX_ABS)
        if hiba:
            return self._elutasit(hiba)
        if abs(szog) < TURN_SZOG_MIN_ABS:
            return self._elutasit(
                _adapter_hiba(
                    "ADAPTER_OUT_OF_RANGE",
                    f"abs(angle_deg) must be at least {TURN_SZOG_MIN_ABS}, got {szog}",
                )
            )
        seb, hiba = _szam(max_angular_speed, "max_angular_speed", TURN_SEB_MIN, TURN_SEB_MAX)
        if hiba:
            return self._elutasit(hiba)
        return self._vegrehajt({"command": "turn", "angle_deg": szog, "max_angular_speed": seb})

    def stop(self) -> dict[str, Any]:
        """A stop mindig atmegy, lezart sessionben is (biztonsagi muvelet).

        Ha a session mar lezarult, a backend is le van zarva - ilyenkor nem
        probalunk ujra kuldeni (az mar hibahoz vezetne). Csak akkor nyugtazzuk,
        hogy a rover all, ha a lezaraskor kikuldott stopot a rover vissza is
        igazolta. Backend-hiba miatti lezarasnal stop nem ment ki; korabban az
        adapter ilyenkor is "completed"-et adott, ami hamis nyugta volt.
        """
        if self.session.lezarva:
            if self.session.stop_megerositve:
                return {
                    "status": "completed",
                    "note": "the rover was already stopped when the session closed",
                }
            return _adapter_hiba(
                "ADAPTER_STOP_UNCONFIRMED",
                "session closed; the rover was not reachable, so the stop could not be confirmed",
            )
        self.session.parancsok += 1
        return self._backend_hivas({"command": "stop"})

    def reset_position(self) -> dict[str, Any]:
        """Kiserletvezetoi muvelet: a rover visszaallitasa a kezdo pozicioba.

        NEM agent-eszkoz (az MCP-szerver nem teszi ki): egy valodi rovert nem
        lehet teleportalni, ezert a muvelet leteze maga is elarulna, hogy
        szimulacio all a backend mogott. A kiserleti futasok kozotti resetet a
        meresindito szkript vegzi ezen a metoduson keresztul.
        """
        valasz = self._vegrehajt({"command": "reset_position"})
        if valasz.get("status") == "completed":
            # A rover resetkor nullazza az utkozesszamlalot. Ha a mi
            # referenciank a regi erteken maradna, az uj futas elso utkozesei
            # (1, 2, ... a regi ertekig) nem novelnek, es elvesznenek.
            self.session.utolso_utkozes_szamlalo = 0
            self.session.utkozes_az_utolso_parancs_ota = False
        return valasz

    def get_status(self) -> dict[str, Any]:
        """A rover allapotgepe: IDLE / MOVING / TURNING / ERROR.

        Agent-eszkoz. Enelkul egy agent nem veszi eszre, ha a rover ERROR
        allapotba kerult, es vakon kuldene tovabb parancsokat, amiket a rover
        egyesevel elutasit - a parancskeret kozben fogy.

        A protocol_version kikerul a valaszbol: fejlesztoi adat, a vezerleshez
        nem kell, es a vak API-kiertekeles tanulsaga szerint minden folosleges
        mezo zajt visz az eszkozleirasba.
        """
        valasz = self._vegrehajt({"command": "get_status"})
        valasz.pop("protocol_version", None)
        # Vedelem a beagyazott valasz ellen. A szerver korabban a teljes elozo
        # valasz JSON-jat tarolta a last_command_result mezoben, igy egy
        # observe utani get_status kiadta a position/speed/collision_count
        # mezoket - az _szur ezt nem latta, mert az csak felso szintu kulcsokat
        # tavolit el. A szerver mar osszefoglalot kuld ("move:completed"), de ha
        # barmikor visszaesne a regi viselkedesre, az agent akkor se lassa.
        eredmeny = valasz.get("last_command_result")
        if isinstance(eredmeny, str) and eredmeny.lstrip().startswith("{"):
            valasz.pop("last_command_result", None)
        return valasz

    def session_status(self) -> dict[str, Any]:
        eltelt = time.monotonic() - self.session.kezdet
        return {
            "commands_used": self.session.parancsok,
            "commands_limit": self.korlatok.max_parancs,
            "elapsed_s": round(eltelt, 1),
            "time_limit_s": self.korlatok.max_idotartam_s,
            "distance_used_m": round(self.session.ossz_tavolsag_m, 3),
            "distance_limit_m": self.korlatok.max_ossz_tavolsag_m,
            "max_single_move_m": min(MOVE_TAV_MAX, self.korlatok.max_move_tav_m),
            "rejected_calls": self.session.elutasitott,
            "closed": self.session.lezarva,
            "closed_reason": self.session.lezaras_oka,
        }

    def lezar(self, ok: str) -> None:
        """A session lezarasa: eloszor stop, aztan a backend bontasa.

        A stop es a close hibaja sem terjedhet tovabb - a lezaras mindig
        befejezodik, kulonben egy halozati hiba miatt "felig nyitva" maradna a
        session.
        """
        if self.session.lezarva:
            return
        self.session.lezarva = True
        self.session.lezaras_oka = ok
        try:
            valasz = self._backend.kuld({"command": "stop"})
            self.session.stop_megerositve = (
                isinstance(valasz, dict) and valasz.get("status") == "completed"
            )
        except Exception:  # noqa: BLE001
            self.session.stop_megerositve = False
        finally:
            try:
                self._backend.close()
            except Exception:  # noqa: BLE001
                pass

    def _lezar_backend_nelkul(self, ok: str) -> None:
        """Lezaras, amikor a backend mar bizonyitottan nem valaszol: nem
        probalunk stopot kuldeni, csak bontjuk a kapcsolatot."""
        if self.session.lezarva:
            return
        self.session.lezarva = True
        self.session.lezaras_oka = ok
        self.session.stop_megerositve = False
        try:
            self._backend.close()
        except Exception:  # noqa: BLE001
            pass

    # --- belso ----------------------------------------------------------------

    def _elutasit(self, hiba: dict[str, Any]) -> dict[str, Any]:
        """Elutasitott hivas: a parancskeretbe is beleszamit.

        Enelkul egy hibas vagy rosszindulatu agent korlatlanul probalkozhatna
        ervenytelen parametereku hivasokkal, mert azok nem fogyasztanak keretet.
        """
        self.session.elutasitott += 1
        self.session.parancsok += 1
        return hiba

    def _vegrehajt(self, parancs: dict[str, Any]) -> dict[str, Any]:
        # Nem assert: az -O kapcsoloval futo Python kihagyna a biztonsagi ellenorzest.
        if parancs["command"] not in ENGEDELYEZETT_PARANCSOK:
            raise ValueError(f"Az adapter nem tovabbithat ilyen parancsot: {parancs['command']!r}")
        if self.session.lezarva:
            return self._elutasit(
                _adapter_hiba(
                    "ADAPTER_SESSION_CLOSED", f"session closed: {self.session.lezaras_oka}"
                )
            )
        if self.session.parancsok >= self.korlatok.max_parancs:
            self.lezar("command limit reached")
            return self._elutasit(
                _adapter_hiba("ADAPTER_SESSION_CLOSED", "session closed: command limit reached")
            )
        if time.monotonic() - self.session.kezdet > self.korlatok.max_idotartam_s:
            self.lezar("time limit reached")
            return self._elutasit(
                _adapter_hiba("ADAPTER_SESSION_CLOSED", "session closed: time limit reached")
            )
        self.session.parancsok += 1
        return self._backend_hivas(parancs)

    def _backend_hivas(self, parancs: dict[str, Any]) -> dict[str, Any]:
        """A backend hivasa ugy, hogy semmilyen belso kivetel ne juthasson ki.

        Barmilyen I/O-, protokoll- vagy dekodolasi hiba eseten a session
        lezarul (fail-safe), es az agent egyseges, backend-fuggetlen hibat kap:
        a kivetel tipusa es szovege soha nem szivarog ki, mert abbol
        kikovetkeztetheto lenne a mogottes backend tipusa.
        """
        try:
            valasz = self._backend.kuld(parancs)
        except Exception:  # noqa: BLE001 - szandekosan minden kivetel
            self._lezar_backend_nelkul("backend error")
            return self._elutasit(
                _adapter_hiba("ADAPTER_BACKEND_ERROR", "the rover is not reachable; session closed")
            )
        if not isinstance(valasz, dict):
            self._lezar_backend_nelkul("backend error")
            return self._elutasit(
                _adapter_hiba("ADAPTER_BACKEND_ERROR", "the rover is not reachable; session closed")
            )
        return self._szur(valasz)

    def _szur(self, valasz: dict[str, Any]) -> dict[str, Any]:
        """Privilegizalt mezok eltavolitasa + utkozesjelzes szamitasa.

        A backend kumulativ collision_count-jat nem adjuk tovabb, de a
        novekmenyebol eloallitjuk az "utolso observe ota volt-e utkozes"
        jelzest, es azt az observe valaszaba tesszuk (lasd UTKOZES_MEZO).
        """
        szamlalo = valasz.get("collision_count")
        if isinstance(szamlalo, int):
            if szamlalo < self.session.utolso_utkozes_szamlalo:
                # A szamlalo csokkent: a backend kozben resetelt (nem rajtunk at).
                # Az uj szamlalot nullarol merjuk, kulonben az utkozesek elvesznek.
                self.session.utolso_utkozes_szamlalo = 0
            if szamlalo > self.session.utolso_utkozes_szamlalo:
                self.session.utkozes_az_utolso_parancs_ota = True
            self.session.utolso_utkozes_szamlalo = szamlalo

        szurt = {k: v for k, v in valasz.items() if k not in ELREJTETT_MEZOK and k != "request_id"}
        if "sensor_center" in szurt:
            szurt[UTKOZES_MEZO] = self.session.utkozes_az_utolso_parancs_ota
            # Az observe leolvassa a jelzest, es nullazza a kovetkezo parancsig.
            self.session.utkozes_az_utolso_parancs_ota = False
        return szurt
