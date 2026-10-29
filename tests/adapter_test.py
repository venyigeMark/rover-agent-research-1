"""M12 adapter-tesztek mock backenddel (nem igenyelnek Unity-t)."""

from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapter.backend import (  # noqa: E402
    MockAkadaly,
    MockBackend,
    UnityTcpBackend,
    tavolsag_a_kozepvonaltol,
)
from adapter.orseg import (  # noqa: E402
    ELREJTETT_MEZOK,
    UTKOZES_MEZO,
    Orseg,
    SessionKorlatok,
)


class MockBackendTeszt(unittest.TestCase):
    def test_kezdo_pozicio_a_vonalon(self):
        b = MockBackend()
        obs = b.kuld({"command": "observe"})
        self.assertEqual(obs["status"], "completed")
        self.assertTrue(obs["sensor_center"]["white"])
        self.assertEqual(len(obs["lidar_szektor_min"]), 6)

    def test_lidar_nyers_es_maszk_konzisztens_a_szektorokkal(self):
        # M13/RQ5: a nyers jel es a tomoritett szektorok ugyanarra a meresre
        # epulnek - a szektor erteke a hozza tartozo sugarak minimuma.
        b = MockBackend()
        obs = b.kuld({"command": "observe"})
        nyers = obs["lidar_nyers"]
        maszk = obs["lidar_nyers_ervenyes"]
        szektorok = obs["lidar_szektor_min"]
        self.assertEqual(len(nyers), 36)
        self.assertEqual(len(maszk), len(nyers))
        sugar_per_szektor = len(nyers) // len(szektorok)
        for i, szektor_ertek in enumerate(szektorok):
            resz = nyers[i * sugar_per_szektor : (i + 1) * sugar_per_szektor]
            self.assertAlmostEqual(szektor_ertek, min(resz), places=6)
        # Regresszio: a mock eloszor minden sugarra True-t adott, ami pont a
        # forditottja a Unity viselkedesenek (ott a nem talalo sugar false).
        # A 19 meglevo teszt egyike sem fogta meg - eles Unity-ellenorzes
        # derult ki. A maszk true = az adott sugar talalt valamit.
        for ny, m in zip(nyers, maszk):
            self.assertEqual(m, ny < 10.0)

    def test_get_status_allapotot_ad_protocol_version_nelkul(self):
        # A kiiras 2.1 pontja nevesiti a get_status-t az agent-eszkozok kozott,
        # de az M12-es adapterbol hianyzott: egy agent nem vette volna eszre,
        # ha a rover ERROR allapotba kerul.
        o = Orseg(MockBackend())
        v = o.get_status()
        self.assertEqual(v["status"], "completed")
        self.assertIn("state", v)
        self.assertNotIn("protocol_version", v)

    def test_get_status_nem_enged_at_beagyazott_valaszt(self):
        # Regresszio egy sajat, 3eb9c85-ben bevitt hibara: a Unity szerver a
        # teljes elozo valasz JSON-jat tarolta a last_command_result mezoben,
        # igy egy observe utani get_status visszaadta a position, speed es
        # collision_count mezoket. Az _szur ezt nem fogta meg, mert csak felso
        # szintu kulcsokat tavolit el, a szivargas pedig egy sztringbe volt
        # agyazva. A MockBackend ilyen mezot nem ad vissza, ezert egyik meglevo
        # teszt sem lathatta - ez a stub kifejezetten a szivargast modellezi.
        class SzivargoBackend:
            def kuld(self, parancs):
                return {
                    "status": "completed",
                    "state": "IDLE",
                    "protocol_version": 1,
                    "last_command_result": (
                        '{"status":"completed","position":{"x":2.0,"y":0.25,'
                        '"z":9.49},"speed":0.0,"collision_count":7}'
                    ),
                }

        v = Orseg(SzivargoBackend()).get_status()
        kiirva = json.dumps(v)
        self.assertNotIn("last_command_result", v)
        self.assertNotIn("position", kiirva)
        self.assertNotIn("speed", kiirva)
        self.assertNotIn("collision_count", kiirva)

    def test_geometria_fantom_iv_nelkul(self):
        # (0, 2): a javitas elott 0 lett volna, helyesen 4 m
        self.assertAlmostEqual(tavolsag_a_kozepvonaltol(0.0, 2.0), 4.0, places=6)
        self.assertAlmostEqual(tavolsag_a_kozepvonaltol(4.0, 0.0), 0.0, places=6)
        self.assertAlmostEqual(tavolsag_a_kozepvonaltol(0.0, 10.0), 0.0, places=6)

    def test_move_halad_es_v1_hibakodok(self):
        b = MockBackend()
        v = b.kuld({"command": "move", "distance_m": 0.5, "max_speed": 0.2})
        self.assertEqual(v["status"], "completed")
        self.assertAlmostEqual(b.z, 0.5, places=6)
        v = b.kuld({"command": "move", "distance_m": 5.0, "max_speed": 0.2})
        self.assertEqual(v["error"]["code"], 1203)
        v = b.kuld({"command": "move", "distance_m": "x", "max_speed": 0.2})
        self.assertEqual(v["error"]["code"], 1101)
        v = b.kuld({"command": "fly"})
        self.assertEqual(v["error"]["code"], 1200)

    def test_akadaly_utkozes_es_lidar(self):
        b = MockBackend(akadalyok=[MockAkadaly(x=4.0, z=1.0)])
        obs = b.kuld({"command": "observe"})
        self.assertLess(min(obs["lidar_szektor_min"]), 1.0)
        b.kuld({"command": "move", "distance_m": 1.0, "max_speed": 0.2})
        self.assertEqual(b.utkozesek, 1)
        self.assertLess(b.z, 0.7)


