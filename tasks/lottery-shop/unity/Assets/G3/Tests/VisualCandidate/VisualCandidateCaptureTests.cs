using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using Lottery.G3.Persistence;
using Lottery.G3.Rendering;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;
using Stopwatch = System.Diagnostics.Stopwatch;

namespace Lottery.G3.VisualCandidate.Tests
{
    // Diagnostic candidate only. A simulated Input System fixture and a camera image
    // cannot establish Android touch, natural-seed balance, visual acceptance, or G3 PASS.
    public sealed class VisualCandidateCaptureTests : IPrebuildSetup
    {
        const string Scope = "DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS";
        const string FixtureRun = "g3-day-qafixture-001";
        readonly List<GameObject> hiddenRoots = new List<GameObject>();
        readonly List<FrameReceipt> frames = new List<FrameReceipt>();
        readonly List<ActionReceipt> actions = new List<ActionReceipt>();
        static readonly HashSet<string> OwnedLegacyRoots = new HashSet<string>
        { "Probe Camera", "Probe Key Light", "Render capability sample", "Probe Overlay", "G3 One Day Whitebox" };
        Scene prior, scene;
        G3SliceBootstrap app;
        G3PhoneDisplay phoneIdentity;
        Material verifiedBrass;
        Texture verifiedBrassBase,verifiedBrassNormal,verifiedBrassPacked;
        FileStateStore store;
        Mouse mouse;
        Keyboard keyboard;
        RenderTexture target;
        RenderPipelineAsset oldDefaultPipeline, oldQualityPipeline;
        InputSettings inputSettings;
        InputSettings.UpdateMode oldUpdate;
        InputSettings.BackgroundBehavior oldBackground;
#if UNITY_EDITOR
        InputSettings.EditorInputBehaviorInPlayMode oldEditorInput;
#endif
        bool capturedInputSettings;
        string storeDirectory, output;
        int inputUpdates;
        ProgressTrail runtimeProgress;
        const double RuntimeSeconds = 900, FaceSeconds = 120, WalkSeconds = 180, UnloadSeconds = 10;
        G3Presenter P => app.Presenter;
        G3InputRouter Router => P.Router;
        RunState State => P.Snapshot;

