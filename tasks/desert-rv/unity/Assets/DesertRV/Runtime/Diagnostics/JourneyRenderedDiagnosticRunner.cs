#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace DesertRV.Editor
{
    [InitializeOnLoad]
    public static class JourneyRenderedDiagnosticRunner
    {
        public const string Entry = "DesertRV.Editor.JourneyRenderedCommandLine.Run";
        public const string SmokeEntry = "DesertRV.Editor.JourneyRenderedCommandLine.RunWindowSmoke";
        static string RequestedEntry
        {
            get
            {
                var args = Environment.GetCommandLineArgs(); int count = 0; string method = null;
                for (int i = 0; i < args.Length; i++) if (args[i] == "-executeMethod")
                { count++; method = i + 1 < args.Length ? args[i + 1] : null; }
                return count == 1 && (method == Entry || method == SmokeEntry) ? method : null;
            }
        }
        static bool Smoke => RequestedEntry == SmokeEntry;
        static JourneyWindowSmokeEvidence smokeRecorder;
        [Serializable] sealed class CaptureRequest { public string title; public int pid; }
        [Serializable] sealed class CaptureReady { public string title, windowId; public int pid; public bool valid; }
        static JourneyInputEvidence recorder;
        static EditorWindow captureView;
        static string captureTitle, handshake;
        static int pid;
        static double started, deadline;
        static bool running, waitingForVideo;
        static JourneyRenderedDiagnosticRunner()
        {
            EditorApplication.playModeStateChanged += OnPlayMode;
            EditorApplication.update += Poll;
        }
        static bool ExplicitInvocation => RequestedEntry != null;
        static string Required(string name)
        {
            string value = Environment.GetEnvironmentVariable(name);
            if (string.IsNullOrWhiteSpace(value)) throw new InvalidOperationException("Missing explicit " + name);
            return value;
        }
        static void MarkPhase(string phase)
        {
            string directory = Environment.GetEnvironmentVariable("DESERTRV_PROGRESS_DIR");
            if (string.IsNullOrWhiteSpace(directory)) return;
            if (!Directory.Exists(directory)) throw new InvalidOperationException("Diagnostic progress directory unavailable.");
            string marker = Path.Combine(directory, phase);
            if (File.Exists(marker)) return;
            File.WriteAllText(marker + ".tmp", "1"); File.Move(marker + ".tmp", marker);
        }
        public static void RunWindowSmoke() => Run();
        public static void Run()
        {
            MarkPhase("executeMethod-entered");
            if (!ExplicitInvocation || Application.isBatchMode || SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
                throw new InvalidOperationException("Use explicit rendered non-batch Editor under Xvfb.");
            if (!Smoke) { Required("DESERTRV_DIAGNOSTIC_SCOPE"); Required("DESERTRV_INPUT_PLAN"); }
            Required("DESERTRV_EVIDENCE_DIR"); Required("DESERTRV_CAPTURE_HANDSHAKE_DIR");
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Start from EditMode.");
            for (int i = 0; i < UnityEngine.SceneManagement.SceneManager.sceneCount; i++)
                if (UnityEngine.SceneManagement.SceneManager.GetSceneAt(i).isDirty) throw new InvalidOperationException("Refusing to discard scene edits.");
            EditorSceneManager.OpenScene(Smoke ? JourneyWindowSmokeEvidence.ScenePath : JourneyDiagnosticScope.Scenes[0], OpenSceneMode.Single);
            EditorApplication.EnterPlaymode();
        }
        static void OnPlayMode(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode || !ExplicitInvocation) return;
            try
            {
                MarkPhase("playmode-entered");
                if (Application.isBatchMode || SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
                    throw new InvalidOperationException("Rendered Editor required.");
                if (!Smoke) JourneyDiagnosticScope.Open(Required("DESERTRV_DIAGNOSTIC_SCOPE"));
                // A new floating GameView owns a separate native window; never record the main Editor desktop.
                var type = typeof(EditorWindow).Assembly.GetType("UnityEditor.GameView", true);
                captureView = ScriptableObject.CreateInstance(type) as EditorWindow;
                if (!captureView) throw new InvalidOperationException("Could not create dedicated GameView.");
                captureTitle = "DESERTRV_GAME_" + Guid.NewGuid().ToString("N");
                captureView.titleContent = new GUIContent(captureTitle);
                captureView.position = new Rect(20, 40, 1280, 760);
                captureView.ShowUtility(); captureView.Focus();
                MarkPhase("view-created");
                pid = System.Diagnostics.Process.GetCurrentProcess().Id;
                handshake = Required("DESERTRV_CAPTURE_HANDSHAKE_DIR");
                if (!Directory.Exists(handshake) || Directory.GetFileSystemEntries(handshake).Length != 0)
                    throw new InvalidOperationException("Fresh existing capture-handshake directory required.");
                string request = Path.Combine(handshake, "request.json");
                File.WriteAllText(request + ".tmp", JsonUtility.ToJson(new CaptureRequest { title = captureTitle, pid = pid }));
                File.Move(request + ".tmp", request);
                started = EditorApplication.timeSinceStartup; deadline = 30;
                waitingForVideo = running = true; Application.logMessageReceived += OnLog;
            }
            catch (Exception error) { Debug.LogException(error); Finish(2); }
        }
        static void BeginAfterVideoReady()
        {
            if (Smoke)
            {
                smokeRecorder = JourneyWindowSmokeEvidence.StartCapture(Required("DESERTRV_EVIDENCE_DIR"));
                waitingForVideo = false; started = EditorApplication.timeSinceStartup; deadline = 45; return;
            }
            string path = Required("DESERTRV_INPUT_PLAN");
            var plan = JsonUtility.FromJson<JourneyInputEvidence.Plan>(File.ReadAllText(path));
            JourneyInputEvidence.ValidatePlan(plan);
            recorder = JourneyInputEvidence.StartCapture(path, Required("DESERTRV_EVIDENCE_DIR"));
            File.Copy(Required("DESERTRV_DIAGNOSTIC_SCOPE"), Path.Combine(Required("DESERTRV_EVIDENCE_DIR"), "diagnostic-scope.json"), false);
            waitingForVideo = false; started = EditorApplication.timeSinceStartup; deadline = plan.maximumWallSeconds + 30;
        }
        static void OnLog(string message, string trace, LogType type)
        {
            if (running && (type == LogType.Error || type == LogType.Exception || type == LogType.Assert))
            { recorder?.Stop("blocked: runtime error"); smokeRecorder?.Stop("blocked: runtime error"); if (waitingForVideo) Finish(2); }
        }
        static void Poll()
        {
            if (!running) return;
            try
            {
                if (!captureView || EditorWindow.focusedWindow != captureView || captureView.GetType().FullName != "UnityEditor.GameView" || captureView.titleContent.text != captureTitle)
                    throw new InvalidOperationException("Dedicated GameView identity changed.");
                if (File.Exists(Path.Combine(handshake, "invalid.json"))) throw new InvalidOperationException("Capture identity failed.");
                if (EditorApplication.timeSinceStartup - started > deadline) throw new InvalidOperationException("Render/capture watchdog.");
                if (waitingForVideo)
                {
                    string readyPath = Path.Combine(handshake, "ready.json");
                    if (!File.Exists(readyPath)) return;
                    var ready = JsonUtility.FromJson<CaptureReady>(File.ReadAllText(readyPath));
                    if (ready == null || !ready.valid || ready.pid != pid || ready.title != captureTitle || string.IsNullOrWhiteSpace(ready.windowId))
                        throw new InvalidOperationException("Capture handshake identity mismatch.");
                    // The capture worker publishes ready only after ffmpeg reports at least one actual video frame.
                    BeginAfterVideoReady();
                }
                string heartbeat = Path.Combine(handshake, "heartbeat.json");
                if (!File.Exists(heartbeat) || (DateTime.UtcNow - File.GetLastWriteTimeUtc(heartbeat)).TotalSeconds > 3)
                    throw new InvalidOperationException("Window identity monitoring stopped.");
                if (Screen.width < Screen.height) throw new InvalidOperationException("GameView is not landscape.");
                if (Smoke)
                {
                    if (!smokeRecorder) throw new InvalidOperationException("Smoke recorder lost.");
                    if (EditorApplication.timeSinceStartup - started > 10 &&
                        (smokeRecorder.CaptureCount == 0 || Time.realtimeSinceStartupAsDouble - smokeRecorder.LastCaptureWall > 5))
                        throw new InvalidOperationException("Smoke PNG heartbeat missing.");
                    if (smokeRecorder.Stopped)
                    {
                        if (smokeRecorder.StopReason == "window-smoke-ended") MarkPhase("duration-complete");
                        Finish(smokeRecorder.StopReason == "window-smoke-ended" ? 0 : 1);
                    }
                    return;
                }
                if (!recorder) throw new InvalidOperationException("Recorder lost.");
                if (EditorApplication.timeSinceStartup - started > 10 &&
                    (recorder.CaptureCount == 0 || Time.realtimeSinceStartupAsDouble - recorder.LastCaptureWall > 5))
                    throw new InvalidOperationException("End-of-frame PNG heartbeat missing.");
                if (recorder.Stopped)
                {
                    if (recorder.StopReason.StartsWith("plan-ended", StringComparison.Ordinal)) MarkPhase("duration-complete");
                    Finish(recorder.StopReason.StartsWith("plan-ended", StringComparison.Ordinal) ? 0 : 1);
                }
            }
            catch (Exception) { recorder?.Stop("blocked: verified-game-window capture unavailable"); smokeRecorder?.Stop("blocked: verified-game-window capture unavailable"); Finish(3); }
        }
        static void Finish(int code)
        {
            running = waitingForVideo = false; Application.logMessageReceived -= OnLog;
            if (!string.IsNullOrEmpty(handshake) && Directory.Exists(handshake))
            {
                string stop = Path.Combine(handshake, "stop.json");
                File.WriteAllText(stop + ".tmp", "{\"editorExitCode\":" + code + "}");
                if (!File.Exists(stop)) File.Move(stop + ".tmp", stop); else File.Delete(stop + ".tmp");
            }
            if (!Smoke) JourneyDiagnosticScope.Close();
            // Keep the GameView alive until ffmpeg has stopped; process exit is deferred to acknowledgment.
            if (!string.IsNullOrEmpty(handshake) && File.Exists(Path.Combine(handshake, "ready.json")))
            {
                double until = EditorApplication.timeSinceStartup + 10;
                EditorApplication.CallbackFunction exit = null;
                exit = () => {
                    if (!File.Exists(Path.Combine(handshake, "stopped.json")) && EditorApplication.timeSinceStartup < until) return;
                    EditorApplication.update -= exit; EditorApplication.Exit(code);
                };
                EditorApplication.update += exit;
            }
            else EditorApplication.Exit(code);
        }
    }
}
#endif

