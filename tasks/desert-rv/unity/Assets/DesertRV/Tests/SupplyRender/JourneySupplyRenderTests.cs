using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV.Tests
{
    // Isolated Editor fixture; never counted as rules, PlayMode or gameplay acceptance.
    public sealed class JourneySupplyRenderTests
    {
        [Test] public void AuthorAndCaptureSupplyViews()
        {
            Assert.That(SystemInfo.graphicsDeviceType, Is.EqualTo(GraphicsDeviceType.OpenGLCore));
            var type=Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor",true);
            type.GetMethod("AuthorCandidateScenes",BindingFlags.Static|BindingFlags.Public).Invoke(null,null);
            type.GetMethod("CaptureOptionalSupplyCandidates",BindingFlags.Static|BindingFlags.Public).Invoke(null,null);
        }
    }
}
