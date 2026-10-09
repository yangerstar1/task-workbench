# Candidate art import and bounded technical evidence

This pipeline produces unapproved candidates. Real Pouncer, Armored and Weapon Discovery runs have succeeded; they establish imported metadata only. The first Armored strict binding/capture revision is awaiting native execution. It preserves original assets, scenes, source, production gates and acceptance flags. Use only the existing explicitly authorized public/free Actions workflow.

## Files and execution

1. Obtain the exact successful generation run JSON and artifact JSON from authenticated GitHub API, plus the original artifact ZIP. These metadata files are trusted inputs; hand-written lookalike JSON is not independent provenance.
2. Author one immutable contract for one asset, after reading the actual final export. Do not use failed historical candidates or guessed hash/path/take values. `python stage_artifact.py --contract CONTRACT --run RUN_JSON --artifact ARTIFACT_JSON --archive ZIP --output NEW_STAGING_DIRECTORY` verifies repository/run/source/archive server digest and each copied payload hash; only declared FBX/PNG/TGA files are staged. Output must not exist.
3. Add JourneyCandidateArtImport.cs and its meta to the Unity 6000.3.19f1 project. Keep latest actual runtime/gates in place. Set DESERTRV_ART_INPUT to staging, DESERTRV_ART_CONTRACT to the exact contract JSON, DESERTRV_ART_ARCHIVE to original ZIP. From Unity project working directory call `-batchmode -quit -executeMethod DesertRV.Editor.JourneyCandidateArtImport.Import` using the existing authorized Actions Unity setup. The editor does not independently authenticate the API metadata: running the stager is mandatory.
4. Unity writes only a new `Assets/DesertRV/CandidateArtImports/<id>/` directory: copied source files, generated new metas, persistent URP materials, Base Layer controller, independent Candidate.prefab and copied contract. An existing candidate ID/meta fails; retry using a fresh ID and preserve failed evidence. The actual readback report is `JourneyEvidence/CandidateArt/import-report.json`; upload it and candidate outputs before importing another candidate because this filename is per invocation. Failed import may leave partial candidate files, and never reports success.
5. Preserve generated assets AND metas together for stable subsequent GUIDs. The report includes Unity dependency hash and the production gate's byte-level dependency SHA256. Both model and animation FBXs must remain real prefab dependencies, including split armored static-model/rig-only animation exports.

## Exact JSON contract (schema 1)

Required identity: schema=1, mode (DISCOVERY_ONLY or STRICT_BINDING), scope (FULL_CANDIDATE, DEATH_DIAGNOSTIC_NOT_FULL, or PARTIAL_DIAGNOSTIC_NOT_FULL), id (new lowercase slug), kind (pouncer/armored/weapon), repository=yangerstar1/task-workbench, runUrl (exact numeric GitHub Actions run URL), sourceCommit (40 lowercase hex), artifactName, artifactSha256 (64 lowercase hex matching GitHub artifact digest), modelFile (relative FBX path).

files is an array of {file, sha256}; relative paths have no traversal, backslash, absolute paths or collisions. Include the model, all clip FBXs, and all material textures. Supplied meta/scripts are forbidden. Actual source bytes must exactly match hashes.

clips is an array of {state, file, take, seconds, loop, poseExpectation}. `file` is the hashed FBX, `take` the exact actual FBX importer takeName, not a guessed state suffix. No extra/missing takes are allowed. `poseExpectation` must explicitly be `held` or `varying` based on the authored contract; held Recover is legal because plate opening belongs to the runtime presenter. Do not add fake movement to satisfy capture checks. Animator state names are exact and flat under Base Layer. Idle and enemy Walk loop. The reviewed Armored Attack source loop is also allowed to cover the existing attack timer and normalized CrossFade overrun; no other attack/reload loop is allowed.

Duration seconds:
- Pouncer: Idle 2, Walk .4, Windup .78, Attack .8, Recover 1.3, Hit .28, Death 1.8.
- Armored: Idle 2, Walk .6, Windup 1.1, Attack 1.2, Recover 2, Hit .28, Death 1.8.
- Weapon: Idle 2, Fire .22, Reload 1.65.

Importer reads back actual AnimationClip frame rate, duration (within one actual frame), loop status, transform curves, event absence, object-curve absence, competing quaternion/Euler bindings and root/motion curves. Every binding path must resolve against the final model Animator root. This structural readback is not a visual or motion approval. Charge timeout/crossfade overrun still needs actual runtime review.

