# M12 biztonsági átvizsgálás (security review)

A kiírás M12 kötelező AI-használati pontja szerint az API-t egy **külön
AI-munkamenetben** vizsgáltuk át: egy önálló Claude Code session elolvasta az
`adapter/` három moduljának forrását (a rovert vezérlő munkamenettől
függetlenül), és felsorolta, mivel tudna egy hibás vagy rosszindulatú agent
kárt okozni, hol kerülhetők meg a korlátok, és mi szivároghat ki.

Nyers kimenet: `docs/m12/security-review-raw.txt`
Vak API-használhatósági teszt (külön munkamenet): `docs/m12/agent-session-raw.txt`

## Találatok és kezelésük

| # | Találat | Súlyosság | Kezelés | Regressziós teszt |
|---|---|---|---|---|
| 1 | Nincs hibakezelés a backend I/O körül: a `UnityTcpBackend` nyers kivételei (socket timeout, `ConnectionError`, JSON-hiba) kiszűretlenül jutnának az agenthez, és hiba esetén nem megy ki `stop` (fail-open) | magas | **Javítva**: minden backend-hívás `_backend_hivas()`-on át megy; bármilyen kivétel egységes `ADAPTER_BACKEND_ERROR` választ ad és lezárja a munkamenetet (fail-safe). A kivétel típusa/szövege sosem szivárog ki — abból a backend típusa is kikövetkeztethető lenne | `test_1_backend_kivetel_nem_szivarog_ki`, `test_1b_nem_dict_valasz_is_kezelve` |
| 2 | Az ütközési telemetria teljesen rejtve volt, így az agent nem tudta meg, hogy nekiment valaminek, és ismételhette ugyanazt a parancsot | magas | **Javítva, tudatos eltéréssel az eredeti tervtől**: az `observe` válaszába bekerült a `collision_detected` bool (volt-e ütközés az előző `observe` óta). Indok: bumper/IMU egy valódi roveren is lenne, tehát ez nem privilegizált szimulátor-információ; enélkül az M13-as agent-kísérlet mesterséges hendikeppel mérne. A kumulatív `collision_count`, a `position` és a `speed` **továbbra is rejtve marad** | `test_2_utkozesjelzes_lathato_de_a_szamlalo_nem` |
| 3 | `stop()` lezárt munkamenetben is a már bezárt backendre próbált írni — reprodukálható összeomlás valódi hardveren, amit a mock elfedett | közepes | **Javítva**: lezárt munkamenetben a `stop()` nem nyúl a backendhez, hanem nyugtázza, hogy a rover a lezáráskor kiküldött `stop` miatt már áll. *Pontosítás (2026-10-26, második audit):* nyugtát csak akkor ad, ha a lezáráskori `stop`-ot a rover visszaigazolta; backend-hiba miatti lezárás után `ADAPTER_STOP_UNCONFIRMED` hibát ad, mert ott stop nem ment ki | `test_3_stop_lezart_sessionben_nem_hasznalja_a_backendet` |
| 4 | Az érvénytelen paraméterű hívások nem fogyasztottak a parancskeretből, így egy hibás agent korlátlanul próbálkozhatott | közepes | **Javítva**: az elutasított hívás is növeli a felhasznált parancsszámot | `test_4_elutasitott_hivas_is_fogyasztja_a_keretet` |
| 5 | A `move` leírása félrevezető volt: a `completed` státusz nem jelenti, hogy a rover a teljes távolságot megtette (akadálynak ütközve hamarabb megáll) | közepes | **Javítva dokumentációban**: az eszközleírás most kimondja ezt, és a `collision_detected`-re irányítja az agentet | — |
| 6 | Az időkorlát csak parancsok **között** ellenőrződik; egy hosszú, blokkoló `move` a limit fölé viheti a tényleges munkamenet-időt | alacsony | **Nyitva (M13+)**: kemény wall-clock plafonhoz watchdog-szál kellene | — |
| 7 | A megengedett parancsok szűrése csupasz `assert`-tel történt, amit a `-O` kapcsoló kikapcsol | alacsony | **Javítva**: explicit `raise ValueError` | `test_7_tiltott_parancs_raise_nem_assert` |
| 8 | A backend típusa **válaszidőből** kikövetkeztethető: a mock azonnal válaszol, a Unity a mozgás idejéig blokkol | megfigyelés | **Nyitva (M13+)**: elvi korlát; ha szigorúan kell, a mock mesterséges késleltetéssel igazítható. A tartalmi rejtés (mezőszűrés, egységes hibaüzenetek) ettől függetlenül teljes | — |

Ezen felül a vak API-használhatósági teszt (`docs/m12/agent-session-raw.txt`)
három dokumentációs hiányt tárt fel, amelyek szintén javítva lettek az
eszközleírásokban: a Lidar-szektorok szöggeometriája és a rover szélességéhez
igazított biztonsági küszöb, az `intensity` folytonos jelentése
vonalkövetéshez, valamint a `reset_position` munkamenet-keretre gyakorolt
hatása.

## Utólagos kiegészítés: a `reset_position` mint backend-jelzés

Egy külső átvizsgálás felvetette, hogy a `reset_position` eszköz maga is
szimulátor-specifikus: egy valódi rovert nem lehet teleportálni, tehát a
művelet puszta létezése elárulja, hogy szimuláció áll a backend mögött —
ugyanaz a 4. kérdés ("szivárog-e ki bármi, aminek rejtve kellene maradnia"),
amit a review az adatmezőkre vizsgált.

**Kezelés**: a `reset_position` kikerült az agent eszközkészletéből (az
MCP-szerver már csak öt eszközt tesz ki: `observe`, `move`, `turn`, `stop`,
`session_status`). Az `Orseg.reset_position()` metódus megmarad, de kizárólag
kísérletvezetői műveletként, a mérésindító szkript számára — így az agent
eszközei pontosan azok, amik egy valódi roveren is léteznének.

## Mit nem talált a review

A 11 eredeti unit teszt mindegyike zölden futott a fenti hibák mellett is:
egyik sem szimulált hálózati hibát, lezárt backendet vagy ütközés utáni
állapotot. A javításokhoz 7 új regressziós teszt készült (összesen 18).
