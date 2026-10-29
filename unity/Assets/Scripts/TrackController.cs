using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

// Ezt a scriptet Dalma írta kézzel (nem a Codex), mert a hónapos AI-kvóta
// elfogyott az M06 mérföldkő munkája közben. A szcenárió-sémát, a
// generátort és a dokumentációt a Codex készítette (lásd AI_USAGE.md).
//
// Beolvas egy szcenárió JSON fájlt (experiments/scenarios/ mappából),
// felépíti a stadion alakú fehér vonalat, és létrehozza/időzíti az
// akadályokat a schedule mezők alapján.
[ExecuteAlways]
public class TrackController : MonoBehaviour
{
    [Header("Szcenárió")]
    [SerializeField]
    private string szcenarioFajlNev = "stadium-train-baseline.json";

    [Header("Hivatkozások")]
    [SerializeField]
    private Renderer talajRenderer; // húzd ide a Plane-t az Inspectorban

    private LineRenderer vonalRenderer;
    private ScenarioDokumentum dokumentum;
    private readonly List<AkadalyPeldany> akadalyok = new List<AkadalyPeldany>();

    private const int IvSzegmensSzam = 24; // hány szakaszból áll egy félkör
    private const string AkadalyTagNev = "Akadaly"; // M10: utkozesdetektalashoz

    [Serializable]
    private class Pont3D
    {
        public float x;
        public float y;
        public float z;

        public Vector3 UnityVektor()
        {
            return new Vector3(x, y, z);
        }
    }

    [Serializable]
    private class Rgb
    {
        public int r;
        public int g;
        public int b;

        public Color UnitySzin()
        {
            return new Color(r / 255f, g / 255f, b / 255f);
        }
    }

    [Serializable]
    private class Utemezes
    {
        public float appear_at_s;
        public float visible_for_s;
        public float disappear_at_s;
    }

    [Serializable]
    private class Akadaly
    {
        public string id;
        public Pont3D position_m;
        public Pont3D size_m;
        public Utemezes schedule;
    }

    [Serializable]
    private class Palya
    {
        public float straight_length_m;
        public float turn_radius_m;
        public float line_width_m;
        public Rgb background_color_rgb;
    }

    [Serializable]
    private class Metaadat
    {
        public string name;
        public string type;
        public uint seed;
    }

    [Serializable]
    private class ScenarioDokumentum
    {
        public string schema_version;
        public Metaadat metadata;
        public Palya track;
        public Akadaly[] obstacles;
    }

    private class AkadalyPeldany
    {
        public GameObject Objektum;
        public float MegjelenesIdo;
        public float EltunesIdo;
    }

    private float utemezesKezdeteS;

    private void Awake()
    {
        utemezesKezdeteS = Time.timeSinceLevelLoad;

        vonalRenderer = GetComponent<LineRenderer>();
        if (vonalRenderer == null)
        {
            vonalRenderer = gameObject.AddComponent<LineRenderer>();
        }

        string tartalom = BeolvasSzcenariot(AktivSzcenarioFajlNev());
        dokumentum = JsonUtility.FromJson<ScenarioDokumentum>(tartalom);

        if (dokumentum == null || dokumentum.track == null)
        {
            Debug.LogError(
                $"TrackController: nem sikerült beolvasni/értelmezni a "
                + $"'{szcenarioFajlNev}' szcenáriót.",
                this
            );
            return;
        }

        FelepitPalyaVonalat();
        BeallitTalajSzint();
        FelepitAkadalyokat();

        Debug.Log(
            $"TrackController: '{dokumentum.metadata.name}' szcenárió betöltve "
            + $"({dokumentum.obstacles.Length} akadállyal, seed={dokumentum.metadata.seed}).",
            this
        );
    }

    /// <summary>
    /// M10: az akadaly-utemezes "nulla idopontjat" ujraallitja a jelenlegi
    /// pillanatra. A RoverGatewayServer hivja meg reset_position parancsnal,
    /// hogy minden futas sajat, fuggetlen eselyt kapjon az akadalyokkal
    /// valo talalkozasra - kulonben a schedule.appear_at_s/disappear_at_s
    /// csak egyszer, a Play mod inditasa utan rovid ideig ervenyesulne.
    /// </summary>
    public void UjrakezdiAkadalyUtemezest()
    {
        utemezesKezdeteS = Time.timeSinceLevelLoad;
        // Azonnal alkalmazzuk az utemezest, ne csak a kovetkezo Update-ben:
        // igy a reset valasza mar a valodi lathatosagot jelenti.
        FrissitAkadalyLathatosagot();
    }

