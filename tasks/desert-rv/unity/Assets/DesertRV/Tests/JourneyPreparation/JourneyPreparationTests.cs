using System;
using System.Linq;
using System.IO;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Tests
{
    public sealed class JourneyPreparationTests
    {
        static void VerifyFxPreviewLifecycle(bool fail)
        {
            var editor = Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor", true);
            var method = editor.GetMethod("WithFxPreviewScene", BindingFlags.Static | BindingFlags.NonPublic);
            var create = editor.GetMethod("FxObject", BindingFlags.Static | BindingFlags.NonPublic);
            var original = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            var active = SceneManager.GetActiveScene();
            var roots = original.SelectMany(scene => scene.GetRootGameObjects()).Select(go => go.GetInstanceID()).OrderBy(id => id).ToArray();
            Scene preview = default; GameObject root = null, child = null;
            Action<Scene> author = scene => {
                preview = scene;
                root = (GameObject)create.Invoke(null, new object[] { "FX isolation fixture", scene, null });
                child = (GameObject)create.Invoke(null, new object[] { "FX child fixture", scene, root.transform });
                Assert.AreEqual(scene, root.scene); Assert.AreEqual(scene, child.scene); Assert.AreEqual(root.transform, child.transform.parent);
                if (fail) throw new InvalidOperationException("Injected FX preview authoring failure.");
            };
            if (fail)
            {
                var error = Assert.Throws<TargetInvocationException>(() => method.Invoke(null, new object[] { author }));
                Assert.IsInstanceOf<InvalidOperationException>(error.InnerException);
                Assert.AreEqual("Injected FX preview authoring failure.", error.InnerException.Message);
            }
            else Assert.DoesNotThrow(() => method.Invoke(null, new object[] { author }));
            Assert.IsFalse(preview.IsValid()); Assert.IsFalse(root); Assert.IsFalse(child);
            var after = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            CollectionAssert.AreEqual(original.Select(scene => scene.handle), after.Select(scene => scene.handle));
            CollectionAssert.AreEqual(roots, after.SelectMany(scene => scene.GetRootGameObjects()).Select(go => go.GetInstanceID()).OrderBy(id => id));
            Assert.AreEqual(active, SceneManager.GetActiveScene()); Assert.IsTrue(after.All(scene => !scene.isDirty));
        }
        static void VerifyPoseJsonRoundtrip()
        {
            var editor = Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor", true);
            var requestType = editor.GetNestedType("Request"); var poseType = editor.GetNestedType("Pose");
            var readyType = Type.GetType("DesertRV.Editor.JourneyCandidatePreparation+ReadyInput, Assembly-CSharp-Editor", true);
            var resolve = editor.GetMethod("ResolveArcModulePose", BindingFlags.Static | BindingFlags.NonPublic);
            var shape = editor.GetMethod("NamedPoseShape", BindingFlags.Static | BindingFlags.NonPublic);
            object PoseOf(object request, string name) => requestType.GetField(name).GetValue(request);
            object ParsePose(string json) => JsonUtility.FromJson(json, poseType);
            const string unit = "{\"localPosition\":{\"x\":0.125,\"y\":0.25,\"z\":0.5},\"localRotation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"localScale\":{\"x\":1,\"y\":1,\"z\":1}}";
            var derived = ParsePose(unit); // Isolated method fixture only; never written to a production input/asset.
            var actual = JsonUtility.FromJson(File.ReadAllText("JourneyEvidence/JourneyPreparation/ready-input.json"), readyType);
            var roundtrip = JsonUtility.FromJson(JsonUtility.ToJson(actual), readyType);
            foreach (var ready in new[] { actual, roundtrip })
            {
                var request = readyType.GetField("integration").GetValue(ready);
                string intent = (string)readyType.GetField("arcModulePoseSource").GetValue(ready);
                var selected = PoseOf(request, "arcModulePose");
                Debug.Log("JOURNEY_POSE_JSON_ROUNDTRIP source=" + intent + "; arcNull=" + (selected == null) + "; arc=" + (selected == null ? "null" : JsonUtility.ToJson(selected)));
                var resolved = resolve.Invoke(null, new[] { (object)intent, selected, derived });
                Assert.AreSame(intent == "scene-geometry" ? derived : selected, resolved);
                foreach (string role in new[] { "weaponCameraPose", "flashMuzzlePose" }) shape.Invoke(null, new[] { PoseOf(request, role), role });
            }
            var observedNull = PoseOf(JsonUtility.FromJson("{\"arcModulePose\":null}", requestType), "arcModulePose");
            Assert.AreSame(derived, resolve.Invoke(null, new[] { (object)"scene-geometry", observedNull, derived }));
            var explicitPose = ParsePose(unit);
            Assert.AreSame(explicitPose, resolve.Invoke(null, new[] { (object)"selection", explicitPose, derived }));
            var invalid = ParsePose(unit); poseType.GetField("localScale").SetValue(invalid, Vector3.zero);
            foreach (var args in new[] {
                new[] { (object)"selection", invalid, derived }, new[] { (object)"selection", observedNull, derived },
                new[] { (object)"scene-geometry", explicitPose, derived }, new[] { (object)"scene-geometry", observedNull, invalid },
                new[] { (object)null, observedNull, derived }, new[] { (object)"unknown", observedNull, derived } })
            {
                var error = Assert.Throws<TargetInvocationException>(() => resolve.Invoke(null, args));
                Assert.IsInstanceOf<InvalidOperationException>(error.InnerException);
            }
        }
        [Test] public void PrepareVerifiedSameWorkspaceJourney()
        {
            // Actual native success and injected-failure cleanup, inside the existing single-case gate.
            VerifyFxPreviewLifecycle(false); VerifyFxPreviewLifecycle(true); VerifyPoseJsonRoundtrip();
            Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor", true)
                .GetMethod("PrepareVerifiedSameWorkspace").Invoke(null, null);
        }
    }
}
