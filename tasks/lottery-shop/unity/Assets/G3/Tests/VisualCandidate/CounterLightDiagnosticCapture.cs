using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;
using Stopwatch = System.Diagnostics.Stopwatch;

namespace Lottery.G3.VisualCandidate.Tests
{
    // OPT-IN DIAGNOSTIC. This file creates no NUnit case and changes no production asset.
    // All renders run synchronously inside the already captured pending-phone frame.
    internal static class CounterLightDiagnosticCapture
    {
        const string Scope = "DIAGNOSTIC_COUNTER_LIGHT_NOT_ART_APPROVAL_NOT_G3_PASS";
        internal static readonly string[] Cases = {
            "pendant-zero", "boardwash-zero", "counter-pair-zero", "daylight-zero",
            "reading-zero", "shelf-zero", "all-direct-zero", "probe-intensity-zero",
            "global-reflection-zero", "reflection-controls-zero", "ambient-sh-zero",
            "counter-and-reflection-controls-zero", "oak-specular-highlights-off",
            "oak-normal-flat", "oak-roughness-one", "oak-texture-only", "oak-target-mask"
        };
        static readonly string[] Names = { "Soft window daylight", "Warm counter pendant",
            "Table reading pendant", "Shelf ambient fill", "Counter board wash" };
        static readonly float[] Expected = { .6f, 1.15f, 1.6f, .55f, .06f };
        static readonly LightShadows[] ExpectedShadows = { LightShadows.Soft, LightShadows.Soft,
            LightShadows.Soft, LightShadows.None, LightShadows.None };
        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            var indices = Enumerable.Range(0, a.Length).Where(i => a[i] == name).ToArray();
            Require(indices.Length <= 1, "DUPLICATE_DIAGNOSTIC_ARGUMENT");
            if(indices.Length == 0) return "";
            Require(indices[0] + 1 < a.Length, "MISSING_DIAGNOSTIC_ARGUMENT_VALUE");
            return a[indices[0] + 1];
        }
        internal static bool IsRequested()
        {
            string value = Arg("-counterLightDiagnostic");
            Require(value == "" || value == "1", "DIAGNOSTIC_FLAG_MUST_BE_ONE");
            Require(value == "1" || Arg("-counterLightDiagnosticFault") == "", "FAULT_REQUIRES_DIAGNOSTIC");
            return value == "1";
        }
        internal static void Run(G3ShopEnvironment environment, Camera camera, RenderTexture target,
            string normalOutput, string normalPngSha256, string storeDirectory, Func<string> unchanged)
        {
            Require(IsRequested(), "DIAGNOSTIC_NOT_REQUESTED");
            new Session(environment, camera, target, normalOutput, normalPngSha256, storeDirectory, unchanged).Execute();
        }
        static void Require(bool ok, string code) { if(!ok) throw new InvalidOperationException(code); }
        static string Hash(string text) => StateCodec.HashBytes(Encoding.UTF8.GetBytes(text));
        static string Id(Object o) => o == null ? "null" : o.GetInstanceID().ToString(CultureInfo.InvariantCulture);
        static string Serialized(Object o)
        {
#if UNITY_EDITOR
            return o == null ? "null" : UnityEditor.EditorJsonUtility.ToJson(o);
#else
            throw new InvalidOperationException("DIAGNOSTIC_EDITOR_ONLY");
#endif
        }
        static void Attempt(Action action, List<Exception> errors)
        { try { action(); } catch(Exception e) { errors.Add(e); } }
        static void ThrowIfAny(List<Exception> errors)
        { if(errors.Count > 0) throw new AggregateException("Counter light diagnostic failed; no normal continuation", errors); }

        sealed class Session
        {
            const long BudgetMs = 180000;
            readonly G3ShopEnvironment environment;
            readonly UniversalAdditionalCameraData urp;
            readonly string urpSerialized;
            readonly Camera[] cameraStack;
            readonly Transform volumeTrigger;
            readonly CameraReceipt cameraBefore;
            readonly ControlledTransform[] transforms;
            readonly string rendererIds, lightIds, probeIds, transformIds;
            readonly List<RenderTexture> ownedTargets = new List<RenderTexture>();
            readonly Camera camera;
            readonly RenderTexture target, initialActive;
            readonly Func<string> unchanged;
            readonly string storeDirectory, normalSha, root, originalInvariant, originalDisk;
            readonly Light[] lights;
            readonly float[] intensities;
            readonly ReflectionProbe probe;
            readonly float probeIntensity, reflectionIntensity;
            readonly SphericalHarmonicsL2 ambient;
            readonly AmbientMode ambientMode;
            readonly float ambientIntensity;
            readonly Color ambientSky, ambientEquator, ambientGround, ambientAlias;
            readonly Renderer[] renderers;
            readonly Material[][] bindings;
            readonly Material[] originalMaterials;
            readonly string[] materialStates;
            readonly Renderer oak;
            readonly Material oakMaterial;
            readonly List<Material> owned = new List<Material>();
            readonly int frame;
            readonly string originalCamera, originalGuard, fault;
            readonly Stopwatch timer = Stopwatch.StartNew();
            readonly Receipt receipt;
            string stage = "PRECONDITION";
            bool faultConsumed;

