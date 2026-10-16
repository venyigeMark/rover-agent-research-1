[![CI](https://github.com/Dalma1991/rover-agent-research/actions/workflows/ci.yml/badge.svg)](https://github.com/Dalma1991/rover-agent-research/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22161119.svg)](https://doi.org/10.5281/zenodo.22161119)

# rover-agent-research

Kutatási projekt: *Simulation-Blind Two-Timescale Rover Control by
General-Purpose Coding Agents* (Miskolci Egyetem, Hatvany József
Informatikai Tudományok Doktori Iskola).

Egy rover Unity-szimulációban, egységes, külső szenzor-akció interfészen
keresztül irányítva — hagyományos algoritmussal, AI coding agenttel, agent
által generált controllerrel és neurális policy-vel egyaránt. A fejlesztés
maga is AI coding agentekkel történik (Codex M01–M06, Claude M06 végétől),
és ez a folyamat a kutatás tárgya is: a teljes napló az
[AI_USAGE.md](AI_USAGE.md).

## Jelenlegi állapot

| | |
|---|---|
| Lezárt mérföldkövek | m01–m12, plusz m10.5 / m10.6 / m10.7 utólagos finomítások |
| M10 | train szcenárión 25/30 (2026-10-08); a holdout-pályán a mérés lefutott, az eredmény 2/30 (v2/kevert kód), így az M10 kapu jelenleg nem teljesült. (`docs/m10-plan.md`) |
| Következő | **m13** — agent-vezérelt rover, a baseline-hoz mérve |
| Tesztek | 46 Python + 21 adapter-teszt + 10 Unity Edit/Play Mode teszt |
| CI | tesztek, szcenárió- és protokoll-sémavalidáció, `black`, `pyflakes`, dokumentáció-ellenőrzés |

### A baseline kontroller mért teljesítménye

> A 2026-10-06 előtti baseline-számok (régi kezdőpóz, a dokumentált paranccsal
> nem reprodukálható mérés) érvénytelenek. Az alábbiak az új, teljesen
> naplózott, előre rögzített feltételű mérések.

**Akadálymentes vonalkövetés (M09), újramérve 2026-10-06-án:** 30/30 sikeres
futás az előre rögzített 27/30-as küszöbbel szemben, teljes naplózással;
a szenzorjavítás után 2026-10-08-án megismételve ugyanígy 30/30
(`docs/m09-plan.md`, „Eredmény").

**Akadályos pálya (M10), mérve 2026-10-08-án:** 30 futás a train
szcenárión, mindkét akadály állandóan látható, 1500 lépés, előre rögzített
16/30-as küszöbbel (`docs/m10-plan.md`, „1. eredmény"; adatok:
`docs/m10-meres.json`, `docs/m10-meres-futasok.jsonl`):

| Metrika | Érték |
|---|---|
| Sikeres futás (kör + 0 ütközés + nincs pályaelhagyás) | **25/30** |
| Teljesített kör (task success) | 26/30 |
| Ütközésmentes futás | 29/30 |

> **Ezen a szcenárión az előre rögzített feltétel teljesült, az M10 kapu ezzel
> még nem igazolt.** A kiírás az akadályszcenáriók többségét kéri, dinamikus és
> eltűnő akadályokkal; ez a mérés egyetlen szcenárión futott, ugyanazon,
> amelyen a kerülést hangoltuk, és a futások seed nélkül, közel
> determinisztikusan ismétlődtek. Következő lépés: előre rögzített holdout-mérés
> több szcenárión, futásonként eltérő seeddel. A 4 pályaelhagyás oka a
> lépésnaplóból azonosítva (a keresés a vonaltól elfelé indult); a javított
> baseline (v2) még nincs mérve.

## Tartalom

| Útvonal | Tartalom |
|---|---|
| `unity/` | Unity szimulációs projekt (pálya, rover, szenzorok, TCP szerver) |
| `gateway/` | Python CLI kliens a rover API-hoz |
| `controllers/` | baseline vonalkövető, kísérletindító, replay-vizualizáció, naplóelemzők |
| `adapter/` | agent-facing réteg: backend-absztrakció, biztonsági őrség, MCP-szerver |
| `common/` | közös lépésenkénti naplóséma |
| `experiments/` | szcenáriók, validátor, commitolt referenciaepizód |
| `scripts/` | `doctor`, referenciaepizód-ellenőrző, dokumentáció-ellenőrző, tool schema export |
| `tests/` | unit, integrációs és regressziós tesztek (`tests/README.md`: lefedettség) |
| `docs/` | protokoll, szenzorok, LiDAR, koordinátarendszer, mérföldkőtervek, mérési adatok |
| `prompts/` | a kutatás szempontjából lényeges, megosztható AI-promptok |
| `paper/` | az angol nyelvű cikk forrása (később) |
| `training/`, `models/` | neurális policy tanítása (később) |

Gyökérszintű dokumentumok: [INSTALL_CHECKLIST.md](INSTALL_CHECKLIST.md) (telepítés
lépésről lépésre), [ENVIRONMENT.md](ENVIRONMENT.md) (fejlesztői környezet),
[REPRODUCIBILITY.md](REPRODUCIBILITY.md) (reprodukálhatóság),
[AI_USAGE.md](AI_USAGE.md) (AI-használati napló).

## Telepítés

```bash
./scripts/doctor
```

Részletesen: [INSTALL_CHECKLIST.md](INSTALL_CHECKLIST.md).

## Használat

**Kézi kipróbálás.** Nyisd meg a `unity/` projektet, töltsd be a
`TrackScene`-t, nyomj Play-t (a szerver a 127.0.0.1:8765 porton indul),
majd terminálban:

```bash
python3 gateway/client.py
# observe | move <táv> <sebesség> | turn <fok> <sebesség> | stop
```

**Méréssorozat** (a Unity Play módban fut, a futások között automatikus
`reset_position`):

```bash
python3 controllers/futtat_kiserletet.py --futasok-szama 30
```

**Reprodukálhatóság Unity nélkül.** A commitolt referenciaepizód friss
klónból is ellenőrizhető, ez fut a CI-ban is:

```bash
python3 scripts/referencia_epizod.py
```

## Licenc és hivatkozás

A projekt [MIT licenc](LICENSE) alatt érhető el.

Minden mérföldkő külön, Zenodón archivált kiadást és saját DOI-t kap. Az összes
verzióra érvényes hivatkozás (mindig a legfrissebbre mutat):

> Sipos-Posta, D. *Simulation-Blind Two-Timescale Rover Control by General-Purpose Coding Agents*. Zenodo. https://doi.org/10.5281/zenodo.22161119

A gépi olvasható hivatkozási adatokat a [CITATION.cff](CITATION.cff) tartalmazza
— a GitHub a repó jobb oldali sávjában *Cite this repository* néven is megjeleníti.

### Mérföldkövenkénti DOI-k

Minden mérföldkő külön, Zenodón archivált kiadást kapott. A disszertációban
és a cikkben ezekre lehet pontosan hivatkozni, nem csak a projekt egészére.

| Tag | DOI |
|---|---|
| `m01` | [10.5281/zenodo.22161307](https://doi.org/10.5281/zenodo.22161307) |
| `m02` | [10.5281/zenodo.22161315](https://doi.org/10.5281/zenodo.22161315) |
| `m03` | [10.5281/zenodo.22161319](https://doi.org/10.5281/zenodo.22161319) |
| `m04` | [10.5281/zenodo.22161328](https://doi.org/10.5281/zenodo.22161328) |
| `m05` | [10.5281/zenodo.22161332](https://doi.org/10.5281/zenodo.22161332) |
| `m06` | [10.5281/zenodo.22161337](https://doi.org/10.5281/zenodo.22161337) |
| `m07` | [10.5281/zenodo.22161342](https://doi.org/10.5281/zenodo.22161342) |
| `m08` | [10.5281/zenodo.22161349](https://doi.org/10.5281/zenodo.22161349) |
| `m09` | [10.5281/zenodo.22161357](https://doi.org/10.5281/zenodo.22161357) |
| `m10` | [10.5281/zenodo.22161120](https://doi.org/10.5281/zenodo.22161120) |
| `m10-5` | [10.5281/zenodo.22164382](https://doi.org/10.5281/zenodo.22164382) |
| `m10-6` | [10.5281/zenodo.23183236](https://doi.org/10.5281/zenodo.23183236) |
| `m10-7` | [10.5281/zenodo.23183248](https://doi.org/10.5281/zenodo.23183248) |
| `m11` | [10.5281/zenodo.23183186](https://doi.org/10.5281/zenodo.23183186) |
| `m11.1` | [10.5281/zenodo.23183214](https://doi.org/10.5281/zenodo.23183214) |
| `m12` | [10.5281/zenodo.23183230](https://doi.org/10.5281/zenodo.23183230) |

## Mérföldkövek

- **m01**: friss klónból megnyitható Unity projekt, futó Python környezet,
  legalább egy ellenőrzött Codex-módosítás(Unity verzió: 6000.3.20f1 szükséges, lásd [INSTALL_CHECKLIST.md](INSTALL_CHECKLIST.md) ).
- **m02**: mozgó gömb Unityben, billentyűzetes vezérléssel, Play Mode
  tesztekkel.
- **m03**: a gömb külső, TCP/JSON alapú vezérlése Python CLI kliensből.
- **m04**: roverszerű, négykerekű kinematikus objektum és prefab,
  determinisztikus mozgással.
- **m05**: formális roverprotokoll (v1), JSON séma, hibakódok, állapotgép,
  biztonsági korlátok (sebesség/távolság/szög/timeout), idempotencia,
  fuzz/property-based tesztek.
- **m06**: zárt, stadion alakú pálya fehér vonallal, paraméterezhető
  geometriával (egyenes hossz, kanyar sugár, vonalszélesség, háttérszín),
  seedelt determinisztikus akadályütemezés, train/dev/test szcenáriók.
- **m07**: vonalérzékelő szenzorok (raycast + zaj + küszöb modell), mérés
  alapján kalibrált küszöb, kapcsolható egy-/háromszenzoros (bal-közép-jobb)
  mód, reprodukálható zaj-seedek.
- **m08**: 2D LiDAR-szimuláció (raycast-alapú, konfigurálható
  látómező/felbontás/hatótáv), szektoros tömörítés, zaj/dropout/
  késleltetés-modellezés, geometriai kalibráció ismert pozíciókban,
  futásidő-profilozás több felbontásnál.
- **m09**: hagyományos (AI nélküli) vonalkövető baseline kontroller
  (állapotgép + P-szabályozó), LiDAR-alapú akadályelkerülés, új
  `reset_position` protokollparancs a reprodukálható mérésekhez, két
  30 futásos mérési sorozat, dokumentált nyitott kérdéssel az akadálykerülés
  kétmodális eloszlásáról (`docs/m09-plan.md`).
- **m10**: ütközésdetektálás (`OnCollisionEnter`, időalapú cooldown a
  többszörös számlálás ellen), lépésenkénti diagnosztikai naplózás,
  irányított vonal-visszakeresés akadálykerülés után (`VISSZATALALAS`
  állapot), explicit zsákutca-észlelés és -eszkalálás, javított
  akadály-időzítés (`reset_position`-höz kötve, nem a Play mód indításához),
  végleges 30 futásos mérés (`docs/m10-plan.md`).
- **m11**: reprodukálható kísérleti platform. Egységes lépésenkénti
  naplóséma (`common/kiserlet_naplo.py`), replay-vizualizáció statikus képpel
  és animált videóval (`controllers/replay_visualizer.py`), egyparancsos
  méréssorozat-indítás automatikus összesítéssel
  (`controllers/futtat_kiserletet.py`), Unity Edit/Play Mode tesztek
  (10, mind zöld) + 29 Python-teszt, CI és Unity nélkül, friss klónból
  reprodukálható referenciaepizód (`scripts/referencia_epizod.py`). Az M11
  tesztjei két örökölt hibát találtak és javítottak: fantom fehér ív a
  pálya-geometriában (M07 óta) és az összesítő futásszám-hibája
  (`docs/m11-plan.md`).
- **m12**: agent-facing MCP-adapter. Az `adapter/` réteg öt MCP-eszközön
  (`observe`, `move`, `turn`, `stop`, `session_status`) keresztül teszi
  vezérelhetővé a rovert AI-agentek számára. Backend-absztrakció (Unity TCP
  vagy mock, az agent számára megkülönböztethetetlenül), biztonsági réteg
  (paraméter-validáció a rover előtt, munkamenet-korlátok, automatikus stop,
  a privilegizált szimulátor-mezők elrejtése), 18 mock teszt (azóta 6 eszköz és 21 teszt, lásd `tests/README.md`), exportált tool
  schema. Egy vak kiértékelésben egy külön Claude Code munkamenet kizárólag
  az eszközleírásokból vezette a rovert 20 lépésen át, egy másik pedig
  biztonsági átvizsgálást végzett — a nyolc találatból öt javítva
  (`docs/m12-plan.md`, `docs/m12-security-review.md`).

### Utólagos, nem hivatalos finomítások

Ezek nem a kiírás mérföldkövei, hanem az M09–M10 nyitva maradt
akadálykerülési problémájára adott, külön mért válaszok:

- **m10.5**: az M09/M10-ben dokumentált oszcillációs jelenség gyökérokának
  feltárása — az AKADALY állapot mostantól ténylegesen halad is előre a
  fordulás közben, és az `AKADALY_KUSZOB_KILEPES_M` finomhangolva (1.1).
  Eredmény: pályaelhagyás 60% → 0%, átlagos ütközésszám 20.9 → 10.2
  (30 futás). Két elvetett javítási kísérlet is dokumentálva
  (`docs/m10-5-plan.md`).
- **m10.6**: az akadálykerülés újramérése a javított pálya-geometriával.
  Kiderült, hogy az M09–M10.5 mérések a fantom fehér ív miatt érvénytelenek
  voltak (a rover a lépések 73%-ában nem a valódi vonalon volt), és hogy a
  teljesített kör 500 lépéses kerettel matematikailag kizárt volt. Négy hiba
  javítva (AKADALY elhaladási fázis, VISSZATALALAS visszatérés az
  elkerülésbe, KERESES körív helyben forgás helyett, ERROR-ból való reset),
  új metrika: task success. Végleges mérés: task success 0/30 → **9/30**, de
  **ütközésmentes futás 0/30** (`docs/m10-6-plan.md`).
- **m10.7**: akadálykontúr-követés (bug-algoritmus) kísérlete — a mérés
  megcáfolta (az elkerülési irányt tartó P-szabályozó miatt a kilépési
  feltétel sosem teljesül, a rover körbekeringi az akadályt), visszavonva.
  Dokumentálva a `docs/m10-6-plan.md` „Elvetett javítás 2." szakaszában.

### Hátralévő mérföldkövek

- **m13–m18**: a hivatalos feladatkiírás szerint. Az **m13** az
  agent-vezérelt rover kísérlete: egy általános célú coding agent irányítja
  a rovert az M12-es MCP-interfészen keresztül, azonos szcenáriókon és azonos
  metrikákkal mérve, mint a fenti baseline.
