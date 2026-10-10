#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace DesertRV.Tests
{
    // Isolated native regression of the Motor candidate. No saved scenes, PreviewScenes,
    // OS key claims, or writes to a human gameplay session. Same additive lifecycle
    // as JourneyCabinEntryPhysicsTests. All state/placement writes are fixture setup.
    public sealed class JourneyVehicleContactFixPhysicsTests
    {
        const string SourceScene = "Assets/DesertRV/Scenes/BodyStudy.unity";
        const string Manifest = "Assets/DesertRV/Scenes/Journey/JourneyContent.asset";
        const string Output = "JourneyEvidence/VehicleContactFix/native-contact-fix.json";
        const string InputPath = "JourneyEvidence/VehicleContactFix/consumer-input.json";
        const string InputHash = "JourneyEvidence/VehicleContactFix/consumer-input.sha256";
        const int Finger = 43101;
        static readonly Vector3 Extents = new Vector3(1.05f, 1.12f, 2.7f);
        const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static Type T(string n) => Type.GetType("DesertRV." + n + ", Assembly-CSharp", true);
        static object Get(object o, string n) => o.GetType().GetProperty(n).GetValue(o);
        static object Field(object o, string n) => o.GetType().GetField(n, Instance).GetValue(o);
        static void Set(object o, string n, object v) => o.GetType().GetField(n, Instance).SetValue(o, v);
        static object Call(object o, string n, params object[] a) => o.GetType().GetMethod(n).Invoke(o, a);
        static object E(string t, string v) => Enum.Parse(T(t), v);

        [Serializable] public sealed class FilePin { public string path, sha256; }
        [Serializable] public sealed class DependencyRow { public string path, sha256, kind, packageName, packageVersion; public long bytes; }
        [Serializable] public sealed class DependencyVersion { public string sha256; public long bytes; }
        [Serializable] public sealed class DependencyChange { public string path; public DependencyVersion before, after; }
        [Serializable] public sealed class ConsumerInput { public int schema; public string status, producerCommit, producerRunId, producerArtifactSha256, consumerCommit, currentProductionCommit; public DependencyRow[] dependencies; public DependencyChange[] dependencyChanges; }
        [Serializable] public sealed class DependencyCheck
        {
            public string status = "not-started", inputSha256, failureCode = "";
            public bool passed; public int expectedCount, actualCount;
            public DependencyRow[] actualDependencies = Array.Empty<DependencyRow>();
            public string[] mismatches = Array.Empty<string>();
        }
        [Serializable] public sealed class ColliderRow
        {
            public int id; public string hierarchy, type, mesh = "", meshGuid = "", role;
            public bool trigger, convex; public Vector3 min, max, capsuleCenter; public float capsuleRadius, capsuleHeight;
        }
        [Serializable] public sealed class HitRow
        { public int collider; public float distance; public Vector3 point, normal; public bool self, walker, upward, beast, dead; }
        [Serializable] public sealed class Frame
        {
            public int frame, rawCount, allCount, vehicleHealth; public string phase, state, control;
            public float dt, throttle, speedBefore, speedAtCast, speedAfter, intendedDistance, actualDistance, predictedAllowed;
            public bool castExecuted, rawSaturated, powerConnected; public Vector3 before, after, center, forward;
            public int[] overlaps;
            public HitRow[] rawHits, allHits, motorBufferHits, obstacleEvents;
        }
        [Serializable] public sealed class ApproachFrame
        {
            public int step, healthBefore, healthAfter; public float actualUpdateDelta;
            public Vector3[] positions; public string[] phases; public int[] proxyOverlaps;
        }
        [Serializable] public sealed class Case
        {
            public string name, placement, outcome = "recorded"; public float dt, throttle;
            public int requestedCapacity, actualCapacity; public bool ramInstalled, liveStationary, deathConfirmed, released, baselineMoved, wallHeld;
            public bool requiredLiveMove, requiredLiveBlock, liveActorsSurvived;
            public int[] liveActorHealthBefore = Array.Empty<int>(), liveActorHealthAfter = Array.Empty<int>();
            public Vector3 start, end; public int[] actorColliders;
            public List<Frame> frames = new List<Frame>();
            public List<ApproachFrame> approach = new List<ApproachFrame>();
        }
        [Serializable] public sealed class GeometryCheck
        {
            public string name, kind; public float travel, initialDepth, finalDepth, startAxisDistance, endAxisDistance, radius;
            public bool initialOverlap, finalOverlap, allowed, expectedAllowed, passed;
            public Vector3 endpoint1, endpoint2, boxCenter, boxForward;
        }
        [Serializable] public sealed class Report
        {
            public int schemaVersion = 2; public string scope = "motor-initial-live-capsule-escape-and-translation-buffer"; public bool regressionsPassed; public string status = "fixture-incomplete", failureCode = "", unityVersion;
            public string inputRoute = "editor-owned Accelerate/Brake -> MobileInputAdapter.Sample/Throttle -> production JourneyMotor.Tick; W/S-equivalent, no OS events";
            public string queryRoute = "raw/all/overlap queries sampled immediately before motor Tick; motorBufferHits is actual private buffer prefix using mirrored rawCount; obstacleEvents are actual callbacks; predictedAllowed is legacy geometry-only allowance excluding ram kills and the candidate escape/fallback logic";
            public string naturalRoute = "controlled same-PlayMode-frame calls to unchanged BeastActor.Update with fixed observed Time.deltaTime; no actor placement after exterior spawn; not automatic frame timing or human play";
            public string referenceProducerRunId = "38054694730";
            public Vector3 proxyExtents = Extents; public float proxyCenterY = 1.45f, maximumDeltaTime;
            public bool replayDetached, sceneUnloaded, sourceFilesUnchanged, anySyntheticLockReleased, anyNaturalProxyOverlap;
            public DependencyCheck dependencyCheck = new DependencyCheck();
            public List<FilePin> sourceFiles = new List<FilePin>();
            public List<ColliderRow> colliders = new List<ColliderRow>();
            public List<Case> cases = new List<Case>();
            public List<GeometryCheck> geometryChecks = new List<GeometryCheck>();
        }

        Scene loaded, originalActive; bool ownsLoad;
        CursorLockMode oldLock; bool oldCursor;
        GameObject host, road, inspectionWalker; Component viewer, session, adapter, motor;
        object state, touch; Transform vehicle; Quaternion initialRotation;
        GameObject pouncerPrefab, armoredPrefab; CharacterController walker;
        readonly List<Material> materials = new List<Material>();
        readonly List<Component> actors = new List<Component>();
        readonly Dictionary<Collider, int> ids = new Dictionary<Collider, int>();
        readonly List<HitRow> events = new List<HitRow>();
        readonly RaycastHit[] raw = new RaycastHit[32];
        Report report;

        [UnityTest, Timeout(600000)] public IEnumerator RealRV_RegressionInitialOverlapAndFullBuffer()
        {
            originalActive = SceneManager.GetActiveScene(); oldLock = Cursor.lockState; oldCursor = Cursor.visible;
            report = new Report { unityVersion = Application.unityVersion, maximumDeltaTime = Time.maximumDeltaTime };
            foreach (var path in new[] { SourceScene, SourceScene + ".meta", Manifest, Manifest + ".meta",
                "Assets/DesertRV/Runtime/JourneyMotor.cs", "Assets/DesertRV/Runtime/JourneyMotor.cs.meta",
                "Assets/DesertRV/Runtime/BeastActor.cs", "Assets/DesertRV/Runtime/BeastActor.cs.meta",
                "Assets/DesertRV/Runtime/MobileInputAdapter.cs", "Assets/DesertRV/Runtime/MobileInputAdapter.cs.meta",
                "Assets/DesertRV/Tests/PlayMode/JourneyVehicleContactFixPhysicsTests.cs", "Assets/DesertRV/Tests/PlayMode/JourneyVehicleContactFixPhysicsTests.cs.meta" }) Pin(path);
            Write(); VerifyDependencies();
            Assert.That(Application.isPlaying, Is.True);
            Assert.That(SceneManager.GetSceneByPath(SourceScene).isLoaded, Is.False, "SOURCE_ALREADY_LOADED");
            ownsLoad = true;
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(SourceScene, new LoadSceneParameters(LoadSceneMode.Additive));
            loaded = SceneManager.GetSceneByPath(SourceScene); ConfigureSavedRV();
            foreach (float dt in new[] { 1f / 60, 1f / 30, .2f })
            foreach (float direction in new[] { 1f, -1f })
            {
                Baseline(dt, direction);
                Synthetic(dt, direction, "pouncer", false);
                Synthetic(dt, direction, "two-pouncers", false);
                Synthetic(dt, direction, "armored", true);
            }
            WallAndRamControls();
            foreach (int count in new[] { 31, 32, 33 }) Capacity(count);
            Synthetic(1f / 60, 1, "deep-front", false);
            Synthetic(1f / 60, -1, "deep-front", false);
            Capacity(32, true); Capacity(33, true);
            EscapeBlockedByWall();
            // Yield only between finished isolated cases. Actors are disabled; no
            // automatic AI/input can race the manually observed production ticks.
            yield return null;
            NaturalApproach();
            GeometryChecks();
            report.anySyntheticLockReleased = report.cases.Any(c => c.placement == "synthetic-overlap" && c.liveStationary && c.deathConfirmed && c.released);
            report.regressionsPassed = RegressionPassed();
            report.status = "completed"; Write();
            Assert.That(report.cases.Count, Is.EqualTo(38), "CASE_COUNT");
            Assert.That(report.cases.Sum(c => c.frames.Count), Is.EqualTo(2500), "FRAME_COUNT");
            Assert.That(report.regressionsPassed, Is.True, "MOTOR_REGRESSION_FAILED");
        }

        void ConfigureSavedRV()
        {
            var roots = loaded.GetRootGameObjects();
            viewer = roots.SelectMany(r => r.GetComponentsInChildren(T("BodyViewer"), true)).Single();
            vehicle = (Transform)Field(viewer, "body"); inspectionWalker = ((CharacterController)Field(viewer, "walker")).gameObject;
            foreach (var r in vehicle.GetComponentsInChildren<Renderer>(true)) foreach (var m in r.sharedMaterials)
                if (m && !EditorUtility.IsPersistent(m) && !materials.Contains(m)) materials.Add(m);
            foreach (var b in roots.SelectMany(r => r.GetComponentsInChildren<MonoBehaviour>(true))) b.enabled = false;
            foreach (var c in roots.SelectMany(r => r.GetComponentsInChildren<Camera>(true))) c.enabled = false;
            foreach (var a in roots.SelectMany(r => r.GetComponentsInChildren<AudioListener>(true))) a.enabled = false;
            var nodes = vehicle.GetComponentsInChildren<Transform>(true);
            var forward = nodes.Single(t => t.name == "GEO-windscreen").GetComponent<Renderer>().bounds.center - vehicle.position;
            forward.y = 0; forward.Normalize(); var correction = Quaternion.FromToRotation(forward, Vector3.forward); var origin = vehicle.position;
            foreach (var root in roots) { root.transform.position = correction * (root.transform.position - origin); root.transform.rotation = correction * root.transform.rotation; }
            initialRotation = vehicle.rotation;
            foreach (var c in roots.SelectMany(r => r.GetComponentsInChildren<Collider>(true))) if (!c.transform.IsChildOf(vehicle)) c.enabled = false;
            road = new GameObject("Road surface"); SceneManager.MoveGameObjectToScene(road, loaded);
            road.transform.position = new Vector3(0, -.015f, 30); road.transform.localScale = new Vector3(8, .10f, 94); road.AddComponent<BoxCollider>();
            var manifest = AssetDatabase.LoadAssetAtPath(Manifest, T("JourneyContentManifest")); Assert.That(manifest, Is.Not.Null, "MANIFEST_MISSING");
            pouncerPrefab = (GameObject)Field(Field(manifest, "pouncer"), "prefab"); armoredPrefab = (GameObject)Field(Field(manifest, "armored"), "prefab");
            foreach (var prefab in new[] { pouncerPrefab, armoredPrefab })
            {
                Assert.That(prefab, Is.Not.Null, "CANDIDATE_PREFAB_MISSING"); var path = AssetDatabase.GetAssetPath(prefab); Pin(path); Pin(path + ".meta");
            }
            Physics.SyncTransforms();
            Assert.That(vehicle.GetComponentsInChildren<Collider>(true).Length, Is.EqualTo(17), "RETAINED_COLLIDER_COUNT");
            Assert.That(Object.FindObjectsByType<Collider>(FindObjectsSortMode.None).Where(c => c.enabled && c.gameObject.activeInHierarchy && !c.isTrigger).All(c => c.gameObject.scene == loaded), Is.True, "FOREIGN_ACTIVE_COLLIDER");
            foreach (var c in vehicle.GetComponentsInChildren<Collider>(true)) Register(c, "retained-rv");
            Register(road.GetComponent<Collider>(), "authored-road");
            var shell = nodes.Single(t => t.name == "GEO-coach_body_shell").GetComponent<Collider>();
            Assert.That(Vector3.Distance(shell.bounds.min, new Vector3(-1.14f, .62f, -2.91f)), Is.LessThan(.002f), "RETAINED_SHELL_MIN");
            Assert.That(Vector3.Distance(shell.bounds.max, new Vector3(1.14f, 2.75f, 3)), Is.LessThan(.002f), "RETAINED_SHELL_MAX");
        }

        Case Begin(string name, string placement, float dt, float throttle, bool ram = false)
        {
            DestroyHost(); vehicle.SetPositionAndRotation(Vector3.zero, initialRotation);
            host = new GameObject("Vehicle contact native fixture"); SceneManager.MoveGameObjectToScene(host, loaded);
            session = host.AddComponent(T("JourneySession")); ((Behaviour)session).enabled = false;
            adapter = (Component)Get(session, "Input"); state = Get(session, "State"); touch = Get(adapter, "State");
            var obj = new GameObject("Motor"); obj.transform.SetParent(host.transform, false); obj.SetActive(false); motor = obj.AddComponent(T("JourneyMotor"));
            Set(motor, "journey", session); Set(motor, "vehicle", vehicle); Set(motor, "view", Field(viewer, "view"));
            Set(motor, "localForward", vehicle.InverseTransformDirection(Vector3.forward));
            var nodes = vehicle.GetComponentsInChildren<Transform>(true);
            Set(motor, "doorHinge", nodes.Single(t => t.name == "RIG-entry_door_pivot")); Set(motor, "entryStep", nodes.Single(t => t.name == "GEO-entry_step"));
            foreach (var n in new[] { "ram", "arc", "roofCargo" }) Set(motor, n, Field(viewer, n == "roofCargo" ? n : n + "Module"));
            obj.SetActive(true); ((Behaviour)motor).enabled = false; walker = (CharacterController)Field(motor, "walker");
            ((Camera)Field(motor, "view")).GetComponent<AudioListener>().enabled = false;
            Call(adapter, "Sample"); Call(adapter, "AttachEditorReplay", host); Assert.That(Call(session, "StartJourney"), Is.True);
            Call(state, "SetControl", E("ControlMode", "Driving")); Call(session, "ApplyContext");
            if (ram) { Assert.That(Call(state, "TryCollect", "native-ram", E("ComponentPart", "RamPart")), Is.True); Assert.That(Call(state, "TryInstall", E("ComponentPart", "RamPart")), Is.True); }
            Call(motor, "ResetVehicle"); motor.GetType().GetEvent("ObstacleContact").AddEventHandler(motor, new Action<RaycastHit, float>((hit, speed) => events.Add(Describe(hit))));
            Physics.SyncTransforms();
            var result = new Case { name = name, placement = placement, dt = dt, throttle = throttle, ramInstalled = ram, start = vehicle.position };
            report.cases.Add(result); return result;
        }
        Component Spawn(bool armored, Vector3 at, string name)
        {
            var obj = Object.Instantiate(armored ? armoredPrefab : pouncerPrefab, at, Quaternion.identity); obj.name = name;
            SceneManager.MoveGameObjectToScene(obj, loaded); obj.transform.SetParent(host.transform, true);
            foreach (var b in obj.GetComponentsInChildren<Behaviour>(true)) if (!(b is Animator)) b.enabled = false;
            // CandidateArt fixtures establish the controller pose before manual
            // actor phases. Keep Animator enabled so production CrossFade remains valid.
            foreach (var animation in obj.GetComponentsInChildren<Animator>(true))
            { Assert.That(animation.applyRootMotion, Is.False, "CANDIDATE_ROOT_MOTION"); animation.enabled = true; animation.Rebind(); animation.Update(0); }
            var actor = obj.GetComponent(T("BeastActor")); Assert.That(actor, Is.Not.Null);
            Set(actor, "journey", session); Set(actor, "player", motor); Call(actor, "ResetActor");
            var cap = obj.GetComponent<CapsuleCollider>(); Assert.That(cap && cap.enabled && !cap.isTrigger && cap.direction == 1, Is.True, "CANDIDATE_CAPSULE_INVALID");
            Assert.That(obj.GetComponentsInChildren<Collider>(true).Length, Is.EqualTo(1), "CANDIDATE_COLLIDER_COUNT");
            Assert.That(Vector3.Distance(obj.transform.lossyScale, Vector3.one), Is.LessThan(.00001f));
            Physics.SyncTransforms(); Register(cap, armored ? "actual-armored" : "actual-pouncer"); actors.Add(actor); return actor;
        }
        void SetInput(float direction)
        {
            Call(adapter, "ReleaseAll"); Call(adapter, "SetEditorReplayFingers", host, Array.Empty<int>()); Call(adapter, "Sample");
            if (direction != 0) { Assert.That(Call(touch, "Begin", Finger, E("TouchControl", direction > 0 ? "Accelerate" : "Brake")), Is.True); Call(adapter, "SetEditorReplayFingers", host, new[] { Finger }); }
        }
        void Run(Case result, string phase, float direction, float seconds, bool keepHeld = false)
        {
            if (!keepHeld) SetInput(direction);
            else Assert.That((float)Get(adapter, "Throttle"), Is.EqualTo(direction), "HELD_INPUT_CHANGED");
            int frames = Mathf.CeilToInt(seconds / result.dt);
            for (int i = 0; i < frames; i++) result.frames.Add(Observe(result.frames.Count, phase, result.dt));
            result.end = vehicle.position; Write();
        }
        Frame Observe(int number, string phase, float dt)
        {
            Physics.SyncTransforms(); Call(adapter, "Sample");
            float speed = (float)Get(motor, "Speed"), throttle = Mathf.Clamp((float)Get(adapter, "Throttle"), -1, 1);
            float target = throttle >= 0 ? throttle * (float)Field(motor, "topSpeed") : throttle * (float)Field(motor, "topSpeed") * .38f;
            float atCast = Mathf.MoveTowards(speed, target, dt * (Mathf.Abs(throttle) < .05f ? 7 : 4.5f));
            Vector3 before = vehicle.position, forward = (Vector3)Get(motor, "Forward"), displacement = forward * atCast * dt;
            float distance = displacement.magnitude; var heading = Quaternion.LookRotation(forward); var center = before + Vector3.up * 1.45f;
            var frame = new Frame { frame = number, phase = phase, dt = dt, throttle = throttle, speedBefore = speed, speedAtCast = atCast,
                intendedDistance = distance, before = before, center = center, forward = forward, castExecuted = distance > .001f,
                state = Get(state, "Status").ToString(), control = Get(state, "Control").ToString(), powerConnected = (bool)Get(state, "PowerConnected"),
                overlaps = Physics.OverlapBox(center, Extents, heading, ~0, QueryTriggerInteraction.Ignore).Select(c => Register(c)).OrderBy(x => x).ToArray(),
                rawHits = Array.Empty<HitRow>(), allHits = Array.Empty<HitRow>(), motorBufferHits = Array.Empty<HitRow>() };
            if (frame.castExecuted)
            {
                frame.rawCount = Physics.BoxCastNonAlloc(center, Extents, displacement.normalized, raw, heading, distance + .10f, ~0, QueryTriggerInteraction.Ignore);
                var all = Physics.BoxCastAll(center, Extents, displacement.normalized, heading, distance + .10f, ~0, QueryTriggerInteraction.Ignore);
                Assert.That(all.Length, Is.LessThanOrEqualTo(phase == "capacity" ? 33 : 20), "ISOLATED_QUERY_BOUND");
                frame.allCount = all.Length; frame.rawSaturated = frame.rawCount == raw.Length;
                frame.rawHits = raw.Take(frame.rawCount).Select(Describe).ToArray(); frame.allHits = all.OrderBy(h => h.distance).Select(Describe).ToArray();
                float allowed = frame.rawSaturated ? 0 : distance;
                foreach (var hit in raw.Take(frame.rawCount).OrderBy(h => h.distance))
                {
                    if (hit.distance > allowed + .10f) break;
                    if (!hit.collider || hit.collider.transform.IsChildOf(vehicle) || hit.collider == walker || hit.normal.y > .65f) continue;
                    allowed = Mathf.Min(allowed, Mathf.Max(0, hit.distance - .10f));
                }
                frame.predictedAllowed = allowed; // Geometry-only prediction: intentionally never calls damage or substitutes for the actual motor.
            }
            events.Clear(); Call(motor, "Tick", dt); Call(adapter, "ConsumeFrame");
            frame.after = vehicle.position; frame.actualDistance = Vector3.Distance(before, frame.after); frame.speedAfter = (float)Get(motor, "Speed");
            frame.vehicleHealth = (int)Get(state, "VehicleHealth"); frame.obstacleEvents = events.ToArray();
            Assert.That(events.Count, Is.LessThanOrEqualTo(2), "ISOLATED_CONTACT_BOUND");
            if (frame.castExecuted) frame.motorBufferHits = ((RaycastHit[])Field(motor, "carHits")).Take(frame.rawCount).Select(Describe).ToArray();
            Physics.SyncTransforms(); return frame;
        }
        void Baseline(float dt, float sign)
        {
            var c = Begin("baseline-" + Mathf.RoundToInt(1 / dt) + "-" + (sign > 0 ? "W" : "S"), "no-beast", dt, sign);
            c.requiredLiveMove = true; Run(c, "baseline", sign, 1); c.baselineMoved = Vector3.Distance(c.start, c.end) > .2f; Write();
        }
        void Synthetic(float dt, float sign, string kind, bool armored)
        {
            var c = Begin(kind + "-" + Mathf.RoundToInt(1 / dt) + "-" + (sign > 0 ? "W" : "S"), "synthetic-overlap", dt, sign, true);
            c.requiredLiveBlock = kind == "deep-front" || (kind == "two-pouncers" && sign > 0);
            c.requiredLiveMove = !c.requiredLiveBlock;
            Spawn(armored, kind == "deep-front" ? new Vector3(0, 0, 2.5f) : new Vector3(1.25f, 0, 2.50f), "Synthetic " + kind + " A");
            if (kind == "two-pouncers") Spawn(false, new Vector3(.35f, 0, 2.9f), "Synthetic pouncer B");
            c.actorColliders = actors.Select(a => Register(a.GetComponent<Collider>())).ToArray();
            c.liveActorHealthBefore = actors.Select(a => (int)Get(a, "Health")).ToArray();
            Run(c, "live", sign, 1); c.liveStationary = Vector3.Distance(c.start, vehicle.position) < .005f;
            c.liveActorHealthAfter = actors.Select(a => (int)Get(a, "Health")).ToArray();
            c.liveActorsSurvived = actors.All(a => !(bool)Get(a, "Dead")) && c.liveActorHealthBefore.SequenceEqual(c.liveActorHealthAfter);
            foreach (var actor in actors) Call(actor, "TakeHit", 10000, Vector3.forward, false);
            c.deathConfirmed = actors.All(a => (bool)Get(a, "Dead") && !a.GetComponent<Collider>().enabled);
            Vector3 beforeDeathRun = vehicle.position; Run(c, "after-death-same-held-direction", sign, 1, true);
            c.released = Vector3.Distance(beforeDeathRun, vehicle.position) > .2f; Write();
        }
        GameObject Box(string name, Vector3 at, Vector3 size, bool self = false)
        {
            var obj = new GameObject(name); SceneManager.MoveGameObjectToScene(obj, loaded); obj.transform.SetParent(self ? vehicle : host.transform, true);
            obj.transform.position = at; obj.AddComponent<BoxCollider>().size = size; Register(obj.GetComponent<Collider>(), self ? "synthetic-self" : "synthetic-wall"); return obj;
        }
        void WallAndRamControls()
        {
            foreach (string mode in new[] { "wall-beast-behind", "front-ram", "front-no-ram", "reverse-ram-installed", "initial-wall-overlap" })
            {
                float sign = mode == "reverse-ram-installed" ? -1 : 1;
                var c = Begin(mode, "wall-and-ram-control", 1f / 60, sign, mode != "front-no-ram");
                if (mode == "wall-beast-behind") Box("Native nearest wall", new Vector3(0, 1.45f, 4.2f), new Vector3(4, 2.24f, .2f));
                if (mode == "initial-wall-overlap") Box("Native initial-overlap wall", new Vector3(1.0f, 1.45f, 2.5f), new Vector3(.2f, 2.24f, 1));
                else Spawn(false, new Vector3(0, 0, sign * 6), "Control pouncer");
                int health = actors.Count == 0 ? 0 : (int)Get(actors[0], "Health"); Run(c, "control", sign, 2);
                c.deathConfirmed = actors.Count > 0 && (bool)Get(actors[0], "Dead");
                c.wallHeld = mode == "wall-beast-behind" ? vehicle.position.z < 1.41f && (int)Get(actors[0], "Health") == health : mode == "initial-wall-overlap" && vehicle.position.magnitude < .005f;
                Write();
            }
        }
        void Capacity(int count, bool wall = false)
        {
            var c = Begin("capacity-" + count + (wall ? "-with-wall" : ""), wall ? "synthetic-mixed-buffer-wall" : "synthetic-self-buffer-saturation", 1f / 30, 1);
            c.requiredLiveMove = !wall; c.requiredLiveBlock = wall;
            if (wall) Box("Native capacity wall", new Vector3(0, 1.45f, 2.83f), new Vector3(4, 2.24f, .2f));
            c.requestedCapacity = count; var created = new List<GameObject>();
            // Fillers are self-colliders; the optional real wall must still block.
            // Add exactly enough to make the complete query count 31/32/33.
            for (int i = 0; i < 40; i++)
            {
                Physics.SyncTransforms(); c.actualCapacity = Physics.BoxCastAll(Vector3.up * 1.45f, Extents, Vector3.forward, Quaternion.identity, .105f, ~0, QueryTriggerInteraction.Ignore).Length;
                if (c.actualCapacity >= count) break;
                created.Add(Box("Native self capacity " + i, new Vector3(0, 1.45f, 0), Vector3.one * .02f, true));
            }
            Assert.That(c.actualCapacity, Is.EqualTo(count), "CAPACITY_COUNT_UNREACHABLE");
            Run(c, "capacity", 1, .2f); c.wallHeld = wall && vehicle.position.magnitude < .005f;
            foreach (var obj in created) Object.DestroyImmediate(obj); Physics.SyncTransforms(); Write();
        }
        void EscapeBlockedByWall()
        {
            var c = Begin("escape-against-wall", "synthetic-escape-with-wall", 1f / 60, -1, true);
            c.requiredLiveBlock = true;
            Spawn(false, new Vector3(.35f, 0, 2.9f), "Escapable front pouncer");
            Box("Native rear wall", new Vector3(0, 1.45f, -2.83f), new Vector3(4, 2.24f, .2f));
            c.actorColliders = actors.Select(a => Register(a.GetComponent<Collider>())).ToArray();
            c.liveActorHealthBefore = actors.Select(a => (int)Get(a, "Health")).ToArray();
            Run(c, "live", -1, 1); c.liveStationary = vehicle.position.magnitude < .005f;
            c.liveActorHealthAfter = actors.Select(a => (int)Get(a, "Health")).ToArray();
            c.liveActorsSurvived = actors.All(a => !(bool)Get(a, "Dead")) && c.liveActorHealthBefore.SequenceEqual(c.liveActorHealthAfter);
            foreach (var actor in actors) Call(actor, "TakeHit", 10000, Vector3.forward, false);
            c.deathConfirmed = actors.All(a => (bool)Get(a, "Dead") && !a.GetComponent<Collider>().enabled);
            Vector3 atDeath = vehicle.position; Run(c, "after-death-same-held-direction", -1, 1, true);
            c.released = Vector3.Distance(atDeath, vehicle.position) > .2f;
            c.wallHeld = vehicle.position.magnitude < .005f; Write();
        }

        // Enabled trigger proxy exists only in this native fixture. Both native
        // ComputePenetration colliders are enabled; production casts ignore triggers.
        // Actor geometry is the unchanged candidate capsule, including tilted axes.
        void GeometryChecks()
        {
            Geometry("pouncer-side-W", false, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, .2f, true);
            Geometry("pouncer-side-S", false, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, -.2f, true);
            Geometry("armored-side-W", true, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, .2f, true);
            Geometry("armored-side-S", true, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, -.2f, true);
            Geometry("pouncer-front-W", false, new Vector3(.35f, 0, 2.9f), Quaternion.identity, .2f, false);
            Geometry("pouncer-front-S", false, new Vector3(.35f, 0, 2.9f), Quaternion.identity, -.2f, true);
            Geometry("pouncer-front-long-W", false, new Vector3(.35f, 0, 2.9f), Quaternion.identity, 7, false);
            Geometry("pouncer-corner-W", false, new Vector3(1.2f, 0, 2.85f), Quaternion.identity, .2f, false);
            Geometry("pouncer-corner-S", false, new Vector3(1.2f, 0, 2.85f), Quaternion.identity, -.2f, true);
            Geometry("pouncer-deep-W", false, new Vector3(0, 0, 2.5f), Quaternion.identity, .2f, false);
            Geometry("pouncer-deep-S", false, new Vector3(0, 0, 2.5f), Quaternion.identity, -.2f, false);
            Geometry("pouncer-zero", false, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, 0, false);
            Geometry("pouncer-boundary-inside-S", false, new Vector3(0, 0, 3.0595f), Quaternion.identity, -.2f, true);
            Geometry("pouncer-boundary-outside-S", false, new Vector3(0, 0, 3.0605f), Quaternion.identity, -.2f, false);
            Geometry("pouncer-axis-epsilon-S", false, new Vector3(0, 0, 2.700001f), Quaternion.identity, -.2f, false);
            Geometry("pouncer-tilted-side-W", false, Vector3.zero, Quaternion.Euler(12, 33, 17), .2f, true, 0, 1.25f);
            Geometry("pouncer-tilted-side-S", false, Vector3.zero, Quaternion.Euler(12, 33, 17), -.2f, true, 0, 1.25f);
            Geometry("armored-tilted-front-W", true, Vector3.zero, Quaternion.Euler(25, -20, 14), .2f, false, 2, 2.9f);
            Geometry("armored-tilted-front-S", true, Vector3.zero, Quaternion.Euler(25, -20, 14), -.2f, true, 2, 2.9f);
            Geometry("pouncer-other-hit-S", false, new Vector3(.35f, 0, 2.9f), Quaternion.identity, -.2f, false, -1, 0, true);
            Geometry("pouncer-heading37-side-W", false, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, .2f, true, -1, 0, false, 37);
            Geometry("pouncer-heading37-side-S", false, new Vector3(1.25f, 0, 2.5f), Quaternion.identity, -.2f, true, -1, 0, false, 37);
            Geometry("pouncer-heading37-front-W", false, new Vector3(.35f, 0, 2.9f), Quaternion.identity, .2f, false, -1, 0, false, 37);
            Geometry("pouncer-heading37-front-S", false, new Vector3(.35f, 0, 2.9f), Quaternion.identity, -.2f, true, -1, 0, false, 37);
        }
        Vector3 AxisVector(Vector3 a, Vector3 b) => (Vector3)motor.GetType().GetMethod("CapsuleBoxVector", Instance).Invoke(motor, new object[] { a, b });
        void Capsule(Component actor, out Vector3 bottom, out Vector3 top, out float radius)
        {
            object[] values = { Vector3.zero, Vector3.zero, 0f };
            Assert.That((bool)actor.GetType().GetMethod("TryGetSweepCapsule", Instance).Invoke(actor, values), Is.True, "NATIVE_CAPSULE_UNAVAILABLE");
            bottom = (Vector3)values[0]; top = (Vector3)values[1]; radius = (float)values[2];
        }
        void Geometry(string name, bool armored, Vector3 at, Quaternion rotation, float travel, bool expected, int alignAxis = -1, float axisMinimum = 0, bool otherHit = false, float vehicleYaw = 0)
        {
            var fixture = Begin("geometry-oracle", "native-geometry-oracle", 1f / 60, 0);
            report.cases.Remove(fixture); // Geometry checks are separate from the 38 motor case inventory.
            var yaw = Quaternion.AngleAxis(vehicleYaw, Vector3.up); vehicle.rotation = yaw * initialRotation;
            var actor = Spawn(armored, yaw * at, "Native geometry capsule"); actor.transform.rotation = yaw * rotation;
            Capsule(actor, out var bottom, out var top, out float radius);
            if (alignAxis >= 0)
            {
                var shift = Vector3.zero; shift[alignAxis] = axisMinimum - Mathf.Min(bottom[alignAxis], top[alignAxis]);
                actor.transform.position += shift; Capsule(actor, out bottom, out top, out radius);
            }
            Vector3 center = vehicle.position + Vector3.up * 1.45f, forward = (Vector3)Get(motor, "Forward");
            var heading = Quaternion.LookRotation(forward); var inverse = Quaternion.Inverse(heading);
            var oracleObject = new GameObject("Native enabled trigger oracle"); oracleObject.transform.SetParent(host.transform, false);
            oracleObject.transform.SetPositionAndRotation(center, heading);
            var oracle = oracleObject.AddComponent<BoxCollider>(); oracle.size = Extents * 2; oracle.isTrigger = true;
            var cap = actor.GetComponent<CapsuleCollider>(); Physics.SyncTransforms();
            bool initial = Physics.ComputePenetration(oracle, center, heading, cap, cap.transform.position, cap.transform.rotation, out _, out float initialDepth);
            bool final = Physics.ComputePenetration(oracle, center + forward * travel, heading, cap, cap.transform.position, cap.transform.rotation, out _, out float finalDepth);
            Vector3 a = inverse * (bottom - center), b = inverse * (top - center), offset = Vector3.forward * travel;
            bool allowed = (bool)motor.GetType().GetMethod("CanLeaveInitialBeastOverlap", Instance).Invoke(motor, new object[] { actor, otherHit ? (Collider)oracle : cap, center, heading, travel });
            var check = new GeometryCheck { name = name, kind = armored ? "armored" : "pouncer", travel = travel,
                initialOverlap = initial, initialDepth = initialDepth, finalOverlap = final, finalDepth = finalDepth,
                allowed = allowed, expectedAllowed = expected, startAxisDistance = AxisVector(a, b).magnitude,
                endAxisDistance = AxisVector(a - offset, b - offset).magnitude, radius = radius, endpoint1 = bottom, endpoint2 = top, boxCenter = center, boxForward = forward };
            bool nativeAgreement = initial == (check.startAxisDistance < radius) && final == (check.endAxisDistance < radius);
            if (initial && check.startAxisDistance > .00001f) nativeAgreement &= Mathf.Abs(initialDepth - (radius - check.startAxisDistance)) < .0002f;
            if (final && check.endAxisDistance > .00001f) nativeAgreement &= Mathf.Abs(finalDepth - (radius - check.endAxisDistance)) < .0002f;
            check.passed = allowed == expected && nativeAgreement && (!allowed || (initial && finalDepth <= initialDepth + .0002f && check.endAxisDistance + .00001f >= check.startAxisDistance));
            report.geometryChecks.Add(check); Write();
        }
        bool RegressionPassed()
        {
            if (report.cases.Count != 38 || report.cases.Sum(c => c.frames.Count) != 2500 || report.geometryChecks.Count != 24 || report.geometryChecks.Any(g => !g.passed)) return false;
            foreach (var c in report.cases)
            {
                float primaryTravel = c.frames.Where(f => f.phase == "live" || f.phase == "capacity" || f.phase == "baseline").Sum(f => f.actualDistance);
                if (c.requiredLiveMove && primaryTravel <= (c.requestedCapacity > 0 ? .02f : .2f)) return false;
                if (c.requiredLiveBlock && primaryTravel >= .005f) return false;
                if (c.placement == "no-beast" && !c.baselineMoved) return false;
                if (c.placement == "synthetic-overlap" && (!c.liveActorsSurvived || !c.deathConfirmed || !c.released)) return false;
                if (c.requestedCapacity > 0)
                {
                    if (c.actualCapacity != c.requestedCapacity || c.frames.Any(f => f.allCount != c.requestedCapacity || f.rawCount != Math.Min(32, c.requestedCapacity))) return false;
                    if (c.placement == "synthetic-self-buffer-saturation" && c.frames.Any(f => f.allHits.Any(h => !h.self))) return false;
                    if (c.placement == "synthetic-mixed-buffer-wall" && (!c.wallHeld || c.frames.Any(f => !f.allHits.Any(h => !h.self && !h.walker && !h.upward && !h.beast && h.distance > 0 && h.distance < .1f)))) return false;
                }
            }
            Case named(string name) => report.cases.Single(c => c.name == name);
            var behind = named("wall-beast-behind");
            if (!behind.wallHeld || behind.deathConfirmed || behind.end.z < 1.25f || behind.end.z > 1.41f) return false;
            var ram = named("front-ram");
            if (!ram.deathConfirmed || ram.end.z < 6 || !ram.frames.Any(f => f.speedAtCast > 3 && f.allHits.Any(h => h.beast && !h.dead && h.distance > 0 && Vector3.Dot(h.point - f.before, f.forward) > 1.8f && Vector3.Dot(-h.normal, f.forward) > .45f))) return false;
            foreach (var name in new[] { "front-no-ram", "reverse-ram-installed" })
            { var c = named(name); if (c.deathConfirmed || Mathf.Abs(c.end.z) < 2.7f || Mathf.Abs(c.end.z) > 2.95f) return false; }
            var initialWall = named("initial-wall-overlap");
            if (!initialWall.wallHeld || initialWall.frames.Sum(f => f.actualDistance) >= .005f) return false;
            var escape = named("escape-against-wall");
            if (!escape.wallHeld || !escape.liveActorsSurvived || !escape.deathConfirmed || escape.released ||
                !escape.frames.Any(f => f.phase == "live" && f.allHits.Any(h => h.beast && h.distance == 0) && f.allHits.Any(h => !h.self && !h.walker && !h.upward && !h.beast && h.distance > 0 && h.distance < .1f))) return false;
            return true;
        }

        void NaturalApproach()
        {
            var c = Begin("natural-production-update", "exterior-spawn-production-ai", 1f / 60, -1, true);
            Spawn(false, new Vector3(2.3f, 0, 6), "Natural pouncer A"); Spawn(false, new Vector3(3.1f, 0, 5.2f), "Natural pouncer B");
            c.actorColliders = actors.Select(a => Register(a.GetComponent<Collider>())).ToArray();
            float observedDelta = Mathf.Min(Time.deltaTime, .1f); Assert.That(observedDelta, Is.GreaterThan(0), "NATURAL_DELTA_ZERO");
            var update = T("BeastActor").GetMethod("Update", Instance);
            for (int i = 0; i < 720; i++)
            {
                int before = (int)Get(state, "VehicleHealth"); foreach (var a in actors) { update.Invoke(a, null); Physics.SyncTransforms(); }
                var overlapping = Physics.OverlapBox(vehicle.position + Vector3.up * 1.45f, Extents, Quaternion.LookRotation((Vector3)Get(motor, "Forward")), ~0, QueryTriggerInteraction.Ignore)
                    .Where(col => col.GetComponentInParent(T("BeastActor")) != null).Select(col => Register(col)).ToArray();
                c.approach.Add(new ApproachFrame { step = i, actualUpdateDelta = observedDelta, healthBefore = before, healthAfter = (int)Get(state, "VehicleHealth"),
                    positions = actors.Select(a => a.transform.position).ToArray(), phases = actors.Select(a => Get(a, "Phase").ToString()).ToArray(), proxyOverlaps = overlapping });
                if (overlapping.Length > 0) { report.anyNaturalProxyOverlap = true; c.outcome = "natural-proxy-overlap"; break; }
                if ((int)Get(state, "VehicleHealth") < before) { c.outcome = "natural-vehicle-contact-without-proxy-overlap"; break; }
                if (i == 719) c.outcome = "bounded-approach-ended-without-contact";
            }
            Run(c, "natural-after-approach-W", 1, 1); Run(c, "natural-after-approach-S", -1, 1);
            c.liveStationary = c.frames.Sum(f => f.actualDistance) < .005f;
            foreach (var actor in actors) Call(actor, "TakeHit", 10000, Vector3.forward, false);
            c.deathConfirmed = actors.All(a => (bool)Get(a, "Dead") && !a.GetComponent<Collider>().enabled);
            Vector3 deadStart = vehicle.position; Run(c, "natural-after-death-S", -1, 1, true); c.released = Vector3.Distance(deadStart, vehicle.position) > .2f; Write();
        }

        HitRow Describe(RaycastHit h)
        {
            var beast = h.collider ? h.collider.GetComponentInParent(T("BeastActor")) : null;
            return new HitRow { collider = h.collider ? Register(h.collider) : 0, distance = h.distance, point = h.point, normal = h.normal,
                self = h.collider && h.collider.transform.IsChildOf(vehicle), walker = h.collider == walker, upward = h.normal.y > .65f,
                beast = beast != null, dead = beast != null && (bool)Get(beast, "Dead") };
        }
        int Register(Collider c, string role = "observed")
        {
            if (ids.TryGetValue(c, out int id)) return id; Assert.That(ids.Count, Is.LessThan(512), "COLLIDER_BOUND");
            id = ids.Count + 1; ids.Add(c, id); var names = new List<string>(); for (var t = c.transform; t; t = t.parent) names.Insert(0, t.name);
            var row = new ColliderRow { id = id, hierarchy = string.Join("/", names), type = c.GetType().Name, role = role, trigger = c.isTrigger, min = c.bounds.min, max = c.bounds.max };
            Assert.That(row.hierarchy.Length, Is.LessThan(512), "HIERARCHY_BOUND");
            if (c is MeshCollider m && m.sharedMesh) { row.convex = m.convex; row.mesh = AssetDatabase.GetAssetPath(m.sharedMesh); row.meshGuid = AssetDatabase.AssetPathToGUID(row.mesh); if (!string.IsNullOrEmpty(row.mesh)) Pin(row.mesh); }
            if (c is CapsuleCollider cap) { row.capsuleCenter = cap.center; row.capsuleRadius = cap.radius; row.capsuleHeight = cap.height; }
            report.colliders.Add(row); return id;
        }
        static string Hash(string path) { using (var sha = SHA256.Create()) using (var stream = File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant(); }
        void Pin(string path) { Assert.That(SafePath(path) && File.Exists(path), Is.True, "PIN_MISSING_OR_UNSAFE"); if (!report.sourceFiles.Any(p => p.path == path)) report.sourceFiles.Add(new FilePin { path = path, sha256 = Hash(path) }); }
        static bool SafePath(string path) => !string.IsNullOrEmpty(path) && !Path.IsPathRooted(path) && !path.Contains("\\") && !path.Any(char.IsControl) && path.Split('/').All(p => p != "" && p != "." && p != "..");
        void VerifyDependencies()
        {
            var check = report.dependencyCheck; check.status = "checking";
            try
            {
                Pin(InputPath); Pin(InputHash); check.inputSha256 = Hash(InputPath); Assert.That(File.ReadAllText(InputHash).Trim(), Is.EqualTo(check.inputSha256), "INPUT_HASH");
                var input = JsonUtility.FromJson<ConsumerInput>(File.ReadAllText(InputPath)); Assert.That(input.schema, Is.EqualTo(1)); Assert.That(input.producerRunId, Is.EqualTo("38054694730"));
                Assert.That(input.status, Is.EqualTo("VERIFIED_ED21_PREPARED_ASSETS_MOTOR_FIX_CONSUMER_NOT_APPROVED"));
                Assert.That(input.producerCommit, Is.EqualTo("ed21b214f327b3ec439b9b3d7fec6b41a16d8a85"));
                Assert.That(input.currentProductionCommit, Is.EqualTo(input.consumerCommit));
                Assert.That(input.producerArtifactSha256, Is.EqualTo("1e9f5e73417b7454f5e85e5bfa426499c93cb045e383da6467e49eca64d878b1"));
                Assert.That(input.consumerCommit, Is.EqualTo(Environment.GetEnvironmentVariable("GITHUB_SHA")), "CONSUMER_IDENTITY");
                Assert.That(input.dependencyChanges.Length, Is.EqualTo(1), "DEPENDENCY_CHANGE_COUNT");
                var change = input.dependencyChanges[0];
                Assert.That(change.path, Is.EqualTo("Assets/DesertRV/Runtime/JourneyMotor.cs"));
                Assert.That(change.before.sha256, Is.EqualTo("7f12f78f5fee78f03aac4ea32dd53e3ed9336d0866d19f750df4496f9e310397"));
                Assert.That(change.before.bytes, Is.EqualTo(12486));
                Assert.That(change.after.sha256, Is.EqualTo(Hash(change.path)));
                Assert.That(change.after.bytes, Is.EqualTo(new FileInfo(change.path).Length));
                var changedRow = input.dependencies.Single(d => d.path == change.path);
                Assert.That(changedRow.sha256, Is.EqualTo(change.after.sha256)); Assert.That(changedRow.bytes, Is.EqualTo(change.after.bytes));
                Assert.That(input.dependencies.Length, Is.EqualTo(796)); Assert.That(input.dependencies.All(d => SafePath(d.path)), Is.True);
                var owner = Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor", true);
                var snapshot = owner.GetMethod("DependencySnapshot", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
                check.actualDependencies = ((Array)snapshot.Invoke(null, null)).Cast<object>().Select(d => new DependencyRow { path = (string)Field(d, "path"), sha256 = (string)Field(d, "sha256"), bytes = (long)Field(d, "bytes"), kind = (string)Field(d, "kind"), packageName = (string)Field(d, "packageName"), packageVersion = (string)Field(d, "packageVersion") }).ToArray();
                Assert.That(check.actualDependencies.All(d => SafePath(d.path)), Is.True, "UNSAFE_DEPENDENCY_PATH");
                check.expectedCount = input.dependencies.Length; check.actualCount = check.actualDependencies.Length;
                var expected = input.dependencies.ToDictionary(d => d.path); var actual = check.actualDependencies.ToDictionary(d => d.path);
                check.mismatches = expected.Keys.Union(actual.Keys).Where(p => !expected.ContainsKey(p) || !actual.ContainsKey(p) || JsonUtility.ToJson(expected[p]) != JsonUtility.ToJson(actual[p])).OrderBy(p => p).ToArray();
                Assert.That(check.actualCount, Is.EqualTo(796)); Assert.That(check.actualDependencies.Count(d => d.kind == "package"), Is.EqualTo(24)); Assert.That(check.mismatches, Is.Empty, "NATIVE_DEPENDENCY_MISMATCH");
                check.passed = true; check.status = "verified-native-closure";
            }
            catch { check.status = "failed"; check.failureCode = "DEPENDENCY_VERIFICATION_FAILED"; report.failureCode = check.failureCode; throw; }
            finally { Write(); }
        }
        void Write()
        {
            Assert.That(report.cases.Sum(c => c.frames.Count), Is.LessThanOrEqualTo(2520), "FRAME_BOUND");
            var json = JsonUtility.ToJson(report, false); Assert.That(System.Text.Encoding.UTF8.GetByteCount(json), Is.LessThan(64 * 1024 * 1024), "REPORT_BOUND");
            Directory.CreateDirectory(Path.GetDirectoryName(Output)); File.WriteAllText(Output, json + "\n");
        }
        void DestroyHost()
        {
            if (adapter && host) { Call(adapter, "DetachEditorReplay", host); if (report != null) report.replayDetached = !(bool)Get(adapter, "EditorReplayActive"); }
            if (host) Object.DestroyImmediate(host); actors.Clear(); host = null; adapter = null; motor = null;
        }
        [UnityTearDown] public IEnumerator Cleanup()
        {
            DestroyHost(); if (road) Object.DestroyImmediate(road); if (inspectionWalker) Object.DestroyImmediate(inspectionWalker);
            if (originalActive.IsValid() && originalActive.isLoaded) SceneManager.SetActiveScene(originalActive);
            if (ownsLoad && !loaded.IsValid()) loaded = SceneManager.GetSceneByPath(SourceScene);
            if (ownsLoad && loaded.IsValid() && loaded.isLoaded) yield return SceneManager.UnloadSceneAsync(loaded);
            foreach (var material in materials) if (material) Object.DestroyImmediate(material);
            Cursor.lockState = oldLock; Cursor.visible = oldCursor;
            if (report != null) { report.sceneUnloaded = !SceneManager.GetSceneByPath(SourceScene).isLoaded; report.sourceFilesUnchanged = report.sourceFiles.All(p => File.Exists(p.path) && Hash(p.path) == p.sha256); Write(); Assert.That(report.sceneUnloaded && report.sourceFilesUnchanged, Is.True, "CLEANUP_OR_SOURCE_MUTATION"); }
            ids.Clear(); materials.Clear();
        }
    }
}
#endif
