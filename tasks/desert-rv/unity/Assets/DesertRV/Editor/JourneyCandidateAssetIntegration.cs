using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    // Explicit EditMode assembly of existing native STRICT artifacts. No import, review or build.
    public static partial class JourneyCandidateAssetIntegration
    {
        public const string Label = "STRICT_CANDIDATES_BOUND_UNREVIEWED";
        public const string ReportPath = "JourneyEvidence/journey-candidate-integration.json";
        [Serializable] public class FilePin { public string path, sha256; }
        [Serializable] public sealed class AssetPin : FilePin { public string dependencyHash, dependencySha256; }
        [Serializable] public sealed class Candidate
        {
            public string kind, sourceModelPath;
            public AssetPin prefab;
            public FilePin contract, importReport;
        }
        [Serializable] public sealed class Pose
        {
            public Vector3 localPosition, localScale;
            public Quaternion localRotation;
        }
        [Serializable] public sealed class EnemyPlacement
        {
            public string id, kind;
            public Vector3 position;
            public float yaw;
        }
        [Serializable] public sealed class Wave { public EnemyPlacement[] enemies; }
        [Serializable] public sealed class RegionPlan
        {
            public int region;
            public EnemyPlacement[] guards, roadBeasts;
            public Wave[] waves;
        }
        [Serializable] public sealed class Sound { public string role; public AssetPin clip; }
        [Serializable] public sealed class Request
        {
            public int schema;
            public string label, sourceCommit;
            public Candidate[] candidates;
            public AssetPin[] savedInputs;
            public AssetPin muzzleFlashPrefab, arcPresentationPrefab;
            public Pose weaponCameraPose, flashMuzzlePose, arcModulePose;
            public Sound[] sounds;
            public RegionPlan[] regions;
        }
        [Serializable] public sealed class OutputFile
        {
            public string path, sha256, dependencyHash, dependencySha256;
        }
        [Serializable] public sealed class Result
        {
            public string status = "failed-no-approval", sourceCommit, requestSha256;
            public bool candidateOnly = true, visualReviewed = false, gameplayReviewed = false, audioAuditioned = false;
            public bool protectedSourcesUnchanged, rolledBack;
            public string[] failures = Array.Empty<string>(), productionGateFailures = Array.Empty<string>();
            public FilePin[] protectedFiles;
            public OutputFile[] outputs;
        }
        sealed class Resolved
        {
            public Candidate input;
            public GameObject prefab;
            public JourneyCandidateArtImport.Contract contract;
            public JourneyCandidateArtImport.Report report;
        }
        public static string[] TargetPaths() => new[] { JourneySceneAuthoring.BootstrapPath }
            .Concat(JourneySceneAuthoring.RegionPaths).Concat(new[] { JourneySceneAuthoring.ManifestPath }).ToArray();
        static readonly string[] Kinds = { "pouncer", "armored", "weapon" };
        static readonly string[] SoundRoles = { "shot", "hit", "reload", "pickup", "upgrade", "wind", "arc" };
        static void Require(bool ok, string reason) { if (!ok) throw new InvalidOperationException(reason); }
        static bool Finite(float n) => !float.IsNaN(n) && !float.IsInfinity(n);
        static bool Finite(Vector3 v) => Finite(v.x) && Finite(v.y) && Finite(v.z);
        static bool Hash(string s, int length) => Regex.IsMatch(s ?? "", "^[a-f0-9]{" + length + "}$");
        static void PoseShape(Pose p)
        {
            Require(p != null && Finite(p.localPosition) && Finite(p.localScale) &&
                Finite(p.localRotation.x) && Finite(p.localRotation.y) && Finite(p.localRotation.z) && Finite(p.localRotation.w) &&
                Mathf.Abs(Quaternion.Dot(p.localRotation, p.localRotation) - 1) <= .0001f && p.localScale == Vector3.one, "Explicit finite pose with unit outer scale required; do not renormalize imported rig scale.");
        }
        static void NamedPoseShape(Pose pose, string role)
        {
            try { PoseShape(pose); }
            catch (InvalidOperationException error)
            {
                string values = pose == null ? "null" : JsonUtility.ToJson(pose) +
                    "; positionFinite=" + Finite(pose.localPosition) + "; scaleFinite=" + Finite(pose.localScale) +
                    "; rotationFinite=" + (Finite(pose.localRotation.x) && Finite(pose.localRotation.y) && Finite(pose.localRotation.z) && Finite(pose.localRotation.w)) +
                    "; rotationNormSquared=" + Quaternion.Dot(pose.localRotation, pose.localRotation).ToString("R", System.Globalization.CultureInfo.InvariantCulture) +
                    "; unitOuterScale=" + (pose.localScale == Vector3.one);
                throw new InvalidOperationException(role + " rejected: " + values + "; " + error.Message, error);
            }
        }
        internal static Pose ResolveArcModulePose(string source, Pose selected, Pose derived)
        {
            Require(source == "selection" || source == "scene-geometry", "Explicit pinned arc pose source required.");
            if (source == "selection") { NamedPoseShape(selected, "arcModulePose(selection)"); return selected; }
            // Observe this Unity version's representation of the exact null field, rather than accepting an arbitrary invalid pose.
            var nullPose = JsonUtility.FromJson<Request>("{\"arcModulePose\":null}").arcModulePose;
            Require(selected == null && nullPose == null || selected != null && nullPose != null &&
                selected.localPosition.Equals(nullPose.localPosition) && selected.localScale.Equals(nullPose.localScale) && selected.localRotation.Equals(nullPose.localRotation),
                "Scene-derived arc pose requires the explicitly selected JSON null; supplied pose cannot be replaced.");
            NamedPoseShape(derived, "arcModulePose(actual scene geometry)"); return derived;
        }
        // Public pure input-shape check: useful to fail before asset/scene writes and in isolated NUnit tests.
        public static void ValidateRequestShape(Request r, string expectedCommit)
        {
            Require(r != null && r.schema == 1 && r.label == Label && Hash(r.sourceCommit, 40) &&
                r.sourceCommit == expectedCommit, "Explicit schema, candidate label and current Actions commit required.");
            Require(r.candidates != null && r.candidates.Length == 3 && r.candidates.All(c => c != null) &&
                new HashSet<string>(r.candidates.Select(c => c.kind)).SetEquals(Kinds), "Exactly one pouncer, armored and weapon STRICT candidate required.");
            foreach (var c in r.candidates)
                Require(c.prefab != null && c.contract != null && c.importReport != null &&
                    !string.IsNullOrWhiteSpace(c.sourceModelPath), "Candidate requires explicit prefab, contract, import report and source model path.");
            Require(r.savedInputs != null && r.savedInputs.Length == 5 && r.savedInputs.All(p => p != null) &&
                new HashSet<string>(r.savedInputs.Select(p => p.path)).SetEquals(TargetPaths()), "Pin exactly four already-generated Journey scenes and the JourneyContent asset.");
            Require(r.muzzleFlashPrefab != null && r.arcPresentationPrefab != null, "Explicit authored muzzle flash and arc presentation prefab pins required.");
            NamedPoseShape(r.weaponCameraPose, "weaponCameraPose"); NamedPoseShape(r.flashMuzzlePose, "flashMuzzlePose"); NamedPoseShape(r.arcModulePose, "arcModulePose");
            Require(r.sounds != null && r.sounds.Length == 7 && r.sounds.All(s => s != null && s.clip != null) &&
                new HashSet<string>(r.sounds.Select(s => s.role)).SetEquals(SoundRoles), "Seven exact playable audio roles required, including reload and arc.");
            Require(r.regions != null && r.regions.Length == 3 && r.regions.All(p => p != null) &&
                new HashSet<int>(r.regions.Select(p => p.region)).SetEquals(new[] { 1, 2, 3 }), "Three explicit regional placement tables required.");
            var ids = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in r.regions)
            {
                Require(p.guards != null && p.roadBeasts != null && p.waves != null, "Null enemy/wave arrays are not an explicit plan.");
                Require(p.guards.Length == (p.region == 1 ? 2 : 0) && p.roadBeasts.Length == (p.region == 1 ? 1 : 0) &&
                    p.waves.Length == (p.region == 1 ? 0 : 2), "Keep the authored first-station guard/road and two-wave powered encounter topology.");
                CheckRows(p.guards, "pouncer", ids); CheckRows(p.roadBeasts, "armored", ids);
                for (int i = 0; i < p.waves.Length; i++)
                {
                    Require(p.waves[i] != null && p.waves[i].enemies != null && p.waves[i].enemies.Length == (i == 0 ? 2 : 1), "Powered waves require two pouncers then one armored actor.");
                    CheckRows(p.waves[i].enemies, i == 0 ? "pouncer" : "armored", ids);
                }
            }
        }
        static void CheckRows(EnemyPlacement[] rows, string kind, HashSet<string> ids)
        {
            foreach (var row in rows)
                Require(row != null && Regex.IsMatch(row.id ?? "", "^[a-z0-9][a-z0-9/-]{2,79}$") && ids.Add(row.id) &&
                    row.kind == kind && Finite(row.position) && Finite(row.yaw), "Missing/duplicate enemy ID, wrong prefab kind or nonfinite spawn.");
        }
        static void FileCheck(FilePin pin, string prefix)
        {
            Require(pin != null && !string.IsNullOrWhiteSpace(pin.path) && pin.path.StartsWith(prefix, StringComparison.Ordinal) &&
                !Path.IsPathRooted(pin.path) && !pin.path.Contains("..") && !pin.path.Contains("\\") && Hash(pin.sha256, 64), "Explicit safe path and SHA256 required.");
            Require(JourneyDiagnosticScope.IsPinnedPathSafe(pin.path, out string reason), reason);
            Require(JourneyDiagnosticScope.HashFile(pin.path) == pin.sha256, "Input byte hash changed: " + pin.path);
        }
        static void AssetCheck(AssetPin pin)
        {
            FileCheck(pin, "Assets/DesertRV/");
            Require(Hash(pin.dependencyHash, 32) && Hash(pin.dependencySha256, 64) &&
                AssetDatabase.GetAssetDependencyHash(pin.path).ToString() == pin.dependencyHash &&
                JourneyContentChecks.DependencySha256(pin.path) == pin.dependencySha256, "Actual asset dependency hashes missing/stale: " + pin.path);
        }
        static T Load<T>(AssetPin pin) where T : Object
        {
            AssetCheck(pin); var asset = AssetDatabase.LoadAssetAtPath<T>(pin.path);
            Require(asset, "Wrong asset type: " + pin.path); return asset;
        }
        public static void ValidateStrictIdentity(JourneyCandidateArtImport.Contract contract)
        {
            JourneyCandidateArtImport.ValidateSourceContract(contract);
            Require(contract.mode == "STRICT_BINDING" && contract.scope == "FULL_CANDIDATE", "Discovery/partial sources cannot be scene candidates.");
        }
        static Resolved Resolve(Candidate input)
        {
            FileCheck(input.contract, "Assets/DesertRV/CandidateArtImports/");
            FileCheck(input.importReport, "JourneyEvidence/CandidateArt/");
            var contract = JsonUtility.FromJson<JourneyCandidateArtImport.Contract>(File.ReadAllText(input.contract.path));
            var report = JsonUtility.FromJson<JourneyCandidateArtImport.Report>(File.ReadAllText(input.importReport.path));
            ValidateStrictIdentity(contract);
            Require(contract.kind == input.kind, "Strict contract kind does not match selected input.");
            Require(report != null && report.mode == "STRICT_BINDING" && report.scope == "FULL_CANDIDATE" && report.kind == input.kind &&
                report.status == "candidate-structure-imported-unreviewed" && report.failures != null && report.failures.Count == 0 &&
                report.candidateOnly && !report.visualReviewed && !report.gameplayReviewed, "Successful native STRICT full import receipt required; receipt is not approval.");
            Require(report.contractSha256 == input.contract.sha256 && report.prefab == input.prefab.path &&
                report.dependencyHash == input.prefab.dependencyHash && report.dependencySha256 == input.prefab.dependencySha256 &&
                report.runUrl == contract.runUrl && report.sourceCommit == contract.sourceCommit &&
                report.artifactName == contract.artifactName && report.artifactSha256 == contract.artifactSha256,
                "STRICT receipt, contract, source identity and exact prefab digests disagree.");
            string folder = Path.GetDirectoryName(input.contract.path).Replace('\\', '/');
            Require(input.contract.path == folder + "/contract.json" && folder == "Assets/DesertRV/CandidateArtImports/" + contract.id &&
                input.prefab.path == folder + "/Candidate.prefab" && input.sourceModelPath == folder + "/Source/" + contract.modelFile,
                "Candidate source paths do not match the actual copied strict contract.");
            var prefab = Load<GameObject>(input.prefab);
            Require(PrefabUtility.IsPartOfPrefabAsset(prefab), "Persistent native prefab required.");
            var dependencies = AssetDatabase.GetDependencies(input.prefab.path, true);
            Require(report.dependencies != null && new HashSet<string>(report.dependencies).SetEquals(dependencies), "Dependency set changed since native import.");
            Require(contract.files != null && contract.clips != null && contract.clips.Length == (input.kind == "weapon" ? 3 : 7), "Complete source payload and clip contract required.");
            foreach (var file in contract.files)
                FileCheck(new FilePin { path = folder + "/Source/" + file.file, sha256 = file.sha256 }, folder + "/Source/");
            Require(dependencies.Contains(input.sourceModelPath), "Prefab has no actual model dependency.");
            var modelPaths = new HashSet<string>(contract.files.Where(f => f.file.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase)).Select(f => folder + "/Source/" + f.file));
            foreach (var mesh in Meshes(prefab)) Require(mesh && mesh.vertexCount > 0 && modelPaths.Contains(AssetDatabase.GetAssetPath(mesh)), "No primitive, missing or unpinned combat mesh is allowed.");
            Require(Meshes(prefab).Any() && prefab.GetComponentsInChildren<Renderer>(true).Any(r => r.enabled), "Real visible candidate geometry required.");
            CheckMaterials(prefab);
            var animators = prefab.GetComponentsInChildren<Animator>(true);
            Require(animators.Length == 1 && animators[0].runtimeAnimatorController is AnimatorController, "Exactly one real bound AnimatorController required.");
            var controller = (AnimatorController)animators[0].runtimeAnimatorController;
            var wanted = input.kind == "weapon" ? new[] { "Idle", "Fire", "Reload" } : JourneyContentChecks.EnemyStates;
            Require(controller.layers.Length == 1 && controller.layers[0].name == "Base Layer", "Expected native strict Base Layer controller.");
            var states = controller.layers[0].stateMachine.states.Select(s => s.state).ToArray();
            Require(states.Length == wanted.Length && new HashSet<string>(states.Select(s => s.name)).SetEquals(wanted), "Native strict state set changed.");
            foreach (var state in states)
            {
                var clip = state.motion as AnimationClip;
                Require(clip && clip.length > 0 && modelPaths.Contains(AssetDatabase.GetAssetPath(clip)) &&
                    AnimationUtility.GetCurveBindings(clip).Length > 0 && AnimationUtility.GetAnimationEvents(clip).Length == 0, "Missing real pose animation or unexpected animation events.");
            }
            if (input.kind != "weapon")
            {
                var actor = prefab.GetComponent<BeastActor>(); var collider = prefab.GetComponent<CapsuleCollider>();
                Require(actor && actor.armored == (input.kind == "armored") && actor.animator == animators[0] && collider && collider.enabled && !collider.isTrigger,
                    "Strict actor identity, Animator or root physical capsule missing.");
                Require(collider.direction == 1 && collider.radius >= .15f && collider.radius <= 1.5f && collider.height >= .4f && collider.height <= 4 &&
                    collider.height >= 2 * collider.radius && prefab.transform.localScale == Vector3.one, "Unverified physical collider dimensions/outer scale.");
                if (actor.armored)
                {
                    var weak = prefab.GetComponent<BeastWeakPointPresentation>();
                    Require(weak, "Actual armored weakpoint presentation missing.");
                    Require(weak.ValidateBindings(out var reason), reason);
                    var errors = new List<string>(); WeakPointContractChecks.Validate(weak, "Scene integration armored input", errors);
                    Require(errors.Count == 0, string.Join("; ", errors));
                }
            }
            else Require(prefab.GetComponentsInChildren<WeaponPresentation>(true).Length == 1 && prefab.GetComponent<WeaponPresentation>(), "Root strict weapon presenter required.");
            return new Resolved { input = input, contract = contract, report = report, prefab = prefab };
        }
        public static bool SourceAxisAligned(Transform muzzle) => muzzle && muzzle.name == "CandidateShotMuzzleAxis" && muzzle.parent &&
            muzzle.localPosition.sqrMagnitude < .0000000001f && Vector3.Dot(muzzle.forward.normalized, muzzle.parent.TransformDirection(Vector3.up).normalized) > .99999f;
        static IEnumerable<Mesh> Meshes(GameObject go) => go.GetComponentsInChildren<MeshFilter>(true).Select(f => f.sharedMesh)
            .Concat(go.GetComponentsInChildren<SkinnedMeshRenderer>(true).Select(r => r.sharedMesh));
        static void CheckMaterials(GameObject go)
        {
            foreach (var renderer in go.GetComponentsInChildren<Renderer>(true))
                Require(renderer.sharedMaterials.Length > 0 && renderer.sharedMaterials.All(m => m && m.shader && AssetDatabase.Contains(m)), "Persistent material/shader references missing on " + renderer.name);
        }
        static T[] All<T>(Scene scene) where T : Component => scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<T>(true)).ToArray();
        static T One<T>(Scene scene) where T : Component
        { var values = All<T>(scene); Require(values.Length == 1, "Exactly one " + typeof(T).Name + " required in " + scene.path); return values[0]; }
        static void Record(Object o) { if (PrefabUtility.IsPartOfPrefabInstance(o)) PrefabUtility.RecordPrefabInstancePropertyModifications(o); }
        static void SetPose(Transform t, Pose p) { t.localPosition = p.localPosition; t.localRotation = p.localRotation; t.localScale = p.localScale; Record(t); }
        static JourneyAssetReview Review(Resolved value) => new JourneyAssetReview {
            prefab = value.prefab, sourceModel = AssetDatabase.LoadAssetAtPath<GameObject>(value.input.sourceModelPath),
            dependencyHash = value.input.prefab.dependencyHash, reviewedDependencySha256 = value.input.prefab.dependencySha256,
            generationRunUrl = value.contract.runUrl, accepted = false, visualEvidence = "", motionEvidence = ""
        };
        static bool Approved(JourneyContentManifest m) => m.pouncer != null && m.pouncer.accepted || m.armored != null && m.armored.accepted || m.weapon != null && m.weapon.accepted ||
            !string.IsNullOrWhiteSpace(m.bootstrapEvidence) || !string.IsNullOrWhiteSpace(m.combatIntegrationEvidence) || m.environmentEvidence != null && m.environmentEvidence.Any(s => !string.IsNullOrWhiteSpace(s));
        static bool Empty(string value) => string.IsNullOrEmpty(value);
        static bool EmptyReview(JourneyAssetReview review) => review != null && !review.prefab && !review.sourceModel && !review.accepted &&
            Empty(review.dependencyHash) && Empty(review.reviewedDependencySha256) && Empty(review.generationRunUrl) && Empty(review.visualEvidence) && Empty(review.motionEvidence);
        public static bool ManifestIsUnbound(JourneyContentManifest m) => m && EmptyReview(m.pouncer) && EmptyReview(m.armored) && EmptyReview(m.weapon) &&
            !m.weaponPresentation && !m.arcPresentation && !m.armoredWeakpointPresentation && Empty(m.bootstrapDependencyHash) &&
            Empty(m.bootstrapEvidence) && Empty(m.combatIntegrationEvidence) && m.environmentDependencyHashes != null &&
            m.environmentDependencyHashes.Length == 3 && m.environmentDependencyHashes.All(Empty) && m.environmentEvidence != null &&
            m.environmentEvidence.Length == 3 && m.environmentEvidence.All(Empty);
        public static string[] ExpectedMissingApprovals() => new[] {
            "Pouncer: visual and motion acceptance missing.", "Armored: visual and motion acceptance missing.", "Weapon viewmodel: visual and motion acceptance missing.",
            "Missing reviewed weapon/arc/weakpoint in-game action evidence."
        }.Concat(JourneySceneAuthoring.RegionPaths.Select(p => p + ": 地区场景或战斗资产尚未验收。"))
            .Concat(new[] { JourneySceneAuthoring.BootstrapPath }.Concat(JourneySceneAuthoring.RegionPaths).Select(p => p + ": saved scene review/evidence hash missing or stale.")).ToArray();
        public static void RequireOnlyMissingApprovals(string[] failures)
        {
            var expected = ExpectedMissingApprovals();
            Require(failures != null && failures.Length == expected.Length && new HashSet<string>(failures, StringComparer.Ordinal).SetEquals(expected),
                "Production inspection must fail only for the exact missing approvals; a structural error, duplicate, changed message or missing gate is not accepted. Actual: " + string.Join(" | ", failures ?? Array.Empty<string>()));
        }
        public static bool CapsuleOverlapsVolume(CapsuleCollider capsule, Collider volume)
        {
            Require(capsule && capsule.enabled && !capsule.isTrigger, "Active physical capsule required for volume exclusion.");
            if (!volume) return false;
            Require(volume.enabled && volume.isTrigger && volume.gameObject.activeInHierarchy, "Exit/safety volume must be an active trigger.");
            return Physics.ComputePenetration(capsule, capsule.transform.position, capsule.transform.rotation,
                volume, volume.transform.position, volume.transform.rotation, out _, out float depth) && depth > 0;
        }
        static void WireBootstrap(Scene boot, Request request, Dictionary<string, Resolved> assets, GameObject flashPrefab, GameObject arcPrefab, Dictionary<string, AudioClip> audio)
        {
            var director = One<JourneyDirector>(boot); var motor = One<JourneyMotor>(boot); var actions = One<JourneyActions>(boot);
            Require(director.motor == motor && director.actions == actions && director.journey == motor.journey && actions.motor == motor &&
                actions.journey == director.journey && motor.vehicle && motor.view && motor.arc && actions.cabinWorkbench && actions.workbenchSurface &&
                actions.cabinWorkbench.IsChildOf(motor.vehicle) && actions.workbenchSurface.transform.IsChildOf(motor.vehicle), "Persistent RV/camera/cabin/workbench ownership is incomplete; cannot infer replacements.");
            Require(All<WeaponPresentation>(boot).Length == 0 && All<ArcPresentation>(boot).Length == 0 && !actions.shotMuzzle && !actions.arcOrigin,
                "Refusing to overwrite existing weapon/arc wiring. Start from hash-pinned unbound generated candidate scenes.");
            var weapon = (GameObject)PrefabUtility.InstantiatePrefab(assets["weapon"].prefab, motor.view.transform); SetPose(weapon.transform, request.weaponCameraPose);
            var presenter = weapon.GetComponent<WeaponPresentation>(); presenter.enabled = false;
            Require(presenter.animator && SourceAxisAligned(presenter.muzzle) && presenter.muzzle.IsChildOf(presenter.animator.transform), "Strict source-axis adapter missing/misaligned; raw Muzzle.forward is not the source +Y barrel axis.");
            var flash = (GameObject)PrefabUtility.InstantiatePrefab(flashPrefab, presenter.muzzle); SetPose(flash.transform, request.flashMuzzlePose);
            presenter.muzzleFlash = flash.GetComponent<ParticleSystem>(); presenter.actions = actions; actions.shotMuzzle = presenter.muzzle;
            actions.shotSound = audio["shot"]; actions.hitSound = audio["hit"]; actions.reloadSound = audio["reload"];
            actions.pickupSound = audio["pickup"]; actions.upgradeSound = audio["upgrade"]; actions.windSound = audio["wind"];
            Require(presenter.ValidateBindings(out string weaponReason), "Weapon scene binding rejected: " + weaponReason); presenter.enabled = true; Record(presenter);
            var arc = (GameObject)PrefabUtility.InstantiatePrefab(arcPrefab, motor.arc.transform); SetPose(arc.transform, request.arcModulePose);
            var arcPresenter = arc.GetComponent<ArcPresentation>(); arcPresenter.enabled = false;
            arcPresenter.actions = actions; arcPresenter.arcModule = motor.arc.transform; arcPresenter.arcSound = audio["arc"]; actions.arcOrigin = arcPresenter.source;
            Physics.SyncTransforms();
            LogArcBinding(arcPresenter, "wired-module-inactive");
            Require(arcPresenter.ValidateBindings(out string arcReason), "Arc scene binding rejected: " + arcReason); arcPresenter.enabled = true; Record(arcPresenter);
            // Arc starts inactive with the retained upgrade. Test its physical source with the module enabled, then restore exactly.
            bool wasActive = motor.arc.activeSelf;
            try { motor.arc.SetActive(true); Physics.SyncTransforms(); LogArcBinding(arcPresenter, "wired-module-active"); Require(actions.ArcSourceReady, "Explicit arc source lies inside retained RV/module collider."); }
            finally { motor.arc.SetActive(wasActive); }
            Require(All<BeastActor>(boot).Length == 0, "Persistent bootstrap cannot contain regional enemies.");
        }
        public const string SpawnGroundingPath = "JourneyEvidence/JourneyPreparation/spawn-grounding.json";
        [Serializable] public sealed class SpawnGroundingRow
        {
            public string id, kind, scene, floor;
            public int region, layer;
            public Vector3 declaredPosition, resolvedPosition, hitPoint, hitNormal;
            public float yaw;
        }
        [Serializable] public sealed class SpawnGroundingReport
        {
            public int schema = 1;
            public string status = "ACTUAL_NATIVE_ROOT_GROUNDING_UNREVIEWED", sourceCommit, source, selectionSha256, readyInputSha256;
            public bool approved;
            public SpawnGroundingRow[] rows;
        }
        static SpawnGroundingRow ResolveRootGrounding(Scene scene, Collider[] floors, EnemyPlacement row, int region)
        {
            Require(scene.IsValid() && scene.isLoaded && row != null && Finite(row.position) && Finite(row.yaw) && row.position.y == 0,
                "Root grounding requires a finite declared zero-height anchor in a loaded region.");
            Require(floors != null && floors.Length > 0 && floors.All(c => c && c.gameObject.scene == scene && c.enabled && !c.isTrigger && c.gameObject.activeInHierarchy && c.gameObject.layer == 0 &&
                c is BoxCollider && (c.name == "Route foundation" || c.name == "Road surface") && Finite(c.bounds.min) && Finite(c.bounds.max)), "Missing/foreign/disabled/trigger/nonfloor grounding collider.");
            float top = floors.Max(c => c.bounds.max.y) + .5f, bottom = floors.Min(c => c.bounds.min.y) - .5f;
            var ray = new Ray(new Vector3(row.position.x, top, row.position.z), Vector3.down);
            var hits = new List<RaycastHit>();
            foreach (var floor in floors) if (floor.Raycast(ray, out var hit, top - bottom)) hits.Add(hit);
            var legal = hits.Where(h => h.collider && h.collider.gameObject.scene == scene && Finite(h.point) && Finite(h.normal) && h.normal.y >= .9f).OrderByDescending(h => h.point.y).ToArray();
            Require(legal.Length > 0, "Declared root XZ has no actual physical floor: " + row.id);
            var selected = legal[0];
            var resolved = new Vector3(row.position.x, selected.point.y, row.position.z);
            Require(Mathf.Abs(selected.point.x - row.position.x) < .0001f && Mathf.Abs(selected.point.z - row.position.z) < .0001f, "Floor ray changed declared XZ.");
            return new SpawnGroundingRow { id = row.id, kind = row.kind, region = region, scene = scene.path, floor = selected.collider.name, layer = selected.collider.gameObject.layer,
                declaredPosition = row.position, resolvedPosition = resolved, hitPoint = selected.point, hitNormal = selected.normal, yaw = row.yaw };
        }
        static void RunReadOnlySceneQuery(Action query, Action restore, Action verify)
        {
            var errors = new List<Exception>();
            try { query(); } catch (Exception error) { errors.Add(error); }
            try { restore(); } catch (Exception error) { errors.Add(error); }
            try { verify(); } catch (Exception error) { errors.Add(error); }
            if (errors.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(errors[0]).Throw();
            if (errors.Count > 1) throw new AggregateException("Root grounding failed, including scene restoration/protected source verification.", errors);
        }
        public static SpawnGroundingReport ResolveSpawnRootHeights(Request request, string source, string selectionSha256, string readyInputSha256)
        {
            Require(source == "scene-physical-floor" && Hash(selectionSha256, 64) && Hash(readyInputSha256, 64) && request != null && Hash(request.sourceCommit, 40), "Pinned original root-grounding input required.");
            var setup = EditorSceneManager.GetSceneManagerSetup();
            Require(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "Root grounding must preserve open scene edits.");
            var protectedFiles = SnapshotProtected(Array.Empty<string>()); var rows = new List<SpawnGroundingRow>();
            SpawnGroundingReport report = null;
            RunReadOnlySceneQuery(() => {
                Require(request.regions != null && request.regions.Select(r => r.region).OrderBy(i => i).SequenceEqual(new[] { 1, 2, 3 }), "Root grounding requires exactly the three real regions.");
                foreach (var plan in request.regions.OrderBy(p => p.region))
                {
                    var scene = EditorSceneManager.OpenScene(JourneySceneAuthoring.RegionPaths[plan.region - 1], OpenSceneMode.Single);
                    Require(!EditorSceneManager.IsPreviewScene(scene) && scene.GetPhysicsScene() == Physics.defaultPhysicsScene, "Root grounding requires the actual ordinary region physics scene.");
                    var binding = One<RegionBinding>(scene);
                    Require(binding.region == plan.region && !binding.environmentVerified && !binding.combatAssetsVerified, "Root grounding region/approval mismatch.");
                    var floors = new[] { binding.transform.Find("Route foundation"), binding.transform.Find("Road surface") };
                    Require(floors.All(t => t && t.IsChildOf(binding.transform)), "Authored real floor bindings absent.");
                    var colliders = floors.Select(t => t.GetComponent<Collider>()).ToArray(); Physics.SyncTransforms();
                    foreach (var row in plan.guards.Concat(plan.roadBeasts).Concat(plan.waves.SelectMany(w => w.enemies)))
                    {
                        var result = ResolveRootGrounding(scene, colliders, row, plan.region); rows.Add(result); row.position = result.resolvedPosition;
                        Debug.Log("JOURNEY_SPAWN_ROOT_RESOLVED " + JsonUtility.ToJson(result));
                    }
                }
                Require(rows.Count > 0 && rows.Select(r => r.id).Distinct().Count() == rows.Count, "Duplicate/empty grounded actor inventory.");
                report = new SpawnGroundingReport { sourceCommit = request.sourceCommit, source = source, selectionSha256 = selectionSha256, readyInputSha256 = readyInputSha256, rows = rows.ToArray() };
            }, () => JourneySceneAuthoring.RestoreSceneSetup(setup), () => VerifyProtected(protectedFiles, Array.Empty<string>()));
            return report;
        }
        static BeastActor[] Spawn(EnemyPlacement[] rows, RegionBinding binding, Dictionary<string, Resolved> assets)
        {
            return rows.Select(row => {
                var go = (GameObject)PrefabUtility.InstantiatePrefab(assets[row.kind].prefab, binding.transform);
                go.name = row.id; go.transform.SetPositionAndRotation(row.position, Quaternion.Euler(0, row.yaw, 0));
                go.SetActive(true); Record(go); Record(go.transform); return go.GetComponent<BeastActor>();
            }).ToArray();
        }
        static void WireRegion(Scene scene, Scene boot, RegionPlan plan, Dictionary<string, Resolved> assets)
        {
            var binding = One<RegionBinding>(scene); var motor = One<JourneyMotor>(boot);
            Require(binding.region == plan.region && !binding.combatAssetsVerified && !binding.environmentVerified, "Only matching unapproved region candidates may be wired.");
            Require(All<BeastActor>(scene).Length == 0 && !binding.AllEnemies().Any(), "Refusing to replace existing regional actors.");
            binding.guards = Spawn(plan.guards, binding, assets); binding.roadBeasts = Spawn(plan.roadBeasts, binding, assets);
            binding.waves = plan.waves.Select(w => new RegionWave { enemies = Spawn(w.enemies, binding, assets) }).ToArray();
            Require(binding.ValidateStructure(out string reason), reason);
            Require(!binding.Validate(out _), "Production approval gate unexpectedly opened.");
            Require(binding.regionOffset == JourneySceneAuthoring.RegionOffsets[plan.region - 1] && binding.progressDirection == Vector3.forward &&
                (plan.region == 1 || binding.chargeSeconds == (plan.region == 2 ? 28 : 36)), "Existing region progress/charging rules changed.");
            motor.vehicle.SetPositionAndRotation(binding.spawn.position, binding.spawn.rotation); Physics.SyncTransforms();
            var solids = All<Collider>(scene).Concat(All<Collider>(boot)).Where(c => c.enabled && !c.isTrigger && c.gameObject.activeInHierarchy).ToArray();
            foreach (var actor in binding.AllEnemies())
            {
                var cap = actor.GetComponent<CapsuleCollider>(); var bounds = cap.bounds;
                Require(Vector3.Distance(actor.transform.position, binding.spawn.position) >= 4 &&
                    !CapsuleOverlapsVolume(cap, binding.exitVolume) && !CapsuleOverlapsVolume(cap, binding.safeZone), "Spawn blocks arrival/exit/safe zone: " + actor.name);
                foreach (var other in solids)
                {
                    if (other.transform.IsChildOf(actor.transform)) continue;
                    Require(!Physics.ComputePenetration(cap, cap.transform.position, cap.transform.rotation, other, other.transform.position, other.transform.rotation, out _, out float depth) || depth <= .015f,
                        "Physical spawn penetrates " + other.name + ": " + actor.name);
                }
                var hits = Physics.RaycastAll(new Vector3(bounds.center.x, bounds.min.y + .25f, bounds.center.z), Vector3.down, .5f, ~0, QueryTriggerInteraction.Ignore);
                Debug.Log("JOURNEY_SPAWN_FLOOR actor=" + actor.name + "; root=" + actor.transform.position.ToString("R") + "; capsuleMin=" + bounds.min.ToString("R") +
                    "; scene=" + scene.path + "; defaultPhysics=" + (scene.GetPhysicsScene() == Physics.defaultPhysicsScene) + "; hits=" + string.Join(" | ", hits.OrderBy(h => h.distance).Take(16).Select(h =>
                        h.collider.name + ",scene=" + h.collider.gameObject.scene.path + ",layer=" + h.collider.gameObject.layer + ",enabled=" + h.collider.enabled + ",trigger=" + h.collider.isTrigger +
                        ",point=" + h.point.ToString("R") + ",normal=" + h.normal.ToString("R") + ",gap=" + Mathf.Abs(h.point.y - bounds.min.y).ToString("R", System.Globalization.CultureInfo.InvariantCulture))));
                Require(hits.Any(h => h.collider.gameObject.scene == scene && !h.collider.GetComponentInParent<BeastActor>() &&
                    h.normal.y >= .9f && Mathf.Abs(h.point.y - bounds.min.y) <= .12f), "Spawn lacks nearby physical floor: " + actor.name);
            }
            // The Director is the owner of activation and generation binding. Never persist cross-scene journey/player references.
            foreach (var actor in binding.AllEnemies()) Require(!actor.journey && !actor.player, "Imported actor carries a forbidden persistent scene/session reference.");
            foreach (var actor in binding.roadBeasts) { actor.gameObject.SetActive(false); Record(actor.gameObject); }
            foreach (var wave in binding.waves) foreach (var actor in wave.enemies) { actor.gameObject.SetActive(false); Record(actor.gameObject); }
        }
        static void LogArcBinding(ArcPresentation arc, string stage)
        {
            var a = arc.actions; var m = a ? a.motor : null;
            bool ready = a && a.CheckArcSource(out _, out _, out _);
            Collider blocker = null; float distance = float.NaN; string query = "missing-actions";
            if (a) a.CheckArcSource(out blocker, out distance, out query);
            string path = blocker && m && m.vehicle ? AnimationUtility.CalculateTransformPath(blocker.transform, m.vehicle) : "none";
            var flags = new[] { (bool)a, (bool)arc.arcModule, (bool)arc.source, a && a.arcOrigin == arc.source,
                arc.source && arc.arcModule && arc.source.IsChildOf(arc.arcModule), (bool)m, m && m.arc,
                m && m.arc && m.arc.transform == arc.arcModule, (bool)arc.audioSource,
                arc.audioSource && arc.arcModule && arc.audioSource.transform.IsChildOf(arc.arcModule), (bool)arc.arcSound, ready };
            Debug.Log("JOURNEY_ARC_BINDING stage=" + stage + "; predicates=" + string.Join(",", flags.Select(value => value ? "1" : "0")) +
                "; source=" + (arc.source ? arc.source.position.ToString("R") : "missing") + "; moduleActive=" + (arc.arcModule && arc.arcModule.gameObject.activeInHierarchy) +
                "; blocker=" + path + "; type=" + (blocker ? blocker.GetType().Name : "none") + "; convex=" + (blocker is MeshCollider mc && mc.convex) +
                "; query=" + query + "; squaredDistance=" + distance.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            if (a && m && m.vehicle && arc.source)
            {
                var solids = m.vehicle.GetComponentsInChildren<Collider>(true).Where(c => c.enabled && !c.isTrigger && c.gameObject.activeInHierarchy).ToArray();
                var nearest = solids.OrderBy(c => c.bounds.SqrDistance(arc.source.position)).FirstOrDefault();
                if (nearest) Debug.Log("JOURNEY_ARC_BOUNDS stage=" + stage + "; count=" + solids.Length + "; collider=" + AnimationUtility.CalculateTransformPath(nearest.transform, m.vehicle) +
                    "; min=" + nearest.bounds.min.ToString("R") + "; max=" + nearest.bounds.max.ToString("R") + "; lowerBoundSquared=" + nearest.bounds.SqrDistance(arc.source.position).ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            }
        }
        static void VerifySavedPose(Transform transform, Pose pose, string role)
        {
            NamedPoseShape(pose, role);
            Require(transform && Vector3.Distance(transform.localPosition, pose.localPosition) < .0001f && Quaternion.Angle(transform.localRotation, pose.localRotation) < .001f &&
                Vector3.Distance(transform.localScale, pose.localScale) < .00001f, "Saved selected pose changed: " + role);
        }
        static void VerifySavedBindings(Request request, Dictionary<string, Resolved> assets)
        {
            var boot = EditorSceneManager.OpenScene(JourneySceneAuthoring.BootstrapPath, OpenSceneMode.Single);
            var weapon = One<WeaponPresentation>(boot); var arc = One<ArcPresentation>(boot);
            Require(weapon.enabled && SourceAxisAligned(weapon.muzzle), "Saved weapon presenter/axis override was lost.");
            Require(weapon.ValidateBindings(out string weaponReason), "Saved weapon: " + weaponReason);
            LogArcBinding(arc, "saved-bootstrap");
            Require(arc.enabled && arc.ValidateBindings(out string arcReason), "Saved arc binding invalid.");
            Require(PrefabUtility.GetCorrespondingObjectFromSource(weapon.gameObject) == assets["weapon"].prefab, "Saved weapon lost strict prefab identity.");
            Require(PrefabUtility.GetCorrespondingObjectFromSource(arc.gameObject) == AssetDatabase.LoadAssetAtPath<GameObject>(request.arcPresentationPrefab.path) &&
                weapon.muzzleFlash && PrefabUtility.GetCorrespondingObjectFromSource(weapon.muzzleFlash.gameObject) == AssetDatabase.LoadAssetAtPath<GameObject>(request.muzzleFlashPrefab.path), "Saved authored FX prefab identity changed.");
            VerifySavedPose(weapon.transform, request.weaponCameraPose, "weaponCameraPose");
            VerifySavedPose(weapon.muzzleFlash.transform, request.flashMuzzlePose, "flashMuzzlePose");
            VerifySavedPose(arc.transform, request.arcModulePose, "arcModulePose");
            var actions = One<JourneyActions>(boot);
            Require(JourneySceneAuthoring.ValidateArcMeshGeometry(actions, out string geometryReason), geometryReason);
            var actualAudio = new[] { actions.shotSound, actions.hitSound, actions.reloadSound, actions.pickupSound, actions.upgradeSound, actions.windSound, arc.arcSound };
            for (int i = 0; i < SoundRoles.Length; i++)
            {
                var expectedAudio = request.sounds.Single(sound => sound.role == SoundRoles[i]).clip.path;
                Require(actualAudio[i] && actualAudio[i].length > 0 && AssetDatabase.GetAssetPath(actualAudio[i]) == expectedAudio, "Saved real audio reference changed: " + SoundRoles[i]);
            }
            CheckMaterials(weapon.gameObject); CheckMaterials(arc.gameObject);
            foreach (var plan in request.regions)
            {
                var scene = EditorSceneManager.OpenScene(JourneySceneAuthoring.RegionPaths[plan.region - 1], OpenSceneMode.Single);
                var binding = One<RegionBinding>(scene);
                Require(!binding.combatAssetsVerified && !binding.environmentVerified && binding.ValidateStructure(out string reason), "Saved region structure/approval changed.");
                var rows = plan.guards.Concat(plan.roadBeasts).Concat(plan.waves.SelectMany(w => w.enemies)).ToDictionary(row => row.id);
                Require(All<BeastActor>(scene).Length == rows.Count && binding.AllEnemies().Count() == rows.Count, "Saved enemy count changed.");
                foreach (var actor in binding.AllEnemies())
                {
                    Require(rows.TryGetValue(actor.name, out EnemyPlacement row), "Saved actor ID changed.");
                    Require(PrefabUtility.GetCorrespondingObjectFromSource(actor.gameObject) == assets[row.kind].prefab &&
                        Vector3.Distance(actor.transform.position, row.position) < .0001f &&
                        Quaternion.Angle(actor.transform.rotation, Quaternion.Euler(0, row.yaw, 0)) < .001f && !actor.journey && !actor.player,
                        "Saved actor source/pose/ownership changed: " + actor.name);
                    var collider = actor.GetComponent<CapsuleCollider>();
                    Require(collider && collider.enabled && !collider.isTrigger && new HashSet<Mesh>(Meshes(actor.gameObject)).SetEquals(Meshes(assets[row.kind].prefab)), "Saved actor lost physical collider or original imported geometry.");
                    CheckMaterials(actor.gameObject);
                    Require(actor.animator && actor.animator.runtimeAnimatorController == assets[row.kind].prefab.GetComponent<BeastActor>().animator.runtimeAnimatorController,
                        "Saved enemy lost its native Animator controller.");
                }
                Require(binding.guards.All(a => a.gameObject.activeSelf) && binding.roadBeasts.All(a => !a.gameObject.activeSelf) && binding.waves.All(w => w.enemies.All(a => !a.gameObject.activeSelf)),
                    "Saved actor activation disagrees with Director ownership.");
            }
        }
        static Dictionary<string, string> SnapshotProtected(IEnumerable<string> allowedPaths = null)
        {
            var allowed = new HashSet<string>(allowedPaths ?? TargetPaths().SelectMany(p => new[] { p, p + ".meta" }));
            var result = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var folder in new[] { "Assets", "ProjectSettings", "Packages" })
                if (Directory.Exists(folder)) foreach (var file in Directory.GetFiles(folder, "*", SearchOption.AllDirectories))
                {
                    string path = file.Replace('\\', '/');
                    if (!allowed.Contains(path)) { Require(JourneyDiagnosticScope.IsPinnedPathSafe(path, out string reason), reason); result.Add(path, JourneyDiagnosticScope.HashFile(path)); }
                }
            return result;
        }
        [Serializable] sealed class PublicSourcePaths { public FilePin[] files, restoredFiles; }
        [Serializable] sealed class PublicStrictPaths
        {
            public string status, importCommit, importRunUrl, kind;
            public bool approved;
            public FilePin[] files;
        }
        static HashSet<string> PublicProtectedPaths(Dictionary<string, string> before)
        {
            var result = new HashSet<string>(StringComparer.Ordinal);
            void Accept(string path, string sha) { if (before.TryGetValue(path, out string actual) && Hash(sha, 64) && actual == sha) result.Add(path); }
            try
            {
                var source = JsonUtility.FromJson<PublicSourcePaths>(File.ReadAllText("../SOURCE-STATE.json"));
                const string prefix = "tasks/desert-rv/unity/";
                foreach (var pin in (source.files ?? Array.Empty<FilePin>()).Concat(source.restoredFiles ?? Array.Empty<FilePin>()))
                    if (pin.path != null && pin.path.StartsWith(prefix, StringComparison.Ordinal)) Accept(pin.path.Substring(prefix.Length), pin.sha256);
                const string readyPath = "JourneyEvidence/JourneyPreparation/ready-input.json";
                string readySha = File.ReadAllText("JourneyEvidence/JourneyPreparation/ready-input.sha256").Trim();
                if (Hash(readySha, 64) && JourneyDiagnosticScope.HashFile(readyPath) == readySha)
                {
                    var ready = JsonUtility.FromJson<JourneyCandidatePreparation.ReadyInput>(File.ReadAllText(readyPath));
                    foreach (var pin in ready.validatedExportReceipts ?? Array.Empty<FilePin>())
                    {
                        if (!Regex.IsMatch(pin.path ?? "", "^tasks/desert-rv/journey-preparation-export/(armored|pouncer|weapon)/receipt\\.json$")) continue;
                        string file = Path.Combine("../../..", pin.path);
                        if (!Hash(pin.sha256, 64) || JourneyDiagnosticScope.HashFile(file) != pin.sha256) continue;
                        var receipt = JsonUtility.FromJson<PublicStrictPaths>(File.ReadAllText(file));
                        if (receipt.approved || receipt.status != "STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED" || receipt.importCommit != ready.sourceCommit ||
                            receipt.importRunUrl != "https://github.com/yangerstar1/task-workbench/actions/runs/" + Environment.GetEnvironmentVariable("GITHUB_RUN_ID")) continue;
                        foreach (var row in receipt.files ?? Array.Empty<FilePin>())
                            if (row.path == "CandidateArtImports.meta" || row.path != null && row.path.StartsWith("CandidateArtImports/", StringComparison.Ordinal)) Accept("Assets/DesertRV/" + row.path, row.sha256);
                    }
                }
                var fx = JsonUtility.FromJson<FxResult>(File.ReadAllText("JourneyEvidence/journey-candidate-fx.json"));
                if (fx.status == "ORIGINAL_NATIVE_FX_AUTHORED_UNCALIBRATED" && fx.protectedSourcesUnchanged)
                    foreach (var pin in fx.outputs ?? Array.Empty<OutputFile>()) { Accept(pin.path, pin.sha256); if (before.ContainsKey(pin.path + ".meta")) result.Add(pin.path + ".meta"); }
                foreach (string path in before.Keys)
                    if (Regex.IsMatch(path, "^Assets/DesertRV/Scenes/Journey/(Layout-[0-9A-F]{6}\\.mat|Region-[123]-Sky\\.mat)(\\.meta)?$") ||
                        path == JourneySceneAuthoring.Folder + ".meta" || path == JourneySceneAuthoring.Folder + "/CandidateFx.meta" ||
                        Regex.IsMatch(path, "^Assets/DesertRV/Scenes/Journey/CandidateFx/[a-z0-9-]+\\.meta$")) result.Add(path);
            }
            catch (Exception) { /* Diagnostics fail closed: unknown paths remain hashes, never raw names. */ }
            return result;
        }
        static string[] ProtectedDelta(Dictionary<string, string> before, Dictionary<string, string> after)
        {
            var known = PublicProtectedPaths(before);
            string Label(string path)
            {
                if (known.Contains(path)) return path;
                using (var hash = System.Security.Cryptography.SHA256.Create()) return "unknown-path-sha256=" + BitConverter.ToString(hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes(path))).Replace("-", "").ToLowerInvariant();
            }
            return before.Keys.Concat(after.Keys).Distinct().OrderBy(p => p, StringComparer.Ordinal).Where(p => !before.TryGetValue(p, out string b) || !after.TryGetValue(p, out string a) || a != b)
                .Select(p => (before.ContainsKey(p) ? after.ContainsKey(p) ? "changed" : "removed" : "added") + ":" + Label(p) + ":before=" + (before.TryGetValue(p, out string b) ? b : "absent") + ":after=" + (after.TryGetValue(p, out string a) ? a : "absent")).ToArray();
        }
        static void LogProtectedStage(string stage, Dictionary<string, string> before)
        {
            var delta = ProtectedDelta(before, SnapshotProtected());
            Debug.Log("JOURNEY_PROTECTED_STAGE stage=" + stage + "; count=" + delta.Length + "; delta=" + string.Join(" | ", delta.Take(32)));
        }
        static void VerifyProtected(Dictionary<string, string> before, IEnumerable<string> allowedPaths = null)
        {
            var after = SnapshotProtected(allowedPaths);
            var delta = ProtectedDelta(before, after);
            Require(delta.Length == 0, "Protected files changed outside exactly four Journey scenes and JourneyContent asset. " + string.Join(" | ", delta.Take(32)) + "; total=" + delta.Length);

        }
        static AssetPin CompleteSelectedAsset(AssetPin selected)
        {
            Require(selected != null && !string.IsNullOrWhiteSpace(selected.path) && selected.path.StartsWith("Assets/DesertRV/", StringComparison.Ordinal) &&
                !selected.path.Contains("..") && !selected.path.Contains("\\") && !Path.IsPathRooted(selected.path), "Select an existing exact asset path; no discovery or fallback is performed.");
            Require(JourneyDiagnosticScope.IsPinnedPathSafe(selected.path, out string reason), reason);
            var actual = PinAsset(selected.path);
            Require((string.IsNullOrEmpty(selected.sha256) || selected.sha256 == actual.sha256) &&
                (string.IsNullOrEmpty(selected.dependencyHash) || selected.dependencyHash == actual.dependencyHash) &&
                (string.IsNullOrEmpty(selected.dependencySha256) || selected.dependencySha256 == actual.dependencySha256), "Supplied asset pin is stale; never overwrite an asserted hash.");
            AssetCheck(actual); return actual;
        }
        static void WriteFreshInput(string path, object input)
        {
            Require(!string.IsNullOrWhiteSpace(path) && path.StartsWith("JourneyEvidence/", StringComparison.Ordinal) && !path.Contains("..") &&
                !path.Contains("\\") && !Path.IsPathRooted(path) && !File.Exists(path), "Fresh explicit project-local input output required.");
            Require(JourneyDiagnosticScope.IsPinnedPathSafe(Path.GetDirectoryName(path), out string reason), reason);
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(input, true));
        }
        // Freeze explicit selected paths into a complete immutable hash request using actual Unity dependency data.
        // A missing path or a missing report hash fails; successful artifact names are never inferred.
        public static void FreezeSelectedInputsFromEnvironment()
        {
            Require(!Application.isPlaying && !BuildPipeline.isBuildingPlayer, "Freeze inputs in EditMode only.");
            var pin = new FilePin { path = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_ASSET_SELECTION"), sha256 = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_ASSET_SELECTION_SHA256") };
            FileCheck(pin, "JourneyEvidence/"); var r = JsonUtility.FromJson<Request>(File.ReadAllText(pin.path));
            Require(r != null, "Missing selected input JSON.");
            if (string.IsNullOrEmpty(r.sourceCommit)) r.sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA");
            ValidateRequestShape(r, Environment.GetEnvironmentVariable("GITHUB_SHA"));
            foreach (var c in r.candidates)
            {
                FileCheck(c.importReport, "JourneyEvidence/CandidateArt/");
                c.prefab = CompleteSelectedAsset(c.prefab); FileCheck(c.contract, "Assets/DesertRV/CandidateArtImports/");
                Resolve(c); // complete, unchanged successful FULL STRICT report must already exist.
            }
            r.savedInputs = r.savedInputs.Select(CompleteSelectedAsset).ToArray();
            r.muzzleFlashPrefab = CompleteSelectedAsset(r.muzzleFlashPrefab); r.arcPresentationPrefab = CompleteSelectedAsset(r.arcPresentationPrefab);
            foreach (var sound in r.sounds) sound.clip = CompleteSelectedAsset(sound.clip);
            FileCheck(pin, "JourneyEvidence/"); WriteFreshInput(Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_ASSET_INPUT"), r);
        }
        [Serializable] public sealed class ScenePoseProposal
        {
            public string status = "GEOMETRY_DERIVED_INITIAL_POSES_UNCALIBRATED";
            public string sourceCommit;
            public bool gameplayCameraReviewed = false, reticleReviewed = false;
            public AssetPin bootstrap;
            public Pose weaponCameraPose, arcModulePose;
            public Vector3 arcModuleBoundsCenter, arcModuleBoundsSize, proposedWorldArcOrigin;
            public float arcClearanceMeters = .08f, requiredWalkingVerticalFov = 66;
        }
        // A native geometry read, not calibration or permission to change the gameplay projection.
        public static void ProposeScenePoses()
        {
            Require(!Application.isPlaying && !BuildPipeline.isBuildingPlayer, "Pose proposal is EditMode only.");
            var setup = EditorSceneManager.GetSceneManagerSetup();
            Require(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "Save/discard dirty scenes first.");
            var protectedFiles = SnapshotProtected(Array.Empty<string>());
            try
            {
                var boot = EditorSceneManager.OpenScene(JourneySceneAuthoring.BootstrapPath, OpenSceneMode.Single);
                var motor = One<JourneyMotor>(boot); Require(motor.arc && motor.vehicle, "Retained arc module/RV required.");
                var renderers = motor.arc.GetComponentsInChildren<Renderer>(true).Where(r => r is MeshRenderer || r is SkinnedMeshRenderer).ToArray();
                Require(renderers.Length > 0, "Arc module has no actual authored bounds.");
                var bounds = renderers[0].bounds; foreach (var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
                var origin = new Vector3(bounds.center.x, bounds.max.y + .08f, bounds.center.z);
                Require(Finite(origin) && bounds.size.sqrMagnitude > .001f, "Arc module bounds are not usable.");
                // R10 source→asset is (-x,z,-y), source→camera is (x,z,y). Quaternion is A*R_BlenderXYZ*C^T.
                // These exact numeric values are a source-supported initial pose, not a 66-degree gameplay framing result.
                var result = new ScenePoseProposal {
                    sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA"), bootstrap = PinAsset(JourneySceneAuthoring.BootstrapPath),
                    weaponCameraPose = new Pose { localPosition = new Vector3(.749840021f, -.446830004f, 2.446929932f),
                        localRotation = new Quaternion(-.267574460f, .863942266f, -.044380691f, .424308878f), localScale = Vector3.one },
                    arcModulePose = new Pose { localPosition = motor.arc.transform.InverseTransformPoint(origin), localRotation = Quaternion.identity, localScale = Vector3.one },
                    arcModuleBoundsCenter = bounds.center, arcModuleBoundsSize = bounds.size, proposedWorldArcOrigin = origin
                };
                PoseShape(result.weaponCameraPose); PoseShape(result.arcModulePose);
                Directory.CreateDirectory("JourneyEvidence"); File.WriteAllText("JourneyEvidence/journey-candidate-poses.json", JsonUtility.ToJson(result, true));
            }
            finally { try { JourneySceneAuthoring.RestoreSceneSetup(setup); } finally { VerifyProtected(protectedFiles, Array.Empty<string>()); } }
        }
        internal static void ConfirmProtectedSources(Result result, Action verify)
        {
            result.protectedSourcesUnchanged = false;
            verify();
            result.protectedSourcesUnchanged = true;
        }
        internal static void RunCandidateTransaction(Action stage, Action restoreSetup, Action saveReceipt, Action rollback)
        {
            try { stage(); restoreSetup(); saveReceipt(); }
            catch (Exception initial)
            {
                var errors = new List<Exception> { initial };
                try { rollback(); } catch (Exception error) { errors.Add(error); }
                finally { try { restoreSetup(); } catch (Exception error) { errors.Add(error); } }
                if (errors.Count > 1) throw new AggregateException("Candidate transaction failed, including recovery.", errors);
                throw;
            }
        }
        static void RestoreCandidateFiles(Dictionary<string, byte[]> original)
        {
            if (original.Count == 0) return;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (var file in original) File.WriteAllBytes(file.Key, file.Value);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            Require(original.All(p => p.Value.SequenceEqual(File.ReadAllBytes(p.Key))), "Candidate scene rollback failed.");
        }
        static void WriteVerifiedReceipt(string path, string contents)
        {
            string temporary = path + ".pending-" + Guid.NewGuid().ToString("N");
            try
            {
                File.WriteAllText(temporary, contents);
                Require(File.ReadAllText(temporary) == contents, "Integration receipt readback failed.");
                if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
        static void WriteIntegrationReceipt(Result result)
        {
            Directory.CreateDirectory("JourneyEvidence"); WriteVerifiedReceipt(ReportPath, JsonUtility.ToJson(result, true));
        }
        public static void IntegrateFromEnvironment()
        {
            Require(!Application.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode && !BuildPipeline.isBuildingPlayer, "Explicit EditMode only; never import/build/play callbacks.");
            var setup = EditorSceneManager.GetSceneManagerSetup();
            Require(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "Save/discard dirty scenes first.");
            string path = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_ASSET_INPUT");
            var inputPin = new FilePin { path = path, sha256 = Environment.GetEnvironmentVariable("DESERTRV_JOURNEY_ASSET_INPUT_SHA256") };
            FileCheck(inputPin, "JourneyEvidence/");
            var request = JsonUtility.FromJson<Request>(File.ReadAllText(path)); ValidateRequestShape(request, Environment.GetEnvironmentVariable("GITHUB_SHA"));
            var result = new Result { sourceCommit = request.sourceCommit, requestSha256 = inputPin.sha256 };
            var original = new Dictionary<string, byte[]>(); var protectedFiles = SnapshotProtected();
            result.protectedFiles = protectedFiles.OrderBy(p => p.Key).Select(p => new FilePin { path = p.Key, sha256 = p.Value }).ToArray();
            try
            {
                RunCandidateTransaction(() => {
                foreach (var pin in request.savedInputs) AssetCheck(pin);
                foreach (string target in TargetPaths()) foreach (string file in new[] { target, target + ".meta" })
                { Require(File.Exists(file), "Generated candidate or meta missing: " + file); original.Add(file, File.ReadAllBytes(file)); }
                var assets = request.candidates.Select(Resolve).ToDictionary(c => c.input.kind);
                var flash = Load<GameObject>(request.muzzleFlashPrefab); var arc = Load<GameObject>(request.arcPresentationPrefab);
                Require(PrefabUtility.IsPartOfPrefabAsset(flash) && flash.GetComponent<ParticleSystem>() &&
                    flash.GetComponentsInChildren<MonoBehaviour>(true).Length == 0 && flash.GetComponentsInChildren<Collider>(true).Length == 0, "Authored root ParticleSystem flash prefab without scripts/colliders required.");
                var ap = arc.GetComponent<ArcPresentation>();
                Require(PrefabUtility.IsPartOfPrefabAsset(arc) && ap && ap.source && ap.source.IsChildOf(arc.transform) && ap.audioSource && ap.audioSource.transform.IsChildOf(arc.transform) &&
                    ap.beams != null && ap.impacts != null && ap.beams.Length > 0 && ap.beams.Length == ap.impacts.Length &&
                    ap.beams.All(b => b && b.transform.IsChildOf(arc.transform)) && ap.impacts.All(i => i && i.transform.IsChildOf(arc.transform)) &&
                    arc.GetComponentsInChildren<MonoBehaviour>(true).Length == 1 && arc.GetComponentsInChildren<Collider>(true).Length == 0, "Explicit self-contained arc source/audio/beam/impact prefab required.");
                Require(flash.GetComponentsInChildren<Camera>(true).Length == 0 && arc.GetComponentsInChildren<Camera>(true).Length == 0 &&
                    flash.GetComponentsInChildren<AudioListener>(true).Length == 0 && arc.GetComponentsInChildren<AudioListener>(true).Length == 0, "FX must not duplicate camera/listener ownership.");
                CheckMaterials(flash); CheckMaterials(arc);
                var audio = request.sounds.ToDictionary(s => s.role, s => Load<AudioClip>(s.clip));
                Require(audio.All(s => s.Value.length > 0 && s.Value.samples > 0), "Missing/nonplayable audio input.");
                var manifest = AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(JourneySceneAuthoring.ManifestPath);
                Require(ManifestIsUnbound(manifest), "Manifest contains existing review/provenance/bindings; use a genuinely empty authored candidate manifest.");
                var boot = EditorSceneManager.OpenScene(JourneySceneAuthoring.BootstrapPath, OpenSceneMode.Single);
                LogProtectedStage("before-bootstrap-wire", protectedFiles);
                WireBootstrap(boot, request, assets, flash, arc, audio);
                LogProtectedStage("after-bootstrap-wire", protectedFiles);
                Require(EditorSceneManager.SaveScene(boot, JourneySceneAuthoring.BootstrapPath), "Bootstrap save failed.");
                LogProtectedStage("after-bootstrap-save", protectedFiles);
                foreach (var plan in request.regions.OrderBy(p => p.region))
                {
                    boot = EditorSceneManager.OpenScene(JourneySceneAuthoring.BootstrapPath, OpenSceneMode.Single);
                    var scene = EditorSceneManager.OpenScene(JourneySceneAuthoring.RegionPaths[plan.region - 1], OpenSceneMode.Additive);
                    LogProtectedStage("before-region-" + plan.region, protectedFiles);
                    WireRegion(scene, boot, plan, assets);
                    LogProtectedStage("after-region-" + plan.region, protectedFiles);
                    Require(EditorSceneManager.SaveScene(scene, JourneySceneAuthoring.RegionPaths[plan.region - 1]), "Regional scene save failed.");
                }
                manifest.pouncer = Review(assets["pouncer"]); manifest.armored = Review(assets["armored"]); manifest.weapon = Review(assets["weapon"]);
                manifest.weaponPresentation = assets["weapon"].prefab.GetComponent<WeaponPresentation>(); manifest.arcPresentation = ap;
                manifest.armoredWeakpointPresentation = assets["armored"].prefab.GetComponent<BeastWeakPointPresentation>();
                EditorUtility.SetDirty(manifest); AssetDatabase.SaveAssetIfDirty(manifest);
                // Discard temporary RV placement before independent saved-scene checks.
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                VerifySavedBindings(request, assets);
                var errors = JourneyContentChecks.Inspect(false); Require(errors.Count == 0, string.Join("\n", errors));
                var productionFailures = JourneyContentChecks.Inspect(true); result.productionGateFailures = productionFailures.ToArray();
                RequireOnlyMissingApprovals(result.productionGateFailures);
                Require(!Approved(manifest), "Production approval must remain absent.");
                FileCheck(inputPin, "JourneyEvidence/"); ConfirmProtectedSources(result, () => VerifyProtected(protectedFiles));
                result.outputs = TargetPaths().Select(p => new OutputFile { path = p, sha256 = JourneyDiagnosticScope.HashFile(p),
                    dependencyHash = AssetDatabase.GetAssetDependencyHash(p).ToString(), dependencySha256 = JourneyContentChecks.DependencySha256(p) }).ToArray();
                result.status = Label;
                }, () => JourneySceneAuthoring.RestoreSceneSetup(setup), () => {
                    ConfirmProtectedSources(result, () => VerifyProtected(protectedFiles));
                    WriteIntegrationReceipt(result); // No commit until actual receipt write/readback and scene restoration both succeed.
                }, () => {
                    // Record the original failing stage before Refresh can introduce a separate recovery delta.
                    try { LogProtectedStage("before-rollback", protectedFiles); } catch (Exception diagnostic) { Debug.LogWarning("Protected stage diagnostic failed: " + diagnostic.GetType().Name); }
                    RestoreCandidateFiles(original); result.rolledBack = original.Count > 0;
                    LogProtectedStage("after-rollback", protectedFiles);
                    ConfirmProtectedSources(result, () => VerifyProtected(protectedFiles));
                });
            }
            catch (Exception error)
            {
                result.status = "failed-no-approval"; result.outputs = null; result.failures = new[] { error.ToString() };
                // A broken report destination must not prevent rollback or scene restoration (already attempted by the transaction).
                try { WriteIntegrationReceipt(result); }
                catch (Exception reportError) { Debug.LogWarning("Failure receipt could not be persisted: " + reportError.Message); }
                throw;
            }
        }
    }
}
