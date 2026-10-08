using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace DesertRV.Editor
{
    public static class JourneyCandidateArtCapture
    {
        [Serializable] sealed class Frame
        {
            public string image, requestedState, imageSha256, meshPoseSha256;
            public float advanceSeconds, normalizedTime, worldMinY, groundReferenceY;
            public int stateHash, sampledVertices, outsideViewportVertices, behindCameraVertices, belowReferenceVertices;
            public bool transitioning, groundDiagnosticApplicable;
        }
        [Serializable] sealed class Evidence
        {
            public string status="not-complete", scope="real-Animator-pose-diagnostics-only", prefab, dependencySha256;
            public bool visualAccepted=false, gameplayAccepted=false;
            public string[] notCovered={"Authoritative combat/weakpoint event state", "Gameplay interruption and reload counts", "Whole-session restart", "Three-region walkthrough", "Android device"};
            public List<Frame> frames=new List<Frame>();
        }
        // Entry is called inside the dedicated native NUnit assembly, not a build method.
        public static void ImportAndCapture()
        {
            string folder=Path.GetFullPath("CandidateImportInput");
            Environment.SetEnvironmentVariable("DESERTRV_ART_INPUT",Path.Combine(folder,"payload"));
            Environment.SetEnvironmentVariable("DESERTRV_ART_CONTRACT",Path.Combine(folder,"contract.json"));
            Environment.SetEnvironmentVariable("DESERTRV_ART_ARCHIVE",Path.Combine(folder,"artifact.zip"));
            if(SystemInfo.graphicsDeviceType!=GraphicsDeviceType.OpenGLCore)throw new InvalidOperationException("Real OpenGLCore renderer required, not null graphics.");
            JourneyCandidateArtImport.Import();
            var import=JsonUtility.FromJson<JourneyCandidateArtImport.Report>(File.ReadAllText("JourneyEvidence/CandidateArt/import-report.json"));
            var contract=JsonUtility.FromJson<JourneyCandidateArtImport.Contract>(File.ReadAllText(Path.Combine(folder,"contract.json")));
            var evidence=new Evidence{prefab=import.prefab,dependencySha256=import.dependencySha256};
            var scene=EditorSceneManager.NewPreviewScene();
            GameObject subject=null; RenderTexture target=null; Texture2D pixels=null;
            try
            {
                subject=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(import.prefab),scene);
                // Runtime presenters need real gameplay references. This diagnostic exercises Animator only.
                foreach(var script in subject.GetComponentsInChildren<MonoBehaviour>(true))script.enabled=false;
                var animator=subject.GetComponentInChildren<Animator>();
                animator.cullingMode=AnimatorCullingMode.AlwaysAnimate; animator.applyRootMotion=false; animator.Rebind(); animator.Update(0);
                var cameraObject=new GameObject("CandidateReviewCamera"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(cameraObject,scene);
                var camera=cameraObject.AddComponent<Camera>(); camera.scene=scene; camera.backgroundColor=new Color(.12f,.14f,.17f); camera.clearFlags=CameraClearFlags.SolidColor;
                target=new RenderTexture(960,540,24); target.Create(); camera.targetTexture=target;
                pixels=new Texture2D(960,540,TextureFormat.RGB24,false);
                var lightObject=new GameObject("CandidateReviewLight"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(lightObject,scene);
                var light=lightObject.AddComponent<Light>(); light.type=LightType.Directional; light.intensity=2; light.transform.rotation=Quaternion.Euler(40,-30,0);
                var initialRenderers=subject.GetComponentsInChildren<Renderer>(true).Where(r=>r.enabled && !(r is ParticleSystemRenderer)).ToArray();
                if(initialRenderers.Length==0)throw new InvalidOperationException("Missing geometry.");
                var initialBounds=initialRenderers[0].bounds; foreach(var r in initialRenderers)initialBounds.Encapsulate(r.bounds);
                camera.transform.position=initialBounds.center+new Vector3(1,.45f,-1).normalized*initialBounds.extents.magnitude*3.2f; camera.transform.LookAt(initialBounds.center); camera.nearClipPlane=.005f; camera.farClipPlane=150;
                var states=((AnimatorController)animator.runtimeAnimatorController).layers[0].stateMachine.states.Select(x=>x.state.name).ToArray();
                foreach(string state in states)
                {
                    int start=evidence.frames.Count;
                    foreach(float time in new[]{0f,.25f,.5f,.75f,.999f})
                    { animator.Play("Base Layer."+state,0,time); animator.Update(0); if(animator.GetCurrentAnimatorStateInfo(0).fullPathHash!=Animator.StringToHash("Base Layer."+state))throw new InvalidOperationException("Actual Animator did not enter "+state); Capture(state+"-"+time.ToString("0.000",System.Globalization.CultureInfo.InvariantCulture),state,0); }
                    if(contract.clips.Single(c=>c.state==state).poseExpectation=="varying" && evidence.frames.Skip(start).Select(f=>f.meshPoseSha256).Distinct().Count()<2)
                        throw new InvalidOperationException("Contract expected actual mesh pose variation in "+state);
                    // Held Recover is valid when declared; presenter-owned opening is not exercised here.
                }
                if(states.Contains("Attack"))
                {
                    foreach(float interrupt in new[]{.25f,.5f,.75f})
                    {
                        animator.Play("Base Layer.Attack",0,interrupt); animator.Update(0);
                        animator.CrossFade("Recover",.12f); // Exact current BeastActor normalized-duration API.
                        Sequence("Attack-"+interrupt+"-Recover","Recover");
                    }
                    foreach(string phase in states.Where(s=>s!="Death")) foreach(float interrupt in new[]{.25f,.5f,.75f})
                    {
                        animator.Play("Base Layer."+phase,0,interrupt); animator.Update(0); animator.CrossFade("Death",.12f);
                        Sequence(phase+"-"+interrupt+"-Death","Death");
                    }
                    // Explicit Animator reset only. Whole-session restart remains a separate runtime requirement.
                    for(int repeat=0;repeat<2;repeat++) { animator.Rebind(); animator.Play("Base Layer.Idle",0,0); animator.Update(0); Capture("animator-reset-"+repeat,"Idle",0); }
                }
                evidence.status="captured-unreviewed";
                void Sequence(string label,string state)
                { float elapsed=0; foreach(float step in new[]{0f,.016f,.033f,.067f,.12f,.25f,.5f}) { animator.Update(step); elapsed+=step; Capture(label+"-"+elapsed.ToString("0.000",System.Globalization.CultureInfo.InvariantCulture),state,step); }
                    if(animator.IsInTransition(0) || animator.GetCurrentAnimatorStateInfo(0).fullPathHash!=Animator.StringToHash("Base Layer."+state))throw new InvalidOperationException("CrossFade did not reach "+state); }
                void Capture(string label,string state,float advance)
                {
                    var renderers=subject.GetComponentsInChildren<Renderer>(true).Where(r=>r.enabled && !(r is ParticleSystemRenderer)).ToArray();
                    if(renderers.Length==0)throw new InvalidOperationException("No actual visible geometry.");
                    var bounds=renderers[0].bounds; foreach(var renderer in renderers)bounds.Encapsulate(renderer.bounds);
                    float radius=bounds.extents.magnitude;
                    if(float.IsNaN(radius)||float.IsInfinity(radius)||radius<.01f||radius>20)throw new InvalidOperationException("Invalid imported pose bounds.");
                    // Keep the initial camera fixed; never hide drifting poses by reframing each image.
                    var previous=RenderTexture.active;
                    try
                    {
                        var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                        if(!RenderPipeline.SupportsRenderRequest(camera,request))throw new InvalidOperationException("Current pipeline does not support URP SingleCameraRequest.");
                        RenderPipeline.SubmitRenderRequest(camera,request);
                        RenderTexture.active=target; pixels.ReadPixels(new Rect(0,0,960,540),0,0); pixels.Apply();
                    }
                    finally { RenderTexture.active=previous; }
                    var rgb=pixels.GetPixels32(); var first=rgb[0]; int changed=rgb.Count(p=>Math.Abs(p.r-first.r)+Math.Abs(p.g-first.g)+Math.Abs(p.b-first.b)>20);
                    if(changed<200)throw new InvalidOperationException("Blank/near-blank actual render.");
                    string file="frame-"+evidence.frames.Count.ToString("D4")+".png"; byte[] png=pixels.EncodeToPNG(); File.WriteAllBytes("JourneyEvidence/CandidateArt/"+file,png);
                    string imageHash; using(var sha=System.Security.Cryptography.SHA256.Create())imageHash=BitConverter.ToString(sha.ComputeHash(png)).Replace("-","").ToLowerInvariant();
                    var info=animator.GetCurrentAnimatorStateInfo(0);
                    var frame=new Frame{image=file,imageSha256=imageHash,requestedState=label,advanceSeconds=advance,normalizedTime=info.normalizedTime,stateHash=info.fullPathHash,transitioning=animator.IsInTransition(0),groundDiagnosticApplicable=contract.kind!="weapon",groundReferenceY=subject.transform.position.y};
                    MeasureMeshes(renderers,camera,frame); evidence.frames.Add(frame);
                }
            }
            finally
            {
                try { File.WriteAllText("JourneyEvidence/CandidateArt/capture-report.json",JsonUtility.ToJson(evidence,true)); }
                finally
                {
                    try { if(target) { try { target.Release(); } finally { UnityEngine.Object.DestroyImmediate(target); } } }
                    finally
                    {
                        try { if(pixels)UnityEngine.Object.DestroyImmediate(pixels); }
                        finally { EditorSceneManager.ClosePreviewScene(scene); }
                    }
                }
                // No normal scene opened or saved.
            }
        }
        // Actual deformed vertices, not Renderer.bounds. Measurements are diagnostics, not foot-contact approval.
        static void MeasureMeshes(Renderer[] renderers,Camera camera,Frame frame)
        {
            float minY=float.PositiveInfinity;
            using(var bytes=new MemoryStream()) using(var writer=new BinaryWriter(bytes))
            {
                foreach(var renderer in renderers)
                {
                    Mesh temporary=null;
                    try
                    {
                        Mesh mesh;
                        if(renderer is SkinnedMeshRenderer skin) { temporary=new Mesh(); skin.BakeMesh(temporary,false); mesh=temporary; }
                        else { var filter=renderer.GetComponent<MeshFilter>(); mesh=filter?filter.sharedMesh:null; }
                        if(!mesh || !mesh.isReadable || mesh.vertexCount==0)throw new InvalidOperationException("Actual readable mesh required for pose diagnostics: "+renderer.name);
                        writer.Write(renderer.name);
                        foreach(var local in mesh.vertices)
                        {
                            Vector3 world=renderer.transform.TransformPoint(local);
                            if(float.IsNaN(world.x)||float.IsNaN(world.y)||float.IsNaN(world.z)||float.IsInfinity(world.x)||float.IsInfinity(world.y)||float.IsInfinity(world.z))throw new InvalidOperationException("Nonfinite deformed vertex.");
                            writer.Write(world.x);writer.Write(world.y);writer.Write(world.z);
                            minY=Mathf.Min(minY,world.y);frame.sampledVertices++;
                            var viewport=camera.WorldToViewportPoint(world);
                            if(viewport.z<=0)frame.behindCameraVertices++;
                            if(viewport.z<camera.nearClipPlane || viewport.z>camera.farClipPlane || viewport.x<0 || viewport.x>1 || viewport.y<0 || viewport.y>1)frame.outsideViewportVertices++;
                            if(frame.groundDiagnosticApplicable && world.y<frame.groundReferenceY)frame.belowReferenceVertices++;
                        }
                    }
                    finally { if(temporary)UnityEngine.Object.DestroyImmediate(temporary); }
                }
                if(frame.sampledVertices==0)throw new InvalidOperationException("No mesh diagnostic samples.");
                frame.worldMinY=minY;writer.Flush();
                using(var sha=System.Security.Cryptography.SHA256.Create())frame.meshPoseSha256=BitConverter.ToString(sha.ComputeHash(bytes.ToArray())).Replace("-","").ToLowerInvariant();
            }
        }
    }
}