class OrsegTeszt(unittest.TestCase):
    def setUp(self):
        self.backend = MockBackend()
        self.orseg = Orseg(self.backend, SessionKorlatok(max_parancs=5, max_ossz_tavolsag_m=1.5))

    def test_ervenytelen_hivas_nem_jut_a_backendhez(self):
        elotte = len(self.backend.parancsnaplo)
        rosszak = [
            ("x", 0.2),
            (5.0, 0.2),
            (0.5, 9.9),
            (float("nan"), 0.2),
            (True, 0.2),
            (-0.1, 0.2),
        ]
        for rossz in rosszak:
            v = self.orseg.move(*rossz)
            self.assertEqual(v["status"], "rejected", rossz)
            self.assertTrue(v["error"]["code"].startswith("ADAPTER_"), rossz)
        self.assertEqual(
            len(self.backend.parancsnaplo), elotte, "a backend nem kaphatott parancsot"
        )
        self.assertEqual(self.orseg.session.elutasitott, 6)

    def test_turn_validacio(self):
        self.assertEqual(self.orseg.turn(0.5)["status"], "rejected")
        self.assertEqual(self.orseg.turn(200)["status"], "rejected")
        self.assertEqual(self.orseg.turn(30, 100)["status"], "rejected")
        self.assertEqual(self.orseg.turn(-30)["status"], "completed")

    def test_backend_rejtes(self):
        obs = self.orseg.observe()
        for mezo in ELREJTETT_MEZOK:
            self.assertNotIn(mezo, obs)
        self.assertNotIn("request_id", obs)
        self.assertIn("sensor_center", obs)
        self.assertIn("lidar_szektor_min", obs)
        # M13/RQ5: a nyers LiDAR-jel nem privilegizalt szimulator-adat,
        # az agensnek latnia kell - kulonben az RQ5 nem vizsgalhato.
        self.assertIn("lidar_nyers", obs)
        self.assertIn("lidar_nyers_ervenyes", obs)
        self.assertNotIn("lidar_nyers", ELREJTETT_MEZOK)
        self.assertNotIn("lidar_nyers_ervenyes", ELREJTETT_MEZOK)

    def test_parancslimit_automatikus_stop(self):
        for _ in range(5):
            self.assertEqual(self.orseg.observe()["status"], "completed")
        v = self.orseg.observe()
        self.assertEqual(v["error"]["code"], "ADAPTER_SESSION_CLOSED")
        self.assertTrue(self.orseg.session.lezarva)
        self.assertEqual(
            self.backend.parancsnaplo[-1]["command"], "stop", "lezaraskor stop-ot kell kuldeni"
        )
        # lezart sessionben minden mas elutasitva, a stop viszont atmegy
        self.assertEqual(self.orseg.move(0.1)["error"]["code"], "ADAPTER_SESSION_CLOSED")
        self.assertEqual(self.orseg.stop()["status"], "completed")

    def test_tavolsagkeret(self):
        self.assertEqual(self.orseg.move(1.0)["status"], "completed")
        v = self.orseg.move(0.6)
        self.assertEqual(v["error"]["code"], "ADAPTER_DISTANCE_BUDGET")
        self.assertEqual(self.orseg.move(0.5)["status"], "completed")
        self.assertAlmostEqual(self.orseg.session_status()["distance_used_m"], 1.5)

    def test_idolimit(self):
        import time

        o = Orseg(MockBackend(), SessionKorlatok(max_idotartam_s=0.0))
        time.sleep(0.01)
        self.assertEqual(o.observe()["error"]["code"], "ADAPTER_SESSION_CLOSED")
        self.assertEqual(o.session_status()["closed_reason"], "time limit reached")

    def test_session_status_mezok(self):
        s = self.orseg.session_status()
        for k in (
            "commands_used",
            "commands_limit",
            "distance_used_m",
            "distance_limit_m",
            "closed",
        ):
            self.assertIn(k, s)


