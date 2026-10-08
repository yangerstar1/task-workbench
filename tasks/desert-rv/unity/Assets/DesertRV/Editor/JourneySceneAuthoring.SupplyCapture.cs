using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneySceneAuthoring
    {
        [Serializable] sealed class SupplyImage { public int region; public string view,file; public Vector3 cameraPosition,lookAt; }
        [Serializable] sealed class SupplyImages { public string status="NATIVE_EDITMODE_SUPPLY_LAYOUT_ONLY_NOT_PLAYTHROUGH";public SupplyImage[] images; }
        // Separate opt-in evidence command: it does not alter the original 18-image contract.
        public static void CaptureOptionalSupplyCandidates()
        {
            if(SystemInfo.graphicsDeviceType==GraphicsDeviceType.Null)throw new InvalidOperationException("Real graphics device required for supply evidence.");
            var setup=EditorSceneManager.GetSceneManagerSetup();
            if(setup.Any(s=>s.isLoaded&&SceneManager.GetSceneByPath(s.path).isDirty))throw new InvalidOperationException("Save/discard scene edits before capture.");
            var protectedFiles=SnapshotProtectedFiles();var images=new List<SupplyImage>();string folder="JourneyEvidence/supplies";Directory.CreateDirectory(folder);
            RenderTexture target=null;Texture2D pixels=null;var previous=RenderTexture.active;
            try
            {
                target=new RenderTexture(1440,900,24,RenderTextureFormat.ARGB32){hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create())throw new InvalidOperationException("Supply render target creation failed.");
                pixels=new Texture2D(1440,900,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                for(int region=1;region<=3;region++)
                {
                    var boot=EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);
                    var env=EditorSceneManager.OpenScene(RegionPaths[region-1],OpenSceneMode.Additive);SceneManager.SetActiveScene(env);
                    var motor=Components<JourneyMotor>(boot).Single();var b=Components<RegionBinding>(env).Single();
                    motor.vehicle.SetPositionAndRotation(b.spawn.position,b.spawn.rotation);CheckOptionalSupplyApproaches(b);
                    var camera=motor.view;camera.enabled=false;camera.fieldOfView=66;camera.nearClipPlane=.04f;camera.farClipPlane=450;camera.clearFlags=CameraClearFlags.Skybox;
                    var view=b.GetComponentInChildren<JourneySupplyChoiceVisual>(true);
                    var plan=SupplyPlacements(region);
                    foreach(var key in new[]{"directions","ammo-choice","repair-choice"})
                    {
                        Vector3 at,look;
                        if(key=="directions") {look=view.availableBoard.transform.position;at=look+Vector3.back*4.5f+Vector3.up*.1f;}
                        else {var p=plan[key=="ammo-choice"?0:1];at=p.stand+Vector3.up*1.52f;look=p.at+Vector3.up*.84f;}
                        camera.transform.position=at;camera.transform.LookAt(look);Physics.SyncTransforms();
                        foreach(var text in Components<Text>(env).Where(t=>t.isActiveAndEnabled))text.font.RequestCharactersInTexture(text.text,text.fontSize,text.fontStyle);
                        Canvas.ForceUpdateCanvases();
                        var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                        if(!RenderPipeline.SupportsRenderRequest(camera,request))throw new InvalidOperationException("URP capture unsupported.");
                        RenderPipeline.SubmitRenderRequest(camera,request);RenderTexture.active=target;pixels.ReadPixels(new Rect(0,0,1440,900),0,0);pixels.Apply();
                        var colors=pixels.GetPixels32();float min=1,max=0;
                        for(int n=0;n<colors.Length;n+=97){float v=(colors[n].r+colors[n].g+colors[n].b)/765f;min=Mathf.Min(min,v);max=Mathf.Max(max,v);}
                        if(max-min<.06f||max<.1f)throw new InvalidOperationException("Blank supply capture rejected.");
                        string file=Path.Combine(folder,env.name+"-"+key+".png");File.WriteAllBytes(file,pixels.EncodeToPNG());
                        images.Add(new SupplyImage{region=region,view=key,file=file,cameraPosition=at,lookAt=look});RenderTexture.active=previous;
                    }
                }
            }
            finally
            {
                try { RenderTexture.active=previous; }
                finally
                {
                    try { if(pixels)Object.DestroyImmediate(pixels); }
                    finally
                    {
                        try { if(target)target.Release(); }
                        finally
                        {
                            try { if(target)Object.DestroyImmediate(target); }
                            finally {try{RestoreSceneSetup(setup);}finally{VerifyProtectedFiles(protectedFiles);}}
                        }
                    }
                }
            }
            if(images.Count!=9)throw new InvalidOperationException("All three supply choices must have three real native images each.");
            File.WriteAllText(Path.Combine(folder,"capture-report.json"),JsonUtility.ToJson(new SupplyImages{images=images.ToArray()},true));
        }
    }
}
