using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using UnityEngine;

[RequireComponent(typeof(Rigidbody))]
public class RoverGatewayServer : MonoBehaviour
{
    private const int ProtokollVerzio = 1;
    private const int MaximalisFrameMeret = 16 * 1024;
    // Parancs-timeout SZIMULACIOS idoben (2026-10-26). Korabban fix 15 s valos
    // ido volt: timescale 1 mellett egy ervenyes, 2 m-es move 0.05 m/s-mal (40 s)
    // ERROR-ba futott, timescale 70 mellett viszont egy elakadt mozgas 1050 s
    // szimulacios idot is futhatott. Most: a varhato idotartam 1.5-szorose + 2 s.
    private const float ParancsIdotullepesSzorzo = 1.5f;
    private const float ParancsIdotullepesTartalekS = 2f;

    private enum RoverAllapot
    {
        IDLE,
        MOVING,
        TURNING,
        ERROR
    }

    [SerializeField, Range(1, 65535)]
    private int port = 8765;

    [SerializeField, Min(256)]
    private int maximalisUzenethossz = MaximalisFrameMeret;

    private readonly ConcurrentQueue<FuggobenLevoKeres> keresek =
        new ConcurrentQueue<FuggobenLevoKeres>();

    private readonly ConcurrentQueue<string> naploUzenetek =
        new ConcurrentQueue<string>();

    private readonly ConcurrentQueue<Guid> bontottKapcsolatok =
        new ConcurrentQueue<Guid>();

    private readonly ConcurrentDictionary<Guid, byte> bontottKapcsolatAzonositok =
        new ConcurrentDictionary<Guid, byte>();

    private readonly Dictionary<string, IdempotenciaBejegyzes> idempotenciaTar =
        new Dictionary<string, IdempotenciaBejegyzes>();

    private readonly object kliensekZar = new object();
    private readonly List<TcpClient> aktivKliensek = new List<TcpClient>();

    private Rigidbody rigidBody;
    private TrackController trackController; // M10: akadaly-utemezes ujraindításához reset_position-nel
    private SensorArray szenzorTomb;
    private LidarSensor lidar;
    private Vector3 kezdoPozicio;
    private Quaternion kezdoForgatas;
    
    [Header("GPS Célpontok (Végpontok)")]
    [SerializeField]
    private Vector3[] gpsPontok = new Vector3[] {
    new Vector3(1f, 0f, 2f),   // Példa pontok, a Unity Inspectorban felülírhatod
    new Vector3(1f, 0f, -2f),
    new Vector3(-1f, 0f, -2f),
    new Vector3(-1f, 0f, 2f)
};
    private int aktualisGpsIndex = 0;
    private bool eppMostErteEl = false;
    private const float GpsKuszob = 0.5f; // 50 cm-es pontosság a cél eléréséhez

    // --- M10: utkozesdetektalas (hiba-taxonomia "utkozes" kategoriaja) ---
    // A TrackController "Akadaly" taggel latja el a letrehozott akadalyokat
    // (lasd TrackController.FelepitAkadalyokat). Csak ezekkel az utkozeseket
    // szamoljuk, a talajjal/palyaval valo folyamatos erintkezest nem.
    private const string AkadalyTagNev = "Akadaly";
    private bool utkozesTortentAzUtolsoResetOta = false;
    private int utkozesekSzamaAzUtolsoResetOta = 0;
    // M10 javitas (2. probalkozas): a colliderenkenti be-/kilepes
    // szamlalasa instabilnak bizonyult, amikor a rover tobb colliderje
    // (alvaz + 4 kerek) egyszerre, melyen atfedesben van egy akadallyal
    // - a fizikai motor ilyenkor bizonytalanul, oda-vissza jelzi az
    // erintkezest. Ehelyett egy egyszeru, idoalapu "hutesi" ablakot
    // hasznalunk: ha ket OnCollisionEnter kozott kevesebb, mint
    // UtkozesCooldownMasodperc telik el, nem szamit uj utkozesnek.
    private const float UtkozesCooldownMasodperc = 0.5f;
    private float utolsoUtkozesIdopontja = float.NegativeInfinity;
    private TcpListener listener;
    private Thread listenerSzal;
    private volatile bool fut;
    private Vector3 mozgasIranya;
    private float hatralevoTavolsag;
    private float maximalisSebesseg;
    private float hatralevoSzog;
    private float maximalisSzogsebesseg;
    private float aktivParancsKezdete;
    private float aktivParancsKeretS;
    private volatile RoverAllapot allapot = RoverAllapot.IDLE;
    private FuggobenLevoKeres aktivMozgasKeres;
    private string utolsoParancsEredmenye = "none";

    [Serializable]
    private class AlapValasz
    {
        public string request_id;
        public string status;
        public string state;
        public HibaAdat error;
        public string message;
        public float sim_time_s;
    }

    [Serializable]
    private class HibaAdat
    {
        public int code;
        public string name;
        public string message;
    }

    [Serializable]
    private class Pozicio
    {
        public float x;
        public float y;
        public float z;

        public Pozicio(Vector3 ertek)
        {
            x = ertek.x;
            y = ertek.y;
            z = ertek.z;
        }
    }

    [Serializable]
    private class SzenzorErtek
    {
        public bool white;
        public float intensity;

        public SzenzorErtek(bool feher, float intenzitas)
        {
            white = feher;
            intensity = intenzitas;
        }
    }

    [Serializable]
    private class ObserveValasz
    {
        public string request_id;
        public string status;
        public string state;
        public HibaAdat error;
        public Pozicio position;
        public float speed;
        public float target_distance;
        public float target_angle;
        public bool gps_reached;
        public string sensor_mode;
        public SzenzorErtek sensor_left;
        public SzenzorErtek sensor_center;
        public SzenzorErtek sensor_right;
        public float[] lidar_szektor_min;
        public float[] lidar_nyers;
        public bool[] lidar_nyers_ervenyes;
        public bool collision_occurred;
        public int collision_count;
        public float sim_time_s;
    }

