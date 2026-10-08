#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Editor
{
    // An ephemeral Editor capability. Never sets acceptance fields or builds a player.
    [InitializeOnLoad]
    public static class JourneyDiagnosticScope
    {
        [Serializable] public sealed class Pin { public string path, sha256, dependencyHash, kind; }
        [Serializable] public sealed class Request
        {
            public string label, sourceCommit;
            public Pin[] files;
        }
        [Serializable] sealed class DiscoveryModel { public string file, dependencyHash; }
        [Serializable] sealed class DiscoveryReceipt
        {
            public string mode, status, contractSha256;
            public string[] failures;
            public DiscoveryModel[] models;
        }
        [Serializable] sealed class ContractFile { public string file, sha256; }
        [Serializable] sealed class ImportContract { public ContractFile[] files; }
        public const string Label = "EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT";
        public static readonly string[] Scenes = {
            "Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity",
            "Assets/DesertRV/Scenes/Journey/FirstStation.unity",
            "Assets/DesertRV/Scenes/Journey/Scrapyard.unity",
            "Assets/DesertRV/Scenes/Journey/NightBeacon.unity"
        };
        static Request request;
        static string requestPath, requestHash, invalidReason;
        static double nextCheck;
        public static bool Active => request != null;
        public static string InvalidReason => invalidReason;
        static JourneyDiagnosticScope()
        {
            EditorApplication.playModeStateChanged += state => {
                if (state == PlayModeStateChange.ExitingPlayMode || state == PlayModeStateChange.EnteredEditMode) Close();
            };
            AssemblyReloadEvents.beforeAssemblyReload += Close;
            EditorApplication.quitting += Close;
            EditorApplication.update += Monitor;
        }
        public static void Close() { request = null; requestPath = requestHash = invalidReason = null; }
        public static bool IsPinnedPathSafe(string path, out string reason)
        {
            reason = null;
            try
            {
                string root = Path.GetFullPath(Directory.GetCurrentDirectory()).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string full = Path.GetFullPath(path);
                var comparison = Path.DirectorySeparatorChar == '\\' ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
                if (!full.StartsWith(root + Path.DirectorySeparatorChar, comparison))
                { reason = "Pinned path escapes project."; return false; }
                string current = full;
                while (current != null)
                {
                    if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                    { reason = "Symlink/reparse point in pinned path chain."; return false; }
                    if (string.Equals(current, root, comparison)) return true;
                    current = Path.GetDirectoryName(current);
                }
                reason = "Pinned path has no project ancestor."; return false;
            }
            catch (Exception error) { reason = "Unreadable pinned path: " + error.GetType().Name; return false; }
        }
        public static string HashFile(string path)
        {
            using (var sha = SHA256.Create()) using (var stream = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }
        static List<string> SourceFiles()
        {
            var result = new List<string>(); var pending = new Stack<string>(); pending.Push("Assets/DesertRV");
            while (pending.Count > 0)
            {
                string directory = pending.Pop();
                if (!IsPinnedPathSafe(directory, out var reason)) throw new IOException(reason);
                foreach (string file in Directory.GetFiles(directory, "*.cs", SearchOption.TopDirectoryOnly))
                {
                    if (!IsPinnedPathSafe(file, out reason)) throw new IOException(reason);
                    result.Add(file.Replace('\\', '/'));
                }
                foreach (string child in Directory.GetDirectories(directory)) pending.Push(child);
            }
            return result;
        }
        public static bool CheckRequest(Request r, string expectedCommit, out string reason)
        {
            reason = null;
            if (r == null || r.label != Label || !Regex.IsMatch(r.sourceCommit ?? "", "^[0-9a-f]{40}$") || r.sourceCommit != expectedCommit || r.files == null)
            { reason = "Explicit diagnostic label, pinned Actions SHA and files are required."; return false; }
            var paths = new HashSet<string>(StringComparer.Ordinal);
            var scenePaths = new HashSet<string>(); var sources = new HashSet<string>();
            int imports = 0, reports = 0;
            foreach (var pin in r.files)
            {
                if (pin == null || string.IsNullOrWhiteSpace(pin.path) || pin.path.Contains("..") || pin.path.Contains("\\") ||
                    Path.IsPathRooted(pin.path) || !(pin.path.StartsWith("Assets/DesertRV/", StringComparison.Ordinal) || pin.path.StartsWith("JourneyEvidence/CandidateArtDiscovery/", StringComparison.Ordinal) || pin.path.StartsWith("JourneyEvidence/CandidateArt/", StringComparison.Ordinal)) ||
                    !paths.Add(pin.path) || !Regex.IsMatch(pin.sha256 ?? "", "^[0-9a-f]{64}$") || !File.Exists(pin.path))
                { reason = "Missing, duplicate or unsafe pinned file."; return false; }
                if (!IsPinnedPathSafe(pin.path, out reason)) return false;
                if (HashFile(pin.path) != pin.sha256)
                { reason = "Changed file hash: " + pin.path; return false; }
                if (pin.kind == "source") sources.Add(pin.path);
                else if (pin.kind == "scene") scenePaths.Add(pin.path);
                else if (pin.kind == "import-report")
                {
                    if (!pin.path.StartsWith("JourneyEvidence/CandidateArt", StringComparison.Ordinal) || !pin.path.EndsWith(".json", StringComparison.Ordinal))
                    { reason = "Import reports must be actual importer JSON artifacts."; return false; }
                    reports++;
                }
                else if (pin.kind == "import-contract")
                {
                    if (!pin.path.EndsWith("/contract.json", StringComparison.Ordinal) && !pin.path.EndsWith("/discovery-contract.json", StringComparison.Ordinal))
                    { reason = "Actual copied source import contract required."; return false; }
                }
                else if (pin.kind == "imported-model")
                {
                    if (!(pin.path.StartsWith("Assets/DesertRV/CandidateArtDiscovery/", StringComparison.Ordinal) || pin.path.StartsWith("Assets/DesertRV/CandidateArtImports/", StringComparison.Ordinal)) ||
                        !pin.path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase) ||
                        !AssetDatabase.LoadAllAssetsAtPath(pin.path).OfType<Mesh>().Any(m => m && m.vertexCount > 0))
                    { reason = "Actual imported FBX geometry required: " + pin.path; return false; }
                    imports++;
                }
                else { reason = "Unknown pin kind."; return false; }
                if (pin.kind == "scene" || pin.kind == "imported-model")
                    if (string.IsNullOrWhiteSpace(pin.dependencyHash) || AssetDatabase.GetAssetDependencyHash(pin.path).ToString() != pin.dependencyHash)
                    { reason = "Changed scene/model dependency hash: " + pin.path; return false; }
            }
            List<string> actualSources;
            try { actualSources = SourceFiles(); }
            catch (IOException error) { reason = error.Message; return false; }
            if (!sources.SetEquals(actualSources) || !scenePaths.SetEquals(Scenes) || imports == 0 || reports == 0)
            { reason = "Pin every current DesertRV C# file, exactly four journey scenes, real imported models and discovery report."; return false; }
            var receipts = new List<DiscoveryReceipt>();
            foreach (var report in r.files.Where(p => p.kind == "import-report"))
            {
                var receipt = JsonUtility.FromJson<DiscoveryReceipt>(File.ReadAllText(report.path));
                if (receipt == null || receipt.failures == null || receipt.failures.Length != 0 ||
                    !(receipt.mode == "DISCOVERY_ONLY" && receipt.status == "discovered-unreviewed-not-bound" || receipt.status == "candidate-structure-imported-unreviewed"))
                { reason = "Successful actual importer report required; it is not approval."; return false; }
                receipts.Add(receipt);
            }
            foreach (var pin in r.files.Where(p => p.kind == "imported-model"))
            {
                int source = pin.path.IndexOf("/Source/", StringComparison.Ordinal);
                if (source < 0) { reason = "Imported model lacks its original Source payload path."; return false; }
                string folder = pin.path.Substring(0, source), file = pin.path.Substring(source + 8);
                string contractPath = folder + (folder.StartsWith("Assets/DesertRV/CandidateArtDiscovery/", StringComparison.Ordinal) ? "/discovery-contract.json" : "/contract.json");
                var contractPin = r.files.FirstOrDefault(p => p.kind == "import-contract" && p.path == contractPath);
                if (contractPin == null || !receipts.Any(rp => rp.contractSha256 == contractPin.sha256))
                { reason = "Model lacks its pinned source contract and matching successful import report: " + pin.path; return false; }
                var contract = JsonUtility.FromJson<ImportContract>(File.ReadAllText(contractPath));
                if (contract == null || contract.files == null || !contract.files.Any(f => f != null && f.file == file && f.sha256 == pin.sha256))
                { reason = "Actual imported FBX bytes do not match original artifact contract: " + pin.path; return false; }
            }
            return true;
        }
        // Prepare an audit request from actual imported/saved bytes, without enabling a session.
        public static void PrepareRequestFromEnvironment()
        {
            if (Application.isPlaying || BuildPipeline.isBuildingPlayer) throw new InvalidOperationException("Prepare in EditMode only.");
            string output = Environment.GetEnvironmentVariable("DESERTRV_DIAGNOSTIC_SCOPE");
            string selection = Environment.GetEnvironmentVariable("DESERTRV_DIAGNOSTIC_MODEL_PATHS");
            if (string.IsNullOrWhiteSpace(output) || string.IsNullOrWhiteSpace(selection) || File.Exists(output))
                throw new InvalidOperationException("Explicit fresh scope path and newline-separated real imported FBX paths required.");
            var pins = new List<Pin>();
            Action<string, string> add = (path, kind) => {
                if (!IsPinnedPathSafe(path, out var error)) throw new IOException(error);
                pins.Add(new Pin { path = path, kind = kind, sha256 = HashFile(path),
                    dependencyHash = kind == "scene" || kind == "imported-model" ? AssetDatabase.GetAssetDependencyHash(path).ToString() : null });
            };
            foreach (string path in SourceFiles().OrderBy(p => p)) add(path, "source");
            foreach (string path in Scenes) add(path, "scene");
            var contracts = new HashSet<string>();
            foreach (string selected in selection.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string path = selected.Trim(); add(path, "imported-model");
                int source = path.IndexOf("/Source/", StringComparison.Ordinal);
                if (source < 0) throw new InvalidOperationException("Expected original Source payload path.");
                string folder = path.Substring(0, source);
                contracts.Add(folder + (folder.StartsWith("Assets/DesertRV/CandidateArtDiscovery/", StringComparison.Ordinal) ? "/discovery-contract.json" : "/contract.json"));
            }
            foreach (string path in contracts) add(path, "import-contract");
            string reports = Environment.GetEnvironmentVariable("DESERTRV_DIAGNOSTIC_IMPORT_REPORTS");
            if (string.IsNullOrWhiteSpace(reports)) throw new InvalidOperationException("Select actual import report paths, one per line.");
            foreach (string path in reports.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)) add(path.Trim(), "import-report");
            var r = new Request { label = Label, sourceCommit = Environment.GetEnvironmentVariable("GITHUB_SHA"), files = pins.ToArray() };
            if (!CheckRequest(r, Environment.GetEnvironmentVariable("GITHUB_SHA"), out var reason)) throw new InvalidOperationException(reason);
            using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(r, true));
        }
        public static void Open(string path)
        {
            if (Active || !Application.isPlaying || BuildPipeline.isBuildingPlayer)
                throw new InvalidOperationException("Diagnostic scope opens only once in Editor PlayMode, never during a player build.");
            var parsed = JsonUtility.FromJson<Request>(File.ReadAllText(path));
            if (!CheckRequest(parsed, Environment.GetEnvironmentVariable("GITHUB_SHA"), out var reason))
                throw new InvalidOperationException(reason);
            requestPath = Path.GetFullPath(path); requestHash = HashFile(path); request = parsed;
            Debug.LogWarning(Label + " source=" + parsed.sourceCommit + "; no asset or gameplay acceptance has been granted.");
        }
        public static bool ValidateCurrent(out string reason)
        {
            reason = invalidReason;
            if (!Active) { reason = "Diagnostic scope is closed."; return false; }
            if (reason != null) return false;
            try
            {
                if (!Application.isPlaying || BuildPipeline.isBuildingPlayer || !File.Exists(requestPath) || HashFile(requestPath) != requestHash)
                    reason = "Diagnostic lifetime or request hash changed.";
                else if (!CheckRequest(request, Environment.GetEnvironmentVariable("GITHUB_SHA"), out reason)) { }
            }
            catch (Exception error) { reason = "Diagnostic hash validation failed: " + error.Message; }
            if (reason != null) { invalidReason = reason; Debug.LogError(Label + " INVALIDATED: " + reason); return false; }
            return true;
        }
        static void Monitor()
        {
            if (!Active || EditorApplication.timeSinceStartup < nextCheck) return;
            nextCheck = EditorApplication.timeSinceStartup + .5;
            if (!ValidateCurrent(out var reason))
            {
                foreach (var recorder in UnityEngine.Object.FindObjectsByType<JourneyInputEvidence>(FindObjectsSortMode.None))
                    recorder.Stop("invalidated: " + reason);
                // Invalid evidence must not keep simulating after the source/content boundary changes.
                EditorApplication.isPaused = true;
            }
        }
        static bool RealMeshes(GameObject root, HashSet<string> imported, out string reason)
        {
            reason = null; int count = 0;
            var meshes = root.GetComponentsInChildren<MeshFilter>(true).Select(f => f.sharedMesh)
                .Concat(root.GetComponentsInChildren<SkinnedMeshRenderer>(true).Select(r => r.sharedMesh));
            foreach (var mesh in meshes)
            {
                if (!mesh || mesh.vertexCount == 0 || !imported.Contains(AssetDatabase.GetAssetPath(mesh)))
                { reason = "Combat renderer uses missing or unpinned/placeholder geometry: " + root.name; return false; }
                count++;
            }
            if (count == 0) reason = "Combat actor has no imported geometry: " + root.name;
            return reason == null;
        }
        public static bool ValidateRegion(RegionBinding region, out string reason)
        {
            if (!ValidateCurrent(out reason)) return false;
            if (!region || !Scenes.Skip(1).Contains(region.gameObject.scene.path))
            { reason = "Diagnostic region is not a pinned saved scene."; return false; }
            if (!region.ValidateStructure(out reason)) return false;
            var imported = new HashSet<string>(request.files.Where(p => p.kind == "imported-model").Select(p => p.path));
            foreach (var enemy in region.AllEnemies())
            {
                if (!RealMeshes(enemy.gameObject, imported, out reason)) return false;
                if (!enemy.animator || !enemy.animator.runtimeAnimatorController || enemy.animator.runtimeAnimatorController.animationClips.Length == 0)
                { reason = "Real animated enemy wiring is required; discovery alone is insufficient."; return false; }
            }
            var weapons = UnityEngine.Object.FindObjectsByType<WeaponPresentation>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            if (weapons.Length != 1 || !weapons[0].enabled || !weapons[0].ValidateBindings(out reason))
            { reason = reason ?? "Exactly one bound real weapon presenter required."; return false; }
            if (!RealMeshes(weapons[0].animator.gameObject, imported, out reason)) return false;
            Debug.LogWarning(Label + " loading structure-valid region " + region.region + "; approval flags remain unchanged.");
            return true;
        }
    }
}
#endif
