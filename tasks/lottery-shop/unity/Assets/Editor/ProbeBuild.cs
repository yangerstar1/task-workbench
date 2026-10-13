using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.Rendering.Universal;
namespace Lottery.Probe.Editor
{
    public static class ProbeBuild
    {
        public const string Generated = "Assets/GeneratedProbe";
        public const string PipelinePath = Generated + "/Pipeline.asset";
        public const string RendererPath = Generated + "/Renderer.asset";
        public const string ScenePath = Generated + "/Probe.unity";
        public static void Prepare() => PrepareInternal(false, null);
        // Test prebuild hooks already own a runner scene. Never unload or recreate it.
        public static void PrepareForTests() => PrepareInternal(true, null);
        public static void PrepareForTests(Action<int,bool,bool,bool,bool,bool> observe) => PrepareInternal(true, observe);
        static void PrepareInternal(bool preserveLoadedScenes, Action<int,bool,bool,bool,bool,bool> observe)
        {
            if (Application.unityVersion != "6000.3.19f1") throw new Exception("Unexpected Unity version");
            Directory.CreateDirectory(Generated);
            AssetDatabase.Refresh();
            var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(RendererPath);
            if (renderer == null) { renderer = ScriptableObject.CreateInstance<UniversalRendererData>(); AssetDatabase.CreateAsset(renderer, RendererPath); }
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if (pipeline == null) { pipeline = UniversalRenderPipelineAsset.Create(renderer); AssetDatabase.CreateAsset(pipeline, PipelinePath); }
            pipeline.msaaSampleCount = 1;
            pipeline.supportsHDR = false;
            pipeline.renderScale = 1;
            pipeline.supportsCameraDepthTexture = false;
            pipeline.supportsCameraOpaqueTexture = false;
            // supportsMainLightShadows has no public setter in this URP API.
            // Use the public distance control and disable shadows on our light.
            pipeline.shadowDistance = 0f;
            renderer.depthPrimingMode = DepthPrimingMode.Disabled;
            EditorUtility.SetDirty(renderer);
            GraphicsSettings.defaultRenderPipeline = pipeline;
            int originalQuality = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++) { QualitySettings.SetQualityLevel(i); QualitySettings.renderPipeline = pipeline; }
            QualitySettings.SetQualityLevel(originalQuality);
            EditorUtility.SetDirty(pipeline);
            var priorScene = SceneManager.GetActiveScene();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,
                preserveLoadedScenes ? NewSceneMode.Additive : NewSceneMode.Single);
            Action build = () =>
            {
            if (preserveLoadedScenes) RequirePreparedSceneActive(scene, 10, observe);
            var camera = new GameObject("Probe Camera").AddComponent<Camera>();
            camera.transform.position = new Vector3(0, 2.0f, -3.3f);
            camera.transform.LookAt(new Vector3(0, .6f, 0));
            camera.backgroundColor = new Color(.08f, .10f, .12f);
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.GetUniversalAdditionalCameraData().renderPostProcessing = false;
            var light = new GameObject("Probe Key Light").AddComponent<Light>();
            light.type = LightType.Directional; light.intensity = 1.8f;
            light.shadows = LightShadows.None;
            light.transform.rotation = Quaternion.Euler(45, -25, 0);
            RenderSettings.ambientLight = new Color(.35f, .35f, .35f);
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) throw new Exception("Missing URP Lit shader");
            var material = AssetDatabase.LoadAssetAtPath<Material>(Generated + "/ProbeSurface.mat");
            if (material == null) { material = new Material(shader); AssetDatabase.CreateAsset(material, Generated + "/ProbeSurface.mat"); }
            material.color = new Color(.65f, .27f, .10f); EditorUtility.SetDirty(material);
            var table = GameObject.CreatePrimitive(PrimitiveType.Cube); table.name = "Render capability sample";
            table.transform.position = new Vector3(0, .6f, 0); table.transform.localScale = new Vector3(2.2f, .15f, 1.2f);
            table.GetComponent<Renderer>().sharedMaterial = material;
            var runtime = new GameObject("Probe Overlay").AddComponent<Lottery.Probe.ProbeRuntime>();
            runtime.chineseFont = AssetDatabase.LoadAssetAtPath<Font>("Assets/Resources/ProbeChinese.otf");
            if (runtime.chineseFont == null) throw new Exception("Missing licensed Chinese font");
            bool saved = EditorSceneManager.SaveScene(scene, ScenePath);
            if (preserveLoadedScenes && !saved) throw new IOException("Probe scene save failed");
            AssetDatabase.SaveAssets();
            if (!preserveLoadedScenes)
                EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            };
            if(preserveLoadedScenes)
                RunPreparationWithCleanup(build,()=>RestorePreparedScene(priorScene,scene,12,observe));
            else build();
        }
        // SetActiveScene's native bool alone does not establish the postcondition.
        // A newly created Editor scene may already be active. Never create a root
        // until validity, loading and the actual active handle all agree.
        public static void RequirePreparedSceneActive(Scene scene, int stageCode, Action<int,bool,bool,bool,bool,bool> observe)
        {
            bool valid=scene.IsValid(), loaded=valid&&scene.isLoaded;
            bool active=valid&&loaded&&SceneManager.GetActiveScene().handle==scene.handle;
            observe?.Invoke(stageCode,valid,loaded,active,false,false);
            if(!valid||!loaded)throw new InvalidOperationException("Isolated preparation scene is not valid and loaded");
            bool attempted=!active, returned=false;
            if(attempted)returned=SceneManager.SetActiveScene(scene);
            valid=scene.IsValid();loaded=valid&&scene.isLoaded;
            active=valid&&loaded&&SceneManager.GetActiveScene().handle==scene.handle;
            observe?.Invoke(stageCode+1,valid,loaded,active,attempted,returned);
            if(!active)throw new InvalidOperationException("Isolated preparation scene active-handle postcondition failed");
        }
        public static void RestorePreparedScene(Scene priorScene,Scene ownedScene,int stageCode,Action<int,bool,bool,bool,bool,bool> observe)
        {
            bool attempted=false,returned=false;
            RunPreparationWithCleanup(
                () => RunPreparationWithCleanup(
                    () =>
                    {
                        if(priorScene.IsValid()&&priorScene.isLoaded&&SceneManager.GetActiveScene().handle!=priorScene.handle)
                        {attempted=true;returned=SceneManager.SetActiveScene(priorScene);}
                    },
                    () =>
                    {
                        // Only this invocation's owned scene may be closed, even
                        // when restoring the active scene throws. Keep both failures.
                        if(ownedScene.IsValid()&&ownedScene.isLoaded)EditorSceneManager.CloseScene(ownedScene,true);
                    }),
                () =>
                {
                    // Observe the actual state after the close attempt even if
                    // activation/close failed. Preserve a third observation failure.
                    bool valid=priorScene.IsValid(),loaded=valid&&priorScene.isLoaded;
                    bool active=valid&&loaded&&SceneManager.GetActiveScene().handle==priorScene.handle;
                    observe?.Invoke(stageCode,valid,loaded,active,attempted,returned);
                    if(!active)throw new InvalidOperationException("Original preparation scene restoration postcondition failed");
                });
        }
        // A cleanup error must not replace the preparation error (or an earlier
        // restoration error). Both original exception objects keep their stacks.
        public static void RunPreparationWithCleanup(Action operation,Action cleanup)
        {
            Exception operationFailure=null,cleanupFailure=null;
            try { operation(); }
            catch(Exception error) { operationFailure=error; }
            finally
            {
                try { cleanup(); }
                catch(Exception error) { cleanupFailure=error; }
            }
            if(operationFailure!=null&&cleanupFailure!=null)
                throw new AggregateException("Preparation and cleanup both failed",operationFailure,cleanupFailure);
            if(operationFailure!=null)System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(operationFailure).Throw();
            if(cleanupFailure!=null)System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(cleanupFailure).Throw();
        }
        public static void BuildAndroid()
        {
            Prepare();
            var commit = Arg("-probeCommit"); var run = Arg("-probeRunId");
            if (!System.Text.RegularExpressions.Regex.IsMatch(commit, "^[0-9a-f]{40}$") || !System.Text.RegularExpressions.Regex.IsMatch(run, "^[1-9][0-9]*$")) throw new Exception("Invalid source/run identity");
            PlayerSettings.companyName = "BuYuQi"; PlayerSettings.productName = "Lottery G0 Technical Probe";
            PlayerSettings.bundleVersion = "0.0.1"; PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Android, "com.buyuqi.lotteryprobe");
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel26;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel35;
            PlayerSettings.Android.useCustomKeystore = false;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.OpenGLES3 });
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            EditorUserBuildSettings.buildAppBundle = false;
            var output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../build/Android")); Directory.CreateDirectory(output);
            var apk = Path.Combine(output, "LotteryG0.apk");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[] { ScenePath }, locationPathName = apk, target = BuildTarget.Android, options = BuildOptions.Development });
            if (report.summary.result != BuildResult.Succeeded || !File.Exists(apk)) throw new Exception("Android build failed");
            var receipt = new Receipt { sourceCommit = commit, runId = run, unityVersion = Application.unityVersion, apkSha256 = Hash(apk), apkBytes = new FileInfo(apk).Length, builtAtUtc = DateTime.UtcNow.ToString("O"), buildResult = report.summary.result.ToString(), buildTarget = report.summary.platform.ToString(), scriptingBackend = PlayerSettings.GetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android).ToString(), architecture = PlayerSettings.Android.targetArchitectures.ToString(), minSdk = (int)PlayerSettings.Android.minSdkVersion, targetSdk = (int)PlayerSettings.Android.targetSdkVersion, graphicsApis = string.Join(",", PlayerSettings.GetGraphicsAPIs(BuildTarget.Android).Select(x => x.ToString())), editorRevision = UnityEditorInternal.InternalEditorUtility.GetFullUnityVersion() };
            File.WriteAllText(Path.Combine(output, "build-receipt.json"), JsonUtility.ToJson(receipt, true));
            var packages = UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages().OrderBy(p => p.name).Select(p => p.name + "@" + p.version);
            File.WriteAllLines(Path.Combine(output, "resolved-packages.txt"), packages);
        }
        private static string Arg(string key) { var a = Environment.GetCommandLineArgs(); int i = Array.IndexOf(a, key); if (i < 0 || i + 1 >= a.Length) throw new Exception("Missing " + key); return a[i + 1]; }
        private static string Hash(string path) { using (var sha = SHA256.Create()) using (var stream = File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant(); }
        [Serializable] private sealed class Receipt
        {
            public string scope = "G0_TECHNICAL_PROBE_NOT_GAME_NOT_DEVICE_TESTED";
            public string sourceCommit, runId, unityVersion, apkSha256, builtAtUtc;
            public long apkBytes;
            public string buildResult, buildTarget, scriptingBackend, architecture, graphicsApis, editorRevision;
            public int minSdk, targetSdk;
            public string deviceQa = "NOT_RUN", renderedFrameQa = "NOT_RUN", gameplayQa = "NOT_RUN", signing = "development-debug";
        }
    }
}
