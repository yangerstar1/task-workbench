using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Tests
{
    // Static native physics evidence from saved authoring. No journey state, input,
    // player position, inventory, control mode, or production collider is changed.
    // A completed diagnostic is NOT traversal, prompt, or gameplay acceptance.
    public sealed class JourneyInteractionReachabilityTests
    {
        const string Folder = "Assets/DesertRV/Scenes/Journey/";
        const string Output = "JourneyEvidence/InteractionReachability/native-reachability.json";
        const string DependencyInputPath = "JourneyEvidence/InteractionReachability/consumer-input.json";
        static readonly string[] Names = { "JourneyBootstrap", "FirstStation", "Scrapyard", "NightBeacon" };
        const BindingFlags Fields = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
        static Type Production(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static T Field<T>(object target, string name) => (T)target.GetType().GetField(name, Fields).GetValue(target);
        static Component Find(Scene scene, string type) => scene.GetRootGameObjects()
            .SelectMany(r => r.GetComponentsInChildren(Production(type), true)).Single();
        static string Hash(string path)
        { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant(); }

        [Serializable] public sealed class FilePin { public string path, sha256; }
        [Serializable] public sealed class DependencyRow
        { public string path, sha256, kind, packageName, packageVersion; public long bytes; }
        [Serializable] public sealed class DependencyChange
        { public string path, producerSha256, consumerSha256; public long producerBytes, consumerBytes; }
        [Serializable] public sealed class ConsumerInput
        {
            public int schema;
            public string status, producerCommit, producerRunId, producerArtifactSha256, consumerCommit, currentProductionCommit;
            public DependencyRow[] dependencies; public DependencyChange[] dependencyChanges;
        }
        [Serializable] public sealed class DependencyMismatch
        { public string path, issue; public bool expectedPresent, actualPresent; public DependencyRow expected, actual; }
        [Serializable] public sealed class DependencyCheck
        {
            public string status = "not-started", inputPath = DependencyInputPath, inputSha256, snapshotError, snapshotFailureCode, snapshotFailurePath;
            public int expectedCount, actualCount; public bool passed;
            public DependencyRow[] actualDependencies = Array.Empty<DependencyRow>();
            public List<DependencyMismatch> mismatches = new List<DependencyMismatch>();
        }
        [Serializable] public sealed class Surface
        {
            public string hierarchy, type, objectId, mesh, meshSha256;
            public bool enabled, active, trigger; public Vector3 min, max;
        }
        [Serializable] public sealed class Sample
        {
            public int region; public string purpose, approach, predicate;
            public Vector3 foot, eye, target, hitPoint, hitNormal, driverLinecastPoint, driverLinecastNormal;
            public float distance, limit, hitDistance, endpointDistance, savedVehicleDistance, driverEntryDistance, driverLinecastDistance, driverLinecastEndpointDistance;
            public bool withinRange, productionCanReachPoint, hasFirstHit, acceptedSurfaceIsFirstHit;
            public bool supported, standingCapsuleClear, driverDistancePromptPredicate, driverDistanceEnterPredicate, driverLinecastHasHit, driverLinecastAllowsGeometry;
            public Surface acceptedSurface, firstHit, support, driverLinecastHit;
            public Surface[] standingBlockers;
        }
        [Serializable] public sealed class Report
        {
            public int schemaVersion = 2;
            public string status = "incomplete", unityVersion;
            public string scope = "saved-scene-static-native-physics; no runtime progression or input";
            public string driverScope = "distance prompt predicate and native Linecast geometry only; FindInteraction/TryEnterDriver not invoked; door remains saved-closed";
            public string powerScope = "same production CanReachPoint gate for connect/disconnect; no connection state or parked-RV transition exercised";
            public bool sourceUnchanged, copiesDeleted, setupRestored;
            public DependencyCheck dependencyCheck = new DependencyCheck();
            public List<FilePin> sourceFiles = new List<FilePin>();
            public List<Sample> samples = new List<Sample>();
            public List<string> cleanupErrors = new List<string>();
        }
        Report report;
        void Write() { Directory.CreateDirectory(Path.GetDirectoryName(Output)); File.WriteAllText(Output, JsonUtility.ToJson(report, true)); }
        void Pin(string path)
        {
            Assert.That(File.Exists(path), Is.True, "Prepared saved-scene dependency missing: " + path);
            if (!report.sourceFiles.Any(p => p.path == path)) report.sourceFiles.Add(new FilePin { path = path, sha256 = Hash(path) });
        }
        Surface Describe(Collider collider)
        {
            if (!collider) return null;
            var names = new List<string>(); for (var t = collider.transform; t; t = t.parent) names.Insert(0, t.name + "[" + t.GetSiblingIndex() + "]");
            var result = new Surface { hierarchy = string.Join("/", names), type = collider.GetType().Name,
                objectId = GlobalObjectId.GetGlobalObjectIdSlow(collider).ToString(), enabled = collider.enabled,
                active = collider.gameObject.activeInHierarchy, trigger = collider.isTrigger,
                min = collider.bounds.min, max = collider.bounds.max };
            if (collider is MeshCollider mesh && mesh.sharedMesh)
            {
                result.mesh = AssetDatabase.GetAssetPath(mesh.sharedMesh);
                if (File.Exists(result.mesh)) { Pin(result.mesh); Pin(result.mesh + ".meta"); result.meshSha256 = Hash(result.mesh); }
            }
            return result;
        }

        static bool SameDependency(DependencyRow a, DependencyRow b) => a.path == b.path && a.kind == b.kind &&
            a.sha256 == b.sha256 && a.bytes == b.bytes && a.packageName == b.packageName && a.packageVersion == b.packageVersion;
        static bool SafeDependencyPath(string path) => !string.IsNullOrEmpty(path) && !Path.IsPathRooted(path) &&
            !path.Contains("\\") && !path.Any(char.IsControl) && path.Split('/').All(p => p != "" && p != "." && p != "..");
        void VerifyDependencyClosure()
        {
            var check = report.dependencyCheck; check.status = "checking-input";
            try
            {
                Pin(DependencyInputPath); Pin("JourneyEvidence/InteractionReachability/consumer-input.sha256");
                check.inputSha256 = Hash(DependencyInputPath);
                Assert.That(File.ReadAllText("JourneyEvidence/InteractionReachability/consumer-input.sha256").Trim(), Is.EqualTo(check.inputSha256));
                var input = JsonUtility.FromJson<ConsumerInput>(File.ReadAllText(DependencyInputPath));
                Assert.That(input, Is.Not.Null); Assert.That(input.schema, Is.EqualTo(1));
                Assert.That(input.status, Is.EqualTo("VERIFIED_HISTORICAL_ASSETS_CURRENT_CONSUMER_NOT_APPROVED"));
                Assert.That(input.producerCommit, Is.EqualTo("2c64f9b5a8cb86ea9a0beb6de582b7209e6f136c"));
                Assert.That(input.producerRunId, Is.EqualTo("38034314713"));
                Assert.That(input.producerArtifactSha256, Is.EqualTo("3b1af69279a23fb049d009d37bba7f2b52f078276a12c9445403d883bf5f3894"));
                Assert.That(input.currentProductionCommit, Is.EqualTo("ecd3fd411802e498ff21d14626cae5e4bde4333c"));
                Assert.That(input.consumerCommit, Does.Match("^[a-f0-9]{40}$"));
                Assert.That(input.consumerCommit, Is.EqualTo(Environment.GetEnvironmentVariable("GITHUB_SHA")));
                Assert.That(input.dependencies, Is.Not.Null); Assert.That(input.dependencies.Length, Is.EqualTo(796));
                Assert.That(input.dependencies.All(p => p != null && SafeDependencyPath(p.path) && p.bytes >= 0), Is.True);
                Assert.That(input.dependencies.Select(p => p.path).Distinct(StringComparer.Ordinal).Count(), Is.EqualTo(796));
                Assert.That(input.dependencies.Count(p => p.kind == "asset" && p.path.StartsWith("Assets/", StringComparison.Ordinal) && p.packageName == "" && p.packageVersion == ""), Is.EqualTo(772));
                Assert.That(input.dependencies.Count(p => p.kind == "package" && p.path.StartsWith("Packages/" + p.packageName + "/", StringComparison.Ordinal) && !string.IsNullOrEmpty(p.packageVersion)), Is.EqualTo(24));
                foreach (var pin in input.dependencies) Assert.That(pin.sha256, Does.Match("^[a-f0-9]{64}$"), pin.path);
                // The host preserves the old producer receipt and records only these
                // two current-source substitutions in its separate consumer input.
                Assert.That(input.dependencyChanges, Is.Not.Null); Assert.That(input.dependencyChanges.Length, Is.EqualTo(2));
                string[] paths = { "Assets/DesertRV/Runtime/JourneyMotor.cs", "Assets/DesertRV/Runtime/JourneyHud.cs" };
                string[] oldHashes = { "a0ac13f7a4ddeb2007d11935ead4ede8b7c13362115d85afc12f71654fd1d65a", "d9650d2449e3632f94ca55a39b20243052a138c123cf7b90b8b61966fa91c7ed" };
                string[] newHashes = { "7f12f78f5fee78f03aac4ea32dd53e3ed9336d0866d19f750df4496f9e310397", "6a9ccf0a396bd3fc09cc39b0daedabe4b0bd1c42ff12d67cfc8c0d9d24ddb9ed" };
                for (int i = 0; i < paths.Length; i++)
                {
                    var change = input.dependencyChanges.Single(p => p.path == paths[i]);
                    var expected = input.dependencies.Single(p => p.path == paths[i]);
                    Assert.That(change.producerSha256, Is.EqualTo(oldHashes[i]), paths[i]);
                    Assert.That(change.consumerSha256, Is.EqualTo(newHashes[i]), paths[i]);
                    Assert.That(expected.sha256, Is.EqualTo(change.consumerSha256), paths[i]);
                    Assert.That(expected.bytes, Is.EqualTo(change.consumerBytes), paths[i]);
                    Assert.That(change.producerBytes, Is.GreaterThan(0), paths[i]);
                }
                check.expectedCount = input.dependencies.Length; check.status = "calling-production-snapshot";
                var preparation = Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor", true);
                var snapshot = preparation.GetMethod("DependencySnapshot", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
                Assert.That(snapshot, Is.Not.Null);
                // Reuse the production recursive closure/package resolver unchanged.
                // No copied closure algorithm, fake package hash, or metadata fallback.
                check.actualDependencies = ((Array)snapshot.Invoke(null, null)).Cast<object>().Select(p => new DependencyRow {
                    path = Field<string>(p, "path"), sha256 = Field<string>(p, "sha256"), bytes = Field<long>(p, "bytes"),
                    kind = Field<string>(p, "kind"), packageName = Field<string>(p, "packageName"), packageVersion = Field<string>(p, "packageVersion") }).ToArray();
                check.actualCount = check.actualDependencies.Length;
                Assert.That(check.actualDependencies.Select(p => p.path).Distinct(StringComparer.Ordinal).Count(), Is.EqualTo(check.actualCount), "Duplicate native dependency paths.");
                var expectedByPath = input.dependencies.ToDictionary(p => p.path, StringComparer.Ordinal);
                var actualByPath = check.actualDependencies.ToDictionary(p => p.path, StringComparer.Ordinal);
                foreach (string path in expectedByPath.Keys.Union(actualByPath.Keys).OrderBy(p => p, StringComparer.Ordinal))
                {
                    bool expectedPresent = expectedByPath.TryGetValue(path, out var expected);
                    bool actualPresent = actualByPath.TryGetValue(path, out var actual);
                    if (!expectedPresent || !actualPresent || !SameDependency(expected, actual))
                        check.mismatches.Add(new DependencyMismatch { path = path, issue = !expectedPresent ? "unexpected" : !actualPresent ? "missing" : "changed",
                            expectedPresent = expectedPresent, actualPresent = actualPresent, expected = expected, actual = actual });
                }
                check.status = check.mismatches.Count == 0 ? "verified-native-closure" : "dependency-mismatch";
                Assert.That(check.mismatches, Is.Empty, "Native dependency mismatch; exact relative paths and expected/actual hashes are in " + Output);
                Assert.That(check.actualCount, Is.EqualTo(796)); check.passed = true;
            }
            catch (Exception error)
            {
                var cause = error is TargetInvocationException invocation && invocation.InnerException != null ? invocation.InnerException : error;
                check.snapshotError = cause.GetType().Name + ": " + cause.Message;
                const string missingPrefix = "Missing dependency bytes/meta: ";
                if (check.status == "calling-production-snapshot" && cause is InvalidOperationException &&
                    cause.Message.StartsWith(missingPrefix, StringComparison.Ordinal))
                {
                    string missing = cause.Message.Substring(missingPrefix.Length);
                    if (SafeDependencyPath(missing) && (missing.StartsWith("Assets/", StringComparison.Ordinal) || missing.StartsWith("Packages/", StringComparison.Ordinal)))
                    { check.snapshotFailureCode = "MISSING_DEPENDENCY_BYTES_OR_META"; check.snapshotFailurePath = missing; }
                }
                if (check.status != "dependency-mismatch") check.status = "dependency-verification-failed";
                report.status = "dependency-verification-failed"; throw;
            }
            finally { Write(); }
        }

        [Test] public void SavedScenes_RecordProductionReachabilityAndExactBlockers()
        {
            report = new Report { unityVersion = Application.unityVersion };
            Write(); // A missing dependency must not leave an old completed report.
            Assert.That(Application.isPlaying, Is.False, "This is an EditMode geometry diagnostic.");
            Assert.That(Application.unityVersion, Is.EqualTo("6000.3.19f1"));
            VerifyDependencyClosure(); // Fail closed BEFORE any saved-scene replacement or physics query.
            foreach (string name in Names) { Pin(Folder + name + ".unity"); Pin(Folder + name + ".unity.meta"); }
            foreach (string name in new[] { "JourneyRaycast", "JourneyActions", "JourneyMotor" }) Pin("Assets/DesertRV/Runtime/" + name + ".cs");
            Pin("Assets/DesertRV/Editor/JourneySceneAuthoring.cs");
            Pin("Assets/DesertRV/Editor/JourneySceneAuthoring.Supplies.cs");
            Write();
            var fixture = new SavedSceneFixture(report);
            try
            {
                fixture.Prepare();
                for (int region = 1; region <= 3; region++)
                {
                    var boot = EditorSceneManager.OpenScene(fixture.Copy(Names[0]), OpenSceneMode.Single);
                    var environment = EditorSceneManager.OpenScene(fixture.Copy(Names[region]), OpenSceneMode.Additive);
                    Assert.That(SceneManager.SetActiveScene(environment), Is.True);
                    Physics.SyncTransforms();
                    var actions = Find(boot, "JourneyActions"); var motor = Field<Component>(actions, "motor");
                    var binding = Find(environment, "RegionBinding");
                    Assert.That(Field<int>(binding, "region"), Is.EqualTo(region));
                    var vehicle = Field<Transform>(motor, "vehicle");
                    Assert.That(boot.GetRootGameObjects().Concat(environment.GetRootGameObjects())
                        .SelectMany(r => r.GetComponentsInChildren<MeshCollider>(true)).All(c => c.sharedMesh), Is.True,
                        "A missing imported collider mesh invalidates physics observations.");

                    // Use the author's standing points, including the rotated R2 cache.
                    var author = Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor", true);
                    var placements = (Array)author.GetMethod("SupplyPlacements").Invoke(null, new object[] { region });
                    foreach (object supply in Field<Array>(binding, "supplies"))
                    {
                        string id = Field<string>(supply, "id");
                        object placement = placements.Cast<object>().Single(p => Field<string>(p, "id") == id);
                        var stand = Field<Vector3>(placement, "stand");
                        var right = Quaternion.Euler(0, Field<float>(placement, "yaw"), 0) * Vector3.right;
                        foreach (float lateral in new[] { -.3f, 0f, .3f })
                            Observe(region, "supply:" + id, "authored-front-lateral-" + lateral.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture), stand + right * lateral,
                                Field<Transform>(supply, "point").position, Field<Collider>(supply, "surface"), 2.2f, true, vehicle.position);
                    }
                    if (region <= 2)
                    {
                        var salvage = Field<Transform>(binding, "salvage").position;
                        foreach (float lateral in new[] { -.3f, 0f, .3f })
                            Observe(region, region == 1 ? "ram-salvage" : "coil-salvage", "bench-front-lateral-" + lateral.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture),
                                new Vector3(salvage.x + lateral, .025f, salvage.z - 1.15f), salvage,
                                Field<Collider>(binding, "salvageSurface"), 2.5f, false, vehicle.position);
                    }
                    if (region >= 2)
                    {
                        var point = Field<Transform>(binding, "powerPoint").position;
                        foreach (float lateral in new[] { -.45f, 0f, .45f })
                            Observe(region, "power-connect-and-disconnect", "cabinet-front-lateral-" + lateral.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture),
                                new Vector3(point.x + lateral, .025f, point.z - 1.15f), point,
                                Field<Collider>(binding, "powerSurface"), 2.5f, false, vehicle.position);
                    }
                    // The retained cabin floor, bench, and closed door are never rebuilt.
                    var floor = vehicle.GetComponentsInChildren<Collider>(true).Single(c => c.name == "GEO-interior_floor");
                    var bench = Field<Transform>(actions, "cabinWorkbench").position;
                    var forward = (Vector3)motor.GetType().GetProperty("Forward").GetValue(motor);
                    var rightward = Vector3.Cross(Vector3.up, forward);
                    foreach (float lateral in new[] { -.3f, 0f, .3f })
                    {
                        var foot = bench + forward * .85f + rightward * lateral; foot.y = floor.bounds.max.y + .025f;
                        Observe(region, "cabin-workbench", "cabin-aisle-lateral-" + lateral.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture), foot, bench,
                            Field<Collider>(actions, "workbenchSurface"), 2.1f, false, vehicle.position);
                    }
                    var entry = (Vector3)motor.GetType().GetProperty("EntryPosition").GetValue(motor);
                    var outward = rightward * Mathf.Sign(Vector3.Dot(entry - vehicle.position, rightward));
                    foreach (float along in new[] { -.55f, 0f, .55f })
                    {
                        var foot = entry + outward * .95f + forward * along; foot.y = vehicle.position.y + .04f;
                        var sample = Observe(region, "driver-prompt-and-return-geometry", "door-outside-along-" + along.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture),
                            foot, entry + Vector3.up * 1.15f, null, 2.8f, false, vehicle.position);
                        // Driver prompt uses feet-to-entry distance, NOT CanReachPoint.
                        sample.predicate = "JourneyActions.FindInteraction: feet-entry < 2.8; JourneyMotor.TryEnterDriver: native Linecast";
                        sample.driverEntryDistance = Vector3.Distance(foot, entry);
                        sample.driverDistancePromptPredicate = sample.driverEntryDistance < 2.8f;
                        sample.driverDistanceEnterPredicate = sample.driverEntryDistance <= 2.8f;
                        // Match TryEnterDriver exactly: feet + 1.52, entry + 1.15,
                        // all layers, ignore triggers, blocked only when endpoint > .35.
                        // Record this Linecast's OWN hit; do not substitute TryFirstHit.
                        sample.driverLinecastHasHit = Physics.Linecast(sample.eye, sample.target, out var hit, ~0, QueryTriggerInteraction.Ignore);
                        sample.driverLinecastAllowsGeometry = !sample.driverLinecastHasHit || !(Vector3.Distance(hit.point, sample.target) > .35f);
                        if (sample.driverLinecastHasHit)
                        {
                            sample.driverLinecastHit = Describe(hit.collider); sample.driverLinecastPoint = hit.point;
                            sample.driverLinecastNormal = hit.normal; sample.driverLinecastDistance = hit.distance;
                            sample.driverLinecastEndpointDistance = Vector3.Distance(hit.point, sample.target);
                        }
                    }
                    Write(); // Retain all completed regions even if a later fixture fails.
                }
                Assert.That(report.samples.Count, Is.EqualTo(48));
                report.status = "observations-complete-not-gameplay-acceptance";
            }
            finally
            {
                fixture.Cleanup();
                if (report.cleanupErrors.Count != 0) report.status = "cleanup-failed";
                Write();
            }
            Assert.That(report.cleanupErrors, Is.Empty, "See native-reachability.json for cleanup failures.");
            Assert.That(report.sourceUnchanged && report.copiesDeleted && report.setupRestored, Is.True);
            // Deliberately no all-reachable assertion: this test collects blockers,
            // including expected failures, and does not turn diagnostics into acceptance.
        }

        Sample Observe(int region, string purpose, string approach, Vector3 foot, Vector3 target,
            Collider surface, float limit, bool inclusive, Vector3 vehicle)
        {
            var eye = foot + Vector3.up * 1.52f; var delta = target - eye;
            var sample = new Sample { region = region, purpose = purpose, approach = approach, foot = foot, eye = eye,
                target = target, distance = delta.magnitude, limit = limit, acceptedSurface = Describe(surface),
                predicate = "JourneyRaycast.CanReachPoint", savedVehicleDistance = Vector3.Distance(vehicle, target),
                withinRange = inclusive ? delta.magnitude <= limit : delta.magnitude < limit };
            // EditMode contains no runtime-generated walker; null excludes no world collider.
            sample.productionCanReachPoint = (bool)Production("JourneyRaycast").GetMethod("CanReachPoint")
                .Invoke(null, new object[] { eye, target, null, surface });
            object[] args = { eye, delta, delta.magnitude, null, default(RaycastHit) };
            sample.hasFirstHit = (bool)Production("JourneyRaycast").GetMethod("TryFirstHit").Invoke(null, args);
            if (sample.hasFirstHit)
            {
                var hit = (RaycastHit)args[4]; sample.firstHit = Describe(hit.collider);
                sample.hitPoint = hit.point; sample.hitNormal = hit.normal; sample.hitDistance = hit.distance;
                sample.endpointDistance = Vector3.Distance(hit.point, target); sample.acceptedSurfaceIsFirstHit = hit.collider == surface;
            }
            // Native standing-space/support evidence, not a simulated walking route.
            sample.standingBlockers = Physics.OverlapCapsule(foot + Vector3.up * .19f, foot + Vector3.up * 1.43f,
                .19f, ~0, QueryTriggerInteraction.Ignore).Select(Describe).ToArray();
            sample.standingCapsuleClear = sample.standingBlockers.Length == 0;
            sample.supported = Physics.Raycast(foot + Vector3.up * .08f, Vector3.down, out var support, .20f, ~0, QueryTriggerInteraction.Ignore);
            if (sample.supported) sample.support = Describe(support.collider);
            report.samples.Add(sample); return sample;
        }

        // Adapted from JourneyTracerMaterialTests' already-used ordinary saved-scene
        // lifecycle. Never save a PreviewScene. Preserve batch Untitled recovery first.
        sealed class SavedSceneFixture
        {
            readonly Report report; readonly SceneSetup[] setup; readonly Scene[] previous;
            readonly string id = Guid.NewGuid().ToString("N");
            readonly Dictionary<string, byte[]> originals = new Dictionary<string, byte[]>();
            readonly Dictionary<string, byte[]> recoveryFiles = new Dictionary<string, byte[]>();
            bool restorable, replaced, ownsFolder;
            string Temporary => "Assets/JourneyInteractionTest_" + id;
            public string Copy(string name) => Temporary + "/" + name + ".unity";
            public SavedSceneFixture(Report value)
            {
                report = value; setup = EditorSceneManager.GetSceneManagerSetup();
                previous = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            }
            public void Prepare()
            {
                restorable = setup.Any(s => s.isLoaded && s.isActive) && setup.All(s => !string.IsNullOrEmpty(s.path) && File.Exists(s.path)) && previous.All(s => !s.isLoaded || !s.isDirty);
                Assert.That(restorable || previous.Length == 0 || Application.isBatchMode, Is.True,
                    "Save open Editor scenes first; Untitled/dirty recovery is allowed only in the isolated batch project.");
                foreach (string path in setup.Select(s => s.path).Where(p => !string.IsNullOrEmpty(p)).SelectMany(p => new[] { p, p + ".meta" }).Distinct().Where(File.Exists))
                    originals.Add(path, File.ReadAllBytes(path));
                Assert.That(Directory.Exists(Temporary) || File.Exists(Temporary + ".meta"), Is.False);
                Assert.That(AssetDatabase.CreateFolder("Assets", Path.GetFileName(Temporary)), Is.Not.Empty); ownsFolder = true;
                if (!restorable)
                {
                    string recovery = "Library/DesertRVInteractionFixture/" + id; Directory.CreateDirectory(recovery);
                    for (int i = 0; i < previous.Length; i++)
                    {
                        var initial = previous[i]; if (!initial.isLoaded) continue;
                        string path = initial.path; bool dirty = initial.isDirty;
                        string copy = Copy("Initial-" + i);
                        Assert.That(EditorSceneManager.SaveScene(initial, copy, true), Is.True);
                        foreach (string suffix in new[] { "", ".meta" })
                        {
                            string destination = recovery + "/Initial-" + i + ".unity" + suffix;
                            byte[] bytes = File.ReadAllBytes(copy + suffix); File.WriteAllBytes(destination, bytes);
                            recoveryFiles.Add(destination, bytes); Assert.That(File.ReadAllBytes(destination), Is.EqualTo(bytes));
                        }
                        File.WriteAllText(recovery + "/Initial-" + i + ".txt", "path=" + path + "\ndirty=" + dirty + "\nactive=" + (initial == SceneManager.GetActiveScene()) + "\nrootCount=" + initial.rootCount);
                        Assert.That(initial.path, Is.EqualTo(path)); Assert.That(initial.isDirty, Is.EqualTo(dirty));
                    }
                }
                replaced = true;
                foreach (string name in Names)
                {
                    var original = EditorSceneManager.OpenScene(Folder + name + ".unity", OpenSceneMode.Single);
                    Assert.That(EditorSceneManager.IsPreviewScene(original), Is.False);
                    Assert.That(EditorSceneManager.SaveScene(original, Copy(name), true), Is.True);
                    Assert.That(original.path, Is.EqualTo(Folder + name + ".unity"));
                    // Subsequent OpenScene(Single) unloads the original. The test then
                    // reloads every serialized copy before making native queries.
                }
            }
            void Attempt(Action action)
            { try { action(); } catch (Exception error) { report.cleanupErrors.Add(error.GetType().Name + ": " + error.Message); } }
            public void Cleanup()
            {
                Attempt(() => {
                    if (replaced)
                    {
                        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                        if (restorable) EditorSceneManager.RestoreSceneManagerSetup(setup);
                    }
                    if (restorable)
                    {
                        var after = EditorSceneManager.GetSceneManagerSetup();
                        Assert.That(after.Select(s => s.path), Is.EqualTo(setup.Select(s => s.path)));
                        Assert.That(after.Select(s => s.isLoaded), Is.EqualTo(setup.Select(s => s.isLoaded)));
                        Assert.That(after.Select(s => s.isActive), Is.EqualTo(setup.Select(s => s.isActive)));
                    }
                    else if (replaced) { Assert.That(SceneManager.sceneCount, Is.EqualTo(1)); Assert.That(SceneManager.GetActiveScene().rootCount, Is.Zero); }
                    if (replaced) Assert.That(Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt)
                        .All(s => !s.isLoaded || !s.isDirty), Is.True);
                    report.setupRestored = true;
                });
                Attempt(() => {
                    bool loaded = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).Any(s => s.path.StartsWith(Temporary + "/", StringComparison.Ordinal));
                    Assert.That(loaded, Is.False, "Temporary scenes retained because unload failed.");
                    if (ownsFolder) Assert.That(AssetDatabase.DeleteAsset(Temporary), Is.True);
                    Assert.That(Directory.Exists(Temporary) || File.Exists(Temporary + ".meta"), Is.False); report.copiesDeleted = true;
                });
                Attempt(() => {
                    foreach (var pair in originals.Concat(recoveryFiles)) Assert.That(File.ReadAllBytes(pair.Key), Is.EqualTo(pair.Value), pair.Key);
                    foreach (var pin in report.sourceFiles) Assert.That(Hash(pin.path), Is.EqualTo(pin.sha256), pin.path);
                    report.sourceUnchanged = true;
                });
                Physics.SyncTransforms();
            }
        }
    }
}
