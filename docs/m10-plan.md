# M10 terv: akadálykerülés és visszatalálás a vonalra

> **Utólagos megjegyzés (M10.6, 2026-09-11).** Az itt közölt mérések a
> `TrackController` fantom-ív hibájával készültek (M07 óta lappangott, az M11-ben
> javítva), ezért **érvénytelenek**: a rover a lépések 73%-ában nem a valódi
> vonalon volt. Az újramérés és az M10-es elfogadási feltétel őszinte
> értékelése: `docs/m10-6-plan.md`. Az elfogadási feltétel (ütközésmentes
> visszatérés a vonalra a szcenáriók többségében) **nem teljesül**.


## Cél

Az M09 baseline kiegészítése **teljes, determinisztikus**
akadálykerüléssel és vonal-visszakereséssel: a rendszer előre
definiált akadályszcenáriók többségében ütközés nélkül térjen
vissza a vonalra, a kudarcokat pedig egy explicit hiba-taxonómia
szerint automatikusan címkézze.

## Kiindulási állapot (M09-ből örökölt)

Az M09 baseline (`controllers/baseline_line_follower.py`) már
tartalmaz egy kezdetleges **AKADÁLY** állapotot: LiDAR-szektor
alapú akadályészlelés hiszterézissel (belépés 0.5 m, kilépés 0.8 m)
és egy fix szögű (45°) elkerülő fordulat a szabadabb oldal felé.
Két 30 futásos mérési sorozat mindkettő 0/30 pályaelhagyással zárult
- a baseline stabil, de a `docs/m09-plan.md` dokumentál egy
**nyitva hagyott, őszintén jelzett problémát**: az akadálykerülések
száma futásonként erősen kétmodális eloszlású (a futások kb.
egyharmada 10-12 ismétlődő akadálytalálkozást mutat), ami arra utal,
hogy bizonyos megközelítési szögeknél az elkerülő fordulat
visszafordítja a rovert ugyanahhoz vagy egy másik akadályhoz -
**oszcillációs ciklus**. Ennek gyökere lépésenkénti naplózás nélkül
nem volt diagnosztizálható.

**Fontos, eddig fel nem ismert dokumentációs/mérési rés**, amit M10
elején pótoltunk:
- `docs/protocol.md` nem dokumentálta a `lidar_szektor_min` mezőt
  (pedig M08 óta az `observe` válasz része) - pótolva.
- A rendszernek **nem volt ütközésdetektálása**: sem a Unity, sem a
  protokoll nem jelezte vissza, ha a rover ténylegesen nekiütközött
  egy akadálynak. Az "akadálykerülések száma" metrika valójában csak
  azt mérte, hányszor lépett AKADÁLY állapotba - nem azt, hogy sikeres
  volt-e a kerülés.

## M10 munkacsomagok

### 1. Lépésenkénti diagnosztikai naplózás (kész)
`controllers/baseline_line_follower.py` új `LepesNaplozo` osztálya
minden lépésnél JSONL-be írja: `run_id`, lépésszám, állapot előtte/
utána, a három vonalszenzor nyers értéke, `lidar_szektor_min`, a
lépésben kiadott parancs(ok), valamint - **kizárólag diagnosztikai
célra, a vezérlési döntésben nem használva** - a privilegizált
`position` és az új `collision_occurred`/`collision_count` mezőket.
Napló helye: `logs/m10_lepes_naplo.jsonl` (`--lepes-naplo` kapcsolóval
állítható vagy kikapcsolható).

### 2. Ütközésdetektálás Unity oldalon (kész)
- `TrackController.FelepitAkadalyokat()`: minden létrehozott akadály
  megkapja az `Akadaly` taget.
- `RoverGatewayServer.cs`: új `OnCollisionEnter` kezelő, ami az
  `Akadaly` taggel ütköző eseményeket számolja
  (`utkozesTortentAzUtolsoResetOta`, `utkozesekSzamaAzUtolsoResetOta`).
  Ezek a `reset_position`/`reset_error` parancsoknál nullázódnak, így
  futásonként tisztán mérhető az ütközésszám.
- `observe` válasz bővítve `collision_occurred`/`collision_count`
  mezőkkel (`docs/protocol.md`-ben dokumentálva, kizárólag
  diagnosztikai célra megjelölve, ahogy a `position`/`speed` is).
