using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEngine;
using static DesertRV.Editor.JourneyCandidateArtImport;

namespace DesertRV.Editor
{
    // Candidate-only mechanics sampling of the real Animator and skin rig.
    // Gameplay reload commits, actions, shot raycasts and scene camera remain separate gates.
    public static class CandidateWeaponDiagnostics
    {
        [Serializable] public sealed class Sample
        {
            public string state,animatorPoseSha256;public float normalized;
            public int loadedBefore,plannedAdded;
            public bool ikApplied,poseAccepted;
            public ArmReachDiagnostics left,right;
            public Vector3 incomingLocalOffset,leftLocalOffset,worldPitch,subjectWorldPosition;
            public Quaternion subjectWorldRotation;
        }
        [Serializable] public sealed class Readback
        {
            public string status="not-complete";
            public bool mechanicsPassed=false,gameplayAccepted=false,visualAccepted=false,sceneCalibrated=false;
            public string scope="Real imported Animator and actual presenter count projection. Reload alone applies runtime fixed-length IK; Idle/Fire are measured without extra correction. No gameplay commit/FX/reticle acceptance.";
            public int sampleRateHz=200;
            public float maxWristGapWorld,maxShoulderDriftWorld,maxTargetDriftWorld;
            public List<Sample> samples=new List<Sample>();
            public List<string> failures=new List<string>();
        }
        public static void Prepare(GameObject subject)
        {
            var p=subject.GetComponent<WeaponPresentation>();Check(p&&p.armReach&&p.animator,"Real candidate weapon calibration required.");
            foreach(var nail in p.loadedNails)nail.enabled=true;
            foreach(var nail in p.incomingNails)nail.enabled=false;
        }
        public static void Capture(GameObject subject,Readback result,Action<string,string> captureImage,ClipSpec[] clipSpecs)
        {
            var p=subject.GetComponent<WeaponPresentation>();Check(p&&p.armReach&&p.animator,"Real candidate weapon binding required.");
            var reach=p.armReach;var animator=p.animator;animator.speed=0;
            var poseTransforms=animator.GetComponentsInChildren<Transform>(true);
            Check(WeaponArmCalibration.ValidateSourceAndBinding(reach,out string bindingReason),bindingReason);
            Vector3 incomingRest=p.incomingOffset.localPosition,leftRest=p.leftReloadOffset.localPosition;
            Vector3 subjectPosition=subject.transform.position;Quaternion subjectRotation=subject.transform.rotation;
            try
            {
                // Every feasible loaded-before count at 200 Hz; extra 3+5 is a partial-reserve case.
                for(int before=0;before<12;before++)Dense(before,12-before);
                Dense(3,5);
                // Real regional positions expose float quantization hidden by an origin-only test.
                // Keep the imported scale-100 rig; move/rotate only the outer instance as a camera would.
                foreach(float distance in new[]{0f,100f,200f})foreach(Vector3 angles in new[]{Vector3.zero,new Vector3(12,37,-4),new Vector3(-18,143,6)})
                {
                    subject.transform.position=subjectPosition+Vector3.right*distance;
                    subject.transform.rotation=subjectRotation*Quaternion.Euler(angles);
                    foreach(var scenario in new[]{new[]{0,12},new[]{3,5},new[]{11,1}})
                        foreach(float t in new[]{0f,34f/99f,54f/99f,67f/99f,1f})Measure("Reload",t,scenario[0],scenario[1]);
                }
                subject.transform.SetPositionAndRotation(subjectPosition,subjectRotation);
                foreach(string state in new[]{"Idle","Fire"})foreach(float t in new[]{0f,.25f,.5f,.75f,.999f})
                {Measure(state,t,12,0);captureImage(state+"-"+F(t),state);}
                foreach(var scenario in new[]{new[]{0,12},new[]{3,5},new[]{11,1}})
                    foreach(float t in new[]{0f,34f/99f,54f/99f,67f/99f,1f})
                    {Measure("Reload",t,scenario[0],scenario[1]);captureImage("Reload-"+scenario[0]+"-plus-"+scenario[1]+"-"+F(t),"Reload");}
                foreach(var clip in clipSpecs)
                    if(clip.poseExpectation=="varying")Check(result.samples.Where(s=>s.state==clip.state).Select(s=>s.animatorPoseSha256).Distinct().Count()>1,
                        "Contract expected real Animator pose variation BEFORE count projection/IK: "+clip.state);
                result.status="imported-arm-count-mechanics-passed-unreviewed";result.mechanicsPassed=true;
            }
            catch(Exception error){result.failures.Add(error.Message);result.status="failed-imported-arm-count-mechanics";throw;}
            finally
            {
                subject.transform.SetPositionAndRotation(subjectPosition,subjectRotation);
                reach.RestoreBindPose();p.incomingOffset.localPosition=incomingRest;p.leftReloadOffset.localPosition=leftRest;
                animator.Play("Base Layer.Idle",0,0);animator.Update(0);Prepare(subject);
            }
            void Dense(int before,int added)
            {
                for(int step=0;step<=330;step++)Measure("Reload",step/330f,before,added);
            }
            void Measure(string state,float normalized,int before,int added)
            {
                // Exact runtime ordering: restore omitted arm rotations, Animator, absolute carriers, arms.
                reach.RestoreBindPose();p.incomingOffset.localPosition=incomingRest;p.leftReloadOffset.localPosition=leftRest;
                animator.Play("Base Layer."+state,0,normalized);animator.Update(0);
                Check(animator.GetCurrentAnimatorStateInfo(0).fullPathHash==Animator.StringToHash("Base Layer."+state),"Actual Animator failed to enter "+state);
                Check(Vector3.Distance(p.incomingOffset.localPosition,incomingRest)<=reach.numericToleranceRig&&
                    Vector3.Distance(p.leftReloadOffset.localPosition,leftRest)<=reach.numericToleranceRig,"Animator overwrote a runtime-owned count carrier.");
                string animatorPose=PoseHash(poseTransforms);
                bool reload=state=="Reload";
                p.ApplyCandidateCountPose(reload,before,added,normalized,incomingRest,leftRest);
                Vector3 strip=p.incomingOffset.localPosition-incomingRest,hand=p.leftReloadOffset.localPosition-leftRest;
                ArmReachDiagnostics left,right;bool poseAccepted;string reason;
                if(reload)
                {
                    bool solved=reach.TrySolveBoth(out reason);left=reach.LeftDiagnostics;right=reach.RightDiagnostics;
                    poseAccepted=solved&&left.solved&&right.solved&&left.measured&&right.measured&&left.measurementsFinite&&right.measurementsFinite;
                }
                else
                {
                    // Runtime SolveArms returns immediately outside reload. Do NOT repair Idle/Fire here.
                    bool bindingValid=reach.ValidateBindings(out reason);
                    bool scaleValid=WeaponArmReach.UniformPositive(reach.rigRoot,out float scale);
                    left=ObserveAnimatorArm(reach.left,reach.rigRoot,scale);right=ObserveAnimatorArm(reach.right,reach.rigRoot,scale);
                    poseAccepted=bindingValid&&scaleValid&&ObservedWithinTolerance(left,reach.positionToleranceRig*scale,reach.numericToleranceRig*scale)&&
                        ObservedWithinTolerance(right,reach.positionToleranceRig*scale,reach.numericToleranceRig*scale);
                    if(bindingValid)reason=poseAccepted?"Measured unmodified Animator pose; no IK applied.":"Unmodified Animator wrist/segment/shoulder residual failed; no diagnostic IK correction permitted.";
                }
                var sample=new Sample{state=state,animatorPoseSha256=animatorPose,normalized=normalized,loadedBefore=before,plannedAdded=added,ikApplied=reload,poseAccepted=poseAccepted,left=left,right=right,
                    incomingLocalOffset=strip,leftLocalOffset=hand,worldPitch=p.incomingOffset.parent.TransformVector(p.nailPitch),subjectWorldPosition=subject.transform.position,subjectWorldRotation=subject.transform.rotation};
                result.samples.Add(sample);
                result.maxWristGapWorld=Mathf.Max(result.maxWristGapWorld,sample.left.wristGap,sample.right.wristGap);
                result.maxShoulderDriftWorld=Mathf.Max(result.maxShoulderDriftWorld,sample.left.shoulderDrift,sample.right.shoulderDrift);
                result.maxTargetDriftWorld=Mathf.Max(result.maxTargetDriftWorld,sample.left.targetDrift,sample.right.targetDrift);
                bool accepted=sample.poseAccepted;
                if(!accepted)
                    try {captureImage("FAILED-"+state+"-"+before+"-plus-"+added+"-"+F(normalized),state);}
                    catch(Exception frameError){result.failures.Add("Failure-frame capture: "+frameError.Message);}
                Check(accepted,"Imported "+state+" count "+before+"+"+added+" normalized "+F(normalized)+" world="+subject.transform.position+" failed runtime-matching arm check (IK="+reload+"): "+reason+" LEFT "+Metrics(sample.left)+" RIGHT "+Metrics(sample.right));
            }
        }
        static ArmReachDiagnostics ObserveAnimatorArm(ArmReachBinding arm,Transform rig,float scale)
        {
            // Read only: retain solved=false to distinguish observation from an executed IK solve.
            Vector3 shoulder=arm.upperArm.position,elbow=arm.forearm.position,tip=arm.wristTip.position,target=arm.wristTarget.position;
            var d=new ArmReachDiagnostics{measured=true,solved=false,expectedUpperLength=arm.upperLengthRig*scale,expectedForeLength=arm.foreLengthRig*scale,
                upperLength=Vector3.Distance(shoulder,elbow),foreLength=Vector3.Distance(elbow,tip),wristGap=Vector3.Distance(tip,target),
                shoulderDrift=Vector3.Distance(shoulder,rig.TransformPoint(arm.shoulderLocal)),targetDrift=0,targetDistance=Vector3.Distance(shoulder,target),
                reason="Unmodified Animator pose observed; no IK executed."};
            d.measurementsFinite=Finite(d.expectedUpperLength)&&Finite(d.expectedForeLength)&&Finite(d.upperLength)&&Finite(d.foreLength)&&
                Finite(d.wristGap)&&Finite(d.shoulderDrift)&&Finite(d.targetDistance);
            if(!d.measurementsFinite)
            {
                d.reason="Nonfinite unmodified Animator measurements.";
                d.expectedUpperLength=Clean(d.expectedUpperLength);d.expectedForeLength=Clean(d.expectedForeLength);
                d.upperLength=Clean(d.upperLength);d.foreLength=Clean(d.foreLength);d.wristGap=Clean(d.wristGap);
                d.shoulderDrift=Clean(d.shoulderDrift);d.targetDistance=Clean(d.targetDistance);
            }
            return d;
        }
        static bool ObservedWithinTolerance(ArmReachDiagnostics d,float positionTolerance,float numericTolerance)
            =>d.measured&&d.measurementsFinite&&Mathf.Abs(d.upperLength-d.expectedUpperLength)<=positionTolerance&&
                Mathf.Abs(d.foreLength-d.expectedForeLength)<=positionTolerance&&d.wristGap<=positionTolerance&&d.shoulderDrift<=numericTolerance;
        static bool Finite(float value)=>!float.IsNaN(value)&&!float.IsInfinity(value);
        static float Clean(float value)=>Finite(value)?value:0;
        static string PoseHash(Transform[] transforms)
        {
            using(var stream=new MemoryStream())using(var writer=new BinaryWriter(stream))
            {
                foreach(var t in transforms)
                {
                    var p=t.localPosition;var q=t.localRotation;var s=t.localScale;
                    foreach(float value in new[]{p.x,p.y,p.z,q.x,q.y,q.z,q.w,s.x,s.y,s.z})
                    {Check(!float.IsNaN(value)&&!float.IsInfinity(value),"Nonfinite actual Animator transform.");writer.Write(value);}
                }
                writer.Flush();using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(stream.ToArray())).Replace("-","").ToLowerInvariant();
            }
        }
        static string Metrics(ArmReachDiagnostics d)=>"measured="+d.measured+" finite="+d.measurementsFinite+" solved="+d.solved+
            " upper="+F(d.upperLength)+"/"+F(d.expectedUpperLength)+" fore="+F(d.foreLength)+"/"+F(d.expectedForeLength)+
            " wristGap="+F(d.wristGap)+" shoulderDrift="+F(d.shoulderDrift)+" targetDrift="+F(d.targetDrift)+" targetDistance="+F(d.targetDistance)+" reason="+d.reason;
        static string F(float value)=>value.ToString("0.000000",System.Globalization.CultureInfo.InvariantCulture);
    }
}
