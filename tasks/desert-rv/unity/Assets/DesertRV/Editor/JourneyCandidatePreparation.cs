using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Xml;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Editor
{
    // Existing import/capture runs and strict exporters have already succeeded, in this exact project.
    // This entry only composes existing authoring APIs. It never grants approval or invents input events.
    public static class JourneyCandidatePreparation
    {
        const string Folder = "JourneyEvidence/JourneyPreparation";
        const string Input = Folder + "/ready-input.json";
        public const string Scope = "JourneyEvidence/journey-diagnostic-scope.json";
        [Serializable] public sealed class ReadyInput
        {
            public int schema;
            public string status, sourceCommit, arcModulePoseSource, spawnRootHeightSource, selectionSha256;
            public JourneyCandidateAssetIntegration.FxRequest fx;
            public JourneyCandidateAssetIntegration.Request integration;
            public JourneyCandidateAssetIntegration.FilePin[] validatedExportReceipts, validationSourcePins;
            public NativeProof[] nativeProofs;
        }
        [Serializable] public sealed class NativeProof { public string kind; public JourneyCandidateAssetIntegration.FilePin xml; public string[] cases; }
        [Serializable] public sealed class AuthoredAssets
        {
            public int schema = 3;
            public string status = "ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED", sourceCommit, unityVersion, importRunUrl;
            public bool approved;
            public JourneyCandidateAssetIntegration.FilePin spawnGrounding;
            public JourneyCandidateAssetIntegration.FilePin[] files;
            public DependencyPin[] dependencies;
        }
        [Serializable] public sealed class DependencyPin
        {
            public string path, sha256, kind, packageName, packageVersion;
            public long bytes;
        }
        [Serializable] sealed class ExportReceipt
        {
            public string status, importCommit, importRunUrl, kind, contractSha256, nativeXmlSha256;
            public bool approved;
            public int nativeCases;
        }
        static void Check(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
        static string Hash(string path) => JourneyDiagnosticScope.HashFile(path);
        static void WriteFresh(string path, object value)
        {
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream)) writer.Write(JsonUtility.ToJson(value, true));
        }
        static DependencyPin[] DependencySnapshot()
        {
            var result = new List<DependencyPin>();
            // Unity, before exit, enumerates the recursive closure of the four scenes and content manifest.
            foreach (string asset in AssetDatabase.GetDependencies(JourneyDiagnosticScope.Scenes.Concat(new[] { JourneySceneAuthoring.Folder + "/JourneyContent.asset" }).ToArray(), true).OrderBy(p => p, StringComparer.Ordinal))
            {
                Check(!Path.IsPathRooted(asset) && !asset.Contains("..") && !asset.Contains("\\"), "Unsafe native dependency path.");
                if (asset == "Resources/unity_builtin_extra" || asset == "Library/unity default resources")
                {
                    result.Add(new DependencyPin { path = asset, kind = "builtin", sha256 = "", packageName = "", packageVersion = "" });
                    continue;
                }
                string physical = asset, kind = "asset", packageName = "", packageVersion = "";
                if (asset.StartsWith("Packages/", StringComparison.Ordinal))
                {
                    var package = UnityEditor.PackageManager.PackageInfo.FindForAssetPath(asset);
                    Check(package != null && asset.StartsWith("Packages/" + package.name + "/", StringComparison.Ordinal), "Unresolved official package dependency.");
                    packageName = package.name; packageVersion = package.version; kind = "package";
                    physical = Path.Combine(package.resolvedPath, asset.Substring(("Packages/" + package.name + "/").Length));
                }
                else Check(asset.StartsWith("Assets/", StringComparison.Ordinal), "Unknown native dependency location.");
                foreach (string suffix in new[] { "", ".meta" })
                {
                    Check(File.Exists(physical + suffix), "Missing dependency bytes/meta: " + asset + suffix);
                    result.Add(new DependencyPin { path = asset + suffix, kind = kind, sha256 = Hash(physical + suffix),
                        bytes = new FileInfo(physical + suffix).Length, packageName = packageName, packageVersion = packageVersion });
                }
            }
            return result.OrderBy(p => p.path, StringComparer.Ordinal).ToArray();
        }
        public static void PrepareVerifiedSameWorkspace()
        {
            var timer = System.Diagnostics.Stopwatch.StartNew(); double previousSeconds = 0;
            void MarkPhase(string stage)
            {
                double seconds = timer.Elapsed.TotalSeconds;
                Debug.Log("JOURNEY_PREPARATION_PHASE_COMPLETED stage=" + stage + "; seconds=" +
                    (seconds - previousSeconds).ToString("F3", System.Globalization.CultureInfo.InvariantCulture) + "; totalSeconds=" +
                    seconds.ToString("F3", System.Globalization.CultureInfo.InvariantCulture));
                previousSeconds = seconds;
            }
            Check(!Application.isPlaying && !BuildPipeline.isBuildingPlayer && Application.unityVersion == "6000.3.19f1", "Explicit pinned native EditMode preparation required.");
            Check(JourneyDiagnosticScope.IsPinnedPathSafe(Input, out string reason), reason);
            string inputHash = File.ReadAllText(Folder + "/ready-input.sha256").Trim();
            Check(Regex.IsMatch(inputHash, "^[a-f0-9]{64}$") && Hash(Input) == inputHash, "Actual same-job ready input hash missing/changed.");
            var input = JsonUtility.FromJson<ReadyInput>(File.ReadAllText(Input));
            Check(input != null && input.schema == 1 && input.status == "THREE_NATIVE_STRICT_EXPORTS_VERIFIED_NOT_APPROVED" &&
                input.sourceCommit == Environment.GetEnvironmentVariable("GITHUB_SHA") && Regex.IsMatch(input.sourceCommit ?? "", "^[a-f0-9]{40}$"), "Same-job strict readiness is absent.");
            Check(input.integration != null && input.fx != null && input.integration.candidates != null && input.integration.candidates.Length == 3 &&
                input.validatedExportReceipts != null && input.validatedExportReceipts.Length == 3, "All three actual strict exports required.");
            Check(input.arcModulePoseSource == "scene-geometry" || input.arcModulePoseSource == "selection", "Explicit pinned arc pose source required.");
            Check(input.spawnRootHeightSource == "scene-physical-floor" && Regex.IsMatch(input.selectionSha256 ?? "", "^[a-f0-9]{64}$"), "Explicit native root grounding intent and original selection hash required.");
            var kinds = new[] { "armored", "pouncer", "weapon" };
            Check(new HashSet<string>(input.integration.candidates.Select(c => c.kind)).SetEquals(kinds), "Three independent strict kinds required.");
            string repo = Path.GetFullPath("../../.."), run = null;
            Check(input.validationSourcePins != null && input.validationSourcePins.Length > 4 && input.nativeProofs != null && input.nativeProofs.Length == 3,
                "Actual validator/test source version and native XML inventories required.");
            foreach (var pin in input.validationSourcePins)
            {
                Check(!pin.path.Contains("..") && !pin.path.Contains("\\") && !Path.IsPathRooted(pin.path) &&
                    (pin.path.StartsWith("tasks/desert-rv/art/import-candidate/", StringComparison.Ordinal) && pin.path.EndsWith(".py", StringComparison.Ordinal) ||
                     pin.path.StartsWith("tasks/desert-rv/unity/Assets/DesertRV/Tests/CandidateArt/", StringComparison.Ordinal) && pin.path.EndsWith(".cs", StringComparison.Ordinal)), "Invalid validation source path.");
                Check(Hash(Path.Combine(repo, pin.path)) == pin.sha256, "Current strict validation/test version changed.");
            }
            foreach (string kind in kinds)
            {
                string path = "tasks/desert-rv/journey-preparation-export/" + kind + "/receipt.json";
                var pins = input.validatedExportReceipts.Where(p => p.path == path).ToArray(); Check(pins.Length == 1, "Exact validated exporter receipt selection required.");
                string full = Path.Combine(repo, path);
                Check(File.Exists(full) && Hash(full) == pins[0].sha256, "Validated exporter receipt changed.");
                var receipt = JsonUtility.FromJson<ExportReceipt>(File.ReadAllText(full));
                var selected = input.integration.candidates.Single(c => c.kind == kind);
                Check(receipt != null && receipt.status == "STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED" && !receipt.approved &&
                    receipt.kind == kind && receipt.importCommit == input.sourceCommit && receipt.contractSha256 == selected.contract.sha256 &&
                    Regex.IsMatch(receipt.importRunUrl ?? "", "^https://github\\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*$"), "Exporter did not establish current unapproved full native success.");
                Check(run == null || run == receipt.importRunUrl, "All strict passes must be from this same hosted job/run."); run = receipt.importRunUrl;
                var proof = input.nativeProofs.Single(p => p.kind == kind);
                Check(proof.xml != null && proof.xml.path.StartsWith("tasks/desert-rv/artifacts/journey-strict-" + kind + "/", StringComparison.Ordinal) &&
                    !proof.xml.path.Contains("..") && !proof.xml.path.Contains("\\") && proof.xml.path.EndsWith(".xml", StringComparison.Ordinal) &&
                    proof.xml.sha256 == receipt.nativeXmlSha256 && Hash(Path.Combine(repo, proof.xml.path)) == proof.xml.sha256, "Actual validated native XML changed.");
                var xml = new XmlDocument { XmlResolver = null }; xml.Load(Path.Combine(repo, proof.xml.path));
                var cases = xml.SelectNodes("//test-case").Cast<XmlNode>().ToArray();
                var names = cases.Select(c => c.Attributes["fullname"]?.Value).ToArray();
                Check(xml.DocumentElement.Name == "test-run" && xml.DocumentElement.GetAttribute("result") == "Passed" &&
                    proof.cases != null && cases.Length > 0 && cases.Length == receipt.nativeCases && proof.cases.Length == cases.Length &&
                    names.All(n => !string.IsNullOrWhiteSpace(n)) && names.Distinct().Count() == names.Length &&
                    cases.All(c => c.Attributes["result"]?.Value == "Passed") && new HashSet<string>(names).SetEquals(proof.cases),
                    "Exact native inventory differs from the current strict exporter's version-pinned result.");
                Check(Hash(selected.importReport.path) == selected.importReport.sha256 && Hash(selected.contract.path) == selected.contract.sha256 &&
                    JourneyContentChecks.DependencySha256(selected.prefab.path) == selected.prefab.dependencySha256 &&
                    AssetDatabase.GetAssetDependencyHash(selected.prefab.path).ToString() == selected.prefab.dependencyHash,
                    "Actual imported prefab/report changed after strict export. No copied-asset reimport fallback.");
            }
            Check(!File.Exists(Scope), "Never overwrite a previously pinned scope.");
            MarkPhase("input-and-three-strict-proofs");
            var saved = new Dictionary<string, string>();
            void Set(string key, string value) { if (!saved.ContainsKey(key)) saved[key] = Environment.GetEnvironmentVariable(key); Environment.SetEnvironmentVariable(key, value); }
            try
            {
                JourneySceneAuthoring.AuthorCandidateScenes(); MarkPhase("four-scene-authoring");
                JourneyCandidateAssetIntegration.ProposeScenePoses(); MarkPhase("actual-scene-pose-proposal");
                var poses = JsonUtility.FromJson<JourneyCandidateAssetIntegration.ScenePoseProposal>(File.ReadAllText("JourneyEvidence/journey-candidate-poses.json"));
                input.fx.sourceCommit = input.sourceCommit;
                string fxSelection = Folder + "/fx-selection.json", fxInput = Folder + "/fx-input.json";
                WriteFresh(fxSelection, input.fx);
                Set("DESERTRV_JOURNEY_FX_SELECTION", fxSelection); Set("DESERTRV_JOURNEY_FX_SELECTION_SHA256", Hash(fxSelection)); Set("DESERTRV_JOURNEY_FX_INPUT", fxInput);
                JourneyCandidateAssetIntegration.FreezeSelectedFxInputFromEnvironment(); Set("DESERTRV_JOURNEY_FX_INPUT_SHA256", Hash(fxInput));
                JourneyCandidateAssetIntegration.AuthorFxFromEnvironment(); MarkPhase("fx-authoring-and-stable-save");
                var fx = JsonUtility.FromJson<JourneyCandidateAssetIntegration.FxResult>(File.ReadAllText("JourneyEvidence/journey-candidate-fx.json"));
                Check(fx.status == "ORIGINAL_NATIVE_FX_AUTHORED_UNCALIBRATED" && fx.protectedSourcesUnchanged && fx.failures.Length == 0 && !fx.visualCalibrated && !fx.audioAuditioned && !fx.gameplayReviewed, "Actual original FX authoring did not finish.");
                input.integration.sourceCommit = input.sourceCommit;
                input.integration.muzzleFlashPrefab = fx.muzzleFlashPrefab; input.integration.arcPresentationPrefab = fx.arcPresentationPrefab;
                // The host pinned the raw JSON null/object intent before Unity inline DTO deserialization.
                input.integration.arcModulePose = JourneyCandidateAssetIntegration.ResolveArcModulePose(input.arcModulePoseSource, input.integration.arcModulePose, poses.arcModulePose);
                var grounding = JourneyCandidateAssetIntegration.ResolveSpawnRootHeights(input.integration, input.spawnRootHeightSource, input.selectionSha256, inputHash);
                WriteFresh(JourneyCandidateAssetIntegration.SpawnGroundingPath, grounding);
                string groundingSha = Hash(JourneyCandidateAssetIntegration.SpawnGroundingPath); MarkPhase("nine-actual-root-grounding-records");
                string selection = Folder + "/integration-selection.json", frozen = Folder + "/integration-input.json";
                WriteFresh(selection, input.integration);
                Set("DESERTRV_JOURNEY_ASSET_SELECTION", selection); Set("DESERTRV_JOURNEY_ASSET_SELECTION_SHA256", Hash(selection)); Set("DESERTRV_JOURNEY_ASSET_INPUT", frozen);
                JourneyCandidateAssetIntegration.FreezeSelectedInputsFromEnvironment(); Set("DESERTRV_JOURNEY_ASSET_INPUT_SHA256", Hash(frozen)); MarkPhase("freeze-integration-input");
                JourneyCandidateAssetIntegration.IntegrateFromEnvironment();
                var integrated = JsonUtility.FromJson<JourneyCandidateAssetIntegration.Result>(File.ReadAllText(JourneyCandidateAssetIntegration.ReportPath));
                Check(integrated.status == JourneyCandidateAssetIntegration.Label && integrated.protectedSourcesUnchanged && integrated.failures.Length == 0 && !integrated.rolledBack &&
                    !integrated.visualReviewed && !integrated.gameplayReviewed && !integrated.audioAuditioned, "Real saved scene integration is not ready.");
                MarkPhase("integration-save-reload-and-production-rejection");
                Set("DESERTRV_DIAGNOSTIC_SCOPE", Scope);
                Set("DESERTRV_DIAGNOSTIC_MODEL_PATHS", string.Join("\n", input.integration.candidates.Select(c => c.sourceModelPath)));
                Set("DESERTRV_DIAGNOSTIC_IMPORT_REPORTS", string.Join("\n", input.integration.candidates.Select(c => c.importReport.path)));
                JourneyDiagnosticScope.PrepareRequestFromEnvironment();
                var scope = JsonUtility.FromJson<JourneyDiagnosticScope.Request>(File.ReadAllText(Scope));
                Check(JourneyDiagnosticScope.CheckRequest(scope, input.sourceCommit, out reason), reason);
                Check(Hash(Input) == inputHash, "Preparation input changed during authoring.");
                Check(Hash(JourneyCandidateAssetIntegration.SpawnGroundingPath) == groundingSha, "Actual native grounding evidence changed during integration.");
                MarkPhase("diagnostic-scope-and-source-recheck");
                var authored = Directory.GetFiles(JourneySceneAuthoring.Folder, "*", SearchOption.AllDirectories).Concat(new[] { JourneySceneAuthoring.Folder + ".meta" }).OrderBy(p => p).ToArray();
                WriteFresh(Folder + "/authored-assets.json", new AuthoredAssets { sourceCommit = input.sourceCommit,
                    unityVersion = Application.unityVersion, importRunUrl = run, approved = false,
                    files = authored.Select(p => new JourneyCandidateAssetIntegration.FilePin { path = p.Replace('\\', '/'), sha256 = Hash(p) }).ToArray(),
                    dependencies = DependencySnapshot(),
                    spawnGrounding = new JourneyCandidateAssetIntegration.FilePin { path = JourneyCandidateAssetIntegration.SpawnGroundingPath, sha256 = groundingSha } });
                MarkPhase("native-authored-file-and-dependency-manifest");
                Debug.Log("JOURNEY_SAME_WORKSPACE_SCOPE_PREPARED_UNREVIEWED: no input plan, runtime session or approval has been manufactured.");
            }
            finally { foreach (var pair in saved) Environment.SetEnvironmentVariable(pair.Key, pair.Value); }
        }
    }
}
