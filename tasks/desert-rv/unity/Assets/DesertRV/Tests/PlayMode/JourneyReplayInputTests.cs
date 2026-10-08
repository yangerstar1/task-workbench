#if UNITY_EDITOR
using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace DesertRV.Tests
{
    public sealed class JourneyReplayInputTests
    {
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Call(object obj, string name, params object[] args) => obj.GetType().GetMethod(name).Invoke(obj, args);
        static object Get(object obj, string name) => obj.GetType().GetProperty(name).GetValue(obj);
        static object E(string type, string value) => Enum.Parse(T(type), value);
        [UnityTest] public IEnumerator HeldFire_SurvivesAdapterSampleWithoutNewPressedEdge()
        {
            var go = new GameObject("replay ownership test"); var adapter = go.AddComponent(T("MobileInputAdapter"));
            try
            {
                Call(adapter, "Sample"); // Initialize screen/safe-area before pressing.
                Call(adapter, "AttachEditorReplay", go);
                Call(adapter, "SetContext", E("TouchContext", "OnFoot"));
                var state = Get(adapter, "State");
                Assert.That(Call(state, "Begin", 41001, E("TouchControl", "Fire")), Is.True);
                Call(state, "Begin", 41003, E("TouchControl", "Move")); Call(state, "Move", 41003, .8f, .3f);
                Call(adapter, "SetEditorReplayFingers", go, new[] { 41001, 41003 });
                Call(adapter, "ConsumeFrame");
                Call(adapter, "Sample");
                Assert.That(Get(state, "FireHeld"), Is.True);
                Assert.That(Get(state, "FirePressed"), Is.False, "Holding is not a new button-down each frame.");
                Assert.That(Get(state, "MoveX"), Is.EqualTo(.8f).Within(.0001));
                Assert.That(Get(state, "MoveY"), Is.EqualTo(.3f).Within(.0001));
                Call(state, "End", 41003);
                Call(state, "End", 41001); Call(adapter, "SetEditorReplayFingers", go, Array.Empty<int>());
                Call(adapter, "Sample"); Assert.That(Get(state, "FireHeld"), Is.False);
                Call(adapter, "DetachEditorReplay", go);
                Assert.That(Get(adapter, "EditorReplayActive"), Is.False);
            }
            finally { UnityEngine.Object.Destroy(go); }
            yield return null;
        }
        [UnityTest] public IEnumerator ContextCancellation_HeldReplayRequiresLiftBeforeRepress()
        {
            var go = new GameObject("replay cancellation test"); var adapter = go.AddComponent(T("MobileInputAdapter"));
            try
            {
                Call(adapter, "Sample"); Call(adapter, "AttachEditorReplay", go);
                Call(adapter, "SetContext", E("TouchContext", "OnFoot")); var state = Get(adapter, "State");
                Call(state, "Begin", 41002, E("TouchControl", "Fire"));
                Call(adapter, "SetEditorReplayFingers", go, new[] { 41002 });
                Call(adapter, "SetContext", E("TouchContext", "Overlay"));
                Call(adapter, "SetContext", E("TouchContext", "OnFoot")); Call(adapter, "Sample");
                Assert.That(Get(state, "FireHeld"), Is.False);
                Assert.That(Call(state, "Begin", 41002, E("TouchControl", "Fire")), Is.False);
                Call(state, "End", 41002); Call(adapter, "SetEditorReplayFingers", go, Array.Empty<int>()); Call(adapter, "Sample");
                Assert.That(Call(state, "Begin", 41002, E("TouchControl", "Fire")), Is.True);
                Call(adapter, "DetachEditorReplay", go);
            }
            finally { UnityEngine.Object.Destroy(go); }
            yield return null;
        }
        [UnityTest] public IEnumerator ScopeRequestHashChange_InvalidatesAndCloseClearsCapability()
        {
            // Deliberately corrupt only the diagnostic capability fixture, never gameplay state.
            var type = T("Editor.JourneyDiagnosticScope");
            string path = System.IO.Path.Combine(Application.temporaryCachePath, "diagnostic-scope-" + Guid.NewGuid() + ".json");
            try
            {
                System.IO.File.WriteAllText(path, "changed request");
                type.GetField("request", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, Activator.CreateInstance(type.GetNestedType("Request")));
                type.GetField("requestPath", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, path);
                type.GetField("requestHash", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, new string('0', 64));
                object[] args = { null };
                LogAssert.Expect(LogType.Error, "EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT INVALIDATED: Diagnostic lifetime or request hash changed.");
                Assert.That(type.GetMethod("ValidateCurrent").Invoke(null, args), Is.False);
                Assert.That(type.GetProperty("InvalidReason").GetValue(null), Is.Not.Null);
            }
            finally
            {
                type.GetMethod("Close").Invoke(null, null);
                if (System.IO.File.Exists(path)) System.IO.File.Delete(path);
            }
            Assert.That(type.GetProperty("Active").GetValue(null), Is.False);
            yield return null;
        }
    }
}
#endif
