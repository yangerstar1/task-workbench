using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;
using Lottery.G3.Rendering;

namespace Lottery.G3.Editor
{
    // Read-only observation of the actual importer. Never changes/reimports source assets.
    public static class G3ArtworkValidation
    {
        public const string RawDiagnostic="g3-android-import-diagnostic.json";
        [Serializable] public sealed class Platform
        {
            public bool overridden,crunchedCompression,allowsAlphaSplitting;
            public int maxTextureSize=-1,format=-1,textureCompression=-1;
        }
        [Serializable] public sealed class Check { public string id;public bool passed; }
        [Serializable] public sealed class Observation
        {
            public string artworkId,sourceSha256="",layoutSha256="",assetGuid="";
            public bool sourcePng,bindingPresent,bindingIdMatches,texturePresent,bindingTextureMatches,bindingPathMatches,verificationMatches,importerPresent,sRGBTexture;
            public int sourceWidth=-1,sourceHeight=-1,layoutWidth=-1,layoutHeight=-1,textureWidth=-1,textureHeight=-1,textureFormat=-1;
            public int npotScale=-1,textureType=-1,wrapU=-1,wrapV=-1,wrapW=-1,maxTextureSize=-1,textureCompression=-1;
            public Platform defaultPlatform=new Platform(),androidPlatform=new Platform();
            public Check[] checks;
        }
        [Serializable] public sealed class Report
        {
            public int schemaVersion=1;
            public string sourceCommit,runId,runAttempt,unityVersion,stage="ANDROID_IMPORT_PREFLIGHT";
            public Observation[] artworks;
        }
        static string ExpectedSha(string id)
        {
            if(id=="number")return "aa9cd14c555cb2db4b402508ddee91e65a02b415e9226a0d99270b3d2e823e14";
            if(id=="challenge")return "4d1bc2a0999439014db391bd1754ef053f8729f699dbc02af05100ddc83a5384";
            throw new ArgumentException("G3_ARTWORK_ID_NOT_REVIEWED");
        }
        static Platform ObservePlatform(TextureImporterPlatformSettings p) => new Platform {
            overridden=p.overridden,maxTextureSize=p.maxTextureSize,format=(int)p.format,
            textureCompression=(int)p.textureCompression,crunchedCompression=p.crunchedCompression,allowsAlphaSplitting=p.allowsAlphaSplitting};
        static int BigEndian(byte[] b,int offset) => (b[offset]<<24)|(b[offset+1]<<16)|(b[offset+2]<<8)|b[offset+3];
        public static Observation Inspect(ApprovedArtworkBinding binding,string id)
        {
            string expected=ExpectedSha(id),path="Assets/G3/Rendering/Resources/G3/"+id+"-ticket-albedo.png";
            var o=new Observation{artworkId=id,bindingPresent=binding!=null};
            if(File.Exists(path))
            {
                using(var stream=File.OpenRead(path))
                {
                    if(stream.Length<=8*1024*1024)
                    {
                        using(var sha=SHA256.Create())o.sourceSha256=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
                        stream.Position=0;var header=new byte[24];int count=stream.Read(header,0,header.Length);
                        o.sourcePng=count==24 && header.Take(8).SequenceEqual(new byte[]{137,80,78,71,13,10,26,10});
                        if(o.sourcePng){o.sourceWidth=BigEndian(header,16);o.sourceHeight=BigEndian(header,20);}
                    }
                }
            }
            var tex=AssetDatabase.LoadAssetAtPath<Texture2D>(path);var importer=AssetImporter.GetAtPath(path) as TextureImporter;
            o.assetGuid=AssetDatabase.AssetPathToGUID(path);o.texturePresent=tex!=null;o.importerPresent=importer!=null;
            if(tex!=null){o.textureWidth=tex.width;o.textureHeight=tex.height;o.textureFormat=(int)tex.format;}
            if(binding!=null)
            {
                o.bindingIdMatches=binding.ArtworkId==id;o.bindingTextureMatches=binding.Albedo==tex && tex!=null;
                o.bindingPathMatches=AssetDatabase.GetAssetPath(binding.Albedo)==path;
                if(o.bindingIdMatches){var layout=binding.GetReviewedLayout();o.layoutWidth=layout.Width;o.layoutHeight=layout.Height;o.layoutSha256=layout.ArtworkSha256;}
                var s=new SerializedObject(binding);
                o.verificationMatches=s.FindProperty("verifiedTexture").objectReferenceValue==tex && tex!=null &&
                    s.FindProperty("verifiedArtworkId").stringValue==id && s.FindProperty("verifiedSourceSha256").stringValue==expected &&
                    s.FindProperty("verifiedAssetGuid").stringValue==o.assetGuid;
            }
            if(importer!=null)
            {
                o.npotScale=(int)importer.npotScale;o.textureType=(int)importer.textureType;o.sRGBTexture=importer.sRGBTexture;
                o.wrapU=(int)importer.wrapModeU;o.wrapV=(int)importer.wrapModeV;o.wrapW=(int)importer.wrapModeW;
                o.maxTextureSize=importer.maxTextureSize;o.textureCompression=(int)importer.textureCompression;
                o.defaultPlatform=ObservePlatform(importer.GetDefaultPlatformTextureSettings());
                o.androidPlatform=ObservePlatform(importer.GetPlatformTextureSettings("Android"));
            }
            o.checks=Evaluate(o);return o;
        }
        static Check C(string id,bool passed) => new Check{id=id,passed=passed};
        public static Check[] Evaluate(Observation o)
        {
            string expected=ExpectedSha(o.artworkId);
            return new[]{
                C("BINDING_ID",o.bindingPresent && o.bindingIdMatches),
                C("SOURCE_BYTES",o.sourcePng && o.sourceSha256==expected && o.sourceWidth==1536 && o.sourceHeight==1024),
                C("SOURCE_LAYOUT",o.layoutWidth==1536 && o.layoutHeight==1024 && o.layoutSha256==expected),
                C("TEXTURE_BINDING",o.texturePresent && o.bindingTextureMatches && o.bindingPathMatches),
                C("TEXTURE_DIMENSIONS",o.textureWidth==1536 && o.textureHeight==1024),
                C("TEXTURE_UNCOMPRESSED",o.textureFormat==(int)TextureFormat.RGB24 || o.textureFormat==(int)TextureFormat.RGBA32),
                C("IMPORTER_SHAPE",o.importerPresent && o.npotScale==(int)TextureImporterNPOTScale.None && o.textureType==(int)TextureImporterType.Default && o.sRGBTexture && o.wrapU==(int)TextureWrapMode.Clamp && o.wrapV==(int)TextureWrapMode.Clamp && o.wrapW==(int)TextureWrapMode.Clamp),
                C("IMPORTER_DEFAULT",o.maxTextureSize==2048 && o.textureCompression==(int)TextureImporterCompression.Uncompressed),
                C("DEFAULT_PLATFORM",!o.defaultPlatform.overridden && o.defaultPlatform.maxTextureSize==2048 && o.defaultPlatform.format==(int)TextureImporterFormat.Automatic && o.defaultPlatform.textureCompression==(int)TextureImporterCompression.Uncompressed && !o.defaultPlatform.crunchedCompression && !o.defaultPlatform.allowsAlphaSplitting),
                C("ANDROID_PLATFORM",o.androidPlatform.overridden && o.androidPlatform.maxTextureSize==2048 && o.androidPlatform.format==(int)TextureImporterFormat.RGB24 && o.androidPlatform.textureCompression==(int)TextureImporterCompression.Uncompressed && !o.androidPlatform.crunchedCompression && !o.androidPlatform.allowsAlphaSplitting),
                C("COMMITTED_VERIFICATION",o.verificationMatches && System.Text.RegularExpressions.Regex.IsMatch(o.assetGuid,"^[0-9a-f]{32}$"))};
        }
        public static void Require(Observation o)
        {
            var failed=Evaluate(o).Where(c=>!c.passed).Select(c=>c.id).ToArray();
            if(failed.Length!=0)throw new InvalidOperationException("G3_ARTWORK_CHECK "+o.artworkId+" "+string.Join(",",failed));
        }
        public static Report InspectBoth(string commit,string run,string attempt)
        {
            if(!System.Text.RegularExpressions.Regex.IsMatch(commit,"^[0-9a-f]{40}$") || !System.Text.RegularExpressions.Regex.IsMatch(run,"^[1-9][0-9]{0,19}$") || !System.Text.RegularExpressions.Regex.IsMatch(attempt,"^[1-9][0-9]{0,5}$"))throw new InvalidOperationException("Invalid artwork diagnostic identity");
            return new Report{sourceCommit=commit,runId=run,runAttempt=attempt,unityVersion=Application.unityVersion,artworks=new[]{
                Inspect(AssetDatabase.LoadAssetAtPath<ApprovedArtworkBinding>("Assets/G3/Rendering/Resources/G3/number.asset"),"number"),
                Inspect(AssetDatabase.LoadAssetAtPath<ApprovedArtworkBinding>("Assets/G3/Rendering/Resources/G3/challenge.asset"),"challenge")}};
        }
        public static void WriteAndroidDiagnostic(string commit,string run,string attempt)
        {
            var report=InspectBoth(commit,run,attempt);string json=JsonUtility.ToJson(report,true);
            if(json.Length>16384)throw new InvalidOperationException("Artwork diagnostic exceeds bound");
            string directory=Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts"));
            Directory.CreateDirectory(directory);File.WriteAllText(Path.Combine(directory,RawDiagnostic),json);
            foreach(var o in report.artworks)Require(o);
        }
    }
}
