# Vonalérzékelő szenzorok és kalibráció (M07)

## Szenzormodell

A `ColorSensor.cs` egy egyszerűsített, lefelé néző optikai szenzort
szimulál (hasonlóan egy valódi vonalkövető robot IR/fényvisszaverő
szenzoraihoz):

1. Minden `FixedUpdate`-ben egy raycast indul lefelé
   (`Vector3.down`), a `Raycast Magassag` mezőben megadott
   magasságból, `Raycast Tavolsag` hosszban.
2. A találati pontban a `TrackController` geometriai lekérdezése
   (`TavolsagAKozepvonaltol`) megadja, milyen messze van a pont a
   pálya középvonalától.
3. Ebből a `VonalFelSzelessegeM` alapján egy folytonos, 0–1 közötti
   nyers intenzitás (`I`) számolódik: 1.0 a vonal közepén, 0.0 a
   vonalon kívül, közte lineáris átmenet a vonal szélén.
4. A nyers intenzitásra Gauss-eloszlású zaj kerül (Box-Muller
   transzformáció, seedelt `System.Random`-mal — lásd
   [Zaj-reprodukálhatóság](#zaj-reprodukálhatóság)).
5. A zajos intenzitást a `Kuszob` mezővel összehasonlítva születik
   a bináris kimenet: `WHITE` / `not_white`.

Opcionálisan (`Keses Fixed Update` és `Meres Kimaradas Eselye`
mezők) a szenzor mesterséges méréskésleltetést és véletlenszerű
méréskimaradást is szimulálhat, egy valódi szenzor korlátainak
közelítésére.

## Kalibráció

A `0.5`-ös alapértelmezett küszöböt **mérés**, nem találgatás
igazolja. Öt, a pálya egyenes szakaszán elhelyezkedő ismert
pozícióban (X=4.00 / 4.09 / 4.14 / 4.19 / 4.50, Z=0) rögzítettük a
szenzor kimenetét:

| # | Pozíció (X) | Vizsgált eset                      | Mért `I` | Várt állapot |
|---|-------------|-------------------------------------|----------|--------------|
| 1 | 4.00        | vonal közepe                        | ≈1.0     | WHITE        |
| 2 | 4.09        | vonal széle, még belül              | ≈1.0     | WHITE        |
| 3 | 4.14        | átmeneti zóna közepe                | ≈0.5     | határeset    |
| 4 | 4.19        | lecsengés külső határa              | ≈0.0     | not_white    |
| 5 | 4.50        | egyértelműen kívül                  | ≈0.0     | not_white    |

A mérés megerősítette, hogy a `0.5`-ös küszöb helyesen választja
el a vonalon lévő és a vonalon kívüli eseteket — ez volt az M07
kötelező AI-használati elemének (Claude segítségével végzett
kalibrációs elemzés) tárgya.

## Zaj-reprodukálhatóság

Minden `ColorSensor` komponens saját `Zaj Seed` mezővel
rendelkezik. Azonos seed mellett a szenzor zaja mindig ugyanazt a
sorozatot adja — ez teszi lehetővé, hogy egy adott futás
determinisztikusan reprodukálható legyen (hasonlóan a
`docs/scenario-schema.md`-ban dokumentált szcenárió-seedekhez).

**Futásonkénti zaj-seed (M10, 2026-10).** A fenti, Inspectorban megadott
seed önmagában minden futásban ugyanazt a zajsorozatot adná. A
`reset_position` parancs opcionális `noise_seed` mezőjével (lásd
`docs/protocol.md`) a zaj futásonként eltér, de reprodukálható marad: a
szenzor ilyenkor a `zajSeed * 31 + noise_seed` értékkel indítja újra a
generátort (`ColorSensor.ZajUjrainditasa`). `noise_seed` nélkül a
viselkedés a régi. A mérések a futtató `--seed N` kapcsolójával az i.
futásban N + i − 1 értéket küldik, és a metaadatban rögzítik.

### Aktuális paraméterek

| Paraméter | Érték | Megjegyzés |
|---|---|---|
| Zaj szórása (`zajSzoras`) | 0.05 | Gauss, az intenzitásra adva, utána 0–1-re vágva |
| Küszöb (`kuszob`) | 0.5 | lásd Kalibráció |
| Lecsengési sáv a vonal szélén | 0.1 m | a kódban rögzített (`FolytonosIntenzitas`) |
| Késleltetés (`kesesFixedUpdateKeretekben`) | 0 | kikapcsolva |
| Mérés-kimaradás (`meresKimaradasValoszinusege`) | 0 | kikapcsolva |

A háromszenzoros elrendezésben mindhárom szenzor **eltérő** seedet
kapott (12345 / 12346 / 12347), hogy a zajuk ne legyen egymással
korrelált — ez reálisabb, mint ha mindhárom szenzor azonos zajmintát
mutatna.

## Egy- és háromszenzoros mód (`SensorArray.cs`)

A `SensorArray` komponens (a `RoverChassis`-on) fogja össze a bal
(`SensorLeft`), közép (`SensorCenter`) és jobb (`SensorRight`)
szenzort, és egy `Harom Szenzoros Mod` kapcsolóval vezérli, melyik
van aktívan:

- **Kikapcsolva (alapértelmezett):** csak a középső szenzor aktív
  (`GameObject.SetActive`) — ez az egyszenzoros mód.
- **Bekapcsolva:** mindhárom szenzor aktív.

A mód Inspectorban (Editor és Play módban egyaránt, az
`OnValidate` hívásnak köszönhetően) és kódból is átkapcsolható
(`HaromSzenzorosModBeallitasa(bool)`). A kikapcsolt szenzorok
GameObject-je ténylegesen inaktív, tehát nem futtat felesleges
raycastet/zajszámítást, és a zaj-seedjük sem "csúszik el"
feleslegesen.

### Szenzorpozíciók

| Szenzor      | Helyi X (RoverChassis-hoz képest) | Zaj Seed |
|--------------|-----------------------------------|----------|
| SensorCenter | 0                                 | 12345    |
| SensorLeft   | -0.3                               | 12346    |
| SensorRight  | 0.3                                | 12347    |

A középső szenzor eredetileg (M07) ≈ -0.115-ös X-eltolással került a
jelenetbe; később a rover tengelyére került (X = 0), a táblázat a
`unity/Assets/Prefabs/RoverChassis.prefab` jelenlegi értékeit mutatja.

Mindhárom szenzor Z-eltolása megegyezik (≈0.264), vagyis a rover
elülső éle előtt helyezkednek el — ez stabilabb, "előretekintő"
vonalkövetést tesz lehetővé, mint a rover geometriai közepére
pozicionált szenzor.

### Kanyar-teszt

A háromszenzoros mód differenciált működését a pálya kanyarjában
igazoltuk: a rovert a kanyarba állítva és elforgatva a három
szenzor egyidejűleg eltérő kimenetet adott:
I=0.00 not_white (bal szenzor, teljesen kívül)
I=0.12 not_white (közép szenzor, átmeneti zóna szélén)
I=1.00 WHITE (jobb szenzor, a vonalon)

Ez igazolja, hogy a három szenzor ténylegesen független,
helyzetfüggő méréseket ad — ez a vonalkövető algoritmus (jövőbeli
mérföldkő) számára szükséges alapfeltétel.

## Ismert korlát: anyag-instanciálás Edit módban

A `TrackController.cs` `[ExecuteAlways]` attribútumot kapott, hogy
a pálya Play mód nélkül is látszódjon a Scene nézetben (korábban
csak a `LineRenderer` futásidejű felépítése miatt csak Play módban
volt látható). Emiatt előkerült egy már meglévő hiba: a script két
helyen (`vonalRenderer.material = ...` és
`talajRenderer.material`-t olvasva) a `.material` property-t
használta, ami Unity-ben minden hozzáféréskor egy új anyag-másolatot
hoz létre — Edit módban ismételt újrafutásnál ez anyag-szivárgáshoz
("Instantiating material... This will leak materials into the
scene") vezetett volna. Mindkét helyen `.sharedMaterial`-ra
javítottuk, ami nem másol, csak az eredeti, megosztott anyagot
állítja be.