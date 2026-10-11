# Fresh Android Journey development candidate

This candidate starts from public source `c15c3ecbde24156d4e4116b129802a9cbd1df926`, whose same-job Linux producer/build ran at https://github.com/yangerstar1/task-workbench/actions/runs/38113296255. It is a new source candidate. Preparing this patch does not compile an APK or certify Android gameplay, and prior Linux R1/R2 observations do not complete R3 or Android acceptance.

## Build path

`.github/workflows/desert-rv-journey-android.yml` is a separate, one-use owner push on `journey-android-c15`. The branch must already point to the exact base before the single candidate commit is pushed; branch creation, force pushes, reruns, other owners, and other parents are rejected. Its request binds the actual source inventory, selection and image. Publication and triggering are separate from local patch preparation.

The workflow reuses the fresh producer's same-job source/font restoration, protected source inventory, strict armored/Pouncer/weapon archives and import/capture gates, authoring of Bootstrap plus three regions, package dependency closure, saved-grounding report and 17 native candidate-boundary cases. The two historical Linux/TraversalHarness workflows and requests are unchanged. It does not restore older prepared scene receipts or use the rejected environment/observer payloads.

All native stages use Android as the active import target from the start. This avoids reusing Linux import fingerprints for an Android build. The shared builder still checks every source/dependency byte, actual scene import hashes, real support bindings, per-scene runtime identity, and exact temporary settings restoration. The original production approval gate stays in force for ordinary/release builds. The new capability requires exactly `DESERTRV_CANDIDATE_ANDROID`, Android, and Development plus DetailedBuildReport. The existing 17-case boundary suite also checks the new Android profile and rejects cross-target, missing/extra define, release and auto-run variants.

Before the expensive APK build, the workflow additionally runs the exact current `expected_playmode_test_cases.json` inventory (13, not the historical 9) and the existing 13 Pouncer ground-support regression cases, with pinned XML receipts. Existing tracer, keyboard look, cabin entry, HUD lifecycle and combat-feedback native stages remain. A separate exact ten-case production mobile HUD suite additionally verifies layout, input arbitration and a finite thirteen-render fixture set: three profiles each for on-foot glare, driving daylight and paused night; compact loading, failed and complete states; and the smaller 568×296 logical-unit safe area under on-foot glare. Every PNG and text-fit CSV is hash-bound, checked for expected dimensions/nonblank pixels/finite unclipped label metrics, preserved before isolated-project cleanup, and pinned with its native XML into the same build input. These fixtures are simulated Editor captures, not physical-device or authored-region gameplay evidence. The old source-diagnostic unit cases remain in this workflow; the old real-Git fixture that requires the prior producer's exact unchanged 14+2 Unity map belongs to the unchanged historical workflow. The new Android dispatch has its own actual-Git corruption tests.

## Official toolchain and signing

Before any cold Docker pull, the existing readiness helper selects the fixed Android profile. It requires the Android digest for cache/target checks and keeps the existing bounded target-plus-preview quota checks, dynamic quota windows, sole same-digest fallback, and sanitized report schema. A Linux cache or report cannot satisfy Android readiness. Zero remaining quota stops before the first pull.