    [Serializable]
    private class StatusValasz
    {
        public string request_id;
        public string status;
        public string state;
        public HibaAdat error;
        public int protocol_version;
        public string last_command_result;
        public float sim_time_s;
    }

    private sealed class FeldolgozottKeres
    {
        public string RequestId;
        public string Command;
        public float Distance;
        public float MaxSpeed;
        public float Angle;
        public float MaxAngularSpeed;
        public int NoiseSeed;
    }

    [Serializable]
    private sealed class KeresDto
    {
        public string request_id;
        public string command;
        public float distance_m;
        public float max_speed;
        public float angle_deg;
        public float max_angular_speed;
        public int noise_seed;
    }

    private sealed class IdempotenciaBejegyzes
    {
        public readonly string PayloadHash;
        public string VegsoValasz;

        public IdempotenciaBejegyzes(string payloadHash)
        {
            PayloadHash = payloadHash;
        }
    }

    private sealed class FuggobenLevoKeres
    {
        public readonly string Json;
        public readonly Guid KapcsolatId;
        public readonly ManualResetEventSlim Elkeszult = new ManualResetEventSlim(false);
        public string RequestId;
        public string Command;
        public string Valasz;

        public FuggobenLevoKeres(string json, Guid kapcsolatId)
        {
            Json = json;
            KapcsolatId = kapcsolatId;
        }
    }

    private void Awake()
    {
        rigidBody = GetComponent<Rigidbody>();
        trackController = FindFirstObjectByType<TrackController>();
                szenzorTomb = GetComponent<SensorArray>();
        lidar = GetComponentInChildren<LidarSensor>();
        kezdoPozicio = rigidBody.position;
        kezdoForgatas = rigidBody.rotation;
        Time.timeScale = 10f;
    }

    private void Start()
    {
        // Az Awake-ben a TrackController meg nem biztos, hogy betoltotte a
        // szcenariot, ezert a kezdopozt itt vesszuk at tole.
        if (KezdoPozFrissitese())
        {
            rigidBody.position = kezdoPozicio;
            rigidBody.rotation = kezdoForgatas;
            transform.SetPositionAndRotation(kezdoPozicio, kezdoForgatas);
        }
    }

    private bool KezdoPozFrissitese()
    {
        if (trackController != null
            && trackController.KezdoPoz(kezdoPozicio.y, out Vector3 p, out Quaternion f))
        {
            kezdoPozicio = p;
            kezdoForgatas = f;
            return true;
        }
        return false;
    }

    // Resetnel a szenzorok zajgeneratora ujraindul a seedbol. Enelkul a
    // generator a Play mod inditasatol futott tovabb, igy ket futas soha
    // nem kaphatta ugyanazt a zajsorozatot.
    private void SzenzorZajUjrainditasa(int futasSeed = 0)
    {
        foreach (ColorSensor szenzor in GetComponentsInChildren<ColorSensor>(true))
        {
            szenzor.ZajUjrainditasa(futasSeed);
        }
        if (lidar != null)
        {
            lidar.ZajUjrainditasa(futasSeed);
        }
    }

    private void OnEnable()
    {
        InditSzerver();
    }

    private void Update()
    {
        while (naploUzenetek.TryDequeue(out string uzenet))
        {
            Debug.Log(uzenet, this);
        }
    }

    private void FixedUpdate()
    {
        
        eppMostErteEl = false;
        if (gpsPontok != null && gpsPontok.Length > 0 && aktualisGpsIndex < gpsPontok.Length)
        {
            float tavolsag = Vector3.Distance(rigidBody.position, gpsPontok[aktualisGpsIndex]);
            if (tavolsag < GpsKuszob)
            {
                aktualisGpsIndex++;
                eppMostErteEl = true;
                if (aktualisGpsIndex >= gpsPontok.Length)
                {
                    aktualisGpsIndex = 0; // Ha körbeért, kezdje elölről
                }
            }
        }

        KapcsolatBontasokFeldolgozasa();

        while (keresek.TryDequeue(out FuggobenLevoKeres keres))
        {
            string valasz;
            try
            {
                valasz = FeldolgozKeres(keres);
            }
            catch (Exception hiba)
            {
                Debug.LogException(hiba, this);
                string requestId = RequestIdKinyerese(keres.Json);
                valasz = HibaValasz(
                    requestId,
                    1600,
                    "INTERNAL_ERROR",
                    "A kérés feldolgozása közben belső szerverhiba történt."
                );
                VegsoValaszTarolasa(requestId, valasz);
                utolsoParancsEredmenye = "internal:error";
            }
            if (valasz != null)
            {
                BefejezVarakozoKerest(keres, valasz);
            }
        }

        FrissitAktivMozgast();
    }

    private void OnDisable()
    {
        LeallitSzerver();
    }


    // --- M10: utkozesdetektalas ---
    // A rover Rigidbody-jat hordozo GameObject-en fut (RequireComponent),
    // ezert az OnCollisionEnter itt a rover fizikai utkozeseit fogja el.
    // A rover kinematikus, az akadalyok statikus colliderek - ez a
    // kombinacio eleg ahhoz, hogy Unity generalja az utkozesi esemenyt,
    // mivel a roveren van (kinematikus) Rigidbody.

    private void OnCollisionEnter(Collision utkozes)
    {
        if (utkozes.collider != null && utkozes.collider.CompareTag(AkadalyTagNev))
        {
            float most = Time.time;
            if (most - utolsoUtkozesIdopontja > UtkozesCooldownMasodperc)
            {
                utkozesTortentAzUtolsoResetOta = true;
                utkozesekSzamaAzUtolsoResetOta++;
                naploUzenetek.Enqueue(
                    $"M10: utkozes eszlelve az akadallyal '{utkozes.collider.name}' " +
                    $"(osszesen {utkozesekSzamaAzUtolsoResetOta} az utolso reset ota)."
                );
            }
            utolsoUtkozesIdopontja = most;
        }
    }



    private void OnApplicationQuit()
    {
        LeallitSzerver();
    }