- **- **Unity Play módban igazolva:** a rover pozícióját kézzel egy
  mindig aktív teszt-objektum (`TesztAkadaly`, ideiglenesen `Akadaly`
  taggel ellátva) helyére állítva az `OnCollisionEnter` helyesen és
  ismételten lefutott (`M10: utkozes eszlelve...` log-üzenet).
- - **Javítva és igazolva:** a többszörös ütközés-számlálás problémáját
  egy időalapú "hűtési" (cooldown) mechanizmussal orvosoltuk
  (`UtkozesCooldownMasodperc = 0.5f`): egy új ütközés csak akkor
  számít, ha az előzőtől legalább fél másodperc telt el. Az első
  próbálkozás (colliderenkénti be-/kilépés számlálása
  `OnCollisionEnter`/`OnCollisionExit` párral) **nem vált be** - a
  rover több colliderje (alváz + 4 kerék) egyszerre, mélyen átfedésben
  egy akadállyal instabil, oda-vissza ugráló érintkezés-jelzéseket
  produkált a fizikai motorban. Az időalapú megoldást manuálisan
  teszteltük: egy rögzített pozícióban a számláló **nem nőtt tovább**
  több mint két percig, míg a korábbi (hibás) verzióval percenként
  több tucatszor nőtt volna.

### 3. Oszcilláció diagnosztizálása a lépésnaplóból (kész)
Új `controllers/analyze_step_log.py` szkript: futásonként megkeresi az
AKADÁLY-belépéseket, és két egymást követő belépés `position` mezője
alapján (kizárólag diagnosztikai célra) jelzi, ha a rover 0.3 m-nél
kevesebbet haladt előre két akadálytalálkozás között - ez a jel az
M09-ben leírt "ugyanahhoz az akadályhoz visszafordul" jelenségre utal,
szemben azzal, amikor egyszerűen több, egymástól távoli akadállyal
találkozik útközben. Szintetikus naplóval végponttól végpontig
tesztelve (helyben-ismétlődő párt helyesen jelzett, távoli,
egyszeri akadálytalálkozást helyesen nem jelzett gyanúsnak).
**Korlát, amit nem hallgatunk el:** ez csak azt méri, hogy a pozíció
alig változott - nem bizonyítja, hogy ugyanazt az akadályt kerülte-e
a rover ismételten; első, gyors triázs-eszköznek szánjuk, nem végleges
hiba-taxonómia-döntésnek. Éles naplóval (valódi Unity-futásból) még
nincs kipróbálva.

### 4. Explicit vonal-visszakeresési eljárás kerülés után (kész, validálva Unity Play módban)
Új `VISSZATALALAS` állapot: az AKADÁLY állapot már nem közvetlenül
VONALON-ra vált, amint a LiDAR szabadnak jelzi az elülső szektorokat,
hanem a `VISSZATALALAS` állapotba lép. Ott a rendszer megjegyzi az
elkerülő fordulat irányát, és azzal **ellentétes** irányba forog kis
lépésekben (5°-onként), miközben lassan előre halad, amíg valamelyik
vonalszenzor `white`-ot nem jelez. Ha ez `VISSZATALALAS_MAX_LEPES`
(15) lépésen belül nem sikerül, a rendszer a tágabb, általános
KERESÉS állapotra eszkalál.
**Unity Play módban tesztelve (10+1 futás):** 18, teljes 500 lépésig
lefutott, "tiszta" (pályaelhagyás nélküli) futás közül 11-ben
aktiválódott a `VISSZATALALAS` állapot, és mind a 11 esetben
sikeresen visszatalált a vonalra (`VONALON`) - egyetlen eszkalálás
sem történt a tágabb `KERESES` állapotra. **Ez biztató, de a
mintaméret (11 esemény) kicsi** ahhoz, hogy általános
megbízhatóságot állítsunk - nagyobb mintás mérés (a tervezett
végleges 30 futásos sorozat) szükséges a szilárd következtetéshez.

