#!/usr/bin/env python3
"""Osszegzo statisztika az M09/M10 baseline kontroller futasi naploibol.

Megjegyzes: az "utkozott"/"utkozesek_szama" mezok csak az M10 bovites
(RoverGatewayServer collision_occurred/collision_count) utan keszult
naplobejegyzesekben szerepelnek - regebbi (M09) sorokban hianyozhatnak,
ezert ezekre .get(..., alapertelmezett) hasznalatos.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

NAPLO_FAJL = Path(__file__).resolve().parent.parent / "logs" / "m09_runs.jsonl"


def utolso_n_futas(n: int) -> list[dict]:
    if not NAPLO_FAJL.is_file():
        return []
    sorok = [s for s in NAPLO_FAJL.read_text(encoding="utf-8").splitlines() if s.strip()]
    return [json.loads(sor) for sor in sorok[-n:]] if n > 0 else []


def _szoras(adatok) -> float:
    """Szoras; egyetlen adatnal 0.0 (a statistics.stdev ilyenkor kivetelt dob)."""
    adatok = list(adatok)
    return statistics.stdev(adatok) if len(adatok) >= 2 else 0.0


def osszegez(n: int = 30) -> None:
    futasok = utolso_n_futas(n)
    if not futasok:
        print(f"Nincs osszegezheto futas: {NAPLO_FAJL}")
        return

    parancsok = [f.get("parancsok_szama", 0) for f in futasok]
    vonalveszesek = [f.get("vonalvesztesek_szama", 0) for f in futasok]
    akadalykerulesek = [f.get("akadaly_kerulesek_szama", 0) for f in futasok]
    zsakutcak = [f.get("zsakutcak_szama", 0) for f in futasok]
    palyaelhagyasok = sum(1 for f in futasok if f.get("palyaelhagyas", False))
    utkozesek = [f.get("utkozesek_szama", 0) for f in futasok]
    utkozott_futasok = sum(1 for f in futasok if f.get("utkozott", False))

    print(f"Osszegzes ({len(futasok)} futas):")
    print(
        f"  Parancsok szama:      atlag={statistics.mean(parancsok):.1f}, "
        f"szoras={_szoras(parancsok):.1f}, "
        f"min={min(parancsok)}, max={max(parancsok)}"
    )
    print(
        f"  Vonalvesztesek szama: atlag={statistics.mean(vonalveszesek):.1f}, "
        f"szoras={_szoras(vonalveszesek):.1f}, "
        f"min={min(vonalveszesek)}, max={max(vonalveszesek)}"
    )
    print(
        f"  Akadalykerulesek:     atlag={statistics.mean(akadalykerulesek):.1f}, "
        f"szoras={_szoras(akadalykerulesek):.1f}, "
        f"min={min(akadalykerulesek)}, max={max(akadalykerulesek)}"
    )
    print(
        f"  Zsakutcak szama:      atlag={statistics.mean(zsakutcak):.1f}, "
        f"szoras={_szoras(zsakutcak):.1f}, "
        f"min={min(zsakutcak)}, max={max(zsakutcak)}"
    )
    print(f"  Palyaelhagyasok:      {palyaelhagyasok}/{len(futasok)} futasban")
    print(
        f"  Utkozesek szama:      atlag={statistics.mean(utkozesek):.1f}, "
        f"szoras={_szoras(utkozesek):.1f}, "
        f"min={min(utkozesek)}, max={max(utkozesek)}"
    )
    print(f"  Utkozott futasok:     {utkozott_futasok}/{len(futasok)} futasban")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Baseline futasi naplok osszegzese")
    parser.add_argument(
        "--utolso",
        type=int,
        default=30,
        help="Hany legutobbi futast osszegezzen a naplobol (alapertelmezett: 30).",
    )
    args = parser.parse_args()
    osszegez(args.utolso)
