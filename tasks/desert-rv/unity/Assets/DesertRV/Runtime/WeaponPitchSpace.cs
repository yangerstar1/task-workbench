using UnityEngine;

namespace DesertRV
{
    // nailPitch is serialized in IncomingOffset.parent space. Limits are physical metres,
    // independent of the FBX's imported scale (the verified weapon rig uses scale 100).
    public static class WeaponPitchSpace
    {
        public static bool ValidParent(Transform parent)
        {
            if(!parent)return false;
            var matrix=parent.localToWorldMatrix;
            for(int i=0;i<16;i++)if(!Finite(matrix[i]))return false;
            return Finite(matrix.determinant)&&matrix.determinant!=0;
        }
        public static bool ValidPitch(Transform parent,Vector3 localPitch)
        {
            if(!ValidParent(parent)||!Finite(localPitch.x)||!Finite(localPitch.y)||!Finite(localPitch.z))return false;
            Vector3 worldPitch=parent.TransformVector(localPitch);
            // Preserve the existing strict physical interval: greater than 1 mm, less than 100 mm.
            return Finite(worldPitch.x)&&Finite(worldPitch.y)&&Finite(worldPitch.z)&&
                worldPitch.sqrMagnitude>.000001f&&worldPitch.sqrMagnitude<.01f;
        }
        public static Vector3 InOtherParent(Vector3 localOffset,Transform sourceParent,Transform targetParent)
            =>targetParent.InverseTransformVector(sourceParent.TransformVector(localOffset));
        static bool Finite(float value)=>!float.IsNaN(value)&&!float.IsInfinity(value);
    }
}