materials is an array of {sourceName, baseColorFile, normalFile, metallicSmoothnessFile, occlusionFile, baseColor, metallic, smoothness}. `sourceName` must exactly match actual imported source material name. Every source renderer slot must map, and no mapping may be unused. Optional texture path may be empty; other texture paths must be hashed files. `baseColor` is Unity Color JSON {r,g,b,a}. Only already-correct Unity packed metallic R/smoothness A is supported; DO NOT route raw ORM into this field. Armored ormFile uses the explicitly tested linear conversion R=source.B, G=source.R, B=0, A=255-source.G, with actual imported pixel readback and unchanged original hash. Texture content/channel correctness needs actual inspection. No material inference or silent fallback.

bindings: every transform/renderer path is exact model-root-relative (animatorPath alone may be empty for model root), with no duplicate sibling-name ambiguity. Do not assume FBX axis conversion or hierarchy.
- Common: animatorPath, body (renderer path).
- Enemies: colliderCenter {x,y,z}, colliderRadius, colliderHeight explicitly agreed from the imported model.
- Weapon: leftHand/rightHand (actual hand.L/hand.R bone paths), muzzle (explicit authored Muzzle bone path, never inferred tip), incomingOffset/leftReloadOffset (actual carrier paths), loadedNails/incomingNails (12 exact renderer paths each, ordered LoadedNail_00..11 / IncomingNail_00..11).
- Armored: weakPointRoot, core, plates[2], plateRenderers[2], openEuler[2] as Vector3 JSON, openEmission as Color. Requires the new two-plate BeastWeakPointPresentation fields. Core is rigid one-slot MeshRenderer; body outside the weakpoint subtree. WeakPointAssembly and all descendants must have zero float/object curves. Explicit measured Unity opening rotations must be supplied; Blender angles or initial intent cannot count as calibration. Intended author hierarchy is Bulwark_Rig/body/WeakPointAssembly with Core_Renderer and left/right ArmorPlate_*_Pivot/ArmorPlate_*_Renderer. Confirm actual import paths.

## Known fail-closed blockers and required next integration

- Runtime helper now exists on public main 91c8b42cb7549da0fab574e7082d25210431ad1f. This importer calls actual NailRigOwnership.Validate, ValidateLoaded and TryGetAnimationTargets. Incoming skinned positive weights must belong to IncomingOffset; loaded weights may not. Mesh read/write is enabled. No mesh is reparented. The dual-plate gate uses the actual WeakPointContractChecks.Validate helper. Their real Unity tests and this importer still need execution.
- Explicit Muzzle bone must exist in the final author export. The author has proposed adding it after the fourth run; older binaries may lack it and must fail.
- Weapon prefab presenter intentionally disabled and has no fabricated scene actions. A later explicit scene integration must set actions/camera/shotMuzzle, enable and invoke ValidateBindings, and test live reload/fire interruption. No scene-binding function is provided here.
- Muzzle FX is deliberately NOT created or bound. The author confirms Muzzle source bone local forward +Y, head (0,.35,.072), tail (0,.385,.072). Import report records actual marker position and all three imported world basis vectors without guessing which is the barrel direction. `calibratedForScene=false`; WeaponPresentation.muzzleFlash=null forces normal live binding validation/production preflight to fail until an explicit scene integration verifies the export head/tail or basis against barrel geometry, creates a calibrated adapter and binds correctly oriented FX. Camera-ray gameplay does not validate flash direction.
- Nail pitch derives from actual mesh bounds centers in the imported rest pose, checks uniform loaded/incoming spacing and transforms into the real carrier-parent space. This cannot establish finger contact/collision correctness.
- Armored uses the new two-plate fields via checked SerializedObject reflection. Old single-plate runtime fails immediately rather than silently falling back.
- Actual Unity compilation/import/render, interrupted actions, reload cases, weakpoint states, three-region playthrough, Android device performance and the unchanged production gate remain required. No accepted=true or evidence approval is generated.

## Manual workflow and real capture entry

`.github/workflows/desert-rv-candidate-art-import.yml` takes a checked-in contract path and independently reviewed SHA256. `prepare_input.py` retrieves authenticated repository/run/artifact metadata and the original ZIP using the read-only Actions token. It rejects private repositories and revalidates source, server digest and payload bytes. The fixed Unity 6000.3.19f1 / official GameCI / Mesa software OpenGL environment and existing Unity secrets are reused.

