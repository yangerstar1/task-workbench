using System;
using System.IO;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV.Editor {
public static class BodyBuild {
    [Serializable] class MatEntry {public string name;public float[] color;public float roughness;public float metallic;}
    [Serializable] class MatList {public MatEntry[] entries;}
    // One-time reconstruction only. Normal exports preserve the authored scene.
    public static void Initialize(){
        WebBuild.Prepare();
        foreach(var o in new List<GameObject>(UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects()))
            if(o.name!="Preflight Camera"&&o.name!="Main Light")UnityEngine.Object.DestroyImmediate(o);
        var importer=AssetImporter.GetAtPath("Assets/DesertRV/Art/rv-polish.fbx") as ModelImporter;
        importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
        importer.importCameras=false;importer.importLights=false;importer.importAnimation=false;
        importer.globalScale=1;importer.SaveAndReimport();
        foreach(var stem in new[]{"coach","door"}){
            var aoImporter=AssetImporter.GetAtPath("Assets/DesertRV/Art/Textures/"+stem+"-ao.png") as TextureImporter;
            if(aoImporter!=null){aoImporter.sRGBTexture=false;aoImporter.SaveAndReimport();}
        }
        var prototype=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/DesertRV/Art/rv-polish.fbx");
        var body=UnityEngine.Object.Instantiate(prototype);body.name="RV Body Study";
        var entries=JsonUtility.FromJson<MatList>(File.ReadAllText("Assets/DesertRV/Art/polish-body-material-values.json")).entries;
        var materials=new Dictionary<string,Material>();
        Directory.CreateDirectory("Assets/DesertRV/Art/Materials");
        foreach(var entry in entries){
            var path="Assets/DesertRV/Art/Materials/"+entry.name+".mat";
            var material=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!material){material=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(material,path);}
            // Blender values are scene linear; Unity Color properties accept sRGB authoring values.
            var color=new Color(entry.color[0],entry.color[1],entry.color[2]).gamma;
            material.SetColor("_BaseColor",color);material.SetFloat("_Smoothness",1-entry.roughness);material.SetFloat("_Metallic",entry.metallic);
            materials[entry.name]=material;
        }
        Bounds bounds=new Bounds();bool first=true;
        foreach(var r in body.GetComponentsInChildren<Renderer>()){
            var ms=r.sharedMaterials;
            for(int i=0;i<ms.Length;i++){
                if(ms[i]&&materials.TryGetValue(ms[i].name,out var replacement))ms[i]=replacement;
            }
            r.sharedMaterials=ms;r.shadowCastingMode=ShadowCastingMode.On;r.receiveShadows=true;
            if(r.name=="GEO-coach_body_shell"||r.name=="GEO-entry_door"){
                string stem=r.name=="GEO-entry_door"?"door":"coach";
                var painted=new Material(materials["MAT-enamel_cream"]);
                painted.name=stem+" baked paint";painted.SetColor("_BaseColor",Color.white);
                painted.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/DesertRV/Art/Textures/"+stem+"-albedo.png"));
                painted.SetTexture("_OcclusionMap",AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/DesertRV/Art/Textures/"+stem+"-ao.png"));
                painted.EnableKeyword("_OCCLUSIONMAP");painted.SetFloat("_OcclusionStrength",.65f);
                for(int i=0;i<ms.Length;i++)ms[i]=painted;r.sharedMaterials=ms;
            }
            if(r.name.Contains("window_glass")||r.name=="GEO-windscreen"||r.name=="GEO-entry_door_window"){
                var transparent=new Material(materials["MAT-glass_bluegrey"]);
                transparent.SetColor("_BaseColor",new Color(.32f,.46f,.49f,.23f));
                transparent.SetFloat("_Surface",1);transparent.SetFloat("_ZWrite",0);transparent.SetFloat("_Cull",0);
                transparent.SetFloat("_SrcBlend",(float)BlendMode.SrcAlpha);transparent.SetFloat("_DstBlend",(float)BlendMode.OneMinusSrcAlpha);
                transparent.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");transparent.renderQueue=3000;
                r.sharedMaterial=transparent;r.shadowCastingMode=ShadowCastingMode.Off;
            }
            if(r.name.Contains("under_cabinet_light")){
                var lamp=new Material(r.sharedMaterial);lamp.EnableKeyword("_EMISSION");lamp.SetColor("_EmissionColor",new Color(1.8f,1.2f,.57f));r.sharedMaterial=lamp;
                var warm=new GameObject("Cabinet warm light").AddComponent<Light>();warm.transform.SetParent(body.transform);
                warm.transform.position=r.bounds.center-Vector3.up*.035f;warm.type=LightType.Spot;warm.transform.rotation=Quaternion.Euler(90,0,0);warm.spotAngle=145;warm.innerSpotAngle=90;warm.range=2.1f;warm.intensity=.45f;warm.color=new Color(1,.79f,.55f);
            }
            if(r.name=="GEO-coach_body_shell"||r.name=="GEO-entry_door"||r.name.Contains("interior_floor")||r.name.Contains("entry_step")||r.name.Contains("workbench_frame")||r.name.Contains("supply_cabinet")||r.name.Contains("rear_repair_bench")||r.name.Contains("cab_seat")||r.name.Contains("cab_dashboard"))
                r.gameObject.AddComponent<MeshCollider>().sharedMesh=r.GetComponent<MeshFilter>().sharedMesh;
            if(first){bounds=r.bounds;first=false;}else bounds.Encapsulate(r.bounds);
        }
        foreach(var r in body.GetComponentsInChildren<Renderer>())
            if(r.name=="GEO-entry_door"){
                Debug.Log("RV_DOOR_IMPORTED_BOUNDS: "+r.bounds);
                if(Mathf.Abs(r.bounds.center.y-1.65f)>.08f)throw new Exception("FBX door hinge conversion changed the door height: "+r.bounds);
            }
        body.transform.position-=new Vector3(bounds.center.x,bounds.min.y,bounds.center.z);
        var camera=Camera.main;camera.fieldOfView=44;camera.backgroundColor=new Color(.29f,.35f,.38f);
        var light=UnityEngine.Object.FindFirstObjectByType<Light>();light.transform.rotation=Quaternion.Euler(44,-38,0);light.intensity=1.5f;
        light.shadowBias=.02f;light.shadowNormalBias=.16f;
        RenderSettings.ambientSkyColor=new Color(.55f,.61f,.67f);RenderSettings.ambientEquatorColor=new Color(.36f,.39f,.4f);RenderSettings.ambientGroundColor=new Color(.23f,.20f,.17f);
        var floor=GameObject.CreatePrimitive(PrimitiveType.Cube);floor.name="Neutral inspection floor";floor.transform.position=new Vector3(0,-.06f,0);floor.transform.localScale=new Vector3(35,.10f,35);
        var floorMat=AssetDatabase.LoadAssetAtPath<Material>("Assets/DesertRV/Art/Materials/InspectionFloor.mat");
        if(!floorMat){floorMat=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(floorMat,"Assets/DesertRV/Art/Materials/InspectionFloor.mat");}
        floorMat.SetColor("_BaseColor",new Color(.38f,.38f,.35f));floor.GetComponent<Renderer>().sharedMaterial=floorMat;
        var viewer=new GameObject("Body Viewer").AddComponent<BodyViewer>();viewer.body=body.transform;viewer.view=camera;
        viewer.checker=AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/DesertRV/Art/Textures/uv-checker.png");
        StationEnvironment.Create(body,viewer);
        string scenePath="Assets/DesertRV/Scenes/BodyStudy.unity";
        EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(),scenePath);
        AssetDatabase.SaveAssets();
        Debug.Log("RV_BODY_SCENE_INITIALIZED");
    }
    public static void Build(){
        const string scenePath="Assets/DesertRV/Scenes/BodyStudy.unity";
        if(!File.Exists(scenePath))throw new Exception("Saved candidate scene is missing. Initialize it explicitly before building.");
        AssetDatabase.SaveAssets();
        var output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../build/web-preflight"));
        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{scenePath},locationPathName=output,target=BuildTarget.WebGL,options=BuildOptions.None});
        File.WriteAllText(Path.Combine(Path.GetDirectoryName(Application.dataPath),"../body-runtime-report.txt"),$"result={report.summary.result}\nbytes={report.summary.totalSize}\nseconds={report.summary.totalTime.TotalSeconds:F3}\nsource=saved-scene\n");
        if(report.summary.result!=BuildResult.Succeeded)throw new Exception("Candidate Web build failed");
        Debug.Log("RV_BODY_WEB_EXPORTED");
    }
}}
