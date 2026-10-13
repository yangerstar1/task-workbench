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
        [Serializable] sealed class MaterialEntry { public string name,baseColorTexture,normalTexture,roughnessTexture,emissionTexture;public float[] baseColor,baseColorFactor,mainTextureScale,emissionColor;public float metallic,roughness,transmission,emission,normalStrength=1; }
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
            importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;importer.addCollider=false;importer.isReadable=true;importer.generateSecondaryUV=true;
            foreach(var item in data.materials)
            {
                if(string.IsNullOrEmpty(item.name)||item.baseColor==null||item.baseColor.Length<3)throw new InvalidOperationException("Invalid material entry");
                string path=Root+"/Materials/"+item.name+".mat";var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(material==null){material=new Material(shader);AssetDatabase.CreateAsset(material,path);}else material.shader=shader;
                // Factors describe actual Blender node multiplication, not a second tint
                // guessed from the texture's average colour. Direct textures use white.
                var factor=item.baseColorFactor;
                if(!string.IsNullOrEmpty(item.baseColorTexture)&&(factor==null||factor.Length<4))throw new InvalidOperationException("Textured material needs explicit baseColorFactor: "+item.name);
                if(factor==null)factor=item.baseColor;
                material.SetColor("_BaseColor",SourceLinearBaseColor(factor));
                // Printed paper panels are physically two-sided. Blender previews did
                // not cull their reverse side, unlike the default URP/Lit material.
                material.SetFloat("_Cull",IsPrintedPanel(item.name)||item.name=="Leaves_Green"?(float)CullMode.Off:(float)CullMode.Back);
                material.SetFloat("_Metallic",Mathf.Clamp01(item.metallic));material.SetFloat("_Smoothness",1-Mathf.Clamp01(item.roughness));
                material.SetTexture("_BaseMap",string.IsNullOrEmpty(item.baseColorTexture)?null:Texture(item.baseColorTexture,false));
                material.SetTextureScale("_BaseMap",item.mainTextureScale!=null&&item.mainTextureScale.Length==2?new Vector2(item.mainTextureScale[0],item.mainTextureScale[1]):Vector2.one);
                material.SetTexture("_BumpMap",null);material.DisableKeyword("_NORMALMAP");
                if(!string.IsNullOrEmpty(item.normalTexture)){material.SetTexture("_BumpMap",Texture(item.normalTexture,true));material.EnableKeyword("_NORMALMAP");material.SetFloat("_BumpScale",item.normalStrength);}
                material.SetTexture("_MetallicGlossMap",null);material.DisableKeyword("_METALLICSPECGLOSSMAP");material.SetFloat("_SmoothnessTextureChannel",0);
                if(!string.IsNullOrEmpty(item.roughnessTexture))
                {material.SetTexture("_MetallicGlossMap",PackRoughness(item));material.SetFloat("_Smoothness",1);material.EnableKeyword("_METALLICSPECGLOSSMAP");}
                material.SetFloat("_Surface",0);material.SetFloat("_SrcBlend",(float)BlendMode.One);material.SetFloat("_DstBlend",(float)BlendMode.Zero);material.SetFloat("_ZWrite",1);material.DisableKeyword("_SURFACE_TYPE_TRANSPARENT");material.renderQueue=(int)RenderQueue.Geometry;
                if(item.transmission>0){material.SetFloat("_Surface",1);material.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);material.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);material.SetFloat("_ZWrite",0);material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");material.renderQueue=(int)RenderQueue.Transparent;}
                material.DisableKeyword("_EMISSION");material.SetColor("_EmissionColor",Color.black);material.SetTexture("_EmissionMap",null);
                if(item.emission>0){var e=item.emissionColor??item.baseColor;material.EnableKeyword("_EMISSION");material.SetColor("_EmissionColor",(new Color(e[0],e[1],e[2])*Mathf.Min(item.emission,2)).gamma);if(!string.IsNullOrEmpty(item.emissionTexture))material.SetTexture("_EmissionMap",Texture(item.emissionTexture,false));}
                EditorUtility.SetDirty(material);importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material),item.name),material);
            }
            importer.SaveAndReimport();
            foreach(string toolFile in Directory.GetFiles(Root,"Tool_*.fbx"))
            {var toolImporter=AssetImporter.GetAtPath(toolFile) as ModelImporter;if(toolImporter==null)throw new InvalidOperationException("Tool model importer missing");toolImporter.globalScale=1;toolImporter.useFileScale=true;toolImporter.importAnimation=false;toolImporter.importCameras=false;toolImporter.importLights=false;toolImporter.addCollider=false;toolImporter.isReadable=true;
                foreach(var item in data.materials)toolImporter.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material),item.name),AssetDatabase.LoadAssetAtPath<Material>(Root+"/Materials/"+item.name+".mat"));toolImporter.SaveAndReimport();}

            var source=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(Lottery.Probe.Editor.ProbeBuild.PipelinePath);
            if(source==null)throw new InvalidOperationException("Prepare Probe pipeline before G3 shop art");
            var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if(pipeline==null){pipeline=UnityEngine.Object.Instantiate(source);AssetDatabase.CreateAsset(pipeline,PipelinePath);}else EditorUtility.CopySerialized(source,pipeline);
            pipeline.name="G3 original shop lighting";pipeline.shadowDistance=12;pipeline.msaaSampleCount=4;pipeline.supportsHDR=false;
            var serialized=new SerializedObject(pipeline);SetBool(serialized,"m_MainLightShadowsSupported",true);SetBool(serialized,"m_SoftShadowsSupported",true);
            SetInt(serialized,"m_MainLightShadowmapResolution",2048);SetInt(serialized,"m_ShadowCascadeCount",2);SetInt(serialized,"m_AdditionalLightsRenderingMode",(int)LightRenderingMode.PerPixel);SetInt(serialized,"m_AdditionalLightsPerObjectLimit",8);SetBool(serialized,"m_AdditionalLightShadowsSupported",true);SetInt(serialized,"m_AdditionalLightsShadowmapResolution",2048);SetBool(serialized,"m_ReflectionProbeBoxProjection",true);serialized.ApplyModifiedPropertiesWithoutUndo();
            GraphicsSettings.defaultRenderPipeline=pipeline;int original=QualitySettings.GetQualityLevel();for(int i=0;i<QualitySettings.names.Length;i++){QualitySettings.SetQualityLevel(i);QualitySettings.renderPipeline=pipeline;}QualitySettings.SetQualityLevel(original);
            EditorUtility.SetDirty(pipeline);AssetDatabase.SaveAssets();
            var loaded=AssetDatabase.LoadAssetAtPath<GameObject>(model);var renderers=loaded.GetComponentsInChildren<Renderer>();
            if(renderers.Length<30||renderers.Any(r=>r.sharedMaterials.Any(m=>m==null||m.shader!=shader)))throw new InvalidOperationException("Shop import has too few authored renderers or unresolved URP materials");
            BuildRuntimePrefab(loaded,"LotteryShop_Runtime",true);
            foreach(string toolFile in Directory.GetFiles(Root,"Tool_*.fbx"))BuildRuntimePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(toolFile),Path.GetFileNameWithoutExtension(toolFile)+"_Runtime",false);
            Debug.Log("G3_SHOP_IMPORT original_authored_meshes="+renderers.Length+" materials="+data.materials.Length+" pipeline="+PipelinePath+" DEVICE_QA_NOT_RUN");
        }
        static void BuildRuntimePrefab(GameObject source,string outputName,bool validateRoom)
        {
            // Merge only static authored room meshes by material. Dynamic tickets,
            // state-bound tools and JSON interaction colliders remain independent.
            string generated=Root+"/Generated";Directory.CreateDirectory(generated);
            var anchors=JsonUtility.FromJson<Lottery.G3.Interaction.G3ShopEnvironment.LayoutData>(File.ReadAllText(Root+"/anchors.json"));
            // Use the importer mapping actually measured in Unity 6000.3:
            // (-BlenderX, BlenderZ, -BlenderY). All authored anchors and collision
            // positions now use that same basis; no reflected prefab parent exists.
            if(anchors.requiresUnityXReflection)throw new InvalidOperationException("Shop manifest still requests the superseded X reflection");
            var instance=UnityEngine.Object.Instantiate(source);
            var mirroredMeshes=new Dictionary<Mesh,Mesh>();
            var root=new GameObject(outputName);var groups=new Dictionary<string,List<CombineInstance>>();var materials=new Dictionary<string,Material>();int transparent=0;
            try
            {
                foreach(string anchorName in validateRoom?new[]{"ScratchTicket","TableSurface","PlayerSpawn"}:new string[0])
                {
                    var declared=anchors.anchors.FirstOrDefault(t=>t.name==anchorName);var marker=instance.GetComponentsInChildren<Transform>().FirstOrDefault(t=>t.name=="Anchor_"+anchorName);
                    if(declared==null||declared.position==null||declared.position.Length!=3||marker==null)throw new InvalidOperationException("FBX/JSON anchor missing: "+anchorName);
                    var expected=new Vector3(declared.position[0],declared.position[1],declared.position[2]);
                    if(Vector3.Distance(marker.position,expected)>.015f)throw new InvalidOperationException("FBX metre/axis anchor mismatch "+anchorName+" expected="+expected.ToString("F4")+" actual="+marker.position.ToString("F4"));
                    Debug.Log("G3_SHOP_AXIS anchor="+anchorName+" actual="+marker.position.ToString("F4")+" expected="+expected.ToString("F4")+" reflectedX="+anchors.requiresUnityXReflection);
                }
                foreach(var filter in instance.GetComponentsInChildren<MeshFilter>())
                {
                    var renderer=filter.GetComponent<MeshRenderer>();if(renderer==null||filter.sharedMesh==null)continue;
                    for(int sub=0;sub<filter.sharedMesh.subMeshCount;sub++)
                    {
                        var material=renderer.sharedMaterials[Mathf.Min(sub,renderer.sharedMaterials.Length-1)];
                        string key=material.name+(material.renderQueue>=(int)RenderQueue.Transparent?"_glass_"+(transparent++):"");
                        if(!groups.ContainsKey(key)){groups[key]=new List<CombineInstance>();materials[key]=material;}
                        var matrix=filter.transform.localToWorldMatrix;var mesh=filter.sharedMesh;
                        if(matrix.determinant<0)
                        {
                            // CombineMeshes bakes a reflection into vertices/normals;
                            // it does not fix triangle orientation or tangent handedness.
                            if(!mirroredMeshes.TryGetValue(mesh,out var fixedMesh))
                            {
                                fixedMesh=UnityEngine.Object.Instantiate(mesh);
                                for(int sm=0;sm<fixedMesh.subMeshCount;sm++){var triangles=fixedMesh.GetTriangles(sm);for(int t=0;t<triangles.Length;t+=3){int tmp=triangles[t+1];triangles[t+1]=triangles[t+2];triangles[t+2]=tmp;}fixedMesh.SetTriangles(triangles,sm,false);}
                                var tangents=fixedMesh.tangents;for(int t=0;t<tangents.Length;t++)tangents[t].w=-tangents[t].w;fixedMesh.tangents=tangents;mirroredMeshes.Add(mesh,fixedMesh);
                            }
                            mesh=fixedMesh;
                        }
                        // Printed UVs retain their authored tile and direction.
                        // Native room coordinates no longer need a second U mirror.
                        groups[key].Add(new CombineInstance{mesh=mesh,subMeshIndex=sub,transform=matrix});
                    }
                }
                foreach(var pair in groups)
                {
                    string path=generated+"/"+outputName+"_"+pair.Key+".asset";var mesh=AssetDatabase.LoadAssetAtPath<Mesh>(path);if(mesh==null){mesh=new Mesh();AssetDatabase.CreateAsset(mesh,path);}else mesh.Clear();
                    mesh.name="Static shop "+pair.Key;mesh.indexFormat=IndexFormat.UInt32;mesh.CombineMeshes(pair.Value.ToArray(),true,true);AlignWindingWithAuthoredNormals(mesh);mesh.RecalculateBounds();mesh.RecalculateTangents();EditorUtility.SetDirty(mesh);
                    var go=new GameObject(pair.Key);go.transform.SetParent(root.transform,false);go.AddComponent<MeshFilter>().sharedMesh=mesh;var renderer=go.AddComponent<MeshRenderer>();renderer.sharedMaterial=materials[pair.Key];renderer.receiveShadows=true;renderer.shadowCastingMode=materials[pair.Key].renderQueue>=(int)RenderQueue.Transparent?ShadowCastingMode.Off:ShadowCastingMode.On;
                }
                PrefabUtility.SaveAsPrefabAsset(root,Root+"/"+outputName+".prefab");AssetDatabase.SaveAssets();
                Debug.Log("G3_SHOP_STATIC_BATCH opaque-by-material plus separate glass renderers="+groups.Count+"; performance on device remains NOT_RUN");
            }
            finally{foreach(var mesh in mirroredMeshes.Values)UnityEngine.Object.DestroyImmediate(mesh);UnityEngine.Object.DestroyImmediate(instance);UnityEngine.Object.DestroyImmediate(root);}
        }
        static Color SourceLinearBaseColor(float[] values)
        {
            // The manifest exporter reads Blender Principled socket values, which
            // are scene-linear. The frozen project is Gamma; Material.SetColor stores
            // an ordinary URP _BaseColor without conversion in this workflow.
            // Do not transform PNGs or apply a second conversion to white factors.
            var linear=new Color(values[0],values[1],values[2],values.Length>3?values[3]:1);
            return PlayerSettings.colorSpace==ColorSpace.Gamma?linear.gamma:linear;
        }
        static bool IsPrintedPanel(string name)=>name=="Newspaper"||name=="ShopSign"||name=="ResultsBoard"||name=="Poster_Fortune"||name=="ServiceNotice"||name=="Decoration_Print_Atlas"||name.StartsWith("Ticket_Swap_")||name.StartsWith("CounterToolTag_");
        static void AlignWindingWithAuthoredNormals(Mesh mesh)
        {
            // FBX handedness and CombineMeshes must leave the geometric face and
            // its imported shading normals facing the same way. Validate the final
            // baked mesh rather than assuming how negative matrices are handled.
            var vertices=mesh.vertices;var normals=mesh.normals;
            if(normals.Length!=vertices.Length)throw new InvalidOperationException("Authored shop mesh lost normals");
            var triangles=mesh.triangles;int corrected=0;
            for(int i=0;i<triangles.Length;i+=3)
            {
                int a=triangles[i],b=triangles[i+1],c=triangles[i+2];
                var face=Vector3.Cross(vertices[b]-vertices[a],vertices[c]-vertices[a]);
                if(Vector3.Dot(face,normals[a]+normals[b]+normals[c]) < -0.0000000001f)
                {triangles[i+1]=c;triangles[i+2]=b;corrected++;}
            }
            if(corrected>0)mesh.triangles=triangles;
            Debug.Log("G3_SHOP_FINAL_WINDING corrected="+corrected+" triangles="+(triangles.Length/3));
        }
        static Texture2D PackRoughness(MaterialEntry item)
        {
            // The source grey map is linear roughness. URP Lit expects smoothness in
            // metallic-map alpha; copying the grey texture directly would invert PBR.
            string path=Root+"/Textures/"+Path.GetFileName(item.roughnessTexture);
            var importer=AssetImporter.GetAtPath(path) as TextureImporter;if(importer==null)throw new InvalidOperationException("Missing roughness texture "+path);
            importer.textureType=TextureImporterType.Default;importer.sRGBTexture=false;importer.isReadable=true;importer.textureCompression=TextureImporterCompression.Uncompressed;importer.maxTextureSize=2048;importer.SaveAndReimport();
            var source=AssetDatabase.LoadAssetAtPath<Texture2D>(path);var pixels=source.GetPixels32();byte metal=(byte)Mathf.RoundToInt(Mathf.Clamp01(item.metallic)*255);
            for(int i=0;i<pixels.Length;i++)pixels[i]=new Color32(metal,0,0,(byte)(255-pixels[i].r));
            string packedPath=Root+"/Materials/"+item.name+"_MetallicSmoothness.asset";var packed=AssetDatabase.LoadAssetAtPath<Texture2D>(packedPath);
            if(packed==null){packed=new Texture2D(source.width,source.height,TextureFormat.RGBA32,true,true);AssetDatabase.CreateAsset(packed,packedPath);}else packed.Reinitialize(source.width,source.height,TextureFormat.RGBA32,true);
            packed.name=item.name+" linear metallic and inverted roughness";packed.wrapMode=TextureWrapMode.Repeat;packed.filterMode=FilterMode.Trilinear;packed.SetPixels32(pixels);packed.Apply(true,false);EditorUtility.SetDirty(packed);
            importer.isReadable=false;importer.SaveAndReimport();return packed;
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