class HibasBackend:
    """Backend, ami a megadott hivasszam utan kivetelt dob (halozati hiba)."""

    def __init__(self, hibatol: int = 0, kivetel=None) -> None:
        self.hivasok = 0
        self.hibatol = hibatol
        self.kivetel = kivetel or ConnectionError("A kapcsolat varatlanul megszakadt.")
        self.lezarva = False

    def kuld(self, parancs):
        self.hivasok += 1
        if self.hivasok > self.hibatol:
            raise self.kivetel
        return {"status": "completed", "state": "IDLE"}

    def close(self) -> None:
        self.lezarva = True


class BiztonsagiJavitasokTeszt(unittest.TestCase):
    """A M12 security review talalatainak regresszios tesztjei."""

    def test_1_backend_kivetel_nem_szivarog_ki(self):
        backend = HibasBackend()
        orseg = Orseg(backend)
        valasz = orseg.observe()
        self.assertEqual(valasz["error"]["code"], "ADAPTER_BACKEND_ERROR")
        self.assertNotIn("ConnectionError", json.dumps(valasz))
        self.assertNotIn("megszakadt", json.dumps(valasz))
        self.assertTrue(orseg.session.lezarva, "backend-hiba eseten a session lezarul")
        self.assertTrue(backend.lezarva, "a backendet le kell zarni")

    def test_1b_nem_dict_valasz_is_kezelve(self):
        class RosszValaszBackend(HibasBackend):
            def kuld(self, parancs):
                return "nem dict"

        orseg = Orseg(RosszValaszBackend())
        self.assertEqual(orseg.observe()["error"]["code"], "ADAPTER_BACKEND_ERROR")

    def test_2_utkozesjelzes_lathato_de_a_szamlalo_nem(self):
        backend = MockBackend(akadalyok=[MockAkadaly(x=4.0, z=0.5)])
        orseg = Orseg(backend)
        elso = orseg.observe()
        self.assertFalse(elso[UTKOZES_MEZO], "meg nem volt utkozes")
        orseg.move(0.5)
        masodik = orseg.observe()
        self.assertTrue(masodik[UTKOZES_MEZO], "az utkozest jeleznie kell")
        for mezo in ELREJTETT_MEZOK:
            self.assertNotIn(mezo, masodik, f"{mezo} nem szivaroghat ki")
        harmadik = orseg.observe()
        self.assertFalse(harmadik[UTKOZES_MEZO], "a jelzes az observe utan nullazodik")

    def test_3_stop_lezart_sessionben_nem_hasznalja_a_backendet(self):
        backend = MockBackend()
        orseg = Orseg(backend, SessionKorlatok(max_parancs=1))
        orseg.observe()
        orseg.observe()
        self.assertTrue(orseg.session.lezarva)
        hivasok = len(backend.parancsnaplo)
        valasz = orseg.stop()
        self.assertEqual(valasz["status"], "completed")
        self.assertEqual(len(backend.parancsnaplo), hivasok, "lezart backendre nem kuldunk")

    def test_4_elutasitott_hivas_is_fogyasztja_a_keretet(self):
        orseg = Orseg(MockBackend(), SessionKorlatok(max_parancs=3))
        for _ in range(3):
            self.assertEqual(orseg.move(99.0)["status"], "rejected")
        self.assertEqual(orseg.session.parancsok, 3)
        self.assertEqual(orseg.observe()["error"]["code"], "ADAPTER_SESSION_CLOSED")

    def test_7_tiltott_parancs_raise_nem_assert(self):
        orseg = Orseg(MockBackend())
        with self.assertRaises(ValueError):
            orseg._vegrehajt({"command": "reset_error"})

    def test_lezaras_hibas_backenddel_sem_dob(self):
        class MindigHibas(HibasBackend):
            def close(self) -> None:
                raise OSError("close hiba")

        orseg = Orseg(MindigHibas())
        orseg.lezar("teszt")
        self.assertTrue(orseg.session.lezarva)


