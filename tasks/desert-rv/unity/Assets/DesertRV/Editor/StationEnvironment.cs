using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
namespace DesertRV.Editor {
public static class StationEnvironment {
    [Serializable] class Entry {public string name;public float[] color;public float roughness;public float metallic;}
    [Serializable] class Entries {public Entry[] entries;}
    const string Art="Assets/DesertRV/Art/";
    static void Surface(Material m,string tile,bool colour){
        m.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"Textures/polish-"+tile+"-albedo.png"));
        if(colour)m.SetColor("_BaseColor",Color.white);
        m.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"Textures/polish-"+tile+"-height.png"));
        m.EnableKeyword("_NORMALMAP");m.SetFloat("_BumpScale",tile=="sand"?.055f:tile=="wood"?.022f:tile=="metal"?.07f:.16f);
    }
    public static void Create(GameObject body,BodyViewer viewer){
        foreach(var tile in new[]{"sand","concrete","wood","asphalt","stucco","rock","metal"}){
            var importer=AssetImporter.GetAtPath(Art+"Textures/polish-"+tile+"-height.png") as TextureImporter;
            importer.textureType=TextureImporterType.NormalMap;importer.convertToNormalmap=true;importer.heightmapScale=.045f;importer.sRGBTexture=false;importer.SaveAndReimport();
        }
        var stationImporter=AssetImporter.GetAtPath(Art+"station-polish.fbx") as ModelImporter;
        stationImporter.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
        stationImporter.importLights=false;stationImporter.importCameras=false;stationImporter.importAnimation=false;stationImporter.SaveAndReimport();
        var station=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Art+"station-polish.fbx"));station.name="Station visual candidate";
        var mats=new Dictionary<string,Material>();
        foreach(var e in JsonUtility.FromJson<Entries>(File.ReadAllText(Art+"polish-station-material-values.json")).entries){
            var m=new Material(Shader.Find(e.name=="MAT-desert_sand"?"Universal Render Pipeline/Particles/Simple Lit":"Universal Render Pipeline/Lit"));m.name=e.name;
            m.SetColor("_BaseColor",new Color(e.color[0],e.color[1],e.color[2]).gamma);m.SetFloat("_Metallic",e.metallic);m.SetFloat("_Smoothness",1-e.roughness);
            if(e.name.Contains("desert_leaf"))m.SetFloat("_Cull",0);
            if(e.name=="MAT-desert_sand")Surface(m,"sand",true);
            if(e.name=="MAT-road_asphalt")Surface(m,"asphalt",true);
            if(e.name=="MAT-station_concrete")Surface(m,"concrete",true);
            if(e.name.Contains("wood")||e.name.Contains("plywood"))Surface(m,"wood",false);
            if(e.name.Contains("stucco")||e.name.Contains("roof_patch")||e.name=="MAT-roof_silver")Surface(m,"stucco",false);
            if(e.name.Contains("sandstone"))Surface(m,"rock",false);
            if(e.name.Contains("metal")||e.name.Contains("enamel"))Surface(m,"metal",false);
            if(e.name=="MAT-desert_sand")m.SetColor("_SpecColor",Color.black);
            mats[e.name]=m;
        }
        foreach(var r in station.GetComponentsInChildren<Renderer>()){
            var ms=r.sharedMaterials;for(int i=0;i<ms.Length;i++)if(ms[i]&&mats.TryGetValue(ms[i].name,out var m))ms[i]=m;r.sharedMaterials=ms;
            GameObjectUtility.SetStaticEditorFlags(r.gameObject,StaticEditorFlags.BatchingStatic);
            if(r.name.Contains("sand_drift")||r.name.Contains("floor_oil_stain")||r.name.Contains("road_wheel_track")){
                var dust=new Material(Shader.Find("Universal Render Pipeline/Particles/Simple Lit"));
                dust.SetColor("_BaseColor",r.name.Contains("sand_drift")?Color.white:new Color(.30f,.25f,.19f));
                if(r.name.Contains("sand_drift"))dust.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"Textures/polish-sand-albedo.png"));
                dust.SetFloat("_Surface",1);dust.SetFloat("_ZWrite",0);dust.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);dust.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);
                dust.SetFloat("_SpecularHighlights",0);dust.SetFloat("_Smoothness",0);dust.SetColor("_SpecColor",Color.black);
                dust.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");dust.renderQueue=3000;r.sharedMaterial=dust;r.shadowCastingMode=ShadowCastingMode.Off;
            }
            if(r.name.Contains("garage_workbench_top"))viewer.garageBench=r.transform;
            if(r.name.Contains("garage_lamp_bulb")){
                var lamp=new Material(r.sharedMaterial);lamp.EnableKeyword("_EMISSION");lamp.SetColor("_EmissionColor",new Color(2.4f,1.7f,.8f));r.sharedMaterial=lamp;
                var light=new GameObject("Workbench lamp").AddComponent<Light>();light.type=LightType.Spot;light.transform.position=r.bounds.center-Vector3.up*.05f;
                light.transform.rotation=Quaternion.Euler(90,0,0);light.range=4;light.spotAngle=115;light.innerSpotAngle=70;light.intensity=1.2f;light.color=new Color(1,.82f,.58f);
            }
            if(r.name.Contains("ground")||r.name.Contains("apron")||r.name.Contains("wall")||r.name.Contains("pier")||r.name.Contains("partition")||r.name.Contains("column")||r.name.Contains("workbench_top"))
                r.gameObject.AddComponent<MeshCollider>().sharedMesh=r.GetComponent<MeshFilter>().sharedMesh;
        }
        foreach(var r in body.GetComponentsInChildren<Renderer>())foreach(var m in r.sharedMaterials){
            if(m.name.Contains("wood")||m.name.Contains("plywood")||m.name.Contains("floor_board"))Surface(m,"wood",false);
            else if(m.name.Contains("metal")||m.name.Contains("steel")||m.name.Contains("brass"))Surface(m,"metal",false);
        }
        UnityEngine.Object.DestroyImmediate(GameObject.Find("Neutral inspection floor"));
        var sun=GameObject.Find("Main Light").GetComponent<Light>();sun.transform.rotation=Quaternion.Euler(52,-35,0);sun.color=new Color(1,.91f,.78f);sun.intensity=1.35f;
        sun.shadowBias=.045f;sun.shadowNormalBias=.12f;RenderSettings.sun=sun;
        var sky=new Material(Shader.Find("DesertRV/SoftDesertSky"));
        RenderSettings.skybox=sky;viewer.view.clearFlags=CameraClearFlags.Skybox;
        RenderSettings.ambientMode=AmbientMode.Trilight;
        RenderSettings.ambientSkyColor=new Color(.62f,.72f,.85f);RenderSettings.ambientEquatorColor=new Color(.55f,.51f,.44f);RenderSettings.ambientGroundColor=new Color(.42f,.30f,.20f);
        RenderSettings.fog=true;RenderSettings.fogMode=FogMode.ExponentialSquared;RenderSettings.fogDensity=.0048f;RenderSettings.fogColor=new Color(.75f,.72f,.67f);
        var bounce=new GameObject("Warm cabin reflected light").AddComponent<Light>();bounce.transform.SetParent(body.transform);bounce.transform.localPosition=new Vector3(0,1.97f,-1.3f);bounce.type=LightType.Point;bounce.range=2.5f;bounce.intensity=.32f;bounce.color=new Color(1,.79f,.56f);bounce.shadows=LightShadows.None;
        var renderer=AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/DesertRV/Settings/WebRenderer.asset");
        ScreenSpaceAmbientOcclusion ao=null;foreach(var feature in renderer.rendererFeatures)if(feature is ScreenSpaceAmbientOcclusion existing)ao=existing;
        if(!ao){ao=ScriptableObject.CreateInstance<ScreenSpaceAmbientOcclusion>();ao.name="Contact shading";AssetDatabase.AddObjectToAsset(ao,renderer);renderer.rendererFeatures.Add(ao);}
        var settings=new SerializedObject(ao);var s=settings.FindProperty("m_Settings");
        s.FindPropertyRelative("AOMethod").enumValueIndex=1;s.FindPropertyRelative("Downsample").boolValue=true;
        s.FindPropertyRelative("Intensity").floatValue=.8f;s.FindPropertyRelative("Radius").floatValue=.28f;s.FindPropertyRelative("DirectLightingStrength").floatValue=.15f;
        settings.ApplyModifiedPropertiesWithoutUndo();ao.Create();EditorUtility.SetDirty(renderer);
        var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/DesertRV/Settings/WebURP.asset");
        pipeline.supportsHDR=true;pipeline.shadowCascadeCount=4;pipeline.cascade4Split=new Vector3(.08f,.25f,.55f);EditorUtility.SetDirty(pipeline);
        viewer.view.GetUniversalAdditionalCameraData().renderPostProcessing=true;
        var volume=new GameObject("Exposure response").AddComponent<Volume>();volume.isGlobal=true;volume.sharedProfile=ScriptableObject.CreateInstance<VolumeProfile>();
        volume.sharedProfile.Add<Tonemapping>(true).mode.Override(TonemappingMode.ACES);
        var grade=volume.sharedProfile.Add<ColorAdjustments>(true);grade.contrast.Override(5);grade.saturation.Override(5);
        Debug.Log("STATION_VISUAL_CANDIDATE_PREPARED");
    }
}}
