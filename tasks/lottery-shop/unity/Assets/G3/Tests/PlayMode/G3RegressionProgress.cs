using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using NUnit.Framework.Interfaces;
using UnityEngine;
using UnityEngine.TestRunner;

[assembly: TestRunCallback(typeof(Lottery.G3.PlayMode.Tests.G3RegressionProgress))]
namespace Lottery.G3.PlayMode.Tests
{
    // UTF 1.6.0 callback. Bounded diagnostic milestones only; never a test verdict.
    // No assertion message, stack, test output, game state, or environment is read.
    public sealed class G3RegressionProgress : ITestRunCallback
    {
        const string Scope="DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS";
        const string Assemblies="Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests";
        const int MaximumBytes=65536, MaximumEvents=128;
        // SHA-256 of the exact 35 current contract fullnames; tested against that contract.
        static readonly HashSet<string> CaseKeys=new HashSet<string> {
            "159863c79e23387097d03394a700065bae8959f64c867293c6740b6d64a97e5e",
            "d879a954e13be0e65ee8184591f09d30979a2f77edb4f4f4150e73bf800b8a09",
            "c6ceb797f9a2ed996f738f47b26464eb008bf6863a315d62120d8817f21464ab",
            "2894cdfff905214154e75544fa7b2499ae4e164417e27d7287aae4a1e4b89ac9",
            "bcee96fa01f8ebafa12f0fcadda0c96de8f436de3189916158624a73c145f3ac",
            "4250ad1729e4448b9b7d53b33a3314de9d264e429f2569164d81960ff7d95ef3",
            "05563e3367676910d71725a9568d57958c27ec442ffafa1cb0a6a3ca4db78d6a",
            "ef3058f328d787cd4600f411326ce0a55af07700f456d44a06b3960f1208af57",
            "748f76c6251f69a43b96d755c00fe3fa0eb6299994120e7e2d617c2c61d9204b",
            "0dcc2cb8aa4a6741d81fed1aad827d33bffad89263e9fd5996737b4c15ebdffd",
            "303833244645a23c9cc66438dad7bb7a6b8d6ff0c93786587e2656ffe0a83262",
            "682dbe30a7c97187abbd8b6882106bb3d4866c20ef88c51085a5370d345362c7",
            "bd42f776628e53329d6572a9c1bfcc73f275f2ffae79c590b2891094d283a834",
            "110792d2c55594ecd0fa76d75e2beed75b9665caae8a5fdc36d8097090f0ea11",
            "bd128e7b05c001782ed9d0209be2c1870b74fbbe7a3c0b4c800d5846451867b4",
            "ac1113f0a85c5edef751259c9b25c46461e9a4b097d0963b5ba97a78a90fba2b",
            "289e834c7efd67348309fe73373c83f92e3c8d5d7e87cbd778f37959dce4ec84",
            "39275743544bb43f85579a99848bd9abe998fb551bd594ee7e314bd424e8aab0",
            "7d60c4e0b423d331e6f97966ffde2772626efd4bccd932965ce2a85a9a533f6b",
            "7a06832f3f96f94fdaa90947003c1209b8580a90e1e5f267f7e4368543e72b21",
            "20370f2e707df35b47266771a89b8bf90f22fcb242d2577acb92d7ba66366adb",
            "e24d8c202af94756375fbe6b48b78055e1d1ce1e9f00e7b68857d43effa95dd8",
            "e13df05955108708d81571009da3aadf0baf9b35bd8d7b90fbb6bace99720316",
            "284b9812ee19ee43cfd61e85339d11a20051e2089b14382d66cf5038233e9b23",
            "d3d89ab801835a848c95e91f3fab2a0dbdfb699cce3342c63e98db5be9444a25",
            "3caf6d01528b160e74924f7077bde677d29e2daaba30aff03dbdbefd5e9ae474",
            "f6c7bd93f0a035adfc62b49e910157937b6a840ae3d4fd70d5b082f453aa5d5b",
            "4932b1ed32d39da55da51c2b04793bfe9f29e0b0f478d749da3be105ab8575b9",
            "bc6462469dd2c29f067e9892467074baae1e330e9852759e1c2f190ac62f0bb0",
            "23a8e2a7ba8307f61a1d007f09939524cade7dc23395c76fc2c8c17641dbe563",
            "d33d951660c6d7aac9fc56da5f368f0ecac58df09bcee15775445affaf228997",
            "96a08d8f9074ab4af2ba3950c4c77c0b3d23ae9a6999fdb62f33532e9f0802ea",
            "419527d5c96765c8aab22f3f7a7597bbb7bde5d05f2c511d773650cc12ce5d06",
            "0ece37a8dec72f6e5d6c192283c548bdc5da659f4834ca315cb45102b14589c0",
            "ca78d437c219bc73b4be929ff7a2655291b915aa3813e4dd74213d5cfecb1604",
        };
        static string Arg(string name){var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,name);return i>=0&&i+1<args.Length?args[i+1]:"";}
        static bool Enabled=>Arg("-g3RegressionProgress")=="1"&&Arg("-assemblyNames")==Assemblies&&Arg("-testPlatform")=="playmode";
        static string PathName=>Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/visual-regression-play/test-progress.json"));
        public void RunStarted(ITest testsToRun){if(Enabled)Mark("run-start","","UNAVAILABLE");}
        public void RunFinished(ITestResult testResults){if(Enabled)Mark("run-end","","UNAVAILABLE");}
        public void TestStarted(ITest test){if(Enabled&&!test.IsSuite)Mark("case-start",Key(test.FullName),"UNAVAILABLE");}
        public void TestFinished(ITestResult result)
        {
            if(!Enabled||result.Test.IsSuite)return;
            string outcome;
            switch(result.ResultState.Status){case TestStatus.Passed:outcome="PASSED";break;case TestStatus.Failed:outcome="FAILED";break;case TestStatus.Skipped:outcome="SKIPPED";break;default:outcome="INCONCLUSIVE";break;}
            Mark("case-end",Key(result.Test.FullName),outcome);
        }
        static string Key(string name){using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(name))).Replace("-","").ToLowerInvariant();}
        static void Mark(string stage,string key,string outcome)
        {
            try
            {
                var source=Arg("-probeCommit");var reviewed=Arg("-probeReviewedCommit");var run=Arg("-probeRunId");var attempt=Arg("-probeRunAttempt");
                if(!Regex.IsMatch(source,"^[0-9a-f]{40}$")||!Regex.IsMatch(reviewed,"^[0-9a-f]{40}$")||source==reviewed||!Regex.IsMatch(run,"^[1-9][0-9]*$")||!Regex.IsMatch(attempt,"^[1-9][0-9]*$"))throw new InvalidOperationException();
                if(stage.StartsWith("case-",StringComparison.Ordinal)&&!CaseKeys.Contains(key))throw new InvalidOperationException();
                Receipt receipt;
                if(File.Exists(PathName))
                {
                    if(new FileInfo(PathName).Length>MaximumBytes)throw new InvalidOperationException();
                    receipt=JsonUtility.FromJson<Receipt>(File.ReadAllText(PathName));
                    if(receipt==null||receipt.schemaVersion!=1||receipt.scope!=Scope||receipt.status!="MILESTONES_ONLY_NOT_TEST_PASS"||receipt.sourceCommit!=source||receipt.reviewedCandidateCommit!=reviewed||receipt.runId!=run||receipt.runAttempt!=attempt||receipt.events==null||receipt.events.Length==0||receipt.events[0].stage!="run-start")throw new InvalidOperationException();
                }
                else
                {
                    if(stage!="run-start")throw new InvalidOperationException();
                    receipt=new Receipt{sourceCommit=source,reviewedCandidateCommit=reviewed,runId=run,runAttempt=attempt,events=new Event[0]};
                }
                var events=new List<Event>(receipt.events);
                // Framework suite callbacks never add a second run-start record.
                if(stage=="run-start"&&events.Count>0)return;
                if(events.Count>=MaximumEvents)throw new InvalidOperationException();
                var now=DateTime.UtcNow;
                long elapsed=events.Count==0?0:Math.Max(events.Last().elapsedMs,Math.Max(0,(long)(now-DateTime.Parse(events[0].utc,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind)).TotalMilliseconds));
                if(elapsed>86400000)throw new InvalidOperationException();
                events.Add(new Event{sequence=events.Count+1,stage=stage,caseKey=key,result=outcome,elapsedMs=elapsed,utc=now.ToString("O")});receipt.events=events.ToArray();
                string json=JsonUtility.ToJson(receipt,true);if(Encoding.UTF8.GetByteCount(json)>MaximumBytes)throw new InvalidOperationException();
                Directory.CreateDirectory(Path.GetDirectoryName(PathName));File.WriteAllText(PathName,json);
            }
            catch
            {
                // Never feed callback I/O failures or assertion details into a log.
                // Missing/invalid progress remains missing; NUnit/real exit gates stay independent.
                Debug.LogWarning("G3_REGRESSION_PROGRESS_WRITE_FAILED");
            }
        }
        [Serializable] sealed class Event{public int sequence;public string stage,caseKey,result,utc;public long elapsedMs;}
        [Serializable] sealed class Receipt
        {
            public int schemaVersion=1;public string scope=Scope,status="MILESTONES_ONLY_NOT_TEST_PASS",sourceCommit,reviewedCandidateCommit,runId,runAttempt;public Event[] events;
        }
    }
}
