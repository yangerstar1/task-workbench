using System;
using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace DesertRV.Tests
{
    public sealed class JourneyLoaderPlayModeTests
    {
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Call(object obj, string name, params object[] args) => obj.GetType().GetMethod(name).Invoke(obj, args);
        [UnityTest] public IEnumerator MissingRegion_RemainsLoadingAndSameTicketCanRetry()
        {
            var go = new GameObject("load retry test");
            var host = go.AddComponent(T("JourneySession"));
            var loader = go.AddComponent(T("RegionLoader"));
            Call(host, "StartJourney");
            var ticket = Call(host, "BeginCurrentRegionLoad");
            var callbackType = typeof(Func<,>).MakeGenericType(T("RegionBinding"), typeof(bool));
            var accept = Delegate.CreateDelegate(callbackType, typeof(JourneyLoaderPlayModeTests).GetMethod("Accept", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic).MakeGenericMethod(T("RegionBinding")));
            int failures = 0;
            Action<string> failed = reason => failures++;
            Call(loader, "Load", host, ticket, accept, failed);
            yield return null;
            Assert.That(failures, Is.EqualTo(1));
            var state = host.GetType().GetProperty("State").GetValue(host);
            Assert.That(state.GetType().GetProperty("Status").GetValue(state).ToString(), Is.EqualTo("Loading"));
            Assert.That(Call(host, "IsCurrentLoad", ticket), Is.True);
            Call(loader, "Load", host, ticket, accept, failed);
            yield return null;
            Assert.That(failures, Is.EqualTo(2));
            Assert.That(state.GetType().GetProperty("SceneId").GetValue(state), Is.EqualTo(1));
            UnityEngine.Object.Destroy(go);
        }
        static bool Accept<TBinding>(TBinding binding) => true;
    }
}