    private void InditSzerver()
    {
        if (fut)
        {
            return;
        }

        fut = true;
        listenerSzal = new Thread(ListenerCiklus)
        {
            IsBackground = true,
            Name = "RoverGateway TCP listener"
        };
        listenerSzal.Start();
    }

    private void ListenerCiklus()
    {
        try
        {
            listener = new TcpListener(IPAddress.Loopback, port);
            listener.Start();
            naploUzenetek.Enqueue($"RoverGateway figyel: 127.0.0.1:{port}");

            while (fut)
            {
                TcpClient kliens = listener.AcceptTcpClient();

                lock (kliensekZar)
                {
                    aktivKliensek.Add(kliens);
                }

                Thread kliensSzal = new Thread(() => KliensKezelo(kliens))
                {
                    IsBackground = true,
                    Name = "RoverGateway TCP client"
                };
                kliensSzal.Start();
            }
        }
        catch (SocketException hiba)
        {
            if (fut)
            {
                naploUzenetek.Enqueue($"RoverGateway hálózati hiba: {hiba.Message}");
            }
        }
        catch (Exception hiba)
        {
            naploUzenetek.Enqueue($"RoverGateway szerverhiba: {hiba.Message}");
        }
        finally
        {
            try
            {
                listener?.Stop();
            }
            catch (SocketException)
            {
                // A listener egy másik szálon már leállhatott.
            }
        }
    }

    private void KliensKezelo(TcpClient kliens)
    {
        Guid kapcsolatId = Guid.NewGuid();

        try
        {
            kliens.NoDelay = true;

            using (kliens)
            using (NetworkStream halozat = kliens.GetStream())
            {
                List<FuggobenLevoKeres> kapcsolatKeresei = new List<FuggobenLevoKeres>();

                while (fut)
                {
                    // Nem blokkolunk egy hosszú move/turn válaszára: ugyanerről a
                    // kapcsolatról közben stop/observe/get_status is érkezhet.
                    for (int i = 0; i < kapcsolatKeresei.Count; i++)
                    {
                        FuggobenLevoKeres keszKeres = kapcsolatKeresei[i];
                        if (!keszKeres.Elkeszult.IsSet)
                        {
                            continue;
                        }

                        FrameIras(halozat, keszKeres.Valasz);
                        kapcsolatKeresei.RemoveAt(i);
                        i--;
                    }

                    if (KapcsolatLezart(kliens))
                    {
                        break;
                    }

                    if (!halozat.DataAvailable)
                    {
                        Thread.Sleep(10);
                        continue;
                    }

                    byte[] hosszPuffer = new byte[4];
                    if (!PontosanOlvas(halozat, hosszPuffer, 4))
                    {
                        break;
                    }

                    int frameHossz = (hosszPuffer[0] << 24)
                        | (hosszPuffer[1] << 16)
                        | (hosszPuffer[2] << 8)
                        | hosszPuffer[3];

                    // A v1 protokollban a prefix a UTF-8 payload bájthosszát adja meg.
                    int tenylegesMaximum = Math.Min(maximalisUzenethossz, MaximalisFrameMeret);
                    if (frameHossz <= 0 || frameHossz > tenylegesMaximum)
                    {
                        string hiba = HibaValasz(
                            "",
                            1101,
                            "INVALID_FIELD_TYPE",
                            $"A TCP frame mérete 1 és {tenylegesMaximum} bájt között lehet."
                        );
                        FrameIras(halozat, hiba);
                        break;
                    }

                    byte[] payload = new byte[frameHossz];
                    if (!PontosanOlvas(halozat, payload, frameHossz))
                    {
                        break;
                    }

                    string json = new UTF8Encoding(false, true).GetString(payload);
                    FuggobenLevoKeres keres = new FuggobenLevoKeres(json, kapcsolatId);
                    kapcsolatKeresei.Add(keres);
                    keresek.Enqueue(keres);
                }
            }
        }
        catch (IOException hiba)
        {
            if (fut)
            {
                naploUzenetek.Enqueue($"RoverGateway klienskapcsolati hiba: {hiba.Message}");
            }
        }
        catch (Exception hiba)
        {
            if (fut)
            {
                naploUzenetek.Enqueue($"RoverGateway klienshiba: {hiba.Message}");
            }
        }
        finally
        {
            bontottKapcsolatAzonositok.TryAdd(kapcsolatId, 0);
            bontottKapcsolatok.Enqueue(kapcsolatId);
            lock (kliensekZar)
            {
                aktivKliensek.Remove(kliens);
            }
        }
    }

