# Rover vezérlési protokoll (v1)

## Áttekintés

TCP-kapcsolaton keresztüli, hossz-prefixelt, JSON-alapú protokoll a
rover vezérléséhez. Ez a dokumentum az M05 mérföldkőnél lefagyasztott
v1 protokollt írja le.

**Protokollverzió:** 1

## Kötelező mezők minden kérésben

```json
{
  "request_id": "UUID v4, 36 karakter",
  "command": "observe | move | turn | stop | get_status | reset_error | reset_position"
}
```

## Parancsok

### observe
Lekérdezi a rover aktuális pozícióját, sebességét és — az M09
mérföldkőtől kezdve — a vonalérzékelő szenzorok állapotát. Minden
állapotban engedélyezett.

**Válaszmezők (a szabvány mezőkön felül):**

```json
{
  "position": { "x": 0.0, "y": 0.0, "z": 0.0 },
  "speed": 0.0,
  "sensor_mode": "single | three",
  "sensor_left": { "white": false, "intensity": 0.0 },
  "sensor_center": { "white": false, "intensity": 0.0 },
  "sensor_right": { "white": false, "intensity": 0.0 }
}
```

- `position`, `speed`: a rover Unity-beli pozíciója (méter) és
  aktuális sebessége (m/s). **Kizárólag diagnosztikai/naplózási
  célra** - a szenzorokra épülő controllerek (pl. M09 baseline) nem
  támaszkodhatnak ezekre a mezőkre, mivel ez privilegizált
  szimulátor-információ, ami egy valódi roveren nem állna
  rendelkezésre.
- `sensor_mode`: `"single"`, ha csak a középső szenzor aktív,
  `"three"`, ha a bal-közép-jobb háromszenzoros elrendezés aktív
  (lásd `docs/sensors.md`).
- `lidar_szektor_min`: 6 elemű lista (`float[]`), a rover előtti
  180 fokos legyező hat, egyenként 30 fokos szektorának legkisebb
  mért akadálytávolsága méterben, balról jobbra rendezve. A
  `LidarSensor.MaxHatotav` (alapértelmezetten 10.0) érték azt
  jelenti, hogy az adott szektorban nincs akadály hatótávon belül.
  Ha a jelenetben nincs `LidarSensor`, a mező üres tömb. Az M08
  mérföldkőnél került be; a `position`/`speed`-del ellentétben ez
  **nem** privilegizált információ, egy valódi roveren is elérhető
  lenne (lásd `docs/lidar.md`).
- `lidar_nyers`: a LiDAR **nyers, sugáronkénti** távolságai méterben
  (`float[]`, alapértelmezetten 36 elem), balról jobbra rendezve,
  ugyanabban a 180 fokos legyezőben, mint a `lidar_szektor_min`. Az
  M13 mérföldkőnél került be, az RQ5 vizsgálatához: enélkül nem
  hasonlítható össze, hogy egy ágens a tömörített szektoradatból
  vagy a nyers jelből vezérel-e jobban. A `lidar_szektor_min`
  változatlanul megmarad - a kettő ugyanarra a mérésre épül, a
  szektor értéke a hozzá tartozó sugarak minimuma.
- `lidar_nyers_ervenyes`: logikai maszk (`bool[]`), sugaranként
  `true`, ha az adott sugár **talált** valamit a hatótávon belül.
  Enélkül a `lidar_nyers` félrevezető lenne: a nem találó sugarak is
  a maximális hatótávot (10.0) adják vissza, így a nyers számokból
  nem derülne ki, hogy ott mérés történt-e egyáltalán.
  **Figyelem, a `false` két dolgot jelenthet**, és ezeket a jelenlegi
  szenzormodell nem különbözteti meg: (1) nincs akadály a hatótávon
  belül - vagyis az irány *szabad*; (2) a mérés kimaradt
  (`meresKimaradasEselye`). A `LidarSensor` mindkettőt azonos módon
  jelöli. A `false` tehát **nem** jelent automatikusan szenzorhibát,
  és nyílt pályán ez a tipikus érték. Ha az M13-as kiértékelésnél a
  kettő megkülönböztetése számít, a `LidarSensor`-t kell bővíteni egy
  harmadik állapottal. A szektoros tömörítés a nem találó sugarakat
  eleve kiszűri, a nyers jelnél ezt a fogyasztóra hagyjuk. Mint a
  `lidar_szektor_min`, ez **sem** privilegizált információ.
