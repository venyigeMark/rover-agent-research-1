"""MCP-szerver a rover vezerlesehez (M12, 3. munkacsomag).

Az agent (Claude Code) ezen a hat eszkozon keresztul latja a rovert:
observe, get_status, move, turn, stop, session_status.

A reset_position SZANDEKOSAN nem agent-eszkoz: egy valodi rovert nem lehet
teleportalni, tehat ez a muvelet elarulna, hogy szimulacio all mogotte (lasd
docs/m12-security-review.md). A kiserleti futasok kozotti pozicio-resetet a
meresinditó szkript vegzi kozvetlenul a backenden, az Orseg.reset_position()
metoduson keresztul.

Amit az agent NEM kap meg:
- shell- vagy fajlrendszer-hozzaferest,
- a Unity szimulator privilegizalt mezoit (pozicio, sebesseg, utkozesszamlalo),
- a v1 protokoll tovabbi parancsait (reset_error, reset_position),
- azt az informaciot, hogy valodi Unity-szimulacio vagy mock all mogotte.

Inditas (a projekt Python 3.9-es venv-je erintetlen marad):
    uv run --no-project --python 3.12 --with-requirements requirements-mcp.txt \
        python adapter/mcp_szerver.py --backend mock
    uv run --no-project --python 3.12 --with-requirements requirements-mcp.txt \
        python adapter/mcp_szerver.py --backend unity

A --backend valasztas a kiserletvezetoe, nem az agente; az agent szamara a
ket eset megkulonboztethetetlen.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapter.backend import MockAkadaly, MockBackend, UnityTcpBackend  # noqa: E402
from adapter.orseg import Orseg, SessionKorlatok  # noqa: E402

from mcp.server.mcpserver import MCPServer  # noqa: E402

_orseg: Orseg | None = None

szerver = MCPServer(
    name="rover",
    version="0.12.0",
    instructions=(
        "Egy vonalkoveto rover vezerlese egy stadion alaku palyan. "
        "A rover harom szinszenzorral (bal/kozep/jobb) latja a feher vonalat, "
        "es egy 6 szektoros Lidarral az akadalyokat. Minden lepesnel eloszor "
        "hivj observe-ot, majd dontsd el a kovetkezo move/turn parancsot. "
        "A munkamenet korlatozott (parancsszam, ido, ossztavolsag): a "
        "session_status megmutatja, mennyi maradt (az elutasitott hivasok is "
        "fogyasztanak a parancskeretbol). Nincs hozzaferesed a rover valos "
        "pozciojahoz vagy sebessegehez - csak a szenzorokra tamaszkodhatsz. Ha "
        "egy hivas ADAPTER_BACKEND_ERROR-t ad, a rover elerhetetlenne valt es a "
        "munkamenet lezarult; ilyenkor ne probalkozz tovabb."
    ),
)


def orseg() -> Orseg:
    if _orseg is None:
        raise RuntimeError("Az adapter nincs inicializalva.")
    return _orseg


@szerver.tool(
    description=(
        "Leolvassa a rover szenzorait. Minden allapotban hivhato, nem mozgatja "
        "a rovert. Visszaadott mezok: sensor_left / sensor_center / "
        "sensor_right a harom lefele nezo szinszenzor (a rover kozepvonalatol balra 0.3 m, kozepen es jobbra 0.3 m, "
        "mindharom 0.26 m-rel a rover kozeppontja elott): "
        "'white' = a feher vonal folott van-e, 'intensity' 0-1 folytonos ertek "
        "(1.0 = pontosan a vonal kozepen, 0.0 = a vonaltol legalabb 10 cm-re); "
        "vonalkovetesnel a bal es jobb szenzor intensity-kulonbsege adja a "
        "korrekcio iranyat. A lidar_szektor_min 6 szam: a rover elotti 180 "
        "fokos legyezo hat, egyenkent 30 fokos szektoranak legkozelebbi "
        "akadalytavolsaga meterben, balrol jobbra ([0] = 90-60 fok balra, "
        "[2] = 30-0 balra, [3] = 0-30 jobbra, [5] = 60-90 jobbra); a 10.0 azt "
        "jelenti, hogy az adott szektorban nincs akadaly hatotavon belul. A "
        "rover a kerekekkel kb. 1.7 m szeles (+-0.85 m a kozepvonaltol), az "
        "eleje 0.65 m-re van a kozepponttol, a LiDAR a kozepvonalon, 0.26 m-rel a "
        "kozeppont elott ul. Ezert a [2] es [3] szektor onmagaban nem eleg: egy "
        "oldalt, akar 60 fokban latott akadaly is a rover savjaba eshet. A "
        "lidar_nyers sugaraibol kiszamolhato, mi esik a +-0.85 m-es savba - ha "
        "ott 1 m-en belul akadaly van, fordulj, ne haladj tovabb. A "
        "lidar_nyers ugyanezt a merest adja tomorites nelkul: 36 szam, "
        "balrol jobbra, kb. 5 fokonkent egy sugar. A lidar_nyers_ervenyes "
        "azonos hosszu logikai lista: true, ha az adott sugar talalt valamit. "
        "A false ketfele lehet - vagy nincs akadaly hatotavon belul (vagyis "
        "szabad az irany, ez a tipikus eset), vagy kimaradt a meres; a ketto "
        "nem megkulonboztetheto. A false tehat nem szenzorhiba. A "
        "lidar_szektor_min minden eleme a hozza "
        "tartozo 6 nyers sugar minimuma; hasznald, amelyik kenyelmesebb. A "
        "collision_detected jelzi, volt-e utkozes az elozo observe ota "
        "(bumper/gyorsulasmero): ha true, ne ismeteld ugyanazt a parancsot. A "
        "rover valos pozicioja es sebessege nem lekerdezheto."
    )
)
def observe() -> dict[str, Any]:
    return orseg().observe()


@szerver.tool(
    description=(
        "Megadja a rover allapotgepenek aktualis allapotat. Nem mozgatja a "
        "rovert. A 'state' erteke: IDLE (all, parancsra kesz), MOVING (eppen "
        "halad), TURNING (eppen fordul), ERROR (hibaallapot). ERROR allapotban "
        "a move es a turn hivasok elutasitasra kerulnek, es az elutasitott "
        "hivas is fogyaszt a parancskeretbol - ha ezt latod, ne probalkozz "
        "tovabb ugyanazzal, hanem jelezd a problemat; ERROR-bol az agent nem "
        "tud sajat erobol kilepni. A 'last_command_result' az elozo parancs "
        "nevet es kimenetelet adja meg, ilyen alakban: 'move:completed', "
        "'turn:rejected' - akkor hasznos, ha egy valasz nem erkezett meg es nem "
        "tudod, vegrehajtodott-e. Mint az observe, ez a hivas is fogyaszt a "
        "parancskeretbol."
    )
)
def get_status() -> dict[str, Any]:
    return orseg().get_status()


@szerver.tool(
    description=(
        "Elore mozgatja a rovert. distance_m: 0.01-1.00 meter. max_speed: "
        "0.05-0.50 m/s (alapertelmezett 0.2). A parancs a mozgas "
        "befejezesekor ter vissza. Tartomanyon kivuli vagy nem szamertek "
        "eseten a hivas elutasitasra kerul (status: rejected), a rover nem "
        "mozdul; az elutasitott hivas is fogyaszt a parancskeretbol. FIGYELEM: "
        "a 'completed' status nem jelenti, hogy a rover a teljes tavolsagot "
        "megtette - akadalynak utkozve hamarabb megall, es a megtett tavolsagot "
        "nem lehet lekerdezni; a kovetkezo observe collision_detected mezoje "
        "jelzi, ha ez tortent. Az ossztavolsag-keretbe mindig a KERT tavolsag "
        "szamit bele."
    )
)
def move(distance_m: float, max_speed: float = 0.2) -> dict[str, Any]:
    return orseg().move(distance_m, max_speed)


@szerver.tool(
    description=(
        "Elforgatja a rovert a helyben. angle_deg: -180 es 180 kozott, az "
        "abszolut erteke legalabb 1; pozitiv = jobbra, negativ = balra. "
        "max_angular_speed: 5-45 fok/s (alapertelmezett 30). Tartomanyon "
        "kivuli ertek eseten a hivas elutasitasra kerul, a rover nem mozdul; "
        "az elutasitott hivas is fogyaszt a parancskeretbol."
    )
)
def turn(angle_deg: float, max_angular_speed: float = 30.0) -> dict[str, Any]:
    return orseg().turn(angle_deg, max_angular_speed)


@szerver.tool(
    description=(
        "Azonnal leallitja a rovert. Barmikor hivhato, idempotens (ha mar all, "
        "nem tortenik semmi). Lezart munkamenetben is hivhato: ilyenkor a rover "
        "mar all (a lezaras automatikusan leallitotta), a valasz ezt nyugtazza."
    )
)
def stop() -> dict[str, Any]:
    return orseg().stop()


@szerver.tool(
    description=(
        "Megmutatja a munkamenet felhasznalt es maximalis kereteit: "
        "parancsszam, eltelt ido, megtett ossztavolsag, egy move maximalis "
        "hossza, elutasitott hivasok szama, valamint hogy a munkamenet le "
        "van-e mar zarva es miert. Nem szamit bele a parancskeretbe. A limit "
        "elerese eseten a rover automatikusan leall, es a tovabbi vezerlo "
        "hivasok ADAPTER_SESSION_CLOSED hibaval terulnek vissza."
    )
)
def session_status() -> dict[str, Any]:
    return orseg().session_status()


def parancssor() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rover MCP-szerver (M12)")
    p.add_argument(
        "--backend", choices=("mock", "unity"), default=os.environ.get("ROVER_BACKEND", "mock")
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--max-parancs", type=int, default=300)
    p.add_argument("--max-ido-s", type=float, default=900.0)
    p.add_argument("--max-tavolsag-m", type=float, default=60.0)
    p.add_argument("--mock-akadalyokkal", action="store_true", help="Mock backend ket akadallyal.")
    return p.parse_args()


def main() -> int:
    global _orseg
    args = parancssor()
    if args.backend == "unity":
        backend = UnityTcpBackend(args.host, args.port)
    else:
        akadalyok = (
            [MockAkadaly(x=4.0, z=3.0), MockAkadaly(x=3.6, z=8.5)] if args.mock_akadalyokkal else []
        )
        backend = MockBackend(akadalyok=akadalyok)
    _orseg = Orseg(
        backend,
        SessionKorlatok(
            max_parancs=args.max_parancs,
            max_idotartam_s=args.max_ido_s,
            max_ossz_tavolsag_m=args.max_tavolsag_m,
        ),
    )
    # A backend tipusa csak a szerver stderr-jere kerul (a kiserletvezetonek),
    # az MCP-csatornara soha - az agent nem tudhatja meg.
    print(f"[rover-mcp] backend={args.backend} korlatok={_orseg.korlatok}", file=sys.stderr)
    szerver.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
