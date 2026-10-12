# G3 verification pipeline

Status: PIPELINE_IMPLEMENTATION_PREPARED_NATIVE_NOT_RUN. This document does not report native execution or G3 acceptance.

## Bounded route

- The dedicated G3 workflow is inert until a separate request-only commit changes ci/g3-request.json. This scaffold never creates that file.
- A fresh approved ci/g3-preflight.review.json must bind the exact committed input file SHA-256 map and an ancestor reviewed source commit. The review itself and triggering request are excluded from that map to avoid circular hashes. Old G0/G2 files remain unchanged. If the old G2 trigger is deliberately omitted from the authoring workspace, its existing reviewed document supplies only an expected hash; the runner verifies the actual committed old request bytes. No old request is created or retriggered.
- The entire Git repository tree, including modes and types, must equal the reviewed source commit except the two exact review/request paths. The input map covers every task file, including ancestor Directory.Build.props/targets, NuGet configuration and arbitrary extensions. Actual checkout bytes, executable modes and symlinks are checked before process compilation and Unity snapshots; untracked/ignored materialized inputs are rejected. Metadata/request exceptions must themselves equal their committed bytes. Initial guard, process compilation and first/cold Unity snapshots require pristine committed sources; only the exact restored licensed font is admitted after restoration. Later invocations admit enumerated runtime outputs and audited generated Unity changes. Real temporary-Git regression tests exercise post-review insertion, modification, deletion, mode/link drift, ignored/untracked inputs and control-file drift.
- The absent large font in a text-only preparation workspace is represented by its previously pinned expected digest. CI verifies the actual committed font archive bytes, then the decompressed original font and license; a local expected digest is not evidence of having downloaded those bytes.
- The workflow retains the accepted pinned checkout, upload, Unity test-runner and Unity builder actions, Unity 6000.3.19f1, existing secret names, shared unity-personal-proof concurrency, read-only repository permissions, and 30/45-minute job limits. It adds no SDK installer, cache restoration, payment, dispatch permission or third-party service.
- Sequence: existing 25 Linux/.NET G2 process kills; 36 G3 commit-window kills and one closed-waiting lifecycle kill; native baseline EditMode45; baseline PlayMode8 and four original frames; G3 exact EditMode; G3 exact PlayMode and original frames; independent cold ARM64 IL2CPP Android build.

## New process coverage

Every command executes production G3 Core/Persistence source in a separate .NET8 process. The parent harness waits for an actual fault hook, sends SIGKILL to its own child PID, checks exit code -9, starts a fresh verifier process, checks authoritative recovery, replays the same command, and replays again with a stale revision. This is not an exception/dispose simulation and is not Android force-stop or power-loss evidence.

Six families: challenge-cell selection, copy-paper consumption, atomic old-tool sale/new-tool purchase, borrowing, friend repayment, night payment. Each covers BeforeWrite, TempHalfWritten, TempFlushed, BeforePublish, AfterPublish, BeforeResponse. Fixed numeric observations accompany canonical before/expected/recovered/final hashes; generic PASS is insufficient.

A separate G3 ad-waiting case begins in an explicitly marked SYNTHETIC_AD_FIXTURE. The real G3 store commits CLOSED_AWAITING_REWARD, holds its live writer lease, and pauses until the parent actually sends SIGKILL. A fresh process verifies original copy-paper stock, common quality, 1500-minor reservation, drawer 0 and 30000-minor cash, rejects normal purchase of reserved stock and spending reserved cash, and proves a poll without reward makes no change. Only then is a durable late reward delivered. Exactly one 1500-minor debit, one original drawer item, one stock removal and one success count must result; duplicate provider reward, poll and stale commit leave the canonical state unchanged. Fixed observations independently assert 6 waiting commands and 10 final commands, alongside state hashes.

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

2026-10-12:108 existing Python helper tests and43 new G3 validator tests (including actual temporary Git repositories) passed. Python AST and YAML parsing passed. These check the validators only. No local dotnet compiler, Unity Editor, native NUnit run, graphics frame or APK was executed here.

The binary AXML parser was also checked read-only against the preserved real G2 run38256015857 APK (SHA-2566e7e8cee8e465ed7ca19d9c35586ca2cc9193d2fc3dc24ff2809be75e007d128), observing package com.buyuqi.lotteryprobe, versionName0.0.2 and versionCode2. This checks the parser against existing native output; it is not a G3 build. Baseline comparison found16 existing helper/workflow files and119 existing Unity files byte-identical to accepted G2 candidate010.

The authored G3 capture contract has14 ordered original frames. Thirteen belong to the single marked g3-day-qafixture-001 diagnostic run; challenge-protected is explicitly the separate g3-protected-render-fixture with SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE. The validator checks each frame’s game-run identity and fixture label. These are disclosed test inputs, not natural-run probability or human-input evidence.

Candidate001 authored identities were baseline Edit45/Play8, G3 Edit225/Play12. Candidate002 freezes G3 Edit236 (102 persistence,32 ads,68 economy,26 day-core,1 fixed day scenario,7 snapshot identity) and Play18 from final owner source-hash manifests. All existing12 Play identities are retained; six new cases cover current/next isolation, normal startup/resume, cancelled boost selection, accurate no-change feedback, diagnostic-entry preservation and the continuous 75-step marked scenario. Every parameterized instance is separately named. Contract freezing authorizes no trigger and proves no native execution; the independent preflight remains DRAFT_NOT_APPROVED.

