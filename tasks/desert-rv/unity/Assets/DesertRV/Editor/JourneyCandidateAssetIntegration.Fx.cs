using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneyCandidateAssetIntegration
    {
        [Serializable] public sealed class FxRequest
        {
            public int schema;
            public string id, sourceCommit;
            public float flashLifetimeSeconds, flashDiameterMeters, flashSpeedMetersPerSecond;
            public Color flashColor;
            public float arcWidthMeters, impactLifetimeSeconds, impactDiameterMeters, impactSpeedMetersPerSecond;
            public Color arcColor;
            public int arcSlots;
            public AssetPin arcSound;
        }
        [Serializable] public sealed class FxResult
        {
            public string status = "failed-fx-authoring", sourceCommit, parametersSha256;
            public bool visualCalibrated = false, audioAuditioned = false, gameplayReviewed = false, protectedSourcesUnchanged;
            public AssetPin muzzleFlashPrefab, arcPresentationPrefab;
            public string[] failures = Array.Empty<string>();
            public OutputFile[] outputs;
            public FilePin[] protectedFiles;
        }
        public static void ValidateFxRequestShape(FxRequest r, string sha)
        {
            Require(r != null && r.schema == 1 && Hash(r.sourceCommit, 40) && r.sourceCommit == sha &&
                Regex.IsMatch(r.id ?? "", "^[a-z0-9][a-z0-9-]{3,63}$"), "Explicit FX candidate ID/schema/current Actions SHA required.");
            Require(Finite(r.flashLifetimeSeconds) && r.flashLifetimeSeconds > 0 && r.flashLifetimeSeconds <= .1f &&
                Finite(r.flashDiameterMeters) && r.flashDiameterMeters >= .01f && r.flashDiameterMeters <= .2f &&
                Finite(r.flashSpeedMetersPerSecond) && r.flashSpeedMetersPerSecond >= 0 && r.flashSpeedMetersPerSecond <= 2,
                "Flash physical size/speed/short lifetime outside bounded candidate range.");
            Require(Finite(r.arcWidthMeters) && r.arcWidthMeters >= .002f && r.arcWidthMeters <= .08f &&
                Finite(r.impactLifetimeSeconds) && r.impactLifetimeSeconds > 0 && r.impactLifetimeSeconds <= .16f &&
                Finite(r.impactDiameterMeters) && r.impactDiameterMeters >= .005f && r.impactDiameterMeters <= .1f &&
                Finite(r.impactSpeedMetersPerSecond) && r.impactSpeedMetersPerSecond >= 0 && r.impactSpeedMetersPerSecond <= 3 &&
                r.arcSlots >= 3 && r.arcSlots <= 16 && r.arcSound != null, "Explicit bounded arc dimensions/slots and real audio required.");
            foreach (var color in new[] { r.flashColor, r.arcColor })
                Require(Finite(color.r) && Finite(color.g) && Finite(color.b) && Finite(color.a) &&
                    color.r >= 0 && color.g >= 0 && color.b >= 0 && color.maxColorComponent > 0 && color.maxColorComponent <= 8 && color.a > 0 && color.a <= 1,
                    "Explicit finite nonzero FX color required.");
        }
        static AssetPin PinAsset(string path) => new AssetPin { path = path, sha256 = JourneyDiagnosticScope.HashFile(path),
            dependencyHash = AssetDatabase.GetAssetDependencyHash(path).ToString(), dependencySha256 = JourneyContentChecks.DependencySha256(path) };
        static Material FxMaterial(string folder, string name, bool streak)
        {
            // Original analytic texture; no downloaded/restricted art and no combat placeholder geometry.
            var texture = new Texture2D(32, 32, TextureFormat.RGBA32, false);
            try
            {
                for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++)
                {
                    float a = (x + .5f) / 16 - 1, b = (y + .5f) / 16 - 1;
                    float light = streak ? Mathf.Pow(Mathf.Clamp01(1 - Mathf.Abs(b)), 2) :
                        Mathf.Pow(Mathf.Clamp01(1 - Mathf.Sqrt(a * a + b * b)), 2) * .75f +
                        .25f * Mathf.Pow(Mathf.Clamp01(1 - Mathf.Min(Mathf.Abs(a), Mathf.Abs(b)) * 8), 3) * Mathf.Clamp01(1 - Mathf.Max(Mathf.Abs(a), Mathf.Abs(b)));
                    texture.SetPixel(x, y, new Color(light, light, light, light));
                }
                texture.Apply(); File.WriteAllBytes(folder + "/" + name + ".png", texture.EncodeToPNG());
            }
            finally { Object.DestroyImmediate(texture); }
            string texturePath = folder + "/" + name + ".png"; AssetDatabase.ImportAsset(texturePath, ImportAssetOptions.ForceSynchronousImport);
            var importer = (TextureImporter)AssetImporter.GetAtPath(texturePath);
            importer.textureType = TextureImporterType.Default; importer.sRGBTexture = true; importer.alphaSource = TextureImporterAlphaSource.FromInput;
            importer.mipmapEnabled = false; importer.wrapMode = TextureWrapMode.Clamp; importer.filterMode = FilterMode.Bilinear; importer.SaveAndReimport();
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit"); Require(shader && shader.isSupported, "Actual supported URP particle shader required.");
            var material = new Material(shader) { name = name, renderQueue = (int)RenderQueue.Transparent };
            material.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath)); material.SetColor("_BaseColor", Color.white);
            material.SetFloat("_Surface", 1); material.SetFloat("_Blend", 2); material.SetFloat("_ZWrite", 0);
            material.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha); material.SetFloat("_DstBlend", (float)BlendMode.One);
            material.SetFloat("_Cull", (float)CullMode.Off); material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            material.SetOverrideTag("RenderType", "Transparent");
            AssetDatabase.CreateAsset(material, folder + "/" + name + ".mat"); return material;
        }
        [Serializable] sealed class FxMaterialSaveEvidence
        {
            public string path, beforeSha256, afterSha256, metaSha256;
            public string[] removedSerializedLines, addedSerializedLines, nativeAssetTypes;
            public bool secondSaveStable, allNativeObjectsClean;
        }
        static Material CheckFxMaterial(string path, string texturePath, string textureGuid)
        {
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            Require(material && EditorUtility.IsPersistent(material) && AssetDatabase.IsMainAsset(material) &&
                AssetDatabase.GetAssetPath(material) == path && material.shader && material.shader.name == "Universal Render Pipeline/Particles/Unlit" && material.shader.isSupported,
                "Generated FX material lost its persistent URP particle shader identity.");
            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath);
            Require(texture && AssetDatabase.AssetPathToGUID(texturePath) == textureGuid && material.GetTexture("_BaseMap") == texture &&
                material.GetColor("_BaseColor").Equals(Color.white) && material.GetTextureScale("_BaseMap").Equals(Vector2.one) &&
                material.GetTextureOffset("_BaseMap").Equals(Vector2.zero), "Generated FX texture/GUID/color/UV meaning changed during save.");
            Require(material.renderQueue == (int)RenderQueue.Transparent && material.GetTag("RenderType", false) == "Transparent" &&
                material.IsKeywordEnabled("_SURFACE_TYPE_TRANSPARENT") && material.GetFloat("_Surface") == 1 && material.GetFloat("_Blend") == 2 &&
                material.GetFloat("_ZWrite") == 0 && material.GetFloat("_SrcBlend") == (float)BlendMode.SrcAlpha &&
                material.GetFloat("_DstBlend") == (float)BlendMode.One && material.GetFloat("_Cull") == (float)CullMode.Off,
                "Generated FX transparency/additive blend/depth/cull meaning changed during save.");
            return material;
        }
        static string[] FxMaterialLines(string path)
        {
            var lines = File.ReadAllLines(path);
            Require(new FileInfo(path).Length <= 65536 && lines.Length <= 1024 && lines.All(line => line.Length <= 512), "Generated FX material serialization exceeds diagnostic bounds.");
            return lines;
        }
        static void SaveAndReimportFxMaterial(string path, string texturePath, string textureGuid)
        {
            CheckFxMaterial(path, texturePath, textureGuid);
            // Save only this generated file, including URP's native AssetVersion subasset. No global SaveAssets.
            AssetDatabase.SaveAssetIfDirty(AssetDatabase.GUIDFromAssetPath(path));
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            AssetDatabase.SaveAssetIfDirty(AssetDatabase.GUIDFromAssetPath(path));
            CheckFxMaterial(path, texturePath, textureGuid);
            var objects = AssetDatabase.LoadAllAssetsAtPath(path);
            Require(objects.Length > 0 && objects.All(value => value && EditorUtility.IsPersistent(value) && !EditorUtility.IsDirty(value)),
                "Generated FX material or native subasset remains dirty after its explicit save.");
        }
        static void FinalizeFxMaterials(string folder)
        {
            // Complete the real installed URP import/save lifecycle before freezing ANY FX dependency hash.
            var stableFiles = new Dictionary<string, string>();
            foreach (string name in new[] { "Flash", "Arc" })
            {
                string path = folder + "/" + name + ".mat", texturePath = folder + "/" + name + ".png";
                string textureGuid = AssetDatabase.AssetPathToGUID(texturePath), originalMeta = JourneyDiagnosticScope.HashFile(path + ".meta");
                Require(Hash(textureGuid, 32), "Generated FX texture GUID missing.");
                string before = JourneyDiagnosticScope.HashFile(path); var beforeLines = FxMaterialLines(path);
                SaveAndReimportFxMaterial(path, texturePath, textureGuid);
                string stable = JourneyDiagnosticScope.HashFile(path); var stableLines = FxMaterialLines(path);
                var removed = beforeLines.Except(stableLines).ToArray(); var added = stableLines.Except(beforeLines).ToArray();
                Require(removed.Length <= 128 && added.Length <= 128, "Generated FX serialization difference exceeds bounded field diagnostics.");
                SaveAndReimportFxMaterial(path, texturePath, textureGuid);
                Require(JourneyDiagnosticScope.HashFile(path) == stable && JourneyDiagnosticScope.HashFile(path + ".meta") == originalMeta,
                    "Generated FX material/metadata did not stabilize across two actual save/import cycles.");
                stableFiles.Add(path, stable); stableFiles.Add(path + ".meta", originalMeta);
                Debug.Log("JOURNEY_FX_MATERIAL_SAVE_STABLE " + JsonUtility.ToJson(new FxMaterialSaveEvidence {
                    path = path, beforeSha256 = before, afterSha256 = stable, metaSha256 = originalMeta,
                    removedSerializedLines = removed, addedSerializedLines = added,
                    nativeAssetTypes = AssetDatabase.LoadAllAssetsAtPath(path).Select(value => value.GetType().FullName).OrderBy(value => value).ToArray(),
                    secondSaveStable = true, allNativeObjectsClean = true }));
            }
            Require(stableFiles.All(file => JourneyDiagnosticScope.HashFile(file.Key) == file.Value) &&
                new[] { "Flash", "Arc" }.All(name => AssetDatabase.LoadAllAssetsAtPath(folder + "/" + name + ".mat").All(value => value && !EditorUtility.IsDirty(value))),
                "Finalizing one FX material changed the other material or left native state dirty.");
        }
        static ParticleSystem Particles(GameObject owner, Material material, float lifetime, float diameter, float speed, Color color, short count)
        {
            var particles = owner.AddComponent<ParticleSystem>(); particles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            particles.useAutoRandomSeed = false; particles.randomSeed = 431;
            var main = particles.main; main.playOnAwake = false; main.loop = false; main.duration = lifetime;
            main.startLifetime = lifetime; main.startSize = diameter; main.startSpeed = speed; main.startColor = color;
            main.maxParticles = count; main.gravityModifier = 0; main.simulationSpace = ParticleSystemSimulationSpace.World;
            // Imported hand rigs have scale 100. Shape-only scaling keeps sizes and velocities in metres.
            main.scalingMode = ParticleSystemScalingMode.Shape;
            var shape = particles.shape; shape.enabled = false;
            var emission = particles.emission; emission.enabled = true; emission.rateOverTime = 0; emission.rateOverDistance = 0;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0, count) });
            var colorOver = particles.colorOverLifetime; colorOver.enabled = true;
            var gradient = new Gradient(); gradient.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
                new[] { new GradientAlphaKey(1, 0), new GradientAlphaKey(0, 1) }); colorOver.color = gradient;
            var sizeOver = particles.sizeOverLifetime; sizeOver.enabled = true; sizeOver.size = new ParticleSystem.MinMaxCurve(1, AnimationCurve.Linear(0, 1, 1, .1f));
            var renderer = owner.GetComponent<ParticleSystemRenderer>(); renderer.sharedMaterial = material; renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.shadowCastingMode = ShadowCastingMode.Off; renderer.receiveShadows = false;
            return particles;
        }
        public static void FreezeSelectedFxInputFromEnvironment()
        {
            Require(!Application.isPlaying && !BuildPipeline.isBuildingPlayer, "Freeze FX input in EditMode only.");
            var pin = new FilePin { path = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_FX_SELECTION"), sha256 = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_FX_SELECTION_SHA256") };
            FileCheck(pin, "JourneyEvidence/"); var r = JsonUtility.FromJson<FxRequest>(File.ReadAllText(pin.path));
            Require(r != null, "Missing selected FX JSON.");
            if (string.IsNullOrEmpty(r.sourceCommit)) r.sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA");
            ValidateFxRequestShape(r, Environment.GetEnvironmentVariable("GITHUB_SHA")); r.arcSound = CompleteSelectedAsset(r.arcSound);
            FileCheck(pin, "JourneyEvidence/"); WriteFreshInput(Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_FX_INPUT"), r);
        }
        static Scene[] FxOriginalScenes() => Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
        internal static void WithFxPreviewScene(Action<Scene> author)
        {
            var original = FxOriginalScenes();
            Require(original.All(scene => !scene.isDirty), "Save/discard dirty scenes before FX authoring.");
            var active = SceneManager.GetActiveScene();
            var roots = original.ToDictionary(scene => scene.handle, scene => scene.GetRootGameObjects().Select(go => go.GetInstanceID()).OrderBy(id => id).ToArray());
            var preview = EditorSceneManager.NewPreviewScene();
            try { author(preview); }
            finally
            {
                try { if (preview.IsValid()) Require(EditorSceneManager.ClosePreviewScene(preview) && !preview.IsValid(), "FX preview cleanup failed."); }
                finally
                {
                    var after = FxOriginalScenes();
                    Require(after.Select(scene => scene.handle).SequenceEqual(original.Select(scene => scene.handle)) && SceneManager.GetActiveScene() == active &&
                        after.All(scene => !scene.isDirty && scene.GetRootGameObjects().Select(go => go.GetInstanceID()).OrderBy(id => id).SequenceEqual(roots[scene.handle])),
                        "FX preview changed an original scene, root object, dirty state or active scene.");
                }
            }
        }
        internal static GameObject FxObject(string name, Scene preview, Transform parent = null)
        {
            Require(preview.IsValid() && EditorSceneManager.IsPreviewScene(preview) && (!parent || parent.gameObject.scene == preview), "FX objects require the owned preview scene.");
            var value = new GameObject(name);
            try { SceneManager.MoveGameObjectToScene(value, preview); if (parent) value.transform.SetParent(parent, false); return value; }
            catch { Object.DestroyImmediate(value); throw; }
        }
        public static void AuthorFxFromEnvironment()
        {
            Require(!Application.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode && !BuildPipeline.isBuildingPlayer, "FX authoring is explicit EditMode work only.");
            Require(FxOriginalScenes().All(scene => !scene.isDirty), "Save/discard dirty scenes before FX authoring.");
            var pin = new FilePin { path = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_FX_INPUT"), sha256 = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_FX_INPUT_SHA256") };
            FileCheck(pin, "JourneyEvidence/"); var r = JsonUtility.FromJson<FxRequest>(File.ReadAllText(pin.path)); ValidateFxRequestShape(r, Environment.GetEnvironmentVariable("GITHUB_SHA"));
            var audio = Load<AudioClip>(r.arcSound); Require(audio.length > 0, "Actual playable arc sound required.");
            string parent = JourneySceneAuthoring.Folder + "/CandidateFx", folder = parent + "/" + r.id;
            Require(Directory.Exists(JourneySceneAuthoring.Folder) && !Directory.Exists(folder) && !File.Exists(folder + ".meta"), "Run after Journey candidate authoring and use a fresh FX ID; never replace assets/metas.");
            string[] files = { "Flash.png", "Flash.mat", "Arc.png", "Arc.mat", "MuzzleFlash.prefab", "ArcPresentation.prefab" };
            var outputs = files.Select(f => folder + "/" + f).ToArray();
            var allowed = outputs.SelectMany(p => new[] { p, p + ".meta" }).Concat(new[] { parent + ".meta", folder + ".meta" }).ToArray();
            var protectedFiles = SnapshotProtected(allowed); var result = new FxResult { sourceCommit = r.sourceCommit, parametersSha256 = pin.sha256 };
            GameObject flash = null, arc = null;
            try
            {
                WithFxPreviewScene(temporary => {
                Directory.CreateDirectory(folder); AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                var flashMaterial = FxMaterial(folder, "Flash", false); var arcMaterial = FxMaterial(folder, "Arc", true);
                flash = FxObject("Candidate muzzle short flash (unreviewed)", temporary);
                Particles(flash, flashMaterial, r.flashLifetimeSeconds, r.flashDiameterMeters, r.flashSpeedMetersPerSecond, r.flashColor, 1);
                Require(PrefabUtility.SaveAsPrefabAsset(flash, folder + "/MuzzleFlash.prefab"), "Flash prefab save failed.");
                arc = FxObject("Candidate arc presentation (unreviewed)", temporary);
                var presenter = arc.AddComponent<ArcPresentation>(); presenter.enabled = false;
                var source = FxObject("Candidate arc source", temporary, arc.transform).transform; presenter.source = source;
                presenter.audioSource = source.gameObject.AddComponent<AudioSource>(); presenter.audioSource.playOnAwake = false;
                presenter.audioSource.spatialBlend = 1; presenter.audioSource.minDistance = 2; presenter.audioSource.maxDistance = 24; presenter.arcSound = audio;
                presenter.beams = new LineRenderer[r.arcSlots]; presenter.impacts = new ParticleSystem[r.arcSlots];
                for (int i = 0; i < r.arcSlots; i++)
                {
                    var beam = FxObject("Arc beam " + i, temporary, arc.transform).AddComponent<LineRenderer>();
                    beam.sharedMaterial = arcMaterial; beam.useWorldSpace = true; beam.positionCount = 2; beam.SetPositions(new[] { Vector3.zero, Vector3.zero });
                    beam.startWidth = r.arcWidthMeters; beam.endWidth = r.arcWidthMeters * .4f; beam.startColor = r.arcColor; beam.endColor = r.arcColor;
                    beam.textureMode = LineTextureMode.Stretch; beam.shadowCastingMode = ShadowCastingMode.Off; beam.receiveShadows = false; beam.enabled = false;
                    var impact = FxObject("Arc impact " + i, temporary, arc.transform);
                    presenter.beams[i] = beam; presenter.impacts[i] = Particles(impact, flashMaterial, r.impactLifetimeSeconds, r.impactDiameterMeters, r.impactSpeedMetersPerSecond, r.arcColor, 5);
                }
                Require(PrefabUtility.SaveAsPrefabAsset(arc, folder + "/ArcPresentation.prefab"), "Arc prefab save failed.");
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                FinalizeFxMaterials(folder);
                result.muzzleFlashPrefab = PinAsset(folder + "/MuzzleFlash.prefab"); result.arcPresentationPrefab = PinAsset(folder + "/ArcPresentation.prefab");
                FileCheck(pin, "JourneyEvidence/"); result.protectedSourcesUnchanged = false; VerifyProtected(protectedFiles, allowed); result.protectedSourcesUnchanged = true;
                result.outputs = outputs.Select(p => new OutputFile { path = p, sha256 = JourneyDiagnosticScope.HashFile(p), dependencyHash = AssetDatabase.GetAssetDependencyHash(p).ToString(), dependencySha256 = JourneyContentChecks.DependencySha256(p) }).ToArray();
                result.status = "ORIGINAL_NATIVE_FX_AUTHORED_UNCALIBRATED";
                });
            }
            catch (Exception error) { result.status = "failed-fx-authoring"; result.failures = new[] { error.ToString() }; throw; }
            finally
            {
                if (flash) Object.DestroyImmediate(flash); if (arc) Object.DestroyImmediate(arc);
                try { result.protectedSourcesUnchanged = false; VerifyProtected(protectedFiles, allowed); result.protectedSourcesUnchanged = true; }
                catch (Exception error) { result.status = "failed-fx-protection"; result.failures = result.failures.Concat(new[] { error.ToString() }).ToArray(); throw; }
                finally
                {
                    result.protectedFiles = protectedFiles.OrderBy(p => p.Key).Select(p => new FilePin { path = p.Key, sha256 = p.Value }).ToArray();
                    Directory.CreateDirectory("JourneyEvidence"); File.WriteAllText("JourneyEvidence/journey-candidate-fx.json", JsonUtility.ToJson(result, true));
                }
            }
        }
    }
}
