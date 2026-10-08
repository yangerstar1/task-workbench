#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Editor
{
    // Compiled only for Editor; runtime folder permits ephemeral MonoBehaviour attachment. Does not approve content or alter authoritative simulation state.
    [DefaultExecutionOrder(-50)]
    public sealed class JourneyInputEvidence : MonoBehaviour
    {
        [Serializable] public sealed class Plan
        {
            public string label = "automated-input-diagnostic-not-human-playtest";
            public float maximumWallSeconds = 120;
            public Step[] steps;
        }
        [Serializable] public sealed class Step
        {
            public string label;
            public float seconds = 1;
            public int region; // 0 means no region assertion (e.g. initial loading).
            public string status, control, promptContains;
            public float moveX, moveY, lookXDegreesPerSecond, lookYDegreesPerSecond;
            public bool accelerate, brake, fire, interact, reload, allowLoadError;
            public string command; // Begin, Pause, Restart, RetryLoad; same entrypoints as HUD.
        }
        [Serializable] sealed class Sample
        {
            public string kind = "sample", label, utc, status, control, prompt, loadError, activityEvidence;
            public int frame, step, region, generation, playerHealth, vehicleHealth, loaded, reserve, upgrades, nearbyLiveThreats, currentWave, completedWaves, waveAlive, screenWidth, screenHeight;
            public double waveCharge;
            public double wall, gameTime, stormTime, stormFront, progress;
            public float dt, speed;
            public Vector3 player, vehicle;
            public bool cabin, installing, reloading, power, gate, objectives, ramPart, coil,
                environmentVerified, combatAssetsVerified, safety;
        }
        [Serializable] sealed class Event
        {
            public string kind, detail;
            public int frame;
            public double wall;
        }
        JourneyDirector director;
        Plan plan;
        StreamWriter log;
        string output;
        int index = -1;
        double start, stepStart, nextCapture;
        bool stopped, capturePending;
        readonly Dictionary<TouchControl, int> held = new Dictionary<TouchControl, int>();
        int nextPointer = 100000;
        Coroutine capture;
        const string Marker = "EDITOR INPUT DIAGNOSTIC • NOT VISUAL APPROVAL • NOT HUMAN PLAYTEST";

        [MenuItem("Desert RV/Diagnostics/Replay input and capture evidence")]
        public static void Launch()
        {
            if (!Application.isPlaying) throw new InvalidOperationException("Enter PlayMode with the saved JourneyBootstrap first. This command never authors or approves scenes.");
            string path = Environment.GetEnvironmentVariable("DESERTRV_INPUT_PLAN");
            string directory = Environment.GetEnvironmentVariable("DESERTRV_EVIDENCE_DIR");
            if (string.IsNullOrWhiteSpace(path) || string.IsNullOrWhiteSpace(directory))
                throw new InvalidOperationException("Set DESERTRV_INPUT_PLAN and DESERTRV_EVIDENCE_DIR to explicit paths.");
            StartCapture(path, directory);
        }
        // Entry for a future Editor PlayMode UnityTest; the test must wait for Stopped and inspect evidence.
        public static JourneyInputEvidence StartCapture(string path, string directory)
        {
            if (!Application.isPlaying) throw new InvalidOperationException("Editor PlayMode required.");
            if (FindObjectsByType<JourneyInputEvidence>(FindObjectsSortMode.None).Length != 0)
                throw new InvalidOperationException("A diagnostic already owns input.");
            var all = FindObjectsByType<JourneyDirector>(FindObjectsSortMode.None);
            if (all.Length != 1 || !all[0].OwnsJourney) throw new InvalidOperationException("One valid JourneyDirector required.");
            var parsed = JsonUtility.FromJson<Plan>(File.ReadAllText(path));
            ValidatePlan(parsed);
            if (Directory.Exists(directory) && Directory.GetFileSystemEntries(directory).Length != 0)
                throw new InvalidOperationException("Evidence directory must be empty; never overwrite an earlier run.");
            Directory.CreateDirectory(directory);
            File.Copy(path, Path.Combine(directory, "input-plan.json"), false);
            var host = new GameObject("Editor input evidence (unapproved diagnostic)");
            DontDestroyOnLoad(host);
            var recorder = host.AddComponent<JourneyInputEvidence>();
            recorder.director = all[0]; recorder.plan = parsed; recorder.output = directory;
            recorder.log = new StreamWriter(Path.Combine(directory, "timeline.jsonl")) { AutoFlush = true };
            recorder.start = Time.realtimeSinceStartupAsDouble;
            recorder.director.journey.Input.AttachEditorReplay(recorder);
            recorder.director.motor.ObstacleContact += recorder.Contact;
            recorder.WriteEvent("begin", Marker);
            return recorder;
        }
        static bool Finite(float f) => !float.IsNaN(f) && !float.IsInfinity(f);
        public static void ValidatePlan(Plan p)
        {
            if (p == null || p.steps == null || p.steps.Length == 0 || !Finite(p.maximumWallSeconds) || p.maximumWallSeconds <= 0)
                throw new ArgumentException("A finite, bounded explicit input plan is required.");
            foreach (var s in p.steps)
            {
                if (s == null || !Finite(s.seconds) || s.seconds <= 0 || s.region < 0 || s.region > 3 ||
                    !Finite(s.moveX) || !Finite(s.moveY) || Mathf.Abs(s.moveX) > 1 || Mathf.Abs(s.moveY) > 1 ||
                    !Finite(s.lookXDegreesPerSecond) || !Finite(s.lookYDegreesPerSecond))
                    throw new ArgumentException("Invalid input step.");
                if (!string.IsNullOrEmpty(s.command) && s.command != "Begin" && s.command != "Pause" && s.command != "Restart" && s.command != "RetryLoad")
                    throw new ArgumentException("Unsupported command; simulation-state commands are forbidden.");
            }
        }
        public int CaptureCount { get; private set; }
        public double LastCaptureWall { get; private set; }
        Vector3 previousPlayer;
        int previousRegion;
        public bool Stopped => stopped;
        public string StopReason { get; private set; }
        void Update()
        {
            if (stopped || log == null) return;
            if (!director || !director.OwnsJourney) { Stop("blocked: director lost"); return; }
            if (Time.timeScale != 1 || Time.captureFramerate != 0) { Stop("blocked: accelerated/fixed capture clock"); return; }
            double now = Time.realtimeSinceStartupAsDouble;
            if (now - start > plan.maximumWallSeconds) { Stop("blocked: wall deadline"); return; }
            bool first = index < 0 || now - stepStart >= plan.steps[index].seconds;
            if (first)
            {
                index++;
                if (index >= plan.steps.Length) { Stop("plan-ended: completion is not implied"); return; }
                stepStart = now;
                WriteEvent("step", plan.steps[index].label);
            }
            var s = plan.steps[index]; var session = director.journey;
            if (!string.IsNullOrEmpty(director.LoadError) && !s.allowLoadError && s.command != "RetryLoad")
            { Stop("blocked: " + director.LoadError); return; }
            if ((s.region != 0 && (director.Region == null || director.Region.region != s.region)) ||
                (!string.IsNullOrEmpty(s.status) && session.State.Status.ToString() != s.status) ||
                (!string.IsNullOrEmpty(s.control) && session.State.Control.ToString() != s.control) ||
                (!string.IsNullOrEmpty(s.promptContains) && !(director.actions.Prompt ?? "").Contains(s.promptContains)))
            { Stop("blocked: step precondition " + s.label); return; }
            if (first)
            {
                switch (s.command)
                {
                    case "Begin": director.Begin(); break;
                    case "Pause": session.TogglePause(); break;
                    case "Restart": director.Restart(); break;
                    case "RetryLoad": director.RetryLoad(); break;
                }
            }
            // Session.Sample already ran at -100; Director consumes at +50. No Tick is called here.
            var input = session.Input.State;
            Push(input, TouchControl.Move, s.moveX != 0 || s.moveY != 0, s.moveX, s.moveY);
            Push(input, TouchControl.Look, s.lookXDegreesPerSecond != 0 || s.lookYDegreesPerSecond != 0,
                s.lookXDegreesPerSecond * Time.deltaTime / 150, s.lookYDegreesPerSecond * Time.deltaTime / 150);
            Push(input, TouchControl.Accelerate, s.accelerate);
            Push(input, TouchControl.Brake, s.brake);
            Push(input, TouchControl.Fire, s.fire);
            Push(input, TouchControl.Interact, first && s.interact);
            Push(input, TouchControl.Reload, first && s.reload);
            session.Input.SetEditorReplayFingers(this, held.Values);
        }
        void Push(TouchInputState input, TouchControl control, bool enabled, float x = 0, float y = 0)
        {
            if (!enabled)
            {
                if (held.TryGetValue(control, out int released)) { input.End(released); held.Remove(control); }
                return;
            }
            if (!held.TryGetValue(control, out int id))
            {
                id = nextPointer++;
                if (!input.Begin(id, control)) { WriteEvent("input-rejected", control.ToString()); return; }
                held.Add(control, id);
            }
            input.Move(id, x, y);
            // One Begin per held control. Context cancellation still requires release before re-press.
        }
        void LateUpdate()
        {
            if (stopped || log == null || !director) return;
            var s = director.journey.State; var b = director.Region; var m = director.motor;
            int threats = 0;
            if (b) foreach (var enemy in b.AllEnemies())
                if (enemy && enemy.gameObject.activeInHierarchy && !enemy.Dead &&
                    enemy.Phase != BeastPhase.Idle && Vector3.Distance(enemy.transform.position, m.PlayerPosition) <= 34) threats++;
            bool moved = b && previousRegion == b.region && Vector3.Distance(previousPlayer, m.PlayerPosition) > .002f;
            bool firing = director.journey.Input.Fire;
            string activity = s.Status != SessionStatus.Playing ? s.Status.ToString() :
                director.actions.Installing ? "physical-installation" : director.actions.Reloading ? "reload" :
                threats > 0 ? (moved || firing ? "threatened-action" : "threatened-stationary") :
                moved ? (s.Control == ControlMode.Driving ? "driving-traversal" : "walking-exploration-candidate") :
                s.PowerConnected && director.Encounter != null && director.Encounter.AliveCount == 0 ? "empty-powered-wait" : "stationary-no-action";
            previousPlayer = m.PlayerPosition; previousRegion = b ? b.region : 0;
            log.WriteLine(JsonUtility.ToJson(new Sample {
                screenWidth = Screen.width, screenHeight = Screen.height,
                activityEvidence = activity, nearbyLiveThreats = threats, currentWave = director.Encounter?.CurrentWave ?? 0,
                completedWaves = director.Encounter?.CompletedWaves ?? 0, waveAlive = director.Encounter?.AliveCount ?? 0, waveCharge = director.Encounter?.ChargeProgress ?? 0,
                label = Marker, utc = DateTime.UtcNow.ToString("O"), frame = Time.frameCount, step = index,
                wall = Time.realtimeSinceStartupAsDouble - start, gameTime = Time.timeAsDouble, dt = Time.deltaTime,
                region = b ? b.region : 0, generation = s.Generation, status = s.Status.ToString(), control = s.Control.ToString(),
                playerHealth = s.PlayerHealth, vehicleHealth = s.VehicleHealth, loaded = s.LoadedAmmo, reserve = s.ReserveAmmo,
                upgrades = (int)s.Upgrades, stormTime = s.StormElapsedSeconds, stormFront = s.StormFrontProgress,
                progress = director.WorldProgress, player = m.PlayerPosition, vehicle = m.vehicle.position, speed = m.Speed,
                cabin = m.InsideCabin, installing = director.actions.Installing, reloading = director.actions.Reloading,
                power = s.PowerConnected, gate = s.GateOpen, objectives = s.ObjectivesResolved,
                ramPart = s.HasPart(ComponentPart.RamPart), coil = s.HasPart(ComponentPart.Coil),
                environmentVerified = b && b.environmentVerified, combatAssetsVerified = b && b.combatAssetsVerified,
                safety = b && b.VehicleInsideSafety(m), prompt = director.actions.Prompt, loadError = director.LoadError
            }));
            if (!capturePending && Time.realtimeSinceStartupAsDouble >= nextCapture)
            { nextCapture = Time.realtimeSinceStartupAsDouble + 1; capture = StartCoroutine(CaptureFrame()); }
        }
        IEnumerator CaptureFrame()
        {
            capturePending = true;
            yield return new WaitForEndOfFrame();
            if (stopped) { capturePending = false; yield break; }
            string name = "frame-" + Time.frameCount.ToString("D8") + ".png";
            Texture2D texture = null;
            try
            {
                texture = ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(output, name), texture.EncodeToPNG());
                WriteEvent("capture", name); CaptureCount++; LastCaptureWall = Time.realtimeSinceStartupAsDouble;
            }
            catch (Exception error) { Stop("blocked: screenshot capture: " + error.Message); }
            finally { if (texture) Destroy(texture); }
            capturePending = false;
        }
        void Contact(RaycastHit hit, float speed)
        {
            WriteEvent(hit.collider == director.Region?.ramGate ? "ram-gate-contact" : "obstacle-contact",
                "speed=" + speed.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
        }
        void OnGUI()
        {
            GUI.color = Color.yellow;
            GUI.Label(new Rect(8, 8, Screen.width - 16, 30), Marker);
        }
        void WriteEvent(string kind, string detail)
        {
            log?.WriteLine(JsonUtility.ToJson(new Event { kind = kind, detail = detail, frame = Time.frameCount,
                wall = Time.realtimeSinceStartupAsDouble - start }));
        }
        public void Stop(string reason)
        {
            if (stopped) return;
            stopped = true; StopReason = reason;
            WriteEvent("stop", reason);
            if (director) { director.journey.Input.DetachEditorReplay(this); held.Clear(); director.motor.ObstacleContact -= Contact; }
            if (capture != null) StopCoroutine(capture);
            log?.Dispose(); log = null;
        }
        void OnDestroy() => Stop("interrupted: recorder destroyed");
        void OnDisable() { if (log != null) Stop("interrupted: recorder disabled"); }
    }
}
#endif
