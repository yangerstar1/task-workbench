using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Lottery.G3.Interaction;
using Lottery.G3.Rendering;
namespace Lottery.G3.Editor
{
    // Original approved PNGs are source-hashed, never inferred from compressed GPU pixels.
    public static class G3Build
    {
        public const string ScenePath="Assets/G3/Scenes/G3Day.unity";
        public const string RulesSha256="e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668";
        public static void ValidateArtwork(ApprovedArtworkBinding binding,string expectedId)
        {
            var observation=G3ArtworkValidation.Inspect(binding,expectedId);
            G3ArtworkValidation.Require(observation);
            binding.RequireVerifiedPair(); // Read-only; committed verification must already be correct.
        }

        public static void Prepare() => PrepareInternal(false, null);
        // Only diagnostic prebuild hooks use this entry. The ordinary build path
        // keeps its existing Single-scene behavior and build-scene selection.
        public static void PrepareForVisualTests() => PrepareInternal(true, null);
        public static void PrepareForVisualTestsObserved(Action<int,bool,bool,bool,bool,bool> observe) => PrepareInternal(true, observe);
        static void PrepareInternal(bool preserveLoadedScenes, Action<int,bool,bool,bool,bool,bool> observe)
        {
            if(preserveLoadedScenes) Lottery.Probe.Editor.ProbeBuild.PrepareForTests(observe);
            else Lottery.Probe.Editor.ProbeBuild.Prepare();
            ApprovedArtworkBinding number=null,challenge=null;
            if(!preserveLoadedScenes)PrepareShopBindings(out number,out challenge);
            var priorScene=SceneManager.GetActiveScene();
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,
                preserveLoadedScenes?NewSceneMode.Additive:NewSceneMode.Single);
            Action build = () =>
            {
            if(preserveLoadedScenes)Lottery.Probe.Editor.ProbeBuild.RequirePreparedSceneActive(scene,20,observe);
            // All importer temporary GameObjects live in this owned scene, too;
            // create/destroy must not dirty the framework's saved runner scene.
            if(preserveLoadedScenes)PrepareShopBindings(out number,out challenge);
            G3ShopReflectionBaker.Prepare();
            var bootstrap=new GameObject("G3 Original Shop Visual Candidate").AddComponent<G3SliceBootstrap>();
            bootstrap.chineseFont=AssetDatabase.LoadAssetAtPath<Font>("Assets/Resources/ProbeChinese.otf");
            bootstrap.paperShader=AssetDatabase.LoadAssetAtPath<Shader>("Assets/G3/Rendering/TicketPaper.shader");
            bootstrap.silverShader=AssetDatabase.LoadAssetAtPath<Shader>("Assets/G3/Rendering/TicketLocalSilver.shader");
            bootstrap.maskedFontShader=AssetDatabase.LoadAssetAtPath<Shader>("Assets/G3/Rendering/MaskedTicketFont.shader");
            bootstrap.fontShader=AssetDatabase.LoadAssetAtPath<Shader>("Assets/G2/Rendering/G2Font.shader");
            bootstrap.flatShader=AssetDatabase.LoadAssetAtPath<Shader>("Assets/G2/Rendering/G2Flat.shader");
            bootstrap.surfaceShader=Shader.Find("Universal Render Pipeline/Lit");
            bootstrap.numberArtwork=number;bootstrap.challengeArtwork=challenge;
            if(bootstrap.chineseFont==null || bootstrap.paperShader==null || bootstrap.silverShader==null ||
                bootstrap.maskedFontShader==null || bootstrap.fontShader==null || bootstrap.flatShader==null || bootstrap.surfaceShader==null)
                throw new InvalidOperationException("G3 scene dependencies missing");
            Directory.CreateDirectory("Assets/G3/Scenes");
            if(!EditorSceneManager.SaveScene(scene,ScenePath))throw new IOException("G3 scene save failed");
            AssetDatabase.SaveAssets();
            if(!preserveLoadedScenes)EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(ScenePath,true)};
            };
            if(preserveLoadedScenes)
                Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(build,
                    ()=>Lottery.Probe.Editor.ProbeBuild.RestorePreparedScene(priorScene,scene,22,observe));
            else build();
        }
        static void PrepareShopBindings(out ApprovedArtworkBinding number,out ApprovedArtworkBinding challenge)
        {
            G3ShopArtImporter.Prepare();
            number=AssetDatabase.LoadAssetAtPath<ApprovedArtworkBinding>("Assets/G3/Rendering/Resources/G3/number.asset");
            challenge=AssetDatabase.LoadAssetAtPath<ApprovedArtworkBinding>("Assets/G3/Rendering/Resources/G3/challenge.asset");
            ValidateArtwork(number,"number");ValidateArtwork(challenge,"challenge");
        }
        public static void BuildAndroid()
        {
            if(Lottery.G2.Core.NumberTicketRules.RulesSha256!=RulesSha256)throw new InvalidOperationException("Frozen rules mismatch");
            string commit=Arg("-probeCommit"),run=Arg("-probeRunId");
            if(!System.Text.RegularExpressions.Regex.IsMatch(commit,"^[0-9a-f]{40}$") || !System.Text.RegularExpressions.Regex.IsMatch(run,"^[1-9][0-9]*$"))throw new InvalidOperationException("Invalid source/run identity");
            G3ArtworkValidation.WriteAndroidDiagnostic(commit,run,Arg("-probeRunAttempt"));
            Prepare();
            PlayerSettings.companyName="BuYuQi";PlayerSettings.productName="Lottery G3 Original Shop Visual Candidate";
            PlayerSettings.bundleVersion="0.0.3";PlayerSettings.Android.bundleVersionCode=3;
            PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Android,"com.buyuqi.lotteryprobe");
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android,ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures=AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion=AndroidSdkVersions.AndroidApiLevel26;PlayerSettings.Android.targetSdkVersion=AndroidSdkVersions.AndroidApiLevel35;
            PlayerSettings.Android.useCustomKeystore=false;PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android,false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android,new[]{GraphicsDeviceType.OpenGLES3});
            PlayerSettings.defaultInterfaceOrientation=UIOrientation.LandscapeLeft;EditorUserBuildSettings.buildAppBundle=false;
            var output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/G3/Android"));Directory.CreateDirectory(output);var apk=Path.Combine(output,"LotteryG3.apk");
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},locationPathName=apk,target=BuildTarget.Android,options=BuildOptions.Development});
            if(report.summary.result!=BuildResult.Succeeded || !File.Exists(apk))throw new InvalidOperationException("G3 Android build failed");
            var receipt=new Receipt{sourceCommit=commit,runId=run,unityVersion=Application.unityVersion,apkSha256=Hash(apk),apkBytes=new FileInfo(apk).Length,builtAtUtc=DateTime.UtcNow.ToString("O"),buildResult=report.summary.result.ToString(),buildTarget=report.summary.platform.ToString(),scriptingBackend=PlayerSettings.GetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android).ToString(),architecture=PlayerSettings.Android.targetArchitectures.ToString(),minSdk=(int)PlayerSettings.Android.minSdkVersion,targetSdk=(int)PlayerSettings.Android.targetSdkVersion,graphicsApis=string.Join(",",PlayerSettings.GetGraphicsAPIs(BuildTarget.Android).Select(x=>x.ToString())),editorRevision=UnityEditorInternal.InternalEditorUtility.GetFullUnityVersion()};
            File.WriteAllText(Path.Combine(output,"build-receipt.json"),JsonUtility.ToJson(receipt,true));
            File.WriteAllLines(Path.Combine(output,"resolved-packages.txt"),UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages().OrderBy(p=>p.name).Select(p=>p.name+"@"+p.version));
        }
        static string Arg(string key){var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,key);if(i<0||i+1>=args.Length)throw new InvalidOperationException("Missing build identity");return args[i+1];}
        static string Hash(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
        [Serializable]sealed class Receipt {
            public string scope="G3_ONE_DAY_WHITEBOX_NOT_DEVICE_TESTED",sourceCommit,runId,unityVersion,apkSha256,builtAtUtc;
            public long apkBytes;public string buildResult,buildTarget,scriptingBackend,architecture,graphicsApis,editorRevision;public int minSdk,targetSdk;
            public string rulesSha256=RulesSha256,standardsDigest="1984cc8f225db73485a052942d30637127679a56b0492edf36497911373f30b1",runtimeScene=ScenePath,fakeAd="DEVELOPMENT_FAKE_ONLY";
            public int versionCode=3;public string versionName="0.0.3",applicationIdentifier="com.buyuqi.lotteryprobe",normalRuntimeFixture="NONE";public bool coldBuild=true;
            public string deviceQa="NOT_RUN",renderedFrameQa="NOT_RUN",gameplayQa="NOT_RUN",signing="development-debug",finalQuality="NOT_PASSED";
        }
    }
}