The isolated `DesertRV.CandidateArtTests` assembly contains the selected-mode entry plus two animation-policy regression tests and a real missing/reused/destroyed Animator regression. Core game inventories are separate. Strict Armored samples actual Animator clips, existing normalized CrossFade interruptions, source-loop overrun and Animator resets, then nine real-presenter Editor fixture views. Camera images are diagnostic candidates; an Animator reset is not whole-game restart evidence.

The safe exporter requires all six native cases, successful native/protected steps, closed-schema reports, exact frame inventory and original-source identity. Failure uploads only a safe fixed code and validated source identity. It never uploads partial candidate directories or raw logs. The existing Discovery branch preserves its narrower source-only export and does not produce screenshots.

## Reviewed inputs and remaining work

Three actual Discovery outputs now exist, including Weapon combined FULL metadata and Armored model/animation/texture readback. Armored has a new genuine FULL aggregate and measured strict contract; its first strict Unity run remains pending. Weapon requires measured source-unit, material, muzzle and two-bone calibration work before its strict safe-export path is opened. Pouncer partial Death discovery remains partial. Visual acceptance, actual runtime interruption, whole-game input traversal and Android device acceptance remain separate gates.

## Capture lifecycle and source-first compilation revision

Capture uses URP `SingleCameraRequest`, `SupportsRenderRequest` and `SubmitRenderRequest`, matching the previously exercised environment capture route. It does not call legacy Camera.Render. Report writes are inside nested try/finally cleanup, so a failed report save still fails the test but cannot skip RenderTexture release/destroy, Texture2D destroy, or preview-scene closure. Per-render active RenderTexture is restored even on render/readback failure.

Every captured frame now reports actual BakeMesh/rigid-mesh vertex count, worldMinY, actor-origin groundReferenceY, offscreen/behind-camera vertex counts, and a deformed-mesh SHA256. Below-reference counts apply only to enemy kinds, never to the weapon. These are raw measured diagnostics, not approved foot-contact thresholds; renderer-wide bounds alone do not certify feet or floor contact. Held clips do not fail because their five images match. The separate nine-view weakpoint fixture exercises the actual presenter under isolated authoritative state; it is not end-to-end gameplay.

The C# Editor sources and isolated test assembly can be published first for ordinary Unity compilation, with no concrete artifact contract and no importer dispatch. The normal native workflow's explicit EditMode/PlayMode assembly selection does not execute DesertRV.CandidateArtTests; compilation still sees the Editor C# source. Do not claim compilation passed until its actual Actions result. The dedicated candidate workflow intentionally fails without a real reviewed contract; it is not auto-triggered on push.

Local validation covers the stager, source contracts and both safe exporters with positive and negative fixtures. These tests do not substitute for native compilation/rendering.

## Final source overlay integrity

`Tests/CandidateArt.meta` now has an explicit stable folder GUID and is included in the source manifest. All new C#/asmdef files already have explicit metas. Existing parent metas are reused, not included or overwritten: DesertRV 315d70a22293ab4459ebe0d2ddea67c7; Editor 419d3fa976be7ef4383f85f049b2e89e; Tests 9b7c8a53d9504c14b16a87de95f1c060 (read from the real contract integration tree).

The muzzle observation is not a directional acceptance flag: there is no generated flash or ShotMuzzle adapter to inherit a guessed +Z orientation. Actual scene binding remains blocked until calibrated; import/capture can still run as explicitly incomplete candidate diagnostics.

## Two-stage import: discovery removes the circular prerequisite

Stage 1 contract uses mode DISCOVERY_ONLY. It contains schema/id/kind/repository/runUrl/sourceCommit/artifactId/artifactName/artifactSha256/files plus an explicit source scope. No clips, bindings or material mapping may be supplied (unknown Unity values are deliberately absent). No accepted visual status is required for discovery; a successful genuine generation run, exact provenance and an allowlisted FBX/texture byte inventory are required. The workflow mode input must match the SHA-pinned contract.

`JourneyCandidateArtDiscovery.Discover` imports only in a fresh `Assets/DesertRV/CandidateArtDiscovery/<id>/Source` directory. It preserves imported take names and default clip frame ranges and does not select clip frames, generate controllers/prefabs, attach runtime components, infer actor fields, remap materials or calibrate axes. The separate `JourneyEvidence/CandidateArtDiscovery/discovery-report.json` has mode DISCOVERY_ONLY, original scope, status discovered-unreviewed-not-bound, approved=false and bindingCalibrated=false. It enumerates actual transform paths/names/local poses/world positions/all three basis vectors (including any Muzzle node), renderer/material names and asset paths, mesh bounds/vertex/submesh counts, bones/rootBone/bindpose matrices/weight counts, default takes and imported clip names/durations/curves/events/root flags, dependencies and dependency hashes. No discovery screenshot is produced, so no neutral diagnostic material can be mistaken for finished art.

