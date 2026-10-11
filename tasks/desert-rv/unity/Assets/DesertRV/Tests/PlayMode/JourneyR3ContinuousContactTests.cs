#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace DesertRV.Tests
{
    // These observers never drive production simulation or synchronize transforms.
    // Session=-100, BeastActor=0 and Director=50 retain their production Update order.
    [DefaultExecutionOrder(-50)] public sealed class R3BeforeAIObserver : MonoBehaviour
    { public Action sample; void Update() { sample?.Invoke(); } }
    [DefaultExecutionOrder(40)] public sealed class R3BeforeMotorObserver : MonoBehaviour
    { public Action sample; void Update() { sample?.Invoke(); } }
    [DefaultExecutionOrder(60)] public sealed class R3AfterDirectorObserver : MonoBehaviour
    { public Action sample; void Update() { sample?.Invoke(); } }

    public sealed class JourneyR3ContinuousContactTests
    {
        const string Bootstrap = "Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity";
        const string R3 = "Assets/DesertRV/Scenes/Journey/NightBeacon.unity";
        const string Folder = "JourneyEvidence/R3ContinuousContact/";
        const string Output = Folder + "native-r3-continuous-contact.json";
        const string InputPath = Folder + "consumer-input.json";
        const string Producer = "2915b8b1e5be8b800a3d71f186b5316a8f626bc8";
        const float Cadence = 1f / 30;
        const int MaxFrames = 2000, ThrottleFinger = 43101, SteeringFinger = 43102;
        static readonly Vector3 Extents = new Vector3(1.05f, 1.12f, 2.7f);
        const BindingFlags Any = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static Type T(string n) => Type.GetType("DesertRV." + n + ", Assembly-CSharp", true);
        static object Get(object o, string n) => o.GetType().GetProperty(n, Any).GetValue(o);
        static object Field(object o, string n) => o.GetType().GetField(n, Any).GetValue(o);
        static void Set(object o, string n, object v) => o.GetType().GetField(n, Any).SetValue(o, v);
        static object Call(object o, string n, params object[] a) => o.GetType().GetMethod(n, Any).Invoke(o, a);
        static object E(string t, string n) => Enum.Parse(T(t), n);
        static Component[] Components(Scene s, string type) => s.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren(T(type), true)).Cast<Component>().ToArray();

        [Serializable] public sealed class Pin { public string path, sha256; }
        [Serializable] public sealed class Dependency { public string path, sha256, kind, packageName, packageVersion; public long bytes; }
        [Serializable] public sealed class ChangeBytes { public string sha256; public long bytes; }
        [Serializable] public sealed class DependencyChange { public string path; public ChangeBytes before, after; }
        [Serializable] public sealed class ConsumerInput
        { public int schema; public string status, producerCommit, producerRunId, producerArtifactSha256, consumerCommit, currentProductionCommit; public string derivedReceiptSha256; public Dependency[] dependencies; public DependencyChange[] dependencyChanges, productionSourceOverlay; }
        [Serializable] public sealed class DependencyCheck
        { public bool passed; public int expectedCount, actualCount; public string inputSha256; public string[] mismatches = Array.Empty<string>(); }
        [Serializable] public sealed class ColliderIdentity
        { public int id, instanceId; public string scene, path, type, role; public bool trigger; public Vector3 min, max; }
        [Serializable] public sealed class Hit
        { public bool present; public int collider; public float distance; public Vector3 point, normal; public bool self, walker, upward, beast, dead; }
        [Serializable] public sealed class Query
        { public int rawCount, fullCount; public bool performed, saturated; public int[] rawIds, fullIds; public Hit nearestRaw, nearestFull; public Vector3 direction; public float distance; }
        [Serializable] public sealed class AIQuery
        {
            public string route; public bool recorded, clearAttackLine; public Hit attackLineHit;
            public Vector3 queryBottom, queryTop; public Query forward, tangent;
        }
        [Serializable] public sealed class Beast
        {
            public int id, health; public string phase; public bool active, enabled, dead, killedByRam;
            public int[] actualAIHitBufferColliderIds; public Vector3 position, bottom, top, physicsMin, physicsMax; public float yaw, radius, phaseTime, attackClock;
            public bool proxyOverlap, axisInside, penetration; public float axisDistance, penetrationDepth;
            public Vector3 penetrationDirection; public AIQuery aiQuery;
        }
        [Serializable] public sealed class ArcTarget
        { public int beast; public float centerDistance, surfaceDistance; public bool inRange, clearLine; public Hit firstLOSBlocker; }
        [Serializable] public sealed class ArcObservation
        { public bool sourceReady, sourceDistanceFinite; public int sourceBlocker, pulseId; public string sourceQuery, sourceSquareDistanceRaw; public float sourceSquareDistance; public double cooldown; public Vector3 origin; public ArcTarget[] targets; }
        [Serializable] public sealed class ArcEvent
        { public int frame, target, epoch, sequence, pulse; public Vector3 origin, end; }
        [Serializable] public sealed class Contact
        { public int frame; public float speed; public Vector3 actualVehiclePosition; public float actualVehicleYaw; public Hit hit; }
        [Serializable] public sealed class MotorObservation
        {
            public Vector3 position, forward; public float yaw, speed, targetSpeed, predictedSpeed, intendedDistance, throttle, steering;
            public bool powerConnected, rotationAttempted, rotationBlocked; public int rotationRawCount, rotationFullCount;
            public int[] rotationRawIds, rotationFullIds; public int rotationNearest;
            public float attemptedYaw, castHeadingYaw; public Query translation;
        }
        [Serializable] public sealed class Frame
        {
            public int frame, sequenceFrame, vehicleHealthBeforeAI, vehicleHealthBeforeMotor, vehicleHealthAfter, playerHealth;
            public float dt, aiDelta, unscaledDelta, fixedDelta, captureDelta, timeScale; public double gameTime, realTime;
            public string status, control, step; public Vector3 beforeAI, after; public float yawAfter, speedAfter;
            public Beast[] beastsBeforeAI, beastsBeforeMotor, beastsAfter;
            public int[] actualMotor32BufferColliderIds, actualRotation32BufferColliderIds;
            public MotorObservation motor; public ArcObservation arcBeforeDirector, arcAfterDirector;
            public List<Contact> motorObstacleContact = new List<Contact>();
            public List<ArcEvent> arcPresented = new List<ArcEvent>();
        }
        [Serializable] public sealed class Step
        { public string name; public int frames; public float throttle, steering; public Step(string n, int f, float t, float s = 0) { name = n; frames = f; throttle = t; steering = s; } }
        [Serializable] public sealed class Sequence
        {
            public string name, fixture; public bool liveEnemies, completed; public float yawOffset, requestedCaptureDelta;
            public Vector3 sourceSpawn, initialVehicle; public float initialYaw; public Beast[] authoredEnemies;
            public int initialVehicleHealth, initialPlayerHealth; public string upgrades; public Step[] plan;
            public List<Frame> frames = new List<Frame>();
        }
        [Serializable] public sealed class Report
        {
            public int schemaVersion = 1; public string status = "fixture-incomplete", failureCode = "", unityVersion;
            public string producerCommit, consumerCommit, producerRunId;
            public string scope = "controlled R3 fixture, real yielding PlayMode frames and unchanged production Update; not an exact replay or human play";
            public string timestep = "Time.captureDeltaTime=1/30 or 0.2 and timeScale=1; fixedDeltaTime preserved; controlled game-time cadence, not measured rendering FPS; Beast Update clamps delta to 0.1 while Director uses full delta";
            public string inputRoute = "test-owned replay fingers -> ordinary JourneySession.Update/Input.Sample -> Director.Update/Motor.Tick/Actions.Tick; no OS key events";
            public string queryRoute = "read-only snapshots: AI queries before actor Updates (cross-actor ordering may differ); Motor queries after AI/before Director are predictions without mutating self-collider poses; repeat NonAlloc selection/order may differ; Arc geometry is sampled before and after Director, while actual ObstacleContact and ArcPresented callbacks; raw production buffer IDs are read-only and may contain stale entries outside unknown valid prefixes; no per-frame Physics.SyncTransforms";
            public string nearestSemantics = "Motor nearest filters self/walker/upward only, before initial-overlap escape and ram logic. AI nearest filters own hierarchy/upward. Rotation nearest uses bounds distance, since overlap has no contact distance.";
            public bool physicsAutoSyncTransforms, replayDetached, sceneUnloaded, sourceFilesUnchanged, timeRestored;
            public float originalCaptureDelta, originalTimeScale, originalFixedDelta; public int frameBound = MaxFrames;
            public DependencyCheck dependencyCheck = new DependencyCheck(); public List<Pin> sourceFiles = new List<Pin>();
            public List<ColliderIdentity> colliders = new List<ColliderIdentity>(); public List<Sequence> sequences = new List<Sequence>();
        }

        Report report; ConsumerInput input; Scene originalActive, bootstrapScene, regionScene;
        Component director, session, motor, actions, region, adapter; object state, touch;
        Transform vehicle; CharacterController walker; GameObject observerHost; BoxCollider proxy;
        Component[] actors; Quaternion[] authoredActorRotations; Action<RaycastHit, float> contactListener; Delegate arcListener;
        Sequence current; Frame frame; string stepName; bool recording, ownsBootstrap, ownsR3;
        readonly Dictionary<Collider, int> colliderIds = new Dictionary<Collider, int>();
        readonly RaycastHit[] motorRaw = new RaycastHit[32], aiRaw = new RaycastHit[16];
        readonly Collider[] rotationRaw = new Collider[32];
        Exception observerFailure; CursorLockMode oldLock; bool oldCursor;

        [UnityTest, Timeout(600000)] public IEnumerator RealR3_ContinuousAIAndStaticControl()
        {
            originalActive = SceneManager.GetActiveScene(); oldLock = Cursor.lockState; oldCursor = Cursor.visible;
            report = new Report { unityVersion = Application.unityVersion, physicsAutoSyncTransforms = Physics.autoSyncTransforms,
                originalCaptureDelta = Time.captureDeltaTime, originalTimeScale = Time.timeScale, originalFixedDelta = Time.fixedDeltaTime };
            Write(); VerifyDependencies();
            foreach (var n in new[] { Bootstrap, R3, "Assets/DesertRV/Runtime/JourneyMotor.cs", "Assets/DesertRV/Runtime/BeastActor.cs",
                "Assets/DesertRV/Runtime/JourneyDirector.cs", "Assets/DesertRV/Runtime/JourneySession.cs", "Assets/DesertRV/Runtime/MobileInputAdapter.cs",
                "Assets/DesertRV/Runtime/JourneyActions.cs", "Assets/DesertRV/Runtime/JourneyActions.Geometry.cs",
                "Assets/DesertRV/Runtime/PouncerGroundSupport.cs", "Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs", "Assets/DesertRV/Runtime/RegionBinding.cs",
                "Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs" }) { PinFile(n); PinFile(n + ".meta"); }
            Assert.That(Application.isPlaying, Is.True);
            Assert.That(Object.FindObjectsByType(T("JourneyDirector"), FindObjectsSortMode.None), Is.Empty, "FOREIGN_DIRECTOR");
            Assert.That(SceneManager.GetSceneByPath(Bootstrap).isLoaded || SceneManager.GetSceneByPath(R3).isLoaded, Is.False, "SOURCE_ALREADY_LOADED");
            Time.captureDeltaTime = Cadence; Time.timeScale = 1;
            ownsBootstrap = true;
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(Bootstrap, new LoadSceneParameters(LoadSceneMode.Additive));
            bootstrapScene = SceneManager.GetSceneByPath(Bootstrap);
            director = (Component)Object.FindObjectsByType(T("JourneyDirector"), FindObjectsSortMode.None).Single();
            Assert.That((bool)Get(director, "OwnsJourney"), Is.True, "DIRECTOR_OWNER");
            session = (Component)Field(director, "journey"); motor = (Component)Field(director, "motor"); actions = (Component)Field(director, "actions");
            state = Get(session, "State"); adapter = (Component)Get(session, "Input"); touch = Get(adapter, "State");
            vehicle = (Transform)Field(motor, "vehicle"); walker = ((Transform)Get(motor, "Walker")).GetComponent<CharacterController>();
            ownsR3 = true;
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(R3, new LoadSceneParameters(LoadSceneMode.Additive));
            regionScene = SceneManager.GetSceneByPath(R3); Assert.That(SceneManager.SetActiveScene(regionScene), Is.True);
            region = Components(regionScene, "RegionBinding").Single(); Assert.That((int)Field(region, "region"), Is.EqualTo(3));
            actors = ((Array)Field(((Array)Field(region, "waves")).GetValue(0), "enemies")).Cast<Component>().ToArray();
            Assert.That(actors.Length, Is.EqualTo(2), "FIRST_WAVE_TWO_POUNCERS");
            authoredActorRotations=actors.Select(a=>a.transform.rotation).ToArray();
            Assert.That(actors.All(a => !(bool)Field(a, "armored") && a.GetComponent<CapsuleCollider>()), Is.True);
            Assert.That(Vector3.Distance(new Vector3(actors[0].transform.position.x, 0, actors[0].transform.position.z), new Vector3(-7, 0, 33)), Is.LessThan(.001f));
            Assert.That(Vector3.Distance(new Vector3(actors[1].transform.position.x, 0, actors[1].transform.position.z), new Vector3(7, 0, 39)), Is.LessThan(.001f));
            Assert.That(Object.FindObjectsByType<Collider>(FindObjectsSortMode.None).Where(c => c.enabled && !c.isTrigger).All(c => c.gameObject.scene == regionScene || c.transform.IsChildOf(director.transform)), Is.True, "FOREIGN_COLLIDER");
            observerHost = new GameObject("R3 contact observation only"); SceneManager.MoveGameObjectToScene(observerHost, regionScene);
            proxy = observerHost.AddComponent<BoxCollider>(); proxy.isTrigger = true; proxy.size = Extents * 2;
            observerHost.AddComponent<R3BeforeAIObserver>().sample = () => Safe(BeforeAI);
            observerHost.AddComponent<R3BeforeMotorObserver>().sample = () => Safe(BeforeMotor);
            observerHost.AddComponent<R3AfterDirectorObserver>().sample = () => Safe(AfterDirector);
            contactListener = (hit, speed) => { if (recording && frame != null) frame.motorObstacleContact.Add(new Contact { frame = Time.frameCount, speed = speed, actualVehiclePosition=vehicle.position, actualVehicleYaw=vehicle.eulerAngles.y, hit = Describe(hit) }); };
            motor.GetType().GetEvent("ObstacleContact").AddEventHandler(motor, contactListener);
            var eventInfo = actions.GetType().GetEvent("ArcPresented");
            var method = GetType().GetMethod(nameof(OnArc), Any).MakeGenericMethod(eventInfo.EventHandlerType.GetGenericArguments()[0]);
            arcListener = Delegate.CreateDelegate(eventInfo.EventHandlerType, this, method); eventInfo.AddEventHandler(actions, arcListener);
            Call(adapter, "AttachEditorReplay", observerHost);
            // Settle initial Screen/safe-area reconciliation before fixture fingers are held.
            yield return null;
            foreach (var spec in new[] { ("static-control", false, 0f, Cadence), ("natural-approach-30hz", true, 0f, Cadence), ("natural-approach-5hz-heading20", true, 20f, .2f) })
            {
                Time.captureDeltaTime = spec.Item4; yield return null;
                SetupSequence(spec.Item1, spec.Item2, spec.Item3, spec.Item4);
                foreach (var step in current.plan)
                {
                    stepName = step.name; SetInput(step.throttle, step.steering); recording = true;
                    for (int i = 0; i < step.frames; i++)
                    {
                        int count = current.frames.Count; yield return null;
                        if (observerFailure != null) throw new InvalidOperationException("R3 observer failed", observerFailure);
                        Assert.That(current.frames.Count, Is.EqualTo(count + 1), "EXACTLY_ONE_OBSERVED_FRAME_PER_YIELD");
                    }
                    recording = false; Write();
                }
                current.completed = true; SetInput(0, 0); Write();
            }
            report.status = "completed"; Write();
            Assert.That(report.sequences.Count, Is.EqualTo(3));
            Assert.That(report.sequences.Sum(s => s.frames.Count), Is.EqualTo(1212));
        }

        void SetupSequence(string name, bool live, float yawOffset, float cadence)
        {
            recording = false; frame = null;
            if ((int)Get(session, "Generation") == 0) Assert.That(Call(session, "StartJourney"), Is.True);
            else Call(state, "ResetJourney"); // Fixture restoration between sequences; no terminal/damage shortcut.
            foreach (string part in new[] { "RamPart", "Coil" })
            { Assert.That(Call(state, "TryCollect", "r3-fixture/" + part, E("ComponentPart", part)), Is.True); Assert.That(Call(state, "TryInstall", E("ComponentPart", part)), Is.True); }
            for (int i = 0; i < 2; i++)
            { Call(state, "SetObjectivesResolved", true); Assert.That(Call(state, "TryAdvance"), Is.True); Assert.That(Call(state, "CompleteLoading"), Is.True); }
            // Fixture-only binding through the same production BindRegion used by RegionLoader.
            // Editor async load bypasses approval/build-list gates; no claim of a played R1/R2 progression.
            object ticket = Call(session, "BeginCurrentRegionLoad"); Set(director, "pending", ticket);
            Set(director, "progress", Activator.CreateInstance(T("RegionProgressState"), state, Get(session, "Generation")));
            Assert.That(Call(director, "BindRegion", region), Is.True, "PRODUCTION_BIND_R3");
            var spawn = (Transform)Field(region, "spawn");
            var at = new Vector3(1.7f, spawn.position.y, 24);
            Call(motor, "PlaceForRegion", at, Quaternion.AngleAxis(yawOffset, Vector3.up) * spawn.rotation);
            Call(session, "ResetPositionSample", Call(region, "WorldProgress", at));
            Call(state, "SetPowerConnected", false); Call(session, "ApplyContext");
            // Actual first-wave actors retain saved positions and grounded Y. Activate only at setup.
            // Encounter remains unpowered; this isolates the first wave and excludes an unrelated second wave.
            for(int i=0;i<actors.Length;i++) { actors[i].transform.rotation=authoredActorRotations[i]; actors[i].gameObject.SetActive(live); }
            Physics.SyncTransforms(); // Once per fixture restoration, never in recorded frames.
            current = new Sequence { name = name, liveEnemies = live, yawOffset = yawOffset, requestedCaptureDelta = cadence, sourceSpawn = spawn.position,
                initialVehicle = vehicle.position, initialYaw = vehicle.eulerAngles.y, initialVehicleHealth = (int)Get(state, "VehicleHealth"),
                initialPlayerHealth = (int)Get(state, "PlayerHealth"), upgrades = Get(state, "Upgrades").ToString(),
                fixture = "fresh R3 setup; Ram+Arc installed via state APIs; Driving/unplugged; first wave activated at saved natural roots; RV x=1.7/z=24 and relative heading are approximate fixture values, not measured desktop coordinates; no later beast placement or damage calls",
                authoredEnemies = actors.Select(a => BeastState(a, false)).ToArray(),
                plan = live && cadence > .1f ? new[] { new Step("stationary-approach",80,0), new Step("reverse",17,-1), new Step("forward",16,1),
                    new Step("reverse-again",17,-1), new Step("reverse-left",6,-1,-1), new Step("forward-left",7,1,-1),
                    new Step("reverse-right",9,-1,1), new Step("forward-held",22,1) } : live ? new[] { new Step("stationary-approach",240,0), new Step("reverse",102,-1), new Step("forward",96,1),
                    new Step("reverse-again",102,-1), new Step("reverse-left",36,-1,-1), new Step("forward-left",39,1,-1),
                    new Step("reverse-right",51,-1,1), new Step("forward-held",132,1) }
                    : new[] { new Step("stationary",30,0), new Step("reverse",60,-1), new Step("forward",90,1), new Step("forward-left",30,1,-1), new Step("reverse-right",30,-1,1) } };
            report.sequences.Add(current); Write();
        }
        void SetInput(float throttle, float steering)
        {
            // A real replay lift clears TouchInputState suppression before reusing IDs.
            // No simulation frame or production Update is inserted or invoked here.
            Call(touch, "End", ThrottleFinger); Call(touch, "End", SteeringFinger);
            Call(adapter, "SetEditorReplayFingers", observerHost, Array.Empty<int>());
            Call(adapter, "ReleaseAll"); var fingers = new List<int>();
            if (Get(state,"Status").ToString()!="Playing") return; // Keep observing terminal states with released fingers.
            if (throttle != 0) { Assert.That(Call(touch, "Begin", ThrottleFinger, E("TouchControl", throttle > 0 ? "Accelerate" : "Brake")), Is.True); fingers.Add(ThrottleFinger); }
            if (steering != 0) { Assert.That(Call(touch, "Begin", SteeringFinger, E("TouchControl", "Move")), Is.True); Call(touch, "Move", SteeringFinger, steering, 0f); fingers.Add(SteeringFinger); }
            Call(adapter, "SetEditorReplayFingers", observerHost, fingers.ToArray());
        }
        void Safe(Action action)
        {
            if (!recording || observerFailure != null) return;
            try { action(); } catch (Exception e) { observerFailure = e; report.failureCode = "OBSERVER_" + e.GetType().Name; recording = false; }
        }
        void BeforeAI()
        {
            Assert.That(report.sequences.Sum(s => s.frames.Count), Is.LessThan(MaxFrames));
            frame = new Frame { frame = Time.frameCount, sequenceFrame = current.frames.Count, step = stepName,
                dt = Time.deltaTime, aiDelta = Mathf.Min(Time.deltaTime,.1f), unscaledDelta = Time.unscaledDeltaTime,
                fixedDelta = Time.fixedDeltaTime, captureDelta = Time.captureDeltaTime, timeScale = Time.timeScale,
                gameTime = Time.timeAsDouble, realTime = Time.realtimeSinceStartupAsDouble,
                beforeAI = vehicle.position, vehicleHealthBeforeAI = (int)Get(state,"VehicleHealth"),
                beastsBeforeAI = actors.Select(a => BeastState(a,true)).ToArray() };
            Assert.That(frame.dt, Is.EqualTo(current.requestedCaptureDelta).Within(.00001f), "DELTA_BOUND");
        }
        void BeforeMotor()
        {
            Assert.That(frame.frame, Is.EqualTo(Time.frameCount), "OBSERVER_ORDER");
            frame.vehicleHealthBeforeMotor = (int)Get(state,"VehicleHealth");
            frame.beastsBeforeMotor = actors.Select(a => BeastState(a,false)).ToArray();
            frame.motor = ObserveMotor(); frame.arcBeforeDirector = ObserveArc();
        }
        void AfterDirector()
        {
            Assert.That(frame.frame, Is.EqualTo(Time.frameCount)); Assert.That(frame.motor, Is.Not.Null);
            frame.after = vehicle.position; frame.yawAfter = vehicle.eulerAngles.y; frame.speedAfter = (float)Get(motor,"Speed");
            frame.vehicleHealthAfter = (int)Get(state,"VehicleHealth"); frame.playerHealth = (int)Get(state,"PlayerHealth");
            frame.status = Get(state,"Status").ToString(); frame.control = Get(state,"Control").ToString();
            frame.beastsAfter = actors.Select(a => BeastState(a,false)).ToArray(); frame.arcAfterDirector=ObserveArc();
            frame.actualMotor32BufferColliderIds=((RaycastHit[])Field(motor,"carHits")).Select(h=>Id(h.collider)).ToArray();
            frame.actualRotation32BufferColliderIds=((Collider[])Field(motor,"rotationHits")).Select(Id).ToArray();
            current.frames.Add(frame);
        }
        void OnArc<TEvent>(TEvent e)
        {
            if (!recording || frame == null) return;
            frame.arcPresented.Add(new ArcEvent { frame = Time.frameCount, target = ((Component)Field(e,"Target")).GetInstanceID(),
                epoch = (int)Field(e,"Epoch"), sequence = (int)Field(e,"Sequence"), pulse = (int)Field(e,"Pulse"),
                origin = (Vector3)Field(e,"Origin"), end = (Vector3)Field(e,"End") });
        }

        MotorObservation ObserveMotor()
        {
            var m = new MotorObservation { position = vehicle.position, yaw = vehicle.eulerAngles.y, speed = (float)Get(motor,"Speed"),
                throttle = Mathf.Clamp((float)Get(adapter,"Throttle"),-1,1), steering = ((Vector2)Get(adapter,"Movement")).x,
                powerConnected = (bool)Get(state,"PowerConnected"), forward = (Vector3)Get(motor,"Forward") };
            m.targetSpeed = m.throttle >= 0 ? m.throttle * (float)Field(motor,"topSpeed") : m.throttle * (float)Field(motor,"topSpeed") * .38f;
            m.predictedSpeed = Mathf.MoveTowards(m.speed,m.targetSpeed,Time.deltaTime * (Mathf.Abs(m.throttle)<.05f?7:4.5f));
            Quaternion attempt = Quaternion.AngleAxis(m.steering*m.predictedSpeed*Time.deltaTime*7,Vector3.up)*vehicle.rotation;
            Vector3 attemptedForward = (attempt * (Vector3)Field(motor,"localForward")).normalized;
            Quaternion heading = Quaternion.LookRotation(attemptedForward); Vector3 center = vehicle.position + Vector3.up*1.45f;
            m.attemptedYaw = attempt.eulerAngles.y; m.rotationAttempted = Mathf.Abs(m.steering*m.predictedSpeed)>.01f;
            int count = Physics.OverlapBoxNonAlloc(center,Extents,rotationRaw,heading,~0,QueryTriggerInteraction.Ignore);
            var full = Physics.OverlapBox(center,Extents,heading,~0,QueryTriggerInteraction.Ignore);
            m.rotationRawCount=count; m.rotationFullCount=full.Length;
            m.rotationRawIds=rotationRaw.Take(count).Select(Id).ToArray(); m.rotationFullIds=full.Select(Id).ToArray();
            Func<Collider,bool> blocks = c => c && !c.transform.IsChildOf(vehicle) && c!=walker && c.bounds.max.y>vehicle.position.y+.34f;
            m.rotationBlocked = m.rotationAttempted && (count==rotationRaw.Length || rotationRaw.Take(count).Any(blocks));
            m.rotationNearest=Id(full.Where(blocks).OrderBy(c=>c.bounds.SqrDistance(center)).FirstOrDefault());
            if(m.rotationBlocked) heading=Quaternion.LookRotation(m.forward);
            m.castHeadingYaw=heading.eulerAngles.y; m.intendedDistance=Mathf.Abs(m.predictedSpeed*Time.deltaTime);
            if (!m.powerConnected && Get(state,"Status").ToString()=="Playing" && m.intendedDistance>.001f)
            {
                Vector3 direction=(heading*Vector3.forward)*Mathf.Sign(m.predictedSpeed);
                count=Physics.BoxCastNonAlloc(center,Extents,direction,motorRaw,heading,m.intendedDistance+.10f,~0,QueryTriggerInteraction.Ignore);
                var hits=Physics.BoxCastAll(center,Extents,direction,heading,m.intendedDistance+.10f,~0,QueryTriggerInteraction.Ignore);
                m.translation=Compare(motorRaw,count,hits,direction,m.intendedDistance+.10f,null);
            }
            return m;
        }
        Beast BeastState(Component actor, bool ai)
        {
            var c=actor.GetComponent<CapsuleCollider>();
            var b=new Beast { id=actor.GetInstanceID(), health=(int)Get(actor,"Health"), phase=Get(actor,"Phase").ToString(),
                active=actor.gameObject.activeInHierarchy, enabled=((Behaviour)actor).enabled, dead=(bool)Get(actor,"Dead"), killedByRam=(bool)Get(actor,"KilledByRam"),
                position=actor.transform.position,yaw=actor.transform.eulerAngles.y,radius=c.radius,
                actualAIHitBufferColliderIds=((RaycastHit[])Field(actor,"hits")).Select(h=>Id(h.collider)).ToArray(),
                phaseTime=(float)Field(actor,"phaseTime"),attackClock=(float)Field(actor,"attackClock"), physicsMin=c.bounds.min,physicsMax=c.bounds.max };
            Assert.That(c.direction==1 && (actor.transform.lossyScale-Vector3.one).sqrMagnitude<1e-10f,Is.True,"ACTUAL_CAPSULE_SHAPE");
            Capsule(actor,actor.transform.rotation,out b.bottom,out b.top);
            Assert.That(Mathf.Abs(Vector3.Dot((b.top-b.bottom).normalized,Vector3.up)),Is.GreaterThan(.99999f),"UPRIGHT_AXIS_REQUIRED");
            Quaternion heading=Quaternion.LookRotation((Vector3)Get(motor,"Forward")); Vector3 center=vehicle.position+Vector3.up*1.45f;
            // Axis direction is authored upright; this independently computes distance to the current oriented proxy.
            Vector3 local=Quaternion.Inverse(heading)*((b.bottom+b.top)*.5f-center);
            float ygap=Mathf.Max(0,Mathf.Abs(local.y)-((b.top-b.bottom).magnitude*.5f+Extents.y));
            b.axisDistance=new Vector3(Mathf.Max(0,Mathf.Abs(local.x)-Extents.x),ygap,Mathf.Max(0,Mathf.Abs(local.z)-Extents.z)).magnitude;
            b.axisInside=b.axisDistance<=.00001f;
            b.proxyOverlap=Physics.OverlapBox(center,Extents,heading,~0,QueryTriggerInteraction.Ignore).Contains(c);
            if(b.active && c.enabled)
                b.penetration=Physics.ComputePenetration(proxy,center,heading,c,actor.transform.position,actor.transform.rotation,out b.penetrationDirection,out b.penetrationDepth);
            if(!b.penetration) { b.penetrationDepth=0; b.penetrationDirection=Vector3.zero; } // Both false-result outputs are undefined; preserve true results unchanged.
            if(ai && b.active && b.enabled && !b.dead) b.aiQuery=ObserveAI(actor,b);
            return b;
        }
        static void Capsule(Component actor,Quaternion rotation,out Vector3 bottom,out Vector3 top)
        {
            var c=actor.GetComponent<CapsuleCollider>(); Vector3 center=actor.transform.position+rotation*c.center;
            Vector3 half=rotation*Vector3.up*(c.height*.5f-c.radius); bottom=center-half;top=center+half;
        }
        AIQuery ObserveAI(Component actor, Beast b)
        {
            var result=new AIQuery {recorded=true,route="no-move-in-this-phase"}; float dt=Mathf.Min(Time.deltaTime,.1f);
            Vector3 target=(Vector3)Get(motor,"PlayerPosition"), to=target-actor.transform.position;to.y=0;
            Vector3 line=target+Vector3.up*.7f-(actor.transform.position+Vector3.up*.6f);
            bool lineHit=Physics.Raycast(actor.transform.position+Vector3.up*.6f,line.normalized,out var first,line.magnitude,~0,QueryTriggerInteraction.Ignore);
            result.attackLineHit=lineHit?Describe(first):null;
            result.clearAttackLine=!lineHit || first.collider.transform.IsChildOf(vehicle) || first.collider.transform==walker.transform;
            Vector3 displacement=Vector3.zero; Quaternion rotation=actor.transform.rotation; bool tangent=false;
            if(b.phase=="Stalk")
            {
                if(to.magnitude>34) { to=(Vector3)Field(actor,"home")-actor.transform.position;to.y=0;displacement=to.normalized*2*dt; result.route="home-forward-then-tangent-if-blocked";tangent=true; }
                else
                {
                    if(to.sqrMagnitude>.001f) rotation=Quaternion.Slerp(rotation,Quaternion.LookRotation(to),dt*7);
                    if(to.magnitude<5.2f && result.clearAttackLine) result.route="windup-eligible-no-move";
                    else { displacement=to.normalized*2.7f*dt;result.route="stalk-forward-then-tangent-if-blocked";tangent=true; }
                }
                if(to.magnitude<.3f) displacement=Vector3.zero;
            }
            else if(b.phase=="Attack") { displacement=(Vector3)Field(actor,"attackDirection")*8*dt;result.route="attack-forward"; }
            Capsule(actor,rotation,out result.queryBottom,out result.queryTop);
            if(displacement.magnitude>=.0001f)
            {
                result.forward=CapsuleQuery(actor,result.queryBottom,result.queryTop,b.radius,displacement);
                if(tangent) result.tangent=CapsuleQuery(actor,result.queryBottom,result.queryTop,b.radius,Vector3.Cross(Vector3.up,to.normalized)*displacement.magnitude*.6f);
            }
            return result;
        }
        Query CapsuleQuery(Component actor,Vector3 bottom,Vector3 top,float radius,Vector3 displacement)
        {
            int count=Physics.CapsuleCastNonAlloc(bottom,top,radius,displacement.normalized,aiRaw,displacement.magnitude+.04f,~0,QueryTriggerInteraction.Ignore);
            var full=Physics.CapsuleCastAll(bottom,top,radius,displacement.normalized,displacement.magnitude+.04f,~0,QueryTriggerInteraction.Ignore);
            return Compare(aiRaw,count,full,displacement.normalized,displacement.magnitude+.04f,actor);
        }
        Query Compare(RaycastHit[] raw,int count,RaycastHit[] full,Vector3 direction,float distance,Component ai)
        {
            Func<RaycastHit,bool> eligible=h=>h.collider && (ai ? !h.collider.transform.IsChildOf(ai.transform) && h.normal.y<.65f : !h.collider.transform.IsChildOf(vehicle) && h.collider!=walker && h.normal.y<=.65f);
            var r=raw.Take(count).Where(eligible).OrderBy(h=>h.distance).ToArray();var f=full.Where(eligible).OrderBy(h=>h.distance).ToArray();
            return new Query {performed=true,rawCount=count,fullCount=full.Length,saturated=count==raw.Length,rawIds=raw.Take(count).Select(h=>Id(h.collider)).ToArray(),fullIds=full.Select(h=>Id(h.collider)).ToArray(),
                nearestRaw=r.Length>0?Describe(r[0]):null,nearestFull=f.Length>0?Describe(f[0]):null,direction=direction,distance=distance};
        }
        ArcObservation ObserveArc()
        {
            object[] args={null,0f,null}; bool ready=(bool)Call(actions,"CheckArcSource",args);
            var source=(Transform)Field(actions,"arcOrigin");var combat=Field(actions,"arc");
            var a=new ArcObservation {sourceReady=ready,sourceBlocker=Id((Collider)args[0]),sourceSquareDistance=float.IsNaN((float)args[1])||float.IsInfinity((float)args[1])?0:(float)args[1],
                sourceDistanceFinite=!float.IsNaN((float)args[1])&&!float.IsInfinity((float)args[1]),sourceSquareDistanceRaw=((float)args[1]).ToString("R",System.Globalization.CultureInfo.InvariantCulture),sourceQuery=(string)args[2],
                origin=source.position,pulseId=(int)Get(combat,"PulseId"),cooldown=(double)Get(combat,"CooldownRemaining")};
            var inRange=Physics.OverlapSphere(source.position,5,~0,QueryTriggerInteraction.Ignore);
            a.targets=actors.Select(actor=> {var c=actor.GetComponent<Collider>();bool hit=Physics.Linecast(source.position,c.bounds.center,out var first,~0,QueryTriggerInteraction.Ignore);
                return new ArcTarget {beast=actor.GetInstanceID(),centerDistance=Vector3.Distance(source.position,c.bounds.center),surfaceDistance=Vector3.Distance(source.position,c.ClosestPoint(source.position)),
                    inRange=inRange.Contains(c),clearLine=!hit || first.collider.GetComponentInParent(T("BeastActor"))==actor,firstLOSBlocker=hit?Describe(first):null};}).ToArray();
            return a;
        }
        Hit Describe(RaycastHit h)
        {
            var c=h.collider;var beast=c?c.GetComponentInParent(T("BeastActor")):null;
            return new Hit {present=c,collider=Id(c),distance=h.distance,point=h.point,normal=h.normal,self=c && c.transform.IsChildOf(vehicle),walker=c==walker,upward=h.normal.y>.65f,beast=beast,dead=beast && (bool)Get(beast,"Dead")};
        }
        int Id(Collider c)
        {
            if(!c)return 0;if(colliderIds.TryGetValue(c,out int id))return id;
            id=colliderIds.Count+1;colliderIds.Add(c,id);var path=new List<string>();for(var t=c.transform;t;t=t.parent)path.Add(t.name);path.Reverse();
            report.colliders.Add(new ColliderIdentity {id=id,instanceId=c.GetInstanceID(),scene=c.gameObject.scene.path,path=string.Join("/",path),type=c.GetType().Name,trigger=c.isTrigger,min=c.bounds.min,max=c.bounds.max,
                role=c.transform.IsChildOf(vehicle)?"retained-rv":c==walker?"walker":c.GetComponentInParent(T("BeastActor"))?"beast":"world"});return id;
        }
        static string Hash(string path) {using(var sha=SHA256.Create())using(var stream=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();}
        void PinFile(string path) {Assert.That(File.Exists(path),Is.True,"PIN_MISSING:"+path);if(!report.sourceFiles.Any(p=>p.path==path))report.sourceFiles.Add(new Pin {path=path,sha256=Hash(path)});}
        void VerifyDependencies()
        {
            PinFile(InputPath);PinFile(Path.ChangeExtension(InputPath,"sha256"));report.dependencyCheck.inputSha256=Hash(InputPath);
            Assert.That(File.ReadAllText(Path.ChangeExtension(InputPath,"sha256")).Trim(),Is.EqualTo(report.dependencyCheck.inputSha256));
            input=JsonUtility.FromJson<ConsumerInput>(File.ReadAllText(InputPath));
            Assert.That(input.schema,Is.EqualTo(1));Assert.That(input.status,Is.EqualTo("VERIFIED_2915_PREPARED_WITH_EXPLICIT_SOURCE_AND_SCENE_OVERLAY_NOT_APPROVED"));
            Assert.That(input.producerCommit,Is.EqualTo(Producer));Assert.That(input.currentProductionCommit,Is.EqualTo(input.consumerCommit));
            Assert.That(input.producerRunId,Is.EqualTo("38091066745"));Assert.That(input.producerArtifactSha256,Is.EqualTo("98448f817201ca54b7206ba535040a6ef5641bc2151c0da8ebe3fcb6caa60957"));
            Assert.That(input.consumerCommit,Is.EqualTo(Environment.GetEnvironmentVariable("GITHUB_SHA")));
            report.producerCommit=input.producerCommit;report.consumerCommit=input.consumerCommit;report.producerRunId=input.producerRunId;
            var owner=Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor",true);
            var snapshot=owner.GetMethod("DependencySnapshot",BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic);
            var actual=((Array)snapshot.Invoke(null,null)).Cast<object>().Select(d=>new Dependency {path=(string)Field(d,"path"),sha256=(string)Field(d,"sha256"),bytes=(long)Field(d,"bytes"),kind=(string)Field(d,"kind"),packageName=(string)Field(d,"packageName"),packageVersion=(string)Field(d,"packageVersion")}).ToDictionary(d=>d.path);
            var expected=input.dependencies.ToDictionary(d=>d.path);var check=report.dependencyCheck;check.expectedCount=expected.Count;check.actualCount=actual.Count;
            check.mismatches=expected.Keys.Union(actual.Keys).Where(p=>!expected.ContainsKey(p)||!actual.ContainsKey(p)||JsonUtility.ToJson(expected[p])!=JsonUtility.ToJson(actual[p])).OrderBy(p=>p).ToArray();
            Assert.That(input.derivedReceiptSha256!=null && input.derivedReceiptSha256.Length==64 && input.derivedReceiptSha256.All(c=>c>='0'&&c<='9'||c>='a'&&c<='f'),Is.True,"DERIVED_RECEIPT_HASH");
            Assert.That(input.productionSourceOverlay,Is.Not.Null.And.Not.Empty,"SOURCE_OVERLAY_REQUIRED");
            Assert.That(input.dependencyChanges,Is.Not.Null.And.Not.Empty,"DECLARED_OVERLAY_REQUIRED");
            var changed=input.dependencyChanges.Select(c=>c.path).ToArray();
            Assert.That(changed.SequenceEqual(changed.Distinct().OrderBy(p=>p,StringComparer.Ordinal)),Is.True,"DECLARED_OVERLAY_ORDER");
            foreach(var change in input.dependencyChanges)
            {
                Assert.That(change.path.StartsWith("Assets/DesertRV/",StringComparison.Ordinal) && !change.path.Contains("..") && !change.path.Contains("\\") && expected.ContainsKey(change.path),Is.True,"DECLARED_OVERLAY_PATH");
                Assert.That(change.after,Is.Not.Null);
                Assert.That(change.after.sha256,Is.EqualTo(expected[change.path].sha256));Assert.That(change.after.bytes,Is.EqualTo(expected[change.path].bytes));
                Assert.That(change.after.bytes,Is.GreaterThan(0));
                // JsonUtility can materialize a null inline class as its empty default.
                // The sealed input was already checked for exact null-vs-object shape by the host.
                bool added=change.before==null || string.IsNullOrEmpty(change.before.sha256) && change.before.bytes==0;
                Assert.That(added || change.before.sha256!=null && change.before.sha256.Length==64 && change.before.sha256.All(c=>c>='0'&&c<='9'||c>='a'&&c<='f') && change.before.bytes>0,Is.True,"DECLARED_OVERLAY_BEFORE");
                Assert.That(added || change.before.sha256!=change.after.sha256 || change.before.bytes!=change.after.bytes,Is.True,"DECLARED_OVERLAY_CHANGED");
            }
            Assert.That(check.expectedCount,Is.EqualTo(798));Assert.That(check.actualCount,Is.EqualTo(798));Assert.That(check.mismatches,Is.Empty,"DEPENDENCY_BYTES_DIFFER");check.passed=true;Write();
        }
        void Write()
        {
            if(report==null)return;
            Assert.That(report.sequences.Sum(s=>s.frames.Count),Is.LessThanOrEqualTo(MaxFrames));
            var json=JsonUtility.ToJson(report,false);Assert.That(System.Text.Encoding.UTF8.GetByteCount(json),Is.LessThan(24*1024*1024));
            Directory.CreateDirectory(Folder);File.WriteAllText(Output,json+"\n");
        }
        [UnityTearDown] public IEnumerator Cleanup()
        {
            recording=false;
            bool finalPawsObserved=report==null || report.status!="completed";
            if(adapter && observerHost){Call(adapter,"DetachEditorReplay",observerHost);report.replayDetached=!(bool)Get(adapter,"EditorReplayActive");}
            if(motor && contactListener!=null)motor.GetType().GetEvent("ObstacleContact").RemoveEventHandler(motor,contactListener);
            if(actions && arcListener!=null)actions.GetType().GetEvent("ArcPresented").RemoveEventHandler(actions,arcListener);
            // Let the last recorded Update frame finish its ordinary paw LateUpdate with
            // its director and PhysicsScene intact. This released-input cleanup wait is not
            // part of the 1212-frame recording; all native errors still fail the test.
            if(ownsR3)
            {
                regionScene=SceneManager.GetSceneByPath(R3);
                if(regionScene.IsValid()&&regionScene.isLoaded)
                {
                    int lastRecordedFrame=report==null ? -1 : report.sequences.SelectMany(s=>s.frames).Select(f=>f.frame).DefaultIfEmpty(-1).Last();
                    int waitFrame=Time.frameCount;
                    var eligible=Array.Empty<Component>(); bool witnessReadFailed=false;
                    try
                    {
                        eligible=Components(regionScene,"PouncerPawContactConstraint").Where(p=>
                        {
                            var animation=(Animator)Field(p,"animator");
                            return ((Behaviour)p).isActiveAndEnabled && animation && animation.isActiveAndEnabled &&
                                animation.speed>0 && Time.timeScale>0;
                        }).ToArray();
                    }
                    catch { witnessReadFailed=true; }
                    yield return null;
                    int freshValidCount=0,missingCount=0,minReportFrame=-1,maxReportFrame=-1;
                    foreach(var paw in eligible)
                    {
                        try
                        {
                            object last=paw ? Field(paw,"lastReport") : null;
                            if(last==null){missingCount++;continue;}
                            int observed=(int)Field(last,"frame");
                            minReportFrame=minReportFrame<0 ? observed : Mathf.Min(minReportFrame,observed);
                            maxReportFrame=Mathf.Max(maxReportFrame,observed);
                            if(observed>=waitFrame && observed>=lastRecordedFrame && (bool)Field(last,"valid") && !(bool)Get(paw,"HasFailure"))freshValidCount++;
                        }
                        catch { witnessReadFailed=true;missingCount++; }
                    }
                    finalPawsObserved=!witnessReadFailed && missingCount==0 && freshValidCount==eligible.Length &&
                        (eligible.Length>0 || report==null || report.status!="completed");
                    Debug.Log("R3 final paw observation: recordedFrame="+lastRecordedFrame+"; waitFrame="+waitFrame+
                        "; minReportFrame="+minReportFrame+"; maxReportFrame="+maxReportFrame+"; eligibleCount="+eligible.Length+
                        "; freshValidCount="+freshValidCount+"; missingCount="+missingCount+"; witnessReadFailed="+witnessReadFailed);
                }
                // Match RegionLoader: stop the owned environment before destroying its
                // session or unloading its scene. Recheck after the cleanup wait.
                regionScene=SceneManager.GetSceneByPath(R3);
                if(regionScene.IsValid()&&regionScene.isLoaded)
                    foreach(var root in regionScene.GetRootGameObjects())if(root.activeSelf)root.SetActive(false);
            }
            if(director)Object.DestroyImmediate(director.gameObject);
            if(originalActive.IsValid() && originalActive.isLoaded)SceneManager.SetActiveScene(originalActive);
            if(ownsR3){regionScene=SceneManager.GetSceneByPath(R3);if(regionScene.IsValid()&&regionScene.isLoaded)yield return SceneManager.UnloadSceneAsync(regionScene);}
            if(ownsBootstrap){bootstrapScene=SceneManager.GetSceneByPath(Bootstrap);if(bootstrapScene.IsValid()&&bootstrapScene.isLoaded)yield return SceneManager.UnloadSceneAsync(bootstrapScene);}
            if(report!=null)
            {
                Time.captureDeltaTime=report.originalCaptureDelta;Time.timeScale=report.originalTimeScale;
                report.timeRestored=Mathf.Approximately(Time.captureDeltaTime,report.originalCaptureDelta)&&Time.timeScale==report.originalTimeScale&&Time.fixedDeltaTime==report.originalFixedDelta;
                report.sceneUnloaded=!SceneManager.GetSceneByPath(Bootstrap).isLoaded&&!SceneManager.GetSceneByPath(R3).isLoaded;
                report.sourceFilesUnchanged=report.sourceFiles.All(p=>File.Exists(p.path)&&Hash(p.path)==p.sha256);
                Write();Assert.That(report.sceneUnloaded&&report.sourceFilesUnchanged&&report.timeRestored,Is.True,"CLEANUP_OR_SOURCE_MUTATION");
            }
            Cursor.lockState=oldLock;Cursor.visible=oldCursor;
            Assert.That(finalPawsObserved,Is.True,"FINAL_RECORDED_PAW_LATEUPDATE_MISSING_OR_FAILED");
        }
    }
}
#endif
