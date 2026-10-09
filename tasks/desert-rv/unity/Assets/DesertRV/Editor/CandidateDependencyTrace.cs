using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEngine;

namespace DesertRV.Editor
{
    // Read-only bounded observations. Never saves assets, changes the canonical digest,
    // resolves virtual Packages differently, or refreshes a stored expected hash.
    public sealed class CandidateDependencyTrace
    {
        [Serializable] sealed class Header
        {
            public string side="native",subject,phase,aggregateSha256;
            public bool subjectExistsAtCwd,subjectExistsAtProjectRoot,cwdIsProject,aggregateValid;
            public int dependencyCount,hashedFileCount,missingFileCount,omittedItems;
        }
        [Serializable] sealed class Entry
        {
            public string side="native",subject,phase,file,sha256;
            public bool exists,projectExists;
            public long bytes;
        }
        readonly Header header;readonly string projectRoot;
        readonly List<Entry> entries=new List<Entry>();static int sequence;
        CandidateDependencyTrace(string subject)
        {
            projectRoot=Path.GetDirectoryName(Application.dataPath);
            header=new Header{subject=subject,phase="native-"+System.Threading.Interlocked.Increment(ref sequence),
                subjectExistsAtCwd=File.Exists(subject),subjectExistsAtProjectRoot=File.Exists(Path.Combine(projectRoot,subject)),
                cwdIsProject=string.Equals(Path.GetFullPath(".").TrimEnd(Path.DirectorySeparatorChar),Path.GetFullPath(projectRoot).TrimEnd(Path.DirectorySeparatorChar),StringComparison.Ordinal)};
        }
        static bool CandidatePath(string path)=>Regex.IsMatch(path??"","^Assets/DesertRV/CandidateArtImports/[a-z0-9][a-z0-9-]{3,79}/Candidate\\.prefab$");
        public static CandidateDependencyTrace Begin(string path)=>CandidatePath(path)?new CandidateDependencyTrace(path):null;
        public void DependencyCount(int count)=>header.dependencyCount=count;
        public void Record(string path,bool exists,byte[] bytes)
        {
            if(exists)header.hashedFileCount++;else header.missingFileCount++;
            if(entries.Count>=600||!PublicPath(path)){header.omittedItems++;return;}
            string hash="";
            if(exists)using(var algorithm=SHA256.Create())hash=BitConverter.ToString(algorithm.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
            entries.Add(new Entry{subject=header.subject,phase=header.phase,file=path,exists=exists,projectExists=File.Exists(Path.Combine(projectRoot,path)),bytes=exists?bytes.LongLength:-1,sha256=hash});
        }
        public void Finish(string digest)
        {
            header.aggregateSha256=Regex.IsMatch(digest??"","^[a-f0-9]{64}$")?digest:"";
            header.aggregateValid=header.aggregateSha256.Length==64;
            Debug.Log("CANDIDATE_DEPENDENCY_HEADER "+JsonUtility.ToJson(header));
            // Chunked log records avoid one giant JSON line and bound stack-trace overhead.
            for(int i=0;i<entries.Count;i+=12)
                Debug.Log(string.Join("\n",entries.Skip(i).Take(12).Select(e=>"CANDIDATE_DEPENDENCY_ITEM "+JsonUtility.ToJson(e))));
        }
        static bool PublicPath(string path)
        {
            if(string.IsNullOrEmpty(path)||path.Length>512||path.Any(char.IsControl)||Path.IsPathRooted(path)||path.Contains('\\')||path.Contains(':')||path.Split('/').Any(s=>s==""||s=="."||s==".."))return false;
            return path.StartsWith("Assets/DesertRV/",StringComparison.Ordinal)||Regex.IsMatch(path,"^Packages/com\\.unity\\.[a-z0-9_.-]+/")||
                path=="Resources/unity_builtin_extra"||path=="Resources/unity_builtin_extra.meta"||path=="Library/unity default resources"||path=="Library/unity default resources.meta";
        }
        // Called after the real material persistence test has cleaned up its own fixture.
        // This additional observation is not assigned back to import/capture evidence.
        public static void ObserveAfterMaterialTest()
        {
            try
            {
                const string reportPath="JourneyEvidence/CandidateArt/import-report.json";
                if(!File.Exists(reportPath))return;
                var report=JsonUtility.FromJson<JourneyCandidateArtImport.Report>(File.ReadAllText(reportPath));
                if(report==null||!CandidatePath(report.prefab))return;
                Debug.Log("CANDIDATE_DEPENDENCY_PROBE phase=after-material-test storedValid="+Regex.IsMatch(report.dependencySha256??"","^[a-f0-9]{64}$")+" storedLength="+(report.dependencySha256??"").Length);
                JourneyContentChecks.DependencySha256(report.prefab);
            }
            catch(Exception error){Debug.Log("CANDIDATE_DEPENDENCY_PROBE phase=after-material-test observationError="+error.GetType().Name);}
        }
    }
}
