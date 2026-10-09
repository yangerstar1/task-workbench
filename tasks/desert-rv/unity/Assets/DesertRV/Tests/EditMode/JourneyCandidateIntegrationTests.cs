using System;
using System.Linq;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneyCandidateIntegrationTests
    {
        static Type Integration => Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor", true);
        const string Sha = "1111111111111111111111111111111111111111";
        static object Read(string name, string json) => JsonUtility.FromJson(json, Integration.GetNestedType(name));
        static void Set(object target, string field, object value) => target.GetType().GetField(field).SetValue(target, value);
        static object Get(object target, string field) => target.GetType().GetField(field).GetValue(target);
        static object Call(string name, params object[] args) => Integration.GetMethod(name, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic).Invoke(null, args);
        static void Reject(string method, object request)
        {
            var error = Assert.Throws<TargetInvocationException>(() => Call(method, request, Sha));
            Assert.That(error.InnerException, Is.TypeOf<InvalidOperationException>());
        }
        static object Fx()
        {
            return Read("FxRequest", "{\"schema\":1,\"id\":\"original-fx-r1\",\"sourceCommit\":\"" + Sha + "\",\"flashLifetimeSeconds\":0.045,\"flashDiameterMeters\":0.065,\"flashSpeedMetersPerSecond\":0.4,\"flashColor\":{\"r\":1,\"g\":0.58,\"b\":0.16,\"a\":1},\"arcWidthMeters\":0.018,\"impactLifetimeSeconds\":0.12,\"impactDiameterMeters\":0.035,\"impactSpeedMetersPerSecond\":0.3,\"arcColor\":{\"r\":0.15,\"g\":0.65,\"b\":1,\"a\":1},\"arcSlots\":6,\"arcSound\":{}}");
        }
        static object ValidShape() => Read("Request", @"{""schema"":1,""label"":""STRICT_CANDIDATES_BOUND_UNREVIEWED"",""sourceCommit"":""1111111111111111111111111111111111111111"",""candidates"":[{""kind"":""pouncer"",""sourceModelPath"":""shape-only/pouncer.fbx"",""prefab"":{""path"":"""",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},""contract"":{""path"":"""",""sha256"":""""},""importReport"":{""path"":"""",""sha256"":""""}},{""kind"":""armored"",""sourceModelPath"":""shape-only/armored.fbx"",""prefab"":{""path"":"""",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},""contract"":{""path"":"""",""sha256"":""""},""importReport"":{""path"":"""",""sha256"":""""}},{""kind"":""weapon"",""sourceModelPath"":""shape-only/weapon.fbx"",""prefab"":{""path"":"""",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},""contract"":{""path"":"""",""sha256"":""""},""importReport"":{""path"":"""",""sha256"":""""}}],""savedInputs"":[{""path"":""Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},{""path"":""Assets/DesertRV/Scenes/Journey/FirstStation.unity"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},{""path"":""Assets/DesertRV/Scenes/Journey/Scrapyard.unity"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},{""path"":""Assets/DesertRV/Scenes/Journey/NightBeacon.unity"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},{""path"":""Assets/DesertRV/Scenes/Journey/JourneyContent.asset"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}],""muzzleFlashPrefab"":{""path"":"""",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},""arcPresentationPrefab"":{""path"":"""",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""},""weaponCameraPose"":{""localPosition"":{""x"":0.749840021,""y"":-0.446830004,""z"":2.446929932},""localRotation"":{""x"":-0.26757446,""y"":0.863942266,""z"":-0.044380691,""w"":0.424308878},""localScale"":{""x"":1,""y"":1,""z"":1}},""flashMuzzlePose"":{""localPosition"":{""x"":0,""y"":0,""z"":0},""localScale"":{""x"":1,""y"":1,""z"":1},""localRotation"":{""x"":0,""y"":0,""z"":0,""w"":1}},""arcModulePose"":{""localPosition"":{""x"":0,""y"":0,""z"":0},""localScale"":{""x"":1,""y"":1,""z"":1},""localRotation"":{""x"":0,""y"":0,""z"":0,""w"":1}},""sounds"":[{""role"":""shot"",""clip"":{""path"":""Assets/DesertRV/Audio/shot.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}},{""role"":""hit"",""clip"":{""path"":""Assets/DesertRV/Audio/hit.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}},{""role"":""reload"",""clip"":{""path"":""Assets/DesertRV/Audio/reload.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}},{""role"":""pickup"",""clip"":{""path"":""Assets/DesertRV/Audio/pickup.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}},{""role"":""upgrade"",""clip"":{""path"":""Assets/DesertRV/Audio/upgrade.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}},{""role"":""wind"",""clip"":{""path"":""Assets/DesertRV/Audio/wind.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}},{""role"":""arc"",""clip"":{""path"":""Assets/DesertRV/Audio/arc.wav"",""sha256"":"""",""dependencyHash"":"""",""dependencySha256"":""""}}],""regions"":[{""region"":1,""guards"":[{""id"":""first-station/guard-1"",""kind"":""pouncer"",""position"":{""x"":-6,""y"":0,""z"":18},""yaw"":180},{""id"":""first-station/guard-2"",""kind"":""pouncer"",""position"":{""x"":6,""y"":0,""z"":24},""yaw"":180}],""roadBeasts"":[{""id"":""first-station/road-armored"",""kind"":""armored"",""position"":{""x"":0,""y"":0,""z"":39},""yaw"":180}],""waves"":[]},{""region"":2,""guards"":[],""roadBeasts"":[],""waves"":[{""enemies"":[{""id"":""region-2/wave-1-pouncer-1"",""kind"":""pouncer"",""position"":{""x"":-7,""y"":0,""z"":33},""yaw"":180},{""id"":""region-2/wave-1-pouncer-2"",""kind"":""pouncer"",""position"":{""x"":7,""y"":0,""z"":39},""yaw"":180}]},{""enemies"":[{""id"":""region-2/wave-2-armored"",""kind"":""armored"",""position"":{""x"":-5,""y"":0,""z"":43},""yaw"":180}]}]},{""region"":3,""guards"":[],""roadBeasts"":[],""waves"":[{""enemies"":[{""id"":""region-3/wave-1-pouncer-1"",""kind"":""pouncer"",""position"":{""x"":-7,""y"":0,""z"":33},""yaw"":180},{""id"":""region-3/wave-1-pouncer-2"",""kind"":""pouncer"",""position"":{""x"":7,""y"":0,""z"":39},""yaw"":180}]},{""enemies"":[{""id"":""region-3/wave-2-armored"",""kind"":""armored"",""position"":{""x"":-5,""y"":0,""z"":43},""yaw"":180}]}]}]}");
        [Test] public void Request_CompleteExplicitShapePassesWithoutGrantingApproval() { Assert.DoesNotThrow(() => Call("ValidateRequestShape", ValidShape(), Sha)); }
        [Test] public void Request_MissingOneFullCandidateFailsClosed()
        {
            var r = ValidShape(); var old = (Array)Get(r, "candidates"); var next = Array.CreateInstance(old.GetType().GetElementType(), 2);
            Array.Copy(old, next, 2); Set(r, "candidates", next); Reject("ValidateRequestShape", r);
        }
        [Test] public void Request_DuplicateEnemyIdFailsClosed()
        {
            var r = ValidShape(); var regions = (Array)Get(r, "regions"); var guards = (Array)Get(regions.GetValue(0), "guards");
            Set(guards.GetValue(1), "id", Get(guards.GetValue(0), "id")); Reject("ValidateRequestShape", r);
        }
        [Test] public void Request_CannotRescaleImportedViewmodel()
        { var r = ValidShape(); Set(Get(r, "weaponCameraPose"), "localScale", Vector3.one * .01f); Reject("ValidateRequestShape", r); }
        [Test] public void Request_NonfiniteSpawnFailsClosed()
        {
            var r = ValidShape(); var regions = (Array)Get(r, "regions"); var guards = (Array)Get(regions.GetValue(0), "guards");
            Set(guards.GetValue(0), "position", new Vector3(float.PositiveInfinity, 0, 0)); Reject("ValidateRequestShape", r);
        }
        [Test] public void Request_NullFailsClosed() { Reject("ValidateRequestShape", null); }
        [Test] public void Request_EmptyCannotBindScenes() { Reject("ValidateRequestShape", Read("Request", "{}")); }
        [Test] public void OutputPaths_OnlyFourJourneyScenesAndManifest()
        {
            var paths = (string[])Call("TargetPaths"); Assert.That(paths, Has.Length.EqualTo(5));
            Assert.That(paths.Distinct().Count(), Is.EqualTo(5));
            Assert.That(paths.All(p => p.StartsWith("Assets/DesertRV/Scenes/Journey/")), Is.True);
            Assert.That(paths.Any(p => p.Contains("BodyStudy") || p.Contains("TraversalHarness") || p.Contains("CandidateArtImports")), Is.False);
        }
        [Test] public void Fx_ExplicitCandidateParametersAreStructurallyAccepted() { Assert.DoesNotThrow(() => Call("ValidateFxRequestShape", Fx(), Sha)); }
        [Test] public void Fx_WrongActionsCommitFailsClosed() { var r = Fx(); Set(r, "sourceCommit", new string('2', 40)); Reject("ValidateFxRequestShape", r); }
        [Test] public void Fx_TraversalIdFailsClosed() { var r = Fx(); Set(r, "id", "../BodyStudy"); Reject("ValidateFxRequestShape", r); }
        [Test] public void Fx_LongFlashFailsClosed() { var r = Fx(); Set(r, "flashLifetimeSeconds", .22f); Reject("ValidateFxRequestShape", r); }
        [Test] public void Fx_NonfiniteWorldSizeFailsClosed() { var r = Fx(); Set(r, "flashDiameterMeters", float.NaN); Reject("ValidateFxRequestShape", r); }
        [Test] public void Fx_MissingArcAudioFailsClosed() { var r = Fx(); Set(r, "arcSound", null); Reject("ValidateFxRequestShape", r); }
        [Test] public void Fx_InsufficientArcSlotsFailsClosed() { var r = Fx(); Set(r, "arcSlots", 0); Reject("ValidateFxRequestShape", r); }
        [Test] public void Axis_RawMuzzleForwardIsRejected()
        {
            var root = new GameObject("Muzzle");
            try { Assert.That(Call("SourceAxisAligned", root.transform), Is.False); }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
        [Test] public void Axis_ObservedSourceYChildSurvivesImportedScale100()
        {
            var parent = new GameObject("Muzzle"); var child = new GameObject("CandidateShotMuzzleAxis");
            try
            {
                parent.transform.localScale = Vector3.one * 100; parent.transform.localRotation = Quaternion.Euler(-90, 0, 0);
                child.transform.SetParent(parent.transform, false); child.transform.localRotation = Quaternion.LookRotation(Vector3.up, Vector3.forward);
                Assert.That(Call("SourceAxisAligned", child.transform), Is.True);
                child.transform.localRotation = Quaternion.identity; Assert.That(Call("SourceAxisAligned", child.transform), Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(parent); }
        }
        [Test] public void Fx_ParticlesUseWorldUnitsAndDoNotStartThemselves()
        {
            var root = new GameObject("Candidate native FX structural test");
            try
            {
                root.transform.localScale = Vector3.one * 100;
                var particles = (ParticleSystem)Call("Particles", root, null, .045f, .065f, .4f, Color.yellow, (short)1);
                Assert.That(particles.main.playOnAwake, Is.False); Assert.That(particles.main.loop, Is.False);
                Assert.That(particles.main.scalingMode, Is.EqualTo(ParticleSystemScalingMode.Shape));
                Assert.That(particles.main.simulationSpace, Is.EqualTo(ParticleSystemSimulationSpace.World));
                Assert.That(particles.main.startSize.constant, Is.EqualTo(.065f)); Assert.That(particles.emission.burstCount, Is.EqualTo(1));
                Assert.That(particles.main.startLifetime.constant, Is.EqualTo(.045f)); Assert.That(particles.main.maxParticles, Is.EqualTo(1));
                Assert.That(particles.isPlaying, Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        static Type Runtime(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Identity()
        {
            var type = Type.GetType("DesertRV.Editor.JourneyCandidateArtImport+Contract, Assembly-CSharp-Editor", true);
            return JsonUtility.FromJson("{\"schema\":1,\"mode\":\"STRICT_BINDING\",\"scope\":\"FULL_CANDIDATE\",\"id\":\"identity-fixture\",\"kind\":\"armored\",\"repository\":\"yangerstar1/task-workbench\",\"runUrl\":\"https://github.com/yangerstar1/task-workbench/actions/runs/123\",\"sourceCommit\":\"" + Sha + "\",\"artifactName\":\"identity-only-fixture\",\"artifactSha256\":\"" + new string('a',64) + "\",\"files\":[{\"file\":\"fixture.fbx\",\"sha256\":\"" + new string('a',64) + "\"}]}", type);
        }
        [Test] public void StrictIdentity_UsesImporterSourceContractAndRejectsEqualButInvalidFields()
        {
            Assert.DoesNotThrow(() => Call("ValidateStrictIdentity", Identity()));
            foreach (string field in new[] { "repository", "runUrl", "sourceCommit", "artifactName", "artifactSha256", "id" })
            {
                var contract = Identity(); Set(contract, field, "");
                Assert.Throws<TargetInvocationException>(() => Call("ValidateStrictIdentity", contract), field);
            }
            var wrongSchema = Identity(); Set(wrongSchema, "schema", 0);
            Assert.Throws<TargetInvocationException>(() => Call("ValidateStrictIdentity", wrongSchema));
        }
        [Test] public void StrictIdentity_DiscoveryCannotPromoteItself()
        {
            var contract = Identity(); Set(contract, "mode", "DISCOVERY_ONLY");
            Assert.Throws<TargetInvocationException>(() => Call("ValidateStrictIdentity", contract));
        }
        [Test] public void NativeFilePin_ActualByteTamperFailsBeforeAssetLoading()
        {
            Directory.CreateDirectory("JourneyEvidence"); string path = "JourneyEvidence/native-pin-fixture-" + Guid.NewGuid().ToString("N") + ".json";
            try
            {
                File.WriteAllText(path, "{\"source\":\"original\"}"); string hash;
                using (var sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
                var pin = Read("FilePin", "{}"); Set(pin, "path", path); Set(pin, "sha256", hash);
                Assert.DoesNotThrow(() => Call("FileCheck", pin, "JourneyEvidence/"));
                File.WriteAllText(path, "{\"source\":\"tampered\"}");
                Assert.Throws<TargetInvocationException>(() => Call("FileCheck", pin, "JourneyEvidence/"));
            }
            finally { if (File.Exists(path)) File.Delete(path); }
        }
        [Test] public void NativeProtectionReport_HashFailureClearsPreviousSuccessfulProof()
        {
            Directory.CreateDirectory("JourneyEvidence"); string path = "JourneyEvidence/protection-status-fixture-" + Guid.NewGuid().ToString("N") + ".txt";
            try
            {
                File.WriteAllText(path, "original"); string hash;
                using (var sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
                var pin = Read("FilePin", "{}"); Set(pin, "path", path); Set(pin, "sha256", hash);
                var result = Read("Result", "{}"); Action verify = () => Call("FileCheck", pin, "JourneyEvidence/");
                Call("ConfirmProtectedSources", result, verify); Assert.That(Get(result, "protectedSourcesUnchanged"), Is.True);
                File.WriteAllText(path, "changed after prior proof");
                Assert.Throws<TargetInvocationException>(() => Call("ConfirmProtectedSources", result, verify));
                Assert.That(Get(result, "protectedSourcesUnchanged"), Is.False);
            }
            finally { if (File.Exists(path)) File.Delete(path); }
        }
        [Test] public void Manifest_ExistingUnapprovedProvenanceCannotBeOverwritten()
        {
            var manifest = ScriptableObject.CreateInstance(Runtime("JourneyContentManifest")); var source = new GameObject("Existing source fixture");
            try
            {
                Assert.That(Call("ManifestIsUnbound", manifest), Is.True);
                foreach (string asset in new[] { "pouncer", "armored", "weapon" })
                {
                    var review = Get(manifest, asset);
                    foreach (string field in new[] { "dependencyHash", "reviewedDependencySha256", "generationRunUrl", "visualEvidence", "motionEvidence" })
                    { Set(review, field, "existing provenance"); Assert.That(Call("ManifestIsUnbound", manifest), Is.False, asset + "." + field); Set(review, field, null); }
                    Set(review, "sourceModel", source); Assert.That(Call("ManifestIsUnbound", manifest), Is.False); Set(review, "sourceModel", null);
                }
                var component = source.AddComponent(Runtime("JourneyActions")); Set(manifest, "armoredWeakpointPresentation", component);
                Assert.That(Call("ManifestIsUnbound", manifest), Is.False); Set(manifest, "armoredWeakpointPresentation", null);
                Set(manifest, "bootstrapDependencyHash", "existing hash"); Assert.That(Call("ManifestIsUnbound", manifest), Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(manifest); UnityEngine.Object.DestroyImmediate(source); }
        }
        [Test] public void ProductionGate_OnlyExactMissingApprovalSetIsPermitted()
        {
            var expected = (string[])Call("ExpectedMissingApprovals"); Assert.That(expected, Has.Length.EqualTo(11));
            Assert.DoesNotThrow(() => Call("RequireOnlyMissingApprovals", (object)expected));
            Assert.Throws<TargetInvocationException>(() => Call("RequireOnlyMissingApprovals", (object)expected.Take(10).ToArray()));
            Assert.Throws<TargetInvocationException>(() => Call("RequireOnlyMissingApprovals", (object)expected.Concat(new[] { expected[0] }).ToArray()));
        }
        [Test] public void ProductionGate_ActualManifestStructuralFailuresAreNotSwallowed()
        {
            var manifest = ScriptableObject.CreateInstance(Runtime("JourneyContentManifest"));
            try
            {
                var structural = new List<string>();
                Type.GetType("DesertRV.Editor.JourneyContentChecks, Assembly-CSharp-Editor", true).GetMethod("ValidateManifest").Invoke(null, new object[] { manifest, structural });
                Assert.That(structural.Any(s => s.Contains("real prefab missing")), Is.True);
                var combined = ((string[])Call("ExpectedMissingApprovals")).Concat(structural).ToArray();
                Assert.Throws<TargetInvocationException>(() => Call("RequireOnlyMissingApprovals", (object)combined));
            }
            finally { UnityEngine.Object.DestroyImmediate(manifest); }
        }
        [Test] public void NativeCapsule_CrossingTriggerEdgeIsRejectedEvenWithCenterOutside()
        {
            var beast = new GameObject("Native capsule-only collision fixture"); var exit = new GameObject("Native exit trigger fixture");
            try
            {
                var capsule = beast.AddComponent<CapsuleCollider>(); capsule.radius = .5f; capsule.height = 2; capsule.center = Vector3.zero;
                var trigger = exit.AddComponent<BoxCollider>(); trigger.size = new Vector3(2,3,2); trigger.isTrigger = true;
                beast.transform.position = new Vector3(-1.4f, 0, 0); Physics.SyncTransforms();
                Assert.That(Vector3.Distance(trigger.ClosestPoint(capsule.bounds.center), capsule.bounds.center), Is.GreaterThan(.3f));
                Assert.That(Call("CapsuleOverlapsVolume", capsule, trigger), Is.True);
                beast.transform.position = new Vector3(-1.51f, 0, 0); Physics.SyncTransforms();
                Assert.That(Call("CapsuleOverlapsVolume", capsule, trigger), Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(beast); UnityEngine.Object.DestroyImmediate(exit); }
        }
        static void SavedSceneTransactionFixture(string failure)
        {
            var setup = EditorSceneManager.GetSceneManagerSetup();
            string folder = "Assets/DesertRV/Tests/EditMode/IntegrationFixture-" + Guid.NewGuid().ToString("N");
            Directory.CreateDirectory(folder); AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            string path = folder + "/Fixture.unity", receipt = folder + "/receipt.txt";
            int restores = 0; bool rolledBack = false;
            try
            {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single); new GameObject("Before transaction");
                Assert.That(EditorSceneManager.SaveScene(scene, path), Is.True);
                var original = new Dictionary<string, byte[]> { { path, File.ReadAllBytes(path) }, { path + ".meta", File.ReadAllBytes(path + ".meta") } };
                var fixtureSetup = EditorSceneManager.GetSceneManagerSetup();
                Action stage = () => {
                    var loaded = EditorSceneManager.OpenScene(path, OpenSceneMode.Single); loaded.GetRootGameObjects().Single().name = "Saved candidate change";
                    if (!EditorSceneManager.SaveScene(loaded, path)) throw new IOException("Fixture save failed.");
                    if (failure == "stage") throw new InvalidOperationException("Injected failure after real scene save.");
                };
                Action restore = () => {
                    restores++;
                    if (failure == "restore" && restores == 1) throw new IOException("Injected initial setup restore failure.");
                    EditorSceneManager.RestoreSceneManagerSetup(fixtureSetup);
                };
                Action write = () => Call("WriteVerifiedReceipt", failure == "receipt" ? folder : receipt, "actual saved receipt"); // Production writer + directory target produces real IO failure.
                Action rollback = () => { Call("RestoreCandidateFiles", original); rolledBack = true; };
                if (failure == null) Assert.DoesNotThrow(() => Call("RunCandidateTransaction", stage, restore, write, rollback));
                else Assert.Throws<TargetInvocationException>(() => Call("RunCandidateTransaction", stage, restore, write, rollback));
                Assert.That(rolledBack, Is.EqualTo(failure != null));
                Assert.That(restores, Is.EqualTo(failure == "stage" ? 1 : failure == null ? 1 : 2));
                if (failure != null) foreach (var pair in original) Assert.That(File.ReadAllBytes(pair.Key), Is.EqualTo(pair.Value));
                else { Assert.That(File.ReadAllText(receipt), Is.EqualTo("actual saved receipt")); Assert.That(File.ReadAllBytes(path).SequenceEqual(original[path]), Is.False); }
                var reloaded = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                Assert.That(reloaded.GetRootGameObjects().Single().name, Is.EqualTo(failure == null ? "Saved candidate change" : "Before transaction"));
            }
            finally
            {
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                AssetDatabase.DeleteAsset(folder);
                if (setup.Length > 0 && setup.All(s => !s.isLoaded || !string.IsNullOrEmpty(s.path))) EditorSceneManager.RestoreSceneManagerSetup(setup);
            }
        }
        [Test] public void NativeTransaction_SavedSceneAndReceiptCommitTogether() { SavedSceneTransactionFixture(null); }
        [Test] public void NativeTransaction_PostSaveFailureRestoresSceneAndMetaBytes() { SavedSceneTransactionFixture("stage"); }
        [Test] public void NativeTransaction_ActualReceiptIoFailureRollsBackAndRestoresSetup() { SavedSceneTransactionFixture("receipt"); }
        [Test] public void NativeTransaction_SetupFailureRollsBackAndRetriesRestoration() { SavedSceneTransactionFixture("restore"); }
    }
}
