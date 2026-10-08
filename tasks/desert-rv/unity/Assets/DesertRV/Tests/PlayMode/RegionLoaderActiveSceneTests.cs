using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using System.IO;
using System.Linq;
#endif

namespace DesertRV.Tests
{
    // Real, generated scene assets are used only by this test fixture. They do not change
    // production content verification, and are removed with their temporary build entry.
    public sealed class RegionLoaderSceneFixture : IPrebuildSetup, IPostBuildCleanup
    {
        public const string Folder = "Assets/DesertRVLoaderTestFixtures";
        public const string ScenePath = Folder + "/LoaderEnvironment.unity";
#if UNITY_EDITOR
        const string Backup = "Library/DesertRVLoaderTestBuildSettings.json";
        [Serializable] sealed class Settings { public Entry[] scenes; }
        [Serializable] sealed class Entry { public string path; public bool enabled; }
#endif
        public void Setup()
        {
#if UNITY_EDITOR
            if (AssetDatabase.IsValidFolder(Folder) || File.Exists(Backup)) throw new InvalidOperationException("Loader fixture already exists; refusing to overwrite it.");
            var previousActive = SceneManager.GetActiveScene();
            Scene scene = default; bool prepared = false;
            var old = EditorBuildSettings.scenes;
            File.WriteAllText(Backup, JsonUtility.ToJson(new Settings { scenes = old.Select(x => new Entry { path = x.path, enabled = x.enabled }).ToArray() }));
            try
            {
                AssetDatabase.CreateFolder("Assets", "DesertRVLoaderTestFixtures");
                scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
                SceneManager.SetActiveScene(scene);
                RenderSettings.fog = true; RenderSettings.fogColor = new Color(.17f, .31f, .53f, 1);
                var root = new GameObject("Fixture region");
                var type = Type.GetType("DesertRV.RegionBinding, Assembly-CSharp", true);
                var binding = root.AddComponent(type);
                var surface = root.AddComponent<BoxCollider>();
                void Set(string field, object value) => type.GetField(field).SetValue(binding, value);
                Set("region", 1); Set("spawn", root.transform); Set("exitVolume", surface);
                Set("salvage", root.transform); Set("salvageSurface", surface); Set("ramGate", surface);
                Set("pickupId", "test-only-loader-fixture");
                Set("environmentVerified", true); Set("combatAssetsVerified", true);
                var enemyType = Type.GetType("DesertRV.BeastActor, Assembly-CSharp", true);
                foreach (var field in new[] { "guards", "roadBeasts" })
                {
                    var enemy = new GameObject(field + " fixture actor"); enemy.transform.SetParent(root.transform);
                    enemy.AddComponent<BoxCollider>(); var actor = (Behaviour)enemy.AddComponent(enemyType); actor.enabled = false;
                    var array = Array.CreateInstance(enemyType, 1); array.SetValue(actor, 0); Set(field, array);
                }
                if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("Could not save loader fixture.");
                EditorBuildSettings.scenes = old.Concat(new[] { new EditorBuildSettingsScene(ScenePath, true) }).ToArray();
                prepared = true;
            }
            finally
            {
                if (scene.IsValid() && scene.isLoaded) EditorSceneManager.CloseScene(scene, true);
                if (previousActive.IsValid() && previousActive.isLoaded) SceneManager.SetActiveScene(previousActive);
                if (!prepared) Cleanup();
            }
#endif
        }
        public void Cleanup()
        {
#if UNITY_EDITOR
            if (!File.Exists(Backup)) return;
            var settings = JsonUtility.FromJson<Settings>(File.ReadAllText(Backup));
            EditorBuildSettings.scenes = settings.scenes.Select(x => new EditorBuildSettingsScene(x.path, x.enabled)).ToArray();
            if (AssetDatabase.IsValidFolder(Folder)) AssetDatabase.DeleteAsset(Folder);
            File.Delete(Backup);
#endif
        }
    }

