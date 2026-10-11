using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace DesertRV.Tests
{
    // Opt-in native authoring gate. The host supplies an isolated exact-source project and
    // immutable prepared inputs, then independently accepts only the three changed scenes.
    public sealed class JourneyPouncerSupportBindingTests
    {
        const string Folder = "JourneyEvidence/PouncerGroundSupport";
        const string InputPath = Folder + "/author-input.json";
        const string OutputPath = Folder + "/native-authoring.json";
        const string ReceiptSha = "e25634798fd3ed6d90758225ea1952b95691a6aada5e3b6f545f04c6696d66ba";
        const string SceneFolder = "Assets/DesertRV/Scenes/Journey/";
        const BindingFlags Static = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
        static readonly string[] ScenePaths = { SceneFolder + "FirstStation.unity", SceneFolder + "Scrapyard.unity", SceneFolder + "NightBeacon.unity" };
        static readonly string[] SceneHashes = {
            "8dac5cd36c3d34a59f00d28075a786424d3837bfec05b36c6cf0c57cbd4d6e16",
            "4ab0e61c56b1a922cfd33473f69d8c74fcd4899da5bfb0d8020680e723e70de7",
            "f491acb525b971fa78f3dda56e859da839b3fca2d3af395ac4b31066b62e7e33" };
        static readonly string[] MetaHashes = {
            "fbd456b946fee2e03e6267ca698051a05720c79fa2ccac5f90d7c28ed2566ff0",
            "92bf1fd4fdff9b75df0fc224a26045aed7590efe59e5a22ff3c1a3336b11f31b",
            "d1f03b29720a57f0ec7385a88a567e4b95eb503e7cdef3fc7945e97502ef2cc4" };
        static readonly string[] SourcePaths = new[] {
            "Assets/DesertRV/Editor/JourneyCandidateAssetIntegration.cs",
            "Assets/DesertRV/Runtime/RegionBinding.cs",
            "Assets/DesertRV/Runtime/BeastActor.cs",
            "Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs",
            "Assets/DesertRV/Runtime/PouncerGroundSupport.cs",
            "Assets/DesertRV/Tests/EditMode/JourneyPouncerSupportBindingTests.cs"
        }.SelectMany(p => new[] { p, p + ".meta" }).ToArray();

        [Serializable] public sealed class FilePin { public string path, sha256; }
        [Serializable] public sealed class ScenePin { public string path, sha256, metaSha256; }
        [Serializable] public sealed class AuthorInput
        {
            public int schema;
            public string status, sourceCommit, producerGeneratedReceiptSha256;
            public FilePin[] sourcePins;
            public ScenePin[] scenes;
        }
        [Serializable] public sealed class SceneResult
        {
            public string path, beforeSha256, afterSha256;
            public int actorCount, pouncerCount, supportCount;
        }
        [Serializable] public sealed class AuthorResult
        {
            public int schema = 1;
            public string status = "INCOMPLETE_DERIVED_SCENES_UNREVIEWED", sourceCommit, inputSha256, unityVersion, failureStage, failureCode;
            public bool approved, saved, reloaded, bindingsValid, posesUnchanged, colliderGeometryUnchanged,
                healthUnchanged, approvalFlagsUnchanged, sceneMetasUnchanged, sourcesUnchanged, existingSerializedStateUnchanged;
            public SceneResult[] scenes = Array.Empty<SceneResult>();
        }
        sealed class GateFailure : Exception { internal readonly string code; internal GateFailure(string code) { this.code = code; } }
        sealed class SceneState
        {
            internal Dictionary<string, string> poses, colliders, health, serialized;
            internal string binding;
        }
        static Type Runtime(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static Type Editor(string name) => Type.GetType("DesertRV.Editor." + name + ", Assembly-CSharp-Editor", true);
        static object Field(object target, string name) => target.GetType().GetField(name).GetValue(target);
        static void Check(bool condition, string code) { if (!condition) throw new GateFailure(code); }
        static bool Sha(string value, int length = 64) => Regex.IsMatch(value ?? "", "^[a-f0-9]{" + length + "}$");
        static string Hash(string path)
        {
            using (var sha = SHA256.Create()) using (var file = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
        }
        static string Number(float value)
        {
            Check(!float.IsNaN(value) && !float.IsInfinity(value), "NONFINITE_SCENE_VALUE");
            return value.ToString("R", CultureInfo.InvariantCulture);
        }
        static string Vector(Vector3 value) => Number(value.x) + "," + Number(value.y) + "," + Number(value.z);
        static string Rotation(Quaternion value) => Number(value.x) + "," + Number(value.y) + "," + Number(value.z) + "," + Number(value.w);
        static string Key(Transform t) => t.parent ? Key(t.parent) + "/" + t.GetSiblingIndex() : t.GetSiblingIndex().ToString(CultureInfo.InvariantCulture);
        static string Reference(Object value) => value ? GlobalObjectId.GetGlobalObjectIdSlow(value).ToString() : "null";
        static string NormalizedReference(Object value)
        {
            if (!value) return "null";
            if (EditorUtility.IsPersistent(value) && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out string guid, out long localId))
            {
                Check(!string.IsNullOrEmpty(guid) && localId != 0, "UNSTABLE_SERIALIZED_ASSET_REFERENCE");
                return "asset:" + guid + ":" + localId.ToString(CultureInfo.InvariantCulture);
            }
            var id = GlobalObjectId.GetGlobalObjectIdSlow(value);
            Check(id.identifierType != 0 && id.targetObjectId != 0, "UNSTABLE_SERIALIZED_OBJECT_REFERENCE");
            return id.ToString();
        }
        static Component[] All(Scene scene, Type type) => scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren(type, true)).ToArray();
        static Component Binding(Scene scene, int region)
        {
            var rows = All(scene, Runtime("RegionBinding"));
            Check(rows.Length == 1 && (int)Field(rows[0], "region") == region, "REGION_INVENTORY_CHANGED");
            return rows[0];
        }
        static Component[] Actors(Scene scene, Component binding)
        {
            var actors = ((IEnumerable)binding.GetType().GetMethod("AllEnemies").Invoke(binding, null)).Cast<Component>().ToArray();
            Check(actors.Length == 3 && actors.Distinct().Count() == 3 && new HashSet<Component>(actors).SetEquals(All(scene, Runtime("BeastActor"))), "ACTOR_INVENTORY_CHANGED");
            Check(actors.Count(a => !(bool)Field(a, "armored")) == 2 && actors.All(a => a.gameObject.scene == scene && PrefabUtility.IsPartOfPrefabInstance(a)), "PREPARED_ACTORS_REQUIRED");
            return actors;
        }
        static string Pose(Transform t) => t.name + "|" + t.gameObject.activeSelf + "|" + t.gameObject.layer + "|" +
            Vector(t.localPosition) + "|" + Rotation(t.localRotation) + "|" + Vector(t.localScale) + "|" + Vector(t.position) + "|" + Rotation(t.rotation) + "|" + Vector(t.lossyScale);
        static string ColliderState(Collider c)
        {
            string common = c.GetType().FullName + "|" + c.enabled + "|" + c.isTrigger + "|" + Number(c.contactOffset) + "|" +
                Reference(c.sharedMaterial) + "|" + Reference(c.attachedRigidbody) + "|" + c.includeLayers.value + "|" + c.excludeLayers.value + "|" + c.layerOverridePriority;
            if (c is BoxCollider box) return common + "|" + Vector(box.center) + "|" + Vector(box.size);
            if (c is CapsuleCollider capsule) return common + "|" + Vector(capsule.center) + "|" + Number(capsule.radius) + "|" + Number(capsule.height) + "|" + capsule.direction;
            if (c is SphereCollider sphere) return common + "|" + Vector(sphere.center) + "|" + Number(sphere.radius);
            if (c is MeshCollider mesh) return common + "|" + Reference(mesh.sharedMesh) + "|" + mesh.convex + "|" + (int)mesh.cookingOptions;
            throw new GateFailure("UNEXPECTED_COLLIDER_TYPE");
        }
        static string BindingState(Component binding)
        {
            Check(!(bool)Field(binding, "combatAssetsVerified") && !(bool)Field(binding, "environmentVerified"), "APPROVAL_GATE_OPENED");
            object[] reason = { null };
            Check(!(bool)binding.GetType().GetMethod("Validate").Invoke(binding, reason), "PRODUCTION_APPROVAL_OPENED");
            // Compare the complete existing binding, including all enemy/supply references,
            // while omitting only the newly authorized support array.
            var values = new List<string>(); var serialized = new SerializedObject(binding); var p = serialized.GetIterator();
            while (p.Next(true))
            {
                if (p.propertyPath == "pouncerSupportSurfaces" || p.propertyPath.StartsWith("pouncerSupportSurfaces.", StringComparison.Ordinal)) continue;
                if (p.propertyType == SerializedPropertyType.ObjectReference) values.Add(p.propertyPath + "=" + Reference(p.objectReferenceValue));
                else if (p.propertyType == SerializedPropertyType.Integer) values.Add(p.propertyPath + "=" + p.longValue);
                else if (p.propertyType == SerializedPropertyType.Enum) values.Add(p.propertyPath + "=" + p.enumValueIndex);
                else if (p.propertyType == SerializedPropertyType.ArraySize) values.Add(p.propertyPath + "=" + p.intValue);
                else if (p.propertyType == SerializedPropertyType.Boolean) values.Add(p.propertyPath + "=" + p.boolValue);
                else if (p.propertyType == SerializedPropertyType.Float)
                {
                    Check(!double.IsNaN(p.doubleValue) && !double.IsInfinity(p.doubleValue), "NONFINITE_REGION_VALUE");
                    values.Add(p.propertyPath + "=" + p.doubleValue.ToString("R", CultureInfo.InvariantCulture));
                }
                else if (p.propertyType == SerializedPropertyType.String) values.Add(p.propertyPath + "=" + p.stringValue);
            }
            return string.Join("\n", values);
        }
        static string OmitAuthorizedArray(string json, string name)
        {
            // Only these two known top-level reference arrays are omitted. The complete
            // original ordered GameObject component list is independently included below.
            string pattern = "\"" + name + "\"\\s*:\\s*(?:null|\\[[^\\[\\]]*\\])";
            Check(Regex.Matches(json, pattern).Count == 1, "AUTHORIZED_SERIALIZED_ARRAY_NOT_FOUND");
            return Regex.Replace(json, pattern, "\"" + name + "\":[]");
        }
        static string SerializedState(Object value, Func<Object, string> normalize)
        {
            string json = EditorJsonUtility.ToJson(value);
            string componentInventory = "";
            if (value is GameObject go)
            {
                var components = go.GetComponents<Component>();
                Check(components.All(c => c), "EXISTING_COMPONENT_MISSING");
                componentInventory = string.Join("|", components.Where(c => c.GetType() != Runtime("PouncerGroundSupport")).Select(c => normalize(c)));
                json = OmitAuthorizedArray(json, "m_Component");
            }
            if (value.GetType() == Runtime("RegionBinding")) json = OmitAuthorizedArray(json, "pouncerSupportSurfaces");
            json = Regex.Replace(json, "\"instanceID\"\\s*:\\s*(-?[0-9]+)", match => {
                int id = int.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture);
                var referenced = id == 0 ? null : EditorUtility.InstanceIDToObject(id);
                Check(id == 0 || referenced, "SERIALIZED_OBJECT_REFERENCE_UNRESOLVED");
                return "\"stableObjectId\":\"" + normalize(referenced) + "\"";
            });
            return json + "\noriginalComponents=" + componentInventory;
        }
        static Dictionary<string, string> ExistingSerializedState(Scene scene)
        {
            var objects = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Transform>(true)).Select(t => t.gameObject).ToArray();
            var values = objects.Cast<Object>().Concat(objects.SelectMany(go => go.GetComponents<Component>()).Where(c => c && c.GetType() != Runtime("PouncerGroundSupport")).Cast<Object>()).ToArray();
            // Scope the identity cache to one loaded snapshot; Unity instance IDs can be
            // recycled after a close/reopen, while the serialized identities stay stable.
            var identities = new Dictionary<int, string>();
            string Normalize(Object value)
            {
                if (!value) return "null";
                int id = value.GetInstanceID();
                if (!identities.TryGetValue(id, out string identity)) identities.Add(id, identity = NormalizedReference(value));
                return identity;
            }
            return values.ToDictionary(Normalize, value => SerializedState(value, Normalize));
        }
        static SceneState Snapshot(Scene scene, Component binding)
        {
            var actors = Actors(scene, binding); var colliders = All(scene, typeof(Collider)).Cast<Collider>().ToArray();
            Check(colliders.Length > 2, "SCENE_COLLIDERS_ABSENT");
            return new SceneState {
                poses = scene.GetRootGameObjects().Select(r => r.transform).Concat(actors.Select(a => a.transform)).Concat(colliders.Select(c => c.transform)).Distinct().ToDictionary(Key, Pose),
                colliders = colliders.ToDictionary(c => Key(c.transform) + "/" + Array.IndexOf(c.GetComponents<Collider>(), c), ColliderState),
                health = actors.ToDictionary(a => Key(a.transform), a => string.Join("|", new[] { "Health", "Phase", "Dead", "KilledByRam" }.Select(n => a.GetType().GetProperty(n).GetValue(a, null).ToString()))),
                serialized = ExistingSerializedState(scene),
                binding = BindingState(binding)
            };
        }
        static bool Equal(Dictionary<string, string> a, Dictionary<string, string> b) => a.Count == b.Count && a.All(p => b.TryGetValue(p.Key, out string value) && value == p.Value);
        static void Unchanged(SceneState before, SceneState after)
        {
            Check(Equal(before.poses, after.poses), "ROOT_POSES_CHANGED");
            Check(Equal(before.colliders, after.colliders), "COLLIDER_GEOMETRY_CHANGED");
            Check(Equal(before.health, after.health), "ACTOR_HEALTH_CHANGED");
            Check(before.binding == after.binding, "EXISTING_REGION_BINDING_CHANGED");
            Check(Equal(before.serialized, after.serialized), "EXISTING_SERIALIZED_STATE_CHANGED");
        }
        static void VerifyBindings(Scene scene, Component binding)
        {
            var actors = Actors(scene, binding); var supportType = Runtime("PouncerGroundSupport");
            // The immutable producer scenes predate these support bindings. Structural
            // validation belongs after the production binder and after native reload.
            object[] structureReason = { null };
            Check((bool)binding.GetType().GetMethod("ValidateStructure").Invoke(binding, structureReason), "REGION_STRUCTURE_INVALID");
            var expected = new[] { "Route foundation", "Road surface" }.Select(n => binding.transform.Find(n)?.GetComponent<BoxCollider>()).ToArray();
            Check(expected.All(c => c && c.transform.parent == binding.transform && c.gameObject.scene == scene) && expected.Distinct().Count() == 2, "EXACT_SUPPORT_BOXES_ABSENT");
            var surfaces = (BoxCollider[])Field(binding, "pouncerSupportSurfaces");
            Check(surfaces != null && surfaces.SequenceEqual(expected), "SERIALIZED_SUPPORT_REFERENCES_INVALID");
            var allSupports = All(scene, supportType); Check(allSupports.Length == 2, "SUPPORT_COMPONENT_INVENTORY_INVALID");
            var serialized = new SerializedObject(binding); var property = serialized.FindProperty("pouncerSupportSurfaces");
            Check(property != null && property.isArray && property.arraySize == 2, "SUPPORT_ARRAY_NOT_SERIALIZED");
            for (int i = 0; i < 2; i++) Check(property.GetArrayElementAtIndex(i).objectReferenceValue == expected[i], "SUPPORT_BOX_NOT_SERIALIZED");
            foreach (var actor in actors)
            {
                var supports = actor.GetComponents(supportType);
                if ((bool)Field(actor, "armored")) { Check(supports.Length == 0, "ARMORED_SUPPORT_WAS_ADDED"); continue; }
                Check(supports.Length == 1 && allSupports.Contains(supports[0]) && ((Behaviour)supports[0]).enabled, "POUNCER_SUPPORT_NOT_UNIQUE");
                var support = supports[0]; var paws = actor.GetComponent(Runtime("PouncerPawContactConstraint"));
                Check((Object)Field(support, "actor") == actor && (Object)Field(support, "paws") == paws && (Object)Field(support, "region") == binding, "SUPPORT_OBJECT_REFERENCES_INVALID");
                var refs = new SerializedObject(support);
                foreach (var pair in new[] { new KeyValuePair<string, Object>("actor", actor), new KeyValuePair<string, Object>("paws", paws), new KeyValuePair<string, Object>("region", binding) })
                {
                    var reference = refs.FindProperty(pair.Key);
                    Check(reference != null && reference.propertyType == SerializedPropertyType.ObjectReference && reference.objectReferenceValue == pair.Value, "SUPPORT_REFERENCE_NOT_SERIALIZED");
                }
                object[] reason = { null };
                Check((bool)supportType.GetMethod("ValidateBindings").Invoke(support, reason), "PRODUCTION_SUPPORT_VALIDATION_FAILED");
                Check(!(Object)Field(actor, "journey") && !(Object)Field(actor, "player"), "CROSS_SCENE_ACTOR_REFERENCE_ADDED");
            }
        }
        static void CheckSources(AuthorInput input)
        {
            Check(input.sourcePins != null && input.sourcePins.Length == SourcePaths.Length &&
                input.sourcePins.All(p => p != null) && input.sourcePins.Select(p => p.path).Distinct().Count() == SourcePaths.Length &&
                new HashSet<string>(input.sourcePins.Select(p => p.path)).SetEquals(SourcePaths), "SOURCE_PIN_INVENTORY_INVALID");
            foreach (var pin in input.sourcePins) Check(Sha(pin.sha256) && Hash(pin.path) == pin.sha256, "SOURCE_PIN_CHANGED");
        }
        static void WriteResult(AuthorResult result, string dependencies)
        {
            string json = JsonUtility.ToJson(result, true);
            File.WriteAllText(OutputPath, json.Substring(0, json.LastIndexOf('}')) + ",\n  \"dependencies\": " + dependencies + "\n}\n");
        }
        static void Ordinary(Scene scene, string path) => Check(scene.IsValid() && scene.isLoaded && scene.path == path &&
            !EditorSceneManager.IsPreviewScene(scene) && scene.GetPhysicsScene() == Physics.defaultPhysicsScene, "ORDINARY_RESTORED_SCENE_REQUIRED");

        [Test, Explicit("Requires isolated pinned prepared scenes; writes only three derived scene files."), Timeout(600000)]
        public void BindPinnedPreparedScenes_SaveReloadPreservesSourceAndPoses()
        {
            var result = new AuthorResult { sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA"), unityVersion = Application.unityVersion, failureStage = "input" };
            var rows = new List<SceneResult>(); string dependencies = "[]"; Scene opened = default;
            var initial = EditorSceneManager.GetSceneManagerSetup(); var active = SceneManager.GetActiveScene();
            var initialScenes = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            var initialDirty = initialScenes.Select(s => s.isDirty).ToArray();
            var initialRoots = initialScenes.Select(s => s.isLoaded ? s.GetRootGameObjects().Select(r => r.GetInstanceID()).ToArray() : Array.Empty<int>()).ToArray();
            Check(!File.Exists(OutputPath), "OUTPUT_ALREADY_EXISTS");
            Directory.CreateDirectory(Folder); WriteResult(result, dependencies);
            try
            {
                Check(Application.isBatchMode && !Application.isPlaying && !BuildPipeline.isBuildingPlayer && Application.unityVersion == "6000.3.19f1", "PINNED_BATCH_EDITMODE_REQUIRED");
                // Additive lifecycle preserves even dirty/unsaved initial content. Only
                // owned ordinary targets close; their handles must not exist beforehand.
                Check(ScenePaths.All(p => !SceneManager.GetSceneByPath(p).IsValid()), "INITIAL_SCENE_STATE_NOT_ISOLATED");
                result.inputSha256 = File.ReadAllText(Folder + "/author-input.sha256").Trim();
                Check(Sha(result.inputSha256) && Hash(InputPath) == result.inputSha256, "AUTHOR_INPUT_HASH_INVALID");
                var input = JsonUtility.FromJson<AuthorInput>(File.ReadAllText(InputPath));
                Check(input != null && input.schema == 1 && input.status == "PINNED_POUNCER_SUPPORT_AUTHOR_INPUT" &&
                    Sha(input.sourceCommit, 40) && input.sourceCommit == result.sourceCommit && input.producerGeneratedReceiptSha256 == ReceiptSha, "AUTHOR_INPUT_IDENTITY_INVALID");
                CheckSources(input);
                Check(input.scenes != null && input.scenes.Length == 3, "SCENE_PIN_INVENTORY_INVALID");
                for (int i = 0; i < 3; i++) Check(input.scenes[i] != null && input.scenes[i].path == ScenePaths[i] && input.scenes[i].sha256 == SceneHashes[i] &&
                    input.scenes[i].metaSha256 == MetaHashes[i] && Hash(ScenePaths[i]) == SceneHashes[i] && Hash(ScenePaths[i] + ".meta") == MetaHashes[i], "PREPARED_SCENE_PIN_CHANGED");
                var binder = Editor("JourneyCandidateAssetIntegration").GetMethod("BindPouncerGroundSupport", BindingFlags.Public | BindingFlags.Static);
                Check(binder != null && binder.ReturnType == typeof(void), "PRODUCTION_BINDER_ABSENT");
                for (int i = 0; i < 3; i++)
                {
                    result.failureStage = "scene-authoring";
                    opened = EditorSceneManager.OpenScene(ScenePaths[i], OpenSceneMode.Additive); Ordinary(opened, ScenePaths[i]);
                    var binding = Binding(opened, i + 1); var before = Snapshot(opened, binding);
                    Check(All(opened, Runtime("PouncerGroundSupport")).Length == 0, "PREPARED_SCENE_ALREADY_DERIVED");
                    binder.Invoke(null, new object[] { binding }); VerifyBindings(opened, binding); Unchanged(before, Snapshot(opened, binding));
                    EditorSceneManager.MarkSceneDirty(opened);
                    Check(EditorSceneManager.SaveScene(opened, ScenePaths[i]), "DERIVED_SCENE_SAVE_FAILED");
                    string after = Hash(ScenePaths[i]); Check(after != SceneHashes[i], "DERIVED_SCENE_WAS_NOT_WRITTEN");
                    Check(EditorSceneManager.CloseScene(opened, true), "DERIVED_SCENE_CLOSE_FAILED"); opened = default;
                    Check(!SceneManager.GetSceneByPath(ScenePaths[i]).IsValid(), "DERIVED_SCENE_REMAINS_LOADED");
                    result.failureStage = "scene-reload";
                    opened = EditorSceneManager.OpenScene(ScenePaths[i], OpenSceneMode.Additive); Ordinary(opened, ScenePaths[i]);
                    binding = Binding(opened, i + 1); VerifyBindings(opened, binding); Unchanged(before, Snapshot(opened, binding));
                    Check(!opened.isDirty && Hash(ScenePaths[i]) == after && Hash(ScenePaths[i] + ".meta") == MetaHashes[i], "RELOADED_SCENE_OR_META_CHANGED");
                    var actors = Actors(opened, binding);
                    rows.Add(new SceneResult { path = ScenePaths[i], beforeSha256 = SceneHashes[i], afterSha256 = after, actorCount = actors.Length,
                        pouncerCount = actors.Count(a => !(bool)Field(a, "armored")), supportCount = All(opened, Runtime("PouncerGroundSupport")).Length });
                    Check(EditorSceneManager.CloseScene(opened, true), "RELOADED_SCENE_CLOSE_FAILED"); opened = default;
                }
                result.failureStage = "source-safety";
                CheckSources(input); result.sourcesUnchanged = true;
                Check(Hash(InputPath) == result.inputSha256 && File.ReadAllText(Folder + "/author-input.sha256").Trim() == result.inputSha256, "AUTHOR_INPUT_CHANGED");
                Check(ScenePaths.Select((p, i) => Hash(p + ".meta") == MetaHashes[i]).All(v => v), "SCENE_META_CHANGED");
                result.sceneMetasUnchanged = true;
                result.failureStage = "dependencies";
                var snapshot = (Array)Editor("JourneyCandidatePreparation").GetMethod("DependencySnapshot", Static).Invoke(null, null);
                Check(snapshot != null && snapshot.Length > 0 && snapshot.GetType().GetElementType().FullName == "DesertRV.Editor.JourneyCandidatePreparation+DependencyPin", "NATIVE_DEPENDENCY_SNAPSHOT_INVALID");
                dependencies = "[" + string.Join(",", snapshot.Cast<object>().Select(pin => JsonUtility.ToJson(pin))) + "]";
                result.failureStage = "final-pins";
                CheckSources(input);
                Check(rows.All(row => Hash(row.path) == row.afterSha256) && ScenePaths.Select((p, i) => Hash(p + ".meta") == MetaHashes[i]).All(v => v), "FINAL_SCENE_PIN_CHANGED");
                result.saved = result.reloaded = result.bindingsValid = result.posesUnchanged = result.colliderGeometryUnchanged = result.healthUnchanged = result.approvalFlagsUnchanged = result.existingSerializedStateUnchanged = true;
            }
            catch (GateFailure error) { result.failureCode = error.code; }
            catch (Exception) { result.failureCode = "NATIVE_OPERATION_FAILED"; }
            finally
            {
                try
                {
                    if (opened.IsValid() && opened.isLoaded) Check(EditorSceneManager.CloseScene(opened, true), "OWNED_SCENE_CLOSE_FAILED");
                    if (active.IsValid() && active.isLoaded) Check(SceneManager.SetActiveScene(active), "INITIAL_ACTIVE_SCENE_RESTORE_FAILED");
                    var after = EditorSceneManager.GetSceneManagerSetup();
                    Check(initial.Length == after.Length && initial.Zip(after, (a, b) => a.path == b.path && a.isLoaded == b.isLoaded && a.isActive == b.isActive).All(v => v), "INITIAL_SCENE_SETUP_CHANGED");
                    Check(SceneManager.sceneCount == initialScenes.Length, "INITIAL_SCENE_COUNT_CHANGED");
                    for (int i = 0; i < initialScenes.Length; i++)
                    {
                        var scene = SceneManager.GetSceneAt(i);
                        Check(scene.handle == initialScenes[i].handle && scene.isDirty == initialDirty[i] &&
                            (!scene.isLoaded || scene.GetRootGameObjects().Select(r => r.GetInstanceID()).SequenceEqual(initialRoots[i])), "INITIAL_SCENE_CONTENT_CHANGED");
                    }
                    Check(SceneManager.GetActiveScene().handle == active.handle, "INITIAL_ACTIVE_SCENE_CHANGED");
                }
                catch (Exception) { result.failureStage = "scene-lifecycle"; result.failureCode = "INITIAL_SCENE_SETUP_NOT_RESTORED"; }
                result.scenes = rows.ToArray();
                if (string.IsNullOrEmpty(result.failureCode) && rows.Count == 3)
                { result.status = "COMPLETED_DERIVED_SCENES_UNREVIEWED"; result.failureStage = ""; result.failureCode = ""; }
                else dependencies = "[]";
                WriteResult(result, dependencies);
            }
            Assert.That(result.status, Is.EqualTo("COMPLETED_DERIVED_SCENES_UNREVIEWED"), "Pouncer support authoring incomplete: " + result.failureStage + "/" + result.failureCode);
        }
    }
}