        // Unity's supported prebuild fixture hook runs before entering PlayMode.
        // The fixed reflection target avoids a runtime -> Editor assembly dependency.
        public void Setup()
        {
#if UNITY_EDITOR
            var progress = new ProgressTrail("prebuild");
            progress.Mark("prebuild-begin");
            try
            {
                VisualCandidateLifecycleProbe.Arm();
                var type = AppDomain.CurrentDomain.GetAssemblies()
                    .Select(a => a.GetType("Lottery.G3.Editor.G3Build", false)).FirstOrDefault(t => t != null);
                if(type == null) throw new InvalidOperationException("G3Build missing: no whitebox fallback");
                var prepare = type.GetMethod("PrepareForVisualTestsObserved", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
                if(prepare == null) throw new InvalidOperationException("G3Build.PrepareForVisualTestsObserved missing");
                progress.Mark("prebuild-scene-guard-begin");
                progress.Mark("prebuild-guard-snapshot-begin");
                PrebuildSceneGuard preserved;
                try { preserved = new PrebuildSceneGuard(); }
                catch(Exception failure)
                {
                    try { progress.Mark(GuardFailureStage(failure)); }
                    catch(Exception diagnosticFailure) { throw new AggregateException(failure, diagnosticFailure); }
                    throw;
                }
                progress.Mark("prebuild-guard-snapshot-end");
                PrepareAndVerify(prepare, preserved, progress, new PreparationSceneTrail());
                progress.Mark("prebuild-scene-guard-passed");
                progress.Mark("prebuild-end");
                VisualCandidateStartupProbe.PrebuildReturned();
            }
            catch(Exception failure)
            {
                try { progress.Mark("prebuild-failed"); }
                catch(Exception diagnosticFailure) { throw new AggregateException(failure, diagnosticFailure); }
                throw;
            }
#endif
        }

#if UNITY_EDITOR
        enum GuardFailure
        {
            NoOriginalScene, InvalidOriginalActiveScene, SceneCountChanged,
            ActiveSceneChanged, SceneIdentityChanged, SceneLoadedStateChanged,
            ScenePathChanged, SceneDirtyStateChanged, RootCountChanged,
            RootIdentityChanged, RootActiveStateChanged, BuildSceneSelectionChanged
        }
        sealed class PrebuildGuardException : InvalidOperationException
        {
            public readonly GuardFailure Code;
            public PrebuildGuardException(GuardFailure code) : base("Prebuild scene preservation guard: " + code) { Code = code; }
        }
        static string GuardFailureStage(Exception failure)
        {
            var known = failure as PrebuildGuardException;
            if(known == null) return "prebuild-guard-unexpected-failed";
            switch(known.Code)
            {
                case GuardFailure.NoOriginalScene: return "prebuild-guard-failed-no-original-scene";
                case GuardFailure.InvalidOriginalActiveScene: return "prebuild-guard-failed-invalid-active-scene";
                case GuardFailure.SceneCountChanged: return "prebuild-guard-failed-scene-count";
                case GuardFailure.ActiveSceneChanged: return "prebuild-guard-failed-active-scene";
                case GuardFailure.SceneIdentityChanged: return "prebuild-guard-failed-scene-identity";
                case GuardFailure.SceneLoadedStateChanged: return "prebuild-guard-failed-scene-loaded-state";
                case GuardFailure.ScenePathChanged: return "prebuild-guard-failed-scene-path";
                case GuardFailure.SceneDirtyStateChanged: return "prebuild-guard-failed-scene-dirty-state";
                case GuardFailure.RootCountChanged: return "prebuild-guard-failed-root-count";
                case GuardFailure.RootIdentityChanged: return "prebuild-guard-failed-root-identity";
                case GuardFailure.RootActiveStateChanged: return "prebuild-guard-failed-root-active-state";
                case GuardFailure.BuildSceneSelectionChanged: return "prebuild-guard-failed-build-scene-selection";
                default: return "prebuild-guard-unexpected-failed";
            }
        }
        static void DiagnosticMark(ProgressTrail progress, string stage, List<Exception> errors)
        {
            try { progress.Mark(stage); }
            catch(Exception error) { errors.Add(error); }
        }
        static void PrepareAndVerify(System.Reflection.MethodInfo prepare, PrebuildSceneGuard guard, ProgressTrail progress, PreparationSceneTrail sceneTrail)
        {
            var errors = new List<Exception>();
            DiagnosticMark(progress, "prebuild-prepare-begin", errors);
            try
            {
                prepare.Invoke(null, new object[] { new Action<int,bool,bool,bool,bool,bool>(sceneTrail.Record) });
                DiagnosticMark(progress, "prebuild-prepare-end", errors);
            }
            catch(Exception failure)
            {
                errors.Add(failure);
                DiagnosticMark(progress, "prebuild-prepare-failed", errors);
            }
            finally
            {
                // Even a failed diagnostic write must not suppress verification.
                DiagnosticMark(progress, "prebuild-guard-verify-begin", errors);
                try
                {
                    guard.RequireUnchanged();
                    DiagnosticMark(progress, "prebuild-guard-verify-passed", errors);
                }
                catch(Exception failure)
                {
                    errors.Add(failure);
                    DiagnosticMark(progress, GuardFailureStage(failure), errors);
                }
            }
            if(sceneTrail.WriteFailure != null)errors.Add(sceneTrail.WriteFailure);
            // Do not let a guard or diagnostic failure replace the Prepare cause.
            // These original exceptions stay in Unity's handling, never in artifacts.
            if(errors.Count > 1) throw new AggregateException("Prebuild failed in multiple guarded phases", errors);
            if(errors.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(errors[0]).Throw();
        }

        sealed class PreparationSceneTrail
        {
            readonly Stopwatch timer = Stopwatch.StartNew();
            readonly List<PreparationSceneObservation> observations = new List<PreparationSceneObservation>();
            readonly string path = Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/visual-candidate/preparation-scenes.json"));
            public Exception WriteFailure {get;private set;}
            public void Record(int stageCode,bool sceneValid,bool isLoaded,bool activeMatches,bool activationAttempted,bool activationReturned)
            {
                try
                {
                    if(observations.Count>=6||!new[]{10,11,12,20,21,22}.Contains(stageCode)||observations.Any(x=>x.stageCode==stageCode))
                        throw new InvalidOperationException("Preparation scene diagnostic bound/code mismatch");
                    observations.Add(new PreparationSceneObservation{stageCode=stageCode,elapsedMs=timer.ElapsedMilliseconds,
                        sceneValid=sceneValid,isLoaded=isLoaded,activeMatches=activeMatches,
                        activationAttempted=activationAttempted,activationReturned=activationReturned});
                    var receipt=new PreparationScenesReceipt{sourceCommit=Arg("-probeCommit"),runId=Arg("-probeRunId"),
                        runAttempt=Arg("-probeRunAttempt"),observations=observations.ToArray()};
                    var json=JsonUtility.ToJson(receipt,true);
                    if(Encoding.UTF8.GetByteCount(json)>16384)throw new InvalidOperationException("Preparation scene receipt exceeds bound");
                    Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,json);
                }
                catch(Exception failure)
                {
                    // Retain for final failure without interrupting Editor cleanup.
                    if(WriteFailure==null)WriteFailure=failure;
                }
            }
        }
        [Serializable] sealed class PreparationSceneObservation
        {
            public int stageCode;public long elapsedMs;
            public bool sceneValid,isLoaded,activeMatches,activationAttempted,activationReturned;
        }
        [Serializable] sealed class PreparationScenesReceipt
        {
            public int schemaVersion=1;
            public string scope=Scope,sourceCommit,runId,runAttempt;
            public string status="MILESTONES_ONLY_NOT_TEST_PASS";
            public PreparationSceneObservation[] observations;
        }

        // SceneSetup restoration reloads paths but cannot preserve live object identity.
        // Official UTF 1.4.6 creates its runner before IPrebuildSetup; this guard
        // verifies the actual pinned runtime instead of assuming 1.6.0 internals.
        // Both preparation levels must preserve every original object on failure too.
        sealed class PrebuildSceneGuard
        {
            readonly Scene[] scenes;
            readonly bool[] loadedScenes, dirtyScenes;
            readonly string[] scenePaths;
            readonly GameObject[][] roots;
            readonly bool[][] activeRoots;
            readonly Scene active;
            readonly UnityEditor.EditorBuildSettingsScene[] buildScenes;
            public PrebuildSceneGuard()
            {
                active = SceneManager.GetActiveScene();
                scenes = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
                scenePaths = scenes.Select(s => s.path).ToArray();
                loadedScenes = scenes.Select(s => s.isLoaded).ToArray();
                dirtyScenes = scenes.Select(s => s.isDirty).ToArray();
                roots = scenes.Select(s => s.isLoaded ? s.GetRootGameObjects() : new GameObject[0]).ToArray();
                activeRoots = roots.Select(rs => rs.Select(r => r.activeSelf).ToArray()).ToArray();
                buildScenes = UnityEditor.EditorBuildSettings.scenes;
                if(scenes.Length == 0) throw new PrebuildGuardException(GuardFailure.NoOriginalScene);
                if(!active.IsValid() || !active.isLoaded) throw new PrebuildGuardException(GuardFailure.InvalidOriginalActiveScene);
            }
            public void RequireUnchanged()
            {
                if(SceneManager.sceneCount != scenes.Length) throw new PrebuildGuardException(GuardFailure.SceneCountChanged);
                if(SceneManager.GetActiveScene().handle != active.handle) throw new PrebuildGuardException(GuardFailure.ActiveSceneChanged);
                for(int i = 0; i < scenes.Length; i++)
                {
                    var current = SceneManager.GetSceneAt(i);
                    if(!scenes[i].IsValid() || current.handle != scenes[i].handle)
                        throw new PrebuildGuardException(GuardFailure.SceneIdentityChanged);
                    if(current.isLoaded != loadedScenes[i]) throw new PrebuildGuardException(GuardFailure.SceneLoadedStateChanged);
                    if(current.path != scenePaths[i])
                        throw new PrebuildGuardException(GuardFailure.ScenePathChanged);
                    if(current.isDirty != dirtyScenes[i])
                        throw new PrebuildGuardException(GuardFailure.SceneDirtyStateChanged);
                    var currentRoots = current.isLoaded ? current.GetRootGameObjects() : new GameObject[0];
                    if(currentRoots.Length != roots[i].Length)
                        throw new PrebuildGuardException(GuardFailure.RootCountChanged);
                    for(int r = 0; r < roots[i].Length; r++)
                    {
                        if(roots[i][r] == null || !currentRoots.Contains(roots[i][r]))
                            throw new PrebuildGuardException(GuardFailure.RootIdentityChanged);
                        if(roots[i][r].activeSelf != activeRoots[i][r]) throw new PrebuildGuardException(GuardFailure.RootActiveStateChanged);
                    }
                }
                var currentBuildScenes = UnityEditor.EditorBuildSettings.scenes;
                if(currentBuildScenes.Length != buildScenes.Length ||
                    currentBuildScenes.Where((s, i) => s.path != buildScenes[i].path || s.enabled != buildScenes[i].enabled).Any())
                    throw new PrebuildGuardException(GuardFailure.BuildSceneSelectionChanged);
            }
        }
#endif

        [UnitySetUp]
        public IEnumerator SetUpRuntime()
        {
            verifiedBrass=null;verifiedBrassBase=null;verifiedBrassNormal=null;verifiedBrassPacked=null;
            BoundedGlyphLabel.BeginCostObservation();G3InputRouter.BeginCostObservation();
            runtimeProgress = new ProgressTrail("runtime");
            runtimeProgress.Mark("runtime-setup-begin");
            prior = SceneManager.GetActiveScene();
            // Isolate only project-owned objects across loaded scenes. Never disable
            // an arbitrary ancestor that could contain the Unity test controller.
            foreach(var bootstrap in Object.FindObjectsByType<G3SliceBootstrap>(FindObjectsSortMode.None))
            {
                var owned = bootstrap.gameObject;
                if(owned.activeInHierarchy && owned.scene.IsValid() && owned.scene.isLoaded)
                { hiddenRoots.Add(owned); owned.SetActive(false); }
            }
            for(int index = 0; index < SceneManager.sceneCount; index++)
            {
                var loaded = SceneManager.GetSceneAt(index);
                if(!loaded.isLoaded) continue;
                foreach(var root in loaded.GetRootGameObjects())
                    if(root.activeSelf && OwnedLegacyRoots.Contains(root.name)) { hiddenRoots.Add(root); root.SetActive(false); }
            }
            scene = SceneManager.CreateScene("Visual candidate actual runtime");
            SceneManager.SetActiveScene(scene);
            Assert.That(Application.isPlaying, Is.True);
            Assert.That(Application.unityVersion, Is.EqualTo("6000.3.19f1"));
            Assert.That(SystemInfo.graphicsDeviceType, Is.Not.EqualTo(GraphicsDeviceType.Null));
            oldDefaultPipeline = GraphicsSettings.defaultRenderPipeline;
            oldQualityPipeline = QualitySettings.renderPipeline;
            inputSettings = InputSystem.settings;
            oldUpdate = inputSettings.updateMode;
            oldBackground = inputSettings.backgroundBehavior;
#if UNITY_EDITOR
            oldEditorInput = inputSettings.editorInputBehaviorInPlayMode;
            inputSettings.editorInputBehaviorInPlayMode = InputSettings.EditorInputBehaviorInPlayMode.AllDeviceInputAlwaysGoesToGameView;
#endif
            capturedInputSettings = true;
            inputSettings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            inputSettings.updateMode = InputSettings.UpdateMode.ProcessEventsManually;
            mouse = InputSystem.AddDevice<Mouse>();
            keyboard = InputSystem.AddDevice<Keyboard>();
            storeDirectory = Path.Combine(Path.GetTempPath(), "lottery-visual-candidate-" + Guid.NewGuid().ToString("N"));
            store = new FileStateStore(storeDirectory, RunFactory.CreateDiagnostic(FixtureRun));
            app = new GameObject("Visual candidate real G3 bootstrap").AddComponent<G3SliceBootstrap>();
            app.Initialize(new DayGameService(store), null, store);
            Router.PollAutomatically = false;
            phoneIdentity = P.View.Phone;
            BindTarget(1280, 720);
            Physics.SyncTransforms();
            yield return null;
            Router.NotifyPause(false); Router.NotifyFocus(true);
            MouseEvent(Vector2.zero, false);
            // Prime per-frame press tracking while every device is neutral.
            Assert.That(mouse.leftButton.wasPressedThisFrame, Is.False);
            Assert.That(mouse.leftButton.wasReleasedThisFrame, Is.False);
            Assert.That(keyboard.escapeKey.wasPressedThisFrame, Is.False);
            InputSystem.QueueStateEvent(keyboard, new KeyboardState());
            MouseEvent(Vector2.zero, false);
            Assert.That(Router.AwaitingRelease, Is.False);
            Assert.That(Object.FindObjectsByType<G3SliceBootstrap>(FindObjectsSortMode.None).Count(x => x.isActiveAndEnabled), Is.EqualTo(1), "Exactly one owned active G3 bootstrap is allowed");
            Assert.That(Object.FindObjectsByType<G3SceneView>(FindObjectsSortMode.None).Count(x => x.isActiveAndEnabled), Is.EqualTo(1), "Exactly one active G3 view is allowed");
            Assert.That(Camera.allCameras.Count(x => x.enabled && x.gameObject.activeInHierarchy), Is.EqualTo(1), "A duplicate scene camera invalidates the capture");
            Assert.That(P.View.Environment.HasImportedArt, Is.True);
            Assert.That(P.View.Environment.ImportedRendererCount, Is.GreaterThan(10));
            Assert.That(app.SceneCamera.orthographic, Is.False);
            output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../artifacts/visual-candidate/captures"));
            Directory.CreateDirectory(output);
            frames.Clear(); actions.Clear();
            WriteReceipt(false);
            Milestone("runtime-setup-end");
            CheckRuntimeBudget();
        }

        [UnityTearDown]
        public IEnumerator TearDownRuntime()
        {
            try
            {
            runtimeProgress?.Mark("runtime-teardown-begin");
            ReleaseTarget();
            if(app != null) Object.Destroy(app.gameObject);
            store?.Dispose();
            if(mouse != null && mouse.added) InputSystem.RemoveDevice(mouse);
            if(keyboard != null && keyboard.added) InputSystem.RemoveDevice(keyboard);
            if(capturedInputSettings)
            {
                inputSettings.updateMode = oldUpdate; inputSettings.backgroundBehavior = oldBackground;
#if UNITY_EDITOR
                inputSettings.editorInputBehaviorInPlayMode = oldEditorInput;
#endif
                capturedInputSettings = false;
            }
            // Let the visual environment restore its own temporary pipeline first.
            yield return null;
            GraphicsSettings.defaultRenderPipeline = oldDefaultPipeline;
            QualitySettings.renderPipeline = oldQualityPipeline;
            if(prior.IsValid()) SceneManager.SetActiveScene(prior);
            foreach(var root in hiddenRoots) if(root != null) root.SetActive(true);
            hiddenRoots.Clear();
            if(scene.IsValid() && scene.isLoaded)
            {
                var unloading = SceneManager.UnloadSceneAsync(scene);
                var timer = Stopwatch.StartNew();
                for(int frame = 0; unloading != null && !unloading.isDone && frame < 600; frame++)
                {
                    Assert.That(timer.Elapsed.TotalSeconds, Is.LessThan(UnloadSeconds), "Visual fixture scene unload exceeded 10 seconds");
                    yield return null;
                }
                Assert.That(unloading == null || unloading.isDone, Is.True, "Visual fixture scene unload exceeded 600 frames");
            }
            if(storeDirectory != null && Directory.Exists(storeDirectory)) Directory.Delete(storeDirectory, true);
            runtimeProgress?.Mark("runtime-teardown-end");
            }
            finally{BoundedGlyphLabel.EndCostObservation();G3InputRouter.EndCostObservation();}
        }

        [UnityTest]
        public IEnumerator ScenarioStateCaptureRetainsTwentyThreeViewsFromRealTransactionsV2()
        {
            // Entry and explicitly labelled exterior diagnostics are fixture-positioned.
            // They never establish walked arrival or parallax acceptance.
            Click("stand");
            P.View.Walk.SetPose(P.View.Environment.EntryPosition, P.View.Environment.EntryYaw);
            P.View.Layout(); Physics.SyncTransforms(); Observe("fixture-position-entry-camera"); yield return null;
            Capture("entry-whole-shop", "FIXTURE_POSITIONED_PLAYER_VIEW");
            SetupScenarioSeated(); yield return null;
            Capture("table-empty", "NORMAL_SEATED_PLAYER_VIEW");

            BuyStock("small_prize_box"); Equip("small_prize_box", 0);
            Buy("number"); ScratchCell(3); ScratchCell(4); ScratchCell(5);
            Assert.That(State.CurrentTicket.Scratch.RevealedCellCount, Is.EqualTo(3));
            yield return null; Capture("number-half", "NORMAL_SEATED_PLAYER_VIEW");
            string halfHash = StateCodec.ComputeHash(State);
            BindTarget(1600, 720); yield return null;
            Capture("number-half-20x9", "SAME_STATE_ALTERNATE_ASPECT");
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(halfHash));
            BindTarget(1280, 720); yield return null;
            yield return PhysicalPhoneBorrowKeepsConfirmedTicket();
            QuickRevealNumber(); Claim();
            BuyStock("inspection_lamp"); Equip("inspection_lamp", 1);
            BuyStock("large_prize_stamp"); Equip("large_prize_stamp", 2);
            Buy("challenge"); RevealSelected(0); RevealSelected(1);
            Assert.That(State.CurrentTicket.ConfigurationSnapshot.Length, Is.EqualTo(3));
            Assert.That(State.CurrentTicket.RevealedCells.Count(x => x), Is.EqualTo(2));
            Assert.That(P.Service.PreviewSettlement().RawPrizeMinor, Is.EqualTo(2000));
            yield return null; Capture("challenge-two-safe-three-tools", "NORMAL_SEATED_PLAYER_VIEW");

            string challengeHash = StateCodec.ComputeHash(State);
            SetupScenarioPanel(G3Panel.Shop); string localBody = P.BuildPanel().Body; Close();
            // Explicit camera station: this receipt establishes state/visuals, not walked arrival.
            P.Execute(new G3Action(G3ActionKind.Stand));
            var station=P.View.Environment.ShelfViewPosition;
            var offset=P.View.Environment.ShelfTargetPosition-(station+Vector3.up*1.58f);
            float heading=Mathf.Atan2(offset.x,offset.z)*Mathf.Rad2Deg;
            float pitch=Mathf.Atan2(-offset.y,new Vector2(offset.x,offset.z).magnitude)*Mathf.Rad2Deg;
            P.View.Walk.SetPose(station,heading,pitch);P.View.Layout();Physics.SyncTransforms();
            Observe("scenario-position-shelf-camera");yield return null;
            Capture("shelf-before-open", "SCENARIO_POSITIONED_SHELF_VIEW");
            var pose=app.SceneCamera.transform.position;var rotation=app.SceneCamera.transform.rotation;
            SetupScenarioPanel(G3Panel.Shop);
            Assert.That(P.BuildPanel().Body,Is.EqualTo(localBody));
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(challengeHash));
            yield return null;Capture("shelf-after-open", "SAME_POSE_SCENARIO_PANEL");
            Close();Assert.That(app.SceneCamera.transform.position,Is.EqualTo(pose));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(rotation));
            SetupScenarioSeated();Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(challengeHash));
            yield return null;Capture("challenge-returned-from-shelf", "SCENARIO_SEATED_SAME_CONFIRMED_TICKET");
            Claim();

            int remaining = 12 - State.TicketsPurchasedToday;
            Assert.That(remaining, Is.InRange(0, 12), "Invalid remaining day quota");
            Assert.That(State.SettledTicketCount, Is.EqualTo(State.TicketsPurchasedToday));
            for(int index = 0; index < remaining; index++)
            {
                CheckRuntimeBudget();
                Buy("number"); QuickRevealNumber(); Claim();
                Milestone("day-ticket-settled");
                yield return null;
            }
            Assert.That(State.TicketsPurchasedToday, Is.EqualTo(12));
            Assert.That(State.SettledTicketCount, Is.EqualTo(12));
            Assert.That(State.Tickets.Select(x => x.Id).Distinct().Count(), Is.EqualTo(12));
            Assert.That(State.HasUnsettledTicket, Is.False);
            Assert.That(State.Phase, Is.EqualTo(DayPhase.CLOSING_PREP));
            yield return null; Capture("closing-day-table", "NORMAL_SEATED_PLAYER_VIEW");
            yield return ExteriorFixtureViews(false);
            var dayPosition = app.SceneCamera.transform.position; var dayRotation = app.SceneCamera.transform.rotation;
            SetupScenarioPanel(G3Panel.Bill); Click("enter-night"); Confirm();
            Assert.That(State.Phase, Is.EqualTo(DayPhase.NIGHT_BILL));
            Close(); yield return null;
            Assert.That(P.Panel, Is.EqualTo(G3Panel.None));
            Assert.That(app.SceneCamera.transform.position, Is.EqualTo(dayPosition));
            Assert.That(app.SceneCamera.transform.rotation, Is.EqualTo(dayRotation));
            Capture("night-table", "SAME_CAMERA_AS_CLOSING_DAY_WITH_BILL_CLOSED");
            yield return ExteriorFixtureViews(true);
            SetupScenarioPanel(G3Panel.Bill); yield return null; Capture("night-bill", "NORMAL_BILL_INFORMATION_HIERARCHY");
            Assert.That(frames.Count, Is.EqualTo(23));
            // Returning to the same confirmed ticket may correctly produce identical pixels.
            Assert.That(frames.Single(x => x.stage == "shelf-before-open").sha256, Is.Not.EqualTo(frames.Single(x => x.stage == "shelf-after-open").sha256));
            Assert.That(frames.Single(x => x.stage == "closing-day-table").sha256, Is.Not.EqualTo(frames.Single(x => x.stage == "night-table").sha256));
            WriteReceipt(true);
            Milestone("scenario-complete");
        }

        // Controlled diagnostic stations, NOT keyboard traversal or a claim that these
        // poses are collision-reachable. Day/night is the existing production bill flow.
        IEnumerator ExteriorFixtureViews(bool isNight)
        {
            Assert.That(State.Phase, Is.EqualTo(isNight ? DayPhase.NIGHT_BILL : DayPhase.CLOSING_PREP));
            Assert.That(P.Panel, Is.EqualTo(G3Panel.None));
            string hash = StateCodec.ComputeHash(State);
            var mode = P.Mode; var panel = P.Panel; bool walking=P.Walking; bool phoneFocused=P.View.Phone.IsFocused;
            string ticketHash=TicketContentHash(State.CurrentTicket);
            var walkPosition = P.View.Walk.SavedPosition; var walkRotation = P.View.Walk.SavedRotation;
            var cameraPosition = app.SceneCamera.transform.position; var cameraRotation = app.SceneCamera.transform.rotation;
            float fov = app.SceneCamera.fieldOfView;
            int first = frames.Count;
            Click("stand");
            try
            {
                var positions = new[] { new Vector3(-.405f,0,-1.25f), new Vector3(-2.05f,0,1.55f), new Vector3(.55f,0,1.55f) };
                var headings = new[] { 0f, 55f, -45f }; var pitches = new[] { 8f, 8f, 18f };
                var labels = new[] { "far-front", "near-window-left-oblique", "near-door-right-oblique" };
                for(int i=0;i<positions.Length;i++)
                {
                    var overlaps=Physics.OverlapCapsule(positions[i]+Vector3.up*.205f,positions[i]+Vector3.up*1.54f,.18f,
                        ~0,QueryTriggerInteraction.Ignore).Where(c=>c.transform.IsChildOf(P.View.Environment.transform)).ToArray();
                    Assert.That(overlaps, Is.Empty, "Diagnostic station must not intersect production environment colliders");
                    P.View.Walk.SetPose(positions[i],headings[i],pitches[i]); P.View.Layout(); Physics.SyncTransforms();
                    yield return null;
                    Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(hash));
                    Assert.That(app.SceneCamera.fieldOfView, Is.EqualTo(64f));
                    // Validate first: a failing material contract must not append
                    // an incomplete frame and invalidate earlier diagnostic captures.
                    var metadata = ExteriorMetadata(isNight);
                    Capture("exterior-"+(isNight?"night-":"day-")+labels[i], "FIXTURE_VIEW_NOT_WALKED", metadata, hash);
                }
            }
            finally
            {
                P.View.Walk.SetPose(walkPosition,walkRotation.eulerAngles.y,walkRotation.eulerAngles.x);
                SetupScenarioSeated(); P.View.Layout(); Physics.SyncTransforms();
                Assert.That(P.Mode, Is.EqualTo(mode)); Assert.That(P.Panel, Is.EqualTo(panel)); Assert.That(P.Walking, Is.EqualTo(walking));
                Assert.That(P.View.Phone.IsFocused, Is.EqualTo(phoneFocused));
                Assert.That(TicketContentHash(State.CurrentTicket), Is.EqualTo(ticketHash));
                Assert.That(P.View.Walk.SavedPosition, Is.EqualTo(walkPosition));
                Assert.That(Quaternion.Angle(P.View.Walk.SavedRotation,walkRotation), Is.LessThan(.001f));
                Assert.That(app.SceneCamera.transform.position, Is.EqualTo(cameraPosition));
                Assert.That(Quaternion.Angle(app.SceneCamera.transform.rotation,cameraRotation), Is.LessThan(.001f));
                Assert.That(app.SceneCamera.fieldOfView, Is.EqualTo(fov));
                Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(hash));
                foreach(var frame in frames.Skip(first))
                { frame.fixtureStateAfter=StateCodec.ComputeHash(State); frame.fixturePoseRestored=true; }
                WriteReceipt(false);
            }
        }
        ExteriorReceipt ExteriorMetadata(bool isNight)
        {
            var renderers=P.View.Environment.GetComponentsInChildren<Renderer>();
            var materials=renderers.SelectMany(r=>r.sharedMaterials).Where(m=>m!=null).Distinct().ToArray();
            var backdrop=materials.Single(m=>m.name.StartsWith("V19 exterior day-night",StringComparison.Ordinal));
            var glass=materials.Where(m=>m.name.StartsWith("Glass_Clear",StringComparison.Ordinal)).ToArray();
            Assert.That(glass.Length, Is.GreaterThan(0));
            foreach(var m in glass)
            {
                Assert.That(m.renderQueue, Is.EqualTo((int)RenderQueue.Transparent));
                Assert.That(m.GetFloat("_Surface"), Is.EqualTo(1)); Assert.That(m.GetFloat("_ZWrite"), Is.Zero);
                Assert.That(m.GetColor("_BaseColor").a, Is.InRange(.001f,.999f));
            }
            var frustum=GeometryUtility.CalculateFrustumPlanes(app.SceneCamera);
            Func<Renderer,bool> visible=r=>r.enabled&&r.gameObject.activeInHierarchy&&
                (app.SceneCamera.cullingMask&(1<<r.gameObject.layer))!=0&&GeometryUtility.TestPlanesAABB(frustum,r.bounds);
            int glassVisible=renderers.Count(r=>r.sharedMaterials.Any(m=>glass.Contains(m))&&visible(r));
            int backdropVisible=renderers.Count(r=>r.sharedMaterials.Contains(backdrop)&&visible(r));
            Assert.That(glassVisible, Is.GreaterThan(0)); Assert.That(backdropVisible, Is.EqualTo(1));
            var texture=Resources.Load<Texture2D>("G3/Shop/Exterior/Street-"+(isNight?"night":"day"));
            Assert.That(backdrop.shader.name, Is.EqualTo("Lottery/G3/ExteriorBackdrop"));
            Assert.That(backdrop.GetTexture("_BaseMap"), Is.SameAs(texture));
            Assert.That(backdrop.GetFloat("_Exposure"), Is.EqualTo(isNight?.72f:1f).Within(.0001f));
            int backdropCount=renderers.Count(r=>r.sharedMaterials.Contains(backdrop));
            Assert.That(backdropCount, Is.EqualTo(1));
            var near=P.View.Environment.transform.Find("Exterior near-field sidewalk and threshold");
            Assert.That(near, Is.Not.Null); Assert.That(near.GetComponentsInChildren<Collider>(), Is.Empty);
            int triangles=near.GetComponent<MeshFilter>().sharedMesh.triangles.Length/3;
            Assert.That(triangles, Is.EqualTo(60));
            var felt=materials.Single(m=>m.name.StartsWith("Dark_Green_Felt",StringComparison.Ordinal));
            var liner=materials.Single(m=>m.name.StartsWith("Tool_Dock_Liner",StringComparison.Ordinal));
            var brass=materials.Single(m=>m.name.StartsWith("Brass_Worn",StringComparison.Ordinal));
#if UNITY_EDITOR
            RequireOwnedRuntimeMaterial(felt,"Dark_Green_Felt");
            RequireOwnedRuntimeMaterial(liner,"Tool_Dock_Liner");
            RequireOwnedRuntimeMaterial(brass,"Brass_Worn");
#endif
            Assert.That(felt.GetFloat("_BumpScale"), Is.EqualTo(.60f).Within(.0001f));
            Assert.That(liner.GetFloat("_Smoothness"), Is.EqualTo(.08f).Within(.0001f));
            Assert.That(liner.GetTexture("_BumpMap"), Is.SameAs(felt.GetTexture("_BumpMap")));
            RequireBrassPbr(brass);
            return new ExteriorReceipt { basis="MATERIAL_METADATA_NOT_PIXEL_ACCEPTANCE", backdropShader=backdrop.shader.name,
                textureName=texture.name, textureWidth=texture.width, textureHeight=texture.height,
                exposure=backdrop.GetFloat("_Exposure"), backdropRendererCount=backdropCount,
                glassFrustumRendererCount=glassVisible, backdropFrustumRendererCount=backdropVisible, transparentGlassMaterialCount=glass.Length, glassAlpha=glass.Min(m=>m.GetColor("_BaseColor").a),
                glassSurface=glass.Min(m=>m.GetFloat("_Surface")), glassZWrite=glass.Max(m=>m.GetFloat("_ZWrite")),
                glassRenderQueue=glass.Min(m=>m.renderQueue), nearFieldTriangles=triangles, nearFieldColliderCount=near.GetComponentsInChildren<Collider>().Length,
                feltNormalScale=felt.GetFloat("_BumpScale"), linerSmoothness=liner.GetFloat("_Smoothness"), brassSmoothness=brass.GetFloat("_Smoothness") };
        }