    /// <summary>
    /// Masodik audit / hibas train-meres (2026-10-26): ha a komponens ki van
    /// kapcsolva, az Awake lefut (az akadalyok letrejonnek, inaktivan), de az
    /// Update nem, igy az akadalyok sosem jelennek meg - a meres pedig 0
    /// akadallyal, eszrevetlenul futott le. Ezek a mezok a reset valaszaba
    /// kerulnek, es a meresi futtato ellenorzi oket a szcenariofajl alapjan.
    /// </summary>
    public int AkadalyokSzama => akadalyok.Count;

    public int AktivAkadalyokSzama
    {
        get
        {
            int db = 0;
            foreach (AkadalyPeldany akadaly in akadalyok)
            {
                if (akadaly.Objektum != null && akadaly.Objektum.activeSelf)
                {
                    db++;
                }
            }
            return db;
        }
    }

    public bool UtemezesFut => isActiveAndEnabled;

    /// <summary>
    /// A rover szcenariohoz kotott kezdopoza: a jobb oldali egyenes kozepe
    /// (x = turn_radius_m, z = 0), a vonalon, -z iranyba nezve. Korabban a
    /// rover ott indult, ahol a jelenetben eppen allt (egy M07-es teszt
    /// maradvanya a kanyarban), ami csak a train palyan esett a vonal
    /// kozelebe; a dev es a holdout palyan tobb mint 1 m-rel a vonal mellol
    /// indult volna.
    /// </summary>
    public string SzcenarioNev =>
        dokumentum != null && dokumentum.metadata != null ? dokumentum.metadata.name : "";

    public bool KezdoPoz(float y, out Vector3 pozicio, out Quaternion forgatas)
    {
        pozicio = Vector3.zero;
        forgatas = Quaternion.identity;
        if (dokumentum == null || dokumentum.track == null)
        {
            return false;
        }
        pozicio = new Vector3(dokumentum.track.turn_radius_m, y, 0f);
        forgatas = Quaternion.Euler(0f, 180f, 0f);
        return true;
    }

    private void Update()
    {
        FrissitAkadalyLathatosagot();
    }

    private void FrissitAkadalyLathatosagot()
    {
        // Kikapcsolt komponensnel az utemezes nem fut (az Update sem futna);
        // a reset sem kapcsolhatja be helyette az akadalyokat.
        if (!isActiveAndEnabled)
        {
            return;
        }
        float t = Time.timeSinceLevelLoad - utemezesKezdeteS;

        foreach (AkadalyPeldany akadaly in akadalyok)
        {
            bool lathato = t >= akadaly.MegjelenesIdo && t < akadaly.EltunesIdo;
            if (akadaly.Objektum.activeSelf != lathato)
            {
                akadaly.Objektum.SetActive(lathato);
            }
        }
    }

    /// <summary>
    /// 2026-10-26: a mereshez hasznalt szcenario a jelenet modositasa nelkul is
    /// kivalaszthato. Ha letezik az experiments/scenarios/aktiv_szcenario.txt
    /// (nem verziokovetett) fajl, annak elso sora felulirja az Inspector
    /// szcenarioFajlNev mezojet. Korabban minden mereshez at kellett irni es
    /// menteni a TrackScene-t, amitol a munkafa "piszkos" lett (git_tiszta=False),
    /// es a Unity a generalt vonal-anyagot is ujraszerializalta.
    /// </summary>
    private string AktivSzcenarioFajlNev()
    {
        string felulirasFajl = Path.Combine(SzcenarioMappa(), "aktiv_szcenario.txt");
        if (File.Exists(felulirasFajl))
        {
            foreach (string sor in File.ReadAllLines(felulirasFajl))
            {
                string nev = sor.Trim();
                if (nev.Length == 0 || nev.StartsWith("#"))
                {
                    continue;
                }
                return nev.EndsWith(".json") ? nev : nev + ".json";
            }
        }
        return szcenarioFajlNev;
    }

    private static string SzcenarioMappa()
    {
        string gyokerMappa = Path.GetFullPath(
            Path.Combine(Application.dataPath, "..", "..")
        );
        return Path.Combine(gyokerMappa, "experiments", "scenarios");
    }

    private string BeolvasSzcenariot(string fajlNev)
    {
        string gyokerMappa = Path.GetFullPath(
            Path.Combine(Application.dataPath, "..", "..")
        );
        string teljesUtvonal = Path.Combine(
            gyokerMappa, "experiments", "scenarios", fajlNev
        );
        return File.ReadAllText(teljesUtvonal);
    }

