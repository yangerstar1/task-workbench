# Three-region authoring candidate

Baseline: public `yangerstar1/task-workbench` @ `6dc675517db262c72dcb8c1507239d4bf10acc5d`, Unity root `tasks/desert-rv/unity`. Requires the integrated JourneyDirector, JourneyActions, RegionBinding, RegionLoader and rules candidates. This package does not edit JourneyBuild, BodyStudy, TraversalHarness, their metadata, or approved RV models/materials/GUIDs.

Status: source-only candidate. No Unity editor, importer, compiler, build, scene authoring or Unity test was run here. No scene YAML is supplied. No visual/gameplay/device acceptance is claimed. Primitive foundation/cover/cabinets are explicitly candidate environment layout geometry, not approved release art. An actual human review and corresponding asset fingerprints are required before production. 20–30 minute pacing is unmeasured; compact 64 m encounter routes and 28/36 second power intervals are provisional and do not purport to meet a duration target.

## Explicit Actions authoring

Run Unity in the licensed GitHub Actions job, not the assistant's cloud computer:

1. `-batchmode -quit -executeMethod DesertRV.Editor.JourneySceneAuthoring.AuthorCandidateScenes`
2. `-batchmode -quit -executeMethod DesertRV.Editor.JourneyContentChecks.CheckCandidateLayout`
3. EditMode tests including the seven full names below.
4. `-batchmode -quit -executeMethod DesertRV.Editor.JourneyContentChecks.CheckProductionContent` as a separate expected-to-fail readiness stage while assets are absent. Preserve its failure and `JourneyEvidence/production-content.json`; never reinterpret it as gameplay passing because a layout stage passed.

First authoring refuses to overwrite any existing target scene. It opens the saved original only in memory, aligns environment and vehicle to fixed +Z, moves the retained RV/camera/exposure rig into the new persistent root, and saves exclusively to new paths. Source scene and meta bytes are checked in a finally block. It creates one new manifest if absent, with no acceptance defaults. It never invokes the old BodyStudy generator, legacy JourneyBuild, or sets verification flags to true. Additive regions contain neither RV nor Session/Motor/HUD/camera. FirstStation preserves the source station environment; later regions reuse original workshop drums, tower and selected desert scenery dependencies along with explicit layout geometry. Baked-coordinate meshes are recentered through parent pivots without modifying their mesh assets.

New paths:
- `Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity`
- `Assets/DesertRV/Scenes/Journey/FirstStation.unity`
- `Assets/DesertRV/Scenes/Journey/Scrapyard.unity`
- `Assets/DesertRV/Scenes/Journey/NightBeacon.unity`
- `Assets/DesertRV/Scenes/Journey/JourneyContent.asset`

Loader names: `FirstStation`, `Scrapyard`, `NightBeacon`. Do not also include an old scene with the same basename in a production build. Region offsets: 0, 100, 200; forward: global +Z. Spawn rotations retain the actual corrected RV orientation rather than assuming imported model-local +Z. Physical exit volumes finish before the next offset. Cabin workbench belongs exclusively to the RV; regional salvage/power interaction points reference their exact colliders.

If authoring fails after saving an earlier candidate scene, preserve the partial output/log for diagnosis. The tool deliberately refuses to silently overwrite it on retry. Review/archive/remove only these generated candidate outputs explicitly before a clean retry. Never delete or regenerate original reference scenes or approved assets.

## Review and fail-closed content

The manifest records independent Pouncer, Armored and weapon prefab references, source FBX, exact sorted dependency bytes SHA256, Unity dependency hash, generation Actions run URL, visual evidence and motion evidence. `JourneyContentChecks.DependencySha256(assetPath)` computes the deterministic SHA256 over each sorted dependency path/content and its meta, with explicit length prefixes. Approval is manual after actual evidence review. Empty lists or `accepted=true` alone cannot pass. Updating any dependency invalidates the review digest.

Production checks require:
- Persistent prefab identity and actual source FBX dependency, real mesh/material/shader references; independent armored geometry, not the Pouncer prefab or recolored identical mesh set.
- Root enabled physical Collider with bounded dimensions; actor identity; AnimatorController states `Idle`, `Walk`, `Windup`, `Attack`, `Recover`, `Hit`, `Death`, each resolving to real animation curves (including nonempty blend trees).
- Reviewed prefab instances for every bound scene enemy, no unbound enemies, no empty encounters or waves, matching scene Animator and geometry.
- Six real nonempty action AudioClips, including reload. The current baseline has no `reload.wav`; this remains an explicit blocker, not a generated fake sound.
- Retained RV ram/arc geometry, cabin workbench, persistent root ownership, named scenes/order, HUD font, no legacy simulation owner.
- Actual implemented weapon presenter bound to live JourneyActions and visible renderer, reviewed weapon instance under camera; actual arc presenter bound to JourneyActions, retained arc module and an AudioClip; armored weakpoint presenter bound to armored actor and renderer. References do not substitute for runtime/action review.
- Nonempty combat-integration evidence; saved scene dependency hashes tied to reviewed environment/bootstrap screenshots; RegionBinding environment/combat approval flags are still required only after that review.

