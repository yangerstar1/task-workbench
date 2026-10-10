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
            var setup = EditorSceneManager.GetSceneManagerSetup();
            var previous = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            Debug.Log("JOURNEY_TRACER_FIXTURE_INITIAL sceneCount=" + previous.Length + " scenes=" + string.Join(";", previous.Select(s =>
                "pathEmpty=" + string.IsNullOrEmpty(s.path) + ",loaded=" + s.isLoaded + ",dirty=" + s.isDirty + ",rootCount=" + (s.isLoaded ? s.rootCount : -1))));
            bool restorable = setup.Any(s => s.isLoaded && s.isActive) &&
                setup.All(s => !string.IsNullOrEmpty(s.path) && File.Exists(s.path)) && previous.All(s => !s.isLoaded || !s.isDirty);
            // CI may start with default objects or test-runner state in Untitled. Preserve a
            // serialized recovery copy first; never apply that identity-changing fallback to a user's Editor.
            Assert.That(restorable || previous.Length == 0 || Application.isBatchMode, Is.True,
                "Unsaved initial scenes require the isolated batch fixture or an explicitly saved Editor setup.");
            var originalFiles = setup.Select(s => s.path).Where(p => !string.IsNullOrEmpty(p))
                .SelectMany(p => new[] { p, p + ".meta" }).Distinct().Where(File.Exists).ToDictionary(p => p, File.ReadAllBytes);
            string id = Guid.NewGuid().ToString("N");
            string recovery = "Library/DesertRVTracerFixture/" + id;
            var temporaryCopies = new List<string>();
            var recoveryFiles = new Dictionary<string, byte[]>();
            bool replaced = false;
            Scene scene = default;
            string path = "Assets/JourneyTracerTest_" + id + ".unity";
            Assert.That(File.Exists(path) || File.Exists(path + ".meta"), Is.False);
            try
            {
                if (!restorable && previous.Any(s => s.isLoaded))
                {
                    Assert.That(Directory.Exists(recovery), Is.False);
                    Directory.CreateDirectory(recovery);
                    for (int i = 0; i < previous.Length; i++)
                    {
                        var initial = previous[i]; if (!initial.isLoaded) continue;
                        string initialPath = initial.path; bool initialDirty = initial.isDirty;
                        string copy = "Assets/JourneyTracerInitial_" + id + "_" + i + ".unity";
                        Assert.That(File.Exists(copy) || File.Exists(copy + ".meta"), Is.False);
                        temporaryCopies.Add(copy);
                        Assert.That(EditorSceneManager.SaveScene(initial, copy, true), Is.True);
                        foreach (string suffix in new[] { "", ".meta" })
                        {
                            string destination = recovery + "/Initial-" + i + ".unity" + suffix;
                            var bytes = File.ReadAllBytes(copy + suffix);
                            File.WriteAllBytes(destination, bytes); recoveryFiles.Add(destination, bytes);
                            Assert.That(File.ReadAllBytes(destination), Is.EqualTo(bytes));
                        }
                        File.WriteAllText(recovery + "/Initial-" + i + ".txt", "path=" + initialPath + "\ndirty=" + initialDirty +
                            "\nactive=" + (initial == SceneManager.GetActiveScene()) + "\nrootCount=" + initial.rootCount);
                        Assert.That(initial.path, Is.EqualTo(initialPath)); Assert.That(initial.isDirty, Is.EqualTo(initialDirty));
                        Assert.That(AssetDatabase.DeleteAsset(copy), Is.True);
                    }
                }
                // Match SavedSceneTransactionFixture: ordinary scenes support real save/reload.
                replaced = true;
                scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var owner = new GameObject("inactive serialized tracer fixture"); owner.SetActive(false);
                SceneManager.MoveGameObjectToScene(owner, scene);
                var component = owner.AddComponent(Production.Type(type));
                var serialized = new SerializedObject(component);
                var field = serialized.FindProperty("nailTrajectoryMaterial");
                Assert.That(field, Is.Not.Null, "Both runtime material fields must be serialized.");
                field.objectReferenceValue = Material(); serialized.ApplyModifiedPropertiesWithoutUndo();
                Assert.That(EditorSceneManager.SaveScene(scene, path), Is.True);
                var dependencies = AssetDatabase.GetDependencies(path, true);
                Assert.That(dependencies, Does.Contain(MaterialPath));
                Assert.That(dependencies, Does.Contain(ShaderPath));
                Assert.That(CheckSavedMaterial(Material(), path), Is.Empty);
                Assert.That(CheckSavedMaterial(null, path), Is.Not.Empty);
                Assert.That(CheckSavedMaterial(Material(), ""), Is.Not.Empty);
                var clone = new Material(Material());
                try { Assert.That(CheckSavedMaterial(clone, path), Is.Not.Empty, "Runtime clones are not authored dependencies."); }
                finally { Object.DestroyImmediate(clone); }
                // Opening in Single mode closes the saved fixture and loads its serialized bytes.
                scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                var restored = scene.GetRootGameObjects().Single().GetComponent(Production.Type(type));
                Assert.That(Field(restored, "nailTrajectoryMaterial"), Is.SameAs(Material()));
                Set(restored, "nailTrajectoryMaterial", null);
                EditorUtility.SetDirty(restored);
                EditorSceneManager.MarkSceneDirty(scene); Assert.That(EditorSceneManager.SaveScene(scene, path), Is.True);
                Assert.That(CheckSavedMaterial(Material(), path), Is.Not.Empty, "An old saved scene cannot pass using only an in-memory material.");
            }
            finally
            {
                bool setupRestored = false;
                try
                {
                    // Unload even a partially authored/dirty fixture before deleting its asset.
                    if (replaced)
                    {
                        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                        if (restorable) EditorSceneManager.RestoreSceneManagerSetup(setup);
                        setupRestored = true;
                    }
                }
                finally
                {
                    bool fixtureUnloaded = !SceneManager.GetSceneByPath(path).IsValid();
                    try
                    {
                        if (fixtureUnloaded)
                        {
                            AssetDatabase.DeleteAsset(path);
                            Assert.That(File.Exists(path), Is.False);
                            Assert.That(File.Exists(path + ".meta"), Is.False);
                        }
                        else Debug.Log("JOURNEY_TRACER_FIXTURE_RETAINED loadedFixture=true");
                        foreach (string copy in temporaryCopies)
                        {
                            AssetDatabase.DeleteAsset(copy);
                            Assert.That(File.Exists(copy) || File.Exists(copy + ".meta"), Is.False);
                        }
                    }
                    finally
                    {
                        foreach (var original in originalFiles) Assert.That(File.ReadAllBytes(original.Key), Is.EqualTo(original.Value));
                        foreach (var copy in recoveryFiles) Assert.That(File.ReadAllBytes(copy.Key), Is.EqualTo(copy.Value));
                        var after = EditorSceneManager.GetSceneManagerSetup();
                        if (setupRestored && restorable)
                        {
                            Assert.That(after.Select(s => s.path), Is.EqualTo(setup.Select(s => s.path)));
                            Assert.That(after.Select(s => s.isLoaded), Is.EqualTo(setup.Select(s => s.isLoaded)));
                            Assert.That(after.Select(s => s.isActive), Is.EqualTo(setup.Select(s => s.isActive)));
                        }
                        else if (setupRestored)
                        {
                            Assert.That(SceneManager.sceneCount, Is.EqualTo(1));
                            var empty = SceneManager.GetActiveScene();
                            Assert.That(empty.IsValid() && empty.isLoaded, Is.True);
                            Assert.That(empty.path, Is.Empty); Assert.That(empty.rootCount, Is.Zero);
                        }
                        if (setupRestored) Assert.That(Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt)
                            .All(s => !s.isLoaded || !s.isDirty), Is.True);
                        Debug.Log("JOURNEY_TRACER_FIXTURE_RECOVERY restoredNamedSetup=" + (setupRestored && restorable) +
                            " privateRecoveryFiles=" + recoveryFiles.Count + " replaced=" + replaced);
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
