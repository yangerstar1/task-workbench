using System;
using System.Linq;
using NUnit.Framework;
using Unity.Collections;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class NailRigOwnershipTests
    {
        static Type Helper=>Type.GetType("DesertRV.NailRigOwnership, Assembly-CSharp",true);
        static bool Check(Renderer renderer,Transform owner,Transform rig,out string reason,string method="Validate")
        {
            object[] args={renderer,owner,rig,null};bool valid=(bool)Helper.GetMethod(method).Invoke(null,args);reason=args[3] as string;return valid;
        }
        static Transform Child(string name,Transform parent)
        { var go=new GameObject(name);go.transform.SetParent(parent,false);return go.transform; }
        sealed class Fixture:IDisposable
        {
            public readonly GameObject Rig=new GameObject("nail rig fixture");
            public readonly Transform Incoming,Loaded,External;
            public readonly SkinnedMeshRenderer Skin;
            public readonly Mesh Mesh;
            public Transform[] Bones;
            public Fixture()
            {
                Rig.SetActive(false);Incoming=Child("IncomingOffset",Rig.transform);Loaded=Child("Loaded",Rig.transform);
                External=new GameObject("foreign rig bone").transform;
                Bones=new[]{Child("reload_strip",Incoming),Child("another incoming bone",Incoming),Child("unused same-rig bone",Loaded)};
                Skin=Child("IncomingNail_00 at rig root",Rig.transform).gameObject.AddComponent<SkinnedMeshRenderer>();Skin.rootBone=Rig.transform;Skin.bones=Bones;
                Mesh=new Mesh {name="actual skinned nail fixture"};Mesh.vertices=new[]{Vector3.zero,Vector3.right*.03f,Vector3.up*.03f};Mesh.triangles=new[]{0,1,2};Mesh.bindposes=Bones.Select(b=>b.worldToLocalMatrix*Skin.transform.localToWorldMatrix).ToArray();
                Skin.sharedMesh=Mesh;SetWeights(new BoneWeight1 {boneIndex=0,weight=1});
            }
            public void SetWeights(params BoneWeight1[] perVertex)
            {
                using(var counts=new NativeArray<byte>(new[]{(byte)perVertex.Length,(byte)perVertex.Length,(byte)perVertex.Length},Allocator.Temp))
                using(var weights=new NativeArray<BoneWeight1>(Enumerable.Range(0,3).SelectMany(_=>perVertex).ToArray(),Allocator.Temp))
                    Mesh.SetBoneWeights(counts,weights);
            }
            public void Dispose() { UnityEngine.Object.DestroyImmediate(Rig);UnityEngine.Object.DestroyImmediate(External.gameObject);UnityEngine.Object.DestroyImmediate(Mesh); }
        }
        [Test] public void SkinnedAtRigRoot_AcceptsPositiveOwnerBonesIncludingMoreThanFour()
        {
            using(var f=new Fixture())
            {
                Assert.That(f.Skin.transform.IsChildOf(f.Incoming),Is.False);
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out var reason),Is.True,reason);
                f.Bones=Enumerable.Range(0,5).Select(i=>Child("influence "+i,f.Incoming)).ToArray();f.Skin.bones=f.Bones;
                f.Mesh.bindposes=f.Bones.Select(b=>b.worldToLocalMatrix*f.Skin.transform.localToWorldMatrix).ToArray();
                f.SetWeights(Enumerable.Range(0,5).Select(i=>new BoneWeight1 {boneIndex=i,weight=.2f}).ToArray());
                Assert.That(f.Mesh.GetBonesPerVertex()[0],Is.EqualTo(5));
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out reason),Is.True,reason);
                f.Bones[4]=Child("fifth positive bone outside incoming",f.Loaded);f.Skin.bones=f.Bones;
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False,"A fifth positive influence cannot evade a four-weight-only check.");
            }
        }
        [Test] public void Skinned_RejectsExternalReferencesAndMixedOwnerWeights()
        {
            using(var f=new Fixture())
            {
                f.Skin.transform.SetParent(f.External,true);Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False);f.Skin.transform.SetParent(f.Rig.transform,true);
                f.Skin.rootBone=f.External;Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False);f.Skin.rootBone=f.Rig.transform;
                var bones=(Transform[])f.Bones.Clone();bones[2]=f.External;f.Skin.bones=bones;
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False,"An unused external reference must also fail.");f.Skin.bones=f.Bones;
                f.SetWeights(new BoneWeight1 {boneIndex=0,weight=.5f},new BoneWeight1 {boneIndex=2,weight=.5f});
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False);
                f.Skin.transform.SetParent(f.Incoming,true); // Parenting cannot conceal the wrong positive bone.
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False);
                f.SetWeights(new BoneWeight1 {boneIndex=0,weight=1});Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out var reason),Is.True,reason);
            }
        }
        [Test] public void RigidMesh_StillRequiresRealTransformOwnership()
        {
            using(var f=new Fixture())
            {
                var node=Child("rigid nail",f.Incoming);node.gameObject.AddComponent<MeshFilter>().sharedMesh=f.Mesh;
                var renderer=node.gameObject.AddComponent<MeshRenderer>();Assert.That(Check(renderer,f.Incoming,f.Rig.transform,out var reason),Is.True,reason);
                Assert.That(Check(renderer,f.Incoming,f.Rig.transform,out _,"ValidateLoaded"),Is.False);
                node.SetParent(f.Rig.transform,true);Assert.That(Check(renderer,f.Incoming,f.Rig.transform,out _),Is.False);
                Assert.That(Check(renderer,f.Incoming,f.Rig.transform,out reason,"ValidateLoaded"),Is.True,reason);
                node.SetParent(f.Incoming,true);node.GetComponent<MeshFilter>().sharedMesh=null;Assert.That(Check(renderer,f.Incoming,f.Rig.transform,out _),Is.False);
            }
        }
        [Test] public void LoadedNail_CannotHaveIncomingBoneInfluence()
        {
            using(var f=new Fixture())
            {
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _,"ValidateLoaded"),Is.False);
                f.SetWeights(new BoneWeight1 {boneIndex=2,weight=1});
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out var reason,"ValidateLoaded"),Is.True,reason);
                f.SetWeights(new BoneWeight1 {boneIndex=2,weight=.75f},new BoneWeight1 {boneIndex=0,weight=.25f});
                Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _,"ValidateLoaded"),Is.False);
            }
        }
        [Test] public void MeshAndWeightTable_RejectEmptyUnreadableAndMalformedData()
        {
            using(var f=new Fixture())
            {
                // Test invalid snapshots through the exact validator used by the actual Mesh reader;
                // injecting NaN into native mesh buffers is deliberately avoided.
                var counts=f.Mesh.GetBonesPerVertex().ToArray();var weights=f.Mesh.GetAllBoneWeights().ToArray();var poses=f.Mesh.bindposes;
                bool Table(byte[] c,BoneWeight1[] w,Matrix4x4[] p)
                {
                    object[] args={3,c,w,f.Bones,p,f.Incoming,f.Rig.transform,null,null};
                    return (bool)Helper.GetMethod("ValidateWeightTable").Invoke(null,args);
                }
                Assert.That(Table(counts,weights,poses),Is.True);
                foreach(float bad in new[]{float.NaN,float.PositiveInfinity,-.1f,0f,.5f,1.1f})
                { var broken=(BoneWeight1[])weights.Clone();broken[0]=new BoneWeight1 {boneIndex=0,weight=bad};Assert.That(Table(counts,broken,poses),Is.False); }
                var invalidIndex=(BoneWeight1[])weights.Clone();invalidIndex[0]=new BoneWeight1 {boneIndex=99,weight=1};Assert.That(Table(counts,invalidIndex,poses),Is.False);
                Assert.That(Table(new byte[]{0,1,1},weights,poses),Is.False);Assert.That(Table(counts,Array.Empty<BoneWeight1>(),poses),Is.False);
                var invalidPose=(Matrix4x4[])poses.Clone();var m=invalidPose[0];m.m00=float.NaN;invalidPose[0]=m;Assert.That(Table(counts,weights,invalidPose),Is.False);
                var singular=(Matrix4x4[])poses.Clone();singular[0]=Matrix4x4.zero;Assert.That(Table(counts,weights,singular),Is.False);
                var duplicates=Enumerable.Range(0,6).Select(_=>new BoneWeight1 {boneIndex=0,weight=.5f}).ToArray();Assert.That(Table(new byte[]{2,2,2},duplicates,poses),Is.False);
                var empty=new Mesh {vertices=f.Mesh.vertices,triangles=f.Mesh.triangles,bindposes=poses};f.Skin.sharedMesh=empty;
                try { Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False); } finally { f.Skin.sharedMesh=f.Mesh;UnityEngine.Object.DestroyImmediate(empty); }
                f.Mesh.UploadMeshData(true);Assert.That(Check(f.Skin,f.Incoming,f.Rig.transform,out _),Is.False);
            }
        }
        [Test] public void AnimationTargets_IncludeActualPositiveBonesNotUnusedBoneReferences()
        {
            using(var f=new Fixture())
            {
                object[] args={f.Skin,f.Rig.transform,null,null};
                Assert.That(Helper.GetMethod("TryGetAnimationTargets").Invoke(null,args),Is.True);
                var targets=(Transform[])args[2];Assert.That(targets,Has.Member(f.Skin.transform));Assert.That(targets,Has.Member(f.Bones[0]));
                Assert.That(targets,Has.No.Member(f.Bones[2]));Assert.That(targets.Length,Is.EqualTo(2));
            }
        }
    }
}
