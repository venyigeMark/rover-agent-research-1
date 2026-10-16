# Reprodukálhatóság

Ez a dokumentum lépésről lépésre leírja, hogyan futtatható újra a projekt
jelenlegi állapota egy friss klónból, m01-m06 mérföldkövek szerint.

## 1. Előfeltételek

- **Unity**: 6000.3.20f1 LTS (lásd [ENVIRONMENT.md](ENVIRONMENT.md))
- **Python**: 3.9+ (virtuális környezetben ajánlott)
- **Git**

## 2. Klónozás és ellenőrzés

```bash
git clone https://github.com/Dalma1991/rover-agent-research.git
cd rover-agent-research
./scripts/doctor
```

A `scripts/doctor` ellenőrzi a Python/Git verziót és az alapfájlok meglétét.

## 3. Unity projekt megnyitása

1. Nyisd meg a `unity/` mappát Unity Hub-ból (6000.3.20f1 LTS-szel)
2. Válaszd ki a `TrackScene`-t (M06-M07), vagy a `NetworkControlScene`-t
   (M03-M05 közvetlen gateway-teszteléshez)
3. Nyomj Play-t

## 4. Python gateway kliens

```bash
cd gateway
# nincs külső függőség: a kliens csak a Python standard libraryt használja
python3 client.py
```

Interaktív parancsok: `observe`, `move <táv> <sebesség>`, `turn <szög> <szögsebesség>`,
`stop`, `get_status`, `reset_error`, `quit` (lásd [docs/protocol.md](docs/protocol.md)).

## 5. Tesztek futtatása

### Protokoll fuzz/property-based tesztek (M05)

Előfeltétel: a Unity Play mód fusson (`NetworkControlScene` vagy `TrackScene`).

```bash
python3 tests/protocol_fuzz_test.py -v
```

### Szcenárió reprodukálhatósági teszt (M06)

Nem igényel futó Unity-t, tisztán Python.

```bash
python3 tests/scenario_seed_test.py -v
```

### Szcenárió validátor (M06)

```bash
pip install jsonschema
python3 experiments/scenario_validator.py "experiments/scenarios/*.json"
```

### Python unit tesztek (M09-M11, nem igényelnek futó Unity-t)

```bash
python3 tests/baseline_line_follower_test.py -v
python3 tests/kiserlet_naplo_test.py -v
python3 tests/replay_visualizer_test.py -v
```

Ugyanezeket futtatja automatikusan a GitHub Actions CI is minden
`main`-re történő push-nál (`.github/workflows/ci.yml`).

### Méréssorozat indítása és összesítése (M09-M11)

Előfeltétel: Unity Play mód a `TrackScene`-nel. Az akadályok az
alapértelmezett `stadium-train-baseline.json` szcenárióban időzítve,
rövid ablakokban láthatók; az M10/M10.5 végleges mérések a
`TrackController` Inspectorában átállított
`stadium-train-baseline-always-visible.json` szcenárióval készültek.

```bash
#Megbizonyosodunk róla hogy a HEAD-en lévő v3 kontrollert futtassa az instrukció
git checkout 7d86198
# N futas egymas utan + automatikus osszesites (csak az uj futasokra)
python3 controllers/futtat_kiserletet.py --futasok-szama 30

# korabbi futasok utolagos osszesitese
python3 controllers/summarize_runs.py --utolso 30

# lepesenkenti naplo elemzese es replay-kep
python3 controllers/analyze_step_log.py
python3 controllers/replay_visualizer.py
```

A run-szintű napló a `logs/m09_runs.jsonl`, a lépésenkénti napló a
`logs/kiserlet_naplo.jsonl` (M11 séma) fájlba íródik.

## 5b. Referenciaepizód friss klónból (M11 elfogadási feltétel)

Nem igényel futó Unity-t. A `experiments/referencia_epizod/` mappa
egy teljes, 500 lépéses baseline-futás lépésenkénti naplóját
tartalmazza (`referencia_epizod.jsonl`, M11 naplóséma, Unity
szimulátor, `stadium-train-baseline-always-visible.json` szcenárió,
M10.5-ös kontroller-paraméterek), valamint a belőle számított elvárt
metrikákat (`elvart.json`).

