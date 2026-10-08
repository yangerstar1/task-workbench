using System;
using System.Collections.Generic;
using UnityEngine;

namespace DesertRV
{
    // Shared by runtime binding validation and Editor import/preflight. Never reparents meshes.
    public static class NailRigOwnership
    {
        public static bool Validate(Renderer nail,Transform requiredOwner,Transform rig,out string reason)
            => Analyze(nail,requiredOwner,rig,null,out _,out reason);
        public static bool ValidateLoaded(Renderer nail,Transform incomingBranch,Transform rig,out string reason)
        {
            if(!incomingBranch || !rig || !incomingBranch.IsChildOf(rig)) { reason="Incoming branch is missing or belongs to another rig."; return false; }
            return Analyze(nail,rig,rig,incomingBranch,out _,out reason);
        }
        // Renderer paths alone are insufficient for skinning: include every positively influencing bone.
        public static bool TryGetAnimationTargets(Renderer nail,Transform rig,out Transform[] targets,out string reason)
            => Analyze(nail,rig,rig,null,out targets,out reason);

        static bool Analyze(Renderer nail,Transform owner,Transform rig,Transform forbidden,out Transform[] targets,out string reason)
        {
            targets=Array.Empty<Transform>();reason=null;
            if(!nail || !owner || !rig || !owner.IsChildOf(rig) || !nail.transform.IsChildOf(rig))
                return Fail("Nail renderer and required owner must belong to the same Animator rig.",out reason);
            try
            {
                Mesh mesh;
                if(nail is SkinnedMeshRenderer skin) mesh=skin.sharedMesh;
                else if(nail is MeshRenderer)
                { var filter=nail.GetComponent<MeshFilter>();mesh=filter?filter.sharedMesh:null; }
                else return Fail("Nail requires a MeshRenderer or SkinnedMeshRenderer.",out reason);
                if(!mesh || !mesh.isReadable || mesh.vertexCount<3 || mesh.subMeshCount<1)
                    return Fail("Nail mesh must be present, readable and nonempty.",out reason);
                foreach(var vertex in mesh.vertices) if(!Finite(vertex.x)||!Finite(vertex.y)||!Finite(vertex.z))
                    return Fail("Nail mesh contains nonfinite vertex positions.",out reason);
                if(nail is SkinnedMeshRenderer skinned)
                {
                    if(!skinned.rootBone || !skinned.rootBone.IsChildOf(rig))
                        return Fail("Skinned nail rootBone must reference this Animator rig.",out reason);
                    var bones=skinned.bones;
                    // Unity 6000.3 documents these views as Allocator.None, owned by Mesh.
                    // Read/copy them immediately; never retain or Dispose these borrowed native views.
                    var counts=mesh.GetBonesPerVertex().ToArray();
                    var weights=mesh.GetAllBoneWeights().ToArray();
                    if(!ValidateWeightTable(mesh.vertexCount,counts,weights,bones,mesh.bindposes,owner,rig,forbidden,out reason)) return false;
                    var affected=new HashSet<Transform>{nail.transform};
                    foreach(var weight in weights) if(weight.weight>0) affected.Add(bones[weight.boneIndex]);
                    targets=new Transform[affected.Count];affected.CopyTo(targets);return true;
                }
                if(!nail.transform.IsChildOf(owner)) return Fail("Rigid nail transform must lie under the required owner.",out reason);
                if(forbidden && nail.transform.IsChildOf(forbidden)) return Fail("Loaded rigid nail lies under the incoming branch.",out reason);
                targets=new[]{nail.transform};return true;
            }
            catch(Exception error)
            { return Fail("Nail mesh ownership could not be verified: "+error.GetType().Name,out reason); }
        }
        // The same validator consumes snapshots from the actual Mesh reader. Public for deterministic invalid-table regression.
        public static bool ValidateWeightTable(int vertexCount,byte[] counts,BoneWeight1[] weights,Transform[] bones,
            Matrix4x4[] bindposes,Transform owner,Transform rig,Transform forbidden,out string reason)
        {
            reason=null;
            if(!owner || !rig || !owner.IsChildOf(rig) || (forbidden && !forbidden.IsChildOf(rig)))
                return Fail("Weight ownership branches must belong to the same rig.",out reason);
            if(vertexCount<=0 || counts==null || counts.Length!=vertexCount || weights==null || weights.Length==0 ||
                bones==null || bones.Length==0 || bindposes==null || bindposes.Length!=bones.Length)
                return Fail("Missing or mismatched vertex weights, bones or bindposes.",out reason);
            for(int i=0;i<bones.Length;i++)
            {
                if(!bones[i] || !bones[i].IsChildOf(rig)) return Fail("Null or external-rig bone reference, even if unused.",out reason);
                var boneMatrix=bones[i].localToWorldMatrix;
                for(int element=0;element<16;element++)
                    if(!Finite(bindposes[i][element]) || !Finite(boneMatrix[element]))
                        return Fail("Nonfinite bone transform or bindpose matrix.",out reason);
                if(!Finite(bindposes[i].determinant) || Mathf.Abs(bindposes[i].determinant)<1e-10f)
                    return Fail("Singular bindpose matrix.",out reason);
            }
            long expected=0;foreach(byte count in counts) { if(count==0) return Fail("Every nail vertex must have positive bone influence.",out reason); expected+=count; }
            if(expected!=weights.Length) return Fail("Weight count does not match per-vertex influence counts.",out reason);
            int cursor=0;
            for(int vertex=0;vertex<vertexCount;vertex++)
            {
                double sum=0;float previous=float.PositiveInfinity;var seen=new HashSet<int>();
                for(int i=0;i<counts[vertex];i++)
                {
                    var w=weights[cursor++];
                    if(!Finite(w.weight) || w.weight<=0 || w.weight>1 || w.boneIndex<0 || w.boneIndex>=bones.Length || !seen.Add(w.boneIndex))
                        return Fail("Bone weight is nonfinite, nonpositive, out of range or duplicated.",out reason);
                    if(w.weight>previous+.000001f) return Fail("Bone weights must be in descending order per vertex.",out reason);
                    previous=w.weight;sum+=w.weight;var bone=bones[w.boneIndex];
                    if(!bone.IsChildOf(owner)) return Fail("Positive nail weight refers outside the required owner branch.",out reason);
                    if(forbidden && bone.IsChildOf(forbidden)) return Fail("Loaded nail has positive weight on the incoming branch.",out reason);
                }
                if(Math.Abs(sum-1)>0.002) return Fail("Per-vertex nail weights must normalize to one.",out reason);
            }
            return true;
        }
        static bool Finite(float value)=>!float.IsNaN(value)&&!float.IsInfinity(value);
        static bool Fail(string value,out string reason) { reason=value;return false; }
    }
}
