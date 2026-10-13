using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;

namespace Lottery.G3.VisualCandidate.Tests
{
    // Fixed diagnostic breadcrumbs, active only for the dedicated capture assembly.
    // No scene, game state, log text, device identifier, or environment is exported.
    internal static class VisualCandidateLifecycleProbe
    {
        const string Scope = "DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS";
        const string AssemblyName = "Lottery.G3.VisualCandidate.Tests";
        const int MaximumBytes = 65536, MaximumEvents = 128;
        static readonly string[] Stages = {
            "editor-exiting-edit-mode", "runtime-before-scene-load",
            "runtime-after-scene-load", "editor-entered-play-mode"
        };
        static string PathName => Path.GetFullPath(Path.Combine(Application.dataPath,
            "../../artifacts/visual-candidate/lifecycle-progress.json"));
        static string Arg(string name)
        {
            var args = Environment.GetCommandLineArgs(); int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : "";
        }
        static bool IsCaptureProcess() => Arg("-assemblyNames") == AssemblyName;
        public static void Arm()
        {
#if UNITY_EDITOR
            if(!IsCaptureProcess()) throw new InvalidOperationException("Lifecycle probe needs the dedicated capture assembly");
            RequireIdentity();
            VisualCandidateStartupProbe.Arm();
            Directory.CreateDirectory(Path.GetDirectoryName(PathName));
            // Only this probe's own fixed output, never project/source/store files.
            if(File.Exists(PathName)) File.Delete(PathName);
            RegisterEditorCallback();
#endif
        }
#if UNITY_EDITOR
        [UnityEditor.InitializeOnLoadMethod]
        static void RegisterEditorCallback()
        {
            if(!IsCaptureProcess()) return;
            UnityEditor.EditorApplication.playModeStateChanged -= OnPlayModeState;
            UnityEditor.EditorApplication.playModeStateChanged += OnPlayModeState;
        }
        static void OnPlayModeState(UnityEditor.PlayModeStateChange state)
        {
            if(state == UnityEditor.PlayModeStateChange.ExitingEditMode) Mark(Stages[0], true);
            else if(state == UnityEditor.PlayModeStateChange.EnteredPlayMode) Mark(Stages[3], false);
        }
#endif
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void BeforeSceneLoad() => Mark(Stages[1], false);
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AfterSceneLoad() => Mark(Stages[2], false);
        static void RequireIdentity()
        {
            if(!Regex.IsMatch(Arg("-probeCommit"), "^[0-9a-f]{40}$") ||
                !Regex.IsMatch(Arg("-probeRunId"), "^[1-9][0-9]*$") ||
                !Regex.IsMatch(Arg("-probeRunAttempt"), "^[1-9][0-9]*$"))
                throw new InvalidOperationException("Lifecycle diagnostic identity missing");
        }
        static void Mark(string stage, bool first)
        {
            if(!IsCaptureProcess()) return;
            try
            {
                RequireIdentity();
                Receipt receipt;
                var events = new List<Event>();
                if(first)
                {
                    if(File.Exists(PathName)) throw new InvalidOperationException("Lifecycle first event already exists");
                    receipt = new Receipt { sourceCommit = Arg("-probeCommit"), runId = Arg("-probeRunId"), runAttempt = Arg("-probeRunAttempt") };
                }
                else
                {
                    if(!File.Exists(PathName) || new FileInfo(PathName).Length > MaximumBytes)
                        throw new InvalidOperationException("Lifecycle first event missing or oversized");
                    receipt = JsonUtility.FromJson<Receipt>(File.ReadAllText(PathName));
                    if(receipt == null || receipt.schemaVersion != 1 || receipt.kind != "lifecycle" || receipt.scope != Scope ||
                        receipt.status != "MILESTONES_ONLY_NOT_TEST_PASS" || receipt.sourceCommit != Arg("-probeCommit") ||
                        receipt.runId != Arg("-probeRunId") || receipt.runAttempt != Arg("-probeRunAttempt") ||
                        receipt.events == null || receipt.events.Length == 0 || receipt.events[0].stage != Stages[0])
                        throw new InvalidOperationException("Lifecycle prior identity/schema mismatch");
                    events.AddRange(receipt.events);
                }
                if(events.Count >= MaximumEvents || !Stages.Contains(stage) || events.Any(e => e.stage == stage))
                    throw new InvalidOperationException("Lifecycle stage/event bound mismatch");
                var now = DateTime.UtcNow;
                long elapsed = events.Count == 0 ? 0 : Math.Max(events[events.Count - 1].elapsedMs,
                    Math.Max(0, (long)(now - DateTime.Parse(events[0].utc, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind)).TotalMilliseconds));
                events.Add(new Event { stage = stage, utc = now.ToString("O"), elapsedMs = elapsed });
                receipt.events = events.ToArray();
                var json = JsonUtility.ToJson(receipt, true);
                if(System.Text.Encoding.UTF8.GetByteCount(json) > MaximumBytes)
                    throw new InvalidOperationException("Lifecycle receipt exceeds bound");
                File.WriteAllText(PathName, json);
                Debug.Log("VISUAL_CANDIDATE_LIFECYCLE " + stage);
            }
            catch
            {
                // A missing breadcrumb is never fabricated into a successful stage.
                // Keep the failure fixed-text rather than dumping exception/log data.
                Debug.LogError("VISUAL_CANDIDATE_LIFECYCLE_WRITE_FAILED");
            }
        }
        [Serializable] sealed class Event
        {
            public string stage, utc, dayPhase = "UNAVAILABLE";
            public long elapsedMs;
            public int inputUpdates = 0, frameCount = 0, purchased = -1, settled = -1;
        }
        [Serializable] sealed class Receipt
        {
            public int schemaVersion = 1;
            public string scope = Scope, kind = "lifecycle", sourceCommit, runId, runAttempt;
            public string status = "MILESTONES_ONLY_NOT_TEST_PASS";
            public Event[] events;
        }
    }
}
