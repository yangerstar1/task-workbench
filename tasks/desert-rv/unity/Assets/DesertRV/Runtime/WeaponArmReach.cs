using System;
using UnityEngine;

namespace DesertRV
{
    [Serializable]
    public sealed class ArmReachBinding
    {
        public Transform upperArm,forearm,wristTip,wristTarget;
        // Written only by explicit import-time calibration in a known neutral pose.
        public bool calibrated;
        public float upperLengthRig,foreLengthRig,sourceUpperLength,sourceForeLength,sourceToRigScale;
        public Vector3 upperAxisLocal,foreAxisLocal,poleRigLocal;
        public Vector3 shoulderLocal,elbowLocal,tipLocal,upperScale,foreScale;
        public Quaternion upperBindRotation,foreBindRotation;
        public string neutralPoseEvidence;
    }
    [Serializable]
    public struct ArmReachDiagnostics
    {
        public bool solved,measured,measurementsFinite;
        public float upperLength,foreLength,wristGap,shoulderDrift,targetDrift,targetDistance,expectedUpperLength,expectedForeLength;
        public string reason;
    }
    public struct ArmReachFailureReport
    {
        public int generation,epoch,reloadSequence,loadedBefore,plannedAdded,unityFrame;
        public float normalizedReload;
        public string reason;
        public ArmReachDiagnostics left,right;
    }
    [DisallowMultipleComponent]
    public sealed class WeaponArmReach : MonoBehaviour
    {
        public Animator animator;
        public Transform rigRoot;
        public ArmReachBinding left=new ArmReachBinding(),right=new ArmReachBinding();
        public UnityEngine.Object calibratedSourceModel;
        public string sourceSha256;
        // Explicit import policy values, not silently derived/defaulted at runtime.
        public float positionToleranceRig,numericToleranceRig;
        public bool LastSolveAccepted {get;private set;}
        public ArmReachDiagnostics LeftDiagnostics {get;private set;}
        public ArmReachDiagnostics RightDiagnostics {get;private set;}