    private string FeldolgozKeres(FuggobenLevoKeres fuggoben)
    {
        string json = fuggoben.Json;
        if (!KeresValidalasa(json, out FeldolgozottKeres keres, out string validaciosHiba))
        {
            return validaciosHiba;
        }

        string payloadHash = Sha256(json);
        if (idempotenciaTar.TryGetValue(keres.RequestId, out IdempotenciaBejegyzes letezo))
        {
            if (!string.Equals(letezo.PayloadHash, payloadHash, StringComparison.Ordinal))
            {
                return HibaValasz(
                    keres.RequestId,
                    1401,
                    "REQUEST_ID_CONFLICT",
                    "A request_id korábban eltérő payload-dal szerepelt."
                );
            }

            if (letezo.VegsoValasz != null)
            {
                return letezo.VegsoValasz;
            }

            return HibaValasz(
                keres.RequestId,
                1400,
                "DUPLICATE_REQUEST",
                "Az azonos request_id-jú kérés még feldolgozás alatt áll."
            );
        }

        // Az ID-t a végrehajtás előtt foglaljuk le, így nincs dupla mozgás.
        idempotenciaTar.Add(keres.RequestId, new IdempotenciaBejegyzes(payloadHash));

        // A kapcsolat a hálózati és a Unity-szál közötti átadás közben is megszakadhat.
        if (bontottKapcsolatAzonositok.ContainsKey(fuggoben.KapcsolatId))
        {
            string bontasiHiba = HibaValasz(
                keres.RequestId,
                1501,
                "WATCHDOG_EXPIRED",
                "A klienskapcsolat a kérés végrehajtása előtt megszakadt."
            );
            VegsoValaszTarolasa(keres.RequestId, bontasiHiba);
            utolsoParancsEredmenye = keres.Command + ":error";
            return bontasiHiba;
        }

        string valasz;
        switch (keres.Command)
        {
            case "observe":
                string szenzorMod = szenzorTomb != null && szenzorTomb.HaromSzenzorosMod ? "three" : "single";

                // ÚJ BLOKK: Relatív vektor kiszámítása
                float celTavolsag = 0f;
                float celSzog = 0f;
                if (gpsPontok != null && gpsPontok.Length > 0 && aktualisGpsIndex < gpsPontok.Length)
                {
                    Vector3 celIrany = gpsPontok[aktualisGpsIndex] - rigidBody.position;
                    celIrany.y = 0; // Csak 2D-s síkban (XZ) navigálunk
                    celTavolsag = celIrany.magnitude;
                    celSzog = Vector3.SignedAngle(transform.forward, celIrany, Vector3.up);
                }

                valasz = JsonUtility.ToJson(new ObserveValasz
                {
                    request_id = keres.RequestId,
                    status = "completed",
                    state = AllapotNev,
                    error = null,
                    position = new Pozicio(rigidBody.position),
                    speed = rigidBody.linearVelocity.magnitude,
                    sensor_mode = szenzorMod,
                    sensor_left = new SzenzorErtek(
                        szenzorTomb != null && szenzorTomb.BalFeher,
                        szenzorTomb != null ? szenzorTomb.BalErtek : 0f
                    ),
                    sensor_center = new SzenzorErtek(
                        szenzorTomb != null && szenzorTomb.KozepFeher,
                        szenzorTomb != null ? szenzorTomb.KozepErtek : 0f
                    ),
                    sensor_right = new SzenzorErtek(
                        szenzorTomb != null && szenzorTomb.JobbFeher,
                        szenzorTomb != null ? szenzorTomb.JobbErtek : 0f
                    ),
                    lidar_szektor_min = lidar != null ? lidar.SzektorMinTavolsag : new float[0],
<<<<<<< Updated upstream
                    lidar_nyers = lidar != null ? lidar.NyersTavolsagok : new float[0],
                    lidar_nyers_ervenyes = lidar != null ? lidar.ErvenyessegiMaszk : new bool[0],
<<<<<<< HEAD
                        collision_occurred = utkozesTortentAzUtolsoResetOta,
                        collision_count = utkozesekSzamaAzUtolsoResetOta
=======
                    collision_occurred = utkozesTortentAzUtolsoResetOta,
                    collision_count = utkozesekSzamaAzUtolsoResetOta,

                    // ÚJ MEZŐK KITÖLTÉSE
                    target_distance = celTavolsag,
                    target_angle = celSzog,
                    gps_reached = eppMostErteEl
>>>>>>> Stashed changes
=======
                    collision_occurred = utkozesTortentAzUtolsoResetOta,
                    collision_count = utkozesekSzamaAzUtolsoResetOta,
                    sim_time_s = SzimulaciosIdo
>>>>>>> eaf15e1d41e5b3e7c51c73cda11b34faac27b785
                });
                valasz = NullHiba(valasz);
                break;

            case "get_status":
                valasz = JsonUtility.ToJson(new StatusValasz
                {
                    request_id = keres.RequestId,
                    status = "completed",
                    state = AllapotNev,
                    error = null,
                    protocol_version = ProtokollVerzio,
                    last_command_result = utolsoParancsEredmenye,
                    sim_time_s = SzimulaciosIdo
                });
                valasz = NullHiba(valasz);
                break;

            case "move":
                if (allapot != RoverAllapot.IDLE)
                {
                    valasz = HibaValasz(
                        keres.RequestId,
                        1300,
                        "COMMAND_NOT_ALLOWED_IN_STATE",
                        $"A move parancs {AllapotNev} állapotban nem engedélyezett."
                    );
                    break;
                }

                mozgasIranya = transform.forward.normalized;
                hatralevoTavolsag = keres.Distance;
                maximalisSebesseg = keres.MaxSpeed;
                AktivMozgasInditasa(
                    RoverAllapot.MOVING, fuggoben, keres.RequestId, keres.Distance / keres.MaxSpeed
                );
                return null;

            case "turn":
                if (allapot != RoverAllapot.IDLE)
                {
                    valasz = HibaValasz(
                        keres.RequestId,
                        1300,
                        "COMMAND_NOT_ALLOWED_IN_STATE",
                        $"A turn parancs {AllapotNev} állapotban nem engedélyezett."
                    );
                    break;
                }

                hatralevoSzog = keres.Angle;
                maximalisSzogsebesseg = keres.MaxAngularSpeed;
                AktivMozgasInditasa(
                    RoverAllapot.TURNING,
                    fuggoben,
                    keres.RequestId,
                    Mathf.Abs(keres.Angle) / keres.MaxAngularSpeed
                );
                return null;

            case "stop":
                RoverAllapot stopElottiAllapot = allapot;
                RoverAzonnaliLeallitasa();
                // ERROR állapotban a stop biztonságos no-op, nem hibanyugtázás.
                if (stopElottiAllapot != RoverAllapot.ERROR)
                {
                    allapot = RoverAllapot.IDLE;
                }
                if (aktivMozgasKeres != null)
                {
                    string megszakitott = HibaValasz(
                        aktivMozgasKeres.RequestId,
                        1300,
                        "COMMAND_NOT_ALLOWED_IN_STATE",
                        "Az aktív mozgást stop parancs szakította meg."
                    );
                    MozgasiKeresBefejezese(megszakitott);
                }
                valasz = SikerValasz(keres.RequestId, "A rover áll.");
                break;

            case "reset_error":
                if (allapot != RoverAllapot.ERROR)
                {
                    valasz = HibaValasz(
                        keres.RequestId,
                        1300,
                        "COMMAND_NOT_ALLOWED_IN_STATE",
                        $"A reset_error parancs {AllapotNev} állapotban nem engedélyezett."
                    );
                    break;
                }

                if (!BiztonsagosHibaReset())
                {
                    valasz = HibaValasz(
                        keres.RequestId,
                        1502,
                        "ERROR_RESET_NOT_SAFE",
                        "A rover fizikai állapota nem teszi lehetővé a biztonságos resetet."
                    );
                    break;
                }

                RoverAzonnaliLeallitasa();
                KezdoPozFrissitese();
                rigidBody.position = kezdoPozicio;
                rigidBody.rotation = kezdoForgatas;
                SzenzorZajUjrainditasa();
                allapot = RoverAllapot.IDLE;
                utkozesTortentAzUtolsoResetOta = false;
                utkozesekSzamaAzUtolsoResetOta = 0;
                utolsoUtkozesIdopontja = float.NegativeInfinity;
                valasz = SikerValasz(
                    keres.RequestId,
                    "A hiba törölve; a rover visszaállt a kezdőhelyzetbe."
                );
                break;

            case "reset_position":
                if (allapot != RoverAllapot.IDLE)
                {
                    valasz = HibaValasz(
                        keres.RequestId,
                        1300,
                        "COMMAND_NOT_ALLOWED_IN_STATE",
                        $"A reset_position parancs {AllapotNev} allapotban nem engedelyezett."
                    );
                    break;
                }

                if (!BiztonsagosHibaReset())
                {
                    valasz = HibaValasz(
                        keres.RequestId,
                        1502,
                        "ERROR_RESET_NOT_SAFE",
                        "A rover fizikai allapota nem teszi lehetove a biztonsagos resetet."
                    );
                    break;
                }

                RoverAzonnaliLeallitasa();
                KezdoPozFrissitese();
                rigidBody.position = kezdoPozicio;
                rigidBody.rotation = kezdoForgatas;
                SzenzorZajUjrainditasa(keres.NoiseSeed);
                utkozesTortentAzUtolsoResetOta = false;
                utkozesekSzamaAzUtolsoResetOta = 0;
                trackController?.UjrakezdiAkadalyUtemezest();
                utolsoUtkozesIdopontja = float.NegativeInfinity;
                aktualisGpsIndex = 0; // ÚJ SOR: Célpontok nullázása
                valasz = SikerValasz(
                    keres.RequestId,
                    "A rover visszaallt a kezdohelyzetbe. scenario="
                        + (trackController != null ? trackController.SzcenarioNev : "")
                        + " timescale="
                        + Time.timeScale.ToString(System.Globalization.CultureInfo.InvariantCulture)
                        // A meresi futtato ezekbol ellenorzi, hogy az akadalyok
                        // tenyleg jelen vannak (lasd TrackController.UtemezesFut).
                        + " obstacles="
                        + (trackController != null ? trackController.AkadalyokSzama : 0)
                        + " active="
                        + (trackController != null ? trackController.AktivAkadalyokSzama : 0)
                        + " schedule="
                        + (trackController != null && trackController.UtemezesFut ? "on" : "off")
                );
                break;

            default:
                valasz = HibaValasz(
                    keres.RequestId,
                    1200,
                    "UNKNOWN_COMMAND",
                    "Ismeretlen parancs."
                );
                break;
        }

        VegsoValaszTarolasa(keres.RequestId, valasz);
        // Ide CSAK rovid osszefoglalo kerul, soha a teljes valasz. Korabban a
        // teljes valasz JSON-ja volt eltarolva, aminek ket kovetkezmenye volt:
        // (1) a get_status last_command_result mezoje visszaadta az elozo
        //     observe privilegizalt mezoit (position, speed, collision_count),
        //     megkerulve az adapter szurojet, ami csak felso szintu kulcsokat nez;
        // (2) minden valasz beagyazta az elozot escape-elve, igy az ismetelt
        //     get_status hivasok merete hivasonkent duplazodott.
        utolsoParancsEredmenye = EredmenyOsszefoglalo(keres.Command, valasz);
        return valasz;
    }

