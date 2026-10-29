#!/usr/bin/env python3
"""M11: egyparancsos kiserletinditas es eredmeny-osszesites.

Lefuttat N darab kontroller-futast egymas utan, majd a vegen automatikusan
lefuttatja a summarize_runs.py-t az osszesitett eredmenyekkel. Igy nem kell
kulon-kulon inditani a mereset es az osszesitest.

A --controller kapcsoloval barmelyik, a controllers/ mappaban levo kontroller
merheto ugyanezzel a receptel (M13+: agent-alapu es tanult kontrollerek), amig
elfogadja a --host/--port/--max-lepes kapcsolokat es a kozos naploformatumba ir.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="M11 egyparancsos kiserletinditas")
    parser.add_argument(
        "--futasok-szama",
        type=int,
        default=30,
        help="Hany egymas utani futast inditson el (alapertelmezett: 30).",
    )
    parser.add_argument(
        "--controller",
        default="baseline_line_follower.py",
        help=(
            "A futtatando kontroller a controllers/ mappaban vagy teljes utvonalkent "
            "(alapertelmezett: baseline_line_follower.py)."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-lepes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--elvart-szcenario", default=None)
    args = parser.parse_args()

    projekt_gyoker = Path(__file__).resolve().parent.parent
    megadott = Path(args.controller)
    kontroller_szkript = (
        megadott if megadott.is_absolute() else projekt_gyoker / "controllers" / megadott
    )
    if not kontroller_szkript.is_file():
        print(f"Nincs ilyen kontroller: {kontroller_szkript}", file=sys.stderr)
        return 2
    summarize_szkript = projekt_gyoker / "controllers" / "summarize_runs.py"

    if not args.elvart_szcenario:
        print(
            "Figyelem: --elvart-szcenario nelkul nem ellenorizzuk, melyik palya van betoltve. "
            "Elozetesen regisztralt meresnel mindig add meg.",
            file=sys.stderr,
        )
    print(f"=== {args.futasok_szama} futas inditasa ({kontroller_szkript.name}) ===")
    for i in range(1, args.futasok_szama + 1):
        print(f"--- Futas {i}/{args.futasok_szama} ---")
        parancs = [
            sys.executable,
            str(kontroller_szkript),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--max-lepes",
            str(args.max_lepes),
        ]
        if args.seed is not None:
            # Futasonkent eltero zaj-seed: alap + a futas sorszama - 1.
            parancs += ["--seed", str(args.seed + i - 1)]
        if args.elvart_szcenario:
            parancs += ["--elvart-szcenario", args.elvart_szcenario]

        eredmeny = subprocess.run(parancs)
        if eredmeny.returncode != 0:
            print(f"Hiba tortent a(z) {i}. futasnal, leallitas.", file=sys.stderr)
            return eredmeny.returncode

    print("\n=== Osszesites futtatasa ===")
    osszesito_eredmeny = subprocess.run(
        [sys.executable, str(summarize_szkript), "--utolso", str(args.futasok_szama)]
    )
    return osszesito_eredmeny.returncode


if __name__ == "__main__":
    raise SystemExit(main())