Stage 2 uses the measured discovery output to author the strict bindings/material/take contract and explicitly calibrate the armored opening axes and muzzle scene adapter as appropriate. It uses a different new ID and the existing CandidateArtImports path. STRICT_BINDING requires FULL_CANDIDATE scope; a death-only diagnostic cannot promote itself into a full asset by changing the dispatch mode. Root must select a genuinely full generation artifact before that stage. The strict importer retains all existing gates. Human visual acceptance and production acceptance remain later independent operations.

The dedicated test routes only by the explicit contract mode. Output validation checks mode-specific paths/status and forbids any discovery prefab. Failure and success outputs are isolated; neither is read as production approval. New negative tests reject missing modes, unknown scopes, discovery with invented take/binding data, and partial diagnostic promotion. Original no-overwrite, path, archive/source/server-digest and payload mismatch tests remain.

Pouncer run 37829068773 is eligible for proposed discovery only under DEATH_DIAGNOSTIC_NOT_FULL. `pouncer-death-input-inventory.json` records hashes actually read from the available FBX/PNG and the artifact's source-commit.txt. It is an inventory rather than a dispatch contract. The separate contracts/pouncer-death-discovery-37829068773.json is the real reviewed-input DiscoveryOnly contract; provenance and ZIP byte checks are documented below. No Unity take or material name was invented. Root has not approved Death visual quality; no full-motion pass is implied.

Only explicit manual dispatch executes discovery/import. Ordinary core test compilation does not execute the isolated candidate assembly.

## Historical verified Pouncer Discovery input

Contract: `tasks/desert-rv/art/import-candidate/contracts/pouncer-death-discovery-37829068773.json`
Contract SHA256: `cbd1f7901223a436461cb2cb58380bdea730664097db424f7cdc69b89214bb90`
Mode: `DISCOVERY_ONLY`; scope: `DEATH_DIAGNOSTIC_NOT_FULL`.

Parent verified successful run 37829068773 at source b904ed4b37b22f345c9e705caca409d1078300f8 and unexpired artifact 11573760750 (`pouncer-death-diagnostic-37829068773`). This worker independently checked the original ZIP is 18,854,616 bytes and SHA256 67d92a92628c3331fd2c7ed522326b506288565c30952cedd8d322ac8efcd0e9, matching the reported server digest. All 34 SHA256SUMS entries inside the 35-entry ZIP passed independent hashing. Source commit and scope were read directly from the ZIP. The workflow must re-fetch and authenticate API metadata at execution; these notes do not bypass that check.

Only two payload files enter Unity:
- pouncer-candidate.fbx: ee09adc854401aff7589121c618897226c5155c27c9336493df7d2d0b106cadd
- pouncer-basecolor.png: d771c6ddefb650959e1702359745b6ecc076a3df6f4aa1f09e99346db7e4a06b

No takes, hierarchy roles, material names, muzzle/plate calibration, final prefab or acceptance are filled in. ZIP scope explicitly says full_motion_visual_review=NOT_RUN, render_fps=30. Even successful Unity discovery will not permit this partial input to enter STRICT_BINDING. Selecting a genuinely full candidate and constructing a later measured binding contract remain separate decisions.


## Bounded export and current execution scopes

The manual workflow offers DISCOVERY_ONLY and measured Armored/Weapon/Pouncer STRICT_BINDING. The hosted preflight rejects strict inputs for other asset kinds until their measured binding and safe export contracts are implemented. A genuine FULL_CANDIDATE source is mandatory for strict mode; old partial inputs are never relabeled.

Strict capture expects six passing isolated CandidateArt NUnit cases, 202 actual 960×540 PNGs including nine real-presenter Editor fixture views, 70 root-curve records, measured root stability, and exact source/prefab dependencies. The reviewed contract pins the actual Discovery neutral root TRS and four renderer world bounds. Capture checks these before any Animator Rebind/Update, retains that original baseline, and reports actual deformed mesh dimensions on every sample. Constant root curves must also agree with the imported neutral transform; there is no automatic unit normalization or camera rescaling around a changed animation root. ORM conversion is checked again offline against every original pixel, Unity's bottom-up decoded-pixel hash and linear readable importer settings. No game test inventory is altered: the core baseline remains 164 EditMode / 9 PlayMode.