```bash
git clone https://github.com/Dalma1991/rover-agent-research.git
cd rover-agent-research
pip install matplotlib
python3 scripts/referencia_epizod.py
```

Elvárt kimenet: a szkript kiírja a metrikákat, `OK: a referenciaepizod
metrikai megegyeznek az elvart ertekekkel.` üzenettel zár, és
elkészíti a `docs/screenshots/referencia_replay.png` replay-képet.
Az elvárt értékek (`experiments/referencia_epizod/elvart.json`):

| Metrika | Érték |
|---|---|
| Lépések száma | 500 |
| Mozgásparancsok (turn/move, observe nélkül) | 667 |
| VONALON→AKADALY belépések | 1 |
| AKADALY→VISSZATALALAS→VONALON | 1 → 1 |
| VONALON→KERESES belépések | 34 |
| Ütközések (collision_count növekmény) | 6 |
| Zsákutca-eszkaláció (AKADALY→KERESES) | 0 |

Ha bármelyik érték eltér, a szkript felsorolja az eltéréseket és
nem-nulla kilépési kóddal tér vissza. Ugyanez a lépés a CI-ban is
lefut minden push-nál, így a referenciaepizód reprodukálhatósága
folyamatosan ellenőrzött.

A CI (`.github/workflows/ci.yml`) ezen felül futtatja a Python
teszteket, a szcenárió-séma validációt (`experiments/scenario_validator.py`),
a formázás-ellenőrzést (`black --check`), a statikus kódellenőrzést (`pyflakes`) és a dokumentáció-ellenőrzést
(`scripts/ellenoriz_dokumentaciot.py`: a dokumentumokban hivatkozott
fájlok verziókövetettek-e).

## 5c. Az M12 MCP-adapter indítása és ellenőrzése

Az adapter magja (`adapter/backend.py`, `adapter/orseg.py`) és a tesztek
Python 3.9-en futnak, az MCP-szerver viszont Python 3.10+-t igényel. A projekt
virtuális környezetét nem kell váltani; az MCP-szerver külön indul:

```bash
# tesztek (Unity nélkül, a projekt 3.9-es venv-jéből)
python3 tests/adapter_test.py -v

# MCP-szerver mock backenddel (izolált 3.12-es környezetben)
uv run --no-project --python 3.12 --with mcp \
  python adapter/mcp_szerver.py --backend mock --mock-akadalyokkal

# MCP-szerver élő Unity ellen (Play mód szükséges)
uv run --no-project --python 3.12 --with mcp \
  python adapter/mcp_szerver.py --backend unity

# a tool schema újraexportálása / ellenőrzése
uv run --no-project --python 3.12 --with mcp python scripts/export_tool_schema.py
uv run --no-project --python 3.12 --with mcp python scripts/export_tool_schema.py --ellenoriz
```

Claude Code-hoz így regisztrálható (a repó gyökeréből):

```bash
claude mcp add rover -- "$HOME/.local/bin/uv" run --no-project --python 3.12 \
  --with mcp python "$PWD/adapter/mcp_szerver.py" --backend mock --mock-akadalyokkal
claude mcp list
```

Fontos: az `uv run`-t a repó gyökerében **`--no-project` nélkül ne** futtasd,
mert az `uv` sajátjaként kezeli és újraépíti a projekt `.venv`-jét.

## 6. Mérföldkövek és a hozzájuk tartozó fő artifactok

