using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV.Tests
{
    public sealed class JourneyTerrainProbeTests
    {
        [Test, Timeout(600000)] public void AuthorAndCaptureEightChannelAblations()
        {
            Assert.That(SystemInfo.graphicsDeviceType,Is.EqualTo(GraphicsDeviceType.OpenGLCore));
            var clock=System.Diagnostics.Stopwatch.StartNew();
            var type=Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor",true);
            type.GetMethod("AuthorAndCaptureTerrainProbe",BindingFlags.Static|BindingFlags.Public).Invoke(null,null);
            Debug.Log("TERRAIN_PROBE_STAGE complete-eight-ms="+clock.ElapsedMilliseconds);
        }
    }
}
