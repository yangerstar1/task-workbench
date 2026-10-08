using System;
using System.Collections;
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
        IEnumerator LoadRoutine(JourneySession session, JourneySession.LoadTicket ticket, Func<RegionBinding, bool> ready, Action<string> failed)
        {
            Busy = true;
            string name = ticket.Scene >= 1 && ticket.Scene <= regionScenes.Length ? regionScenes[ticket.Scene - 1] : null;
            if (string.IsNullOrWhiteSpace(name) || !Application.CanStreamedLevelBeLoaded(name))
            { Busy = false; failed("地区未列入构建或场景缺失；可以重试。 "); yield break; }
            // Unload even when restarting the same scene; GetSceneByName must never select
            // a stale duplicate. Failure leaves the persistent journey safely Loading.
            if (activeEnvironment.IsValid())
            { yield return SceneManager.UnloadSceneAsync(activeEnvironment); activeEnvironment = default; }
            AsyncOperation op = null; string loadError = null;
            try { op = SceneManager.LoadSceneAsync(name, LoadSceneMode.Additive); }
            catch (Exception e) { loadError = e.Message; }
            if (op == null) { Busy = false; failed("地区加载失败：" + (loadError ?? "加载器未返回操作。")); yield break; }
            yield return op;
            var scene = SceneManager.GetSceneByName(name);
            RegionBinding binding = null; int bindings = 0; bool duplicateJourney = false;
            if (scene.IsValid()) foreach (var root in scene.GetRootGameObjects())
            {
                if (root.GetComponentInChildren<JourneySession>(true) || root.GetComponentInChildren<JourneyMotor>(true)) duplicateJourney = true;
                foreach (var candidate in root.GetComponentsInChildren<RegionBinding>(true)) { binding = candidate; bindings++; }
            }
            string reason = "地区必须具有唯一且匹配的 RegionBinding。";
            if (!session.IsCurrentLoad(ticket) || duplicateJourney || bindings != 1 || binding.region != ticket.Scene || !binding.Validate(out reason))
            {
                if (scene.IsValid()) yield return SceneManager.UnloadSceneAsync(scene);
                Busy = false;
                if (session.IsCurrentLoad(ticket)) failed(reason ?? "地区加载回调已失效。");
                yield break;
            }
            var previous = activeEnvironment;
            activeEnvironment = scene;
            bool accepted = false; string callbackError = null;
            try { accepted = ready(binding); }
            catch (Exception e) { callbackError = e.Message; }
            if (!accepted)
            {
                yield return SceneManager.UnloadSceneAsync(scene); activeEnvironment = default;
                Busy = false; failed(callbackError == null ? "地区出生坐标或持久对象绑定无效；仍可重试原加载。" : "地区接线失败：" + callbackError); yield break;
            }
            if (previous.IsValid() && previous != scene) yield return SceneManager.UnloadSceneAsync(previous);
            Busy = false;
        }
    }
}
