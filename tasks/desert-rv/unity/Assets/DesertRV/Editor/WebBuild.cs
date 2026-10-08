using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace DesertRV.Editor
{
    public static class WebBuild
    {
        const string Root = "Assets/DesertRV";
        const string ScenePath = Root + "/Scenes/WebPreflight.unity";

        public static void Prepare()
        {
            Directory.CreateDirectory(Root + "/Scenes");
            Directory.CreateDirectory(Root + "/Settings");
            AssetDatabase.Refresh();
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(Root + "/Settings/WebURP.asset");
            if (!pipeline)
            {
                var renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(renderer, Root + "/Settings/WebRenderer.asset");
                pipeline = UniversalRenderPipelineAsset.Create(renderer);
                pipeline.msaaSampleCount = 2;
                pipeline.shadowDistance = 45;
                pipeline.mainLightShadowmapResolution = 2048;
                pipeline.supportsHDR = false;
                pipeline.supportsCameraDepthTexture = false;
                pipeline.supportsCameraOpaqueTexture = false;
                AssetDatabase.CreateAsset(pipeline, Root + "/Settings/WebURP.asset");
            }
            GraphicsSettings.defaultRenderPipeline = pipeline;
            // Web starts from its platform-default quality level, not the Editor's selection.
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = pipeline;
                QualitySettings.shadows = UnityEngine.ShadowQuality.All;
                QualitySettings.shadowDistance = 45;
            }
            var pipelineSettings = new SerializedObject(pipeline);
            pipelineSettings.FindProperty("m_SoftShadowsSupported").boolValue = true;
            pipelineSettings.ApplyModifiedPropertiesWithoutUndo();
            QualitySettings.vSyncCount = 0;
            PlayerSettings.companyName = "Local Prototype";
            PlayerSettings.productName = "Desert RV - Technical Preflight";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.runInBackground = false;
            PlayerSettings.defaultWebScreenWidth = 1280;
            PlayerSettings.defaultWebScreenHeight = 720;
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
            PlayerSettings.WebGL.decompressionFallback = false;
            PlayerSettings.WebGL.dataCaching = false;
            PlayerSettings.WebGL.template = "PROJECT:DesertRV";
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.WebGL, ScriptingImplementation.IL2CPP);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var cameraObject = new GameObject("Preflight Camera");
            var camera = cameraObject.AddComponent<Camera>();
            cameraObject.tag = "MainCamera";
            camera.transform.position = new Vector3(5, 4, -7);
            camera.transform.LookAt(new Vector3(0, 0.7f, 0));
            camera.backgroundColor = new Color(.13f, .18f, .23f);
            camera.clearFlags = CameraClearFlags.SolidColor;
            cameraObject.AddComponent<UniversalAdditionalCameraData>();
            var light = new GameObject("Main Light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(48, -35, 0);
            light.intensity = 1.6f;
            light.shadows = LightShadows.Soft;
            light.gameObject.AddComponent<UniversalAdditionalLightData>();
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.42f, .49f, .58f);
            RenderSettings.ambientEquatorColor = new Color(.25f, .29f, .33f);
            RenderSettings.ambientGroundColor = new Color(.16f, .18f, .2f);
            MakeShape("Ground", PrimitiveType.Cube, new Vector3(0, -.2f, 0), new Vector3(14, .4f, 14), new Color(.35f, .39f, .4f));
            var subject = MakeShape("Material test", PrimitiveType.Cube, new Vector3(0, 1, 0), new Vector3(1.8f, 2, 1.8f), new Color(.1f, .46f, .57f));
            MakeShape("Smooth normal test", PrimitiveType.Sphere, new Vector3(-2.4f, .8f, 1), Vector3.one * 1.6f, new Color(.75f, .4f, .15f));
            var fixture = new GameObject("Technical Test").AddComponent<WebPreflight>();
            fixture.subject = subject.transform;
            fixture.view = camera;
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log("DESERT_RV_PREFLIGHT_PREPARED: Unity=" + Application.unityVersion + "; URP=" + pipeline.name);
        }

        static GameObject MakeShape(string name, PrimitiveType primitive, Vector3 position, Vector3 scale, Color color)
        {
            var go = GameObject.CreatePrimitive(primitive);
            go.name = name;
            go.transform.position = position;
            go.transform.localScale = scale;
            var path = Root + "/Settings/" + name.Replace(" ", "") + ".mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!material)
            {
                material = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                material.SetColor("_BaseColor", color);
                material.SetFloat("_Smoothness", .28f);
                AssetDatabase.CreateAsset(material, path);
            }
            go.GetComponent<Renderer>().sharedMaterial = material;
            return go;
        }

        public static void BuildPreflight()
        {
            Prepare();
            string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../build/web-preflight"));
            Directory.CreateDirectory(output);
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { ScenePath }, locationPathName = output,
                target = BuildTarget.WebGL, options = BuildOptions.None
            });
            var summary = report.summary;
            File.WriteAllText(Path.Combine(output, "build-result.txt"), $"result={summary.result}\nbytes={summary.totalSize}\nseconds={summary.totalTime.TotalSeconds:F1}\n");
            if (summary.result != BuildResult.Succeeded) throw new Exception("Web preflight build failed: " + summary.result);
            Debug.Log("DESERT_RV_WEB_BUILD_SUCCEEDED: " + output);
        }
    }
}
