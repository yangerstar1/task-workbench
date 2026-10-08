using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
namespace DesertRV.Editor {
public static class CabinQuality {
    public static void Apply(){
        var renderer=AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/DesertRV/Settings/WebRenderer.asset");
        var serialized=new SerializedObject(renderer);
        serialized.FindProperty("postProcessData").objectReferenceValue=AssetDatabase.LoadAssetAtPath<PostProcessData>("Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset");
        serialized.ApplyModifiedPropertiesWithoutUndo();renderer.SetDirty();EditorUtility.SetDirty(renderer);
        foreach(var feature in renderer.rendererFeatures){
            if(feature.GetType().Name!="ScreenSpaceAmbientOcclusion")continue;
            var ao=new SerializedObject(feature);ao.FindProperty("m_Settings.Downsample").boolValue=false;
            ao.FindProperty("m_Settings.Intensity").floatValue=.55f;ao.FindProperty("m_Settings.Radius").floatValue=.22f;
            ao.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(feature);
        }
        var camera=UnityEngine.Object.FindFirstObjectByType<BodyViewer>().view;
        camera.allowHDR=true;camera.GetUniversalAdditionalCameraData().renderPostProcessing=true;
        var pipeline=AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/DesertRV/Settings/WebURP.asset");
        var pipelineData=new SerializedObject(pipeline);
        pipelineData.FindProperty("m_ReflectionProbeBlending").boolValue=true;
        pipelineData.FindProperty("m_ReflectionProbeBoxProjection").boolValue=true;
        pipelineData.FindProperty("m_AdditionalLightsPerObjectLimit").intValue=8;
        pipelineData.ApplyModifiedPropertiesWithoutUndo();EditorUtility.SetDirty(pipeline);
        foreach(var volume in UnityEngine.Object.FindObjectsByType<Volume>(FindObjectsSortMode.None)){
            if(volume.sharedProfile.TryGet<ColorAdjustments>(out var grade)){
                grade.postExposure.Override(.38f);grade.contrast.Override(1);grade.saturation.Override(3);EditorUtility.SetDirty(grade);
            }
        }
        var body=UnityEngine.Object.FindFirstObjectByType<BodyViewer>().body;
        for(int side=-1;side<=1;side+=2){
            string name="Cabin window bounce "+side;
            var t=body.Find(name);var light=t?t.GetComponent<Light>():new GameObject(name).AddComponent<Light>();
            light.transform.SetParent(body,false);light.transform.localPosition=new Vector3(side*.86f,2.035f,-1.23f);
            light.type=LightType.Point;light.range=1.65f;light.intensity=.20f;light.color=new Color(.74f,.85f,1f);light.shadows=LightShadows.None;
        }
        var transform=body.Find("Cabin interior reflection");
        var probe=transform?transform.GetComponent<ReflectionProbe>():new GameObject("Cabin interior reflection").AddComponent<ReflectionProbe>();
        probe.transform.SetParent(body,false);probe.transform.localPosition=new Vector3(0,1.92f,-1.08f);
        probe.size=new Vector3(2.13f,1.78f,4.86f);probe.center=new Vector3(0,-.18f,.82f);
        probe.resolution=256;probe.hdr=true;probe.boxProjection=true;probe.importance=10;probe.blendDistance=.06f;
        probe.intensity=.9f;probe.nearClipPlane=.04f;probe.farClipPlane=60;
        probe.mode=ReflectionProbeMode.Custom;probe.renderDynamicObjects=true;
        const string reflectionPath="Assets/DesertRV/Art/CabinInteriorReflection.exr";
        if(!Lightmapping.BakeReflectionProbe(probe,reflectionPath))throw new System.Exception("Cabin reflection bake failed");
        AssetDatabase.ImportAsset(reflectionPath,ImportAssetOptions.ForceSynchronousImport);
        probe.customBakedTexture=AssetDatabase.LoadAssetAtPath<Cubemap>(reflectionPath);
        if(!probe.customBakedTexture)throw new System.Exception("Cabin reflection texture missing");
        // The cubemap follows this enclosed cabin; exterior world shadows stay realtime.
        foreach(var r in body.GetComponentsInChildren<Renderer>())if(r.name.Contains("cabin_finished")||r.name.Contains("cabin_detail")||r.name.Contains("vise")||r.name.Contains("toolbox")){
            r.reflectionProbeUsage=ReflectionProbeUsage.BlendProbes;
            EditorUtility.SetDirty(r);if(PrefabUtility.IsPartOfPrefabInstance(r))PrefabUtility.RecordPrefabInstancePropertyModifications(r);
        }
        EditorSceneManager.MarkSceneDirty(camera.gameObject.scene);
        AssetDatabase.SaveAssets();EditorSceneManager.SaveOpenScenes();
        Debug.Log("RV_POSTPROCESS_BOUND: "+(renderer.postProcessData!=null));
    }
}
}