#if UNITY_EDITOR
        static void RequireOwnedRuntimeMaterial(Material actual,string name)
        {
            string path="Assets/G3/Shop/Resources/G3/Shop/Materials/"+name+".mat";
            var expected=UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(path);
            Assert.That(expected,Is.Not.Null);Assert.That(actual,Is.SameAs(expected),"Runtime material must use the validated external asset");
            Assert.That(UnityEditor.AssetDatabase.IsMainAsset(actual),Is.True);
            Assert.That(UnityEditor.AssetDatabase.GetAssetPath(actual),Is.EqualTo(path));
            Assert.That(UnityEditor.AssetDatabase.TryGetGUIDAndLocalFileIdentifier(actual,out string actualGuid,out long actualId),Is.True);
            Assert.That(UnityEditor.AssetDatabase.TryGetGUIDAndLocalFileIdentifier(expected,out string expectedGuid,out long expectedId),Is.True);
            Assert.That(actualGuid,Is.EqualTo(expectedGuid));Assert.That(actualId,Is.EqualTo(expectedId));
            Assert.That(actualGuid,Is.EqualTo(UnityEditor.AssetDatabase.AssetPathToGUID(path)));
        }
#endif

        // v24: scalar smoothness is the packed-alpha multiplier, not roughness.
        // One full content verification per fixture; paired views reuse one material.
        void RequireBrassPbr(Material brass)
        {
            if(verifiedBrass != null)
            {
                Assert.That(brass, Is.SameAs(verifiedBrass), "Brass material identity changed between paired views");
                RequireBrassProperties(brass,verifiedBrassBase,verifiedBrassNormal,verifiedBrassPacked);
                return;
            }
#if UNITY_EDITOR
            var timer=Stopwatch.StartNew();
            const string root="Assets/G3/Shop/Resources/G3/Shop/";
            Assert.That(brass, Is.SameAs(UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(root+"Materials/Brass_Worn.mat")));
            var baseMap=RequireBrassSource(root+"Textures/BrushedBrass_v24_BaseColor.png",291373,"8aae14d147ad7baec41880cad0cb46f0840b0173d422bcf74a7606cb393ed5da",UnityEditor.TextureImporterType.Default,true);
            var normal=RequireBrassSource(root+"Textures/BrushedBrass_v24_Normal.png",876507,"87529521ff91022ef5b6b747ec31157c9e9d9b32da7fad91e4a7e045d62e9904",UnityEditor.TextureImporterType.NormalMap,false);
            const string roughPath=root+"Textures/BrushedBrass_v24_Roughness.png";
            RequireBrassSource(roughPath,164909,"37623986d2a49befaa5acb9e8468698866d27d449210a304c8e4c7dcdbd09cc2",UnityEditor.TextureImporterType.Default,false);
            var packed=UnityEditor.AssetDatabase.LoadAssetAtPath<Texture2D>(root+"Materials/Brass_Worn_MetallicSmoothness.asset");
            Assert.That(packed, Is.Not.Null); Assert.That(packed.width, Is.EqualTo(1024)); Assert.That(packed.height, Is.EqualTo(1024));
            Assert.That(packed.format, Is.EqualTo(TextureFormat.RGBA32)); Assert.That(packed.isDataSRGB, Is.False);
            Assert.That(packed.isReadable, Is.True); Assert.That(packed.mipmapCount, Is.EqualTo(11));
            Assert.That(packed.wrapMode, Is.EqualTo(TextureWrapMode.Repeat)); Assert.That(packed.filterMode, Is.EqualTo(FilterMode.Trilinear));
            RequireBrassProperties(brass,baseMap,normal,packed);
            Texture2D decoded=null; Material negative=null;
            try
            {
                // Decode the frozen PNG into a temporary linear texture. Never toggle
                // source importer readability or rewrite a project asset for this test.
                decoded=new Texture2D(2,2,TextureFormat.RGBA32,false,true);
                Assert.That(ImageConversion.LoadImage(decoded,File.ReadAllBytes(roughPath),false), Is.True);
                Assert.That(decoded.width, Is.EqualTo(1024)); Assert.That(decoded.height, Is.EqualTo(1024));
                var sourcePixels=decoded.GetPixels32(); var packedPixels=packed.GetPixels32(0);
                Assert.That(sourcePixels.Length, Is.EqualTo(1048576)); Assert.That(packedPixels.Length, Is.EqualTo(sourcePixels.Length));
                int minimum,maximum;
                int mismatches=BrassPackingErrors(sourcePixels,packedPixels,out minimum,out maximum);
                Assert.That(mismatches, Is.Zero, "Packed brass must be R199/G0/B0/A(255-sourceR) for every source pixel");
                Assert.That(minimum, Is.EqualTo(109)); Assert.That(maximum, Is.EqualTo(214));
                // Constant-size negative probes exercise the same predicates without
                // re-reading or re-scanning the million-pixel real texture.
                var s=new[]{new Color32(41,41,41,255),new Color32(146,146,146,255)};
                var good=new[]{new Color32(199,0,0,214),new Color32(199,0,0,109)};
                Assert.That(BrassPackingErrors(s,good,out minimum,out maximum), Is.Zero);
                var reversed=new[]{new Color32(199,0,0,41),new Color32(199,0,0,146)};
                Assert.That(BrassPackingErrors(s,reversed,out minimum,out maximum), Is.GreaterThan(0), "Non-inverted roughness must fail");
                var flat=new[]{new Color32(199,0,0,180),new Color32(199,0,0,180)};
                Assert.That(BrassPackingErrors(s,flat,out minimum,out maximum), Is.GreaterThan(0), "Flat packed alpha must fail");
                negative=new Material(brass);
                negative.SetTexture("_BaseMap",normal);
                Assert.That(BrassPbrBindingMatches(negative,baseMap,normal,packed), Is.False, "Wrong map binding must fail");
                negative.SetTexture("_BaseMap",baseMap);negative.DisableKeyword("_NORMALMAP");
                Assert.That(BrassPbrBindingMatches(negative,baseMap,normal,packed), Is.False, "Disabled normal map must fail");
                negative.EnableKeyword("_NORMALMAP");negative.DisableKeyword("_METALLICSPECGLOSSMAP");
                Assert.That(BrassPbrBindingMatches(negative,baseMap,normal,packed), Is.False, "Disabled packed map must fail");
                verifiedBrassBase=baseMap;verifiedBrassNormal=normal;verifiedBrassPacked=packed;
                verifiedBrass=brass;
            }
            finally
            {
                if(negative!=null)Object.DestroyImmediate(negative);
                if(decoded!=null)Object.DestroyImmediate(decoded);
                timer.Stop();
                TestContext.WriteLine("G3_BRASS_PBR_CONTENT_CHECK elapsedMs="+timer.ElapsedMilliseconds+" realPixels=1048576");
            }
            CheckRuntimeBudget();
#else
            Assert.Fail("Brass source-content contract requires the Editor capture fixture");
#endif
        }
