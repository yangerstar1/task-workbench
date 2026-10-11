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
    // Observers only: the real Session (-100), BeastActor (0), Director (50), Animator
    // and paw constraint (LateUpdate 1500) keep their normal lifecycle and ordering.
    [DefaultExecutionOrder(-50)] public sealed class PreparedSupportBeforeAI : MonoBehaviour
    { public Action sample; void Update() { sample?.Invoke(); } }
    [DefaultExecutionOrder(2000)] public sealed class PreparedSupportAfterPaws : MonoBehaviour
    { public Action sample; void LateUpdate() { sample?.Invoke(); } }

    public sealed class JourneyPouncerPreparedSupportTests
    {
        const string Bootstrap = "Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity";
        const string R3 = "Assets/DesertRV/Scenes/Journey/NightBeacon.unity";
        const string Folder = "JourneyEvidence/PouncerGroundSupport/";
        const string InputPath = Folder + "focused-input.json";
        const string Output = Folder + "native-focused-support.json";
        const string Producer = "2915b8b1e5be8b800a3d71f186b5316a8f626bc8";
        const string GeneratedReceipt = "e25634798fd3ed6d90758225ea1952b95691a6aada5e3b6f545f04c6696d66ba";
        const float RootTolerance = .0001f, PawFloorTolerance = .004f, PawMaximumCorrection = .100f;
        const BindingFlags Any = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Get(object target, string name) => target.GetType().GetProperty(name, Any).GetValue(target);
        static object Field(object target, string name) => target.GetType().GetField(name, Any).GetValue(target);
        static void Set(object target, string name, object value) => target.GetType().GetField(name, Any).SetValue(target, value);
        static object Call(object target, string name, params object[] args) => target.GetType().GetMethod(name, Any).Invoke(target, args);
        static object E(string type, string value) => Enum.Parse(T(type), value);
        static Component[] Components(Scene scene, string name) => scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren(T(name), true)).Cast<Component>().ToArray();

        [Serializable] public sealed class Pin { public string path, sha256; }
        [Serializable] public sealed class ScenePin { public string path, sha256, metaSha256; }
        [Serializable] public sealed class Input
        {
            public int schema; public string status, sourceCommit, producerCommit, producerGeneratedReceiptSha256, derivedReceiptSha256;
            public Pin[] sourcePins; public ScenePin[] scenes;
        }
        [Serializable] public sealed class Case
        {
            public string name;
            public float captureDelta, aiDelta, actualDeltaMin, actualDeltaMax;
            public int frameBound, frames, firstFrame, lastFrame, stalkFrames, windupFrames, walkFrames, animatorWindupFrames;
            public int stalkToWindupCount, walkToWindupCount, blendedWalkToWindupFrames, riseCount, dropCount, mixedSupportSamples;
            public int lowSupportSamples, highSupportSamples, selectedSoleVertices, correctedLegFrames, aiMovementFrames;
            public int independentSamples, independentCrossingSamples, independentTransitionSamples;
            public int deathFrames, resetFrames;
            public Vector3 fixtureActorRoot, initialRoot, finalRoot, target;
            public float initialSupportY, finalSupportY, measuredSurfaceRise, horizontalTravel;
            public float maxRootStep, maxRootSupportError, maxRootCenterGroundDelta, maxPawCorrection, maxPawResidual, maxCorrectedClearanceError, maxSkinningAgreementError;
            public bool completed, actorYUnchangedAtSetup, boundSupportValid, modelUnchanged, targetStationary, lifecycleCompleted;
        }
        [Serializable] public sealed class Report
        {
            public int schema = 1; public string status = "INCOMPLETE_FOCUSED_SUPPORT_UNREVIEWED", sourceCommit = "", producerCommit = Producer;
            public string producerGeneratedReceiptSha256 = GeneratedReceipt, derivedReceiptSha256 = "", inputSha256 = "", unityVersion;
            public string failureCode = ""; public int nativeErrorCount, sourcePinCount, scenePinCount;
            public bool approved, inputVerified, replayDetached, scenesUnloaded, originalScenesPreserved, sourcesUnchanged, timeRestored, cursorRestored;
            public List<Case> cases = new List<Case>();
        }
        sealed class Skin
        {
            internal SkinnedMeshRenderer renderer; internal Mesh source; internal Transform[] bones; internal int[] vertices;
        }

        Report report; Input input; Case current; Scene originalActive, regionScene;
        Scene[] originalScenes; Component director, session, motor, region, actor, paws, support, adapter;
        object state; Transform vehicle; Animator animator; RuntimeAnimatorController controller;
        GameObject observer; BoxCollider foundation, road; Skin[] skins; MethodInfo measure;
        Vector3 beforeAI, previousRoot; string beforePhase, previousAnimation; int sampledFrame = -1;
        bool recording, ownsBootstrap, ownsRegion, callbackAttached, observerFailed, sawWalk, cleanupFailed;
        float oldCapture, oldScale, oldFixed; CursorLockMode oldLock; bool oldCursor;
        enum LifecyclePhase { None, Death, Reset }
        LifecyclePhase lifecycle; Vector3 deathRoot, lifecycleTarget; CapsuleCollider hurtbox;
        AnimationClip deathClip; float deathElapsed; int lifecycleLastFrame = -1, resetMovingFrames, resetWalkFrames;
        bool deathFinished;

        [UnityTest, Timeout(600000)] public IEnumerator RealPreparedR3_PouncerCrossesSupportAtBothCadences()
        {
            var routine = Run();
            while (true)
            {
                bool more;
                try { more = routine.MoveNext(); }
                catch
                {
                    Fail("TEST_EXCEPTION"); Write(); throw; // Preserve native NUnit failure and a bounded partial report.
                }
                if (!more) break;
                yield return routine.Current;
            }
        }

        IEnumerator Run()
        {
            originalActive = SceneManager.GetActiveScene();
            originalScenes = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            oldCapture = Time.captureDeltaTime; oldScale = Time.timeScale; oldFixed = Time.fixedDeltaTime;
            oldLock = Cursor.lockState; oldCursor = Cursor.visible;
            report = new Report { unityVersion = Application.unityVersion };
            Application.logMessageReceived += NativeLog; callbackAttached = true;
            Write(); VerifyInput();
            Require(Application.isPlaying, "NOT_PLAYMODE");
            Require(Object.FindObjectsByType(T("JourneyDirector"), FindObjectsSortMode.None).Length == 0, "FOREIGN_DIRECTOR");
            Require(!SceneManager.GetSceneByPath(Bootstrap).isLoaded && !SceneManager.GetSceneByPath(R3).isLoaded, "SOURCE_ALREADY_LOADED");
            Time.captureDeltaTime = 1f / 30; Time.timeScale = 1;
            ownsBootstrap = true;
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(Bootstrap, new LoadSceneParameters(LoadSceneMode.Additive));
            director = (Component)Object.FindObjectsByType(T("JourneyDirector"), FindObjectsSortMode.None).Single();
            Require((bool)Get(director, "OwnsJourney"), "DIRECTOR_OWNER");
            session = (Component)Field(director, "journey"); motor = (Component)Field(director, "motor");
            state = Get(session, "State"); adapter = (Component)Get(session, "Input"); vehicle = (Transform)Field(motor, "vehicle");
            ownsRegion = true;
            yield return EditorSceneManager.LoadSceneAsyncInPlayMode(R3, new LoadSceneParameters(LoadSceneMode.Additive));
            regionScene = SceneManager.GetSceneByPath(R3);
            Require(SceneManager.SetActiveScene(regionScene), "ACTIVE_SCENE");
            region = Components(regionScene, "RegionBinding").Single();
            Require((int)Field(region, "region") == 3, "REGION_ID");
            var wave = (Array)Field(((Array)Field(region, "waves")).GetValue(0), "enemies");
            Require(wave.Length == 2, "FIRST_WAVE_INVENTORY"); actor = (Component)wave.GetValue(0);
            Require(!(bool)Field(actor, "armored"), "POUNCER_REQUIRED");
            paws = actor.GetComponent(T("PouncerPawContactConstraint")); support = actor.GetComponent(T("PouncerGroundSupport"));
            animator = (Animator)Field(actor, "animator"); controller = animator.runtimeAnimatorController;
            Require(paws && support && controller && animator.enabled && !animator.applyRootMotion, "SAVED_MODEL_BINDING");
            Require(Field(support, "actor") == actor && Field(support, "paws") == paws && Field(support, "region") == region, "SAVED_SUPPORT_BINDING");
            Require((float)Field(paws, "maxCorrectionMeters") == PawMaximumCorrection, "UNCHANGED_PAW_BUDGET");
            var floors = ((Array)Field(region, "pouncerSupportSurfaces")).Cast<BoxCollider>().ToArray();
            Require(floors.Length == 2, "SAVED_SUPPORT_INVENTORY");
            foundation = floors.Single(f => f.name == "Route foundation"); road = floors.Single(f => f.name == "Road surface");
            Require(Mathf.Abs(foundation.bounds.max.y + .04f) < RootTolerance && Mathf.Abs(road.bounds.max.y - .035f) < RootTolerance, "PREPARED_SUPPORT_HEIGHTS");
            Require(Mathf.Abs(road.bounds.min.x + 4) < RootTolerance && Mathf.Abs(road.bounds.max.x - 4) < RootTolerance, "PREPARED_ROAD_EDGE");
            Require(Object.FindObjectsByType<Collider>(FindObjectsSortMode.None).Where(c => c.enabled && !c.isTrigger)
                .All(c => c.gameObject.scene == regionScene || c.transform.IsChildOf(director.transform)), "FOREIGN_COLLIDER");
            var measurement = Type.GetType("DesertRV.Editor.JourneyCandidateMeshMeasurement, Assembly-CSharp-Editor", true);
            measure = measurement.GetMethod("GetWorldVertices", BindingFlags.Static | BindingFlags.Public);
            BuildSoleInventory();
            observer = new GameObject("Prepared support read-only observers"); SceneManager.MoveGameObjectToScene(observer, regionScene);
            observer.AddComponent<PreparedSupportBeforeAI>().sample = () => ObserveSafely(BeforeAI);
            observer.AddComponent<PreparedSupportAfterPaws>().sample = () => ObserveSafely(AfterPaws);
            Call(adapter, "AttachEditorReplay", observer); Call(adapter, "SetEditorReplayFingers", observer, Array.Empty<int>()); Call(adapter, "ReleaseAll");
            yield return null; // Ordinary input screen/safe-area reconciliation before the cases.
            foreach (bool lowCadence in new[] { false, true }) foreach (bool drop in new[] { false, true })
            {
                Time.captureDeltaTime = lowCadence ? .2f : 1f / 30; yield return null;
                SetupCase(drop, lowCadence); recording = true;
                for (int frame = 0; frame < current.frameBound && !current.completed; frame++)
                {
                    yield return null;
                    Require(!observerFailed && report.nativeErrorCount == 0, "NATIVE_OR_OBSERVER_FAILURE");
                }
                recording = false;
                Require(current.completed, "CROSSING_OR_TRANSITION_NOT_OBSERVED"); Write();
                var life = ObserveLifecycle();
                while (life.MoveNext()) yield return life.Current; // Keep lifecycle exceptions inside the outer first-error recorder.
                actor.gameObject.SetActive(false); // Between-case fixture cleanup only.
            }
            Require(report.cases.Count == 4 && report.cases.All(c => c.completed && c.lifecycleCompleted), "CASE_INVENTORY");
            report.status = "COMPLETED_FOCUSED_SUPPORT_UNREVIEWED"; Write();
        }

        void SetupCase(bool drop, bool lowCadence)
        {
            // Explicit fixture restoration only. No actor/target placement occurs in recorded frames.
            recording = false; sampledFrame = -1; previousAnimation = ""; sawWalk = false;
            if ((int)Get(session, "Generation") == 0) Require((bool)Call(session, "StartJourney"), "START_JOURNEY");
            else Call(state, "ResetJourney");
            foreach (string part in new[] { "RamPart", "Coil" })
            {
                Require((bool)Call(state, "TryCollect", "prepared-support/" + part, E("ComponentPart", part)), "FIXTURE_COLLECT");
                Require((bool)Call(state, "TryInstall", E("ComponentPart", part)), "FIXTURE_INSTALL");
            }
            for (int i = 0; i < 2; i++)
            {
                Call(state, "SetObjectivesResolved", true);
                Require((bool)Call(state, "TryAdvance") && (bool)Call(state, "CompleteLoading"), "FIXTURE_ADVANCE");
            }
            Set(director, "pending", Call(session, "BeginCurrentRegionLoad"));
            Set(director, "progress", Activator.CreateInstance(T("RegionProgressState"), state, Get(session, "Generation")));
            Require((bool)Call(director, "BindRegion", region), "PRODUCTION_BIND_R3");
            // Preserve the saved authored actor Y, including for the high-side fixture. The
            // first normal production LateUpdate establishes the start-support baseline.
            float authoredY = actor.transform.position.y;
            var root = new Vector3(drop ? -1 : -10, authoredY, 14);
            var target = new Vector3(drop ? -13 : 3.5f, vehicle.position.y, 14);
            actor.transform.SetPositionAndRotation(root, Quaternion.LookRotation(new Vector3(target.x - root.x, 0, 0)));
            Call(motor, "PlaceForRegion", target, Quaternion.identity);
            Call(session, "ResetPositionSample", Call(region, "WorldProgress", target));
            Call(state, "SetPowerConnected", false); Call(session, "ApplyContext");
            Call(adapter, "ReleaseAll"); actor.gameObject.SetActive(true);
            Physics.SyncTransforms(); // Setup only; production owns all recorded-frame synchronization.
            object[] args = { null }; bool valid = (bool)Call(support, "ValidateBindings", args);
            current = new Case { name = (drop ? "drop-" : "rise-") + (lowCadence ? "5hz" : "30hz"),
                captureDelta = Time.captureDeltaTime, aiDelta = Mathf.Min(Time.captureDeltaTime, .1f),
                frameBound = lowCadence ? 120 : 240, fixtureActorRoot = root, target = target,
                actorYUnchangedAtSetup = actor.transform.position.y == authoredY, boundSupportValid = valid,
                selectedSoleVertices = skins.Sum(s => s.vertices.Length), modelUnchanged = true, targetStationary = true };
            report.cases.Add(current); Require(valid && current.actorYUnchangedAtSetup, "FIXTURE_BINDINGS"); Write();
        }

        IEnumerator ObserveLifecycle()
        {
            // Fixture actions happen between stages. Observation starts only on a new full
            // BeforeAI/Animator/LateUpdate frame; no clip sampling or actor placement here.
            hurtbox = actor.GetComponent<CapsuleCollider>();
            var clips = controller.animationClips.Where(c => c.name == "Death").Distinct().ToArray();
            Require(clips.Length == 1 && clips[0] && !clips[0].isLooping &&
                Mathf.Abs(clips[0].length - 1.8f) <= RootTolerance, "DEATH_LIFECYCLE");
            deathClip = clips[0]; deathRoot = actor.transform.position; lifecycleTarget = vehicle.position;
            deathElapsed = 0; deathFinished = false; sampledFrame = lifecycleLastFrame = -1;
            int health = (int)Get(actor, "Health");
            Require(health > 0 && hurtbox && hurtbox.enabled, "DEATH_LIFECYCLE");
            Call(actor, "TakeHit", health, actor.transform.forward, false);
            Require((bool)Get(actor, "Dead") && (int)Get(actor, "Health") == 0 && !hurtbox.enabled &&
                actor.transform.position.Equals(deathRoot), "DEATH_LIFECYCLE");
            lifecycle = LifecyclePhase.Death; Write();
            for (int frame = 0; frame < current.frameBound && !deathFinished; frame++)
            {
                yield return null;
                Require(!observerFailed && report.nativeErrorCount == 0, "NATIVE_OR_OBSERVER_FAILURE");
            }
            Require(deathFinished, "LIFECYCLE_TIMEOUT");
            var deathEnd = animator.GetCurrentAnimatorStateInfo(0);
            Debug.Log("Prepared support Death complete " + current.name + ": frames=" + current.deathFrames +
                "; normalized=" + deathEnd.normalizedTime + "; seconds=" + deathEnd.length +
                "; inTransition=" + animator.IsInTransition(0) + "; root=" + deathRoot.ToString("F6"));
            lifecycle = LifecyclePhase.None; sampledFrame = lifecycleLastFrame = -1;
            // ResetActor owns the authored home. Move only the real motor's fixture target
            // near that home, so ordinary Idle -> Stalk can wake and move after reset.
            var home = (Vector3)Field(actor, "home");
            lifecycleTarget = new Vector3(0, vehicle.position.y, home.z);
            float targetDistance = new Vector2(lifecycleTarget.x - home.x, lifecycleTarget.z - home.z).magnitude;
            Require(targetDistance > 5.2f && targetDistance < 19, "RESET_LIFECYCLE");
            Call(motor, "PlaceForRegion", lifecycleTarget, Quaternion.identity);
            Call(session, "ResetPositionSample", Call(region, "WorldProgress", lifecycleTarget));
            Call(actor, "ResetActor");
            Require(!(bool)Get(actor, "Dead") && Get(actor, "Phase").ToString() == "Idle" &&
                (int)Get(actor, "Health") == health && hurtbox.enabled && !(bool)Get(paws, "HasFailure") &&
                actor.transform.position.Equals(home), "RESET_LIFECYCLE");
            Debug.Log("Prepared support lifecycle " + current.name + ": home=" + home.ToString("F6") +
                "; reset target=" + lifecycleTarget.ToString("F6") + "; Death clip seconds=" + deathClip.length);
            resetMovingFrames = resetWalkFrames = 0; lifecycle = LifecyclePhase.Reset; Write();
            for (int frame = 0; frame < current.frameBound && !current.lifecycleCompleted; frame++)
            {
                yield return null;
                Require(!observerFailed && report.nativeErrorCount == 0, "NATIVE_OR_OBSERVER_FAILURE");
            }
            Require(current.lifecycleCompleted, "LIFECYCLE_TIMEOUT");
            Debug.Log("Prepared support Reset complete " + current.name + ": frames=" + current.resetFrames +
                "; AI moving frames=" + resetMovingFrames + "; settled Walk frames=" + resetWalkFrames +
                "; phase=" + Get(actor, "Phase") + "; root=" + actor.transform.position.ToString("F6"));
            lifecycle = LifecyclePhase.None; sampledFrame = -1; Write();
        }

        void BeforeAI()
        {
            sampledFrame = Time.frameCount; beforeAI = actor.transform.position; beforePhase = Get(actor, "Phase").ToString();
            Require(Mathf.Abs(Time.deltaTime - current.captureDelta) < .00001f && Time.timeScale == 1, "CAPTURE_CADENCE");
            Require(Get(state, "Status").ToString() == "Playing", "PLAYING_REQUIRED");
            Require((float)Get(adapter, "Throttle") == 0 && (Vector2)Get(adapter, "Movement") == Vector2.zero, "STATIONARY_INPUT_REQUIRED");
        }
        void AfterPaws()
        {
            if (sampledFrame != Time.frameCount) return; // Recording can begin after this frame's BeforeAI.
            if (lifecycle != LifecyclePhase.None) { AfterLifecyclePaws(); return; }
            Require(current.frames < current.frameBound, "FRAME_BOUND");
            if (current.frames > 0) Require(Time.frameCount == current.lastFrame + 1, "OBSERVATION_GAP");
            var root = actor.transform.position; string phase = Get(actor, "Phase").ToString();
            object pawReport = Field(paws, "lastReport");
            Require(pawReport != null && (int)Field(pawReport, "frame") == Time.frameCount, "PAW_REPORT_FRESH");
            Require((bool)Field(pawReport, "valid") && !(bool)Get(paws, "HasFailure"), "PAW_REPORT_FAILED");
            Require(animator.enabled && animator.speed == 1 && animator.runtimeAnimatorController == controller && !animator.applyRootMotion,
                "ANIMATOR_CHANGED");
            current.modelUnchanged &= skins.All(s => s.renderer.sharedMesh == s.source && s.renderer.bones.SequenceEqual(s.bones));
            current.targetStationary &= Vector3.Distance(vehicle.position, current.target) < RootTolerance;
            Require(current.modelUnchanged && current.targetStationary, "FIXTURE_MUTATED");
            var legs = ((IEnumerable)Field(pawReport, "legs")).Cast<object>().ToArray(); Require(legs.Length == 4, "LEG_REPORT_INVENTORY");
            string animation = (string)Field(legs[0], "sourceState"), destination = (string)Field(legs[0], "destinationState");
            if (phase == "Stalk") current.stalkFrames++;
            if (phase == "Windup") current.windupFrames++;
            if (animation == "Walk") { current.walkFrames++; sawWalk = true; }
            if (animation == "Windup") current.animatorWindupFrames++;
            if (beforePhase == "Stalk" && phase == "Windup") current.stalkToWindupCount++;
            if (animation == "Walk" && destination == "Windup") current.blendedWalkToWindupFrames++;
            if (sawWalk && animation == "Windup" && previousAnimation != "Windup") current.walkToWindupCount++;
            foreach (var leg in legs)
            {
                Require((bool)Field(leg, "valid"), "LEG_INVALID");
                float correction = (float)Field(leg, "correctionMeters"), distance = (float)Field(leg, "postMinDistance");
                Require(Finite(correction) && Finite(distance), "NONFINITE_SAMPLE");
                current.maxPawCorrection = Mathf.Max(current.maxPawCorrection, correction);
                current.maxPawResidual = Mathf.Max(current.maxPawResidual, Mathf.Max(0, -distance));
                Require(correction <= PawMaximumCorrection && distance >= -PawFloorTolerance, "PAW_LIMIT");
                if ((bool)Field(leg, "corrected"))
                {
                    current.correctedLegFrames++;
                    float error = Mathf.Abs(distance - (float)Field(leg, "targetClearance"));
                    current.maxCorrectedClearanceError = Mathf.Max(current.maxCorrectedClearanceError, error);
                    Require(error <= .0002f, "CORRECTED_CLEARANCE");
                }
            }
            float rootGround = SupportAt(root, out _);
            current.maxRootCenterGroundDelta = Mathf.Max(current.maxRootCenterGroundDelta, Mathf.Abs(root.y - rootGround));
            bool heightChanged = current.frames > 0 && Mathf.Abs(root.y - previousRoot.y) > RootTolerance;
            bool transitionWitness = phase == "Windup" || animation == "Walk" && destination == "Windup";
            // Full BakeMesh/LBS checks are bounded to witnesses: the settled initial frame,
            // every root-height crossing and all Windup/Walk-to-Windup frames. Paw reports
            // retain their original .100/.004 gates on every observed frame.
            if (current.frames == 0 || heightChanged || transitionWitness)
            {
                current.independentSamples++;
                if (heightChanged) current.independentCrossingSamples++;
                if (transitionWitness) current.independentTransitionSamples++;
                current.finalSupportY = MeasureActualSupport(rootGround);
                current.maxRootSupportError = Mathf.Max(current.maxRootSupportError, Mathf.Abs(root.y - current.finalSupportY));
                Require(current.maxRootSupportError <= RootTolerance, "ROOT_NOT_ON_ACTUAL_SUPPORT");
            }
            float expected = current.finalSupportY;
            float aiMovement = new Vector2(root.x - beforeAI.x, root.z - beforeAI.z).magnitude;
            if (aiMovement > .00001f)
            {
                current.aiMovementFrames++;
                Require(beforePhase == "Stalk" || beforePhase == "Attack", "MOVEMENT_OUTSIDE_PRODUCTION_AI_PHASE");
            }
            if (current.frames == 0)
            {
                current.firstFrame = Time.frameCount; current.initialRoot = root; current.initialSupportY = expected;
                current.actualDeltaMin = Time.deltaTime;
                float start = current.name.StartsWith("drop-", StringComparison.Ordinal) ? road.bounds.max.y : foundation.bounds.max.y;
                Require(Mathf.Abs(expected - start) < RootTolerance, "INITIAL_SUPPORT_WRONG");
            }
            else
            {
                float step = root.y - previousRoot.y;
                current.maxRootStep = Mathf.Max(current.maxRootStep, Mathf.Abs(step));
                if (step > RootTolerance) current.riseCount++;
                if (step < -RootTolerance) current.dropCount++;
                current.horizontalTravel += new Vector2(root.x - previousRoot.x, root.z - previousRoot.z).magnitude;
            }
            current.frames++; current.lastFrame = Time.frameCount; current.finalRoot = root; current.finalSupportY = expected;
            current.actualDeltaMin = Mathf.Min(current.actualDeltaMin, Time.deltaTime); current.actualDeltaMax = Mathf.Max(current.actualDeltaMax, Time.deltaTime);
            current.measuredSurfaceRise = Mathf.Abs(current.finalSupportY - current.initialSupportY);
            previousRoot = root; previousAnimation = animation;
            bool dropCase = current.name.StartsWith("drop-", StringComparison.Ordinal);
            bool crossed = dropCase ? current.dropCount > 0 && current.finalSupportY < current.initialSupportY :
                current.riseCount > 0 && current.finalSupportY > current.initialSupportY;
            current.completed = crossed && current.lowSupportSamples > 0 && current.highSupportSamples > 0 &&
                Mathf.Abs(current.measuredSurfaceRise - (road.bounds.max.y - foundation.bounds.max.y)) <= RootTolerance &&
                current.maxRootStep <= road.bounds.max.y - foundation.bounds.max.y + RootTolerance &&
                current.horizontalTravel > 3 && current.aiMovementFrames > 0 && current.independentCrossingSamples > 0 && current.independentTransitionSamples > 0 && current.stalkFrames > 0 && current.walkFrames > 0 && current.stalkToWindupCount > 0 &&
                current.windupFrames >= 2 && current.animatorWindupFrames > 0 && current.walkToWindupCount > 0;
            if (current.completed || current.frames % 15 == 0) Write();
        }

        void AfterLifecyclePaws()
        {
            string code = lifecycle == LifecyclePhase.Death ? "DEATH_LIFECYCLE" : "RESET_LIFECYCLE";
            if (lifecycleLastFrame >= 0) Require(Time.frameCount == lifecycleLastFrame + 1, code);
            lifecycleLastFrame = Time.frameCount;
            if (lifecycle == LifecyclePhase.Death)
            { Require(current.deathFrames < current.frameBound, "LIFECYCLE_TIMEOUT"); current.deathFrames++; }
            else { Require(current.resetFrames < current.frameBound, "LIFECYCLE_TIMEOUT"); current.resetFrames++; }
            var root = actor.transform.position;
            object pawReport = Field(paws, "lastReport");
            Require(pawReport != null && (int)Field(pawReport, "frame") == Time.frameCount, "PAW_REPORT_FRESH");
            Require(animator.enabled && animator.speed == 1 && animator.runtimeAnimatorController == controller &&
                !animator.applyRootMotion, "ANIMATOR_CHANGED");
            current.modelUnchanged &= skins.All(s => s.renderer.sharedMesh == s.source && s.renderer.bones.SequenceEqual(s.bones));
            current.targetStationary &= Vector3.Distance(vehicle.position, lifecycleTarget) < RootTolerance;
            Require(current.modelUnchanged && current.targetStationary, "FIXTURE_MUTATED");
            var legs = ((IEnumerable)Field(pawReport, "legs")).Cast<object>().ToArray();
            Require(legs.Length == 4, "LEG_REPORT_INVENTORY");
            foreach (var leg in legs)
            {
                float correction = (float)Field(leg, "correctionMeters"), distance = (float)Field(leg, "postMinDistance");
                Require(Finite(correction) && Finite(distance), "NONFINITE_SAMPLE");
                current.maxPawCorrection = Mathf.Max(current.maxPawCorrection, correction);
                current.maxPawResidual = Mathf.Max(current.maxPawResidual, Mathf.Max(0, -distance));
                Require(correction <= PawMaximumCorrection && distance >= -PawFloorTolerance, "PAW_LIMIT");
                Require((bool)Field(leg, "valid"), "LEG_INVALID");
                if ((bool)Field(leg, "corrected"))
                {
                    float error = Mathf.Abs(distance - (float)Field(leg, "targetClearance"));
                    current.maxCorrectedClearanceError = Mathf.Max(current.maxCorrectedClearanceError, error);
                    Require(error <= .0002f, "CORRECTED_CLEARANCE");
                }
            }
            Require((bool)Field(pawReport, "valid") && !(bool)Get(paws, "HasFailure"), "PAW_REPORT_FAILED");
            float expected = MeasureActualSupport(SupportAt(root, out _), false);
            var info = animator.GetCurrentAnimatorStateInfo(0);
            if (lifecycle == LifecyclePhase.Death)
            {
                Require((bool)Get(actor, "Dead") && beforePhase == "Dead" && (int)Get(actor, "Health") == 0 &&
                    !hurtbox.enabled && root.Equals(deathRoot) && beforeAI.Equals(deathRoot), code);
                deathElapsed += Time.deltaTime;
                bool deathState = info.shortNameHash == Animator.StringToHash("Death");
                if (!animator.IsInTransition(0))
                {
                    Require(deathState && !info.loop && Mathf.Abs(info.length - deathClip.length) <= RootTolerance, code);
                    Require(legs.All(l => (string)Field(l, "sourceState") == "Death" &&
                        (string)Field(l, "destinationState") == "Death"), code);
                }
                deathFinished = !animator.IsInTransition(0) && deathState && info.normalizedTime >= 1 &&
                    deathElapsed + .00001f >= deathClip.length;
            }
            else
            {
                Require(!(bool)Get(actor, "Dead") && (int)Get(actor, "Health") > 0 && hurtbox.enabled, code);
                // The original crossing root/counter evidence stays frozen after completion.
                Require(Mathf.Abs(root.y - expected) <= RootTolerance, "ROOT_NOT_ON_ACTUAL_SUPPORT");
                float distance = new Vector2(root.x - beforeAI.x, root.z - beforeAI.z).magnitude;
                if (distance > .00001f)
                { Require(beforePhase == "Stalk", code); resetMovingFrames++; }
                if (Get(actor, "Phase").ToString() == "Stalk" && !animator.IsInTransition(0) &&
                    info.shortNameHash == Animator.StringToHash("Walk")) resetWalkFrames++;
                current.lifecycleCompleted = current.resetFrames >= 2 && resetMovingFrames >= 2 && resetWalkFrames >= 2;
            }
            Write();
        }

        float MeasureActualSupport(float rootGround, bool recordCrossingSamples = true)
        {
            float expected = rootGround; bool low = false, high = false;
            foreach (var skin in skins)
            {
                object[] args = { skin.renderer, 0f, 0f };
                var vertices = (Vector3[])measure.Invoke(null, args);
                current.maxSkinningAgreementError = Mathf.Max(current.maxSkinningAgreementError, (float)args[1]);
                foreach (int index in skin.vertices)
                {
                    var point = vertices[index]; float height = SupportAt(point, out var floor);
                    expected = Mathf.Max(expected, height); low |= floor == foundation; high |= floor == road;
                    float residual = Mathf.Max(0, height - point.y);
                    current.maxPawResidual = Mathf.Max(current.maxPawResidual, residual);
                    Require(residual <= PawFloorTolerance, "INDEPENDENT_SOLE_CLEARANCE");
                }
            }
            if (recordCrossingSamples)
            {
                if (low && high) current.mixedSupportSamples++;
                if (Mathf.Abs(expected - foundation.bounds.max.y) < RootTolerance) current.lowSupportSamples++;
                if (Mathf.Abs(expected - road.bounds.max.y) < RootTolerance) current.highSupportSamples++;
            }
            return expected;
        }

        void BuildSoleInventory()
        {
            // Independently select complete paw-subtree vertices from the full native weight
            // stream. Mixed parent/paw vertices are excluded, matching the declared sole scope.
            var pawBones = ((Array)Field(paws, "legs")).Cast<object>().Select(l => (Transform)Field(l, "paw")).ToArray();
            Require(pawBones.Length == 4 && pawBones.All(p => p), "PAW_BINDINGS");
            var source = ((Array)Field(paws, "sourceRenderers")).Cast<SkinnedMeshRenderer>().ToArray();
            Require(source.Length > 0 && new HashSet<SkinnedMeshRenderer>(source).SetEquals(actor.GetComponentsInChildren<SkinnedMeshRenderer>(true)), "SKIN_INVENTORY");
            skins = source.Select(renderer =>
            {
                var mesh = renderer.sharedMesh; var bones = renderer.bones;
                Require(mesh && mesh.isReadable && renderer.quality == SkinQuality.Auto && QualitySettings.skinWeights == SkinWeights.Unlimited, "READABLE_NATIVE_SKIN");
                var counts = mesh.GetBonesPerVertex(); var weights = mesh.GetAllBoneWeights(); var selected = new List<int>(); int offset = 0;
                for (int vertex = 0; vertex < counts.Length; vertex++)
                {
                    int owner = -1; bool mixed = false;
                    for (int influence = 0; influence < counts[vertex]; influence++)
                    {
                        var weight = weights[offset++]; if (weight.weight == 0) continue;
                        var bone = bones[weight.boneIndex]; int leg = Array.FindIndex(pawBones, p => bone == p || bone.IsChildOf(p));
                        if (leg < 0 || owner >= 0 && owner != leg) mixed = true; else owner = leg;
                    }
                    if (owner >= 0 && !mixed) selected.Add(vertex);
                }
                Require(offset == weights.Length, "WEIGHT_STREAM_INVENTORY");
                return new Skin { renderer = renderer, source = mesh, bones = bones, vertices = selected.ToArray() };
            }).ToArray();
            Require(skins.Sum(s => s.vertices.Length) >= 16, "SOLE_INVENTORY_EMPTY");
        }
        float SupportAt(Vector3 point, out BoxCollider selected)
        {
            Require(Finite(point.x) && Finite(point.y) && Finite(point.z), "NONFINITE_SAMPLE");
            selected = null; float height = 0;
            // Read-only native collider rays against exactly the saved authored supports;
            // independent of the production support module's analytic box intersection.
            foreach (var floor in new[] { foundation, road })
            {
                var origin = new Vector3(point.x, Mathf.Max(point.y, floor.bounds.max.y) + 1, point.z);
                if (!floor.Raycast(new Ray(origin, Vector3.down), out var hit, 4)) continue;
                Require(hit.normal.y >= .9f, "NONWALKABLE_SUPPORT");
                if (!selected || hit.point.y > height) { selected = floor; height = hit.point.y; }
            }
            Require(selected, "SUPPORT_MISSING"); return height;
        }
        void ObserveSafely(Action action)
        {
            if ((!recording && lifecycle == LifecyclePhase.None) || observerFailed) return;
            try { action(); }
            catch { observerFailed = true; Fail("OBSERVER_EXCEPTION"); Write(); }
        }
        void NativeLog(string message, string stack, LogType type)
        {
            if (type != LogType.Error && type != LogType.Exception && type != LogType.Assert) return;
            report.nativeErrorCount++; Fail("UNITY_ERROR"); // Never suppress failing logs or copy arbitrary log text.
        }
        static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
        static string Hash(string path)
        { using (var sha = SHA256.Create()) using (var stream = File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant(); }
        static bool Hex(string value, int length) => value != null && value.Length == length && value.All(c => c >= '0' && c <= '9' || c >= 'a' && c <= 'f');
        void VerifyInput()
        {
            Require(File.Exists(InputPath) && File.Exists(Path.ChangeExtension(InputPath, "sha256")), "INPUT_MISSING");
            report.inputSha256 = Hash(InputPath);
            Require(File.ReadAllText(Path.ChangeExtension(InputPath, "sha256")).Trim() == report.inputSha256, "INPUT_HASH");
            input = JsonUtility.FromJson<Input>(File.ReadAllText(InputPath));
            Require(input != null && input.schema == 1 && input.status == "PINNED_POUNCER_SUPPORT_FOCUSED_INPUT", "INPUT_SCHEMA");
            Require(Hex(input.sourceCommit, 40) && input.sourceCommit == Environment.GetEnvironmentVariable("GITHUB_SHA") && input.producerCommit == Producer &&
                input.producerGeneratedReceiptSha256 == GeneratedReceipt && Hex(input.derivedReceiptSha256, 64), "INPUT_PROVENANCE");
            Require(input.sourcePins != null && input.sourcePins.Length > 0 && input.sourcePins.Select(p => p.path).Distinct().Count() == input.sourcePins.Length, "SOURCE_PIN_INVENTORY");
            foreach (var pin in input.sourcePins)
                Require(pin.path.StartsWith("Assets/DesertRV/", StringComparison.Ordinal) && !pin.path.Contains("..") && !pin.path.Contains("\\") &&
                    (pin.path.EndsWith(".cs", StringComparison.Ordinal) || pin.path.EndsWith(".cs.meta", StringComparison.Ordinal)) &&
                    Hex(pin.sha256, 64) && File.Exists(pin.path) && Hash(pin.path) == pin.sha256, "SOURCE_PIN_HASH");
            foreach (string path in new[] { "Runtime/PouncerGroundSupport.cs", "Runtime/PouncerPawContactConstraint.cs", "Runtime/BeastActor.cs", "Runtime/RegionBinding.cs",
                "Editor/JourneyCandidateMeshMeasurement.cs", "Tests/PlayMode/JourneyPouncerPreparedSupportTests.cs" })
                Require(input.sourcePins.Any(p => p.path == "Assets/DesertRV/" + path) && input.sourcePins.Any(p => p.path == "Assets/DesertRV/" + path + ".meta"), "REQUIRED_SOURCE_PIN");
            Require(input.scenes != null && input.scenes.Length == 2 && input.scenes[0].path == Bootstrap && input.scenes[1].path == R3, "SCENE_PIN_INVENTORY");
            Require(PinsUnchanged(), "CONSUMER_BYTES_DIFFER");
            report.sourceCommit = input.sourceCommit; report.derivedReceiptSha256 = input.derivedReceiptSha256;
            report.sourcePinCount = input.sourcePins.Length; report.scenePinCount = input.scenes.Length; report.inputVerified = true; Write();
        }
        bool PinsUnchanged() => input != null && input.sourcePins != null && input.scenes != null &&
            input.sourcePins.All(p => File.Exists(p.path) && Hash(p.path) == p.sha256) &&
            input.scenes.All(p => File.Exists(p.path) && Hash(p.path) == p.sha256 && File.Exists(p.path + ".meta") && Hash(p.path + ".meta") == p.metaSha256) &&
            File.Exists(InputPath) && Hash(InputPath) == report.inputSha256 && File.Exists(Path.ChangeExtension(InputPath, "sha256")) &&
            File.ReadAllText(Path.ChangeExtension(InputPath, "sha256")).Trim() == report.inputSha256;
        void Require(bool condition, string code) { if (condition) return; Fail(code); Assert.Fail(code); }
        void Fail(string code)
        {
            if (report == null) return;
            if (report.failureCode.Length == 0) report.failureCode = code;
            report.status = "INCOMPLETE_FOCUSED_SUPPORT_UNREVIEWED";
        }
        void Write()
        {
            if (report == null) return; string json = JsonUtility.ToJson(report, false);
            if (System.Text.Encoding.UTF8.GetByteCount(json) >= 64 * 1024) throw new InvalidOperationException("REPORT_SIZE_BOUND");
            Directory.CreateDirectory(Folder); File.WriteAllText(Output, json + "\n");
        }

        void CleanupAction(Action action)
        {
            try { action(); } catch { cleanupFailed = true; Fail("CLEANUP_EXCEPTION"); }
        }
        [UnityTearDown] public IEnumerator Cleanup()
        {
            recording = false; lifecycle = LifecyclePhase.None;
            try
            {
                CleanupAction(() => { if (actor) actor.gameObject.SetActive(false); });
                CleanupAction(() => { if (adapter && observer) { Call(adapter, "DetachEditorReplay", observer); report.replayDetached = !(bool)Get(adapter, "EditorReplayActive"); } });
                CleanupAction(() => { if (director) Object.DestroyImmediate(director.gameObject); });
                CleanupAction(() => { if (originalActive.IsValid() && originalActive.isLoaded) SceneManager.SetActiveScene(originalActive); });
                if (ownsRegion) { var scene = SceneManager.GetSceneByPath(R3); if (scene.IsValid() && scene.isLoaded) yield return SceneManager.UnloadSceneAsync(scene); }
                if (ownsBootstrap) { var scene = SceneManager.GetSceneByPath(Bootstrap); if (scene.IsValid() && scene.isLoaded) yield return SceneManager.UnloadSceneAsync(scene); }
            }
            finally
            {
                if (report != null)
                {
                    Time.captureDeltaTime = oldCapture; Time.timeScale = oldScale;
                    Cursor.lockState = oldLock; Cursor.visible = oldCursor;
                    report.timeRestored = Time.captureDeltaTime == oldCapture && Time.timeScale == oldScale && Time.fixedDeltaTime == oldFixed;
                    report.cursorRestored = Cursor.lockState == oldLock && Cursor.visible == oldCursor;
                    report.scenesUnloaded = !SceneManager.GetSceneByPath(Bootstrap).isLoaded && !SceneManager.GetSceneByPath(R3).isLoaded;
                    report.originalScenesPreserved = originalScenes != null && originalScenes.All(s => s.IsValid() && s.isLoaded) &&
                        SceneManager.sceneCount == originalScenes.Length && SceneManager.GetActiveScene() == originalActive;
                    try { report.sourcesUnchanged = PinsUnchanged(); } catch { report.sourcesUnchanged = false; }
                    bool cleaned = !cleanupFailed && report.replayDetached && report.timeRestored && report.cursorRestored &&
                        report.scenesUnloaded && report.originalScenesPreserved && report.sourcesUnchanged;
                    if (!cleaned) Fail("CLEANUP_FAILED");
                    if (report.nativeErrorCount > 0) Fail("UNITY_ERROR");
                    if (callbackAttached) { Application.logMessageReceived -= NativeLog; callbackAttached = false; }
                    Write(); Assert.That(cleaned && report.nativeErrorCount == 0, Is.True, "CLEANUP_OR_NATIVE_ERROR");
                }
            }
        }
    }
}
#endif
