using System;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class CandidateMuzzleAxisTests
    {
        [Test] public void SourceYAdapterDoesNotRotateTheAuthoredMuzzle()
        {
            var go=new GameObject("actual imported muzzle basis fixture");
            try
            {
                go.transform.rotation=Quaternion.Euler(-90,0,0);go.transform.localScale=Vector3.one*100;
                var rotation=go.transform.localRotation;var position=go.transform.localPosition;
                var type=Type.GetType("DesertRV.Editor.CandidateWeaponBinding, Assembly-CSharp-Editor",true);
                var adapter=(Transform)type.GetMethod("CreateSourceAxisAdapter").Invoke(null,new object[]{go.transform,Vector3.up,Vector3.forward});
                Assert.That(Quaternion.Angle(go.transform.localRotation,rotation),Is.LessThan(.00001f));
                Assert.That(go.transform.localPosition,Is.EqualTo(position));
                Assert.That(Vector3.Dot(adapter.forward,go.transform.TransformDirection(Vector3.up)),Is.GreaterThan(.99999f));
                Assert.That(Vector3.Dot(adapter.forward,Vector3.back),Is.GreaterThan(.99999f));
                Assert.That(Mathf.Abs(Vector3.Dot(adapter.forward,go.transform.forward)),Is.LessThan(.00001f),"Raw Transform.forward pointed up, not down the barrel.");
                Assert.That(Vector3.Distance(adapter.position,go.transform.position),Is.LessThan(.00001f));
                Assert.That(adapter.GetComponent<ParticleSystem>(),Is.Null,"Axis adapter is not scene/flash acceptance.");
            }
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
    }
}
