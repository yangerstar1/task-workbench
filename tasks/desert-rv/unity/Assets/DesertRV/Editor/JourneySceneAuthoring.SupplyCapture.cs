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
        [Serializable] sealed class SupplySceneHash { public string path,beforeSha256,afterSha256; }
        [Serializable] sealed class SupplyFixture
        {
            public int region,reserveBefore,reserveAfter,repairBefore,repairAfter;
            public string selectedId,blockedId;
            public bool otherRejected,selectedOfferHidden,otherSealed,selectedBoxStillPresent;
        }
        [Serializable] sealed class SupplyImages
        {
            public string status="EDITOR_VISUAL_FIXTURE_NOT_INPUT_PLAYTHROUGH",graphicsDeviceType,graphicsDeviceName;
            public int bufferSceneTransitionsChecked;public bool captureBuffersReleased;
            public SupplySceneHash[] savedScenes;public SupplyFixture[] fixtures;public SupplyImage[] images;
        }
        static SessionState SupplyFixtureState(int region)
        {
            // Standalone visual fixture only. These public rule calls are not traversal evidence.
            var state=new SessionState();
            if(!state.ConfigureStorm(-40,2,4)||!state.Start())throw new InvalidOperationException("Fixture start failed.");
            for(int i=1;i<region;i++)
            {
                var part=i==1?ComponentPart.RamPart:ComponentPart.Coil;
                if(!state.TryCollect("editor-fixture-part-"+i,part)||!state.TryInstall(part)||!state.SetObjectivesResolved(true)||!state.TryAdvance()||!state.CompleteLoading())
                    throw new InvalidOperationException("Fixture region setup failed.");
            }
            state.SetControl(ControlMode.OnFoot);return state;
        }
        // Separate opt-in evidence command: it does not alter the original 18-image contract.
        public static void CaptureOptionalSupplyCandidates()
        {
            if(SystemInfo.graphicsDeviceType==GraphicsDeviceType.Null)throw new InvalidOperationException("Real graphics device required for supply evidence.");
            var setup=EditorSceneManager.GetSceneManagerSetup();
            if(setup.Any(s=>s.isLoaded&&SceneManager.GetSceneByPath(s.path).isDirty))throw new InvalidOperationException("Save/discard scene edits before capture.");
            var protectedFiles=SnapshotProtectedFiles();var images=new List<SupplyImage>();var fixtures=new List<SupplyFixture>();
            var saved=new[]{BootstrapPath}.Concat(RegionPaths).SelectMany(path=>new[]{path,path+".meta"}).Select(path=>new SupplySceneHash{path=path,beforeSha256=HashFile(path)}).ToArray();
            int transitions=0;bool released=false;string folder="JourneyEvidence/supplies";Directory.CreateDirectory(folder);
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
                    if(!target||!target.IsCreated()||!pixels)throw new InvalidOperationException("Supply buffers lost across scene transition.");transitions++;
                    var camera=motor.view;camera.enabled=false;camera.fieldOfView=66;camera.nearClipPlane=.04f;camera.farClipPlane=450;camera.clearFlags=CameraClearFlags.Skybox;
                    var view=b.GetComponentInChildren<JourneySupplyChoiceVisual>(true);
                    var plan=SupplyPlacements(region);var state=SupplyFixtureState(region);view.Refresh(state);
                    foreach(var key in new[]{"directions-before","ammo-before","repair-sealed-after-ammo"})
                    {
                        if(key=="repair-sealed-after-ammo")
                        {
                            var selected=b.supplies[0];var other=b.supplies[1];
                            var fixture=new SupplyFixture{region=region,selectedId=selected.id,blockedId=other.id,reserveBefore=state.ReserveAmmo,repairBefore=state.RepairKits};
                            if(!state.TryCollectSupply(region,state.Generation,selected.id,selected.kind,selected.amount,selected.choiceGroup))throw new InvalidOperationException("Fixture supply collection failed.");
                            fixture.otherRejected=!state.TryCollectSupply(region,state.Generation,other.id,other.kind,other.amount,other.choiceGroup);
                            view.Refresh(state);fixture.reserveAfter=state.ReserveAmmo;fixture.repairAfter=state.RepairKits;
                            fixture.selectedOfferHidden=!view.options[0].availableSign.activeSelf;
                            fixture.otherSealed=view.options[1].sealedSign.activeSelf&&!view.options[1].availableSign.activeSelf&&view.sealedBoard.activeSelf;
                            fixture.selectedBoxStillPresent=selected.visual.activeSelf;
                            if(!fixture.otherRejected||!fixture.selectedOfferHidden||!fixture.otherSealed)throw new InvalidOperationException("Actual choice presentation did not seal the alternative.");
                            fixtures.Add(fixture);
                        }
                        Vector3 at,look;
                        if(key=="directions-before") {look=view.availableBoard.transform.position;at=look+Vector3.back*4.5f+Vector3.up*.1f;}
                        else {var p=plan[key=="ammo-before"?0:1];at=p.stand+Vector3.up*1.52f;look=p.at+Vector3.up*.84f;}
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
                            try { if(target)Object.DestroyImmediate(target);if(target||pixels)throw new InvalidOperationException("Supply capture buffers not released.");released=true; }
                            finally {try{RestoreSceneSetup(setup);}finally{VerifyProtectedFiles(protectedFiles);}}
                        }
                    }
                }
            }
            if(images.Count!=9)throw new InvalidOperationException("All three supply choices must have three real native images each.");
            foreach(var row in saved){row.afterSha256=HashFile(row.path);if(row.beforeSha256!=row.afterSha256)throw new InvalidOperationException("Saved candidate scene changed during fixture.");}
            File.WriteAllText(Path.Combine(folder,"capture-report.json"),JsonUtility.ToJson(new SupplyImages{images=images.ToArray(),fixtures=fixtures.ToArray(),savedScenes=saved,
                graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName,bufferSceneTransitionsChecked=transitions,captureBuffersReleased=released},true));
        }
    }
}
