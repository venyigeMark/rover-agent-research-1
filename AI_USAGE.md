# AI-használati napló

Ez a dokumentum a kutatás során használt AI coding agentek munkáját naplózza.
A kutatás tárgya részben maga ez a folyamat, ezért a napló a sikertelen és
visszavont kísérleteket is tartalmazza, nem csak a beváltakat.

## Eszközök és időszakok

| Időszak | Eszköz | Szerep |
|---|---|---|
| M01–M06 | Codex (JetBrains AI, PyCharm IDE-integráció) | kódgenerálás, protokoll- és sématervezés |
| M06 vége – M12 | Claude (Claude Code) | tervezés, kódjavaslat, napló-diagnózis, review |

A váltás oka nem preferencia volt: az M06 közben elfogyott a havi Codex-kvóta
(lásd a 13. szakaszt), és a megkezdett munkát ezért fejeztük be Claude-dal.

## Munkamegosztás

Minden szakaszban azonos a felosztás, és ezt szándékosan nem mossuk össze:

- **Az AI adta**: a tervet, a kódjavaslatot, a diagnózist a mérési adatokból,
  a tesztek vázát, a review-kat.
- **Én végeztem**: a bevezetést a saját projektbe (Rider/terminál), a Unity
  Play módos futtatást, a méréseket, és minden tartalmi döntést — beleértve
  azt is, hogy egy AI-javaslatot a mérés alapján elvetünk.
- **A mérés döntött**, nem az érvelés: négy javítási kísérletet mért adat
  cáfolt meg és vontunk vissza (M10.5 ×2, M10.6 ×1, M10.7 ×1).

Ahol ettől eltértünk, az külön jelölve van (pl. a 13. szakaszban az M06
kötelező AI-eleme végül nem AI-val készült).

## Mérföldkő-index

| Mérföldkő | Szakasz | Elsődleges AI | Mit adott az AI | Hogyan ellenőriztem |
|---|---|---|---|---|
| M01 | 1–5 | Codex | próbafüggvények, INSTALL_CHECKLIST, `scripts/doctor` | kézi futtatás, friss klónból végigtesztelve |
| M02 | 6–7 | Codex | `MovementController.cs`, Play Mode tesztek | Unity Test Runner |
| M03 | 8–9, „Hibakeresés" | Codex | TCP/JSON szerver, Python CLI kliens | kézi parancsok; két hibát én találtam meg |
| M04 | 10 | Codex | mozgásmodell-összehasonlítás (döntési input) | a döntés az enyém, `docs/coordinate-system.md` |
| M05 | fuzz-szakasz, 11–12 | Codex | protokoll-review, v1 protokoll implementáció | fuzz teszt + kézi esetek; a security-csomag szűkítése saját döntés |
| M06 | 13 | Codex, majd Claude | JSON séma, szcenárió-generátor | validátor + reprodukálhatósági teszt; **a validátort a kvóta elfogyása miatt nem AI írta** |
| M07 | 14 | Claude | ColorSensor-kalibráció elemzése, `SensorArray.cs` | 5 pontos kézi mérés, kanyarpróba (`docs/sensors.md`) |
| M08 | 15 | Claude | `LidarSensor.cs`, kalibrációs és profilozási terv | 5 pontos geometriai kalibráció, futásidő-profilozás (`docs/lidar.md`) |
| M09 | 16–17 | Claude | `observe`-bővítés, baseline kontroller, `reset_position` | 2 × 30 futásos mérés; a negatív eredmény dokumentálva |
| M10 | 18 | Claude | ütközésdetektálás, lépésnapló, `VISSZATALALAS`, zsákutca-kezelés | Unity Play mód, 30 futásos mérés; két saját mérési hibámat is rögzítettem |
| M10.5 | 18 (alszakasz) | Claude | oszcilláció gyökérok-diagnózisa | 30 futásos mérések; **két javaslat mérés alapján elvetve** |
| M11 | 19 | Claude | naplóséma, replay, CI, Unity tesztek | Test Runner, CI, referenciaepizód |
| M12 | 20–21 | Claude | adapter, MCP-szerver; külön munkamenet vak kiértékelésre és biztonsági review-ra | 18 mock teszt; 8 találatból 5 javítva |
| M10.6 | 22 | Claude | geometria-javítás utáni újramérés, 4 hibajavítás, task success metrika | 30 futásos mérés; **a kapu nyitva maradt** |
| M10.7 | 23 | Claude | akadálykontúr-követés kísérlete | 5 futásos mérés **megcáfolta** → visszavonva |

---

### 1. Prímszám-ellenőrzés
A Codex-szel generáltattam egy `prim_e()` függvényt, ami eldönti egy számról,
hogy prímszám-e. A kódot néhány teszt-számmal (1, 2, 7, 17, 20, 25) ki is
próbáltam.

### 2. Mérési adatok kiértékelése
A Codex-szel generáltattam egy `meresek_kiertékelese()` függvényt, ami egy
számlistából (pl. testhőmérséklet-adatok) kiszámolja az átlagot, a minimumot
és a maximumot, majd szépen kiírja az eredményt.

### 3. CSV-fájl beolvasása
A Codex-szel generáltattam egy `csv_elso_sorai()` függvényt, ami beolvas egy
CSV-fájlt, kiírja az oszlopneveket, majd megjeleníti az első 5 adatsort.
Hibakezelést is tartalmaz (pl. ha a fájl nem található).

### 4. Telepítési ellenőrzőlista (INSTALL_CHECKLIST.md)
A Codex-szel generáltattam egy lépésről lépésre követhető, kipipálható telepítési
ellenőrzőlistát, ami leírja a Git, Unity 6000.3.20f1 LTS és Python 3.9 telepítését,
a virtuális környezet létrehozását, valamint a `scripts/doctor` futtatását
ellenőrzésképp. A listát friss klónból végig is teszteltem.

### 5. scripts/doctor bővítése
A Codex-szel generáltattam egy `scripts/doctor` nevű ellenőrző szkriptet, ami
kiírja a Python, Git és Pip verzióját, ellenőrzi a szükséges Python modulokat
(argparse, csv), és megnézi, hogy a projekt alapfájljai (src/main.py, README.md,
AI_USAGE.md) megvannak-e.

> **Utólagos megjegyzés (M12 után).** Ez a leírás a szkript *eredeti*, M01-es
> állapotát rögzíti. A szkriptet később újraírtuk, mert három ponton félrevezetővé
> vált: (1) azt állította, a projekt csak beépített modulokat használ, holott
> szükség van a `jsonschema` és `matplotlib` csomagokra; (2) a kilépési kódja
> mindig 0 volt, így ellenőrzésre valójában alkalmatlan volt; (3) a `src/main.py`-t
> nézte, a projekt érdemi részét adó `controllers/`, `adapter/`, `common/`
> mappákat viszont nem. Az új verzió ellenőrzi a Python-verziót, az Unity projekt
> verzióját, a tényleges függőségeket, a CI által használt eszközök pontos
> verzióit, a projektszerkezetet, és lefuttatja a referenciaepizód-ellenőrzést is
> — hiba esetén pedig 1-es kilépési kóddal áll le.

### 6. Unity mozgó gömb komponens (MovementController.cs)
A Codex-szel megíratattam a MovementController.cs C# komponenst, ami a
WASD/nyílbillentyűkkel mozgatja a gömböt egy Rigidbody segítségével.
A komponens tartalmaz egy Inspectorból állítható sebességparamétert,
egy R billentyűre aktiválódó reset funkciót, és egyszerű ütközésjelzést.
A Codex részletesen elmagyarázta a MonoBehaviour, Update és FixedUpdate
szerepét: a bemenet olvasása az Update-ben történik (képkockánként fut),
míg a fizikai mozgatás a FixedUpdate-ben (rögzített időközönként, a
Unity fizikai motorjához igazodva).

### 7. Play Mode tesztek
A Codex 3 lehetséges tesztelési megközelítést javasolt a mozgás és a
reset ellenőrzésére: (1) publikus metódus közvetlen tesztelése,
(2) bemeneti rendszer szimulálása, (3) Rigidbody közvetlen tesztelése.
A publikus metódus (Move()) közvetlen tesztelése mellett döntöttem,
mert stabil, gyors és nem függ az Input System konfigurációjától.
A Codex ez alapján megírta a MovementControllerPlayModeTests.cs
fájlt, ami két tesztet tartalmaz: a mozgás- és a reset-funkció
ellenőrzését. Mindkét teszt sikeresen lefutott.

