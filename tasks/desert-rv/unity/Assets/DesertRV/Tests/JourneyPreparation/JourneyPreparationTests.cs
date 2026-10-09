using System;
using System.Linq;
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
        [Test] public void PrepareVerifiedSameWorkspaceJourney()
        {
            // Actual native success and injected-failure cleanup, inside the existing single-case gate.
            VerifyFxPreviewLifecycle(false); VerifyFxPreviewLifecycle(true);
            Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor", true)
                .GetMethod("PrepareVerifiedSameWorkspace").Invoke(null, null);
        }
    }
}