| Mérföldkő | Git tag | Fő fájlok |
|---|---|---|
| M01 | `m01` | `scripts/doctor`, `src/main.py` |
| M02 | `m02` | `unity/Assets/Scripts/MovementController.cs`, `docs/videos/movement-demo.mp4` |
| M03 | `m03` | `unity/Assets/Scripts/RoverGatewayServer.cs` (v0), `gateway/client.py` |
| M04 | `m04` | `unity/Assets/Prefabs/RoverChassis.prefab`, `docs/coordinate-system.md` |
| M05 | `m05` | `docs/protocol.md`, `unity/Assets/Scripts/RoverGatewayServer.cs` (v1), `tests/protocol_fuzz_test.py`, `docs/state_machine.svg` |
| M06 | `m06` | `docs/scenario.schema.json`, `docs/scenario-schema.md`, `scripts/generate_scenario_seed.py`, `scripts/generate_example_scenarios.py`, `experiments/scenario_validator.py`, `experiments/scenarios/*.json`, `tests/scenario_seed_test.py`, `unity/Assets/Scripts/TrackController.cs`, `docs/screenshots/m06-*.png` |
| M07 | `m07` | `unity/Assets/Scripts/ColorSensor.cs`, `unity/Assets/Scripts/SensorArray.cs`, `unity/Assets/Scenes/TrackScene.unity`, `docs/sensors.md` |
| M08 | `m08` | `unity/Assets/Scripts/LidarSensor.cs`, `docs/lidar.md` |
| M09 | `m09` | `controllers/baseline_line_follower.py`, `controllers/summarize_runs.py`, `tests/baseline_line_follower_test.py`, `docs/m09-plan.md`, `docs/baseline_state_machine.svg`, `logs/m09_runs.jsonl` |
| M10 | `m10` | `unity/Assets/Scripts/RoverGatewayServer.cs` (ütközésdetektálás), `controllers/analyze_step_log.py`, `docs/m10-plan.md`, `docs/videos/m10-akadalykerules-demo.mov`, `logs/m10_vegleges_30_futas_lepesnaplo.jsonl`, `experiments/scenarios/stadium-train-baseline-always-visible.json` |
| M10.5 (nem hivatalos) | `m10-5` | `controllers/baseline_line_follower.py` (AKADALY előrehaladás, 15°, `AKADALY_KUSZOB_KILEPES_M`=1.1), `docs/m10-5-plan.md` |
| M12 | `m12` | `adapter/backend.py`, `adapter/orseg.py`, `adapter/mcp_szerver.py`, `tests/adapter_test.py`, `scripts/export_tool_schema.py`, `docs/m12-plan.md`, `docs/m12-security-review.md`, `docs/m12-tool-schema.json`, `docs/m12/agent-session-raw.txt`, `docs/m12/security-review-raw.txt` |
| M10.6 (nem hivatalos) | `m10-6` | `controllers/baseline_line_follower.py` (AKADALY elhaladási fázis, VISSZATALALAS-AKADALY visszatérés, KERESES körív, ERROR-reset), `controllers/kor_metrika.py`, `docs/m10-6-plan.md`, `docs/m10-6-meres.json`, `experiments/m10_6_referencia_futas.jsonl` |
| M11 | `m11` | `common/kiserlet_naplo.py`, `controllers/replay_visualizer.py` (`--video`), `controllers/futtat_kiserletet.py`, `controllers/summarize_runs.py` (`--utolso`), `scripts/referencia_epizod.py`, `scripts/ellenoriz_dokumentaciot.py`, `experiments/referencia_epizod/`, `unity/Assets/Tests/EditMode/TrackControllerGeometriaTeszt.cs`, `unity/Assets/Tests/PlayMode/TrackSceneTeszt.cs`, `unity/Assets/Scripts/TrackController.cs` (fantom-ív javítás), `tests/kiserlet_naplo_test.py`, `tests/replay_visualizer_test.py`, `tests/README.md`, `.github/workflows/ci.yml`, `docs/m11-plan.md`, `docs/videos/m11-referencia-replay.gif`, `docs/screenshots/referencia_replay.png`, `docs/screenshots/m11-unity-tests-editmode.png`, `docs/screenshots/m11-unity-tests-playmode.png` |
| M11.1 (utólagos CI-pótlás) | `m11.1` | `.github/workflows/ci.yml` (`black --check`, rögzített verziók), `pyproject.toml` |

Egy adott mérföldkő állapotának pontos visszaállításához:

```bash
git checkout m05   # vagy m01, m02, ..., m10, m10-5, m10-6, m11, m11.1, m12
```

## 7. Ismert korlátok

