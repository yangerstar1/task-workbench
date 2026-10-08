using System;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class ProofBuild
{
    [Serializable]
    private sealed class Receipt
    {
        public string schema = "desert-rv-ci-proof/v1";
        public string scope = "Original CI sample only; no game or device acceptance";
        public string editorVersion;
        public string commit;
        public string workflowRunId;
        public int editModeTestsPassed;
        public string buildTarget;
        public string scriptingBackend;
        public string architecture;
        public string signing = "Unity development/debug signing; not store release";
        public string buildResult;
        public string apkRelativePath;
        public long apkBytes;
        public string apkSha256;
        public string completedUtc;
    }

    public static void BuildAndroid()
    {
        if (Application.unityVersion != "6000.3.19f1")
            throw new InvalidOperationException("Unexpected Unity version: " + Application.unityVersion);
        string commit = Argument("-proofCommit");
        string runId = Argument("-proofRunId");
        int passed;
        if (!Regex.IsMatch(commit, "^[0-9a-f]{40}$") || !Regex.IsMatch(runId, "^[0-9]+$"))
            throw new InvalidOperationException("Missing exact CI commit/run identity");
        if (!int.TryParse(Argument("-proofTestCount"), out passed) || passed != 4)
            throw new InvalidOperationException("The four preceding EditMode tests must pass");

        string repo = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        string output = Path.Combine(repo, "build/Android/Proof.apk");
        string receiptPath = Path.Combine(repo, "build/Android/build-receipt.json");
        if (File.Exists(output) || File.Exists(receiptPath))
            throw new InvalidOperationException("Output must be new for this run");
        Directory.CreateDirectory(Path.GetDirectoryName(output));

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var camera = new GameObject("Proof Camera").AddComponent<Camera>();
        camera.transform.position = new Vector3(0f, 1.2f, -4f);
        camera.transform.LookAt(Vector3.zero);
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.12f, 0.15f, 0.2f);
        var light = new GameObject("Proof Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.transform.rotation = Quaternion.Euler(40f, -25f, 0f);
        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = "Original proof cube";
        new GameObject("Proof Runtime").AddComponent<ProofRuntime>().cube = cube.transform;
        Directory.CreateDirectory(Path.Combine(Application.dataPath, "Generated"));
        const string scenePath = "Assets/Generated/Proof.unity";
        if (!EditorSceneManager.SaveScene(scene, scenePath))
            throw new InvalidOperationException("Could not save generated proof scene");

        PlayerSettings.companyName = "CI Proof";
        PlayerSettings.productName = "Desert RV CI Proof";
        PlayerSettings.bundleVersion = "0.0.1";
        PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, "com.desertrv.ciproof");
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.Android.minSdkVersion = (AndroidSdkVersions)26;
        PlayerSettings.Android.targetSdkVersion = (AndroidSdkVersions)35;
        PlayerSettings.Android.useCustomKeystore = false;
        EditorUserBuildSettings.buildAppBundle = false;
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { scenePath }, locationPathName = output,
            target = BuildTarget.Android, options = BuildOptions.Development
        });
        if (report.summary.result != BuildResult.Succeeded || !File.Exists(output))
            throw new InvalidOperationException("Android build did not succeed: " + report.summary.result);
        string hash;
        using (var stream = File.OpenRead(output))
        using (var sha = SHA256.Create())
            hash = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        var receipt = new Receipt
        {
            editorVersion = Application.unityVersion, commit = commit, workflowRunId = runId,
            editModeTestsPassed = passed, buildTarget = "Android", scriptingBackend = "IL2CPP",
            architecture = "ARM64", buildResult = report.summary.result.ToString(),
            apkRelativePath = "build/Android/Proof.apk", apkBytes = new FileInfo(output).Length,
            apkSha256 = hash, completedUtc = DateTime.UtcNow.ToString("O")
        };
        File.WriteAllText(receiptPath, JsonUtility.ToJson(receipt, true));
        Debug.Log("CI_PROOF_BUILD_COMPLETE " + commit + " " + hash);
    }

    private static string Argument(string name)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; ++i)
            if (args[i] == name) return args[i + 1];
        throw new ArgumentException("Required argument absent: " + name);
    }
}

