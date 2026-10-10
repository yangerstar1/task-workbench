using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace DesertRV.Tests
{
    // Run in Unity after importing this candidate. Host source checks cannot execute these tests.
    public sealed class JourneyTracerMaterialTests
    {
        const string MaterialPath = "Assets/DesertRV/Art/Materials/JourneyNailTrajectory.mat";
        const string ShaderPath = "Packages/com.unity.render-pipelines.universal/Shaders/Unlit.shader";
        const string ShaderGuid = "650dd9526735d5b46b79224bc6e94025";
        const string Warning = "JOURNEY_TRACER_UNAVAILABLE: Assign JourneyNailTrajectory with the URP Unlit shader in the authored scene. Nail trajectory disabled; combat remains available.";
        const BindingFlags Fields = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
        static void Set(object target, string name, object value) => target.GetType().GetField(name, Fields).SetValue(target, value);
        static object Field(object target, string name) => target.GetType().GetField(name, Fields).GetValue(target);
        static Material Material() => AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
        static void AssertColor(Color actual, Color expected)
        {
            // Unity serialization/aliases may round float components; the authored color stays exact.
            Assert.That(actual.r, Is.EqualTo(expected.r).Within(.000001f));
            Assert.That(actual.g, Is.EqualTo(expected.g).Within(.000001f));
            Assert.That(actual.b, Is.EqualTo(expected.b).Within(.000001f));
            Assert.That(actual.a, Is.EqualTo(expected.a).Within(.000001f));
        }
        static List<string> CheckSavedMaterial(Material material, string scenePath)
        {
            var errors = new List<string>();
            var checks = Type.GetType("DesertRV.Editor.JourneyContentChecks, Assembly-CSharp-Editor", true);
            checks.GetMethod("ValidateTracerMaterial").Invoke(null, new object[] { material, scenePath, errors });
            return errors;
        }

        [Test] public void ImportedMaterialReferencesExactPackageShaderAndOrangeColor()
        {
            var material = Material();
            Assert.That(material, Is.Not.Null);
            Assert.That(AssetDatabase.GetAssetPath(material.shader), Is.EqualTo(ShaderPath));
            Assert.That(AssetDatabase.AssetPathToGUID(ShaderPath), Is.EqualTo(ShaderGuid));
            Assert.That(material.shader.name, Is.EqualTo("Universal Render Pipeline/Unlit"));
            AssertColor(material.GetColor("_BaseColor"), new Color(1, .72f, .3f, 1));
            AssertColor(material.GetColor("_Color"), new Color(1, .72f, .3f, 1));
            var original = new Material(AssetDatabase.LoadAssetAtPath<Shader>(ShaderPath));
            try
            {
                original.color = new Color(1, .72f, .3f);
                AssertColor(material.GetColor("_BaseColor"), original.GetColor("_BaseColor"));
            }
            finally { Object.DestroyImmediate(original); }
            Assert.That(material.GetFloat("_Surface"), Is.Zero);
            Assert.That(material.GetFloat("_ZWrite"), Is.EqualTo(1));
        }

        [Test] public void ImportedMaterialReimportDoesNotRewriteSourceBytes()
        {
            // This covers a second import. Initial native import still needs producer evidence.
            byte[] before = File.ReadAllBytes(MaterialPath), meta = File.ReadAllBytes(MaterialPath + ".meta");
            AssetDatabase.ImportAsset(MaterialPath, ImportAssetOptions.ForceUpdate);
            Assert.That(File.ReadAllBytes(MaterialPath), Is.EqualTo(before));
            Assert.That(File.ReadAllBytes(MaterialPath + ".meta"), Is.EqualTo(meta));
        }

        [TestCase("JourneyActions")]
        [TestCase("FirstStationJourney")]
        public void SerializedSceneRetainsMaterialAndShaderDependency(string type)
        {
            var previousActive = SceneManager.GetActiveScene();
            var previous = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            var dirty = previous.ToDictionary(s => s.handle, s => s.isDirty);
            var roots = previous.ToDictionary(s => s.handle, s => s.GetRootGameObjects().Select(go => go.GetInstanceID()).OrderBy(id => id).ToArray());
            Scene scene = default;
            GameObject owner = null;
            string path = "Assets/JourneyTracerTest_" + Guid.NewGuid().ToString("N") + ".unity";
            try
            {
                // Match the FX/grounding fixtures: keep the runner's untitled scene open and untouched.
                scene = EditorSceneManager.NewPreviewScene();
                Assert.That(EditorSceneManager.IsPreviewScene(scene), Is.True);
                owner = new GameObject("inactive serialized tracer fixture"); owner.SetActive(false);
                SceneManager.MoveGameObjectToScene(owner, scene);
                var component = owner.AddComponent(Production.Type(type));
                var serialized = new SerializedObject(component);
                var field = serialized.FindProperty("nailTrajectoryMaterial");
                Assert.That(field, Is.Not.Null, "Both runtime material fields must be serialized.");
                field.objectReferenceValue = Material(); serialized.ApplyModifiedPropertiesWithoutUndo();
                Assert.That(EditorSceneManager.SaveScene(scene, path, true), Is.True);
                var dependencies = AssetDatabase.GetDependencies(path, true);
                Assert.That(dependencies, Does.Contain(MaterialPath));
                Assert.That(dependencies, Does.Contain(ShaderPath));
                Assert.That(CheckSavedMaterial(Material(), path), Is.Empty);
                Assert.That(CheckSavedMaterial(null, path), Is.Not.Empty);
                Assert.That(CheckSavedMaterial(Material(), ""), Is.Not.Empty);
                var clone = new Material(Material());
                try { Assert.That(CheckSavedMaterial(clone, path), Is.Not.Empty, "Runtime clones are not authored dependencies."); }
                finally { Object.DestroyImmediate(clone); }
                Assert.That(EditorSceneManager.ClosePreviewScene(scene), Is.True);
                scene = EditorSceneManager.OpenPreviewScene(path);
                Assert.That(EditorSceneManager.IsPreviewScene(scene), Is.True);
                var restored = scene.GetRootGameObjects().Single().GetComponent(Production.Type(type));
                Assert.That(Field(restored, "nailTrajectoryMaterial"), Is.SameAs(Material()));
                Set(restored, "nailTrajectoryMaterial", null);
                EditorUtility.SetDirty(restored);
                EditorSceneManager.MarkSceneDirty(scene); Assert.That(EditorSceneManager.SaveScene(scene, path, true), Is.True);
                Assert.That(CheckSavedMaterial(Material(), path), Is.Not.Empty, "An old saved scene cannot pass using only an in-memory material.");
            }
            finally
            {
                try
                {
                    try { if (owner) Object.DestroyImmediate(owner); }
                    finally { if (scene.IsValid()) Assert.That(EditorSceneManager.ClosePreviewScene(scene), Is.True); }
                }
                finally
                {
                    try
                    {
                        AssetDatabase.DeleteAsset(path);
                        Assert.That(File.Exists(path), Is.False);
                        Assert.That(File.Exists(path + ".meta"), Is.False);
                    }
                    finally
                    {
                        var after = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
                        Assert.That(after.Select(s => s.handle), Is.EqualTo(previous.Select(s => s.handle)));
                        Assert.That(SceneManager.GetActiveScene(), Is.EqualTo(previousActive));
                        foreach (var original in after)
                        {
                            Assert.That(original.isDirty, Is.EqualTo(dirty[original.handle]));
                            Assert.That(original.GetRootGameObjects().Select(go => go.GetInstanceID()).OrderBy(id => id), Is.EqualTo(roots[original.handle]));
                        }
                    }
                }
            }
        }

        sealed class Fixture : IDisposable
        {
            public readonly GameObject Root = new GameObject("inactive tracer combat fixture");
            public readonly Component Controller;
            public readonly object State;
            public LineRenderer Tracer => Root.GetComponentInChildren<LineRenderer>(true);
            public Fixture(string type, Material material)
            {
                Root.SetActive(false);
                var session = Root.AddComponent(Production.Type("JourneySession"));
                State = Production.Session(); Production.Call(State, "SetControl", Production.Enum("ControlMode", "OnFoot"));
                session.GetType().GetProperty("State").SetValue(session, State);
                var motor = Root.AddComponent(Production.Type("JourneyMotor")); Set(motor, "journey", session);
                var vehicle = Child("vehicle"); Set(motor, "vehicle", vehicle);
                var camera = Child("camera").gameObject.AddComponent<Camera>();
                camera.transform.position = new Vector3(40000, 40000, 40000); Set(motor, "view", camera);
                Set(motor, "walker", Child("walker").gameObject.AddComponent<CharacterController>());
                Controller = Root.AddComponent(Production.Type(type));
                Set(Controller, "journey", session); Set(Controller, "motor", motor); Set(Controller, "nailTrajectoryMaterial", material);
                if (type == "JourneyActions") Set(Controller, "shotMuzzle", Child("authored muzzle"));
                else
                {
                    var empty = Array.CreateInstance(Production.Type("BeastActor"), 0);
                    Set(Controller, "guards", empty); Set(Controller, "roadBeasts", empty);
                }
            }
            Transform Child(string name)
            { var child = new GameObject(name).transform; child.SetParent(Root.transform, false); return child; }
            public void Dispose() { if (Root) Object.DestroyImmediate(Root); }
        }

        [TestCase("JourneyActions", "valid")]
        [TestCase("FirstStationJourney", "valid")]
        [TestCase("JourneyActions", "missing")]
        [TestCase("FirstStationJourney", "missing")]
        [TestCase("JourneyActions", "wrong-shader")]
        [TestCase("FirstStationJourney", "wrong-shader")]
        public void AwakeAndFirePreserveCombatWithOrWithoutTracer(string type, string materialKind)
        {
            var authored = Material(); Assert.That(authored, Is.Not.Null);
            var originalColor = authored.GetColor("_BaseColor");
            Material wrong = null;
            try
            {
                if (materialKind == "wrong-shader")
                {
                    var lit = AssetDatabase.LoadAssetAtPath<Shader>("Packages/com.unity.render-pipelines.universal/Shaders/Lit.shader");
                    Assert.That(lit, Is.Not.Null); wrong = new Material(lit);
                }
                var input = materialKind == "valid" ? authored : wrong;
                using (var fixture = new Fixture(type, input))
                {
                    if (materialKind != "valid") LogAssert.Expect(LogType.Warning, Warning);
                    Assert.DoesNotThrow(() => Production.Call(fixture.Controller, "Awake"));
                    var tracer = fixture.Tracer;
                    Assert.That(tracer, Is.Not.Null, "Awake must finish, including the owned tracer.");
                    Assert.That(tracer.transform.parent, Is.EqualTo(fixture.Root.transform));
                    Assert.That(tracer.enabled, Is.False);
                    Assert.That(tracer.startWidth, Is.EqualTo(.008f)); Assert.That(tracer.endWidth, Is.EqualTo(.003f));
                    if (materialKind == "valid") Assert.That(tracer.sharedMaterial, Is.SameAs(authored));
                    else Assert.That(tracer.sharedMaterial, Is.Null);
                    int before = Production.Get<int>(fixture.State, "LoadedAmmo");
                    Assert.DoesNotThrow(() => Production.Call(fixture.Controller, "Fire"));
                    Assert.That(Production.Get<int>(fixture.State, "LoadedAmmo"), Is.EqualTo(before - 1));
                    Assert.That(Field(fixture.Controller, "fireClock"), Is.EqualTo(.22f));
                    Assert.That(Field(fixture.Controller, "tracerRemaining"), Is.EqualTo(.06f));
                    Assert.That(tracer.enabled, Is.EqualTo(materialKind == "valid"));
                    Assert.That(tracer.GetPosition(1), Is.EqualTo(new Vector3(40000, 40000, 40045)));
                    Object.DestroyImmediate(fixture.Root);
                    Assert.That(tracer == null, Is.True, "Destroying the owner must destroy its tracer child.");
                    Assert.That(authored != null, Is.True, "Shared imported material must survive owner destruction.");
                    AssertColor(authored.GetColor("_BaseColor"), originalColor);
                    Assert.That(AssetDatabase.LoadAssetAtPath<Material>(MaterialPath), Is.SameAs(authored));
                }
            }
            finally { if (wrong) Object.DestroyImmediate(wrong); }
        }
    }
}