    // A last_command_result MINDIG "<parancs>:<completed|error>" alaku (vagy a
    // kezdeti "none"). Korabban harom hibaagon (belso hiba, bontott kapcsolat,
    // mozgas vege) a teljes valasz-JSON kerult ide, ami a semanak sem felelt meg,
    // es a privilegizalt mezoket is kiszivarogtathatta volna.
    private static string EredmenyOsszefoglalo(string parancs, string valasz)
    {
        string statusz = valasz != null && valasz.Contains("\"status\":\"completed\"")
            ? "completed"
            : "error";
        return (string.IsNullOrEmpty(parancs) ? "unknown" : parancs) + ":" + statusz;
    }

    // A JsonUtility a null objektumot nem tudja null-kent irni: az error mezo
    // sikeres valasznal {"code":0,"name":"","message":""} lett volna, ellentetben
    // a docs/protocol.md-vel es a semaval ("error": null).
    private static string NullHiba(string json)
    {
        return json.Replace("\"error\":{\"code\":0,\"name\":\"\",\"message\":\"\"}", "\"error\":null");
    }

    // Szimulacios ido a jelenet betoltese ota (s). Timescale-tol fuggetlenul a
    // fizikai ido: a naplokban ez adja a futasok valodi idotartamat.
    private static float SzimulaciosIdo => Time.timeSinceLevelLoad;

    private void AktivMozgasInditasa(
        RoverAllapot ujAllapot,
        FuggobenLevoKeres fuggoben,
        string requestId,
        float varhatoIdotartamS
    )
    {
        allapot = ujAllapot;
        aktivParancsKezdete = Time.fixedTime;
        aktivParancsKeretS =
            varhatoIdotartamS * ParancsIdotullepesSzorzo + ParancsIdotullepesTartalekS;
        aktivMozgasKeres = fuggoben;
        aktivMozgasKeres.RequestId = requestId;
        aktivMozgasKeres.Command = ujAllapot == RoverAllapot.MOVING ? "move" : "turn";
    }

