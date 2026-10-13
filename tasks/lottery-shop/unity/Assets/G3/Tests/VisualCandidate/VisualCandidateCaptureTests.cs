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
                var type = AppDomain.CurrentDomain.GetAssemblies()
                    .Select(a => a.GetType("Lottery.G3.Editor.G3Build", false)).FirstOrDefault(t => t != null);
                if(type == null) throw new InvalidOperationException("G3Build missing: no whitebox fallback");
                var prepare = type.GetMethod("Prepare", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
                if(prepare == null) throw new InvalidOperationException("G3Build.Prepare missing");
                prepare.Invoke(null, null);
                progress.Mark("prebuild-end");
            }
            catch { progress.Mark("prebuild-failed"); throw; }
#endif
        }

        [UnitySetUp]
        public IEnumerator SetUpRuntime()
        {
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

        [UnityTest]
        public IEnumerator RealRuntimeSixGroupsRetainHudAndRoutePurchasesScratchShelfAndNight()
        {
            // Only the entry framing is fixture-positioned. No claim of a walked
            // arrival is inferred from that single establishing photograph.
            Click("stand");
            P.View.Walk.SetPose(P.View.Environment.EntryPosition, P.View.Environment.EntryYaw);
            P.View.Layout(); Physics.SyncTransforms(); Observe("fixture-position-entry-camera"); yield return null;
            Capture("entry-whole-shop", "FIXTURE_POSITIONED_PLAYER_VIEW");
            Click("stand"); yield return null;
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
            QuickRevealNumber(); Claim();
            BuyStock("inspection_lamp"); Equip("inspection_lamp", 1);
            BuyStock("large_prize_stamp"); Equip("large_prize_stamp", 2);
            Buy("challenge"); RevealSelected(0); RevealSelected(1);
            Assert.That(State.CurrentTicket.ConfigurationSnapshot.Length, Is.EqualTo(3));
            Assert.That(State.CurrentTicket.RevealedCells.Count(x => x), Is.EqualTo(2));
            Assert.That(P.Service.PreviewSettlement().RawPrizeMinor, Is.EqualTo(2000));
            yield return null; Capture("challenge-two-safe-three-tools", "NORMAL_SEATED_PLAYER_VIEW");

            string challengeHash = StateCodec.ComputeHash(State);
            Click("open-shop"); string shortcutBody = P.BuildPanel().Body; Close();
            Click("stand");
            // A known normal stand point begins a bounded real keyboard traversal.
            // Every subsequent displacement goes through the actual InputRouter.
            P.View.Walk.SetPose(P.View.Environment.StandPosition, P.View.Environment.StandYaw);
            Observe("fixture-position-normal-stand-start");
            yield return WalkTo(new Vector3(0, 0, 1.15f));
            yield return WalkTo(new Vector3(-.95f, 0, 1.15f));
            yield return WalkTo(P.View.Environment.ShelfViewPosition);
            yield return Face(P.View.Environment.ShelfTargetPosition);
            yield return null; Capture("shelf-before-open", "KEYBOARD_TRAVERSED_PLAYER_VIEW");
            var point = P.View.WorldToPresentationPoint(P.View.Environment.ShelfTargetPosition);
            Assert.That(P.View.ConsumeUi(point, out _), Is.False, "Physical shelf must remain outside HUD hit regions");
            var worldTarget = P.View.WorldTarget(point);
            Assert.That(worldTarget, Is.Not.Null, "Shelf must be hit by the genuine camera ray");
            Assert.That(worldTarget.Panel, Is.EqualTo(G3Panel.Shop));
            var pose = app.SceneCamera.transform.position; var rotation = app.SceneCamera.transform.rotation;
            MouseEvent(point, true); MouseEvent(point, false);
            Assert.That(P.Panel, Is.EqualTo(G3Panel.Shop));
            Assert.That(P.BuildPanel().Body, Is.EqualTo(shortcutBody));
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(challengeHash));
            Observe("physical-shelf-open-stock-equals-shortcut");
            yield return null; Capture("shelf-after-open", "SAME_POSE_PHYSICAL_RAY_CLICK");
            Close();
            Assert.That(app.SceneCamera.transform.position, Is.EqualTo(pose));
            Assert.That(app.SceneCamera.transform.rotation, Is.EqualTo(rotation));
            yield return WalkTo(new Vector3(-.95f, 0, 1.15f));
            yield return WalkTo(new Vector3(0, 0, 1.15f));
            yield return WalkTo(P.View.Environment.StandPosition);
            Click("stand");
            Assert.That(StateCodec.ComputeHash(State), Is.EqualTo(challengeHash));
            yield return null; Capture("challenge-returned-from-shelf", "KEYBOARD_RETURN_SAME_CONFIRMED_TICKET");
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
            var dayPosition = app.SceneCamera.transform.position; var dayRotation = app.SceneCamera.transform.rotation;
            Click("open-bill"); Click("enter-night"); Confirm();
            Assert.That(State.Phase, Is.EqualTo(DayPhase.NIGHT_BILL));
            Close(); yield return null;
            Assert.That(P.Panel, Is.EqualTo(G3Panel.None));
            Assert.That(app.SceneCamera.transform.position, Is.EqualTo(dayPosition));
            Assert.That(app.SceneCamera.transform.rotation, Is.EqualTo(dayRotation));
            Capture("night-table", "SAME_CAMERA_AS_CLOSING_DAY_WITH_BILL_CLOSED");
            Click("open-bill"); yield return null; Capture("night-bill", "NORMAL_BILL_INFORMATION_HIERARCHY");
            Assert.That(frames.Count, Is.EqualTo(11));
            // Returning to the same confirmed ticket may correctly produce identical pixels.
            Assert.That(frames.Single(x => x.stage == "shelf-before-open").sha256, Is.Not.EqualTo(frames.Single(x => x.stage == "shelf-after-open").sha256));
            Assert.That(frames.Single(x => x.stage == "closing-day-table").sha256, Is.Not.EqualTo(frames.Single(x => x.stage == "night-table").sha256));
            WriteReceipt(true);
            Milestone("scenario-complete");
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
            // Secondary navigation is genuinely opened through the visible control.
            // Never mutate the presentation's More state or bypass the input router.
            if(!P.View.HasButton(id) && (id == "open-tickets" || id == "open-drawer" || id == "open-bill" || id == "open-settings"))
            {
                Assert.That(P.View.HasButton("open-more"), Is.True, "Missing visible More navigation for " + id);
                var more = P.View.ButtonRect("open-more").center;
                MouseEvent(more, true); MouseEvent(more, false); Observe("click:open-more");
            }
            Assert.That(P.View.HasButton(id), Is.True, "Missing runtime control: " + id);
            var point = P.View.ButtonRect(id).center;
            MouseEvent(point, true); MouseEvent(point, false); Observe("click:" + id);
        }
        void Observe(string action)
        {
            actions.Add(new ActionReceipt { action = action, inputUpdate = inputUpdates, revision = State.Revision,
                phase = State.Phase.ToString(), panel = P.Panel.ToString(), stateSha256 = StateCodec.ComputeHash(State),
                playerPosition = P.View.Walk.SavedPosition, cameraPosition = app.SceneCamera.transform.position });
        }
        void Confirm() { Assert.That(P.Panel, Is.EqualTo(G3Panel.Confirm)); Click("confirm-action"); }
        void Close() { if(P.Panel != G3Panel.None) Click("close-panel"); }
        void Buy(string type)
        {
            var before = State.Copy();
            Assert.That(before.HasUnsettledTicket, Is.False);
            Assert.That(before.TicketsPurchasedToday, Is.InRange(0, 11));
            Close(); Click("open-tickets"); Click(type == "number" ? "buy-number" : "buy-challenge"); Confirm();
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
        { Close(); Click("open-shop"); Click("stock-" + State.Stock.Single(x => x.ItemId == item).StockId); Click("stock-buy"); Confirm(); Close(); }
        void Equip(string item, int slot)
        { Close(); Click("open-inventory"); Click("tool-" + item); Click("equip-" + slot); Close(); Assert.That(State.NextToolIds[slot], Is.EqualTo(item)); }
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
        IEnumerator Face(Vector3 point)
        {
            var timer = Stopwatch.StartNew(); Milestone("face-begin");
            for(int i = 0; i < 600; i++)
            {
                CheckRuntimeBudget();
                Assert.That(timer.Elapsed.TotalSeconds, Is.LessThan(FaceSeconds), "Keyboard turn exceeded 120 seconds");
                var offset = point - app.SceneCamera.transform.position;
                float desired = Mathf.Atan2(offset.x, offset.z) * Mathf.Rad2Deg;
                float delta = Mathf.DeltaAngle(app.SceneCamera.transform.eulerAngles.y, desired);
                if(Mathf.Abs(delta) < 1.5f) { KeyboardEvent(); Milestone("face-end"); yield break; }
                KeyboardEvent(delta > 0 ? Key.RightArrow : Key.LeftArrow); yield return null;
            }
            KeyboardEvent(); Assert.Fail("Keyboard turn did not reach the physical target");
        }
        IEnumerator WalkTo(Vector3 destination)
        {
            var start = P.View.Walk.SavedPosition;
            var timer = Stopwatch.StartNew(); Milestone("walk-begin");
            yield return Face(new Vector3(destination.x, app.SceneCamera.transform.position.y, destination.z));
            for(int i = 0; i < 1200; i++)
            {
                CheckRuntimeBudget();
                Assert.That(timer.Elapsed.TotalSeconds, Is.LessThan(WalkSeconds), "Keyboard waypoint exceeded 180 seconds");
                var at = P.View.Walk.SavedPosition; var delta = new Vector2(destination.x - at.x, destination.z - at.z);
                if(delta.magnitude < .09f) { KeyboardEvent(); Observe("keyboard-walk-waypoint"); Milestone("walk-end"); yield break; }
                float desired = Mathf.Atan2(delta.x, delta.y) * Mathf.Rad2Deg;
                float angle = Mathf.DeltaAngle(app.SceneCamera.transform.eulerAngles.y, desired);
                KeyboardEvent(Mathf.Abs(angle) > 4 ? (angle > 0 ? Key.RightArrow : Key.LeftArrow) : Key.W);
                yield return null;
            }
            KeyboardEvent(); Assert.Fail("Real keyboard path blocked from " + start + " to " + destination);
        }
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
        static ProjectionReceipt Projection(Rect rect)
        { return new ProjectionReceipt { x = rect.x, y = rect.y, width = rect.width, height = rect.height }; }
        void Capture(string stage, string cameraOrigin)
        {
            CheckRuntimeBudget(); Milestone("capture-begin:" + stage);
            P.View.RefreshGlyphGeometry();
            Assert.That(P.View.AllHudLabelsFit, Is.True, string.Join(" | ", P.View.OverflowingHudLabels));
            var hud = app.SceneCamera.transform.Find("Same-camera readable HUD");
            Assert.That(hud, Is.Not.Null, "Normal runtime HUD root is required");
            var frustum = GeometryUtility.CalculateFrustumPlanes(app.SceneCamera);
            int visibleHudRenderers = hud.GetComponentsInChildren<Renderer>().Count(r => r.enabled && r.gameObject.activeInHierarchy &&
                (app.SceneCamera.cullingMask & (1 << r.gameObject.layer)) != 0 && GeometryUtility.TestPlanesAABB(frustum, r.bounds));
            Assert.That(visibleHudRenderers, Is.GreaterThan(5), "HUD renderers must actually participate in this camera view");
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
                    stage = stage, file = stage + ".png", sha256 = StateCodec.HashBytes(bytes), bytes = bytes.Length,
                    capturedUtc = DateTime.UtcNow.ToString("O"), width = target.width, height = target.height,
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
                File.WriteAllText(path, JsonUtility.ToJson(new ProgressReceipt { kind = kind, sourceCommit = Arg("-probeCommit"),
                    runId = Arg("-probeRunId"), runAttempt = Arg("-probeRunAttempt"), events = events.ToArray() }, true));
                Debug.Log("VISUAL_CANDIDATE_PROGRESS " + kind + " " + stage + " elapsedMs=" + timer.ElapsedMilliseconds);
            }
        }
        [Serializable] sealed class ProgressEvent
        { public string stage, utc, dayPhase; public long elapsedMs; public int inputUpdates, frameCount, purchased, settled; }
        [Serializable] sealed class ProgressReceipt
        {
            public int schemaVersion = 1;
            public string scope = Scope, kind, sourceCommit, runId, runAttempt;
            public string status = "MILESTONES_ONLY_NOT_TEST_PASS";
            public ProgressEvent[] events;
        }
        [Serializable] sealed class ActionReceipt
        { public string action, phase, panel, stateSha256; public int inputUpdate; public long revision; public Vector3 playerPosition, cameraPosition; }
        [Serializable] sealed class ProjectionReceipt { public float x, y, width, height; }
        [Serializable] sealed class FrameReceipt
        {
            public string stage, file, sha256, capturedUtc, stateSha256, seedSha256, gameRunId, fixtureLabel, ticketId, ticketPhase, ticketMaskSha256, dayPhase, panel, mode, cameraOrigin, qualityName;
            public long bytes, revision; public int width, height, revealedCells, inputUpdates, actionCount, importedRendererCount, hudFrustumRendererCount, renderedShopRendererCount, renderedShopMaterialCount;
            public string[] currentTools, nextTools, visibleControlIds; public ProjectionReceipt paperPresentationBounds; public ProjectionReceipt[] toolPresentationBounds; public float hudOpaqueAreaRatio; public Vector3 cameraPosition, cameraEuler; public float cameraFov;
            public bool cameraOrthographic, hudVisible, hudFits, moreVisible, paperVisible;
        }
        [Serializable] sealed class CaptureReceipt
        {
            public int schemaVersion = 2;
            public string candidatePresentation = "V13_MORE_NAVIGATION_MEASURED_GEOMETRY_NOT_VISUAL_PASS";
            public string scope = Scope, sourceCommit, runId, runAttempt, unityVersion, graphicsDeviceType, graphicsDeviceName;
            public string inputEvidence = "SIMULATED_INPUT_SYSTEM", captureMethod = "URP_STANDARD_REQUEST_READPIXELS",
                seedDisclosure = "FIXED_DIAGNOSTIC_SEED_HASH_ONLY", hudVisibilityBasis = "ENABLED_CAMERA_LAYER_AND_FRUSTUM_TEST_NOT_PIXEL_OCCLUSION", deviceQa = "NOT_RUN", visualReview = "PENDING", g3Gate = "NOT_EVALUATED";
            public bool complete; public FrameReceipt[] frames; public ActionReceipt[] actions;
        }
    }
}
