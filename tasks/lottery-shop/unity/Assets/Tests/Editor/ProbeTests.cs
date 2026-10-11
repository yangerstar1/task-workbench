using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.InputSystem.EnhancedTouch;
using Lottery.Probe.Editor;
namespace Lottery.Probe.Tests
{
    public sealed class ProbeTests
    {
        [OneTimeSetUp] public void PrepareGeneratedAssets() { ProbeBuild.Prepare(); }
        [Test] public void EditorPatchPinned() { Assert.That(Application.unityVersion, Is.EqualTo("6000.3.19f1")); }
        [Test] public void RequiredPackagesResolved()
        {
            var packages = UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages().ToDictionary(p => p.name, p => p.version);
            Assert.That(packages["com.unity.render-pipelines.universal"], Is.EqualTo("17.3.0"));
            Assert.That(packages["com.unity.inputsystem"], Is.EqualTo("1.20.1"));
            Assert.That(packages["com.unity.test-framework"], Is.EqualTo("1.6.0"));
        }
        [Test] public void UrpAssetsSurviveReimport()
        {
            AssetDatabase.ImportAsset(ProbeBuild.PipelinePath, ImportAssetOptions.ForceUpdate);
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(ProbeBuild.PipelinePath);
            var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(ProbeBuild.RendererPath);
            Assert.That(pipeline, Is.Not.Null); Assert.That(renderer, Is.Not.Null);
            var data = new SerializedObject(pipeline).FindProperty("m_RendererDataList");
            Assert.That(data, Is.Not.Null); Assert.That(data.arraySize, Is.GreaterThanOrEqualTo(1));
            Assert.That(data.GetArrayElementAtIndex(0).objectReferenceValue, Is.EqualTo(renderer));
            Assert.That(GraphicsSettings.defaultRenderPipeline, Is.EqualTo(pipeline));
            Assert.That(QualitySettings.renderPipeline, Is.EqualTo(pipeline));
        }
        [Test] public void ChineseFontContainsRequiredGlyphs()
        {
            var font = AssetDatabase.LoadAssetAtPath<Font>("Assets/Resources/ProbeChinese.otf");
            Assert.That(font, Is.Not.Null);
            foreach (char c in "技术探针非游戏成品中文刮奖小店兑奖借款消耗输入触点坐标屏幕安全区仅检查显示与不代表真机或手感验收通过￥100×·".Distinct())
                Assert.That(font.HasCharacter(c), Is.True, "Missing glyph " + c);
        }
        [Test] public void InputBackendAndLifecycle()
        {
#if ENABLE_INPUT_SYSTEM
            bool before = EnhancedTouchSupport.enabled;
            EnhancedTouchSupport.Enable();
            try { Assert.That(EnhancedTouchSupport.enabled, Is.True); }
            finally { EnhancedTouchSupport.Disable(); }
            Assert.That(EnhancedTouchSupport.enabled, Is.EqualTo(before));
            var safe = new Rect(0, 0, 1000, 600);
            Assert.That(ProbeRuntime.HitsLicenseButton(new Vector2(900, 40), safe, 600), Is.True);
            Assert.That(ProbeRuntime.HitsLicenseButton(new Vector2(20, 40), safe, 600), Is.False);
            Assert.That(ProbeRuntime.HitsLicenseButton(new Vector2(900, 100), safe, 600), Is.False);
            Assert.That(ProbeRuntime.HitsLicenseButton(new Vector2(800, 70), new Rect(40, 30, 900, 520), 600), Is.True);
#else
            Assert.Fail("Input System backend was not enabled before compilation");
#endif
        }
        [Test] public void SceneReferencesFontAndUrpMaterial()
        {
            var scene = UnityEditor.SceneManagement.EditorSceneManager.OpenScene(ProbeBuild.ScenePath);
            var roots = scene.GetRootGameObjects();
            var runtime = roots.SelectMany(r => r.GetComponentsInChildren<Lottery.Probe.ProbeRuntime>()).Single();
            Assert.That(runtime.chineseFont, Is.Not.Null);
            var license = Resources.Load<TextAsset>("ProbeFontLicense");
            Assert.That(license, Is.Not.Null);
            Assert.That(license.text, Does.Contain("SIL OPEN FONT LICENSE"));
            var material = roots.SelectMany(r => r.GetComponentsInChildren<Renderer>()).Single().sharedMaterial;
            Assert.That(material, Is.Not.Null); Assert.That(material.shader, Is.Not.Null);
            Assert.That(material.shader.name, Is.EqualTo("Universal Render Pipeline/Lit"));
            Assert.That(AssetDatabase.GetAssetPath(material), Does.StartWith(ProbeBuild.Generated));
            Assert.That(roots.SelectMany(r => r.GetComponentsInChildren<Camera>()).Count(), Is.EqualTo(1));
        }
    }
}
