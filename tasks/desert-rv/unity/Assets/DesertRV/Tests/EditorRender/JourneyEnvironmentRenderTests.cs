using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEditor.SceneManagement;
namespace DesertRV.Tests
{
    // Separate assembly: never counted among EditMode rules or PlayMode loader tests.
    public sealed class JourneyEnvironmentRenderTests
    {
        [Test, Timeout(600000)] public void AuthorAndCaptureEnvironmentViews()
        {
            var stageClock = System.Diagnostics.Stopwatch.StartNew();
            UnityEngine.Debug.Log("ENVIRONMENT_V4_STAGE native-render-start");
            Assert.That(SystemInfo.graphicsDeviceType, Is.Not.EqualTo(GraphicsDeviceType.Null));
            Assert.That(SystemInfo.graphicsDeviceType, Is.EqualTo(GraphicsDeviceType.OpenGLCore));
            var type = Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor", true);
            // Regression: CI starts without any saved loaded scene. The old
            // RestoreSceneManagerSetup(empty) aborted before the first screenshot.
            type.GetMethod("RestoreSceneSetup", BindingFlags.Static | BindingFlags.NonPublic)
                .Invoke(null, new object[] { Array.Empty<SceneSetup>() });
            Assert.That(SceneManager.GetActiveScene().IsValid(), Is.True);
            Assert.That(SceneManager.GetActiveScene().isLoaded, Is.True);
            type.GetMethod("AuthorAndCaptureEnvironmentCandidates", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);
            UnityEngine.Debug.Log("ENVIRONMENT_V4_STAGE author-and-18-views-ms=" + stageClock.ElapsedMilliseconds);
            // V4 renderer-only delta: add two real eye-height views, without importing combat art.
            type.GetMethod("CaptureEnvironmentPolishCloseups", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);
            UnityEngine.Debug.Log("ENVIRONMENT_V4_STAGE complete-20-views-ms=" + stageClock.ElapsedMilliseconds);
        }
    }
}