            public Session(G3ShopEnvironment env, Camera c, RenderTexture t, string output, string sha,
                string directory, Func<string> state)
            {
                Require(Application.isPlaying && Application.isEditor, "DIAGNOSTIC_EDITOR_PLAYMODE_ONLY");
                environment = env; camera = c; target = t; normalSha = sha; storeDirectory = directory; unchanged = state;
                Require(env != null && c != null && t != null && state != null, "MISSING_DIAGNOSTIC_INPUT");
                Require(t.width == 1280 && t.height == 720 && t.format == RenderTextureFormat.ARGB32 && c.targetTexture == t,
                    "DIAGNOSTIC_REQUIRES_EXISTING_1280_720_LDR_TARGET");
                urp = c.GetComponent<UniversalAdditionalCameraData>();
                Require(urp != null && !c.orthographic && !urp.renderPostProcessing, "CAMERA_MODE_DRIFT");
                Require(QualitySettings.activeColorSpace == ColorSpace.Gamma, "COLOR_SPACE_DRIFT");
                Require(System.Text.RegularExpressions.Regex.IsMatch(sha ?? "", "\\A[0-9a-f]{64}\\z"), "INVALID_NORMAL_FRAME_SHA");
                string run = Arg("-probeRunId"), attempt = Arg("-probeRunAttempt"), commit = Arg("-probeCommit");
                Require(System.Text.RegularExpressions.Regex.IsMatch(run, "\\A[1-9][0-9]{0,19}\\z") &&
                    System.Text.RegularExpressions.Regex.IsMatch(attempt, "\\A[1-9][0-9]{0,19}\\z") &&
                    System.Text.RegularExpressions.Regex.IsMatch(commit, "\\A[0-9a-f]{40}\\z"), "INVALID_SOURCE_RUN_IDENTITY");
                root = Path.GetFullPath(Path.Combine(output, "../../counter-light-diagnostic", "run-" + run + "-attempt-" + attempt));
                Require(!Directory.Exists(root), "DIAGNOSTIC_OUTPUT_ALREADY_EXISTS");
                Require(Path.GetFileName(Path.GetFullPath(output)) == "captures", "UNEXPECTED_NORMAL_OUTPUT");
                fault = Arg("-counterLightDiagnosticFault");
                Require(fault == "" || Cases.SelectMany(x => new[] { x+":after-mutation", x+":before-capture", x+":after-png", x+":before-receipt" }).Contains(fault) ||
                    new[] {"negative:camera-target", "negative:material-slot", "negative:probe-transform", "negative:urp-camera"}.Contains(fault),
                    "UNSUPPORTED_FAULT_REQUEST");
                var found = env.GetComponentsInChildren<Light>(true);
                Require(found.Length == Names.Length, "LIGHT_INVENTORY_DRIFT");
                lights = Names.Select(name => found.Single(l => l.name == name)).ToArray();
                intensities = lights.Select(l => l.intensity).ToArray();
                for(int i = 0; i < lights.Length; i++)
                    Require(lights[i].isActiveAndEnabled && Mathf.Abs(intensities[i] - Expected[i]) < .000001f &&
                        lights[i].type == (i == 0 ? LightType.Directional : LightType.Spot), "DAY_LIGHT_BASELINE_DRIFT");
                Require(Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Count(l => l.isActiveAndEnabled) == 5, "EXTRA_ACTIVE_LIGHT");
                Require(lights.Select(l => l.shadows).SequenceEqual(ExpectedShadows), "TABLE_KEY_SHADOW_BASELINE_DRIFT");
                probe = env.GetComponentsInChildren<ReflectionProbe>(true).Single();
                Require(probe.name == "Shop material reflection" && probe.mode == ReflectionProbeMode.Custom &&
                    probe.customBakedTexture != null && probe.isActiveAndEnabled, "REFLECTION_BASELINE_DRIFT");
                probeIntensity = probe.intensity; reflectionIntensity = RenderSettings.reflectionIntensity; ambient = RenderSettings.ambientProbe;
                ambientMode = RenderSettings.ambientMode; ambientIntensity = RenderSettings.ambientIntensity;
                ambientSky = RenderSettings.ambientSkyColor; ambientEquator = RenderSettings.ambientEquatorColor;
                ambientGround = RenderSettings.ambientGroundColor; ambientAlias = RenderSettings.ambientLight;
                Require(ambientMode == AmbientMode.Trilight && !float.IsNaN(ambientIntensity) && !float.IsInfinity(ambientIntensity) &&
                    ambientIntensity >= 0 && ambientIntensity <= 8 && ambientAlias.Equals(ambientSky), "AMBIENT_BASELINE_MODE_OR_ALIAS_DRIFT");
                Require(ambientSky.Equals(new Color(.612f, .666f, .72f)) && ambientEquator.Equals(new Color(.522f, .513f, .459f)) &&
                    ambientGround.Equals(new Color(.306f, .279f, .234f)), "AMBIENT_TRILIGHT_BASELINE_DRIFT");
                Require(Mathf.Abs(probeIntensity - .85f) < .000001f && reflectionIntensity == 1f && RenderSettings.sun == lights[0],
                    "DAY_REFLECTION_BASELINE_DRIFT");
                renderers = env.GetComponentsInChildren<Renderer>(true).OrderBy(r => r.GetInstanceID()).ToArray();
                bindings = renderers.Select(r => r.sharedMaterials.ToArray()).ToArray();
                originalMaterials = bindings.SelectMany(x => x).Where(m => m != null).Distinct().ToArray();
                materialStates = originalMaterials.Select(Serialized).ToArray();
                var oakCandidates = renderers.Where(r => r.name == "Warm_Oak" && r.sharedMaterials.Length == 1 &&
                    r.sharedMaterial != null && r.sharedMaterial.name == "Warm_Oak").ToArray();
                Require(oakCandidates.Length == 1, "MERGED_OAK_TARGET_NOT_UNIQUE");
                oak = oakCandidates[0]; oakMaterial = oak.sharedMaterial;
                Require(oakMaterial.shader.name == "Universal Render Pipeline/Lit" && !oak.HasPropertyBlock(), "OAK_SHADER_OR_PROPERTY_BLOCK_DRIFT");
                Require(new[] {"_BaseMap", "_BaseColor", "_BumpScale", "_Smoothness", "_SpecularHighlights"}.All(oakMaterial.HasProperty),
                    "OAK_PROPERTIES_MISSING");
                Require(oakMaterial.GetTexture("_BaseMap") != null && oakMaterial.GetFloat("_Metallic") == 0 &&
                    !oakMaterial.IsKeywordEnabled("_EMISSION"), "OAK_AUTHORING_DRIFT");
                Require(Shader.Find("Universal Render Pipeline/Unlit") != null, "UNLIT_DIAGNOSTIC_SHADER_MISSING");
                initialActive = RenderTexture.active; frame = Time.frameCount;
                Require(urp.renderType == CameraRenderType.Base && urp.cameraStack != null, "DIAGNOSTIC_BASE_CAMERA_REQUIRED");
                urpSerialized = Serialized(urp); cameraStack = urp.cameraStack.ToArray(); volumeTrigger = urp.volumeTrigger;
                transforms = env.GetComponentsInChildren<Transform>(true).Concat(new[] {camera.transform}).Distinct()
                    .OrderBy(t => Depth(t)).Select(t => new ControlledTransform(t)).ToArray();
                rendererIds = Membership<Renderer>(); lightIds = Membership<Light>(); probeIds = Membership<ReflectionProbe>(); transformIds = Membership<Transform>();
                cameraBefore = CameraObservation();
                originalInvariant = unchanged(); originalDisk = DiskFingerprint(); originalCamera = CameraState(); originalGuard = GuardState();
                receipt = new Receipt { sourceCommit = commit, runId = run, runAttempt = attempt, expectedNormalPngSha256 = sha,
                    frameCount = frame, camera = CameraObservation(), colorSpace = QualitySettings.activeColorSpace.ToString(),
                    graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(), unityVersion = Application.unityVersion,
                    initialControls = Controls(), diagnosticOptIn = true, stateBeforeSha256 = Hash(originalInvariant), diskBeforeSha256 = originalDisk,
                    sceneBeforeSha256 = Hash(originalGuard), materialBeforeSha256 = Hash(string.Join("\n", materialStates)),
                    oakRendererInstanceId = oak.GetInstanceID(), oakMaterialInstanceId = oakMaterial.GetInstanceID(),
                    oakShader = oakMaterial.shader.name, oakBaseMap = oakMaterial.GetTexture("_BaseMap").name,
                    oakBaseColor = oakMaterial.GetColor("_BaseColor"), faultRequest = fault,
                    oakMaterialCoverage = "ALL_MERGED_WARM_OAK_GEOMETRY_NOT_FASCIA_ONLY" };
                receipt.initialControlsJson = JsonUtility.ToJson(receipt.initialControls);
                receipt.initialControlsSha256 = Hash(receipt.initialControlsJson);
            }