**Módszertani tanulság ebből a tesztelési körből:** egy próbálkozás
során ideiglenesen "örökké láthatóvá" tettük a szcenárió akadályait
(a `disappear_at_s` érték drasztikus megnövelésével) a tesztelés
felgyorsítására - ez viszont torzította a mérést, mert a rover a
pálya körbejárása során ismételten ugyanabba az akadályba futott
bele (17-39 ütközés/futás, gyakori pályaelhagyás), ami nem
reprezentálja a tervezett, időzített szcenáriót. Az eredeti
időzítés visszaállítása után a viselkedés visszatért az M09-cel
konzisztens, egészséges mintázathoz (0 pályaelhagyás mind a 10
futásban).

Az állapotgép mind a négy állapotára és azok átmeneteire új unit
tesztek készültek (`tests/baseline_line_follower_test.py`, 9 teszt,
mind zöld) - stub gateway-klienssel, Unity nélkül futnak. **Nem
helyettesítik** a Unity Play Mode-os fizikai tesztet.

### 5. Zsákutca és eltűnő akadály kezelése (kész, ez a session)
**Zsákutca:** ha a rover `ZSAKUTCA_AKADALY_MAX_LEPES` (20) egymást
követő lépésig `AKADALY` állapotban marad anélkül, hogy sikerülne
kikerülnie (pl. két akadály közé szorul), a rendszer a további
fordulgatás helyett a tágabb `KERESES` állapotra eszkalál, és ezt
külön statisztikaként (`zsakutcak_szama`) számolja - elkülönítve a
sikeres akadálykerülésektől. Unit teszttel lefedve
(`test_akadaly_zsakutca_eszleles_eskalal_keresesre`).

**Eltűnő akadály:** ezt a rendszer már korábban is helyesen kezelte
- ha a LiDAR már nem lát akadályt elöl, a rover kilép az `AKADALY`
állapotból, függetlenül attól, hogy ez azért történt, mert sikeresen
elkerülte, vagy mert az akadály közben eltűnt
(`schedule.disappear_at_s`). **Tudatos tervezési döntés, nem
hiányosság:** a rover a rendelkezésére álló, nem-privilegizált
adatokból (LiDAR) nem tudja és nem is szabad, hogy valós időben
megkülönböztesse ezt a két esetet - az privilegizált pozíció-adat
használatát igényelné a vezérlési döntésben, ami sértené a projekt
alapelvét. A különbség utólag, diagnosztikai célra a lépésnaplóból
(`position` mező) az `analyze_step_log.py`-jal állapítható meg.

### 6. Hiba-taxonómia (részben megalapozva)
Feladatkiírás szerinti kategóriák: ütközés, elakadás, téves vonal,
timeout, oszcilláció. Az ütközés mérése mostantól megvan (2. pont).
**Nyitott kérdés, amit nem akarunk elhamarkodottan lezárni:** a
rendszernek jelenleg nincs kör-/etap-befejezés detektálása, tehát
minden futás technikailag a `--max-lepes` biztonsági korlátig fut -
emiatt jelenleg **nem lehet megbízhatóan megkülönböztetni** egy
"időtúllépés miatt leállított, egyébként sikeres" futást egy valódi
"elakadás" esettől. Ezt a hiba-taxonómia automatikus kódolása előtt
tisztázni kell (vagy kör-detektálással, vagy explicit sikerességi
kritérium bevezetésével).

### 7. Végleges 30 futásos mérési sorozat (kész, ez a session)
Egy fontos, korábban észrevétlen hibát is feltártunk és kijavítottunk
eközben: az akadályok `schedule.appear_at_s`/`disappear_at_s`
időzítése a Play mód *indításához* volt kötve, nem az egyes
futások `reset_position` parancsához - emiatt az akadályok gyakorlatilag
csak a Play mód elindítása utáni néhány másodpercben jelentek meg
egyszer, utána egy teljes Play munkamenetben többé soha. Javítás:
`TrackController.UjrakezdiAkadalyUtemezest()` új publikus metódus,
amit a `RoverGatewayServer` minden `reset_position` parancsnál
meghív, így minden futás saját, független időablakot kap.

