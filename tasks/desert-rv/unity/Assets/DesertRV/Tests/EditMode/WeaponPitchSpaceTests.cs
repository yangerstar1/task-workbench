using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class WeaponPitchSpaceTests
    {
        static Type Rules=>Type.GetType("DesertRV.WeaponPitchSpace, Assembly-CSharp",true);
        static bool Valid(Transform parent,Vector3 local)=>(bool)Rules.GetMethod("ValidPitch").Invoke(null,new object[]{parent,local});
        static Vector3 Convert(Vector3 offset,Transform from,Transform to)=>(Vector3)Rules.GetMethod("InOtherParent").Invoke(null,new object[]{offset,from,to});
        [TestCase(1f,TestName="PhysicalPitchAtScaleOne")] [TestCase(100f,TestName="PhysicalPitchAtScaleOneHundred")]
        public void ActualThirtyMillimetrePitchPassesAtBothImportScales(float scale)
        {
            var go=new GameObject("pitch parent");
            try
            {
                go.transform.localScale=Vector3.one*scale;
                // Source pitch becomes world [0,-3.21mm,+30mm] in the actual imported root basis.
                var local=new Vector3(0,-.00321f,.03f)/scale;
                Assert.That(Valid(go.transform,local),Is.True);
                Assert.That(go.transform.TransformVector(local).magnitude,Is.EqualTo(.030171247f).Within(.000001f));
                if(scale==100)Assert.That(local.sqrMagnitude,Is.LessThan(.000001f),"Regression: old local-unit gate rejected the verified FBX.");
            }
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
        [TestCase(.0005f,TestName="RejectSubmillimetreWorldPitchAtScaleOneHundred")] [TestCase(.2f,TestName="RejectOversizeWorldPitchAtScaleOneHundred")]
        public void ScaleOneHundredDoesNotRelaxPhysicalLimits(float metres)
        {
            var go=new GameObject("pitch parent");
            try {go.transform.localScale=Vector3.one*100;Assert.That(Valid(go.transform,Vector3.forward*(metres/100)),Is.False);}
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
        [Test] public void TinyUnscaledPitchRemainsInvalid()
        {
            var go=new GameObject("pitch parent");
            try {Assert.That(Valid(go.transform,new Vector3(0,-.0000321f,.0003f)),Is.False);}
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
        [Test] public void NullSingularAndNonfiniteInputsFailClosed()
        {
            var go=new GameObject("pitch parent");
            try
            {
                Assert.That(Valid(null,Vector3.forward*.03f),Is.False);
                Assert.That(Valid(go.transform,new Vector3(float.NaN,0,0)),Is.False);
                Assert.That(Valid(go.transform,new Vector3(float.PositiveInfinity,0,0)),Is.False);
                go.transform.localScale=new Vector3(1,0,1);Assert.That(Valid(go.transform,Vector3.forward*.03f),Is.False);
            }
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
        [Test] public void DifferentCarrierParentsPreserveTheSameWorldOffset()
        {
            var root=new GameObject("different pitch spaces");
            try
            {
                var incoming=new GameObject("incoming parent").transform;incoming.SetParent(root.transform,false);
                var left=new GameObject("left parent").transform;left.SetParent(root.transform,false);
                incoming.localScale=Vector3.one*100;incoming.localRotation=Quaternion.Euler(-17,36,11);
                left.localScale=new Vector3(2,3,4);left.localRotation=Quaternion.Euler(41,-28,67);
                Vector3 localPitch=new Vector3(0,-.0000321f,.0003f);
                Assert.That(Valid(incoming,localPitch),Is.True);
                foreach(int count in new[]{0,3,11,12})foreach(float grip in new[]{0f,.25f,1f})
                {
                    var offset=localPitch*count;
                    var converted=Convert(offset,incoming,left);
                    var expected=incoming.TransformVector(offset)*grip;
                    Assert.That(Vector3.Distance(left.TransformVector(converted*grip),expected),Is.LessThan(.000001f));
                    Assert.That(Convert(offset,incoming,left),Is.EqualTo(converted),"Offsets are absolute and repeated sampling cannot accumulate.");
                }
            }
            finally {UnityEngine.Object.DestroyImmediate(root);}
        }
        [Test] public void SharedCarrierParentKeepsOriginalLocalVector()
        {
            var go=new GameObject("shared pitch parent");
            try
            {
                go.transform.localScale=Vector3.one*100;go.transform.localRotation=Quaternion.Euler(17,26,-9);
                var offset=new Vector3(0,-.0000321f,.0003f)*11;
                Assert.That(Vector3.Distance(Convert(offset,go.transform,go.transform),offset),Is.LessThan(.00000001f));
            }
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
    }
}
