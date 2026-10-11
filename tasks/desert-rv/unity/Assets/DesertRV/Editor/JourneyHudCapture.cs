#if UNITY_EDITOR
using System;
using System.IO;
using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;
using Object=UnityEngine.Object;

namespace DesertRV.Editor
{
    // An isolated native UI render fixture, not gameplay/device acceptance. It renders the actual
    // production HUD graph and pinned font through URP; supplied strings deliberately stress fit.
    public static class JourneyHudCapture
    {
        static readonly BindingFlags Private=BindingFlags.Instance|BindingFlags.NonPublic;
        static T Field<T>(JourneyHud hud,string name)=>(T)typeof(JourneyHud).GetField(name,Private).GetValue(hud);
        static void Text(JourneyHud hud,string name,string value)=>Field<Text>(hud,name).text=value;
        public static void CaptureAndMeasure()
        {
            if(SystemInfo.graphicsDeviceType==GraphicsDeviceType.Null) throw new InvalidOperationException("A real graphics device is required.");
            string output=Path.GetFullPath("JourneyEvidence/MobileHudNative"); Directory.CreateDirectory(output);
            var manifest=new CaptureManifest{source="production JourneyHud graph and pinned CJK font",evidence="native simulated-device UI render; no physical-device or gameplay acceptance",files=new List<CaptureFile>()};
            var shots=new List<string>();
            foreach(var profile in new[]{"desktop","compact","wide"})
            { shots.Add(profile+"-foot-glare");shots.Add(profile+"-drive-day");shots.Add(profile+"-pause-night"); }
            shots.Add("small-foot-glare");
            shots.AddRange(new[]{"compact-loading-glare","compact-failed-night","compact-complete-day"});
            foreach(string stem in shots)
            {
                string[] parts=stem.Split('-');Capture(output,parts[0],parts[1],parts[2]);
                foreach(string suffix in new[]{".png","-fit.csv"})
                {
                    byte[] bytes=File.ReadAllBytes(Path.Combine(output,stem+suffix));
                    using(var sha=SHA256.Create())manifest.files.Add(new CaptureFile{name=stem+suffix,bytes=bytes.Length,sha256=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant()});
                }
            }
            File.WriteAllText(Path.Combine(output,"capture-manifest.json"),JsonUtility.ToJson(manifest,true));
        }
        // Capture an already loaded, authored world using its existing camera view.
        // Camera/world/scene state is read only. HUD values remain fixture values, not live gameplay.
        public static void CaptureOverWorld(Camera sourceCamera,string label)
        {
            if(!sourceCamera)throw new ArgumentNullException(nameof(sourceCamera));
            if(string.IsNullOrEmpty(label)||!System.Text.RegularExpressions.Regex.IsMatch(label,"^[a-zA-Z0-9-]+$"))
                throw new ArgumentException("Use a simple capture label.",nameof(label));
            string output=Path.GetFullPath("JourneyEvidence/MobileHudWorld");Directory.CreateDirectory(output);
            Capture(output,"desktop","foot",label,sourceCamera);
            File.WriteAllText(Path.Combine(output,"EVIDENCE.txt"),"Authored, loaded world camera + production UGUI layout fixture. HUD values are controlled fixture data. Not live gameplay or physical-device acceptance. Saved scenes opened read-only for capture; no scenes saved or replaced.\n");
        }
        [Serializable] sealed class CaptureManifest { public string source,evidence; public List<CaptureFile> files; }
        [Serializable] sealed class CaptureFile { public string name,sha256; public int bytes; }
        static void Capture(string output,string profile,string mode,string background,Camera sourceCamera=null)
        {
            int width=profile=="desktop"?960:profile=="wide"?2400:1920;
            int height=profile=="desktop"?540:profile=="small"?960:1080;
            float scale=profile=="desktop"?1.125f:3;
            Rect safe=profile=="small"?new Rect(108,72,1704,888):profile=="desktop"?new Rect(0,0,width,height):new Rect(profile=="compact"?48:96,36,width-(profile=="compact"?96:192),height-36);
            GameObject root=null,cameraObject=null;RenderTexture target=null;Texture2D pixels=null;
            string stem=Path.Combine(output,profile+"-"+mode+"-"+background);
            if(File.Exists(stem+".png") || File.Exists(stem+"-fit.csv"))
                throw new InvalidOperationException("Capture output already exists.");
            var previous=RenderTexture.active;
            var failures=new List<Exception>();
            void AttemptCleanup(Action action)
            {
                try{action();}catch(Exception error){failures.Add(error);}
            }
            try
            {
                root=new GameObject("Native HUD render fixture",typeof(RectTransform));
                cameraObject=new GameObject("HUD render camera");
                target=new RenderTexture(width,height,24){hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create())throw new InvalidOperationException("Failed to create HUD capture target.");
                pixels=new Texture2D(width,height,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                var hud=root.AddComponent<JourneyHud>(); hud.enabled=false;
                hud.font=AssetDatabase.LoadAssetAtPath<Font>("Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf");
                if(!hud.font)throw new InvalidOperationException("Restore and verify the pinned production font first.");
                typeof(JourneyHud).GetMethod("Awake",Private).Invoke(hud,null);
                var camera=cameraObject.AddComponent<Camera>();
                if(sourceCamera)
                {
                    camera.CopyFrom(sourceCamera);camera.transform.SetPositionAndRotation(sourceCamera.transform.position,sourceCamera.transform.rotation);
                    if(sourceCamera.TryGetComponent<UniversalAdditionalCameraData>(out var sourceData))
                        EditorUtility.CopySerialized(sourceData,cameraObject.AddComponent<UniversalAdditionalCameraData>());
                    camera.cullingMask=sourceCamera.cullingMask|(1<<31);
                }
                else
                {
                    camera.clearFlags=CameraClearFlags.SolidColor;camera.cullingMask=1<<31;
                    camera.backgroundColor=background=="night"?new Color(.035f,.045f,.065f):background=="glare"?new Color(1,.95f,.8f):new Color(.64f,.72f,.75f);
                }
                camera.enabled=false;camera.targetTexture=target;camera.aspect=(float)width/height;
                var canvas=root.GetComponent<Canvas>(); canvas.renderMode=RenderMode.ScreenSpaceCamera; canvas.worldCamera=camera; canvas.planeDistance=1; canvas.scaleFactor=scale;
                hud.ConfigureLayoutPreview(width,height,safe,scale,profile=="desktop"&&mode=="pause");
                bool playing=mode=="foot"||mode=="drive";
                bool stress=profile=="compact"&&mode=="foot";
                Field<RectTransform>(hud,"menuShade").gameObject.SetActive(!playing);
                Text(hud,"regionLabel","荒漠行路 / 03"); Text(hud,"playerResource","体力 100"); Text(hud,"carResource","车况 300");
                Text(hud,"ammoResource","钉弹 999/999"); Text(hud,"kitResource","修理 3");
                Text(hud,"objective",JourneyHudLayout.ObjectiveLines("守住供电设备 · 第 2 波 · 充能 100%"));
                Text(hud,"storm","风暴中 · 正在受伤");
                Text(hud,"damageDirection","左侧受击 · 车况 −25"); Text(hud,"rearThreat","风暴受伤 · 后方近敌蓄力");
                Text(hud,"notice","断电：充能暂停，现有敌人仍会攻击。");
                Text(hud,"prompt",JourneyHudLayout.PromptLines("拔除电缆 · 暂停充能，敌人仍攻击"));
                Text(hud,"interactLabel",mode=="drive"?"下车":"拔除电缆");
                if(sourceCamera)
                {
                    bool first=background=="region-1";
                    Text(hud,"regionLabel",first?"荒漠行路 / 01":"荒漠行路 / 03");
                    Text(hud,"ammoResource",first?"钉弹 12/96":"钉弹 12/144");
                    Text(hud,"objective",first?"搜索加油站的撞角组件":"拔除电缆\n驾驶房车驶入安全区");
                    Text(hud,"prompt",first?"收取撞角组件":"拔除电缆\n暂停充能，敌人仍攻击");
                    Text(hud,"interactLabel",first?"收取组件":"拔除电缆");Text(hud,"storm","风暴正在逼近");
                }
                foreach(var name in new[]{"damagePanel","rearPanel","noticePanel"}) Field<RectTransform>(hud,name).gameObject.SetActive(stress);
                Field<RectTransform>(hud,"stormPanel").gameObject.SetActive(!stress);
                var controls=Field<System.Collections.Generic.Dictionary<TouchControl,RectTransform>>(hud,"controls");
                foreach(var item in controls) item.Value.gameObject.SetActive(playing &&
                    (item.Key==TouchControl.Move||item.Key==TouchControl.Interact||
                    (mode=="drive"?item.Key==TouchControl.Accelerate||item.Key==TouchControl.Brake:item.Key==TouchControl.Fire||item.Key==TouchControl.Reload)));
                Field<Text>(hud,"crosshair").gameObject.SetActive(mode=="foot"); Field<Text>(hud,"hitMark").gameObject.SetActive(false);
                foreach(var name in new[]{"playerBar","carBar","actionBar"}) Field<Image>(hud,name).fillAmount=.68f;
                Field<Image>(hud,"actionBar").transform.parent.gameObject.SetActive(stress);
                bool keyboard=profile=="desktop"&&mode=="pause";
                foreach(var name in new[]{"keyboardLookToggle","keyboardLookSpeed"}) Field<Button>(hud,name).gameObject.SetActive(keyboard);
                Field<Text>(hud,"keyboardLookHelp").gameObject.SetActive(keyboard);
                Field<Button>(hud,"keyboardLookToggle").GetComponentInChildren<Text>().text="键盘视角：IJKL";
                Field<Button>(hud,"keyboardLookSpeed").GetComponentInChildren<Text>().text="视角速度：120°/秒";
                Text(hud,"menuTitle",mode=="loading"?"正在前往下一地区":mode=="failed"?"旅程结束":mode=="complete"?"整局胜利":"旅程暂停");
                Text(hud,"menuBody",mode=="complete"?"信标已经完成，电缆已拔除，房车安全撤离。\n再次出发会重置整局资源与改装。":
                    mode=="loading"?"正在加载地区，物资与风暴进度将保留。":mode=="failed"?"人和房车都得撑到最后。\n重新出发会重置本趟物资和改装。":"暂停时风暴与战斗一起冻结。");
                Text(hud,"primaryLabel",mode=="complete"||mode=="failed"?"整局重新出发":"继续");
                Field<Button>(hud,"primary").interactable=mode!="loading";
                Field<RectTransform>(hud,"promptPanel").gameObject.SetActive(mode=="foot"&&!stress); // One feedback lane; notices replace prompts.
                foreach(var child in root.GetComponentsInChildren<Transform>(true))child.gameObject.layer=31;
                Canvas.ForceUpdateCanvases();
                var safeRect=Field<RectTransform>(hud,"safe").rect;
                if(Mathf.Abs(safeRect.width-safe.width/scale)>1 || Mathf.Abs(safeRect.height-safe.height/scale)>1)
                    throw new InvalidOperationException("Canvas has not adopted simulated device dimensions: "+safeRect);
                string fitFailure=null;
                var report=new System.Text.StringBuilder("profile,mode,background,label,font,available_height,preferred_height\n");
                foreach(var text in root.GetComponentsInChildren<Text>())
                {
                    if(string.IsNullOrEmpty(text.text))continue;
                    var settings=text.GetGenerationSettings(new Vector2(text.rectTransform.rect.width,10000));
                    settings.verticalOverflow=VerticalWrapMode.Overflow;
                    float preferred=text.cachedTextGeneratorForLayout.GetPreferredHeight(text.text,settings)/text.pixelsPerUnit;
                    report.AppendLine(FormattableString.Invariant($"{profile},{mode},{background},{text.name},{text.fontSize},{text.rectTransform.rect.height},{preferred}"));
                    if(preferred>text.rectTransform.rect.height+1)
                        fitFailure=$"Text is clipped: {profile}/{mode}/{text.name}: {preferred} > {text.rectTransform.rect.height}: {text.text}";
                }
                File.WriteAllText(stem+"-fit.csv",report.ToString());
                var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                if(!RenderPipeline.SupportsRenderRequest(camera,request))throw new InvalidOperationException("URP native capture is unavailable.");
                RenderPipeline.SubmitRenderRequest(camera,request); RenderTexture.active=target;
                pixels.ReadPixels(new Rect(0,0,width,height),0,0); pixels.Apply();
                File.WriteAllBytes(stem+".png",pixels.EncodeToPNG());
                if(fitFailure!=null)throw new InvalidOperationException(fitFailure);
            }
            catch(Exception error){failures.Add(error);}
            finally
            {
                // A failed target restore/release must not skip any other cleanup or hide the render error.
                AttemptCleanup(()=>{RenderTexture.active=previous;});
                AttemptCleanup(()=>{if(root)Object.DestroyImmediate(root);});
                AttemptCleanup(()=>{if(cameraObject)Object.DestroyImmediate(cameraObject);});
                AttemptCleanup(()=>{if(pixels)Object.DestroyImmediate(pixels);});
                AttemptCleanup(()=>{if(target)target.Release();});
                AttemptCleanup(()=>{if(target)Object.DestroyImmediate(target);});
                AttemptCleanup(()=>{if(root || cameraObject || target || pixels)throw new InvalidOperationException("HUD capture resources were not released.");});
            }
            if(failures.Count==1)System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failures[0]).Throw();
            if(failures.Count>1)throw new AggregateException("HUD capture and cleanup failed; primary failure first.",failures);
        }
    }
}
#endif