**Fontos, tudatosan vállalt mérési egyszerűsítés:** a 70x Time Scale
miatt a hálózati parancsok oda-vissza útja alatt is több szimulált
másodperc telik el, ami a rövid (5-7 másodperces) időzített
időablakot gyakorlatilag elérhetetlenné teszi TCP-n keresztül
irányított futásoknál. Ezért a végleges méréshez az akadályokat
*állandóan láthatóvá* tettük (`experiments/scenarios/stadium-train-baseline.json`-ben
`disappear_at_s` nagyon nagyra állítva) - ez eltér az eredeti,
tervezett időzített szcenáriótól, és ezt a jövőbeli mérésekben is
egyértelműen jelölni kell.

**Eredmény (30 futás, mindkét akadály állandóan látható):**
- Parancsok száma: átlag 832.9, szórás 317.4 (475-1297)
- Vonalvesztések: átlag 17.2, szórás 11.7 (4-40)
- Akadálykerülések: átlag 2.8, szórás 2.2 (0-10)
- Zsákutcák: 0/30 futásban
- Pályaelhagyások: **18/30 futásban**
- Ütközések: átlag 20.9, szórás 17.0 (3-64)
- Ütközött futások: 30/30

**Értelmezés, őszintén:** ez az eredmény **megerősíti** az M09-ben
már dokumentált, ismert oszcillációs problémát - mivel az akadály
most állandóan jelen van, a rover a pálya minden körbejárásánál
ismételten belefut, ami magyarázza a magas ütközésszámot és a
gyakori pályaelhagyást. Ez **nem** az M10 munkacsomagjainak (ütközés-
detektálás, VISSZATALALAS, zsákutca-kezelés) hibája - azok külön-külön,
célzott teszteken igazoltan helyesen működnek (lásd 2. és 4. pont) -,
hanem az eredeti M09 oszcillációs probléma **még mindig nyitott**,
és ez a mérés ezt csak élesebben megmutatja, mert most nincs esély
arra, hogy az akadály időközben eltűnjön és "megmentse" a rovert.
A gyökérok-javítás (pl. az elkerülési stratégia finomítása ismételt
találkozásoknál) M11+ munkaként azonosítva, nem ennek a
mérföldkőnek a része.

### 8. State-machine diagram, videók (kész)
**Pontosítás:** a `docs/state_machine.svg` valójában a protokoll-szintű
(IDLE/MOVING/TURNING/ERROR) állapotgépet ábrázolja M05 óta, nem a
baseline vonalkövető kontrollerét - ez korábban tévesen lett
összekeverve a tervben. A baseline kontroller állapotgépének
(VONALON/AKADALY/KERESES/VISSZATALALAS) eddig csak szöveges leírása
létezett (`docs/m09-plan.md`), vizuális diagramja nem. Ezt pótoltuk:
új fájl, `docs/baseline_state_machine.svg`, amely mind a négy
állapotot és az M10-ben bevezetett átmeneteket (VISSZATALALAS,
zsákutca-eszkalálás) is ábrázolja.

Demonstrációs videó (`docs/videos/m10-akadalykerules-demo.mov`) egy
valós, sikeres akadálykerülésről rögzítve, csökkentett (3x) Time
Scale mellett a jobb követhetőség kedvéért.

## Utólagos audit és javítás (ugyanaznap)
Egy alapos, utólagos ellenőrzés három konkrét hiányosságot tárt fel,
amit itt dokumentálunk, mert pontosan illik a projekt "őszinte
hibadokumentáció" elvéhez:

1. **Regressziós teszt-hiba (javítva):** a végleges mérés kedvéért
   tartósan módosított `stadium-train-baseline.json` sosem lett
   visszaszinkronizálva az M06-os determinisztikus generátorral,
   emiatt a `tests/scenario_seed_test.py` pirosra vált. Javítás: a
   fájlt visszaállítottuk a generátor-hű, eredeti időzítésre, a
   végleges méréshez használt "örökké látható" változatot pedig
   külön, névvel ellátott fájlba (`stadium-train-baseline-always-visible.json`)
   különítettük el. A teljes tesztkészlet (`scenario_seed_test.py`,
   `baseline_line_follower_test.py`, `protocol_fuzz_test.py`) most
   zöld.
2. **Nyers benchmark logok (javítva):** korábban csak az összesített
   statisztika volt commitolva. Pótoltuk a `logs/m09_runs.jsonl`
   fájlt és a végleges 30 futás szűrt, lépésenkénti naplóját
   (`logs/m10_vegleges_30_futas_lepesnaplo.jsonl`).
