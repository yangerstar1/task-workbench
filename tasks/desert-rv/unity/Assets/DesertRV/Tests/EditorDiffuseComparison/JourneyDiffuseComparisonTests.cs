using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV.Tests
{
    public sealed class JourneyDiffuseComparisonTests
    {
        [Test, Timeout(600000)] public void AuthorAndCaptureFourDiffuseComparisons()
        {
            Assert.That(SystemInfo.graphicsDeviceType,Is.EqualTo(GraphicsDeviceType.OpenGLCore));
            var clock=System.Diagnostics.Stopwatch.StartNew();
            var type=Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor",true);
            type.GetMethod("AuthorAndCaptureDiffuseComparison",BindingFlags.Static|BindingFlags.Public).Invoke(null,null);
            Debug.Log("DIFFUSE_COMPARISON_STAGE complete-four-ms="+clock.ElapsedMilliseconds);
        }
    }
}
