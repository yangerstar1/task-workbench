#if UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Editor
{
    // Thirty seconds of the existing saved scene only. No input source or Journey state/action API.
    public sealed class JourneyWindowSmokeEvidence : MonoBehaviour
    {
        public const string ScenePath = "Assets/DesertRV/Scenes/BodyStudy.unity";
        const string Label = "WINDOW SMOKE ONLY - NO GAMEPLAY OR VISUAL ACCEPTANCE";
        [Serializable] sealed class Scope { public string mode = "WINDOW_SMOKE_ONLY", sourceCommit, scenePath, sceneSha256, dependencyHash; public bool softwareRendererVerified; }
        [Serializable] sealed class Sample
        {
            public string kind = "sample", mode = "WINDOW_SMOKE_ONLY", status = "RenderingOnly", activityEvidence = "RenderingOnly";
            public int frame, screenWidth, screenHeight;
            public double wall;
        }
        [Serializable] sealed class Event { public string kind, detail; public int frame; public double wall; }
        StreamWriter writer;
        string output;
        double start, nextCapture;
        bool pending;
        public bool Stopped { get; private set; }
        public string StopReason { get; private set; }
        public int CaptureCount { get; private set; }
        public double LastCaptureWall { get; private set; }
        public static JourneyWindowSmokeEvidence StartCapture(string directory)
        {
            if (!Application.isPlaying || Application.isBatchMode || Application.unityVersion != "6000.3.19f1" ||
                SceneManager.GetActiveScene().path != ScenePath ||
                SystemInfo.graphicsDeviceType != UnityEngine.Rendering.GraphicsDeviceType.OpenGLCore ||
                SystemInfo.graphicsDeviceName.IndexOf("llvmpipe", StringComparison.OrdinalIgnoreCase) < 0 ||
                UnityEngine.Object.FindObjectsByType<JourneyDirector>(FindObjectsInactive.Include, FindObjectsSortMode.None).Length != 0)
                throw new InvalidOperationException("Only the saved BodyStudy scene with no journey owner may run the window smoke.");
            if (Directory.Exists(directory) && Directory.GetFileSystemEntries(directory).Length != 0)
                throw new InvalidOperationException("Fresh smoke evidence directory required.");
            Directory.CreateDirectory(directory);
            var source = new Scope { sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA"), scenePath = ScenePath,
                softwareRendererVerified = true, sceneSha256 = JourneyDiagnosticScope.HashFile(ScenePath), dependencyHash = AssetDatabase.GetAssetDependencyHash(ScenePath).ToString() };
            File.WriteAllText(Path.Combine(directory, "window-smoke-scope.json"), JsonUtility.ToJson(source));
            var go = new GameObject("Window smoke evidence only");
            var recorder = go.AddComponent<JourneyWindowSmokeEvidence>(); recorder.output = directory;
            recorder.writer = new StreamWriter(Path.Combine(directory, "timeline.jsonl")) { AutoFlush = true };
            recorder.start = Time.realtimeSinceStartupAsDouble;
            return recorder;
        }
        void Update()
        {
            if (Stopped || writer == null) return;
            if (Time.timeScale != 1 || Time.captureFramerate != 0) { Stop("blocked: altered capture clock"); return; }
            if (Time.realtimeSinceStartupAsDouble - start >= 30) Stop("window-smoke-ended");
        }
        void LateUpdate()
        {
            if (Stopped || writer == null) return;
            writer.WriteLine(JsonUtility.ToJson(new Sample { frame = Time.frameCount, wall = Time.realtimeSinceStartupAsDouble - start,
                screenWidth = Screen.width, screenHeight = Screen.height }));
            if (!pending && Time.realtimeSinceStartupAsDouble >= nextCapture)
            { nextCapture = Time.realtimeSinceStartupAsDouble + 1; StartCoroutine(Capture()); }
        }
        IEnumerator Capture()
        {
            pending = true; yield return new WaitForEndOfFrame();
            if (Stopped) { pending = false; yield break; }
            Texture2D texture = null;
            try
            {
                texture = ScreenCapture.CaptureScreenshotAsTexture();
                string name = "frame-" + Time.frameCount.ToString("D8") + ".png";
                File.WriteAllBytes(Path.Combine(output, name), texture.EncodeToPNG());
                writer.WriteLine(JsonUtility.ToJson(new Event { kind = "capture", detail = name, frame = Time.frameCount, wall = Time.realtimeSinceStartupAsDouble - start }));
                CaptureCount++; LastCaptureWall = Time.realtimeSinceStartupAsDouble;
            }
            catch (Exception) { Stop("blocked: smoke PNG capture"); }
            finally { if (texture) Destroy(texture); pending = false; }
        }
        void OnGUI() { GUI.color = Color.yellow; GUI.Label(new Rect(8, 8, Screen.width - 16, 30), Label); }
        public void Stop(string reason)
        {
            if (Stopped) return; Stopped = true; StopReason = reason;
            writer?.WriteLine(JsonUtility.ToJson(new Event { kind = "stop", detail = reason, frame = Time.frameCount, wall = Time.realtimeSinceStartupAsDouble - start }));
            writer?.Dispose(); writer = null;
        }
        void OnDisable() => Stop("blocked: smoke recorder disabled");
    }
}
#endif