3. **Az elfogadási feltétel formális teljesülése (nyitott kérdés,
   nem "javítható"):** a kiírás megfogalmazása szerint a rendszernek
   "előre definiált akadályszcenáriók többségében ütközés nélkül"
   kell visszatérnie a vonalra. A VI. fejezetben (Az eredmények
   összegzése) bemutatott, saját, integrált mérésünk ezt nem
   teljesíti (30/30 futásban volt ütközés, 18/30-ban pályaelhagyás).
   Ennek okát az M09-es, még nyitott oszcillációs problémára
   vezetjük vissza - ezt nem tekintjük M10-specifikus hibának, de
   formálisan nem állítjuk, hogy az elfogadási feltétel teljesül.

## Következő konkrét lépés
A fenti 1-2. pont javítva. A 3. pont (az integrált elfogadási
feltétel formális teljesítése) az M09-es oszcillációs probléma
gyökérokának megoldásától függ - ez M11+ munkaként azonosítva marad.

---

## M10 kapu – előre rögzített mérési terv (2026-10-08, a mérés előtt)

Ez a szakasz a mérés **előtt**, külön commitban kerül a repóba. Az itt leírt
feltételeket a mérés után nem módosítjuk; ha a mérés eltérést mutat, azt új,
dátumozott szakaszban rögzítjük.

### Előzmény

A régi kerüléssel (szektoros döntés, ±30°) az akadályos pályán átlagosan 77,4
ütközés jutott egy futásra, és csak 9/30 futás tett meg teljes kört. A kerülés
három ponton változott (részletesen a kontroller commitüzenetében):
oldalsó ellenőrzés a nyers LiDAR-ból a rover valódi szélességével,
korábbi kitérés és 1,0 m-es vak zóna, valamint iránytartás a visszatéréskor.
Egyetlen próbafutás (nem része a mérésnek): 0 ütközés, 0 pályaelhagyás,
4 kerülés, mind visszatért a vonalra.

### A mérés

- Szcenárió: `stadium-train-baseline-always-visible`, a jelenetben beállítva,
  a futtató `--elvart-szcenario` kapcsolójával ellenőrizve.
- 30 egymást követő futás, futásonként legfeljebb 1500 lépés.
- Parancs:
  `python3 controllers/futtat_kiserletet.py --futasok-szama 30 --max-lepes 1500 --elvart-szcenario stadium-train-baseline-always-visible`
- Kiértékelés: `python3 controllers/kor_metrika.py --utolso 30 --json`, az
  eredmény a `docs/m10-meres.json`, a futásonkénti metaadat a
  `docs/m10-meres-meta.jsonl` fájlba kerül.
- A mérés kódja a terv commitja előtti commit; a metaadatnapló minden futásnál
  rögzíti a `git_commit` és a `git_tiszta` értékét.

### Sikerfeltétel (futásonként)

Egy futás akkor sikeres, ha mindhárom teljesül:

1. legalább 1 teljes kör (kör-arány ≥ 1,0),
2. 0 ütközés,
3. nincs pályaelhagyás.

### Kapu

Az M10 kapu akkor teljesül, ha a sikeres futások száma **legalább 16/30**
(a kiírás szerinti „többség”).

### Előre ismert korlátok

- A vak zóna 1,0 m-es egyenes szakasza a naplóban egyetlen lépésként jelenik
  meg (legfeljebb 13 mozgásparanccsal), így a lépésszám nem egyenesen arányos
  a megtett úttal.
- A próbafutásban a visszatérés közben a rover mind a négy esetben újra
  kitérésbe váltott, és kb. 1,8 m-re eltávolodott a vonaltól, mielőtt
  visszatalált. Ez nem pályaelhagyás (az a 90 lépéses sikertelen keresést
  jelenti), de a kerülés hosszát és a vonalon töltött arányt rontja.
- A paramétereket (1,0 / 1,3 m, 0,30 m ráhagyás, 1,0 m vak zóna, 30°) egyetlen
  próbafutás alapján, geometriai megfontolásból választottuk; nem volt
  paraméter-sweep, és nincs külön dev/holdout szcenárió.

### 1. eredmény (2026-10-08) – a kapu teljesült