            public void Execute()
            {
                // Nothing above this point mutates lighting, binding, material or state.
                Directory.CreateDirectory(root);
                var errors = new List<Exception>();
                try
                {
                    stage = "BASELINE_BEFORE"; WriteReceipt(); RequireUnchanged();
                    InjectStateNegative(); RequireUnchanged();
                    var before = Capture("baseline-before", true); receipt.baselineBeforeSha256 = before.sha256;
                    Require(before.sha256 == normalSha, "NORMAL_TO_DIAGNOSTIC_BASELINE_PIXEL_MISMATCH");
                    WriteReceipt();
                    foreach(string id in Cases) RunCase(id);
                    Require(fault == "" || faultConsumed, "FAULT_NOT_EXERCISED");
                }
                catch(Exception e) { errors.Add(e); receipt.failureCode = stage; }
                finally
                {
                    Restore(errors); // Must run even when the clock is already over budget.
                    int beforeProperties = errors.Count;
                    Attempt(() => RequireUnchanged(), errors);
                    receipt.propertiesRestored = errors.Count == beforeProperties;
                    if(WithinBudget())
                        Attempt(() => {
                            var after = Capture("baseline-after", true); receipt.baselineAfterSha256 = after.sha256;
                            Require(after.sha256 == normalSha, "FINAL_RESTORED_PIXEL_MISMATCH");
                            RequireUnchanged(); CheckBudget(); receipt.restored = true;
                        }, errors);
                    else
                        errors.Add(new InvalidOperationException("BUDGET_EXPIRED_PIXEL_RESTORATION_UNVERIFIED"));
                    receipt.pixelRestoreProof = receipt.restored ? "VERIFIED_EXACT_PNG" : "UNVERIFIED";
                    receipt.stateAfterSha256 = SafeValue(() => Hash(unchanged()), errors);
                    receipt.diskAfterSha256 = SafeValue(DiskFingerprint, errors);
                    receipt.sceneAfterSha256 = SafeValue(() => Hash(GuardState()), errors);
                    receipt.materialAfterSha256 = SafeValue(() => Hash(string.Join("\n", originalMaterials.Select(Serialized))), errors);
                    receipt.ownedMaterialCountAfter = owned.Count;
                    receipt.ownedTargetCountAfter = ownedTargets.Count;
                    if(!WithinBudget()) errors.Add(new InvalidOperationException("DIAGNOSTIC_TIME_BUDGET"));
                    if(errors.Count > 0 && string.IsNullOrEmpty(receipt.failureCode)) receipt.failureCode = "FINAL_RESTORE_OR_PROOF_FAILED";
                    receipt.complete = errors.Count == 0 && WithinBudget() && string.IsNullOrEmpty(receipt.failureCode) &&
                        receipt.propertiesRestored && receipt.restored && receipt.cases.Count == Cases.Length;
                    receipt.status = receipt.complete ? "COMPLETE_DIAGNOSTIC_RESTORED" :
                        receipt.restored ? "FAILED_DIAGNOSTIC_RESTORED" : "FAILED_RESTORE_NOT_PROVEN";
                    Attempt(WriteReceipt, errors);
                }
                ThrowIfAny(errors); // Never let a diagnostic failure proceed to a normal frame.
            }
            void RunCase(string id)
            {
                stage = id; CheckBudget(); RequireUnchanged();
                var errors = new List<Exception>(); var row = new CaseReceipt { id = id }; receipt.cases.Add(row);
                try
                {
                    Apply(id); Fault(id + ":after-mutation"); RequireStateAndCamera(); row.controls = Controls();
                    row.controlsBeforeJson = JsonUtility.ToJson(row.controls);
                    row.controlsBeforeSha256 = Hash(row.controlsBeforeJson);
                    // Fail closed if the effective probe has not synchronously updated; do not advance a frame.
                    RequireAmbientCase(id);
                    Fault(id + ":before-capture"); var png = Capture(id, true); row.file = png.file; row.sha256 = png.sha256; row.bytes = png.bytes;
                    Fault(id + ":after-png"); RequireStateAndCamera();
                    row.controlsAfterJson = JsonUtility.ToJson(Controls());
                    row.controlsAfterSha256 = Hash(row.controlsAfterJson);
                    RequireAmbientCase(id);
                    if(id == "ambient-sh-zero") Require(row.sha256 != normalSha, "AMBIENT_ABLATION_ENCODED_IMAGE_UNCHANGED");
                    Require(row.controlsBeforeSha256 == row.controlsAfterSha256, "CONTROL_MUTATION_DURING_RENDER");
                    row.controlsStable = true; row.captured = true;
                }
                catch(Exception e) { errors.Add(e); }
                finally
                {
                    Restore(errors);
                    int beforeProperties = errors.Count;
                    Attempt(() => RequireUnchanged(), errors);
                    row.propertiesRestored = errors.Count == beforeProperties;
                    if(WithinBudget()) Attempt(() => {
                        var restored = Capture("restore-check", false);
                        row.restoredPngSha256 = restored.sha256;
                        Require(restored.sha256 == normalSha, "PER_CASE_RESTORED_PIXEL_MISMATCH");
                        RequireUnchanged(); CheckBudget(); row.restored = true;
                    }, errors);
                    else errors.Add(new InvalidOperationException("BUDGET_EXPIRED_PIXEL_RESTORATION_UNVERIFIED"));
                    Attempt(() => { Fault(id + ":before-receipt"); WriteReceipt(); }, errors);
                }
                ThrowIfAny(errors);
            }
            bool WithinBudget() => timer.ElapsedMilliseconds < BudgetMs;
            void CheckBudget() => Require(WithinBudget(), "DIAGNOSTIC_TIME_BUDGET");
            static int Depth(Transform t) { int n = 0; for(var p = t.parent; p != null; p = p.parent) n++; return n; }
            string Membership<T>() where T : Component => string.Join(",", environment.GetComponentsInChildren<T>(true)
                .Select(x => x.GetInstanceID()).OrderBy(x => x));
            void InjectStateNegative()
            {
                if(!fault.StartsWith("negative:", StringComparison.Ordinal)) return;
                faultConsumed = true;
                switch(fault)
                {
                    case "negative:camera-target":
                        var replacement = new RenderTexture(target.descriptor) { name = "DIAGNOSTIC owned target negative" };
                        ownedTargets.Add(replacement); replacement.Create(); camera.targetTexture = replacement; break;
                    case "negative:material-slot": LitClone(); break;
                    case "negative:probe-transform": probe.transform.localPosition += Vector3.right * .001f; break;
                    case "negative:urp-camera": urp.renderPostProcessing = !urp.renderPostProcessing; break;
                }
            }
            void Fault(string point)
            { if(fault == point && !faultConsumed) { faultConsumed = true; throw new InvalidOperationException("INJECTED_DIAGNOSTIC_FAULT"); } }
            void Apply(string id)
            {
                switch(id)
                {
                    case "pendant-zero": lights[1].intensity = 0; break;
                    case "boardwash-zero": lights[4].intensity = 0; break;
                    case "counter-pair-zero": lights[1].intensity = 0; lights[4].intensity = 0; break;
                    case "daylight-zero": lights[0].intensity = 0; break;
                    case "reading-zero": lights[2].intensity = 0; break;
                    case "shelf-zero": lights[3].intensity = 0; break;
                    case "all-direct-zero": foreach(var light in lights) light.intensity = 0; break;
                    case "probe-intensity-zero": probe.intensity = 0; break;
                    case "global-reflection-zero": RenderSettings.reflectionIntensity = 0; break;
                    case "reflection-controls-zero": probe.intensity = 0; RenderSettings.reflectionIntensity = 0; break;
                    case "ambient-sh-zero":
                        // Trilight's effective probe is derived from its three colors.
                        // Preserve mode, intensity, alpha, direct-light and reflection settings.
                        RenderSettings.ambientSkyColor = ZeroRgb(ambientSky);
                        RenderSettings.ambientEquatorColor = ZeroRgb(ambientEquator);
                        RenderSettings.ambientGroundColor = ZeroRgb(ambientGround); break;
                    case "counter-and-reflection-controls-zero":
                        lights[1].intensity = 0; lights[4].intensity = 0; probe.intensity = 0; RenderSettings.reflectionIntensity = 0; break;
                    case "oak-specular-highlights-off":
                        var spec = LitClone(); spec.SetFloat("_SpecularHighlights", 0); spec.EnableKeyword("_SPECULARHIGHLIGHTS_OFF"); break;
                    case "oak-normal-flat": LitClone().SetFloat("_BumpScale", 0); break;
                    case "oak-roughness-one": LitClone().SetFloat("_Smoothness", 0); break;
                    case "oak-texture-only": UnlitClone(false); break;
                    case "oak-target-mask": UnlitClone(true); break;
                    default: throw new InvalidOperationException("UNKNOWN_DIAGNOSTIC_CASE");
                }
            }
            static Color ZeroRgb(Color value) => new Color(0, 0, 0, value.a);
            void RequireAmbientCase(string id)
            {
                bool zero = id == "ambient-sh-zero";
                Require(RenderSettings.ambientMode == ambientMode && RenderSettings.ambientIntensity == ambientIntensity,
                    "AMBIENT_MODE_OR_INTENSITY_MUTATED");
                Require(RenderSettings.ambientSkyColor.Equals(zero ? ZeroRgb(ambientSky) : ambientSky) &&
                    RenderSettings.ambientEquatorColor.Equals(zero ? ZeroRgb(ambientEquator) : ambientEquator) &&
                    RenderSettings.ambientGroundColor.Equals(zero ? ZeroRgb(ambientGround) : ambientGround) &&
                    RenderSettings.ambientLight.Equals(zero ? ZeroRgb(ambientAlias) : ambientAlias), "AMBIENT_COLOR_OR_ALIAS_DRIFT");
                var effective = RenderSettings.ambientProbe;
                for(int channel = 0; channel < 3; channel++) for(int coefficient = 0; coefficient < 9; coefficient++)
                    Require(effective[channel, coefficient] == (zero ? 0f : ambient[channel, coefficient]),
                        "AMBIENT_EFFECTIVE_SH_NOT_EXPECTED");
            }
            Material LitClone()
            {
                var material = new Material(oakMaterial) { name = "DIAGNOSTIC owned Warm_Oak", hideFlags = HideFlags.HideAndDontSave };
                owned.Add(material); oak.sharedMaterial = material; return material;
            }
            void UnlitClone(bool mask)
            {
                var material = new Material(Shader.Find("Universal Render Pipeline/Unlit"))
                    { name = "DIAGNOSTIC owned Warm_Oak display", hideFlags = HideFlags.HideAndDontSave };
                owned.Add(material);
                material.SetTexture("_BaseMap", mask ? null : oakMaterial.GetTexture("_BaseMap"));
                material.SetColor("_BaseColor", mask ? Color.magenta : oakMaterial.GetColor("_BaseColor"));
                material.SetTextureScale("_BaseMap", oakMaterial.GetTextureScale("_BaseMap"));
                material.SetTextureOffset("_BaseMap", oakMaterial.GetTextureOffset("_BaseMap"));
                material.SetFloat("_Cull", oakMaterial.GetFloat("_Cull")); material.SetFloat("_Surface", 0);
                material.SetFloat("_ZWrite", 1); material.SetFloat("_SrcBlend", (float)BlendMode.One); material.SetFloat("_DstBlend", (float)BlendMode.Zero);
                material.shaderKeywords = new string[0]; material.enableInstancing = false; material.doubleSidedGI = false;
                material.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None; material.renderQueue = (int)RenderQueue.Geometry;
                oak.sharedMaterial = material;
            }
            void Restore(List<Exception> errors)
            {
                // Independent cleanup steps: one exception must not suppress later recovery.
                foreach(var saved in transforms) Attempt(saved.Restore, errors);
                Attempt(RestoreCamera, errors);
                for(int i = 0; i < renderers.Length; i++) { int n = i; Attempt(() => { if(!renderers[n].sharedMaterials.SequenceEqual(bindings[n])) renderers[n].sharedMaterials = bindings[n]; }, errors); }
                for(int i = 0; i < lights.Length; i++) { int n = i; Attempt(() => { if(lights[n].intensity != intensities[n]) lights[n].intensity = intensities[n]; }, errors); }
                Attempt(() => probe.intensity = probeIntensity, errors);
                Attempt(() => RenderSettings.reflectionIntensity = reflectionIntensity, errors);
                Attempt(() => { if(RenderSettings.ambientMode != ambientMode) RenderSettings.ambientMode = ambientMode; }, errors);
                Attempt(() => { if(RenderSettings.ambientIntensity != ambientIntensity) RenderSettings.ambientIntensity = ambientIntensity; }, errors);
                // ambientLight is the native alias of ambientSkyColor; restore once,
                // then RequireUnchanged compares both real getters in Controls().
                Attempt(() => { if(!RenderSettings.ambientSkyColor.Equals(ambientSky)) RenderSettings.ambientSkyColor = ambientSky; }, errors);
                Attempt(() => { if(!RenderSettings.ambientEquatorColor.Equals(ambientEquator)) RenderSettings.ambientEquatorColor = ambientEquator; }, errors);
                Attempt(() => { if(!RenderSettings.ambientGroundColor.Equals(ambientGround)) RenderSettings.ambientGroundColor = ambientGround; }, errors);
                Attempt(() => RenderSettings.ambientProbe = ambient, errors);
                Attempt(() => RenderTexture.active = initialActive, errors);
                foreach(var texture in ownedTargets.ToArray()) Attempt(() => {
                    if(texture != null) { texture.Release(); Object.DestroyImmediate(texture); }
                    ownedTargets.Remove(texture);
                }, errors);
                foreach(var material in owned.ToArray()) Attempt(() => {
                    // Only our unsaved new Material objects, never a shared asset.
                    if(material != null) Object.DestroyImmediate(material);
                    owned.Remove(material);
                }, errors);
            }
            void RequireStateAndCamera()
            {
                Require(Time.frameCount == frame, "UNITY_FRAME_ADVANCED");
                Require(unchanged() == originalInvariant && DiskFingerprint() == originalDisk, "GAME_OR_PERSISTENCE_MUTATED");
                Require(camera.targetTexture == target, "ACTUAL_CAMERA_TARGET_BINDING_MUTATED");
                Require(camera.GetComponent<UniversalAdditionalCameraData>() == urp && Serialized(urp) == urpSerialized &&
                    urp.volumeTrigger == volumeTrigger && urp.cameraStack.SequenceEqual(cameraStack), "URP_CAMERA_MUTATED");
                Require(CameraState() == originalCamera, "CAMERA_OR_TARGET_MUTATED");
                Require(Membership<Renderer>() == rendererIds && Membership<Light>() == lightIds && Membership<ReflectionProbe>() == probeIds && Membership<Transform>() == transformIds,
                    "CONTROLLED_COMPONENT_MEMBERSHIP_MUTATED");
                foreach(var saved in transforms) saved.RequireUnchanged();
                for(int i = 0; i < renderers.Length; i++)
                {
                    var allowed = renderers[i] == oak && owned.Count == 1 ? new[] { owned[0] } : bindings[i];
                    Require(renderers[i] != null && renderers[i].sharedMaterials.SequenceEqual(allowed), "UNEXPECTED_MATERIAL_SLOT_DURING_CASE");
                }
            }
            void RequireUnchanged()
            {
                RequireStateAndCamera();
                Require(Membership<Renderer>() == rendererIds && Membership<Light>() == lightIds && Membership<ReflectionProbe>() == probeIds && Membership<Transform>() == transformIds,
                    "CONTROLLED_COMPONENT_MEMBERSHIP_MUTATED");
                for(int i = 0; i < renderers.Length; i++)
                    Require(renderers[i] != null && renderers[i].sharedMaterials.SequenceEqual(bindings[i]), "EXPLICIT_MATERIAL_SLOT_REFERENCE_MUTATED");
                foreach(var saved in transforms) saved.RequireUnchanged();
                Require(owned.Count == 0 && ownedTargets.Count == 0 && GuardState() == originalGuard, "SCENE_RESTORATION_NOT_PROVEN");
                Require(originalMaterials.Select(Serialized).SequenceEqual(materialStates), "SHARED_MATERIAL_ASSET_MUTATED");
                Require(RenderTexture.active == initialActive, "ACTIVE_RENDER_TEXTURE_LEAK");
            }
            void RestoreCamera()
            {
                // No normal diagnostic case changes camera configuration. If a fault or
                // callback did, restore it but retain the original failure so no normal frame follows.
                if(camera.GetComponent<UniversalAdditionalCameraData>() != urp)
                    throw new InvalidOperationException("URP_CAMERA_COMPONENT_REPLACED_NOT_REPAIRABLE");
#if UNITY_EDITOR
                if(Serialized(urp) != urpSerialized) UnityEditor.EditorJsonUtility.FromJsonOverwrite(urpSerialized, urp);
#endif
                if(urp.volumeTrigger != volumeTrigger) urp.volumeTrigger = volumeTrigger;
                if(!urp.cameraStack.SequenceEqual(cameraStack)) { urp.cameraStack.Clear(); urp.cameraStack.AddRange(cameraStack); }
                if(camera.targetTexture != target) camera.targetTexture = target;
                if(CameraState() != originalCamera)
                {
                    camera.transform.SetPositionAndRotation(cameraBefore.position, cameraBefore.rotation);
                    camera.fieldOfView = cameraBefore.fov; camera.aspect = cameraBefore.aspect;
                    camera.nearClipPlane = cameraBefore.near; camera.farClipPlane = cameraBefore.far;
                    camera.rect = new Rect(cameraBefore.viewport[0], cameraBefore.viewport[1], cameraBefore.viewport[2], cameraBefore.viewport[3]); camera.orthographic = cameraBefore.orthographic;
                    camera.enabled = cameraBefore.enabled; camera.allowHDR = cameraBefore.allowHDR; camera.allowMSAA = cameraBefore.allowMSAA;
                    camera.cullingMask = cameraBefore.cullingMask; camera.backgroundColor = cameraBefore.background;
                    camera.clearFlags = (CameraClearFlags)Enum.Parse(typeof(CameraClearFlags), cameraBefore.clearFlags);
                    camera.projectionMatrix = ToMatrix(cameraBefore.projection); camera.worldToCameraMatrix = ToMatrix(cameraBefore.worldToCamera);
                }
            }
            sealed class ControlledTransform
            {
                readonly Transform value, parent; readonly Vector3 position, scale; readonly Quaternion rotation;
                readonly bool active; readonly int layer, sibling;
                public ControlledTransform(Transform t)
                { value = t; parent = t.parent; position = t.localPosition; rotation = t.localRotation; scale = t.localScale;
                    active = t.gameObject.activeSelf; layer = t.gameObject.layer; sibling = t.GetSiblingIndex(); }
                public string CurrentState() => Id(value) + ":" + Id(value == null ? null : value.parent) + ":" +
                    (value == null ? "DESTROYED" : JsonUtility.ToJson(value.localPosition) + JsonUtility.ToJson(value.localRotation) +
                    JsonUtility.ToJson(value.localScale) + ":" + value.gameObject.activeSelf + ":" + value.gameObject.layer + ":" + value.GetSiblingIndex());
                public void Restore()
                {
                    Require(value != null, "CONTROLLED_TRANSFORM_DESTROYED");
                    if(value.parent != parent) value.SetParent(parent, false);
                    if(value.GetSiblingIndex() != sibling) value.SetSiblingIndex(sibling);
                    if(value.localPosition != position) value.localPosition = position;
                    if(value.localRotation != rotation) value.localRotation = rotation;
                    if(value.localScale != scale) value.localScale = scale;
                    if(value.gameObject.layer != layer) value.gameObject.layer = layer;
                    if(value.gameObject.activeSelf != active) value.gameObject.SetActive(active);
                }
                public void RequireUnchanged()
                { Require(value != null && value.parent == parent && value.localPosition == position && value.localRotation == rotation &&
                    value.localScale == scale && value.gameObject.activeSelf == active && value.gameObject.layer == layer &&
                    value.GetSiblingIndex() == sibling, "CONTROLLED_TRANSFORM_OR_GAMEOBJECT_MUTATED"); }
            }
            string DiskFingerprint()
            {
                Require(Directory.Exists(storeDirectory), "FIXTURE_STORE_MISSING");
                var files = Directory.GetFiles(storeDirectory).OrderBy(x => x, StringComparer.Ordinal).ToArray();
                Require(files.Length <= 64 && Directory.GetDirectories(storeDirectory).Length == 0, "FIXTURE_STORE_BOUND");
                var b = new StringBuilder(); long total = 0;
                foreach(string path in files)
                {
                    var info = new FileInfo(path); total += info.Length; Require(total <= 64L * 1024 * 1024, "FIXTURE_STORE_BYTES_BOUND");
                    b.Append(info.Name).Append(':').Append(info.Length).Append(':');
                    // FileStateStore intentionally holds writer.lock with FileShare.None.
                    b.Append(info.Name == "writer.lock" ? "LOCK_EXISTENCE_AND_LENGTH_ONLY" : StateCodec.HashBytes(File.ReadAllBytes(path))).Append('\n');
                }
                return Hash(b.ToString());
            }
            string GuardState()
            {
                var b = new StringBuilder();
                foreach(var l in lights) b.Append(Id(l)).Append(Serialized(l));
                b.Append(Id(probe)).Append(Serialized(probe));
                b.Append(JsonUtility.ToJson(Controls()));
                b.Append(Id(RenderSettings.sun)).Append(RenderSettings.ambientMode).Append(RenderSettings.defaultReflectionMode);
                b.Append(JsonUtility.ToJson(RenderSettings.ambientSkyColor)).Append(JsonUtility.ToJson(RenderSettings.ambientEquatorColor));
                b.Append(JsonUtility.ToJson(RenderSettings.ambientGroundColor)).Append(JsonUtility.ToJson(RenderSettings.ambientLight));
                b.Append(Id(RenderSettings.skybox));
                b.Append(Id(QualitySettings.renderPipeline)).Append(Serialized(QualitySettings.renderPipeline));
                b.Append(Id(GraphicsSettings.defaultRenderPipeline)).Append(Serialized(GraphicsSettings.defaultRenderPipeline));
                foreach(var r in renderers) b.Append(Id(r)).Append(Serialized(r));
                foreach(var saved in transforms) b.Append(saved.CurrentState());
                return b.ToString();
            }
            CameraReceipt CameraObservation() => new CameraReceipt { instanceId = camera.GetInstanceID(), position = camera.transform.position,
                rotation = camera.transform.rotation, fov = camera.fieldOfView, aspect = camera.aspect, near = camera.nearClipPlane,
                far = camera.farClipPlane, viewport = new[] {camera.rect.x, camera.rect.y, camera.rect.width, camera.rect.height},
                projection = MatrixValues(camera.projectionMatrix), worldToCamera = MatrixValues(camera.worldToCameraMatrix),
                targetId = camera.targetTexture == null ? 0 : camera.targetTexture.GetInstanceID(), urpInstanceId = urp.GetInstanceID(),
                urpSerializedSha256 = Hash(Serialized(urp)), urpStackIds = urp.cameraStack.Select(x => x == null ? 0 : x.GetInstanceID()).ToArray(),
                volumeTriggerId = urp.volumeTrigger == null ? 0 : urp.volumeTrigger.GetInstanceID(),
                expectedTargetId = target.GetInstanceID(), width = target.width, height = target.height, format = target.format.ToString(),
                targetCreated = target.IsCreated(), antiAliasing = target.antiAliasing, sRGB = target.sRGB,
                allowHDR = camera.allowHDR, allowMSAA = camera.allowMSAA, cullingMask = camera.cullingMask,
                orthographic = camera.orthographic, enabled = camera.enabled, clearFlags = camera.clearFlags.ToString(), background = camera.backgroundColor };
            static float[] MatrixValues(Matrix4x4 m) => Enumerable.Range(0, 16).Select(i => m[i]).ToArray();
            static Matrix4x4 ToMatrix(float[] values) { var m = new Matrix4x4(); for(int i = 0; i < 16; i++) m[i] = values[i]; return m; }
            string CameraState() => JsonUtility.ToJson(CameraObservation());
            ControlsReceipt Controls() => new ControlsReceipt { lightNames = Names, lightIntensities = lights.Select(l => l.intensity).ToArray(),
                lightColors = lights.Select(l => l.color).ToArray(), lightPositions = lights.Select(l => l.transform.position).ToArray(),
                lightRotations = lights.Select(l => l.transform.rotation).ToArray(), lightRanges = lights.Select(l => l.range).ToArray(),
                lightSpotAngles = lights.Select(l => l.spotAngle).ToArray(), lightInnerSpotAngles = lights.Select(l => l.innerSpotAngle).ToArray(),
                lightShadows = lights.Select(l => l.shadows.ToString()).ToArray(), lightEnabled = lights.Select(l => l.enabled).ToArray(),
                lightCullingMasks = lights.Select(l => l.cullingMask).ToArray(), probeIntensity = probe.intensity,
                reflectionIntensity = RenderSettings.reflectionIntensity,
                ambientMode = RenderSettings.ambientMode.ToString(), ambientIntensity = RenderSettings.ambientIntensity,
                ambientSkyColor = RenderSettings.ambientSkyColor, ambientEquatorColor = RenderSettings.ambientEquatorColor,
                ambientGroundColor = RenderSettings.ambientGroundColor, ambientLight = RenderSettings.ambientLight, probeTextureId = Id(probe.customBakedTexture),
                probeTextureName = probe.customBakedTexture.name, ambientSH = Enumerable.Range(0, 27).Select(i => RenderSettings.ambientProbe[i/9, i%9]).ToArray(),
                oakShader = oak.sharedMaterial.shader.name, oakMaterialId = oak.sharedMaterial.GetInstanceID(),
                oakKeywords = oak.sharedMaterial.shaderKeywords.OrderBy(x => x, StringComparer.Ordinal).ToArray(),
                oakSmoothness = oak.sharedMaterial.HasProperty("_Smoothness") ? oak.sharedMaterial.GetFloat("_Smoothness") : -1,
                oakNormalStrength = oak.sharedMaterial.HasProperty("_BumpScale") ? oak.sharedMaterial.GetFloat("_BumpScale") : -1,
                oakSpecularHighlights = ReadFloat("_SpecularHighlights"), oakBaseMapId = Id(oak.sharedMaterial.GetTexture("_BaseMap")),
                oakBaseMapName = oak.sharedMaterial.GetTexture("_BaseMap") == null ? "null" : oak.sharedMaterial.GetTexture("_BaseMap").name,
                oakBaseColor = oak.sharedMaterial.GetColor("_BaseColor"), oakBaseScale = oak.sharedMaterial.GetTextureScale("_BaseMap"),
                oakBaseOffset = oak.sharedMaterial.GetTextureOffset("_BaseMap"), oakBumpMapId = ReadTexture("_BumpMap"),
                oakPackedMapId = ReadTexture("_MetallicGlossMap"), oakEmissionMapId = ReadTexture("_EmissionMap"),
                oakMetallic = ReadFloat("_Metallic"), oakEmissionColor = oak.sharedMaterial.HasProperty("_EmissionColor") ? oak.sharedMaterial.GetColor("_EmissionColor") : Color.clear,
                oakCull = ReadFloat("_Cull"), oakSurface = ReadFloat("_Surface"), oakZWrite = ReadFloat("_ZWrite"),
                oakSrcBlend = ReadFloat("_SrcBlend"), oakDstBlend = ReadFloat("_DstBlend"), oakRenderQueue = oak.sharedMaterial.renderQueue,
                oakEnableInstancing = oak.sharedMaterial.enableInstancing, oakDoubleSidedGI = oak.sharedMaterial.doubleSidedGI,
                oakGIFlags = oak.sharedMaterial.globalIlluminationFlags.ToString() };
            float ReadFloat(string key) => oak.sharedMaterial.HasProperty(key) ? oak.sharedMaterial.GetFloat(key) : -1;
            string ReadTexture(string key) => oak.sharedMaterial.HasProperty(key) ? Id(oak.sharedMaterial.GetTexture(key)) : "ABSENT";
            ImageReceipt Capture(string label, bool save)
            {
                CheckBudget();
                var request = new RenderPipeline.StandardRequest { destination = target };
                Require(RenderPipeline.SupportsRenderRequest(camera, request), "SRP_RENDER_REQUEST_UNSUPPORTED");
                var active = RenderTexture.active; Texture2D image = null;
                try
                {
                    image = new Texture2D(target.width, target.height, TextureFormat.RGB24, false);
                    RequireStateAndCamera(); CheckBudget(); RenderPipeline.SubmitRenderRequest(camera, request); CheckBudget(); RequireStateAndCamera(); CheckBudget(); RenderTexture.active = target;
                    image.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0, false); CheckBudget(); image.Apply(false, false); CheckBudget();
                    byte[] bytes = image.EncodeToPNG(); CheckBudget(); Require(bytes.Length > 10000 && bytes.Length <= 8*1024*1024, "DIAGNOSTIC_PNG_BOUND");
                    var row = new ImageReceipt { file = "DIAGNOSTIC__phone-mom-pending__" + label + ".png", sha256 = StateCodec.HashBytes(bytes), bytes = bytes.Length };
                    if(save) { string path = Path.Combine(root, row.file); Require(!File.Exists(path), "DIAGNOSTIC_PNG_ALREADY_EXISTS"); File.WriteAllBytes(path, bytes); CheckBudget(); }
                    return row;
                }
                finally { try { RenderTexture.active = active; } finally { if(image != null) Object.DestroyImmediate(image); } }
            }
            static string SafeValue(Func<string> read, List<Exception> errors)
            { try { return read(); } catch(Exception e) { errors.Add(e); return "UNVERIFIED"; } }
            void WriteReceipt()
            {
                receipt.elapsedMs = timer.ElapsedMilliseconds;
                if(receipt.complete && (!WithinBudget() || !string.IsNullOrEmpty(receipt.failureCode)))
                { receipt.complete = false; receipt.status = "FAILED_BUDGET_AT_RECEIPT_WRITE"; receipt.failureCode = "DIAGNOSTIC_TIME_BUDGET"; }
                string json = JsonUtility.ToJson(receipt, true); Require(Encoding.UTF8.GetByteCount(json) <= 2097152, "DIAGNOSTIC_RECEIPT_BOUND");
                string temp = Path.Combine(root, "diagnostic-receipt.json.tmp"), path = Path.Combine(root, "diagnostic-receipt.json");
                File.WriteAllText(temp, json);
                if(File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
                if(receipt.complete && !WithinBudget())
                {
                    receipt.complete = false; receipt.status = "FAILED_BUDGET_AT_RECEIPT_WRITE";
                    receipt.failureCode = "DIAGNOSTIC_TIME_BUDGET"; WriteReceipt();
                    throw new InvalidOperationException("DIAGNOSTIC_TIME_BUDGET");
                }
                if(receipt.status == "FAILED_BUDGET_AT_RECEIPT_WRITE") throw new InvalidOperationException("DIAGNOSTIC_TIME_BUDGET");
            }
        }
        [Serializable] sealed class ImageReceipt { public string file, sha256; public int bytes; }
        [Serializable] sealed class CaseReceipt
        { public string id, file, sha256, restoredPngSha256, controlsBeforeSha256, controlsAfterSha256, controlsBeforeJson, controlsAfterJson; public int bytes; public bool captured, restored, controlsStable, propertiesRestored; public ControlsReceipt controls; }
        [Serializable] sealed class CameraReceipt
        {
            public int instanceId, targetId, expectedTargetId, urpInstanceId, volumeTriggerId, width, height, antiAliasing, cullingMask;
            public int[] urpStackIds; public string urpSerializedSha256;
            public Vector3 position; public Quaternion rotation; public float[] projection, worldToCamera, viewport; public Color background;
            public float fov, aspect, near, far; public bool orthographic, enabled, allowHDR, allowMSAA, sRGB, targetCreated; public string format, clearFlags;
        }
        [Serializable] sealed class ControlsReceipt
        {
            public string[] lightNames, lightShadows, oakKeywords; public float[] lightIntensities, lightRanges, lightSpotAngles, lightInnerSpotAngles, ambientSH;
            public Color[] lightColors; public Vector3[] lightPositions; public Quaternion[] lightRotations; public bool[] lightEnabled; public int[] lightCullingMasks;
            public float probeIntensity, reflectionIntensity, oakSmoothness, oakNormalStrength, oakSpecularHighlights;
            public string ambientMode; public float ambientIntensity;
            public Color ambientSkyColor, ambientEquatorColor, ambientGroundColor, ambientLight;
            public string probeTextureId, probeTextureName, oakShader; public int oakMaterialId;
            public string oakBaseMapId, oakBaseMapName, oakBumpMapId, oakPackedMapId, oakEmissionMapId, oakGIFlags;
            public Color oakBaseColor, oakEmissionColor; public Vector2 oakBaseScale, oakBaseOffset;
            public float oakMetallic, oakCull, oakSurface, oakZWrite, oakSrcBlend, oakDstBlend;
            public int oakRenderQueue; public bool oakEnableInstancing, oakDoubleSidedGI;
        }
        [Serializable] sealed class Receipt
        {
            public int schemaVersion = 3; public string scope = Scope, status = "RUNNING", sourceCommit, runId, runAttempt;
            public string baselineSourceFreeze = "02a6440209c26bcc94c50fdf73a87345b563b5ed";
            public string stateOrigin = "SAME_RUNTIME_PHONE_PENDING_NO_INPUT_NO_SERVICE_ACTION";
            public string expectedNormalPngSha256, baselineBeforeSha256, baselineAfterSha256, stateBeforeSha256, stateAfterSha256,
                diskBeforeSha256, diskAfterSha256, sceneBeforeSha256, sceneAfterSha256, materialBeforeSha256, materialAfterSha256, failureCode, faultRequest,
                colorSpace, graphicsDeviceType, unityVersion, oakShader, oakBaseMap, oakMaterialCoverage;
            public int frameCount, oakRendererInstanceId, oakMaterialInstanceId, ownedMaterialCountAfter, ownedTargetCountAfter;
            public string initialControlsJson, initialControlsSha256, pixelRestoreProof; public bool diagnosticOptIn, propertiesRestored;
            public long elapsedMs; public bool complete, restored; public Color oakBaseColor; public CameraReceipt camera; public ControlsReceipt initialControls;
            public List<CaseReceipt> cases = new List<CaseReceipt>();
        }
    }
}