    private void FelepitPalyaVonalat()
    {
        float felHossz = dokumentum.track.straight_length_m / 2f;
        float sugar = dokumentum.track.turn_radius_m;
        float y = 0.01f; // kicsit a talaj fölött, hogy ne "villogjon"

        List<Vector3> pontok = new List<Vector3>();

        // 1. egyenes: x = +sugar, z: +felHossz -> -felHossz
        pontok.Add(new Vector3(sugar, y, felHossz));
        pontok.Add(new Vector3(sugar, y, -felHossz));

        // hátsó félkör (középpont: 0,0,-felHossz), x=+sugar -> x=-sugar,
        // kifelé (negatív z irányba) domborodva
        Vector3 hatsoKozeppont = new Vector3(0f, y, -felHossz);
        for (int i = 1; i < IvSzegmensSzam; i++)
        {
            float szog = Mathf.Deg2Rad * (90f - i * (180f / IvSzegmensSzam));
            Vector3 pont = hatsoKozeppont + sugar * new Vector3(
                Mathf.Sin(szog), 0f, -Mathf.Cos(szog)
            );
            pontok.Add(pont);
        }

        // 2. egyenes: x = -sugar, z: -felHossz -> +felHossz
        pontok.Add(new Vector3(-sugar, y, -felHossz));
        pontok.Add(new Vector3(-sugar, y, felHossz));

        // első (elülső) félkör (középpont: 0,0,+felHossz), x=-sugar -> x=+sugar,
        // kifelé (pozitív z irányba) domborodva
        Vector3 elsoKozeppont = new Vector3(0f, y, felHossz);
        for (int i = 1; i < IvSzegmensSzam; i++)
        {
            float szog = Mathf.Deg2Rad * (-90f + i * (180f / IvSzegmensSzam));
            Vector3 pont = elsoKozeppont + sugar * new Vector3(
                Mathf.Sin(szog), 0f, Mathf.Cos(szog)
            );
            pontok.Add(pont);
        }

        vonalRenderer.positionCount = pontok.Count;
        vonalRenderer.SetPositions(pontok.ToArray());
        vonalRenderer.loop = true;
        vonalRenderer.widthMultiplier = dokumentum.track.line_width_m;
        vonalRenderer.useWorldSpace = true;

        Shader vonalShader = Shader.Find("Universal Render Pipeline/Unlit")
            ?? Shader.Find("Sprites/Default");
        Material vonalAnyag = new Material(vonalShader);
        BeallitAnyagSzint(vonalAnyag, Color.white);
        vonalRenderer.sharedMaterial= vonalAnyag;
    }

    private void BeallitTalajSzint()
    {
        if (talajRenderer == null)
        {
            Debug.LogWarning(
                "TrackController: nincs beállítva a talajRenderer mező, "
                + "a háttérszín nem lesz alkalmazva.",
                this
            );
            return;
        }

        BeallitAnyagSzint(talajRenderer.sharedMaterial, dokumentum.track.background_color_rgb.UnitySzin());
    }

    private void BeallitAnyagSzint(Material anyag, Color szin)
    {
        if (anyag.HasProperty("_BaseColor"))
        {
            anyag.SetColor("_BaseColor", szin);
        }
        else if (anyag.HasProperty("_Color"))
        {
            anyag.SetColor("_Color", szin);
        }
    }

