using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV.Tests
{
    // Separate assembly: never counted among EditMode rules or PlayMode loader tests.
    public sealed class JourneyEnvironmentRenderTests
    {
        [Test] public void AuthorAndCaptureTwelveRealEnvironmentViews()
        {
            Assert.That(SystemInfo.graphicsDeviceType, Is.Not.EqualTo(GraphicsDeviceType.Null));
            Assert.That(SystemInfo.graphicsDeviceType, Is.EqualTo(GraphicsDeviceType.OpenGLCore));
            var type = Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor", true);
            type.GetMethod("AuthorAndCaptureEnvironmentCandidates", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);
        }
    }
}