### 8. TCP/JSON rover gateway szerver (RoverGatewayServer.cs)
A Codex-szel megíratattam egy Unity C# TCP szervert, ami külön háttérszálon
figyel egy portot (127.0.0.1:8765), és newline-delimited JSON üzeneteket
fogad (observe, move, stop parancsok, request_id azonosítóval). A hálózati
szál és a Unity fő szála közötti biztonságos kommunikációt egy
ConcurrentQueue és ManualResetEventSlim párossal oldotta meg — a tényleges
Rigidbody-műveletek mindig a FixedUpdate-ben, a fő szálon futnak.

### 9. Python CLI kliens (gateway/client.py)
A Codex-szel megíratattam egy interaktív Python parancssori klienst, ami
csatlakozik a Unity szerverhez, UUID-alapú request_id-kat generál, és
JSONL fájlba naplózza a kérés-válasz párokat.

### Hibakeresés
A tesztelés során két hibát találtam és javítottam:
1. A gömb nem mozgott annak ellenére, hogy a szerver "elfogadta" a
   parancsot — kiderült, hogy a korábbi MovementController script még
   engedélyezve volt ugyanazon a GameObjecten, és minden FixedUpdate-ben
   nulla elmozdulással felülírta a RoverGatewayServer mozgatását.
   Megoldás: a MovementController letiltása ebben a jelenetben.
