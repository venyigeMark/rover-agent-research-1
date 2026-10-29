#!/usr/bin/env python3
"""Task success, koridő es egyseges sikerfeltetel a lepesenkenti naplobol.

Modszer: a lepesenkenti naploban rogzitett privilegizalt pozicio (position)
alapjan a palya kozeppontja (0, 0) koruli szoget kicsomagoljuk (unwrap), es a
kumulalt szogelfordulast elosztjuk 2*pi-vel. Ez a "kor-arany": 1.0 = pontosan
egy teljes kor. A pozicio KIZAROLAG kiertekelesre hasznalhato, a vezerlesre nem
(lasd docs/protocol.md) - a szkript ezert kulon, utolagos elemzo eszkoz.

2026-10-26 ota:
- a palya meretei (egyenes, sugar, vonalszelesseg) futasonkent a tenylegesen
  betoltott szcenariobol jonnek (a <naplo>_meta.jsonl szcenario-mezoje alapjan),
  nem a train palya rogzitett ertekeibol; ismeretlen szcenarional a regi
  alapertekek maradnak, es ezt a "geometria" mezo jelzi;
- a futasszintu osszesitobol (logs/m09_runs.jsonl, run_id alapjan) a
  palyaelhagyas-jelzo is bekerul, igy egyetlen helyen adodik a SIKERES futas:
  legalabb 1 teljes kor + 0 utkozes + nincs palyaelhagyas.

Hasznalat:
    python3 controllers/kor_metrika.py                      # az alapertelmezett naplo
    python3 controllers/kor_metrika.py --naplo-fajl <fajl>  # masik naplo
    python3 controllers/kor_metrika.py --utolso 30          # csak az utolso N futas
    python3 controllers/kor_metrika.py --json               # gepi feldolgozashoz
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

GYOKER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GYOKER))

from adapter.backend import (  # noqa: E402
    PALYA_EGYENES_HOSSZ_M,
    PALYA_IV_SUGAR_M,
    PALYA_VONAL_SZELESSEG_M,
)

ALAPERTELMEZETT_NAPLO = GYOKER / "logs" / "kiserlet_naplo.jsonl"
ALAPERTELMEZETT_FUTASNAPLO = GYOKER / "logs" / "m09_runs.jsonl"
SZCENARIO_MAPPA = GYOKER / "experiments" / "scenarios"
ALAP_GEOMETRIA = (PALYA_EGYENES_HOSSZ_M, PALYA_IV_SUGAR_M, PALYA_VONAL_SZELESSEG_M)


def pozicio(sor: dict) -> dict | None:
    """A privilegizalt pozicio mind a ket naploformatumbol (M10 es M11)."""
    diag = sor.get("privilegizalt_diagnosztika") or {}
    return diag.get("position") or sor.get("position")


def utkozes_szamlalo(sor: dict) -> int | None:
    diag = sor.get("privilegizalt_diagnosztika") or {}
    ertek = diag.get("collision_count", sor.get("collision_count"))
    return int(ertek) if isinstance(ertek, (int, float)) else None


def tavolsag(x: float, z: float, hossz: float, sugar: float) -> float:
    """Tavolsag a stadion kozepvonalatol (a felkorivek csak a sajat oldalukon)."""
    fel = hossz / 2.0

    def egyenes(allando_x: float) -> float:
        return math.hypot(x - allando_x, z - max(-fel, min(fel, z)))

    def felkor(kozep_z: float, irany: float) -> float:
        dz = z - kozep_z
        return math.inf if dz * irany < 0 else abs(math.hypot(x, dz) - sugar)

    return min(egyenes(sugar), egyenes(-sugar), felkor(-fel, -1.0), felkor(fel, 1.0))


def szcenario_geometria(nev: str | None) -> tuple[tuple[float, float, float], str]:
    """(egyenes, sugar, vonalszelesseg) a szcenariofajlbol; hiba eseten az alapertek."""
    if nev:
        fajl = SZCENARIO_MAPPA / f"{nev}.json"
        try:
            palya = json.loads(fajl.read_text(encoding="utf-8"))["track"]
            return (
                float(palya["straight_length_m"]),
                float(palya["turn_radius_m"]),
                float(palya["line_width_m"]),
            ), nev
        except (OSError, KeyError, ValueError):
            pass
    return ALAP_GEOMETRIA, "alapertelmezett"


def futas_metrikai(
    sorok: list[dict], geometria: tuple[float, float, float] = ALAP_GEOMETRIA
) -> dict:
    hossz, sugar, vonal = geometria
    kerulet = 2 * hossz + 2 * math.pi * sugar
    poziciok = [p for sor in sorok if (p := pozicio(sor))]
    if len(poziciok) < 2:
        return {
            "lepesek": len(sorok),
            "kor_arany": 0.0,
            "teljes_kor": False,
            "megtett_ut_m": 0.0,
            "hatekonysag": 0.0,
            "vonalon_arany": 0.0,
            "utkozesek": 0,
            "palya_kerulet_m": round(kerulet, 2),
        }

    kumulalt_szog = 0.0
    for elozo, kovetkezo in zip(poziciok, poziciok[1:]):
        kulonbseg = math.atan2(kovetkezo["z"], kovetkezo["x"]) - math.atan2(elozo["z"], elozo["x"])
        while kulonbseg > math.pi:
            kulonbseg -= 2 * math.pi
        while kulonbseg < -math.pi:
            kulonbseg += 2 * math.pi
        kumulalt_szog += kulonbseg
    kor_arany = abs(kumulalt_szog) / (2 * math.pi)

    megtett_ut = sum(
        math.hypot(b["x"] - a["x"], b["z"] - a["z"]) for a, b in zip(poziciok, poziciok[1:])
    )
    vonalon = sum(1 for p in poziciok if tavolsag(p["x"], p["z"], hossz, sugar) <= vonal / 2.0)

    szamlalok = [c for sor in sorok if (c := utkozes_szamlalo(sor)) is not None]
    utkozesek = (max(szamlalok) - min(szamlalok)) if szamlalok else 0

    return {
        "lepesek": len(sorok),
        "kor_arany": round(kor_arany, 4),
        "teljes_kor": kor_arany >= 1.0,
        "megtett_ut_m": round(megtett_ut, 2),
        "hatekonysag": round(kor_arany * kerulet / megtett_ut, 4) if megtett_ut else 0.0,
        "vonalon_arany": round(vonalon / len(poziciok), 4),
        "utkozesek": utkozesek,
        "palya_kerulet_m": round(kerulet, 2),
    }


def jsonl_run_id_szerint(fajl: Path) -> dict[str, dict]:
    """run_id -> utolso bejegyzes; a run_id nelkuli (regi) sorokat kihagyja."""
    eredmeny: dict[str, dict] = {}
    if not fajl.is_file():
        return eredmeny
    for sor in fajl.read_text(encoding="utf-8").splitlines():
        if sor.strip():
            bejegyzes = json.loads(sor)
            if bejegyzes.get("run_id"):
                eredmeny[bejegyzes["run_id"]] = bejegyzes
    return eredmeny


def futasokra_bont(naplo_fajl: Path) -> dict[str, list[dict]]:
    futasok: dict[str, list[dict]] = {}
    for sor in naplo_fajl.read_text(encoding="utf-8").splitlines():
        if not sor.strip():
            continue
        bejegyzes = json.loads(sor)
        futasok.setdefault(bejegyzes.get("run_id", "ismeretlen"), []).append(bejegyzes)
    return futasok


def kiertekel(naplo_fajl: Path, futasnaplo: Path, utolso: int | None) -> list[dict]:
    futasok = futasokra_bont(naplo_fajl)
    meta = jsonl_run_id_szerint(naplo_fajl.with_name(naplo_fajl.stem + "_meta.jsonl"))
    osszesito = jsonl_run_id_szerint(futasnaplo)
    azonositok = list(futasok)
    if utolso:
        azonositok = azonositok[-utolso:]
    eredmenyek = []
    for run_id in azonositok:
        geometria, forras = szcenario_geometria((meta.get(run_id) or {}).get("scenario"))
        metrika = futas_metrikai(futasok[run_id], geometria)
        palyaelhagyas = (osszesito.get(run_id) or {}).get("palyaelhagyas")
        metrika.update(
            run_id=run_id,
            geometria=forras,
            palyaelhagyas=palyaelhagyas,
            sikeres=(
                None
                if palyaelhagyas is None
                else bool(metrika["teljes_kor"] and metrika["utkozesek"] == 0 and not palyaelhagyas)
            ),
        )
        eredmenyek.append(metrika)
    return eredmenyek


def kiir(eredmenyek: list[dict], naplo_fajl: Path) -> None:
    n = len(eredmenyek)
    print(f"Kor-metrika ({n} futas, {naplo_fajl.name}):")
    geometriak = sorted({e["geometria"] for e in eredmenyek})
    keruletek = sorted({e["palya_kerulet_m"] for e in eredmenyek})
    print(f"  Geometria:            {', '.join(geometriak)} (kerulet: {keruletek} m)")

    def sor(nev: str, ertekek: list[float], tizedes: int = 3) -> str:
        atlag = statistics.mean(ertekek)
        szoras = statistics.stdev(ertekek) if len(ertekek) > 1 else 0.0
        return (
            f"  {nev:<24}atlag={atlag:.{tizedes}f}, szoras={szoras:.{tizedes}f}, "
            f"min={min(ertekek):.{tizedes}f}, max={max(ertekek):.{tizedes}f}"
        )

    print(sor("Kor-arany:", [e["kor_arany"] for e in eredmenyek]))
    print(sor("Megtett ut (m):", [e["megtett_ut_m"] for e in eredmenyek], 1))
    print(sor("Hatekonysag:", [e["hatekonysag"] for e in eredmenyek]))
    print(sor("Vonalon toltott arany:", [e["vonalon_arany"] for e in eredmenyek]))
    print(sor("Utkozesek:", [float(e["utkozesek"]) for e in eredmenyek], 1))
    print(f"  TASK SUCCESS (teljes kor): {sum(e['teljes_kor'] for e in eredmenyek)}/{n} futas")
    print(f"  Utkozesmentes futas:       {sum(e['utkozesek'] == 0 for e in eredmenyek)}/{n}")
    ismert = [e for e in eredmenyek if e["sikeres"] is not None]
    if len(ismert) == n:
        print(f"  Palyaelhagyas:             {sum(bool(e['palyaelhagyas']) for e in ismert)}/{n}")
        print(
            f"  SIKERES (kor + 0 utkozes + nincs palyaelhagyas): {sum(e['sikeres'] for e in ismert)}/{n}"
        )
    else:
        print(
            f"  SIKERES: nem szamolhato - {n - len(ismert)} futashoz nincs run_id-s "
            "bejegyzes a futasszintu osszesitoben (2026-10-26 elotti futasok)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Task success es koridő a lepesnaplobol")
    parser.add_argument("--naplo-fajl", default=str(ALAPERTELMEZETT_NAPLO))
    parser.add_argument("--futasnaplo", default=str(ALAPERTELMEZETT_FUTASNAPLO))
    parser.add_argument("--utolso", type=int, default=None, help="Csak az utolso N futas.")
    parser.add_argument("--json", action="store_true", help="Gepi olvashato kimenet.")
    args = parser.parse_args()

    naplo_fajl = Path(args.naplo_fajl)
    if not naplo_fajl.is_file():
        print(f"Nincs ilyen naplofajl: {naplo_fajl}", file=sys.stderr)
        return 2

    eredmenyek = kiertekel(naplo_fajl, Path(args.futasnaplo), args.utolso)
    if not eredmenyek:
        print("A naplo nem tartalmaz futast.", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(eredmenyek, ensure_ascii=False, indent=2))
    else:
        kiir(eredmenyek, naplo_fajl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