    [PrebuildSetup(typeof(RegionLoaderSceneFixture))]
    [PostBuildCleanup(typeof(RegionLoaderSceneFixture))]
    public sealed class RegionLoaderActiveSceneTests
    {
        GameObject host;
        Component session, loader;
        Scene initial, newer;
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Call(object obj, string name, params object[] args) => obj.GetType().GetMethod(name).Invoke(obj, args);
        static object Get(object obj, string name) => obj.GetType().GetProperty(name).GetValue(obj);
        static Func<TBinding, bool> Adapt<TBinding>(Func<Component, bool> callback) => binding => callback((Component)(object)binding);
        void Load(object ticket, Func<Component, bool> ready, Action<string> failed)
        {
            var callback = typeof(RegionLoaderActiveSceneTests).GetMethod("Adapt", BindingFlags.Static | BindingFlags.NonPublic).MakeGenericMethod(T("RegionBinding")).Invoke(null, new object[] { ready });
            Call(loader, "Load", session, ticket, callback, failed);
        }
        IEnumerator Finish()
        {
            float deadline = Time.realtimeSinceStartup + 20;
            while ((bool)Get(loader, "Busy") && Time.realtimeSinceStartup < deadline) yield return null;
            Assert.That(Get(loader, "Busy"), Is.False, "Loader did not finish.");
        }
        [UnitySetUp] public IEnumerator SetUp()
        {
            initial = SceneManager.GetActiveScene();
            host = new GameObject("loader fixture host");
            session = host.AddComponent(T("JourneySession")); loader = host.AddComponent(T("RegionLoader"));
            loader.GetType().GetField("regionScenes").SetValue(loader, new[] { RegionLoaderSceneFixture.ScenePath });
            Assert.That(Call(session, "StartJourney"), Is.True);
            yield return null;
        }
        [UnityTearDown] public IEnumerator TearDown()
        {
            if (initial.IsValid() && initial.isLoaded) SceneManager.SetActiveScene(initial);
            if (host) UnityEngine.Object.Destroy(host);
            for (int i = SceneManager.sceneCount - 1; i >= 0; i--)
            {
                var scene = SceneManager.GetSceneAt(i);
                if (scene.path == RegionLoaderSceneFixture.ScenePath || scene == newer) yield return SceneManager.UnloadSceneAsync(scene);
            }
            yield return null;
        }
        [UnityTest] public IEnumerator LoadedRegion_IsActiveWithItsRenderSettingsBeforeReady()
        {
            var ticket = Call(session, "BeginCurrentRegionLoad"); bool called = false; string failure = null;
            Load(ticket, binding =>
            {
                called = true;
                Assert.That(SceneManager.GetActiveScene(), Is.EqualTo(binding.gameObject.scene));
                Assert.That(RenderSettings.fogColor.r, Is.EqualTo(.17f).Within(.001));
                Assert.That(RenderSettings.fogColor.g, Is.EqualTo(.31f).Within(.001));
                return (bool)Call(session, "CompleteRegionLoad", ticket, 0d);
            }, error => failure = error);
            yield return Finish(); Assert.That(failure, Is.Null); Assert.That(called, Is.True);
        }
        [UnityTest] public IEnumerator RejectedSameNameReload_RestoresPreviousActiveAndAllowsSameTicketRetry()
        {
            var first = Call(session, "BeginCurrentRegionLoad");
            string error = null;
            Load(first, binding => (bool)Call(session, "CompleteRegionLoad", first, 0d), message => error = message);
            yield return Finish(); Assert.That(error, Is.Null);
            var previous = SceneManager.GetActiveScene();
            var priorRoot = previous.GetRootGameObjects()[0];
            var inactive = new GameObject("intentionally inactive previous root"); SceneManager.MoveGameObjectToScene(inactive, previous); inactive.SetActive(false);
            var ticket = Call(session, "BeginCurrentRegionLoad");
            Load(ticket, binding => { Assert.That(binding.gameObject.scene.handle, Is.Not.EqualTo(previous.handle)); return false; }, message => error = message);
            yield return Finish();
            Assert.That(error, Is.Not.Null); Assert.That(previous.isLoaded, Is.True);
            Assert.That(SceneManager.GetActiveScene(), Is.EqualTo(previous));
            Assert.That(priorRoot.activeSelf, Is.True); Assert.That(inactive.activeSelf, Is.False);
            Assert.That(Call(session, "IsCurrentLoad", ticket), Is.True);
            error = null;
            Load(ticket, binding => (bool)Call(session, "CompleteRegionLoad", ticket, 0d), message => error = message);
            yield return Finish(); Assert.That(error, Is.Null); Assert.That(previous.isLoaded, Is.False);
        }
        [UnityTest] public IEnumerator ReadyException_RestoresActiveReleasesBusyAndKeepsTicket()
        {
            var ticket = Call(session, "BeginCurrentRegionLoad"); string error = null;
            Load(ticket, binding => throw new InvalidOperationException("fixture ready failure"), message => error = message);
            yield return Finish();
            StringAssert.Contains("fixture ready failure", error);
            Assert.That(SceneManager.GetActiveScene(), Is.EqualTo(initial));
            Assert.That(Call(session, "IsCurrentLoad", ticket), Is.True);
        }
        [UnityTest] public IEnumerator StaleGenerationLoad_DoesNotStealNewerActiveScene()
        {
            var ticket = Call(session, "BeginCurrentRegionLoad"); bool called = false; string error = null;
            Load(ticket, binding => { called = true; return true; }, message => error = message);
            // Complete and end the older lifecycle before its async scene callback arrives.
            Assert.That(Call(session, "CompleteRegionLoad", ticket, 0d), Is.True);
            Call(Get(session, "State"), "DamagePlayer", 100); Assert.That(Call(session, "RestartJourney"), Is.True);
            newer = SceneManager.CreateScene("Newer journey active scene"); SceneManager.SetActiveScene(newer);
            yield return Finish();
            Assert.That(called, Is.False); Assert.That(error, Is.Null);
            Assert.That(SceneManager.GetActiveScene(), Is.EqualTo(newer));
            Assert.That(SceneManager.GetSceneByPath(RegionLoaderSceneFixture.ScenePath).IsValid(), Is.False);
        }
        [UnityTest] public IEnumerator UnloadedScene_ActivationFailsWithoutChangingActiveScene()
        {
            var scene = SceneManager.CreateScene("unloaded activation target");
            yield return SceneManager.UnloadSceneAsync(scene);
            object[] args = { scene, null };
            var method = T("RegionLoader").GetMethod("TryActivate", BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(method.Invoke(null, args), Is.False); Assert.That(args[1], Is.Not.Null);
            Assert.That(SceneManager.GetActiveScene(), Is.EqualTo(initial));
        }
    }
}