- A `protocol_fuzz_test.py` élő Unity-kapcsolatra támaszkodó tesztjei
  időnként megbízhatatlanná válnak (socket timeout) helyi hálózati/
  erőforrás-terhelés miatt - ez tesztinfrastruktúra-korlát, nem
  protokollhiba (lásd [AI_USAGE.md](AI_USAGE.md)). Eredetileg csak a
  `test_move_randomizalt_tartomanyok` és `test_turn_randomizalt_tartomanyok`
  teszteknél figyeltük meg ezt (M05), de egy M11-es futtatáskor
  fordítva történt: pont ez a két teszt futott le sikeresen, míg a
  `setUp()`-ban `reset_error` parancsra váró többi teszt bukott
  timeout-tal - vagyis a jelenség általánosabb, mint az eredeti
  megfigyelés sugallta, és bármelyik, hálózati választ váró tesztet
  érintheti.
- A Codex (JetBrains AI Assistant) havi kvótája M06 közben kimerült; az érintett
  fájlokat (`experiments/scenario_validator.py`, `tests/scenario_seed_test.py`,
  `unity/Assets/Scripts/TrackController.cs`) Claude írta, ez az `AI_USAGE.md`-ben
  dokumentálva van.

## Nagy bináris fájlok és a Git-LFS

**Döntés: a projekt nem vezet be Git-LFS-t.** Ezt tudatos választásként
rögzítjük, nem mulasztásként.

### A jelenlegi állapot

| Fájl | Méret |
|---|---|
| `docs/videos/m10-akadalykerules-demo.mov` | 68 MB |
| `docs/screenshots/unity-friss-klon.png` | 10 MB |
| `logs/m10_vegleges_30_futas_lepesnaplo.jsonl` | 7 MB |
| `docs/videos/m11-referencia-replay.gif` | 4 MB |

A `.git` könyvtár ezekkel együtt kb. 112 MB.

### Miért nem LFS

1. **Visszamenőleg nem segítene.** Az LFS-be mozgatás nem törli a már
   meglévő blobokat a history-ból — ahhoz history-átírás kellene, amit a
   projekt kizárt: az áthelyezné az `m01`–`m12` tageket, amelyek a
   reprodukálhatóság bizonyítékai, és amelyekre azóta Zenodo-kiadások és
   DOI-k is hivatkoznak.
2. **Rontaná a friss klónból való reprodukálhatóságot.** Git-LFS nélkül a
   klónozó csak mutatófájlokat kap a tényleges tartalom helyett. A projekt
   egyik alapkövetelménye, hogy friss klónból, extra eszköz telepítése
   nélkül reprodukálható legyen — az LFS pont ezzel megy szembe.
3. **A méret nem szorít.** A GitHub fájlonkénti korlátja 100 MB; a
   legnagyobb fájlunk 68 MB. A repó mérete kényelmes határon belül van.

### A helyette bevezetett szabály

Új, **10 MB fölötti bináris** nem kerül a verziókövetésbe. Az ilyen
tartalom (demóvideó, nagy felbontású képernyőkép, nyers mérési adat)
GitHub release-mellékletként vagy a mérföldkőhöz tartozó Zenodo-kiadás
mellékleteként kerül közzé, a dokumentáció pedig linkkel hivatkozik rá.

### Mikor kell újragondolni

Ha egyetlen fájl meghaladná a 100 MB-ot (a GitHub ezt elutasítja), vagy ha
a `.git` 500 MB fölé nőne. Addig a fenti szabály elegendő.

## Az M10 kapu mérésének reprodukálása (2026-10-08)

A Unityben a `TrackScene` szcenáriója legyen
`stadium-train-baseline-always-visible`, Play módban, az ablak előtérben:

```bash
python3 controllers/futtat_kiserletet.py --futasok-szama 30 --max-lepes 1500 \
    --elvart-szcenario stadium-train-baseline-always-visible
python3 controllers/kor_metrika.py --utolso 30
```

A futásonkénti metaadat (szcenárió, time scale, commit, tiszta-e a
munkakönyvtár) a helyi logs/ mappába kerül (kiserlet_naplo_meta.jsonl; nincs verziókövetve). A hivatalos mérés
adatai: `docs/m10-meres.json`, `docs/m10-meres-meta.jsonl`; a terv és az
eredmény: `docs/m10-plan.md`.
