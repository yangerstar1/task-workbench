using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using Lottery.G2.Interaction;
namespace Lottery.G2.Editor
{
    // Reuses the verified G0 render configuration; runtime composition has one owner.
    public static class G2Build
    {
        public const string ScenePath = "Assets/G2/Scenes/G2Slice.unity";
        public const string RulesSha256 = "e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668";
        public static void Prepare()
        {
            Lottery.Probe.Editor.ProbeBuild.Prepare();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var bootstrap = new GameObject("G2 Technical Slice").AddComponent<G2SliceBootstrap>();
            bootstrap.chineseFont = AssetDatabase.LoadAssetAtPath<Font>("Assets/Resources/ProbeChinese.otf");
            bootstrap.scratchShader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/G2/Rendering/G2Scratch.shader");
            bootstrap.fontShader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/G2/Rendering/G2Font.shader");
            bootstrap.flatShader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/G2/Rendering/G2Flat.shader");
            bootstrap.surfaceShader = Shader.Find("Universal Render Pipeline/Lit");
            if (bootstrap.chineseFont == null || bootstrap.scratchShader == null || bootstrap.fontShader == null ||
                bootstrap.flatShader == null || bootstrap.surfaceShader == null)
                throw new InvalidOperationException("G2 scene dependencies missing");
            Directory.CreateDirectory("Assets/G2/Scenes");
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new IOException("G2 scene save failed");
            AssetDatabase.SaveAssets();
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        }
        public static void BuildAndroid()
        {
            if (Lottery.G2.Core.NumberTicketRules.RulesSha256 != RulesSha256) throw new InvalidOperationException("G2 rules binding mismatch");
            Prepare();
            var commit = Arg("-probeCommit"); var run = Arg("-probeRunId");
            if (!System.Text.RegularExpressions.Regex.IsMatch(commit, "^[0-9a-f]{40}$") ||
                !System.Text.RegularExpressions.Regex.IsMatch(run, "^[1-9][0-9]*$"))
                throw new InvalidOperationException("Invalid source/run identity");
            PlayerSettings.companyName = "BuYuQi"; PlayerSettings.productName = "Lottery G2 Technical Slice";
            PlayerSettings.bundleVersion = "0.0.2";
            PlayerSettings.Android.bundleVersionCode = 2;
            PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Android, "com.buyuqi.lotteryprobe");
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel26;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel35;
            PlayerSettings.Android.useCustomKeystore = false;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.OpenGLES3 });
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            EditorUserBuildSettings.buildAppBundle = false;
            var output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../build/G2/Android"));
            Directory.CreateDirectory(output);
            var apk = Path.Combine(output, "LotteryG2.apk");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[] { ScenePath },
                locationPathName = apk, target = BuildTarget.Android, options = BuildOptions.Development });
            if (report.summary.result != BuildResult.Succeeded || !File.Exists(apk))
                throw new InvalidOperationException("G2 Android build failed");
            var receipt = new Receipt { sourceCommit = commit, runId = run, unityVersion = Application.unityVersion,
                apkSha256 = Hash(apk), apkBytes = new FileInfo(apk).Length, builtAtUtc = DateTime.UtcNow.ToString("O"),
                buildResult = report.summary.result.ToString(), buildTarget = report.summary.platform.ToString(),
                scriptingBackend = PlayerSettings.GetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android).ToString(),
                architecture = PlayerSettings.Android.targetArchitectures.ToString(), minSdk = (int)PlayerSettings.Android.minSdkVersion,
                targetSdk = (int)PlayerSettings.Android.targetSdkVersion,
                graphicsApis = string.Join(",", PlayerSettings.GetGraphicsAPIs(BuildTarget.Android).Select(x => x.ToString())),
                editorRevision = UnityEditorInternal.InternalEditorUtility.GetFullUnityVersion() };
            File.WriteAllText(Path.Combine(output, "build-receipt.json"), JsonUtility.ToJson(receipt, true));
            File.WriteAllLines(Path.Combine(output, "resolved-packages.txt"),
                UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages().OrderBy(p => p.name).Select(p => p.name + "@" + p.version));
        }
        private static string Arg(string key)
        {
            var args = Environment.GetCommandLineArgs(); int i = Array.IndexOf(args, key);
            if (i < 0 || i + 1 >= args.Length) throw new InvalidOperationException("Missing build identity");
            return args[i + 1];
        }
        private static string Hash(string path)
        {
            using (var sha = SHA256.Create()) using (var stream = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }
        [Serializable] private sealed class Receipt
        {
            public string scope = "G2_TECHNICAL_SLICE_NOT_DEVICE_TESTED";
            public string sourceCommit, runId, unityVersion, apkSha256, builtAtUtc;
            public long apkBytes;
            public string buildResult, buildTarget, scriptingBackend, architecture, graphicsApis, editorRevision;
            public int minSdk, targetSdk;
            public string rulesSha256 = RulesSha256, runtimeScene = ScenePath, fakeAd = "DEVELOPMENT_FAKE_ONLY";
            // These describe this build job. Separate PlayMode evidence must not be inherited as device QA.
            public string deviceQa = "NOT_RUN", renderedFrameQa = "NOT_RUN", gameplayQa = "NOT_RUN", signing = "development-debug";
        }
    }
}