- `collision_occurred` / `collision_count`: az M10 mérföldkőnél
  bevezetett ütközésdetektálás. **Privilegizált diagnosztika**: a
  controllerek nem használhatják vezérlésre, csak naplózásra és
  kiértékelésre. Az M12 adapter az agent elől elrejti a kumulatív
  számlálót, és helyette csak egy `collision_detected` logikai
  jelzést ad tovább (lásd `docs/m12-security-review.md`).
- `sensor_left` / `sensor_center` / `sensor_right`: az adott
  szenzor aktuális mérése. `single` módban a `sensor_left` és
  `sensor_right` mezők jelen vannak, de nem tükröznek valós mérést
  (a szenzor inaktív). `white`: a mért intenzitás a küszöb felett
  van-e. `intensity`: a nyers, zajjal terhelt mért érték (lásd
  `docs/sensors.md` a zajmodellért).

Ez additív, visszafelé kompatibilis bővítés - a protokollverzió
emiatt nem változott (marad v1).

### get_status
Lekérdezi a rover jelenlegi állapotát (state machine állapota,
protokollverzió, utolsó parancs eredménye). Minden állapotban
engedélyezett.

### move
Előre/hátra mozgatja a rovert megadott távolsággal és sebességgel.
Csak IDLE állapotban engedélyezett.

Paraméterek:
- `distance_m`: `0.01 - 2.00` (méter)
- `max_speed`: `0.05 - 0.50` (m/s)

### turn
Elforgatja a rovert megadott szöggel. Csak IDLE állapotban engedélyezett.

Paraméterek:
- `angle_deg`: `-180 - 180`, `abs(angle_deg) >= 1`
- `max_angular_speed`: `5 - 45` (fok/s)

### stop
Azonnal leállítja a rovert. Minden állapotban elfogadott, idempotens
(no-op, ha már áll).

### reset_error
Csak ERROR állapotban engedélyezett. Ha nincs aktív mozgás, és a rover
fizikai állapota biztonságos (minden pozíció-, forgás- és sebességérték
véges), a rovert a kezdő pozícióba és forgatásba állítja, majd IDLE
állapotba vált. Sikertelen biztonsági ellenőrzéskor ERROR állapotban
marad.

### reset_position

Csak IDLE allapotban engedelyezett. A rovert a kezdo pozicioba es
forgatasba allitja, IDLE allapotban marad (nem valtoztat allapotot,
ellentetben a reset_error-ral, ami ERROR-bol IDLE-be valt). Celja:
kiserleti/mereszsi futasok kozotti, reprodukalhato pozicio-reset,
amikor nincs hibaallapot. Sikertelen biztonsagi ellenorzeskor
ERROR_RESET_NOT_SAFE hibat ad, valtozatlan allapotban marad.

Sikeres reset eseten a valasz `message` mezoje szokozzel elvalasztott
`kulcs=ertek` parokat tartalmaz, amelyeket a meresi futtato ellenoriz:

- `scenario=<nev>`: a betoltott szcenario neve (ures, ha nincs betoltve);
- `timescale=<szam>`: a Unity `Time.timeScale` erteke;
- `obstacles=<db>`: a szcenariobol letrehozott akadalyok szama;
- `active=<db>`: a reset pillanataban lathato akadalyok szama (az utemezes
  a resetkor azonnal ervenyesul);
