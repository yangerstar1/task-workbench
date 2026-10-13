#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;

namespace Lottery.G3.VisualCandidate.Tests
{
    // Capture-only observations. No log text, stack, path or test result is serialized.
    // Errors keep their original Unity handling; all observation writes are best effort.
    internal static class VisualCandidateStartupProbe
    {
        const string Scope="CAPTURE_STARTUP_DIAGNOSTIC_NOT_TEST_PASS", Status="OBSERVATIONS_ONLY_NOT_TEST_PASS";
        const int MaximumBytes=32768,MaximumEvents=64,MaximumCounter=1000000;
        static readonly string[] Stages={"ARMED","PREBUILD_RETURNED","ERROR_LOG","UTF_ERROR","UTF_RUN_STARTED","UTF_RUN_FINISHED","BEFORE_RELOAD","DOMAIN_RESTORED","EXITING_EDIT_MODE","ENTERED_PLAY_MODE","EXITING_PLAY_MODE","ENTERED_EDIT_MODE","QUITTING"};
        static readonly string[] Codes={"NONE","UNCLASSIFIED","SCENE_UNTITLED","SCENE_ACTIVE","REFLECTION_RECIPE","REFLECTION_LAYOUT","SHADER_COMPILE","SCRIPT_COMPILE","PREBUILD_SETUP","ASSEMBLY_RELOAD","TEST_RUNNER_CONTEXT","TEST_RUNNER_CANCELLED","TEST_RUNNER_UNEXPECTED","LIFECYCLE_WRITE"};
        static readonly string[] Kinds={"NONE","INVALID_OPERATION","ARGUMENT","NULL_REFERENCE","IO","UNITY","AGGREGATE","OTHER"};
        static readonly string[] Origins={"NONE","PREBUILD_SETUP","GENERATE_CONTEXT","PREPARE_PLAY_MODE","ENTER_PLAY_MODE","TEST_PROGRESS","CALLBACKS","TASK_RUNNER","ASSET_DATABASE","REFLECTION_BAKER","UNKNOWN"};
        static readonly HashSet<string> seenLogs=new HashSet<string>();
        static readonly Callbacks callbacks=new Callbacks();
        static Receipt receipt;static bool registered,writing;
        static string PathName=>Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/visual-candidate/startup-progress.json"));
        static string Arg(string key){var a=Environment.GetCommandLineArgs();int i=Array.IndexOf(a,key);return i>=0&&i+1<a.Length?a[i+1]:"";}
        static bool Eligible()=>Arg("-assemblyNames")=="Lottery.G3.VisualCandidate.Tests"&&Regex.IsMatch(Arg("-probeCommit"),"^[0-9a-f]{40}$")&&Regex.IsMatch(Arg("-probeRunId"),"^[1-9][0-9]{0,19}$")&&Regex.IsMatch(Arg("-probeRunAttempt"),"^[1-9][0-9]{0,19}$");
        public static void Arm()
        {
            if(!Eligible())return;
            try
            {
                receipt=new Receipt{sourceCommit=Arg("-probeCommit"),runId=Arg("-probeRunId"),runAttempt=Arg("-probeRunAttempt"),startedUtc=DateTime.UtcNow.ToString("O")};
                seenLogs.Clear();Register();Mark("ARMED");
            }
            catch{if(receipt!=null)receipt.diagnosticWriteFailed=true;}
        }
        public static void PrebuildReturned()=>Mark("PREBUILD_RETURNED");
        [InitializeOnLoadMethod]
        static void RestoreAfterDomainReload()
        {
            if(!Eligible())return;
            try
            {
                if(!File.Exists(PathName)||new FileInfo(PathName).Length>MaximumBytes)return;
                var restored=JsonUtility.FromJson<Receipt>(File.ReadAllText(PathName));
                if(!Valid(restored))return;
                receipt=restored;Register();Mark("DOMAIN_RESTORED");
            }
            catch{if(receipt!=null)receipt.diagnosticWriteFailed=true;}
        }
        static bool Valid(Receipt r)
        {
            if(r==null||r.schemaVersion!=1||r.scope!=Scope||r.status!=Status||r.sourceCommit!=Arg("-probeCommit")||r.runId!=Arg("-probeRunId")||r.runAttempt!=Arg("-probeRunAttempt")||r.events==null||r.events.Count==0||r.events.Count>MaximumEvents||r.events[0].stage!="ARMED")return false;
            if(!DateTime.TryParseExact(r.startedUtc,"O",CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind,out _))return false;
            if(!Counters(r.errorCount,r.assertCount,r.exceptionCount,r.utfErrorCount))return false;
            long prior=-1;
            foreach(var e in r.events)
            {
                if(e==null||!Stages.Contains(e.stage)||!Codes.Contains(e.code)||!Kinds.Contains(e.exceptionKind)||!Origins.Contains(e.origin)||e.elapsedMs<prior||e.elapsedMs>3600000||!Counters(e.errorCount,e.assertCount,e.exceptionCount,e.utfErrorCount))return false;
                prior=e.elapsedMs;
            }
            return true;
        }
        static bool Counters(params int[] values)=>values.All(v=>v>=0&&v<=MaximumCounter);
        static void Register()
        {
            if(registered)return;
            Application.logMessageReceived+=OnLog;
            EditorApplication.playModeStateChanged+=OnPlayMode;
            EditorApplication.quitting+=OnQuitting;
            AssemblyReloadEvents.beforeAssemblyReload+=BeforeReload;
            // Observe before the command-line exit callback without changing its result.
            TestRunnerApi.RegisterTestCallback(callbacks,int.MaxValue);
            registered=true;
        }
        static void Detach()
        {
            Application.logMessageReceived-=OnLog;
            EditorApplication.playModeStateChanged-=OnPlayMode;
            EditorApplication.quitting-=OnQuitting;
            AssemblyReloadEvents.beforeAssemblyReload-=BeforeReload;
            TestRunnerApi.UnregisterTestCallback(callbacks);registered=false;
        }
        static void BeforeReload(){Mark("BEFORE_RELOAD");try{Detach();}catch{if(receipt!=null)receipt.diagnosticWriteFailed=true;}}
        static void OnQuitting(){Mark("QUITTING");try{Detach();}catch{if(receipt!=null)receipt.diagnosticWriteFailed=true;}}
        static void OnPlayMode(PlayModeStateChange state)
        {
            switch(state)
            {
                case PlayModeStateChange.ExitingEditMode:Mark("EXITING_EDIT_MODE");break;
                case PlayModeStateChange.EnteredPlayMode:Mark("ENTERED_PLAY_MODE");break;
                case PlayModeStateChange.ExitingPlayMode:Mark("EXITING_PLAY_MODE");break;
                case PlayModeStateChange.EnteredEditMode:Mark("ENTERED_EDIT_MODE");break;
            }
        }
        static void Increment(ref int value){if(value<MaximumCounter)value++;else receipt.eventLimitReached=true;}
        static void OnLog(string condition,string stack,LogType type)
        {
            if(receipt==null||writing)return;
            if(type!=LogType.Error&&type!=LogType.Assert&&type!=LogType.Exception)return;
            try
            {
                if(type==LogType.Error)Increment(ref receipt.errorCount);else if(type==LogType.Assert)Increment(ref receipt.assertCount);else Increment(ref receipt.exceptionCount);
                // Consume text only for closed categories. Never retain either input string.
                string code=Classify(condition),kind=ExceptionKind(condition,type==LogType.Exception),origin=Origin(stack);
                string key=((int)type)+"|"+code+"|"+kind+"|"+origin;
                if(seenLogs.Contains(key)){Write();return;}
                if(seenLogs.Count>=32){receipt.eventLimitReached=true;Write();return;}
                seenLogs.Add(key);Mark("ERROR_LOG",code,kind,origin);
            }
            catch{receipt.diagnosticWriteFailed=true;}
        }
        static string Classify(string text)
        {
            if(string.IsNullOrEmpty(text))return "UNCLASSIFIED";
            if(text.IndexOf("untitled scene unsaved",StringComparison.OrdinalIgnoreCase)>=0)return "SCENE_UNTITLED";
            if(text.Contains("scene active-handle")||text.Contains("Could not activate isolated"))return "SCENE_ACTIVE";
            if(text.Contains("Invalid authored shop reflection recipe"))return "REFLECTION_RECIPE";
            if(text.Contains("reflection cubemap")||text.Contains("CUBEMAP_LAYOUT"))return "REFLECTION_LAYOUT";
            if(text.Contains("Shader error")||text.Contains("shader compilation"))return "SHADER_COMPILE";
            if(text.Contains("error CS")||text.Contains("Scripts had compilation errors"))return "SCRIPT_COMPILE";
            if(text.Contains("IPrebuildSetup")||text.Contains("PrebuildSetup"))return "PREBUILD_SETUP";
            if(text.Contains("Assembly reload")||text.Contains("assembly reload"))return "ASSEMBLY_RELOAD";
            if(text.Contains("TestExecutionContext")||text.Contains("PreparePlayModeRun"))return "TEST_RUNNER_CONTEXT";
            if(text.Contains("TestRunCanceled")||text.Contains("test run was cancelled"))return "TEST_RUNNER_CANCELLED";
            if(text.Contains("unexpected error happened while running tests")||text.Contains("unexpected errors happened while running tests"))return "TEST_RUNNER_UNEXPECTED";
            if(text.Contains("VISUAL_CANDIDATE_LIFECYCLE_WRITE_FAILED"))return "LIFECYCLE_WRITE";
            return "UNCLASSIFIED";
        }
        static string ExceptionKind(string text,bool exception)
        {
            if(string.IsNullOrEmpty(text))return exception?"OTHER":"NONE";
            string s=text.StartsWith("System.",StringComparison.Ordinal)?text.Substring(7):text;
            if(s.StartsWith("InvalidOperationException:",StringComparison.Ordinal))return "INVALID_OPERATION";
            if(s.StartsWith("ArgumentException:",StringComparison.Ordinal)||s.StartsWith("ArgumentNullException:",StringComparison.Ordinal)||s.StartsWith("ArgumentOutOfRangeException:",StringComparison.Ordinal))return "ARGUMENT";
            if(s.StartsWith("NullReferenceException:",StringComparison.Ordinal))return "NULL_REFERENCE";
            if(s.StartsWith("IO.",StringComparison.Ordinal)||s.StartsWith("IOException:",StringComparison.Ordinal))return "IO";
            if(s.StartsWith("UnityEngine.UnityException:",StringComparison.Ordinal)||s.StartsWith("UnityException:",StringComparison.Ordinal))return "UNITY";
            if(s.StartsWith("AggregateException:",StringComparison.Ordinal))return "AGGREGATE";
            return exception?"OTHER":"NONE";
        }
        static string Origin(string stack)
        {
            if(string.IsNullOrEmpty(stack))return "UNKNOWN";
            if(stack.Contains("PrebuildSetupTask")||stack.Contains("BuildActionTaskBase"))return "PREBUILD_SETUP";
            if(stack.Contains("GenerateContextTask"))return "GENERATE_CONTEXT";
            if(stack.Contains("PreparePlayModeRunTask"))return "PREPARE_PLAY_MODE";
            if(stack.Contains("EnterPlayModeTask"))return "ENTER_PLAY_MODE";
            if(stack.Contains("TestProgressTask"))return "TEST_PROGRESS";
            if(stack.Contains("CallbacksDelegator"))return "CALLBACKS";
            if(stack.Contains("G3ShopReflectionBaker"))return "REFLECTION_BAKER";
            if(stack.Contains("AssetDatabase"))return "ASSET_DATABASE";
            if(stack.Contains("TestJobRunner"))return "TASK_RUNNER";
            return "UNKNOWN";
        }
        static void Mark(string stage,string code="NONE",string kind="NONE",string origin="NONE")
        {
            if(receipt==null)return;
            try
            {
                if(!Stages.Contains(stage)||!Codes.Contains(code)||!Kinds.Contains(kind)||!Origins.Contains(origin)){receipt.diagnosticWriteFailed=true;return;}
                if(receipt.events.Count>=MaximumEvents){receipt.eventLimitReached=true;Write();return;}
                long elapsed=Math.Max(0,(long)(DateTime.UtcNow-DateTime.ParseExact(receipt.startedUtc,"O",CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind)).TotalMilliseconds);
                if(receipt.events.Count>0)elapsed=Math.Max(elapsed,receipt.events[receipt.events.Count-1].elapsedMs);
                if(elapsed>3600000){receipt.eventLimitReached=true;Write();return;}
                receipt.events.Add(new Event{stage=stage,code=code,exceptionKind=kind,origin=origin,elapsedMs=elapsed,errorCount=receipt.errorCount,assertCount=receipt.assertCount,exceptionCount=receipt.exceptionCount,utfErrorCount=receipt.utfErrorCount,
                    isPlaying=EditorApplication.isPlaying,isPlayingOrWillChangePlaymode=EditorApplication.isPlayingOrWillChangePlaymode,isCompiling=EditorApplication.isCompiling,isUpdating=EditorApplication.isUpdating});
                Write();
            }
            catch{receipt.diagnosticWriteFailed=true;}
        }
        static void Write()
        {
            if(receipt==null||writing)return;writing=true;
            try
            {
                string json=JsonUtility.ToJson(receipt,false);
                if(Encoding.UTF8.GetByteCount(json)>MaximumBytes){receipt.diagnosticWriteFailed=true;return;}
                Directory.CreateDirectory(Path.GetDirectoryName(PathName));File.WriteAllText(PathName,json,new UTF8Encoding(false));
            }
            catch{receipt.diagnosticWriteFailed=true;}
            finally{writing=false;}
        }
        sealed class Callbacks:IErrorCallbacks
        {
            public void OnError(string message)
            {
                if(receipt==null)return;
                try{Increment(ref receipt.utfErrorCount);Mark("UTF_ERROR",Classify(message),ExceptionKind(message,false),"UNKNOWN");}
                catch{receipt.diagnosticWriteFailed=true;}
            }
            public void RunStarted(ITestAdaptor testsToRun)=>Mark("UTF_RUN_STARTED");
            public void RunFinished(ITestResultAdaptor result)=>Mark("UTF_RUN_FINISHED");
            public void TestStarted(ITestAdaptor test){}
            public void TestFinished(ITestResultAdaptor result){}
        }
        [Serializable] sealed class Receipt
        {
            public int schemaVersion=1,errorCount,assertCount,exceptionCount,utfErrorCount;
            public string scope=Scope,status=Status,sourceCommit,runId,runAttempt,startedUtc;
            public bool diagnosticWriteFailed,eventLimitReached;
            public List<Event> events=new List<Event>();
        }
        [Serializable] sealed class Event
        {
            public string stage,code,exceptionKind,origin;
            public long elapsedMs;
            public int errorCount,assertCount,exceptionCount,utfErrorCount;
            public bool isPlaying,isPlayingOrWillChangePlaymode,isCompiling,isUpdating;
        }
    }
}
#endif
