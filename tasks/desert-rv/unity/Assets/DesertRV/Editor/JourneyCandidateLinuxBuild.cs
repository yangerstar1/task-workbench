using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Xml;
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
        const BuildOptions CandidateOptions = BuildOptions.Development | BuildOptions.DetailedBuildReport;
        const string PerformancePackage = "com.unity.test-framework.performance";
        const string PerformanceVersion = "3.5.0";
        const string PerformancePreferenceKey = "PT_ResourcesCleanup";
        static readonly string[] PerformanceJson = { "Assets/Resources/PerformanceTestRunInfo.json", "Assets/Resources/PerformanceTestRunSettings.json" };
        static readonly string[] PerformanceFiles = { "Assets/Resources.meta", "Assets/Resources/PerformanceTestRunInfo.json", "Assets/Resources/PerformanceTestRunInfo.json.meta", "Assets/Resources/PerformanceTestRunSettings.json", "Assets/Resources/PerformanceTestRunSettings.json.meta" };
        static readonly Dictionary<string,string> PerformanceSourcePins = new Dictionary<string,string> {
            { "Editor/TestRunBuilder.cs", "a4c7da5e73122b4483d5decd26fd4752af6fbfd1f1f3230f6b1e10cc077f98b4" },
            { "Runtime/Utils.cs", "f9cbc12cec868d511fa1716d8fd0aa1b9d11146b194ca5aa6d0e39f016792e30" },
            { "Runtime/Data/Run.cs", "b4df5c92a3294f1d218244178498490ec132c34fa70ab89ee7444a5606051d4b" },
            { "Runtime/Data/RunSettings.cs", "28b66c615a25b7cb5655c7831eaf31ec7a6350148056cc0addd22152842da986" },
            { "Runtime/Data/Player.cs", "30eb5220d1609a33bcabddf8a143bd2acaa7e22dacb1ebebd6b0b2fa91dde1b5" },
            { "Runtime/Data/Editor.cs", "1948fc8baadee77bb45266e3736e760958163ebc70a50d7d533bfc533c596701" },
            { "Runtime/Data/Hardware.cs", "c6103bbfca3f0df090de5a5ea7447e1e26504faab7640b0d7a78532cbfb43778" }
        };
        [Serializable] sealed class PerformanceObservation
        {
            public string status="NOT_ARMED", packageIdentity="NOT_OBSERVED";
            public bool packageVerified, baselineAbsent, preferenceRestored, synchronousImportCompleted, exactInventoryRestored, packedReportAvailable;
            public int packedContainers, packedObjects, packedSourceObjects, packedJsonHits;
            public string[] packedScenePaths=Array.Empty<string>(), callbackScenePaths=Array.Empty<string>(), jsonGuids=Array.Empty<string>();
            public InventoryObservation generated=new InventoryObservation();
        }
        sealed class PerformancePreference
        {
            readonly bool existed=EditorPrefs.HasKey(PerformancePreferenceKey), value=EditorPrefs.GetBool(PerformancePreferenceKey);
            public static void Suppress() { EditorPrefs.SetBool(PerformancePreferenceKey,false);Check(!EditorPrefs.GetBool(PerformancePreferenceKey),"PERFORMANCE_PREFERENCE"); }
            public void Restore()
            {
                if(existed) EditorPrefs.SetBool(PerformancePreferenceKey,value); else EditorPrefs.DeleteKey(PerformancePreferenceKey);
                Check(EditorPrefs.HasKey(PerformancePreferenceKey)==existed && (!existed || EditorPrefs.GetBool(PerformancePreferenceKey)==value),"PERFORMANCE_PREFERENCE");
            }
        }
        static void NoLinks(string path)
        {
            for(var current=new FileInfo(Path.GetFullPath(path)) as FileSystemInfo;current!=null;current=current is FileInfo file ? file.Directory : ((DirectoryInfo)current).Parent)
                Check((current.Attributes & FileAttributes.ReparsePoint)==0,"PERFORMANCE_LINK");
        }
        static string PerformanceIdentityKind(bool found,string name,string version)
        {
            if(!found)return "MISSING";
            if(name!=PerformancePackage)return "NAME_MISMATCH";
            if(version==PerformanceVersion)return "REGISTERED_3_5_0";
            if(version=="3.0.3")return "REGISTERED_3_0_3";
            return "OTHER_VERSION";
        }
        static void VerifyPerformancePackage()
        {
            var info=UnityEditor.PackageManager.PackageInfo.FindForAssetPath("Packages/"+PerformancePackage+"/Editor/TestRunBuilder.cs");
            string identity=PerformanceIdentityKind(info!=null,info?.name,info?.version);
            if(currentDiagnostic!=null)currentDiagnostic.performanceResources.packageIdentity=identity;
            Debug.Log("CANDIDATE_PERFORMANCE_PACKAGE_IDENTITY="+identity);
            Check(info!=null,"PERFORMANCE_PACKAGE_MISSING");
            Check(info.name==PerformancePackage,"PERFORMANCE_PACKAGE_NAME");
            Check(info.version==PerformanceVersion,"PERFORMANCE_PACKAGE_VERSION");
            foreach(var pin in PerformanceSourcePins)
            {
                string path=Path.Combine(info.resolvedPath,pin.Key);NoLinks(path);
                bool matches=File.Exists(path) && Hash(path)==pin.Value;
                if(!matches)Debug.Log("CANDIDATE_PERFORMANCE_SOURCE_MISMATCH="+pin.Key);
                Check(matches,"PERFORMANCE_PACKAGE_SOURCE");
            }
        }
        static void RequirePerformanceBaselineAbsent(string root=".")
        {
            Check(!Directory.Exists(Path.Combine(root,"Assets/Resources")) && !File.Exists(Path.Combine(root,"Assets/Resources")) &&
                PerformanceFiles.All(p=>!File.Exists(Path.Combine(root,p)) && !Directory.Exists(Path.Combine(root,p))),"PERFORMANCE_BASELINE");
        }
        static InventoryObservation RequirePerformanceInventory(Request request,bool complete,string root=".")
        {
            var found=InspectInventory(request,root);
            var required=new[]{"Assets/Resources","Assets/Resources.meta"}.Concat(PerformanceJson).ToArray();
            var allowed=new HashSet<string>(PerformanceFiles.Concat(new[]{"Assets/Resources"}),StringComparer.Ordinal);
            bool valid=found.observed && !found.truncated && found.unsafePathsOmitted==0 && found.removedFiles==0 && found.removedDirectories==0 && found.addedDirectories==1 &&
                found.entries.All(e=>e.change=="ADDED" && allowed.Contains(e.path) && (e.path=="Assets/Resources" ? e.kind=="DIRECTORY" : e.kind=="FILE" && e.measurement=="ACTUAL_BYTES" && e.bytes<=65536)) &&
                required.All(p=>found.entries.Any(e=>e.path==p)) && (!complete || found.totalChanges==6 && found.addedFiles==5);
            if(!valid && currentDiagnostic!=null && !currentDiagnostic.primaryInventory.observed)currentDiagnostic.primaryInventory=found;
            Check(valid,"PERFORMANCE_INVENTORY");
            return found;
        }
        static InventoryObservation BeginPerformanceIsolation(Request request,string root=".")
        {
            PerformancePreference.Suppress();
            return RequirePerformanceInventory(request,false,root);
        }
        static string[] ExpectedPerformancePayloads()
        {
            // The pinned official implementation exposes no non-test-build switch. Recreate only its in-memory values,
            // never its Setup/Cleanup methods, and require exact official serialization before touching generated bytes.
            var builder=Type.GetType("Unity.PerformanceTesting.Editor.TestRunBuilder, Unity.PerformanceTesting.Editor",true);
            var settings=Type.GetType("Unity.PerformanceTesting.Data.RunSettings, Unity.PerformanceTesting",true);
            var run=builder.GetMethod("CreateBuildInfo").Invoke(Activator.CreateInstance(builder,true),null);
            var configuration=Activator.CreateInstance(settings,System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic,null,new object[]{Environment.GetCommandLineArgs()},null);
            return new[]{JsonUtility.ToJson(run),JsonUtility.ToJson(configuration)};
        }
        static void ValidatePerformancePayloads(string root=".")
        {
            var expected=ExpectedPerformancePayloads();
            Check(PerformanceJson.Select((path,index)=>File.ReadAllText(Path.Combine(root,path))==expected[index]).All(v=>v),"PERFORMANCE_PAYLOAD");
        }
        static string MetaGuid(string path,bool folder)
        {
            string text=File.ReadAllText(path).Replace("\r\n","\n");
            string importer=folder ? "folderAsset: yes\nDefaultImporter" : "TextScriptImporter";
            var match=Regex.Match(text,"\\AfileFormatVersion: 2\\nguid: ([a-f0-9]{32})\\n"+importer+":\\n  externalObjects: \\{\\}\\n  userData:[ ]*\\n  assetBundleName:[ ]*\\n  assetBundleVariant:[ ]*\\n?\\z");
            Check(match.Success,"PERFORMANCE_META");return match.Groups[1].Value;
        }
        static void MovePerformanceFiles(Request request,InventoryObservation expected,string root,string quarantine)
        {
            var current=RequirePerformanceInventory(request,true,root);
            Check(JsonUtility.ToJson(current)==JsonUtility.ToJson(expected) && !Directory.Exists(quarantine) && !File.Exists(quarantine),"PERFORMANCE_MOVE");
            NoLinks(Path.GetDirectoryName(Path.GetFullPath(quarantine)));Directory.CreateDirectory(quarantine);
            // Preserve the exact original bytes only inside this container's already-cleaned private directory.
            foreach(var row in current.entries.Where(e=>e.kind=="FILE"))
            {
                string source=Path.Combine(root,row.path),target=Path.Combine(quarantine,Path.GetFileName(row.path));
                Check(new FileInfo(source).Length==row.bytes && Hash(source)==row.sha256,"PERFORMANCE_MOVE");
                File.Copy(source,target,false);Check(new FileInfo(target).Length==row.bytes && Hash(target)==row.sha256,"PERFORMANCE_MOVE");
            }
            // Source workspace and private /tmp can be different volumes: verify all copies before deleting any source.
            Check(JsonUtility.ToJson(RequirePerformanceInventory(request,true,root))==JsonUtility.ToJson(expected),"PERFORMANCE_MOVE");
            foreach(var row in current.entries.Where(e=>e.kind=="FILE"))
            {
                string source=Path.Combine(root,row.path);Check(Hash(source)==row.sha256,"PERFORMANCE_MOVE");File.Delete(source);
            }
            string directory=Path.Combine(root,"Assets/Resources");Check(!Directory.EnumerateFileSystemEntries(directory).Any(),"PERFORMANCE_INVENTORY");Directory.Delete(directory,false);
            VerifyInventory(request,root);
        }
        internal static void IsolatePerformanceResources(BuildReport report)
        {
            if(active==null) return;
            Check(report!=null && report.summary.platform==BuildTarget.StandaloneLinux64 && report.summary.options==CandidateOptions && Path.GetFullPath(report.summary.outputPath)==Output,"LEASE_PROFILE");
            var observation=currentDiagnostic.performanceResources;
            Check(observation.status=="ARMED" && observation.baselineAbsent && observation.packageVerified,"PERFORMANCE_BASELINE");
            // Suppress before source revalidation or unknown-inventory rejection can leave additions behind.
            BeginPerformanceIsolation(active.request);VerifyPerformancePackage();ValidatePerformancePayloads();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            observation.synchronousImportCompleted=true;
            observation.generated=RequirePerformanceInventory(active.request,true);ValidatePerformancePayloads();
            MetaGuid("Assets/Resources.meta",true);var jsonGuids=PerformanceJson.Select(p=>MetaGuid(p+".meta",false)).ToArray();
            Check(jsonGuids.Distinct().Count()==2 && PerformanceJson.Select((p,i)=>AssetDatabase.AssetPathToGUID(p)==jsonGuids[i]).All(v=>v),"PERFORMANCE_META");observation.jsonGuids=jsonGuids;
            observation.status="IMPORTED";Persist(currentDiagnostic);
            // The official postprocess still deletes these two exact paths; every subsequent scene verifies the original inventory.
            MovePerformanceFiles(active.request,observation.generated,".",active.performanceQuarantine);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            RequirePerformanceBaselineAbsent();Verify(active,true);
            observation.exactInventoryRestored=true;observation.status="QUARANTINED";Persist(currentDiagnostic);
        }
        static bool IsPerformancePacked(string path,string guid,string[] jsonGuids) => PerformanceJson.Contains(path) || jsonGuids.Contains(guid);
        static void VerifyPackedPerformanceExclusion(BuildReport report,PerformanceObservation observation,string[] callbackScenes)
        {
            Check(observation.status=="QUARANTINED" && report!=null && report.summary.result==BuildResult.Succeeded && report.summary.options==CandidateOptions,"PERFORMANCE_PACKED_REPORT");
            var containers=report.packedAssets;Check(containers!=null && containers.Length>0,"PERFORMANCE_PACKED_REPORT");
            var scenes=new HashSet<string>(StringComparer.Ordinal);int count=0,sourceCount=0,hits=0;
            foreach(var container in containers)
            {
                var contents=container.contents;Check(contents!=null,"PERFORMANCE_PACKED_REPORT");
                foreach(var item in contents)
                {
                    count++;string path=item.sourceAssetPath??"";string guid=item.sourceAssetGUID.ToString();
                    if(IsPerformancePacked(path,guid,observation.jsonGuids))hits++;
                    if(path.StartsWith("Assets/",StringComparison.Ordinal) || path.StartsWith("Packages/",StringComparison.Ordinal))sourceCount++;
                    if(Paths.Contains(path))scenes.Add(path);
                }
            }
            observation.packedReportAvailable=true;observation.packedContainers=containers.Length;observation.packedObjects=count;observation.packedSourceObjects=sourceCount;observation.packedJsonHits=hits;observation.packedScenePaths=scenes.OrderBy(p=>p,StringComparer.Ordinal).ToArray();observation.callbackScenePaths=callbackScenes.OrderBy(p=>p,StringComparer.Ordinal).ToArray();
            Persist(currentDiagnostic);
            Check(count>0 && sourceCount>0 && new HashSet<string>(callbackScenes,StringComparer.Ordinal).SetEquals(Paths) && callbackScenes.Length==Paths.Length && hits==0,"PERFORMANCE_PACKED_CONTENT");
            observation.status="PACKED_VERIFIED";Persist(currentDiagnostic);
        }

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
            public JourneyCandidateAssetIntegration.FilePin restorationProof;
            public string assetProducerSourceCommit, assetProducerRunUrl, restorationNativeXmlSha256;
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
            public JourneyCandidateAssetIntegration.FilePin restorationProof;
            public string assetProducerSourceCommit, assetProducerRunUrl, restorationNativeXmlSha256;
            public string unityVersion = "6000.3.19f1", target = "StandaloneLinux64", backend = "Mono2x", define = "DESERTRV_CANDIDATE_LINUX", executable = "DesertRV.x86_64";
            public string[] scenes;
            public string[] temporarySettingsFiles = { "ProjectSettings/ProjectSettings.asset" };
            // Records the APIs invoked; complete temporary bytes are separately pinned, not an asserted YAML diff.
            public string[] temporarySettingsApiFields = { "scriptingBackend.Standalone", "fullScreenMode", "defaultScreenWidth", "defaultScreenHeight", "productName", "resizableWindow" };
            public bool candidateOnly = true, development = true, detailedBuildReport = true, performanceTestResourcesExcluded = true, approved = false, settingsRestored, sourceBytesUnchanged;
            public bool visualReviewed = false, gameplayReviewed = false, audioAuditioned = false;
        }
        [Serializable] sealed class RootObservation
        {
            public bool observed, rootBytesMatch, rootDependencyBytesMatch;
            public string slot="NONE", expectedImportHash="", observedImportHash="";
        }
        [Serializable] sealed class SafeBuildMessage
        {
            public string category="UNCLASSIFIED_BUILD_ERROR", code="NONE", source="", text="";
            public int line;
        }
        [Serializable] sealed class InventoryEntry
        {
            public string path,change,kind,sha256="",measurement="NOT_APPLICABLE";
            public long bytes;
        }
        [Serializable] sealed class InventoryObservation
        {
            public bool observed,truncated;
            public int totalChanges,addedFiles,removedFiles,addedDirectories,removedDirectories,unsafePathsOmitted;
            public InventoryEntry[] entries=Array.Empty<InventoryEntry>();
        }
        [Serializable] sealed class Diagnostic
        {
            public int schema = 1;
            public string label = "CANDIDATE_LINUX_BUILD_DIAGNOSTIC", stage = "ENTRY", exceptionKind = "NONE", buildResult = "UNAVAILABLE";
            public bool settingsRestored, sourceBytesUnchanged, receiptWritten;
            public bool buildReportAvailable, leaseActiveAtBuildReturn, assemblyReloadObserved;
            public string activeTargetAtEntry="NOT_OBSERVED",activeTargetBeforeBuild="NOT_OBSERVED",activeTargetAfterBuild="NOT_OBSERVED",reportTarget="NOT_OBSERVED";
            public long totalErrors, totalWarnings;
            public string primaryFailureCode = "NONE", primaryExceptionKind = "NONE", restorationFailureCode = "NONE", restorationExceptionKind = "NONE", verificationFailureCode = "NONE", verificationExceptionKind = "NONE", leaseClosedReason = "NONE";
            public string[] buildErrorKinds = Array.Empty<string>();
            public string primaryCallbackGate="NONE", primarySceneRole="NONE", verificationCallbackGate="NONE", verificationSceneRole="NONE";
            public PerformanceObservation performanceResources=new PerformanceObservation();
            public RootObservation primaryRootMismatch=new RootObservation(), verificationRootMismatch=new RootObservation();
            public InventoryObservation primaryInventory=new InventoryObservation(), verificationInventory=new InventoryObservation();
            public SafeBuildMessage[] buildMessages=Array.Empty<SafeBuildMessage>();
            public bool buildMessagesTruncated;
        }
        static readonly Dictionary<string,long> inventoryBaselineSizes=new Dictionary<string,long>(StringComparer.Ordinal);
        static Diagnostic currentDiagnostic;
        static string diagnosticContext = "PRIMARY", currentSceneRole="NONE";
        static string SceneRole(string path) => path==JourneySceneAuthoring.ManifestPath ? "CONTENT" : Array.IndexOf(Paths,path)==0 ? "BOOTSTRAP" : Array.IndexOf(Paths,path)==1 ? "FIRST_STATION" : Array.IndexOf(Paths,path)==2 ? "SCRAPYARD" : Array.IndexOf(Paths,path)==3 ? "NIGHT_BEACON" : "NONE";
        static string CallbackGate()
        {
            string trace=Environment.StackTrace;
            if(trace.Contains("IsolatePerformanceResources")) return "CANDIDATE_PERFORMANCE";
            if(trace.Contains("JourneyProductionBuildGate.OnPreprocessBuild")) return "PRODUCTION_PREPROCESS";
            if(trace.Contains("JourneyProductionBuildGate.OnProcessScene")) return "PRODUCTION_SCENE";
            if(trace.Contains("JourneyCandidateLinuxBuild.ProcessCandidateScene")) return "CANDIDATE_SCENE";
            return "NONE";
        }
        static string TargetKind(BuildTarget target) => target==BuildTarget.StandaloneLinux64 ? "LINUX64" : target==BuildTarget.Android ? "ANDROID" : "OTHER";
        static string ExceptionKind(Exception error) => error is BuildFailedException ? "BUILD_FAILED" : error is UnauthorizedAccessException ? "UNAUTHORIZED_ACCESS" : error is IOException ? "IO" : "OTHER";
        static void RememberFailure(Diagnostic diagnostic, string context, string code, string kind)
        {
            if (diagnostic == null) return;
            if (context == "RESTORATION") { if (diagnostic.restorationFailureCode == "NONE") { diagnostic.restorationFailureCode=code; diagnostic.restorationExceptionKind=kind; } }
            else if (context == "VERIFICATION") { if (diagnostic.verificationFailureCode == "NONE") { diagnostic.verificationFailureCode=code; diagnostic.verificationExceptionKind=kind; diagnostic.verificationCallbackGate=CallbackGate();diagnostic.verificationSceneRole=diagnostic.verificationCallbackGate.StartsWith("PRODUCTION_",StringComparison.Ordinal) ? "NONE" : currentSceneRole; } }
            else if (diagnostic.primaryFailureCode == "NONE") { diagnostic.primaryFailureCode=code; diagnostic.primaryExceptionKind=kind;diagnostic.primaryCallbackGate=CallbackGate();diagnostic.primarySceneRole=diagnostic.primaryCallbackGate.StartsWith("PRODUCTION_",StringComparison.Ordinal) ? "NONE" : currentSceneRole; }
        }
        static void RecordUnhandled(Diagnostic diagnostic, Exception error)
        {
            diagnostic.exceptionKind=ExceptionKind(error);
            // An earlier primary exception can resume after a successful finally. Do not relabel it as verification failure.
            if(diagnostic.primaryFailureCode=="NONE" && diagnostic.restorationFailureCode=="NONE" && diagnostic.verificationFailureCode=="NONE")
                RememberFailure(diagnostic,"PRIMARY","UNCLASSIFIED_EXCEPTION",diagnostic.exceptionKind);
        }
        static void Report(BuildReport report, Diagnostic diagnostic)
        {
            diagnostic.buildReportAvailable = report != null;
            if (report == null) return;
            diagnostic.buildResult = report.summary.result == BuildResult.Succeeded ? "SUCCEEDED" : report.summary.result == BuildResult.Cancelled ? "CANCELLED" : report.summary.result == BuildResult.Failed ? "FAILED" : "UNKNOWN";
            diagnostic.reportTarget=TargetKind(report.summary.platform);
            diagnostic.totalErrors=report.summary.totalErrors; diagnostic.totalWarnings=report.summary.totalWarnings;
            var kinds = new HashSet<string>(StringComparer.Ordinal);var messages=new List<SafeBuildMessage>();int observed=0;
            foreach (var step in report.steps)
                foreach (var message in step.messages)
                    if (message.type == LogType.Error || message.type == LogType.Exception || message.type == LogType.Assert)
                    {
                        observed++;
                        if(messages.Count<32) {var safe=ClassifyBuildMessage(message.content ?? "");kinds.Add(safe.category);messages.Add(safe);}
                    }
            diagnostic.buildErrorKinds=kinds.OrderBy(x=>x,StringComparer.Ordinal).Take(64).ToArray();diagnostic.buildMessages=messages.ToArray();diagnostic.buildMessagesTruncated=observed>messages.Count;
        }
        static SafeBuildMessage ClassifyBuildMessage(string text)
        {
            text=text ?? "";if(text.Length>16384) text=text.Substring(0,16384);
            var result=new SafeBuildMessage();
            // Only reconstruct known public diagnostics. Never publish arbitrary report text or stack frames.
            var known=Regex.Match(text,@"DESERTRV_CANDIDATE_([A-Z_]+)");
            if(known.Success && FailureCodes.Contains(known.Groups[1].Value))
            {result.category="CANDIDATE_GATE";result.code=known.Groups[1].Value;result.text="Candidate build gate rejected: "+result.code;return result;}
            if(text.Contains("Formal journey scenes require current production content preflight") || text.Contains("Run formal content preflight before entering BuildPipeline"))
            {result.category="PRODUCTION_GATE";result.text="Formal journey scenes require current production content preflight.";return result;}
            var compiler=Regex.Match(text,@"\berror (CS[0-9]{4})\b");
            if(compiler.Success)
            {
                result.category="CS_COMPILATION";result.code=CompilerCodes.Contains(compiler.Groups[1].Value) ? compiler.Groups[1].Value : "UNKNOWN_CSHARP_ERROR";result.text="C# compiler diagnostic: "+result.code;
                if(active != null)
                    foreach(var pin in active.request.files.Where(p=>p.path.StartsWith("tasks/desert-rv/unity/Assets/DesertRV/",StringComparison.Ordinal) && p.path.EndsWith(".cs",StringComparison.Ordinal)))
                    {
                        string relative=pin.path.Substring("tasks/desert-rv/unity/".Length);
                        var location=Regex.Match(text,Regex.Escape(relative)+@"\(([0-9]{1,7}),[0-9]{1,7}\)");
                        if(location.Success) {result.source=relative;result.line=int.Parse(location.Groups[1].Value);result.text+=" at "+relative+":"+result.line;break;}
                    }
                return result;
            }
            if(text.Contains("Error building Player because scripts had compiler errors")) {result.category="CS_COMPILATION";result.text="Error building Player because scripts had compiler errors.";return result;}
            if(text.IndexOf("shader",StringComparison.OrdinalIgnoreCase)>=0) {result.category="SHADER_ERROR";result.text="Build report contains a shader error.";}
            return result;
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
            public Request request; public string requestHash, fingerprint, performanceQuarantine;
            public readonly Dictionary<string,string> temporarySettings = new Dictionary<string,string>();
            public readonly HashSet<string> processed = new HashSet<string>(StringComparer.Ordinal);
        }
        static readonly HashSet<string> CompilerCodes = new HashSet<string>(new[] { "CS0006","CS0012","CS0016","CS0029","CS0030","CS0101","CS0103","CS0104","CS0106","CS0111","CS0117","CS0118","CS0120","CS0121","CS0122","CS0136","CS0161","CS0200","CS0234","CS0246","CS0266","CS0535","CS0619","CS1001","CS1002","CS1003","CS1022","CS1026","CS1061","CS1068","CS1069","CS1501","CS1502","CS1503","CS1513","CS1519","CS1525","CS1617","CS1705","UNKNOWN_CSHARP_ERROR" },StringComparer.Ordinal);
        static readonly HashSet<string> FailureCodes = new HashSet<string>(new[] { "PERFORMANCE_PACKAGE_MISSING","PERFORMANCE_PACKAGE_NAME","PERFORMANCE_PACKAGE_VERSION","PERFORMANCE_PACKAGE_SOURCE","PERFORMANCE_PREFERENCE","PERFORMANCE_LINK","PERFORMANCE_PACKAGE","PERFORMANCE_BASELINE","PERFORMANCE_INVENTORY","PERFORMANCE_PAYLOAD","PERFORMANCE_META","PERFORMANCE_MOVE","PERFORMANCE_PACKED_REPORT","PERFORMANCE_PACKED_CONTENT","PERFORMANCE_PRIVATE","BOOTSTRAP_BINDING","BOOTSTRAP_OWNER","BUILD_OR_SCENE_FAILED","BUILD_PROFILE","BUILTIN_DEPENDENCY","DEPENDENCY_BYTES","DEPENDENCY_KIND","DEPENDENCY_PATH","DIRTY_SCENE","ENTRY_PROFILE","IMPORT_FINGERPRINT","INVENTORY_DIRECTORY","INVENTORY_LINK","INVENTORY_NONREGULAR","INVENTORY_SET","LEASE_PROFILE","PACKAGE_IDENTITY","PIN_BYTES","PIN_LINK","PIN_MISSING","PIN_PATH","REGION_BINDING","REGION_IDENTITY","REGION_OWNER","REQUEST_HASH","REQUEST_IDENTITY","REQUEST_RECEIPT_HASH","RESTORATION_PROOF","RESTORATION_XML","ROOT_BYTES","ROOT_DEPENDENCY","ROOT_DEPENDENCY_BYTES","ROOT_IMPORT_HASH","SAVED_RUNTIME_IDENTITY","SCENE_COMPONENT","SCENE_SEQUENCE","TARGET_OUTPUT","UNCLASSIFIED_EXCEPTION" },StringComparer.Ordinal);
        static Lease active;
        static JourneyCandidateLinuxBuild() { AssemblyReloadEvents.beforeAssemblyReload += () => Close("ASSEMBLY_RELOAD"); EditorApplication.quitting += () => Close("EDITOR_QUIT"); }
        static void Close(string reason = "EXPLICIT")
        {
            bool wasActive=active!=null;active=null;
            if (currentDiagnostic != null && wasActive)
            {
                currentDiagnostic.leaseClosedReason=reason;
                if (reason == "ASSEMBLY_RELOAD") currentDiagnostic.assemblyReloadObserved=true;
                try { Persist(currentDiagnostic); } catch { } // Observation cannot keep a lease open or skip restoration.
            }
        }
        static void Check(bool valid, string code)
        {
            if (valid) return;
            if (!FailureCodes.Contains(code)) code="UNCLASSIFIED_EXCEPTION";
            RememberFailure(currentDiagnostic,diagnosticContext,code,"BUILD_FAILED");
            if(currentDiagnostic!=null) {try {Persist(currentDiagnostic);} catch { }}
            throw new BuildFailedException("DESERTRV_CANDIDATE_"+code);
        }
        static string Hash(string path) => JourneyDiagnosticScope.HashFile(path);
        static string HashBytes(byte[] bytes) { using(var sha=System.Security.Cryptography.SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant(); }
        public static bool ValidBuildProfile(BuildTarget target, BuildOptions options, string[] defines) =>
            target == BuildTarget.StandaloneLinux64 && options == CandidateOptions && defines != null && defines.SequenceEqual(new[] { JourneyCandidateLinuxIdentity.Define });
        static string RepoFile(string name)
        {
            Check(!string.IsNullOrEmpty(name) && !Path.IsPathRooted(name) && !name.Contains("..") && !name.Contains("\\") &&
                (name.StartsWith("tasks/desert-rv/",StringComparison.Ordinal) || name.StartsWith(".github/",StringComparison.Ordinal)), "PIN_PATH");
            string root = Path.GetFullPath("../../.."), full = Path.GetFullPath(Path.Combine(root,name));
            Check(full.StartsWith(root + Path.DirectorySeparatorChar,StringComparison.Ordinal) && File.Exists(full), "PIN_MISSING");
            for (string path = full; path != root; path = Path.GetDirectoryName(path))
                Check((File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0, "PIN_LINK");
            return full;
        }
        static InventoryObservation InspectInventory(Request request, string projectRoot = ".")
        {
            Check(request.directories!=null,"INVENTORY_SET");
            const string prefix = "tasks/desert-rv/unity/";
            var expected = new HashSet<string>(request.files.Where(p => p.path.StartsWith(prefix,StringComparison.Ordinal)).Select(p => p.path.Substring(prefix.Length))
                .Where(p => p.StartsWith("Assets/",StringComparison.Ordinal) || p.StartsWith("Packages/",StringComparison.Ordinal) || p.StartsWith("ProjectSettings/",StringComparison.Ordinal)),StringComparer.Ordinal);
            var actual = new HashSet<string>(StringComparer.Ordinal); var directories = new HashSet<string>(StringComparer.Ordinal);
            string root = Path.GetFullPath(projectRoot);
            var pending = new Stack<string>(new[] { "Assets", "Packages", "ProjectSettings" }.Select(n=>Path.Combine(root,n)));
            while (pending.Count > 0)
            {
                string folder = pending.Pop();
                Check(Directory.Exists(folder) && (File.GetAttributes(folder) & FileAttributes.ReparsePoint) == 0,"INVENTORY_DIRECTORY");
                foreach (string child in Directory.GetFileSystemEntries(folder))
                {
                    string path = child.Substring(root.Length+1).Replace('\\','/'); var attributes = File.GetAttributes(child);
                    Check((attributes & FileAttributes.ReparsePoint) == 0,"INVENTORY_LINK");
                    if ((attributes & FileAttributes.Directory) != 0) { directories.Add(path);pending.Push(child); }
                    else { Check(File.Exists(child),"INVENTORY_NONREGULAR");actual.Add(path); }
                }
            }
            var expectedDirectories=new HashSet<string>(request.directories,StringComparer.Ordinal);
            var difference=new InventoryObservation { observed=true,addedFiles=actual.Except(expected).Count(),removedFiles=expected.Except(actual).Count(),addedDirectories=directories.Except(expectedDirectories).Count(),removedDirectories=expectedDirectories.Except(directories).Count() };
            difference.totalChanges=difference.addedFiles+difference.removedFiles+difference.addedDirectories+difference.removedDirectories;
            var changes=actual.Except(expected).Select(p=>new InventoryEntry {path=p,kind="FILE",change="ADDED"})
                .Concat(expected.Except(actual).Select(p=>new InventoryEntry {path=p,kind="FILE",change="REMOVED"}))
                .Concat(directories.Except(expectedDirectories).Select(p=>new InventoryEntry {path=p,kind="DIRECTORY",change="ADDED"}))
                .Concat(expectedDirectories.Except(directories).Select(p=>new InventoryEntry {path=p,kind="DIRECTORY",change="REMOVED"}))
                .OrderBy(p=>p.path,StringComparer.Ordinal).ThenBy(p=>p.kind,StringComparer.Ordinal).ThenBy(p=>p.change,StringComparer.Ordinal).ToArray();
            var entries=new List<InventoryEntry>();
            foreach(var row in changes)
            {
                bool safe=Regex.IsMatch(row.path,@"\A(Assets|Packages|ProjectSettings)/[A-Za-z0-9_./ @+()\-]{1,480}\z") && !row.path.Split('/').Any(n=>n=="." || n==".." || n.Length==0);
                if(!safe) {difference.unsafePathsOmitted++;continue;}
                if(entries.Count>=32) continue;
                if(row.kind=="FILE")
                {
                    if(row.change=="REMOVED")
                    {
                        row.sha256=request.files.Single(p=>p.path=="tasks/desert-rv/unity/"+row.path).sha256;
                        if(inventoryBaselineSizes.TryGetValue(row.path,out var priorSize)) {row.bytes=priorSize;row.measurement="EXPECTED_PIN_PRIOR_SIZE";}
                        else {row.bytes=-1;row.measurement="EXPECTED_PIN_SIZE_UNAVAILABLE";}
                    }
                    else
                    {
                        try
                        {
                            string full=Path.Combine(root,row.path);row.bytes=new FileInfo(full).Length;
                            if(row.bytes<=128L*1024*1024) {row.sha256=Hash(full);row.measurement="ACTUAL_BYTES";}
                            else row.measurement="SIZE_ONLY_LIMIT";
                        }
                        catch { row.bytes=-1;row.sha256="";row.measurement="UNREADABLE"; }
                    }
                }
                entries.Add(row);
            }
            difference.entries=entries.ToArray();difference.truncated=difference.totalChanges>entries.Count;return difference;
        }
        static void VerifyInventory(Request request, string projectRoot = ".")
        {
            var difference=InspectInventory(request,projectRoot);
            if(currentDiagnostic!=null && difference.totalChanges>0)
            {
                if(diagnosticContext=="VERIFICATION") {if(!currentDiagnostic.verificationInventory.observed) currentDiagnostic.verificationInventory=difference;}
                else if(!currentDiagnostic.primaryInventory.observed) currentDiagnostic.primaryInventory=difference;
            }
            Check(difference.totalChanges==0,"INVENTORY_SET");
        }
        [Serializable] sealed class RestorationReport
        {
            public int schema; public string label,sourceCommit,producerRunUrl,assetProducerSourceCommit,assetProducerRunUrl,generatedReceiptSha256,requestSha256,unityVersion;
            public JourneyCandidateAssetIntegration.FilePin sourceTransitionProof;
            public bool sourceBytesUnchanged,originalAssetsUnchanged,structureValidated,productionApprovalRejected,approved,scopeReused;
            public JourneyCandidateAssetIntegration.OutputFile[] scenes;
            public Dependency[] dependencies;
            public JourneyCandidateAssetIntegration.SpawnGroundingReport grounding;
        }
        static bool Pinned(Request request,string path,string hash) => request.files.Count(p=>p.path==path && p.sha256==hash)==1 && Hash(RepoFile(path))==hash;
        static string DependencyKey(Dependency d) => string.Join("|",new[]{d.path,d.sha256,d.bytes.ToString(System.Globalization.CultureInfo.InvariantCulture),d.kind,d.packageName ?? "",d.packageVersion ?? ""});
        static void VerifyRestoration(Request request)
        {
            bool restored=request.restorationProof!=null && !string.IsNullOrEmpty(request.restorationProof.path);
            if(!restored)
            {
                Check((request.restorationProof==null || string.IsNullOrEmpty(request.restorationProof.sha256)) && string.IsNullOrEmpty(request.assetProducerSourceCommit) && string.IsNullOrEmpty(request.assetProducerRunUrl) && string.IsNullOrEmpty(request.restorationNativeXmlSha256),"RESTORATION_PROOF");return;
            }
            const string proofPath="tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json";
            const string inputPath="tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-input.json";
            const string transitionPath="tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-source-proof.json";
            Check(request.restorationProof.path==proofPath && Regex.IsMatch(request.restorationProof.sha256 ?? "","^[a-f0-9]{64}$") && Pinned(request,proofPath,request.restorationProof.sha256) && new FileInfo(RepoFile(proofPath)).Length<=16*1024*1024,"RESTORATION_PROOF");
            var proof=JsonUtility.FromJson<RestorationReport>(File.ReadAllText(RepoFile(proofPath)));
            Check(proof!=null && proof.schema==1 && proof.label=="RESTORED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED" && proof.unityVersion=="6000.3.19f1" &&
                proof.sourceCommit==request.sourceCommit && proof.producerRunUrl==request.producerRunUrl && proof.assetProducerSourceCommit==request.assetProducerSourceCommit && proof.assetProducerRunUrl==request.assetProducerRunUrl &&
                Regex.IsMatch(proof.assetProducerSourceCommit ?? "","^[a-f0-9]{40}$") && Regex.IsMatch(proof.assetProducerRunUrl ?? "",@"^https://github\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*$") &&
                proof.generatedReceiptSha256==request.generatedReceiptSha256 && proof.sourceBytesUnchanged && proof.originalAssetsUnchanged && proof.structureValidated && proof.productionApprovalRejected && !proof.approved && !proof.scopeReused &&
                proof.sourceTransitionProof!=null && proof.sourceTransitionProof.path==transitionPath && Regex.IsMatch(proof.sourceTransitionProof.sha256 ?? "","^[a-f0-9]{64}$") && Pinned(request,transitionPath,proof.sourceTransitionProof.sha256) &&
                Regex.IsMatch(proof.requestSha256 ?? "","^[a-f0-9]{64}$") && Pinned(request,inputPath,proof.requestSha256),"RESTORATION_PROOF");
            Check(proof.scenes!=null && proof.scenes.Length==5 && proof.scenes.Select(p=>p.path).Distinct().Count()==5 &&
                proof.scenes.All(p=>request.scenes.Any(q=>p.path==q.path && p.sha256==q.sha256 && p.dependencyHash==q.dependencyHash && p.dependencySha256==q.dependencySha256)) &&
                proof.dependencies!=null && proof.dependencies.Select(DependencyKey).OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(request.dependencies.Select(DependencyKey).OrderBy(x=>x,StringComparer.Ordinal)) &&
                proof.grounding!=null && proof.grounding.rows!=null && proof.grounding.rows.Length==9 && !proof.grounding.approved,"RESTORATION_PROOF");
            var xmlPins=request.files.Where(p=>p.path.StartsWith("tasks/desert-rv/artifacts/journey-restoration/",StringComparison.Ordinal) && p.path.EndsWith(".xml",StringComparison.Ordinal)).ToArray();
            Check(Regex.IsMatch(request.restorationNativeXmlSha256 ?? "","^[a-f0-9]{64}$") && xmlPins.Length==1 && xmlPins[0].sha256==request.restorationNativeXmlSha256 && Pinned(request,xmlPins[0].path,xmlPins[0].sha256) && new FileInfo(RepoFile(xmlPins[0].path)).Length<=10*1024*1024,"RESTORATION_XML");
            var document=new XmlDocument { XmlResolver=null };
            using(var reader=XmlReader.Create(RepoFile(xmlPins[0].path),new XmlReaderSettings { DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null })) document.Load(reader);
            var root=document.DocumentElement;var cases=document.GetElementsByTagName("test-case");
            Check(root!=null && root.Name=="test-run" && root.GetAttribute("result")=="Passed" && root.GetAttribute("total")=="1" && root.GetAttribute("passed")=="1" && root.GetAttribute("failed")=="0" && root.GetAttribute("skipped")=="0" && root.GetAttribute("inconclusive")=="0" && cases.Count==1 &&
                ((XmlElement)cases[0]).GetAttribute("fullname")=="DesertRV.Tests.JourneyRestorationTests.RevalidatePinnedRestoredJourney" && ((XmlElement)cases[0]).GetAttribute("result")=="Passed","RESTORATION_XML");
        }
        static void Verify(Lease lease, bool building)
        {
            var r = lease.request; VerifyInventory(r);VerifyRestoration(r);
            Check(Hash(Input) == lease.requestHash && Hash(Receipt) == r.generatedReceiptSha256, "REQUEST_RECEIPT_HASH");
            foreach (var pin in r.files)
            {
                string relative = pin.path.StartsWith("tasks/desert-rv/unity/",StringComparison.Ordinal) ? pin.path.Substring("tasks/desert-rv/unity/".Length) : null;
                string expected = building && relative != null && lease.temporarySettings.TryGetValue(relative,out var temporary) ? temporary : pin.sha256;
                Check(Hash(RepoFile(pin.path)) == expected, "PIN_BYTES");
            }
            foreach (var dependency in r.dependencies)
            {
                string path = dependency.path;
                if (dependency.kind == "builtin")
                {
                    Check((path == "Resources/unity_builtin_extra" || path == "Library/unity default resources") && dependency.sha256 == "" && dependency.bytes == 0, "BUILTIN_DEPENDENCY");
                    continue;
                }
                Check(!path.Contains("..") && !path.Contains("\\") && !Path.IsPathRooted(path), "DEPENDENCY_PATH");
                if (dependency.kind == "package")
                {
                    var info = UnityEditor.PackageManager.PackageInfo.FindForAssetPath(path.EndsWith(".meta",StringComparison.Ordinal) ? path.Substring(0,path.Length-5) : path);
                    Check(info != null && info.name == dependency.packageName && info.version == dependency.packageVersion && path.StartsWith("Packages/" + info.name + "/",StringComparison.Ordinal), "PACKAGE_IDENTITY");
                    path = Path.Combine(info.resolvedPath,path.Substring(("Packages/" + info.name + "/").Length));
                }
                else Check(dependency.kind == "asset" && path.StartsWith("Assets/",StringComparison.Ordinal), "DEPENDENCY_KIND");
                Check(File.Exists(path) && new FileInfo(path).Length == dependency.bytes && Hash(path) == dependency.sha256, "DEPENDENCY_BYTES");
            }
            foreach (var scene in r.scenes)
            {
                bool bytes=Hash(scene.path)==scene.sha256; string importHash=AssetDatabase.GetAssetDependencyHash(scene.path).ToString();
                bool dependencies=JourneyContentChecks.DependencySha256(scene.path)==scene.dependencySha256;
                if (currentDiagnostic != null && (!bytes || importHash != scene.dependencyHash || !dependencies))
                {
                    var observation=diagnosticContext=="VERIFICATION" ? currentDiagnostic.verificationRootMismatch : currentDiagnostic.primaryRootMismatch;
                    if(!observation.observed)
                    {
                        observation.observed=true;observation.slot=SceneRole(scene.path);observation.expectedImportHash=scene.dependencyHash;observation.observedImportHash=importHash;
                        observation.rootBytesMatch=bytes;observation.rootDependencyBytesMatch=dependencies;
                    }
                }
                Check(bytes,"ROOT_BYTES");Check(importHash==scene.dependencyHash,"ROOT_IMPORT_HASH");Check(dependencies,"ROOT_DEPENDENCY_BYTES");
            }
            Check(lease.fingerprint == JourneyContentChecks.BuildFingerprint(), "IMPORT_FINGERPRINT");
        }
        public static bool AllowsCandidateBuild(BuildReport report)
        {
            if (active == null) return false;
            Check(report != null && report.summary.platform == BuildTarget.StandaloneLinux64 && report.summary.options == CandidateOptions &&
                Path.GetFullPath(report.summary.outputPath) == Output, "LEASE_PROFILE");
            Verify(active,true); return true;
        }
        static void CheckSceneObjects(Scene scene, JourneyContentManifest content)
        {
            currentSceneRole=SceneRole(scene.path);
            var roots = scene.GetRootGameObjects();
            foreach (var root in roots)
                foreach (var node in root.GetComponentsInChildren<Transform>(true))
                    Check(node.GetComponents<Component>().All(c => c), "SCENE_COMPONENT");
            var directors = roots.SelectMany(r => r.GetComponentsInChildren<JourneyDirector>(true)).ToArray();
            var bindings = roots.SelectMany(r => r.GetComponentsInChildren<RegionBinding>(true)).ToArray();
            if (scene.path == Paths[0])
            {
                Check(directors.Length == 1 && bindings.Length == 0 && roots.SelectMany(r => r.GetComponentsInChildren<JourneySession>(true)).Count() == 1 &&
                    roots.SelectMany(r => r.GetComponentsInChildren<JourneyMotor>(true)).Count() == 1, "BOOTSTRAP_OWNER");
                Check(JourneyCandidateLinuxIdentity.ValidateBootstrap(directors[0],content,out var reason),"BOOTSTRAP_BINDING");
            }
            else
            {
                int index = Array.IndexOf(Paths,scene.path);
                Check(index > 0 && directors.Length == 0 && bindings.Length == 1 && bindings[0].region == index, "REGION_IDENTITY");
                Check(!roots.Any(r => r.GetComponentInChildren<JourneySession>(true) || r.GetComponentInChildren<JourneyMotor>(true) ||
                    r.GetComponentInChildren<JourneyHud>(true) || r.GetComponentInChildren<Camera>(true) || r.GetComponentInChildren<AudioListener>(true)), "REGION_OWNER");
                Check(JourneyCandidateLinuxIdentity.ValidateRegionContent(bindings[0],content,out var reason),"REGION_BINDING");
            }
        }
        internal static void ProcessCandidateScene(Scene scene, BuildReport report)
        {
            if (active == null) return;
            currentSceneRole=SceneRole(scene.path);
            Check(AllowsCandidateBuild(report) && Paths.Contains(scene.path) && active.processed.Add(scene.path), "SCENE_SEQUENCE");
            var content = AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(JourneySceneAuthoring.ManifestPath);
            CheckSceneObjects(scene,content);
            Check(!scene.GetRootGameObjects().Any(r => r.GetComponentInChildren<JourneyCandidateLinuxIdentity>(true)), "SAVED_RUNTIME_IDENTITY");
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
            var diagnostic = new Diagnostic { activeTargetAtEntry=TargetKind(EditorUserBuildSettings.activeBuildTarget) }; inventoryBaselineSizes.Clear();currentDiagnostic=diagnostic;diagnosticContext="PRIMARY";Persist(diagnostic);
            try { BuildPrepared(diagnostic); }
            catch (Exception error)
            {
                RecordUnhandled(diagnostic,error);
                throw;
            }
            finally { Close(); Persist(diagnostic);currentDiagnostic=null;inventoryBaselineSizes.Clear();diagnosticContext="PRIMARY";currentSceneRole="NONE"; }
        }
        static void BuildPrepared(Diagnostic diagnostic)
        {
            Check(active == null && !Application.isPlaying && !BuildPipeline.isBuildingPlayer && Application.unityVersion == "6000.3.19f1", "ENTRY_PROFILE");
            string requestHash = File.ReadAllText("JourneyEvidence/JourneyPreparation/linux-build-input.sha256").Trim();
            Check(Regex.IsMatch(requestHash,"^[a-f0-9]{64}$") && Hash(Input) == requestHash, "REQUEST_HASH");
            var request = JsonUtility.FromJson<Request>(File.ReadAllText(Input));
            Check(request != null && request.schema == 1 && request.label == "CANDIDATE_LINUX_DEVELOPMENT_ONLY" && !request.approved && request.development &&
                request.boundaryNativeCases == 17 && Regex.IsMatch(request.boundaryNativeXmlSha256 ?? "","^[a-f0-9]{64}$") && request.target == "StandaloneLinux64" && request.define == JourneyCandidateLinuxIdentity.Define &&
                request.sourceCommit == Environment.GetEnvironmentVariable("GITHUB_SHA") && Regex.IsMatch(request.sourceCommit ?? "","^[a-f0-9]{40}$") &&
                request.producerRunUrl == "https://github.com/yangerstar1/task-workbench/actions/runs/" + Environment.GetEnvironmentVariable("GITHUB_RUN_ID") &&
                Regex.IsMatch(request.generatedReceiptSha256 ?? "","^[a-f0-9]{64}$") && request.files != null && request.files.Length > 100 && request.files.Select(p=>p.path).Distinct().Count()==request.files.Length &&
                request.directories != null && request.directories.Distinct().Count()==request.directories.Length && request.dependencies != null && request.dependencies.Length > 0 && request.scenes != null && request.scenes.Length == 5 &&
                new HashSet<string>(request.scenes.Select(p=>p.path)).SetEquals(Paths.Concat(new[] { JourneySceneAuthoring.ManifestPath })), "REQUEST_IDENTITY");
            Check(BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Standalone,BuildTarget.StandaloneLinux64) && !Directory.Exists(Path.GetDirectoryName(Output)), "TARGET_OUTPUT");
            var setup = EditorSceneManager.GetSceneManagerSetup(); Check(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "DIRTY_SCENE");
            var lease = new Lease { request=request,requestHash=requestHash,fingerprint=JourneyContentChecks.BuildFingerprint() }; Verify(lease,false);
            foreach(var pin in request.files.Where(p=>p.path.StartsWith("tasks/desert-rv/unity/Assets/",StringComparison.Ordinal) || p.path.StartsWith("tasks/desert-rv/unity/Packages/",StringComparison.Ordinal) || p.path.StartsWith("tasks/desert-rv/unity/ProjectSettings/",StringComparison.Ordinal)))
                inventoryBaselineSizes[pin.path.Substring("tasks/desert-rv/unity/".Length)]=new FileInfo(RepoFile(pin.path)).Length;
            diagnostic.stage="SOURCE_VERIFIED";Persist(diagnostic);
            JourneyCandidateAssetIntegration.RequireOnlyMissingApprovals(JourneyContentChecks.Inspect(true).ToArray());
            try { foreach (var path in Paths) CheckSceneObjects(EditorSceneManager.OpenScene(path,OpenSceneMode.Single),AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(JourneySceneAuthoring.ManifestPath)); }
            finally { JourneySceneAuthoring.RestoreSceneSetup(setup); }
            diagnostic.stage="CONTENT_VERIFIED";Persist(diagnostic);
            VerifyPerformancePackage();RequirePerformanceBaselineAbsent();
            string privateRoot=Environment.GetEnvironmentVariable("DESERTRV_PERFORMANCE_PRIVATE");
            Check(!string.IsNullOrEmpty(privateRoot) && Path.IsPathRooted(privateRoot) && Path.GetFullPath(privateRoot).StartsWith(Path.GetFullPath(Path.GetTempPath()),StringComparison.Ordinal) && Directory.Exists(privateRoot),"PERFORMANCE_PRIVATE");
            NoLinks(privateRoot);lease.performanceQuarantine=Path.Combine(privateRoot,"performance-resources");
            Check(!Directory.Exists(lease.performanceQuarantine) && !File.Exists(lease.performanceQuarantine),"PERFORMANCE_PRIVATE");
            diagnostic.performanceResources.packageVerified=true;diagnostic.performanceResources.baselineAbsent=true;diagnostic.performanceResources.status="ARMED";
            var performancePreference=new PerformancePreference();
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
                string[] defines={JourneyCandidateLinuxIdentity.Define};Check(ValidBuildProfile(BuildTarget.StandaloneLinux64,CandidateOptions,defines),"BUILD_PROFILE");
                currentSceneRole="NONE";diagnostic.activeTargetBeforeBuild=TargetKind(EditorUserBuildSettings.activeBuildTarget);diagnostic.stage="BUILD_PLAYER_ENTERED";Persist(diagnostic);
                result=BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes=Paths,target=BuildTarget.StandaloneLinux64,locationPathName=Output,options=CandidateOptions,extraScriptingDefines=defines });
                diagnostic.stage="BUILD_PLAYER_RETURNED";diagnostic.activeTargetAfterBuild=TargetKind(EditorUserBuildSettings.activeBuildTarget);diagnostic.leaseActiveAtBuildReturn=active!=null;Report(result,diagnostic);Persist(diagnostic);
                Check(result != null && result.summary.result==BuildResult.Succeeded && lease.processed.SetEquals(Paths),"BUILD_OR_SCENE_FAILED");
                VerifyPackedPerformanceExclusion(result,diagnostic.performanceResources,lease.processed.ToArray());
            }
            catch (Exception error)
            {
                if(diagnostic.stage=="BUILD_PLAYER_ENTERED") diagnostic.activeTargetAfterBuild=TargetKind(EditorUserBuildSettings.activeBuildTarget);
                RememberFailure(diagnostic,"PRIMARY","UNCLASSIFIED_EXCEPTION",ExceptionKind(error));throw;
            }
            finally
            {
                Close();diagnosticContext="RESTORATION";currentSceneRole="NONE";
                try
                {
                    performancePreference.Restore();diagnostic.performanceResources.preferenceRestored=true;
                    PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,oldBackend);PlayerSettings.fullScreenMode=oldWindow;
                    PlayerSettings.defaultScreenWidth=oldWidth;PlayerSettings.defaultScreenHeight=oldHeight;PlayerSettings.productName=oldProduct;PlayerSettings.resizableWindow=oldResize;
                    AssetDatabase.SaveAssets();
                }
                catch (Exception error) { RememberFailure(diagnostic,"RESTORATION","UNCLASSIFIED_EXCEPTION",ExceptionKind(error));throw; }
                finally
                {
                    try { File.WriteAllBytes(Settings,settings);diagnostic.settingsRestored=Hash(Settings)==HashBytes(settings);JourneySceneAuthoring.RestoreSceneSetup(setup); }
                    catch (Exception error) { RememberFailure(diagnostic,"RESTORATION","UNCLASSIFIED_EXCEPTION",ExceptionKind(error));throw; }
                    finally
                    {
                        diagnosticContext="VERIFICATION";
                        try { Verify(lease,false);diagnostic.sourceBytesUnchanged=true; }
                        catch (Exception error) { RememberFailure(diagnostic,"VERIFICATION","UNCLASSIFIED_EXCEPTION",ExceptionKind(error));throw; }
                        finally { Persist(diagnostic); }
                    }
                }
            }
            diagnosticContext="PRIMARY";
            PersistJson("JourneyEvidence/JourneyPreparation/linux-build-receipt.json",JsonUtility.ToJson(new Result { sourceCommit=request.sourceCommit,producerRunUrl=request.producerRunUrl,
                restorationProof=request.restorationProof ?? new JourneyCandidateAssetIntegration.FilePin { path="",sha256="" },assetProducerSourceCommit=request.assetProducerSourceCommit ?? "",assetProducerRunUrl=request.assetProducerRunUrl ?? "",restorationNativeXmlSha256=request.restorationNativeXmlSha256 ?? "",generatedReceiptSha256=request.generatedReceiptSha256,boundaryNativeXmlSha256=request.boundaryNativeXmlSha256,boundaryNativeCases=request.boundaryNativeCases,requestSha256=requestHash,executableSha256=Hash(Output),settingsRestored=true,sourceBytesUnchanged=true,scenes=Paths },true));
            diagnostic.stage="RECEIPT_WRITTEN";diagnostic.receiptWritten=true;Persist(diagnostic);
        }
    }
    public sealed class JourneyCandidatePerformanceIsolation : IPreprocessBuildWithReport
    {
        public int callbackOrder => 1;
        public void OnPreprocessBuild(BuildReport report) { JourneyCandidateLinuxBuild.IsolatePerformanceResources(report); }
    }
    public sealed class JourneyCandidateLinuxSceneGate : IProcessSceneWithReport
    {
        public int callbackOrder => 1000000;
        public void OnProcessScene(Scene scene,BuildReport report) { if(report != null) JourneyCandidateLinuxBuild.ProcessCandidateScene(scene,report); }
    }
}
