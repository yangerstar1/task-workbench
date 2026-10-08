using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace DesertRV.Editor
{
    public static class JourneyBuild
    {
        const string ScenePath = "Assets/DesertRV/Scenes/FirstStation.unity";
        const string BeastPath = "Assets/DesertRV/Actors/Pouncer.prefab";
        // Explicit authoring command only; normal builds preserve the saved scene.
        public static void AuthorFirstStation() => Author(false);
        public static void AuthorTraversalHarness() => Author(true);
        static void Author(bool traversalOnly)
        {
            var beastPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(BeastPath);
            if (!traversalOnly && (!beastPrefab || !beastPrefab.GetComponent<BeastActor>()))
                throw new Exception("Reviewed/imported Pouncer prefab required before authoring gameplay scene.");
            var scene = EditorSceneManager.OpenScene("Assets/DesertRV/Scenes/BodyStudy.unity", OpenSceneMode.Single);
            var reference = UnityEngine.Object.FindFirstObjectByType<BodyViewer>();
            if (!reference || !reference.body || !reference.view || !reference.garageBench)
                throw new Exception("Saved reference bindings missing; do not rebuild BodyStudy.");
            Transform body = reference.body;
            var roots = body.GetComponentsInChildren<Transform>(true);
            var glass = roots.Single(t => t.name == "GEO-windscreen").GetComponent<Renderer>();
            Vector3 forward = glass.bounds.center - body.position; forward.y = 0; forward.Normalize();
            var hostObject = new GameObject("Journey");
            var host = hostObject.AddComponent<JourneySession>();
            var motor = hostObject.AddComponent<JourneyMotor>();
            motor.journey = host; motor.vehicle = body; motor.view = reference.view;
            motor.localForward = body.InverseTransformDirection(forward);
            motor.doorHinge = roots.Single(t => t.name == "RIG-entry_door_pivot");
            motor.entryStep = roots.Single(t => t.name == "GEO-entry_step");
            motor.ram = reference.ramModule; motor.arc = reference.arcModule; motor.roofCargo = reference.roofCargo;
            if (!motor.ram || !motor.arc) throw new Exception("Retained upgrade model bindings missing");
            motor.ram.SetActive(false); motor.arc.SetActive(false);
            var controller = hostObject.AddComponent<FirstStationJourney>();
            controller.journey = host; controller.motor = motor; controller.combatUnavailable = traversalOnly;
            var bench = reference.garageBench.GetComponent<Renderer>();
            controller.salvagePoint = Point("Salvage interaction", bench.transform, bench.bounds.center + Vector3.up * .3f);
            var part = UnityEngine.Object.Instantiate(motor.ram, bench.transform);
            part.name = "Salvage ram assembly"; part.SetActive(true);
            part.transform.position = controller.salvagePoint.position;
            part.transform.localScale = Vector3.one * .13f;
            foreach (var collider in part.GetComponentsInChildren<Collider>()) UnityEngine.Object.DestroyImmediate(collider);
            controller.salvageVisual = part;
            var repair = roots.Single(t => t.name == "GEO-rear_repair_bench").GetComponent<Renderer>();
            controller.cabinWorkbench = Point("Cabin installation point", body, repair.bounds.center + Vector3.up * .18f);
            controller.exitPoint = Point("Station north exit", hostObject.transform, body.position + forward * 64);
            Vector3 side = Vector3.Cross(Vector3.up, forward);
            Vector3 garage = bench.bounds.center; garage.y = .02f;
            controller.guards = traversalOnly ? Array.Empty<BeastActor>() : new[]
            {
                Spawn(beastPrefab, host, motor, garage + side * 4 + forward * 7, "Station guard A"),
                Spawn(beastPrefab, host, motor, garage - side * 5 + forward * 9, "Station guard B")
            };
            controller.roadBeasts = traversalOnly ? Array.Empty<BeastActor>() : new[]
            {
                Spawn(beastPrefab, host, motor, body.position + forward * 32 + side * 3, "Road beast A"),
                Spawn(beastPrefab, host, motor, body.position + forward * 40 - side * 3, "Road beast B")
            };
            foreach (var actor in controller.roadBeasts) actor.gameObject.SetActive(false);
            var hud = new GameObject("Journey HUD").AddComponent<JourneyHud>();
            hud.journey = host; hud.motor = motor; hud.station = controller;
            hud.font = AssetDatabase.LoadAssetAtPath<Font>("Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf");
            if (!hud.font) throw new Exception("Licensed Chinese font missing");
            controller.hud = hud;
            controller.shotSound = Audio("shot"); controller.hitSound = Audio("hit");
            controller.pickupSound = Audio("pickup"); controller.upgradeSound = Audio("upgrade"); controller.windSound = Audio("wind");
            UnityEngine.Object.DestroyImmediate(reference.gameObject);
            foreach (var preflight in UnityEngine.Object.FindObjectsByType<WebPreflight>(FindObjectsSortMode.None)) UnityEngine.Object.DestroyImmediate(preflight);
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            PlayerSettings.allowedAutorotateToLandscapeLeft = true; PlayerSettings.allowedAutorotateToLandscapeRight = true;
            PlayerSettings.allowedAutorotateToPortrait = false; PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
            string outputScene = traversalOnly ? "Assets/DesertRV/Scenes/TraversalHarness.unity" : ScenePath;
            EditorSceneManager.SaveScene(scene, outputScene);
            AssetDatabase.SaveAssets();
            Debug.Log("DESERT_RV_FIRST_STATION_AUTHORED source=saved-reference");
        }
        static AudioClip Audio(string name) => AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/DesertRV/Audio/" + name + ".wav");
        static Transform Point(string name, Transform parent, Vector3 position)
        { var point = new GameObject(name).transform; point.SetParent(parent); point.position = position; return point; }
        static BeastActor Spawn(GameObject prefab, JourneySession host, JourneyMotor player, Vector3 at, string name)
        {
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab); instance.name = name;
            instance.transform.position = at;
            var actor = instance.GetComponent<BeastActor>(); actor.journey = host; actor.player = player;
            return actor;
        }
        public static void BuildLinuxFirstStation() => Build(ScenePath, "linux-first-station");
        public static void BuildTraversalHarness()
        {
            AuthorTraversalHarness(); Build("Assets/DesertRV/Scenes/TraversalHarness.unity", "linux-traversal-harness");
        }
        static void Build(string scenePath, string outputFolder)
        {
            if (!File.Exists(scenePath)) throw new FileNotFoundException("Author and review the gameplay scene first", ScenePath);
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1280; PlayerSettings.defaultScreenHeight = 720;
            string output = Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/" + outputFolder + "/DesertRV.x86_64"));
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            { scenes = new[] { scenePath }, target = BuildTarget.StandaloneLinux64, locationPathName = output, options = BuildOptions.Development });
            if (report.summary.result != BuildResult.Succeeded) throw new Exception("First-station build failed");
            Debug.Log("DESERT_RV_FIRST_STATION_BUILT bytes=" + report.summary.totalSize);
        }
    }
}
