using System;
using System.IO;
using System.Linq;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneySceneAuthoring
    {
        [Serializable] sealed class PolishCameraRecord {public string view,file;public Vector3 position,lookAt;public float fieldOfView;}
        [Serializable] sealed class PolishCameraReport {public string status="ACTUAL_EDITOR_EYE_HEIGHT_VIEWS_NOT_INPUT_PLAYTHROUGH",graphicsDevice;public bool savedSceneBytesPreserved,captureBuffersReleased;public PolishCameraRecord[] images;}
        // Additional eye-height evidence. The previous 18-view camera contract stays unchanged.
        public static void CaptureEnvironmentPolishCloseups()
        {
            if(SystemInfo.graphicsDeviceType==GraphicsDeviceType.Null)throw new InvalidOperationException("Actual URP graphics device required.");
            var setup=EditorSceneManager.GetSceneManagerSetup();
            if(setup.Any(s=>s.isLoaded&&SceneManager.GetSceneByPath(s.path).isDirty))throw new InvalidOperationException("Save/discard existing scene edits before capture.");
            var protectedFiles=SnapshotProtectedFiles();
            var saved=new[]{BootstrapPath,RegionPaths[0]}.SelectMany(p=>new[]{p,p+".meta"}).ToDictionary(p=>p,HashFile);
            RenderTexture target=null;Texture2D pixels=null;var previous=RenderTexture.active;
            PolishCameraRecord[] records=null;bool released=false;
            try
            {
                var boot=EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);
                var scene=EditorSceneManager.OpenScene(RegionPaths[0],OpenSceneMode.Additive);SceneManager.SetActiveScene(scene);
                var motor=Components<JourneyMotor>(boot).Single();var b=Components<RegionBinding>(scene).Single();
                motor.vehicle.SetPositionAndRotation(b.spawn.position,b.spawn.rotation);CheckNewLayoutClearance(b,motor,Components<JourneyActions>(boot).Single());
                var camera=motor.view;camera.enabled=false;camera.nearClipPlane=.045f;camera.farClipPlane=450;camera.fieldOfView=66;camera.clearFlags=CameraClearFlags.Skybox;
                var canopy=SourceGeometry(scene).Single(t=>t.name=="GEO-pump_canopy").GetComponent<Renderer>().bounds;
                Vector3 forecourtAt=new Vector3(-4.85f,1.62f,canopy.max.z+2.45f);
                Vector3 garageAt=b.salvage.position+Vector3.right*3.2f;garageAt.y=1.62f;
                records=new[]{
                    new PolishCameraRecord{view="forecourt-eye-height",position=forecourtAt,lookAt=new Vector3(canopy.center.x,1.75f,canopy.center.z),fieldOfView=66},
                    new PolishCameraRecord{view="garage-eye-height",position=garageAt,lookAt=b.salvage.position+Vector3.up*.38f,fieldOfView=66}
                };
                target=new RenderTexture(1440,900,24,RenderTextureFormat.ARGB32){hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create())throw new InvalidOperationException("Closeup target creation failed.");
                pixels=new Texture2D(1440,900,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                Directory.CreateDirectory("JourneyEvidence/environment-v4");
                foreach(var record in records)
                {
                    camera.transform.SetPositionAndRotation(record.position,Quaternion.LookRotation(record.lookAt-record.position));Physics.SyncTransforms();
                    var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                    if(!RenderPipeline.SupportsRenderRequest(camera,request))throw new InvalidOperationException("URP render request unsupported.");
                    RenderPipeline.SubmitRenderRequest(camera,request);RenderTexture.active=target;
                    pixels.ReadPixels(new Rect(0,0,1440,900),0,0);pixels.Apply();
                    var sampled=pixels.GetPixels32().Where((c,i)=>i%97==0).Select(c=>(c.r+c.g+c.b)/765f).ToArray();
                    if(sampled.Max()<.10f||sampled.Max()-sampled.Min()<.06f)throw new InvalidOperationException("Blank closeup rejected: "+record.view);
                    record.file="JourneyEvidence/environment-v4/FirstStation-"+record.view+".png";File.WriteAllBytes(record.file,pixels.EncodeToPNG());RenderTexture.active=previous;
                }
            }
            finally
            {
                try
                {
                    RenderTexture.active=previous;
                    try {if(pixels)Object.DestroyImmediate(pixels);}
                    finally {if(target){try{target.Release();}finally{Object.DestroyImmediate(target);}}}
                    released=!pixels&&!target;
                }
                finally {try{RestoreSceneSetup(setup);}finally{VerifyProtectedFiles(protectedFiles);}}
            }
            if(!released||records==null||records.Length!=2)throw new InvalidOperationException("Incomplete closeup buffer lifecycle.");
            foreach(var pair in saved)if(HashFile(pair.Key)!=pair.Value)throw new InvalidOperationException("Closeup capture changed saved scene bytes: "+pair.Key);
            File.WriteAllText("JourneyEvidence/environment-v4/closeup-capture-report.json",JsonUtility.ToJson(new PolishCameraReport{graphicsDevice=SystemInfo.graphicsDeviceType.ToString(),savedSceneBytesPreserved=true,captureBuffersReleased=released,images=records},true));
        }
    }
}
