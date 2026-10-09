using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEditor.SceneManagement;
using UnityEditor;
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
            type.GetMethod("AuthorAndCaptureCorrectedTerrainCandidates", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);
            UnityEngine.Debug.Log("ENVIRONMENT_V4_STAGE author-and-18-views-ms=" + stageClock.ElapsedMilliseconds);
            // V4 renderer-only delta: add two real eye-height views, without importing combat art.
            type.GetMethod("CaptureEnvironmentPolishCloseups", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);
            var surface = Shader.Find("DesertRV/EnvironmentSurface");
            Assert.That(surface, Is.Not.Null); Assert.That(surface.isSupported, Is.True);
            Assert.That(UnityEditor.ShaderUtil.ShaderHasError(surface), Is.False, "Retained feathered overlay shader compiled without error after all actual captures");
            ValidateOpaqueTerrain();
            type.GetMethod("VerifyCorrectedTerrainCandidatesAfterCapture", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);
            UnityEngine.Debug.Log("ENVIRONMENT_V4_R3_SURFACE standard-lit-depth-normal-shadow shared-world-uv skirt-join-after-20-views");
            UnityEngine.Debug.Log("ENVIRONMENT_V4_STAGE complete-20-views-ms=" + stageClock.ElapsedMilliseconds);
        }
        static void ValidateOpaqueTerrain()
        {
            const string folder="Assets/DesertRV/Scenes/Journey/EnvironmentV4/";
            var sand=AssetDatabase.LoadAssetAtPath<Material>(folder+"Surface-Sand.mat");
            var dune=AssetDatabase.LoadAssetAtPath<Material>(folder+"Surface-Dune.mat");
            Assert.That(sand,Is.Not.Null);Assert.That(dune,Is.Not.Null);
            foreach(var material in new[]{sand,dune})
            {
                Assert.That(material.shader.name,Is.EqualTo("Universal Render Pipeline/Lit"));
                Assert.That(material.shader.isSupported,Is.True);
                Assert.That(ShaderUtil.ShaderHasError(material.shader),Is.False);
                foreach(string pass in new[]{"ForwardLit","DepthOnly","DepthNormals","ShadowCaster"})
                    Assert.That(material.FindPass(pass),Is.GreaterThanOrEqualTo(0),pass);
                Assert.That(material.GetFloat("_Surface"),Is.EqualTo(0));
                Assert.That(material.IsKeywordEnabled("_NORMALMAP"),Is.True);
                Assert.That(material.GetFloat("_BumpScale"),Is.EqualTo(.035f).Within(.000001f));
                Assert.That(material.GetFloat("_Smoothness"),Is.EqualTo(.04f).Within(.000001f));
                Assert.That(material.GetFloat("_Metallic"),Is.EqualTo(0));
                Assert.That(material.IsKeywordEnabled("_METALLICSPECGLOSSMAP"),Is.False);
            }
            Assert.That(dune.GetColor("_BaseColor"),Is.EqualTo(sand.GetColor("_BaseColor")));
            foreach(string property in new[]{"_BaseMap","_BumpMap"})
            {
                var texture=sand.GetTexture(property);Assert.That(texture,Is.Not.Null);
                Assert.That(dune.GetTexture(property),Is.EqualTo(texture));
                Assert.That(texture.filterMode,Is.EqualTo(FilterMode.Trilinear));
            }
            for(int region=1;region<=3;region++)foreach(string name in new[]{"Ground-Sand","ReliefEast-Dune","ReliefWest-Dune"})
            {
                var mesh=AssetDatabase.LoadAssetAtPath<Mesh>(folder+"R"+region+"-"+name+".asset");
                Assert.That(mesh,Is.Not.Null);var vertices=mesh.vertices;var uv=mesh.uv;var normals=mesh.normals;
                int joined=0;
                for(int i=0;i<vertices.Length;i++)
                {
                    Assert.That(uv[i].x,Is.EqualTo(vertices[i].x/2).Within(.0001f));
                    Assert.That(uv[i].y,Is.EqualTo(vertices[i].z/2).Within(.0001f));
                    if(name!="Ground-Sand"&&vertices[i].y<=-.03f)
                    {Assert.That(Vector3.Dot(normals[i],Vector3.up),Is.GreaterThan(.99999f));joined++;}
                }
                if(name!="Ground-Sand")Assert.That(joined,Is.GreaterThan(100));
            }
        }
    }
}
