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
            public CandidateWeaponDiagnostics.Readback weapon;
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
            GameObject subject=null; RenderTexture target=null; Texture2D pixels=null; Camera camera=null;
            var totalMeasurement=new MeshMeasurementSummary();
            try
            {
                subject=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(import.prefab),scene);
                // Runtime presenters need real gameplay references. This diagnostic exercises Animator only.
                foreach(var script in subject.GetComponentsInChildren<MonoBehaviour>(true))script.enabled=false;
                var animator=subject.GetComponentInChildren<Animator>();
                // Lock and compare the genuine imported neutral before any Rebind/Update can overwrite it.
                var rootPosition=animator.transform.localPosition;var rootRotation=animator.transform.localRotation;var rootScale=animator.transform.localScale;
                if(contract.kind=="weapon")CandidateWeaponDiagnostics.Prepare(subject);
                var initialRenderers=subject.GetComponentsInChildren<Renderer>(true).Where(r=>r.enabled && !(r is ParticleSystemRenderer)).ToArray();
                if(initialRenderers.Length==0)throw new InvalidOperationException("Missing neutral geometry.");
                var initialBounds=initialRenderers[0].bounds;foreach(var r in initialRenderers)initialBounds.Encapsulate(r.bounds);
                evidence.neutralRoot=ObserveNeutral(subject,animator,initialRenderers);
                if(contract.kind=="armored" || contract.kind=="pouncer")RequireNeutral(contract.bindings.neutralBaseline,evidence.neutralRoot);
                animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;animator.applyRootMotion=false;
                var cameraObject=new GameObject("CandidateReviewCamera"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(cameraObject,scene);
                camera=cameraObject.AddComponent<Camera>(); camera.scene=scene; camera.backgroundColor=new Color(.12f,.14f,.17f); camera.clearFlags=CameraClearFlags.SolidColor;
                target=new RenderTexture(960,540,24); target.Create(); camera.targetTexture=target;
                pixels=new Texture2D(960,540,TextureFormat.RGB24,false);
                var lightObject=new GameObject("CandidateReviewLight"); UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(lightObject,scene);
                var light=lightObject.AddComponent<Light>(); light.type=LightType.Directional; light.intensity=2; light.transform.rotation=Quaternion.Euler(40,-30,0);
                camera.transform.position=initialBounds.center+new Vector3(1,.45f,-1).normalized*initialBounds.extents.magnitude*3.2f; camera.transform.LookAt(initialBounds.center); camera.nearClipPlane=.005f; camera.farClipPlane=150;
                var neutralMesh=new Frame();var neutralMeasurement=MeasureMeshes(initialRenderers,camera,neutralMesh);
                totalMeasurement.Add(neutralMeasurement);LogMeshMeasurement("neutral",neutralMeasurement);
                if(contract.kind!="weapon")LogSkinProbe("neutral-before-rebind",subject,initialRenderers);
                if(!(neutralMesh.meshWorldSize.x>0 && neutralMesh.meshWorldSize.y>0 && neutralMesh.meshWorldSize.z>0))throw new InvalidOperationException("Degenerate actual neutral mesh world dimensions.");
                evidence.neutralMeshWorldMin=neutralMesh.meshWorldMin;evidence.neutralMeshWorldMax=neutralMesh.meshWorldMax;evidence.neutralMeshWorldSize=neutralMesh.meshWorldSize;
                animator.Rebind();animator.Update(0);
                RequireRootUnchanged();
                var states=((AnimatorController)animator.runtimeAnimatorController).layers[0].stateMachine.states.Select(x=>x.state.name).ToArray();
                if(contract.kind=="weapon")
                {
                    evidence.notCovered[1]="Authoritative gameplay interruptions and reload commits";
                    evidence.weapon=new CandidateWeaponDiagnostics.Readback();
                    var fixedLocalCameraPosition=subject.transform.InverseTransformPoint(camera.transform.position);
                    var fixedLocalCameraRotation=Quaternion.Inverse(subject.transform.rotation)*camera.transform.rotation;
                    CandidateWeaponDiagnostics.Capture(subject,evidence.weapon,(label,state)=>
                    {
                        // Same instance-relative view/projection at 0/100/200m; no per-pose reframing.
                        camera.transform.SetPositionAndRotation(subject.transform.TransformPoint(fixedLocalCameraPosition),subject.transform.rotation*fixedLocalCameraRotation);
                        Capture(label,state,0);
                    },contract.clips);
                }
                else foreach(string state in states)
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
                LogMeshMeasurement("completed",totalMeasurement);
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
                    var measurement=MeasureMeshes(renderers,camera,frame);totalMeasurement.Add(measurement);
                    frame.meshSizeRatioToNeutral=new Vector3(frame.meshWorldSize.x/evidence.neutralMeshWorldSize.x,frame.meshWorldSize.y/evidence.neutralMeshWorldSize.y,frame.meshWorldSize.z/evidence.neutralMeshWorldSize.z);
                    evidence.frames.Add(frame);
                    bool firstFrame=evidence.frames.Count==1;
                    bool failedGround=frame.groundDiagnosticApplicable && frame.worldMinY<frame.groundReferenceY-.004f;
                    if(firstFrame || failedGround)LogMeshMeasurement(failedGround?"first-ground-failure":"first-frame",measurement);
                    if(frame.groundDiagnosticApplicable && (evidence.frames.Count==1 || frame.worldMinY<frame.groundReferenceY-.004f))
                        LogSkinProbe(frame.requestedState,subject,renderers);
                    if(frame.groundDiagnosticApplicable && frame.worldMinY<frame.groundReferenceY-.004f)
                        throw new InvalidOperationException("Ground penetration exceeds 0.004m: "+frame.requestedState+" minY="+frame.worldMinY.ToString("G9")+" referenceY="+frame.groundReferenceY.ToString("G9"));
                }
            }
            finally
            {
                try { File.WriteAllText("JourneyEvidence/CandidateArt/capture-report.json",JsonUtility.ToJson(evidence,true)); }
                finally
                {
                    try { ReleaseCandidateRenderTarget(camera,target); }
                    finally
                    {
                        try { if(pixels)UnityEngine.Object.DestroyImmediate(pixels); }
                        finally { EditorSceneManager.ClosePreviewScene(scene); }
                    }
                }
                // No normal scene opened or saved.
            }
        }
        static void ReleaseCandidateRenderTarget(Camera camera,RenderTexture target)
        {
            try
            {
                if(camera && camera.targetTexture==target)camera.targetTexture=null;
                if(RenderTexture.active==target)RenderTexture.active=null;
            }
            finally
            {
                if(target) {try {target.Release();}finally {UnityEngine.Object.DestroyImmediate(target);}}
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
        [Serializable] sealed class SkinProbeInfluence
        {
            public int boneIndex;public float weight;public string path;
            public Vector3 position,scale;public Quaternion rotation;
            public float[] localToWorld,bindPose;public Vector3 weightedWorld;
        }
        [Serializable] sealed class SkinProbe
        {
            public string phase,rendererPath,rendererType,quality,rigPath,status="observed-not-acceptance";
            public int vertexIndex,influenceCount,blendShapeCount;public bool complete;
            public bool animatorInTransition;public int currentStateHash,nextStateHash;
            public float currentNormalizedTime,currentLength,currentSpeed,currentSpeedMultiplier;
            public float nextNormalizedTime,nextLength,nextSpeed,nextSpeedMultiplier,transitionNormalizedTime,transitionDuration;
            public string transitionDurationUnit;
            public Vector3 bakedLocal,bakedWorld,sourceLocal,weightedWorld;
            public string bakedCoordinateConvention="legacy-false-times-renderer-TRS-observation-only",selectionConvention="minimum-verified-world-vertex";
            public Vector3 measuredWorld;
            public Vector3 compensatedBakedLocal,compensatedBakedWorld;public float compensatedVersusWeightedDistance;
            public Vector3 rendererLocalPosition,rendererLocalScale,rendererLossyScale,rigLocalPosition,rigLocalScale;
            public Quaternion rendererLocalRotation,rigLocalRotation;
            public float[] rendererLocalToWorld,rigLocalToWorld;
            public float weightSum,bakedVersusWeightedDistance;
            public List<SkinProbeInfluence> influences=new List<SkinProbeInfluence>();
        }
        static float[] ProbeMatrix(Matrix4x4 m)
        {
            var values=new float[16];for(int row=0;row<4;row++)for(int col=0;col<4;col++)values[row*4+col]=m[row,col];return values;
        }
        // Bounded public-asset numeric observation only; never changes the quality gate or source pose.
        // Independent linear skinning excludes blend shapes, explicitly reported below.
        static void LogSkinProbe(string phase,GameObject subject,Renderer[] renderers)
        {
            try
            {
                Renderer worst=null;int index=-1;Vector3 measuredWorld=default;float min=float.PositiveInfinity;
                foreach(var renderer in renderers)
                {
                    var world=JourneyCandidateMeshMeasurement.GetWorldVertices(renderer,out _,out _);
                    for(int i=0;i<world.Length;i++)
                        if(world[i].y<min){min=world[i].y;worst=renderer;index=i;measuredWorld=world[i];}
                }
                if(!worst){Debug.Log("CANDIDATE_SKIN_PROBE unavailable-no-readable-vertex");return;}
                var t=worst.transform;Vector3 bakedLocal;Mesh temporary=null;
                try
                {
                    Mesh mesh;
                    if(worst is SkinnedMeshRenderer skin){temporary=new Mesh();skin.BakeMesh(temporary,false);mesh=temporary;}
                    else {var filter=worst.GetComponent<MeshFilter>();mesh=filter?filter.sharedMesh:null;}
                    bakedLocal=mesh.vertices[index];
                }
                finally {if(temporary)UnityEngine.Object.DestroyImmediate(temporary);}
                var bakedWorld=t.TransformPoint(bakedLocal);
                var probe=new SkinProbe{phase=phase,rendererPath=AnimationUtility.CalculateTransformPath(t,subject.transform),rendererType=worst.GetType().Name,vertexIndex=index,measuredWorld=measuredWorld,bakedLocal=bakedLocal,bakedWorld=bakedWorld,rendererLocalPosition=t.localPosition,rendererLocalRotation=t.localRotation,rendererLocalScale=t.localScale,rendererLossyScale=t.lossyScale,rendererLocalToWorld=ProbeMatrix(t.localToWorldMatrix)};
                var animator=subject.GetComponentInChildren<Animator>();
                if(animator && animator.runtimeAnimatorController && animator.layerCount>0)
                {
                    var current=animator.GetCurrentAnimatorStateInfo(0);probe.animatorInTransition=animator.IsInTransition(0);
                    probe.currentStateHash=current.fullPathHash;probe.currentNormalizedTime=current.normalizedTime;probe.currentLength=current.length;probe.currentSpeed=current.speed;probe.currentSpeedMultiplier=current.speedMultiplier;
                    if(probe.animatorInTransition)
                    {
                        var next=animator.GetNextAnimatorStateInfo(0);var transition=animator.GetAnimatorTransitionInfo(0);
                        probe.nextStateHash=next.fullPathHash;probe.nextNormalizedTime=next.normalizedTime;probe.nextLength=next.length;probe.nextSpeed=next.speed;probe.nextSpeedMultiplier=next.speedMultiplier;
                        probe.transitionNormalizedTime=transition.normalizedTime;probe.transitionDuration=transition.duration;probe.transitionDurationUnit=transition.durationUnit.ToString();
                    }
                }
                var rig=subject.GetComponentsInChildren<Transform>(true).FirstOrDefault(x=>x.name=="Pouncer_Rig" || x.name=="Bulwark_Rig");
                if(rig){probe.rigPath=AnimationUtility.CalculateTransformPath(rig,subject.transform);probe.rigLocalPosition=rig.localPosition;probe.rigLocalRotation=rig.localRotation;probe.rigLocalScale=rig.localScale;probe.rigLocalToWorld=ProbeMatrix(rig.localToWorldMatrix);}
                if(worst is SkinnedMeshRenderer skinned)
                {
                    var mesh=skinned.sharedMesh;var bones=skinned.bones;var poses=mesh.bindposes;
                    probe.sourceLocal=mesh.vertices[index];probe.blendShapeCount=mesh.blendShapeCount;probe.quality=skinned.quality.ToString()+"/"+QualitySettings.skinWeights;
                    // Borrowed Mesh-owned Allocator.None views: read only, never Dispose.
                    var counts=mesh.GetBonesPerVertex();var weights=mesh.GetAllBoneWeights();
                    {
                        int offset=0;for(int i=0;i<index;i++)offset+=counts[i];
                        probe.influenceCount=counts[index];probe.complete=probe.influenceCount<=16 && probe.blendShapeCount==0;
                        for(int i=0;i<probe.influenceCount;i++)
                        {
                            var bw=weights[offset+i];var bone=bones[bw.boneIndex];
                            var world=bone.localToWorldMatrix.MultiplyPoint3x4(poses[bw.boneIndex].MultiplyPoint3x4(probe.sourceLocal))*bw.weight;
                            probe.weightedWorld+=world;probe.weightSum+=bw.weight;
                            if(i<16)probe.influences.Add(new SkinProbeInfluence{boneIndex=bw.boneIndex,weight=bw.weight,path=AnimationUtility.CalculateTransformPath(bone,subject.transform),position=bone.localPosition,rotation=bone.localRotation,scale=bone.localScale,localToWorld=ProbeMatrix(bone.localToWorldMatrix),bindPose=ProbeMatrix(poses[bw.boneIndex]),weightedWorld=world});
                        }
                        probe.bakedVersusWeightedDistance=Vector3.Distance(probe.bakedWorld,probe.weightedWorld);
                        var compensated=new Mesh();
                        try
                        {
                            skinned.BakeMesh(compensated,true);probe.compensatedBakedLocal=compensated.vertices[index];
                            probe.compensatedBakedWorld=t.TransformPoint(probe.compensatedBakedLocal);
                            probe.compensatedVersusWeightedDistance=Vector3.Distance(probe.compensatedBakedWorld,probe.weightedWorld);
                        }
                        finally {UnityEngine.Object.DestroyImmediate(compensated);}
                    }
                }
                else {probe.complete=true;probe.sourceLocal=bakedLocal;probe.weightedWorld=bakedWorld;}
                Debug.Log("CANDIDATE_SKIN_PROBE "+JsonUtility.ToJson(probe));
            }
            catch(Exception ex)
            {
                // Diagnostic failure does not mask the original native quality failure or leak raw paths/stack traces.
                Debug.Log("CANDIDATE_SKIN_PROBE unavailable-"+ex.GetType().Name);
            }
        }

        [Serializable] sealed class MeshMeasurementSummary
        {
            public string phase,method="BakeMeshTrueWorldCheckedAgainstFullDoubleLbsNoBlendShapesAutoUnlimited";
            public int rendererCount,vertexCount,verifiedSkinVertices;
            public float maximumErrorMetres,maximumToleranceMetres;
            public void Add(MeshMeasurementSummary sample)
            {
                rendererCount+=sample.rendererCount;vertexCount+=sample.vertexCount;verifiedSkinVertices+=sample.verifiedSkinVertices;
                maximumErrorMetres=Mathf.Max(maximumErrorMetres,sample.maximumErrorMetres);
                maximumToleranceMetres=Mathf.Max(maximumToleranceMetres,sample.maximumToleranceMetres);
            }
        }
        static void LogMeshMeasurement(string phase,MeshMeasurementSummary measurement)
        {
            measurement.phase=phase;Debug.Log("CANDIDATE_MESH_MEASUREMENT "+JsonUtility.ToJson(measurement));
        }

        // Actual deformed vertices, not Renderer.bounds. Measurements are diagnostics, not foot-contact approval.
        static MeshMeasurementSummary MeasureMeshes(Renderer[] renderers,Camera camera,Frame frame)
        {
            var measurement=new MeshMeasurementSummary();
            float minY=float.PositiveInfinity;var minimum=Vector3.one*float.PositiveInfinity;var maximum=Vector3.one*float.NegativeInfinity;
            using(var bytes=new MemoryStream()) using(var writer=new BinaryWriter(bytes))
            {
                foreach(var renderer in renderers)
                {
                    // Full vertex inventory. A failed independent skin comparison throws before any
                    // diagnostic uses the disputed coordinate convention; no fallback or rescaling.
                    var worldVertices=JourneyCandidateMeshMeasurement.GetWorldVertices(renderer,out var skinningError,out var tolerance);
                    measurement.rendererCount++;measurement.vertexCount+=worldVertices.Length;
                    measurement.maximumErrorMetres=Mathf.Max(measurement.maximumErrorMetres,skinningError);
                    measurement.maximumToleranceMetres=Mathf.Max(measurement.maximumToleranceMetres,tolerance);
                    if(renderer is SkinnedMeshRenderer)measurement.verifiedSkinVertices+=worldVertices.Length;
                    writer.Write(renderer.name);
                    foreach(var world in worldVertices)
                    {
                        writer.Write(world.x);writer.Write(world.y);writer.Write(world.z);
                        minY=Mathf.Min(minY,world.y);minimum=Vector3.Min(minimum,world);maximum=Vector3.Max(maximum,world);frame.sampledVertices++;
                        var viewport=camera.WorldToViewportPoint(world);
                        if(viewport.z<=0)frame.behindCameraVertices++;
                        if(viewport.z<camera.nearClipPlane || viewport.z>camera.farClipPlane || viewport.x<0 || viewport.x>1 || viewport.y<0 || viewport.y>1)frame.outsideViewportVertices++;
                        if(frame.groundDiagnosticApplicable && world.y<frame.groundReferenceY)frame.belowReferenceVertices++;
                    }
                }
                if(frame.sampledVertices==0)throw new InvalidOperationException("No mesh diagnostic samples.");
                frame.worldMinY=minY;frame.meshWorldMin=minimum;frame.meshWorldMax=maximum;frame.meshWorldSize=maximum-minimum;writer.Flush();

                using(var sha=System.Security.Cryptography.SHA256.Create())frame.meshPoseSha256=BitConverter.ToString(sha.ComputeHash(bytes.ToArray())).Replace("-","").ToLowerInvariant();
            }
            return measurement;
        }
    }
}

