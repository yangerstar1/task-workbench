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
            var trace=MaterialTrace.Create();
            try {PrepareObserved(trace);trace?.Complete();}
            catch(Exception error){trace?.Failure(error);throw;}
            finally{trace?.Finish();}
        }
        static void PrepareObserved(MaterialTrace trace)
        {
            trace?.Mark(1);
            string model=Root+"/LotteryShop_Interior.fbx",json=Root+"/materials.json";
            if(!File.Exists(model)||!File.Exists(json)||!File.Exists(Root+"/anchors.json"))throw new InvalidOperationException("Original shop FBX and manifests are required for this candidate");
            AssetDatabase.Refresh();Directory.CreateDirectory(Root+"/Materials");
            var data=JsonUtility.FromJson<Materials>(File.ReadAllText(json));
            if(data?.materials==null||data.materials.Length<5)throw new InvalidOperationException("Shop material manifest is incomplete");
            trace?.Mark(2);
            var shader=Shader.Find("Universal Render Pipeline/Lit");if(shader==null)throw new InvalidOperationException("URP/Lit is required");
            var owned=new Dictionary<string,OwnedMaterialState>(StringComparer.Ordinal);
            foreach(var item in data.materials)
            {
                trace?.BeginMaterial(item.name);
                if(string.IsNullOrEmpty(item.name)||item.baseColor==null||item.baseColor.Length<3)throw new InvalidOperationException("Invalid material entry");
                string path=Root+"/Materials/"+item.name+".mat";var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(material==null){material=new Material(shader);AssetDatabase.CreateAsset(material,path);}else material.shader=shader;
                // Finish URP's .mat creation/version postprocessor before authoring
                // final parameters. Materials absent from FBX slots need this too.
                // Test-suite URP upgrade callbacks do not save their dirty assets.
                EditorUtility.SetDirty(material);AssetDatabase.SaveAssetIfDirty(material);
                AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
                material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(material==null||material.shader!=shader)throw new InvalidOperationException("Owned material initialization failed");
                trace?.Mark(11);
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
                trace?.Mark(12);FinalizeAuthoredMaterial(material,item,shader,trace);trace?.Mark(23);
                EditorUtility.SetDirty(material);AssetDatabase.SaveAssetIfDirty(material);
                owned.Add(item.name,new OwnedMaterialState(material,item.name));trace?.MaterialDone();
            }
            // Texture imports can reimport their dependent FBX. Do not keep a
            // ModelImporter or unsaved remaps alive across those imports. Bind all
            // final external materials together, after all dependencies are ready.
            RequireOwnedMaterials(owned,trace,35);
            trace?.Mark(30);RemapModel(model,true,owned);
            RequireOwnedMaterials(owned,trace,36);RequireModelBindings(model,owned,trace,36);
            trace?.Mark(31);foreach(string toolFile in Directory.GetFiles(Root,"Tool_*.fbx").OrderBy(x=>x,StringComparer.Ordinal))
            {RemapModel(toolFile,false,owned);RequireOwnedMaterials(owned,trace,37);RequireModelBindings(toolFile,owned,trace,37);}

            trace?.Mark(32);var source=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(Lottery.Probe.Editor.ProbeBuild.PipelinePath);
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
            trace?.Mark(33);BuildRuntimePrefab(loaded,"LotteryShop_Runtime",true,owned,trace);
            foreach(string toolFile in Directory.GetFiles(Root,"Tool_*.fbx"))BuildRuntimePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(toolFile),Path.GetFileNameWithoutExtension(toolFile)+"_Runtime",false,owned,trace);
            trace?.Mark(34);
            // This is still importer preparation, before Baker's first digest.
            // Never accept a dirty authored material as a stable source baseline.
            AssetDatabase.SaveAssets();
            foreach(var item in data.materials)
            {
                string path=Root+"/Materials/"+item.name+".mat";
                var assets=AssetDatabase.LoadAllAssetsAtPath(path);
                if(assets.Length==0||assets.Any(asset=>EditorUtility.IsDirty(asset)))
                    throw new InvalidOperationException("Owned material preparation remains dirty");
            }
            RequireOwnedMaterials(owned,trace,39);
            Debug.Log("G3_SHOP_IMPORT original_authored_meshes="+renderers.Length+" materials="+data.materials.Length+" pipeline="+PipelinePath+" DEVICE_QA_NOT_RUN");
        }
        enum MaterialPredicate { NONE=0,AUTHOR_SHADER=1,AUTHOR_BASE_COLOR=2,AUTHOR_BASE_MAP=3,AUTHOR_NORMAL_MAP=4,AUTHOR_PACKED_MAP=5,AUTHOR_EMISSION_MAP=6,AUTHOR_METALLIC=7,AUTHOR_SMOOTHNESS=8,AUTHOR_SMOOTHNESS_CHANNEL=9,AUTHOR_NORMAL_STRENGTH=10,AUTHOR_BASE_SCALE=11,AUTHOR_SURFACE=12,AUTHOR_EMISSION_COLOR=13,AUTHOR_CULL=14,DETAIL_ALBEDO_ABSENT=15,DETAIL_NORMAL_ABSENT=16,DETAIL_MULX2_OFF=17,DETAIL_SCALED_OFF=18,FINAL_SHADER=19,FINAL_BASE_COLOR=20,FINAL_EMISSION_COLOR=21,FINAL_TEXTURE_REFERENCE=22,FINAL_TEXTURE_SCALE=23,FINAL_TEXTURE_OFFSET=24,FINAL_FLOAT_PRESENCE=25,FINAL_FLOAT_VALUE=26,ALIAS_TEXTURE=27,ALIAS_SCALE=28,ALIAS_OFFSET=29,ALIAS_COLOR=30,NORMAL_KEYWORD=31,PACKED_KEYWORD=32,EMISSION_KEYWORD=33,TRANSPARENT_KEYWORD=34,ALPHA_TEST_OFF=35,ALPHA_PREMULTIPLY_OFF=36,ALPHA_MODULATE_OFF=37,ALBEDO_SMOOTHNESS_OFF=38,SOURCE_BLEND=39,DEST_BLEND=40,DEPTH_WRITE=41,RENDER_QUEUE=42,RENDER_TAG=43,GI_FLAGS=44,DOUBLE_SIDED_GI=45,OWNED_MATERIAL_IDENTITY=46,OWNED_MATERIAL_STATE=47 }
        sealed class MaterialContractFailure:InvalidOperationException
        {
            public readonly MaterialPredicate Predicate;public readonly int Slot;
            public MaterialContractFailure(MaterialPredicate predicate,int slot):base("Owned material finalization contract failed"){Predicate=predicate;Slot=slot;}
        }
        [Serializable] sealed class MaterialProgress
        {
            public int schemaVersion=1,stageCode=1,materialId=-1,materialsCompleted,firstFailureStage=-1,firstFailureMaterial=-1,predicateCode,slotIndex=-1;
            public string scope="MATERIAL_INITIALIZATION_DIAGNOSTIC_NOT_TEST_PASS",status="RUNNING",sourceCommit,runId,runAttempt,exceptionKind="NONE";
            public bool diagnosticWriteFailed,smoothnessObserved;public int smoothnessMaterialId=-1;public long actualSmoothnessBits,expectedSmoothnessBits;public long elapsedMs,completedBits;
        }
        sealed class MaterialTrace
        {
            static readonly string[] Names={"Aged_Aluminium","Bone_Laminate","Brass_Worn","Ceramic_Glazed","Charcoal_Metal","CounterToolTag_1","CounterToolTag_2","CounterToolTag_3","Cream_Plaster","Dark_Green_Felt","Decoration_Print_Atlas","Display_Silver_Coating","Glass_Blue_Water","Glass_Clear","Grout","Heritage_Green_Paint","Ink","Leaves_Green","Newspaper","Oxblood_Enamel","Paper_Ivory","Plastic_Cream","Rubber","Service_Monitor","ShopSign","StreetBlur","Ticket_Swap_1","Ticket_Swap_2","Ticket_Type_Label","Warm_Light","Warm_Oak","Warm_Terrazzo","Tool_Dock_Liner","Nearfield_Tea","Plant_Stem_Green"};
            readonly MaterialProgress receipt;readonly string path;
            readonly System.Diagnostics.Stopwatch clock=System.Diagnostics.Stopwatch.StartNew();
            MaterialTrace(string commit,string run,string attempt)
            {receipt=new MaterialProgress{sourceCommit=commit,runId=run,runAttempt=attempt};path=Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/visual-candidate/material-initialization-progress.json"));Write();}
            static string Arg(string[] args,string name,string pattern)
            {int i=Array.IndexOf(args,name);return i>=0&&i+1<args.Length&&System.Text.RegularExpressions.Regex.IsMatch(args[i+1],pattern)?args[i+1]:null;}
            public static MaterialTrace Create()
            {
                var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,"-assemblyNames");if(i<0||i+1>=args.Length||args[i+1]!="Lottery.G3.VisualCandidate.Tests")return null;
                string commit=Arg(args,"-probeCommit","\\A[0-9a-f]{40}\\z"),run=Arg(args,"-probeRunId","\\A[1-9][0-9]{0,19}\\z"),attempt=Arg(args,"-probeRunAttempt","\\A[1-9][0-9]{0,19}\\z");
                return commit==null||run==null||attempt==null?null:new MaterialTrace(commit,run,attempt);
            }
            public void ObserveSmoothness(uint actual,uint expected){receipt.smoothnessObserved=true;receipt.smoothnessMaterialId=receipt.materialId;receipt.actualSmoothnessBits=actual;receipt.expectedSmoothnessBits=expected;Write();}
            public void Mark(int stage){receipt.stageCode=stage;Write();}
            public void BeginMaterial(string name){receipt.materialId=Array.IndexOf(Names,name);if(receipt.materialId<0)receipt.diagnosticWriteFailed=true;Mark(10);}
            public void SelectMaterial(string name,int stage){receipt.materialId=Array.IndexOf(Names,name);Mark(stage);}
            public void MaterialDone(){if(receipt.materialId>=0){if((receipt.completedBits&(1L<<receipt.materialId))!=0||receipt.materialsCompleted>=35)receipt.diagnosticWriteFailed=true;receipt.completedBits|=1L<<receipt.materialId;}receipt.materialsCompleted=Math.Min(receipt.materialsCompleted+1,35);Mark(24);}
            public void Failure(Exception error)
            {
                if(receipt.firstFailureStage>=0)return;receipt.firstFailureStage=receipt.stageCode;receipt.firstFailureMaterial=receipt.materialId;
                var contract=error as MaterialContractFailure;if(contract!=null){receipt.predicateCode=(int)contract.Predicate;receipt.slotIndex=contract.Slot;}
                receipt.exceptionKind=error is InvalidOperationException?"INVALID_OPERATION":error is ArgumentException?"ARGUMENT":error is IOException?"IO":error is UnauthorizedAccessException?"ACCESS":error is UnityException?"UNITY":error is NullReferenceException?"NULL_REFERENCE":error is AggregateException?"AGGREGATE":"OTHER";
                receipt.status="FAILED";Write();
            }
            public void Complete(){receipt.status="COMPLETE";receipt.materialId=-1;Mark(40);}
            public void Finish(){Write();}
            void Write()
            {
                try{receipt.elapsedMs=clock.ElapsedMilliseconds;string json=JsonUtility.ToJson(receipt,false);if(System.Text.Encoding.UTF8.GetByteCount(json)>8192)throw new InvalidOperationException();Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,json,new System.Text.UTF8Encoding(false));}
                catch{receipt.diagnosticWriteFailed=true;}
            }
        }
        // Material native storage is IEEE754 binary32. Compare exact stored bits,
        // not an arithmetic temporary that the CLI may retain at higher precision.
        static uint SingleBits(float value){return BitConverter.ToUInt32(BitConverter.GetBytes(value),0);}
        static bool FiniteSingleBits(uint bits){return (bits&0x7f800000U)!=0x7f800000U;}
        static void RequireSmoothness(Material material,MaterialEntry item,bool packed,MaterialTrace trace)
        {
            uint actual=SingleBits(material.GetFloat("_Smoothness")),expected=SingleBits(packed?1:1-Mathf.Clamp01(item.roughness));
            trace?.ObserveSmoothness(actual,expected);
            RequireMaterial(FiniteSingleBits(actual)&&FiniteSingleBits(expected)&&actual==expected,MaterialPredicate.AUTHOR_SMOOTHNESS,-1);
        }
        static void RequireMaterial(bool valid,MaterialPredicate predicate,int slot)
        {if(!valid)throw new MaterialContractFailure(predicate,slot);}
        static readonly string[] AuthoredTextureSlots={"_BaseMap","_BumpMap","_MetallicGlossMap","_EmissionMap"};
        static readonly string[] AuthoredFloatSlots={"_Cull","_Metallic","_Smoothness","_SmoothnessTextureChannel","_Surface","_BumpScale","_GlossMapScale"};
        static void FinalizeAuthoredMaterial(Material material,MaterialEntry item,Shader shader,MaterialTrace trace)
        {
            trace?.Mark(20);
            // Explicit existing intent: standard alpha, no clipping or queue bias.
            // Derived blend/pass/GI/alias state is then produced by the public URP API.
            material.SetFloat("_Blend",0);material.SetFloat("_BlendModePreserveSpecular",0);
            material.SetFloat("_AlphaClip",0);material.SetFloat("_QueueOffset",0);
            var textures=AuthoredTextureSlots.Select(material.GetTexture).ToArray();
            var scales=AuthoredTextureSlots.Select(material.GetTextureScale).ToArray();
            var offsets=AuthoredTextureSlots.Select(material.GetTextureOffset).ToArray();
            var present=AuthoredFloatSlots.Select(material.HasProperty).ToArray();
            var values=AuthoredFloatSlots.Select((name,index)=>present[index]?material.GetFloat(name):0).ToArray();
            var color=material.GetColor("_BaseColor");var emission=material.GetColor("_EmissionColor");
            bool transparent=item.transmission>0,normal=!string.IsNullOrEmpty(item.normalTexture),packed=!string.IsNullOrEmpty(item.roughnessTexture),emissive=item.emission>0;
            RequireMaterial(material.shader==shader,MaterialPredicate.AUTHOR_SHADER,-1);
            RequireMaterial(color==SourceLinearBaseColor(item.baseColorFactor??item.baseColor),MaterialPredicate.AUTHOR_BASE_COLOR,-1);
            RequireMaterial((textures[0]!=null)==!string.IsNullOrEmpty(item.baseColorTexture),MaterialPredicate.AUTHOR_BASE_MAP,-1);
            RequireMaterial((textures[1]!=null)==normal,MaterialPredicate.AUTHOR_NORMAL_MAP,-1);
            RequireMaterial((textures[2]!=null)==packed,MaterialPredicate.AUTHOR_PACKED_MAP,-1);
            RequireMaterial((textures[3]!=null)==(emissive&&!string.IsNullOrEmpty(item.emissionTexture)),MaterialPredicate.AUTHOR_EMISSION_MAP,-1);
            RequireMaterial(material.GetFloat("_Metallic")==Mathf.Clamp01(item.metallic),MaterialPredicate.AUTHOR_METALLIC,-1);
            RequireSmoothness(material,item,packed,trace);
            RequireMaterial(material.GetFloat("_SmoothnessTextureChannel")==0,MaterialPredicate.AUTHOR_SMOOTHNESS_CHANNEL,-1);
            RequireMaterial(!normal||material.GetFloat("_BumpScale")==item.normalStrength,MaterialPredicate.AUTHOR_NORMAL_STRENGTH,-1);
            var expectedScale=item.mainTextureScale!=null&&item.mainTextureScale.Length==2?new Vector2(item.mainTextureScale[0],item.mainTextureScale[1]):Vector2.one;
            RequireMaterial(scales[0]==expectedScale,MaterialPredicate.AUTHOR_BASE_SCALE,-1);
            RequireMaterial(material.GetFloat("_Surface")== (transparent?1:0),MaterialPredicate.AUTHOR_SURFACE,-1);
            var e=item.emissionColor??item.baseColor;var expectedEmission=emissive?(new Color(e[0],e[1],e[2])*Mathf.Min(item.emission,2)).gamma:Color.black;
            RequireMaterial(emission==expectedEmission,MaterialPredicate.AUTHOR_EMISSION_COLOR,-1);
            RequireMaterial(material.GetFloat("_Cull")== (IsPrintedPanel(item.name)||item.name=="Leaves_Green"?(float)CullMode.Off:(float)CullMode.Back),MaterialPredicate.AUTHOR_CULL,-1);
            // Explicit schema intent: no separate detail layer on owned materials.
            material.SetTexture("_DetailAlbedoMap",null);material.SetTexture("_DetailNormalMap",null);
            material.DisableKeyword("_DETAIL_MULX2");material.DisableKeyword("_DETAIL_SCALED");
            // No authoring in this project uses Lit's separate detail workflow.
            RequireMaterial(material.GetTexture("_DetailAlbedoMap")==null,MaterialPredicate.DETAIL_ALBEDO_ABSENT,-1);
            RequireMaterial(material.GetTexture("_DetailNormalMap")==null,MaterialPredicate.DETAIL_NORMAL_ABSENT,-1);
            RequireMaterial(!material.IsKeywordEnabled("_DETAIL_MULX2"),MaterialPredicate.DETAIL_MULX2_OFF,-1);
            RequireMaterial(!material.IsKeywordEnabled("_DETAIL_SCALED"),MaterialPredicate.DETAIL_SCALED_OFF,-1);
            material.globalIlluminationFlags=emissive?MaterialGlobalIlluminationFlags.BakedEmissive:MaterialGlobalIlluminationFlags.EmissiveIsBlack;
            trace?.Mark(21);UnityEditor.BaseShaderGUI.SetMaterialKeywords(material,UnityEditor.Rendering.Universal.ShaderGUI.LitGUI.SetMaterialKeywords);trace?.Mark(22);
            RequireMaterial(material.shader==shader,MaterialPredicate.FINAL_SHADER,-1);
            RequireMaterial(material.GetColor("_BaseColor")==color,MaterialPredicate.FINAL_BASE_COLOR,-1);
            RequireMaterial(material.GetColor("_EmissionColor")==emission,MaterialPredicate.FINAL_EMISSION_COLOR,-1);
            for(int i=0;i<AuthoredTextureSlots.Length;i++){RequireMaterial(material.GetTexture(AuthoredTextureSlots[i])==textures[i],MaterialPredicate.FINAL_TEXTURE_REFERENCE,i); RequireMaterial(material.GetTextureScale(AuthoredTextureSlots[i])==scales[i],MaterialPredicate.FINAL_TEXTURE_SCALE,i); RequireMaterial(material.GetTextureOffset(AuthoredTextureSlots[i])==offsets[i],MaterialPredicate.FINAL_TEXTURE_OFFSET,i);}
            for(int i=0;i<AuthoredFloatSlots.Length;i++){RequireMaterial(material.HasProperty(AuthoredFloatSlots[i])==present[i],MaterialPredicate.FINAL_FLOAT_PRESENCE,i); RequireMaterial((!present[i]||material.GetFloat(AuthoredFloatSlots[i])==values[i]),MaterialPredicate.FINAL_FLOAT_VALUE,i);}
            RequireMaterial(material.GetTexture("_MainTex")==textures[0],MaterialPredicate.ALIAS_TEXTURE,-1);
            RequireMaterial(material.GetTextureScale("_MainTex")==scales[0],MaterialPredicate.ALIAS_SCALE,-1);
            RequireMaterial(material.GetTextureOffset("_MainTex")==offsets[0],MaterialPredicate.ALIAS_OFFSET,-1);
            RequireMaterial(material.GetColor("_Color")==color,MaterialPredicate.ALIAS_COLOR,-1);
            RequireMaterial(material.IsKeywordEnabled("_NORMALMAP")==normal,MaterialPredicate.NORMAL_KEYWORD,-1);
            RequireMaterial(material.IsKeywordEnabled("_METALLICSPECGLOSSMAP")==packed,MaterialPredicate.PACKED_KEYWORD,-1);
            RequireMaterial(material.IsKeywordEnabled("_EMISSION")==emissive,MaterialPredicate.EMISSION_KEYWORD,-1);
            RequireMaterial(material.IsKeywordEnabled("_SURFACE_TYPE_TRANSPARENT")==transparent,MaterialPredicate.TRANSPARENT_KEYWORD,-1);
            RequireMaterial(!material.IsKeywordEnabled("_ALPHATEST_ON"),MaterialPredicate.ALPHA_TEST_OFF,-1);
            RequireMaterial(!material.IsKeywordEnabled("_ALPHAPREMULTIPLY_ON"),MaterialPredicate.ALPHA_PREMULTIPLY_OFF,-1);
            RequireMaterial(!material.IsKeywordEnabled("_ALPHAMODULATE_ON"),MaterialPredicate.ALPHA_MODULATE_OFF,-1);
            RequireMaterial(!material.IsKeywordEnabled("_SMOOTHNESS_TEXTURE_ALBEDO_CHANNEL_A"),MaterialPredicate.ALBEDO_SMOOTHNESS_OFF,-1);
            RequireMaterial(material.GetFloat("_SrcBlend")== (transparent?(float)BlendMode.SrcAlpha:(float)BlendMode.One),MaterialPredicate.SOURCE_BLEND,-1);
            RequireMaterial(material.GetFloat("_DstBlend")== (transparent?(float)BlendMode.OneMinusSrcAlpha:(float)BlendMode.Zero),MaterialPredicate.DEST_BLEND,-1);
            RequireMaterial(material.GetFloat("_ZWrite")== (transparent?0:1),MaterialPredicate.DEPTH_WRITE,-1);
            RequireMaterial(material.renderQueue== (int)(transparent?RenderQueue.Transparent:RenderQueue.Geometry),MaterialPredicate.RENDER_QUEUE,-1);
            RequireMaterial(material.GetTag("RenderType",false)==(transparent?"Transparent":"Opaque"),MaterialPredicate.RENDER_TAG,-1);
            RequireMaterial(material.globalIlluminationFlags==(emissive?MaterialGlobalIlluminationFlags.BakedEmissive:MaterialGlobalIlluminationFlags.EmissiveIsBlack),MaterialPredicate.GI_FLAGS,-1);
            RequireMaterial(material.doubleSidedGI==(material.GetFloat("_Cull")!=(float)CullMode.Back),MaterialPredicate.DOUBLE_SIDED_GI,-1);
        }
        // Read-only post-import contracts, captured only after the original 45
        // authoring/finalization predicates passed. No repair occurs inside checks.
        sealed class OwnedMaterialState
        {
            static readonly string[] Textures=AuthoredTextureSlots.Concat(new[]{"_MainTex","_DetailAlbedoMap","_DetailNormalMap"}).ToArray();
            static readonly string[] Floats=AuthoredFloatSlots.Concat(new[]{"_Blend","_BlendModePreserveSpecular","_AlphaClip","_QueueOffset","_SrcBlend","_DstBlend","_ZWrite"}).ToArray();
            public readonly Material Material;public readonly string Name,Path,Guid;readonly long localId;
            readonly Shader shader;readonly Texture[] textures;readonly Vector2[] scales,offsets;readonly bool[] present;readonly uint[] floats;
            readonly Color[] colors;readonly string[] keywords;readonly string renderType;readonly int queue;
            readonly MaterialGlobalIlluminationFlags gi;readonly bool doubleSided,instancing;
            public OwnedMaterialState(Material material,string name)
            {
                Material=material;Name=name;Path=Root+"/Materials/"+name+".mat";
                if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material,out string guid,out long id))throw new InvalidOperationException("Owned material identity unavailable");
                Guid=guid;localId=id;shader=material.shader;textures=Textures.Select(material.GetTexture).ToArray();
                scales=Textures.Select(material.GetTextureScale).ToArray();offsets=Textures.Select(material.GetTextureOffset).ToArray();
                present=Floats.Select(material.HasProperty).ToArray();floats=Floats.Select((slot,i)=>present[i]?SingleBits(material.GetFloat(slot)):0).ToArray();
                colors=new[]{material.GetColor("_BaseColor"),material.GetColor("_EmissionColor"),material.GetColor("_Color")};
                keywords=material.shaderKeywords.OrderBy(x=>x,StringComparer.Ordinal).ToArray();renderType=material.GetTag("RenderType",false);
                queue=material.renderQueue;gi=material.globalIlluminationFlags;doubleSided=material.doubleSidedGI;instancing=material.enableInstancing;
            }
            public void RequireIdentity(Material actual)
            {
                RequireMaterial(actual!=null&&actual==Material&&AssetDatabase.LoadAssetAtPath<Material>(Path)==actual&&
                    AssetDatabase.IsMainAsset(actual)&&AssetDatabase.GetAssetPath(actual)==Path&&
                    AssetDatabase.AssetPathToGUID(Path)==Guid&&AssetDatabase.GUIDToAssetPath(Guid)==Path&&
                    AssetDatabase.TryGetGUIDAndLocalFileIdentifier(actual,out string guid,out long id)&&guid==Guid&&id==localId,
                    MaterialPredicate.OWNED_MATERIAL_IDENTITY,-1);
            }
            public void RequireState()
            {
                RequireIdentity(Material);
                RequireMaterial(Material.shader==shader,MaterialPredicate.OWNED_MATERIAL_STATE,0);
                RequireMaterial(Textures.Select(Material.GetTexture).SequenceEqual(textures),MaterialPredicate.OWNED_MATERIAL_STATE,1);
                RequireMaterial(Textures.Select(Material.GetTextureScale).SequenceEqual(scales)&&Textures.Select(Material.GetTextureOffset).SequenceEqual(offsets),MaterialPredicate.OWNED_MATERIAL_STATE,2);
                RequireMaterial(Floats.Select(Material.HasProperty).SequenceEqual(present)&&Floats.Select((name,i)=>present[i]?SingleBits(Material.GetFloat(name)):0).SequenceEqual(floats),MaterialPredicate.OWNED_MATERIAL_STATE,3);
                RequireMaterial(new[]{Material.GetColor("_BaseColor"),Material.GetColor("_EmissionColor"),Material.GetColor("_Color")}.SequenceEqual(colors),MaterialPredicate.OWNED_MATERIAL_STATE,4);
                RequireMaterial(Material.shaderKeywords.OrderBy(x=>x,StringComparer.Ordinal).SequenceEqual(keywords),MaterialPredicate.OWNED_MATERIAL_STATE,5);
                RequireMaterial(Material.renderQueue==queue&&Material.GetTag("RenderType",false)==renderType&&Material.globalIlluminationFlags==gi&&Material.doubleSidedGI==doubleSided&&Material.enableInstancing==instancing,MaterialPredicate.OWNED_MATERIAL_STATE,6);
            }
        }
        static void RequireOwnedMaterials(Dictionary<string,OwnedMaterialState> owned,MaterialTrace trace,int stage)
        {foreach(var state in owned.Values){trace?.SelectMaterial(state.Name,stage);state.RequireState();}}
        static void RemapModel(string path,bool room,Dictionary<string,OwnedMaterialState> owned)
        {
            var importer=AssetImporter.GetAtPath(path) as ModelImporter;if(importer==null)throw new InvalidOperationException("Model importer missing");
            importer.globalScale=1;importer.useFileScale=true;importer.importAnimation=false;importer.importCameras=false;importer.importLights=false;
            importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;importer.addCollider=false;importer.isReadable=true;
            if(room)importer.generateSecondaryUV=true;
            foreach(var state in owned.Values)importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material),state.Name),state.Material);
            importer.SaveAndReimport();
        }
        static void RequireModelBindings(string path,Dictionary<string,OwnedMaterialState> owned,MaterialTrace trace,int stage)
        {
            var importer=AssetImporter.GetAtPath(path) as ModelImporter;if(importer==null)throw new InvalidOperationException("Model importer missing after remap");
            var remaps=importer.GetExternalObjectMap();
            foreach(var state in owned.Values)
            {
                trace?.SelectMaterial(state.Name,stage);
                RequireMaterial(remaps.TryGetValue(new AssetImporter.SourceAssetIdentifier(typeof(Material),state.Name),out var mapped)&&mapped==state.Material,MaterialPredicate.OWNED_MATERIAL_IDENTITY,-1);
                state.RequireIdentity(mapped as Material);
            }
            RequireRendererBindings(AssetDatabase.LoadAssetAtPath<GameObject>(path),owned,trace,stage);
        }
        static void RequireRendererBindings(GameObject source,Dictionary<string,OwnedMaterialState> owned,MaterialTrace trace,int stage)
        {
            if(source==null)throw new InvalidOperationException("Prepared model or runtime prefab missing");
            foreach(var renderer in source.GetComponentsInChildren<Renderer>(true))
                foreach(var material in renderer.sharedMaterials)RequireRendererMaterial(material,owned,trace,stage);
        }
        static void RequireRendererMaterial(Material material,Dictionary<string,OwnedMaterialState> owned,MaterialTrace trace,int stage)
        {
            string name=material==null?"":material.name;trace?.SelectMaterial(name,stage);
            RequireMaterial(material!=null&&owned.ContainsKey(name),MaterialPredicate.OWNED_MATERIAL_IDENTITY,-1);
            owned[name].RequireIdentity(material);
        }
        static void BuildRuntimePrefab(GameObject source,string outputName,bool validateRoom,Dictionary<string,OwnedMaterialState> owned,MaterialTrace trace)
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
                        // Dedicated dark green textile only for the three recessed tool docks.
                        // Other rubber (doormat/feet) remains unchanged; no extra geometry.
                        if(validateRoom&&filter.name.StartsWith("Tool_Dock_Recess",StringComparison.Ordinal))
                            material=AssetDatabase.LoadAssetAtPath<Material>(Root+"/Materials/Tool_Dock_Liner.mat")??throw new InvalidOperationException("Missing dock liner material");
                        RequireRendererMaterial(material,owned,trace,38);
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
                string prefabPath=Root+"/"+outputName+".prefab";
                PrefabUtility.SaveAsPrefabAsset(root,prefabPath);AssetDatabase.SaveAssets();
                RequireOwnedMaterials(owned,trace,38);
                RequireRendererBindings(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath),owned,trace,38);
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
