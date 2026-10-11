using System;
using System.Reflection;
using NUnit.Framework;

namespace DesertRV.Tests
{
    // A separate single-case gate; original strict/preparation/boundary case inventories stay unchanged.
    public sealed class JourneyRestorationTests
    {
        static void VerifyPinnedCaptureCacheClassification()
        {
            var authoring = Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor", true);
            var classify = authoring.GetMethod("ClassifyPinnedCaptureCache", BindingFlags.NonPublic | BindingFlags.Static);
            Assert.That(classify, Is.Not.Null);
            // Five real r2 object identities and immutable producer bytes; no Unity objects are modified.
            var cases = new[] {
                new object[] { "Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf", "UnityEngine.Texture2D", "43a8f4976b2571d50b5bff0508efaab7", 2800000L, "a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b", 16437340L, "e4c83478e2ad31187b1c6dd2cce61e2630c06b57c4e5727c6303af491718d09e", 481L, "", "", true, true },
                new object[] { "Packages/com.unity.render-pipelines.universal/Shaders/Lit.shader", "UnityEngine.Shader", "933532a4fcc9baf4fa0491de14d08ed7", 4800000L, "6f4648b6b5271132cfed1d7d7c771ba0a73ef7972470d6694047804d259c0997", 22877L, "f0db005307ffe5480c40a402ca5bfb0b3726259031a86e255e49626228ceb008", 217L, "com.unity.render-pipelines.universal", "17.3.0", false, false },
                new object[] { "Packages/com.unity.render-pipelines.universal/Shaders/Particles/ParticlesSimpleLit.shader", "UnityEngine.Shader", "8516d7a69675844a7a0b7095af7c46af", 4800000L, "5bd621c3363a1eba55fdd9e3594b16116ede25d883e3717d80d58be2dcbe9bb5", 19403L, "06e436bf99c1e986f57625313f6c3320e92908c0acc671bf0afa8f9a42a739d0", 204L, "com.unity.render-pipelines.universal", "17.3.0", false, false },
                new object[] { "Packages/com.unity.render-pipelines.universal/Shaders/Particles/ParticlesUnlit.shader", "UnityEngine.Shader", "0406db5a14f94604a8c57ccfbc9f3b46", 4800000L, "1cd8356cf8cb67f065b7d2f67b071190a675a98c8cdea5a45028c0cb3c9e1e18", 12430L, "122a44759a8ca196415d39727a270c5554553e8270b0cd7871cc45939cd996a4", 217L, "com.unity.render-pipelines.universal", "17.3.0", false, false },
                new object[] { "Packages/com.unity.render-pipelines.universal/Shaders/Unlit.shader", "UnityEngine.Shader", "650dd9526735d5b46b79224bc6e94025", 4800000L, "37ef434d3bd626d59f2aa813fed56850eab15e3b759c2399212f2cc1a4d08964", 11416L, "367956a85cb4183e5f8afd33b78f3a048fe08d5767e42e11b4b127b780acfaf2", 195L, "com.unity.render-pipelines.universal", "17.3.0", false, false },
            };
            var restoration = Type.GetType("DesertRV.Editor.JourneyCandidateRestoration, Assembly-CSharp-Editor", true);
            var errorClass = restoration.GetMethod("ErrorClass", BindingFlags.NonPublic | BindingFlags.Static);
            Assert.That(errorClass, Is.Not.Null);
            foreach (string code in new[] { "CACHE_PACKAGE_IDENTITY", "CACHE_ASSET_BYTES", "CACHE_META_BYTES", "CACHE_SUBASSET_RELATION",
                "CACHE_FONT_NOT_LOADED", "CACHE_FONT_IDENTITY", "CACHE_FONT_NOT_DYNAMIC", "CACHE_FONT_ATLAS_LINK" })
                Assert.That(errorClass.Invoke(null, new object[] { new InvalidOperationException("JOURNEY_WORLD_HUD_" + code) }), Is.EqualTo(code));
            foreach (var row in cases)
            {
                string expected = (string)row[1] == "UnityEngine.Shader" ? "OFFICIAL_URP_SHADER_CACHE" : "DYNAMIC_FONT_ATLAS_CACHE";
                Assert.That(classify.Invoke(null, row), Is.EqualTo(expected));
                // Every identity, source-byte and package-ownership component is individually necessary.
                for (int index = 0; index < 10; index++)
                {
                    var wrong = (object[])row.Clone();
                    wrong[index] = wrong[index] is long value ? (object)(value + 1) : (string)wrong[index] + "-wrong";
                    Assert.That(classify.Invoke(null, wrong), Is.EqualTo("AUTHORING_OR_UNKNOWN"), "Changed cache evidence field " + index);
                }
                foreach (string wrongType in new[] { "UnityEngine.Material", "UnityEngine.Font", "UnityEditor.TrueTypeFontImporter", "UnityEngine.GameObject" })
                {
                    var wrong = (object[])row.Clone(); wrong[1] = wrongType;
                    Assert.That(classify.Invoke(null, wrong), Is.EqualTo("AUTHORING_OR_UNKNOWN"));
                }
                var wrongOwnership = (object[])row.Clone(); wrongOwnership[11] = !(bool)row[11];
                Assert.That(classify.Invoke(null, wrongOwnership), Is.EqualTo("AUTHORING_OR_UNKNOWN"));
                if (expected == "DYNAMIC_FONT_ATLAS_CACHE")
                {
                    var notDynamicAtlas = (object[])row.Clone(); notDynamicAtlas[10] = false;
                    Assert.That(classify.Invoke(null, notDynamicAtlas), Is.EqualTo("AUTHORING_OR_UNKNOWN"));
                }
            }
        }
        static void VerifyWarmLampSerializedContract()
        {
            var authoring = Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor", true);
            var validate = authoring.GetMethod("ValidateWarmLampSerializedChange", BindingFlags.NonPublic | BindingFlags.Static);
            Assert.That(validate, Is.Not.Null);
            // Pure text fixture using the pinned source's actual fields; no asset is loaded or written.
            const string before = "Material:\n  m_Shader: {fileID: 4800000, guid: 933532a4fcc9baf4fa0491de14d08ed7, type: 3}\n" +
                "  m_ValidKeywords:\n  - _EMISSION\n  m_InvalidKeywords: []\n  m_LightmapFlags: 4\n  m_CustomRenderQueue: -1\n" +
                "  disabledShaderPasses:\n  - MOTIONVECTORS\n  m_SavedProperties:\n    m_TexEnvs:\n    - _BaseMap:\n        m_Texture: {fileID: 0}\n" +
                "    m_Floats:\n    - _Metallic: 0\n    - _Smoothness: 0.12\n    m_Colors:\n" +
                "    - _BaseColor: {r: 1, g: 0.76, b: 0.38, a: 1}\n    - _Color: {r: 1, g: 0.76, b: 0.37999994, a: 1}\n" +
                "    - _EmissionColor: {r: 2.5, g: 1.9, b: 0.95, a: 2.5}\n--- !u!114 &2086780894777222751\nMonoBehaviour:\n  version: 10\n";
            string giOnly = before.Replace("m_LightmapFlags: 4", "m_LightmapFlags: 2");
            string authored = giOnly.Replace("_Color: {r: 1, g: 0.76, b: 0.37999994, a: 1}", "_Color: {r: 1, g: 0.76, b: 0.38, a: 1}");
            Assert.That(validate.Invoke(null, new object[] { before, giOnly }), Is.EqualTo(new[] { "GLOBAL_ILLUMINATION_FLAGS_4_TO_2" }));
            Assert.That(validate.Invoke(null, new object[] { before, authored }), Is.EqualTo(new[] { "GLOBAL_ILLUMINATION_FLAGS_4_TO_2", "LEGACY_COLOR_SYNCHRONIZED_TO_BASE_COLOR" }));
            var rejected = new[] {
                new[] { before, "GI" },
                new[] { authored.Replace("m_LightmapFlags: 2", "m_LightmapFlags: 0"), "GI" },
                new[] { authored.Replace("  - _EMISSION\n", ""), "KEYWORD" },
                new[] { authored.Replace("  - _EMISSION\n", "  - _EMISSION\n  - _NORMALMAP\n"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("m_InvalidKeywords: []", "m_InvalidKeywords: [_UNKNOWN]"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("_BaseColor: {r: 1", "_BaseColor: {r: 0.9"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("_EmissionColor: {r: 2.5", "_EmissionColor: {r: 2.6"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("_Color: {r: 1, g: 0.76, b: 0.38", "_Color: {r: 1, g: 0.76, b: 0.38000001"), "ALIAS" },
                new[] { authored.Replace("_Metallic: 0", "_Metallic: 0.2"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("_Smoothness: 0.12", "_Smoothness: 0.2"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("m_Texture: {fileID: 0}", "m_Texture: {fileID: 2800000, guid: 00000000000000000000000000000000, type: 3}"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("m_CustomRenderQueue: -1", "m_CustomRenderQueue: 2000"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("MOTIONVECTORS", "DEPTHONLY"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("933532a4fcc9baf4fa0491de14d08ed7", "00000000000000000000000000000000"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("version: 10", "version: 11"), "UNDECLARED_SERIALIZED_CHANGE" },
                new[] { authored.Replace("2086780894777222751", "2086780894777222752"), "UNDECLARED_SERIALIZED_CHANGE" },
            };
            foreach (var row in rejected)
            {
                var error = Assert.Throws<TargetInvocationException>(() => validate.Invoke(null, new object[] { before, row[0] }));
                Assert.That(error.InnerException, Is.TypeOf<InvalidOperationException>());
                Assert.That(error.InnerException.Message, Is.EqualTo("JOURNEY_WARM_LAMP_" + row[1]));
            }
        }
        [Test, Timeout(600000)]
        public void RevalidatePinnedRestoredJourney()
        {
            VerifyPinnedCaptureCacheClassification();
            VerifyWarmLampSerializedContract();
            var type = Type.GetType("DesertRV.Editor.JourneyCandidateRestoration, Assembly-CSharp-Editor", true);
            var parser = type.GetMethod("ParseConsumerRunId", BindingFlags.Public | BindingFlags.Static);
            Assert.That(parser, Is.Not.Null);
            const string expected = "https://github.com/yangerstar1/task-workbench/actions/runs/123";
            Assert.That(parser.Invoke(null, new object[] { new[] { "Unity", "-journeyRestorationRunId", "123", "-batchmode" }, expected }), Is.EqualTo("123"));
            foreach (var args in new[] {
                Array.Empty<string>(), new[] { "-journeyRestorationRunId" },
                new[] { "-journeyRestorationRunId", "123", "-journeyRestorationRunId", "123" },
                new[] { "-journeyRestorationRunId", "0" }, new[] { "-journeyRestorationRunId", "-1" },
                new[] { "-journeyRestorationRunId", "123/other" }, new[] { "-journeyRestorationRunId", "124" } })
            {
                var error = Assert.Throws<TargetInvocationException>(() => parser.Invoke(null, new object[] { args, expected }));
                Assert.That(error.InnerException, Is.TypeOf<InvalidOperationException>());
            }
            var method = type.GetMethod("RevalidatePinnedRestoredJourney", BindingFlags.Public | BindingFlags.Static);
            Assert.That(method, Is.Not.Null);
            try { method.Invoke(null, null); }
            catch (TargetInvocationException error) when (error.InnerException != null)
            {
                System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(error.InnerException).Throw();
                throw;
            }
        }
    }
}
