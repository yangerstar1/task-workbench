using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace DesertRV.Editor
{
    // Packages the saved traversal test scene. Never authors or initializes scenes.
    public static class AndroidBuild
    {
        const string ScenePath = "Assets/DesertRV/Scenes/TraversalHarness.unity";
        const string ReferencePath = "Assets/DesertRV/Scenes/BodyStudy.unity";
        const string FontPath = "Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf";
        const string FontHash = "a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b";

        [Serializable]
        sealed class Receipt
        {
            public int schemaVersion = 1;
            public string status = "failed";
            public string stage = "preflight";
            public string scope = "traversal-test-only-no-combat-not-complete-game";
            public string project = "desert-rv/unity";
            public string scene = ScenePath;
            public string unityVersion;
            public string version;
            public string commit;
            public string runId;
            public string runAttempt;
            public string buildIdentitySha256;
            public string target = "Android";
            public string architecture = "ARM64";
            public string backend = "IL2CPP";
            public bool development = true;
            public string signing = "debug-only";
            public string apk = "DesertRV.apk";
            public string apkSha256 = "";
            public long apkBytes;
            public string sceneSha256;
            public string referenceSceneSha256;
            public string fontSha256 = FontHash;
        }

        public static void BuildTraversalHarness()
        {
            int exitCode = 1;
            string receiptPath = null;
            var receipt = new Receipt { unityVersion = Application.unityVersion };
            try
            {
                string project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
                if (new DirectoryInfo(project).Name != "unity" ||
                    new DirectoryInfo(project).Parent.Name != "desert-rv")
                    throw new BuildFailedException("Expected desert-rv/unity project.");
                // A fresh output directory prevents a previous APK/receipt masquerading as this run.
                string outputDirectory = Path.GetFullPath(Path.Combine(project, "../build/android-traversal-harness"));
                if (Directory.Exists(outputDirectory))
                    throw new BuildFailedException("Use a clean output directory for each build.");
                Directory.CreateDirectory(outputDirectory);
                receiptPath = Path.Combine(outputDirectory, "build-receipt.json");
                string apk = Path.Combine(outputDirectory, receipt.apk);
                receipt.commit = Metadata("DESERT_RV_BUILD_COMMIT", "-desertRvCommit", @"\A[0-9a-fA-F]{40}\z").ToLowerInvariant();
                receipt.version = "0.1.0-dev." + receipt.commit.Substring(0, 12);
                receipt.runId = Metadata("DESERT_RV_BUILD_RUN_ID", "-desertRvRunId", @"\A[0-9]{1,20}\z");
                receipt.runAttempt = Metadata("DESERT_RV_BUILD_RUN_ATTEMPT", "-desertRvRunAttempt", @"\A[0-9]{1,10}\z");
                receipt.buildIdentitySha256 = HashBytes(Encoding.UTF8.GetBytes(
                    receipt.commit + ":" + receipt.runId + ":" + receipt.runAttempt));
                if (Application.unityVersion != "6000.3.19f1")
                    throw new BuildFailedException("Pinned Unity version required.");
                if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android ||
                    !BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Android, BuildTarget.Android))
                    throw new BuildFailedException("Start Unity with -buildTarget Android and Android support installed.");
                receipt.sceneSha256 = HashFile(Path.Combine(project, ScenePath));
                receipt.referenceSceneSha256 = HashFile(Path.Combine(project, ReferencePath));
                if (HashFile(Path.Combine(project, FontPath)) != FontHash)
                    throw new BuildFailedException("Restore and verify the checkpoint font before starting Unity.");
                if (!AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath) ||
                    !AssetDatabase.LoadAssetAtPath<Font>(FontPath))
                    throw new BuildFailedException("Saved scene or restored font failed to import.");

                var backend = PlayerSettings.GetScriptingBackend(NamedBuildTarget.Android);
                var architectures = PlayerSettings.Android.targetArchitectures;
                bool customKeystore = PlayerSettings.Android.useCustomKeystore;
                bool split = PlayerSettings.Android.buildApkPerCpuArchitecture;
                bool expansion = PlayerSettings.Android.splitApplicationBinary;
                bool bundle = EditorUserBuildSettings.buildAppBundle;
                bool export = EditorUserBuildSettings.exportAsGoogleAndroidProject;
                string version = PlayerSettings.bundleVersion;
                string identifier = PlayerSettings.GetApplicationIdentifier(NamedBuildTarget.Android);
                try
                {
                    PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
                    PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
                    PlayerSettings.Android.useCustomKeystore = false;
                    PlayerSettings.Android.buildApkPerCpuArchitecture = false;
                    PlayerSettings.Android.splitApplicationBinary = false;
                    EditorUserBuildSettings.buildAppBundle = false;
                    EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
                    PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, "com.desertrv.traversal.dev");
                    PlayerSettings.bundleVersion = receipt.version;
                    receipt.stage = "build";
                    var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                    {
                        scenes = new[] { ScenePath },
                        target = BuildTarget.Android,
                        targetGroup = BuildTargetGroup.Android,
                        locationPathName = apk,
                        options = BuildOptions.Development
                    });
                    if (report == null || report.summary.result != BuildResult.Succeeded)
                        throw new BuildFailedException("Android build did not succeed.");
                }
                finally
                {
                    PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, backend);
                    PlayerSettings.Android.targetArchitectures = architectures;
                    PlayerSettings.Android.useCustomKeystore = customKeystore;
                    PlayerSettings.Android.buildApkPerCpuArchitecture = split;
                    PlayerSettings.Android.splitApplicationBinary = expansion;
                    EditorUserBuildSettings.buildAppBundle = bundle;
                    EditorUserBuildSettings.exportAsGoogleAndroidProject = export;
                    PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, identifier);
                    PlayerSettings.bundleVersion = version;
                }
                receipt.stage = "verify-output";
                if (HashFile(Path.Combine(project, ScenePath)) != receipt.sceneSha256 ||
                    HashFile(Path.Combine(project, ReferencePath)) != receipt.referenceSceneSha256)
                    throw new BuildFailedException("Saved scene bytes changed during build.");
                receipt.apkBytes = new FileInfo(apk).Length;
                if (receipt.apkBytes == 0) throw new BuildFailedException("APK is empty.");
                receipt.apkSha256 = HashFile(apk);
                receipt.stage = "complete";
                receipt.status = "succeeded";
                exitCode = 0;
            }
            catch (Exception)
            {
                // Do not put exception text, machine paths or environment dumps in the safe receipt/log marker.
                Debug.LogError("DESERT_RV_ANDROID_FAILED stage=" + receipt.stage);
            }
            finally
            {
                try
                {
                    if (receiptPath != null)
                        File.WriteAllText(receiptPath, JsonUtility.ToJson(receipt, true) + "\n", new UTF8Encoding(false));
                }
                catch (Exception)
                {
                    exitCode = 1;
                    Debug.LogError("DESERT_RV_ANDROID_FAILED stage=receipt-write");
                }
            }
            if (exitCode == 0) Debug.Log("DESERT_RV_ANDROID_SUCCEEDED sha256=" + receipt.apkSha256);
            if (Application.isBatchMode) EditorApplication.Exit(exitCode);
            else if (exitCode != 0) throw new BuildFailedException("Android build failed; inspect the safe receipt stage.");
        }

        static string Metadata(string name, string argument, string pattern)
        {
            // GameCI forwards customParameters, but not arbitrary environment variables.
            // Read only the three explicitly named fields; never dump argv or environment.
            string environment = Environment.GetEnvironmentVariable(name);
            string commandLine = null;
            string[] arguments = Environment.GetCommandLineArgs();
            for (int index = 1; index < arguments.Length; index++)
            {
                if (arguments[index] == argument)
                {
                    if (commandLine != null || index + 1 >= arguments.Length)
                        throw new BuildFailedException("Build metadata argument is duplicated or missing a value.");
                    commandLine = arguments[++index];
                    if (!Regex.IsMatch(commandLine, pattern))
                        throw new BuildFailedException("Build metadata argument is invalid.");
                }
                else if (arguments[index].StartsWith(argument + "=", StringComparison.Ordinal))
                    throw new BuildFailedException("Use a separate argument value for build metadata.");
            }
            if (environment != null && !Regex.IsMatch(environment, pattern))
                throw new BuildFailedException("Build metadata environment value is invalid.");
            if (environment != null && commandLine != null &&
                !String.Equals(environment, commandLine, StringComparison.Ordinal))
                throw new BuildFailedException("Build metadata sources conflict.");
            string value = commandLine ?? environment ?? "";
            if (!Regex.IsMatch(value, pattern))
                throw new BuildFailedException("Required build metadata is missing or invalid.");
            return value;
        }
        static string HashFile(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }
        static string HashBytes(byte[] bytes)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
    }
}
