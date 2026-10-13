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
            var trace=BakeTrace.CreateForCapture();
            Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                ()=>{try{PrepareObserved(trace);if(trace!=null)trace.succeeded=true;}catch(Exception error){trace?.Failure(error);throw;}},
                ()=>trace?.Finish());
        }
        static void PrepareObserved(BakeTrace trace)
        {
            trace?.Mark(10);
            if(Application.isPlaying)throw new BakeFailure(FailureCode.IN_PLAY_MODE);
            trace?.Mark(20);string digest=ComputeDigest(out var beforeInputs);trace?.Mark(21);Directory.CreateDirectory(Root);
            var receipt=ReadReusable(digest);if(trace!=null)trace.cacheHit=receipt!=null;trace?.Mark(30);
            if(receipt==null)
            {
                // An interrupted bake cannot leave an older COMPLETE receipt valid.
                trace?.Mark(40);File.WriteAllText(ReceiptPath,"{\"schemaVersion\":1,\"status\":\"BAKE_IN_PROGRESS\"}");
                var prior=SceneManager.GetActiveScene();var priorLighting=new LightingSnapshot();var priorDefault=GraphicsSettings.defaultRenderPipeline;var priorQuality=QualitySettings.renderPipeline;
                trace?.Mark(50);var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);trace?.ObserveScene(scene);trace?.Mark(51);
                GameObject owner=null;
                Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(()=>Observed(trace,() =>
                {
                    trace?.ClearSceneObservation();trace?.Mark(60);Lottery.Probe.Editor.ProbeBuild.RequirePreparedSceneActive(scene,20,null);trace?.ObserveScene(scene);
                    // Dedicated user layer prevents runner, HUD, phone or live ticket
                    // geometry entering the cube. Reject contaminating scene light.
                    int foreignRenderers=Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None).Count(r=>r.enabled&&r.gameObject.activeInHierarchy&&r.gameObject.layer==G3ShopEnvironment.ReflectionBakeLayer);
                    int foreignLights=Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Count(l=>l.enabled&&l.gameObject.activeInHierarchy&&(l.cullingMask&(1<<G3ShopEnvironment.ReflectionBakeLayer))!=0);
                    int foreignProbes=Object.FindObjectsByType<ReflectionProbe>(FindObjectsSortMode.None).Count(p=>p.enabled&&p.gameObject.activeInHierarchy);
                    if(trace!=null){trace.foreignRenderers=foreignRenderers;trace.foreignLights=foreignLights;trace.foreignProbes=foreignProbes;}trace?.Mark(61);
                    if(foreignRenderers!=0||foreignLights!=0||foreignProbes!=0)
                        throw new BakeFailure(FailureCode.ISOLATION_CONFLICT);
                    trace?.Mark(70);owner=new GameObject("Owned static shop reflection bake");
                    var environment=owner.AddComponent<G3ShopEnvironment>();var probe=environment.BuildForReflectionBake();trace?.Mark(71);
                    trace?.Mark(80);var captureRenderers=owner.GetComponentsInChildren<MeshRenderer>();long captureTriangles=0;
                    foreach(var renderer in captureRenderers)
                    {
                        if(renderer.gameObject.layer!=G3ShopEnvironment.ReflectionBakeLayer)throw new BakeFailure(FailureCode.STATIC_LAYER_MISMATCH);
                        var flags=GameObjectUtility.GetStaticEditorFlags(renderer.gameObject)|StaticEditorFlags.ReflectionProbeStatic;
                        GameObjectUtility.SetStaticEditorFlags(renderer.gameObject,flags);
                        if((GameObjectUtility.GetStaticEditorFlags(renderer.gameObject)&StaticEditorFlags.ReflectionProbeStatic)==0)throw new BakeFailure(FailureCode.STATIC_FLAG_MISSING);
                        var mesh=renderer.GetComponent<MeshFilter>()?.sharedMesh;if(mesh==null)throw new BakeFailure(FailureCode.STATIC_MESH_MISSING);
                        for(int sub=0;sub<mesh.subMeshCount;sub++)captureTriangles+=(long)mesh.GetIndexCount(sub)/3;
                    }
                    if(trace!=null){trace.captureRenderers=captureRenderers.Length;trace.captureTriangles=captureTriangles;}trace?.Mark(81);
                    if(captureRenderers.Length<1||captureRenderers.Length>4096||captureTriangles<1||captureTriangles>2000000)throw new BakeFailure(FailureCode.GEOMETRY_BOUNDS);
                    if(probe.cullingMask!=(1<<G3ShopEnvironment.ReflectionBakeLayer)||probe.resolution!=G3ShopEnvironment.ReflectionFaceSize||probe.mode!=ReflectionProbeMode.Baked)
                        throw new BakeFailure(FailureCode.PROBE_CONFIG);
                    receipt=new G3ShopEnvironment.ReflectionReceipt{schemaVersion=1,status="COMPLETE_BAKED_STATIC_REFLECTIONS",recipe=G3ShopEnvironment.ReflectionRecipe,sourceDigest=digest,unityVersion=Application.unityVersion,captureRenderers=captureRenderers.Length,captureTriangles=(int)captureTriangles};
                    trace?.Mark(90);environment.SetNight(false);receipt.day=BakeOne(probe,"Day.exr",DayGuid,0,trace);
                    trace?.Mark(190);environment.SetNight(true);receipt.night=BakeOne(probe,"Night.exr",NightGuid,1,trace);
                }),()=>CleanupBake(owner,prior,scene,priorDefault,priorQuality,priorLighting,trace));
                trace?.Mark(310);bool same=ComputeDigest(out var afterInputs)==digest;if(trace!=null){trace.digestCompared=true;trace.digestSame=same;trace.ObserveInputChanges(beforeInputs,afterInputs);}trace?.Mark(311);
                if(!same)throw new BakeFailure(FailureCode.SOURCE_DIGEST_CHANGED);
            }
            // Rebinding a validated same-source asset to this build does not rebake
            // it. A stale recipe or either changed file forces the real bake above.
            trace?.Mark(320);receipt.colorSpace=PlayerSettings.colorSpace.ToString();receipt.runtimeDependencyHash=beforeInputs["DEPENDENCY|"+DependencyRoots[0]];receipt.pipelineDependencyHash=beforeInputs["DEPENDENCY|"+DependencyRoots[1]];
            receipt.sourceCommit=Arg("-probeCommit");receipt.runId=Arg("-probeRunId");receipt.runAttempt=Arg("-probeRunAttempt");
            string json=JsonUtility.ToJson(receipt,true);if(Encoding.UTF8.GetByteCount(json)>SmallBytes)throw new BakeFailure(FailureCode.RECEIPT_SIZE);
            // Receipt fields and digest must describe the same input snapshot.
            // Final import/save may flush dirty covered assets: verify, never restamp
            // an earlier bake with a later digest or silently remove inputs.
            bool finalValidated=false;
            Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                ()=>Observed(trace,()=>{
                    trace?.Mark(321);File.WriteAllText(ReceiptPath,json,new UTF8Encoding(false));AssetDatabase.ImportAsset(ReceiptPath,ImportAssetOptions.ForceUpdate);
                    trace?.Mark(322);AssetDatabase.SaveAssets();trace?.Mark(323);
                    if(trace!=null){trace.digestCompared=false;trace.digestSame=false;trace.changedInputCount=-1;trace.changedInputKinds=0;trace.matBits=trace.metaBits=trace.packBits=trace.packMetaBits=0;trace.changedOther=0;}
                    trace?.Mark(324);bool finalSame=ComputeDigest(out var finalInputs)==digest;
                    if(trace!=null){trace.digestCompared=true;trace.digestSame=finalSame;trace.ObserveInputChanges(beforeInputs,finalInputs);}trace?.Mark(325);
                    if(!finalSame)throw new BakeFailure(FailureCode.SOURCE_DIGEST_CHANGED);
                    finalValidated=true;
                }),
                ()=>{if(!finalValidated){File.WriteAllText(ReceiptPath,"{\"schemaVersion\":1,\"status\":\"BAKE_INPUT_CHANGED\"}",new UTF8Encoding(false));AssetDatabase.ImportAsset(ReceiptPath,ImportAssetOptions.ForceUpdate);}});
        }
        static void CleanupBake(GameObject owner,Scene prior,Scene owned,RenderPipelineAsset priorDefault,RenderPipelineAsset priorQuality,LightingSnapshot lighting,BakeTrace trace)
        {
            if(trace!=null)trace.bakeIndex=-1;trace?.Mark(300);
            // Every cleanup stage runs even if a prior stage failed; preserve all
            // causes through the already-reviewed aggregation helper.
            Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                ()=>Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                    ()=>Observed(trace,()=>{trace?.Mark(301);if(owner!=null)Object.DestroyImmediate(owner);}),
                    ()=>Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                        ()=>Lottery.Probe.Editor.ProbeBuild.RunPreparationWithCleanup(
                            ()=>Observed(trace,()=>{trace?.Mark(302);GraphicsSettings.defaultRenderPipeline=priorDefault;}),
                            ()=>Observed(trace,()=>{trace?.Mark(303);QualitySettings.renderPipeline=priorQuality;})),
                        ()=>Observed(trace,()=>{trace?.ClearSceneObservation();trace?.Mark(304);Lottery.Probe.Editor.ProbeBuild.RestorePreparedScene(prior,owned,22,null);trace?.ObserveScene(prior);}))),
                ()=>Observed(trace,()=>{
                    trace?.Mark(305);
                    if(GraphicsSettings.defaultRenderPipeline!=priorDefault||QualitySettings.renderPipeline!=priorQuality||SceneManager.GetActiveScene().handle!=prior.handle)
                        throw new BakeFailure(FailureCode.CLEANUP_PIPELINE_OR_SCENE);
                    lighting.RequireUnchanged();trace?.Mark(306);
                }));
        }
        static G3ShopEnvironment.ReflectionTexture BakeOne(ReflectionProbe probe,string file,string guid,int bakeIndex,BakeTrace trace)
        {
            int stage=100+100*bakeIndex;trace?.ResetCube(bakeIndex);trace?.Mark(stage);
            string path=Root+"/"+file;SeedMeta(path,guid);
            // Do not let the previous day/night output participate in this capture.
            probe.bakedTexture=null;probe.customBakedTexture=null;
            if(File.Exists(path))File.Delete(path); // Regenerate only this owned output; retain its GUID.
            if(trace!=null)trace.bakeAttempted=true;trace?.Mark(stage+1);
            bool bakeReturned=Lightmapping.BakeReflectionProbe(probe,path);if(trace!=null)trace.bakeReturned=bakeReturned;trace?.ObserveFile(path);trace?.Mark(stage+2);
            if(!bakeReturned)throw new BakeFailure(FailureCode.BAKE_RETURNED_FALSE);
            RequireSize(path,CubeBytes);
            trace?.Mark(stage+3);AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
            var importer=AssetImporter.GetAtPath(path) as TextureImporter;if(importer==null)throw new BakeFailure(FailureCode.IMPORTER_MISSING);
            importer.GetSourceTextureWidthAndHeight(out int width,out int height);if(trace!=null){trace.sourceWidth=width;trace.sourceHeight=height;}trace?.Mark(stage+4);
            importer.textureType=TextureImporterType.Default;importer.textureShape=TextureImporterShape.TextureCube;
            importer.sRGBTexture=false;importer.mipmapEnabled=true;importer.isReadable=true;importer.wrapMode=TextureWrapMode.Clamp;importer.filterMode=FilterMode.Trilinear;
            importer.textureCompression=TextureImporterCompression.Uncompressed;importer.maxTextureSize=G3ShopEnvironment.ReflectionFaceSize;
            importer.userData="";
            // An already unbundled owned cube needs no setter. When clearing a
            // prior assignment, use the paired API instead of setting a variant
            // after first clearing its name; still fail if either value remains.
            if(!string.IsNullOrEmpty(importer.assetBundleName)||!string.IsNullOrEmpty(importer.assetBundleVariant))
                importer.SetAssetBundleNameAndVariant("","");
            if(!string.IsNullOrEmpty(importer.assetBundleName)||!string.IsNullOrEmpty(importer.assetBundleVariant))
                throw new BakeFailure(FailureCode.FINAL_TEXTURE_CONTRACT);
            if(importer.GetExternalObjectMap().Count!=0)throw new BakeFailure(FailureCode.IMPORTER_EXTERNAL_REMAP);
            var settings=new TextureImporterSettings();importer.ReadTextureSettings(settings);settings.generateCubemap=TextureImporterGenerateCubemap.AutoCubemap;settings.cubemapConvolution=TextureImporterCubemapConvolution.Specular;importer.SetTextureSettings(settings);
            var platform=importer.GetDefaultPlatformTextureSettings();platform.maxTextureSize=G3ShopEnvironment.ReflectionFaceSize;platform.format=TextureImporterFormat.RGBAHalf;platform.textureCompression=TextureImporterCompression.Uncompressed;importer.SetPlatformTextureSettings(platform);
            trace?.Mark(stage+5);importer.SaveAndReimport();
            var readable=AssetDatabase.LoadAssetAtPath<Cubemap>(path);trace?.ObserveCube(readable);trace?.Mark(stage+6);
            trace?.Mark(stage+7);float contentRange=RequireNonUniformContent(readable,trace);trace?.Mark(stage+8);
            trace?.Mark(stage+9);importer.isReadable=false;importer.SaveAndReimport();
            var finalImporter=AssetImporter.GetAtPath(path) as TextureImporter;
            if(finalImporter==null||!string.IsNullOrEmpty(finalImporter.assetBundleName)||!string.IsNullOrEmpty(finalImporter.assetBundleVariant))
                throw new BakeFailure(FailureCode.FINAL_TEXTURE_CONTRACT);
            trace?.ObserveCube(AssetDatabase.LoadAssetAtPath<Cubemap>(path));trace?.Mark(stage+10);
            trace?.Mark(stage+11);
            string actualGuid=AssetDatabase.AssetPathToGUID(path);trace?.ObserveMeta(path+".meta");if(trace!=null){trace.guidObserved=true;trace.guidPresent=!string.IsNullOrEmpty(actualGuid);trace.guidMatches=actualGuid==guid;}
            if(actualGuid!=guid)throw new BakeFailure(FailureCode.GUID_MISMATCH);
            if(width<128||height<128||width>2048||height>2048)throw new BakeFailure(FailureCode.EXR_DIMENSIONS);
            RequireSize(path+".meta",SmallBytes);
            var info=new G3ShopEnvironment.ReflectionTexture{file=file,sha256=HashFile(path),bytes=new FileInfo(path).Length,metaSha256=HashFile(path+".meta"),metaBytes=new FileInfo(path+".meta").Length,metaGuid=guid,
                sourceWidth=width,sourceHeight=height,faceSize=G3ShopEnvironment.ReflectionFaceSize,mipCount=G3ShopEnvironment.ReflectionMipCount,format="RGBAHalf",shape="Cube",linear=true,specular=true,pixelSampleCount=98304,maxChannelRange=contentRange};
            try{G3ShopEnvironment.RequireReflection(AssetDatabase.LoadAssetAtPath<Cubemap>(path),info,file);}catch(Exception error){throw new BakeFailure(FailureCode.FINAL_TEXTURE_CONTRACT,error);}
            trace?.Mark(stage+12);return info;
        }
        static float RequireNonUniformContent(Cubemap cube,BakeTrace trace)
        {
            if(cube==null||cube.width!=128||cube.height!=128||cube.mipmapCount!=8||cube.format!=TextureFormat.RGBAHalf)throw new BakeFailure(FailureCode.CUBEMAP_LAYOUT);
            Vector3 min=new Vector3(float.MaxValue,float.MaxValue,float.MaxValue),max=new Vector3(float.MinValue,float.MinValue,float.MinValue);int count=0;
            for(int face=0;face<6;face++)foreach(var c in cube.GetPixels((CubemapFace)face,0))
            {
                if(trace!=null)trace.pixelSampleCount=count+1;
                if(float.IsNaN(c.r)||float.IsNaN(c.g)||float.IsNaN(c.b)||float.IsInfinity(c.r)||float.IsInfinity(c.g)||float.IsInfinity(c.b))throw new BakeFailure(FailureCode.HDR_NONFINITE);
                var value=new Vector3(c.r,c.g,c.b);min=Vector3.Min(min,value);max=Vector3.Max(max,value);count++;
            }
            var range=max-min;float spread=Mathf.Max(range.x,Mathf.Max(range.y,range.z));
            if(trace!=null){trace.rangeObserved=true;trace.rangeFinite=!float.IsNaN(spread)&&!float.IsInfinity(spread);trace.maxChannelRange=trace.rangeFinite?spread:-1;}
            if(count!=98304||spread<=.01f||spread>65504)throw new BakeFailure(FailureCode.HDR_FLAT_OR_RANGE);
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
                throw new BakeFailure(FailureCode.CACHE_ARTIFACT_MISMATCH);
        }
        static void SeedMeta(string path,string guid)
        {
            if(File.Exists(path+".meta"))
            {
                if(!File.ReadAllText(path+".meta").Split('\n').Any(x=>x.Trim()=="guid: "+guid))throw new BakeFailure(FailureCode.GUID_OWNERSHIP);
                return;
            }
            File.WriteAllText(path+".meta","fileFormatVersion: 2\nguid: "+guid+"\nTextureImporter:\n  serializedVersion: 13\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n",new UTF8Encoding(false));
        }
        public static string SourceDigest()=>ComputeDigest(out _);
        static string ComputeDigest(out System.Collections.Generic.Dictionary<string,string> inputs)
        {
            inputs=new System.Collections.Generic.Dictionary<string,string>(StringComparer.Ordinal);
            // Every static source byte and import setting under Shop is covered,
            // excluding ONLY our outputs. Generated meshes/materials are included.
            // Dependency hashes also cover the referenced Lit/renderer/pipeline.
            var files=Directory.GetFiles(G3ShopArtImporter.Root,"*",SearchOption.AllDirectories)
                .Select(p=>p.Replace('\\','/')).Where(p=>!p.StartsWith(Root+"/",StringComparison.Ordinal)&&p!=Root+".meta").Concat(RecipeSources).Distinct().OrderBy(p=>p,StringComparer.Ordinal).ToArray();
            var text=new StringBuilder(G3ShopEnvironment.ReflectionRecipe+"\n"+Application.unityVersion+"\n"+PlayerSettings.colorSpace+"\n");
            foreach(string path in files){if(!File.Exists(path))throw new BakeFailure(FailureCode.SOURCE_INPUT_MISSING);string value=HashFile(path);inputs.Add("FILE|"+path,value);text.Append(path).Append('|').Append(value).Append('\n');}
            foreach(string path in DependencyRoots){if(AssetDatabase.LoadMainAssetAtPath(path)==null)throw new BakeFailure(FailureCode.SOURCE_DEPENDENCY_MISSING);string value=AssetDatabase.GetAssetDependencyHash(path).ToString();inputs.Add("DEPENDENCY|"+path,value);text.Append(path).Append('|').Append(value).Append('\n');}
            using(var sha=SHA256.Create())return Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(text.ToString())));
        }
        sealed class LightingSnapshot
        {
            readonly AmbientMode mode=RenderSettings.ambientMode;readonly Color sky=RenderSettings.ambientSkyColor,equator=RenderSettings.ambientEquatorColor,ground=RenderSettings.ambientGroundColor,ambient=RenderSettings.ambientLight;
            readonly SphericalHarmonicsL2 sh=RenderSettings.ambientProbe;readonly Light sun=RenderSettings.sun;readonly float intensity=RenderSettings.reflectionIntensity;
            public void RequireUnchanged()
            {
                if(RenderSettings.ambientMode!=mode||RenderSettings.ambientSkyColor!=sky||RenderSettings.ambientEquatorColor!=equator||RenderSettings.ambientGroundColor!=ground||RenderSettings.ambientLight!=ambient||!RenderSettings.ambientProbe.Equals(sh)||RenderSettings.sun!=sun||RenderSettings.reflectionIntensity!=intensity)
                    throw new BakeFailure(FailureCode.CLEANUP_LIGHTING);
            }
        }
        enum FailureCode
        {
            NONE,IN_PLAY_MODE,ISOLATION_CONFLICT,STATIC_LAYER_MISMATCH,STATIC_FLAG_MISSING,STATIC_MESH_MISSING,GEOMETRY_BOUNDS,PROBE_CONFIG,
            SOURCE_DIGEST_CHANGED,RECEIPT_SIZE,CLEANUP_PIPELINE_OR_SCENE,BAKE_RETURNED_FALSE,IMPORTER_MISSING,IMPORTER_EXTERNAL_REMAP,
            GUID_MISMATCH,EXR_DIMENSIONS,CUBEMAP_LAYOUT,HDR_NONFINITE,HDR_FLAT_OR_RANGE,CACHE_ARTIFACT_MISMATCH,GUID_OWNERSHIP,
            SOURCE_INPUT_MISSING,SOURCE_DEPENDENCY_MISSING,CLEANUP_LIGHTING,FIXED_FILE_MISSING_OR_SIZE,BUILD_IDENTITY_INVALID,
            FINAL_TEXTURE_CONTRACT,UNCLASSIFIED_NATIVE_EXCEPTION,DIAGNOSTIC_WRITE_FAILURE
        }
        sealed class BakeFailure:InvalidOperationException
        {
            public readonly FailureCode Code;
            public BakeFailure(FailureCode code,Exception inner=null):base(code.ToString(),inner){Code=code;}
        }
        static void Observed(BakeTrace trace,Action operation)
        {try{operation();}catch(Exception error){trace?.Failure(error);throw;}}
        // Fixed observations only. No exception message, stack, file path, hardware
        // string, editor log or asset content enters this sidecar.
        // Stable diagnostic IDs only; never serialize file paths or asset text.
        static readonly string[] DiagnosticMaterials={"Aged_Aluminium","Bone_Laminate","Brass_Worn","Ceramic_Glazed","Charcoal_Metal","CounterToolTag_1","CounterToolTag_2","CounterToolTag_3","Cream_Plaster","Dark_Green_Felt","Decoration_Print_Atlas","Display_Silver_Coating","Glass_Blue_Water","Glass_Clear","Grout","Heritage_Green_Paint","Ink","Leaves_Green","Newspaper","Oxblood_Enamel","Paper_Ivory","Plastic_Cream","Rubber","Service_Monitor","ShopSign","StreetBlur","Ticket_Swap_1","Ticket_Swap_2","Ticket_Type_Label","Warm_Light","Warm_Oak","Warm_Terrazzo","Tool_Dock_Liner"};
        static int DiagnosticMaterial(string path,out int role)
        {
            role=0;string prefix=G3ShopArtImporter.Root+"/Materials/";
            for(int i=0;i<DiagnosticMaterials.Length;i++)
            {
                string stem=prefix+DiagnosticMaterials[i];
                if(path==stem+".mat"){role=1;return i;}
                if(path==stem+".mat.meta"){role=2;return i;}
                if(path==stem+"_MetallicSmoothness.asset"){role=3;return i;}
                if(path==stem+"_MetallicSmoothness.asset.meta"){role=4;return i;}
            }
            return -1;
        }
        sealed class BakeTrace
        {
            readonly System.Diagnostics.Stopwatch clock=System.Diagnostics.Stopwatch.StartNew();
            readonly System.Collections.Generic.HashSet<Exception> recorded=new System.Collections.Generic.HashSet<Exception>();
            readonly TraceReceipt receipt;readonly string path;bool writeFailed;
            public bool succeeded,cacheHit,bakeAttempted,bakeReturned,sceneObserved,sceneValid,sceneLoaded,activeMatches,fileObserved,fileExists,
                textureObserved,textureExists,rangeObserved,rangeFinite,digestCompared,digestSame,guidObserved,guidPresent,guidMatches,metaObserved,metaExists;
            public int bakeIndex=-1,captureRenderers=-1,foreignRenderers=-1,foreignLights=-1,foreignProbes=-1,width=-1,height=-1,mipCount=-1,formatCode=-1,
                sourceWidth=-1,sourceHeight=-1,pixelSampleCount,changedInputCount=-1,changedInputKinds;
            public long captureTriangles=-1,fileBytes=-1,metaBytes=-1;public float maxChannelRange=-1;
            public long matBits,metaBits,packBits,packMetaBits,dirtyMatBits=-1,dirtyPackBits=-1;
            public int changedOther,dirtyStage=-1;
            int stageCode;
            BakeTrace(string commit,string run,string attempt)
            {
                receipt=new TraceReceipt{startedUtc=DateTime.UtcNow.ToString("O",System.Globalization.CultureInfo.InvariantCulture),sourceCommit=commit,runId=run,runAttempt=attempt};
                path=Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/visual-candidate/reflection-progress.json"));
            }
            public static BakeTrace CreateForCapture()
            {
                var args=System.Environment.GetCommandLineArgs();int assembly=Array.IndexOf(args,"-assemblyNames");
                if(assembly<0||assembly+1>=args.Length||args[assembly+1]!="Lottery.G3.VisualCandidate.Tests")return null;
                string commit=Arg("-probeCommit"),run=Arg("-probeRunId"),attempt=Arg("-probeRunAttempt");
                if(commit=="LOCAL_UNBOUND"||run=="LOCAL_UNBOUND"||attempt=="LOCAL_UNBOUND")throw new BakeFailure(FailureCode.BUILD_IDENTITY_INVALID);
                return new BakeTrace(commit,run,attempt);
            }
            public void ResetCube(int index)
            {
                bakeIndex=index;bakeAttempted=bakeReturned=fileObserved=fileExists=textureObserved=textureExists=rangeObserved=rangeFinite=guidObserved=guidPresent=guidMatches=metaObserved=metaExists=false;
                width=height=mipCount=formatCode=sourceWidth=sourceHeight=-1;fileBytes=metaBytes=-1;pixelSampleCount=0;maxChannelRange=-1;
            }
            public void ClearSceneObservation(){sceneObserved=sceneValid=sceneLoaded=activeMatches=false;}
            public void ObserveScene(Scene scene)
            {sceneObserved=true;sceneValid=scene.IsValid();sceneLoaded=sceneValid&&scene.isLoaded;activeMatches=sceneLoaded&&SceneManager.GetActiveScene().handle==scene.handle;}
            public void ObserveFile(string file)
            {fileObserved=true;fileExists=File.Exists(file);fileBytes=fileExists?new FileInfo(file).Length:-1;}
            public void ObserveMeta(string file)
            {metaObserved=true;metaExists=File.Exists(file);metaBytes=metaExists?new FileInfo(file).Length:-1;}
            public void ObserveCube(Cubemap cube)
            {
                textureObserved=true;textureExists=cube!=null;
                width=cube!=null?cube.width:-1;height=cube!=null?cube.height:-1;mipCount=cube!=null?cube.mipmapCount:-1;formatCode=cube!=null?(int)cube.format:-1;
            }
            public void ObserveInputChanges(System.Collections.Generic.Dictionary<string,string> before,System.Collections.Generic.Dictionary<string,string> after)
            {
                changedInputCount=0;changedInputKinds=0;matBits=metaBits=packBits=packMetaBits=0;changedOther=0;
                foreach(string key in before.Keys.Union(after.Keys))
                {
                    if(before.TryGetValue(key,out string a)&&after.TryGetValue(key,out string b)&&a==b)continue;
                    changedInputCount++;
                    int role;int id=DiagnosticMaterial(key.StartsWith("FILE|",StringComparison.Ordinal)?key.Substring(5):"",out role);
                    if(id<0)changedOther++;
                    else {long bit=1L<<id;if(role==1)matBits|=bit;else if(role==2)metaBits|=bit;else if(role==3)packBits|=bit;else packMetaBits|=bit;}

                    changedInputKinds|=key.StartsWith("DEPENDENCY|",StringComparison.Ordinal)?64:key.Contains("/Generated/")?1:key.Contains("/Materials/")?2:key.Contains("/Textures/")?4:key.Contains("/Exterior/")?8:key.StartsWith("FILE|"+G3ShopArtImporter.Root+"/",StringComparison.Ordinal)?16:32;
                }
            }
            void ObserveLoadedDirty(int stage)
            {
                // Observe only already-loaded objects: do not load, save, refresh or repair assets.
                try {
                    long materials=0,packed=0;
                    foreach(var asset in Resources.FindObjectsOfTypeAll<Material>().Cast<UnityEngine.Object>().Concat(Resources.FindObjectsOfTypeAll<Texture2D>()))
                    {int role;int id=DiagnosticMaterial(AssetDatabase.GetAssetPath(asset),out role);if(id>=0&&EditorUtility.IsDirty(asset)){if(role==1)materials|=1L<<id;else if(role==3)packed|=1L<<id;}}
                    dirtyMatBits=materials;dirtyPackBits=packed;dirtyStage=stage;
                } catch {dirtyMatBits=dirtyPackBits=-1;dirtyStage=-1;writeFailed=true;}
            }
            public void Mark(int stage){stageCode=stage;if(stage==21||stage==71||stage==112||stage==212||stage==306||stage==310||stage==311||stage==320||stage==321||stage==322||stage==323||stage==324||stage==325)ObserveLoadedDirty(stage);Append(FailureCode.NONE,"NONE");}
            bool AlreadyRecorded(Exception error)
            {return recorded.Contains(error)||(error is AggregateException aggregate&&aggregate.InnerExceptions.Count>0&&aggregate.InnerExceptions.All(AlreadyRecorded));}
            public void Failure(Exception error)
            {
                if(AlreadyRecorded(error))return;recorded.Add(error);
                FailureCode code=error is BakeFailure known?known.Code:FailureCode.UNCLASSIFIED_NATIVE_EXCEPTION;
                string kind=ExceptionKind(error);
                if(receipt.firstFailureStage<0){receipt.firstFailureStage=stageCode;receipt.firstFailureCode=code.ToString();receipt.firstExceptionKind=kind;}
                receipt.failureCount++;Append(code,kind);
            }
            static string ExceptionKind(Exception error)
            {
                if(error is BakeFailure)return "REQUIRE";if(error is AggregateException)return "AGGREGATE";
                if(error is ArgumentException)return "ARGUMENT";if(error is IOException)return "IO";if(error is UnauthorizedAccessException)return "ACCESS";
                if(error is InvalidOperationException)return "INVALID_OPERATION";if(error is UnityException)return "UNITY";
                if(error is NullReferenceException)return "NULL_REFERENCE";if(error is NotSupportedException)return "NOT_SUPPORTED";return "OTHER";
            }
            void Append(FailureCode code,string kind)
            {
                if(receipt.events.Count>=64){writeFailed=true;return;}
                receipt.events.Add(new TraceEvent{stageCode=stageCode,elapsedMs=clock.ElapsedMilliseconds,errorCode=code.ToString(),exceptionKind=kind,bakeIndex=bakeIndex,
                    captureRenderers=captureRenderers,captureTriangles=captureTriangles,foreignRenderers=foreignRenderers,foreignLights=foreignLights,foreignProbes=foreignProbes,
                    sceneObserved=sceneObserved,sceneValid=sceneValid,sceneLoaded=sceneLoaded,activeMatches=activeMatches,fileObserved=fileObserved,fileExists=fileExists,fileBytes=fileBytes,
                    textureObserved=textureObserved,textureExists=textureExists,width=width,height=height,mipCount=mipCount,formatCode=formatCode,sourceWidth=sourceWidth,sourceHeight=sourceHeight,
                    bakeAttempted=bakeAttempted,bakeReturned=bakeReturned,rangeObserved=rangeObserved,rangeFinite=rangeFinite,pixelSampleCount=pixelSampleCount,maxChannelRange=maxChannelRange,
                    digestCompared=digestCompared,digestSame=digestSame,changedInputCount=changedInputCount,changedInputKinds=changedInputKinds,
                    matBits=matBits,metaBits=metaBits,packBits=packBits,packMetaBits=packMetaBits,changedOther=changedOther,dirtyMatBits=dirtyMatBits,dirtyPackBits=dirtyPackBits,dirtyStage=dirtyStage,
                    guidObserved=guidObserved,guidPresent=guidPresent,guidMatches=guidMatches,metaObserved=metaObserved,metaExists=metaExists,metaBytes=metaBytes});
                Write();
            }
            void Write()
            {
                try
                {
                    receipt.cacheHit=cacheHit;receipt.diagnosticWriteFailed=writeFailed;receipt.elapsedMs=clock.ElapsedMilliseconds;
                    string json=JsonUtility.ToJson(receipt,false);if(Encoding.UTF8.GetByteCount(json)>65536)throw new BakeFailure(FailureCode.DIAGNOSTIC_WRITE_FAILURE);
                    Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,json,new UTF8Encoding(false));
                }
                catch{writeFailed=true;receipt.diagnosticWriteFailed=true;}
            }
            public void Finish()
            {
                // Observation failure is fail-closed in the separate CI diagnostic gate,
                // but must never replace a bake exception or turn a valid bake into failure.
                if(writeFailed)Failure(new BakeFailure(FailureCode.DIAGNOSTIC_WRITE_FAILURE));
                receipt.status=succeeded&&receipt.failureCount==0&&!writeFailed?"COMPLETE":"FAILED";
                Mark(receipt.status=="COMPLETE"?400:499);
                if(writeFailed&&receipt.status=="COMPLETE")
                {Failure(new BakeFailure(FailureCode.DIAGNOSTIC_WRITE_FAILURE));receipt.status="FAILED";Mark(499);}
            }
        }
        [Serializable] sealed class TraceReceipt
        {
            public int schemaVersion=1,firstFailureStage=-1,failureCount;
            public string startedUtc;
            public string scope="REFLECTION_PREPARATION_DIAGNOSTIC_NOT_VISUAL_PASS",sourceCommit,runId,runAttempt,status="RUNNING",firstFailureCode="NONE",firstExceptionKind="NONE";
            public bool cacheHit,diagnosticWriteFailed;public long elapsedMs;
            public System.Collections.Generic.List<TraceEvent> events=new System.Collections.Generic.List<TraceEvent>();
        }
        [Serializable] sealed class TraceEvent
        {
            public int stageCode,bakeIndex,captureRenderers,foreignRenderers,foreignLights,foreignProbes,width,height,mipCount,formatCode,sourceWidth,sourceHeight,pixelSampleCount,changedInputCount,changedInputKinds;
            public long elapsedMs,captureTriangles,fileBytes,metaBytes,matBits,metaBits,packBits,packMetaBits,dirtyMatBits,dirtyPackBits;
            public int changedOther,dirtyStage;
            public string errorCode,exceptionKind;
            public bool sceneObserved,sceneValid,sceneLoaded,activeMatches,fileObserved,fileExists,textureObserved,textureExists,bakeAttempted,bakeReturned,rangeObserved,rangeFinite,digestCompared,digestSame,
                guidObserved,guidPresent,guidMatches,metaObserved,metaExists;
            public float maxChannelRange;
        }

        static void RequireSize(string path,long maximum){if(!File.Exists(path)||new FileInfo(path).Length<=0||new FileInfo(path).Length>maximum)throw new BakeFailure(FailureCode.FIXED_FILE_MISSING_OR_SIZE);}
        static string HashFile(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return Hex(sha.ComputeHash(f));}
        static string Hex(byte[] bytes)=>BitConverter.ToString(bytes).Replace("-","").ToLowerInvariant();
        static string Arg(string name)
        {
            var args=System.Environment.GetCommandLineArgs();for(int i=0;i<args.Length-1;i++)if(args[i]==name)
            {string value=args[i+1],pattern=name=="-probeCommit"?"^[0-9a-f]{40}$":"^[1-9][0-9]{0,19}$";if(!System.Text.RegularExpressions.Regex.IsMatch(value,pattern))throw new BakeFailure(FailureCode.BUILD_IDENTITY_INVALID);return value;}
            return "LOCAL_UNBOUND";
        }
    }
}
