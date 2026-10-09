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
        const string ComparisonOriginalDiffuse = "Assets/DesertRV/Art/EnvironmentV4/sand_03_diff_1k.jpg";
        const string ComparisonCorrectedDiffuse = "Assets/DesertRV/Art/TerrainDiffuseCorrection/sand_03_diff_illumination_corrected_1k.png";
        const string ComparisonNormal = "Assets/DesertRV/Art/EnvironmentV4/sand_03_nor_gl_1k.jpg";
        static readonly string[][] comparisonTerrainRoles = {
            new[]{"Ground-Sand","Sand"}, new[]{"ReliefEast-Dune","Dune"}, new[]{"ReliefWest-Dune","Dune"}
        };
        [Serializable] sealed class DiffuseComparisonTerrain
        {
            public string objectName,scenePath,meshAsset,materialAsset;
        }
        [Serializable] sealed class DiffuseComparisonAsset
        {
            public string assetPath,sha256; public int width,height;
        }
        [Serializable] sealed class DiffuseComparisonMaterial
        {
            public string name,shader,baseMapAsset,normalMapAsset; public string[] keywords;
            public float normalScale,smoothness,metallic; public bool normalKeyword;
            public Vector2 baseScale,baseOffset,normalUvScale,normalUvOffset; public Color baseColor;
        }
        [Serializable] sealed class DiffuseComparisonImage
        {
            public string file,view,variant,sceneHash; public int width=1440,height=900,warmupRenderCount=1;
            public float fieldOfView,minimum,maximum; public bool normalEnabled=true,materialParametersPreserved=true;
            public Vector3 cameraPosition,cameraTarget; public DiffuseComparisonMaterial[] actualMaterials;
        }
        [Serializable] sealed class DiffuseComparisonReport
        {
            public string status="DIAGNOSTIC_DIFFUSE_COMPARISON_NOT_ART_ACCEPTANCE",graphicsDeviceType,graphicsDeviceName;
            public bool savedSceneAndMaterialBytesPreserved,captureBuffersReleased;
            public int terrainRenderers,protectedSavedAssetCount,warmupRenderCount=1;
            public DiffuseComparisonAsset[] diffuseAssets;
            public DiffuseComparisonTerrain[] terrainBindings;
            public DiffuseComparisonMaterial[] originalMaterials; public DiffuseComparisonImage[] images;
        }
        static DiffuseComparisonMaterial ReadDiffuseComparisonMaterial(Material m)
        {
            return new DiffuseComparisonMaterial{name=m.name,shader=m.shader.name,
                baseMapAsset=AssetDatabase.GetAssetPath(m.GetTexture("_BaseMap")),normalMapAsset=AssetDatabase.GetAssetPath(m.GetTexture("_BumpMap")),
                normalScale=m.GetFloat("_BumpScale"),smoothness=m.GetFloat("_Smoothness"),metallic=m.GetFloat("_Metallic"),
                normalKeyword=m.IsKeywordEnabled("_NORMALMAP"),keywords=m.shaderKeywords.OrderBy(k=>k,StringComparer.Ordinal).ToArray(),
                baseScale=m.GetTextureScale("_BaseMap"),baseOffset=m.GetTextureOffset("_BaseMap"),
                normalUvScale=m.GetTextureScale("_BumpMap"),normalUvOffset=m.GetTextureOffset("_BumpMap"),baseColor=m.GetColor("_BaseColor")};
        }
        static void AssertDiffuseComparisonMaterial(Material m,Material original,Texture2D diffuse)
        {
            // Enumerate every shader property. Only the _BaseMap texture reference may differ.
            if(m.shader!=original.shader||m.renderQueue!=original.renderQueue||m.enableInstancing!=original.enableInstancing||
                m.doubleSidedGI!=original.doubleSidedGI||m.globalIlluminationFlags!=original.globalIlluminationFlags||
                !m.shaderKeywords.OrderBy(k=>k,StringComparer.Ordinal).SequenceEqual(original.shaderKeywords.OrderBy(k=>k,StringComparer.Ordinal))||
                !m.IsKeywordEnabled("_NORMALMAP")||m.GetTexture("_BumpMap")!=original.GetTexture("_BumpMap")||
                AssetDatabase.GetAssetPath(m.GetTexture("_BumpMap"))!=ComparisonNormal||
                Mathf.Abs(m.GetFloat("_BumpScale")-.035f)>.000001f||m.GetTexture("_BaseMap")!=diffuse)
                throw new InvalidOperationException("Diffuse comparison changed shader, keywords, normal, or actual BaseMap binding.");
            for(int i=0;i<original.passCount;i++)
                if(m.GetShaderPassEnabled(original.GetPassName(i))!=original.GetShaderPassEnabled(original.GetPassName(i)))
                    throw new InvalidOperationException("Diffuse comparison changed a shader pass.");
            for(int i=0;i<original.shader.GetPropertyCount();i++)
            {
                string property=original.shader.GetPropertyName(i);bool same;
                switch(original.shader.GetPropertyType(i))
                {
                    case ShaderPropertyType.Color: same=m.GetColor(property)==original.GetColor(property);break;
                    case ShaderPropertyType.Vector: same=m.GetVector(property)==original.GetVector(property);break;
                    case ShaderPropertyType.Float: case ShaderPropertyType.Range: same=m.GetFloat(property)==original.GetFloat(property);break;
                    case ShaderPropertyType.Int: same=m.GetInteger(property)==original.GetInteger(property);break;
                    case ShaderPropertyType.Texture:
                        same=m.GetTexture(property)==(property=="_BaseMap"?diffuse:original.GetTexture(property))&&
                            m.GetTextureScale(property)==original.GetTextureScale(property)&&m.GetTextureOffset(property)==original.GetTextureOffset(property);break;
                    default: throw new InvalidOperationException("Unrecognized shader property type: "+property);
                }
                if(!same)throw new InvalidOperationException("Diffuse comparison changed material property: "+property);
            }
        }
        // Independent two-by-two diagnostic. Production authoring and the twenty/eight-view gates are untouched.
        public static void AuthorAndCaptureDiffuseComparison()
        {
            if(SystemInfo.graphicsDeviceType!=GraphicsDeviceType.OpenGLCore||SystemInfo.graphicsDeviceName.IndexOf("llvmpipe",StringComparison.OrdinalIgnoreCase)<0)
                throw new InvalidOperationException("Diffuse comparison requires actual OpenGLCore / llvmpipe rendering.");
            Texture2D originalDiffuse=null,correctedDiffuse=null;DiffuseComparisonAsset[] diffuseAssets=null;
            AuthorCandidateScenes();JourneyContentChecks.CheckCandidateLayout();
            var setup=EditorSceneManager.GetSceneManagerSetup();var protectedFiles=SnapshotProtectedFiles();
            var saved=new Dictionary<string,byte[]>();
            foreach(string path in new[]{BootstrapPath}.Concat(RegionPaths).Concat(new[]{PolishGenerated+"/Surface-Sand.mat",PolishGenerated+"/Surface-Dune.mat"}))saved.Add(path,File.ReadAllBytes(path));
            if(saved.Count!=6)throw new InvalidOperationException("Expected four saved scenes and two saved terrain materials.");
            string output=Path.GetFullPath("JourneyEvidence/diffuse-comparison");
            if(Directory.Exists(output))throw new IOException("Refuse stale diffuse comparison evidence.");Directory.CreateDirectory(output);
            var records=new List<DiffuseComparisonImage>();var clones=new List<Material>();
            RenderTexture target=null;Texture2D pixels=null;var previousTarget=RenderTexture.active;
            Renderer[] terrain=null;Material[] originals=null;DiffuseComparisonMaterial[] materials=null;DiffuseComparisonTerrain[] terrainBindings=null;
            bool released=false,preserved=false;
            try
            {
                var boot=EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);
                var env=EditorSceneManager.OpenScene(RegionPaths[1],OpenSceneMode.Additive);
                UnityEngine.SceneManagement.SceneManager.SetActiveScene(env);
                // Load after the final scene transition: the corrected asset has no saved-scene reference.
                originalDiffuse=AssetDatabase.LoadAssetAtPath<Texture2D>(ComparisonOriginalDiffuse);
                correctedDiffuse=AssetDatabase.LoadAssetAtPath<Texture2D>(ComparisonCorrectedDiffuse);
                if(!originalDiffuse||!correctedDiffuse||originalDiffuse==correctedDiffuse||
                    originalDiffuse.width!=1024||originalDiffuse.height!=1024||correctedDiffuse.width!=1024||correctedDiffuse.height!=1024||
                    HashFile(ComparisonOriginalDiffuse)==HashFile(ComparisonCorrectedDiffuse))
                    throw new InvalidOperationException("Required distinct 1K original and illumination-corrected diffuse assets are missing or invalid.");
                diffuseAssets=new[]{originalDiffuse,correctedDiffuse}.Select(t=>new DiffuseComparisonAsset{
                    assetPath=AssetDatabase.GetAssetPath(t),sha256=HashFile(AssetDatabase.GetAssetPath(t)),width=t.width,height=t.height}).ToArray();
                var motor=Components<JourneyMotor>(boot).Single();var b=Components<RegionBinding>(env).Single();
                motor.vehicle.SetPositionAndRotation(b.spawn.position,b.spawn.rotation);
                var actions=Components<JourneyActions>(boot).Single();CheckNewLayoutClearance(b,motor,actions);
                terrain=b.GetComponentsInChildren<Renderer>(true).Where(r=>r.enabled&&r.sharedMaterial&&
                    (AssetDatabase.GetAssetPath(r.sharedMaterial)==PolishGenerated+"/Surface-Sand.mat"||AssetDatabase.GetAssetPath(r.sharedMaterial)==PolishGenerated+"/Surface-Dune.mat")).ToArray();
                string found=string.Join("; ",terrain.Select(r=>r.name+" | "+r.gameObject.scene.path+" | "+AssetDatabase.GetAssetPath(r.sharedMaterial)));
                if(terrain.Length!=3||terrain.Any(r=>r.sharedMaterials.Length!=1))
                    throw new InvalidOperationException("Expected exactly three single-material terrain renderer groups; found: "+found);
                var bindings=new List<DiffuseComparisonTerrain>();
                foreach(var role in comparisonTerrainRoles)
                {
                    // Producer Save() prefixes GameObject names, but not mesh/material asset filenames.
                    var matching=terrain.Where(r=>r.name=="EnvironmentV4 "+role[0]).ToArray();
                    if(matching.Length!=1)throw new InvalidOperationException("Missing or duplicate terrain role "+role[0]+"; found: "+found);
                    var renderer=matching[0];var filter=renderer.GetComponent<MeshFilter>();
                    if(renderer.gameObject.scene!=env||renderer.transform.parent!=b.transform||!filter||!filter.sharedMesh||
                        AssetDatabase.GetAssetPath(filter.sharedMesh)!=PolishGenerated+"/R2-"+role[0]+".asset"||
                        AssetDatabase.GetAssetPath(renderer.sharedMaterial)!=PolishGenerated+"/Surface-"+role[1]+".mat")
                        throw new InvalidOperationException("Terrain role scene, parent, mesh, or material differs: "+role[0]);
                    bindings.Add(new DiffuseComparisonTerrain{objectName=renderer.name,scenePath=renderer.gameObject.scene.path,
                        meshAsset=AssetDatabase.GetAssetPath(filter.sharedMesh),materialAsset=AssetDatabase.GetAssetPath(renderer.sharedMaterial)});
                }
                terrainBindings=bindings.ToArray();
                originals=terrain.Select(r=>r.sharedMaterial).ToArray();
                materials=originals.Distinct().OrderBy(m=>m.name,StringComparer.Ordinal).Select(ReadDiffuseComparisonMaterial).ToArray();
                if(materials.Length!=2||materials.Any(m=>m.shader!="Universal Render Pipeline/Lit"||m.baseMapAsset!=ComparisonOriginalDiffuse||
                    m.normalMapAsset!=ComparisonNormal||!m.normalKeyword||Mathf.Abs(m.normalScale-.035f)>.000001f||Mathf.Abs(m.smoothness-.04f)>.000001f))
                    throw new InvalidOperationException("Comparison must start from the actual unchanged R3 standard Lit terrain.");
                target=new RenderTexture(1440,900,24,RenderTextureFormat.ARGB32){antiAliasing=1,hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create())throw new InvalidOperationException("Comparison render target allocation failed.");
                pixels=new Texture2D(1440,900,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                var camera=motor.view;camera.enabled=false;camera.clearFlags=CameraClearFlags.Skybox;camera.nearClipPlane=.04f;camera.farClipPlane=450;camera.allowHDR=true;
                foreach(var particle in Components<ParticleSystem>(env))particle.Simulate(7,true,true,true);
                string sceneHash=AssetDatabase.GetAssetDependencyHash(RegionPaths[1]).ToString();
                foreach(string variant in new[]{"original","illumination-corrected"})
                {
                    var diffuse=variant=="original"?originalDiffuse:correctedDiffuse;var map=new Dictionary<Material,Material>();
                    foreach(var original in originals.Distinct())
                    {
                        var m=new Material(original){name=original.name,hideFlags=HideFlags.HideAndDontSave};clones.Add(m);map.Add(original,m);
                        m.SetTexture("_BaseMap",diffuse);AssertDiffuseComparisonMaterial(m,original,diffuse);
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
                        // One identical-parameter render warms each camera/state; only the next render is read.
                        for(int warmup=0;warmup<1;warmup++)RenderPipeline.SubmitRenderRequest(camera,request);
                        RenderPipeline.SubmitRenderRequest(camera,request);RenderTexture.active=target;
                        pixels.ReadPixels(new Rect(0,0,1440,900),0,0);pixels.Apply();
                        for(int i=0;i<terrain.Length;i++)
                        {
                            if(terrain[i].sharedMaterial!=map[originals[i]])throw new InvalidOperationException("Comparison renderer material binding changed.");
                            AssertDiffuseComparisonMaterial(terrain[i].sharedMaterial,originals[i],diffuse);
                        }
                        var colors=pixels.GetPixels32();float min=1,max=0;
                        for(int i=0;i<colors.Length;i+=97){float value=(colors[i].r+colors[i].g+colors[i].b)/765f;min=Mathf.Min(min,value);max=Mathf.Max(max,value);}
                        if(max-min<.06f||max<.1f)throw new InvalidOperationException("Blank comparison render.");
                        string file="Scrapyard-"+view+"-"+variant+".png";var encoded=pixels.EncodeToPNG();
                        if(encoded==null||encoded.Length==0)throw new IOException("Comparison PNG encoding failed.");
                        string destination=Path.Combine(output,file);File.WriteAllBytes(destination,encoded);
                        if(!encoded.SequenceEqual(File.ReadAllBytes(destination)))throw new IOException("Comparison PNG save verification failed.");
                        records.Add(new DiffuseComparisonImage{file=file,view=view,variant=variant,sceneHash=sceneHash,fieldOfView=camera.fieldOfView,minimum=min,maximum=max,cameraPosition=at,cameraTarget=look,
                            actualMaterials=terrain.Select(r=>r.sharedMaterial).Distinct().OrderBy(m=>m.name,StringComparer.Ordinal).Select(ReadDiffuseComparisonMaterial).ToArray()});
                        RenderTexture.active=previousTarget;
                    }
                    for(int i=0;i<terrain.Length;i++)terrain[i].sharedMaterial=originals[i];
                    foreach(var m in clones)Object.DestroyImmediate(m);clones.Clear();
                }
                if(originals.Distinct().Any(m=>ShaderUtil.ShaderHasError(m.shader)))throw new InvalidOperationException("Standard Lit shader reported errors.");
            }
            finally
            {
                try
                {
                    if(terrain!=null&&originals!=null)for(int i=0;i<terrain.Length;i++)if(terrain[i])terrain[i].sharedMaterial=originals[i];
                    foreach(var m in clones)if(m)Object.DestroyImmediate(m);
                    RenderTexture.active=previousTarget;if(pixels)Object.DestroyImmediate(pixels);
                    if(target){try{target.Release();}finally{Object.DestroyImmediate(target);}}
                    if(pixels||target||clones.Any(m=>m))throw new InvalidOperationException("Comparison buffers/materials not released.");released=true;
                }
                finally
                {
                    try{RestoreSceneSetup(setup);}
                    finally
                    {
                        VerifyProtectedFiles(protectedFiles);
                        foreach(var item in saved)if(!item.Value.SequenceEqual(File.ReadAllBytes(item.Key)))throw new InvalidOperationException("Comparison changed saved scene/material bytes: "+item.Key);
                        preserved=true;
                    }
                }
            }
            if(records.Count!=4||!released||!preserved)throw new InvalidOperationException("Incomplete diffuse comparison.");
            string report=JsonUtility.ToJson(new DiffuseComparisonReport{graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName,
                savedSceneAndMaterialBytesPreserved=preserved,captureBuffersReleased=released,terrainRenderers=terrainBindings.Length,protectedSavedAssetCount=saved.Count,
                diffuseAssets=diffuseAssets,terrainBindings=terrainBindings,originalMaterials=materials,images=records.ToArray()},true);
            string reportPath=Path.Combine(output,"comparison-report.json");File.WriteAllText(reportPath,report);
            if(File.ReadAllText(reportPath)!=report)throw new IOException("Comparison report save verification failed.");
            Debug.Log("DIFFUSE_COMPARISON_FOUR_ACTUAL_VIEWS complete; normal retained; original production materials unchanged; diagnostic only");
        }
    }
}