    private void FrissitAktivMozgast()
    {
        if (allapot != RoverAllapot.MOVING && allapot != RoverAllapot.TURNING)
        {
            return;
        }

        if (Time.fixedTime - aktivParancsKezdete >= aktivParancsKeretS)
        {
            RoverAzonnaliLeallitasa();
            allapot = RoverAllapot.ERROR;
            string hiba = HibaValasz(
                aktivMozgasKeres.RequestId,
                1500,
                "COMMAND_TIMEOUT",
                "A move/turn parancs a varhato idotartam 1.5-szerese + 2 s "
                    + "(szimulacios ido) alatt nem fejezodott be."
            );
            MozgasiKeresBefejezese(hiba);
            return;
        }

        if (allapot == RoverAllapot.MOVING)
        {
            float lepes = Mathf.Min(maximalisSebesseg * Time.fixedDeltaTime, hatralevoTavolsag);
            rigidBody.MovePosition(rigidBody.position + mozgasIranya * lepes);
            hatralevoTavolsag -= lepes;

            if (hatralevoTavolsag > Mathf.Epsilon)
            {
                return;
            }
        }
        else
        {
            float eloJel = Mathf.Sign(hatralevoSzog);
            float lepes = Mathf.Min(
                maximalisSzogsebesseg * Time.fixedDeltaTime,
                Mathf.Abs(hatralevoSzog)
            ) * eloJel;
            rigidBody.MoveRotation(
                rigidBody.rotation * Quaternion.AngleAxis(lepes, Vector3.up)
            );
            hatralevoSzog -= lepes;

            if (Mathf.Abs(hatralevoSzog) > Mathf.Epsilon)
            {
                return;
            }
        }

        string requestId = aktivMozgasKeres.RequestId;
        RoverAzonnaliLeallitasa();
        allapot = RoverAllapot.IDLE;
        MozgasiKeresBefejezese(SikerValasz(requestId, "A mozgási parancs befejeződött."));
    }

    private void RoverAzonnaliLeallitasa()
    {
        hatralevoTavolsag = 0f;
        maximalisSebesseg = 0f;
        hatralevoSzog = 0f;
        maximalisSzogsebesseg = 0f;
        rigidBody.linearVelocity = Vector3.zero;
        rigidBody.angularVelocity = Vector3.zero;
    }

    private bool BiztonsagosHibaReset()
    {
        return aktivMozgasKeres == null
            && hatralevoTavolsag == 0f
            && hatralevoSzog == 0f
            && VegesVektor(rigidBody.position)
            && VegesQuaternion(rigidBody.rotation)
            && VegesVektor(rigidBody.linearVelocity)
            && VegesVektor(rigidBody.angularVelocity)
            && VegesVektor(kezdoPozicio)
            && VegesQuaternion(kezdoForgatas);
    }

    private static bool VegesVektor(Vector3 ertek)
    {
        return Veges(ertek.x) && Veges(ertek.y) && Veges(ertek.z);
    }

    private static bool VegesQuaternion(Quaternion ertek)
    {
        return Veges(ertek.x) && Veges(ertek.y) && Veges(ertek.z) && Veges(ertek.w);
    }

    private static bool Veges(float ertek)
    {
        return !float.IsNaN(ertek) && !float.IsInfinity(ertek);
    }

    private void MozgasiKeresBefejezese(string valasz)
    {
        if (aktivMozgasKeres == null)
        {
            return;
        }

        FuggobenLevoKeres befejezett = aktivMozgasKeres;
        aktivMozgasKeres = null;
        VegsoValaszTarolasa(befejezett.RequestId, valasz);
        utolsoParancsEredmenye = EredmenyOsszefoglalo(befejezett.Command, valasz);
        BefejezVarakozoKerest(befejezett, valasz);
    }

    private void BefejezVarakozoKerest(FuggobenLevoKeres keres, string valasz)
    {
        keres.Valasz = valasz;
        Debug.Log($"TCP kérés: {keres.Json}\nTCP válasz: {valasz}", this);
        keres.Elkeszult.Set();
    }

    private string SikerValasz(string requestId, string uzenet)
    {
        return NullHiba(JsonUtility.ToJson(new AlapValasz
        {
            request_id = requestId,
            status = "completed",
            state = AllapotNev,
            error = null,
            message = uzenet,
            sim_time_s = SzimulaciosIdo
        }));
    }

    private string HibaValasz(string requestId, int kod, string nev, string uzenet)
    {
        return JsonUtility.ToJson(new AlapValasz
        {
            request_id = requestId ?? "",
            status = "failed",
            state = AllapotNev,
            error = new HibaAdat { code = kod, name = nev, message = uzenet },
            message = uzenet,
            sim_time_s = SzimulaciosIdo
        });
    }

    private string AllapotNev => allapot.ToString();

    private void KapcsolatBontasokFeldolgozasa()
    {
        while (bontottKapcsolatok.TryDequeue(out Guid kapcsolatId))
        {
            if (aktivMozgasKeres == null || aktivMozgasKeres.KapcsolatId != kapcsolatId)
            {
                continue;
            }

            // Csak a mozgást indító kliens bontása aktiválja a watchdogot.
            string requestId = aktivMozgasKeres.RequestId;
            RoverAzonnaliLeallitasa();
            allapot = RoverAllapot.ERROR;
            string hiba = HibaValasz(
                requestId,
                1501,
                "WATCHDOG_EXPIRED",
                "A vezérlőkapcsolat move/turn közben megszakadt."
            );
            MozgasiKeresBefejezese(hiba);
        }
    }

    private void VegsoValaszTarolasa(string requestId, string valasz)
    {
        if (requestId != null
            && idempotenciaTar.TryGetValue(requestId, out IdempotenciaBejegyzes bejegyzes))
        {
            bejegyzes.VegsoValasz = valasz;
        }
    }

