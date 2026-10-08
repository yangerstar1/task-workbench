using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
namespace DesertRV.Tests
{
    public sealed class CandidateAnimationPolicyTests
    {
        static bool Call(string method,params object[] args)=> (bool)Type.GetType("DesertRV.Editor.JourneyCandidateArtImport, Assembly-CSharp-Editor",true).GetMethod(method,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,args);
        [Test] public void OnlyArmoredAttackGetsTheSourceLoopException()
        {
            Assert.That(Call("AllowedLoop","armored","Attack"),Is.True);
            foreach(string kind in new[]{"pouncer","weapon"})Assert.That(Call("AllowedLoop",kind,"Attack"),Is.False);
            foreach(string state in new[]{"Windup","Recover","Hit","Death","Fire","Reload"})Assert.That(Call("AllowedLoop","armored",state),Is.False);
            Assert.That(Call("AllowedLoop","weapon","Idle"),Is.True);Assert.That(Call("AllowedLoop","pouncer","Walk"),Is.True);
        }
        [Test] public void MissingNativeAnimatorGetsCreatedAndReused()
        {
            var root=new GameObject("Missing native Animator regression");
            try
            {
                var method=Type.GetType("DesertRV.Editor.JourneyCandidateArtImport, Assembly-CSharp-Editor",true).GetMethod("EnsureNativeAnimator",BindingFlags.Static|BindingFlags.NonPublic);
                Assert.That((bool)root.GetComponent<Animator>(),Is.False);
                var first=(Animator)method.Invoke(null,new object[]{root.transform});
                Assert.That((bool)first,Is.True);first.applyRootMotion=false;
                var reused=(Animator)method.Invoke(null,new object[]{root.transform});
                Assert.That(reused==first,Is.True);
                Assert.That(root.GetComponents<Animator>().Length,Is.EqualTo(1));
                UnityEngine.Object.DestroyImmediate(first);
                Assert.That((bool)first,Is.False);
                var replacement=(Animator)method.Invoke(null,new object[]{root.transform});
                Assert.That((bool)replacement,Is.True);replacement.applyRootMotion=false;
                Assert.That(root.GetComponents<Animator>().Length,Is.EqualTo(1));
            }
            finally {UnityEngine.Object.DestroyImmediate(root);}
        }
        [Test] public void EqualKeyValuesDoNotExcuseUnsafeTangents()
        {
            foreach(float t in new[]{float.NaN,.000001f,-.000001f,1f,-1f})Assert.That(Call("SafeConstantTangent",t),Is.False);
            foreach(float t in new[]{0f,float.PositiveInfinity,float.NegativeInfinity})Assert.That(Call("SafeConstantTangent",t),Is.True);
        }
    }
}
