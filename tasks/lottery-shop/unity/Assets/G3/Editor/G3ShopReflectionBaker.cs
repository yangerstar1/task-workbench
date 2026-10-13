using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using Lottery.G3.Interaction;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Object=UnityEngine.Object;

namespace Lottery.G3.Editor
{
    // Production asset preparation. The game, menu and tests use the same two
    // imported HDR probes; there is no per-fixture or global runtime cache.
    public static class G3ShopReflectionBaker
    {
        public const string Root=G3ShopArtImporter.Root+"/Reflections";
        public const string ReceiptPath=Root+"/reflection-receipt.json";
        const string DayGuid="b90a2a9e9f0d4c1bab2f613e26d9c771",NightGuid="a54ec87d23ac49ea83e7cf7bad94381a";
        const long CubeBytes=8388608,SmallBytes=16384;
        static readonly string[] RecipeSources={
            "Assets/G3/Interaction/G3ShopEnvironment.cs","Assets/G3/Editor/G3ShopReflectionBaker.cs",
            "Assets/G3/Editor/G3ShopArtImporter.cs","Assets/G3/Editor/G3Build.cs",
            "Packages/manifest.json","Packages/packages-lock.json"};
        static readonly string[] DependencyRoots={G3ShopArtImporter.Root+"/LotteryShop_Runtime.prefab",G3ShopArtImporter.PipelinePath};