Candidate003 active-tree hardening after immutable candidate002: reject directory symlinks before pruning enumerated output roots. The full read-only preflight now precedes legacy.guard, which writes its receipt; artifacts/evidence/build descendants are also scanned for file/directory links before any receipt write. Four further real-Git subcases verify legacy.guard is never called and an outside sentinel stays unchanged for linked evidence root, guard receipt, nested stage directory or artifact file. Eight real temporary-Git negative subcases cover artifacts, evidence, build and the five Unity runtime-output roots. This repair does not alter or retroactively approve candidate002.
The G3 process runner likewise performs no receipt cleanup before its guard succeeds and writes no diagnostic on guard failure. A real-Git negative preserves both outside temporary receipt files unchanged when evidence is linked.


### Candidate003 same-vulnerability entrypoint sweep

- `g3_ci.py source-preflight` and `review-manifest`: read-only helpers plus stdout; no receipt, cleanup or generated file write. Bytecode output is disabled before loading legacy helpers.
- `g3_ci.py guard/restore-font/snapshot/audit/tests/captures/apk/diagnostics`: all eight commands enter the same read-only tree/input/output closure before `legacy.guard`, common receipt creation, per-stage cleanup or success/failure exports. Real temporary-Git negatives call every command with a linked evidence root and prove the legacy writer is not called and outside bytes stay unchanged. The top-level failure handler only emits fixed stderr text.
- `g3_process.py regression`: a tested G3 wrapper closes inputs/destinations before delegating to unchanged G2 code, including G2's early cleanup and diagnostic behavior. A negative proves no delegation occurs on a linked destination.
- `g3_process.py new`: guard/input closure precedes receipt deletion, compilation workspace creation and all process writes. A guard-stage failure cannot call its diagnostic writer. Later failure diagnostics target the already validated evidence tree. Reused process workspace paths are refused.
- `g3_prepare_runner.sh`: `set -euo pipefail`; the guarded Python command precedes every destructive command. Its fixed disposable-runner system cleanup paths are unchanged, never derived from checkout paths. Shell syntax/static ordering only were checked locally; cleanup was not run here.
- Workflow direct shell before Android: only `test ! -e` checks precede guarded font/snapshot commands. The independent checkout, cold Library/build checks and protected source snapshot precede GameCI and `G3Build.BuildAndroid`. Editor scene/APK/receipt writes are downstream of this gate, not a separately launched unguarded CI entry.
- `process-g3/Program.cs` prepare/crash/verify modes are launched only after the parent gate, into a fresh bounded scenario directory beneath the verified artifacts root; no new external worker entry was added. `g3_test_ci.py` writes only disposable temporary test repositories/sentinels; it does not write project artifacts or native results.

The path checks reject existing checkout/output redirection. They do not claim sandbox isolation against a separate concurrent adversary replacing files after a successful check. The existing runner-provided GITHUB_OUTPUT stream is the sole non-checkout status output; repository input never supplies that destination.


### Candidate004 hardlink and file-type closure

Candidate003's symlink patch did not stop regular files shared by hard links. Candidate004 uses lstat in input/output closure before hashing or writing, and checks the review-control type before parsing its JSON. It requires every execution input, review/request control file, restored/generated Unity file and every file in all eight runtime-output subtrees to be an ordinary file with exactly one hard link. Directories must be actual directories; symlinks, dangling links and special files are rejected without opening them. Runtime-output byte hashes remain exempt, but no output subtree is skipped for alias/type checks. Git's own control directory is not traversed. The complete traversal is bounded to100000 entries and rejects overflow; native compatibility remains unexecuted and cannot be assumed.

Real temporary-Git negatives cover hardlinks under each of the eight output roots, guard/process/diagnostic receipt aliases, unchanged-byte source/control aliases and FIFOs under every output root. The tests prove guard/delegated diagnostics are not called, shared sentinels remain byte-identical and process receipts are not deleted. The earlier symlink, initial-write ordering and all-entrypoint tests remain active. Directory containers are permitted, while only regular single-link file leaves can be read or written through this pipeline. This closes pre-existing aliases, not adversarial concurrent path replacement after validation.

Initial guards, process compilation and first/cold snapshots also reject pre-existing Unity runtime cache/output directories. Later verified Unity stages admit their regular generated bytes, while still traversing all directories and file leaves for alias/type safety. Additional negatives cover hardlinked restored fonts/generated settings and a FIFO review control rejected before the JSON reader is called; a positive fixture proves ordinary later-stage output files still pass.


### Candidate005 actual-run helper repair

Actual run01, 38275073822, source15f3d2aaf146c3e7e5f7fb7c91bec484d107ac7b, passed the initial guard and108 baseline Python helpers. Its42 new helper tests stopped at `testReviewManifestExcludesOnlyRequestAndReview`: that authoring-only test incorrectly scanned the live checkout after the guard had created legitimate evidence. .NET, Unity and Android were skipped; no native result or artifact is claimed.

Candidate005 isolates this helper in a purpose-built temporary authoring fixture with exact expected file hashes, preserved archive/old-request expected pins and explicit generated-output refusal. An additional regression runs the actual guard against a real disposable Git repository with disclosed synthetic runner metadata, observes the legitimate receipt, confirms runtime source closure still accepts it, confirms the authoring manifest still rejects output contamination, and runs the isolated helper successfully afterward. No production source-closure rule is relaxed. The new request review identity is lottery-g3-20261012-02; preflight remains DRAFT_NOT_APPROVED and this authoring tree creates no actual trigger.
A second local integration copied the complete active task/workflows into a disposable Git repository, force-added the already-authored inputs so repository ignore rules could not omit approved assets, ran the actual guard with synthetic event metadata, then ran both complete helper suites. All108 baseline and43 G3 helpers passed with the generated guard evidence present; the receipt hash remained unchanged and runtime preflight still passed. This is local Python/Git verification only.
