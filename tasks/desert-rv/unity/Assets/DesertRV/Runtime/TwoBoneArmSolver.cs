using UnityEngine;

namespace DesertRV
{
    public static class TwoBoneArmSolver
    {
        public static bool Finite(float x)=>!float.IsNaN(x)&&!float.IsInfinity(x);
        public static bool Finite(Vector3 v)=>Finite(v.x)&&Finite(v.y)&&Finite(v.z);
        public static bool TryElbow(Vector3 shoulder,Vector3 animatedElbow,Vector3 target,float upperLength,float foreLength,
            Vector3 calibratedPole,float epsilon,out Vector3 elbow,out Vector3 normal,out string reason)
        {
            elbow=normal=Vector3.zero;reason=null;
            if(!Finite(shoulder)||!Finite(animatedElbow)||!Finite(target)||!Finite(calibratedPole)||
                !Finite(upperLength)||!Finite(foreLength)||!Finite(epsilon)||epsilon<=0||upperLength<=epsilon||foreLength<=epsilon)
            {reason="Nonfinite or degenerate arm input.";return false;}
            Vector3 delta=target-shoulder;float d=delta.magnitude;
            if(!Finite(delta)||!Finite(d)){reason="Nonfinite computed target distance.";return false;}
            if(d<=epsilon) {reason="Zero-distance target has no unique solve direction.";return false;}
            if(d>upperLength+foreLength+epsilon||d<Mathf.Abs(upperLength-foreLength)-epsilon)
            {reason="Target is outside the fixed-length reach annulus; no stretch or target clamp.";return false;}
            Vector3 direction=delta/d;
            Vector3 reference=Vector3.ProjectOnPlane(calibratedPole,direction);
            if(reference.sqrMagnitude<=epsilon*epsilon) {reason="Calibrated pole is parallel to target direction.";return false;}
            reference.Normalize();Vector3 bend=Vector3.ProjectOnPlane(animatedElbow-shoulder,direction);
            if(bend.sqrMagnitude<=epsilon*epsilon) bend=reference;
            else {bend.Normalize();if(Vector3.Dot(bend,reference)<0) bend=-bend;}
            float a=(upperLength*upperLength-foreLength*foreLength+d*d)/(2*d);
            float h2=upperLength*upperLength-a*a;
            if(h2 < -epsilon*Mathf.Max(1,upperLength)) {reason="Invalid fixed-length triangle.";return false;}
            elbow=shoulder+direction*a+bend*Mathf.Sqrt(Mathf.Max(0,h2));
            normal=Vector3.Cross(direction,bend).normalized;
            if(!Finite(elbow)||!Finite(normal)){reason="Nonfinite computed elbow or plane.";return false;}
            return true;
        }
        public static bool TrySwing(Vector3 from,Vector3 to,Vector3 calibratedPlaneNormal,float epsilon,out Quaternion swing)
        {
            swing=Quaternion.identity;
            if(!Finite(epsilon)||epsilon<=0||!Finite(calibratedPlaneNormal)||!Finite(from)||!Finite(to)||
                !Finite(from.magnitude)||!Finite(to.magnitude)||from.magnitude<=epsilon||to.magnitude<=epsilon)return false;
            from.Normalize();to.Normalize();
            if(Vector3.Dot(from,to)<-1+.000001f)
            {
                // A 180-degree shortest arc has no unique axis; use the imported bend plane, never a guessed world axis.
                var axis=Vector3.ProjectOnPlane(calibratedPlaneNormal,from);
                if(axis.sqrMagnitude<=epsilon*epsilon)return false;
                swing=Quaternion.AngleAxis(180,axis.normalized);
            }
            else swing=Quaternion.FromToRotation(from,to);
            return Finite(swing.x)&&Finite(swing.y)&&Finite(swing.z)&&Finite(swing.w);
        }
    }
}
