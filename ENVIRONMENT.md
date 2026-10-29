# Környezetleírás

## Szoftverkövetelmények

| Eszköz | Verzió | Megjegyzés |
|---|---|---|
| Unity | 6000.3.20f1 LTS | Universal Render Pipeline (URP), Test Framework 1.6.0 |
| Python (projekt) | 3.9.6 | a kontrollerek, tesztek, elemzőszkriptek és a CI ezen futnak |
| Python (MCP-szerver) | 3.12 | csak az M12 adapter MCP-szerveréhez, `uv`-vel, izoláltan |
| uv | 0.12+ | az MCP-szerver Python 3.12-es futtatókörnyezetéhez |
| Git | 2.50.1 | |
| IDE | PyCharm / Rider | |

## Unity projekt

- Elérési út a repóban: `unity/`
- Fő jelenet: `unity/Assets/Scenes/TrackScene.unity`
- Sablon: 3D URP
- Tesztek: `unity/Assets/Tests/EditMode/`, `unity/Assets/Tests/PlayMode/`
  (Unity Test Runner; a CI-ban nem futnak, lásd `tests/README.md`)

## Python környezet

A projekt virtuális környezete a `.venv` (Python 3.9), a
verziókövetésből kizárva.

```bash
/usr/bin/python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ci.txt
```

| Csomag | Verzió | Mire kell |
|---|---|---|
| black | 25.11.0 | formázás-ellenőrzés (a verzió rögzítve: a black stabil stílusa évente változik) |
| pyflakes | 3.4.0 | statikus kódellenőrzés |
| jsonschema | 4.25.1 | szcenárió- és protokoll-séma validáció |
| matplotlib | 3.9.4 (Python 3.9 alatt) | replay-vizualizáció és videó |

A teljes, tranzitív függőségekkel együtt rögzített lista a
`requirements-ci.txt` (lock-fájl, `uv pip compile`-lal generálva); a CI
is ebből telepít, így a helyi és a CI-környezet ugyanazokat a verziókat
kapja. Az MCP-szerver lock-fájlja a `requirements-mcp.txt`.

A kontrollerek és a `common/` modulok maguk csak a Python standard
library-t használják; a fenti csomagok az ellenőrzésekhez és a
vizualizációhoz kellenek.

### MCP-szerver (M12)

Az MCP Python SDK 3.10+-t igényel, ezért az adapter MCP-szervere nem a
projekt venv-jéből fut, hanem izoláltan:

```bash
uv run --no-project --python 3.12 --with-requirements requirements-mcp.txt \
  python adapter/mcp_szerver.py --backend mock
```

A `--no-project` kötelező: nélküle az `uv` a repó `.venv`-jét kezeli
sajátjaként és újraépíti. Az adapter magja (`adapter/backend.py`,
`adapter/orseg.py`) és a tesztek 3.9-kompatibilisek maradnak.

## Ellenőrzés

```bash
./scripts/doctor                      # verziók és függőségek
python3 tests/adapter_test.py         # adapter (Unity nélkül)
python3 scripts/referencia_epizod.py  # referenciaepizód (Unity nélkül)
```

Teljes recept: `REPRODUCIBILITY.md`.
