using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor.PackageManager;
using UnityEngine;
using static DesertRV.Editor.JourneyCandidateArtImport;

namespace DesertRV.Editor
{
    // Preserve ONLY the four declared, pinned URP dependency bytes for the host verifier.
    // This private directory is outside Assets/Packages and is never a public package export.
    public static class CandidatePackageSnapshot
    {
        const string PackageName="com.unity.render-pipelines.universal";
        const string PackageVersion="17.3.0";
        const string PackageRoot="Packages/"+PackageName;
        const string SnapshotRoot="CandidatePackageSnapshot";
        const string ProjectManifestSha="1a7b8e1c8005e0e9b8255908ae502b4474cfce05331ed3952221b60ee967a485";
        const string ProjectLockSha="e7ed5ba93dacba63a07b0ba5f2751ace24e249edad4b0d96fe9ee5920945be36";
        [Serializable] public sealed class FileRecord {public string path,sha256;public long bytes;}
        [Serializable] sealed class Manifest
        {
            public int schema=1;
            public string editorVersion,packageName,packageVersion,packageSource,manifestSha256,lockSha256;
            public FileRecord[] files;
        }
        [Serializable] sealed class PackageIdentity {public string name,version;}
        static readonly FileRecord[] Pins={
            new FileRecord{path=PackageRoot+"/Editor/AssetVersion.cs",bytes=148,sha256="96ed27e15286cda1fdada6923e804887b6447a905b38360e0f5561f79cd0344c"},
            new FileRecord{path=PackageRoot+"/Editor/AssetVersion.cs.meta",bytes=243,sha256="e7ec88783b56ae3a5adbe60d3ab71fd3b6fe269932af20218d4cc00eb3879868"},
            new FileRecord{path=PackageRoot+"/Shaders/Lit.shader",bytes=22877,sha256="6f4648b6b5271132cfed1d7d7c771ba0a73ef7972470d6694047804d259c0997"},
            new FileRecord{path=PackageRoot+"/Shaders/Lit.shader.meta",bytes=217,sha256="f0db005307ffe5480c40a402ca5bfb0b3726259031a86e255e49626228ceb008"}
        };
        public static void Capture(string[] dependencies)
        {
            Check(Application.unityVersion=="6000.3.19f1","Private package snapshot requires the pinned Unity version.");
            var expected=new HashSet<string>(Pins.Where(p=>!p.path.EndsWith(".meta",StringComparison.Ordinal)).Select(p=>p.path));
            Check(dependencies!=null&&expected.SetEquals(dependencies.Where(p=>p.StartsWith("Packages/",StringComparison.Ordinal))),"Only the two observed URP package dependencies are declared.");
            Check(Sha("Packages/manifest.json")==ProjectManifestSha&&Sha("Packages/packages-lock.json")==ProjectLockSha,"Reviewed package manifest/lock changed; do not infer a new package version.");
            var info=PackageInfo.FindForAssetPath(PackageRoot+"/Shaders/Lit.shader");
            Check(info!=null&&info.name==PackageName&&info.version==PackageVersion&&info.source==PackageSource.BuiltIn&&info.assetPath==PackageRoot,
                "Actual registered package identity differs from pinned builtin URP 17.3.0.");
            Check(!string.IsNullOrWhiteSpace(info.resolvedPath)&&Path.IsPathRooted(info.resolvedPath)&&Directory.Exists(info.resolvedPath),"Actual resolved URP package directory is unavailable.");
            string resolvedRoot=Path.GetFullPath(info.resolvedPath).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
            var metadata=JsonUtility.FromJson<PackageIdentity>(File.ReadAllText(Path.Combine(resolvedRoot,"package.json")));
            Check(metadata!=null&&metadata.name==PackageName&&metadata.version==PackageVersion,"Actual resolved package.json disagrees with PackageInfo.");
            var scriptInfo=PackageInfo.FindForAssetPath(PackageRoot+"/Editor/AssetVersion.cs");
            Check(scriptInfo!=null&&scriptInfo.name==info.name&&scriptInfo.version==info.version&&scriptInfo.source==info.source&&scriptInfo.assetPath==PackageRoot&&
                !string.IsNullOrWhiteSpace(scriptInfo.resolvedPath)&&Path.IsPathRooted(scriptInfo.resolvedPath)&&
                Path.GetFullPath(scriptInfo.resolvedPath).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar==resolvedRoot,
                "AssetVersion metadata and Lit shader must originate from the same registered package.");
            var payload=new Dictionary<string,byte[]>();
            foreach(var pin in Pins)
            {
                string relative=pin.path.Substring(PackageRoot.Length+1);
                string resolved=Path.GetFullPath(Path.Combine(resolvedRoot,relative));
                Check(resolved.StartsWith(resolvedRoot,StringComparison.Ordinal)&&File.Exists(resolved),"Pinned resolved package file is missing.");
                byte[] original=File.ReadAllBytes(pin.path),physical=File.ReadAllBytes(resolved);
                Check(original.LongLength==pin.bytes&&Hash(original)==pin.sha256&&original.SequenceEqual(physical),
                    "Actual virtual/resolved package bytes differ from the reviewed exact source: "+pin.path);
                payload.Add(pin.path,original);
            }
            var manifest=new Manifest{editorVersion=Application.unityVersion,packageName=PackageName,packageVersion=PackageVersion,packageSource="builtin",
                manifestSha256=ProjectManifestSha,lockSha256=ProjectLockSha,files=Pins};
            byte[] manifestBytes=new UTF8Encoding(false).GetBytes(JsonUtility.ToJson(manifest,true)+"\n");
            if(Directory.Exists(SnapshotRoot)||File.Exists(SnapshotRoot))
            {
                ValidateSnapshotTree();
                Check(File.ReadAllBytes(SnapshotRoot+"/manifest.json").SequenceEqual(manifestBytes),"Existing private package snapshot manifest differs; never overwrite it.");
                foreach(var pin in Pins)Check(File.ReadAllBytes(SnapshotRoot+"/"+pin.path).SequenceEqual(payload[pin.path]),"Existing private package snapshot bytes differ; never overwrite them.");
                return;
            }
            Directory.CreateDirectory(SnapshotRoot);
            foreach(var pin in Pins)
            {
                string target=SnapshotRoot+"/"+pin.path;Directory.CreateDirectory(Path.GetDirectoryName(target));
                using(var stream=new FileStream(target,FileMode.CreateNew,FileAccess.Write,FileShare.None))stream.Write(payload[pin.path],0,payload[pin.path].Length);
            }
            using(var stream=new FileStream(SnapshotRoot+"/manifest.json",FileMode.CreateNew,FileAccess.Write,FileShare.None))stream.Write(manifestBytes,0,manifestBytes.Length);
            ValidateSnapshotTree();
            foreach(var pin in Pins)Check(Sha(SnapshotRoot+"/"+pin.path)==pin.sha256,"Private package snapshot readback hash differs.");
            Debug.Log("CANDIDATE_PACKAGE_SNAPSHOT package="+PackageName+" version="+PackageVersion+" source=builtin files=4 private=true canonicalNamesPreserved=true");
        }
        static void ValidateSnapshotTree()
        {
            var files=new HashSet<string>(Pins.Select(p=>p.path)){"manifest.json"};
            var directories=new HashSet<string>();
            foreach(var path in files)
            {
                string parent=Path.GetDirectoryName(path);
                while(!string.IsNullOrEmpty(parent)){directories.Add(parent.Replace('\\','/'));parent=Path.GetDirectoryName(parent);}
            }
            string root=Path.GetFullPath(SnapshotRoot);Check(Directory.Exists(root)&&(File.GetAttributes(root)&FileAttributes.ReparsePoint)==0,"Private package snapshot root is not a regular directory.");
            var pending=new Stack<string>();pending.Push(root);var found=new HashSet<string>();
            while(pending.Count>0)
            {
                foreach(string path in Directory.GetFileSystemEntries(pending.Pop()))
                {
                    var attributes=File.GetAttributes(path);Check((attributes&FileAttributes.ReparsePoint)==0,"Private package snapshot forbids symlinks.");
                    string relative=path.Substring(root.Length+1).Replace('\\','/');
                    if((attributes&FileAttributes.Directory)!=0){Check(directories.Contains(relative),"Unexpected private package snapshot directory.");pending.Push(path);}
                    else {Check(files.Contains(relative),"Unexpected private package snapshot file.");found.Add(relative);}
                }
            }
            Check(found.SetEquals(files),"Private package snapshot file set is incomplete.");
        }
        static string Hash(byte[] bytes){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
    }
}