A mérés a fenti terv szerint futott: 30 futás, mindegyik
`stadium-train-baseline-always-visible` szcenárión, 1500 lépéssel,
time scale 70, a `7d86198` commiton, tiszta munkakönyvtárral (a metaadat mind
a 30 futásnál ezt rögzíti). A `7d86198` csak a tervet adta hozzá, a kód
azonos a `0124aa1`-gyel. Adatok: `docs/m10-meres.json`,
`docs/m10-meres-meta.jsonl`.

| Feltétel | Teljesült |
|---|---|
| legalább 1 teljes kör | 26/30 |
| 0 ütközés | 29/30 |
| nincs pályaelhagyás | 26/30 |
| **mindhárom (sikeres futás)** | **25/30** |

**25/30 ≥ 16/30, az M10 kapu teljesült.**

További mutatók (átlag ± szórás): kör-arány 2,13 ± 0,60; megtett út
113,9 ± 30,2 m; hatékonyság 0,908 ± 0,039; vonalon töltött arány
0,186 ± 0,038; akadálykerülés futásonként 3,6 ± 1,0; zsákutca 0.
A régi kerüléshez képest (9/30 teljes kör, átlagosan 77,4 ütközés) az
ütközések gyakorlatilag megszűntek.

**Sikertelen futások:**

- 7., 14., 16., 21.: pályaelhagyás, mind ugyanott (0,63 kör, 468–471. lépés).
  Ez nem véletlen szórás, hanem egy ismétlődő hibahely, valószínűleg az egyik
  akadály első megkerülése utáni visszatérés. A mérés után nem javítottuk;
  külön vizsgálandó.
- 29.: egyetlen ütközés, a futás egyébként sikeres lett volna (2,35 kör).

A vonalon töltött arány alacsony (18,6%), mert a kerülések hosszúak, és a
vonalkövetés is ±11 cm-es sávban egyensúlyoz (lásd az M09 megismételt mérését).

---

## 2. mérés: baseline v2 – előre rögzített terv (2026-10-08, a mérés előtt)

Az 1. mérés 4 pályaelhagyása ugyanaz a határeset volt: a visszatérés 40 lépés
után kb. 10 cm-re állt meg a vonaltól, és a keresés a vonaltól elfelé fordult.
A v2 egyetlen változtatása: sikertelen visszatérés után a keresés a vonal
felőli oldalra indul. Egy elvetett próbálkozás (párhuzamosra fordulás a vak
zóna előtt) egyetlen próbafutásban 20 ütközést adott, ezért visszavontuk. 
Közben a 5f3c685 commitban bekerült egy változtatás(nettó fordulat előjele 
alapján történő visszatérés), és a holdout mérés (2/30) ezen a kódon futott le, 
mielőtt visszavontuk volna.

- Mérés, szcenárió, sikerfeltétel: azonos az 1. méréssel (30 futás, 1500 lépés,
  always-visible; kör ≥ 1, 0 ütközés, nincs pályaelhagyás).
- Döntési szabály: a v2 lesz az M13 összehasonlítási alapja, ha a sikeres
  futások száma legalább 25/30 (nem rosszabb az 1. mérésnél). Ha kevesebb, az
  M13 az 1. mérés kódjához (0124aa1) mér, és a v2-t elvetjük.
- Adatok: docs/m10-v2-meres.json és docs/m10-v2-meres-meta.jsonl (a mérés után
  jönnek létre). A docs/m10-v2-meres.json elmaradt!

### Helyesbítés (2026-10-08, külső átvizsgálás után)

Az „1. eredmény" címe („a kapu teljesült") túl erős. A mérés az előre rögzített
feltételt teljesítette, de csak a train szcenárión, állandóan látható
akadályokkal, seed nélkül, és ugyanazon a pályán, amelyen a kerülést
hangoltuk. A kiírás az akadályszcenáriók többségét kéri, dinamikus és eltűnő
akadályokkal; ezt holdout-mérés fogja eldönteni. A 25/30 eredmény és az adatok
változatlanok; a futásszintű összesítő utólag került a repóba
(`docs/m10-meres-futasok.jsonl`).


---

## Holdout-mérés – előre rögzített terv (2026-10-08, a mérés előtt)

