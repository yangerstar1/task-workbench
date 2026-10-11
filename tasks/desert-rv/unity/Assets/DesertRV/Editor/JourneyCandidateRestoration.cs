using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using FilePin = DesertRV.Editor.JourneyCandidateAssetIntegration.FilePin;
using AssetPin = DesertRV.Editor.JourneyCandidateAssetIntegration.AssetPin;
using DependencyPin = DesertRV.Editor.JourneyCandidatePreparation.DependencyPin;

namespace DesertRV.Editor
{
    // A separate native read-only consumer of immutable public producer bundles.
    // This never imports/authors assets, activates an old diagnostic scope or grants a build lease.
    public static class JourneyCandidateRestoration
    {
        public const string Folder = "JourneyEvidence/JourneyPreparation";
        public const string InputPath = Folder + "/restoration-input.json";
        public const string ProofPath = Folder + "/restoration-revalidated.json";
        const string Prefix = "tasks/desert-rv/unity/";
        const string ProducerCommit = "7e134d4bbc4a349e5c71b27980dea90d85ff538e";
        const string ProducerRun = "https://github.com/yangerstar1/task-workbench/actions/runs/37923953772";
        const string ProducerReceiptSha = "2b5e06b3b5dfcfb5a53afc3ff750b4eb8f460b222dc1abdca5974fc6c4702526";
        const string SelectionPath = "tasks/desert-rv/art/journey-preparation/three-strict-candidates.json";
        const string SelectionSha = "dfbc3b9a5959350b69544828ab3e6dbb5cfb7f01895fa985c0eefdb38e051f24";
        static bool AndroidProducer(Request request) => request != null &&
            request.assetProducerSourceCommit == "9c95f1009a597cf4573e286d0098b7bc47a62321" &&
            request.assetProducerRunUrl == "https://github.com/yangerstar1/task-workbench/actions/runs/38135035401" &&
            request.generatedReceiptSha256 == "742af42d6c4a5f7d366a562f9afbbd9e560c744863c866123565c2cd38ee1f58";
        static string SelectionDigest(Request request) => AndroidProducer(request) ? "e46d71b118dbf614cb183928528992037a4f8e4d408bf5359484716106457b05" : SelectionSha;
        static bool KnownProducer(Request request) => AndroidProducer(request) || request != null &&
            request.assetProducerSourceCommit == ProducerCommit && request.assetProducerRunUrl == ProducerRun && request.generatedReceiptSha256 == ProducerReceiptSha;
        [Serializable] public sealed class Request
        {
            public int schema;
            public string label, sourceCommit, producerRunUrl, assetProducerSourceCommit, assetProducerRunUrl, generatedReceiptSha256;
            public FilePin sourceTransitionProof, selection, originalGeneratedReceipt, originalNativeManifest, originalGrounding;
            public FilePin[] files;
            public string[] directories;
            public JourneyCandidateAssetIntegration.Request integration;
            public DependencyPin[] expectedDependencies;
        }
        [Serializable] public sealed class ImporterIdentity
        {
            public string kind, path, producerDependencyHash, currentDependencyHash, producerDependencySha256, currentDependencySha256;
        }
        [Serializable] public sealed class Proof
        {
            public int schema = 1;
            public string label = "RESTORED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED";
            public string sourceCommit, producerRunUrl, assetProducerSourceCommit, assetProducerRunUrl, generatedReceiptSha256, requestSha256, unityVersion;
            public FilePin sourceTransitionProof;
            public bool sourceBytesUnchanged, originalAssetsUnchanged, structureValidated, productionApprovalRejected, approved, scopeReused;
            public JourneyCandidateAssetIntegration.OutputFile[] scenes;
            public DependencyPin[] dependencies;
            public JourneyCandidateAssetIntegration.SpawnGroundingReport grounding;
        }
        [Serializable] public sealed class DependencyDifference
        {
            public string path, producerSha256, currentSha256;
            public long producerBytes, currentBytes;
        }
        [Serializable] public class Diagnostic
        {
            public int schema = 1;
            public string label = "RESTORATION_NATIVE_DIAGNOSTIC_ONLY", sourceCommit, producerRunUrl, stage = "INPUT", errorClass = "NONE", runIdentity = "UNVALIDATED";
            public bool completed, consumerIdentityMatched;
            public int dependencyExpectedCount, dependencyActualCount, dependencyAddedCount, dependencyMissingCount;
            public ImporterIdentity[] importerIdentities = Array.Empty<ImporterIdentity>();
            public DependencyDifference[] dependencyDifferences = Array.Empty<DependencyDifference>();
            [NonSerialized] public AssetLifecycleSnapshot[] lifecycleSnapshots = Array.Empty<AssetLifecycleSnapshot>();
        }
        [Serializable] sealed class AndroidDiagnostic : Diagnostic
        {
            public AssetLifecycleSnapshot[] assetLifecycle = Array.Empty<AssetLifecycleSnapshot>();
        }
        [Serializable] public sealed class DirtyDependency
        {
            public string path, type, identityState, guid, dirty, transition, diskState, sha256, captureGateMembership;
            public long localId, bytes;
        }
        [Serializable] public sealed class DiskChange
        {
            public string path, beforeState, beforeSha256, afterState, afterSha256;
            public long beforeBytes, afterBytes;
        }
        [Serializable] public sealed class AssetLifecycleSnapshot
        {
            public int sequence, declaredDependencyCount, observedPathCount, objectCount, distinctPathCount, enteredDirtyCount, retainedDirtyCount,
                clearedCount, unobservedCount, diskMismatchCount, diskUnavailableCount, captureGateObjectCount;
            public string stage, status = "CAPTURED", errorCode = "NONE";
            public bool preexistingBaseline, captureGateBound;
            public DirtyDependency[] dirtyDependencies = Array.Empty<DirtyDependency>();
            public DirtyDependency[] clearedDependencies = Array.Empty<DirtyDependency>();
            public DirtyDependency[] unobservedDependencies = Array.Empty<DirtyDependency>();
            public DiskChange[] diskChanges = Array.Empty<DiskChange>();
        }
        // This observer never loads, imports, saves, serializes or clears a Unity asset.
        // The host-pinned request supplies the closure before any native GetDependencies query.
        sealed class AssetLifecycleProbe
        {
            sealed class DiskState { public string state, sha256; public long bytes; }
            sealed class Loaded { public DirtyDependency row; public bool dirty; }
            readonly Diagnostic diagnostic;
            readonly Dictionary<string, DependencyPin> declared;
            readonly Dictionary<string, string> packages = new Dictionary<string, string>(StringComparer.Ordinal);
            Dictionary<string, DiskState> previousDisk;
            Dictionary<string, DirtyDependency> previousDirty = new Dictionary<string, DirtyDependency>(StringComparer.Ordinal);
            bool hasBaseline;
            HashSet<string> captureGateDependencies;
            readonly HashSet<string> observedPaths = new HashSet<string>(StringComparer.Ordinal);
            readonly List<AssetLifecycleSnapshot> snapshots = new List<AssetLifecycleSnapshot>();
            static readonly HashSet<string> Stages = new HashSet<string>(new[] {
                "RESTORATION_ENTRY", "DEPENDENCIES_BEFORE", "DEPENDENCIES_AFTER", "POSES_BEFORE", "POSES_AFTER",
                "GROUNDING_BEFORE", "GROUNDING_AFTER", "IMPORTER_IDENTITIES_BEFORE", "IMPORTER_IDENTITIES_AFTER",
                "SAVED_ROOT_IDENTITIES_BEFORE", "SAVED_ROOT_IDENTITIES_AFTER", "SAVED_BINDINGS_BEFORE", "SAVED_BINDINGS_AFTER",
                "CAPTURE_ENTRY", "CAPTURE_GATE_BEFORE", "CAPTURE_GATE_AFTER", "CAPTURE_REGION_1_BEFORE", "CAPTURE_REGION_1_AFTER", "CAPTURE_REGION_3_BEFORE", "CAPTURE_REGION_3_AFTER",
                "CAPTURE_SCENE_RESTORE_BEFORE", "CAPTURE_SCENE_RESTORE_AFTER", "RESTORATION_SCENE_RESTORE_BEFORE",
                "RESTORATION_SCENE_RESTORE_AFTER", "FINAL_PROTECTION_BEFORE", "FINAL_PROTECTION_AFTER" }, StringComparer.Ordinal);
            static bool Builtin(string path) => path == "Resources/unity_builtin_extra" || path == "Library/unity default resources";
            static bool SafeName(string path) => !string.IsNullOrEmpty(path) && path.Length <= 512 && !Path.IsPathRooted(path) &&
                !path.Any(char.IsControl) && !path.Contains("\\") && !path.Contains(":") && !path.Split('/').Any(part => part == "" || part == "." || part == "..") &&
                (path.StartsWith("Assets/", StringComparison.Ordinal) || Regex.IsMatch(path, "^Packages/com\\.unity\\.[a-z0-9_.-]+/") || Builtin(path));
            static bool Same(DiskState a, DiskState b) => a.state == b.state && a.sha256 == b.sha256 && a.bytes == b.bytes;
            static string SnapshotError(Exception error) => error is UnauthorizedAccessException ? "UNAUTHORIZED" : error is IOException ? "IO" :
                error is InvalidOperationException || error is ArgumentException ? "VALIDATION" : "OTHER";
            public AssetLifecycleProbe(DependencyPin[] expected, Diagnostic diagnostic)
            {
                this.diagnostic = diagnostic;
                Check(expected != null && expected.Length > 0 && expected.All(p => p != null && SafeName(p.path)) &&
                    expected.Select(p => p.path).Distinct().Count() == expected.Length, "JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED");
                declared = expected.ToDictionary(p => p.path, StringComparer.Ordinal);
                Check(declared.Values.All(p => Builtin(p.path) ? p.kind == "builtin" && p.sha256 == "" && p.bytes == 0 :
                    Digest(p.sha256) && p.bytes >= 0 && (p.kind == "asset" && p.path.StartsWith("Assets/", StringComparison.Ordinal) ||
                    p.kind == "package" && Regex.IsMatch(p.packageName ?? "", "^com\\.unity\\.[a-z0-9_.-]+$") && p.path.StartsWith("Packages/" + p.packageName + "/", StringComparison.Ordinal))),
                    "JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED");
                previousDisk = declared.ToDictionary(p => p.Key, p => new DiskState { state = Builtin(p.Key) ? "BUILTIN" : "AVAILABLE", sha256 = p.Value.sha256, bytes = p.Value.bytes }, StringComparer.Ordinal);
            }
            DiskState ReadDisk(DependencyPin pin)
            {
                if (Builtin(pin.path)) return new DiskState { state = "BUILTIN", sha256 = "", bytes = 0 };
                try
                {
                    string physical = pin.path;
                    if (pin.kind == "package")
                    {
                        if (!packages.TryGetValue(pin.packageName, out string packageRoot))
                        {
                            // Package metadata lookup only; no AssetDatabase asset load or refresh.
                            var package = UnityEditor.PackageManager.PackageInfo.FindForAssetPath(pin.path);
                            if (package == null || package.name != pin.packageName || package.version != pin.packageVersion)
                                return new DiskState { state = "ERROR", sha256 = "" };
                            packages.Add(pin.packageName, packageRoot = package.resolvedPath);
                        }
                        physical = Path.Combine(packageRoot, pin.path.Substring(("Packages/" + pin.packageName + "/").Length));
                    }
                    string root = Path.GetFullPath(".").TrimEnd(Path.DirectorySeparatorChar), full = Path.GetFullPath(physical);
                    if (!full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal)) return new DiskState { state = "UNSAFE", sha256 = "" };
                    for (string current = full; current != root; current = Path.GetDirectoryName(current))
                        if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) return new DiskState { state = "UNSAFE", sha256 = "" };
                    var before = new FileInfo(full); long bytes = before.Length, stamp = before.LastWriteTimeUtc.Ticks;
                    string digest = Hash(full); var after = new FileInfo(full);
                    if (after.Length != bytes || after.LastWriteTimeUtc.Ticks != stamp) return new DiskState { state = "ERROR", sha256 = "" };
                    return new DiskState { state = "AVAILABLE", sha256 = digest, bytes = bytes };
                }
                catch (FileNotFoundException) { return new DiskState { state = "MISSING", sha256 = "" }; }
                catch (DirectoryNotFoundException) { return new DiskState { state = "MISSING", sha256 = "" }; }
                catch (UnauthorizedAccessException) { return new DiskState { state = "UNREADABLE", sha256 = "" }; }
                catch (IOException) { return new DiskState { state = "ERROR", sha256 = "" }; }
            }
            public void BindCaptureGate(HashSet<string> dependencies)
            {
                Check(captureGateDependencies == null && dependencies != null && dependencies.All(declared.ContainsKey), "JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED");
                captureGateDependencies = new HashSet<string>(dependencies, StringComparer.Ordinal);
            }
            DirtyDependency Row(DirtyDependency old, string dirty, string transition, DiskState disk) => new DirtyDependency {
                path = old.path, type = old.type, identityState = old.identityState, guid = old.guid, localId = old.localId,
                dirty = dirty, transition = transition, diskState = disk.state, sha256 = disk.sha256, bytes = disk.bytes,
                captureGateMembership = captureGateDependencies == null ? "UNKNOWN" : captureGateDependencies.Contains(old.path) ? "INCLUDED" : "EXCLUDED" };
            public void Observe(string stage)
            {
                var snapshot = new AssetLifecycleSnapshot { sequence = snapshots.Count, stage = stage, preexistingBaseline = !hasBaseline, captureGateBound = captureGateDependencies != null, declaredDependencyCount = declared.Count };
                try
                {
                    Check(Stages.Contains(stage) && !snapshots.Any(row => row.stage == stage), "JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED");
                    var loaded = new Dictionary<string, Loaded>(StringComparer.Ordinal);
                    foreach (var asset in Resources.FindObjectsOfTypeAll<UnityEngine.Object>())
                    {
                        if (!asset || !EditorUtility.IsPersistent(asset)) continue;
                        string path = AssetDatabase.GetAssetPath(asset);
                        if (!declared.ContainsKey(path)) continue;
                        string type = asset.GetType().FullName;
                        Check(type != null && type.Length <= 256 && Regex.IsMatch(type, "^[A-Za-z_][A-Za-z0-9_.+`]*$"), "JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED");
                        bool resolved = false; string guid = ""; long localId = 0;
                        try { resolved = AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out guid, out localId) && Digest(guid, 32); }
                        catch { /* Unresolved identity stays visible; never omit a dirty object. */ }
                        string key = resolved ? "GUID:" + guid + ":" + localId : "INSTANCE:" + asset.GetInstanceID();
                        loaded.Add(key, new Loaded { dirty = EditorUtility.IsDirty(asset), row = new DirtyDependency {
                            path = path, type = type, identityState = resolved ? "RESOLVED" : "UNAVAILABLE", guid = resolved ? guid : "", localId = resolved ? localId : 0 } });
                    }
                    // Only paths implicated by dirty observations are reread here; the existing full
                    // source/1040-dependency gates still independently protect the complete closure.
                    var observed = new HashSet<string>(observedPaths, StringComparer.Ordinal);
                    foreach (string path in loaded.Values.Where(p => p.dirty).Select(p => p.row.path).Concat(previousDirty.Values.Select(p => p.path)))
                    {
                        observed.Add(path);
                        if (declared.ContainsKey(path + ".meta")) observed.Add(path + ".meta");
                    }
                    var disk = new Dictionary<string, DiskState>(previousDisk, StringComparer.Ordinal);
                    foreach (string path in observed) disk[path] = ReadDisk(declared[path]);
                    snapshot.observedPathCount = observed.Count;
                    var dirty = new Dictionary<string, DirtyDependency>(StringComparer.Ordinal);
                    foreach (var pair in loaded.Where(p => p.Value.dirty))
                        dirty.Add(pair.Key, Row(pair.Value.row, "DIRTY", !hasBaseline ? "PREEXISTING" : previousDirty.ContainsKey(pair.Key) ? "RETAINED" : "ENTERED", disk[pair.Value.row.path]));
                    Func<DirtyDependency, string> order = row => row.path + "|" + row.type + "|" + row.guid + "|" + row.localId;
                    snapshot.dirtyDependencies = dirty.Values.OrderBy(order, StringComparer.Ordinal).ToArray();
                    snapshot.clearedDependencies = previousDirty.Where(p => !dirty.ContainsKey(p.Key) && loaded.ContainsKey(p.Key))
                        .Select(p => Row(loaded[p.Key].row, "CLEAN", "CLEARED", disk[p.Value.path])).OrderBy(order, StringComparer.Ordinal).ToArray();
                    snapshot.unobservedDependencies = previousDirty.Where(p => !loaded.ContainsKey(p.Key))
                        .Select(p => Row(p.Value, "NOT_OBSERVED", "UNOBSERVED", disk[p.Value.path])).OrderBy(order, StringComparer.Ordinal).ToArray();
                    snapshot.objectCount = snapshot.dirtyDependencies.Length; snapshot.distinctPathCount = snapshot.dirtyDependencies.Select(p => p.path).Distinct().Count();
                    snapshot.captureGateObjectCount = snapshot.dirtyDependencies.Count(p => p.captureGateMembership == "INCLUDED" && p.identityState == "RESOLVED");
                    snapshot.enteredDirtyCount = snapshot.dirtyDependencies.Count(p => p.transition == "ENTERED");
                    snapshot.retainedDirtyCount = snapshot.dirtyDependencies.Count(p => p.transition == "RETAINED");
                    snapshot.clearedCount = snapshot.clearedDependencies.Length; snapshot.unobservedCount = snapshot.unobservedDependencies.Length;
                    snapshot.diskChanges = disk.Where(p => !Same(p.Value, previousDisk[p.Key])).OrderBy(p => p.Key, StringComparer.Ordinal).Select(p => new DiskChange {
                        path = p.Key, beforeState = previousDisk[p.Key].state, beforeSha256 = previousDisk[p.Key].sha256, beforeBytes = previousDisk[p.Key].bytes,
                        afterState = p.Value.state, afterSha256 = p.Value.sha256, afterBytes = p.Value.bytes }).ToArray();
                    snapshot.diskMismatchCount = disk.Count(p => !Builtin(p.Key) && (p.Value.state != "AVAILABLE" || p.Value.sha256 != declared[p.Key].sha256 || p.Value.bytes != declared[p.Key].bytes));
                    snapshot.diskUnavailableCount = disk.Count(p => p.Value.state != "AVAILABLE" && p.Value.state != "BUILTIN");
                    snapshots.Add(snapshot); diagnostic.lifecycleSnapshots = snapshots.ToArray(); previousDisk = disk; previousDirty = dirty; observedPaths.UnionWith(observed); hasBaseline = true;
                }
                catch (Exception error)
                {
                    snapshot = new AssetLifecycleSnapshot { sequence = snapshots.Count, stage = stage, preexistingBaseline = !hasBaseline,
                        captureGateBound = captureGateDependencies != null, declaredDependencyCount = declared.Count, status = "FAILED", errorCode = SnapshotError(error) };
                    snapshots.Add(snapshot); diagnostic.lifecycleSnapshots = snapshots.ToArray();
                    throw new InvalidOperationException("JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED", error);
                }
            }
            public void Trace(string stage, Action action, bool cleanup = false)
            {
                var errors = new List<Exception>();
                try { Observe(stage + "_BEFORE"); } catch (Exception error) { errors.Add(error); }
                if (!cleanup && errors.Count != 0) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(errors[0]).Throw();
                try { action(); } catch (Exception error) { errors.Add(error); }
                try { Observe(stage + "_AFTER"); } catch (Exception error) { errors.Add(error); }
                if (errors.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(errors[0]).Throw();
                if (errors.Count > 1) throw new AggregateException("Restoration operation and lifecycle observation failed; primary first.", errors);
            }
        }
        static string ErrorClass(Exception error)
        {
            foreach (string code in new[] { "CACHE_PACKAGE_IDENTITY", "CACHE_ASSET_BYTES", "CACHE_META_BYTES", "CACHE_SUBASSET_RELATION",
                "CACHE_FONT_NOT_LOADED", "CACHE_FONT_IDENTITY", "CACHE_FONT_NOT_DYNAMIC", "CACHE_FONT_ATLAS_LINK" })
                if (error.Message == "JOURNEY_WORLD_HUD_" + code) return code;
            if (error.Message == "JOURNEY_WORLD_HUD_DIRTY_DEPENDENCY_PREEXISTING" || error.Message == "JOURNEY_WORLD_HUD_DIRTY_DEPENDENCY_ADDED") return "DIRTY_DEPENDENCY";
            if (error.Message == "JOURNEY_RESTORATION_ASSET_LIFECYCLE_FAILED") return "ASSET_LIFECYCLE";
            if (error.Message == "JOURNEY_RESTORATION_DIAGNOSTIC_SCHEMA_ARGUMENT") return "DIAGNOSTIC_ARGUMENT";
            if (error.Message == "JOURNEY_RESTORATION_IMPORTER_IDENTITY_MISMATCH") return "IMPORTER_IDENTITY";
            if (error.Message == "JOURNEY_RESTORATION_DEPENDENCY_BYTES_MISMATCH") return "DEPENDENCY_BYTES";
            if (error is AggregateException aggregate && aggregate.InnerExceptions.Count > 0) return ErrorClass(aggregate.InnerExceptions[0]);
            if (error is UnauthorizedAccessException) return "UNAUTHORIZED";
            if (error is IOException) return "IO";
            return error is InvalidOperationException || error is ArgumentException ? "VALIDATION" : "OTHER";
        }
        static void PersistDiagnostic(Diagnostic diagnostic)
        {
            string path = Folder + "/restoration-diagnostic.json", temp = path + ".tmp";
            Directory.CreateDirectory(Folder);
            Check(JourneyDiagnosticScope.IsPinnedPathSafe(Folder, out _), "Unsafe diagnostic folder.");
            if (File.Exists(path)) Check(JourneyDiagnosticScope.IsPinnedPathSafe(path, out _), "Unsafe diagnostic file.");
            // Neither names nor exception content are taken from an untrusted file or exception.
            Check(!File.Exists(temp), "Diagnostic temporary file already exists.");
            object payload = diagnostic;
            if (diagnostic.schema == 2)
            {
                var android = JsonUtility.FromJson<AndroidDiagnostic>(JsonUtility.ToJson(diagnostic));
                android.assetLifecycle = diagnostic.lifecycleSnapshots; payload = android;
            }
            byte[] bytes = new System.Text.UTF8Encoding(false).GetBytes(JsonUtility.ToJson(payload, true));
            Check(bytes.Length <= (diagnostic.schema == 2 ? 512 * 1024 : 128 * 1024), "JOURNEY_RESTORATION_DIAGNOSTIC_SIZE_LIMIT");
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write)) stream.Write(bytes, 0, bytes.Length);
            if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
        }
        [Serializable] sealed class StoredFile : FilePin { public long bytes; public long size; }
        [Serializable] sealed class GeneratedReceipt
        {
            public string schema, status, sourceCommit, importRunUrl, unityVersion, sourceStateSha256, nativeManifestSha256, spawnGroundingSha256;
            public bool approved, scopeReusable, visualReviewed, gameplayReviewed, audioAuditioned;
            public StoredFile[] files;
            public StrictReceiptPin[] strictReceipts;
            public JourneyCandidateAssetIntegration.OutputFile[] integrationOutputs;
        }
        [Serializable] sealed class StrictReceiptPin : FilePin { public string kind, nativeXmlSha256; public int nativeCases; }
        [Serializable] sealed class StrictReceipt
        {
            public string status, kind, mode, scope, importCommit, importRunUrl, nativeXmlSha256, contractSha256, protectedSource;
            public bool approved;
            public int nativeCases;
            public StoredFile[] files;
        }
        [Serializable] sealed class TransitionPolicy { public int schema; public string status; public SourceChange[] changes; }
        [Serializable] sealed class SourceState { public StoredFile[] files, restoredFiles; }
        [Serializable] sealed class SourceChange { public string path, beforeSha256, afterSha256; public long beforeBytes, afterBytes; }
        [Serializable] sealed class SourceProof
        {
            public int schema;
            public string label, sourceCommit, producerRunUrl, assetProducerSourceCommit, assetProducerRunUrl;
            public FilePin policy, producerSource, consumerSource;
            public SourceChange[] changes;
            public bool originalAssetsUnchanged, scopeReused;
        }
        [Serializable] sealed class Selection
        {
            public int schema;
            public string spawnRootHeightSource;
            public JourneyCandidateAssetIntegration.Request integration;
        }
        static void Check(bool condition, string reason) { if (!condition) throw new InvalidOperationException(reason); }
        static string Hash(string path) => JourneyDiagnosticScope.HashFile(path);
        static bool Digest(string value, int length = 64) => Regex.IsMatch(value ?? "", "^[a-f0-9]{" + length + "}$");
        static string RepoFile(string name)
        {
            Check(!string.IsNullOrEmpty(name) && !Path.IsPathRooted(name) && !name.Contains("..") && !name.Contains("\\") &&
                (name.StartsWith("tasks/desert-rv/", StringComparison.Ordinal) || name.StartsWith(".github/", StringComparison.Ordinal)), "Unsafe restoration repository path.");
            string root = Path.GetFullPath("../../.."), full = Path.GetFullPath(Path.Combine(root, name));
            Check(full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal) && File.Exists(full), "Restoration input file is missing.");
            for (string path = full; path != root; path = Path.GetDirectoryName(path))
                Check((File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0, "Linked restoration source is forbidden.");
            return full;
        }
        static string Pin(FilePin pin)
        {
            Check(pin != null && Digest(pin.sha256), "Explicit restoration file digest required.");
            string full = RepoFile(pin.path); Check(Hash(full) == pin.sha256, "Restoration source bytes changed: " + pin.path); return full;
        }
        static void BoundPin(FilePin pin, Dictionary<string, FilePin> files)
        {
            Check(pin != null && files.TryGetValue(pin.path, out var expected) && expected.sha256 == pin.sha256, "Restoration evidence not in the full pinned inventory.");
            Pin(pin);
        }
        static Dictionary<string, StoredFile> SourceFiles(SourceState source)
        {
            Check(source != null && source.files != null && source.restoredFiles != null, "Complete source manifest required.");
            var rows = source.files.Concat(source.restoredFiles).ToArray();
            foreach (var row in rows) if (row != null) row.bytes = row.size;
            Check(rows.Length > 100 && rows.All(p => p != null && Digest(p.sha256) && p.bytes >= 0) && rows.Select(p => p.path).Distinct().Count() == rows.Length,
                "Source manifest has missing/duplicate rows.");
            return rows.ToDictionary(p => p.path, StringComparer.Ordinal);
        }
        static void VerifySourceTransition(Request request, GeneratedReceipt generated, Dictionary<string, FilePin> files)
        {
            Check(request.sourceTransitionProof.path == Prefix + Folder + "/restoration-source-proof.json", "Fixed source transition proof required.");
            BoundPin(request.sourceTransitionProof, files);
            var proof = JsonUtility.FromJson<SourceProof>(File.ReadAllText(Pin(request.sourceTransitionProof)));
            Check(proof != null && proof.schema == 1 && proof.label == "REVIEWED_RESTORATION_SOURCE_TRANSITION" &&
                proof.sourceCommit == request.sourceCommit && proof.producerRunUrl == request.producerRunUrl &&
                proof.assetProducerSourceCommit == request.assetProducerSourceCommit && proof.assetProducerRunUrl == request.assetProducerRunUrl && proof.originalAssetsUnchanged && !proof.scopeReused,
                "Reviewed producer-to-consumer source proof identity changed.");
            Check(proof.policy != null && proof.policy.path == (AndroidProducer(request) ? "tasks/desert-rv/art/journey-preparation/android-restoration-transition.json" : "tasks/desert-rv/art/journey-preparation/restoration-transition.json") &&
                proof.producerSource != null && proof.producerSource.path == Prefix + Folder + "/producer-SOURCE-STATE.json" &&
                proof.producerSource.sha256 == generated.sourceStateSha256 && proof.consumerSource != null && proof.consumerSource.path == "tasks/desert-rv/SOURCE-STATE.json",
                "Fixed policy and original/current source manifests required.");
            BoundPin(proof.policy, files); BoundPin(proof.producerSource, files); BoundPin(proof.consumerSource, files);
            var policy = JsonUtility.FromJson<TransitionPolicy>(File.ReadAllText(Pin(proof.policy)));
            Check(policy != null && policy.schema == 1 && policy.status == "REVIEWED_DIAGNOSTIC_RESTORATION_SOURCE_ONLY" && policy.changes != null && proof.changes != null &&
                policy.changes.Select(p => JsonUtility.ToJson(p)).SequenceEqual(proof.changes.Select(p => JsonUtility.ToJson(p))), "Reviewed transition policy and exact source proof differ.");
            var before = SourceFiles(JsonUtility.FromJson<SourceState>(File.ReadAllText(Pin(proof.producerSource))));
            var after = SourceFiles(JsonUtility.FromJson<SourceState>(File.ReadAllText(Pin(proof.consumerSource))));
            Check(proof.changes != null && proof.changes.All(p => p != null) && proof.changes.Select(p => p.path).Distinct().Count() == proof.changes.Length,
                "Exact source change inventory required.");
            var changes = proof.changes.ToDictionary(p => p.path, StringComparer.Ordinal);
            var changed = before.Keys.Union(after.Keys).Where(p => p != proof.policy.path && (!before.ContainsKey(p) || !after.ContainsKey(p) || before[p].sha256 != after[p].sha256 || before[p].bytes != after[p].bytes)).ToArray();
            Check(new HashSet<string>(changed).SetEquals(changes.Keys), "Reviewed source changes differ from actual source manifests.");
            foreach (string path in changed)
            {
                before.TryGetValue(path, out var old); after.TryGetValue(path, out var current); var delta = changes[path];
                Check(delta.beforeSha256 == (old?.sha256 ?? "") && delta.afterSha256 == (current?.sha256 ?? "") &&
                    delta.beforeBytes == (old?.bytes ?? 0) && delta.afterBytes == (current?.bytes ?? 0), "Source transition digest/size differs from reviewed change.");
            }
            foreach (var row in after.Values)
            {
                BoundPin(row, files); Check(new FileInfo(RepoFile(row.path)).Length == row.bytes, "Current source byte count changed.");
            }
        }
        static void VerifyStrictBundles(Request request, GeneratedReceipt generated, Dictionary<string, FilePin> files)
        {
            Check(generated.strictReceipts != null && generated.strictReceipts.Length == 3 && request.integration.candidates != null && request.integration.candidates.Length == 3 &&
                new HashSet<string>(generated.strictReceipts.Select(p => p.kind)).SetEquals(new[] { "armored", "pouncer", "weapon" }), "Three immutable strict producer receipts required.");
            string publicRoot = Path.GetDirectoryName(Path.GetDirectoryName(request.originalGeneratedReceipt.path)).Replace('\\', '/');
            foreach (var pin in generated.strictReceipts)
            {
                Check(pin.path == pin.kind + "/receipt.json" && pin.nativeCases == 26 && Digest(pin.nativeXmlSha256), "Original strict native receipt inventory changed.");
                var receiptPin = new FilePin { path = publicRoot + "/" + pin.path, sha256 = pin.sha256 }; BoundPin(receiptPin, files);
                var receipt = JsonUtility.FromJson<StrictReceipt>(File.ReadAllText(Pin(receiptPin)));
                Check(receipt != null && receipt.kind == pin.kind && receipt.status == "STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED" && !receipt.approved &&
                    receipt.mode == "STRICT_BINDING" && receipt.scope == "FULL_CANDIDATE" && receipt.importCommit == request.assetProducerSourceCommit && receipt.importRunUrl == request.assetProducerRunUrl &&
                    receipt.nativeCases == 26 && receipt.nativeXmlSha256 == pin.nativeXmlSha256 && receipt.protectedSource == "UNCHANGED" && receipt.files != null &&
                    receipt.files.All(p => p != null) && receipt.files.Select(p => p.path).Distinct().Count() == receipt.files.Length,
                    "Original strict receipt does not prove the pinned unapproved full native result.");
                var candidate = request.integration.candidates.Single(p => p.kind == pin.kind);
                Check(candidate.contract != null && candidate.contract.sha256 == receipt.contractSha256 && candidate.importReport != null &&
                    candidate.importReport.path == "JourneyEvidence/CandidateArt/" + pin.kind + "/import-report.json", "Current strict selection disagrees with original receipt.");
                var safeReport = receipt.files.Single(p => p.path == "import-report.json");
                Check(candidate.importReport.sha256 == safeReport.sha256, "Use the actual public safe report digest, never the historical raw report digest.");
                var installedReport = new FilePin { path = Prefix + candidate.importReport.path, sha256 = safeReport.sha256 };
                BoundPin(installedReport, files);
                var report = JsonUtility.FromJson<JourneyCandidateArtImport.Report>(File.ReadAllText(Pin(installedReport)));
                Check(report != null && report.kind == pin.kind && candidate.prefab != null && candidate.prefab.path == report.prefab &&
                    candidate.prefab.dependencyHash == report.dependencyHash && candidate.prefab.dependencySha256 == report.dependencySha256,
                    "Importer identity diagnostics may contain only the three pinned original strict prefab identities.");
                foreach (var row in receipt.files)
                {
                    string path = row.path.StartsWith("CandidateArtImports/", StringComparison.Ordinal) || row.path == "CandidateArtImports.meta" ? "Assets/DesertRV/" + row.path :
                        row.path.StartsWith("OriginalRuntime/", StringComparison.Ordinal) ? "Assets/DesertRV/Runtime/" + row.path.Substring("OriginalRuntime/".Length) : null;
                    if (path == null) continue;
                    BoundPin(new FilePin { path = Prefix + path, sha256 = row.sha256 }, files);
                    Check(new FileInfo(path).Length == row.bytes, "Restored strict byte size differs from immutable producer receipt.");
                }
            }
        }
        static void VerifyInventory(Request request)
        {
            foreach (var pin in request.files) Pin(pin);
            var expected = new HashSet<string>(request.files.Where(p => p.path.StartsWith(Prefix, StringComparison.Ordinal)).Select(p => p.path.Substring(Prefix.Length))
                .Where(p => p.StartsWith("Assets/", StringComparison.Ordinal) || p.StartsWith("Packages/", StringComparison.Ordinal) || p.StartsWith("ProjectSettings/", StringComparison.Ordinal)), StringComparer.Ordinal);
            var actual = new HashSet<string>(StringComparer.Ordinal); var directories = new HashSet<string>(StringComparer.Ordinal);
            string root = Path.GetFullPath("."); var pending = new Stack<string>(new[] { "Assets", "Packages", "ProjectSettings" }.Select(p => Path.Combine(root, p)));
            while (pending.Count > 0)
            {
                string folder = pending.Pop(); Check(Directory.Exists(folder) && (File.GetAttributes(folder) & FileAttributes.ReparsePoint) == 0, "Missing or linked protected folder.");
                foreach (string child in Directory.GetFileSystemEntries(folder))
                {
                    string path = child.Substring(root.Length + 1).Replace('\\', '/'); var flags = File.GetAttributes(child);
                    Check((flags & FileAttributes.ReparsePoint) == 0, "Linked protected input forbidden.");
                    if ((flags & FileAttributes.Directory) != 0) { directories.Add(path); pending.Push(child); }
                    else { Check(File.Exists(child), "Nonregular protected input."); actual.Add(path); }
                }
            }
            Check(actual.SetEquals(expected) && directories.SetEquals(request.directories), "Restored asset/source file or directory inventory changed.");
        }
        static bool SameDependency(DependencyPin a, DependencyPin b) => a != null && b != null && a.path == b.path && a.sha256 == b.sha256 && a.bytes == b.bytes &&
            a.kind == b.kind && a.packageName == b.packageName && a.packageVersion == b.packageVersion;
        static void MatchDependencies(DependencyPin[] actual, DependencyPin[] expected, Diagnostic diagnostic = null)
        {
            Check(actual != null && expected != null && expected.Length > 0 &&
                actual.All(p => p != null) && expected.All(p => p != null) && actual.Select(p => p.path).Distinct().Count() == actual.Length && expected.Select(p => p.path).Distinct().Count() == expected.Length,
                "Complete unique native dependency inventory required.");
            var left = actual.OrderBy(p => p.path, StringComparer.Ordinal).ToArray(); var right = expected.OrderBy(p => p.path, StringComparer.Ordinal).ToArray();
            if (diagnostic != null)
            {
                var indexed = actual.ToDictionary(p => p.path, StringComparer.Ordinal);
                var expectedPaths = new HashSet<string>(expected.Select(p => p.path), StringComparer.Ordinal);
                diagnostic.dependencyExpectedCount = expected.Length;
                diagnostic.dependencyActualCount = actual.Length;
                diagnostic.dependencyAddedCount = indexed.Keys.Count(p => !expectedPaths.Contains(p));
                diagnostic.dependencyMissingCount = expectedPaths.Count(p => !indexed.ContainsKey(p));
                diagnostic.dependencyDifferences = right.Where(p => !indexed.TryGetValue(p.path, out var current) || !SameDependency(current, p)).Take(32)
                    .Select(p => { indexed.TryGetValue(p.path, out var current); return new DependencyDifference { path = p.path, producerSha256 = p.sha256,
                        currentSha256 = current?.sha256 ?? "", producerBytes = p.bytes, currentBytes = current?.bytes ?? 0 }; }).ToArray();
            }
            Check(left.Length == right.Length, "JOURNEY_RESTORATION_DEPENDENCY_BYTES_MISMATCH");
            for (int i = 0; i < left.Length; i++) Check(SameDependency(left[i], right[i]), "JOURNEY_RESTORATION_DEPENDENCY_BYTES_MISMATCH");
        }
        static AssetPin MeasureAsset(AssetPin original)
        {
            Check(original != null && original.path != null && original.path.StartsWith("Assets/DesertRV/", StringComparison.Ordinal) &&
                JourneyDiagnosticScope.IsPinnedPathSafe(original.path, out _) && Digest(original.sha256) && Hash(original.path) == original.sha256, "Installed original asset bytes changed.");
            return new AssetPin { path = original.path, sha256 = original.sha256, dependencyHash = AssetDatabase.GetAssetDependencyHash(original.path).ToString(), dependencySha256 = JourneyContentChecks.DependencySha256(original.path) };
        }
        static IEnumerable<JourneyCandidateAssetIntegration.EnemyPlacement> Rows(JourneyCandidateAssetIntegration.Request r) => r.regions.OrderBy(p => p.region)
            .SelectMany(p => p.guards.Concat(p.roadBeasts).Concat(p.waves.SelectMany(w => w.enemies)));
        static bool VectorEqual(Vector3 a, Vector3 b) => Vector3.Distance(a, b) < .00001f;
        static void MatchGrounding(Request request, JourneyCandidateAssetIntegration.SpawnGroundingReport actual, JourneyCandidateAssetIntegration.SpawnGroundingReport original)
        {
            Check(original != null && original.schema == 1 && original.status == "ACTUAL_NATIVE_ROOT_GROUNDING_UNREVIEWED" && original.sourceCommit == request.assetProducerSourceCommit &&
                original.source == "scene-physical-floor" && original.selectionSha256 == SelectionDigest(request) && !original.approved && original.rows != null && original.rows.Length == 9 &&
                actual.rows != null && actual.rows.Length == 9 && original.rows.Select(p => p.id).Distinct().Count() == 9, "Original nine-root native evidence is incomplete.");
            var old = original.rows.ToDictionary(p => p.id);
            foreach (var row in actual.rows)
                Check(old.TryGetValue(row.id, out var other) && row.kind == other.kind && row.region == other.region && row.scene == other.scene && row.floor == other.floor &&
                    row.layer == other.layer && row.yaw == other.yaw && row.declaredPosition.y == 0 && VectorEqual(row.declaredPosition, other.declaredPosition) &&
                    VectorEqual(row.resolvedPosition, other.resolvedPosition) && VectorEqual(row.hitPoint, other.hitPoint) && VectorEqual(row.hitNormal, other.hitNormal),
                    "Actual physical floor ray differs from the original native grounding evidence.");
        }
        static void WriteFresh(string path, object value)
        {
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(value, true));
        }
        // The pinned GameCI runner forwards GITHUB_SHA but not GITHUB_RUN_ID.
        // The trusted workflow passes this one explicit argument; never infer it from old producer data.
        public static string ParseConsumerRunId(string[] arguments, string expectedRunUrl)
        {
            const string flag = "-journeyRestorationRunId";
            var positions = arguments == null ? Array.Empty<int>() : Enumerable.Range(0, arguments.Length).Where(i => arguments[i] == flag).ToArray();
            Check(positions.Length != 0, "JOURNEY_RESTORATION_RUN_ID_MISSING");
            Check(positions.Length == 1, "JOURNEY_RESTORATION_RUN_ID_DUPLICATE");
            int index = positions[0];
            Check(index + 1 < arguments.Length && Regex.IsMatch(arguments[index + 1] ?? "", "^[1-9][0-9]*$"), "JOURNEY_RESTORATION_RUN_ID_MALFORMED");
            string run = arguments[index + 1];
            Check(expectedRunUrl == "https://github.com/yangerstar1/task-workbench/actions/runs/" + run, "JOURNEY_RESTORATION_RUN_ID_MISMATCH");
            return run;
        }
        static string RunIdentityFailure(Exception error)
        {
            foreach (string code in new[] { "MISSING", "DUPLICATE", "MALFORMED", "MISMATCH" })
                if (error.Message == "JOURNEY_RESTORATION_RUN_ID_" + code) return code;
            return "UNVALIDATED";
        }
        public static void RevalidatePinnedRestoredJourney()
        {
            string commit = Environment.GetEnvironmentVariable("GITHUB_SHA");
            const string diagnosticFlag = "-journeyRestorationDiagnosticSchema";
            var arguments = Environment.GetCommandLineArgs();
            var diagnosticPositions = Enumerable.Range(0, arguments.Length).Where(i => arguments[i] == diagnosticFlag).ToArray();
            // This explicit GameCI custom parameter selects only the diagnostic format, never trust.
            var diagnostic = new Diagnostic { schema = diagnosticPositions.Length == 0 ? 1 : 2, sourceCommit = Digest(commit, 40) ? commit : "", producerRunUrl = "" };
            Exception primary = null;
            try
            {
                Check(diagnosticPositions.Length == 0 || diagnosticPositions.Length == 1 && diagnosticPositions[0] + 1 < arguments.Length &&
                    arguments[diagnosticPositions[0] + 1] == "2", "JOURNEY_RESTORATION_DIAGNOSTIC_SCHEMA_ARGUMENT");
                Revalidate(diagnostic); diagnostic.completed = true; diagnostic.stage = "COMPLETED";
            }
            catch (Exception error)
            {
                primary = error; string identity = RunIdentityFailure(error);
                if (identity != "UNVALIDATED") { diagnostic.runIdentity = identity; diagnostic.errorClass = "RUN_ID_ARGUMENT"; }
                else diagnostic.errorClass = ErrorClass(error);
                throw;
            }
            finally
            {
                try { PersistDiagnostic(diagnostic); }
                catch (Exception persistenceError)
                {
                    if (primary == null) throw;
                    Debug.LogWarning(persistenceError.Message == "JOURNEY_RESTORATION_DIAGNOSTIC_SIZE_LIMIT" ?
                        "JOURNEY_RESTORATION_DIAGNOSTIC_SIZE_LIMIT" : "JOURNEY_RESTORATION_DIAGNOSTIC_WRITE_FAILED");
                }
            }
        }
        static void Revalidate(Diagnostic diagnostic)
        {
            Check(!Application.isPlaying && !BuildPipeline.isBuildingPlayer && Application.unityVersion == "6000.3.19f1", "Pinned native EditMode restoration only.");
            Check(JourneyDiagnosticScope.IsPinnedPathSafe(InputPath, out var reason), reason);
            string requestHash = File.ReadAllText(Folder + "/restoration-input.sha256").Trim();
            Check(Digest(requestHash) && Hash(InputPath) == requestHash, "Host restoration input digest changed.");
            string envHash = Environment.GetEnvironmentVariable("JOURNEY_RESTORATION_INPUT_SHA256");
            Check(string.IsNullOrEmpty(envHash) || envHash == requestHash, "Restoration environment and sidecar disagree.");
            var request = JsonUtility.FromJson<Request>(File.ReadAllText(InputPath));
            string run = ParseConsumerRunId(Environment.GetCommandLineArgs(), request?.producerRunUrl);
            diagnostic.runIdentity = "MATCHED";
            Check(request != null && request.schema == 1 && request.label == "RESTORE_PINNED_JOURNEY_FOR_NATIVE_REVALIDATION" &&
                Digest(request.sourceCommit, 40) && request.sourceCommit == Environment.GetEnvironmentVariable("GITHUB_SHA") &&
                request.producerRunUrl == "https://github.com/yangerstar1/task-workbench/actions/runs/" + run &&
                KnownProducer(request) && (!AndroidProducer(request) || EditorUserBuildSettings.activeBuildTarget == BuildTarget.Android) &&
                request.files != null && request.files.Length > 100 && request.files.All(p => p != null) && request.files.Select(p => p.path).Distinct().Count() == request.files.Length &&
                request.directories != null && request.directories.Distinct().Count() == request.directories.Length, "Current consumer and immutable producer identities required.");
            diagnostic.producerRunUrl = request.producerRunUrl; diagnostic.consumerIdentityMatched = true;
            Check(!File.Exists(ProofPath) && !File.Exists(JourneyCandidatePreparation.Scope), "Restoration proof must be fresh; old live scope is forbidden.");
            var setup = EditorSceneManager.GetSceneManagerSetup();
            Check(!setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty), "Restoration cannot discard existing scene edits.");
            var files = request.files.ToDictionary(p => p.path, StringComparer.Ordinal); Proof proof = null; var failures = new List<Exception>();
            bool dependenciesValidated = false;
            AssetLifecycleProbe lifecycle = null;
            void ObserveStage(string stage, Action action, bool cleanup = false)
            {
                if (lifecycle == null) action(); else lifecycle.Trace(stage, action, cleanup);
            }
            try
            {
                if (AndroidProducer(request))
                {
                    diagnostic.schema = 2;
                    lifecycle = new AssetLifecycleProbe(request.expectedDependencies, diagnostic);
                    lifecycle.Observe("RESTORATION_ENTRY");
                }
                diagnostic.stage = "INVENTORY"; VerifyInventory(request);
                foreach (var pin in new[] { request.selection, request.originalGeneratedReceipt, request.originalNativeManifest, request.originalGrounding }) BoundPin(pin, files);
                Check(request.selection.path == SelectionPath && request.selection.sha256 == SelectionDigest(request) && request.originalGeneratedReceipt.sha256 == request.generatedReceiptSha256,
                    "Pinned original selector and generated producer receipt required.");
                var generated = JsonUtility.FromJson<GeneratedReceipt>(File.ReadAllText(Pin(request.originalGeneratedReceipt)));
                Check(generated != null && generated.schema == "desert-rv-generated-journey/v1" && generated.status == "GENERATED_JOURNEY_SAVED_UNREVIEWED" &&
                    generated.sourceCommit == request.assetProducerSourceCommit && generated.importRunUrl == request.assetProducerRunUrl && generated.unityVersion == Application.unityVersion &&
                    !generated.approved && !generated.scopeReusable && !generated.visualReviewed && !generated.gameplayReviewed && !generated.audioAuditioned &&
                    request.originalNativeManifest.sha256 == generated.nativeManifestSha256 && request.originalGrounding.sha256 == generated.spawnGroundingSha256,
                    "Original generated receipt/provenance is not exact.");
                diagnostic.stage = "SOURCE_PROOF"; VerifySourceTransition(request, generated, files);
                Check(request.integration != null, "Restoration integration selection required.");
                diagnostic.stage = "STRICT_BUNDLES"; VerifyStrictBundles(request, generated, files);
                var native = JsonUtility.FromJson<JourneyCandidatePreparation.AuthoredAssets>(File.ReadAllText(Pin(request.originalNativeManifest)));
                Check(native != null && native.schema == 3 && native.status == "ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED" && native.sourceCommit == request.assetProducerSourceCommit &&
                    native.importRunUrl == request.assetProducerRunUrl && native.unityVersion == Application.unityVersion && !native.approved, "Original native authored inventory required.");
                diagnostic.stage = "DEPENDENCIES"; MatchDependencies(request.expectedDependencies, native.dependencies);
                DependencyPin[] dependencies = null;
                ObserveStage("DEPENDENCIES", () => { dependencies = JourneyCandidatePreparation.DependencySnapshot(); MatchDependencies(dependencies, native.dependencies, diagnostic); dependenciesValidated = true; });
                diagnostic.stage = "GENERATED_BYTES"; var restored = generated.files.Where(p => p.path.StartsWith("Assets/", StringComparison.Ordinal)).ToArray();
                int expectedGenerated = AndroidProducer(request) ? 314 : 75;
                Check(restored.Length == expectedGenerated && restored.Select(p => p.path).Distinct().Count() == expectedGenerated, "Exact immutable producer generated file count required.");
                foreach (var file in restored)
                {
                    var repoPin = new FilePin { path = Prefix + file.path, sha256 = file.sha256 }; BoundPin(repoPin, files);
                    Check(new FileInfo(file.path).Length == file.bytes, "Original generated byte count changed.");
                }
                diagnostic.stage = "SELECTION"; var selector = JsonUtility.FromJson<Selection>(File.ReadAllText(Pin(request.selection)));
                Check(selector != null && selector.schema == 1 && selector.spawnRootHeightSource == "scene-physical-floor" && selector.integration != null && request.integration != null, "Original declared XZ/yaw/zero-Y selection changed.");
                // Compare each typed regional table, including all original zero-height anchors.
                Check(request.integration.regions != null && selector.integration.regions != null && request.integration.regions.Length == 3 &&
                    request.integration.regions.Select(p => JsonUtility.ToJson(p)).SequenceEqual(selector.integration.regions.Select(p => JsonUtility.ToJson(p))), "Regional selection differs from immutable selector.");
                Check(JsonUtility.ToJson(request.integration.weaponCameraPose) == JsonUtility.ToJson(selector.integration.weaponCameraPose) &&
                    JsonUtility.ToJson(request.integration.flashMuzzlePose) == JsonUtility.ToJson(selector.integration.flashMuzzlePose), "Selected weapon/flash pose changed.");
                var integration = JsonUtility.FromJson<JourneyCandidateAssetIntegration.Request>(JsonUtility.ToJson(request.integration));
                Check(integration.sourceCommit == request.sourceCommit && Rows(integration).Count() == 9 && Rows(integration).All(p => p.position.y == 0), "Current request must preserve all nine declared anchors.");
                diagnostic.stage = "POSES"; ObserveStage("POSES", () => JourneyCandidateAssetIntegration.ProposeScenePoses());
                var poses = JsonUtility.FromJson<JourneyCandidateAssetIntegration.ScenePoseProposal>(File.ReadAllText("JourneyEvidence/journey-candidate-poses.json"));
                Check(poses.sourceCommit == request.sourceCommit && !poses.gameplayCameraReviewed && !poses.reticleReviewed && poses.requiredWalkingVerticalFov == 66,
                    "Readonly scene pose proposal must preserve unreviewed 66-degree walking projection.");
                integration.arcModulePose = JourneyCandidateAssetIntegration.ResolveArcModulePose("scene-geometry", integration.arcModulePose, poses.arcModulePose);
                diagnostic.stage = "GROUNDING";
                JourneyCandidateAssetIntegration.SpawnGroundingReport grounding = null;
                ObserveStage("GROUNDING", () => { grounding = JourneyCandidateAssetIntegration.ResolveSpawnRootHeights(integration, "scene-physical-floor", SelectionDigest(request), requestHash); });
                MatchGrounding(request, grounding, JsonUtility.FromJson<JourneyCandidateAssetIntegration.SpawnGroundingReport>(File.ReadAllText(Pin(request.originalGrounding))));
                diagnostic.stage = "IMPORTER_IDENTITIES"; var identities = new List<ImporterIdentity>();
                ObserveStage("IMPORTER_IDENTITIES", () => {
                foreach (var candidate in integration.candidates)
                {
                    var measured = MeasureAsset(candidate.prefab);
                    identities.Add(new ImporterIdentity { kind = candidate.kind, path = candidate.prefab.path, producerDependencyHash = candidate.prefab.dependencyHash,
                        currentDependencyHash = measured.dependencyHash, producerDependencySha256 = candidate.prefab.dependencySha256, currentDependencySha256 = measured.dependencySha256 });
                    diagnostic.importerIdentities = identities.ToArray();
                    Debug.Log("JOURNEY_RESTORATION_IMPORTER_IDENTITY " + JsonUtility.ToJson(identities.Last()));
                }
                if (identities.Any(p => p.producerDependencyHash != p.currentDependencyHash || p.producerDependencySha256 != p.currentDependencySha256))
                {
                    Debug.LogError("JOURNEY_RESTORATION_IMPORTER_IDENTITY_MISMATCH");
                    throw new InvalidOperationException("JOURNEY_RESTORATION_IMPORTER_IDENTITY_MISMATCH");
                }
                });
                Check(generated.integrationOutputs != null && generated.integrationOutputs.Length == 5 && integration.savedInputs != null && integration.savedInputs.Length == 5,
                    "Exactly five immutable scene/content roots required.");
                foreach (var pin in integration.savedInputs)
                {
                    var old = generated.integrationOutputs.Single(p => p.path == pin.path);
                    Check(pin.sha256 == old.sha256 && Hash(pin.path) == old.sha256, "Original generated scene/content root changed.");
                }
                ObserveStage("SAVED_ROOT_IDENTITIES", () => {
                integration.savedInputs = integration.savedInputs.Select(MeasureAsset).ToArray();
                integration.muzzleFlashPrefab = MeasureAsset(integration.muzzleFlashPrefab); integration.arcPresentationPrefab = MeasureAsset(integration.arcPresentationPrefab);
                foreach (var sound in integration.sounds) sound.clip = MeasureAsset(sound.clip);
                });
                diagnostic.stage = "SAVED_BINDINGS"; ObserveStage("SAVED_BINDINGS", () => JourneyCandidateAssetIntegration.VerifyRestoredSavedContent(integration));
                if (AndroidProducer(request)) { diagnostic.stage = "WORLD_HUD_CAPTURE"; JourneySceneAuthoring.CapturePreparedWorldHudObserved(lifecycle.Observe, lifecycle.BindCaptureGate); }
                var outputs = integration.savedInputs.Select(p => new JourneyCandidateAssetIntegration.OutputFile { path = p.path, sha256 = Hash(p.path),
                    dependencyHash = AssetDatabase.GetAssetDependencyHash(p.path).ToString(), dependencySha256 = JourneyContentChecks.DependencySha256(p.path) }).ToArray();
                proof = new Proof { sourceCommit = request.sourceCommit, producerRunUrl = request.producerRunUrl, assetProducerSourceCommit = request.assetProducerSourceCommit, assetProducerRunUrl = request.assetProducerRunUrl,
                    generatedReceiptSha256 = request.generatedReceiptSha256, sourceTransitionProof = request.sourceTransitionProof, requestSha256 = requestHash, unityVersion = Application.unityVersion,
                    sourceBytesUnchanged = true, originalAssetsUnchanged = true, structureValidated = true, productionApprovalRejected = true, approved = false, scopeReused = false,
                    scenes = outputs, dependencies = dependencies, grounding = grounding };
            }
            catch (Exception error) { failures.Add(error); }
            finally
            {
                if (failures.Count == 0) diagnostic.stage = "FINAL_PROTECTION";
                try { ObserveStage("RESTORATION_SCENE_RESTORE", () => JourneySceneAuthoring.RestoreSceneSetup(setup), true); } catch (Exception error) { failures.Add(error); }
                try
                {
                    ObserveStage("FINAL_PROTECTION", () => {
                    VerifyInventory(request);
                    if (dependenciesValidated) MatchDependencies(JourneyCandidatePreparation.DependencySnapshot(), request.expectedDependencies, diagnostic);
                    Check(Hash(InputPath) == requestHash && File.ReadAllText(Folder + "/restoration-input.sha256").Trim() == requestHash && !File.Exists(JourneyCandidatePreparation.Scope), "Restoration input or forbidden live scope changed.");
                    }, true);
                }
                catch (Exception error) { failures.Add(error); }
            }
            if (failures.Count == 1) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failures[0]).Throw();
            if (failures.Count > 1) throw new AggregateException("Restoration revalidation failed, including source/state protection.", failures);
            Check(proof != null, "Native restoration produced no proof.");
            diagnostic.stage = "PROOF"; WriteFresh(ProofPath, proof);
            Debug.Log("RESTORED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED: exact saved bytes, strict bindings, nine original floor rays and production rejection verified; fresh native XML still required.");
        }
    }
}