    private static string Sha256(string json)
    {
        using (SHA256 sha = SHA256.Create())
        {
            byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(json));
            StringBuilder eredmeny = new StringBuilder(hash.Length * 2);
            foreach (byte ertek in hash)
            {
                eredmeny.Append(ertek.ToString("x2", CultureInfo.InvariantCulture));
            }
            return eredmeny.ToString();
        }
    }

    private bool KeresValidalasa(
        string json,
        out FeldolgozottKeres keres,
        out string hibaValasz
    )
    {
        keres = null;
        hibaValasz = null;
        KeresDto dto;

        // A v1 kérés lapos JSON objektum; a beágyazott objektum/tömb nem része a sémának.
        string levagottJson = json == null ? "" : json.Trim();
        if (levagottJson.Length < 2
            || levagottJson[0] != '{'
            || levagottJson[levagottJson.Length - 1] != '}'
            || levagottJson.IndexOf('{', 1) >= 0
            || levagottJson.IndexOf('[', 1) >= 0)
        {
            hibaValasz = HibaValasz(
                "", 1101, "INVALID_FIELD_TYPE",
                "A v1 kérésnek lapos JSON objektumnak kell lennie."
            );
            return false;
        }

        List<string> mezok = JsonMezonevek(json);
        HashSet<string> latottMezok = new HashSet<string>(StringComparer.Ordinal);
        foreach (string mezo in mezok)
        {
            if (!latottMezok.Add(mezo))
            {
                hibaValasz = HibaValasz(
                    "", 1103, "DUPLICATE_FIELD",
                    $"A(z) {mezo} mező csak egyszer szerepelhet."
                );
                return false;
            }
        }

        try
        {
            dto = JsonUtility.FromJson<KeresDto>(json);
        }
        catch (ArgumentException)
        {
            hibaValasz = HibaValasz(
                "",
                1101,
                "INVALID_FIELD_TYPE",
                "A kérés nem értelmezhető JSON objektumként."
            );
            return false;
        }

        if (dto == null || !StringMezo(json, "request_id"))
        {
            hibaValasz = HibaValasz(
                "",
                1104,
                "INVALID_REQUEST_ID",
                "A request_id kötelező UUID v4 string."
            );
            return false;
        }

        HashSet<string> engedelyezettMezok = new HashSet<string>(StringComparer.Ordinal)
        {
            "request_id", "command"
        };
        if (dto.command == "move")
        {
            engedelyezettMezok.Add("distance_m");
            engedelyezettMezok.Add("max_speed");
        }
        else if (dto.command == "turn")
        {
            engedelyezettMezok.Add("angle_deg");
            engedelyezettMezok.Add("max_angular_speed");
        }
        else if (dto.command == "reset_position")
        {
            // M10 holdout: opcionalis, futasonkenti zaj-seed.
            engedelyezettMezok.Add("noise_seed");
        }

        foreach (string mezo in mezok)
        {
            if (!engedelyezettMezok.Contains(mezo))
            {
                hibaValasz = HibaValasz(
                    dto.request_id, 1102, "UNKNOWN_FIELD",
                    $"A(z) {mezo} mező nem része a(z) {dto.command} kérés sémájának."
                );
                return false;
            }
        }

        if (!ErvenyesUuidV4(dto.request_id))
        {
            hibaValasz = HibaValasz(
                dto.request_id,
                1104,
                "INVALID_REQUEST_ID",
                "A request_id kanonikus UUID v4 formátumú legyen."
            );
            return false;
        }

        if (!StringMezo(json, "command") || string.IsNullOrWhiteSpace(dto.command))
        {
            hibaValasz = HibaValasz(
                dto.request_id,
                1101,
                "INVALID_FIELD_TYPE",
                "A command kötelező string mező."
            );
            return false;
        }

        FeldolgozottKeres eredmeny = new FeldolgozottKeres
        {
            RequestId = dto.request_id,
            Command = dto.command
        };

        if (dto.command == "move")
        {
            if (!NumerikusMezoValidalasa(
                    json, "distance_m", dto.request_id, out double distance, out hibaValasz)
                || !NumerikusMezoValidalasa(
                    json, "max_speed", dto.request_id, out double speed, out hibaValasz))
            {
                return false;
            }

            if (distance < 0.01d || distance > 2.00d)
            {
                hibaValasz = HibaValasz(
                    dto.request_id, 1203, "VALUE_OUT_OF_RANGE",
                    "A distance_m értéke 0.01 és 2.00 méter között lehet."
                );
                return false;
            }
            if (speed < 0.05d || speed > 0.50d)
            {
                hibaValasz = HibaValasz(
                    dto.request_id, 1203, "VALUE_OUT_OF_RANGE",
                    "A max_speed értéke 0.05 és 0.50 m/s között lehet."
                );
                return false;
            }

            eredmeny.Distance = (float)distance;
            eredmeny.MaxSpeed = (float)speed;
        }
        else if (dto.command == "turn")
        {
            if (!NumerikusMezoValidalasa(
                    json, "angle_deg", dto.request_id, out double angle, out hibaValasz)
                || !NumerikusMezoValidalasa(
                    json, "max_angular_speed", dto.request_id,
                    out double angularSpeed, out hibaValasz))
            {
                return false;
            }

            if (angle < -180d || angle > 180d || Math.Abs(angle) < 1d)
            {
                hibaValasz = HibaValasz(
                    dto.request_id, 1203, "VALUE_OUT_OF_RANGE",
                    "Az angle_deg -180 és 180 fok közötti legyen, abszolút értéke legalább 1 fok."
                );
                return false;
            }
            if (angularSpeed < 5d || angularSpeed > 45d)
            {
                hibaValasz = HibaValasz(
                    dto.request_id, 1203, "VALUE_OUT_OF_RANGE",
                    "A max_angular_speed értéke 5 és 45 fok/s között lehet."
                );
                return false;
            }

            eredmeny.Angle = (float)angle;
            eredmeny.MaxAngularSpeed = (float)angularSpeed;
        }

        if (mezok.Contains("noise_seed"))
        {
            if (dto.noise_seed < 1)
            {
                hibaValasz = HibaValasz(
                    dto.request_id, 1101, "INVALID_FIELD_TYPE",
                    "A noise_seed pozitiv egesz szam legyen."
                );
                return false;
            }
            eredmeny.NoiseSeed = dto.noise_seed;
        }

        keres = eredmeny;
        return true;
    }

    private static List<string> JsonMezonevek(string json)
    {
        List<string> mezok = new List<string>();
        int index = 0;
        while (index < json.Length)
        {
            if (json[index] != '"')
            {
                index++;
                continue;
            }

            index++;
            bool escape = false;
            StringBuilder szoveg = new StringBuilder();
            while (index < json.Length)
            {
                char karakter = json[index++];
                if (escape)
                {
                    // Dokumentált mezőneveink nem tartalmaznak escape-et; az
                    // escape-elt nevet ismeretlen mezőként kezeljük.
                    szoveg.Append('\\');
                    szoveg.Append(karakter);
                    escape = false;
                }
                else if (karakter == '\\')
                {
                    escape = true;
                }
                else if (karakter == '"')
                {
                    break;
                }
                else
                {
                    szoveg.Append(karakter);
                }
            }

            int kovetkezo = index;
            while (kovetkezo < json.Length && char.IsWhiteSpace(json[kovetkezo]))
            {
                kovetkezo++;
            }
            if (kovetkezo < json.Length && json[kovetkezo] == ':')
            {
                mezok.Add(szoveg.ToString());
            }
        }
        return mezok;
    }

    private static string RequestIdKinyerese(string json)
    {
        if (string.IsNullOrEmpty(json))
        {
            return "";
        }

        Match match = Regex.Match(
            json,
            "\\\"request_id\\\"\\s*:\\s*\\\"(?<value>[^\\\"]*)\\\"",
            RegexOptions.CultureInvariant
        );
        return match.Success ? match.Groups["value"].Value : "";
    }

    private bool NumerikusMezoValidalasa(
        string json,
        string mezonev,
        string requestId,
        out double ertek,
        out string hibaValasz
    )
    {
        ertek = 0d;
        hibaValasz = null;
        Match match = Regex.Match(
            json,
            "\\\"" + Regex.Escape(mezonev)
                + "\\\"\\s*:\\s*(?<value>[^,}\\s]+)",
            RegexOptions.CultureInvariant
        );

        if (!match.Success
            || Regex.Matches(
                json,
                "\\\"" + Regex.Escape(mezonev) + "\\\"\\s*:",
                RegexOptions.CultureInvariant
            ).Count != 1
            || match.Groups["value"].Value.StartsWith("\"", StringComparison.Ordinal))
        {
            hibaValasz = HibaValasz(
                requestId, 1101, "INVALID_FIELD_TYPE",
                $"A {mezonev} kötelező numerikus mező."
            );
            return false;
        }

        string token = match.Groups["value"].Value;
        if (!double.TryParse(
                token,
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out ertek))
        {
            hibaValasz = HibaValasz(
                requestId, 1101, "INVALID_FIELD_TYPE",
                $"A {mezonev} kötelező numerikus mező."
            );
            return false;
        }

        if (double.IsNaN(ertek) || double.IsInfinity(ertek))
        {
            hibaValasz = HibaValasz(
                requestId, 1202, "NON_FINITE_VALUE",
                $"A {mezonev} értékének véges számnak kell lennie."
            );
            return false;
        }

        return true;
    }

    private static bool StringMezo(string json, string mezonev)
    {
        return Regex.IsMatch(
            json,
            "\\\"" + Regex.Escape(mezonev) + "\\\"\\s*:\\s*\\\"",
            RegexOptions.CultureInvariant
        );
    }

    private static bool ErvenyesUuidV4(string requestId)
    {
        if (requestId == null
            || requestId.Length != 36
            || !Guid.TryParseExact(requestId, "D", out _)
            || requestId[14] != '4')
        {
            return false;
        }

        char varians = char.ToLowerInvariant(requestId[19]);
        return varians == '8' || varians == '9' || varians == 'a' || varians == 'b';
    }

    private static bool PontosanOlvas(Stream stream, byte[] puffer, int hossz)
    {
        int pozicio = 0;
        while (pozicio < hossz)
        {
            int olvasott = stream.Read(puffer, pozicio, hossz - pozicio);
            if (olvasott == 0)
            {
                return false;
            }
            pozicio += olvasott;
        }
        return true;
    }

    private static void FrameIras(Stream stream, string json)
    {
        byte[] payload = Encoding.UTF8.GetBytes(json);
        int hossz = payload.Length;
        byte[] prefix =
        {
            (byte)(hossz >> 24),
            (byte)(hossz >> 16),
            (byte)(hossz >> 8),
            (byte)hossz
        };
        stream.Write(prefix, 0, prefix.Length);
        stream.Write(payload, 0, payload.Length);
        stream.Flush();
    }

    private static bool KapcsolatLezart(TcpClient kliens)
    {
        try
        {
            return kliens.Client.Poll(0, SelectMode.SelectRead)
                && kliens.Client.Available == 0;
        }
        catch (SocketException)
        {
            return true;
        }
        catch (ObjectDisposedException)
        {
            return true;
        }
    }

    private void LeallitSzerver()
    {
        if (!fut)
        {
            return;
        }

        fut = false;

        try
        {
            listener?.Stop();
        }
        catch (SocketException)
        {
            // A listener leállításakor ez ártalmatlan versenyhelyzet lehet.
        }

        lock (kliensekZar)
        {
            foreach (TcpClient kliens in aktivKliensek.ToArray())
            {
                kliens.Close();
            }

            aktivKliensek.Clear();
        }

        while (keresek.TryDequeue(out FuggobenLevoKeres keres))
        {
            keres.Valasz = null;
            keres.Elkeszult.Set();
        }

        if (listenerSzal != null && listenerSzal.IsAlive)
        {
            listenerSzal.Join(1000);
        }

        listenerSzal = null;
        listener = null;
    }
}
