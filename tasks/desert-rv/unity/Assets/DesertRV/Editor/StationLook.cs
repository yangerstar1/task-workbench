using UnityEditor;
using UnityEditor.SceneManagement;
using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
namespace DesertRV.Editor {
public static class StationLook {
    static Color Hex(string value){ColorUtility.TryParseHtmlString("#"+value,out var color);return color;}
    static void Finish(Material m,string color,float smooth,float metal=0){
        m.SetColor("_BaseColor",Hex(color));m.SetFloat("_Smoothness",smooth);m.SetFloat("_Metallic",metal);
        m.DisableKeyword("_NORMALMAP");m.SetTexture("_BumpMap",null);EditorUtility.SetDirty(m);
    }
    public static void Apply(){
        PreserveAuthoredCollision();
        foreach(var name in new[]{"rv-polish","station-polish","cabin-fittings","ram-module","arc-module"}){
            var importer=(ModelImporter)AssetImporter.GetAtPath("Assets/DesertRV/Art/"+name+".fbx");
            var compression=name=="rv-polish"?ModelImporterMeshCompression.Low:ModelImporterMeshCompression.Medium;
            if(importer.meshCompression!=compression||importer.importAnimation){
                importer.meshCompression=compression;importer.importAnimation=false;importer.importCameras=false;importer.importLights=false;importer.SaveAndReimport();
            }
        }
        InstallFittings();
        var seen=new HashSet<Material>();
        foreach(var renderer in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None)){
            if(renderer.name.StartsWith("GEO-gear_tooth")||renderer.name.StartsWith("GEO-bench_spanner_jaw")){renderer.enabled=false;continue;}
            var filter=renderer.GetComponent<MeshFilter>();
            if(renderer.name=="GEO-sand_ground"&&filter){var colors=filter.sharedMesh.colors;Debug.Log("RV_SAND_SOURCE colors="+colors.Length+" sample="+(colors.Length>0?colors[colors.Length/2].ToString():"none")+" shader="+renderer.sharedMaterial.shader.name);}
            if(renderer.name=="GEO-sand_ground"||renderer.name=="GEO-distant_terrain"){
                const string groundPath="Assets/DesertRV/Art/Materials/LayeredSand.mat";
                var ground=AssetDatabase.LoadAssetAtPath<Material>(groundPath);
                if(!ground){ground=new Material(Shader.Find("DesertRV/LayeredSand"));AssetDatabase.CreateAsset(ground,groundPath);}
                ground.SetColor("_BaseColor",Hex("F5C385"));ground.SetColor("_LowColor",Hex("E3AB70"));EditorUtility.SetDirty(ground);
                const string sandTexturePath="Assets/DesertRV/Art/sand-handpainted-v1.png";
                var sandImporter=(TextureImporter)AssetImporter.GetAtPath(sandTexturePath);
                if(sandImporter&&sandImporter.maxTextureSize!=1024){sandImporter.maxTextureSize=1024;sandImporter.mipmapEnabled=true;sandImporter.wrapMode=TextureWrapMode.Repeat;sandImporter.anisoLevel=4;sandImporter.SaveAndReimport();}
                ground.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(sandTexturePath));
                renderer.sharedMaterial=ground;
            }
            if(filter&&filter.sharedMesh&&renderer.sharedMaterials.Length!=filter.sharedMesh.subMeshCount){
                var materials=new Material[filter.sharedMesh.subMeshCount];var old=renderer.sharedMaterials;
                for(int i=0;i<materials.Length;i++)materials[i]=old[Mathf.Min(i,old.Length-1)];renderer.sharedMaterials=materials;
            }
            if(renderer.name=="GEO-bench_drive_gear"||renderer.name=="GEO-bench_spanner_shaft")renderer.sharedMaterial=AssetDatabase.LoadAssetAtPath<Material>("Assets/DesertRV/Art/Materials/MAT-brushed_metal.mat");
            renderer.lightProbeUsage=LightProbeUsage.BlendProbes;renderer.reflectionProbeUsage=ReflectionProbeUsage.BlendProbes;
            foreach(var material in renderer.sharedMaterials){
                if(!material||!seen.Add(material))continue;var name=material.name;
                if(name.Contains("ceiling_linen")){Finish(material,"D5C2A0",.12f);material.SetTexture("_BaseMap",null);}
                else if(name.Contains("interior_plywood")){Finish(material,"B6834F",.30f);material.SetTextureScale("_BaseMap",new Vector2(.5f,.75f));}
                else if(name.Contains("wood_cut_edges"))Finish(material,"B99869",.24f);
                else if(name.Contains("floor_board")){Finish(material,"B78754",.24f);material.SetTextureScale("_BaseMap",new Vector2(.45f,.6f));}
                else if(name.Contains("cabinet_recess"))Finish(material,"775535",.18f);
                else if(name.Contains("tyre_rubber"))Finish(material,"303334",.14f);
                else if(name.Contains("rubber_seals"))Finish(material,"373E40",.21f);
                else if(name.Contains("brushed_metal"))Finish(material,"B4BCC0",.39f,1);
                else if(name.Contains("worn_brass"))Finish(material,"C7AA69",.32f,1);
                else if(name.Contains("painted_steel"))Finish(material,"536267",.34f);
                else if(name.Contains("workshop_teal"))Finish(material,"487F76",.3f);
                else if(name.Contains("enamel_burnt_orange"))Finish(material,"C67744",.32f);
                else if(name.Contains("baked paint")){material.SetColor("_BaseColor",new Color(1.18f,1.15f,1.08f));material.SetFloat("_Smoothness",.43f);material.SetFloat("_Metallic",0);material.SetFloat("_OcclusionStrength",.5f);}
                else if(name.Contains("station_concrete")){Finish(material,"FFF4E4",.12f);material.SetTextureScale("_BaseMap",new Vector2(.28f,.28f));}
                else if(name.Contains("station_stucco")){Finish(material,"DBC19B",.08f);material.SetTextureScale("_BaseMap",new Vector2(.35f,.35f));}
                else if(name.Contains("roof_silver")||name.Contains("roof_patch")){Finish(material,"B6A98F",.1f);material.SetTextureScale("_BaseMap",new Vector2(.3f,.3f));}
                else if(name.Contains("sandstone")){Finish(material,"B76D4E",.06f);material.SetTexture("_BaseMap",null);}
                else if(name.Contains("road_asphalt")){Finish(material,"FFFFFF",.1f);material.SetTextureScale("_BaseMap",new Vector2(.25f,.25f));}
                else if(name.Contains("desert_sand")){Finish(material,"FFFFFF",.02f);material.SetTexture("_BaseMap",null);}
                if(material.HasProperty("_Surface")&&material.GetFloat("_Surface")==1&&name.Contains("glass")){material.SetColor("_BaseColor",new Color(.72f,.82f,.85f,.09f));material.SetFloat("_Metallic",0);material.SetFloat("_Smoothness",.63f);}
                EditorUtility.SetDirty(material);
            }
        }
        var sun=RenderSettings.sun;sun.color=Hex("FFE0B4");sun.intensity=1.3f;sun.transform.rotation=Quaternion.Euler(41,-48,0);
        sun.shadows=LightShadows.Soft;sun.shadowBias=.015f;sun.shadowNormalBias=.07f;sun.lightmapBakeType=LightmapBakeType.Mixed;
        RenderSettings.ambientMode=AmbientMode.Trilight;
        RenderSettings.ambientSkyColor=Hex("99B5D8");RenderSettings.ambientEquatorColor=Hex("938879");RenderSettings.ambientGroundColor=Hex("675341");
        RenderSettings.fogColor=Hex("C4B1A1");RenderSettings.fogDensity=.0035f;
        RenderSettings.reflectionIntensity=.65f;
        if(RenderSettings.skybox){RenderSettings.skybox.SetColor("_Zenith",Hex("7895B2"));RenderSettings.skybox.SetColor("_Horizon",Hex("C4CED0"));RenderSettings.skybox.SetColor("_CloudLight",Hex("E3E6E2"));RenderSettings.skybox.SetColor("_CloudShade",Hex("B4BCC3"));EditorUtility.SetDirty(RenderSettings.skybox);}
        foreach(var lamp in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None)){
            if(lamp==sun)continue;lamp.color=Hex("FFD19A");
            if(lamp.name=="Cabinet warm light"){lamp.intensity=.24f;lamp.range=1.8f;lamp.spotAngle=125;lamp.innerSpotAngle=80;}
            else if(lamp.name=="Warm cabin reflected light"){lamp.intensity=.38f;lamp.range=2.6f;lamp.transform.localPosition=new Vector3(0,2.25f,-.2f);}
            else if(lamp.name=="Workbench lamp"){lamp.intensity=1.6f;lamp.lightmapBakeType=LightmapBakeType.Mixed;}
            EditorUtility.SetDirty(lamp);
        }
        foreach(var volume in UnityEngine.Object.FindObjectsByType<Volume>(FindObjectsSortMode.None)){
            if(volume.sharedProfile.TryGet<ColorAdjustments>(out var grade)){grade.contrast.Override(3);grade.saturation.Override(4);grade.postExposure.Override(0);}
            EditorUtility.SetDirty(volume.sharedProfile);
        }
        var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/DesertRV/Settings/WebURP.asset");
        pipeline.msaaSampleCount=4;pipeline.shadowDistance=70;pipeline.mainLightShadowmapResolution=2048;EditorUtility.SetDirty(pipeline);
        SetUpBake();
        var body=UnityEngine.Object.FindFirstObjectByType<BodyViewer>().body;
        var cabin=body.GetComponent<CabinLighting>();if(!cabin)cabin=body.gameObject.AddComponent<CabinLighting>();cabin.fixtureBounce=Hex("80664D");cabin.Collect();cabin.Refresh();
        AssetDatabase.SaveAssets();EditorSceneManager.SaveOpenScenes();
        Debug.Log("RV_AUTHORED_LOOK_APPLIED");
    }
    static void PreserveAuthoredCollision(){
        const string marker="Assets/DesertRV/Art/CollisionMeshes";
        // Render quantization must not change stair heights or narrow door gaps.
        // Keep only vertices/indices from the original authored collision surfaces.
        if(Directory.Exists(marker))return;
        foreach(var name in new[]{"rv-polish","station-polish"}){
            var importer=(ModelImporter)AssetImporter.GetAtPath("Assets/DesertRV/Art/"+name+".fbx");
            if(importer.meshCompression!=ModelImporterMeshCompression.Off){importer.meshCompression=ModelImporterMeshCompression.Off;importer.SaveAndReimport();}
        }
        Directory.CreateDirectory(marker);AssetDatabase.Refresh();
        foreach(var collider in UnityEngine.Object.FindObjectsByType<MeshCollider>(FindObjectsSortMode.None)){
            var source=collider.sharedMesh;if(!source)continue;
            var path=AssetDatabase.GetAssetPath(source);if(!path.EndsWith("rv-polish.fbx")&&!path.EndsWith("station-polish.fbx"))continue;
            var mesh=new Mesh{name=collider.name+" collision",indexFormat=source.indexFormat};
            mesh.vertices=source.vertices;mesh.triangles=source.triangles;mesh.RecalculateBounds();
            AssetDatabase.CreateAsset(mesh,AssetDatabase.GenerateUniqueAssetPath(marker+"/"+collider.name+".asset"));collider.sharedMesh=mesh;
        }
        AssetDatabase.SaveAssets();
    }
    static GameObject ImportFitting(string file,string name,Transform body){
        var existing=body.Find(name);if(existing)return existing.gameObject;
        var prototype=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/DesertRV/Art/"+file+".fbx");if(!prototype)return null;
        var go=(GameObject)PrefabUtility.InstantiatePrefab(prototype);go.name=name;
        go.transform.position+=body.position;go.transform.SetParent(body,true);
        foreach(var r in go.GetComponentsInChildren<Renderer>()){
            var slots=r.sharedMaterials;
            for(int i=0;i<slots.Length;i++){
                string n=slots[i].name;string path="Assets/DesertRV/Art/Materials/"+n+".mat";
                var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(!material){material=new Material(Shader.Find("Universal Render Pipeline/Lit"));material.name=n;AssetDatabase.CreateAsset(material,path);
                    if(n.Contains("cabin_ivory"))Finish(material,"DABF8F",.24f);
                    else if(n.Contains("cabin_honey"))Finish(material,"A27247",.24f);
                    else if(n.Contains("diffuser")){Finish(material,"FFE8C0",.3f);material.EnableKeyword("_EMISSION");material.SetColor("_EmissionColor",new Color(1.3f,.95f,.55f));}
                    else if(n.Contains("steel"))Finish(material,"8C9AA1",.38f,1);
                    else if(n.Contains("oxide"))Finish(material,"CE804E",.38f);
                    else if(n.Contains("copper"))Finish(material,"DCAB79",.36f,1);
                    else if(n.Contains("ceramic"))Finish(material,"BBD0BD",.32f);
                    else if(n.Contains("teal"))Finish(material,"3B776E",.35f);
                    else if(n.Contains("indicator")){Finish(material,"68C7D0",.4f);material.EnableKeyword("_EMISSION");material.SetColor("_EmissionColor",new Color(.05f,.32f,.38f));}
                    else Finish(material,"323E40",.16f);
                }
                slots[i]=material;
            }
            r.sharedMaterials=slots;
        }
        return go;
    }
    static void InstallFittings(){
        var viewer=UnityEngine.Object.FindFirstObjectByType<BodyViewer>();var body=viewer.body;
        ImportFitting("cabin-fittings","Cabin fitted details",body);
        viewer.ramModule=ImportFitting("ram-module","Fitted ram",body);
        viewer.arcModule=ImportFitting("arc-module","Fitted arc",body);
        foreach(var t in body.GetComponentsInChildren<Transform>(true))if(t.name=="MODULE_roof_cargo")viewer.roofCargo=t.gameObject;
        foreach(var fitting in new[]{viewer.ramModule,viewer.arcModule})if(fitting){
            var bounds=new Bounds();bool first=true;
            foreach(var r in fitting.GetComponentsInChildren<Renderer>(true)){if(first){bounds=r.bounds;first=false;}else bounds.Encapsulate(r.bounds);}
            if(bounds.size.magnitude>4)throw new Exception("Fitting scale mismatch: "+fitting.name+" "+bounds);
            Debug.Log("RV_FITTED_BOUNDS "+fitting.name+" "+bounds);
        }
        viewer.ReviewModule("none");EditorUtility.SetDirty(viewer);
    }
    static void SetUpBake(){
        var station=GameObject.Find("Station visual candidate");
        var importer=AssetImporter.GetAtPath("Assets/DesertRV/Art/station-polish.fbx") as ModelImporter;
        if(!importer.generateSecondaryUV){importer.generateSecondaryUV=true;importer.SaveAndReimport();}
        foreach(var r in station.GetComponentsInChildren<MeshRenderer>()){
            var n=r.name;bool structure=n.Contains("wall")||n.Contains("roof_slab")||n.Contains("canopy")||n.Contains("pier")||n.Contains("partition")||n.Contains("column")||n.Contains("apron")||n.Contains("ground")||n.Contains("workbench");
            GameObjectUtility.SetStaticEditorFlags(r.gameObject,StaticEditorFlags.BatchingStatic|(structure?StaticEditorFlags.ContributeGI:0));
            r.receiveGI=structure?ReceiveGI.Lightmaps:ReceiveGI.LightProbes;
            r.scaleInLightmap=n.Contains("ground")?.10f:n.Contains("apron")?.75f:1;
        }
        var settings=AssetDatabase.LoadAssetAtPath<LightingSettings>("Assets/DesertRV/Settings/StationLighting.lighting");
        if(!settings){settings=new LightingSettings();AssetDatabase.CreateAsset(settings,"Assets/DesertRV/Settings/StationLighting.lighting");}
        settings.bakedGI=true;settings.realtimeGI=false;settings.lightmapper=LightingSettings.Lightmapper.ProgressiveCPU;
        settings.lightmapResolution=8;settings.lightmapMaxSize=1024;settings.directSampleCount=32;settings.indirectSampleCount=128;settings.environmentSampleCount=64;
        settings.maxBounces=3;settings.mixedBakeMode=MixedLightingMode.Shadowmask;settings.ao=true;settings.aoMaxDistance=.65f;
        settings.aoExponentIndirect=.6f;settings.aoExponentDirect=0;Lightmapping.lightingSettings=settings;EditorUtility.SetDirty(settings);
        var probeObject=GameObject.Find("Station bounce samples")??new GameObject("Station bounce samples");
        var probes=probeObject.GetComponent<LightProbeGroup>();if(!probes)probes=probeObject.AddComponent<LightProbeGroup>();
        var points=new List<Vector3>();
        for(int x=-15;x<=24;x+=5)for(int z=-16;z<=16;z+=5)foreach(float y in new[]{.3f,1.7f,3.5f})points.Add(new Vector3(x,y,z));
        probes.probePositions=points.ToArray();
        var reflectionObject=GameObject.Find("Station environment reflection")??new GameObject("Station environment reflection");
        var reflection=reflectionObject.GetComponent<ReflectionProbe>();if(!reflection)reflection=reflectionObject.AddComponent<ReflectionProbe>();
        reflectionObject.transform.position=new Vector3(0,2,0);reflection.size=new Vector3(55,12,55);reflection.resolution=128;
        reflection.mode=ReflectionProbeMode.Baked;reflection.intensity=.65f;reflection.cullingMask=~0;reflection.clearFlags=ReflectionProbeClearFlags.Skybox;
    }
    public static void Bake(){
        if(!Lightmapping.Bake())throw new Exception("Lighting bake failed");
        AssetDatabase.SaveAssets();EditorSceneManager.SaveOpenScenes();
        Debug.Log("RV_STATION_LIGHTING_BAKED: lightmaps="+LightmapSettings.lightmaps.Length+" probes="+(LightmapSettings.lightProbes?LightmapSettings.lightProbes.count:0));
    }
}}