class SzimulaciosIdoRejtesTeszt(unittest.TestCase):
    def test_sim_time_nem_jut_el_az_agenshez(self):
        class IdosBackend(MockBackend):
            def kuld(self, parancs):
                valasz = super().kuld(parancs)
                valasz["sim_time_s"] = 12.5
                return valasz

        orseg = Orseg(IdosBackend())
        for valasz in (orseg.observe(), orseg.get_status(), orseg.move(0.1)):
            self.assertNotIn("sim_time_s", valasz)


class UtkozesResetTeszt(unittest.TestCase):
    """Audit: resetkor a rover nullazza a szamlalot; az adapter referenciaja nem maradhat a regin."""

    def test_reset_utan_az_elso_utkozes_is_latszik(self):
        backend = MockBackend(akadalyok=[MockAkadaly(x=4.0, z=0.5)])
        orseg = Orseg(backend)
        for _ in range(2):  # ket utkozes: a szamlalo 2
            orseg.move(0.5)
            orseg.observe()
        self.assertEqual(orseg.reset_position()["status"], "completed")
        self.assertEqual(backend.utkozesek, 0, "a mock is nullaz, mint a Unity")
        orseg.move(0.5)  # uj futas elso utkozese: a szamlalo 1 (< a regi 2)
        self.assertTrue(orseg.observe()[UTKOZES_MEZO])

    def test_szamlalo_csokkenese_kivulrol_resetelt_backendnel(self):
        backend = MockBackend(akadalyok=[MockAkadaly(x=4.0, z=0.5)])
        orseg = Orseg(backend)
        for _ in range(2):
            orseg.move(0.5)
            orseg.observe()
        backend.kuld({"command": "reset_position"})  # az adapter megkerulesevel
        orseg.move(0.5)
        self.assertTrue(orseg.observe()[UTKOZES_MEZO])


