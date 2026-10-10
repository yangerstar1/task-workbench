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
    // A native collision reproduction, not OS-keyboard or rendered-player acceptance.
    // The entire saved RV is retained. Only the surrounding world is isolated, with
    // the exact Road surface authored by JourneySceneAuthoring.DressEnvironment.
    // No scene/asset is saved and no production controller/collider is modified.
    public sealed class JourneyCabinEntryPhysicsTests
    {
        const string SourceScene = "Assets/DesertRV/Scenes/BodyStudy.unity";
        const string AuthorSource = "Assets/DesertRV/Editor/JourneySceneAuthoring.cs";
        const string MotorSource = "Assets/DesertRV/Runtime/JourneyMotor.cs";
        const string AdapterSource = "Assets/DesertRV/Runtime/MobileInputAdapter.cs";
        const string ReportPath = "JourneyEvidence/CabinEntry/native-entry-probe.json";
        const int MoveFinger = 43001, MaxFrames = 450, MaxContacts = 8, MaxRegressionFrames = 240;
        const BindingFlags Fields = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Get(object target, string name) => target.GetType().GetProperty(name).GetValue(target);
        static object Field(object target, string name) => target.GetType().GetField(name, Fields).GetValue(target);
        static void Set(object target, string name, object value) => target.GetType().GetField(name, Fields).SetValue(target, value);
        static object Call(object target, string name, params object[] args) => target.GetType().GetMethod(name).Invoke(target, args);
        static object E(string type, string value) => Enum.Parse(T(type), value);

        [Serializable] public sealed class FilePin { public string path, sha256; }
        [Serializable] public sealed class ColliderRecord
        {
            public int id; public string hierarchy, type, meshAsset, meshGuid, meshLocalId, authoredBy;
            public bool enabled, active, trigger, convex; public Vector3 min, max;
        }
        [Serializable] public sealed class Contact
        { public int collider; public Vector3 point, normal, moveDirection; public float moveLength; }
        [Serializable] public sealed class Sample
        {
            public int frame, flags, supportCollider, droppedContacts;
            public string phase; public float elapsed, delta, footHeight, intendedDistance, forwardDistance, doorAngle, verticalSpeedBefore, verticalSpeedAfter;
            public Vector3 position, supportPoint; public bool groundedBefore, groundedAfter, insideCabin;
            public Contact[] contacts;
        }
        [Serializable] public sealed class CaseResult
        {
            public string name, outcome = "incomplete"; public float delta;
            public Vector3 exit, end; public bool exited, lowerSupported, upperSupported, floorSupported, enteredCabin;
            public int firstSideContactFrame = -1, firstConstrainedFrame = -1, firstPersistentBlockFrame = -1;
            public List<Sample> frames = new List<Sample>();
            public List<Regression> regressions = new List<Regression>();
        }
        // Entry keeps every original frame and its bounded detailed contact payload.
        // Regression frames are compact all-callback summaries, not sampled frames.
        [Serializable] public sealed class RegressionFrame
        {
            public int frame, flags, supportCollider, sideCollider, contactCount;
            public string phase; public Vector3 position, sidePoint, sideNormal;
            public bool grounded, insideCabin;
            public float verticalSpeed, intendedDistance, forwardDistance;
        }
        [Serializable] public sealed class DriverCycle
        {
            public bool enterAttempted, enterSucceeded, exitAttempted, exitSucceeded;
            public string controlBefore, controlAfterEnter, controlAfterExit, contextBefore, contextAfterEnter, contextAfterExit;
            public bool controllerBefore, controllerAfterEnter, controllerAfterExit;
            public Vector3 positionBefore, positionAfterEnter, positionAfterExit;
        }
        [Serializable] public sealed class Regression
        {
            public string name, outcome = "incomplete"; public Vector3 start, end; public bool standardReset;
            public List<RegressionFrame> frames = new List<RegressionFrame>();
            public List<DriverCycle> driver = new List<DriverCycle>();
        }
        [Serializable] public sealed class ControllerRecord
        { public float height, radius, stepOffset, skinWidth, slopeLimit, minMoveDistance; public Vector3 center; }
        [Serializable] public sealed class Report
        {
            public int schemaVersion = 2;
            public string status = "fixture-incomplete", unityVersion, fixture = "saved-RV-with-reconstructed-authored-road";
            public string referenceRun = "38034314713";
            public string referenceBootstrapSha256 = "a31e108cf90a6244847d414670e4922150c73f45d38d6365cb3f795ed728d09f";
            public string referenceRegionSha256 = "ee6ded8b1e4c6284f6d40218a5b7b3768c95b2b4fee23c46d3f09162880e87e0";
            public string sourceScene = SourceScene, route = "standard-exit; settle-1s; held-forward-max-6s; stop-on-cabin-floor";
            public string regressionRoute = "backward-to-standard-exit; road-settle-1s; real-driver-cycle; road-strafe-rear-1.5m; shell-push-2s";
            public float maximumDeltaTime; public bool referenceGeometryMatched, allEntered, allRegressionsPassed, replayDetached, sceneUnloaded, sourceFilesUnchanged;
            public ControllerRecord controller;
            public int lowerCollider, upperCollider, floorCollider, roadCollider, savedRvColliderCount;
            public List<FilePin> sourceFiles = new List<FilePin>();
            public List<ColliderRecord> colliders = new List<ColliderRecord>();
            public List<CaseResult> cases = new List<CaseResult>();
        }

        Scene loadedScene;
        Scene originalActive;
        GameObject host, road, inspectionWalker;
        Component session, adapter, motor;
        object inputState, state;
        CharacterController walker;
        Transform vehicle;
        JourneyEntryContactProbe observer;
        Report report;
        CursorLockMode originalLock;
        bool originalCursor;
        bool ownsSourceLoad;
        readonly Dictionary<Collider, int> colliderIds = new Dictionary<Collider, int>();
        readonly List<Contact> contacts = new List<Contact>();
        readonly List<Material> transientMaterials = new List<Material>();
        int droppedContacts, contactCount;
        Collider shellCollider;
        Contact sideContact;
        Vector3 observedDirection;

        [UnityTest] public IEnumerator RealRV_StandardExitToCabin_AllTimesteps()
        {
            originalActive = SceneManager.GetActiveScene();
            originalLock = Cursor.lockState; originalCursor = Cursor.visible;
            report = new Report { unityVersion = Application.unityVersion, maximumDeltaTime = Time.maximumDeltaTime };
            foreach (string path in new[] { SourceScene, SourceScene + ".meta", AuthorSource, MotorSource, AdapterSource }) Pin(path);
            WriteReport();
            Assert.That(Application.isPlaying, Is.True);
            Assert.That(SceneManager.GetSceneByPath(SourceScene).isLoaded, Is.False, "The saved source must not already be open in this isolated test project.");
            // An ordinary additive runtime scene supports native CharacterController collision.
            // This does not create a PreviewScene and never calls SaveScene.
            ownsSourceLoad = true;
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(SourceScene, new LoadSceneParameters(LoadSceneMode.Additive));
            loadedScene = SceneManager.GetSceneByPath(SourceScene);
            ConfigureFixture();
            foreach (float delta in new[] { 1f / 60, 1f / 30, .1f, .2f, 1f / 3 })
            {
                RunCase(delta);
                WriteReport(); // Preserve all completed cases even if a later case/teardown fails.
            }
            report.allEntered = report.cases.All(c => c.enteredCabin);
            report.allRegressionsPassed = report.cases.All(c => c.regressions.Count == 4 && c.regressions.All(r => r.outcome == "passed"));
            report.status = "completed";
            WriteReport(); // Evidence exists before traversal assertions, including failures.
            Assert.That(report.cases, Has.Count.EqualTo(5));
            Assert.That(report.allEntered && report.allRegressionsPassed, Is.True,
                "Native RV entry or movement regression failed; all cadence observations are in " + ReportPath);
        }

        void ConfigureFixture()
        {
            var roots = loadedScene.GetRootGameObjects();
            var viewer = roots.SelectMany(r => r.GetComponentsInChildren(T("BodyViewer"), true)).Single();
            vehicle = (Transform)Field(viewer, "body");
            inspectionWalker = ((CharacterController)Field(viewer, "walker")).gameObject;
            // BodyViewer.Awake creates two non-asset render-material copies. Own their cleanup.
            foreach (var renderer in vehicle.GetComponentsInChildren<Renderer>(true))
                foreach (var material in renderer.sharedMaterials)
                    if (material && !EditorUtility.IsPersistent(material) && !transientMaterials.Contains(material)) transientMaterials.Add(material);
            foreach (var behaviour in roots.SelectMany(r => r.GetComponentsInChildren<MonoBehaviour>(true))) behaviour.enabled = false;
            foreach (var camera in roots.SelectMany(r => r.GetComponentsInChildren<Camera>(true))) camera.enabled = false;
            foreach (var listener in roots.SelectMany(r => r.GetComponentsInChildren<AudioListener>(true))) listener.enabled = false;
            // Same saved-RV frame correction as JourneySceneAuthoring.AuthorCandidateScenes.
            var nodes = vehicle.GetComponentsInChildren<Transform>(true);
            Vector3 forward = nodes.Single(t => t.name == "GEO-windscreen").GetComponent<Renderer>().bounds.center - vehicle.position;
            forward.y = 0; forward.Normalize();
            Quaternion correction = Quaternion.FromToRotation(forward, Vector3.forward);
            Vector3 origin = vehicle.position;
            foreach (var root in roots)
            { root.transform.position = correction * (root.transform.position - origin); root.transform.rotation = correction * root.transform.rotation; }
            // Source terrain is replaced in the actual authored journey too. Retain every
            // RV collider (including the true doorway mesh), never its enclosing proxy box.
            foreach (var collider in roots.SelectMany(r => r.GetComponentsInChildren<Collider>(true)))
                if (!collider.transform.IsChildOf(vehicle)) collider.enabled = false;
            road = new GameObject("Road surface"); SceneManager.MoveGameObjectToScene(road, loadedScene);
            road.transform.position = new Vector3(0, -.015f, 30); road.transform.localScale = new Vector3(8, .10f, 94);
            var roadCollider = road.AddComponent<BoxCollider>();

            host = new GameObject("Native RV entry fixture"); SceneManager.MoveGameObjectToScene(host, loadedScene);
            session = host.AddComponent(T("JourneySession")); ((Behaviour)session).enabled = false;
            adapter = (Component)Get(session, "Input"); state = Get(session, "State"); inputState = Get(adapter, "State");
            var motorObject = new GameObject("Motor"); motorObject.transform.SetParent(host.transform, false); motorObject.SetActive(false);
            motor = motorObject.AddComponent(T("JourneyMotor"));
            Set(motor, "journey", session); Set(motor, "vehicle", vehicle); Set(motor, "view", Field(viewer, "view"));
            Set(motor, "localForward", vehicle.InverseTransformDirection(Vector3.forward));
            Set(motor, "doorHinge", nodes.Single(t => t.name == "RIG-entry_door_pivot"));
            Set(motor, "entryStep", nodes.Single(t => t.name == "GEO-entry_step"));
            foreach (string name in new[] { "ram", "arc", "roofCargo" }) Set(motor, name, Field(viewer, name == "roofCargo" ? name : name + "Module"));
            motorObject.SetActive(true); ((Behaviour)motor).enabled = false;
            ((Camera)Field(motor, "view")).GetComponent<AudioListener>().enabled = false;
            walker = (CharacterController)Field(motor, "walker");
            observer = walker.gameObject.AddComponent<JourneyEntryContactProbe>(); observer.Hit = RecordContact;
            Call(adapter, "Sample"); Call(adapter, "AttachEditorReplay", host);
            Assert.That(Call(session, "StartJourney"), Is.True);
            Call(motor, "ResetVehicle"); Physics.SyncTransforms();
            report.controller = new ControllerRecord { height = walker.height, radius = walker.radius, center = walker.center,
                stepOffset = walker.stepOffset, skinWidth = walker.skinWidth, slopeLimit = walker.slopeLimit, minMoveDistance = walker.minMoveDistance };
            var savedColliders = vehicle.GetComponentsInChildren<Collider>(true);
            report.savedRvColliderCount = savedColliders.Length;
            foreach (var collider in savedColliders.OrderBy(c => Hierarchy(c.transform))) Register(collider);
            report.lowerCollider = Register(nodes.Single(t => t.name == "GEO-entry_step_lower").GetComponent<Collider>());
            report.upperCollider = Register(nodes.Single(t => t.name == "GEO-entry_step").GetComponent<Collider>());
            report.floorCollider = Register(nodes.Single(t => t.name == "GEO-interior_floor").GetComponent<Collider>());
            report.roadCollider = Register(roadCollider);
            report.colliders.Single(c => c.id == report.roadCollider).authoredBy = AuthorSource + ":DressEnvironment/Road surface";
            WriteReport();
            // Independent values decoded from the same-run generated JourneyBootstrap
            // and FirstStation, whose hashes are named in the report. These checks bind
            // the reconstructed fixture to that scene's real meshes and world bounds.
            MatchReference(report.lowerCollider, "ef7778cf6f9694d46bbbcffb577837e9", "632f56aceaae30363bacc186ae22b608ef8d0c83ec0ba74a4c3849618c386eb2",
                new Vector3(-1.735f, .2425f, .23f), new Vector3(-1.385f, .3175f, .97f));
            MatchReference(report.upperCollider, "fb5bb4e2e4fae364092b0b4dc2d8f0d4", "c2de71bc4a2d41dada3548fa0f85d2fa9659c07e12ba5969ddd1f76b464cb407",
                new Vector3(-1.505f, .505f, .21f), new Vector3(-1.115f, .595f, .99f));
            MatchReference(report.floorCollider, "e9a2e1feb527207478bf9ac28f3aa9c6", "32dd53d9b4ede2264aa87ba3ab3c191bd5acedb530f208b82a3a5e329af1eb78",
                new Vector3(-1.055f, .725f, -2.69f), new Vector3(1.055f, .805f, 2.53f));
            shellCollider = nodes.Single(t => t.name == "GEO-coach_body_shell").GetComponent<Collider>();
            MatchReference(Register(shellCollider),
                "6cb9559a22d7b0748ac2ded1a560c3d5", "dd7cf5938fe8f164e3f6383639218ef9c0aec1b456d7cfc1e4585afdfe71983b",
                new Vector3(-1.14f, .62f, -2.91f), new Vector3(1.14f, 2.75f, 3));
            MatchReference(Register(nodes.Single(t => t.name == "GEO-entry_door").GetComponent<Collider>()),
                "c5ea368c2cfc10a48a34b5f8a0daf016", "f037f116d03052759674cf859dd3b8c07b7a1dc7df663ae506dc84a2e7b962da",
                new Vector3(-1.1585f, .7285f, .261f), new Vector3(-1.1155f, 2.5715f, .939f));
            AssertBounds(report.colliders.Single(c => c.id == report.roadCollider), new Vector3(-4, -.065f, -17), new Vector3(4, .035f, 77));
            report.referenceGeometryMatched = true; WriteReport();
        }

        void MatchReference(int id, string guid, string sha256, Vector3 min, Vector3 max)
        {
            var row = report.colliders.Single(c => c.id == id);
            Assert.That(row.meshGuid, Is.EqualTo(guid));
            Assert.That(report.sourceFiles.Single(p => p.path == row.meshAsset).sha256, Is.EqualTo(sha256));
            Assert.That(row.enabled && row.active && !row.trigger && !row.convex, Is.True);
            AssertBounds(row, min, max);
        }
        static void AssertBounds(ColliderRecord row, Vector3 min, Vector3 max)
        {
            Assert.That(Vector3.Distance(row.min, min), Is.LessThan(.002f), row.hierarchy + " minimum differs from the saved journey.");
            Assert.That(Vector3.Distance(row.max, max), Is.LessThan(.002f), row.hierarchy + " maximum differs from the saved journey.");
        }

        void RunCase(float delta)
        {
            var result = new CaseResult { name = "fps-" + Mathf.RoundToInt(1 / delta), delta = delta };
            report.cases.Add(result);
            Call(adapter, "ReleaseAll"); Call(adapter, "SetEditorReplayFingers", host, Array.Empty<int>()); Call(adapter, "Sample");
            Call(state, "SetControl", E("ControlMode", "Driving")); Call(session, "ApplyContext");
            Call(motor, "ResetVehicle"); Physics.SyncTransforms();
            result.exited = (bool)Call(motor, "TryExitVehicle");
            result.exit = walker.transform.position;
            if (!result.exited)
            {
                result.outcome = "exit-rejected"; result.end = result.exit;
                RunRegressions(result, delta); return;
            }
            Vector3 inward = Quaternion.Euler(0, (float)Field(motor, "yaw"), 0) * Vector3.forward;
            float elapsed = 0;
            // Let the ordinary door animation finish. The player stays at the standard
            // exit while gravity grounds the unchanged controller; no position writes.
            for (int i = 0; i < Mathf.CeilToInt(1 / delta); i++) Capture(result, "settle", elapsed += delta, delta, inward, false);
            Assert.That(Call(inputState, "Begin", MoveFinger, E("TouchControl", "Move")), Is.True);
            Call(inputState, "Move", MoveFinger, 0f, 1f);
            Call(adapter, "SetEditorReplayFingers", host, new[] { MoveFinger });
            int constrainedStart = -1; float constrainedDuration = 0;
            for (int i = 0; i < Mathf.CeilToInt(6 / delta); i++)
            {
                var sample = Capture(result, "forward", elapsed += delta, delta, inward, true);
                bool side = (sample.flags & (int)CollisionFlags.Sides) != 0;
                if (side && result.firstSideContactFrame < 0) result.firstSideContactFrame = sample.frame;
                bool constrained = side && sample.forwardDistance < sample.intendedDistance * .25f;
                if (constrained && result.firstConstrainedFrame < 0) result.firstConstrainedFrame = sample.frame;
                if (constrained)
                {
                    if (constrainedStart < 0) constrainedStart = sample.frame;
                    constrainedDuration += delta;
                    if (constrainedDuration >= .5f && result.firstPersistentBlockFrame < 0) result.firstPersistentBlockFrame = constrainedStart;
                }
                else { constrainedStart = -1; constrainedDuration = 0; }
                // InsideCabin's broad box alone can become true while still on the upper
                // tread. Require native support on the actual cabin-floor collider too.
                if (sample.insideCabin && sample.supportCollider == report.floorCollider && sample.groundedAfter)
                { result.enteredCabin = true; break; }
            }
            Call(inputState, "End", MoveFinger); Call(adapter, "SetEditorReplayFingers", host, Array.Empty<int>()); Call(adapter, "Sample");
            result.end = walker.transform.position;
            result.outcome = result.enteredCabin ? "entered" : "blocked";
            RunRegressions(result, delta);
        }

        Regression NewRegression(CaseResult result, string name)
        {
            var regression = new Regression { name = name, start = walker.transform.position, end = walker.transform.position };
            result.regressions.Add(regression); return regression;
        }
        void StopMove()
        {
            Call(inputState, "End", MoveFinger);
            Call(adapter, "SetEditorReplayFingers", host, Array.Empty<int>()); Call(adapter, "Sample");
        }
        void BeginMove(float x, float y)
        {
            StopMove();
            if (!(bool)Call(inputState, "Begin", MoveFinger, E("TouchControl", "Move")))
                throw new InvalidOperationException("REGRESSION_MOVE_OWNER");
            Call(inputState, "Move", MoveFinger, x, y);
            Call(adapter, "SetEditorReplayFingers", host, new[] { MoveFinger });
        }
        bool StandardExit()
        {
            StopMove(); Call(adapter, "ReleaseAll");
            Call(state, "SetControl", E("ControlMode", "Driving")); Call(session, "ApplyContext");
            Call(motor, "ResetVehicle"); Physics.SyncTransforms();
            return (bool)Call(motor, "TryExitVehicle");
        }
        bool OnRoad(RegressionFrame frame) => frame.grounded && frame.supportCollider == report.roadCollider && !frame.insideCabin;
        static float HorizontalDistance(Vector3 a, Vector3 b) => Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));

        void RunRegressions(CaseResult result, float delta)
        {
            Vector3 inward = Quaternion.Euler(0, (float)Field(motor, "yaw"), 0) * Vector3.forward;
            Vector3 rearward = Quaternion.Euler(0, (float)Field(motor, "yaw"), 0) * Vector3.right;
            var downstairs = NewRegression(result, "downstairs");
            if (!result.enteredCabin) downstairs.outcome = "entry-not-reached";
            else
            {
                // Follow the same doorway backwards. The last analog input is shortened
                // to reach the standard exit; all displacement still goes through Walk.
                for (int i = 0; i < Mathf.CeilToInt(4 / delta); i++)
                {
                    float remaining = Vector3.Dot(walker.transform.position - result.exit, inward);
                    float strength = Mathf.Clamp01(remaining / (3.1f * delta));
                    if (remaining > .005f) BeginMove(0, -strength); else { strength = 0; StopMove(); }
                    var frame = CaptureRegression(downstairs, strength > 0 ? "backward" : "settle", delta, -inward, strength);
                    if (OnRoad(frame) && HorizontalDistance(frame.position, result.exit) <= .05f) break;
                }
                StopMove();
                var last = downstairs.frames.Last();
                downstairs.outcome = OnRoad(last) && HorizontalDistance(last.position, result.exit) <= .05f &&
                    downstairs.start.y - last.position.y >= .6f ? "passed" : "failed";
            }
            WriteReport();

            var ground = NewRegression(result, "road-grounded");
            bool atRoad = downstairs.outcome == "passed";
            if (!atRoad)
            {
                // Failed entry/descent stays failed. Only the already-used standard
                // setup/exit is permitted to recover independently runnable checks.
                ground.standardReset = true; atRoad = StandardExit();
                ground.start = ground.end = walker.transform.position;
                inward = Quaternion.Euler(0, (float)Field(motor, "yaw"), 0) * Vector3.forward;
                rearward = Quaternion.Euler(0, (float)Field(motor, "yaw"), 0) * Vector3.right;
            }
            if (atRoad)
            {
                for (int i = 0; i < Mathf.CeilToInt(1 / delta); i++) CaptureRegression(ground, "settle", delta, inward, 0);
                float roadTop = report.colliders.Single(c => c.id == report.roadCollider).max.y;
                ground.outcome = ground.frames.All(f => OnRoad(f) && f.position.y >= roadTop - .01f &&
                    f.position.y <= roadTop + .06f && HorizontalDistance(f.position, ground.start) <= .01f) ? "passed" : "failed";
            }
            else ground.outcome = "setup-failed";
            WriteReport();

            var driver = NewRegression(result, "driver-cycle");
            var cycle = new DriverCycle(); driver.driver.Add(cycle);
            cycle.controlBefore = Get(state, "Control").ToString(); cycle.contextBefore = Get(inputState, "Context").ToString();
            cycle.controllerBefore = walker.enabled; cycle.positionBefore = walker.transform.position;
            // This is the real distance/linecast-gated interaction at the ordinary exit.
            // Never alter interaction distances, controller state, or player placement.
            cycle.enterAttempted = atRoad;
            if (cycle.enterAttempted) cycle.enterSucceeded = (bool)Call(motor, "TryEnterDriver");
            cycle.controlAfterEnter = Get(state, "Control").ToString(); cycle.contextAfterEnter = Get(inputState, "Context").ToString();
            cycle.controllerAfterEnter = walker.enabled; cycle.positionAfterEnter = walker.transform.position;
            cycle.exitAttempted = cycle.enterSucceeded;
            if (cycle.exitAttempted) cycle.exitSucceeded = (bool)Call(motor, "TryExitVehicle");
            cycle.controlAfterExit = Get(state, "Control").ToString(); cycle.contextAfterExit = Get(inputState, "Context").ToString();
            cycle.controllerAfterExit = walker.enabled; cycle.positionAfterExit = walker.transform.position;
            driver.end = walker.transform.position;
            driver.outcome = !atRoad ? "setup-failed" :
                cycle.enterSucceeded && cycle.exitSucceeded && cycle.controlBefore == "OnFoot" && cycle.contextBefore == "OnFoot" &&
                cycle.controllerBefore && cycle.controlAfterEnter == "Driving" && cycle.contextAfterEnter == "Driving" &&
                !cycle.controllerAfterEnter && cycle.controlAfterExit == "OnFoot" && cycle.contextAfterExit == "OnFoot" &&
                cycle.controllerAfterExit && Vector3.Distance(cycle.positionBefore, cycle.positionAfterEnter) <= .001f &&
                Vector3.Distance(cycle.positionAfterExit, result.exit) <= .001f ? "passed" : "failed";
            WriteReport();

            var sidewall = NewRegression(result, "sidewall");
            if (!atRoad || !walker.enabled || Get(state, "Control").ToString() != "OnFoot") sidewall.outcome = "setup-failed";
            else
            {
                StopMove();
                // TryExitVehicle enables a fresh controller. Establish real grounding
                // again before walking along the road, including the 3 FPS cadence.
                for (int i = 0; i < Mathf.CeilToInt(1 / delta); i++) CaptureRegression(sidewall, "settle", delta, inward, 0);
                Vector3 target = result.exit + rearward * 1.5f;
                for (int i = 0; i < Mathf.CeilToInt(1 / delta); i++)
                {
                    float remaining = Vector3.Dot(target - walker.transform.position, rearward);
                    if (remaining <= .005f) break;
                    float strength = Mathf.Clamp01(remaining / (3.1f * delta));
                    BeginMove(strength, 0); CaptureRegression(sidewall, "approach", delta, rearward, strength);
                }
                StopMove();
                // z=-0.9 is outside the authored doorway/steps (z>=0.21) and open
                // door. The first full-height obstruction is the saved coach shell.
                // Continue ordinary inward movement for two seconds to test refusal.
                BeginMove(0, 1);
                for (int i = 0; i < Mathf.CeilToInt(2 / delta); i++) CaptureRegression(sidewall, "push", delta, inward, 1);
                StopMove();
                var push = sidewall.frames.Where(f => f.phase == "push").ToArray();
                var approach = sidewall.frames.Where(f => f.phase == "approach").ToArray();
                int shell = Register(shellCollider);
                float outsideLimit = shellCollider.bounds.min.x - walker.radius + 2 * walker.skinWidth + .02f;
                sidewall.outcome = approach.Length > 0 && HorizontalDistance(approach.Last().position, target) <= .05f &&
                    sidewall.frames.All(OnRoad) && push.All(f => f.position.x <= outsideLimit) &&
                    push.Count(f => f.sideCollider == shell) * delta >= .5f && push.Last().sideCollider == shell &&
                    push.Last().forwardDistance <= push.Last().intendedDistance * .25f ? "passed" : "failed";
            }
            WriteReport();
        }

        RegressionFrame CaptureRegression(Regression result, string phase, float delta, Vector3 direction, float strength)
        {
            if (result.frames.Count >= MaxRegressionFrames) throw new InvalidOperationException("REGRESSION_FRAME_BOUND");
            var observation = Observe(result.frames.Count, phase, (result.frames.Count + 1) * delta, delta, direction, strength);
            var frame = new RegressionFrame { frame = result.frames.Count, phase = phase, position = observation.position,
                flags = observation.flags, grounded = observation.groundedAfter, supportCollider = observation.supportCollider,
                verticalSpeed = observation.verticalSpeedAfter, insideCabin = observation.insideCabin,
                intendedDistance = observation.intendedDistance, forwardDistance = observation.forwardDistance,
                sideCollider = sideContact == null ? 0 : sideContact.collider, sidePoint = sideContact == null ? Vector3.zero : sideContact.point,
                sideNormal = sideContact == null ? Vector3.zero : sideContact.normal, contactCount = contactCount };
            result.frames.Add(frame); result.end = frame.position; return frame;
        }

        Sample Capture(CaseResult result, string phase, float elapsed, float delta, Vector3 inward, bool moving)
        {
            if (result.frames.Count >= MaxFrames) throw new InvalidOperationException("ENTRY_FRAME_BOUND");
            var sample = Observe(result.frames.Count, phase, elapsed, delta, inward, moving ? 1 : 0);
            if (sample.groundedAfter && sample.supportCollider == report.lowerCollider) result.lowerSupported = true;
            if (sample.groundedAfter && sample.supportCollider == report.upperCollider) result.upperSupported = true;
            if (sample.groundedAfter && sample.supportCollider == report.floorCollider) result.floorSupported = true;
            result.frames.Add(sample); return sample;
        }
        Sample Observe(int frame, string phase, float elapsed, float delta, Vector3 direction, float strength)
        {
            contacts.Clear(); droppedContacts = contactCount = 0; sideContact = null; observedDirection = direction;
            Vector3 before = walker.transform.position; bool groundedBefore = walker.isGrounded;
            float verticalSpeedBefore = (float)Field(motor, "verticalSpeed");
            Call(adapter, "Sample"); Call(motor, "Tick", delta); Call(adapter, "ConsumeFrame"); Physics.SyncTransforms();
            Vector3 position = walker.transform.position;
            var sample = new Sample { frame = frame, phase = phase, elapsed = elapsed, delta = delta, position = position,
                footHeight = position.y + walker.center.y - walker.height * .5f, groundedBefore = groundedBefore, groundedAfter = walker.isGrounded,
                flags = (int)walker.collisionFlags, intendedDistance = 3.1f * delta * strength,
                forwardDistance = Vector3.Dot(position - before, direction), doorAngle = (float)Field(motor, "doorAngle"),
                verticalSpeedBefore = verticalSpeedBefore, verticalSpeedAfter = (float)Field(motor, "verticalSpeed"),
                insideCabin = (bool)Get(motor, "InsideCabin"), contacts = contacts.ToArray(), droppedContacts = droppedContacts };
            // Ground is sampled at feet, not the visual renderer or a guessed step height.
            var support = Physics.RaycastAll(position + Vector3.up * .12f, Vector3.down, .25f, ~0, QueryTriggerInteraction.Ignore)
                .Where(h => h.collider != walker).OrderBy(h => h.distance).FirstOrDefault();
            if (support.collider)
            { sample.supportCollider = Register(support.collider); sample.supportPoint = support.point; }
            return sample;
        }

        void RecordContact(ControllerColliderHit hit)
        {
            contactCount++;
            // Evaluate every native callback, even when entry's eight detailed records
            // are full. Last-Move collisionFlags alone cannot describe twenty substeps.
            bool opposingShell = sideContact == null && hit.collider == shellCollider && Vector3.Dot(hit.normal, observedDirection) < -.5f;
            Contact row = null;
            if (contacts.Count < MaxContacts || opposingShell)
                row = new Contact { collider = Register(hit.collider), point = hit.point, normal = hit.normal,
                    moveDirection = hit.moveDirection, moveLength = hit.moveLength };
            if (opposingShell) sideContact = row;
            if (contacts.Count < MaxContacts) contacts.Add(row); else droppedContacts++;
        }
        int Register(Collider collider)
        {
            if (colliderIds.TryGetValue(collider, out int existing)) return existing;
            if (colliderIds.Count >= 128) throw new InvalidOperationException("ENTRY_COLLIDER_BOUND");
            int id = colliderIds.Count + 1; colliderIds.Add(collider, id);
            var row = new ColliderRecord { id = id, hierarchy = Hierarchy(collider.transform), type = collider.GetType().Name,
                enabled = collider.enabled, active = collider.gameObject.activeInHierarchy, trigger = collider.isTrigger,
                min = collider.bounds.min, max = collider.bounds.max, meshAsset = "", meshGuid = "", meshLocalId = "", authoredBy = SourceScene };
            if (collider is MeshCollider meshCollider && meshCollider.sharedMesh)
            {
                row.convex = meshCollider.convex; row.meshAsset = AssetDatabase.GetAssetPath(meshCollider.sharedMesh);
                if (AssetDatabase.TryGetGUIDAndLocalFileIdentifier(meshCollider.sharedMesh, out string guid, out long localId))
                { row.meshGuid = guid; row.meshLocalId = localId.ToString(System.Globalization.CultureInfo.InvariantCulture); }
                if (!string.IsNullOrEmpty(row.meshAsset)) { Pin(row.meshAsset); Pin(row.meshAsset + ".meta"); }
            }
            report.colliders.Add(row); return id;
        }
        static string Hierarchy(Transform node)
        { return node.parent ? Hierarchy(node.parent) + "/" + node.name : node.name; }
        void Pin(string path)
        {
            if (report.sourceFiles.Any(p => p.path == path)) return;
            report.sourceFiles.Add(new FilePin { path = path, sha256 = Hash(path) });
        }
        static string Hash(string path)
        { using (var hash = SHA256.Create()) using (var stream = File.OpenRead(path)) return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant(); }
        void WriteReport()
        {
            string json = JsonUtility.ToJson(report, false);
            if (System.Text.Encoding.UTF8.GetByteCount(json) + 1 > 4 * 1024 * 1024) throw new InvalidOperationException("ENTRY_REPORT_BOUND");
            Directory.CreateDirectory(Path.GetDirectoryName(ReportPath)); File.WriteAllText(ReportPath, json + "\n");
        }

        [UnityTearDown] public IEnumerator Cleanup()
        {
            if (adapter && host) { Call(adapter, "DetachEditorReplay", host); report.replayDetached = !(bool)Get(adapter, "EditorReplayActive"); }
            if (observer) observer.Hit = null;
            if (host) Object.DestroyImmediate(host);
            if (road) Object.DestroyImmediate(road);
            if (inspectionWalker) Object.DestroyImmediate(inspectionWalker);
            if (originalActive.IsValid() && originalActive.isLoaded) SceneManager.SetActiveScene(originalActive);
            // Also recover a successfully loaded source if an earlier setup assertion failed.
            if (ownsSourceLoad && !loadedScene.IsValid()) loadedScene = SceneManager.GetSceneByPath(SourceScene);
            if (ownsSourceLoad && loadedScene.IsValid() && loadedScene.isLoaded) yield return SceneManager.UnloadSceneAsync(loadedScene);
            foreach (var material in transientMaterials) if (material) Object.DestroyImmediate(material);
            Cursor.lockState = originalLock; Cursor.visible = originalCursor;
            if (report != null)
            {
                report.sceneUnloaded = !SceneManager.GetSceneByPath(SourceScene).isLoaded;
                report.sourceFilesUnchanged = report.sourceFiles.All(p => File.Exists(p.path) && Hash(p.path) == p.sha256);
                WriteReport();
                Assert.That(report.sourceFilesUnchanged, Is.True, "The read-only fixture changed saved source bytes.");
                Assert.That(report.sceneUnloaded, Is.True);
            }
            colliderIds.Clear(); contacts.Clear(); transientMaterials.Clear();
        }
    }

    public sealed class JourneyEntryContactProbe : MonoBehaviour
    {
        public Action<ControllerColliderHit> Hit;
        void OnControllerColliderHit(ControllerColliderHit hit) => Hit?.Invoke(hit);
    }
}
#endif