#if UNITY_EDITOR
        static Texture2D RequireBrassSource(string path,int bytes,string sha,UnityEditor.TextureImporterType type,bool srgb)
        {
            var raw=File.ReadAllBytes(path);Assert.That(raw.Length, Is.EqualTo(bytes)); Assert.That(StateCodec.HashBytes(raw), Is.EqualTo(sha));
            var importer=UnityEditor.AssetImporter.GetAtPath(path) as UnityEditor.TextureImporter;
            Assert.That(importer, Is.Not.Null);Assert.That(importer.textureType, Is.EqualTo(type));Assert.That(importer.sRGBTexture, Is.EqualTo(srgb));
            var texture=UnityEditor.AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            Assert.That(texture, Is.Not.Null);Assert.That(texture.width, Is.EqualTo(1024));Assert.That(texture.height, Is.EqualTo(1024));
            return texture;
        }
#endif
        static void RequireBrassProperties(Material brass,Texture baseMap,Texture normal,Texture packed)
        {
            Assert.That(BrassPbrBindingMatches(brass,baseMap,normal,packed), Is.True, "Brass PBR binding/keywords differ from frozen source");
            Assert.That(brass.GetFloat("_Smoothness"), Is.EqualTo(1f).Within(.0001f));
            Assert.That(brass.GetFloat("_SmoothnessTextureChannel"), Is.EqualTo(0f));
            Assert.That(brass.GetFloat("_Metallic"), Is.EqualTo(.78f).Within(.0001f));
            Assert.That(brass.GetFloat("_BumpScale"), Is.EqualTo(.18f).Within(.0001f));
            Assert.That(brass.GetColor("_BaseColor"), Is.EqualTo(Color.white));
            Assert.That(brass.GetTextureScale("_BaseMap"), Is.EqualTo(Vector2.one));
        }
        static bool BrassPbrBindingMatches(Material m,Texture baseMap,Texture normal,Texture packed) =>
            m!=null && baseMap!=null && normal!=null && packed!=null && m.shader.name=="Universal Render Pipeline/Lit" && m.GetTexture("_BaseMap")==baseMap &&
            m.GetTexture("_BumpMap")==normal && m.GetTexture("_MetallicGlossMap")==packed &&
            m.IsKeywordEnabled("_NORMALMAP") && m.IsKeywordEnabled("_METALLICSPECGLOSSMAP");
        static int BrassPackingErrors(Color32[] source,Color32[] packed,out int minimum,out int maximum)
        {
            minimum=255;maximum=0;
            if(source.Length!=packed.Length)return int.MaxValue;
            int errors=0;
            for(int i=0;i<source.Length;i++)
            {
                var s=source[i];var p=packed[i];minimum=Math.Min(minimum,p.a);maximum=Math.Max(maximum,p.a);
                if(s.r!=s.g||s.r!=s.b||s.a!=255||p.r!=199||p.g!=0||p.b!=0||p.a!=255-s.r)errors++;
            }
            return errors;
        }

        // Six additional frames exercise one production phone flow inside the
        // original capture test. They are not six independent NUnit tests.
        IEnumerator PhysicalPhoneBorrowKeepsConfirmedTicket()
        {
            Assert.That(P.View.Phone, Is.Not.Null);
            Assert.That(P.View.Phone.transform.IsChildOf(app.SceneCamera.transform), Is.False, "Phone must be a world object, not a camera overlay");
            var before = State.Copy();
            Click("stand");
            var at = P.View.Environment.StandPosition;
            var offset = P.View.Phone.WorldBounds.center - (at + Vector3.up * 1.58f);
            float yaw = Mathf.Atan2(offset.x, offset.z) * Mathf.Rad2Deg;
            float pitch = Mathf.Atan2(-offset.y, new Vector2(offset.x, offset.z).magnitude) * Mathf.Rad2Deg;
            P.View.Walk.SetPose(at, yaw, pitch); P.View.Layout(); Physics.SyncTransforms();
            Observe("fixture-position-standing-phone-camera"); yield return null;
            Capture("phone-room-standing", "FIXTURE_POSITIONED_STANDING_PHONE_VIEW");
            SetupScenarioSeated(); yield return null;
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(before)));
            Capture("phone-table-before", "NORMAL_SEATED_CONFIRMED_TICKET_BEFORE_PHONE");
            var tablePosition = app.SceneCamera.transform.position;
            var tableRotation = app.SceneCamera.transform.rotation; float tableFov = app.SceneCamera.fieldOfView;
            SetupScenarioPanel(G3Panel.Phone); yield return null;
            Assert.That(P.View.Phone.IsFocused, Is.True);
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(before)));
            Capture("phone-contacts", "PRODUCTION_FOCUSED_WORLD_PHONE_CAMERA");
            Click("contact-mother"); Click("phone-choose");
            long borrowAmount = P.BuildPanel().Cards.Single(x => x.Id == "borrow-1000").Action.Amount;
            Assert.That(borrowAmount, Is.EqualTo(10000)); Assert.That(G3Text.Money(borrowAmount), Is.EqualTo("1000"));
            Click("borrow-1000");
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(before)), "Choosing an amount is not a loan");
            var sendPoint = P.View.ButtonRect("phone-send").center;
            MouseEvent(sendPoint, true);
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(before)), "Phone actions execute on release, never press");
            Router.NotifyFocus(false); Router.NotifyFocus(true); MouseEvent(sendPoint, false);
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(before)), "A focus-cancelled send must not persist a request");
            Assert.That(P.Panel, Is.EqualTo(G3Panel.PhoneRequest)); Observe("phone-send-focus-cancelled-no-request");
            Click("phone-send"); yield return null;
            var pending = State.Copy();
            AssertPhoneEconomyUnchanged(before, pending);
            Assert.That(pending.PhoneEvents.Count, Is.EqualTo(before.PhoneEvents.Count + 1));
            var requested = pending.PhoneEvents.Single(x => !before.PhoneEvents.Any(y => y.EventId == x.EventId));
            Assert.That(requested.Kind, Is.EqualTo("BORROW_REQUESTED"));
            Assert.That(requested.ContactId, Is.EqualTo("mother")); Assert.That(requested.AmountMinor, Is.EqualTo(borrowAmount));
            Assert.That(pending.Revision, Is.EqualTo(before.Revision + 1));
            Assert.That(pending.Commands.Count, Is.EqualTo(before.Commands.Count + 1));
            Capture("phone-mom-pending", "PRODUCTION_WORLD_PHONE_PERSISTED_REQUEST_NOT_MONEY");
            var packetPoint = P.View.ButtonRect("packet-pending").center;
            MouseEvent(packetPoint, true); MouseEvent(packetPoint + Vector2.up * 24, true);
            MouseEvent(packetPoint, true); MouseEvent(packetPoint, false);
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(pending)), "Dragging across a packet cannot claim it");
            Assert.That(P.Panel, Is.EqualTo(G3Panel.Contact)); Observe("phone-packet-scroll-no-claim");
            Click("packet-pending"); Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(pending)));
            Click("phone-claim"); yield return null;
            var claimed = State.Copy(); AssertTicketAndDrawsUnchanged(before, claimed);
            Assert.That(claimed.CashMinor, Is.EqualTo(pending.CashMinor + borrowAmount));
            Assert.That(MotherDebt(claimed), Is.EqualTo(MotherDebt(pending) + borrowAmount));
            Assert.That(MotherLifetime(claimed), Is.EqualTo(MotherLifetime(pending) + borrowAmount));
            Assert.That(claimed.Loans.Count, Is.EqualTo(pending.Loans.Count + 1));
            var loan = claimed.Loans.Single(x => !pending.Loans.Any(y => y.LoanId == x.LoanId));
            Assert.That(loan.ContactId, Is.EqualTo("mother")); Assert.That(loan.BorrowedMinor, Is.EqualTo(borrowAmount));
            Assert.That(loan.RemainingMinor, Is.EqualTo(borrowAmount));
            Assert.That(claimed.PhoneEvents.Count, Is.EqualTo(pending.PhoneEvents.Count + 1));
            var received = claimed.PhoneEvents.Single(x => !pending.PhoneEvents.Any(y => y.EventId == x.EventId));
            Assert.That(received.Kind, Is.EqualTo("BORROWED")); Assert.That(received.ContactId, Is.EqualTo("mother"));
            Assert.That(received.AmountMinor, Is.EqualTo(borrowAmount)); Assert.That(received.LoanId, Is.EqualTo(loan.LoanId));
            Assert.That(requested.LoanId, Is.EqualTo(loan.LoanId));
            Assert.That(claimed.Ledger.Count, Is.EqualTo(pending.Ledger.Count + 1));
            Assert.That(claimed.Ledger.Last().DeltaMinor, Is.EqualTo(borrowAmount));
            Assert.That(claimed.Ledger.Last().BalanceMinor, Is.EqualTo(claimed.CashMinor));
            Assert.That(claimed.Revision, Is.EqualTo(pending.Revision + 1));
            Assert.That(claimed.Commands.Count, Is.EqualTo(pending.Commands.Count + 1));
            Assert.That(P.View.HasButton("phone-claim"), Is.False, "Claimed packet must not offer another payout");
            Capture("phone-mom-claimed", "PRODUCTION_WORLD_PHONE_SINGLE_COMMITTED_LOAN");
            Click("close-phone"); yield return null;
            Assert.That(P.View.Phone.IsFocused, Is.False); Assert.That(P.Panel, Is.EqualTo(G3Panel.None));
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(StateCodec.ComputeHash(claimed)), "Closing the phone cannot mutate saved state");
            AssertTicketAndDrawsUnchanged(before, State);
            Assert.That(app.SceneCamera.transform.position, Is.EqualTo(tablePosition));
            Assert.That(app.SceneCamera.transform.rotation, Is.EqualTo(tableRotation));
            Assert.That(app.SceneCamera.fieldOfView, Is.EqualTo(tableFov));
            Capture("phone-table-return", "NORMAL_SEATED_SAME_TICKET_AFTER_PHONE");
        }
        static long MotherDebt(RunState value) => value.Loans.Where(x => x.ContactId == "mother").Sum(x => x.RemainingMinor);
        static long MotherLifetime(RunState value) => value.Contacts.Single(x => x.ContactId == "mother").BorrowedLifetimeMinor;
        static string TicketContentHash(TicketState ticket) => ticket == null ? "NONE" : StateCodec.HashBytes(Encoding.UTF8.GetBytes(JsonUtility.ToJson(ticket)));
        static void AssertTicketAndDrawsUnchanged(RunState before, RunState after)
        {
            Assert.That(TicketContentHash(after.CurrentTicket), Is.EqualTo(TicketContentHash(before.CurrentTicket)));
            Assert.That(after.CurrentTicket.Id, Is.EqualTo(before.CurrentTicket.Id));
            Assert.That(after.CurrentTicket.Phase, Is.EqualTo(before.CurrentTicket.Phase));
            Assert.That(after.CurrentTicket.Scratch.ToBytes(), Is.EqualTo(before.CurrentTicket.Scratch.ToBytes()));
            Assert.That(after.NextToolIds, Is.EqualTo(before.NextToolIds));
            Assert.That(after.TicketsPurchasedToday, Is.EqualTo(before.TicketsPurchasedToday));
            Assert.That(after.SettledTicketCount, Is.EqualTo(before.SettledTicketCount));
            Assert.That(after.Settlements.Count, Is.EqualTo(before.Settlements.Count));
            Assert.That(after.EconomicCounter, Is.EqualTo(before.EconomicCounter));
            Assert.That(after.ChallengeCounter, Is.EqualTo(before.ChallengeCounter));
            Assert.That(after.ShopCounter, Is.EqualTo(before.ShopCounter));
        }
        static void AssertPhoneEconomyUnchanged(RunState before, RunState after)
        {
            AssertTicketAndDrawsUnchanged(before, after);
            Assert.That(after.CashMinor, Is.EqualTo(before.CashMinor));
            Assert.That(MotherDebt(after), Is.EqualTo(MotherDebt(before)));
            Assert.That(MotherLifetime(after), Is.EqualTo(MotherLifetime(before)));
            Assert.That(after.Loans.Count, Is.EqualTo(before.Loans.Count));
            Assert.That(after.Ledger.Count, Is.EqualTo(before.Ledger.Count));
        }

        void CheckRuntimeBudget()
        {
            if(runtimeProgress != null && runtimeProgress.ElapsedSeconds >= RuntimeSeconds)
            {
                Milestone("runtime-timeout");
                Assert.Fail("Visual fixture runtime exceeded 900 seconds; this is a diagnostic failure, never a skip or pass");
            }
        }
        void Milestone(string stage) => runtimeProgress?.Mark(stage, app != null && app.Presenter != null ? State : null, inputUpdates, frames.Count);

        void Pump()
        {
            CheckRuntimeBudget();
            InputSystem.Update(); inputUpdates++;
            Assert.That(InputState.currentUpdateType, Is.EqualTo(InputUpdateType.Manual));
            Router.PollInput();
        }
        void MouseEvent(Vector2 point, bool down)
        { InputSystem.QueueStateEvent(mouse, new MouseState { position = point, buttons = (ushort)(down ? 1 : 0) }); Pump(); }
        void KeyboardEvent(params Key[] keys)
        { InputSystem.QueueStateEvent(keyboard, new KeyboardState(keys)); Pump(); }
        void Click(string id)
        {
            Assert.That(P.View.HasButton(id), Is.True, "Missing runtime control: " + id);
            var point = P.View.ButtonRect(id).center;
            MouseEvent(point, true); MouseEvent(point, false); Observe("click:" + id);
        }
        // Explicit scenario context, never a claim of world navigation input.
        void SetupScenarioPanel(G3Panel panel)
        {P.OpenPanel(panel);Assert.That(P.Panel,Is.EqualTo(panel));Observe("scenario-panel:"+panel);}
        void SetupScenarioSeated()
        {Close();P.Execute(new G3Action(G3ActionKind.Sit));Assert.That(P.Walking,Is.False);Observe("scenario-seated-camera");}
        void Observe(string action)
        {
            actions.Add(new ActionReceipt { action = action, inputUpdate = inputUpdates, revision = State.Revision,
                phase = State.Phase.ToString(), panel = P.Panel.ToString(), stateSha256 = StateCodec.ComputeHash(State),
                playerPosition = P.View.Walk.SavedPosition, cameraPosition = app.SceneCamera.transform.position });
        }
        void Confirm() { Assert.That(P.Panel, Is.EqualTo(G3Panel.Confirm)); Click("confirm-action"); }
        void Close() { if(P.Panel != G3Panel.None) Click(P.PhoneVisible?"close-phone":"close-panel"); }
        void Buy(string type)
        {
            var before = State.Copy();
            Assert.That(before.HasUnsettledTicket, Is.False);
            Assert.That(before.TicketsPurchasedToday, Is.InRange(0, 11));
            Close(); SetupScenarioPanel(G3Panel.Tickets); Click(type == "number" ? "buy-number" : "buy-challenge"); Confirm();
            var after = State; var ticket = after.CurrentTicket;
            Assert.That(ticket, Is.Not.Null);
            Assert.That(ticket.Id, Is.Not.Empty);
            Assert.That(before.Tickets.Any(x => x.Id == ticket.Id), Is.False, "Purchase must create a new ticket identity");
            Assert.That(ticket.TicketType, Is.EqualTo(type));
            Assert.That(ticket.Phase, Is.EqualTo(TicketPhase.ACTIVE));
            Assert.That(ticket.PriceMinor, Is.EqualTo(DayRules.TicketPriceMinor));
            Assert.That(after.Phase, Is.EqualTo(DayPhase.DAY_OPEN));
            Assert.That(after.TicketsPurchasedToday, Is.EqualTo(before.TicketsPurchasedToday + 1));
            Assert.That(after.Tickets.Count, Is.EqualTo(before.Tickets.Count + 1));
            Assert.That(after.SettledTicketCount, Is.EqualTo(before.SettledTicketCount));
            Assert.That(after.Settlements.Count, Is.EqualTo(before.Settlements.Count));
            Assert.That(after.CashMinor, Is.EqualTo(before.CashMinor - DayRules.TicketPriceMinor));
            Assert.That(after.HasUnsettledTicket, Is.True);
        }
        void QuickRevealNumber()
        {
            var before = State.Copy(); string id = before.CurrentTicket.Id;
            Assert.That(before.CurrentTicket.TicketType, Is.EqualTo("number"));
            Assert.That(before.CurrentTicket.Phase, Is.EqualTo(TicketPhase.ACTIVE));
            Click("quick");
            var after = State;
            Assert.That(after.CurrentTicket.Id, Is.EqualTo(id));
            Assert.That(after.CurrentTicket.Phase, Is.EqualTo(TicketPhase.REVEALED_UNCLAIMED));
            Assert.That(after.CurrentTicket.Scratch.IsFullyRevealed, Is.True);
            Assert.That(after.CashMinor, Is.EqualTo(before.CashMinor));
            Assert.That(after.TicketsPurchasedToday, Is.EqualTo(before.TicketsPurchasedToday));
            Assert.That(after.SettledTicketCount, Is.EqualTo(before.SettledTicketCount));
            Assert.That(after.Settlements.Count, Is.EqualTo(before.Settlements.Count));
        }
        void Claim()
        {
            var before = State.Copy(); string id = before.CurrentTicket.Id;
            Assert.That(before.HasUnsettledTicket, Is.True);
            Assert.That(before.Settlements.Count(x => x.TicketId == id), Is.EqualTo(0));
            Click("claim"); if(P.Panel == G3Panel.Confirm) Confirm(); Close();
            var after = State;
            Assert.That(after.CurrentTicket.Id, Is.EqualTo(id));
            Assert.That(after.CurrentTicket.Phase, Is.EqualTo(TicketPhase.SETTLED));
            Assert.That(after.TicketsPurchasedToday, Is.EqualTo(before.TicketsPurchasedToday));
            Assert.That(after.SettledTicketCount, Is.EqualTo(before.SettledTicketCount + 1));
            Assert.That(after.Settlements.Count, Is.EqualTo(before.Settlements.Count + 1));
            Assert.That(after.Settlements.Count(x => x.TicketId == id), Is.EqualTo(1));
            Assert.That(after.CashMinor, Is.EqualTo(before.CashMinor + after.Settlements.Single(x => x.TicketId == id).TotalMinor));
            Assert.That(after.HasUnsettledTicket, Is.False);
            Assert.That(after.Phase, Is.EqualTo(after.TicketsPurchasedToday == 12 ? DayPhase.CLOSING_PREP : DayPhase.DAY_OPEN));
        }
        void BuyStock(string item)
        { Close(); SetupScenarioPanel(G3Panel.Shop); Click("stock-" + State.Stock.Single(x => x.ItemId == item).StockId); Click("stock-buy"); Confirm(); Close(); }
        void Equip(string item, int slot)
        { Close(); SetupScenarioPanel(G3Panel.Inventory); Click("tool-" + item); Click("equip-" + slot); Close(); Assert.That(State.NextToolIds[slot], Is.EqualTo(item)); }
        Vector2 CellPoint(int core, float u = .5f, float v = .5f)
        {
            var layout = P.View.Surface.Layout; var r = layout.Cells.Single(x => x.CoreIndex == core).Silver;
            return P.View.WorldToPresentationPoint(P.View.Surface.PaperUvToWorld(new Uv((r.X + u * r.Width) / layout.Width, 1 - (r.Y + (1 - v) * r.Height) / layout.Height)));
        }
        void ScratchCell(int core)
        {
            MouseEvent(CellPoint(core, .02f, .02f), true); bool right = true;
            for(float v = .02f; v < .99f; v += .10f)
            { MouseEvent(CellPoint(core, right ? .97f : .02f, v), true); MouseEvent(CellPoint(core, right ? .97f : .02f, Mathf.Min(.99f, v + .10f)), true); right = !right; }
            MouseEvent(CellPoint(core, .97f, .99f), false); Observe("scratch-cell:" + core);
        }
        void RevealSelected(int core)
        { MouseEvent(CellPoint(core), true); MouseEvent(CellPoint(core), false); Assert.That(State.CurrentTicket.SelectedCell, Is.EqualTo(core)); Click("quick"); Assert.That(State.CurrentTicket.RevealedCells[core], Is.True); }
        void BindTarget(int width, int height)
        {
            ReleaseTarget(); target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32) { name = "Visual candidate genuine camera output" };
            target.Create(); app.SceneCamera.targetTexture = target; P.View.Layout();
        }
        void ReleaseTarget()
        {
            if(target == null) return;
            if(app != null && app.Presenter != null) app.SceneCamera.targetTexture = null;
            if(RenderTexture.active == target) RenderTexture.active = null;
            target.Release(); Object.Destroy(target); target = null;
        }
        Rect ProjectedPaperBounds()
        {
            if(!P.View.Surface.IsVisible) return new Rect();
            var corners = new[] { new Uv(0, 0), new Uv(0, 1), new Uv(1, 0), new Uv(1, 1) }
                .Select(uv => P.View.WorldToPresentationPoint(P.View.Surface.PaperUvToWorld(uv))).ToArray();
            return Rect.MinMaxRect(corners.Min(p => p.x), corners.Min(p => p.y), corners.Max(p => p.x), corners.Max(p => p.y));
        }
        Rect ProjectedPhoneScreenBounds()
        {
            var corners = P.View.Phone.ScreenWorldCorners;
            Assert.That(corners, Has.Length.EqualTo(4));
            Assert.That(Vector3.Cross(corners[1] - corners[0], corners[2] - corners[0]).sqrMagnitude, Is.GreaterThan(0.00000001f));
            var points = corners.Select(P.View.WorldToPresentationPoint).ToArray();
            return Rect.MinMaxRect(points.Min(p => p.x), points.Min(p => p.y), points.Max(p => p.x), points.Max(p => p.y));
        }
        static ProjectionReceipt Projection(Rect rect)
        { return new ProjectionReceipt { x = rect.x, y = rect.y, width = rect.width, height = rect.height }; }
        void Capture(string stage, string cameraOrigin, ExteriorReceipt exterior = null, string fixtureStateBefore = null)
        {
            CheckRuntimeBudget(); Milestone("capture-begin:" + stage);
            // Daylight balance experiment; the native frame must use the declared light state.
            bool lightingNight=State.Phase==DayPhase.NIGHT_BILL||State.Phase==DayPhase.DAY_COMPLETE||State.Phase==DayPhase.RUN_FAILED;
            var directional=P.View.Environment.GetComponentsInChildren<Light>().Where(light=>light.type==LightType.Directional).ToArray();
            Assert.That(directional,Has.Length.EqualTo(1),"Exactly one owned directional source is required");
            Assert.That(Quaternion.Angle(directional[0].transform.rotation,lightingNight?Quaternion.Euler(25,190,0):Quaternion.Euler(10,185,0)),Is.LessThan(.01f),"Actual day/night direction must match the source-owned A/B angle");
            Assert.That(directional[0].intensity,Is.EqualTo(lightingNight?.16f:.6f).Within(.00001f),"Daylight balance must preserve the explicit day/night source energy");
            var readingSource=P.View.Environment.transform.Find("Table reading pendant");
            Assert.That(readingSource,Is.Not.Null,"The authored reading source must remain present");
            var readingLight=readingSource.GetComponent<Light>();
            Assert.That(readingLight,Is.Not.Null);
            Assert.That(readingLight.intensity,Is.EqualTo(lightingNight?1.3f:1.6f).Within(.00001f),"Local day fill changes while original night reading energy remains intact");
            P.View.RefreshGlyphGeometry();
            Assert.That(P.View.AllHudLabelsFit, Is.True, string.Join(" | ", P.View.OverflowingHudLabels));
            var hud = app.SceneCamera.transform.Find("Same-camera readable HUD");
            Assert.That(hud, Is.Not.Null, "Normal runtime HUD root is required");
            var frustum = GeometryUtility.CalculateFrustumPlanes(app.SceneCamera);
            int visibleHudRenderers = hud.GetComponentsInChildren<Renderer>().Count(r => r.enabled && r.gameObject.activeInHierarchy &&
                (app.SceneCamera.cullingMask & (1 << r.gameObject.layer)) != 0 && GeometryUtility.TestPlanesAABB(frustum, r.bounds));
            bool phoneCloseUp = stage == "phone-contacts" || stage == "phone-mom-pending" || stage == "phone-mom-claimed";
            if(!phoneCloseUp) Assert.That(visibleHudRenderers, Is.GreaterThan(5), "HUD renderers must actually participate in this camera view");
            var phone = P.View.Phone;
            Assert.That(phone, Is.Not.Null);
            Assert.That(phone, Is.SameAs(phoneIdentity), "The same persistent phone instance must survive every view");
            bool phoneWorldObjectActive = phone.isActiveAndEnabled;
            int phoneActiveRendererCount = phone.GetComponentsInChildren<Renderer>().Count(r => r.enabled && r.gameObject.activeInHierarchy);
            Assert.That(phoneWorldObjectActive, Is.True); Assert.That(phoneActiveRendererCount, Is.GreaterThan(2));
            int phoneRenderers = phone.GetComponentsInChildren<Renderer>().Count(r => r.enabled && r.gameObject.activeInHierarchy &&
                (app.SceneCamera.cullingMask & (1 << r.gameObject.layer)) != 0 && GeometryUtility.TestPlanesAABB(frustum, r.bounds));
            var phoneBounds = ProjectedPhoneScreenBounds();
            var phoneCorners = phone.ScreenWorldCorners;
            float phoneMinDepth = phoneCorners.Min(p => app.SceneCamera.WorldToScreenPoint(p).z);
            float phoneMaxDepth = phoneCorners.Max(p => app.SceneCamera.WorldToScreenPoint(p).z);
            var phoneNormal = Vector3.Cross(phoneCorners[1] - phoneCorners[0], phoneCorners[2] - phoneCorners[0]).normalized;
            var phoneCenter = phoneCorners.Aggregate(Vector3.zero, (sum, point) => sum + point) / 4;
            float phonePlaneCameraAbsCosine = Mathf.Abs(Vector3.Dot(phoneNormal, (app.SceneCamera.transform.position - phoneCenter).normalized));
            Assert.That(phone.IsFocused, Is.EqualTo(phoneCloseUp), "Only the three explicit phone close-ups use phone focus");
            if(stage == "phone-room-standing" || phoneCloseUp)
            {
                Assert.That(phoneRenderers, Is.GreaterThan(2), "Real phone body and screen must participate in the camera");
                Assert.That(phoneBounds.width, Is.GreaterThan(2)); Assert.That(phoneBounds.height, Is.GreaterThan(2));
                Assert.That(phoneBounds.xMin, Is.GreaterThanOrEqualTo(0)); Assert.That(phoneBounds.yMin, Is.GreaterThanOrEqualTo(0));
                Assert.That(phoneBounds.xMax, Is.LessThanOrEqualTo(target.width)); Assert.That(phoneBounds.yMax, Is.LessThanOrEqualTo(target.height));
                Assert.That(phoneMinDepth, Is.GreaterThan(app.SceneCamera.nearClipPlane));
                Assert.That(phoneMaxDepth, Is.LessThan(app.SceneCamera.farClipPlane));
                Assert.That(phonePlaneCameraAbsCosine, Is.GreaterThan(.2f), "Phone screen cannot be edge-on");
            }
            var request = new RenderPipeline.StandardRequest { destination = target };
            Assert.That(RenderPipeline.SupportsRenderRequest(app.SceneCamera, request), Is.True);
            var old = RenderTexture.active; var image = new Texture2D(target.width, target.height, TextureFormat.RGB24, false);
            try
            {
                RenderPipeline.SubmitRenderRequest(app.SceneCamera, request); RenderTexture.active = target;
                image.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0, false); image.Apply(false, false);
                var bytes = image.EncodeToPNG(); Assert.That(bytes.Length, Is.InRange(10000, 8 * 1024 * 1024));
                File.WriteAllBytes(Path.Combine(output, stage + ".png"), bytes);
                var ticket = State.CurrentTicket;
                frames.Add(new FrameReceipt {
                    exterior = exterior, fixtureStateBefore = fixtureStateBefore,
                    stage = stage, file = stage + ".png", sha256 = StateCodec.HashBytes(bytes), bytes = bytes.Length,
                    capturedUtc = DateTime.UtcNow.ToString("O"), width = target.width, height = target.height,
                    ticketContentSha256 = TicketContentHash(State.CurrentTicket),
                    phoneFocused = phone.IsFocused, phoneFrustumRendererCount = phoneRenderers, phoneScreenBounds = Projection(phoneBounds),
                    phoneWorldObjectActive = phoneWorldObjectActive, phoneActiveRendererCount = phoneActiveRendererCount, phoneInstanceId = phone.GetInstanceID(),
                    phoneScreenMinDepth = phoneMinDepth, phoneScreenMaxDepth = phoneMaxDepth, phonePlaneCameraAbsCosine = phonePlaneCameraAbsCosine,
                    cashMinor = State.CashMinor, motherDebtMinor = MotherDebt(State), motherLifetimeMinor = MotherLifetime(State),
                    loanCount = State.Loans.Count, ledgerCount = State.Ledger.Count, phoneEventCount = State.PhoneEvents.Count,
                    stateSha256 = StateCodec.ComputeHash(State), seedSha256 = StateCodec.HashBytes(Encoding.UTF8.GetBytes(State.Seed)),
                    gameRunId = State.RunId, fixtureLabel = State.FixtureLabel, revision = State.Revision,
                    ticketId = ticket?.Id ?? "NONE", ticketPhase = ticket?.Phase.ToString() ?? "NONE",
                    ticketMaskSha256 = ticket == null ? "NONE" : StateCodec.HashBytes(ticket.Scratch.ToBytes()),
                    revealedCells = ticket?.Scratch.RevealedCellCount ?? 0, dayPhase = State.Phase.ToString(),
                    currentTools = ticket == null ? new string[0] : ticket.ConfigurationSnapshot.OrderBy(x => x.TableSlot).Select(x => x.ItemId).ToArray(),
                    nextTools = State.NextToolIds.ToArray(), panel = P.Panel.ToString(), mode = P.Mode.ToString(),
                    inputUpdates = inputUpdates, actionCount = actions.Count, cameraOrigin = cameraOrigin,
                    cameraPosition = app.SceneCamera.transform.position, cameraEuler = app.SceneCamera.transform.eulerAngles,
                    cameraFov = app.SceneCamera.fieldOfView, cameraOrthographic = app.SceneCamera.orthographic,
                    importedRendererCount = P.View.Environment.ImportedRendererCount,
                    renderedShopRendererCount = P.View.Environment.RenderedShopRendererCount,
                    renderedShopMaterialCount = P.View.Environment.RenderedShopMaterialCount,
                    hudOpaqueAreaRatio = P.View.VisibleOpaqueHudAreaRatio,
                    visibleControlIds = P.View.VisibleControlIds, moreVisible = P.View.MoreVisible,
                    paperVisible = P.View.Surface.IsVisible, paperPresentationBounds = Projection(ProjectedPaperBounds()),
                    toolPresentationBounds = Enumerable.Range(0, 3).Select(slot => Projection(P.View.ToolPresentationBounds(slot))).ToArray(),
                    hudVisible = hud.gameObject.activeInHierarchy && visibleHudRenderers > 5, hudFrustumRendererCount = visibleHudRenderers, hudFits = P.View.AllHudLabelsFit, qualityName = QualitySettings.names[QualitySettings.GetQualityLevel()]
                });
                WriteReceipt(false);
                Milestone("capture-end:" + stage); CheckRuntimeBudget();
            }
            finally { RenderTexture.active = old; Object.Destroy(image); }
        }
        void WriteReceipt(bool complete)
        {
            var receipt = new CaptureReceipt {
                sourceCommit = Arg("-probeCommit"), runId = Arg("-probeRunId"), runAttempt = Arg("-probeRunAttempt"),
                unityVersion = Application.unityVersion, graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(),
                graphicsDeviceName = SystemInfo.graphicsDeviceName, complete = complete,
                frames = frames.ToArray(), actions = actions.ToArray()
            };
            Assert.That(receipt.sourceCommit, Does.Match("^[0-9a-f]{40}$"));
            Assert.That(receipt.runId, Does.Match("^[1-9][0-9]*$"));
            Assert.That(receipt.runAttempt, Does.Match("^[1-9][0-9]*$"));
            File.WriteAllText(Path.Combine(output, "capture-receipt.json"), JsonUtility.ToJson(receipt, true));
        }
        static string Arg(string key)
        { var args = Environment.GetCommandLineArgs(); int i = Array.IndexOf(args, key); return i >= 0 && i + 1 < args.Length ? args[i + 1] : ""; }
        // Fixed-schema milestones only, never exception text, environment values, seeds, or Unity logs.
        // Cooperative clocks cannot interrupt blocked native Unity calls; CI's step timeout is the backstop.
        sealed class ProgressTrail
        {
            readonly Stopwatch timer = Stopwatch.StartNew();
            readonly string kind, path;
            readonly List<ProgressEvent> events = new List<ProgressEvent>();
            readonly List<FrameCostRow> costs = new List<FrameCostRow>();
            public double ElapsedSeconds => timer.Elapsed.TotalSeconds;
            public ProgressTrail(string kind)
            {
                this.kind = kind;
                path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../artifacts/visual-candidate/" + kind + "-progress.json"));
                Directory.CreateDirectory(Path.GetDirectoryName(path));
            }
            public void Mark(string stage, RunState state = null, int inputUpdates = 0, int frameCount = 0)
            {
                Assert.That(events.Count, Is.LessThan(128), "Diagnostic milestone bound exceeded");
                events.Add(new ProgressEvent { stage = stage, elapsedMs = timer.ElapsedMilliseconds,
                    utc = DateTime.UtcNow.ToString("O"), inputUpdates = inputUpdates, frameCount = frameCount,
                    purchased = state?.TicketsPurchasedToday ?? -1, settled = state?.SettledTicketCount ?? -1,
                    dayPhase = state?.Phase.ToString() ?? "UNAVAILABLE" });
                ProgressReceipt receipt;
                if(kind=="runtime")
                {
                    var glyph=BoundedGlyphLabel.CostObservation();var input=G3InputRouter.CostObservation();
                    costs.Add(new FrameCostRow{values=new[]{glyph[0],glyph[1],glyph[2],glyph[3],input[0],input[1],input[2],input[3],input[4],input[5],System.Math.Max(glyph[4],input[6])}});
                    receipt=new RuntimeProgressReceipt{costs=costs.ToArray(),tickFrequency=Stopwatch.Frequency};
                }
                else receipt=new ProgressReceipt();
                receipt.kind=kind;receipt.sourceCommit=Arg("-probeCommit");receipt.runId=Arg("-probeRunId");receipt.runAttempt=Arg("-probeRunAttempt");receipt.events=events.ToArray();
                File.WriteAllText(path, JsonUtility.ToJson(receipt, kind!="runtime"));
                Debug.Log("VISUAL_CANDIDATE_PROGRESS " + kind + " " + stage + " elapsedMs=" + timer.ElapsedMilliseconds);
            }
        }
        [Serializable] sealed class ProgressEvent
        { public string stage, utc, dayPhase; public long elapsedMs; public int inputUpdates, frameCount, purchased, settled; }
        [Serializable] class ProgressReceipt
        {
            public int schemaVersion = 1;
            public string scope = Scope, kind, sourceCommit, runId, runAttempt;
            public string status = "MILESTONES_ONLY_NOT_TEST_PASS";
            public ProgressEvent[] events;
        }
        [Serializable] sealed class FrameCostRow { public long[] values; }
        [Serializable] sealed class RuntimeProgressReceipt:ProgressReceipt { public long tickFrequency;public FrameCostRow[] costs; }
        [Serializable] sealed class ActionReceipt
        { public string action, phase, panel, stateSha256; public int inputUpdate; public long revision; public Vector3 playerPosition, cameraPosition; }
        [Serializable] sealed class ProjectionReceipt { public float x, y, width, height; }
        [Serializable] sealed class ExteriorReceipt
        {
            public string basis, backdropShader, textureName;
            public int glassFrustumRendererCount, backdropFrustumRendererCount, textureWidth, textureHeight, backdropRendererCount, transparentGlassMaterialCount, glassRenderQueue, nearFieldTriangles, nearFieldColliderCount;
            public float exposure, glassAlpha, glassSurface, glassZWrite, feltNormalScale, linerSmoothness, brassSmoothness;
        }
        [Serializable] sealed class FrameReceipt
        {
            public string stateOrigin="REAL_SERVICE_TRANSACTIONS", navigationEvidence="SCENARIO_SETUP_NOT_WORLD_INPUT";
            public string stage, file, sha256, capturedUtc, stateSha256, seedSha256, gameRunId, fixtureLabel, ticketId, ticketPhase, ticketMaskSha256, dayPhase, panel, mode, cameraOrigin, qualityName;
            public ExteriorReceipt exterior; public string fixtureStateBefore, fixtureStateAfter; public bool fixturePoseRestored;
            public string ticketContentSha256; public bool phoneFocused, phoneWorldObjectActive; public int phoneActiveRendererCount, phoneInstanceId; public ProjectionReceipt phoneScreenBounds;
            public float phoneScreenMinDepth, phoneScreenMaxDepth, phonePlaneCameraAbsCosine;
            public long cashMinor, motherDebtMinor, motherLifetimeMinor; public int phoneFrustumRendererCount, loanCount, ledgerCount, phoneEventCount;
            public long bytes, revision; public int width, height, revealedCells, inputUpdates, actionCount, importedRendererCount, hudFrustumRendererCount, renderedShopRendererCount, renderedShopMaterialCount;
            public string[] currentTools, nextTools, visibleControlIds; public ProjectionReceipt paperPresentationBounds; public ProjectionReceipt[] toolPresentationBounds; public float hudOpaqueAreaRatio; public Vector3 cameraPosition, cameraEuler; public float cameraFov;
            public bool cameraOrthographic, hudVisible, hudFits, moreVisible, paperVisible;
        }
        [Serializable] sealed class CaptureReceipt
        {
            public int schemaVersion = 5;
            public string candidatePresentation = "V31_SCENARIO_STATE_VIEWS_NOT_WORLD_INPUT_PASS";
            public string scope = Scope, sourceCommit, runId, runAttempt, unityVersion, graphicsDeviceType, graphicsDeviceName;
            public string inputEvidence = "SIMULATED_UI_INPUT_WITH_DECLARED_SCENARIO_SETUP", captureMethod = "URP_STANDARD_REQUEST_READPIXELS",
                seedDisclosure = "FIXED_DIAGNOSTIC_SEED_HASH_ONLY", hudVisibilityBasis = "ENABLED_CAMERA_LAYER_AND_FRUSTUM_TEST_NOT_PIXEL_OCCLUSION", deviceQa = "NOT_RUN", visualReview = "PENDING", g3Gate = "NOT_EVALUATED";
            public bool complete; public FrameReceipt[] frames; public ActionReceipt[] actions;
        }
    }
}
