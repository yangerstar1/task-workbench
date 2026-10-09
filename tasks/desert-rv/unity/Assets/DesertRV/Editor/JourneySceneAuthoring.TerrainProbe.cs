using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneySceneAuthoring
    {
        [Serializable] sealed class TerrainProbeImage
        {
            public string file,view,variant,sceneHash; public int width=1440,height=900;
            public float fieldOfView,minimum,maximum; public bool normalEnabled,flatDiffuse;
            public Vector3 cameraPosition,cameraTarget;
        }
        [Serializable] sealed class TerrainProbeMaterial
        {
            public string name,shader,baseMapAsset,normalMapAsset; public float normalScale,smoothness,metallic;
            public Vector2 baseScale,baseOffset; public Color baseColor;
        }
        [Serializable] sealed class TerrainProbeReport
        {
            public string status="DIAGNOSTIC_CHANNEL_ABLATION_NOT_ART_ACCEPTANCE",graphicsDeviceType,graphicsDeviceName;
            public bool savedSceneAndMaterialBytesPreserved,captureBuffersReleased;
            public int terrainRenderers; public int[] flatDiffuseSrgbBytes={108,96,79};
            public TerrainProbeMaterial[] originalMaterials; public TerrainProbeImage[] images;
        }
        // Bounded diagnosis only: same two original Scrapyard camera poses, four fixed channel states.
        // Does not alter the production twenty-view entry, original geometry or source material assets.
        public static void AuthorAndCaptureTerrainProbe()
        {
            if(SystemInfo.graphicsDeviceType!=GraphicsDeviceType.OpenGLCore)throw new InvalidOperationException("Terrain probe requires real OpenGLCore rendering.");
            AuthorCandidateScenes();JourneyContentChecks.CheckCandidateLayout();
            var setup=EditorSceneManager.GetSceneManagerSetup();var protectedFiles=SnapshotProtectedFiles();
            var saved=new Dictionary<string,byte[]>();
            foreach(string path in new[]{BootstrapPath}.Concat(RegionPaths).Concat(new[]{PolishGenerated+"/Surface-Sand.mat",PolishGenerated+"/Surface-Dune.mat"}))saved.Add(path,File.ReadAllBytes(path));
            string output=Path.GetFullPath("JourneyEvidence/terrain-probe");
            if(Directory.Exists(output))throw new IOException("Refuse stale terrain probe evidence.");Directory.CreateDirectory(output);
            var records=new List<TerrainProbeImage>();var clones=new List<Material>();
            RenderTexture target=null;Texture2D pixels=null,meanDiffuse=null;var previousTarget=RenderTexture.active;
            Renderer[] terrain=null;Material[] originals=null;TerrainProbeMaterial[] materials=null;
            bool released=false,preserved=false;
            try
            {
                var boot=EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);
                var env=EditorSceneManager.OpenScene(RegionPaths[1],OpenSceneMode.Additive);
                UnityEngine.SceneManagement.SceneManager.SetActiveScene(env);
                var motor=Components<JourneyMotor>(boot).Single();var b=Components<RegionBinding>(env).Single();
                motor.vehicle.SetPositionAndRotation(b.spawn.position,b.spawn.rotation);
                var actions=Components<JourneyActions>(boot).Single();CheckNewLayoutClearance(b,motor,actions);
                terrain=b.GetComponentsInChildren<Renderer>(true).Where(r=>r.enabled&&r.sharedMaterial&&
                    (AssetDatabase.GetAssetPath(r.sharedMaterial)==PolishGenerated+"/Surface-Sand.mat"||AssetDatabase.GetAssetPath(r.sharedMaterial)==PolishGenerated+"/Surface-Dune.mat")).ToArray();
                if(terrain.Length!=3)throw new InvalidOperationException("Expected exactly ground and two dune renderer groups.");
                originals=terrain.Select(r=>r.sharedMaterial).ToArray();
                materials=originals.Distinct().OrderBy(m=>m.name,StringComparer.Ordinal).Select(m=>new TerrainProbeMaterial{
                    name=m.name,shader=m.shader.name,baseMapAsset=AssetDatabase.GetAssetPath(m.GetTexture("_BaseMap")),normalMapAsset=AssetDatabase.GetAssetPath(m.GetTexture("_BumpMap")),
                    normalScale=m.GetFloat("_BumpScale"),smoothness=m.GetFloat("_Smoothness"),metallic=m.GetFloat("_Metallic"),
                    baseScale=m.GetTextureScale("_BaseMap"),baseOffset=m.GetTextureOffset("_BaseMap"),baseColor=m.GetColor("_BaseColor")}).ToArray();
                if(materials.Length!=2||materials.Any(m=>m.shader!="Universal Render Pipeline/Lit"||Mathf.Abs(m.normalScale-.035f)>.000001f||Mathf.Abs(m.smoothness-.04f)>.000001f))
                    throw new InvalidOperationException("Probe must start from the actual R3 standard Lit terrain.");
                // Linear mean of the exact verified source JPEG, encoded back to sRGB (rounded to 8 bits).
                // A temporary texture keeps the production BaseColor unchanged; flat is diagnosis, not proposed art.
                meanDiffuse=new Texture2D(1,1,TextureFormat.RGBA32,false,false){name="Diagnostic source diffuse mean only",hideFlags=HideFlags.HideAndDontSave};
                meanDiffuse.SetPixels32(new[]{new Color32(108,96,79,255)});meanDiffuse.Apply();
                target=new RenderTexture(1440,900,24,RenderTextureFormat.ARGB32){antiAliasing=1,hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create())throw new InvalidOperationException("Probe render target allocation failed.");
                pixels=new Texture2D(1440,900,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                var camera=motor.view;camera.enabled=false;camera.clearFlags=CameraClearFlags.Skybox;camera.nearClipPlane=.04f;camera.farClipPlane=450;camera.allowHDR=true;
                foreach(var particle in Components<ParticleSystem>(env))particle.Simulate(7,true,true,true);
                string sceneHash=AssetDatabase.GetAssetDependencyHash(RegionPaths[1]).ToString();
                foreach(string variant in new[]{"original","normal-off","diffuse-flat","diffuse-flat-normal-off"})
                {
                    bool flat=variant.StartsWith("diffuse-flat",StringComparison.Ordinal),normal=!variant.EndsWith("normal-off",StringComparison.Ordinal);
                    var map=new Dictionary<Material,Material>();
                    foreach(var original in originals.Distinct())
                    {
                        var m=new Material(original){name="Terrain probe "+variant,hideFlags=HideFlags.HideAndDontSave};clones.Add(m);map.Add(original,m);
                        if(flat)m.SetTexture("_BaseMap",meanDiffuse);
                        if(!normal){m.DisableKeyword("_NORMALMAP");m.SetTexture("_BumpMap",null);m.SetFloat("_BumpScale",0);}
                        // Verify actual clone bindings before rendering, not only intended variant labels.
                        if(m.shader!=original.shader||m.IsKeywordEnabled("_NORMALMAP")!=normal||
                           m.GetTexture("_BaseMap")!=(flat?meanDiffuse:original.GetTexture("_BaseMap"))||
                           m.GetTexture("_BumpMap")!=(normal?original.GetTexture("_BumpMap"):null)||
                           Mathf.Abs(m.GetFloat("_BumpScale")-(normal?.035f:0))>.000001f||
                           m.GetColor("_BaseColor")!=original.GetColor("_BaseColor")||
                           m.GetFloat("_Smoothness")!=original.GetFloat("_Smoothness")||
                           m.GetFloat("_Metallic")!=original.GetFloat("_Metallic"))
                            throw new InvalidOperationException("Actual diagnostic clone differs from its fixed channel state.");
                    }
                    for(int i=0;i<terrain.Length;i++)terrain[i].sharedMaterial=map[originals[i]];
                    foreach(string view in new[]{"overview","ground"})
                    {
                        camera.fieldOfView=view=="overview"?54:58;
                        Vector3 at=view=="overview"?new Vector3(31,39,-17):new Vector3(-5,1.65f,-7);
                        Vector3 look=view=="overview"?new Vector3(0,0,28):new Vector3(2,2.2f,25);
                        camera.transform.position=at;camera.transform.LookAt(look);Physics.SyncTransforms();CheckNewLayoutClearance(b,motor,actions);
                        var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                        if(!RenderPipeline.SupportsRenderRequest(camera,request))throw new InvalidOperationException("URP screenshot request unsupported.");
                        RenderPipeline.SubmitRenderRequest(camera,request);RenderTexture.active=target;
                        pixels.ReadPixels(new Rect(0,0,1440,900),0,0);pixels.Apply();
                        var colors=pixels.GetPixels32();float min=1,max=0;
                        for(int i=0;i<colors.Length;i+=97){float value=(colors[i].r+colors[i].g+colors[i].b)/765f;min=Mathf.Min(min,value);max=Mathf.Max(max,value);}
                        if(max-min<.06f||max<.1f)throw new InvalidOperationException("Blank probe render.");
                        string file="Scrapyard-"+view+"-"+variant+".png";File.WriteAllBytes(Path.Combine(output,file),pixels.EncodeToPNG());
                        records.Add(new TerrainProbeImage{file=file,view=view,variant=variant,sceneHash=sceneHash,fieldOfView=camera.fieldOfView,minimum=min,maximum=max,normalEnabled=normal,flatDiffuse=flat,cameraPosition=at,cameraTarget=look});
                        RenderTexture.active=previousTarget;
                    }
                    for(int i=0;i<terrain.Length;i++)terrain[i].sharedMaterial=originals[i];
                    foreach(var m in clones)Object.DestroyImmediate(m);clones.Clear();
                }
                if(ShaderUtil.ShaderHasError(originals[0].shader))throw new InvalidOperationException("Standard Lit shader reported errors.");
            }
            finally
            {
                try
                {
                    if(terrain!=null&&originals!=null)for(int i=0;i<terrain.Length;i++)if(terrain[i])terrain[i].sharedMaterial=originals[i];
                    foreach(var m in clones)if(m)Object.DestroyImmediate(m);
                    RenderTexture.active=previousTarget;if(pixels)Object.DestroyImmediate(pixels);if(meanDiffuse)Object.DestroyImmediate(meanDiffuse);
                    if(target){try{target.Release();}finally{Object.DestroyImmediate(target);}}
                    if(pixels||meanDiffuse||target)throw new InvalidOperationException("Probe buffers not released.");released=true;
                }
                finally
                {
                    try{RestoreSceneSetup(setup);}
                    finally
                    {
                        VerifyProtectedFiles(protectedFiles);
                        foreach(var item in saved)if(!item.Value.SequenceEqual(File.ReadAllBytes(item.Key)))throw new InvalidOperationException("Probe changed saved scene/material bytes: "+item.Key);
                        preserved=true;
                    }
                }
            }
            if(records.Count!=8||!released||!preserved)throw new InvalidOperationException("Incomplete terrain diagnostic.");
            File.WriteAllText(Path.Combine(output,"probe-report.json"),JsonUtility.ToJson(new TerrainProbeReport{graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName,savedSceneAndMaterialBytesPreserved=preserved,captureBuffersReleased=released,terrainRenderers=3,originalMaterials=materials,images=records.ToArray()},true));
            Debug.Log("TERRAIN_PROBE_EIGHT_ACTUAL_VIEWS complete; original production materials unchanged; diagnostic only");
        }
    }
}
