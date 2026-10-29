# Unity gateway CLI kliens

A `client.py` interaktív, kézi tesztelésre szánt kliens a Unityben futó
`RoverGatewayServer` komponenshez. A v1 protokollt beszéli
(`docs/protocol.md`): TCP-kapcsolaton minden üzenet egy 4 bájtos,
big-endian előjel nélküli hosszprefix és utána a JSON (UTF-8) tartalom.
A keret legfeljebb 16 KiB.

> Korábbi változatában (M03) ez a leírás newline-delimited JSON-t és egy
> gömb mozgatását írta le. A protokoll azóta hosszprefixes keretezésre
> váltott, és a rover kapta meg a `turn`, `get_status`, `reset_error` és
> `reset_position` parancsokat; a leírás 2026-10-26-án frissült a kódhoz.

## Követelmények

- Python 3.9 vagy újabb, csak a standard könyvtár
- A Unity jelenetben (TrackScene) Play módban aktív `RoverGatewayServer`
- Alapértelmezett cím: `127.0.0.1:8765`

## Futtatás

A repository gyökérkönyvtárából:

```bash
python3 gateway/client.py
python3 gateway/client.py --host 127.0.0.1 --port 8765
```

## Parancsok

| Parancs | Leírás |
| --- | --- |
| `observe` | Szenzorok (három vonalszenzor, LiDAR-szektorok és nyers LiDAR), valamint a privilegizált diagnosztika (pozíció, sebesség, ütközés). |
| `get_status` | A rover állapota (IDLE / MOVING / TURNING / ERROR) és az utolsó parancs eredménye. |
| `move <distance_m> <max_speed>` | Előre mozgás; `distance_m` 0.01–2.00 m, `max_speed` 0.05–0.50 m/s. |
| `turn <angle_deg> <max_angular_speed>` | Fordulás; `angle_deg` abszolút értéke 1–180°, `max_angular_speed` 5–45 °/s. |
| `stop` | Azonnali megállás; minden állapotban elfogadott. |
| `reset_error` | ERROR állapotból vissza IDLE-be (csak ERROR-ban). |
| `reset_position` | A rover vissza a kezdőpozícióba (csak IDLE-ben). A kliens nem küld `noise_seed`-et; azt a mérési futtató használja. |
| `quit` | Kilépés. |

A kliens a tartományokat már küldés előtt ellenőrzi. A `move` és a `turn`
válasza a mozgás végén érkezik; 15 s után a szerver parancs-timeouttal
ERROR állapotba vált.

Például:

```text
gateway> observe
gateway> turn 15 20
gateway> move 0.5 0.2
gateway> get_status
gateway> quit
```

Minden kérés UUID-alapú `request_id` mezőt kap; a kliens figyelmeztet, ha
a válaszban más azonosító szerepel.

## Naplózás

A küldött és fogadott üzenetek időbélyeggel, soronként külön
JSON-objektumként a `gateway/logs/session.jsonl` fájlba kerülnek (az első
futáskor jön létre, nem verziókövetett).