        public static void Prepare()
        {
            if(Application.isPlaying)throw new InvalidOperationException("Static reflections must be prepared before entering Play Mode");
            string digest=SourceDigest();Directory.CreateDirectory(Root);
            var receipt=ReadReusable(digest);
            if(receipt==null)
            {
                // An interrupted bake cannot leave an older COMPLETE receipt valid.
                File.WriteAllText(ReceiptPath,"{\"schemaVersion\":1,\"status\":\"BAKE_IN_PROGRESS\"}");
                var prior=SceneManager.GetActiveScene();var priorLighting=new LightingSnapshot();var priorDefault=GraphicsSettings.defaultRenderPipeline;var priorQuality=QualitySettings.renderPipeline;
                var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);
                GameObject owner=null;
                Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(() =>
                {
                    Lottery.Probe.Editor.ProbeBuild.RequirePreparedSceneActive(scene,20,null);
                    // Reserved bake layer prevents runner, HUD, phone or live ticket
                    // geometry entering the cube. Reject contaminating scene light.
                    if(Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None).Any(r=>r.enabled&&r.gameObject.activeInHierarchy&&r.gameObject.layer==31) ||
                       Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Any(l=>l.enabled&&l.gameObject.activeInHierarchy&&(l.cullingMask&(1<<31))!=0)||
                       Object.FindObjectsByType<ReflectionProbe>(FindObjectsSortMode.None).Any(p=>p.enabled&&p.gameObject.activeInHierarchy))
                        throw new InvalidOperationException("Reflection bake requires an isolated source lighting scene");
                    owner=new GameObject("Owned static shop reflection bake");
                    var environment=owner.AddComponent<G3ShopEnvironment>();var probe=environment.BuildForReflectionBake();
                    var captureRenderers=owner.GetComponentsInChildren<MeshRenderer>();long captureTriangles=0;
                    foreach(var renderer in captureRenderers)
                    {
                        if(renderer.gameObject.layer!=31)throw new InvalidOperationException("Unexpected object in static reflection capture");
                        var flags=GameObjectUtility.GetStaticEditorFlags(renderer.gameObject)|StaticEditorFlags.ReflectionProbeStatic;
                        GameObjectUtility.SetStaticEditorFlags(renderer.gameObject,flags);
                        if((GameObjectUtility.GetStaticEditorFlags(renderer.gameObject)&StaticEditorFlags.ReflectionProbeStatic)==0)throw new InvalidOperationException("Reflection capture geometry is not bake-static");
                        var mesh=renderer.GetComponent<MeshFilter>()?.sharedMesh;if(mesh==null)throw new InvalidOperationException("Static reflection capture lost a mesh");
                        for(int sub=0;sub<mesh.subMeshCount;sub++)captureTriangles+=(long)mesh.GetIndexCount(sub)/3;
                    }
                    if(captureRenderers.Length<1||captureRenderers.Length>4096||captureTriangles<1||captureTriangles>2000000)throw new InvalidOperationException("Static reflection geometry count exceeds fixed bounds");
                    if(probe.cullingMask!=(1<<31)||probe.resolution!=G3ShopEnvironment.ReflectionFaceSize||probe.mode!=ReflectionProbeMode.Baked)
                        throw new InvalidOperationException("Unexpected static reflection capture contract");
                    receipt=new G3ShopEnvironment.ReflectionReceipt{schemaVersion=1,status="COMPLETE_BAKED_STATIC_REFLECTIONS",recipe=G3ShopEnvironment.ReflectionRecipe,sourceDigest=digest,unityVersion=Application.unityVersion,captureRenderers=captureRenderers.Length,captureTriangles=(int)captureTriangles};
                    environment.SetNight(false);receipt.day=BakeOne(probe,"Day.exr",DayGuid);
                    environment.SetNight(true);receipt.night=BakeOne(probe,"Night.exr",NightGuid);
                },()=>CleanupBake(owner,prior,scene,priorDefault,priorQuality,priorLighting));
                if(SourceDigest()!=digest)throw new InvalidOperationException("Reflection inputs changed during their bake");
            }
            // Rebinding a validated same-source asset to this build does not rebake
            // it. A stale recipe or either changed file forces the real bake above.
            receipt.colorSpace=PlayerSettings.colorSpace.ToString();receipt.runtimeDependencyHash=AssetDatabase.GetAssetDependencyHash(DependencyRoots[0]).ToString();receipt.pipelineDependencyHash=AssetDatabase.GetAssetDependencyHash(DependencyRoots[1]).ToString();
            receipt.sourceCommit=Arg("-probeCommit");receipt.runId=Arg("-probeRunId");receipt.runAttempt=Arg("-probeRunAttempt");
            string json=JsonUtility.ToJson(receipt,true);if(Encoding.UTF8.GetByteCount(json)>SmallBytes)throw new InvalidOperationException("Reflection receipt exceeds fixed bound");
            File.WriteAllText(ReceiptPath,json,new UTF8Encoding(false));AssetDatabase.ImportAsset(ReceiptPath,ImportAssetOptions.ForceUpdate);
            AssetDatabase.SaveAssets();
        }
        static void CleanupBake(GameObject owner,Scene prior,Scene owned,RenderPipelineAsset priorDefault,RenderPipelineAsset priorQuality,LightingSnapshot lighting)
        {
            // Every cleanup stage runs even if a prior stage failed; preserve all
            // causes through the already-reviewed aggregation helper.
            Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                ()=>Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                    ()=>{if(owner!=null)Object.DestroyImmediate(owner);},
                    ()=>Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                        ()=>Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                            ()=>GraphicsSettings.defaultRenderPipeline=priorDefault,
                            ()=>QualitySettings.renderPipeline=priorQuality),
                        ()=>Lottery.Probe.Editor.ProbeBuild.RestorePreparedScene(prior,owned,22,null))),
                ()=>{
                    if(GraphicsSettings.defaultRenderPipeline!=priorDefault||QualitySettings.renderPipeline!=priorQuality||SceneManager.GetActiveScene().handle!=prior.handle)
                        throw new InvalidOperationException("Static reflection preparation failed to restore its scene or pipeline");
                    lighting.RequireUnchanged();
                });
        }
        static G3ShopEnvironment.ReflectionTexture BakeOne(ReflectionProbe probe,string file,string guid)
        {
            string path=Root+"/"+file;SeedMeta(path,guid);
            // Do not let the previous day/night output participate in this capture.
            probe.bakedTexture=null;probe.customBakedTexture=null;
            if(File.Exists(path))File.Delete(path); // Regenerate only this owned output; retain its GUID.
            if(!Lightmapping.BakeReflectionProbe(probe,path))throw new InvalidOperationException("Unity failed to bake "+file);
            RequireSize(path,CubeBytes);
            AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
            var importer=AssetImporter.GetAtPath(path) as TextureImporter;if(importer==null)throw new InvalidOperationException("Reflection texture importer missing");
            importer.textureType=TextureImporterType.Default;importer.textureShape=TextureImporterShape.TextureCube;
            importer.sRGBTexture=false;importer.mipmapEnabled=true;importer.isReadable=true;importer.wrapMode=TextureWrapMode.Clamp;importer.filterMode=FilterMode.Trilinear;
            importer.textureCompression=TextureImporterCompression.Uncompressed;importer.maxTextureSize=G3ShopEnvironment.ReflectionFaceSize;
            importer.userData="";importer.assetBundleName="";importer.assetBundleVariant="";
            if(importer.GetExternalObjectMap().Count!=0)throw new InvalidOperationException("Reflection importer must not contain external object remaps");
            var settings=new TextureImporterSettings();importer.ReadTextureSettings(settings);settings.generateCubemap=TextureImporterGenerateCubemap.AutoCubemap;settings.cubemapConvolution=TextureImporterCubemapConvolution.Specular;importer.SetTextureSettings(settings);
            var platform=importer.GetDefaultPlatformTextureSettings();platform.maxTextureSize=G3ShopEnvironment.ReflectionFaceSize;platform.format=TextureImporterFormat.RGBAHalf;platform.textureCompression=TextureImporterCompression.Uncompressed;importer.SetPlatformTextureSettings(platform);
            importer.SaveAndReimport();
            var readable=AssetDatabase.LoadAssetAtPath<Cubemap>(path);
            float contentRange=RequireNonUniformContent(readable);
            importer.isReadable=false;importer.SaveAndReimport();
            if(AssetDatabase.AssetPathToGUID(path)!=guid)throw new InvalidOperationException("Reflection output GUID changed");
            importer.GetSourceTextureWidthAndHeight(out int width,out int height);
            if(width<128||height<128||width>2048||height>2048)throw new InvalidOperationException("Unexpected reflection EXR source dimensions");
            RequireSize(path+".meta",SmallBytes);
            var info=new G3ShopEnvironment.ReflectionTexture{file=file,sha256=HashFile(path),bytes=new FileInfo(path).Length,metaSha256=HashFile(path+".meta"),metaBytes=new FileInfo(path+".meta").Length,metaGuid=guid,
                sourceWidth=width,sourceHeight=height,faceSize=G3ShopEnvironment.ReflectionFaceSize,mipCount=G3ShopEnvironment.ReflectionMipCount,format="RGBAHalf",shape="Cube",linear=true,specular=true,pixelSampleCount=98304,maxChannelRange=contentRange};
            G3ShopEnvironment.RequireReflection(AssetDatabase.LoadAssetAtPath<Cubemap>(path),info,file);return info;
        }
        static float RequireNonUniformContent(Cubemap cube)
        {
            if(cube==null||cube.width!=128||cube.height!=128||cube.mipmapCount!=8||cube.format!=TextureFormat.RGBAHalf)throw new InvalidOperationException("Unexpected readable HDR reflection layout");
            Vector3 min=new Vector3(float.MaxValue,float.MaxValue,float.MaxValue),max=new Vector3(float.MinValue,float.MinValue,float.MinValue);int count=0;
            for(int face=0;face<6;face++)foreach(var c in cube.GetPixels((CubemapFace)face,0))
            {
                if(float.IsNaN(c.r)||float.IsNaN(c.g)||float.IsNaN(c.b)||float.IsInfinity(c.r)||float.IsInfinity(c.g)||float.IsInfinity(c.b))throw new InvalidOperationException("Non-finite HDR reflection sample");
                var value=new Vector3(c.r,c.g,c.b);min=Vector3.Min(min,value);max=Vector3.Max(max,value);count++;
            }
            var range=max-min;float spread=Mathf.Max(range.x,Mathf.Max(range.y,range.z));
            if(count!=98304||spread<=.01f||spread>65504)throw new InvalidOperationException("Reflection bake contains only a flat background or invalid HDR range");
            return spread;
        }
        static G3ShopEnvironment.ReflectionReceipt ReadReusable(string digest)
        {
            try
            {
                RequireSize(ReceiptPath,SmallBytes);var r=JsonUtility.FromJson<G3ShopEnvironment.ReflectionReceipt>(File.ReadAllText(ReceiptPath));
                if(r==null||r.captureRenderers<1||r.captureRenderers>4096||r.captureTriangles<1||r.captureTriangles>2000000||r.schemaVersion!=1||r.status!="COMPLETE_BAKED_STATIC_REFLECTIONS"||r.recipe!=G3ShopEnvironment.ReflectionRecipe||r.sourceDigest!=digest||r.unityVersion!=Application.unityVersion||r.colorSpace!=PlayerSettings.colorSpace.ToString()||r.runtimeDependencyHash!=AssetDatabase.GetAssetDependencyHash(DependencyRoots[0]).ToString()||r.pipelineDependencyHash!=AssetDatabase.GetAssetDependencyHash(DependencyRoots[1]).ToString())return null;
                ValidateExisting(r.day,"Day.exr",DayGuid);ValidateExisting(r.night,"Night.exr",NightGuid);return r;
            }
            catch(Exception){return null;} // Invalid cache triggers a synchronous source bake, never a runtime fallback.
        }
        static void ValidateExisting(G3ShopEnvironment.ReflectionTexture info,string file,string guid)
        {
            string path=Root+"/"+file;RequireSize(path,CubeBytes);RequireSize(path+".meta",SmallBytes);
            G3ShopEnvironment.RequireReflection(AssetDatabase.LoadAssetAtPath<Cubemap>(path),info,file);
            if(info.sha256!=HashFile(path)||info.metaSha256!=HashFile(path+".meta")||info.bytes!=new FileInfo(path).Length||info.metaBytes!=new FileInfo(path+".meta").Length||info.metaGuid!=guid||AssetDatabase.AssetPathToGUID(path)!=guid)
                throw new InvalidOperationException("Static reflection source artifact mismatch");
        }
        static void SeedMeta(string path,string guid)
        {
            if(File.Exists(path+".meta"))
            {
                if(!File.ReadAllText(path+".meta").Split('\n').Any(x=>x.Trim()=="guid: "+guid))throw new InvalidOperationException("Refusing to replace an unrelated reflection asset GUID");
                return;
            }
            File.WriteAllText(path+".meta","fileFormatVersion: 2\nguid: "+guid+"\nTextureImporter:\n  serializedVersion: 13\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n",new UTF8Encoding(false));
        }
        public static string SourceDigest()
        {
            // Every static source byte and import setting under Shop is covered,
            // excluding ONLY our outputs. Generated meshes/materials are included.
            // Dependency hashes also cover the referenced Lit/renderer/pipeline.
            var files=Directory.GetFiles(G3ShopArtImporter.Root,"*",SearchOption.AllDirectories)
                .Select(p=>p.Replace('\\','/')).Where(p=>!p.StartsWith(Root+"/",StringComparison.Ordinal)&&p!=Root+".meta").Concat(RecipeSources).Distinct().OrderBy(p=>p,StringComparer.Ordinal).ToArray();
            var text=new StringBuilder(G3ShopEnvironment.ReflectionRecipe+"\n"+Application.unityVersion+"\n"+PlayerSettings.colorSpace+"\n");
            foreach(string path in files){if(!File.Exists(path))throw new InvalidOperationException("Missing reflection source input "+path);text.Append(path).Append('|').Append(HashFile(path)).Append('\n');}
            foreach(string path in DependencyRoots){if(AssetDatabase.LoadMainAssetAtPath(path)==null)throw new InvalidOperationException("Missing reflection dependency "+path);text.Append(path).Append('|').Append(AssetDatabase.GetAssetDependencyHash(path)).Append('\n');}
            using(var sha=SHA256.Create())return Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(text.ToString())));
        }
        sealed class LightingSnapshot
        {
            readonly AmbientMode mode=RenderSettings.ambientMode;readonly Color sky=RenderSettings.ambientSkyColor,equator=RenderSettings.ambientEquatorColor,ground=RenderSettings.ambientGroundColor,ambient=RenderSettings.ambientLight;
            readonly SphericalHarmonicsL2 sh=RenderSettings.ambientProbe;readonly Light sun=RenderSettings.sun;readonly float intensity=RenderSettings.reflectionIntensity;
            public void RequireUnchanged()
            {
                if(RenderSettings.ambientMode!=mode||RenderSettings.ambientSkyColor!=sky||RenderSettings.ambientEquatorColor!=equator||RenderSettings.ambientGroundColor!=ground||RenderSettings.ambientLight!=ambient||!RenderSettings.ambientProbe.Equals(sh)||RenderSettings.sun!=sun||RenderSettings.reflectionIntensity!=intensity)
                    throw new InvalidOperationException("Reflection bake altered the prior scene lighting");
            }
        }
        static void RequireSize(string path,long maximum){if(!File.Exists(path)||new FileInfo(path).Length<=0||new FileInfo(path).Length>maximum)throw new InvalidOperationException("Missing or oversized fixed reflection artifact");}
        static string HashFile(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return Hex(sha.ComputeHash(f));}
        static string Hex(byte[] bytes)=>BitConverter.ToString(bytes).Replace("-","").ToLowerInvariant();
        static string Arg(string name)
        {
            var args=System.Environment.GetCommandLineArgs();for(int i=0;i<args.Length-1;i++)if(args[i]==name)
            {string value=args[i+1],pattern=name=="-probeCommit"?"^[0-9a-f]{40}$":"^[1-9][0-9]{0,19}$";if(!System.Text.RegularExpressions.Regex.IsMatch(value,pattern))throw new InvalidOperationException("Invalid reflection build identity");return value;}
            return "LOCAL_UNBOUND";
        }
    }
}