class StopNyugtaTeszt(unittest.TestCase):
    """Audit: backend-hiba miatti lezaras utan a stop nem adhat hamis nyugtat."""

    def test_backend_hiba_utan_a_stop_nem_completed(self):
        orseg = Orseg(HibasBackend())
        orseg.observe()
        self.assertTrue(orseg.session.lezarva)
        valasz = orseg.stop()
        self.assertEqual(valasz["status"], "rejected")
        self.assertEqual(valasz["error"]["code"], "ADAPTER_STOP_UNCONFIRMED")

    def test_lezaraskori_sikertelen_stop_sem_nyugtazott(self):
        orseg = Orseg(HibasBackend())
        orseg.lezar("teszt")
        self.assertFalse(orseg.session.stop_megerositve)
        self.assertEqual(orseg.stop()["error"]["code"], "ADAPTER_STOP_UNCONFIRMED")

    def test_sikeres_lezaras_utan_a_stop_nyugtazott(self):
        orseg = Orseg(MockBackend())
        orseg.lezar("teszt")
        self.assertTrue(orseg.session.stop_megerositve)
        self.assertEqual(orseg.stop()["status"], "completed")


class _TesztSzerver:
    """Egyetlen kapcsolatot kiszolgalo helyi TCP-szerver; a valaszt `valaszolo(keres)` adja.

    A valaszolo bytes-t ad vissza (a nyers, keretezett valaszt), vagy None-t, ha a
    szerver valasz nelkul bontja a kapcsolatot.
    """

    def __init__(self, valaszolo) -> None:
        self._szerver = socket.create_server(("127.0.0.1", 0))
        self.port = self._szerver.getsockname()[1]
        self._valaszolo = valaszolo
        self._szal = threading.Thread(target=self._fut, daemon=True)
        self._szal.start()

    def _fut(self) -> None:
        kapcsolat, _ = self._szerver.accept()
        with kapcsolat:
            while True:
                fej = kapcsolat.recv(4)
                if len(fej) < 4:
                    return
                hossz = int.from_bytes(fej, "big")
                adat = b""
                while len(adat) < hossz:
                    adat += kapcsolat.recv(hossz - len(adat))
                valasz = self._valaszolo(json.loads(adat.decode("utf-8")))
                if valasz is None:
                    return
                kapcsolat.sendall(valasz)

    def close(self) -> None:
        self._szerver.close()


def _keret(obj) -> bytes:
    payload = json.dumps(obj).encode("utf-8")
    return len(payload).to_bytes(4, "big") + payload


class UnityTcpBackendTeszt(unittest.TestCase):
    """A valodi TCP-backend keretezese es hibakezelese, Unity nelkul."""

    def _backend(self, valaszolo) -> UnityTcpBackend:
        szerver = _TesztSzerver(valaszolo)
        self.addCleanup(szerver.close)
        backend = UnityTcpBackend("127.0.0.1", szerver.port, timeout_s=2.0)
        self.addCleanup(backend.close)
        return backend

    def test_oda_vissza_keretezes_es_request_id(self):
        kapott = []

        def valaszolo(keres):
            kapott.append(keres)
            return _keret({"request_id": keres["request_id"], "status": "completed"})

        backend = self._backend(valaszolo)
        self.assertEqual(backend.kuld({"command": "observe"})["status"], "completed")
        self.assertEqual(kapott[0]["command"], "observe")
        self.assertEqual(len(kapott[0]["request_id"]), 36)

    def test_idegen_request_id_hiba(self):
        backend = self._backend(lambda k: _keret({"request_id": "masik", "status": "completed"}))
        with self.assertRaises(ConnectionError):
            backend.kuld({"command": "observe"})

    def test_tul_nagy_valaszkeret_hiba(self):
        backend = self._backend(lambda k: (10**6).to_bytes(4, "big"))
        with self.assertRaises(ConnectionError):
            backend.kuld({"command": "observe"})

    def test_megszakadt_kapcsolat_hiba(self):
        backend = self._backend(lambda k: None)
        with self.assertRaises(ConnectionError):
            backend.kuld({"command": "observe"})

    def test_orseg_a_tcp_hibat_egyseges_hibava_alakitja(self):
        backend = self._backend(lambda k: None)
        orseg = Orseg(backend)
        valasz = orseg.observe()
        self.assertEqual(valasz["error"]["code"], "ADAPTER_BACKEND_ERROR")
        self.assertEqual(orseg.stop()["error"]["code"], "ADAPTER_STOP_UNCONFIRMED")


if __name__ == "__main__":
    unittest.main()