The current runtime does not supply those complete presentation components, independent approved Armored, accepted Pouncer/weapon or reload audio. Authoring deliberately does not fabricate them or try to guess presenter fields. Wire the real implementations and instantiated weapon once available, save the scenes, inspect them, and enter exact new fingerprints/evidence. Until then production must remain blocked. Layout validation is intentionally independent of missing combat resources.

Formal Android entrypoint: `DesertRV.Editor.JourneyContentChecks.BuildAndroidProduction`. It does not generate scenes. It performs production preflight, temporarily configures exactly bootstrap plus three regional scenes, builds `Build/JourneyAndroid/DesertRV.apk`, and restores settings. Existing review/harness builds are unchanged. A scene-processing build gate rejects direct formal-scene builds lacking a current preflight fingerprint; this also protects explicit BuildPlayerOptions paths that differ from EditorBuildSettings.

## Required Actions artifacts and acceptance

Upload actual generated `.unity`, `.meta`, manifest and layout `.mat` files and a `git diff --binary` restricted to these new files. Include original BodyStudy/TraversalHarness and approved RV model/material SHA256 inventory before/after to prove preservation. Never replace saved-scene diffs with the author script alone.

Always retain:
- `JourneyEvidence/candidate-layout.json` and `JourneyEvidence/production-content.json` (including failures)
- Editor and test logs; full NUnit XML including the exact fullnames below; import warnings/errors
- Saved scene dependency hashes and prefab/source/Animator/material/audio dependency SHA256 inventories
- Actual screenshots `JourneyEvidence/screenshots/first-station-overview.png`, `scrapyard-overview.png`, `night-beacon-overview.png`, `cabin-workbench.png`, `ram-installed.png`, `arc-pulse.png`, `armored-weakpoint-open.png`, `weapon-fire-reload.png`
- Recorded real spawn/exit, dismount, source station traversal, salvage/installation, physical gate hit, short cover-and-dodge combat, cable connect/disconnect, two power-wave encounters, safezone finish, repeated whole-run failure/restart, loading failure/retry and app background/resume checks
- Full-playthrough JourneyTelemetry plus Android device/performance evidence; no claim that editor layout checks validate pace, quality, runtime combat, APK installation or Android safety-area/input behavior

### EditMode test fullnames (seven)

`Assets/DesertRV/Tests/EditMode/JourneyContentTests.cs` uses the existing `DesertRV.EditModeTests` asmdef and reflection into Assembly-CSharp / Assembly-CSharp-Editor; no new test assembly or changes to the original asmdef.

- `DesertRV.Tests.JourneyContentTests.Manifest_MissingAssetFailsClosed`
- `DesertRV.Tests.JourneyContentTests.Manifest_EmptyReviewsCannotPass`
- `DesertRV.Tests.JourneyContentTests.Manifest_ApprovalBooleanDoesNotReplaceAssetEvidence`
- `DesertRV.Tests.JourneyContentTests.Authoring_UsesNewPathsAndPreservesLegacyScenes`
- `DesertRV.Tests.JourneyContentTests.Authoring_OffsetsLeaveFiniteCompactRegions`
- `DesertRV.Tests.JourneyContentTests.Animator_RequiresAllSevenRuntimeNamedStates`
- `DesertRV.Tests.JourneyContentTests.Evidence_MissingDependencyCannotProduceReviewDigest`

These are authored contract tests, not reported as executed. They augment rather than replace existing EditMode/PlayMode and device checks. Add all seven fullnames to the strict expected-tests inventory when integrating this candidate.

## Executable environment-only render and preservation hook

`DesertRV.Editor.JourneySceneAuthoring.AuthorAndCaptureEnvironmentCandidates` runs actual authoring, candidate-layout checking and screenshot capture without requiring enemy/weapon assets. It does not call the production content gate or enable verification flags. To recapture previously generated saved scenes without reauthoring use `DesertRV.Editor.JourneySceneAuthoring.CaptureEnvironmentCandidates`.

