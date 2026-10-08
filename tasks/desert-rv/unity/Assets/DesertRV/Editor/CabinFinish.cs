using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV.Editor {
public static class CabinFinish {
    [Serializable] class FinishRecord {public string name;public float smoothness;public float metallic;}
    [Serializable] class Report {public string[] replacedNames;public FinishRecord[] exportMaterials;}
    const string Art="Assets/DesertRV/Art/";
    static Color Hex(string s){ColorUtility.TryParseHtmlString("#"+s,out var c);return c;}
    public static void Apply(){
        AssetDatabase.Refresh();
        var report=JsonUtility.FromJson<Report>(File.ReadAllText(Path.GetFullPath(Path.Combine(Application.dataPath,"../../cabin-finish-report.json"))));
        var importer=(ModelImporter)AssetImporter.GetAtPath(Art+"cabin-finished.fbx");
        importer.importAnimation=false;importer.importCameras=false;importer.importLights=false;importer.meshCompression=ModelImporterMeshCompression.Off;importer.SaveAndReimport();
        foreach(var stem in new[]{"cabin-finish-albedo","cabin-finish-ao","cabin-finish-normal"}){
            var ti=(TextureImporter)AssetImporter.GetAtPath(Art+stem+".png");
            ti.textureType=stem.EndsWith("normal")?TextureImporterType.NormalMap:TextureImporterType.Default;
            ti.sRGBTexture=stem.EndsWith("albedo");ti.maxTextureSize=stem.EndsWith("ao")?2048:4096;ti.mipmapEnabled=true;ti.anisoLevel=8;ti.wrapMode=TextureWrapMode.Clamp;
            ti.alphaSource=TextureImporterAlphaSource.None;ti.alphaIsTransparency=false;
            ti.textureCompression=TextureImporterCompression.Uncompressed;ti.compressionQuality=100;
            // The user removed the file-size cap. Preserve fine grain and normal gradients.
            ti.ClearPlatformTextureSettings("WebGL");
            ti.SaveAndReimport();
        }
        var viewer=UnityEngine.Object.FindFirstObjectByType<BodyViewer>();var body=viewer.body;
        // Preserve every original collider and its transform; replace renderers only.
        foreach(var r in body.GetComponentsInChildren<Renderer>(true))if(report.replacedNames.Contains(r.name)||r.name.StartsWith("GEO-cabinet_inset_seam")||r.name.StartsWith("GEO-panel_fastener")||r.name.StartsWith("GEO-service_round_gauge")||r.name.StartsWith("GEO-gauge_needle")||r.name.StartsWith("GEO-power_toggle")){
            r.enabled=false;EditorUtility.SetDirty(r);if(PrefabUtility.IsPartOfPrefabInstance(r))PrefabUtility.RecordPrefabInstancePropertyModifications(r);
        }
        var existing=body.Find("Finished cabin surfaces");
        if(existing)UnityEngine.Object.DestroyImmediate(existing.gameObject);
        var prototype=AssetDatabase.LoadAssetAtPath<GameObject>(Art+"cabin-finished.fbx");
        var go=(GameObject)PrefabUtility.InstantiatePrefab(prototype);PrefabUtility.UnpackPrefabInstance(go,PrefabUnpackMode.Completely,InteractionMode.AutomatedAction);
        go.name="Finished cabin surfaces";go.transform.position+=body.position;go.transform.SetParent(body,true);
        foreach(var r in go.GetComponentsInChildren<Renderer>()){
            var mats=r.sharedMaterials;
            for(int i=0;i<mats.Length;i++){
                var record=report.exportMaterials.First(x=>x.name==mats[i].name);
                string path=Art+"Materials/"+record.name+".mat";
                var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(!material){material=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(material,path);}
                material.SetColor("_BaseColor",Color.white);material.SetTexture("_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"cabin-finish-albedo.png"));
                material.SetTexture("_OcclusionMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"cabin-finish-ao.png"));material.SetFloat("_OcclusionStrength",.72f);material.EnableKeyword("_OCCLUSIONMAP");
                material.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"cabin-finish-normal.png"));material.SetFloat("_BumpScale",.65f);material.EnableKeyword("_NORMALMAP");
                material.SetFloat("_Metallic",record.metallic);material.SetFloat("_Smoothness",record.smoothness);EditorUtility.SetDirty(material);mats[i]=material;
            }
            r.sharedMaterials=mats;r.lightProbeUsage=LightProbeUsage.BlendProbes;r.reflectionProbeUsage=ReflectionProbeUsage.BlendProbes;
        }
        var hardwareOld=body.Find("Cabin precision hardware");if(hardwareOld)UnityEngine.Object.DestroyImmediate(hardwareOld.gameObject);
        var hardwareSource=AssetDatabase.LoadAssetAtPath<GameObject>(Art+"cabin-hardware.fbx");
        if(hardwareSource){
            var hardware=(GameObject)PrefabUtility.InstantiatePrefab(hardwareSource);PrefabUtility.UnpackPrefabInstance(hardware,PrefabUnpackMode.Completely,InteractionMode.AutomatedAction);
            hardware.name="Cabin precision hardware";hardware.transform.position+=body.position;hardware.transform.SetParent(body,true);
            foreach(var r in hardware.GetComponentsInChildren<Renderer>()){
                var mats=r.sharedMaterials;
                for(int i=0;i<mats.Length;i++){
                    var n=mats[i].name;
                    mats[i]=FinishMaterial(n,n.Contains("Steel")?"ADB9B9":n.Contains("Safe")?"579C6B":n.Contains("Paper")?"E2E8D3":"34463F",.38f,n.Contains("Steel")?1:0);
                }
                r.sharedMaterials=mats;
            }
        }
        var bounce=body.GetComponent<CabinLighting>();bounce.fixtureBounce=Hex("766C59");bounce.Collect();bounce.Refresh();
        foreach(var lamp in body.GetComponentsInChildren<Light>()){
            if(lamp.name=="Cabinet warm light"){lamp.intensity=.38f;lamp.color=Hex("FFE2B6");lamp.range=1.45f;}
            if(lamp.name=="Warm cabin reflected light"){lamp.intensity=.55f;lamp.color=Hex("FFE9C6");lamp.range=2.6f;}
            EditorUtility.SetDirty(lamp);
        }
        // Existing fixtures gain visible diffusion, without changing the exterior lights.
        var diffuser=FinishMaterial("CabinFixtureDiffuser","FFF1D0",.22f,0);
        diffuser.globalIlluminationFlags=MaterialGlobalIlluminationFlags.BakedEmissive;diffuser.EnableKeyword("_EMISSION");diffuser.SetColor("_EmissionColor",new Color(2.2f,1.75f,1.10f));EditorUtility.SetDirty(diffuser);
        var fittings=FinishMaterial("CabinBrushedHardware","ABB8BA",.38f,.65f);
        foreach(var r in body.GetComponentsInChildren<Renderer>()){
            if(r.name.Contains("refine_cabin_lamp_diffuser")||r.name.Contains("under_cabinet_light"))r.sharedMaterial=diffuser;
            else if(r.name.Contains("overhead_pull")||r.name.Contains("supply_latch")||r.name.Contains("drawer_pull")||r.name.Contains("vise_jaw")||r.name.Contains("vise_screw")||r.name.Contains("vise_lever")||r.name.Contains("refine_cabin_lamp_mount"))r.sharedMaterial=fittings;
            else continue;
            EditorUtility.SetDirty(r);if(PrefabUtility.IsPartOfPrefabInstance(r))PrefabUtility.RecordPrefabInstancePropertyModifications(r);
        }
        EditorUtility.SetDirty(bounce);EditorSceneManager.MarkSceneDirty(go.scene);
        AssetDatabase.SaveAssets();EditorSceneManager.SaveOpenScenes();
        Debug.Log("RV_CABIN_FINISH_APPLIED surfaces="+report.replacedNames.Length+" materialGroups="+report.exportMaterials.Length);
    }
    static Material FinishMaterial(string name,string color,float smooth,float metal){
        var path=Art+"Materials/"+name+".mat";var m=AssetDatabase.LoadAssetAtPath<Material>(path);
        if(!m){m=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(m,path);}
        m.SetColor("_BaseColor",Hex(color));m.SetFloat("_Smoothness",smooth);m.SetFloat("_Metallic",metal);EditorUtility.SetDirty(m);return m;
    }
}
}
