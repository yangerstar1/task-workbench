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
            public float advanceSeconds, normalizedTime, worldMinY, groundReferenceY,rootLocalPositionDelta,rootLocalAngleDelta,rootLocalScaleDelta;
            public int stateHash, sampledVertices, outsideViewportVertices, behindCameraVertices, belowReferenceVertices;
            public bool transitioning, groundDiagnosticApplicable;
            public Vector3 rootLocalPosition,rootLocalScale,meshWorldMin,meshWorldMax,meshWorldSize,meshSizeRatioToNeutral;public Quaternion rootLocalRotation;
        }
        [Serializable] sealed class Evidence
        {
            public string graphicsDeviceType,graphicsDeviceName;
            public JourneyCandidateArtImport.RootNeutralBaseline neutralRoot;
            public Vector3 neutralMeshWorldMin,neutralMeshWorldMax,neutralMeshWorldSize;
            public string status="not-complete", scope="real-Animator-pose-diagnostics-only", prefab, dependencySha256;
            public bool visualAccepted=false, gameplayAccepted=false;
            public string armoredAttackLoopIntent="Only source-authored Armored Attack loops to cover attackClock>1.2 and normalized CrossFade overrun. Gameplay clock/movement/damage unchanged.";
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
            var evidence=new Evidence{prefab=import.prefab,dependencySha256=import.dependencySha256,graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName};
            var scene=EditorSceneManager.NewPreviewScene();
            GameObject subject=null; RenderTexture target=null; Texture2D pixels=null;
            try
            {
                subject=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(import.prefab),scene);
                // Runtime presenters need real gameplay references. This diagnostic exercises Animator only.
                foreach(var script in subject.GetComponentsInChildren<MonoBehaviour>(true))script.enabled=false;
                var animator=subject.GetComponentInChildren<Animator>();
                // Lock and compare the genuine imported neutral before any Rebind/Update can overwrite it.
                var rootPosition=animator.transform.localPosition;var rootRotation=animator.transform.localRotation;var rootScale=animator.transform.localScale;
                var initialRenderers=subject.GetComponentsInChildren<Renderer>(true).Where(r=>r.enabled && !(r is ParticleSystemRenderer)).ToArray();
                if(initialRenderers.Length==0)throw new InvalidOperationException("Missing neutral geometry.");
                var initialBounds=initialRenderers[0].bounds;foreach(var r in initialRenderers)initialBounds.Encapsulate(r.bounds);
                evidence.neutralRoot=ObserveNeutral(subject,animator,initialRenderers);
                if(contract.kind=="armored")RequireNeutral(contract.bindings.neutralBaseline,evidence.neutralRoot);
                animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;animator.applyRootMotion=false;
                var cameraObject=new GameObject("CandidateReviewCamera"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(cameraObject,scene);
                var camera=cameraObject.AddComponent<Camera>(); camera.scene=scene; camera.backgroundColor=new Color(.12f,.14f,.17f); camera.clearFlags=CameraClearFlags.SolidColor;
                target=new RenderTexture(960,540,24); target.Create(); camera.targetTexture=target;
                pixels=new Texture2D(960,540,TextureFormat.RGB24,false);
                var lightObject=new GameObject("CandidateReviewLight"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(lightObject,scene);
                var light=lightObject.AddComponent<Light>(); light.type=LightType.Directional; light.intensity=2; light.transform.rotation=Quaternion.Euler(40,-30,0);
                camera.transform.position=initialBounds.center+new Vector3(1,.45f,-1).normalized*initialBounds.extents.magnitude*3.2f; camera.transform.LookAt(initialBounds.center); camera.nearClipPlane=.005f; camera.farClipPlane=150;
                var neutralMesh=new Frame();MeasureMeshes(initialRenderers,camera,neutralMesh);
                if(!(neutralMesh.meshWorldSize.x>0 && neutralMesh.meshWorldSize.y>0 && neutralMesh.meshWorldSize.z>0))throw new InvalidOperationException("Degenerate actual neutral mesh world dimensions.");
                evidence.neutralMeshWorldMin=neutralMesh.meshWorldMin;evidence.neutralMeshWorldMax=neutralMesh.meshWorldMax;evidence.neutralMeshWorldSize=neutralMesh.meshWorldSize;
                animator.Rebind();animator.Update(0);
                RequireRootUnchanged();
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
                    if(contract.kind=="armored")
                    {
                        foreach(float cycle in new[]{1f,1.1f})
                        { animator.Play("Base Layer.Attack",0,cycle);animator.Update(0);Capture("Attack-overrun-"+cycle.ToString("0.0",System.Globalization.CultureInfo.InvariantCulture),"Attack",0); }
                        animator.CrossFade("Recover",.12f);Sequence("Attack-1.1-Recover","Recover");
                    }
                    // Explicit Animator reset only. Whole-session restart remains a separate runtime requirement.
                    for(int repeat=0;repeat<2;repeat++) { animator.Rebind(); animator.Play("Base Layer.Idle",0,0); animator.Update(0); Capture("animator-reset-"+repeat,"Idle",0); }
                }
                if(contract.kind=="armored")CandidateWeakPointDiagnostics.Capture(subject,camera,label=>Capture(label,"Recover",0));
                string finalDependencySha=JourneyContentChecks.DependencySha256(import.prefab);
                if(finalDependencySha!=import.dependencySha256)throw new InvalidOperationException("Prefab dependency changed during capture.");
                evidence.dependencySha256=finalDependencySha;
                evidence.status="captured-unreviewed";
                void RequireRootUnchanged()
                {
                    if(!(Vector3.Distance(rootPosition,animator.transform.localPosition)<=.00001f) || !(Quaternion.Angle(rootRotation,animator.transform.localRotation)<=.001f) || !(Vector3.Distance(rootScale,animator.transform.localScale)<=.00001f))
                        throw new InvalidOperationException("Animator sampling changed imported neutral root TRS: expected position="+rootPosition.ToString("G9")+" scale="+rootScale.ToString("G9")+" rotation="+rootRotation.ToString("G9")+"; actual position="+animator.transform.localPosition.ToString("G9")+" scale="+animator.transform.localScale.ToString("G9")+" rotation="+animator.transform.localRotation.ToString("G9")+". Units are not automatically normalized.");
                }
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
                    float positionDelta=Vector3.Distance(rootPosition,animator.transform.localPosition),angleDelta=Quaternion.Angle(rootRotation,animator.transform.localRotation),scaleDelta=Vector3.Distance(rootScale,animator.transform.localScale);
                    RequireRootUnchanged();
                    var frame=new Frame{image=file,imageSha256=imageHash,requestedState=label,advanceSeconds=advance,normalizedTime=info.normalizedTime,stateHash=info.fullPathHash,transitioning=animator.IsInTransition(0),groundDiagnosticApplicable=contract.kind!="weapon",groundReferenceY=subject.transform.position.y,rootLocalPositionDelta=positionDelta,rootLocalAngleDelta=angleDelta,rootLocalScaleDelta=scaleDelta,rootLocalPosition=animator.transform.localPosition,rootLocalRotation=animator.transform.localRotation,rootLocalScale=animator.transform.localScale};
                    MeasureMeshes(renderers,camera,frame);
                    frame.meshSizeRatioToNeutral=new Vector3(frame.meshWorldSize.x/evidence.neutralMeshWorldSize.x,frame.meshWorldSize.y/evidence.neutralMeshWorldSize.y,frame.meshWorldSize.z/evidence.neutralMeshWorldSize.z);
                    evidence.frames.Add(frame);
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
        static JourneyCandidateArtImport.RootNeutralBaseline ObserveNeutral(GameObject subject,Animator animator,Renderer[] renderers)
        {
            if(subject.transform.childCount!=1)throw new InvalidOperationException("Expected one source-model child for neutral paths.");
            var model=subject.transform.GetChild(0);
            return new JourneyCandidateArtImport.RootNeutralBaseline{position=animator.transform.localPosition,rotation=animator.transform.localRotation,scale=animator.transform.localScale,renderers=renderers.Select(r=>new JourneyCandidateArtImport.RendererNeutralBaseline{path=AnimationUtility.CalculateTransformPath(r.transform,model),worldCenter=r.bounds.center,worldExtents=r.bounds.extents}).ToArray()};
        }
        static void RequireNeutral(JourneyCandidateArtImport.RootNeutralBaseline expected,JourneyCandidateArtImport.RootNeutralBaseline actual)
        {
            if(expected==null || expected.renderers==null)throw new InvalidOperationException("Exact Discovery neutral root/render-bounds baseline required.");
            if(!(Vector3.Distance(expected.position,actual.position)<=.00001f) || !(Vector3.Distance(expected.scale,actual.scale)<=.00001f) || !(Quaternion.Angle(expected.rotation,actual.rotation)<=.001f))
                throw new InvalidOperationException("Imported neutral root differs from locked Discovery contract TRS; expected position="+expected.position.ToString("G9")+" scale="+expected.scale.ToString("G9")+" rotation="+expected.rotation.ToString("G9")+"; actual position="+actual.position.ToString("G9")+" scale="+actual.scale.ToString("G9")+" rotation="+actual.rotation.ToString("G9"));
            if(expected.renderers.Length!=actual.renderers.Length || expected.renderers.Select(r=>r.path).Distinct().Count()!=expected.renderers.Length)throw new InvalidOperationException("Neutral renderer inventory differs from Discovery.");
            foreach(var e in expected.renderers)
            {
                var matches=actual.renderers.Where(r=>r.path==e.path).ToArray();
                if(matches.Length!=1 || !(Vector3.Distance(e.worldCenter,matches[0].worldCenter)<=.0001f) || !(Vector3.Distance(e.worldExtents,matches[0].worldExtents)<=.0001f))
                    throw new InvalidOperationException("Neutral world bounds differ from locked Discovery: "+e.path+" expected center="+e.worldCenter.ToString("G9")+" extents="+e.worldExtents.ToString("G9")+"; actual="+(matches.Length==1?("center="+matches[0].worldCenter.ToString("G9")+" extents="+matches[0].worldExtents.ToString("G9")):("matches="+matches.Length))+". Refusing to frame away a scale/pose mismatch.");
            }
        }
        // Actual deformed vertices, not Renderer.bounds. Measurements are diagnostics, not foot-contact approval.
        static void MeasureMeshes(Renderer[] renderers,Camera camera,Frame frame)
        {
            float minY=float.PositiveInfinity;var minimum=Vector3.one*float.PositiveInfinity;var maximum=Vector3.one*float.NegativeInfinity;
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
                            minY=Mathf.Min(minY,world.y);minimum=Vector3.Min(minimum,world);maximum=Vector3.Max(maximum,world);frame.sampledVertices++;
                            var viewport=camera.WorldToViewportPoint(world);
                            if(viewport.z<=0)frame.behindCameraVertices++;
                            if(viewport.z<camera.nearClipPlane || viewport.z>camera.farClipPlane || viewport.x<0 || viewport.x>1 || viewport.y<0 || viewport.y>1)frame.outsideViewportVertices++;
                            if(frame.groundDiagnosticApplicable && world.y<frame.groundReferenceY)frame.belowReferenceVertices++;
                        }
                    }
                    finally { if(temporary)UnityEngine.Object.DestroyImmediate(temporary); }
                }
                if(frame.sampledVertices==0)throw new InvalidOperationException("No mesh diagnostic samples.");
                frame.worldMinY=minY;frame.meshWorldMin=minimum;frame.meshWorldMax=maximum;frame.meshWorldSize=maximum-minimum;writer.Flush();
                using(var sha=System.Security.Cryptography.SHA256.Create())frame.meshPoseSha256=BitConverter.ToString(sha.ComputeHash(bytes.ToArray())).Replace("-","").ToLowerInvariant();
            }
        }
    }
}

