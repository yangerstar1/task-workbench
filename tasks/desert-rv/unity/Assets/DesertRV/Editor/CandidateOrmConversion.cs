using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;
namespace DesertRV.Editor
{
    public static class CandidateOrmConversion
    {
        [Serializable] public sealed class Record
        {
            public string source,sourceSha256,derived,derivedSha256,decodedPixelSha256;
            public string mapping="R=source.B; G=source.R; B=0; A=255-source.G";
            public int width,height;public bool sRGB=false,sourceModified=false;
        }
        public static Color32 ConvertPixel(Color32 pixel)=>new Color32(pixel.b,pixel.r,0,(byte)(255-pixel.g));
        public static Texture2D Convert(string source,string output,out Record record)
        {
            if(File.Exists(output)||File.Exists(output+".meta"))throw new InvalidOperationException("Derived texture already exists.");
            string sourceHash=JourneyCandidateArtImport.Sha(source);
            Texture2D raw=null,packed=null;
            try
            {
                raw=new Texture2D(2,2,TextureFormat.RGBA32,false,true);
                if(!ImageConversion.LoadImage(raw,File.ReadAllBytes(source),false))throw new InvalidOperationException("ORM decode failed.");
                var expected=raw.GetPixels32().Select(ConvertPixel).ToArray();
                packed=new Texture2D(raw.width,raw.height,TextureFormat.RGBA32,false,true);packed.SetPixels32(expected);packed.Apply(false,false);
                Directory.CreateDirectory(Path.GetDirectoryName(output));File.WriteAllBytes(output,ImageConversion.EncodeToPNG(packed));
                AssetDatabase.ImportAsset(output,ImportAssetOptions.ForceSynchronousImport);
                var importer=AssetImporter.GetAtPath(output) as TextureImporter;
                if(!importer)throw new InvalidOperationException("Derived texture importer missing.");
                importer.textureType=TextureImporterType.Default;importer.sRGBTexture=false;importer.isReadable=true;importer.alphaSource=TextureImporterAlphaSource.FromInput;
                importer.textureCompression=TextureImporterCompression.Uncompressed;importer.npotScale=TextureImporterNPOTScale.None;importer.maxTextureSize=Mathf.NextPowerOfTwo(Mathf.Max(raw.width,raw.height));importer.mipmapEnabled=true;importer.SaveAndReimport();
                var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(output);var actual=texture.GetPixels32();
                if(texture.width!=raw.width||texture.height!=raw.height||!actual.SequenceEqual(expected))throw new InvalidOperationException("Derived linear RGBA pixel readback mismatch.");
                if(JourneyCandidateArtImport.Sha(source)!=sourceHash)throw new InvalidOperationException("Source ORM was modified.");
                byte[] bytes=actual.SelectMany(p=>new[]{p.r,p.g,p.b,p.a}).ToArray();string pixelHash;
                using(var sha=SHA256.Create())pixelHash=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
                record=new Record{source=source,sourceSha256=sourceHash,derived=output,derivedSha256=JourneyCandidateArtImport.Sha(output),decodedPixelSha256=pixelHash,width=texture.width,height=texture.height};
                return texture;
            }
            finally {try {if(raw)UnityEngine.Object.DestroyImmediate(raw);}finally {if(packed)UnityEngine.Object.DestroyImmediate(packed);}}
        }
    }
}
