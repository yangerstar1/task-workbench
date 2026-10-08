using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DesertRV.Editor
{
    public static class PlayerBuild
    {
        const string ReferenceScene = "Assets/DesertRV/Scenes/BodyStudy.unity";

        // This is the retained art/control reference, not the completed game.
        // Never call BodyBuild.Initialize or WebBuild.Prepare here: both rebuild scenes.
        public static void BuildLinuxReference()
        {
            if (!File.Exists(ReferenceScene)) throw new FileNotFoundException("Saved reference scene missing", ReferenceScene);
            var scene = EditorSceneManager.OpenScene(ReferenceScene, OpenSceneMode.Single);
            int cameras = 0, renderers = 0;
            foreach (var root in scene.GetRootGameObjects())
            {
                cameras += root.GetComponentsInChildren<Camera>(true).Length;
                foreach (var node in root.GetComponentsInChildren<Transform>(true))
                    foreach (var component in node.GetComponents<Component>())
                        if (component == null) throw new Exception("Missing script on " + node.name);
                foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
                {
                    renderers++;
                    foreach (var material in renderer.sharedMaterials)
                        if (material == null || material.shader == null)
                            throw new Exception("Missing material/shader on " + renderer.name);
                }
            }
            if (cameras == 0 || renderers == 0) throw new Exception("Reference has no renderable camera/world");
            Debug.Log($"DESERT_RV_REFERENCE_VALIDATED cameras={cameras} renderers={renderers}");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1280;
            PlayerSettings.defaultScreenHeight = 720;
            PlayerSettings.resizableWindow = true;
            string path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../build/linux-reference/DesertRV.x86_64"));
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ReferenceScene },
                target = BuildTarget.StandaloneLinux64,
                locationPathName = path,
                options = BuildOptions.Development
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new Exception("Reference build failed: " + report.summary.result);
            Debug.Log("DESERT_RV_LINUX_REFERENCE_BUILT bytes=" + report.summary.totalSize);
        }
    }
}
