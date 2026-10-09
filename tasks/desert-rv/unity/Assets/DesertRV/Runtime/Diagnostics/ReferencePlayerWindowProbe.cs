#if DESERTRV_REFERENCE_WINDOW_PROBE && !UNITY_EDITOR
using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;
namespace DesertRV
{
    // Compiled only by BuildLinuxWindowSmoke extraScriptingDefines. No gameplay state/input writes.
    public sealed class ReferencePlayerWindowProbe : MonoBehaviour
    {
        [Serializable] sealed class Request { public int pid; public string scene = "BodyStudy"; }
        [Serializable] sealed class Beat { public int frame; public double wall; public bool focused; }
        string directory;
        readonly Stopwatch elapsed = new Stopwatch();
        static void Write(string path, string text) { File.WriteAllText(path + ".tmp", text); File.Move(path + ".tmp", path, true); }
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartProbe()
        {
            if (SceneManager.GetActiveScene().name != "BodyStudy") { Application.Quit(2); return; }
            var folder = Environment.GetEnvironmentVariable("DESERTRV_PLAYER_HANDSHAKE");
            if (string.IsNullOrEmpty(folder) || !Directory.Exists(folder)) { Application.Quit(2); return; }
            var probe = new GameObject("CandidateOnlyReferenceWindowProbe").AddComponent<ReferencePlayerWindowProbe>();
            probe.directory = folder;
            probe.StartCoroutine(probe.Observe());
        }
        IEnumerator Observe()
        {
            elapsed.Start();
            Write(Path.Combine(directory, "request.json"), JsonUtility.ToJson(new Request { pid = Process.GetCurrentProcess().Id }));
            double begin = -1, shotAt = 0; int shots = 0;
            while (elapsed.Elapsed.TotalSeconds < 90)
            {
                yield return new WaitForEndOfFrame();
                double now = elapsed.Elapsed.TotalSeconds;
                Write(Path.Combine(directory, "frame.json"), JsonUtility.ToJson(new Beat { frame = Time.frameCount, wall = now, focused = Application.isFocused }));
                if (File.Exists(Path.Combine(directory, "ready.json")) && begin < 0) begin = now;
                if (begin < 0) continue;
                if (!Application.isFocused) { Application.Quit(3); yield break; }
                if (shots < 3 && now - begin >= shotAt)
                {
                    var image = new Texture2D(Screen.width, Screen.height, TextureFormat.RGB24, false);
                    image.ReadPixels(new Rect(0, 0, Screen.width, Screen.height), 0, 0); image.Apply();
                    File.WriteAllBytes(Path.Combine(directory, "frame-" + shots + ".png"), image.EncodeToPNG());
                    Destroy(image); shots++; shotAt += 5;
                }
                if (now - begin >= 15)
                {
                    Write(Path.Combine(directory, "duration-complete.json"), "{\"seconds\":15,\"screenshots\":3}");
                    while (!File.Exists(Path.Combine(directory, "stopped.json")) && elapsed.Elapsed.TotalSeconds < 90)
                    { yield return new WaitForEndOfFrame(); Write(Path.Combine(directory, "frame.json"), JsonUtility.ToJson(new Beat { frame = Time.frameCount, wall = elapsed.Elapsed.TotalSeconds, focused = Application.isFocused })); }
                    Application.Quit(File.Exists(Path.Combine(directory, "stopped.json")) ? 0 : 4); yield break;
                }
            }
            Application.Quit(5);
        }
    }
}
#endif
