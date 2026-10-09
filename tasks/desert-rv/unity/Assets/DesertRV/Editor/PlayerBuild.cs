using System;
using System.IO;
using System.Security.Cryptography;
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
        public static void BuildLinuxReference() => BuildReference(false);

        // Candidate-only standalone rendering proof, never Journey or Android approval.
        public static void BuildLinuxWindowSmoke() => BuildReference(true);

        [Serializable] sealed class SmokeReceipt
        {
            public string mode = "BODY_STUDY_LINUX_PLAYER_CANDIDATE_ONLY";
            public string sourceCommit, sceneSha256, executableSha256;
            public string executable = "DesertRV.x86_64";
            public bool targetSupported, buildSucceeded, settingsRestored;
            public bool temporarySettingsOverridden = true;
            public string buildTarget = "StandaloneLinux64", backend = "Mono2x", candidateDefine = "DESERTRV_REFERENCE_WINDOW_PROBE";
            public int width = 1280, height = 720;
            public string fullscreen = "Windowed";
        }
        static string Sha(string file)
        {
            using (var hash = SHA256.Create())
            using (var input = File.OpenRead(file))
                return BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
        }
        static void BuildReference(bool smoke)
        {
            if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Standalone, BuildTarget.StandaloneLinux64))
                throw new InvalidOperationException("LINUX_TARGET_UNSUPPORTED");
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
            string settingsPath = Path.GetFullPath("ProjectSettings/ProjectSettings.asset");
            byte[] originalSettings = File.ReadAllBytes(settingsPath);
            var backend = PlayerSettings.GetScriptingBackend(NamedBuildTarget.Standalone);
            var fullscreen = PlayerSettings.fullScreenMode;
            int width = PlayerSettings.defaultScreenWidth, height = PlayerSettings.defaultScreenHeight;
            bool resize = PlayerSettings.resizableWindow;
            string product = PlayerSettings.productName;
            string path = smoke ? Environment.GetEnvironmentVariable("DESERTRV_PLAYER_BUILD") :
                Path.GetFullPath(Path.Combine(Application.dataPath, "../../build/linux-reference/DesertRV.x86_64"));
            if (string.IsNullOrEmpty(path) || !Path.IsPathRooted(path)) throw new InvalidOperationException("BUILD_PATH_REQUIRED");
            BuildReport report;
            try
            {
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
                PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
                PlayerSettings.defaultScreenWidth = 1280;
                PlayerSettings.defaultScreenHeight = 720;
                PlayerSettings.resizableWindow = !smoke;
                if (smoke) PlayerSettings.productName = "DESERTRV_REFERENCE_PLAYER";
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { ReferenceScene }, target = BuildTarget.StandaloneLinux64,
                    locationPathName = path, options = BuildOptions.Development,
                    extraScriptingDefines = smoke ? new[] { "DESERTRV_REFERENCE_WINDOW_PROBE" } : Array.Empty<string>()
                });
                if (report.summary.result != BuildResult.Succeeded)
                    throw new InvalidOperationException("REFERENCE_BUILD_FAILED");
            }
            finally
            {
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, backend);
                PlayerSettings.fullScreenMode = fullscreen;
                PlayerSettings.defaultScreenWidth = width;
                PlayerSettings.defaultScreenHeight = height;
                PlayerSettings.resizableWindow = resize;
                PlayerSettings.productName = product;
                AssetDatabase.SaveAssets();
                // Restore exact original serialization; the external full-source guard still rejects other changes.
                File.WriteAllBytes(settingsPath, originalSettings);
            }
            if (smoke)
            {
                var receipt = new SmokeReceipt { sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA"),
                    sceneSha256 = Sha(ReferenceScene), executableSha256 = Sha(path),
                    targetSupported = true, buildSucceeded = true, settingsRestored = true };
                File.WriteAllText(Path.Combine(Path.GetDirectoryName(path), "build-receipt.json"), JsonUtility.ToJson(receipt));
            }
            Debug.Log("DESERT_RV_LINUX_REFERENCE_BUILT bytes=" + report.summary.totalSize);
        }
    }
}
