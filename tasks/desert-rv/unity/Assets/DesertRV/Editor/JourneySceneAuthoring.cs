using System;
using System.IO;
using System.Linq;
using UnityEditor;
using Unity.Collections;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using System.Collections.Generic;
using System.Security.Cryptography;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    // Explicit Actions authoring step. Never called by build/preprocess or on import.
    public static partial class JourneySceneAuthoring
    {
        public const string SourcePath = "Assets/DesertRV/Scenes/BodyStudy.unity";
        public const string Folder = "Assets/DesertRV/Scenes/Journey";
        public const string BootstrapPath = Folder + "/JourneyBootstrap.unity";
        public const string ManifestPath = Folder + "/JourneyContent.asset";
        public static readonly string[] RegionPaths = { Folder + "/FirstStation.unity", Folder + "/Scrapyard.unity", Folder + "/NightBeacon.unity" };
        public static readonly double[] RegionOffsets = { 0, 100, 200 };

        [MenuItem("Desert RV/Journey/Author candidate scenes (preserve originals)")]
        public static void AuthorCandidateScenes()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Author in Edit Mode only.");
            foreach (var path in new[] { BootstrapPath }.Concat(RegionPaths))
                if (File.Exists(path)) throw new IOException("Refusing to overwrite a saved scene: " + path + ". Review/archive it explicitly first.");
            var protectedFiles = SnapshotProtectedFiles();
            byte[] source = File.ReadAllBytes(SourcePath), meta = File.ReadAllBytes(SourcePath + ".meta");
            var previous = EditorSceneManager.GetSceneManagerSetup();
            if (previous.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty))
                throw new InvalidOperationException("Save or discard open scene edits before authoring.");
            Directory.CreateDirectory(Folder); AssetDatabase.Refresh();
            try
            {
                var sourceScene = EditorSceneManager.OpenScene(SourcePath, OpenSceneMode.Single);
                var viewer = Components<BodyViewer>(sourceScene).Single();
                if (!viewer.body || !viewer.view || !viewer.garageBench || !viewer.ramModule || !viewer.arcModule)
                    throw new InvalidOperationException("Saved RV/source bindings missing; original will not be regenerated.");
                var body = viewer.body;
                var nodes = body.GetComponentsInChildren<Transform>(true);
                var glass = nodes.Single(t => t.name == "GEO-windscreen").GetComponent<Renderer>();
                Vector3 forward = glass.bounds.center - body.position; forward.y = 0;
                if (forward.sqrMagnitude < .01f) throw new InvalidOperationException("RV forward reference invalid.");
                forward.Normalize(); var correction = Quaternion.FromToRotation(forward, Vector3.forward);
                Vector3 origin = body.position;
                // Rotate the complete environment around the RV anchor; fixed +Z world axis afterwards.
                foreach (var root in sourceScene.GetRootGameObjects())
                { root.transform.position = correction * (root.transform.position - origin); root.transform.rotation = correction * root.transform.rotation; }
                var boot = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
                var host = new GameObject("JourneyBootstrap"); SceneManager.MoveGameObjectToScene(host, boot);
                var session = host.AddComponent<JourneySession>(); var motor = host.AddComponent<JourneyMotor>();
                motor.journey = session; motor.vehicle = body; motor.view = viewer.view;
                motor.localForward = body.InverseTransformDirection(Vector3.forward);
                motor.doorHinge = nodes.Single(t => t.name == "RIG-entry_door_pivot");
                motor.entryStep = nodes.Single(t => t.name == "GEO-entry_step");
                motor.ram = viewer.ramModule; motor.arc = viewer.arcModule; motor.roofCargo = viewer.roofCargo;
                MoveUnder(body, host.transform, boot); MoveUnder(viewer.view.transform, host.transform, boot);
                // Exposure belongs to the persistent camera rig; lights/probes remain local to environments.
                foreach (var root in sourceScene.GetRootGameObjects().Where(r => r.name == "Exposure response")) MoveUnder(root.transform, host.transform, boot);
                motor.ram.SetActive(false); motor.arc.SetActive(false);
                var actions = host.AddComponent<JourneyActions>(); actions.journey = session; actions.motor = motor;
                actions.nailTrajectoryMaterial = AssetDatabase.LoadAssetAtPath<Material>(JourneyTracerMaterial.AssetPath);
                if (!JourneyTracerMaterial.IsValid(actions.nailTrajectoryMaterial)) throw new InvalidOperationException("Journey nail trajectory material or URP Unlit shader missing.");
                AuthorArcMeshGeometry(actions);
                var repair = nodes.Single(t => t.name == "GEO-rear_repair_bench");
                actions.workbenchSurface = ExactSurface(repair);
                actions.cabinWorkbench = Point("Cabin installation point", body, actions.workbenchSurface.bounds.center + Vector3.up * .18f);
                actions.shotSound = Audio("shot"); actions.hitSound = Audio("hit"); actions.reloadSound = Audio("reload");
                actions.pickupSound = Audio("pickup"); actions.upgradeSound = Audio("upgrade"); actions.windSound = Audio("wind");
                var loader = host.AddComponent<RegionLoader>(); loader.regionScenes = RegionPaths.Select(Path.GetFileNameWithoutExtension).ToArray();
                var hudObject = new GameObject("Journey HUD"); hudObject.transform.SetParent(host.transform, false);
                var hud = hudObject.AddComponent<JourneyHud>(); hud.journey = session; hud.motor = motor;
                hud.font = AssetDatabase.LoadAssetAtPath<Font>("Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf");
                var director = host.AddComponent<JourneyDirector>(); director.journey = session; director.motor = motor;
                director.actions = actions; director.loader = loader; director.hud = hud; hud.director = director;
                Object.DestroyImmediate(viewer); // Component only: never delete a source parent that may own dependencies.
                foreach (var preflight in Components<WebPreflight>(sourceScene)) Object.DestroyImmediate(preflight);
                var manifest = AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(ManifestPath);
                if (!manifest) { manifest = ScriptableObject.CreateInstance<JourneyContentManifest>(); AssetDatabase.CreateAsset(manifest, ManifestPath); }
                // Do not infer weapon/arc presentation or review acceptance from a prefab's mere existence.
                Save(boot, BootstrapPath);
                var binding = NewBinding(sourceScene, 1); binding.spawn.rotation = body.rotation;
                var bench = viewerBench(sourceScene);
                binding.salvageSurface = ExactSurface(bench); binding.salvage = Point("Ram salvage interaction", binding.transform, binding.salvageSurface.bounds.center + Vector3.up * .18f);
                binding.salvageVisual = CopyModule(motor.ram, binding.salvage.position, binding.transform, "Ram salvage assembly");
                PopulateLayout(binding, manifest); DressEnvironment(sourceScene,binding,motor); SetAtmosphere(sourceScene,1); CheckNewLayoutClearance(binding,motor,actions);
                Save(sourceScene, RegionPaths[0]);
                // Reuse authored source geometry/materials, never regenerate the accepted RV.
                for (int region = 2; region <= 3; region++)
                {
                    var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
                    var next = NewBinding(scene, region); next.spawn.rotation = body.rotation; PopulateLayout(next, manifest);
                    if (region == 2) next.salvageVisual = CopyModule(motor.arc, next.salvage.position, next.transform, "Coil salvage assembly");
                    var light = new GameObject("Regional sunlight").AddComponent<Light>(); light.transform.SetParent(next.transform, false);
                    light.type = LightType.Directional; light.intensity = region == 3 ? .16f : 1.1f; light.color = region == 3 ? new Color(.38f,.5f,.8f) : new Color(1,.87f,.7f);
                    light.transform.rotation = Quaternion.Euler(45, -25, 0);
                    DressEnvironment(sourceScene,next,motor); SetAtmosphere(scene,region); CheckNewLayoutClearance(next,motor,actions);
                    Save(scene, RegionPaths[region - 1]);
                }
                AssetDatabase.SaveAssets();
                Debug.Log("JOURNEY_CANDIDATES_AUTHORED: NOT reviewed, NOT production-ready. Run JourneyContentChecks.CheckCandidateLayout and CheckProductionContent separately.");
            }
            finally
            {
                // In-memory source changes were saved exclusively to new paths.
                try { RestoreSceneSetup(previous); }
                finally
                {
                    if (!source.SequenceEqual(File.ReadAllBytes(SourcePath)) || !meta.SequenceEqual(File.ReadAllBytes(SourcePath + ".meta")))
                        throw new InvalidOperationException("Source preservation check failed.");
                    VerifyProtectedFiles(protectedFiles);
                }
            }
        }
        // One explicit CI command can author, inspect and render without importing any combat asset.
        public static void AuthorAndCaptureEnvironmentCandidates()
        { AuthorCandidateScenes(); JourneyContentChecks.CheckCandidateLayout(); CaptureEnvironmentCandidates(); }

        // Explicit restored-world entry: only two 960x540 production HUD renders.
        // No authoring, scene saves, gameplay startup, or environment-lighting replacement.
        public static void CapturePreparedWorldHud() => CapturePreparedWorldHudObserved(null, null);
        internal static void CapturePreparedWorldHudObserved(Action<string> observe, Action<HashSet<string>> bindCaptureGate)
        {
            observe?.Invoke("CAPTURE_ENTRY");
            if (Application.isPlaying || EditorApplication.isPlayingOrWillChangePlaymode || BuildPipeline.isBuildingPlayer)
                throw new InvalidOperationException("Prepared world HUD capture requires Edit Mode.");
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
                throw new InvalidOperationException("Actual graphics device required for prepared world HUD capture.");
            var setup = EditorSceneManager.GetSceneManagerSetup();
            if (setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty))
                throw new InvalidOperationException("Save/discard scene edits before capture.");
            foreach (string path in new[] { BootstrapPath }.Concat(RegionPaths))
                if (!File.Exists(path)) throw new InvalidOperationException("Prepared scene missing.");
            if (Directory.Exists("JourneyEvidence/MobileHudWorld"))
                throw new InvalidOperationException("Prepared world HUD output already exists.");
            var protectedFiles = SnapshotProtectedFiles(true);
            var dependencies = new HashSet<string>(AssetDatabase.GetDependencies(
                new[] { BootstrapPath, ManifestPath }.Concat(RegionPaths).ToArray(), true), StringComparer.Ordinal);
            var dirtyAssets = DirtyPersistentCaptureAssets(dependencies, out _, out _, out _);
            bindCaptureGate?.Invoke(new HashSet<string>(dependencies, StringComparer.Ordinal));
            ObserveCaptureStep(observe, "CAPTURE_GATE", () => CheckCaptureAssetLifecycle(dependencies, dirtyAssets, "before"));
            int captured = 0;
            var failures = new List<Exception>();
            void AttemptCleanup(Action action)
            {
                try { action(); } catch (Exception error) { failures.Add(error); }
            }
            try
            {
                foreach (int index in new[] { 0, 2 })
                {
                    ObserveCaptureStep(observe, "CAPTURE_REGION_" + (index + 1), () => {
                    var boot = EditorSceneManager.OpenScene(BootstrapPath, OpenSceneMode.Single);
                    var env = EditorSceneManager.OpenScene(RegionPaths[index], OpenSceneMode.Additive);
                    if (SceneManager.GetActiveScene().handle != env.handle) SceneManager.SetActiveScene(env);
                    var active = SceneManager.GetActiveScene();
                    if (!active.IsValid() || !active.isLoaded || active.handle != env.handle || active.path != RegionPaths[index])
                        throw new InvalidOperationException("Cannot activate prepared region.");
                    var motor = Components<JourneyMotor>(boot).Single();
                    var binding = Components<RegionBinding>(env).Single();
                    if (binding.region != index + 1 || !motor.vehicle || !motor.view || !motor.entryStep)
                        throw new InvalidOperationException("Prepared walker bindings missing.");
                    motor.vehicle.SetPositionAndRotation(binding.spawn.position, binding.spawn.rotation);
                    var camera = motor.view;
                    camera.enabled = false; camera.clearFlags = CameraClearFlags.Skybox;
                    camera.farClipPlane = 450; camera.allowHDR = true;
                    PlaceWalkingCaptureCamera(motor);
                    foreach (var particle in Components<ParticleSystem>(env)) particle.Simulate(7, true, true, true);
                    Physics.SyncTransforms();
                    // Capture owns and destroys all of its buffers before the next Single scene unload.
                    JourneyHudCapture.CaptureOverWorld(camera, "region-" + binding.region);
                    CheckCaptureAssetLifecycle(dependencies, dirtyAssets, "after-region-" + binding.region);
                    captured++;
                    Debug.Log("JOURNEY_WORLD_HUD_CAPTURED region=" + binding.region + "; width=960; height=540; fieldOfView=66; controlledFixtureData=true");
                    });
                }
            }
            catch (Exception error) { failures.Add(error); }
            finally
            {
                // Every cleanup/protection operation runs; the capture failure remains first.
                AttemptCleanup(() => ObserveCaptureStep(observe, "CAPTURE_SCENE_RESTORE", () => RestoreSceneSetup(setup), true));
                AttemptCleanup(() => CheckCaptureAssetLifecycle(dependencies, dirtyAssets, "after-scene-restoration"));
                AttemptCleanup(() => VerifyProtectedFiles(protectedFiles, true));
            }
            if (failures.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failures[0]).Throw();
            if (failures.Count > 1) throw new AggregateException("Prepared world HUD capture and cleanup failed; primary failure first.", failures);
            if (captured != 2) throw new InvalidOperationException("Incomplete prepared world HUD capture.");
            Debug.Log("JOURNEY_WORLD_HUD_CAPTURE_COMPLETE captures=2; originalAndPreparedBytesUnchanged=true; sceneSetupRestored=true; buffersReleasedBeforeSceneUnload=true");
        }
        static void ObserveCaptureStep(Action<string> observe, string stage, Action action, bool cleanup = false)
        {
            var errors = new List<Exception>();
            try { observe?.Invoke(stage + "_BEFORE"); } catch (Exception error) { errors.Add(error); }
            if (!cleanup && errors.Count != 0) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(errors[0]).Throw();
            try { action(); } catch (Exception error) { errors.Add(error); }
            try { observe?.Invoke(stage + "_AFTER"); } catch (Exception error) { errors.Add(error); }
            if (errors.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(errors[0]).Throw();
            if (errors.Count > 1) throw new AggregateException("World capture operation and lifecycle observation failed; primary first.", errors);
        }
        sealed class CaptureCachePin
        {
            public string path, type, guid, assetSha256, metaSha256, packageName, packageVersion, classification;
            public long localId, assetBytes, metaBytes;
        }
        // Exact objects observed in run 38144199976, with immutable producer 38135035401 bytes.
        // Unity's shader compilation cache and dynamic Font atlas are generated engine state;
        // this is not a general exemption for dirty Shader, Texture2D, Material or importer assets.
        static readonly CaptureCachePin[] CaptureCachePins = {
            new CaptureCachePin { path = "Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf", type = "UnityEngine.Texture2D", guid = "43a8f4976b2571d50b5bff0508efaab7", localId = 2800000, assetSha256 = "a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b", assetBytes = 16437340, metaSha256 = "e4c83478e2ad31187b1c6dd2cce61e2630c06b57c4e5727c6303af491718d09e", metaBytes = 481, packageName = "", packageVersion = "", classification = "DYNAMIC_FONT_ATLAS_CACHE" },
            new CaptureCachePin { path = "Packages/com.unity.render-pipelines.universal/Shaders/Lit.shader", type = "UnityEngine.Shader", guid = "933532a4fcc9baf4fa0491de14d08ed7", localId = 4800000, assetSha256 = "6f4648b6b5271132cfed1d7d7c771ba0a73ef7972470d6694047804d259c0997", assetBytes = 22877, metaSha256 = "f0db005307ffe5480c40a402ca5bfb0b3726259031a86e255e49626228ceb008", metaBytes = 217, packageName = "com.unity.render-pipelines.universal", packageVersion = "17.3.0", classification = "OFFICIAL_URP_SHADER_CACHE" },
            new CaptureCachePin { path = "Packages/com.unity.render-pipelines.universal/Shaders/Particles/ParticlesSimpleLit.shader", type = "UnityEngine.Shader", guid = "8516d7a69675844a7a0b7095af7c46af", localId = 4800000, assetSha256 = "5bd621c3363a1eba55fdd9e3594b16116ede25d883e3717d80d58be2dcbe9bb5", assetBytes = 19403, metaSha256 = "06e436bf99c1e986f57625313f6c3320e92908c0acc671bf0afa8f9a42a739d0", metaBytes = 204, packageName = "com.unity.render-pipelines.universal", packageVersion = "17.3.0", classification = "OFFICIAL_URP_SHADER_CACHE" },
            new CaptureCachePin { path = "Packages/com.unity.render-pipelines.universal/Shaders/Particles/ParticlesUnlit.shader", type = "UnityEngine.Shader", guid = "0406db5a14f94604a8c57ccfbc9f3b46", localId = 4800000, assetSha256 = "1cd8356cf8cb67f065b7d2f67b071190a675a98c8cdea5a45028c0cb3c9e1e18", assetBytes = 12430, metaSha256 = "122a44759a8ca196415d39727a270c5554553e8270b0cd7871cc45939cd996a4", metaBytes = 217, packageName = "com.unity.render-pipelines.universal", packageVersion = "17.3.0", classification = "OFFICIAL_URP_SHADER_CACHE" },
            new CaptureCachePin { path = "Packages/com.unity.render-pipelines.universal/Shaders/Unlit.shader", type = "UnityEngine.Shader", guid = "650dd9526735d5b46b79224bc6e94025", localId = 4800000, assetSha256 = "37ef434d3bd626d59f2aa813fed56850eab15e3b759c2399212f2cc1a4d08964", assetBytes = 11416, metaSha256 = "367956a85cb4183e5f8afd33b78f3a048fe08d5767e42e11b4b127b780acfaf2", metaBytes = 195, packageName = "com.unity.render-pipelines.universal", packageVersion = "17.3.0", classification = "OFFICIAL_URP_SHADER_CACHE" },
        };
        // Pure predicate used by the existing single restoration case's positive/negative checks.
        internal static string ClassifyPinnedCaptureCache(string path, string type, string guid, long localId,
            string assetSha256, long assetBytes, string metaSha256, long metaBytes, string packageName,
            string packageVersion, bool dynamicFontAtlasOwner, bool isSubAsset)
        {
            var pin = CaptureCachePins.SingleOrDefault(p => p.path == path && p.type == type && p.guid == guid && p.localId == localId);
            if (pin == null || pin.assetSha256 != assetSha256 || pin.assetBytes != assetBytes || pin.metaSha256 != metaSha256 ||
                pin.metaBytes != metaBytes || pin.packageName != packageName || pin.packageVersion != packageVersion)
                return "AUTHORING_OR_UNKNOWN";
            if (pin.classification == "DYNAMIC_FONT_ATLAS_CACHE" && (!dynamicFontAtlasOwner || !isSubAsset) ||
                pin.classification == "OFFICIAL_URP_SHADER_CACHE" && isSubAsset) return "AUTHORING_OR_UNKNOWN";
            return pin.classification;
        }
        static bool ExactCaptureCacheFile(string physical, string digest, long bytes)
        {
            try
            {
                string root = Path.GetFullPath(".").TrimEnd(Path.DirectorySeparatorChar), full = Path.GetFullPath(physical);
                if (!full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal)) return false;
                for (string current = full; current != root; current = Path.GetDirectoryName(current))
                    if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) return false;
                return new FileInfo(full).Length == bytes && HashFile(full) == digest;
            }
            catch (IOException) { return false; }
            catch (UnauthorizedAccessException) { return false; }
        }
        static string CaptureDirtyClassification(Object asset, string path, string guid, long localId, out string knownGuid, out string reason)
        {
            const string blocked = "AUTHORING_OR_UNKNOWN";
            knownGuid = "UNRECOGNIZED"; reason = "UNRECOGNIZED_OBJECT";
            var pin = CaptureCachePins.SingleOrDefault(p => p.path == path && p.type == asset.GetType().FullName && p.guid == guid && p.localId == localId);
            if (pin == null) return blocked;
            knownGuid = pin.guid;
            string physical = path, packageName = "", packageVersion = "";
            if (path.StartsWith("Packages/", StringComparison.Ordinal))
            {
                var package = UnityEditor.PackageManager.PackageInfo.FindForAssetPath(path);
                Debug.Log("JOURNEY_WORLD_HUD_CACHE_PACKAGE guid=" + pin.guid + "; packageFound=" + (package != null) +
                    "; packageNameMatched=" + (package != null && package.name == pin.packageName) + "; packageVersionMatched=" + (package != null && package.version == pin.packageVersion));
                if (package == null || package.name != pin.packageName || package.version != pin.packageVersion)
                { reason = "PACKAGE_IDENTITY"; return blocked; }
                packageName = package.name; packageVersion = package.version;
                physical = Path.Combine(package.resolvedPath, path.Substring(("Packages/" + package.name + "/").Length));
            }
            bool assetPinMatched = ExactCaptureCacheFile(physical, pin.assetSha256, pin.assetBytes);
            bool metaPinMatched = ExactCaptureCacheFile(physical + ".meta", pin.metaSha256, pin.metaBytes);
            Debug.Log("JOURNEY_WORLD_HUD_CACHE_BYTES guid=" + pin.guid + "; assetPinMatched=" + assetPinMatched + "; metaPinMatched=" + metaPinMatched);
            if (!assetPinMatched) { reason = "ASSET_BYTES"; return blocked; }
            if (!metaPinMatched) { reason = "META_BYTES"; return blocked; }
            bool isSubAsset = AssetDatabase.IsSubAsset(asset), atlasOwner = false;
            Debug.Log("JOURNEY_WORLD_HUD_CACHE_SUBASSET guid=" + pin.guid + "; isSubAsset=" + isSubAsset + "; expectedSubAsset=" + (pin.classification == "DYNAMIC_FONT_ATLAS_CACHE"));
            if (isSubAsset != (pin.classification == "DYNAMIC_FONT_ATLAS_CACHE")) { reason = "SUBASSET_RELATION"; return blocked; }
            if (pin.classification == "DYNAMIC_FONT_ATLAS_CACHE")
            {
                int loadedFontCount = 0; long observedOwnerId = 0;
                bool identityAvailable = false, identity = false, dynamicChecked = false, fontDynamic = false, atlasChecked = false;
                foreach (var font in Resources.FindObjectsOfTypeAll<Font>())
                {
                    if (!font || !EditorUtility.IsPersistent(font) || AssetDatabase.GetAssetPath(font) != path) continue;
                    loadedFontCount++;
                    if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(font, out string ownerGuid, out long ownerId)) continue;
                    identityAvailable = true; observedOwnerId = ownerId;
                    if (ownerGuid != guid || ownerId != 12800000) continue;
                    identity = true;
                    dynamicChecked = true; fontDynamic = font.dynamic;
                    if (!fontDynamic) continue;
                    var material = font.material; atlasChecked = true;
                    if (material && material.mainTexture == asset) { atlasOwner = true; break; }
                }
                Debug.Log("JOURNEY_WORLD_HUD_FONT_CACHE_OWNER guid=" + pin.guid + "; loadedFontCount=" + loadedFontCount +
                    "; ownerIdentityAvailable=" + identityAvailable + "; observedOwnerLocalId=" + observedOwnerId + "; ownerIdentityMatched=" + identity +
                    "; dynamicChecked=" + dynamicChecked + "; fontDynamic=" + fontDynamic + "; atlasLinkChecked=" + atlasChecked + "; atlasLinked=" + atlasOwner);
                if (!atlasOwner)
                { reason = loadedFontCount == 0 ? "FONT_NOT_LOADED" : !identity ? "FONT_IDENTITY" : !fontDynamic ? "FONT_NOT_DYNAMIC" : "FONT_ATLAS_LINK"; return blocked; }
            }
            reason = "ALLOW";
            return ClassifyPinnedCaptureCache(path, asset.GetType().FullName, guid, localId, pin.assetSha256, pin.assetBytes,
                pin.metaSha256, pin.metaBytes, packageName, packageVersion, atlasOwner, isSubAsset);
        }
        static HashSet<string> DirtyPersistentCaptureAssets(HashSet<string> dependencies, out int shaderCaches, out int fontAtlasCaches, out string rejectionCode)
        {
            var result = new HashSet<string>(StringComparer.Ordinal);
            shaderCaches = 0; fontAtlasCaches = 0; rejectionCode = null;
            foreach (var asset in Resources.FindObjectsOfTypeAll<Object>())
            {
                if (!asset || !EditorUtility.IsPersistent(asset) || !dependencies.Contains(AssetDatabase.GetAssetPath(asset)) || !EditorUtility.IsDirty(asset)) continue;
                string path = AssetDatabase.GetAssetPath(asset);
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out string guid, out long localId))
                {
                    Debug.Log("JOURNEY_WORLD_HUD_DIRTY_CLASSIFICATION guid=UNRECOGNIZED; classification=AUTHORING_OR_UNKNOWN; reason=IDENTITY_UNAVAILABLE");
                    result.Add("UNRESOLVED:" + asset.GetInstanceID()); continue;
                }
                string classification = CaptureDirtyClassification(asset, path, guid, localId, out string knownGuid, out string reason);
                Debug.Log("JOURNEY_WORLD_HUD_DIRTY_CLASSIFICATION guid=" + knownGuid + "; classification=" + classification + "; reason=" + reason);
                if (classification == "OFFICIAL_URP_SHADER_CACHE") shaderCaches++;
                else if (classification == "DYNAMIC_FONT_ATLAS_CACHE") fontAtlasCaches++;
                else
                {
                    result.Add(guid + ":" + localId);
                    if (knownGuid != "UNRECOGNIZED" && rejectionCode == null) rejectionCode = "JOURNEY_WORLD_HUD_CACHE_" + reason;
                }
            }
            return result;
        }
        static void CheckCaptureAssetLifecycle(HashSet<string> dependencies, HashSet<string> before, string phase)
        {
            var dirty = DirtyPersistentCaptureAssets(dependencies, out int shaderCaches, out int fontAtlasCaches, out string rejectionCode);
            int added = dirty.Count(id => !before.Contains(id));
            // This exact generated material had an earlier, separate render-lifecycle regression.
            // Observe its loaded state without loading, changing keywords, or saving it.
            var sample = Resources.FindObjectsOfTypeAll<Material>().FirstOrDefault(m =>
                AssetDatabase.GetAssetPath(m) == Folder + "/Layout-FFC261.mat");
            Debug.Log("JOURNEY_WORLD_HUD_ASSET_LIFECYCLE phase=" + phase + "; dirtyDependencyAssets=" + (dirty.Count + shaderCaches + fontAtlasCaches) +
                "; protectedDirtyAssets=" + dirty.Count + "; officialShaderCaches=" + shaderCaches + "; dynamicFontAtlasCaches=" + fontAtlasCaches +
                "; newlyDirty=" + added + "; trackedMaterialLoaded=" + (sample ? "true" : "false") +
                "; trackedMaterialDirty=" + (sample && EditorUtility.IsDirty(sample) ? "true" : "false") +
                "; trackedEmission=" + (sample && sample.IsKeywordEnabled("_EMISSION") ? "true" : "false") +
                "; trackedLightmapFlags=" + (sample ? ((int)sample.globalIlluminationFlags).ToString() : "unloaded"));
            if (phase == "before" && dirty.Count != 0)
                throw new InvalidOperationException(rejectionCode ?? "JOURNEY_WORLD_HUD_DIRTY_DEPENDENCY_PREEXISTING");
            if (added != 0) throw new InvalidOperationException(rejectionCode ?? "JOURNEY_WORLD_HUD_DIRTY_DEPENDENCY_ADDED");
        }
        // The existing environment regression and minimal HUD entry share the same legal dismount view.
        static void PlaceWalkingCaptureCamera(JourneyMotor motor)
        {
            var camera = motor.view; camera.fieldOfView = 66; camera.nearClipPlane = .045f;
            Vector3 entry = motor.entryStep.GetComponent<Renderer>().bounds.center;
            Vector3 right = Vector3.Cross(Vector3.up, motor.Forward);
            Vector3 outward = right * Mathf.Sign(Vector3.Dot(entry - motor.vehicle.position, right));
            Vector3 feet = entry + outward * .95f; feet.y = motor.vehicle.position.y + .04f;
            camera.transform.position = feet + Vector3.up * 1.52f;
            camera.transform.LookAt(camera.transform.position + motor.Forward);
        }

        [Serializable] sealed class ImageRecord { public string region, view, path, sceneHash, cameraModel; public int width,height; public float minimum,maximum,fieldOfView; }
        [Serializable] sealed class ImageReport { public string status="captured-environment-only-not-gameplay-acceptance"; public string graphicsDeviceType, graphicsDeviceName; public int bufferSceneTransitionsChecked; public bool captureBuffersReleased; public ImageRecord[] images; }
        public static void CaptureEnvironmentCandidates()
        {
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null) throw new InvalidOperationException("Actual GPU/software graphics device required; omit -nographics and use the runner virtual display.");
            var setup=EditorSceneManager.GetSceneManagerSetup();
            if (setup.Any(s=>s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty)) throw new InvalidOperationException("Save/discard scene edits before capture.");
            var protectedFiles=SnapshotProtectedFiles();
            var records=new List<ImageRecord>(); string output=Path.GetFullPath("JourneyEvidence/environment"); Directory.CreateDirectory(output);
            RenderTexture target=null; Texture2D pixels=null; var previousTarget=RenderTexture.active;
            int bufferChecks=0; bool buffersReleased=false;
            try
            {
                // OpenScene(Single) unloads unused native objects between regions.
                // Keep these explicit capture buffers alive, then destroy in finally.
                target=new RenderTexture(1440,900,24,RenderTextureFormat.ARGB32){antiAliasing=1,hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create()) throw new InvalidOperationException("Failed to create screenshot render target.");
                pixels=new Texture2D(1440,900,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                for(int i=0;i<3;i++)
                {
                    var boot=EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);
                    var env=EditorSceneManager.OpenScene(RegionPaths[i],OpenSceneMode.Additive);
                    if(!target || !target.IsCreated() || !pixels) throw new InvalidOperationException("Capture buffers were lost during scene loading.");
                    bufferChecks++;
                    SceneManager.SetActiveScene(env); var motor=Components<JourneyMotor>(boot).Single(); var b=Components<RegionBinding>(env).Single();
                    // EditMode capture: no Director.Begin, no enemy simulation, no fake combat acceptance.
                    motor.vehicle.SetPositionAndRotation(b.spawn.position,b.spawn.rotation);
                    CheckNewLayoutClearance(b,motor,Components<JourneyActions>(boot).Single());
                    var camera=motor.view; camera.enabled=false; camera.clearFlags=CameraClearFlags.Skybox;
                    camera.nearClipPlane=.04f; camera.farClipPlane=450; camera.allowHDR=true;
                    foreach(var particle in Components<ParticleSystem>(env)) particle.Simulate(7,true,true,true);
                    foreach(var key in new[]{"overview","ground","landmark","cabin","motor-driving-editor","motor-walking-editor"})
                    {
                        camera.fieldOfView=key=="cabin"?68:key=="overview"?54:58;
                        Vector3 at,look;
                        if(key=="overview") { at=new Vector3(31,39,-17);look=new Vector3(0,0,28); }
                        else if(key=="ground") { at=new Vector3(-5,1.65f,-7);look=new Vector3(2,2.2f,25); }
                        else if(key=="landmark")
                        { var focus=i==0?b.salvage.position:b.powerPoint.position; var towardRV=motor.vehicle.position-focus;towardRV.y=0;
                          at=focus+towardRV.normalized*2.5f;at.y=b.spawn.position.y+1.65f;look=focus; }
                        else if(key=="motor-driving-editor")
                        {
                            camera.fieldOfView=44;camera.nearClipPlane=.045f;
                            Vector3 center=motor.vehicle.position+Vector3.up*1.3f+motor.Forward*2.2f;
                            Quaternion rotation=Quaternion.Euler(74,Quaternion.LookRotation(motor.Forward).eulerAngles.y,0);
                            at=center+rotation*new Vector3(0,0,-26);look=at+rotation*Vector3.forward;
                        }
                        else if(key=="motor-walking-editor")
                        {
                            PlaceWalkingCaptureCamera(motor);
                            at=camera.transform.position;look=at+motor.Forward; // A legal level forward look after dismount, not a running controller.
                        }
                        else { at=motor.vehicle.position+Vector3.forward*.55f+Vector3.up*2.38f;look=at-Vector3.forward*3-Vector3.up*.35f; }
                        camera.transform.position=at;camera.transform.LookAt(look);Physics.SyncTransforms();
                        var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                        if(!RenderPipeline.SupportsRenderRequest(camera,request)) throw new InvalidOperationException("Current render pipeline does not support actual URP screenshot capture.");
                        RenderPipeline.SubmitRenderRequest(camera,request); RenderTexture.active=target;
                        pixels.ReadPixels(new Rect(0,0,1440,900),0,0);pixels.Apply();
                        var colors=pixels.GetPixels32();float min=1,max=0;
                        for(int n=0;n<colors.Length;n+=97) { float value=(colors[n].r+colors[n].g+colors[n].b)/765f;min=Mathf.Min(min,value);max=Mathf.Max(max,value); }
                        if(max-min<.06f || max<.10f) throw new InvalidOperationException("Blank/near-black render rejected: "+env.name+"/"+key);
                        string file=Path.Combine(output,env.name+"-"+key+".png");File.WriteAllBytes(file,pixels.EncodeToPNG());
                        records.Add(new ImageRecord{region=env.name,view=key,path=file,width=1440,height=900,minimum=min,maximum=max,cameraModel=key=="motor-driving-editor"?"JourneyMotor-driving-editor":key=="motor-walking-editor"?"JourneyMotor-walking-editor":"regression-editor",fieldOfView=camera.fieldOfView,sceneHash=AssetDatabase.GetAssetDependencyHash(RegionPaths[i]).ToString()});
                        if(key=="motor-walking-editor" && (b.region==1 || b.region==3))
                            JourneyHudCapture.CaptureOverWorld(camera,"region-"+b.region);
                        RenderTexture.active=previousTarget;
                    }
                }
            }
            finally
            {
                try
                {
                    RenderTexture.active=previousTarget;
                    try { if(pixels) Object.DestroyImmediate(pixels); }
                    finally
                    {
                        if(target) { try { target.Release(); } finally { Object.DestroyImmediate(target); } }
                    }
                    if(pixels || target) throw new InvalidOperationException("Capture buffers were not explicitly released.");
                    buffersReleased=true;
                }
                finally
                {
                    // Even failed buffer cleanup must restore scenes and verify all original bytes.
                    try { RestoreSceneSetup(setup); } finally { VerifyProtectedFiles(protectedFiles); }
                }
            }
            if(bufferChecks!=3 || !buffersReleased) throw new InvalidOperationException("Incomplete capture buffer lifecycle regression.");
            File.WriteAllText(Path.Combine(output,"capture-report.json"),JsonUtility.ToJson(new ImageReport{graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName,bufferSceneTransitionsChecked=bufferChecks,captureBuffersReleased=buffersReleased,images=records.ToArray()},true));
        }
        // A cold batch Editor can have zero loaded scenes. Unity rejects restoring
        // that snapshot (and snapshots of an unnamed scene). Restore a disposable
        // empty in-memory scene instead; never write a fallback asset or settings.
        internal static void RestoreSceneSetup(SceneSetup[] setup)
        {
            bool restorable = setup != null && setup.Any(s => s.isLoaded && s.isActive) &&
                setup.All(s => !s.isLoaded || !string.IsNullOrEmpty(s.path));
            if (restorable) EditorSceneManager.RestoreSceneManagerSetup(setup);
            else EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }
        static Dictionary<string,string> SnapshotProtectedFiles(bool includeJourney = false)
        {
            var result=new Dictionary<string,string>();
            foreach(string folder in new[]{"Assets","ProjectSettings","Packages"})
                if(Directory.Exists(folder)) foreach(string path in Directory.GetFiles(folder,"*",SearchOption.AllDirectories))
                { string p=path.Replace('\\','/');if(includeJourney || !p.StartsWith(Folder+"/",StringComparison.Ordinal)&&p!=Folder+".meta") result[p]=HashFile(p); }
            return result;
        }
        static string HashFile(string path)
        { using(var sha=SHA256.Create()) using(var file=File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(file)).Replace("-","").ToLowerInvariant(); }
        static void VerifyProtectedFiles(Dictionary<string,string> before, bool includeJourney = false)
        {
            var after=SnapshotProtectedFiles(includeJourney);
            var changed=before.Keys.Union(after.Keys).Where(p=>!before.ContainsKey(p)||!after.ContainsKey(p)||before[p]!=after[p]).ToArray();
            Directory.CreateDirectory("JourneyEvidence");
            File.WriteAllLines("JourneyEvidence/protected-source-sha256.txt",before.OrderBy(x=>x.Key).Select(x=>x.Value+"  "+x.Key));
            if(changed.Length>0) throw new InvalidOperationException("Protected source/settings were changed: "+string.Join(", ",changed));
        }
        static void SetAtmosphere(Scene scene,int region)
        {
            SceneManager.SetActiveScene(scene);
            Color sky=region==1?new Color(.34f,.55f,.77f):region==2?new Color(.42f,.49f,.57f):new Color(.055f,.10f,.20f);
            Color horizon=region==1?new Color(.82f,.75f,.63f):region==2?new Color(.73f,.61f,.43f):new Color(.22f,.29f,.40f);
            var shader=Shader.Find("DesertRV/SoftDesertSky");if(!shader||!shader.isSupported)throw new InvalidOperationException("Retained supported desert sky shader required.");
            var skybox=new Material(shader);skybox.SetColor("_Zenith",sky);skybox.SetColor("_Horizon",horizon);
            skybox.SetColor("_CloudLight",region==3?new Color(.31f,.40f,.53f):region==2?new Color(.79f,.72f,.60f):new Color(.96f,.89f,.75f));
            skybox.SetColor("_CloudShade",region==3?new Color(.15f,.22f,.34f):region==2?new Color(.65f,.56f,.45f):new Color(.63f,.64f,.63f));
            AssetDatabase.CreateAsset(skybox,Folder+"/Region-"+region+"-Sky.mat");RenderSettings.skybox=skybox;
            RenderSettings.ambientMode=AmbientMode.Trilight;RenderSettings.ambientSkyColor=region==3?new Color(.25f,.34f,.5f):sky;
            RenderSettings.ambientEquatorColor=region==3?new Color(.20f,.25f,.35f):horizon*.72f;
            RenderSettings.ambientGroundColor=region==3?new Color(.14f,.17f,.22f):new Color(.29f,.23f,.17f);
            RenderSettings.fog=true;RenderSettings.fogMode=FogMode.Linear;RenderSettings.fogColor=horizon;
            RenderSettings.fogStartDistance=region==2?90:140;RenderSettings.fogEndDistance=region==2?330:400;
            foreach(var light in Components<Light>(scene).Where(x=>x.type==LightType.Directional))
            {light.transform.rotation=Quaternion.Euler(region==3?35:region==2?21:25,-38,0);light.color=region==3?new Color(.55f,.68f,1):new Color(1,.84f,.65f);light.intensity=region==3?.62f:region==2?1.05f:1.4f;light.shadows=LightShadows.Soft;RenderSettings.sun=light;}
        }
        static readonly Color Sand = new Color(.89f,.70f,.45f), Asphalt = new Color(.31f,.31f,.29f),
            Rust = new Color(.48f,.27f,.16f), Steel = new Color(.25f,.32f,.32f), Cream = new Color(.77f,.72f,.59f),
            Ochre = new Color(.86f,.57f,.21f), Concrete = new Color(.57f,.53f,.44f), BeaconBlue = new Color(.25f,.75f,.86f);
        static void DressEnvironment(Scene source,RegionBinding b,JourneyMotor motor)
        {
            // Source meshes contain world-baked vertices AND large mesa skirts. Every reused group
            // is normalized from actual renderer world bounds, never guessed from localScale.
            // Disable only obsolete surface/terrain instances in the new FirstStation scene.
            if(b.region==1) foreach(var t in SourceGeometry(source))
            {
                if(t.name.StartsWith("GEO-weathered_mesa",StringComparison.Ordinal) || t.name=="GEO-distant_terrain" || t.name=="GEO-sand_ground" ||
                    t.name=="GEO-asphalt_road" || t.name.StartsWith("GEO-road_",StringComparison.Ordinal) ||
                    t.name.StartsWith("GEO-sand_drift",StringComparison.Ordinal) || t.name.StartsWith("GEO-floor_oil_stain",StringComparison.Ordinal))
                    t.gameObject.SetActive(false);
            }
            var foundation=b.transform.Find("Route foundation");foundation.localScale=new Vector3(2400,.4f,2400);foundation.position=new Vector3(0,-.24f,85);
            // Far scenery is visual only. The physical playable ground footprint stays 230 x 310 m.
            var groundCollider=foundation.GetComponent<BoxCollider>();groundCollider.size=new Vector3(230f/2400,1,310f/2400);
            foundation.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(Sand,"painted-sand",new Vector2(300,300));
            // A continuous drivable road with irregular shoulders, rather than disconnected slabs.
            var road=Solid("Road surface",b.transform,new Vector3(0,-.015f,30),new Vector3(8,.10f,94),Asphalt);
            road.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(Asphalt,"asphalt",new Vector2(2,22));
            for(int i=0;i<16;i++)
            {
                Solid("Road paint "+i,b.transform,new Vector3(0,.043f,-12+i*5),new Vector3(.12f,.01f,1.45f),Ochre);
                var edge=Solid("Road shoulder patch "+i,b.transform,new Vector3(i%2==0?-4.25f:4.25f,-.013f,-10+i*5.2f),new Vector3(.6f,.08f,2.8f),new Color(.90f,.71f,.46f));
                edge.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(new Color(.90f,.71f,.46f),"painted-sand",new Vector2(.12f,.35f));
            }
            // Four smaller distant landforms leave an open roadside basin and an unobstructed horizon.
            Vector3[] mountains={new Vector3(-75,0,60),new Vector3(88,0,92),new Vector3(-98,0,148),new Vector3(62,0,186)};
            for(int i=0;i<mountains.Length;i++)
                CopySized(source,b.transform,"DISTANT-Mesa-"+i,mountains[i],new Vector3(28,17,25),"GEO-weathered_mesa."+(i+2).ToString("000"));
            for(int i=0;i<20;i++)
            {
                float side=i%2==0?-1:1;float z=-9+i*4.4f;
                CopySpatial(source,b.transform,"Shoulder agave "+i,new Vector3(side*(10.5f+i%4*1.3f),0,z),new Vector3(1.5f,1.0f,1.5f),"GEO-agave_leaf.001","GEO-agave_leaf",1.2f);
                if(i%4==0) CopySpatial(source,b.transform,"Shoulder cactus "+i,new Vector3(side*(18+i%3),0,z+2),new Vector3(2.2f,3.7f,2.2f),"GEO-saguaro_trunk.002","GEO-saguaro_",1.9f);
                if(i%3==0)
                {
                    var at=new Vector3(side*23,0,z+1);
                    CopySized(source,b.transform,"Middle boulder "+i,at,new Vector3(3.8f,2.5f,3.3f),"GEO-loose_stone.018");
                    for(int k=0;k<3;k++)CopySized(source,b.transform,"Boulder scatter "+i+"-"+k,at+new Vector3(k*1.6f-2,0,2.8f+k*.5f),new Vector3(.55f+k*.28f,.42f+k*.18f,.6f),"GEO-loose_stone.022");
                }
            }
            ExtendSceneryRoad(b);
            if(b.region==1) {DressStation(source,b);DressRamGate(b);}
            else if(b.region==2) {DressScrapyard(source,b);DressScrapWork(source,b,motor);}
            else {DressBeacon(source,b);DressSignalEquipment(source,b);}
            AuthorOptionalSupplies(source,b,motor);
            AuthorPhysicalSurfaceArt(b);
        }
        static void ExtendSceneryRoad(RegionBinding b)
        {
            // Render-only continuation beyond the unchanged exit/safe-zone. No extra playable distance.
            RenderOnlyBox("Far road continuation",b.transform,new Vector3(0,.002f,338.5f),new Vector3(8,.04f,523),Asphalt);
            RenderOnlyBox("Road behind arrival",b.transform,new Vector3(0,.002f,-308.5f),new Vector3(8,.04f,583),Asphalt);
            for(int i=0;i<20;i++)
            {
                float z=5+i*5.2f;float x=i%2==0?-4.1f:4.1f;
                var drift=GameObject.CreatePrimitive(PrimitiveType.Sphere);drift.name="Roadside sand lobe "+i;drift.transform.SetParent(b.transform,false);
                drift.transform.position=new Vector3(x,.012f,z);drift.transform.localScale=new Vector3(.8f+(i%3)*.3f,.06f,2.5f+(i%4)*.5f);
                drift.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(new Color(.90f,.71f,.46f),"painted-sand",new Vector2(.12f,.35f));
                Object.DestroyImmediate(drift.GetComponent<Collider>());
            }
        }
        static void DressRamGate(RegionBinding b)
        {
            var gate=b.ramGate;gate.GetComponent<Renderer>().enabled=false;
            var intact=new GameObject("Ram gate supported intact assembly").transform;intact.SetParent(b.transform,false);
            var damaged=new GameObject("Ram gate fallen assembly").transform;damaged.SetParent(b.transform,false);
            for(int i=0;i<4;i++)
            {
                float x=-8.8f+i*5.85f;
                RenderOnlyBox("Gate A-frame upright",intact,new Vector3(x,.95f,51),new Vector3(.24f,1.9f,.26f),Steel);
                RenderOnlyRod("Gate rear brace",intact,new Vector3(x,1.5f,51),new Vector3(x,.06f,52.1f),.09f,Steel);
                RenderOnlyBox("Gate ground shoe",intact,new Vector3(x,.08f,51.35f),new Vector3(.8f,.16f,1.65f),Rust);
            }
            for(int i=0;i<6;i++)
            {
                float x=-8.1f+i*3.24f;
                var panel=RenderOnlyBox("Ram gate bolted panel "+i,intact,new Vector3(x,1.15f,50.9f),new Vector3(3.10f,.95f,.16f),i%2==0?Ochre:Cream);
                for(int j=0;j<3;j++)
                {
                    var stripe=RenderOnlyBox("Gate hazard stripe",intact,new Vector3(x-1+j*.86f,1.15f,50.805f),new Vector3(.24f,.89f,.015f),Steel);
                    stripe.transform.Rotate(0,0,-24);
                }
                foreach(float dx in new[]{-1.35f,1.35f}) RenderOnlyBox("Gate bolt",intact,new Vector3(x+dx,1.15f,50.79f),new Vector3(.07f,.07f,.02f),Steel);
                var fallen=RenderOnlyBox("Broken gate panel "+i,damaged,new Vector3(x,.19f,52.2f+i%2*.8f),new Vector3(3.1f,.16f,.95f),i%2==0?Ochre:Cream);
                fallen.transform.rotation=Quaternion.Euler(0,i%2==0?18:-22,i%3*3);
            }
            // Preserve world sizes when attaching beneath the original scaled collider object.
            intact.SetParent(gate.transform,true);damaged.SetParent(gate.transform,true);damaged.gameObject.SetActive(false);
            var visual=gate.gameObject.AddComponent<JourneyRamGateVisual>();visual.gate=gate;visual.intact=intact.gameObject;visual.damaged=damaged.gameObject;
        }
        static void DressScrapWork(Scene source,RegionBinding b,JourneyMotor motor)
        {
            var tire=motor.vehicle.GetComponentsInChildren<Transform>(true).Single(t=>t.name=="GEO-spare_tyre");
            for(int i=0;i<8;i++) CopyLoosePart(tire,b.transform,"Salvaged tire stack "+i,new Vector3(-16.2f+(i%2)*1.25f,(i/2%2)*.36f,16+(i/4)*2),new Vector3(1.15f,.34f,1.15f),Quaternion.Euler(90,0,i*11));
            // An original assembled stripped chassis, using self-authored tire mesh and new steel structure.
            Vector3 chassis=new Vector3(-12,0,30);
            foreach(float x in new[]{-1.15f,1.15f})RenderOnlyBox("Stripped chassis rail",b.transform,chassis+new Vector3(x,.72f,0),new Vector3(.16f,.25f,5.4f),Steel);
            for(int i=0;i<4;i++)RenderOnlyBox("Stripped chassis crossmember",b.transform,chassis+new Vector3(0,.68f,-2+i*1.35f),new Vector3(2.5f,.18f,.18f),Rust);
            foreach(float x in new[]{-1.65f,1.65f})foreach(float z in new[]{-1.9f,1.9f})CopyLoosePart(tire,b.transform,"Chassis salvaged wheel",chassis+new Vector3(x,.04f,z),new Vector3(.4f,1.05f,1.05f),Quaternion.Euler(0,90,0));
            RenderOnlyBox("Exposed engine block",b.transform,chassis+new Vector3(0,1.08f,1.6f),new Vector3(.9f,.75f,1),Steel);
            for(int i=0;i<6;i++)RenderOnlyRod("Engine cooling fin",b.transform,chassis+new Vector3(-.48f,1.15f+i*.065f,1.2f),chassis+new Vector3(.48f,1.15f+i*.065f,1.2f),.018f,Cream);
            var door=RenderOnlyBox("Detached sheet metal door",b.transform,new Vector3(-15.3f,.6f,32),new Vector3(1.3f,1.1f,.08f),Rust);door.transform.Rotate(17,24,8);
            for(int i=0;i<3;i++)
            {
                var at=new Vector3(12.5f+i*.85f,0,29);
                var sheet=RenderOnlyBox("Sorted bent metal sheet",b.transform,at+Vector3.up*(.18f+i*.10f),new Vector3(.75f,.07f,1.9f),i%2==0?Steel:Cream);sheet.transform.Rotate(0,i*13,7);
            }
            RenderOnlyBox("Workshop dismantling table",b.transform,new Vector3(12,1.0f,26.5f),new Vector3(2.6f,.16f,1.1f),Steel);
            CopySized(source,b.transform,"Bench gear assembly",new Vector3(12,1.09f,26.5f),new Vector3(.8f,.6f,.8f),"GEO-bench_drive_gear");
            CopySized(source,b.transform,"Workshop self-authored tool case",new Vector3(13,0,24.7f),new Vector3(.8f,.5f,.65f),"GEO-garage_toolbox");
            for(int i=0;i<3;i++)
            {
                var stain=CopySized(source,b.transform,"Workshop oil mark "+i,new Vector3(-12+i*12,i==1?.046f:.002f,27+i*4),new Vector3(2.4f,.012f,2),"GEO-floor_oil_stain.002");
                foreach(var r in stain.GetComponentsInChildren<Renderer>(true)){r.sharedMaterial=LayoutMaterial(new Color(.24f,.205f,.155f),null,Vector2.one);r.shadowCastingMode=ShadowCastingMode.Off;}
                foreach(var c in stain.GetComponentsInChildren<Collider>(true))Object.DestroyImmediate(c);
            }
            DressPowerControls(b); Lamp(b.transform,"Canopy warm work pool",new Vector3(12,2.9f,26.5f),new Color(1,.77f,.45f),1.6f,10);
        }
        static void DressSignalEquipment(Scene source,RegionBinding b)
        {
            Vector3 dish=new Vector3(-11,8.1f,31.9f);
            var bowl=GameObject.CreatePrimitive(PrimitiveType.Sphere);bowl.name="Beacon directional signal reflector";bowl.transform.SetParent(b.transform,false);bowl.transform.position=dish;bowl.transform.localScale=new Vector3(2.5f,2.5f,.22f);
            bowl.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(Cream,null,Vector2.one);Object.DestroyImmediate(bowl.GetComponent<Collider>());
            for(int i=0;i<12;i++)
            {
                float a=i*Mathf.PI/6,c=(i+1)*Mathf.PI/6;
                RenderOnlyRod("Antenna rim",b.transform,dish+new Vector3(Mathf.Cos(a)*1.28f,Mathf.Sin(a)*1.28f,-.05f),dish+new Vector3(Mathf.Cos(c)*1.28f,Mathf.Sin(c)*1.28f,-.05f),.035f,Steel);
            }
            foreach(float angle in new[]{0f,120f,240f})
            {float a=angle*Mathf.Deg2Rad;RenderOnlyRod("Signal feed support",b.transform,dish+new Vector3(Mathf.Cos(a)*1.1f,Mathf.Sin(a)*1.1f,-.15f),dish+Vector3.back*.75f,.03f,Steel);}
            RenderOnlyBox("Antenna feed receiver",b.transform,dish+Vector3.back*.8f,new Vector3(.28f,.28f,.35f),Ochre);
            RenderOnlyRod("Signal feeder conduit",b.transform,new Vector3(-9.9f,.12f,33),new Vector3(-9.9f,8,33),.055f,Steel);
            for(int i=0;i<3;i++)
            {
                var rack=new Vector3(10+i*1.05f,0,33.2f);
                RenderOnlyBox("Beacon relay accumulator",b.transform,rack+Vector3.up*.65f,new Vector3(.8f,1.3f,.85f),Steel);
                RenderOnlyBox("Relay service panel",b.transform,rack+new Vector3(0,.7f,-.44f),new Vector3(.6f,.9f,.025f),Cream);
                for(int k=0;k<4;k++)RenderOnlyBox("Relay cooling vent",b.transform,rack+new Vector3(0,.4f+k*.10f,-.46f),new Vector3(.45f,.025f,.025f),Rust);
            }
            Vector3[] cable={new Vector3(6.4f,.06f,23),new Vector3(8.8f,.06f,23),new Vector3(8.8f,.06f,33),new Vector3(-9.9f,.06f,33)};
            for(int i=0;i<cable.Length-1;i++)RenderOnlyRod("Beacon ground power cable",b.transform,cable[i],cable[i+1],.035f,Steel);
            DressPowerControls(b);
            var workLamp=RenderOnlyBox("Beacon service lamp housing",b.transform,new Vector3(11,2.76f,31),new Vector3(.45f,.18f,.32f),Steel);
            var diffuser=RenderOnlyBox("Beacon warm lamp diffuser",b.transform,new Vector3(11,2.65f,31),new Vector3(.35f,.035f,.25f),new Color(1,.76f,.38f));
            diffuser.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(new Color(1,.76f,.38f),null,Vector2.one,true);
            Lamp(b.transform,"Beacon equipment worklight",new Vector3(11,2.6f,31),new Color(1,.73f,.37f),2.1f,12);
            Lamp(b.transform,"Beacon base service light",new Vector3(-10,2.4f,31),new Color(1,.73f,.37f),1.6f,9);
            for(int i=0;i<4;i++)
            {
                float z=42+i*5;
                foreach(float sign in new[]{-1f,1f}){var arrow=RenderOnlyBox("Evacuation painted chevron",b.transform,new Vector3(sign*.28f,.043f,z),new Vector3(.13f,.012f,.8f),Cream);arrow.transform.Rotate(0,sign*-35,0);}
            }
        }
        static void DressPowerControls(RegionBinding b)
        {
            Vector3 p=b.powerSurface.bounds.center;
            foreach(float x in new[]{-.2f,.2f})
            {
                var dial=GameObject.CreatePrimitive(PrimitiveType.Cylinder);dial.name="Power analogue gauge";dial.transform.SetParent(b.transform,false);dial.transform.position=p+new Vector3(x,.10f,-.47f);dial.transform.rotation=Quaternion.Euler(90,0,0);dial.transform.localScale=new Vector3(.22f,.018f,.22f);dial.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(Cream,null,Vector2.one);Object.DestroyImmediate(dial.GetComponent<Collider>());
                var needle=RenderOnlyBox("Gauge needle",b.transform,p+new Vector3(x,.10f,-.495f),new Vector3(.025f,.12f,.01f),Steel);needle.transform.Rotate(0,0,-25);
            }
            RenderOnlyBox("Cabinet pull handle",b.transform,p+new Vector3(.34f,-.22f,-.49f),new Vector3(.035f,.22f,.06f),Steel);
            for(int i=0;i<4;i++)RenderOnlyBox("Cabinet lower ventilation slot",b.transform,p+new Vector3(0,-.25f-i*.085f,-.475f),new Vector3(.44f,.023f,.012f),Steel);
        }
        static GameObject RenderOnlyBox(string name,Transform parent,Vector3 at,Vector3 size,Color color)
        {var collider=Solid(name,parent,at,size,color);var go=collider.gameObject;Object.DestroyImmediate(collider);return go;}
        static void RenderOnlyRod(string name,Transform parent,Vector3 start,Vector3 end,float radius,Color color)
        {Rod(name,parent,start,end,radius,color);var child=parent.GetChild(parent.childCount-1);Object.DestroyImmediate(child.GetComponent<Collider>());}
        static Transform CopyLoosePart(Transform part,Transform parent,string name,Vector3 at,Vector3 maximum,Quaternion rotation)
        {
            var root=new GameObject(name).transform;root.SetParent(parent,false);var copy=Object.Instantiate(part.gameObject,root,true);copy.SetActive(true);
            foreach(var r in copy.GetComponentsInChildren<Renderer>(true)){r.lightmapIndex=-1;r.realtimeLightmapIndex=-1;}
            foreach(var c in copy.GetComponentsInChildren<Collider>(true))Object.DestroyImmediate(c);
            PlaceGeometry(root,Vector3.zero);root.rotation=rotation;FitGeometry(root,at,maximum);return root;
        }
        static Transform CopySpatial(Scene source,Transform parent,string name,Vector3 at,Vector3 maximum,string seedName,string prefix,float radius)
        {
            var seed=SourceGeometry(source).Single(t=>t.name==seedName).GetComponent<Renderer>().bounds.center;
            var root=new GameObject(name).transform;root.SetParent(parent,false);
            foreach(var t in SourceGeometry(source).Where(t=>t.name.StartsWith(prefix,StringComparison.Ordinal)&&t.GetComponent<Renderer>()))
            {
                Vector3 delta=t.GetComponent<Renderer>().bounds.center-seed;delta.y=0;if(delta.magnitude>radius)continue;
                var copy=Object.Instantiate(t.gameObject,root,true);copy.SetActive(true);
                foreach(var r in copy.GetComponentsInChildren<Renderer>(true)){r.lightmapIndex=-1;r.realtimeLightmapIndex=-1;}
            }
            PlaceGeometry(root,at);FitGeometry(root,at,maximum);
            var visible=GeometryBounds(root);
            if(visible.size.y<maximum.y*.25f || visible.size.x<maximum.x*.15f || visible.size.z<maximum.z*.15f)
                throw new InvalidOperationException("Plant spatial cluster collapsed below visible authored dimensions: "+name);
            return root;
        }
        static void FitGeometry(Transform root,Vector3 at,Vector3 maximum)
        {
            Bounds bounds=GeometryBounds(root);float scale=Mathf.Min(maximum.x/Mathf.Max(.001f,bounds.size.x),Mathf.Min(maximum.y/Mathf.Max(.001f,bounds.size.y),maximum.z/Mathf.Max(.001f,bounds.size.z)));
            root.localScale*=scale;PlaceGeometry(root,at);Physics.SyncTransforms();bounds=GeometryBounds(root);
            if(bounds.size.x>maximum.x+.02f||bounds.size.y>maximum.y+.02f||bounds.size.z>maximum.z+.02f)throw new InvalidOperationException("World bounds normalization failed: "+root.name);
        }
        static void DressStation(Scene source,RegionBinding b)
        {
            // Retain the complete source station as the first region's unique landmark.
            for(int i=0;i<3;i++) CopySized(source,b.transform,"Station forecourt drum "+i,new Vector3(7.2f,0,10+i*3),new Vector3(.7f,1.05f,.7f),"GEO-workshop_drum.001");
            CopySized(source,b.transform,"Station spare tool case",new Vector3(8,0,17),new Vector3(1.1f,.6f,.8f),"GEO-garage_toolbox","GEO-toolbox_lid","GEO-toolbox_handle","GEO-toolbox_clasp");
        }
        static void DressScrapyard(Scene source,RegionBinding b)
        {
            // A real sorting yard: corrugated bins, overhead lifting frame and short cover alleys.
            Container(b.transform,new Vector3(-12,0,21),new Vector3(5.2f,2.5f,8),Rust);
            Container(b.transform,new Vector3(14,0,40),new Vector3(5.2f,2.5f,8),Steel);
            Container(b.transform,new Vector3(14,2.55f,40),new Vector3(5.2f,2.1f,6.6f),Cream);
            for(int i=0;i<8;i++)
            {
                float z=12+i*5;
                Solid("Yard perimeter post L "+i,b.transform,new Vector3(-19,1.15f,z),new Vector3(.16f,2.3f,.16f),Steel);
                Solid("Yard perimeter post R "+i,b.transform,new Vector3(21,1.15f,z),new Vector3(.16f,2.3f,.16f),Steel);
                if(i<7){Solid("Yard corrugated fence L "+i,b.transform,new Vector3(-19,1,z+2.3f),new Vector3(.09f,1.6f,4.5f),Rust);Solid("Yard corrugated fence R "+i,b.transform,new Vector3(21,1,z+2.3f),new Vector3(.09f,1.6f,4.5f),Cream);}
            }
            Vector3 gantry=new Vector3(-11,0,38);
            foreach(float x in new[]{-3f,3f}) Solid("Salvage hoist upright",b.transform,gantry+new Vector3(x,3.3f,0),new Vector3(.32f,6.6f,.42f),Ochre);
            Solid("Salvage hoist beam",b.transform,gantry+Vector3.up*6.5f,new Vector3(6.7f,.42f,.5f),Ochre);
            Solid("Salvage hoist trolley",b.transform,gantry+new Vector3(.6f,6.05f,0),new Vector3(.8f,.55f,.72f),Steel);
            Rod("Hoist chain",b.transform,gantry+new Vector3(.6f,6,0),gantry+new Vector3(.6f,3.5f,0),.055f,Steel);
            for(int i=0;i<5;i++)
            {
                var rack=new Vector3(-12+(i%2)*3,0,43+(i/2)*3);
                Solid("Sorted scrap pallet "+i,b.transform,rack+Vector3.up*.13f,new Vector3(2,.26f,1.6f),Rust);
                CopySized(source,b.transform,"Sorted gears "+i,rack+Vector3.up*.27f,new Vector3(1.2f,.8f,1.2f),"GEO-bench_drive_gear","GEO-gear_hub","GEO-gear_tooth");
            }
            for(int i=0;i<5;i++) CopySized(source,b.transform,"Salvage drum group "+i,new Vector3(12+(i%2)*1.1f,0,13+i*1.4f),new Vector3(.75f,1.05f,.75f),"GEO-workshop_drum.001");
            ServiceCanopy(b.transform,new Vector3(11,0,28),new Vector3(8,3.4f,8),Rust);
            DecoratePowerCabinet(b); Lamp(b.transform,"Yard task light",new Vector3(11,3.1f,28),new Color(1,.74f,.39f),1.2f,13);
        }
        static void DressBeacon(Scene source,RegionBinding b)
        {
            // The beacon is visible steel structure, not merely a point light or thin unmarked pole.
            Vector3 tower=new Vector3(-11,0,33);
            Solid("Beacon foundation",b.transform,tower+Vector3.up*.16f,new Vector3(6,.32f,6),Concrete);
            for(int side=0;side<4;side++)
            {
                float angle=side*Mathf.PI*.5f; Vector3 corner=new Vector3(Mathf.Cos(angle+Mathf.PI*.25f),0,Mathf.Sin(angle+Mathf.PI*.25f))*2.4f;
                Rod("Beacon lattice leg",b.transform,tower+corner+Vector3.up*.3f,tower+corner*.38f+Vector3.up*10,.15f,Steel);
                for(int level=0;level<3;level++)
                {
                    float nextAngle=(side+1)*Mathf.PI*.5f;Vector3 other=new Vector3(Mathf.Cos(nextAngle+Mathf.PI*.25f),0,Mathf.Sin(nextAngle+Mathf.PI*.25f))*2.4f;
                    float low=1+level*2.7f,high=low+2.6f;
                    Rod("Beacon diagonal brace",b.transform,tower+corner*(1-low/16)+Vector3.up*low,tower+other*(1-high/16)+Vector3.up*high,.07f,Ochre);
                }
            }
            Solid("Beacon lantern housing",b.transform,tower+Vector3.up*10.2f,new Vector3(2.5f,.55f,2.5f),Steel);
            var lens=Solid("Beacon emissive lens",b.transform,tower+Vector3.up*10.85f,new Vector3(1.9f,.75f,1.9f),BeaconBlue);
            lens.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(BeaconBlue,null,Vector2.one,true);
            Lamp(b.transform,"Beacon blue lantern",tower+Vector3.up*10.85f,new Color(.35f,.78f,1),4,23);
            ServiceCanopy(b.transform,new Vector3(12,0,31),new Vector3(7,3.6f,8),Steel);
            Solid("Relay shelter rear wall",b.transform,new Vector3(12,1.6f,35),new Vector3(7,3.2f,.18f),Cream);
            for(int i=0;i<3;i++)
            {
                var panel=Solid("Beacon solar collector "+i,b.transform,new Vector3(15+i*1.8f,1.25f,19),new Vector3(1.6f,.10f,3),new Color(.16f,.25f,.34f));panel.transform.rotation=Quaternion.Euler(-18,0,0);
                for(int k=0;k<4;k++) Solid("Solar cell divider",panel.transform,panel.transform.TransformPoint(new Vector3(0,.07f,-.38f+k*.25f)),new Vector3(1.55f,.012f,.025f),Steel);
            }
            DecoratePowerCabinet(b);
            for(int i=0;i<6;i++)
            { float z=35+i*5;float x=i%2==0?-5.3f:5.3f;Solid("Safe-route bollard "+i,b.transform,new Vector3(x,.4f,z),new Vector3(.16f,.8f,.16f),Cream);Lamp(b.transform,"Safe-route lamp "+i,new Vector3(x,.85f,z),new Color(1,.68f,.31f),.8f,5); }
            foreach(float x in new[]{-6.8f,6.8f}) Solid("Safe-zone arch post",b.transform,new Vector3(x,2.8f,62),new Vector3(.35f,5.6f,.45f),Cream);
            Solid("Safe-zone arch lintel",b.transform,new Vector3(0,5.5f,62),new Vector3(14,.45f,.5f),Steel);
            Lamp(b.transform,"Safe-zone arrival light",new Vector3(0,5.3f,62),new Color(.48f,1,.72f),2,12);
        }
        static void ServiceCanopy(Transform parent,Vector3 at,Vector3 size,Color color)
        {
            foreach(float x in new[]{-size.x*.5f,size.x*.5f}) foreach(float z in new[]{-size.z*.5f,size.z*.5f})
                Solid("Service canopy post",parent,at+new Vector3(x,size.y*.5f,z),new Vector3(.15f,size.y,.15f),Steel);
            Solid("Service corrugated roof",parent,at+Vector3.up*size.y,new Vector3(size.x+.5f,.12f,size.z+.5f),color);
            for(int i=0;i<12;i++) Solid("Canopy roof rib",parent,at+new Vector3(-size.x*.5f+i*size.x/11,size.y+.1f,0),new Vector3(.055f,.065f,size.z+.5f),Cream);
        }
        static void Container(Transform parent,Vector3 at,Vector3 size,Color color)
        {
            Solid("Salvage container body",parent,at+Vector3.up*size.y*.5f,size,color);
            for(int i=0;i<11;i++) foreach(float x in new[]{-size.x*.505f,size.x*.505f})
                Solid("Container corrugation",parent,at+new Vector3(x,size.y*.5f,-size.z*.45f+i*size.z*.09f),new Vector3(.07f,size.y*.92f,.12f),Cream);
            foreach(float z in new[]{-size.z*.5f,size.z*.5f}) Solid("Container corner rail",parent,at+new Vector3(0,size.y,z),new Vector3(size.x+.12f,.1f,.1f),Steel);
        }
        static void DecoratePowerCabinet(RegionBinding b)
        {
            var p=b.powerSurface.bounds.center;
            Solid("Power cabinet face",b.transform,p+new Vector3(0,0,-.43f),new Vector3(.8f,1,.045f),Cream);
            for(int i=0;i<3;i++) Solid("Power status indicator "+i,b.transform,p+new Vector3(-.23f+i*.23f,.25f,-.47f),new Vector3(.09f,.09f,.03f),i==0?BeaconBlue:Ochre);
            Rod("Power socket conduit",b.transform,p+new Vector3(.45f,-.55f,0),new Vector3(4.8f,.08f,p.z),.035f,Steel);
        }
        static void Lamp(Transform parent,string name,Vector3 at,Color color,float strength,float range)
        {var light=new GameObject(name).AddComponent<Light>();light.transform.SetParent(parent,false);light.transform.position=at;light.type=LightType.Point;light.color=color;light.intensity=strength;light.range=range;}
        static void Rod(string name,Transform parent,Vector3 start,Vector3 end,float radius,Color color)
        {
            var go=GameObject.CreatePrimitive(PrimitiveType.Cylinder);go.name=name;go.transform.SetParent(parent,false);
            go.transform.position=(start+end)*.5f;go.transform.rotation=Quaternion.FromToRotation(Vector3.up,end-start);
            go.transform.localScale=new Vector3(radius*2,(end-start).magnitude*.5f,radius*2);go.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(color,null,Vector2.one);
        }
        public const string WarmLampMaterialPath = Folder + "/Layout-FFC261.mat";
        const string WarmLampMaterialGuid = "7807e70b78cd80b04b21bf136de97aaf";
        const string WarmLampOriginalSha = "ef01bab64fa8fe3f2ebe42a59ed43ddf426e1e8f0c3a5a3401a7dd0fe5202395";
        const string WarmLampMetaSha = "3114cac24a6efaddb06b5ee3aaaaefd50d2bee2b98c295d5661f57484b509a21";
        [Serializable] public sealed class WarmLampState
        {
            public int giFlags;
            public bool emissionKeyword;
            public Color baseColor, emissionColor, legacyColor;
        }
        [Serializable] public sealed class WarmLampDerivation
        {
            public int schema = 1;
            public string status = "DERIVED_WARM_LAMP_MATERIAL_UNREVIEWED";
            public string path = WarmLampMaterialPath, guid = WarmLampMaterialGuid, beforeSha256, afterSha256, metaSha256;
            public long localId = 2100000, beforeBytes, afterBytes, metaBytes;
            public WarmLampState source, loaded, authored, reloaded;
            public bool loadedDirtyBeforeAuthoring, unloadVerified, reloadedClean, bytesStableAfterReload;
            public string[] semanticChanges;
        }
        static void WarmLampRequire(bool valid, string code)
        {
            if (valid) return;
            throw new InvalidOperationException("JOURNEY_WARM_LAMP_" + code);
        }
        static bool WarmLampColorEqual(Color left, Color right) =>
            Mathf.Abs(left.r - right.r) <= 0.000001f && Mathf.Abs(left.g - right.g) <= 0.000001f &&
            Mathf.Abs(left.b - right.b) <= 0.000001f && Mathf.Abs(left.a - right.a) <= 0.000001f;
        static System.Text.RegularExpressions.Match WarmLampColorMatch(string text, string property)
        {
            var rows = System.Text.RegularExpressions.Regex.Matches(text, "^    - " + System.Text.RegularExpressions.Regex.Escape(property) + @": \{r: ([^,]+), g: ([^,]+), b: ([^,]+), a: ([^}]+)\}$", System.Text.RegularExpressions.RegexOptions.Multiline);
            WarmLampRequire(rows.Count == 1, "SOURCE_FORMAT");
            return rows[0];
        }
        static string WarmLampColorLine(string text, string property) => WarmLampColorMatch(text, property).Value;
        static Color WarmLampSourceColor(string text, string property)
        {
            var match = WarmLampColorMatch(text, property);
            var values = new float[4];
            for (int i = 0; i < 4; i++)
                WarmLampRequire(float.TryParse(match.Groups[i + 1].Value, System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out values[i]) && !float.IsNaN(values[i]) && !float.IsInfinity(values[i]), "SOURCE_FORMAT");
            return new Color(values[0], values[1], values[2], values[3]);
        }
        // Pure whole-file constraint: every other line and every AssetVersion document stays exact.
        internal static string[] ValidateWarmLampSerializedChange(string before, string after)
        {
            var flags = new System.Text.RegularExpressions.Regex(@"^  m_LightmapFlags: ([0-9]+)$", System.Text.RegularExpressions.RegexOptions.Multiline);
            WarmLampRequire(flags.Matches(before).Count == 1 && flags.Match(before).Groups[1].Value == "4", "SOURCE_SEMANTICS");
            WarmLampRequire(flags.Matches(after).Count == 1 && flags.Match(after).Groups[1].Value == "2", "GI");
            var keywords = new System.Text.RegularExpressions.Regex(@"^  m_ValidKeywords:\n  - _EMISSION\n", System.Text.RegularExpressions.RegexOptions.Multiline);
            WarmLampRequire(keywords.Matches(before).Count == 1 && keywords.Matches(after).Count == 1, "KEYWORD");
            string oldAlias = WarmLampColorLine(before, "_Color"), newAlias = WarmLampColorLine(after, "_Color");
            string synchronizedAlias = WarmLampColorLine(before, "_BaseColor").Replace("_BaseColor:", "_Color:");
            WarmLampRequire(newAlias == oldAlias || newAlias == synchronizedAlias, "ALIAS");
            string oldNormalized = flags.Replace(before, "  m_LightmapFlags: AUTHORED").Replace(oldAlias, "    - _Color: AUTHORED_ALIAS");
            string newNormalized = flags.Replace(after, "  m_LightmapFlags: AUTHORED").Replace(newAlias, "    - _Color: AUTHORED_ALIAS");
            WarmLampRequire(oldNormalized == newNormalized, "UNDECLARED_SERIALIZED_CHANGE");
            return oldAlias == newAlias ? new[] { "GLOBAL_ILLUMINATION_FLAGS_4_TO_2" } :
                new[] { "GLOBAL_ILLUMINATION_FLAGS_4_TO_2", "LEGACY_COLOR_SYNCHRONIZED_TO_BASE_COLOR" };
        }
        static WarmLampState ReadWarmLampState(Material material) => new WarmLampState {
            giFlags = (int)material.globalIlluminationFlags, emissionKeyword = material.IsKeywordEnabled("_EMISSION"),
            baseColor = material.GetColor("_BaseColor"), emissionColor = material.GetColor("_EmissionColor"), legacyColor = material.GetColor("_Color") };
        static void RequireWarmLampAuthoredState(WarmLampState before, WarmLampState after)
        {
            WarmLampRequire(after.giFlags == (int)MaterialGlobalIlluminationFlags.BakedEmissive, "GI");
            WarmLampRequire(after.emissionKeyword, "KEYWORD");
            WarmLampRequire(WarmLampColorEqual(before.baseColor, after.baseColor) && WarmLampColorEqual(before.emissionColor, after.emissionColor), "RUNTIME_VALUES");
            WarmLampRequire(WarmLampColorEqual(before.baseColor, after.legacyColor), "ALIAS");
        }
        static void AuthorLitEmission(Material material)
        {
            // Explicit author intent, including eligibility for a future bake. No lighting bake is run here.
            material.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
            BaseShaderGUI.SetMaterialKeywords(material, UnityEditor.Rendering.Universal.ShaderGUI.LitGUI.SetMaterialKeywords);
        }
        static string WarmLampAliasProperty(SerializedObject value)
        {
            var colors = value.FindProperty("m_SavedProperties.m_Colors");
            WarmLampRequire(colors != null && colors.isArray, "SERIALIZED_LAYOUT");
            string result = null;
            for (int i = 0; i < colors.arraySize; i++)
            {
                var row = colors.GetArrayElementAtIndex(i);
                if (row.FindPropertyRelative("first").stringValue != "_Color") continue;
                WarmLampRequire(result == null, "SERIALIZED_LAYOUT");
                result = row.FindPropertyRelative("second").propertyPath;
            }
            WarmLampRequire(result != null, "SERIALIZED_LAYOUT"); return result;
        }
        static void RequireWarmLampOnlyAuthoredProperties(SerializedObject before, SerializedObject after)
        {
            string alias = WarmLampAliasProperty(before);
            WarmLampRequire(alias == WarmLampAliasProperty(after), "SERIALIZED_LAYOUT");
            bool Allowed(string path) => path == "m_LightmapFlags" || path == alias || path.StartsWith(alias + ".", StringComparison.Ordinal) ||
                path == "m_ValidKeywords" || path.StartsWith("m_ValidKeywords.", StringComparison.Ordinal) || path == "m_ShaderKeywords";
            var names = new HashSet<string>(StringComparer.Ordinal);
            var left = before.GetIterator();
            while (left.Next(true))
            {
                names.Add(left.propertyPath);
                var right = after.FindProperty(left.propertyPath);
                WarmLampRequire(right != null && right.propertyType == left.propertyType, "UNDECLARED_RUNTIME_CHANGE");
                if (left.propertyType == SerializedPropertyType.Generic || Allowed(left.propertyPath)) continue;
                if (!SerializedProperty.DataEquals(left, right))
                {
                    Debug.LogError("JOURNEY_WARM_LAMP_UNDECLARED_RUNTIME_CHANGE property=" + left.propertyPath);
                    WarmLampRequire(false, "UNDECLARED_RUNTIME_CHANGE");
                }
            }
            var current = after.GetIterator();
            while (current.Next(true)) WarmLampRequire(names.Contains(current.propertyPath) || Allowed(current.propertyPath), "UNDECLARED_RUNTIME_CHANGE");
        }
        static void RequireWarmLampIdentity(Material material)
        {
            WarmLampRequire(material, "IDENTITY");
            bool persistent = EditorUtility.IsPersistent(material), main = AssetDatabase.IsMainAsset(material), pathMatched = AssetDatabase.GetAssetPath(material) == WarmLampMaterialPath;
            bool identity = AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out string guid, out long id);
            string shaderGuid = ""; long shaderId = 0;
            bool shaderIdentity = material.shader && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material.shader, out shaderGuid, out shaderId);
            Debug.Log("JOURNEY_WARM_LAMP_IDENTITY persistent=" + persistent + "; main=" + main + "; pathMatched=" + pathMatched +
                "; identityAvailable=" + identity + "; guidMatched=" + (guid == WarmLampMaterialGuid) + "; localId=" + id + "; shaderIdentityAvailable=" + shaderIdentity +
                "; shaderGuidMatched=" + (shaderGuid == "933532a4fcc9baf4fa0491de14d08ed7") + "; shaderLocalId=" + shaderId);
            WarmLampRequire(persistent && main && pathMatched && identity && guid == WarmLampMaterialGuid && id == 2100000 && material.shader &&
                shaderIdentity && shaderGuid == "933532a4fcc9baf4fa0491de14d08ed7" && shaderId == 4800000, "IDENTITY");
        }
        static string WarmLampObservedField(Func<string> read)
        {
            try { return read(); } catch { return "UNAVAILABLE"; }
        }
        static void ObserveWarmLampObjects(Object[] assets, Material material, long serializedVersionId, string phase)
        {
            Debug.Log("JOURNEY_WARM_LAMP_OBJECTS phase=" + phase + "; count=" + (assets == null ? -1 : assets.Length) +
                "; containsMain=" + (assets != null && assets.Contains(material)) + "; target=" + WarmLampMaterialPath + "; serializedVersionLocalId=" + serializedVersionId);
            if (assets == null) return;
            for (int index = 0; index < assets.Length; index++)
            {
                var asset = assets[index];
                if (!asset) { Debug.Log("JOURNEY_WARM_LAMP_OBJECT phase=" + phase + "; index=" + index + "; valid=false"); continue; }
                string type = asset.GetType().FullName ?? "UNAVAILABLE";
                if (type.Length > 256 || !System.Text.RegularExpressions.Regex.IsMatch(type, @"^[A-Za-z0-9_.+`]+$")) type = "UNAVAILABLE";
                string path = WarmLampObservedField(() => { string value = AssetDatabase.GetAssetPath(asset); return value == WarmLampMaterialPath ? WarmLampMaterialPath : string.IsNullOrEmpty(value) ? "EMPTY" : "OUTSIDE_TARGET"; });
                string persistent = WarmLampObservedField(() => EditorUtility.IsPersistent(asset).ToString());
                string main = WarmLampObservedField(() => AssetDatabase.IsMainAsset(asset).ToString());
                string sub = WarmLampObservedField(() => AssetDatabase.IsSubAsset(asset).ToString());
                string dirty = WarmLampObservedField(() => EditorUtility.IsDirty(asset).ToString());
                string guid = "UNAVAILABLE", identity = "UNAVAILABLE"; long localId = 0;
                try
                {
                    bool available = AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out string foundGuid, out localId);
                    identity = available.ToString();
                    if (available && System.Text.RegularExpressions.Regex.IsMatch(foundGuid ?? "", "^[a-f0-9]{32}$")) guid = foundGuid;
                }
                catch { }
                string version = WarmLampObservedField(() => {
                    using (var data = new SerializedObject(asset))
                    {
                        data.Update(); var property = data.FindProperty("version");
                        return property == null ? "ABSENT" : property.propertyType == SerializedPropertyType.Integer ?
                            property.intValue.ToString(System.Globalization.CultureInfo.InvariantCulture) : "NON_INTEGER";
                    }
                });
                Debug.Log("JOURNEY_WARM_LAMP_OBJECT phase=" + phase + "; index=" + index + "; valid=true; ownedMain=" + (asset == material) +
                    "; type=" + type + "; path=" + path + "; persistent=" + persistent + "; isMain=" + main + "; isSub=" + sub +
                    "; identityAvailable=" + identity + "; guid=" + guid + "; localId=" + localId + "; dirty=" + dirty + "; version=" + version);
            }
        }
        static Dictionary<Object, string> ReadWarmLampOwnedObjects(Material material, long serializedVersionId, bool authoring, string phase)
        {
            // The public loader defines file ownership. Hidden object classification is diagnostic only.
            var assets = AssetDatabase.LoadAllAssetsAtPath(WarmLampMaterialPath);
            ObserveWarmLampObjects(assets, material, serializedVersionId, phase);
            WarmLampRequire(assets != null && assets.Contains(material) && assets.All(a => a), "SUBASSET_IDENTITY");
            var snapshots = new Dictionary<Object, string>();
            foreach (var asset in assets.Distinct())
            {
                bool dirty = EditorUtility.IsDirty(asset), main = asset == material;
                Debug.Log("JOURNEY_WARM_LAMP_OBJECT_CHECK phase=" + phase + "; ownedMain=" + main + "; dirty=" + dirty + "; mainAuthoringAllowed=" + authoring);
                WarmLampRequire(!dirty || main && authoring, main ? phase == "LOAD" ? "LOADED_DIRTY" : "RELOAD_DIRTY" : "SUBASSET_DIRTY");
                snapshots.Add(asset, main || (phase != "LOAD" && phase != "AUTHOR") ? "" : EditorJsonUtility.ToJson(asset));
                bool dirtyAfterSnapshot = EditorUtility.IsDirty(asset);
                Debug.Log("JOURNEY_WARM_LAMP_OBJECT_CHECK phase=" + phase + "; ownedMain=" + main + "; dirtyAfterSnapshot=" + dirtyAfterSnapshot + "; mainAuthoringAllowed=" + authoring);
                WarmLampRequire(!dirtyAfterSnapshot || main && authoring, main ? phase == "LOAD" ? "LOADED_DIRTY" : "RELOAD_DIRTY" : "SUBASSET_DIRTY");
            }
            return snapshots;
        }
        static void RequireWarmLampOtherObjectsUnchanged(Dictionary<Object, string> before, Dictionary<Object, string> after)
        {
            bool sameObjects = new HashSet<Object>(before.Keys).SetEquals(after.Keys);
            bool sameData = sameObjects && before.All(pair => pair.Key && after[pair.Key] == pair.Value);
            Debug.Log("JOURNEY_WARM_LAMP_OBJECT_SNAPSHOT sameObjects=" + sameObjects + "; sameSerializedData=" + sameData);
            WarmLampRequire(sameObjects && sameData, "SUBASSET_CHANGED");
        }
        static Dictionary<int, string> WarmLampSceneState()
        {
            var result = new Dictionary<int, string>();
            for (int index = 0; index < SceneManager.sceneCount; index++)
            {
                var scene = SceneManager.GetSceneAt(index);
                WarmLampRequire(scene.IsValid(), "SCENE_CHANGED");
                result.Add(scene.handle, scene.path + "|" + scene.isLoaded + "|" + scene.isDirty);
            }
            return result;
        }
        static void RequireWarmLampOtherAssetsClean(Material owned, Dictionary<int, string> sceneState)
        {
            var currentScenes = WarmLampSceneState();
            WarmLampRequire(sceneState.Count == currentScenes.Count && sceneState.All(pair => currentScenes.TryGetValue(pair.Key, out string state) && state == pair.Value), "SCENE_CHANGED");
            foreach (var asset in Resources.FindObjectsOfTypeAll<Object>())
            {
                if (!asset || asset == owned || !EditorUtility.IsPersistent(asset) || !(asset is Material || asset is AssetImporter)) continue;
                string path = AssetDatabase.GetAssetPath(asset);
                if (!path.StartsWith("Assets/", StringComparison.Ordinal) && !path.StartsWith("Packages/", StringComparison.Ordinal)) continue;
                WarmLampRequire(!EditorUtility.IsDirty(asset), "OTHER_ASSET_DIRTY");
            }
        }
        static void RequireWarmLampOtherBytesUnchanged(Dictionary<string, string> before, bool allowOwnedChange)
        {
            var after = SnapshotProtectedFiles(true);
            WarmLampRequire(new HashSet<string>(before.Keys, StringComparer.Ordinal).SetEquals(after.Keys) && before.All(pair =>
                allowOwnedChange && pair.Key == WarmLampMaterialPath || after[pair.Key] == pair.Value), "PROTECTION");
        }
        public static WarmLampDerivation AuthorPinnedWarmLamp()
        {
            string phase = "INPUT";
            Dictionary<string, string> protectedFiles = null;
            var failures = new List<Exception>(); WarmLampDerivation record = null;
            try
            {
                WarmLampRequire(!Application.isPlaying && !BuildPipeline.isBuildingPlayer && Application.unityVersion == "6000.3.19f1", "CONTEXT");
                WarmLampRequire(JourneyDiagnosticScope.IsPinnedPathSafe(WarmLampMaterialPath, out _) &&
                    new FileInfo(WarmLampMaterialPath).Length == 3845 && HashFile(WarmLampMaterialPath) == WarmLampOriginalSha, "SOURCE_PIN");
                WarmLampRequire(JourneyDiagnosticScope.IsPinnedPathSafe(WarmLampMaterialPath + ".meta", out _) &&
                    new FileInfo(WarmLampMaterialPath + ".meta").Length == 188 && HashFile(WarmLampMaterialPath + ".meta") == WarmLampMetaSha, "META_PIN");
                protectedFiles = SnapshotProtectedFiles(true);
                var sceneState = WarmLampSceneState();
                string original = File.ReadAllText(WarmLampMaterialPath);
                var originalFlags = System.Text.RegularExpressions.Regex.Matches(original, @"^  m_LightmapFlags: ([0-9]+)$", System.Text.RegularExpressions.RegexOptions.Multiline);
                var versionRows = System.Text.RegularExpressions.Regex.Matches(original, @"^--- !u!114 &([0-9]+)$", System.Text.RegularExpressions.RegexOptions.Multiline);
                WarmLampRequire(originalFlags.Count == 1 && originalFlags[0].Groups[1].Value == "4" && versionRows.Count == 1, "SOURCE_FORMAT");
                long versionId = long.Parse(versionRows[0].Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
                record = new WarmLampDerivation { beforeSha256 = WarmLampOriginalSha, beforeBytes = 3845, metaSha256 = WarmLampMetaSha, metaBytes = 188,
                    source = new WarmLampState { giFlags = int.Parse(originalFlags[0].Groups[1].Value), emissionKeyword = original.Contains("  m_ValidKeywords:\n  - _EMISSION\n"), baseColor = WarmLampSourceColor(original, "_BaseColor"),
                        emissionColor = WarmLampSourceColor(original, "_EmissionColor"), legacyColor = WarmLampSourceColor(original, "_Color") } };
                phase = "LOAD";
                foreach (var existing in Resources.FindObjectsOfTypeAll<Material>())
                    if (existing && EditorUtility.IsPersistent(existing) && AssetDatabase.GetAssetPath(existing) == WarmLampMaterialPath)
                    {
                        RequireWarmLampIdentity(existing);
                        Debug.Log("JOURNEY_WARM_LAMP_EXISTING dirty=" + EditorUtility.IsDirty(existing) + "; state=" + JsonUtility.ToJson(ReadWarmLampState(existing)));
                        WarmLampRequire(!EditorUtility.IsDirty(existing), "LOADED_DIRTY");
                    }
                var material = AssetDatabase.LoadAssetAtPath<Material>(WarmLampMaterialPath); RequireWarmLampIdentity(material);
                record.loaded = ReadWarmLampState(material); record.loadedDirtyBeforeAuthoring = EditorUtility.IsDirty(material);
                Debug.Log("JOURNEY_WARM_LAMP_BEFORE source=" + JsonUtility.ToJson(record.source) + "; loaded=" + JsonUtility.ToJson(record.loaded) + "; loadedDirty=" + record.loadedDirtyBeforeAuthoring);
                var ownedBefore = ReadWarmLampOwnedObjects(material, versionId, false, "LOAD");
                record.loaded = ReadWarmLampState(material); record.loadedDirtyBeforeAuthoring = EditorUtility.IsDirty(material);
                Debug.Log("JOURNEY_WARM_LAMP_BEFORE allObjectsLoaded=true; source=" + JsonUtility.ToJson(record.source) + "; loaded=" + JsonUtility.ToJson(record.loaded) + "; loadedDirty=" + record.loadedDirtyBeforeAuthoring);
                // A dirty loaded object is not a trustworthy copy of the pinned source. Never save it.
                WarmLampRequire(!record.loadedDirtyBeforeAuthoring, "LOADED_DIRTY");
                WarmLampRequire(record.loaded.giFlags == record.source.giFlags &&
                    WarmLampColorEqual(record.loaded.baseColor, record.source.baseColor) &&
                    WarmLampColorEqual(record.loaded.emissionColor, record.source.emissionColor) &&
                    (WarmLampColorEqual(record.loaded.legacyColor, record.source.legacyColor) || WarmLampColorEqual(record.loaded.legacyColor, record.source.baseColor)), "LOADED_SOURCE");
                RequireWarmLampOtherAssetsClean(material, sceneState);
                phase = "AUTHOR";
                using (var before = new SerializedObject(material))
                {
                    before.Update();
                    AuthorLitEmission(material);
                    var ownedAfter = ReadWarmLampOwnedObjects(material, versionId, true, "AUTHOR");
                    RequireWarmLampOtherObjectsUnchanged(ownedBefore, ownedAfter);
                    record.authored = ReadWarmLampState(material);
                    Debug.Log("JOURNEY_WARM_LAMP_AUTHORED " + JsonUtility.ToJson(record.authored));
                    RequireWarmLampAuthoredState(record.loaded, record.authored);
                    WarmLampRequire(material.shaderKeywords.Length == 1 && material.shaderKeywords[0] == "_EMISSION", "KEYWORD");
                    using (var after = new SerializedObject(material)) { after.Update(); RequireWarmLampOnlyAuthoredProperties(before, after); }
                }
                RequireWarmLampOtherAssetsClean(material, sceneState);
                RequireWarmLampOtherBytesUnchanged(protectedFiles, false);
                phase = "SAVE";
                EditorUtility.SetDirty(material);
                AssetDatabase.SaveAssetIfDirty(AssetDatabase.GUIDFromAssetPath(WarmLampMaterialPath));
                string saved = File.ReadAllText(WarmLampMaterialPath);
                record.semanticChanges = ValidateWarmLampSerializedChange(original, saved);
                record.afterSha256 = HashFile(WarmLampMaterialPath); record.afterBytes = new FileInfo(WarmLampMaterialPath).Length;
                RequireWarmLampOtherBytesUnchanged(protectedFiles, true);
                phase = "IMPORT";
                AssetDatabase.ImportAsset(WarmLampMaterialPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                WarmLampRequire(HashFile(WarmLampMaterialPath) == record.afterSha256, "IMPORT_BYTES");
                material = AssetDatabase.LoadAssetAtPath<Material>(WarmLampMaterialPath); RequireWarmLampIdentity(material);
                var importedObjects = ReadWarmLampOwnedObjects(material, versionId, false, "IMPORT").Keys.ToArray();
                phase = "UNLOAD";
                // Explicitly release this exact owned asset file's objects; never use instance-ID equality as a reload test.
                foreach (var asset in importedObjects) if (asset) Resources.UnloadAsset(asset);
                record.unloadVerified = importedObjects.All(a => !a);
                Debug.Log("JOURNEY_WARM_LAMP_UNLOADED returnedCount=" + importedObjects.Length + "; invalidatedCount=" + importedObjects.Count(a => !a) + "; verified=" + record.unloadVerified);
                WarmLampRequire(record.unloadVerified, "UNLOAD");
                phase = "RELOAD";
                material = AssetDatabase.LoadAssetAtPath<Material>(WarmLampMaterialPath); RequireWarmLampIdentity(material);
                var reloadedObjects = ReadWarmLampOwnedObjects(material, versionId, false, "RELOAD").Keys.ToArray();
                record.reloaded = ReadWarmLampState(material);
                record.reloadedClean = reloadedObjects.Length > 0 && reloadedObjects.All(a => a && !EditorUtility.IsDirty(a));
                Debug.Log("JOURNEY_WARM_LAMP_RELOADED " + JsonUtility.ToJson(record.reloaded) + "; clean=" + record.reloadedClean + "; unloaded=" + record.unloadVerified);
                RequireWarmLampAuthoredState(record.loaded, record.reloaded);
                WarmLampRequire(material.shaderKeywords.Length == 1 && material.shaderKeywords[0] == "_EMISSION", "KEYWORD");
                WarmLampRequire(record.reloadedClean, "RELOAD_DIRTY");
                record.bytesStableAfterReload = HashFile(WarmLampMaterialPath) == record.afterSha256 && new FileInfo(WarmLampMaterialPath).Length == record.afterBytes;
                WarmLampRequire(record.bytesStableAfterReload, "RELOAD_BYTES");
                ValidateWarmLampSerializedChange(original, File.ReadAllText(WarmLampMaterialPath));
                RequireWarmLampOtherAssetsClean(material, sceneState);
            }
            catch (Exception error)
            {
                Exception failure = error is InvalidOperationException && error.Message.StartsWith("JOURNEY_WARM_LAMP_", StringComparison.Ordinal) ? error :
                    new InvalidOperationException("JOURNEY_WARM_LAMP_NATIVE_" + phase, error);
                Debug.LogError("JOURNEY_WARM_LAMP_FAILURE phase=" + phase + "; code=" + failure.Message);
                failures.Add(failure);
            }
            finally
            {
                if (protectedFiles != null)
                    try { RequireWarmLampOtherBytesUnchanged(protectedFiles, true); }
                    catch (Exception error) { failures.Add(error is InvalidOperationException && error.Message == "JOURNEY_WARM_LAMP_PROTECTION" ? error : new InvalidOperationException("JOURNEY_WARM_LAMP_PROTECTION", error)); }
            }
            if (failures.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failures[0]).Throw();
            if (failures.Count > 1) throw new AggregateException("Warm material authoring and protection failed; primary first.", failures);
            return record;
        }

        static Material LayoutMaterial(Color color,string tile,Vector2 tiling,bool emission=false)
        {
            string path=Folder+"/Layout-"+ColorUtility.ToHtmlStringRGB(color)+".mat";
            var material=AssetDatabase.LoadAssetAtPath<Material>(path);
            if(!material)
            {
                var shader=Shader.Find("Universal Render Pipeline/Lit");if(!shader||!shader.isSupported)throw new InvalidOperationException("Supported URP/Lit required for candidate materials.");
                material=new Material(shader);material.SetColor("_BaseColor",color);material.SetFloat("_Smoothness",.12f);AssetDatabase.CreateAsset(material,path);
            }
            // This path is generated-only. Never mutate a shared source material or its importer.
            if(tile!=null){var tex=AssetDatabase.LoadAssetAtPath<Texture2D>(tile=="painted-sand"?"Assets/DesertRV/Art/sand-handpainted-v1.png":"Assets/DesertRV/Art/Textures/polish-"+tile+"-albedo.png");if(!tex)throw new InvalidOperationException("Existing texture missing: "+tile);material.SetColor("_BaseColor",Color.white);material.SetTexture("_BaseMap",tex);material.SetTextureScale("_BaseMap",tiling);}
            if(emission){material.SetColor("_EmissionColor",color*2.5f);if(path==WarmLampMaterialPath)AuthorLitEmission(material);else material.EnableKeyword("_EMISSION");}
            EditorUtility.SetDirty(material);return material;
        }
        static Transform CopySized(Scene source,Transform parent,string name,Vector3 at,Vector3 maximum,params string[] prefixes)
        {
            var root=CopyCluster(source,parent,name,at,prefixes);Bounds bounds=GeometryBounds(root);
            float scale=Mathf.Min(maximum.x/Mathf.Max(.001f,bounds.size.x),Mathf.Min(maximum.y/Mathf.Max(.001f,bounds.size.y),maximum.z/Mathf.Max(.001f,bounds.size.z)));
            root.localScale*=scale;PlaceGeometry(root,at);Physics.SyncTransforms();bounds=GeometryBounds(root);
            if(bounds.size.x>maximum.x+.02f||bounds.size.y>maximum.y+.02f||bounds.size.z>maximum.z+.02f)throw new InvalidOperationException("World bounds normalization failed: "+name);
            return root;
        }
        static Bounds GeometryBounds(Transform root)
        {var renderers=root.GetComponentsInChildren<Renderer>(true);if(renderers.Length==0)throw new InvalidOperationException("No geometry: "+root.name);var b=renderers[0].bounds;foreach(var r in renderers.Skip(1))b.Encapsulate(r.bounds);return b;}
        static JourneyActions.ArcMeshSnapshot ReadArcMeshGeometry(Mesh mesh)
        {
            if (!mesh) throw new InvalidOperationException("Missing retained collider mesh.");
            using (var data = MeshUtility.AcquireReadOnlyMeshData(mesh))
            using (var vertices = new NativeArray<Vector3>(data[0].vertexCount, Allocator.Temp))
            {
                data[0].GetVertices(vertices); var triangles = new List<int>();
                for (int sub = 0; sub < data[0].subMeshCount; sub++)
                {
                    var descriptor = data[0].GetSubMesh(sub);
                    if (descriptor.topology != MeshTopology.Triangles || descriptor.indexCount % 3 != 0) throw new InvalidOperationException("Retained collider has nontriangle topology.");
                    using (var indices = new NativeArray<int>(descriptor.indexCount, Allocator.Temp))
                    { data[0].GetIndices(indices, sub, true); triangles.AddRange(indices.ToArray()); }
                }
                return JourneyActions.ArcMeshSnapshot.FromImportedMesh(mesh, vertices.ToArray(), triangles.ToArray());
            }
        }
        static Mesh[] ArcColliderMeshes(JourneyActions actions)
        {
            if (!actions || !actions.motor || !actions.motor.vehicle) throw new InvalidOperationException("Missing retained arc collider owner.");
            return actions.motor.vehicle.GetComponentsInChildren<MeshCollider>(true).Where(c => !c.convex && !c.isTrigger).Select(c => c.sharedMesh).Distinct().ToArray();
        }
        public static void AuthorArcMeshGeometry(JourneyActions actions)
        {
            actions.arcMeshGeometry = ArcColliderMeshes(actions).Select(ReadArcMeshGeometry).ToArray();
            EditorUtility.SetDirty(actions);
        }
        public static bool ValidateArcMeshGeometry(JourneyActions actions, out string reason)
        {
            reason = null;
            try
            {
                var expected = ArcColliderMeshes(actions); var actual = actions.arcMeshGeometry;
                if (actual == null || actual.Length != expected.Length || actual.Any(s => s == null || !s.SourceMesh) || actual.Select(s => s.SourceMesh).Distinct().Count() != actual.Length)
                    throw new InvalidOperationException("Missing/duplicate retained arc geometry inventory.");
                foreach (var mesh in expected)
                {
                    var found = actual.SingleOrDefault(s => s.SourceMesh == mesh); var source = ReadArcMeshGeometry(mesh);
                    if (found == null || found.Sha256 != source.Sha256 || JourneyActions.ArcGeometryDigest(found) != source.Sha256)
                        throw new InvalidOperationException("Retained arc mesh identity/hash/topology differs from actual imported data.");
                }
                return true;
            }
            catch (Exception error) { reason = error.Message; return false; }
        }
        static float InteractionSurfaceDistanceSquared(Collider collider, Vector3 point)
        {
            if (!collider || !collider.enabled || !collider.gameObject.activeInHierarchy || collider.isTrigger) throw new InvalidOperationException("Missing/inactive interaction surface.");
            if (collider is MeshCollider mesh && !mesh.convex)
                return JourneyActions.ArcMeshDistanceSquared(ReadArcMeshGeometry(mesh.sharedMesh), collider.transform.localToWorldMatrix, point, out _);
            if (collider is BoxCollider || collider is SphereCollider || collider is CapsuleCollider || collider is MeshCollider convex && convex.convex)
                return (collider.ClosestPoint(point) - point).sqrMagnitude;
            throw new InvalidOperationException("Unsupported interaction surface collider.");
        }
        [Serializable] sealed class ClearanceReport {public int region;public bool passed;public string[] checkedZones;public int distantMeshes;}
        static void CheckNewLayoutClearance(RegionBinding b,JourneyMotor motor,JourneyActions actions)
        {
            Physics.SyncTransforms();var zones=new Dictionary<string,Bounds>();
            if(b.powerPoint && (!b.powerSurface || InteractionSurfaceDistanceSquared(b.powerSurface,b.powerPoint.position)>.65f*.65f))
                throw new InvalidOperationException("Power interaction point is detached from its real surface after transform synchronization.");
            if(b.salvage && (!b.salvageSurface || InteractionSurfaceDistanceSquared(b.salvageSurface,b.salvage.position)>1f))
                throw new InvalidOperationException("Salvage interaction point is detached from its real surface after transform synchronization.");
            zones["driving-corridor"]=new Bounds(new Vector3(0,2.1f,30),new Vector3(8.6f,3.8f,78));
            zones["vehicle-spawn"]=new Bounds(b.spawn.position+Vector3.up*1.65f,new Vector3(4.5f,3.1f,8));
            var step=motor.entryStep.GetComponent<Renderer>().bounds.center;float side=Mathf.Sign(step.x-motor.vehicle.position.x);if(side==0)side=1;
            zones["dismount"]=new Bounds(step+new Vector3(side*.85f,.9f,0),new Vector3(1.25f,1.65f,1.5f));
            zones["cabin-workbench"]=new Bounds(actions.cabinWorkbench.position,new Vector3(.7f,1.6f,.7f));
            if(b.salvage)zones["salvage-access"]=new Bounds(b.salvage.position+Vector3.up*.75f,new Vector3(.65f,1.3f,.65f));
            if(b.powerPoint)zones["power-access"]=new Bounds(b.powerPoint.position+Vector3.back*.6f+Vector3.up*.35f,new Vector3(.8f,1.4f,.8f));
            foreach(var interaction in new[]{b.salvage,b.powerPoint}) if(interaction)
            {
                Vector3 end=interaction.position;Vector3 start=new Vector3(Mathf.Clamp(end.x,-4,4),end.y,end.z);
                if(Vector3.Distance(start,end)<1.1f)continue;end=Vector3.MoveTowards(end,start,1);
                zones["short-approach-"+interaction.name]=new Bounds((start+end)*.5f+Vector3.up*.8f,new Vector3(Mathf.Abs(end.x-start.x)+.65f,1.5f,.8f));
            }
            foreach(var r in b.GetComponentsInChildren<Renderer>(true))
            {
                if(!r.enabled||!r.gameObject.activeInHierarchy||r.bounds.max.y<.18f||(b.ramGate&&r.transform.IsChildOf(b.ramGate.transform))||r.GetComponent<Collider>()==b.salvageSurface||r.GetComponent<Collider>()==b.powerSurface||
                    (b.salvageVisual&&r.transform.IsChildOf(b.salvageVisual.transform))||r.GetComponentInParent<BeastActor>())continue;
                foreach(var zone in zones)if(r.bounds.Intersects(zone.Value))throw new InvalidOperationException("New visible geometry blocks "+zone.Key+": "+r.name+" "+r.bounds);
            }
            foreach(var collider in b.GetComponentsInChildren<Collider>(true))
            {
                if(!collider.enabled||!collider.gameObject.activeInHierarchy||collider.isTrigger||collider.bounds.max.y<.18f||collider==b.ramGate||collider==b.salvageSurface||collider==b.powerSurface||collider.GetComponentInParent<BeastActor>())continue;
                foreach(var zone in zones)if(collider.bounds.Intersects(zone.Value))throw new InvalidOperationException("New collider blocks "+zone.Key+": "+collider.name);
            }
            CheckOptionalSupplyApproaches(b);
            var mesas=b.GetComponentsInChildren<Transform>(true).Where(t=>t.name.StartsWith("DISTANT-Mesa-",StringComparison.Ordinal)).ToArray();
            foreach(var mesa in mesas){var bounds=GeometryBounds(mesa);if(bounds.min.x<35&&bounds.max.x>-35&&bounds.min.z<85)throw new InvalidOperationException("Mesa invades the open play basin: "+mesa.name);}
            Directory.CreateDirectory("JourneyEvidence");File.WriteAllText("JourneyEvidence/clearance-region-"+b.region+".json",JsonUtility.ToJson(new ClearanceReport{region=b.region,passed=true,checkedZones=zones.Keys.ToArray(),distantMeshes=mesas.Length},true));
        }
        static Transform viewerBench(Scene scene) => Components<Transform>(scene).Single(t => t.name == "GEO-garage_workbench_top");
        static void MoveUnder(Transform obj, Transform parent, Scene scene)
        { obj.SetParent(null, true); SceneManager.MoveGameObjectToScene(obj.gameObject, scene); obj.SetParent(parent, true); }
        static RegionBinding NewBinding(Scene scene, int region)
        {
            var root = new GameObject("Region " + region + " environment"); SceneManager.MoveGameObjectToScene(root, scene);
            var b = root.AddComponent<RegionBinding>(); b.region = region; b.regionOffset = RegionOffsets[region - 1]; b.progressDirection = Vector3.forward;
            b.spawn = Point("Vehicle spawn", root.transform, Vector3.zero);
            b.spawn.rotation = Quaternion.identity; // caller copies the retained RV rotation (localForward need not be +Z)
            b.exit = Point("Vehicle exit", root.transform, new Vector3(0,0,64));
            b.exitVolume = Volume("Exit volume", root.transform, new Vector3(0,2,64), new Vector3(10,6,8));
            b.pickupId = region == 1 ? "first-station/ram" : "scrapyard/coil";
            b.environmentVerified = b.combatAssetsVerified = false;
            return b;
        }
        // Keep the endpoint in front of the cabinet face and its status indicators.
        internal static Vector3 PowerInteractionPosition(Collider power) => power.bounds.center + Vector3.back * .50f;

        static void PopulateLayout(RegionBinding b, JourneyContentManifest manifest)
        {
            Solid("Route foundation", b.transform, new Vector3(0,-.24f,30), new Vector3(34,.4f,94), new Color(.46f,.37f,.25f));
            if (b.region == 1)
                b.ramGate = Solid("Ram breakaway road gate", b.transform, new Vector3(0,1.1f,51), new Vector3(20,2.2f,.7f), new Color(.52f,.27f,.12f));
            else
            {
                var power = Solid(b.region == 3 ? "Beacon power cabinet" : "Scrapyard power cabinet", b.transform, new Vector3(6,.65f,23), new Vector3(1.1f,1.3f,.8f), new Color(.21f,.31f,.33f));
                b.powerSurface = power; b.powerPoint = Point("Power interaction", b.transform, PowerInteractionPosition(power));
                b.chargeSeconds = b.region == 3 ? 36 : 28;
                if (b.region == 2)
                {
                    b.salvageSurface = Solid("Coil salvage bench", b.transform, new Vector3(8,.45f,30), new Vector3(2,.9f,1), new Color(.42f,.3f,.19f));
                    b.salvage = Point("Coil interaction", b.transform, b.salvageSurface.bounds.center + Vector3.up * .65f);
                }
                else
                {
                    b.safeZone = Volume("Beacon safe zone", b.transform, new Vector3(0,2,62), new Vector3(12,6,12));
                }
            }
            // Only real supplied prefabs are instantiated. Missing art leaves explicit empty arrays and a failing production gate.
            b.guards = b.region == 1 ? Spawn(manifest.pouncer, b, new[] { new Vector3(-6,0,18),new Vector3(6,0,24) }) : Array.Empty<BeastActor>();
            b.roadBeasts = b.region == 1 ? Spawn(manifest.armored, b, new[] { new Vector3(0,0,39) }) : Array.Empty<BeastActor>();
            b.waves = b.region == 1 ? Array.Empty<RegionWave>() : new[] {
                new RegionWave { enemies = Spawn(manifest.pouncer, b, new[] { new Vector3(-7,0,33), new Vector3(7,0,39) }) },
                new RegionWave { enemies = Spawn(manifest.armored, b, new[] { new Vector3(-5,0,43) }) }
            };
        }
        static BeastActor[] Spawn(JourneyAssetReview review, RegionBinding binding, Vector3[] at)
        {
            if (review == null || !review.prefab || !review.prefab.GetComponent<BeastActor>()) return Array.Empty<BeastActor>();
            return at.Select(position => { var go = (GameObject)PrefabUtility.InstantiatePrefab(review.prefab, binding.transform); go.transform.position = position; return go.GetComponent<BeastActor>(); }).ToArray();
        }
        static GameObject CopyModule(GameObject original, Vector3 position, Transform parent, string name)
        { var holder=new GameObject(name).transform; holder.SetParent(parent,false); var copy=Object.Instantiate(original,holder,true); copy.SetActive(true); PlaceGeometry(holder,Vector3.zero); holder.localScale=Vector3.one*.18f; holder.position=position; foreach(var c in holder.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(c); return holder.gameObject; }
        static Transform[] SourceGeometry(Scene scene) => scene.GetRootGameObjects().Single(r=>r.name=="Station visual candidate").GetComponentsInChildren<Transform>(true);
        static Transform CopyCluster(Scene source,Transform parent,string name,Vector3 at,params string[] prefixes)
        {
            var holder=new GameObject(name).transform; holder.SetParent(parent,false);
            foreach(var part in SourceGeometry(source).Where(t=>prefixes.Any(p=>t.name.StartsWith(p,StringComparison.Ordinal))))
            {var copy=Object.Instantiate(part.gameObject,holder,true);copy.SetActive(true);
                foreach(var t in copy.GetComponentsInChildren<Transform>(true))GameObjectUtility.SetStaticEditorFlags(t.gameObject,0);
                foreach(var r in copy.GetComponentsInChildren<Renderer>(true)){r.lightmapIndex=-1;r.realtimeLightmapIndex=-1;}
            }
            PlaceGeometry(holder,at);return holder;
        }
        static void PlaceGeometry(Transform root,Vector3 at)
        {
            var renderers=root.GetComponentsInChildren<Renderer>(true);
            if(renderers.Length==0) throw new InvalidOperationException("Retained scenery cluster has no visible geometry: "+root.name);
            Bounds bounds=renderers[0].bounds; foreach(var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
            root.position += at-new Vector3(bounds.center.x,bounds.min.y,bounds.center.z);
            // Root becomes a local pivot at the requested anchor while all child world transforms stay fixed.
            var children=root.Cast<Transform>().ToArray(); foreach(var child in children) child.SetParent(root.parent,true);
            root.position=at; foreach(var child in children) child.SetParent(root,true);
        }
        static Collider ExactSurface(Transform t)
        { var collider = t.GetComponent<Collider>(); if (collider) { Physics.SyncTransforms(); return collider; } var mesh = t.GetComponent<MeshFilter>(); if (!mesh || !mesh.sharedMesh) throw new InvalidOperationException("Missing exact interaction mesh: " + t.name); var box = t.gameObject.AddComponent<BoxCollider>(); box.center = mesh.sharedMesh.bounds.center; box.size = mesh.sharedMesh.bounds.size; Physics.SyncTransforms(); return box; }
        static Collider Solid(string name,Transform parent,Vector3 at,Vector3 size,Color color)
        {var go=GameObject.CreatePrimitive(PrimitiveType.Cube);go.name=name;go.transform.SetParent(parent,false);go.transform.position=at;go.transform.localScale=size;go.GetComponent<Renderer>().sharedMaterial=LayoutMaterial(color,null,Vector2.one);Physics.SyncTransforms();return go.GetComponent<Collider>();}
        static Collider Volume(string name, Transform parent, Vector3 at, Vector3 size)
        { var go = new GameObject(name); go.transform.SetParent(parent,false); go.transform.position = at; var c = go.AddComponent<BoxCollider>(); c.size = size; c.isTrigger = true; return c; }
        static Transform Point(string name, Transform parent, Vector3 at)
        { var t = new GameObject(name).transform; t.SetParent(parent,true); t.position = at; return t; }
        static AudioClip Audio(string name) => AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/DesertRV/Audio/" + name + ".wav");
        static T[] Components<T>(Scene scene) where T : Component => scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<T>(true)).ToArray();
        static void Save(Scene scene, string path) { if (!EditorSceneManager.SaveScene(scene,path)) throw new IOException("Failed to save " + path); }
    }
}