    private void FelepitAkadalyokat()
    {
        // M10 javitas: torli a korabbi (pl. ExecuteAlways ujrafutasabol
        // vagy kezi torlesbol) maradt akadalyokat, mielott ujakat hozna
        // letre - igy a metodus barmennyiszer lefuthat, sosem duplikal
        // es sosem hagy "halott" hivatkozast a listaban.
        for (int i = akadalyok.Count - 1; i >= 0; i--)
        {
            if (akadalyok[i].Objektum != null)
            {
                if (Application.isPlaying)
                {
                    Destroy(akadalyok[i].Objektum);
                }
                else
                {
                    DestroyImmediate(akadalyok[i].Objektum);
                }
            }
        }
        akadalyok.Clear();

        foreach (Akadaly akadaly in dokumentum.obstacles)
        {
            GameObject objektum = GameObject.CreatePrimitive(PrimitiveType.Cube);
            objektum.name = akadaly.id;
            // M10: "Akadaly" tag az utkozesdetektalashoz (lasd
            // RoverGatewayServer.OnCollisionEnter). A tag maganak a
            // Unity projektnek a Tags & Layers listajaban is szerepelnie
            // kell (ProjectSettings/TagManager.asset - mar hozzaadva).
            objektum.tag = AkadalyTagNev;
            // M13: az [ExecuteAlways] miatt ez Edit modban is lefut, es a
            // generalt akadalyok bekerulnenek a TrackScene.unity fajlba
            // (M11-ben ez tenyleg megtortent, kezzel kellett visszaallitani).
            // A DontSave jelzes miatt a jelenet mentesekor kimaradnak - futas
            // idejen a FelepitAkadalyokat() ugyis ujragenerálja oket.
            if (!Application.isPlaying)
            {
                objektum.hideFlags = HideFlags.DontSave;
            }
            objektum.transform.SetParent(transform);
            objektum.transform.position = akadaly.position_m.UnityVektor();
            objektum.transform.localScale = akadaly.size_m.UnityVektor();
            objektum.SetActive(false);

            akadalyok.Add(new AkadalyPeldany
            {
                Objektum = objektum,
                MegjelenesIdo = akadaly.schedule.appear_at_s,
                EltunesIdo = akadaly.schedule.disappear_at_s,
            });
        }
    }
    // --- M07: nyilvános geometriai lekérdezés a szenzorokhoz ---
    //
    // Visszaadja, hogy egy adott világkoordináta (XZ síkban vetítve)
    // mekkora távolságra van a pálya középvonalától (méterben), valamint
    // hogy ez a táv a vonal félszélességén belül van-e ("a vonalon van").
    public bool TavolsagAKozepvonaltol(Vector3 vilagPoziicio, out float tavolsagM)
    {
        if (dokumentum == null || dokumentum.track == null)
        {
            tavolsagM = float.PositiveInfinity;
            return false;
        }

        float felHossz = dokumentum.track.straight_length_m / 2f;
        float sugar = dokumentum.track.turn_radius_m;
        float felSzelesseg = dokumentum.track.line_width_m / 2f;

        float x = vilagPoziicio.x;
        float z = vilagPoziicio.z;

        float legkisebbTavolsag = float.PositiveInfinity;

        legkisebbTavolsag = Mathf.Min(
            legkisebbTavolsag,
            TavolsagEgyenestol(x, z, sugar, -felHossz, felHossz)
        );

        legkisebbTavolsag = Mathf.Min(
            legkisebbTavolsag,
            TavolsagEgyenestol(x, z, -sugar, -felHossz, felHossz)
        );

        // Also felkoriv: kozeppont (0, -felHossz), csak z <= -felHossz oldalon.
        legkisebbTavolsag = Mathf.Min(
            legkisebbTavolsag,
            TavolsagIvtol(x, z, 0f, -felHossz, sugar, -1f)
        );

        // Felso felkoriv: kozeppont (0, +felHossz), csak z >= +felHossz oldalon.
        legkisebbTavolsag = Mathf.Min(
            legkisebbTavolsag,
            TavolsagIvtol(x, z, 0f, felHossz, sugar, +1f)
        );

        tavolsagM = legkisebbTavolsag;
        return legkisebbTavolsag <= felSzelesseg;
    }

    private float TavolsagEgyenestol(float x, float z, float allandoX, float z1, float z2)
    {
        float zClamp = Mathf.Clamp(z, Mathf.Min(z1, z2), Mathf.Max(z1, z2));
        float dx = x - allandoX;
        float dz = z - zClamp;
        return Mathf.Sqrt(dx * dx + dz * dz);
    }

    // M11 javitas (Edit Mode teszt talalta): korabban a teljes korhoz merte
    // a tavolsagot, ezert a stadion belsejeben egy "fantom" felkoriv is
    // vonalnak szamitott (pl. a (0, +-2) pontokban 0 tavolsag), ahol a
    // ColorSensor tevesen feheret mert volna. A felkoriv csak a sajat
    // oldalan (irany * (z - kozepZ) >= 0) ervenyes; a masik oldalon a ket
    // vegpontjat az egyenes szakaszok mar lefedik.
    private float TavolsagIvtol(float x, float z, float kozepX, float kozepZ, float sugar, float irany)
    {
        float dx = x - kozepX;
        float dz = z - kozepZ;
        if (dz * irany < 0f)
        {
            return float.PositiveInfinity;
        }
        float tavKozepponttol = Mathf.Sqrt(dx * dx + dz * dz);
        return Mathf.Abs(tavKozepponttol - sugar);
    }

    public float VonalFelSzelessegeM
    {
        get
        {
            if (dokumentum == null || dokumentum.track == null)
            {
                return 0.1f;
            }
            return dokumentum.track.line_width_m / 2f;
        }
    }
}