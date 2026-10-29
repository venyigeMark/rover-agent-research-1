#!/usr/bin/env python3
"""M11 referenciaepizod: friss klonbol reprodukalhato ellenorzes.

A repoba commitolt experiments/referencia_epizod/referencia_epizod.jsonl
lepesenkenti naplobol kiszamolja a futas metrikait, osszeveti az
elvart.json-ban rogzitett ertekekkel, es elkesziti a replay-kepet.

A replay-kep alapertelmezes szerint a logs/ ala kerul (nem verziokovetett).
Korabban az ellenorzes a verziokovetett docs/screenshots/referencia_replay.png-t
irta felul: egy friss klonban mar az elso ellenorzes "piszkos" munkafat hagyott
(a PNG bajtjai matplotlib-verzionkent elternek), es egy utana inditott meres
metaadataban git_tiszta=False lett volna. A dokumentalt kep csak --rogzit-tel
frissul.
Nem igenyel futo Unity-t. Sikertelen egyezes eseten nem-nulla
kilepesi koddal ter vissza (CI-ban is fut).

Hasznalat:
  python3 scripts/referencia_epizod.py            # ellenorzes
  python3 scripts/referencia_epizod.py --rogzit   # elvart.json es a dokumentalt kep ujrairasa
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

GYOKER = Path(__file__).resolve().parent.parent
EPIZOD_MAPPA = GYOKER / "experiments" / "referencia_epizod"
NAPLO = EPIZOD_MAPPA / "referencia_epizod.jsonl"
ELVART = EPIZOD_MAPPA / "elvart.json"
DOKUMENTALT_KEP = GYOKER / "docs" / "screenshots" / "referencia_replay.png"
ELLENORZO_KEP = GYOKER / "logs" / "referencia_replay.png"


def betolt() -> list[dict]:
    sorok = [json.loads(s) for s in NAPLO.read_text(encoding="utf-8").splitlines() if s.strip()]
    if not sorok:
        raise SystemExit(f"Ures referencia-naplo: {NAPLO}")
    return sorok


def metrikak(sorok: list[dict]) -> dict:
    run_idk = {s["run_id"] for s in sorok}
    if len(run_idk) != 1:
        raise SystemExit(
            f"A referencia-naploban pontosan egy run_id-nak kell lennie, talalt: {len(run_idk)}"
        )

    allapot_valtasok = Counter(
        f'{s["allapot_elotte"]}->{s["allapot_utana"]}'
        for s in sorok
        if s["allapot_elotte"] != s["allapot_utana"]
    )
    parancsok = sum(len(s.get("parancsok", [])) for s in sorok)

    utkozesek = 0
    elozo = None
    for s in sorok:
        d = s.get("privilegizalt_diagnosztika") or {}
        cc = d.get("collision_count")
        if cc is not None and elozo is not None and cc > elozo:
            utkozesek += cc - elozo
        if cc is not None:
            elozo = cc

    return {
        "run_id": sorok[0]["run_id"],
        "controller": sorok[0].get("controller"),
        "backend": sorok[0].get("backend"),
        "seed": sorok[0].get("seed"),
        "lepesek_szama": len(sorok),
        "parancsok_szama": parancsok,
        "akadaly_belepesek": allapot_valtasok.get("VONALON->AKADALY", 0),
        "kereses_belepesek": allapot_valtasok.get("VONALON->KERESES", 0),
        "visszatalalas_belepesek": allapot_valtasok.get("AKADALY->VISSZATALALAS", 0),
        "utkozesek_szama": utkozesek,
        "allapot_valtasok": dict(sorted(allapot_valtasok.items())),
    }


def replay_kep(run_id: str, kep: Path) -> None:
    kep.parent.mkdir(parents=True, exist_ok=True)
    parancs = [
        sys.executable,
        str(GYOKER / "controllers" / "replay_visualizer.py"),
        "--naplo-fajl",
        str(NAPLO),
        "--run-id",
        run_id,
        "--kimenet",
        str(kep),
    ]
    eredmeny = subprocess.run(parancs)
    if eredmeny.returncode != 0:
        raise SystemExit("A replay-kep elkeszitese sikertelen.")


def main() -> int:
    parser = argparse.ArgumentParser(description="M11 referenciaepizod ellenorzese")
    parser.add_argument(
        "--rogzit", action="store_true", help="Az elvart.json ujrairasa a jelenlegi ertekekkel."
    )
    parser.add_argument("--kep-nelkul", action="store_true", help="Ne keszitse el a replay-kepet.")
    args = parser.parse_args()

    sorok = betolt()
    m = metrikak(sorok)
    print(json.dumps(m, indent=2, ensure_ascii=False))

    if args.rogzit:
        ELVART.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Elvart ertekek rogzitve: {ELVART}")
    else:
        elvart = json.loads(ELVART.read_text(encoding="utf-8"))
        elteresek = {k: (elvart.get(k), m.get(k)) for k in elvart if elvart.get(k) != m.get(k)}
        if elteresek:
            print("ELTERES az elvart ertekektol (elvart, kapott):")
            for k, (e, k2) in elteresek.items():
                print(f"  {k}: {e} != {k2}")
            return 1
        print("OK: a referenciaepizod metrikai megegyeznek az elvart ertekekkel.")

    if not args.kep_nelkul:
        kep = DOKUMENTALT_KEP if args.rogzit else ELLENORZO_KEP
        replay_kep(m["run_id"], kep)
        print(f"Replay-kep: {kep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
