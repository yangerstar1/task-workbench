using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using Lottery.G3.Editor;
using Lottery.G3.Rendering;

namespace Lottery.G3.EditMode.Tests
{
    public sealed class ArtworkImportTests
    {
        static readonly string[] Ids={"number","challenge"};
        static readonly string[] Shas={"aa9cd14c555cb2db4b402508ddee91e65a02b415e9226a0d99270b3d2e823e14","4d1bc2a0999439014db391bd1754ef053f8729f699dbc02af05100ddc83a5384"};
        static ApprovedArtworkBinding Binding(string id) => AssetDatabase.LoadAssetAtPath<ApprovedArtworkBinding>("Assets/G3/Rendering/Resources/G3/"+id+".asset");
        static string Hash(string path){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path)));}
        static G3ArtworkValidation.Observation Clone(G3ArtworkValidation.Observation o) => JsonUtility.FromJson<G3ArtworkValidation.Observation>(JsonUtility.ToJson(o));
        static bool Pass(G3ArtworkValidation.Observation o,string check) => G3ArtworkValidation.Evaluate(o).Single(x=>x.id==check).passed;
        [Test] public void BothOriginalImportsMatchFrozenPixelsBindingsAndExplicitPlatforms()
        {
            for(int i=0;i<Ids.Length;i++)
            {
                var o=G3ArtworkValidation.Inspect(Binding(Ids[i]),Ids[i]);
                TestContext.Out.WriteLine("G3_ACTUAL_EDITOR_IMPORT "+JsonUtility.ToJson(o));
                Assert.That(o.sourceSha256,Is.EqualTo(Shas[i]));Assert.That(o.sourceWidth,Is.EqualTo(1536));Assert.That(o.sourceHeight,Is.EqualTo(1024));
                Assert.That(o.textureWidth,Is.EqualTo(1536));Assert.That(o.textureHeight,Is.EqualTo(1024));
                Assert.That(o.androidPlatform.overridden,Is.True);Assert.That(o.androidPlatform.format,Is.EqualTo((int)TextureImporterFormat.RGB24));
                Assert.That(o.checks.Where(x=>!x.passed).Select(x=>x.id),Is.Empty);Assert.DoesNotThrow(()=>G3Build.ValidateArtwork(Binding(Ids[i]),Ids[i]));
            }
        }
        [Test] public void ImportInspectionAndBuildValidationNeverRewriteCommittedAssets()
        {
            foreach(string id in Ids)
            {
                string root="Assets/G3/Rendering/Resources/G3/"+id;
                var paths=new[]{root+".asset",root+".asset.meta",root+"-ticket-albedo.png",root+"-ticket-albedo.png.meta"};
                var before=paths.Select(Hash).ToArray();var binding=Binding(id);bool dirty=EditorUtility.IsDirty(binding);
                G3ArtworkValidation.Inspect(binding,id);G3Build.ValidateArtwork(binding,id);
                Assert.That(paths.Select(Hash).ToArray(),Is.EqualTo(before));Assert.That(EditorUtility.IsDirty(binding),Is.EqualTo(dirty));
            }
        }
        [Test] public void SwappingSameSizedOriginalArtworkFailsIdentityAndTextureBinding()
        {
            var o=G3ArtworkValidation.Inspect(Binding("number"),"challenge");
            Assert.That(o.sourceWidth,Is.EqualTo(1536));Assert.That(o.sourceHeight,Is.EqualTo(1024));
            Assert.That(Pass(o,"BINDING_ID"),Is.False);Assert.That(Pass(o,"TEXTURE_BINDING"),Is.False);
            Assert.That(Assert.Throws<InvalidOperationException>(()=>G3ArtworkValidation.Require(o)).Message,Does.Contain("BINDING_ID"));
        }
        [Test] public void SyntheticCompressionAndDimensionRegressionsHaveSpecificFailureIds()
        {
            var original=G3ArtworkValidation.Inspect(Binding("number"),"number");
            var o=Clone(original);o.textureCompression=1;Assert.That(Pass(o,"IMPORTER_DEFAULT"),Is.False);
            o=Clone(original);o.textureWidth=1024;Assert.That(Pass(o,"TEXTURE_DIMENSIONS"),Is.False);
            o=Clone(original);o.defaultPlatform.textureCompression=1;Assert.That(Pass(o,"DEFAULT_PLATFORM"),Is.False);
            o=Clone(original);o.layoutSha256=new string('0',64);Assert.That(Pass(o,"SOURCE_LAYOUT"),Is.False);
        }
        [Test] public void SyntheticAndroidFallbackCompressionAndDownsizeCannotPass()
        {
            var original=G3ArtworkValidation.Inspect(Binding("challenge"),"challenge");
            var o=Clone(original);o.androidPlatform.overridden=false;Assert.That(Pass(o,"ANDROID_PLATFORM"),Is.False);
            o=Clone(original);o.androidPlatform.maxTextureSize=1024;Assert.That(Pass(o,"ANDROID_PLATFORM"),Is.False);
            o=Clone(original);o.androidPlatform.format=(int)TextureImporterFormat.ETC2_RGB4;Assert.That(Pass(o,"ANDROID_PLATFORM"),Is.False);
            o=Clone(original);o.androidPlatform.textureCompression=1;Assert.That(Pass(o,"ANDROID_PLATFORM"),Is.False);
        }
        [Test] public void DiagnosticSerializationContainsOnlyBoundedIdentityAndImportObservations()
        {
            var report=G3ArtworkValidation.InspectBoth(new string('a',40),"123","1");string json=JsonUtility.ToJson(report);
            Assert.That(report.artworks.Select(x=>x.artworkId),Is.EqualTo(Ids));Assert.That(report.runAttempt,Is.EqualTo("1"));
            Assert.That(json.Length,Is.LessThan(16384));Assert.That(json,Does.Not.Contain(Application.dataPath));
            Assert.That(json,Does.Not.Contain("Assets/"));Assert.That(json,Does.Not.Contain("password"));
            Assert.Throws<InvalidOperationException>(()=>G3ArtworkValidation.InspectBoth("path-or-secret","123","1"));
        }
    }
}
