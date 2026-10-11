using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneySceneAuthoring
    {
        const string SurfaceArtFolder = Folder + "/SurfaceArt";
        const string SandDiffuse = "Assets/DesertRV/Art/TerrainDiffuseCorrection/sand_03_diff_illumination_corrected_1k.png";
        const string AsphaltDiffuse = "Assets/DesertRV/Art/EnvironmentV4/asphalt_02_diff_1k.jpg";

        readonly struct SurfaceArtRole
        {
            internal readonly string objectName, fileName;
            internal readonly bool sand;
            internal SurfaceArtRole(string objectName, string fileName, bool sand)
            { this.objectName = objectName; this.fileName = fileName; this.sand = sand; }
        }

        static IEnumerable<SurfaceArtRole> SurfaceArtRoles()
        {
            yield return new SurfaceArtRole("Route foundation", "Foundation", true);
            yield return new SurfaceArtRole("Road surface", "Road", false);
            yield return new SurfaceArtRole("Far road continuation", "RoadAhead", false);
            yield return new SurfaceArtRole("Road behind arrival", "RoadBehind", false);
            for (int i = 0; i < 16; i++) yield return new SurfaceArtRole("Road shoulder patch " + i, "Shoulder-" + i.ToString("00"), true);
            for (int i = 0; i < 20; i++) yield return new SurfaceArtRole("Roadside sand lobe " + i, "Lobe-" + i.ToString("00"), true);
        }

        static void SurfaceRequire(bool ok, string message)
        { if (!ok) throw new InvalidOperationException("Surface art: " + message); }
        static string SurfaceMeshPath(int region, SurfaceArtRole role) => SurfaceArtFolder + "/R" + region + "-" + role.fileName + ".asset";
        static string SurfaceMaterialPath(bool sand) => SurfaceArtFolder + (sand ? "/Sand.mat" : "/Asphalt.mat");
        static float SurfaceTileMetres(bool sand) => sand ? 2f : 3f;
        static Color SurfaceTint(bool sand) => sand ? new Color(1.75f, 1.52f, 1.16f, 1) : new Color(.76f, .77f, .76f, 1);

        static Material SurfaceMaterial(bool sand)
        {
            string path = SurfaceMaterialPath(sand);
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material) { ValidateSurfaceMaterial(material, sand); return material; }
            SurfaceRequire(!File.Exists(path), "Refusing to replace an existing material: " + path);
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(sand ? SandDiffuse : AsphaltDiffuse);
            SurfaceRequire(shader && shader.isSupported && !ShaderUtil.ShaderHasError(shader) && texture, "Verified diffuse or supported URP Lit missing.");
            material = new Material(shader) { name = sand ? "Journey Sand Surface" : "Journey Asphalt Surface" };
            material.SetTexture("_BaseMap", texture);
            material.SetTextureScale("_BaseMap", Vector2.one); material.SetTextureOffset("_BaseMap", Vector2.zero);
            material.SetColor("_BaseColor", SurfaceTint(sand));
            material.SetFloat("_Metallic", 0); material.SetFloat("_Smoothness", sand ? .04f : .12f);
            material.SetColor("_EmissionColor", Color.black);
            // Diffuse-only candidate: original mesh normals, lights and all existing materials survive.
            // No new shader, normal map, emission, alpha overlay or geometry displacement.
            AssetDatabase.CreateAsset(material, path);
            // Only these two new owned materials are normalized. Complete URP's
            // saved native subasset lifecycle before any prepared dependency is pinned.
            byte[] meta = File.ReadAllBytes(path + ".meta");
            SaveAndReimportSurfaceMaterial(path, sand);
            byte[] stable = File.ReadAllBytes(path);
            material = SaveAndReimportSurfaceMaterial(path, sand);
            SurfaceRequire(File.ReadAllBytes(path).SequenceEqual(stable) && File.ReadAllBytes(path + ".meta").SequenceEqual(meta),
                "Owned surface material or metadata did not stabilize across two save/import cycles.");
            return material;
        }

        static Material SaveAndReimportSurfaceMaterial(string path, bool sand)
        {
            SurfaceRequire(path == SurfaceMaterialPath(sand), "Only the exact owned surface material may be finalized.");
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            SurfaceRequire(material && EditorUtility.IsPersistent(material) && AssetDatabase.IsMainAsset(material) &&
                material.shader && material.shader.name == "Universal Render Pipeline/Lit", "Owned URP Lit material missing.");
            // The public equivalent of URP 17.3 ShaderUtils.UpdateMaterial's Lit branch.
            // It synchronizes legacy aliases and the opaque, non-emissive keyword state.
            BaseShaderGUI.SetMaterialKeywords(material, UnityEditor.Rendering.Universal.ShaderGUI.LitGUI.SetMaterialKeywords);
            EditorUtility.SetDirty(material);
            AssetDatabase.SaveAssetIfDirty(AssetDatabase.GUIDFromAssetPath(path));
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            AssetDatabase.SaveAssetIfDirty(AssetDatabase.GUIDFromAssetPath(path));
            material = AssetDatabase.LoadAssetAtPath<Material>(path);
            ValidateSurfaceMaterial(material, sand);
            var objects = AssetDatabase.LoadAllAssetsAtPath(path);
            SurfaceRequire(objects.Length > 0 && objects.All(asset => asset && EditorUtility.IsPersistent(asset) && !EditorUtility.IsDirty(asset)),
                "Owned surface material or native subasset remains dirty after save/import.");
            return material;
        }

        static void ValidateSurfaceMaterial(Material material, bool sand)
        {
            SurfaceRequire(material && AssetDatabase.GetAssetPath(material) == SurfaceMaterialPath(sand) &&
                material.shader && material.shader.name == "Universal Render Pipeline/Lit" &&
                AssetDatabase.GetAssetPath(material.GetTexture("_BaseMap")) == (sand ? SandDiffuse : AsphaltDiffuse) &&
                material.GetTextureScale("_BaseMap") == Vector2.one && material.GetTextureOffset("_BaseMap") == Vector2.zero &&
                material.GetColor("_BaseColor") == SurfaceTint(sand) &&
                material.GetTexture("_MainTex") == material.GetTexture("_BaseMap") &&
                material.GetTextureScale("_MainTex") == Vector2.one && material.GetTextureOffset("_MainTex") == Vector2.zero &&
                material.GetColor("_Color") == SurfaceTint(sand) && material.GetColor("_EmissionColor") == Color.black &&
                Mathf.Approximately(material.GetFloat("_Smoothness"), sand ? .04f : .12f) &&
                Mathf.Approximately(material.GetFloat("_Metallic"), 0) &&
                material.GetFloat("_Surface") == 0 && material.GetFloat("_AlphaClip") == 0 && material.GetFloat("_ZWrite") == 1 &&
                material.renderQueue == (int)UnityEngine.Rendering.RenderQueue.Geometry && material.GetTag("RenderType", false) == "Opaque" &&
                !material.GetTexture("_BumpMap") && !material.GetTexture("_DetailAlbedoMap") && !material.GetTexture("_DetailNormalMap") &&
                !material.IsKeywordEnabled("_EMISSION") && !material.IsKeywordEnabled("_NORMALMAP") &&
                !material.IsKeywordEnabled("_DETAIL_MULX2") && !material.IsKeywordEnabled("_DETAIL_SCALED"), "Material identity/properties changed.");
        }

        static void AuthorPhysicalSurfaceArt(RegionBinding binding)
        {
            SurfaceRequire(binding && binding.region >= 1 && binding.region <= 3, "Unknown region.");
            if (!AssetDatabase.IsValidFolder(SurfaceArtFolder)) AssetDatabase.CreateFolder(Folder, "SurfaceArt");
            var colliders = binding.GetComponentsInChildren<Collider>(true);
            var colliderBytes = colliders.Select(c => EditorJsonUtility.ToJson(c)).ToArray();
            foreach (var role in SurfaceArtRoles())
            {
                var node = binding.transform.Find(role.objectName);
                SurfaceRequire(node && node.parent == binding.transform, "Missing exact direct-child surface: " + role.objectName);
                var filter = node.GetComponent<MeshFilter>(); var renderer = node.GetComponent<MeshRenderer>();
                SurfaceRequire(filter && filter.sharedMesh && renderer && filter.sharedMesh.isReadable, "Missing readable primitive mesh: " + role.objectName);
                string path = SurfaceMeshPath(binding.region, role);
                SurfaceRequire(!File.Exists(path), "Refusing to replace an existing projected mesh: " + path);
                var original = filter.sharedMesh;
                var mesh = Object.Instantiate(original); mesh.name = "R" + binding.region + "-" + role.fileName;
                var vertices = mesh.vertices; var uv = new Vector2[vertices.Length];
                for (int i = 0; i < vertices.Length; i++)
                {
                    Vector3 world = node.TransformPoint(vertices[i]);
                    uv[i] = new Vector2(world.x, world.z) / SurfaceTileMetres(role.sand);
                }
                mesh.uv = uv;
                SurfaceRequire(mesh.vertices.SequenceEqual(original.vertices) && mesh.normals.SequenceEqual(original.normals) &&
                    mesh.triangles.SequenceEqual(original.triangles) && mesh.bounds == original.bounds,
                    "Projection changed original geometry: " + role.objectName);
                AssetDatabase.CreateAsset(mesh, path); AssetDatabase.SaveAssetIfDirty(mesh);
                filter.sharedMesh = mesh; renderer.sharedMaterial = SurfaceMaterial(role.sand);
            }
            SurfaceRequire(binding.GetComponentsInChildren<Collider>(true).SequenceEqual(colliders) &&
                colliders.Select(c => EditorJsonUtility.ToJson(c)).SequenceEqual(colliderBytes), "Original collider inventory or values changed.");
            ValidatePhysicalSurfaceArt(binding);
        }

        static void ValidatePhysicalSurfaceArt(RegionBinding binding)
        {
            int count = 0;
            foreach (var role in SurfaceArtRoles())
            {
                var node = binding.transform.Find(role.objectName);
                SurfaceRequire(node && node.parent == binding.transform, "Saved surface missing: " + role.objectName);
                var filter = node.GetComponent<MeshFilter>(); var renderer = node.GetComponent<MeshRenderer>();
                SurfaceRequire(filter && filter.sharedMesh && renderer && filter.sharedMesh.isReadable &&
                    AssetDatabase.GetAssetPath(filter.sharedMesh) == SurfaceMeshPath(binding.region, role), "Saved mesh binding changed.");
                ValidateSurfaceMaterial(renderer.sharedMaterial, role.sand);
                var vertices = filter.sharedMesh.vertices; var uv = filter.sharedMesh.uv;
                SurfaceRequire(vertices.Length == uv.Length, "UV count changed.");
                for (int i = 0; i < vertices.Length; i++)
                {
                    Vector3 world = node.TransformPoint(vertices[i]);
                    SurfaceRequire((uv[i] - new Vector2(world.x, world.z) / SurfaceTileMetres(role.sand)).sqrMagnitude < 1e-10f,
                        "Saved physical texture scale/origin changed: " + role.objectName);
                }
                count++;
            }
            SurfaceRequire(count == 40, "Exact 40-surface region inventory required.");
            var foundation = binding.transform.Find("Route foundation").GetComponent<BoxCollider>();
            var road = binding.transform.Find("Road surface").GetComponent<BoxCollider>();
            SurfaceRequire(foundation && road && foundation.enabled && road.enabled && !foundation.isTrigger && !road.isTrigger,
                "Original two physical supports must remain enabled boxes.");
        }

        static Object LoadCleanSurfaceMainAsset(string path, Type expectedType, string stage)
        {
            SurfaceRequire(expectedType == typeof(Mesh) || expectedType == typeof(Material), "Unexpected surface asset type.");
            SurfaceRequire(File.Exists(path) && File.Exists(path + ".meta"), "Saved surface asset or metadata missing: " + path);
            var asset = AssetDatabase.LoadMainAssetAtPath(path);
            bool persistent = asset && EditorUtility.IsPersistent(asset), dirty = asset && EditorUtility.IsDirty(asset);
            bool loaded = AssetDatabase.IsMainAssetAtPathLoaded(path);
            int hideFlags = asset ? (int)asset.hideFlags : -1;
            string type = asset && asset.GetType() == expectedType ? expectedType.Name : "unexpected-or-missing";
            string hashes = "; sha256=" + HashFile(path) + "; metaSha256=" + HashFile(path + ".meta");
            Debug.Log("JOURNEY_SURFACE_RELOAD_ASSET stage=" + stage + "; path=" + path + "; type=" + type +
                "; persistent=" + persistent + "; dirty=" + dirty + "; hideFlags=" + hideFlags + "; loaded=" + loaded + hashes);
            SurfaceRequire(asset && asset.GetType() == expectedType && persistent && !dirty && loaded &&
                AssetDatabase.IsMainAsset(asset) && AssetDatabase.GetAssetPath(asset) == path,
                "Exact clean persistent main surface asset required: " + path);
            return asset;
        }

        static void UnloadSurfaceMainAsset(string path, Type expectedType)
        {
            var asset = LoadCleanSurfaceMainAsset(path, expectedType, "before-unload");
            int hideFlags = (int)asset.hideFlags;
            Resources.UnloadAsset(asset);
            asset = null;
            // Unity 6000.3 Object.bool may still report a Mesh/Material alive through its
            // PersistentManager instance ID. Test native residency without the old wrapper.
            // See AssetDatabase.IsMainAssetAtPathLoaded's official material unload example.
            bool loaded = AssetDatabase.IsMainAssetAtPathLoaded(path);
            Debug.Log("JOURNEY_SURFACE_RELOAD_ASSET stage=after-unload; path=" + path + "; type=" + expectedType.Name +
                "; hideFlags=" + hideFlags + "; loaded=" + loaded + "; sha256=" + HashFile(path) + "; metaSha256=" + HashFile(path + ".meta"));
            SurfaceRequire(!loaded, "Native main surface asset remains loaded: " + path);
        }

        // Called by the existing native preparation case, after the real saved integration.
        // Reloads every real region; it does not certify rendering, gameplay or Android.
        public static void ValidateSavedPhysicalSurfaceArt()
        {
            var setup = EditorSceneManager.GetSceneManagerSetup();
            SurfaceRequire(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "Save/discard scene edits before validation.");
            var paths = Enumerable.Range(1, 3).SelectMany(region => SurfaceArtRoles().Select(role => SurfaceMeshPath(region, role)))
                .Concat(new[] { SurfaceMaterialPath(true), SurfaceMaterialPath(false) }).ToArray();
            SurfaceRequire(paths.Length == 122 && paths.Distinct().Count() == 122, "Exact 122 surface main asset paths required.");
            var files = paths.Concat(RegionPaths).SelectMany(path => new[] { path, path + ".meta" }).ToArray();
            foreach (string path in files) SurfaceRequire(File.Exists(path), "Saved surface verification file missing: " + path);
            var hashes = files.ToDictionary(path => path, HashFile);
            // Preserve the original clean-asset precondition before closing any scenes.
            // Discard each wrapper here; reacquire it only after scene references are gone.
            foreach (string path in paths) LoadCleanSurfaceMainAsset(path,
                path.EndsWith(".mat", StringComparison.Ordinal) ? typeof(Material) : typeof(Mesh), "preflight");
            var failures = new List<Exception>();
            try
            {
                // Remove scene references before acquiring wrappers. Retain no Mesh/Material
                // wrapper across unload, and do not save/reimport while proving disk identity.
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                Debug.Log("JOURNEY_SURFACE_RELOAD_PHASE stage=scenes-closed; assets=122");
                foreach (string path in paths) UnloadSurfaceMainAsset(path, path.EndsWith(".mat", StringComparison.Ordinal) ? typeof(Material) : typeof(Mesh));
                foreach (string path in paths) SurfaceRequire(!AssetDatabase.IsMainAssetAtPathLoaded(path), "Surface main asset reloaded before scene open: " + path);
                Debug.Log("JOURNEY_SURFACE_RELOAD_PHASE stage=all-unloaded; assets=122");
                foreach (string path in RegionPaths)
                {
                    Debug.Log("JOURNEY_SURFACE_RELOAD_PHASE stage=scene-open; path=" + path);
                    var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                    var binding = Components<RegionBinding>(scene).Single();
                    ValidatePhysicalSurfaceArt(binding);
                    SurfaceRequire(binding.pouncerSupportSurfaces != null && binding.pouncerSupportSurfaces.Length == 2 &&
                        binding.pouncerSupportSurfaces.Contains(binding.transform.Find("Route foundation").GetComponent<BoxCollider>()) &&
                        binding.pouncerSupportSurfaces.Contains(binding.transform.Find("Road surface").GetComponent<BoxCollider>()),
                        "Saved Pouncer support bindings changed.");
                    foreach (string assetPath in SurfaceArtRoles().Select(role => SurfaceMeshPath(binding.region, role))
                        .Concat(new[] { SurfaceMaterialPath(true), SurfaceMaterialPath(false) }))
                    {
                        SurfaceRequire(AssetDatabase.IsMainAssetAtPathLoaded(assetPath), "Scene did not reload its surface main asset: " + assetPath);
                        var asset = AssetDatabase.LoadMainAssetAtPath(assetPath);
                        SurfaceRequire(asset && EditorUtility.IsPersistent(asset) && !EditorUtility.IsDirty(asset), "Reloaded surface asset is not clean/persistent: " + assetPath);
                    }
                    SurfaceRequire(!scene.isDirty, "Saved surface verification dirtied its scene: " + path);
                    Debug.Log("JOURNEY_SURFACE_RELOAD_PHASE stage=scene-verified; path=" + path);
                }
            }
            catch (Exception failure) { failures.Add(failure); }
            finally
            {
                // Preserve the first failed assertion even if restoration or the final byte
                // check also fails, as in the existing read-only integration transaction.
                try { RestoreSceneSetup(setup); }
                catch (Exception failure) { failures.Add(failure); }
                try
                {
                    foreach (var file in hashes) SurfaceRequire(File.Exists(file.Key) && HashFile(file.Key) == file.Value,
                        "Surface asset, scene or metadata bytes changed during reload/restoration: " + file.Key);
                    Debug.Log("JOURNEY_SURFACE_RELOAD_PHASE stage=disk-hashes-preserved; files=" + hashes.Count);
                }
                catch (Exception failure) { failures.Add(failure); }
            }
            if (failures.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failures[0]).Throw();
            if (failures.Count > 1) throw new AggregateException("Surface reload verification/restoration failed.", failures);
            Debug.Log("JOURNEY_SURFACE_ART_SAVED_BINDINGS: 120 actual render meshes, two materials, metre UVs and original two-box supports verified; visual acceptance pending.");
        }
    }
}
