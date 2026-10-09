using System;
using UnityEngine;

namespace DesertRV.Editor
{
    // Diagnostic-only. Never changes an imported transform, mesh, weight, or quality setting.
    // Candidate BakeMesh(true) convention: independently check every world vertex before use.
    // Supported reference domain is deliberately narrow: no blend shapes, Auto/Unlimited skinning.
    public static class JourneyCandidateMeshMeasurement
    {
        public const float NearOriginAgreementToleranceMetres = .00005f;
        public const float MaximumAgreementToleranceMetres = .00025f;

        public static Vector3[] GetWorldVertices(Renderer renderer,out float maximumSkinningErrorMetres,out float maximumAgreementToleranceMetres)
        {
            if(!renderer)throw new InvalidOperationException("Actual mesh renderer required.");
            maximumSkinningErrorMetres=0;maximumAgreementToleranceMetres=0;
            if(renderer is SkinnedMeshRenderer skin)
            {
                var reference=LinearSkinWorldVertices(skin);
                var baked=new Mesh();
                try
                {
                    // Unity 6000.3 documents true as scale compensation; accept it only after
                    // every actual native world vertex matches the independent LBS reference.
                    // Do not substitute a fixed divisor, TR-only matrix, or Renderer.bounds.
                    skin.BakeMesh(baked,true);
                    if(!baked.isReadable || baked.vertexCount!=reference.Length)
                        throw new InvalidOperationException("Baked/source vertex inventory differs: "+renderer.name);
                    var world=baked.vertices;
                    for(int i=0;i<world.Length;i++)world[i]=renderer.transform.TransformPoint(world[i]);
                    maximumSkinningErrorMetres=RequireWorldAgreement(world,reference,renderer.name,out maximumAgreementToleranceMetres);
                    return world;
                }
                finally { UnityEngine.Object.DestroyImmediate(baked); }
            }
            var filter=renderer.GetComponent<MeshFilter>();var mesh=filter?filter.sharedMesh:null;
            if(!(renderer is MeshRenderer) || !mesh || !mesh.isReadable || mesh.vertexCount==0)
                throw new InvalidOperationException("Actual readable mesh required for pose diagnostics: "+renderer.name);
            var vertices=mesh.vertices;
            for(int i=0;i<vertices.Length;i++)
            {
                vertices[i]=renderer.transform.TransformPoint(vertices[i]);
                RequireFinite(vertices[i],renderer.name,i);
            }
            return vertices;
        }

        static Vector3[] LinearSkinWorldVertices(SkinnedMeshRenderer skin)
        {
            var mesh=skin.sharedMesh;
            if(!mesh || !mesh.isReadable || mesh.vertexCount==0)
                throw new InvalidOperationException("Actual readable source skin mesh required: "+skin.name);
            if(mesh.blendShapeCount!=0)
                throw new InvalidOperationException("Independent skin reference does not support blend shapes: "+skin.name);
            if(skin.quality!=SkinQuality.Auto || QualitySettings.skinWeights!=SkinWeights.Unlimited)
                throw new InvalidOperationException("Independent skin reference requires Auto/Unlimited, without truncated weights: "+skin.name);
            var source=mesh.vertices;var bones=skin.bones;var bindposes=mesh.bindposes;
            if(bones.Length==0 || bones.Length!=bindposes.Length)
                throw new InvalidOperationException("Complete matching bone/bind-pose inventory required: "+skin.name);
            var boneToWorld=new Matrix4x4[bones.Length];
            for(int i=0;i<bones.Length;i++)
            {
                if(!bones[i])throw new InvalidOperationException("Missing skin bone: "+skin.name+" bone="+i);
                boneToWorld[i]=bones[i].localToWorldMatrix;
            }
            // These are read-only views owned by Mesh (Allocator.None), not temporary allocations.
            // Read the full variable-length weight stream, including influences beyond the first four.
            var counts=mesh.GetBonesPerVertex();var weights=mesh.GetAllBoneWeights();
            if(counts.Length!=source.Length)throw new InvalidOperationException("Missing per-vertex skin weights: "+skin.name);
            var result=new Vector3[source.Length];int offset=0;
            for(int i=0;i<source.Length;i++)
            {
                RequireFinite(source[i],skin.name,i);
                if(counts[i]==0 || counts[i]>weights.Length-offset)
                    throw new InvalidOperationException("Incomplete skin weight stream: "+skin.name+" vertex="+i);
                double sum=0,worldX=0,worldY=0,worldZ=0;
                for(int j=0;j<counts[i];j++)
                {
                    var influence=weights[offset++];int bone=influence.boneIndex;float weight=influence.weight;
                    if(bone<0 || bone>=bones.Length || !(weight>0) || weight>1 || float.IsInfinity(weight))
                        throw new InvalidOperationException("Invalid skin influence: "+skin.name+" vertex="+i);
                    // Fully independent of BakeMesh, renderer bounds, or renderer TransformPoint.
                    // Double arithmetic prevents accumulation of one float world-position rounding
                    // per influence (especially at the weapon's 100m/200m diagnostic positions).
                    var bind=bindposes[bone];var matrix=boneToWorld[bone];var vertex=source[i];
                    double x=(double)bind.m00*vertex.x+(double)bind.m01*vertex.y+(double)bind.m02*vertex.z+bind.m03;
                    double y=(double)bind.m10*vertex.x+(double)bind.m11*vertex.y+(double)bind.m12*vertex.z+bind.m13;
                    double z=(double)bind.m20*vertex.x+(double)bind.m21*vertex.y+(double)bind.m22*vertex.z+bind.m23;
                    worldX+=(matrix.m00*x+matrix.m01*y+matrix.m02*z+matrix.m03)*weight;
                    worldY+=(matrix.m10*x+matrix.m11*y+matrix.m12*z+matrix.m13)*weight;
                    worldZ+=(matrix.m20*x+matrix.m21*y+matrix.m22*z+matrix.m23)*weight;
                    sum+=weight;
                }
                if(double.IsNaN(sum) || Math.Abs(sum-1d)>.0001d)
                    throw new InvalidOperationException("Skin weights do not sum to one: "+skin.name+" vertex="+i);
                var world=new Vector3((float)worldX,(float)worldY,(float)worldZ);
                RequireFinite(world,skin.name,i);result[i]=world;
            }
            if(offset!=weights.Length)throw new InvalidOperationException("Unconsumed skin influences: "+skin.name);
            return result;
        }

