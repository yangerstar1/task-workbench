using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace Lottery.G3.PlayMode.Tests
{
    // Private raw logs and assertion messages never enter this append-only sidecar.
    // Each closed record is durable before the next frame; a killed final append
    // cannot truncate earlier records. The exporter discards only an incomplete tail.
    public static class G3WorldProgress
    {
        const string Assemblies="Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests";
        const int MaximumBytes=262144, MaximumRecords=128, MaximumRecordBytes=4096;
        const string Scope="WORLD_ROUTE_RAY_DIAGNOSTIC_NOT_TEST_PASS";
        const string RoutePattern=@"WORLD_ROUTE_V1 segment=(?:ENTRY_TO_TICKET_RACK|TICKET_RACK_TO_TABLE|ENTRY_TO_INVENTORY|INVENTORY_TO_SHELF_AISLE|AISLE_TO_TOOL_SHELF|TOOL_SHELF_TO_DRAWER|TABLE_TO_PHONE_AISLE|AISLE_TO_PHONE|PHONE_TO_RETURN_AISLE|RETURN_AISLE_TO_TABLE) phase=(?:BEGIN|SAMPLE|REACHED|ABORTED) elapsed=-?[0-9]{1,6}\.[0-9]{4} limit=45 frames=[0-9]{1,7} stationaryFrames=[0-9]{1,7} body=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) origin=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) destination=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) remaining=-?[0-9]{1,6}\.[0-9]{4} minRemaining=-?[0-9]{1,6}\.[0-9]{4} lastStep=-?[0-9]{1,6}\.[0-9]{4} pathMeters=-?[0-9]{1,6}\.[0-9]{4} maxFrameWall=-?[0-9]{1,6}\.[0-9]{4} maxUnscaledDelta=-?[0-9]{1,6}\.[0-9]{4} command=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) camera=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) cameraEuler=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) moveId=(?:-1|901) lookId=(?:-1|902) mode=[0-9]{1,2} focused=(?:True|False) awaitingRelease=(?:True|False) cameraWrite=(?:True|False)";
        const string RayPattern=@"WORLD_RAY_V2 kind=(?:NONE|CHARACTER_CONTROLLER|WORLD_TARGET|UNTARGETED_COLLIDER) trigger=(?:True|False) ownBody=(?:True|False) environment=(?:True|False) hitDistance=-?[0-9]{1,6}\.[0-9]{4} horizontalReach=-?[0-9]{1,6}\.[0-9]{4} body=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) camera=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) target=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) pixel=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) rayOrigin=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) rayDirection=\(-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4},-?[0-9]{1,6}\.[0-9]{4}\) foreignHits=[0-9]{1,7} foreignDistance=-?[0-9]{1,6}\.[0-9]{4} foreignController=(?:True|False) foreignTarget=(?:True|False) foreignNearestTies=[0-9]{1,7}";
        const string PhasePattern=@"WORLD_PHASE_V1 segment=(?:ENTRY_TO_TICKET_RACK|TICKET_RACK_TO_TABLE|ENTRY_TO_INVENTORY|INVENTORY_TO_SHELF_AISLE|AISLE_TO_TOOL_SHELF|TOOL_SHELF_TO_DRAWER|TABLE_TO_PHONE_AISLE|AISLE_TO_PHONE|PHONE_TO_RETURN_AISLE|RETURN_AISLE_TO_TABLE) frequency=[0-9]{1,16} intervals=[0-9]{1,16} frame=[0-9]{1,16} wallTicks=[0-9]{1,16} yieldTicks=[0-9]{1,16} resumeTicks=[0-9]{1,16} pumpCalls=[0-9]{1,16} pumpTicks=[0-9]{1,16} diagnosticCalls=[0-9]{1,16} diagnosticTicks=[0-9]{1,16} pollCalls=[0-9]{1,16} pollTicks=[0-9]{1,16} glyphCalls=[0-9]{1,16} glyphTicks=[0-9]{1,16} atlasNotifications=[0-9]{1,16} updateCalls=[0-9]{1,16} updateTicks=[0-9]{1,16} showCalls=[0-9]{1,16} showTicks=[0-9]{1,16} gcMax=[0-2] gc0=[0-9]{1,16} gc1=[0-9]{1,16} gc2=[0-9]{1,16} incomplete=[01] overflow=[01](?: cpuAvailable=[01] processCpuTicks=[0-9]{1,16})?";
        public static bool PhaseTimingEnabled=>Enabled;
        static int sequence;
        static bool writeFailed;
        static string Arg(string name){var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,name);return i>=0&&i+1<args.Length?args[i+1]:"";}
        static bool Enabled=>Arg("-g3RegressionProgress")=="1"&&Arg("-assemblyNames")==Assemblies&&Arg("-testPlatform")=="playmode"&&Arg("-g3RegressionShard")=="world";
        static string PathName=>Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/visual-regression-world/world-progress.jsonl"));
        static bool AllowedCase(string name)=>
            name=="Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputEntryToTicketRackAndTableUsesConcurrentMoveLookAndRelease"||
            name=="Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputStorageToolShelfDrawerAndPointerOwnershipArePhysical"||
            name=="Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputTableToPhysicalPhoneAndBackPreservesTicketAndCamera";
        static string Key(string name){using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(name))).Replace("-","").ToLowerInvariant();}
        public static void Record(string sample)
        {
            if(!Enabled||writeFailed)return;
            try
            {
                if(sample==null||sample.Length>2048||!(Regex.IsMatch(sample,"\\A"+RoutePattern+"\\z")||Regex.IsMatch(sample,"\\A"+RayPattern+"\\z")||Regex.IsMatch(sample,"\\A"+PhasePattern+"\\z")))throw new InvalidOperationException();
                var name=TestContext.CurrentContext.Test.FullName;
                if(!AllowedCase(name))throw new InvalidOperationException();
                var source=Arg("-probeCommit");var reviewed=Arg("-probeReviewedCommit");var run=Arg("-probeRunId");var attempt=Arg("-probeRunAttempt");
                if(!Regex.IsMatch(source,"\\A[0-9a-f]{40}\\z")||!Regex.IsMatch(reviewed,"\\A[0-9a-f]{40}\\z")||source==reviewed||!Regex.IsMatch(run,"\\A[1-9][0-9]{0,19}\\z")||attempt!="1")throw new InvalidOperationException();
                if(sequence>=MaximumRecords)throw new InvalidOperationException();
                var row=new Observation{sequence=sequence+1,sourceCommit=source,reviewedCandidateCommit=reviewed,runId=run,runAttempt=attempt,caseKey=Key(name),utc=DateTime.UtcNow.ToString("O"),sample=sample};
                byte[] bytes=Encoding.UTF8.GetBytes(JsonUtility.ToJson(row)+"\n");
                if(bytes.Length>MaximumRecordBytes)throw new InvalidOperationException();
                Directory.CreateDirectory(Path.GetDirectoryName(PathName));
                using(var stream=new FileStream(PathName,sequence==0?FileMode.CreateNew:FileMode.Append,FileAccess.Write,FileShare.Read))
                {
                    if(stream.Length+bytes.Length>MaximumBytes)throw new InvalidOperationException();
                    stream.Write(bytes,0,bytes.Length);stream.Flush(true);
                }
                sequence++;
            }
            catch
            {
                // Stop after the first failed append, so a partial row can only be
                // the final row. No raw exception or sample is echoed on failure.
                writeFailed=true;Debug.LogWarning("G3_WORLD_PROGRESS_WRITE_FAILED");
            }
        }
        [Serializable] sealed class Observation
        {
            public int schemaVersion=1,sequence;public string scope=Scope,status="OBSERVATIONS_ONLY_NOT_TEST_PASS",sourceCommit,reviewedCandidateCommit,runId,runAttempt,caseKey,utc,sample;
        }
    }
}