2. A "stop" parancs figyelmeztetést dobott ("Setting linear velocity of
   a kinematic body is not supported"), mert a Rigidbody kinematikus
   (MovePosition-t használ), így nem lehet rajta közvetlenül sebességet
   beállítani. Megoldás: a felesleges linearVelocity/angularVelocity
   beállítások eltávolítása a stop ágból — a mozgás leállításához elég
   a hátralévő távolság és sebesség nullázása.

### 10. Rovermozgás-modell összehasonlítás
A Codex-től kértem egy összehasonlítást a kinematikus és a WheelCollider-
alapú mozgásmodell között (m04 kötelező AI-használat). A kinematikus
modellt választottam, mert gyors, determinisztikus, könnyen
hibakereshető, és a fejlesztés jelenlegi fázisában (AI-vezérlés és
interfészek kialakítása) ez a fontosabb szempont, nem a fizikai
realizmus. A Codex azt is javasolta, hogy a vezérlés ne Unity-specifikus
parancsokkal, hanem absztrakt sebesség-parancsokkal (linear_velocity_mps,
angular_velocity_radps) történjen, hogy később könnyebben átvihető
legyen WheelCollider-re vagy fizikai roverre — ezt a döntést a
docs/coordinate-system.md fájlban dokumentáltam.

### Fuzz-tesztelési tapasztalatok és ismert korlátok (M05)

A `protocol_fuzz_test.py` sikeresen igazolt, és segített kijavítani két
valódi hibát a `RoverGatewayServer.cs` fájlban: egy regressziót, amely minden
kérésnél lefagyást okozott, valamint egy JSON-validációs rést, amely
csendben elfogadta a duplikált vagy nem dokumentált extra mezőket. Mindkét
hibát kijavítottuk, amit a fuzz teszt is megerősített:
`test_hibas_es_csonka_json_mindig_strukturalt_hibat_ad: ok`.

A randomizált `test_move_randomizalt_tartomanyok` és
`test_turn_randomizalt_tartomanyok` futtatása során ugyanakkor többször
megbízhatatlanná vált a helyi Python tesztkliens és a Unity Editor közötti
kommunikáció, jellemzően több egymást követő lépés után. A timeoutok
`WATCHDOG_EXPIRED` hibát és ERROR állapotot eredményeztek. A jelenség
feltételezett oka a Unity Editor háttérfolyamatainak vagy a helyi gép
erőforrás-terhelésének hatása.

Ezt tesztinfrastruktúra-korlátként, nem protokollhibaként dokumentáljuk.
A szerver minden egyedileg, kézzel tesztelt esetben helyesen viselkedett a
validáció, az állapotgép, a `reset_error` és az idempotencia tekintetében.
Jövőbeli munkaként érdemes a fuzz tesztet izolált CI-környezetben vagy
stabilabb hálózati és erőforrás-körülmények között futtatni.

### 11. Protokoll-review támadói/hibakereső szemszögből (M05 kötelező AI-használat)
A Codex-től kértem egy protokoll-review-t a RoverGatewayServer.cs jelenlegi
implementációjáról, kifejezetten támadói és hibakereső szemszögből. A Codex
felsorolta a lehetséges visszaéléseket (végtelen/túl nagy mozgásparancsok,
NaN/Infinity értékek, request_id ismétlés, gyors egymás utáni parancsok,
kapcsolatbontás menet közben), konkrét számszerű korlátokat javasolt
(sebesség, távolság, szög, timeout, watchdog), egy formális állapotgépet
(IDLE/MOVING/TURNING/ERROR), egy hibakód-rendszert, és egy idempotencia-
megoldást. Ez alapján terveztük meg és dokumentáltuk a docs/protocol.md
fájlban a v1 protokollt.

Az 5 kiemelt prioritást valósítottam meg (véges számok + validáció,
állapotgép, watchdog, idempotencia, frame/rate limit) a teljes javasolt
security-csomag (TLS, control lease, teljes audit-napló) helyett, mivel ez
egy lokális kutatási prototípus, és ezt a döntést a docs/protocol.md
"Tudatosan elhalasztott elemek" szakaszában dokumentáltam.

### 12. Protokoll implementáció és hibajavítás
A Codex implementálta a turn és get_status parancsokat, az állapotgépet,
a szigorú validációt, az idempotencia-cache-t, a reset_error parancsot,
valamint a dinamikus timeout-számítást a fuzz tesztekhez. Egy köztes
lépésben a Codex regressziót vezetett be (minden kérés lefagyott), amit
ő maga azonosított és javított egy try-catch védelemmel és részletes
naplózással.

### 13. Szcenárió-séma, generátor és dokumentáció (M06 kötelező AI-használat)
A Codex-től kértem egy JSON sémát egy zárt, stadion alakú rover-pálya
leírásához (geometria, akadályok, seedelt ütemezés), egy generátor
szkriptet, ami determinisztikusan (SHA-256 alapú, platformfüggetlen
módon) állítja elő a train/dev/test példaszcenáriókat, valamint
dokumentációt (docs/scenario-schema.md). A seedeket a Codex tudatosan
nem "kézzel kitalálva" adta meg, hanem egy dokumentált, reprodukálható
segédszkripttel generálta a szcenárió stabil azonosítójából - ezzel
teljesítve a feladat azon megkötését, hogy a teszt seedek ne kerüljenek
"bele" a promptpéldákba.

**Fontos korlát**: a hónapos Codex-kvóta (JetBrains AI) elfogyott menet
közben, mielőtt a validátor és a reprodukálhatósági teszt elkészült
volna. Ezt a két fájlt (experiments/scenario_validator.py,
tests/scenario_seed_test.py), valamint a Unity pálya-építő scriptet
(unity/Assets/Scripts/TrackController.cs) emiatt kézzel írtam meg,
Claude segítségével, Codex nélkül - a Codex által lefektetett séma és
generálási logika pontos ismeretében, hogy a kimenet konzisztens
maradjon. Ezt azért fontos dokumentálni, mert az M06 kötelező
AI-használati elemét (validátor) végül nem AI készítette.

A validátor és a reprodukálhatósági teszt mindegyike lefutott és
sikeres: mind a 3 példaszcenárió érvényes a JSON Schema szerint, és a
reprodukálhatósági teszt igazolta, hogy azonos (típus, név) pár mindig
azonos seedet és azonos akadálysorozatot ad.

### 14. Szenzorkalibráció és háromszenzoros mód (M07 kötelező AI-használat)
A Claude-tól kértem segítséget az M07 mérföldkőhöz: a ColorSensor.cs
kalibrációjának elemzéséhez (5 ismert pozícióban mért intenzitásérték
kiértékelése, a 0.5-ös alapértelmezett küszöb mérés alapú igazolása),
valamint a háromszenzoros (bal-közép-jobb) elrendezés
megtervezéséhez és megírásához. A Claude megírta a SensorArray.cs
komponenst, amely egy kapcsolható (Inspectorban és kódból is
átállítható) haromSzenzorosMod mezővel aktiválja/deaktiválja a bal
és jobb szenzor GameObject-jét, míg a középső mindig aktív marad. A
munka során előkerült egy már meglévő hiba is: a TrackController.cs
két helyen a `.material` property-t használta `.sharedMaterial`
helyett, ami Edit módban anyag-szivárgáshoz vezetett volna — ezt is
a Claude segítségével javítottuk. A háromszenzoros mód helyes,
differenciált működését a pálya kanyarjában végzett kézi teszttel
igazoltam: a három szenzor egyidejűleg eltérő kimenetet adott
(I=0.00 not_white, I=0.12 not_white, I=1.00 WHITE), lásd
docs/sensors.md.

### 15. LiDAR-szimuláció, kalibráció és profilozás (M08 kötelező AI-használat)
A Claude-tól kértem segítséget az M08 mérföldkőhöz: a LidarSensor.cs
megtervezéséhez és megírásához (raycast-alapú, konfigurálható
látómezejű/felbontású 2D LiDAR-modell, szektoros tömörítéssel, zaj-,
dropout- és késleltetés-modellezéssel), valamint a geometriai
kalibráció és a futásidő-profilozás terveinek kidolgozásához. A
kalibráció két lépésben zajlott: előbb egy elvi, transzformáció
nélküli tesztobjektumon (hogy kiküszöböljük a RoverChassis összetett
skálázásából eredő zavaró tényezőket), majd megismételve közvetlenül
a RoverChassis-on lévő éles Lidar komponensen is, ismert
világkoordinátás pozíciókban elhelyezett tesztakadállyal. Mind az öt
mérési pont (0.5/1.5/2.5/4.5/7.5 m elvárt felület-távolság) a 0.02
m-es beállított zaj-szórás ésszerű tartományán belül teljesült,
mindkét tesztsorozatban. A futásidő-profilozás négy felbontásnál
(12/36/72/144 sugár) 0.040–0.239 ms közötti, közel lineárisan
skálázódó mérési időt igazolt. A munka során felmerült egy
self-collision probléma is (a Lidar a rover saját dobozütközőjébe
ütközött) — ezt egy külön "Rover" Unity-réteg bevezetésével és az
Akadaly Reteg mezőből való kizárásával oldottuk meg. Lásd
docs/lidar.md.

### 16. Az observe válasz bővítése szenzoradatokkal (M09 előkészítés, kötelező AI-használat)
Az M09 mérföldkő (hagyományos, AI nélküli vonalkövető baseline)
tervezése közben felmerült, hogy az `observe` parancs válasza addig
kizárólag a rover Unity-beli `position` és `speed` mezőit adta
vissza — ezekre a baseline controller nem támaszkodhat, mivel egy
valódi roveren nem állna rendelkezésre ilyen privilegizált
szimulátor-információ. A Claude-tól kértem segítséget a
RoverGatewayServer.cs observe válaszának kibővítéséhez: a szerver
mostantól a SensorArray komponensből kiolvasva `sensor_mode`
(single/three) és `sensor_left`/`sensor_center`/`sensor_right`
mezőket is visszaad, mindegyiket a saját `white`/`intensity`
értékével. A bővítés additív és visszafelé kompatibilis, a
protokollverzió emiatt nem változott (marad v1). A módosítást a
Python TCP klienssel (gateway/client.py) manuálisan teszteltem: az
`observe` parancsra adott válasz helyesen tartalmazta mindhárom
szenzor aktuális mérését. A docs/protocol.md dokumentációt is
frissítettük az új válaszmezők leírásával és egy rövid
verziótörténeti bejegyzéssel.

### 17. Baseline vonalkövető kontroller, akadályelkerülés és reset_position (M09 kötelező AI-használat)
A Claude-tól kértem segítséget az M09 mérföldkőhöz: egy
hagyományos, szabály-alapú (nem AI-vezérelt) vonalkövető baseline
kontroller (`controllers/baseline_line_follower.py`) megtervezéséhez
és megírásához - állapotgép (VONALON/KERESES/AKADALY) egy P-
szabályozóval a bal/jobb szenzor intenzitáskülönbségére. Az első
tesztek során kiderült, hogy a rover kerekei nekiütköztek az
akadályoknak fordulás közben, mielőtt a test elfordulhatott volna -
ennek okát (a RoverChassis Scale Z=1.5 túlnyújtása és a kerekek
aránytalan mérete) a Claude segítségével azonosítottuk és
javítottuk (Scale Z 1.0-ra, kerekek arányosítva). Emellett a Claude
megírta a LidarSensor szektoradatainak (`lidar_szektor_min`)
observe-válaszba integrálását az akadályelkerüléshez, és egy új
`reset_position` protokollparancsot (a meglévő
BiztonsagosHibaReset/RoverAzonnaliLeallitasa segédmetódusok
újrahasznosításával), hogy a kísérleti futások azonos
kezdőállapotból induljanak.

Két mérési sorozatot (30-30 futás) végeztünk: az elsőben átlagosan
3.9 akadálykerülést mértünk nagy szórással (0-23), amit egy
oszcilláló akadály-elkerülési viselkedésre gyanakodva hiszterézis
bevezetésével (0.5 m belépési / 0.8 m kilépési küszöb) és a
fordulási szög növelésével (15°→45°) próbáltunk kezelni. A második
mérés (átlag 4.6, szórás 5.0, 0-12 tartomány) azt mutatta, hogy ez
a beavatkozás **nem oldotta meg érdemben** a jelenséget - a nyers
adatokban kétmodális eloszlás maradt (a futások kb. egyharmada
10-12 körüli, ismétlődő akadálytalálkozást mutatott). Ezt a
mérföldkő dokumentációjában (docs/m09-plan.md) őszintén, negatív/
vegyes eredményként rögzítettük, a gyökérok pontos diagnosztizálását
(lépésenkénti naplózás hiányában) jövőbeli munkaként (M10)
azonosítva, nem próbáltuk tovább vakon paraméter-hangolással
"eltüntetni" a jelenséget.

### 18. M10: ütközésdetektálás, lépésnaplózás, vonal-visszakeresés (M10 kötelező AI-használat)
Az M10 mérföldkő elején a Claude-tól kértem, hogy a hivatalos
feladatkiírás alapján állítson össze egy M10 tervet
(`docs/m10-plan.md`), majd a repó tényleges állapotát egyeztetve vele
derült ki két, korábban észrevétlen rés: a `docs/protocol.md` nem
dokumentálta a már M08 óta létező `lidar_szektor_min` mezőt, és a
rendszernek egyáltalán nem volt ütközésdetektálása (az "akadálykerülések
száma" metrika valójában csak az AKADÁLY állapotba lépések számát
mérte, nem a kerülés sikerességét). A Claude ezeket pótolta: `Akadaly`
tag bevezetése (`TrackController.cs`, `TagManager.asset`),
`OnCollisionEnter` kezelő és `collision_occurred`/`collision_count`
mezők (`RoverGatewayServer.cs`, `observe` válasz), dokumentálva
`docs/protocol.md`-ben, kizárólag diagnosztikai célként megjelölve.

Emellett a Claude megírta a lépésenkénti diagnosztikai naplózást
(`LepesNaplozo` osztály a baseline kontrollerben), egy heurisztikus
oszcilláció-kereső elemzőszkriptet (`controllers/analyze_step_log.py`),
és egy új, teszteletlen `VISSZATALALAS` állapotot az akadálykerülés
utáni explicit vonal-visszakereséshez (az elkerülési iránnyal
ellentétes irányba forogva keres, és `KERESES`-re eszkalál, ha nem
talál vonalat). Az állapotgép mind a négy állapotára írt 9 unit tesztet
(`tests/baseline_line_follower_test.py`, stub gateway-kliens, Unity
nélkül futtatható) - mind zöld.

**Emberi ellenőrzés (Unity Play mód):** manuálisan teszteltem az
ütközésdetektálást Play módban - egy mindig aktív teszt-objektumot
(`TesztAkadaly`) ideiglenesen `Akadaly` taggel ellátva, és a rover
pozícióját kézzel ráállítva, az `OnCollisionEnter` helyesen és
ismételten lefutott a Console naplóban. Ezzel megerősítést nyert,
hogy a mechanizmus működik.

A teszt közben egy fontos, nem tervezett módszertani problémát is
feltártunk: ha a rover mélyen belelóg egy akadályba és ott marad, a
fizikai motor minden lépésben újra meghívja az `OnCollisionEnter`-t,
így egyetlen folyamatos ütközés a jelenlegi implementációval több
tucat különálló eseményként számolódik (13-szor nőtt a számláló
néhány másodperc alatt egyetlen beragadás során). Ezt dokumentáltuk a
`docs/m10-plan.md`-ben, mint az éles mérés előtt kötelezően javítandó
hibát - nem hallgattuk el és nem próbáltuk "belesimítani" az
eredménybe.

A `VISSZATALALAS` állapot tényleges Unity Play mód-os viselkedése
még nem lett kipróbálva - ez a következő lépés.

**Utólagos javítás (ugyanaznap):** a fenti, dokumentált többszörös
ütközés-számlálási hibát kijavítottuk. Az első próbálkozás (a
`OnCollisionEnter`/`OnCollisionExit` pár segítségével számolt, hány
akadállyal érintkezik éppen a rover) **nem vált be** - egy
diagnosztikai naplózással feltártuk, hogy a rover több colliderje
(alváz + 4 kerék) egyszerre, mélyen átfedésben egy akadállyal
instabil, oda-vissza ugráló érintkezés-jelzéseket okozott a fizikai
motorban, így a számláló továbbra is hamisan magas maradt. Ehelyett egy egyszerűbb, időalapú "hűtési" (cooldown) mechanizmusra váltottunk
(0.5 másodperc): ez manuálisan tesztelve bevált - egy rögzített
pozícióban a számláló nem nőtt tovább több mint két percig, míg a
korábbi verzióval percenként több tucatszor nőtt volna.

**A `VISSZATALALAS` állapot Unity Play mód-os validálása:** 10
automatizált futást hajtottam végre a baseline kontrollerrel az
eredeti (időzített) szcenárión. 18, teljes 500 lépésig lefutott
"tiszta" futás közül 11-ben aktiválódott a `VISSZATALALAS` állapot,
és mind a 11 esetben sikeresen visszatalált a vonalra, egyetlen
eszkalálás sem történt a tágabb `KERESES` állapotra. A Claude
figyelmeztetett, hogy ez a mintaméret (11 esemény) kicsi az
általános megbízhatóság megállapításához, ezt a korlátot a
`docs/m10-plan.md`-ben is dokumentáltuk.

Eközben egy saját hibámat is érdemes rögzíteni: a tesztelés
felgyorsítása érdekében ideiglenesen "örökké láthatóvá" tettem a
szcenárió akadályait a szcenárió-JSON-ban - ez torzította a mérést
(a rover a pálya körbejárása során ismételten ugyanabba az
akadályba futott, 17-39 ütközés/futás, gyakori pályaelhagyás). A
Claude segített felismerni a torzítás okát és visszaállítani az
eredeti időzítést, ami után a viselkedés visszatért az M09-cel
konzisztens, egészséges mintázathoz.

**Zsákutca-kezelés (ugyanaznap):** a Claude-tól kértem a `docs/m10-plan.md`
5. munkacsomagjának (zsákutca és eltűnő akadály kezelése)
megvalósítását. Egy explicit lépésszámláló bevezetésével (ha a rover
`ZSAKUTCA_AKADALY_MAX_LEPES` lépésig nem tud kikerülni egy akadályt,
a `KERESES` állapotra eszkalál, külön statisztikaként számolva) és
egy hozzá tartozó unit teszttel egészítettük ki a rendszert. Az
eltűnő akadály esetére a Claude azt javasolta, hogy ezt **ne**
próbáljuk explicit módon megkülönböztetni a sikeres kerüléstől
valós időben, mert az privilegizált pozíció-adat használatát
igényelné a vezérlési döntésben - ehelyett dokumentáltuk ezt mint
tudatos tervezési korlátot, ami utólag, diagnosztikai célra a
lépésnaplóból elemezhető.

A manuális szerkesztés (Rider-ben, kézzel másolva/beillesztve) során
két kódszerkesztési hiba is becsúszott: egyszer egy `import`-lista
csere véletlenül szintaktikai hibát okozott, egyszer pedig egy
függvényhívás módosítása közben egy `elif` ág rossz behúzással és
rossz argumentum-sorrenddel csúszott be. Mindkettőt a hibaüzenetek
(`SyntaxError`, `TypeError`) alapján, a kód pontos, aktuális
állapotát megnézve azonosítottuk és javítottuk - egyik esetben sem
próbáltunk vakon, a tényleges fájltartalom ellenőrzése nélkül
módosítani.

**Akadály-időzítés javítása és végleges mérés (ugyanaznap):** a
végleges 30 futásos mérési sorozat közben derült ki egy komoly,
korábban észrevétlen hiba - az akadályok `schedule.appear_at_s`/
`disappear_at_s` időzítése a Play mód *indításához* volt kötve, nem
az egyes futások `reset_position` parancsához. Ez azt jelentette,
hogy az akadályok gyakorlatilag csak egyszer, röviddel a Play mód
elindítása után jelentek meg, utána egy teljes Play munkamenetben
soha többé - így a korábbi mérési sorozatok jelentős része
valójában akadály nélkül futott. A Claude-dal együtt azonosítottuk
a gyökérokot (a `TrackController.Update()` a `Time.timeSinceLevelLoad`
abszolút értékét használta), és bevezettünk egy
`UjrakezdiAkadalyUtemezest()` nyilvános metódust, amit a
`RoverGatewayServer` minden `reset_position` parancsnál meghív.
Eközben egy másik hibát is találtunk és javítottunk: a
`TrackController.FelepitAkadalyokat()` korábban sosem törölte a
korábban létrehozott akadályokat újraépítés előtt, ami Editor-beli
újrafordításoknál duplikálódáshoz és `MissingReferenceException`-höz
vezetett.

Menet közben kiderült egy további, gyakorlati korlát is: a 70x Time
Scale miatt a hálózati parancsok oda-vissza útja alatt is több
szimulált másodperc telik el, így az eredeti, rövid (5-7 másodperces)
időzített akadály-ablakot TCP-n keresztül irányítva gyakorlatilag
lehetetlen eltalálni. Emiatt a végleges méréshez **tudatosan és
dokumentáltan** állandóan láthatóvá tettük az akadályokat (eltérve az
eredeti, tervezett időzített szcenáriótól) - ezt a döntést és a
korlátot a `docs/m10-plan.md`-ben egyértelműen jelöltük, nem
próbáltuk elhallgatni vagy "véletlennek" beállítani.

A végleges mérés (30 futás, mindkét akadály állandóan látható): átlag
2.8 akadálykerülés/futás, 0 zsákutca, de **18/30 futásban
pályaelhagyás** és átlag 20.9 ütközés/futás. A Claude egyértelműen
jelezte, hogy ez nem az M10-es fejlesztések (ütközésdetektálás,
VISSZATALALAS, zsákutca-kezelés) hibája - azok külön-külön, célzott
teszteken igazoltan helyesen működnek -, hanem az M09-ben már ismert
oszcillációs probléma élesebb megjelenése, mert az állandóan jelenlévő
akadály nem ad esélyt a rovernek "megúszni" egy rossz elkerülési
döntést. A gyökérok-javítást nem próbáltuk ebben a mérföldkőben
megoldani, hanem explicit módon M11+ munkaként azonosítottuk.

Ez a szakasz sok manuális Unity/Rider-műveletet igényelt (script-
módosítások, Time Scale állítgatása, JSON-szerkesztés), és menet
közben több félresikerült próbálkozás is volt, mire a Claude
azonosította a tényleges gyökérokot - ezt szándékosan nem
szépítettem el, mert a folyamat maga is tanulság: első ránézésre
"nem működik az akadálykerülés" jelenség mögött végül egy
infrastrukturális (időzítési) hiba állt, nem a vezérlési logika
hibája.

**M10.5 (ugyanaznap, utólagos gyökérok-javítás):** az M09/M10-ben
dokumentált oszcillációs jelenség gyökérokát a Claude az
`analyze_step_log.py` végleges mérési adaton történő lefuttatásával
azonosította: az AKADALY állapot korábban kizárólag fordult, sosem
haladt előre, ezért a rover valódi oldaltávolság-nyerés nélkül látta
"tisztának" a kilátást egy kis elfordulás után. Két javítási
kísérlet is történt, mindkettő őszintén dokumentálva:

1. Első kísérlet (45°-os fordulás + előrehaladás minden lépésben):
   Unity Play módos, videóval dokumentált teszt megmutatta, hogy a
   rover nagy, tág köröket írt le az akadály körül, elhagyva a
   vonalat - a diagnózis helyes volt, a megvalósítás túl durva.
   Elvetve.
2. Finomított javítás (15°-os fordulás + előrehaladás): videóval
   megerősítve, hogy a rover következetesen körbejárja a pályát.
   30 futásos mérés: pályaelhagyás 60%->3.3%.
3. Második finomítási kísérlet (biztonsági távolság küszöb az
   előrehaladáshoz): 30 futásos mérés nem mutatott javulást, sőt
   rontott az eredményen. Elvetve.
4. `AKADALY_KUSZOB_KILEPES_M` paraméterkeresés (0.8 -> 1.5 -> 1.1):
   az 1.1-es érték minden mutatóban a legjobb eredményt adta:
   pályaelhagyás 60%->0%, átlagos ütközésszám 20.9->10.2.

Minden lépésnél a Claude adta a diagnózist és a konkrét kódjavaslatot,
a felhasználó pedig Unity Play módban, kézzel (Rider-ben szerkesztve)
vezette be a saját projektjébe, és videóval/naplóadattal ellenőrizte
minden egyes kísérlet tényleges hatását - beleértve a két elvetett,
negatív eredményű kísérletet is. Részletek: `docs/m10-5-plan.md`.


### 19. M11: naplózási séma, replay, CI és egyparancsos kísérletindítás (M11 kötelező AI-használat)

Az M11 minden munkacsomagjánál a Claude adta a tervet és a
kódjavaslatot, a felhasználó Rider-ben/terminálban vezette be és
Unity Play módban, élesben ellenőrizte:

1. **Egységes naplózási séma** (`common/kiserlet_naplo.py`): a
   vezérlési adatok és a privilegizált diagnosztika szándékos
   szétválasztása két blokkra a Claude javaslata volt, hogy a "ne
   használjon privilegizált Unity-pozíciót" elv a naplóból is
   ellenőrizhető legyen.
2. **Replay-vizualizáció** (`controllers/replay_visualizer.py`):
   első verzióban a `collision_occurred` mezőt használtuk, ami a
   teljes útvonalat "ütközöttnek" jelölte; a `RoverGatewayServer.cs`
   forrásának átnézésével a Claude azonosította, hogy a mező ragadós,
   és a `collision_count` lépésenkénti változására váltottunk.
3. **CI-pipeline** (`.github/workflows/ci.yml`): a Claude írta a
   workflow-t; a `protocol_fuzz_test.py` tudatos kihagyása (élő
   Unity kell hozzá) közös döntés. A PAT `workflow` hatáskörének
   hiányát a felhasználó oldotta meg.
4. **Egyparancsos kísérletindítás** (`controllers/futtat_kiserletet.py`):
   a Claude írta; az éles próbán a felhasználó vette észre, hogy az
   összesítő 30 futást ír 3 helyett - a `--utolso` kapcsoló ennek a
   javítása.

5. **Referenciaepizód és CI-bővítés** (elfogadási feltétel): a Claude
   javasolta, hogy a friss klónból reprodukálható referenciaepizód
   ne élő Unity-futásra, hanem egy commitolt lépésnaplóra épüljön
   (`experiments/referencia_epizod/`), és a metrika-ellenőrzés
   (`scripts/referencia_epizod.py`) a CI-ban is fusson. A CI-t a
   kiírás négy előírt elemére bővítettük (tesztek, sémavalidáció,
   pyflakes, dokumentáció-ellenőrzés). A pyflakes három valódi
   hibát talált (nem használt változó/importok), a
   dokumentáció-ellenőrzés (`scripts/ellenoriz_dokumentaciot.py`)
   pedig helyben zöld volt, CI-ban piros: a dokumentumok
   `.gitignore`-olt naplófájlokra hivatkoztak. A javítás nem lazítás
   volt, hanem `git ls-files` alapú ellenőrzés + a futásidőben
   generált fájlok explicit, kommentált listája - így helyben és
   friss klónban azonos eredményt ad.
6. **Replay videó** (`--video` kapcsoló): a Claude implementálta
   matplotlib `FuncAnimation`-nel, a felhasználó a referenciaepizódon
   generálta és ellenőrizte (`docs/videos/m11-referencia-replay.gif`).
7. **Lefedettségi összefoglaló** (`tests/README.md`): a Claude
   állította össze a 29 teszt táblázatát azzal, hogy melyik teszt
   melyik korábbi hibára regressziós; a felhasználó ellenőrizte az
   állításokat.

8. **Unity Edit/Play Mode tesztek**: a Claude írta a tesztfájlokat és
   az asmdef-eket a repó forrásának átolvasása alapján (publikus API:
   `TavolsagAKozepvonaltol`, `LidarSensor.NyersTavolsagok`,
   `ColorSensor.FeherVonalon`); a felhasználó futtatta a Unity Test
   Runnerben és a Unity-hibaüzenetek alapján közösen javítottuk az
   assembly-beállításokat (egy mappa - egy asmdef; Play Mode-hoz üres
   `includePlatforms`). Kiderült, hogy a repóban a korai mérföldkövek
   óta volt Play Mode teszt (`MovementControllerPlayModeTests.cs`), ami
   a dokumentációból hiányzott. **Az első futtatás egy valódi, M07 óta
   lappangó geometriai hibát talált** (fantom fehér ív a stadion
   belsejében, lásd `docs/m11-plan.md` 3. munkacsomag): a Claude
   azonosította az okot a teszt hibaüzenetéből, javasolta a javítást
   és a regressziós tesztet, a felhasználó Unity-ben ellenőrizte
   (5/5 + 5/5 zöld).

Egy Unity-crash után `Assets/_Recovery/` mappa keletkezett; a Claude
a jelenetfájlok objektumneveinek összevetésével (`grep m_Name`)
igazolta, hogy a mentett `TrackScene.unity` teljes, a recovery csak
duplikált, futásidőben generált akadályokat tartalmazott - törölve.

### 20. M12: agent-interfész - backend-absztrakció, biztonsági réteg, MCP-szerver, vak API-kiértékelés (M12 kötelező AI-használat)

Az M12 minden munkacsomagjánál a Claude adta a tervet és a
kódjavaslatot, a felhasználó vezette be és ellenőrizte a teszteket:

1. **Backend-absztrakció és biztonsági réteg** (`adapter/backend.py`,
   `adapter/orseg.py`): a Claude tervezte meg a `Backend` protokollt
   (Unity TCP + memóriabeli mock, azonos interfésszel) és az "őrség"
   réteget (parancsszűrés, paraméter-validáció a backend előtt,
   session-limitek, privilegizált mezők elrejtése). A `MockBackend`
   a pálya-geometriát az M11-ben javított
   `TavolsagAKozepvonaltol`-logika Python-párjaként számolja, hogy
   Unity nélkül is determinisztikus tesztek fussanak. 11 adapter-teszt,
   bekerült a CI-ba.
2. **MCP-szerver** (`adapter/mcp_szerver.py`) és exportált tool schema
   (`scripts/export_tool_schema.py` → `docs/m12-tool-schema.json`): a
   Claude írta mindkettőt; a hat eszköz (`observe`/`move`/`turn`/
   `stop`/`reset_position`/`session_status`) leírását is a Claude
   fogalmazta meg, a felhasználó indította el élesben (`uv run`).
3. **Vak API-használhatósági kiértékelés**: a felhasználó egy önálló
   Claude Code munkamenetet indított azzal az explicit utasítással,
   hogy a forráskódot ne olvassa el, kizárólag az MCP-eszközök
   nevéből/leírásából vezesse a rovert kb. 20 lépésen át egy stadion
   alakú pályán, majd értékelje az API érthetőségét. A nyers kimenet:
   `docs/m12/agent-session-raw.txt`. A kiértékelő agent több érdemi,
   dokumentálatlan hiányosságot azonosított (lidar-szektor - fizikai
   irány leképezés, ajánlott biztonsági küszöb hiánya, `reset_position`
   keret-hatásának tisztázatlansága) - ezek a lépéshez tartozó
   `docs/m12-plan.md` 4. munkacsomagjában részletesek, jegyzőkönyvezve
   mint M12+ nyitott pontok, nem javítva még.
4. **Hiba: `.venv` véletlen verziókövetése**: a 3. munkacsomag
   commitjakor a teljes Python virtualenv (3207 fájl, ~90 MB)
   véletlenül bekerült a git indexbe és fel is lett push-olva, mert a
   `.venv/` sosem volt a `.gitignore`-ban. A folytatás munkamenetében
   a Claude vette észre a `git show --stat` áttekintésekor, javasolta
   a javítást (`.gitignore` bővítése + `git rm -r --cached`, tudatosan
   history-rewrite/force-push nélkül, mert az megosztott history-t
   írna felül), a felhasználó jóváhagyta a megközelítést és a push-ot.

### 21. M12 biztonsági átvizsgálás és a talált hibák javítása

A kiírás M12-es kötelező AI-használati pontjához egy **külön, tiszta Claude
Code munkamenet** olvasta el az `adapter/` három modulját, és készített
biztonsági átvizsgálást (nyers kimenet: `docs/m12/security-review-raw.txt`,
strukturált összefoglaló: `docs/m12-security-review.md`). Nyolc találat
született, súlyosság szerint rendezve, fájl- és sorhivatkozásokkal.

Öt találatot javítottunk (a Claude adta a javítás kódját, a felhasználó
ellenőrizte és hagyta jóvá): egységes, fail-safe backend-hibakezelés a
kivétel-szivárgás ellen; ütközésjelzés az `observe` válaszában; a `stop()`
javítása lezárt munkamenetben; az elutasított hívások beszámítása a
parancskeretbe; `assert` helyett `raise`. Kettő nyitva maradt M13+-ra
(wall-clock időkorlát, időzítés-alapú backend-felismerés), egy megfigyelés.

Két döntés a felhasználóé volt. Az egyik: a `collision_detected` bool
bevezetése az `observe`-ban, tudatos eltérésként az eredeti "minden
ütközés-adat rejtve" elvtől — indoklás a `docs/m12-security-review.md`
2. sorában. A másik: a `.venv` véletlen verziókövetését `.gitignore` +
`git rm --cached` úton javítottuk, nem history-átírással, mert az a
mérföldkő-tageket is áthelyezné.

Módszertani megjegyzés a kutatáshoz: a nyolc találat egyikét sem fogta meg a
11 meglévő unit teszt — egyik sem szimulált hálózati hibát, lezárt backendet
vagy ütközés utáni állapotot. A javításokhoz 7 regressziós teszt készült.
Ugyanez a minta ismétlődött az M11-ben is (fantom-ív hiba), tehát az
"AI-generált kód + AI-generált teszt" páros vakfoltjai rendszeresek: a tesztek
a boldog útvonalat fedik, a hibaágakat nem.

### 22. M10.6: az akadálykerülés újramérése és javítása

Kiindulópont egy külső, szigorú audit volt, ami több ponton nyitva találta az
M10-es elfogadási feltételt. A Claude ebből azt emelte ki, hogy a mérések
**érvényessége** a kérdéses, nem csak az eredménye: az M11-ben javított
fantom-ív hiba visszamenőleg is hatott, és ezt a `kor_metrika.py`-val
számszerűsítettük (a rover a lépések 73%-ában nem a valódi vonalon volt).

A munka menete: a Claude a lépésenkénti naplóból diagnosztizálta a három
állapotgép-hibát (AKADALY korai kilépés, VISSZATALALAS visszafordulás az
akadályba, KERESES helyben forgás), írta a javításokat és a hozzájuk tartozó
érvelést; a felhasználó futtatta a méréseket Unity Play módban, és a mérési
eredmények döntöttek minden lépésnél. Két tanulságos mozzanat:

- A **táguló spirál** hipotézist a mérés megcáfolta (163 ütközés/futás, a
  lépések 9%-ában volt a vonalon a 30% helyett). A javaslat logikusnak tűnt —
  a sikertelen futások mind 1.4-1.5 m-re álltak meg, épp a körív átmérőjén
  kívül —, mégis rontott. A visszavonás és a cáfolat dokumentálása a mérési
  fegyelem része, nem kudarc.
- A mérés közben négy **azonos** futás (121 lépés, 0.0 m megtett út) vezetett
  egy M09 óta lappangó hiba felfedezéséhez: ERROR-állapotból a
  `reset_position` nem hoz ki, mert az csak IDLE-ben működik.

A hangolást négy iteráció után **szándékosan abbahagytuk**: az utolsó kettő
nem hozott javulást, és a további paraméterezés a train-szcenárióra való
túlillesztés felé vitt volna. Az M10-es kapu ezért nyitva marad, őszintén
dokumentálva (`docs/m10-6-plan.md`) — negatív eredményként, megnevezett okkal.

### 23. M10.7: akadálykontúr-követés — elvetett javítási kísérlet

Az M10.6 után nyitva maradt kapuhoz (0/30 ütközésmentes futás) a Claude egy
elvi, nem hangolás-jellegű javaslatot adott: a bug-algoritmusok mintájára a
rover ne egy rögzített szöggel forduljon el az akadálytól, hanem egy
P-szabályozóval tartson állandó oldaltávolságot tőle, azaz kövesse a kontúrját
(`KERULES_CEL_OLDALTAV_M = 0.6`, `KERULES_P_FOK_PER_M = 25.0`).

**A mérés megcáfolta**: 349.6 ütközés/futás a referenciaként újramért 67.6
helyett, 0/5 task success az 1/5 helyett. A diagnózis a lépésnaplóból: pont a
szabályozó működése okozta a bajt — mivel az akadályt pontosan 0.6 m-en
tartotta, a kilépési feltétel (`AKADALY_KUSZOB_KILEPES_M = 1.1`) soha nem
teljesült, így a rover körbekeringte az akadályt ahelyett, hogy elhagyta volna.
A bug-algoritmusok hiányzó eleme a *leave condition*, amihez tudni kellene,
merre van az eredeti útvonal — ez a jelenlegi, szenzor-only interfészen nem áll
rendelkezésre.

A javítást visszavontuk, a kontroller a mért M10.6-os állapotában maradt. A
kísérlet, a mérési adatok és a módszertani tanulság a `docs/m10-6-plan.md`
„Elvetett javítás 2.: akadálykontúr-követés (bug-algoritmus)" szakaszában.

Ez a kísérlet jelölte ki a továbblépés irányát is: a hiányzó kilépési feltételt
**odometriával** lehetne pótolni, azaz a rover saját kiadott `turn`/`move`
parancsainak integrálásával. Ez nem privilegizált szimulátor-adat — a rover a
saját parancsait ismeri —, tehát nem sérti a kutatás alapelvét. M13+ munkaként
rögzítve.

Ezzel a hangolást tudatosan abbahagytuk: négy iterációból az utolsó kettő nem
hozott javulást, és a további paraméterezés a train-szcenárióra való
túlillesztés felé vitt volna.

### 24. M13 előkészítés: nyers LiDAR-vektor az API-ban

Az M13 (agent-vezérelt rover) egyik kutatási kérdése, az **RQ5**, azt vizsgálja,
hogy egy ágens a **tömörített** szektoradatból vagy a **nyers** szenzorjelből
vezérel-e jobban. Az `observe` válasz addig csak a 6 elemű `lidar_szektor_min`
mezőt adta vissza, így az RQ5 egyszerűen nem volt vizsgálható — ezt egy külső
audit is jelezte.

A `LidarSensor` (M08) már korábban is publikussá tette a nyers adatot
(`NyersTavolsagok`, `ErvenyessegiMaszk`), tehát a szenzort nem kellett
módosítani, csak kivezetni az `observe` válaszába. A bővítés additív, a
protokollverzió marad v1.

Egy részletre a Claude külön felhívta a figyelmet, és ez érdemi tervezési
döntés lett: a `LidarSensor` a **kimaradt és a találat nélküli** sugarakat
egyaránt a maximális hatótávval (10.0) tölti ki. A szektoros tömörítés eddig
kiszűrte az érvényteleneket, de a nyers jelnél ez elveszne — az ágens nem
tudná megkülönböztetni a „szabad az út 10 méterig" és a „ez a sugár kimaradt"
esetet. Ezért a `lidar_nyers` mellé bekerült a `lidar_nyers_ervenyes` maszk is.

Az élesben, Unity Play módban végzett ellenőrzés ezt rögtön igazolta is: egy
`observe` válaszban 36 sugárból csak kettő volt `true` (a két akadályt találó
sugár), a többi 34 pedig `false` — pedig mind 10.0-t írt. A nyers számok
önmagukban azt sugallták volna, hogy minden irányban 10 méterig szabad az út.

Ugyanez az ellenőrzés egy pontatlanságot is feltárt a saját
dokumentációnkban: a maszk `false` értéke valójában **kétfélét** jelenthet
(nincs akadály hatótávon belül, vagy kimaradt a mérés), és ezeket a
`LidarSensor` nem különbözteti meg. Az első megfogalmazás „érvényes-e a mérés"
-ként írta le, ami szenzorhibát sugallt — holott nyílt pályán a `false` a
normális érték. Javítva; a megkülönböztetés hiánya nyitott kérdésként
rögzítve az M13-hoz.
Ez ugyanaz a fajta csendes torzítás, mint az M11-ben felfedezett fantom fehér
ív: nem hibaüzenettel jelentkezik, hanem elrontott mérésekkel.

A `MockBackend` nem futtat valódi raycastert, ezért a nyers sugarakat a
szektorértékekből származtatja. Ez a kódban kommentként is rögzítve van, hogy
ne tűnjön valódi geometriának. Így a „szektor minimuma = a hozzá tartozó
sugarak minimuma" invariáns a mockban pontosan teljesül, és erre külön
regressziós teszt is készült.

### 25. Specifikáció-megfelelés és egy lappangó geometriai eltérés

Három, egymástól független hiányosság pótlása, amiket részben egy külső audit,
részben a `get_status` kapcsán indult vizsgálódás hozott elő.

**`get_status` mint agent-eszköz.** A kiírás 2.1 pontja nevesíti, az M12-es
adapterből mégis kimaradt. Nem formai kérdés: enélkül egy ágens nem veszi
észre, ha a rover ERROR állapotba került, és vakon küldene tovább parancsokat,
amiket a rover egyesével elutasít — miközben a parancskerete fogy. A válaszból
a `protocol_version` kikerül: fejlesztői adat, és a vak API-kiértékelés
tanulsága szerint minden fölösleges mező zajt visz az eszközleírásba.

Közben egy nyitott kérdés is megfogalmazódott az M13-hoz: **ERROR állapotból
az ágens nem tud saját erejéből kilépni**, mert a `reset_error` nem
agent-eszköz. Az eszközleírás ezt most explicit módon kimondja ("jelezd a
problémát, ne próbálkozz tovább"), de hogy ez a helyes tervezés-e, azt az M13-as
kísérlet fogja megmutatni.

**A kliens súgója.** A `gateway/client.py` kezelte a `reset_position`
parancsot, de a parancslistájából hiányzott. Egysoros, de ugyanaz a fajta rés
dokumentáció és valóság között, amit aznap már kétszer javítottunk.

**A prefab geometriája — ez volt a komoly.** A `coordinate-system.md`
átnézésekor derült ki, hogy az általa megadott alváz- és kerékméretek egyik
tényleges értékkel sem egyeznek. A nyomot követve kiderült, hogy **három
különböző geometria** van forgalomban: a jelenetbeli (amin minden mérés
készült), a prefabbeli (az M09 előtti, ütközésre hajlamos), és a
dokumentumban leírt (egyikkel sem azonos).

A gyökérok: az M09-es javítás — alváz Scale Z 1.5 → 1.0, kerekek arányosítva —
csak a jelenetbeli példányon történt meg, prefab-felülírásként (override).

**Helyesbítés (ugyanaznap, külső audit nyomán).** Ennek a bejegyzésnek az első
változata, a `83c36e6` commit üzenete és a `coordinate-system.md` azt állította,
hogy a jelenetbeli rover le lett választva a prefabról. Ez téves volt: a Claude
egy Play módban készült képernyőképből következtetett, a jelenetfájl ellenőrzése
nélkül. A commitolt `TrackScene.unity` prefab-példányt tartalmaz, a javított
méretekkel felülírva. A súlyosság is kisebb az alább leírtnál: a mérések friss
klónból is a helyes geometrián futottak volna, csak a prefab új példányosítása
adott volna régi rovert. A prefab javítása ettől függetlenül helyes.

Ez **reprodukálhatósági hiba**: friss klónból a prefabot példányosítva a
javítás előtti rover jött volna létre, vagyis a mérések nem lettek volna
megismételhetők — miközben az egész projekt erre épül. A prefab az M04
elfogadási feltételének része, ezért nem töröltük, hanem a jelenetbeli, mért
geometriához igazítottuk.

A diagnózis menete itt is a megszokott volt: a Claude a prefab- és
jelenetfájlok tényleges értékeinek összevetéséből állította fel a hipotézist,
a felhasználó pedig a Unity Inspectorban ellenőrizte és végezte el a javítást.

### 26. A `get_status` adatszivárgása: egy aznap bevitt hiba

A 25. pontban leírt `get_status` eszköz hibás volt, és ezt egy külső audit
találta meg néhány órával a bevezetése után. A Unity-szerver minden parancs
után a **teljes választ** eltárolta, a `get_status` pedig ezt adta vissza a
`last_command_result` mezőben. Egy `observe` utáni `get_status` így kiadta az
ágensnek a pozíciót, a sebességet és az ütközésszámlálót, vagyis pont azt, amit
az adapter elrejteni hivatott. Az adapter szűrője csak a felső szintű kulcsokat
nézte, a szövegbe ágyazott választ nem. Ugyanez a mechanizmus az ismételt
hívások válaszméretét hívásonként megduplázta.

A hibát a Claude vitte be: a `protocol_version` kiszűrésére figyelt, a
`last_command_result` tartalmát viszont nem nézte meg a szerver kódjában, és a
hozzá írt teszt a mockon futott, ami ilyen mezőt nem ad vissza.

Javítás két szinten: a szerver már csak rövid összefoglalót tárol
(`observe:completed`), az adapter pedig eldobja a mezőt, ha az beágyazott
JSON-nak látszik. A regressziós teszt egy kifejezetten szivárgó stub backendet
használ. A javítást élő Unityn is ellenőriztük.

### 27. Szcenárióhoz kötött kezdőpóz és a zajgenerátor újraindítása

Külső audit két pontja nyomán. (1) A rover addig ott indult, ahol a jelenetben
éppen állt: egy M07-es teszt maradványaként a kanyarban, elfordulva, ami csak a
train pályán esett a vonal közelébe. Mostantól a `TrackController` számolja a
kezdőpózt a szcenárió pályájából (az egyenes közepe, a vonalon), és a szerver
induláskor és minden resetnél oda állítja a rovert. (2) A szenzorok
zajgenerátora csak a Play mód indulásakor jött létre a seedből; mostantól
minden resetnél újraindul.

A Claude írta a kódot a szerver, a pályavezérlő és a két szenzor forrásának
átolvasása után; a felhasználó Unity Play módban ellenőrizte (`reset_position`
után `position` = (4,0; 0,0), a középső szenzor fehéret lát).

Ismert, még nyitott korlátok: a futások ettől még nem bitre azonosak, mert a
szenzorok `FixedUpdate`-enként húznak zajt, a parancsok pedig valós időben
érkeznek; és az élő mérés megerősítette, hogy a középső színszenzor kb.
11,5 cm-rel el van tolva oldalra. A korábbi baseline-mérések a régi kezdőpózzal
készültek, újramérés szükséges.

### 28. Mérésnaplózás és az M09-es kapu újramérése

Külső audit nyomán: a fő mérés a dokumentált paranccsal nem volt előállítható,
a napló nem rögzítette, mi futott, és az M09 akadálymentes kapuja a
geometria-javítás óta nem volt újramérve.

A Claude írta a naplózás bővítését (a Unity resetnél közli a betöltött
szcenáriót és a Time Scale-t; futásonkénti metaadat a paraméterekkel és a
committal; `--elvart-szcenario` kapcsoló) és az akadálymentes szcenáriót. A
sikerfeltételt (teljes kör pályaelhagyás nélkül, legalább 27/30) a felhasználó
hagyta jóvá, és a mérés előtt, külön commitban került a repóba (`f697693`).

A felhasználó élő Unityn futtatta a 30 futást: **30/30**. Közben két hiba
derült ki a meglévő eszközökben (a szcenárió-validátor üres akadálylistán, az
összesítő egyetlen futásnál szállt el), és egy a Claude új kódjában (a
tisztaság-ellenőrzés a verziókövetett napló miatt mindig hamisat adott volna).
Mindhárom a mérés előtt javítva.

Nyitva maradt: paraméter-sweep, mérés a dev és a holdout pályán, a szenzorok
aszimmetrikus elhelyezése. Részletek: `docs/m09-plan.md`.

### 29. Szenzorgeometria és teljes szélességű kerülés

Külső audit nyomán. A jelenet- és prefabfájlok átvizsgálása szerint a rover a
kerekekkel kb. 1,7 m széles, a kerülés viszont csak a ±30°-os elülső
szektorokat nézte, ami 0,5 m-en ±0,29 m-es sávot fed le; a középső színszenzor
és a LiDAR 11,5 cm-rel oldalra volt tolva; a szenzorok csak a jelenetben voltak
a roverre téve, a prefabban nem; az MCP eszközleírás pedig 0,35 m-es szélességet
és 6 cm-es szenzortávolságot közölt az ágenssel.

A felhasználó döntött: a rover marad, a kerülés megtanulja a teljes szélességet,
a szenzorok most kerülnek középre. A Claude írta a nyers LiDAR-sugarakból
számoló kerülési logikát és öt tesztjét, javította az eszközleírást és a mock
szenzortávolságát; a felhasználó Unityben helyezte át a szenzorokat, vitte át
őket a prefabba, és élőben ellenőrizte (a középső szenzor a vonal közepén 0,92-t
mér a korábbi 0,71 helyett).

### 30. M10 kapu: a kerülés javítása és a mérés (2026-10-08)

**Eszköz:** Claude (Claude Code), a kódot és a mérést Dalma futtatta a saját gépén.

**Kiindulás:** a korridoros kerüléssel egy próbafutás 21 ütközést adott.
A lépésnaplóból (állapot, parancsok, LiDAR-szektorok az ütközés pillanatában)
az derült ki, hogy a rover nem szemből, hanem oldalról és hátulról ütközik.

**Diagnózis és javítás, lépésenként (minden lépés után élő próbafutás):**

1. A helyben forduló rover sarkai (~1,07 m) beleértek az akadályba, és az oldalsó
   ellenőrzés (1,0 m a LiDAR-tól) nem számolt a 0,85 m-es félszélességgel →
   korábbi kitérés (1,0/1,3 m), oldalsó ellenőrzés a nyers LiDAR-ból a valódi
   szélességgel, 1,0 m-es vak zóna (a 180 fokos LiDAR nem lát hátra).
   Eredmény: 0 ütközés, de pályaelhagyás.
2. A visszatérés vakon fordult (5 fok × 15 lépés), a rover kifelé állva
   távolodott → iránytartás: a kitérés összegzett fordulatát visszaforgatja,
   majd 30 fokban tart a vonal felé. Eredmény: 0 ütközés, 0 pályaelhagyás,
   4 kerülés, mind visszatért.

**A mérés:** a kód (`0124aa1`) és a mérési terv (`7d86198`, 16/30-as küszöb)
külön commitban, a mérés előtt került a repóba. Eredmény: 25/30, a kapu
teljesült. A 4 pályaelhagyás ugyanott történt; ezt nem javítottuk utólag.

**Az ember döntései:** a 16/30-as küszöb elfogadása; a mérés futtatása.
**Az AI hibái ebben a szakaszban:** a hosszú beillesztendő parancsokat a
terminál többször elvágta; a megoldás a rövid, ellenőrző összeggel (md5)
igazolt darabok lettek.

*Pontosítás (2026-10-26):* a „kapu teljesült" csak a train szcenárióra igaz;
a holdout-mérés ezt nem igazolta. Lásd a 31. pontot és a `docs/m10-plan.md`
„Helyesbítés" szakaszát.

### 31. Második audit, holdout és a mérési lánc javítása (2026-10-08 – 10-26)

**Eszköz:** Claude (Claude Code). A Unity-méréseket Dalma futtatta a saját
gépén; 2026-10-26-tól Claude a repóba közvetlenül is commitol (GitHub-alkalmazás,
Dalma engedélyével), a commitokat a `Co-Authored-By` sor jelöli.

**M10 holdout és validáció.** Egy külső audit után a v1-es baseline-t egy
előre regisztrált holdout pályán is lemértük: 2/30 (bukás). A javított v3
(lengő keresés, `6ea4858`) egy seedből generált validációs pályán 28/30-at,
a train pályán regresszióként 29/30-at ért el; ez lett az M13 baseline.
Részletek és korlátok: `docs/m10-plan.md`.

**Az AI hibái ebben a szakaszban:**
- egy auditori hipotézisre épülő előjel-javítás (a nettó fordulat előjele
  nem azt mutatja, merre van a vonal) rontott a holdout eredményén;
  visszavonva, dokumentálva;
- a kör-metrika minden pályán a train geometriájával számolt, így a holdout
  vonalon-aránya és hatékonysága hibás volt; javítva (`e5f6be1`);
- egy mérés futásszintű összesítője kimaradt a commitból; pótolva.

**Javítások 2026-10-26-án (a gyűjtő-issue Unity nélküli pontjai):**
- egységes sikerfeltétel (kör + 0 ütközés + nincs pályaelhagyás) a
  szcenárió saját geometriájával, `run_id` a futásszintű összesítőben;
- futtató: érthető hiba üres szcenárió-névnél, 30 s-os socket-timeout,
  az elutasított gateway-parancs megállítja a futást (korábban csendben
  folytatódott), teljes KERESES-naplózás, `summarize_runs` KeyError;
- adapter: az ütközésjelzés reset után nem vész el, nincs hamis
  stop-nyugta backend-hiba után, a `UnityTcpBackend` ellenőrzi a
  `request_id`-t és tesztekkel fedett;
- lock-fájlok (`requirements-ci.txt`, `requirements-mcp.txt`), a
  referenciaepizód ellenőrzése nem írja felül a verziókövetett képet,
  `docs/sensors.md` és a gateway README a kódhoz igazítva.

Minden javítás regressziós tesztet kapott (61 Python- és 31 adapterteszt);
a viselkedést megváltoztató pont (elutasítás = futás megáll) a commitban és
itt is jelölve.

**Az ember döntései:** a holdout-mérés elvégzése a hibás baseline
befagyasztása helyett (A opció); a v3 elfogadása M13 baselinenak; a nyitott
pontok lezárása az M13 előtt.

## Megjegyzések

- Minden AI által generált kódot (Codex és Claude egyaránt) átnéztem és
  kipróbáltam, mielőtt bekerült volna a projektbe. A Unity-oldali változtatásokat
  Play módban, a Python-oldaliakat teszttel vagy éles méréssel ellenőriztem.
- A naplóban szándékosan benne maradtak a saját hibáim is (félrevitt mérés az
  „örökké látható" akadályokkal, kézi szerkesztési hibák Riderben, a `.venv`
  véletlen verziókövetése), mert a kutatás kérdése épp az, hogy egy ilyen
  munkafolyamat hol és hogyan hibázik.
- Visszatérő minta, amit érdemes külön kiemelni: **az AI-generált kód és az
  ugyanazon AI által generált teszt párosa rendszeresen ugyanazt a vakfoltot
  hagyja** — a tesztek a boldog útvonalat fedik, a hibaágakat nem. Két külön
  mérföldkőben is így derült ki egy lappangó hiba (M11: fantom fehér ív;
  M12: nyolc biztonsági találat, amiből egyet sem fogott meg a 11 meglévő teszt).
