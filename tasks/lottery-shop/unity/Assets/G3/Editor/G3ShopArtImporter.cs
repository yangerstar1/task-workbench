using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
namespace Lottery.G3.Editor
{
    public static class G3ShopArtImporter
    {
        public const string Root="Assets/G3/Shop/Resources/G3/Shop";
        public const string PipelinePath=Root+"/G3VisualPipeline.asset";
        [Serializable] sealed class Materials { public MaterialEntry[] materials; }
        [Serializable] sealed class MaterialEntry { public string name,baseColorTexture,normalTexture;public float[] baseColor;public float metallic,roughness,transmission,emission; }
        [MenuItem("Lottery/G3/Prepare original shop art")]
        public static void Prepare()
        {
            string model=Root+"/LotteryShop_Interior.fbx",json=Root+"/materials.json";
            if(!File.Exists(model)||!File.Exists(json)||!File.Exists(Root+"/anchors.json"))throw new InvalidOperationException("Original shop FBX and manifests are required for this candidate");
            AssetDatabase.Refresh();Directory.CreateDirectory(Root+"/Materials");
            var data=JsonUtility.FromJson<Materials>(File.ReadAllText(json));
            if(data?.materials==null||data.materials.Length<5)throw new InvalidOperationException("Shop material manifest is incomplete");
            var shader=Shader.Find("Universal Render Pipeline/Lit");if(shader==null)throw new InvalidOperationException("URP/Lit is required");
            var importer=AssetImporter.GetAtPath(model) as ModelImporter;if(importer==null)throw new InvalidOperationException("FBX model importer missing");
            importer.globalScale=1;importer.useFileScale=true;importer.importAnimation=false;importer.importCameras=false;importer.importLights=false;
            importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;importer.addCollider=false;importer.isReadable=true;
            foreach(var item in data.materials)
            {
                if(string.IsNullOrEmpty(item.name)||item.baseColor==null||item.baseColor.Length<3)throw new InvalidOperationException("Invalid material entry");
                string path=Root+"/Materials/"+item.name+".mat";var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(material==null){material=new Material(shader);AssetDatabase.CreateAsset(material,path);}else material.shader=shader;
                material.SetColor("_BaseColor",new Color(item.baseColor[0],item.baseColor[1],item.baseColor[2],item.baseColor.Length>3?item.baseColor[3]:1));
                material.SetFloat("_Metallic",Mathf.Clamp01(item.metallic));material.SetFloat("_Smoothness",1-Mathf.Clamp01(item.roughness));
                if(!string.IsNullOrEmpty(item.baseColorTexture))material.SetTexture("_BaseMap",Texture(item.baseColorTexture,false));
                if(!string.IsNullOrEmpty(item.normalTexture)){material.SetTexture("_BumpMap",Texture(item.normalTexture,true));material.EnableKeyword("_NORMALMAP");material.SetFloat("_BumpScale",.35f);}
                if(item.transmission>0){var c=material.GetColor("_BaseColor");c.a=item.name=="Glass_Clear"? .13f:.42f;material.SetColor("_BaseColor",c);material.SetFloat("_Surface",1);material.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);material.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);material.SetFloat("_ZWrite",0);material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");material.renderQueue=(int)RenderQueue.Transparent;}
                if(item.emission>0){material.EnableKeyword("_EMISSION");material.SetColor("_EmissionColor",new Color(item.baseColor[0],item.baseColor[1],item.baseColor[2])*Mathf.Min(item.emission,2));}
                EditorUtility.SetDirty(material);importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material),item.name),material);
            }
            importer.SaveAndReimport();
            foreach(string toolFile in Directory.GetFiles(Root,"Tool_*.fbx"))
            {var toolImporter=AssetImporter.GetAtPath(toolFile) as ModelImporter;if(toolImporter==null)throw new InvalidOperationException("Tool model importer missing");toolImporter.globalScale=1;toolImporter.useFileScale=true;toolImporter.importAnimation=false;toolImporter.importCameras=false;toolImporter.importLights=false;toolImporter.addCollider=false;
                foreach(var item in data.materials)toolImporter.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material),item.name),AssetDatabase.LoadAssetAtPath<Material>(Root+"/Materials/"+item.name+".mat"));toolImporter.SaveAndReimport();}

            var source=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(Lottery.Probe.Editor.ProbeBuild.PipelinePath);
            if(source==null)throw new InvalidOperationException("Prepare Probe pipeline before G3 shop art");
            var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if(pipeline==null){pipeline=UnityEngine.Object.Instantiate(source);AssetDatabase.CreateAsset(pipeline,PipelinePath);}else EditorUtility.CopySerialized(source,pipeline);
            pipeline.name="G3 original shop lighting";pipeline.shadowDistance=12;pipeline.msaaSampleCount=4;pipeline.supportsHDR=false;
            var serialized=new SerializedObject(pipeline);SetBool(serialized,"m_MainLightShadowsSupported",true);SetBool(serialized,"m_SoftShadowsSupported",true);
            SetInt(serialized,"m_MainLightShadowmapResolution",2048);SetInt(serialized,"m_ShadowCascadeCount",2);SetInt(serialized,"m_AdditionalLightsRenderingMode",1);SetInt(serialized,"m_AdditionalLightsPerObjectLimit",4);serialized.ApplyModifiedPropertiesWithoutUndo();
            GraphicsSettings.defaultRenderPipeline=pipeline;int original=QualitySettings.GetQualityLevel();for(int i=0;i<QualitySettings.names.Length;i++){QualitySettings.SetQualityLevel(i);QualitySettings.renderPipeline=pipeline;}QualitySettings.SetQualityLevel(original);
            EditorUtility.SetDirty(pipeline);AssetDatabase.SaveAssets();
            var loaded=AssetDatabase.LoadAssetAtPath<GameObject>(model);var renderers=loaded.GetComponentsInChildren<Renderer>();
            if(renderers.Length<30||renderers.Any(r=>r.sharedMaterials.Any(m=>m==null||m.shader!=shader)))throw new InvalidOperationException("Shop import has too few authored renderers or unresolved URP materials");
            BuildRuntimePrefab(loaded);
            Debug.Log("G3_SHOP_IMPORT original_authored_meshes="+renderers.Length+" materials="+data.materials.Length+" pipeline="+PipelinePath+" DEVICE_QA_NOT_RUN");
        }
        static void BuildRuntimePrefab(GameObject source)
        {
            // Merge only static authored room meshes by material. Dynamic tickets,
            // state-bound tools and JSON interaction colliders remain independent.
            string generated=Root+"/Generated";Directory.CreateDirectory(generated);
            var instance=UnityEngine.Object.Instantiate(source);
            var root=new GameObject("LotteryShop_Runtime");var groups=new Dictionary<string,List<CombineInstance>>();var materials=new Dictionary<string,Material>();int transparent=0;
            try
            {
                var marker=instance.GetComponentsInChildren<Transform>().FirstOrDefault(t=>t.name=="Anchor_ScratchTicket");
                if(marker==null||Vector3.Distance(marker.position,new Vector3(2.05f,.824f,-.1f))>.015f)
                    throw new InvalidOperationException("FBX metre/axis anchor mismatch. Expected Anchor_ScratchTicket=(2.05,.824,-.1); actual="+(marker==null?"MISSING":marker.position.ToString("F4")));
                foreach(var filter in instance.GetComponentsInChildren<MeshFilter>())
                {
                    var renderer=filter.GetComponent<MeshRenderer>();if(renderer==null||filter.sharedMesh==null)continue;
                    for(int sub=0;sub<filter.sharedMesh.subMeshCount;sub++)
                    {
                        var material=renderer.sharedMaterials[Mathf.Min(sub,renderer.sharedMaterials.Length-1)];
                        string key=material.name+(material.renderQueue>=(int)RenderQueue.Transparent?"_glass_"+(transparent++):"");
                        if(!groups.ContainsKey(key)){groups[key]=new List<CombineInstance>();materials[key]=material;}
                        groups[key].Add(new CombineInstance{mesh=filter.sharedMesh,subMeshIndex=sub,transform=filter.transform.localToWorldMatrix});
                    }
                }
                foreach(var pair in groups)
                {
                    string path=generated+"/"+pair.Key+".asset";var mesh=AssetDatabase.LoadAssetAtPath<Mesh>(path);if(mesh==null){mesh=new Mesh();AssetDatabase.CreateAsset(mesh,path);}else mesh.Clear();
                    mesh.name="Static shop "+pair.Key;mesh.indexFormat=IndexFormat.UInt32;mesh.CombineMeshes(pair.Value.ToArray(),true,true);mesh.RecalculateBounds();EditorUtility.SetDirty(mesh);
                    var go=new GameObject(pair.Key);go.transform.SetParent(root.transform,false);go.AddComponent<MeshFilter>().sharedMesh=mesh;var renderer=go.AddComponent<MeshRenderer>();renderer.sharedMaterial=materials[pair.Key];renderer.receiveShadows=true;renderer.shadowCastingMode=materials[pair.Key].renderQueue>=(int)RenderQueue.Transparent?ShadowCastingMode.Off:ShadowCastingMode.On;
                }
                PrefabUtility.SaveAsPrefabAsset(root,Root+"/LotteryShop_Runtime.prefab");AssetDatabase.SaveAssets();
                Debug.Log("G3_SHOP_STATIC_BATCH opaque-by-material plus separate glass renderers="+groups.Count+"; performance on device remains NOT_RUN");
            }
            finally{UnityEngine.Object.DestroyImmediate(instance);UnityEngine.Object.DestroyImmediate(root);}
        }
        static Texture2D Texture(string file,bool normal)
        {
            string path=Root+"/Textures/"+Path.GetFileName(file);var importer=AssetImporter.GetAtPath(path) as TextureImporter;
            if(importer==null)throw new InvalidOperationException("Missing shop texture: "+path);
            importer.textureType=normal?TextureImporterType.NormalMap:TextureImporterType.Default;importer.sRGBTexture=!normal;importer.mipmapEnabled=true;importer.wrapMode=TextureWrapMode.Repeat;importer.maxTextureSize=2048;importer.textureCompression=TextureImporterCompression.Compressed;importer.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }
        static void SetBool(SerializedObject target,string name,bool value){var p=target.FindProperty(name);if(p==null)throw new InvalidOperationException("Unsupported pinned URP field "+name);p.boolValue=value;}
        static void SetInt(SerializedObject target,string name,int value){var p=target.FindProperty(name);if(p==null)throw new InvalidOperationException("Unsupported pinned URP field "+name);p.intValue=value;}
    }
}