        static bool QFinite(Quaternion q)=>TwoBoneArmSolver.Finite(q.x)&&TwoBoneArmSolver.Finite(q.y)&&TwoBoneArmSolver.Finite(q.z)&&TwoBoneArmSolver.Finite(q.w)&&Mathf.Abs(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w-1)<.002f;
        static bool Unit(Vector3 v)=>TwoBoneArmSolver.Finite(v)&&Mathf.Abs(v.magnitude-1)<.002f;
        public static bool UniformPositive(Transform t,out float scale)
        {
            scale=0;if(!t)return false;var m=t.localToWorldMatrix;
            for(int i=0;i<16;i++)if(!TwoBoneArmSolver.Finite(m[i]))return false;
            var x=m.MultiplyVector(Vector3.right);var y=m.MultiplyVector(Vector3.up);var z=m.MultiplyVector(Vector3.forward);
            if(!TwoBoneArmSolver.Finite(x)||!TwoBoneArmSolver.Finite(y)||!TwoBoneArmSolver.Finite(z))return false;
            scale=x.magnitude;if(scale<=.000001f||m.determinant<=0)return false;
            return Mathf.Abs(y.magnitude-scale)<=scale*.0001f&&Mathf.Abs(z.magnitude-scale)<=scale*.0001f&&
                Mathf.Abs(Vector3.Dot(x.normalized,y.normalized))<.0001f&&Mathf.Abs(Vector3.Dot(x.normalized,z.normalized))<.0001f&&Mathf.Abs(Vector3.Dot(y.normalized,z.normalized))<.0001f;
        }
        public bool ValidateBindings(out string reason)
        {
            reason=null;
            if(!animator||!rigRoot||!rigRoot.IsChildOf(animator.transform)||!UniformPositive(rigRoot,out _)||
                !calibratedSourceModel||string.IsNullOrWhiteSpace(sourceSha256)||sourceSha256.Length!=64||
                !TwoBoneArmSolver.Finite(positionToleranceRig)||!TwoBoneArmSolver.Finite(numericToleranceRig)||
                numericToleranceRig<=0||positionToleranceRig<numericToleranceRig)
            {reason="Arm reach requires explicit source/pose calibration, tolerances and a uniform positive rig.";return false;}
            if(!ValidateArm(left,out reason)||!ValidateArm(right,out reason))return false;
            var leftNodes=new[]{left.upperArm,left.forearm,left.wristTip,left.wristTarget};
            var rightNodes=new[]{right.upperArm,right.forearm,right.wristTip,right.wristTarget};
            foreach(var l in leftNodes) foreach(var r in rightNodes)
                if(l==r||l.IsChildOf(r)||r.IsChildOf(l))
                {reason="Left/right upper, forearm, tip and target branches must not share or cross-bind nodes.";return false;}
            return true;
        }
        bool ValidateArm(ArmReachBinding b,out string reason)
        {
            reason=null;
            if(b==null||!b.calibrated||string.IsNullOrWhiteSpace(b.neutralPoseEvidence)||!b.upperArm||!b.forearm||!b.wristTip||!b.wristTarget||
                b.upperArm.parent!=rigRoot||b.forearm.parent!=b.upperArm||b.wristTip.parent!=b.forearm||
                !b.wristTarget.IsChildOf(rigRoot)||b.wristTarget.IsChildOf(b.upperArm)||!TwoBoneArmSolver.Finite(b.wristTarget.position)||!UniformPositive(b.upperArm,out _)||!UniformPositive(b.forearm,out _))
            {reason="Arm needs a calibrated fixed shoulder→elbow→tip chain and separate hand-owned target.";return false;}
            if(!Unit(b.upperAxisLocal)||!Unit(b.foreAxisLocal)||!Unit(b.poleRigLocal)||!QFinite(b.upperBindRotation)||!QFinite(b.foreBindRotation)||
                !TwoBoneArmSolver.Finite(b.upperLengthRig)||!TwoBoneArmSolver.Finite(b.foreLengthRig)||
                !TwoBoneArmSolver.Finite(b.sourceUpperLength)||!TwoBoneArmSolver.Finite(b.sourceForeLength)||!TwoBoneArmSolver.Finite(b.sourceToRigScale)||
                b.upperLengthRig<=numericToleranceRig||b.foreLengthRig<=numericToleranceRig||positionToleranceRig>Mathf.Min(b.upperLengthRig,b.foreLengthRig)*.005f||b.sourceUpperLength<=0||b.sourceForeLength<=0||b.sourceToRigScale<=0||
                Mathf.Abs(b.upperLengthRig-b.sourceUpperLength*b.sourceToRigScale)>positionToleranceRig||Mathf.Abs(b.foreLengthRig-b.sourceForeLength*b.sourceToRigScale)>positionToleranceRig)
            {reason="Invalid calibrated axes, segment lengths, rotations or source-scale cross-check.";return false;}
            if(!Near(b.upperArm.localPosition,b.shoulderLocal)||!Near(b.forearm.localPosition,b.elbowLocal)||!Near(b.wristTip.localPosition,b.tipLocal)||
                !Near(b.upperArm.localScale,b.upperScale)||!Near(b.forearm.localScale,b.foreScale)||
                Vector3.Dot(b.forearm.localPosition.normalized,b.upperAxisLocal)<.9999f||Vector3.Dot(b.wristTip.localPosition.normalized,b.foreAxisLocal)<.9999f)
            {reason="Arm joints/scale/axes changed since calibration; translated or stretched bones are forbidden.";return false;}
            return true;
        }
        bool Near(Vector3 a,Vector3 b)=>TwoBoneArmSolver.Finite(a)&&TwoBoneArmSolver.Finite(b)&&(a-b).sqrMagnitude<=numericToleranceRig*numericToleranceRig;
        // Called BEFORE every Animator sample so omitted constant tracks cannot accumulate the previous solve.
        public void RestoreBindPose()
        {
            LastSolveAccepted=false;Restore(left);Restore(right);
            LeftDiagnostics=RightDiagnostics=default;
        }
        static void Restore(ArmReachBinding b)
        {if(b==null||!b.calibrated)return;if(b.upperArm&&QFinite(b.upperBindRotation))b.upperArm.localRotation=b.upperBindRotation;if(b.forearm&&QFinite(b.foreBindRotation))b.forearm.localRotation=b.foreBindRotation;}
        void OnDisable()=>RestoreBindPose();
        public bool TrySolveBoth(out string reason)
        {
            LastSolveAccepted=false;
            if(!ValidateBindings(out reason)) { LeftDiagnostics=new ArmReachDiagnostics {reason="Binding failure: "+reason}; RightDiagnostics=default; return false; }
            var lu=left.upperArm.localRotation;var lf=left.forearm.localRotation;var ru=right.upperArm.localRotation;var rf=right.forearm.localRotation;
            bool l=TrySolve(left,out var ld);ArmReachDiagnostics rd=default;bool r=l&&TrySolve(right,out rd);Sanitize(ref ld);Sanitize(ref rd);l=l&&ld.solved;r=r&&rd.solved;LeftDiagnostics=ld;RightDiagnostics=rd;
            if(l&&r){LastSolveAccepted=true;reason=null;return true;}
            // A failed side rolls back BOTH sides to the freshly sampled animation pose.
            left.upperArm.localRotation=lu;left.forearm.localRotation=lf;right.upperArm.localRotation=ru;right.forearm.localRotation=rf;
            reason=l?rd.reason:ld.reason;return false;
        }
        static void Sanitize(ref ArmReachDiagnostics d)
        {
            d.measurementsFinite=d.measured;
            float Clean(float value){if(TwoBoneArmSolver.Finite(value))return value;return 0;}
            bool finite=TwoBoneArmSolver.Finite(d.upperLength)&&TwoBoneArmSolver.Finite(d.foreLength)&&TwoBoneArmSolver.Finite(d.wristGap)&&
                TwoBoneArmSolver.Finite(d.shoulderDrift)&&TwoBoneArmSolver.Finite(d.targetDrift)&&TwoBoneArmSolver.Finite(d.targetDistance)&&
                TwoBoneArmSolver.Finite(d.expectedUpperLength)&&TwoBoneArmSolver.Finite(d.expectedForeLength);
            if(!finite){d.solved=false;d.measurementsFinite=false;d.reason="Nonfinite metrics: "+d.reason;}
            d.upperLength=Clean(d.upperLength);d.foreLength=Clean(d.foreLength);d.wristGap=Clean(d.wristGap);d.shoulderDrift=Clean(d.shoulderDrift);d.targetDrift=Clean(d.targetDrift);d.targetDistance=Clean(d.targetDistance);d.expectedUpperLength=Clean(d.expectedUpperLength);d.expectedForeLength=Clean(d.expectedForeLength);
        }
        bool TrySolve(ArmReachBinding b,out ArmReachDiagnostics d)
        {
            d=default;UniformPositive(rigRoot,out float scale);float epsilon=numericToleranceRig*scale,tolerance=positionToleranceRig*scale;
            Vector3 s=b.upperArm.position,e=b.forearm.position,t=b.wristTarget.position;
            float l1=b.upperLengthRig*scale,l2=b.foreLengthRig*scale;
            d.measured=true;d.expectedUpperLength=l1;d.expectedForeLength=l2;d.targetDistance=Vector3.Distance(s,t);
            d.upperLength=Vector3.Distance(s,e);d.foreLength=Vector3.Distance(e,b.wristTip.position);d.wristGap=Vector3.Distance(b.wristTip.position,t);
            if(Mathf.Abs(Vector3.Distance(s,e)-l1)>tolerance||Mathf.Abs(Vector3.Distance(e,b.wristTip.position)-l2)>tolerance)
            {d.reason="Animated segments differ from calibrated fixed lengths.";return false;}
            if(!TwoBoneArmSolver.TryElbow(s,e,t,l1,l2,rigRoot.TransformDirection(b.poleRigLocal),epsilon,out var desired,out var normal,out d.reason))return false;
            if(!TwoBoneArmSolver.TrySwing(e-s,desired-s,normal,epsilon,out var q)){d.reason="Upper swing is degenerate.";return false;}
            b.upperArm.rotation=q*b.upperArm.rotation;
            if(!TwoBoneArmSolver.TrySwing(b.wristTip.position-b.forearm.position,t-b.forearm.position,normal,epsilon,out q))
            {d.reason="Forearm swing is degenerate.";return false;}
            b.forearm.rotation=q*b.forearm.rotation;
            d.upperLength=Vector3.Distance(b.upperArm.position,b.forearm.position);d.foreLength=Vector3.Distance(b.forearm.position,b.wristTip.position);
            d.wristGap=Vector3.Distance(b.wristTip.position,t);d.shoulderDrift=Vector3.Distance(b.upperArm.position,s);d.targetDrift=Vector3.Distance(b.wristTarget.position,t);
            d.solved=Mathf.Abs(d.upperLength-l1)<=tolerance&&Mathf.Abs(d.foreLength-l2)<=tolerance&&d.wristGap<=tolerance&&d.shoulderDrift<=epsilon&&d.targetDrift<=epsilon;
            if(!d.solved)d.reason="Fixed-length/shoulder/target/wrist residual check failed.";
            return d.solved;
        }
    }
}