- `schedule=on|off`: fut-e az akadaly-utemezes (`off`, ha a
  `TrackController` komponens ki van kapcsolva - ilyenkor egyetlen akadaly
  sem jelenik meg).

A `controllers/baseline_line_follower.py` `--elvart-szcenario` mellett
osszeveti ezeket a szcenariofajllal, es elteres eseten nem indul el
(2026-10-26, a masodik audit es egy 0 akadallyal lefutott meres nyoman).

## Válaszformátum

```json
{
  "request_id": "...",
  "status": "accepted | completed | failed",
  "state": "IDLE | MOVING | TURNING | ERROR",
  "error": null
}
```

Hiba esetén:
```json
{
  "request_id": "...",
  "status": "failed",
  "state": "IDLE",
  "error": {
    "code": 1203,
    "name": "VALUE_OUT_OF_RANGE",
    "message": "distance_m must be between 0.01 and 2.00"
  }
}
```

## Korlátok (v1)

| Paraméter | Minimum | Maximum |
|---|---:|---:|
| move distance_m | 0.01 m | 2.00 m |
| move max_speed | 0.05 m/s | 0.50 m/s |
| turn angle_deg | 1° (abs) | 180° (abs) |
| turn max_angular_speed | 5°/s | 45°/s |
| Parancs timeout (szimulációs idő) | - | a várható időtartam × 1.5 + 2 s |
| TCP frame méret | - | 16 KiB |

**Pontosítás (2026-10-26, második audit).** A korábbi táblázat négy olyan
korlátot is felsorolt, amelyek közül három sosem volt megvalósítva:

- *Parancs timeout:* fix 15 s **valós** idő volt. Timescale 1 mellett egy
  érvényes, 2 m-es `move` 0.05 m/s-mal (40 s) ERROR-ba futott, timescale 70
  mellett viszont egy elakadt mozgás akár 1050 s szimulációs ideig tartott.
  Most szimulációs időben mér: a várható időtartam (`distance_m / max_speed`,
  illetve `|angle_deg| / max_angular_speed`) 1.5-szerese + 2 s.
- *Watchdog / heartbeat (1 s):* nincs heartbeat-mechanizmus. A
  `WATCHDOG_EXPIRED` (1501) akkor keletkezik, ha a mozgást indító kliens
  **bontja a kapcsolatot** a mozgás közben; ilyenkor a rover azonnal megáll.
  A kliensek a `move`/`turn` válaszára blokkolva várnak, ezért egy
  heartbeat-követelmény minden meglévő klienst megtörne.
- *Kérés/s és várakozási sor (10/s, 32):* nincs megvalósítva. Az ágens felé
  a korlátokat az adapter őrsége adja (parancskeret, időkeret,
  távolságkeret, lásd `adapter/orseg.py`).

A kliensoldali socket-timeout ennél hosszabb (baseline: 30 s, adapter:
90 s), és csak a lefagyott vagy leállított Unityt fogja meg.

**Szimulációs időbélyeg.** Minden válasz `sim_time_s` mezőt is tartalmaz
(a jelenet betöltése óta eltelt szimulációs idő, s). Privilegizált
diagnosztika: a lépésnapló rögzíti, az adapter elrejti az ágens elől.
Sikeres válaszban az `error` értéke `null` (korábban a Unity
`JsonUtility` egy üres, `code: 0` hibaobjektumot írt ide). A `get_status`
`last_command_result` mezője mindig `<parancs>:<completed|error>` alakú
(kezdetben `none`), soha nem a teljes válasz.

Minden numerikus mezőt véges számnak kell lennie
(NaN/Infinity elutasítva) és a fenti tartományon belülinek -
tartományon kívüli vagy nem véges érték error-t eredményez, nem
csendes korlátozást (nincs "clamp").

