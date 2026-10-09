using System;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using Unity.Collections;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class CandidateMeshMeasurementTests
    {
        static Type Helper=>Type.GetType("DesertRV.Editor.JourneyCandidateMeshMeasurement, Assembly-CSharp-Editor",true);
        static Vector3[] Measure(Renderer renderer,out float error,out float tolerance)
        {
            object[] args={renderer,0f,0f};
            var vertices=(Vector3[])Helper.GetMethod("GetWorldVertices").Invoke(null,args);
            error=(float)args[1];tolerance=(float)args[2];return vertices;
        }
        static Transform Child(string name,Transform parent)
        { var t=new GameObject(name).transform;t.SetParent(parent,false);return t; }
        sealed class Fixture:IDisposable
        {
            public readonly GameObject Root=new GameObject("world skin fixture");
            public readonly Transform Parent,Rig;
            public readonly Transform[] Bones;
            public readonly SkinnedMeshRenderer Skin;
            public readonly Mesh Mesh;
            public readonly float Unit;
            public Fixture(float rendererScale,float parentScale)
            {
                Unit=rendererScale*parentScale;
                Root.transform.localRotation=Quaternion.Euler(7,19,-3);
                Parent=Child("rotated parent",Root.transform);Parent.localRotation=Quaternion.Euler(-11,23,5);Parent.localScale=Vector3.one*parentScale;
                Rig=Child("rig",Parent);Rig.localScale=Vector3.one*rendererScale;Rig.localRotation=Quaternion.Euler(-90,0,0);
                Skin=Child("offset mesh",Parent).gameObject.AddComponent<SkinnedMeshRenderer>();
                Skin.transform.localPosition=new Vector3(-.259f,.669f,.965f)/parentScale;
                Skin.transform.localRotation=Quaternion.Euler(-90,0,0);Skin.transform.localScale=Vector3.one*rendererScale;
                Bones=new Transform[5];
                for(int i=0;i<Bones.Length;i++)
                {
                    Bones[i]=Child("bone "+i,i==0?Rig:Bones[0]);
                    Bones[i].localPosition=new Vector3(.03f*i,.08f*i,.015f*i)/Unit;
                    Bones[i].localRotation=Quaternion.Euler(i*3,i*-5,i*2);
                }
                Mesh=new Mesh{name="five influence triangle"};
                Mesh.vertices=new[]{new Vector3(-.13f,.05f,-.032f)/Unit,new Vector3(.24f,-.11f,.09f)/Unit,new Vector3(-.07f,.29f,.12f)/Unit};
                Mesh.triangles=new[]{0,1,2};Mesh.RecalculateNormals();
                Mesh.bindposes=Bones.Select(b=>b.worldToLocalMatrix*Skin.transform.localToWorldMatrix).ToArray();
                var perVertex=new[]{.5f,.25f,.125f,.0625f,.0625f};
                using(var counts=new NativeArray<byte>(new byte[]{5,5,5},Allocator.Temp))
                using(var weights=new NativeArray<BoneWeight1>(Enumerable.Range(0,3).SelectMany(_=>perVertex.Select((w,i)=>new BoneWeight1{boneIndex=i,weight=w})).ToArray(),Allocator.Temp))
                    Mesh.SetBoneWeights(counts,weights);
                Skin.bones=Bones;Skin.rootBone=Rig;Skin.sharedMesh=Mesh;Skin.quality=SkinQuality.Auto;Skin.updateWhenOffscreen=true;
            }
            public void Pose(int pose,float translation)
            {
                Root.transform.position=new Vector3(translation,translation*.125f,-translation*.25f);
                Root.transform.rotation=Quaternion.Euler(7+11*pose,19+43*pose,-3+5*pose);
                Bones[0].localPosition=new Vector3(.012f*pose,.025f*pose,-.014f*pose)/Unit;
                Bones[0].localRotation=Quaternion.Euler(13*pose,-7*pose,9*pose);
                Bones[4].localPosition=new Vector3(.12f,.32f,.06f+.08f*pose)/Unit;
                Bones[4].localRotation=Quaternion.Euler(12+17*pose,-20-11*pose,8+5*pose);
            }
            public void Dispose()
            { UnityEngine.Object.DestroyImmediate(Root);UnityEngine.Object.DestroyImmediate(Mesh); }
        }

        // Test-side independent homogeneous-matrix implementation; does not call the production LBS.
        static double[] Multiply(Matrix4x4 matrix,double[] point)
        {
            var result=new double[4];
            for(int row=0;row<4;row++)for(int col=0;col<4;col++)result[row]+=matrix[row,col]*point[col];
            return result;
        }
        static Vector3[] Reference(Fixture f,bool omitFifth=false)
        {
            var source=f.Mesh.vertices;var poses=f.Mesh.bindposes;var counts=f.Mesh.GetBonesPerVertex();var weights=f.Mesh.GetAllBoneWeights();
            var result=new Vector3[source.Length];int offset=0;
            for(int i=0;i<source.Length;i++)
            {
                double[] total={0d,0d,0d,0d};double[] point={source[i].x,source[i].y,source[i].z,1d};
                for(int j=0;j<counts[i];j++)
                {
                    var w=weights[offset++];if(omitFifth && w.boneIndex==4)continue;
                    var transformed=Multiply(f.Bones[w.boneIndex].localToWorldMatrix,Multiply(poses[w.boneIndex],point));
                    for(int axis=0;axis<4;axis++)total[axis]+=w.weight*transformed[axis];
                }
                result[i]=new Vector3((float)total[0],(float)total[1],(float)total[2]);
            }
            Assert.That(offset,Is.EqualTo(weights.Length));return result;
        }
        static void Reject(Action action,string message)
        {
            var error=Assert.Throws<TargetInvocationException>(()=>action());
            Assert.That(error.InnerException,Is.TypeOf<InvalidOperationException>());
            StringAssert.Contains(message,error.InnerException.Message);
        }

        [Test] public void ScaledTranslatedRotatedHierarchyMatchesIndependentSkinning()
        {
            var previous=QualitySettings.skinWeights;
            try
            {
                QualitySettings.skinWeights=SkinWeights.Unlimited;
                foreach(float rendererScale in new[]{1f,100f})foreach(float parentScale in new[]{1f,100f})
                using(var f=new Fixture(rendererScale,parentScale))
                {
                    Assert.That(f.Mesh.GetAllBoneWeights().Length,Is.EqualTo(15));
                    foreach(float translation in new[]{0f,100f,200f})foreach(int pose in new[]{0,1,2})
                    {
                        f.Pose(pose,translation);var expected=Reference(f);var actual=Measure(f.Skin,out var error,out var tolerance);
                        Assert.That(actual.Length,Is.EqualTo(f.Mesh.vertexCount));
                        Assert.That(tolerance,Is.InRange(.00005f,.00025f));Assert.That(error,Is.LessThanOrEqualTo(tolerance));
                        for(int i=0;i<actual.Length;i++)Assert.That(Vector3.Distance(actual[i],expected[i]),Is.LessThanOrEqualTo(tolerance),"scale="+rendererScale+" parent="+parentScale+" translation="+translation+" pose="+pose+" vertex="+i);
                        Assert.That(Vector3.Distance(expected[2],Reference(f,true)[2]),Is.GreaterThan(.004f),"The fifth weight must be consequential.");
                    }
                    if(rendererScale==100f && parentScale==1f)
                    {
                        f.Pose(1,0);var legacy=new Mesh();
                        try
                        {
                            f.Skin.BakeMesh(legacy,false);var expected=Reference(f);
                            float legacyError=Vector3.Distance(f.Skin.transform.TransformPoint(legacy.vertices[2]),expected[2]);
                            Assert.That(legacyError,Is.GreaterThan(.004f),"Fixture must expose the old double-scale measurement.");
                            // Nonzero translation makes dividing the final world point by 100 invalid.
                            Assert.That(Vector3.Distance(f.Skin.transform.TransformPoint(legacy.vertices[2])/100f,expected[2]),Is.GreaterThan(.004f));
                        }
                        finally {UnityEngine.Object.DestroyImmediate(legacy);}
                    }
                }
            }
            finally {QualitySettings.skinWeights=previous;}
        }

        [Test] public void RejectsBlendShapesAndTruncatedSkinQuality()
        {
            var previous=QualitySettings.skinWeights;
            try
            {
                QualitySettings.skinWeights=SkinWeights.Unlimited;
                using(var f=new Fixture(100,1))
                {
                    f.Pose(1,0);Measure(f.Skin,out _,out _);
                    f.Skin.quality=SkinQuality.Bone4;Reject(()=>Measure(f.Skin,out _,out _),"Auto/Unlimited");
                    f.Skin.quality=SkinQuality.Auto;QualitySettings.skinWeights=SkinWeights.FourBones;Reject(()=>Measure(f.Skin,out _,out _),"Auto/Unlimited");
                    QualitySettings.skinWeights=SkinWeights.Unlimited;
                    var deltas=Enumerable.Repeat(new Vector3(.01f,0,0),f.Mesh.vertexCount).ToArray();
                    f.Mesh.AddBlendShapeFrame("unsupported blend",100,deltas,new Vector3[3],new Vector3[3]);
                    Reject(()=>Measure(f.Skin,out _,out _),"blend shapes");f.Mesh.ClearBlendShapes();
                    var bones=f.Skin.bones;bones[4]=null;f.Skin.bones=bones;Reject(()=>Measure(f.Skin,out _,out _),"Missing skin bone");
                }
                var compare=Helper.GetMethod("RequireWorldAgreement",BindingFlags.Static|BindingFlags.NonPublic);
                var expected=new[]{Vector3.zero,Vector3.one,new Vector3(200,25,-50)};
                var actual=(Vector3[])expected.Clone();actual[2].y+=.001f;
                Reject(()=>compare.Invoke(null,new object[]{actual,expected,"tail vertex mismatch",0f}),"world/LBS disagreement");
                actual=(Vector3[])expected.Clone();actual[1].x=float.NaN;
                Reject(()=>compare.Invoke(null,new object[]{actual,expected,"nonfinite",0f}),"Nonfinite");
                Reject(()=>compare.Invoke(null,new object[]{new Vector3[2],expected,"missing vertex",0f}),"inventory");
            }
            finally {QualitySettings.skinWeights=previous;}
        }

        [Test] public void StaticMeshesAndFourMillimetreGateUseWorldVertices()
        {
            var host=new GameObject("static diagnostic fixture");var cameraObject=new GameObject("diagnostic camera");var mesh=new Mesh();
            try
            {
                host.transform.SetPositionAndRotation(new Vector3(-.259f,.669f,.965f),Quaternion.Euler(-90,23,8));host.transform.localScale=new Vector3(100,50,75);
                host.AddComponent<MeshFilter>().sharedMesh=mesh;var renderer=host.AddComponent<MeshRenderer>();
                var camera=cameraObject.AddComponent<Camera>();camera.transform.position=new Vector3(0,0,-3);camera.nearClipPlane=.01f;camera.farClipPlane=20;
                var capture=Type.GetType("DesertRV.Editor.JourneyCandidateArtCapture, Assembly-CSharp-Editor",true);
                var frameType=capture.GetNestedType("Frame",BindingFlags.NonPublic);
                var measure=capture.GetMethod("MeasureMeshes",BindingFlags.Static|BindingFlags.NonPublic);
                foreach(float minY in new[]{-.00399f,-.00401f,-.0415903f})
                {
                    var intended=new[]{new Vector3(-.1f,.12f,0),new Vector3(.2f,.25f,.2f),new Vector3(.05f,minY,.1f)};
                    mesh.vertices=intended.Select(host.transform.InverseTransformPoint).ToArray();mesh.triangles=new[]{0,1,2};mesh.RecalculateBounds();
                    var actual=Measure(renderer,out var error,out var tolerance);
                    Assert.That(error,Is.Zero);Assert.That(tolerance,Is.Zero);Assert.That(actual.Length,Is.EqualTo(3));
                    for(int i=0;i<3;i++)Assert.That(Vector3.Distance(actual[i],intended[i]),Is.LessThan(.000001f));
                    var frame=Activator.CreateInstance(frameType,true);
                    frameType.GetField("groundDiagnosticApplicable").SetValue(frame,true);frameType.GetField("groundReferenceY").SetValue(frame,0f);
                    measure.Invoke(null,new object[]{new Renderer[]{renderer},camera,frame});
                    float measuredMinY=(float)frameType.GetField("worldMinY").GetValue(frame);
                    Assert.That(measuredMinY,Is.EqualTo(minY).Within(.000001f));
                    Assert.That(measuredMinY<-.004f,Is.EqualTo(minY<-.004f),"The unchanged 4mm gate consumes actual world metres.");
                    Assert.That((int)frameType.GetField("sampledVertices").GetValue(frame),Is.EqualTo(3));
                    Assert.That((int)frameType.GetField("belowReferenceVertices").GetValue(frame),Is.EqualTo(1));
                }
            }
            finally
            { UnityEngine.Object.DestroyImmediate(host);UnityEngine.Object.DestroyImmediate(cameraObject);UnityEngine.Object.DestroyImmediate(mesh); }
        }
    }
}