Run with the licensed Unity runner's virtual display/software graphics, `-batchmode -quit`, but **not** `-nographics`. Actual graphics-device availability and URP render-request support are checked; null graphics, empty/near-black images, missing scenery and failed render targets throw rather than producing success evidence. Unity's [single-camera URP render-request API](https://docs.unity.com/en-us/engine/6000.0/script-reference/unityengine/rendering/renderpipeline/submitrenderrequest) is used, matching the existing project's render technique. These hooks remain unexecuted in the assistant environment and require real Actions validation.

Each region is loaded additively alongside the real saved Bootstrap, made active for its RenderSettings, and photographed with the retained RV/camera in EditMode. No game completion, enemy simulation or review acceptance is inferred. Captures are 1440×900:
- `JourneyEvidence/environment/FirstStation-{overview,ground,landmark,cabin}.png`
- `JourneyEvidence/environment/Scrapyard-{overview,ground,landmark,cabin}.png`
- `JourneyEvidence/environment/NightBeacon-{overview,ground,landmark,cabin}.png`
- `JourneyEvidence/environment/capture-report.json` records saved-scene dependency hashes and nonblank-image diagnostic values, not visual approval.

The scenes contain retained asphalt segments with broken edges/gaps, reusable detailed drums/tower/cacti/agave and near/middle/far mesa groups. Materials are reused read-only. Saved per-region procedural sky/ambient/fog/sun settings distinguish warm low evening light, dusty amber haze and readable blue night with warm route lights. Actual runtime RegionLoader must activate each loaded scene to adopt its settings; merely loading additively is insufficient.

All generated Unity assets, including the manifest, sky/layout materials and their meta, are now under the new `Assets/DesertRV/Scenes/Journey/` tree. The author and capture hooks snapshot all pre-existing Assets outside that tree plus ProjectSettings and Packages, then byte-check them in finally; changes or unexpected new files outside the permitted generated tree fail. `JourneyEvidence/protected-source-sha256.txt` is the before inventory. Capture never saves camera/RV preview changes; RT, image objects, original active render target and scene setup are restored in finally.

Use `scripts/run_environment_evidence.sh` in the actual Actions checkout to collect all generated new file diffs (including untracked files), scene/meta/material snapshots, layout report and screenshot report. A capture failure remains a failure. The script does not claim formal readiness and never changes project settings or deletes original scenes/assets.

## Manual native environment evidence (separate from gameplay checks)

Owner dispatch on public main: `Desert RV environment candidate evidence`, no inputs. Standard `ubuntu-24.04`, CPU software Mesa OpenGL only; no paid GPU or larger runner. It runs only `DesertRV.EditorRenderTests`, which calls `JourneySceneAuthoring.AuthorAndCaptureEnvironmentCandidates` through reflection. The existing 78 EditMode and 6 PlayMode test inventories remain separate and are NOT_RUN by this job. A successful candidate capture is not production art approval or an APK.

GameCI test-runner is fixed at `0ff419b913a3630032cbe0de48a0099b5a9f0ed9` (v4.3.1). Its reviewed `dist/platforms/ubuntu/run_tests.sh` invokes Editor tests without `-nographics`; the pinned official image's `unity-editor` wrapper uses Xvfb. Software rendering adds only official Ubuntu Mesa/Xauth packages in a disposable derived image, sets `LIBGL_ALWAYS_SOFTWARE=1` / `GALLIUM_DRIVER=llvmpipe`, and validates `glxinfo` before secrets are used. The job forces `-force-glcore`; both native and independent Python checks require a real non-null OpenGL device, and the receipt requires llvmpipe. Missing graphics, initialization, render support, blank images, or any changed tracked source fail closed.

Reviewed implementation:
- https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh
- https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/src/model/docker.ts
- https://github.com/game-ci/docker/blob/75891f03fd6c243db6198f285313118cef0fc806/images/ubuntu/editor/Dockerfile

The immutable base is `unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264`, the actual official `ubuntu-6000.3.19f1-linux-il2cpp-3` image recorded in successful baseline test job 113377169629. The runtime wrapper and renderer are revalidated rather than assuming current upstream source proves an old image's contents.

Only the sanitized artifact directory is uploaded: exactly twelve 1440×900 PNGs (overview/ground/landmark/cabin for FirstStation/Scrapyard/NightBeacon), allowlisted generated Journey scene/material/content/meta files, generated-files diff, run/source-bound receipt and SHA256 inventory. Absolute native paths, raw Unity or licensing logs, XML, cache, credentials and the complete workspace are excluded. Native XML is checked locally and its digest enters the receipt. All pre-existing tracked source, assets, meta/GUIDs, Packages and ProjectSettings must have identical before/after hashes. Source files in this change are authored and statically checked; native 78/6 tests and environment capture require new runs at the new commit.