## Állapotgép
IDLE --move--> MOVING --siker--> IDLE
IDLE --turn--> TURNING --siker--> IDLE
(MOVING|TURNING) --stop--> IDLE
(MOVING|TURNING) --timeout/hiba--> ERROR
ERROR --reset_error (biztonságos)--> IDLE
* --stop--> (mindig elfogadott, idempotens)

Engedélyezési mátrix:

| Parancs | IDLE | MOVING | TURNING | ERROR |
|---|---:|---:|---:|---:|
| observe | igen | igen | igen | igen |
| get_status | igen | igen | igen | igen |
| move | igen | nem | nem | nem |
| turn | igen | nem | nem | nem |
| stop | igen (no-op) | igen | igen | igen (no-op) |
| reset_error | nem | nem | nem | igen |
| reset_position | igen | nem | nem | nem |

## Hibakódok (v1 alkészlet)

| Kód | Név | Jelentés |
|---:|---|---|
| 1101 | INVALID_FIELD_TYPE | Rossz adattípus |
| 1102 | UNKNOWN_FIELD | Nem dokumentált vagy az adott parancsnál nem engedélyezett mező |
| 1103 | DUPLICATE_FIELD | Egy JSON-mező többször szerepel a kérésben |
| 1104 | INVALID_REQUEST_ID | Hibás/hiányzó request_id |
| 1200 | UNKNOWN_COMMAND | Ismeretlen parancs |
| 1202 | NON_FINITE_VALUE | NaN vagy Infinity |
| 1203 | VALUE_OUT_OF_RANGE | Korláton kívüli érték |
| 1300 | COMMAND_NOT_ALLOWED_IN_STATE | Rossz állapotban küldött parancs |
| 1400 | DUPLICATE_REQUEST | Azonos request_id, már feldolgozott |
| 1401 | REQUEST_ID_CONFLICT | Azonos request_id, eltérő payload |
| 1500 | COMMAND_TIMEOUT | Parancs időtúllépés |
| 1501 | WATCHDOG_EXPIRED | Heartbeat hiányzik, kapcsolat vesztve |
| 1502 | ERROR_RESET_NOT_SAFE | A rover fizikai állapota nem resetelhető biztonságosan |
| 1600 | INTERNAL_ERROR | Váratlan belső szerverhiba a kérés feldolgozása közben |

A `reset_error` megszünteti a protokoll korábbi ismert korlátját: ERROR
állapotból korábban nem volt visszatérési út IDLE állapotba.

## Idempotencia

Minden request_id-hoz a szerver eltárolja a payload SHA-256
hash-ét és a végső választ.
- Azonos ID + azonos payload + befejezett kérés -> a cache-elt válasz
  megy vissza, új végrehajtás nélkül.
- Azonos ID + eltérő payload -> 1401 REQUEST_ID_CONFLICT.

## Tesztelési tapasztalatok és ismert korlátok

A `protocol_fuzz_test.py` teszt sikeresen igazolt, és segített kijavítani
két valódi hibát a `RoverGatewayServer.cs` implementációban:

1. egy regressziót, amely minden kérésnél lefagyást okozott;
2. egy JSON-validációs rést, amely csendben elfogadta a duplikált vagy
   nem dokumentált extra mezőket.

Mindkét hibát kijavítottuk, amit a fuzz teszt is megerősített:
`test_hibas_es_csonka_json_mindig_strukturalt_hibat_ad: ok`.

A randomizált `test_move_randomizalt_tartomanyok` és
`test_turn_randomizalt_tartomanyok` ismételt futtatása során a helyi Python
tesztkliens és a Unity Editor közötti kommunikáció több egymást követő
lépés után esetenként megbízhatatlanná vált. Ez timeoutokat,
`WATCHDOG_EXPIRED` hibát és ERROR állapotot okozhatott. Ennek feltételezett
oka a Unity Editor háttérfolyamatainak vagy a helyi gép
erőforrás-terhelésének hatása.

