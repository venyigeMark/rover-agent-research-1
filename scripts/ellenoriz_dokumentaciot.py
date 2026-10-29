#!/usr/bin/env python3
"""Dokumentacio-ellenorzes (M11 CI): a README.md, REPRODUCIBILITY.md es a
docs/*.md fajlokban backtick kozott hivatkozott repo-beli utvonalak
verziokovetettek-e (git ls-files), vagy szerepelnek-e a futasidoben
generalt fajlok explicit listajaban. Igy helyben es friss klonban (CI)
ugyanazt az eredmenyt adja. Csak olyan hivatkozasokat vizsgal, amelyek egyertelmuen
fajlutvonalnak neznek ki (tartalmaznak '/'-t vagy ismert kiterjesztest,
es nem parancsok). Hianyzo fajl eseten nem-nulla kilepesi kod."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

GYOKER = Path(__file__).resolve().parent.parent
FAJLOK = [
    GYOKER / "README.md",
    GYOKER / "REPRODUCIBILITY.md",
    *sorted((GYOKER / "docs").glob("*.md")),
]
MINTA = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|md|cs|json|yml|yaml|cff|svg|png|mov|mp4|jsonl|unity|prefab|asmdef))`"
)
KIHAGY = ("http", "*")
# Futasidoben generalt, szandekosan nem verziokovetett fajlok (.gitignore):
# ezekre a dokumentacio hivatkozhat anelkul, hogy a repoban lennenek.
FUTASIDOBEN_GENERALT = {
    "logs/kiserlet_naplo.jsonl",  # M11 lepesenkenti naplo (minden futasnal bovul)
    "logs/m10_lepes_naplo.jsonl",  # M10 regi formatumu lepesnaplo (tortenetileg hivatkozott)
    "logs/referencia_replay.png",  # a referenciaepizod ellenorzesenek replay-kepe
}


def verziokovetett_fajlok() -> set[str]:
    # Verziokovetett + uj, meg nem commitolt, de nem ignoralt fajlok
    # (--others --exclude-standard), hogy egy uj fajl es a ra hivatkozo
    # dokumentacio egyutt, egy commitban is atmehessen az ellenorzesen.
    kimenet = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=GYOKER,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return set(kimenet.split())


def main() -> int:
    hianyzo: list[tuple[Path, str]] = []
    ellenorzott = 0
    tracked = verziokovetett_fajlok()
    for md in FAJLOK:
        for hivatkozas in MINTA.findall(md.read_text(encoding="utf-8")):
            if any(k in hivatkozas for k in KIHAGY) or "/" not in hivatkozas:
                continue
            ellenorzott += 1
            if hivatkozas not in tracked and hivatkozas not in FUTASIDOBEN_GENERALT:
                hianyzo.append((md.relative_to(GYOKER), hivatkozas))
    print(f"{ellenorzott} hivatkozas ellenorizve {len(FAJLOK)} dokumentumban.")
    if hianyzo:
        print("HIANYZO fajlok:")
        for md, h in hianyzo:
            print(f"  {md}: {h}")
        return 1
    print("OK: minden hivatkozott fajl verziokovetett vagy dokumentaltan futasidoben generalt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
