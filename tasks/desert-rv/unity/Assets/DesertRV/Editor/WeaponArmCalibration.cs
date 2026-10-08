using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Editor
{
    public static class WeaponArmCalibration
    {
        // Explicit import/author operation. Caller must have sampled the identified neutral pose first.
        // Never invoked by runtime, OnEnable, or a production validation pass.
        public static bool CaptureCurrentNeutral(WeaponArmReach reach,UnityEngine.Object sourceModel,string poseEvidence,
            float sourceToRigScale,float leftUpper,float leftFore,float rightUpper,float rightFore,
            float positionToleranceRig,float numericToleranceRig,out string reason)
        {
            reason=null;
            if(!reach||!reach.rigRoot||!reach.animator||!sourceModel||string.IsNullOrWhiteSpace(poseEvidence)||
                !WeaponArmReach.UniformPositive(reach.rigRoot,out var scale)||!TwoBoneArmSolver.Finite(positionToleranceRig)||
                !TwoBoneArmSolver.Finite(numericToleranceRig)||numericToleranceRig<=0||positionToleranceRig<numericToleranceRig)
            {reason="Supply actual imported rig/source, known neutral pose and explicit finite tolerances.";return false;}
            string path=AssetDatabase.GetAssetPath(sourceModel);
            if(!path.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase)||!File.Exists(path))
            {reason="Calibration source must be the actual imported FBX asset.";return false;}
            if(!Capture(reach.left,reach.rigRoot,sourceToRigScale,leftUpper,leftFore,positionToleranceRig,numericToleranceRig,poseEvidence,out var left,out reason)||
                !Capture(reach.right,reach.rigRoot,sourceToRigScale,rightUpper,rightFore,positionToleranceRig,numericToleranceRig,poseEvidence,out var right,out reason))return false;
            reach.left=left;reach.right=right;reach.calibratedSourceModel=sourceModel;
            using(var sha=SHA256.Create())reach.sourceSha256=BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();
            reach.positionToleranceRig=positionToleranceRig;reach.numericToleranceRig=numericToleranceRig;
            if(!ValidateSourceAndBinding(reach,out reason)) {left.calibrated=right.calibrated=false;return false;}
            EditorUtility.SetDirty(reach);return true;
        }
        static bool Capture(ArmReachBinding b,Transform rig,float conversion,float sourceUpper,float sourceFore,float tolerance,float epsilon,string pose,
            out ArmReachBinding output,out string reason)
        {
            output=null;reason=null;
            if(b==null||!b.upperArm||!b.forearm||!b.wristTip||!b.wristTarget||b.upperArm.parent!=rig||b.forearm.parent!=b.upperArm||b.wristTip.parent!=b.forearm||
                !b.wristTarget.IsChildOf(rig)||b.wristTarget.IsChildOf(b.upperArm)||!WeaponArmReach.UniformPositive(b.upperArm,out _)||!WeaponArmReach.UniformPositive(b.forearm,out _))
            {reason="Actual imported chain/markers missing or wrong hierarchy.";return false;}
            Vector3 s=rig.InverseTransformPoint(b.upperArm.position),e=rig.InverseTransformPoint(b.forearm.position),w=rig.InverseTransformPoint(b.wristTip.position),t=rig.InverseTransformPoint(b.wristTarget.position);
            float upper=(e-s).magnitude,fore=(w-e).magnitude;
            if(!TwoBoneArmSolver.Finite(s)||!TwoBoneArmSolver.Finite(e)||!TwoBoneArmSolver.Finite(w)||!TwoBoneArmSolver.Finite(t)||
                !TwoBoneArmSolver.Finite(conversion)||!TwoBoneArmSolver.Finite(sourceUpper)||!TwoBoneArmSolver.Finite(sourceFore)||conversion<=0||sourceUpper<=0||sourceFore<=0||
                upper<=epsilon||fore<=epsilon||tolerance>Mathf.Min(upper,fore)*.005f||(w-t).magnitude>tolerance||Mathf.Abs(upper-sourceUpper*conversion)>tolerance||Mathf.Abs(fore-sourceFore*conversion)>tolerance)
            {reason="Neutral seam/length/source-scale cross-check failed; no axis or length guess permitted.";return false;}
            var pole=Vector3.ProjectOnPlane(e-s,(w-s).normalized);
            if(pole.sqrMagnitude<=epsilon*epsilon){reason="Neutral bend pole is degenerate; use a measured non-collinear pose.";return false;}
            output=new ArmReachBinding {upperArm=b.upperArm,forearm=b.forearm,wristTip=b.wristTip,wristTarget=b.wristTarget,calibrated=true,
                upperLengthRig=upper,foreLengthRig=fore,sourceUpperLength=sourceUpper,sourceForeLength=sourceFore,sourceToRigScale=conversion,
                upperAxisLocal=b.forearm.localPosition.normalized,foreAxisLocal=b.wristTip.localPosition.normalized,poleRigLocal=pole.normalized,
                shoulderLocal=b.upperArm.localPosition,elbowLocal=b.forearm.localPosition,tipLocal=b.wristTip.localPosition,
                upperScale=b.upperArm.localScale,foreScale=b.forearm.localScale,upperBindRotation=b.upperArm.localRotation,foreBindRotation=b.forearm.localRotation,neutralPoseEvidence=pose};
            return true;
        }
        public static bool ValidateSourceAndBinding(WeaponArmReach reach,out string reason)
        {
            if(!reach){reason="Missing calibrated arm reach component.";return false;}
            if(!reach.ValidateBindings(out reason))return false;
            string path=AssetDatabase.GetAssetPath(reach.calibratedSourceModel);
            if(!path.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase)||!File.Exists(path)) {reason="Calibrated source FBX unavailable.";return false;}
            bool actualSource=reach.animator.GetComponentsInChildren<SkinnedMeshRenderer>(true).Any(r=>r.sharedMesh&&AssetDatabase.GetAssetPath(r.sharedMesh)==path)||
                reach.animator.GetComponentsInChildren<MeshFilter>(true).Any(f=>f.sharedMesh&&AssetDatabase.GetAssetPath(f.sharedMesh)==path);
            if(!actualSource){reason="Calibration FBX is not an actual mesh dependency of this rig.";return false;}
            using(var sha=SHA256.Create())
                if(BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant()!=reach.sourceSha256)
                {reason="Arm calibration source changed; actual neutral recalibration is required.";return false;}
            if(!reach.animator.runtimeAnimatorController){reason="Missing actual Animator controller for arm motion validation.";return false;}
            foreach(var b in new[]{reach.left,reach.right})
                foreach(var clip in reach.animator.runtimeAnimatorController.animationClips.Distinct())
                    foreach(var binding in AnimationUtility.GetCurveBindings(clip))
                    {
                        Vector3 expected;bool match=false;
                        string upper=AnimationUtility.CalculateTransformPath(b.upperArm,reach.animator.transform);
                        string fore=AnimationUtility.CalculateTransformPath(b.forearm,reach.animator.transform);
                        string tip=AnimationUtility.CalculateTransformPath(b.wristTip,reach.animator.transform);
                        expected=Vector3.zero;
                        if(binding.propertyName.StartsWith("m_LocalPosition",StringComparison.Ordinal))
                        {
                            if(binding.path==upper){expected=b.shoulderLocal;match=true;}
                            else if(binding.path==fore){expected=b.elbowLocal;match=true;}
                            else if(binding.path==tip){expected=b.tipLocal;match=true;}
                        }
                        else if(binding.propertyName.StartsWith("m_LocalScale",StringComparison.Ordinal))
                        {
                            if(binding.path==upper){expected=b.upperScale;match=true;}
                            else if(binding.path==fore){expected=b.foreScale;match=true;}
                        }
                        if(!match)continue;
                        int axis=binding.propertyName.EndsWith(".x",StringComparison.Ordinal)?0:binding.propertyName.EndsWith(".y",StringComparison.Ordinal)?1:binding.propertyName.EndsWith(".z",StringComparison.Ordinal)?2:-1;
                        var curve=AnimationUtility.GetEditorCurve(clip,binding);
                        if(axis<0||curve==null||curve.keys.Any(k=>!TwoBoneArmSolver.Finite(k.value)||Mathf.Abs(k.value-expected[axis])>reach.numericToleranceRig||
                            float.IsNaN(k.inTangent)||float.IsNaN(k.outTangent)||
                            (TwoBoneArmSolver.Finite(k.inTangent)&&Mathf.Abs(k.inTangent)>reach.numericToleranceRig)||
                            (TwoBoneArmSolver.Finite(k.outTangent)&&Mathf.Abs(k.outTangent)>reach.numericToleranceRig)))
                        {reason="Arm clip translates/stretches a calibrated fixed joint: "+clip.name+" / "+binding.path+" / "+binding.propertyName;return false;}
                    }
            return true;
        }
    }
}