Only exact contract-declared source files/metas, newly generated candidate prefab/controller/materials/derived ORM, three closed-schema reports and the exact referenced PNGs can leave the runner. All files are validated before export. Failed native/protected/schema/image checks export only a fixed safe error code and validated source identity. No workspace, cache, raw XML, stack, licensing log or arbitrary directory is uploaded. The receipt binds the current import SHA/run, upstream source identity, native XML hash and every exported file hash.

All tracked source, including original Assets, Packages and ProjectSettings, must remain unchanged. Candidate technical output never sets visual/gameplay/production approval. The weakpoint fixture uses an isolated in-memory SessionState/BeastCombatState and actual presenter; it does not establish input-driven combat, interruption/restart, whole-game progression or Android acceptance. The first strict revision remains unexecuted until its own successful native receipt exists.

The first Armored strict run 37855265665 compiled and passed both policy tests but failed when C# null-coalescing retained Unity's missing native Animator wrapper. The shared creation helper now uses Unity Object boolean checks; a fourth isolated native case covers creation, reuse and recreation after destruction. Root/asset/export gates are unchanged. The rerun is pending until its own receipt exists.

The second strict run 37856943062 passed all three policy/Animator regressions and reached the material gate, which correctly rejected a nonpersistent _EMISSION keyword. URP 17.3 rebuilds it from AnyEmissive flags. The new open material now explicitly selects BakedEmissive, clears EmissiveIsBlack, saves and reimports, then reloads and checks the persisted asset. A fifth native regression unloads/reloads the real material and checks keyword, flags, color and unchanged closed material. This does not bake scene lighting or change body emission. Actual nine-view weakpoint images remain required.

## Measured Weapon strict candidate

The reviewed FULL Weapon source has a separate closed-schema exporter: 25 actual PNGs and 4,463 bounded numerical samples, with all 7 persisted materials, original FBX, exact source-unit calibration and prefab dependencies checked. Idle/Fire measure original Animator poses without extra IK; only Reload applies the same count projection and fixed-length solve as runtime. The actual source-axis muzzle child is not scene/reticle calibration, and no flash or approval is assigned. New core test inventory is 173 EditMode / 9 PlayMode; the separate CandidateArt assembly now has six cases. This revision has not yet executed its own native runs.

Enemy captures also reject any sampled deformed vertex more than 0.004 m below the actor ground reference, including crossfades; the offline validator enforces the same 4 mm bound. Weapon geometry is explicitly exempt from the ground criterion. Earlier fixed runs that only recorded the measurements require a separate frame-by-frame audit and do not inherit this later gate.

Run 37858863664 passed four policy/persistence tests but failed because cleanup destroyed the RenderTexture while still bound to the camera. Cleanup now detaches both its camera target and active binding before Release/DestroyImmediate, with a sixth real native resource-lifecycle regression. No unexpected-log suppression is used. A frame that fails the enemy ground criterion is recorded before the exception so later bounded failure diagnostics can identify its actual worst frame without changing the failed outcome.

Candidate runs use contract-path concurrency groups with cancellation disabled. The checked-in path/hash and source identity must pass before Unity starts. Hosted workspaces and run-ID artifact names are independent. The authorized schedule limits simultaneous candidate imports to the three distinct asset kinds; it never dispatches the same contract twice or changes Unity licensing/runner class.

## Failure diagnostics remain failures

A failed native/quality run may retain a separate FAILED_DIAGNOSTICS packet after independent identity, protected-source, full-import and closed-schema verification. It contains regenerated finite numeric observations and at most eight verified RGB24 PNGs, prioritized by measured ground penetration or explicit weapon failure. It contains no prefab, source assets, raw reports, logs, XML or stack text. Invalid/missing images are excluded while safe numeric observations may survive. The original exception is rethrown and the workflow stays failed; all approval flags remain false. These packets cannot substitute for a complete successful strict candidate.

Pouncer has its own pinned FULL strict contract and exact 184-frame validator. The model root remains scale1; the independent Pouncer_Rig anchor remains scale100 with seventy static TRS curves. Its 27 renderer neutral bounds and nine material mappings come from the new real Discovery. It has no Armored weakpoint/overrun/Core_Open outputs. Pouncer export tests use the already-verified staged source bytes after input staging. Failed Pouncer capture uses the same bounded numeric/at-most-eight-PNG diagnostics without exporting assets or changing the failed outcome.

The exporter threat boundary is the trusted owner/main sequential hosted job with private random staging. Original bytes, declared paths, exact tree and final hashes are checked before atomic commit. This does not claim resistance to an already-compromised host process with the same UID.