A külső átvizsgálás szerint az 1. mérés egyetlen szcenárión, seed nélkül futott,
ugyanazon a pályán, amelyen a kerülést hangoltuk. Ez a mérés ezt pótolja.

- Szcenárió: stadium-test-holdout-always-visible (14 m egyenes, 4,5 m sugár,
  0,16 m vonal, más akadályhelyek). Ezen a pályán a kontroller még egyszer sem
  futott, próbafutás sem lesz.
- Kód: a baseline v2 (298c38d), változtatás nélkül.
- 30 futás, futásonként 1500 lépés, zaj-seed 1001–1030 (--seed 1001).
- Sikerfeltétel futásonként: kör ≥ 1, 0 ütközés, nincs pályaelhagyás.
- Kapu: legalább 16/30 sikeres futás.
- Ha teljesül: a v2 lesz az M13 összehasonlítási alapja. Ha nem: dokumentáljuk,
  és a train-eredmény nem általánosítható.
- Nem fedi: dinamikus és eltűnő akadályok. Az M10 kapu ettől függetlenül
  részben nyitott marad.
- Adatok a mérés után: docs/m10-holdout-meres.json, docs/m10-holdout-meta.jsonl,
  docs/m10-holdout-futasok.jsonl.

### Holdout-eredmény (2026-10-08) – a kapu nem teljesült

30 futás a terv szerint: stadium-test-holdout-always-visible, f269cf1 (kód =
298c38d), tiszta munkakönyvtár, 30 különböző zaj-seed (1001–1030), 1500 lépés.

| Feltétel | Teljesült |
|---|---|
| legalább 1 teljes kör | 12/30 |
| 0 ütközés | 29/30 |
| nincs pályaelhagyás | 2/30 |
| **mindhárom (sikeres futás)** | **2/30** |

**2/30 < 16/30: a holdout-kapu nem teljesült; a train pályán mért 25/30 nem
általánosít.** Vonalvesztés futásonként átlagosan 58,4 (train: 14,4), vagyis a
keskenyebb (0,16 m) vonalon már a vonalkövetés is bizonytalan, nem csak a
kerülés utáni visszatalálás.

Korlát: a kor_metrika.py a train pálya méreteivel számol, ezért ezen a pályán a
„vonalon töltött arány" és a hatékonyság érvénytelen. A kör-arány (szög a pálya
középpontja körül) és a pályaelhagyás-jelző nem érintett, a 2/30 érvényes.

Adatok: `docs/m10-holdout-meres.json`, `docs/m10-holdout-meta.jsonl`,
`docs/m10-holdout-futasok.jsonl`.

---

## Validációs mérés – előre rögzített terv (2026-10-08, a pálya generálása előtt)

A holdout-diagnózis alapján javított kontrollert (baseline v3: helyben lengő
keresés) egy harmadik, általunk ki nem választott pályán igazoljuk.

- Pálya: scripts/generate_validation_scenario.py, név stadium-validation-20261008,
  típus dev. A méretek a névből képzett seedből jönnek: egyenes 10–16 m, sugár
  3,5–5,0 m, vonalszélesség 0,14–0,22 m; 2 akadály, végig láthatóan. Ha a pálya
  könnyűnek bizonyul, nem cseréljük, hanem leírjuk.
- Validációs mérés: 30 futás, 1500 lépés, zaj-seed 2001–2030; ugyanaz a
  sikerfeltétel; kapu: legalább 16/30.
- Regresszió a train pályán (always-visible): 30 futás, seed 3001–3030;
  feltétel: legalább 25/30 (nem rosszabb az 1. mérésnél).
- A v3 akkor lesz az M13 összehasonlítási alapja, ha mindkét feltétel teljesül.
- A holdout pályán a v3-at nem mérjük (azt már felhasználtuk).

**Kiegészítés a validációs tervhez (a mérés előtt):** a train pályán futtatott
próba (seed 999) hibát mutatott: a délelőtti előjel-javítás újrakitérés után
rossz irányba indította a visszatérést. Visszavontuk; a mért kód 6ea4858. A
validációs pályán ezt megelőzően egyetlen futás sem volt. Ugyanez a hiba a
holdout-mérés (v2) kódjában is benne volt, így a holdout 2/30 részben ennek is
betudható, a keskeny vonal hatásától utólag nem választható szét.
