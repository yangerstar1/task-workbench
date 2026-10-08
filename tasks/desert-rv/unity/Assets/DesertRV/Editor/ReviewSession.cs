using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEditor;
using UnityEditor.SceneManagement;

namespace DesertRV.Editor {
// A temporary, local review session for this scene; no network or general command execution.
[InitializeOnLoad]
public static class ReviewSession {
    const string ScenePath="Assets/DesertRV/Scenes/BodyStudy.unity";
    const string Running="DesertRV.ReviewSession.Running";
    static string Root=>Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
    static string RequestPath=>Path.Combine(Root,"review-request.json");
    static double nextCheck;
    static bool busy;
    [Serializable] public class Request {public string id;public string action;public string label;}
    [Serializable] public class Result {public string id;public string action;public string status;public string message;public double seconds;}
    static ReviewSession(){EditorApplication.update+=Tick;}
    public static void Start(){
        EditorSceneManager.OpenScene(ScenePath);
        UnityEditor.SessionState.SetBool(Running,true);
        PersistEmbeddedAssets();
        File.WriteAllText(Path.Combine(Root,"review-ready.txt"),DateTime.UtcNow.ToString("O"));
        Debug.Log("RV_REVIEW_READY: saved scene, GPU render, no Web export");
    }
    static void Tick(){
        if(!UnityEditor.SessionState.GetBool(Running,false)||busy||EditorApplication.isCompiling||Lightmapping.isRunning||EditorApplication.timeSinceStartup<nextCheck)return;
        nextCheck=EditorApplication.timeSinceStartup+1;
        if(!File.Exists(RequestPath))return;
        Request request;
        try{request=JsonUtility.FromJson<Request>(File.ReadAllText(RequestPath));}catch{return;}
        if(request==null||string.IsNullOrWhiteSpace(request.id)||request.id==UnityEditor.SessionState.GetString(Running+".last", ""))return;
        UnityEditor.SessionState.SetString(Running+".last",request.id);
        busy=true;var watch=System.Diagnostics.Stopwatch.StartNew();
        try{
            switch(request.action){
                case "capture":Capture(request.label??request.id);break;
                case "refresh":AssetDatabase.Refresh();break;
                case "look":StationLook.Apply();PersistEmbeddedAssets();Capture(request.label??request.id);break;
                case "cabin":CabinFinish.Apply();PersistEmbeddedAssets();Capture(request.label??request.id);break;
                case "quality":CabinQuality.Apply();PersistEmbeddedAssets();Capture(request.label??request.id);break;
                case "bake":StationLook.Bake();Capture(request.label??request.id);break;
                case "build":EditorSceneManager.SaveOpenScenes();BodyBuild.Build();break;
                case "build-assets":ReportBuildAssets();break;
                case "stop":UnityEditor.SessionState.SetBool(Running,false);break;
                default:throw new InvalidOperationException("Unknown review action: "+request.action);
            }
            WriteResult(request,"ok","",watch.Elapsed.TotalSeconds);
            if(request.action=="stop")EditorApplication.Exit(0);
        }catch(Exception ex){Debug.LogException(ex);WriteResult(request,"error",ex.ToString(),watch.Elapsed.TotalSeconds);}
        finally{busy=false;}
    }
    static void WriteResult(Request request,string status,string message,double seconds){
        var result=new Result{id=request.id,action=request.action,status=status,message=message,seconds=seconds};
        File.WriteAllText(Path.Combine(Root,"review-result.json"),JsonUtility.ToJson(result,true));
        Debug.Log("RV_REVIEW_RESULT "+JsonUtility.ToJson(result));
    }
    static void ReportBuildAssets(){
        var report=BuildReport.GetLatestReport();if(report==null)throw new InvalidOperationException("No saved build report");
        var lines=report.packedAssets.SelectMany(p=>p.contents).GroupBy(p=>p.sourceAssetPath)
            .Select(g=>new {path=g.Key,bytes=g.Sum(p=>(long)p.packedSize)})
            .OrderByDescending(p=>p.bytes).Take(25).Select(p=>p.bytes+"\t"+p.path);
        File.WriteAllLines(Path.Combine(Root,"build-largest-assets.tsv"),lines);
    }
    static void PersistEmbeddedAssets(){
        const string folder="Assets/DesertRV/Art/SceneMaterials";
        Directory.CreateDirectory(folder);AssetDatabase.Refresh();
        var seen=new Dictionary<Material,Material>();
        foreach(var renderer in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None)){
            var materials=renderer.sharedMaterials;
            for(int i=0;i<materials.Length;i++){
                var material=materials[i];if(!material||AssetDatabase.Contains(material))continue;
                if(!seen.TryGetValue(material,out var saved)){
                    saved=new Material(material);saved.name=material.name;
                    var name=string.Join("_",material.name.Split(Path.GetInvalidFileNameChars()));
                    AssetDatabase.CreateAsset(saved,AssetDatabase.GenerateUniqueAssetPath(folder+"/"+name+".mat"));seen[material]=saved;
                }
                materials[i]=saved;
            }
            renderer.sharedMaterials=materials;
        }
        if(RenderSettings.skybox&&!AssetDatabase.Contains(RenderSettings.skybox)){
            var sky=new Material(RenderSettings.skybox);AssetDatabase.CreateAsset(sky,folder+"/DesertSky.mat");RenderSettings.skybox=sky;
        }
        foreach(var volume in UnityEngine.Object.FindObjectsByType<Volume>(FindObjectsSortMode.None)){
            if(!volume.sharedProfile||AssetDatabase.Contains(volume.sharedProfile))continue;
            var profile=UnityEngine.Object.Instantiate(volume.sharedProfile);
            AssetDatabase.CreateAsset(profile,AssetDatabase.GenerateUniqueAssetPath("Assets/DesertRV/Settings/StationLook.asset"));
            for(int i=0;i<profile.components.Count;i++){
                var component=UnityEngine.Object.Instantiate(profile.components[i]);profile.components[i]=component;AssetDatabase.AddObjectToAsset(component,profile);
            }
            volume.sharedProfile=profile;
        }
        AssetDatabase.SaveAssets();EditorSceneManager.SaveOpenScenes();
    }
    public static void Capture(string label){
        if(label.IndexOfAny(Path.GetInvalidFileNameChars())>=0)throw new ArgumentException("Invalid capture label");
        var folder=Path.Combine(Root,"screenshots",label);Directory.CreateDirectory(folder);
        var viewer=UnityEngine.Object.FindFirstObjectByType<BodyViewer>();var camera=viewer.view;var body=viewer.body;
        Vector3 forward=Vector3.forward;Transform hinge=null;
        foreach(var t in body.GetComponentsInChildren<Transform>()){
            if(t.name=="GEO-windscreen"){forward=t.GetComponent<Renderer>().bounds.center-body.position;forward.y=0;forward.Normalize();}
            if(t.name=="RIG-entry_door_pivot")hinge=t;
        }
        var oldPosition=camera.transform.position;var oldRotation=camera.transform.rotation;float oldFov=camera.fieldOfView;
        var oldDoor=hinge.localRotation;
        var target=new RenderTexture(1280,720,24,RenderTextureFormat.ARGB32){antiAliasing=4};target.Create();
        try{
            foreach(var key in new[]{"front","top","garage","inside","inside-detail","upgrades"}){
                viewer.ReviewModule(key=="upgrades"?"both":"none");
                hinge.localRotation=oldDoor;
                if(key.StartsWith("inside")||key=="garage"){
                    camera.fieldOfView=66;
                    Vector3 point,face;
                    if(key.StartsWith("inside")){
                        point=body.position+forward*(key=="inside-detail"?-1.55f:.55f)+Vector3.up*(.86f+1.52f);face=-forward;
                        hinge.localRotation=oldDoor*Quaternion.AngleAxis(-100,hinge.InverseTransformDirection(Vector3.up));
                    }else{
                        var bench=viewer.garageBench.GetComponent<Renderer>().bounds.center;var toward=body.position-bench;toward.y=0;toward.Normalize();
                        point=bench-toward+Vector3.Cross(Vector3.up,toward)*.9f;point.y=.06f+1.52f;face=body.position-point;face.y=0;
                    }
                    camera.transform.SetPositionAndRotation(point,Quaternion.Euler(key=="inside-detail"?29:8,Quaternion.LookRotation(face).eulerAngles.y,0));
                }else{
                    camera.fieldOfView=44;var center=body.position+Vector3.up*1.3f;
                    if(key=="top"){var to=viewer.garageBench.GetComponent<Renderer>().bounds.center-body.position;to.y=0;center+=to*.44f;}
                    var rotation=key=="top"?Quaternion.Euler(58,-125,0):Quaternion.Euler(19,145,0);
                    camera.transform.position=center+rotation*new Vector3(0,0,key=="top"?-34:-10);camera.transform.LookAt(center);
                }
                Physics.SyncTransforms();
                var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                RenderPipeline.SubmitRenderRequest(camera,request);
                var previous=RenderTexture.active;RenderTexture.active=target;
                var pixels=new Texture2D(1280,720,TextureFormat.RGB24,false);pixels.ReadPixels(new Rect(0,0,1280,720),0,0);pixels.Apply();
                File.WriteAllBytes(Path.Combine(folder,key+".png"),pixels.EncodeToPNG());
                UnityEngine.Object.DestroyImmediate(pixels);RenderTexture.active=previous;
            }
        }finally{
            viewer.ReviewModule("none");camera.transform.SetPositionAndRotation(oldPosition,oldRotation);camera.fieldOfView=oldFov;hinge.localRotation=oldDoor;
            target.Release();UnityEngine.Object.DestroyImmediate(target);
        }
    }
}}