        static float RequireWorldAgreement(Vector3[] actual,Vector3[] expected,string rendererName,out float maximumTolerance)
        {
            if(actual.Length==0 || actual.Length!=expected.Length)
                throw new InvalidOperationException("World skin vertex inventory differs: "+rendererName);
            float maximum=0;maximumTolerance=0;
            for(int i=0;i<actual.Length;i++)
            {
                RequireFinite(actual[i],rendererName,i);RequireFinite(expected[i],rendererName,i);
                float tolerance=AgreementTolerance(actual[i],expected[i]);
                float error=Vector3.Distance(actual[i],expected[i]);
                if(!(error<=tolerance))
                    throw new InvalidOperationException("BakeMesh(true) world/LBS disagreement: "+rendererName+" vertex="+i+" errorMetres="+error.ToString("G9")+" toleranceMetres="+tolerance.ToString("G9"));
                maximum=Mathf.Max(maximum,error);maximumTolerance=Mathf.Max(maximumTolerance,tolerance);
            }
            return maximum;
        }

        static float AgreementTolerance(Vector3 actual,Vector3 expected)
        {
            double magnitude=Math.Max(1d,Math.Max(Math.Max(Math.Abs(actual.x),Math.Abs(actual.y)),Math.Max(Math.Abs(actual.z),Math.Max(Math.Abs(expected.x),Math.Max(Math.Abs(expected.y),Math.Abs(expected.z))))));
            // 50 micrometres near-origin numerical allowance plus four binary32 ULPs at
            // this world's largest component. Double LBS accumulation avoids an N-weights
            // float-addition budget. At 200m this is 0.111mm, not a looser ground gate.
            // Native translated fixtures must validate this bounded numerical cross-check;
            // it is not a promise about arbitrary ill-conditioned transform hierarchies.
            double ulp=Math.Pow(2d,Math.Floor(Math.Log(magnitude,2d))-23d);
            float tolerance=NearOriginAgreementToleranceMetres+(float)(4d*ulp);
            if(tolerance>MaximumAgreementToleranceMetres)
                throw new InvalidOperationException("World position exceeds bounded skin-reference precision domain.");
            return tolerance;
        }

        static void RequireFinite(Vector3 point,string rendererName,int index)
        {
            if(float.IsNaN(point.x)||float.IsNaN(point.y)||float.IsNaN(point.z)||float.IsInfinity(point.x)||float.IsInfinity(point.y)||float.IsInfinity(point.z))
                throw new InvalidOperationException("Nonfinite deformed vertex: "+rendererName+" vertex="+index);
        }
    }
}