The digest was read from the successful official Android baseline [job 113380892675](https://github.com/yangerstar1/task-workbench/actions/runs/37796490106/job/113380892675):

- `unityci/editor:ubuntu-6000.3.19f1-android-3`
- `unityci/editor@sha256:1e98c949ff728e6ff627b5c55ef65975125a6dc47cf27060601b79a141cc8692`
- Bundled AndroidPlayer, OpenJDK, SDK, NDK, build-tools 36.0.0 and sdkmanager 16.0
- The baseline installed `platforms;android-35` after pulling this image. The candidate does the same through the bundled official sdkmanager, before credentials enter a container, with stdin closed and no new-license auto-acceptance.

The candidate keeps the source minimum SDK and sets target SDK 35, IL2CPP, ARM64 only, one APK, Development, `com.desertrv.journey.dev`, version code 1 and a commit-bound development version. `useCustomKeystore=false`; no release signing key or new signing secret is needed. Existing Unity activation/return scripts and existing Unity license secrets are reused. The APK is intended for sideloaded development testing, not a store release.

Native success alone cannot export a candidate. The consumer also verifies AndroidManifest/dex/ARM64 IL2CPP contents and CRC, aapt's actual package/version/ABI/debuggable/target-SDK values, apksigner verification and Android Debug certificate identity, the exact APK hash and native receipt, unchanged prepared-source closure, and the actual serialized Android class-94 shader registry resolving both URP Unlit (tracer) and URP Lit (surface materials) to packed class-48 shaders. Split asset files are supported only as a complete, uniquely numbered bounded sequence. Source material/package shader dependency proof remains required. Unknown formats fail closed; shader inclusion does not claim rendering correctness.

The existing performance-package source pins, in-memory official-payload validation, private resource quarantine and packed-build report exclusion are reused to keep test-run/system resources out of the APK. Successful export waits for license return and private cleanup. Only the APK and bounded validated manifests/receipts/status leave the build. Raw Unity, Gradle, activation and return logs remain private and are removed. No device, emulator, KVM, store publishing, account creation or release signing step exists here.

## Remaining verification

The local Python/Git/ZIP/XML tests, workflow parsing and patch-application checks are host evidence only. The new Android module imports, C# compile, exact native inventories, same-job authoring, IL2CPP build, SDK tools and shader gate still need the actual approved Actions run. Docker registry or SDK availability is not guaranteed by the historical successful run.

After a successful candidate exists, verify a genuine ARM64 Android device: install/launch; both landscape aspect ratios and safe-area UI; simultaneous movement/look/fire and cancellation on focus loss; cabin enter/exit, vehicle controls and supply interactions; actual combat and Pouncer support transitions; pause/background/resume/restart; complete R1/R2/R3 playthrough; audio and performance. Current Linux R3 remains unfinished. APK compilation or Editor PlayMode passes do not close these acceptance tasks.

References: [GameCI builder](https://game.ci/docs/github/builder/), [pinned test-runner command](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh), [Unity custom keystore](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/PlayerSettings.Android-useCustomKeystore.html), [Unity Android SDK versions](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/AndroidSdkVersions.html).

## Combined production source

This batch also includes the finite surface-art patch: 120 UV-only mesh copies and two URP Lit materials across the three real regions, preserving original mesh geometry and collider values. The ordinary generated-file closure is exactly 322 files. The two new owned Lit materials are normalized through the official public URP keyword/alias routine and must stabilize through two per-path GUID save/synchronous reimport/save cycles before their closure is sealed. The existing native preparation case requires clean persistent objects, unloads and reloads the 122 surface objects, and reopens each saved region before validating bindings. No new permissive asset wildcard or historical scene receipt is used.

The mobile HUD uses the production graph and original CJK font. The original package manifest and lock are preserved. The successful baseline Android build included `AndroidJNIModule` in UnityLinker and IL2CPP inputs even without an explicit module dependency. Native Editor fixtures cannot execute the Android-only density branch. Actual Android safe areas, density, two-thumb controls, focus/resume and readability still require device evidence.

The existing authoring capture loop also preserves exactly two R1/R3 walking-camera world views with the production HUD graph and controlled fixture values. Their four PNG/fit files plus the explicit evidence label are validated and exported after fresh preparation, then pinned into the Android build input. These images are authored-world layout fixtures, not live playthrough evidence.

The existing Android control now preserves the first fixed command/stage/error code or fixed exception class across cleanup. Arbitrary exception text never enters it. A separate strict control-only upload remains available after preflight, restoration, staging or export failure; the APK export still requires all original source, native, package, shader, license-return and cleanup gates.
