# G3 verification pipeline

Status: PIPELINE_IMPLEMENTATION_PREPARED_NATIVE_NOT_RUN. This document does not report native execution or G3 acceptance.

## Bounded route

- The dedicated G3 workflow is inert until a separate request-only commit changes ci/g3-request.json. This scaffold never creates that file.
- A fresh approved ci/g3-preflight.review.json must bind the exact committed input file SHA-256 map and an ancestor reviewed source commit. The review itself and triggering request are excluded from that map to avoid circular hashes. Old G0/G2 files remain unchanged. If the old G2 trigger is deliberately omitted from the authoring workspace, its existing reviewed document supplies only an expected hash; the runner verifies the actual committed old request bytes. No old request is created or retriggered.
- The absent large font in a text-only preparation workspace is represented by its previously pinned expected digest. CI verifies the actual committed font archive bytes, then the decompressed original font and license; a local expected digest is not evidence of having downloaded those bytes.
- The workflow retains the accepted pinned checkout, upload, Unity test-runner and Unity builder actions, Unity 6000.3.19f1, existing secret names, shared unity-personal-proof concurrency, read-only repository permissions, and 30/45-minute job limits. It adds no SDK installer, cache restoration, payment, dispatch permission or third-party service.
- Sequence: existing 25 Linux/.NET G2 process kills; 36 additional G3 process kills; native baseline EditMode45; baseline PlayMode8 and four original frames; G3 exact EditMode; G3 exact PlayMode and original frames; independent cold ARM64 IL2CPP Android build.

## New process coverage

Every command executes production G3 Core/Persistence source in a separate .NET8 process. The parent harness waits for an actual fault hook, sends SIGKILL to its own child PID, checks exit code -9, starts a fresh verifier process, checks authoritative recovery, replays the same command, and replays again with a stale revision. This is not an exception/dispose simulation and is not Android force-stop or power-loss evidence.

Six families: challenge-cell selection, copy-paper consumption, atomic old-tool sale/new-tool purchase, borrowing, friend repayment, night payment. Each covers BeforeWrite, TempHalfWritten, TempFlushed, BeforePublish, AfterPublish, BeforeResponse. Fixed numeric observations accompany canonical before/expected/recovered/final hashes; generic PASS is insufficient.

Fixtures are labelled, new-run-only states. Diagnostic purchases use the reviewed number seed and legal stock/challenge inputs. Six-owned replacement cannot be naturally reached from one day's three stock: its explicitly synthetic boundary starts with30000 minor minus six initial purchases29500 =500, borrows20000 through the ordinary service, sells loss_mat for1500, and purchases alternating_stamp for14000, leaving8000. It does not inject debug money or claim normal day-one reachability.

## Native and generated-source audit

Original safe NUnit XML is retained. Exact assembly ownership, exact full case identities, zero failed/skipped/inconclusive cases and counts are validated before a profile passes. Contract status must be FROZEN_FOR_CI, never DRAFT.

Each Unity invocation snapshots every Assets/Packages/ProjectSettings file. Existing bounded normalization clears only the unused ps4Passcode scalar after proving its exact-empty baseline; other credential-like settings fail closed. Artifacts distinguish normalized data from original bytes. Full source audit remains enabled. The G3-generated allowlist is exactly Assets/G3/Scenes/G3Day.unity, its .meta and Assets/G3/Scenes.meta. Original G0 generated probe paths are explicitly enumerated, and G2's accepted generated paths are retained. No arbitrary G3 Assets exemption exists.

The two approved PNG files must match the reviewed source SHA, fixed type and1536×1024 3:2 dimensions. Editor preparation validates texture-to-artwork identity, import NPOT None, no downsize/compression and matching asset GUID. Runtime bindings must be committed already, including verification fields; they are not free-to-mutate generated files.

## Android identity and limits

The Android job uses a separate checkout with no Library and no G3 build directory before Unity; it restores no prior job artifacts or cache. This observation is recorded separately. The native build uses versionName0.0.3 and versionCode3, package com.buyuqi.lotteryprobe, ARM64 IL2CPP, OpenGLES3, minSDK26/targetSDK35 and development signing. Verification checks source/run receipt, hash and size, APK ZIP CRC, native AArch64 ELF and IL2CPP entries, resolved packages and compiled binary AndroidManifest AXML package/version, rather than trusting receipt version declarations alone.

No raw Unity/compiler/worker logs are artifact inputs. Failures export only bounded identities, source coordinates/error codes, hashes and allowlisted status fields. Artifact retention is7 days and does not satisfy durable evidence preservation by itself.

Physical touch, Android installation/force-stop, independent normal-input play, final visual/gameplay quality and the G3 stage gate remain NOT_RUN or NOT_PASSED until their actual evidence exists. A built APK or automated input cannot close those gates.

## Local checks actually executed

2026-10-12:108 existing Python helper tests and21 new G3 synthetic validator tests passed. Python AST and YAML parsing passed. These check the validators only. No local dotnet compiler, Unity Editor, native NUnit run, graphics frame or APK was executed here.

The binary AXML parser was also checked read-only against the preserved real G2 run38256015857 APK (SHA-2566e7e8cee8e465ed7ca19d9c35586ca2cc9193d2fc3dc24ff2809be75e007d128), observing package com.buyuqi.lotteryprobe, versionName0.0.2 and versionCode2. This checks the parser against existing native output; it is not a G3 build. Baseline comparison found16 existing helper/workflow files and119 existing Unity files byte-identical to accepted G2 candidate010.

The authored G3 capture contract has14 ordered original frames. Thirteen belong to the single marked g3-day-qafixture-001 diagnostic run; challenge-protected is explicitly the separate g3-protected-render-fixture with SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE. The validator checks each frame’s game-run identity and fixture label. These are disclosed test inputs, not natural-run probability or human-input evidence.

Frozen authored native identities: baseline Edit45 and Play8 are unchanged; G3 Edit225 (98 persistence,32 ads,68 economy,26 day-core,1 fixed day scenario) and Play12 are enumerated exactly. Every parameterized instance is separately named. Contract freezing authorizes no trigger and proves no native execution; the independent preflight remains DRAFT_NOT_APPROVED.
