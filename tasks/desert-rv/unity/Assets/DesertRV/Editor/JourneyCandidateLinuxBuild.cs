using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Editor
{
    [InitializeOnLoad]
    public static class JourneyCandidateLinuxBuild
    {
        const string Input = "JourneyEvidence/JourneyPreparation/linux-build-input.json";
        const string Receipt = "../journey-preparation-export/generated/receipt.json";
        const string Settings = "ProjectSettings/ProjectSettings.asset";
        static readonly string[] Paths = new[] { JourneyCandidateLinuxIdentity.Bootstrap }.Concat(JourneyCandidateLinuxIdentity.Regions).ToArray();
        static string Output => Path.GetFullPath("../journey-linux-private-build/DesertRV.x86_64");
        [Serializable] public sealed class Dependency { public string path, sha256, kind, packageName, packageVersion, owner; public long bytes; }
        [Serializable] public sealed class Request
        {
            public int schema; public string label, sourceCommit, producerRunUrl, generatedReceiptSha256, define, target, boundaryNativeXmlSha256;
            public int boundaryNativeCases;
            public bool development, approved;
            public JourneyCandidateAssetIntegration.FilePin[] files;
            public string[] directories;
            public Dependency[] dependencies;
            public JourneyCandidateAssetIntegration.OutputFile[] scenes;
        }
        [Serializable] sealed class Result
        {
            public int schema = 1;
            public string label = "CANDIDATE_LINUX_DEVELOPMENT_BUILT_UNREVIEWED", sourceCommit, producerRunUrl, generatedReceiptSha256, executableSha256, requestSha256, boundaryNativeXmlSha256;
            public int boundaryNativeCases;
            public string unityVersion = "6000.3.19f1", target = "StandaloneLinux64", backend = "Mono2x", define = "DESERTRV_CANDIDATE_LINUX", executable = "DesertRV.x86_64";
            public string[] scenes;
            public string[] temporarySettingsFiles = { "ProjectSettings/ProjectSettings.asset" };
            // Records the APIs invoked; complete temporary bytes are separately pinned, not an asserted YAML diff.
            public string[] temporarySettingsApiFields = { "scriptingBackend.Standalone", "fullScreenMode", "defaultScreenWidth", "defaultScreenHeight", "productName", "resizableWindow" };
            public bool candidateOnly = true, development = true, approved = false, settingsRestored, sourceBytesUnchanged;
            public bool visualReviewed = false, gameplayReviewed = false, audioAuditioned = false;
        }
        [Serializable] sealed class Diagnostic
        {
            public int schema = 1;
            public string label = "CANDIDATE_LINUX_BUILD_DIAGNOSTIC", stage = "ENTRY", exceptionKind = "NONE", buildResult = "UNAVAILABLE";
            public bool settingsRestored, sourceBytesUnchanged, receiptWritten;
        }
        static void PersistJson(string path, string json)
        {
            string temporary = path + ".tmp";
            File.WriteAllText(temporary,json);
            if (File.Exists(path)) File.Replace(temporary,path,null); else File.Move(temporary,path);
        }
        static void Persist(Diagnostic diagnostic) => PersistJson("JourneyEvidence/JourneyPreparation/linux-build-diagnostic.json",JsonUtility.ToJson(diagnostic,true));
        sealed class Lease
        {
            public Request request; public string requestHash, fingerprint;
            public readonly Dictionary<string,string> temporarySettings = new Dictionary<string,string>();
            public readonly HashSet<string> processed = new HashSet<string>(StringComparer.Ordinal);
        }
        static Lease active;
        static JourneyCandidateLinuxBuild() { AssemblyReloadEvents.beforeAssemblyReload += Close; EditorApplication.quitting += Close; }
        static void Close() { active = null; }
        static void Check(bool valid, string message) { if (!valid) throw new BuildFailedException(message); }
        static string Hash(string path) => JourneyDiagnosticScope.HashFile(path);
        public static bool ValidBuildProfile(BuildTarget target, BuildOptions options, string[] defines) =>
            target == BuildTarget.StandaloneLinux64 && options == BuildOptions.Development && defines != null && defines.SequenceEqual(new[] { JourneyCandidateLinuxIdentity.Define });
        static string RepoFile(string name)
        {
            Check(!string.IsNullOrEmpty(name) && !Path.IsPathRooted(name) && !name.Contains("..") && !name.Contains("\\") &&
                (name.StartsWith("tasks/desert-rv/",StringComparison.Ordinal) || name.StartsWith(".github/",StringComparison.Ordinal)), "Invalid pinned repository path.");
            string root = Path.GetFullPath("../../.."), full = Path.GetFullPath(Path.Combine(root,name));
            Check(full.StartsWith(root + Path.DirectorySeparatorChar,StringComparison.Ordinal) && File.Exists(full), "Missing pinned repository file.");
            for (string path = full; path != root; path = Path.GetDirectoryName(path))
                Check((File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0, "Linked repository input rejected.");
            return full;
        }
        static void VerifyInventory(Request request, string projectRoot = ".")
        {
            const string prefix = "tasks/desert-rv/unity/";
            var expected = new HashSet<string>(request.files.Where(p => p.path.StartsWith(prefix,StringComparison.Ordinal)).Select(p => p.path.Substring(prefix.Length))
                .Where(p => p.StartsWith("Assets/",StringComparison.Ordinal) || p.StartsWith("Packages/",StringComparison.Ordinal) || p.StartsWith("ProjectSettings/",StringComparison.Ordinal)),StringComparer.Ordinal);
            var actual = new HashSet<string>(StringComparer.Ordinal); var directories = new HashSet<string>(StringComparer.Ordinal);
            string root = Path.GetFullPath(projectRoot);
            var pending = new Stack<string>(new[] { "Assets", "Packages", "ProjectSettings" }.Select(n=>Path.Combine(root,n)));
            while (pending.Count > 0)
            {
                string folder = pending.Pop();
                Check(Directory.Exists(folder) && (File.GetAttributes(folder) & FileAttributes.ReparsePoint) == 0,"Linked or missing protected directory.");
                foreach (string child in Directory.GetFileSystemEntries(folder))
                {
                    string path = child.Substring(root.Length+1).Replace('\\','/'); var attributes = File.GetAttributes(child);
                    Check((attributes & FileAttributes.ReparsePoint) == 0,"Linked protected input rejected.");
                    if ((attributes & FileAttributes.Directory) != 0) { directories.Add(path);pending.Push(child); }
                    else { Check(File.Exists(child),"Nonregular protected input rejected.");actual.Add(path); }
                }
            }
            Check(actual.SetEquals(expected) && request.directories != null && directories.SetEquals(request.directories),"Actual protected file/directory inventory changed.");
        }
        static void Verify(Lease lease, bool building)
        {
            var r = lease.request; VerifyInventory(r);
            Check(Hash(Input) == lease.requestHash && Hash(Receipt) == r.generatedReceiptSha256, "Actual Linux build request/producer receipt changed.");
            foreach (var pin in r.files)
            {
                string relative = pin.path.StartsWith("tasks/desert-rv/unity/",StringComparison.Ordinal) ? pin.path.Substring("tasks/desert-rv/unity/".Length) : null;
                string expected = building && relative != null && lease.temporarySettings.TryGetValue(relative,out var temporary) ? temporary : pin.sha256;
                Check(Hash(RepoFile(pin.path)) == expected, "Pinned source or candidate bytes changed.");
            }
            foreach (var dependency in r.dependencies)
            {
                string path = dependency.path;
                if (dependency.kind == "builtin")
                {
                    Check((path == "Resources/unity_builtin_extra" || path == "Library/unity default resources") && dependency.sha256 == "" && dependency.bytes == 0, "Unexpected builtin dependency.");
                    continue;
                }
                Check(!path.Contains("..") && !path.Contains("\\") && !Path.IsPathRooted(path), "Unsafe dependency path.");
                if (dependency.kind == "package")
                {
                    var info = UnityEditor.PackageManager.PackageInfo.FindForAssetPath(path.EndsWith(".meta",StringComparison.Ordinal) ? path.Substring(0,path.Length-5) : path);
                    Check(info != null && info.name == dependency.packageName && info.version == dependency.packageVersion && path.StartsWith("Packages/" + info.name + "/",StringComparison.Ordinal), "Official native package identity changed.");
                    path = Path.Combine(info.resolvedPath,path.Substring(("Packages/" + info.name + "/").Length));
                }
                else Check(dependency.kind == "asset" && path.StartsWith("Assets/",StringComparison.Ordinal), "Unknown dependency class.");
                Check(File.Exists(path) && new FileInfo(path).Length == dependency.bytes && Hash(path) == dependency.sha256, "Native dependency bytes differ from real generated export.");
            }
            foreach (var scene in r.scenes)
                Check(Hash(scene.path) == scene.sha256 && AssetDatabase.GetAssetDependencyHash(scene.path).ToString() == scene.dependencyHash &&
                    JourneyContentChecks.DependencySha256(scene.path) == scene.dependencySha256, "Saved scene/content dependency changed.");
            Check(lease.fingerprint == JourneyContentChecks.BuildFingerprint(), "Build scene fingerprint changed.");
        }
        public static bool AllowsCandidateBuild(BuildReport report)
        {
            if (active == null) return false;
            Check(report != null && report.summary.platform == BuildTarget.StandaloneLinux64 && report.summary.options == BuildOptions.Development &&
                Path.GetFullPath(report.summary.outputPath) == Output, "Candidate lease cannot authorize another build profile.");
            Verify(active,true); return true;
        }
        static void CheckSceneObjects(Scene scene, JourneyContentManifest content)
        {
            var roots = scene.GetRootGameObjects();
            foreach (var root in roots)
                foreach (var node in root.GetComponentsInChildren<Transform>(true))
                    Check(node.GetComponents<Component>().All(c => c), "Missing compiled scene component.");
            var directors = roots.SelectMany(r => r.GetComponentsInChildren<JourneyDirector>(true)).ToArray();
            var bindings = roots.SelectMany(r => r.GetComponentsInChildren<RegionBinding>(true)).ToArray();
            if (scene.path == Paths[0])
            {
                Check(directors.Length == 1 && bindings.Length == 0 && roots.SelectMany(r => r.GetComponentsInChildren<JourneySession>(true)).Count() == 1 &&
                    roots.SelectMany(r => r.GetComponentsInChildren<JourneyMotor>(true)).Count() == 1, "Unique real bootstrap ownership required.");
                Check(JourneyCandidateLinuxIdentity.ValidateBootstrap(directors[0],content,out var reason),reason ?? "Bootstrap bindings invalid.");
            }
            else
            {
                int index = Array.IndexOf(Paths,scene.path);
                Check(index > 0 && directors.Length == 0 && bindings.Length == 1 && bindings[0].region == index, "Exact region scene identity required.");
                Check(!roots.Any(r => r.GetComponentInChildren<JourneySession>(true) || r.GetComponentInChildren<JourneyMotor>(true) ||
                    r.GetComponentInChildren<JourneyHud>(true) || r.GetComponentInChildren<Camera>(true) || r.GetComponentInChildren<AudioListener>(true)), "Regional scene duplicates persistent ownership.");
                Check(JourneyCandidateLinuxIdentity.ValidateRegionContent(bindings[0],content,out var reason),reason ?? "Regional real bindings invalid.");
            }
        }
        internal static void ProcessCandidateScene(Scene scene, BuildReport report)
        {
            if (active == null) return;
            Check(AllowsCandidateBuild(report) && Paths.Contains(scene.path) && active.processed.Add(scene.path), "Candidate scene absent/duplicated in this build.");
            var content = AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(JourneySceneAuthoring.ManifestPath);
            CheckSceneObjects(scene,content);
            Check(!scene.GetRootGameObjects().Any(r => r.GetComponentInChildren<JourneyCandidateLinuxIdentity>(true)), "Saved source must not contain runtime diagnostic identity.");
            var director = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<JourneyDirector>(true)).SingleOrDefault();
            var binding = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<RegionBinding>(true)).SingleOrDefault();
            var owner = director ? director.gameObject : binding.gameObject;
            var identity = owner.AddComponent<JourneyCandidateLinuxIdentity>();
            identity.sourceCommit = active.request.sourceCommit; identity.producerRunUrl = active.request.producerRunUrl;
            identity.generatedReceiptSha256 = active.request.generatedReceiptSha256; identity.content = content; identity.director = director; identity.region = binding;
            // No SaveScene/SaveAssets call: the identity exists only in the scene copy passed to the build callback.
        }
        public static void BuildPreparedLinuxDiagnostic()
        {
            var diagnostic = new Diagnostic(); Persist(diagnostic);
            try { BuildPrepared(diagnostic); }
            catch (Exception error)
            {
                diagnostic.exceptionKind = error is BuildFailedException ? "BUILD_FAILED" : error is UnauthorizedAccessException ? "UNAUTHORIZED_ACCESS" : error is IOException ? "IO" : "OTHER";
                throw;
            }
            finally { Close(); Persist(diagnostic); }
        }
        static void BuildPrepared(Diagnostic diagnostic)
        {
            Check(active == null && !Application.isPlaying && !BuildPipeline.isBuildingPlayer && Application.unityVersion == "6000.3.19f1", "Explicit pinned EditMode candidate build only.");
            string requestHash = File.ReadAllText("JourneyEvidence/JourneyPreparation/linux-build-input.sha256").Trim();
            Check(Regex.IsMatch(requestHash,"^[a-f0-9]{64}$") && Hash(Input) == requestHash, "Missing real host-verified build request.");
            var request = JsonUtility.FromJson<Request>(File.ReadAllText(Input));
            Check(request != null && request.schema == 1 && request.label == "CANDIDATE_LINUX_DEVELOPMENT_ONLY" && !request.approved && request.development &&
                request.boundaryNativeCases == 17 && Regex.IsMatch(request.boundaryNativeXmlSha256 ?? "","^[a-f0-9]{64}$") && request.target == "StandaloneLinux64" && request.define == JourneyCandidateLinuxIdentity.Define &&
                request.sourceCommit == Environment.GetEnvironmentVariable("GITHUB_SHA") && Regex.IsMatch(request.sourceCommit ?? "","^[a-f0-9]{40}$") &&
                request.producerRunUrl == "https://github.com/yangerstar1/task-workbench/actions/runs/" + Environment.GetEnvironmentVariable("GITHUB_RUN_ID") &&
                Regex.IsMatch(request.generatedReceiptSha256 ?? "","^[a-f0-9]{64}$") && request.files != null && request.files.Length > 100 && request.files.Select(p=>p.path).Distinct().Count()==request.files.Length &&
                request.directories != null && request.directories.Distinct().Count()==request.directories.Length && request.dependencies != null && request.dependencies.Length > 0 && request.scenes != null && request.scenes.Length == 5 &&
                new HashSet<string>(request.scenes.Select(p=>p.path)).SetEquals(Paths.Concat(new[] { JourneySceneAuthoring.ManifestPath })), "Current same-source same-job generated export is required.");
            Check(BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Standalone,BuildTarget.StandaloneLinux64) && !Directory.Exists(Path.GetDirectoryName(Output)), "Fresh supported Linux build output required.");
            var setup = EditorSceneManager.GetSceneManagerSetup(); Check(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "Dirty scenes cannot enter candidate build.");
            var lease = new Lease { request=request,requestHash=requestHash,fingerprint=JourneyContentChecks.BuildFingerprint() }; Verify(lease,false);diagnostic.stage="SOURCE_VERIFIED";Persist(diagnostic);
            JourneyCandidateAssetIntegration.RequireOnlyMissingApprovals(JourneyContentChecks.Inspect(true).ToArray());
            try { foreach (var path in Paths) CheckSceneObjects(EditorSceneManager.OpenScene(path,OpenSceneMode.Single),AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(JourneySceneAuthoring.ManifestPath)); }
            finally { JourneySceneAuthoring.RestoreSceneSetup(setup); }
            diagnostic.stage="CONTENT_VERIFIED";Persist(diagnostic);
            byte[] settings = File.ReadAllBytes(Settings);
            var oldBackend = PlayerSettings.GetScriptingBackend(NamedBuildTarget.Standalone);
            var oldWindow = PlayerSettings.fullScreenMode; int oldWidth=PlayerSettings.defaultScreenWidth,oldHeight=PlayerSettings.defaultScreenHeight;
            string oldProduct=PlayerSettings.productName; bool oldResize=PlayerSettings.resizableWindow; BuildReport result=null;
            try
            {
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
                PlayerSettings.fullScreenMode=FullScreenMode.Windowed;PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;
                PlayerSettings.productName="DESERTRV_JOURNEY_CANDIDATE";PlayerSettings.resizableWindow=false;
                AssetDatabase.SaveAssets();
                lease.temporarySettings[Settings]=Hash(Settings);active=lease;
                string[] defines={JourneyCandidateLinuxIdentity.Define};Check(ValidBuildProfile(BuildTarget.StandaloneLinux64,BuildOptions.Development,defines),"Candidate build profile rejected.");
                diagnostic.stage="BUILD_PLAYER_ENTERED";Persist(diagnostic);
                result=BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes=Paths,target=BuildTarget.StandaloneLinux64,locationPathName=Output,options=BuildOptions.Development,extraScriptingDefines=defines });
                diagnostic.stage="BUILD_PLAYER_RETURNED";diagnostic.buildResult=result != null && result.summary.result==BuildResult.Succeeded ? "SUCCEEDED" : "FAILED";Persist(diagnostic);
                Check(result != null && result.summary.result==BuildResult.Succeeded && lease.processed.SetEquals(Paths),"Candidate Linux build or exact scene processing failed.");
            }
            finally
            {
                Close();
                try
                {
                    PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,oldBackend);PlayerSettings.fullScreenMode=oldWindow;
                    PlayerSettings.defaultScreenWidth=oldWidth;PlayerSettings.defaultScreenHeight=oldHeight;PlayerSettings.productName=oldProduct;PlayerSettings.resizableWindow=oldResize;
                    AssetDatabase.SaveAssets();
                }
                finally
                {
                    File.WriteAllBytes(Settings,settings);
                    try { JourneySceneAuthoring.RestoreSceneSetup(setup); } finally { Verify(lease,false);diagnostic.settingsRestored=true;diagnostic.sourceBytesUnchanged=true;Persist(diagnostic); }
                }
            }
            PersistJson("JourneyEvidence/JourneyPreparation/linux-build-receipt.json",JsonUtility.ToJson(new Result { sourceCommit=request.sourceCommit,producerRunUrl=request.producerRunUrl,
                generatedReceiptSha256=request.generatedReceiptSha256,boundaryNativeXmlSha256=request.boundaryNativeXmlSha256,boundaryNativeCases=request.boundaryNativeCases,requestSha256=requestHash,executableSha256=Hash(Output),settingsRestored=true,sourceBytesUnchanged=true,scenes=Paths },true));
            diagnostic.stage="RECEIPT_WRITTEN";diagnostic.receiptWritten=true;Persist(diagnostic);
        }
    }
    public sealed class JourneyCandidateLinuxSceneGate : IProcessSceneWithReport
    {
        public int callbackOrder => 1000000;
        public void OnProcessScene(Scene scene,BuildReport report) { if(report != null) JourneyCandidateLinuxBuild.ProcessCandidateScene(scene,report); }
    }
}