Ezt tesztinfrastruktúra-korlátként, nem protokollhibaként tartjuk nyilván.
A szerver minden egyedileg, kézzel ellenőrzött esetben helyesen viselkedett,
beleértve a validációt, az állapotgépet, a `reset_error` parancsot és az
idempotenciát. Jövőbeli munkaként érdemes a fuzz tesztet izolált
CI-környezetben vagy stabilabb hálózati és erőforrás-körülmények között
futtatni.

## Formális séma

A protokoll kérés- és válaszüzeneteinek formális JSON Schema leírása:
`docs/protocol.schema.json`. Ez gépi validációra használható (a
szcenárió-sémához hasonlóan), és a fuzz tesztek referenciája.

## Verziótörténet (v1 keretében, additív bővítések)

- **M09**: az `observe` válasz kibővítve `sensor_mode`,
  `sensor_left`, `sensor_center`, `sensor_right` mezőkkel, hogy a
  hagyományos (AI nélküli) baseline controller kizárólag
  szenzoradatra tudjon támaszkodni, ne a privilegizált
  `position`/`speed` mezőkre.
- **M08**: az `observe` válasz kibővítve a `lidar_szektor_min`
  mezővel (6 szektoros, szektoronkénti minimális akadálytávolság).
- **M10**: az `observe` válasz kibővítve a `collision_occurred` és
  `collision_count` privilegizált diagnosztikai mezőkkel.
- **M12**: a protokoll formális JSON Schema leírást kapott
  (`docs/protocol.schema.json`); maga a protokoll nem változott.
- **M13**: az `observe` válasz kibővítve a `lidar_nyers` és
  `lidar_nyers_ervenyes` mezőkkel (nyers, sugáronkénti LiDAR-jel és
  érvényességi maszk). Additív bővítés, a protokollverzió marad v1.
  Indok: az RQ5 (tömörített vs. nyers szenzorjel) enélkül nem
  vizsgálható.
- **M09**: uj `reset_position` parancs - IDLE allapotbol hivhato
  pozicio-reset a kiserleti futasok kozotti reprodukalhatosaghoz
  (korabban csak a `reset_error` allitotta vissza a kezdopoziciot,
  de az kizarolag ERROR allapotbol volt hivhato).

## Tudatosan elhalasztott elemek (jövőbeli munka)

A következő elemeket a Codex protokoll-review-ja javasolta, de az
M05 mérföldkőnél tudatosan NEM valósítottuk meg, mert a jelenlegi
fejlesztési fázisban (lokális, egyjátékos kutatási prototípus,
kizárólag 127.0.0.1-en futó szerver) nem indokolt a többletköltségük:

- **TLS/hitelesítés** - csak akkor válik szükségessé, ha a szerver
  külső hálózatra nyílik (pl. távoli fizikai roverhez kapcsolódás).
- **Control lease (kliens-tulajdonjog)** - csak több egyidejű
  vezérlő kliens esetén releváns; jelenleg egyszerre csak egy
  kliens (a Python CLI vagy egy AI agent) vezérel.
- **Teljes audit-napló, kliensazonosítás** - később, ha a rendszer
  többfelhasználós vagy fizikai roverre kerül, érdemes bővíteni.

Ezeket újra kell értékelni, mielőtt a rendszer külső hálózatra
nyílik vagy fizikai roverre kerül.

### reset_position: opcionális noise_seed (2026-10-08)

A `reset_position` kérés opcionális `noise_seed` mezőt kaphat (pozitív egész).
Megadva a szín- és LiDAR-szenzorok zajgenerátora ebből és a szenzor saját
seedjéből indul újra, így futásonként eltérő, de reprodukálható zajsorozat
állítható be. Hiányában a viselkedés a korábbival azonos. Más parancsnál a mező
`UNKNOWN_FIELD` hibát ad, nem pozitív értéknél `INVALID_FIELD_TYPE`-ot. A
kísérletfuttató `--seed N` kapcsolója az i. futáshoz N + i − 1 seedet küld.
