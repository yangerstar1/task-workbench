using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV
{
    // Scene names are explicit build-settings entries; a failed attempt retains its ticket.
    public sealed class RegionLoader : MonoBehaviour
    {
        public string[] regionScenes = new string[3];
        public bool Busy { get; private set; }
        Scene activeEnvironment;
        public void Load(JourneySession session, JourneySession.LoadTicket ticket, Func<RegionBinding, bool> ready, Action<string> failed)
        {
            if (Busy || !session.IsCurrentLoad(ticket)) return;
            StartCoroutine(LoadRoutine(session, ticket, ready, failed));
        }
        // Exposed internally for an actual unloaded-scene regression, not a success override.
        internal static bool TryActivate(Scene scene, out string error)
        {
            error = null;
            if (!scene.IsValid() || !scene.isLoaded) { error = "地区场景无效或尚未加载。"; return false; }
            try
            {
                if (SceneManager.SetActiveScene(scene)) return true;
                error = "无法将地区设为活动场景。";
            }
            catch (Exception e) { error = "地区激活失败：" + e.Message; }
            return false;
        }
        static bool ValidateForLoad(RegionBinding binding, out string reason)
        {
#if UNITY_EDITOR
            if (Editor.JourneyDiagnosticScope.Active)
                return Editor.JourneyDiagnosticScope.ValidateRegion(binding, out reason);
#endif
#if DESERTRV_CANDIDATE_LINUX && UNITY_STANDALONE_LINUX && DEVELOPMENT_BUILD && !UNITY_EDITOR
            return JourneyCandidateLinuxIdentity.ValidateForLoad(binding, out reason);
#else
            return binding.Validate(out reason);
#endif
        }
        static void RestoreActive(Scene rejected, Scene previous)
        {
            // Do not overwrite another owner's newer active scene.
            if (SceneManager.GetActiveScene() == rejected && previous.IsValid() && previous.isLoaded)
                TryActivate(previous, out _);
        }
        IEnumerator LoadRoutine(JourneySession session, JourneySession.LoadTicket ticket, Func<RegionBinding, bool> ready, Action<string> failed)
        {
            Busy = true;
            string name = ticket.Scene >= 1 && ticket.Scene <= regionScenes.Length ? regionScenes[ticket.Scene - 1] : null;
            if (string.IsNullOrWhiteSpace(name) || !Application.CanStreamedLevelBeLoaded(name))
            { Busy = false; failed("地区未列入构建或场景缺失；可以重试。 "); yield break; }
            var previousActive = SceneManager.GetActiveScene();
            var previousEnvironment = activeEnvironment;
            var existingHandles = new HashSet<int>();
            for (int i = 0; i < SceneManager.sceneCount; i++) existingHandles.Add(SceneManager.GetSceneAt(i).handle);
            AsyncOperation op = null; string loadError = null;
            try { op = SceneManager.LoadSceneAsync(name, LoadSceneMode.Additive); }
            catch (Exception e) { loadError = e.Message; }
            if (op == null) { Busy = false; failed("地区加载失败：" + (loadError ?? "加载器未返回操作。")); yield break; }
            yield return op;
            // Same-name whole-run restarts may coexist briefly: identify this load's new handle.
            Scene scene = default;
            for (int i = 0; i < SceneManager.sceneCount; i++)
            {
                var candidate = SceneManager.GetSceneAt(i);
                if (!existingHandles.Contains(candidate.handle) && (candidate.name == name || candidate.path == name)) { scene = candidate; break; }
            }
            RegionBinding binding = null; int bindings = 0; bool duplicateJourney = false;
            if (scene.IsValid() && scene.isLoaded) foreach (var root in scene.GetRootGameObjects())
            {
                if (root.GetComponentInChildren<JourneySession>(true) || root.GetComponentInChildren<JourneyMotor>(true)) duplicateJourney = true;
                foreach (var candidate in root.GetComponentsInChildren<RegionBinding>(true)) { binding = candidate; bindings++; }
            }
            string reason = "地区必须具有唯一且匹配的 RegionBinding。";
            if (!session.IsCurrentLoad(ticket) || !scene.IsValid() || !scene.isLoaded || duplicateJourney || bindings != 1 || binding.region != ticket.Scene || !ValidateForLoad(binding, out reason))
            {
                if (scene.IsValid() && scene.isLoaded) yield return SceneManager.UnloadSceneAsync(scene);
                Busy = false;
                if (session.IsCurrentLoad(ticket)) failed(reason ?? "地区加载回调已失效。");
                yield break;
            }
            // No yield between the ticket check, activation and binding; stale loads never steal
            // the new journey's active scene. Its RenderSettings apply before ready is invoked.
            if (!TryActivate(scene, out reason))
            {
                RestoreActive(scene, previousActive);
                yield return SceneManager.UnloadSceneAsync(scene);
                Busy = false; if (session.IsCurrentLoad(ticket)) failed(reason); yield break;
            }
            var suspended = new List<GameObject>();
            if (previousEnvironment.IsValid() && previousEnvironment.isLoaded)
                foreach (var root in previousEnvironment.GetRootGameObjects())
                    if (root.activeSelf) { suspended.Add(root); root.SetActive(false); }
            bool accepted = false; string callbackError = null;
            try { accepted = ready(binding); }
            catch (Exception e) { callbackError = e.Message; }
            if (!accepted)
            {
                RestoreActive(scene, previousActive);
                foreach (var root in suspended) if (root) root.SetActive(true);
                yield return SceneManager.UnloadSceneAsync(scene);
                Busy = false;
                if (session.IsCurrentLoad(ticket)) failed(callbackError == null ? "地区出生坐标或持久对象绑定无效；仍可重试原加载。" : "地区接线失败：" + callbackError);
                yield break;
            }
            activeEnvironment = scene;
            if (previousEnvironment.IsValid() && previousEnvironment.isLoaded && previousEnvironment != scene)
                yield return SceneManager.UnloadSceneAsync(previousEnvironment);
            Busy = false;
        }
    }
}
