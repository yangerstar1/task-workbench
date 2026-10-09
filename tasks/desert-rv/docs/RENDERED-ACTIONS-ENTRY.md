# Actual rendered Editor entry: source candidate, not a successful window run

## Verified blocker and official source

Existing GameCI `unity-test-runner@0ff419b913a3630032cbe0de48a0099b5a9f0ed9` invokes `unity-editor -batchmode` in its `run_tests.sh`. The official Docker `unity-editor` wrapper itself calls `xvfb-run ... "$UNITY_PATH/Editor/Unity" -batchmode "$@"`. Neither can launch the actual non-batch GameView on our already-verified display. Passing extra parameters to that test action is not a non-batch solution.

Read primary source:
- [Pinned test invocation](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh)
- [Pinned activation](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/activate.sh), [return](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/return_license.sh), [personal-machine setup](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/entrypoint.sh)
- [Pinned license-to-serial conversion](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/src/model/input.ts)
- [Docker wrapper source](https://github.com/game-ci/docker/blob/75891f03fd6c243db6198f285313118cef0fc806/images/ubuntu/editor/Dockerfile), [UNITY_PATH base](https://github.com/game-ci/docker/blob/75891f03fd6c243db6198f285313118cef0fc806/images/ubuntu/base/Dockerfile)

The Docker repository source read is not claimed to be an attested build-source commit for the previously selected image. The new Dockerfile therefore checks the actual fixed image's version file, raw executable and wrapper behavior before any secret is present. Those image checks have not run in this preparation.

## Small execution shell

`.github/actions/desert-rv-rendered/action.yml` is a same-job composite. It consumes an already-prepared workspace; it does not download/reconstruct candidate project artifacts or author missing scenes/prefabs. `.github/workflows/desert-rv-rendered-smoke.yml` is a manually dispatched, owner/main/public/github-hosted-only 30-second smoke caller. Neither was published or dispatched here.

Reused boundaries:
- Unity 6000.3.19f1, existing immutable image `unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264`, existing Environment.Dockerfile/Mesa llvmpipe, existing prepare_runner/font restoration.
- Existing checkout/upload action commit pins, read-only repository permission, two CPUs/12GiB container limits.
- Existing input recorder, immutable diagnostic scope, PID/title/window-ID first-frame handshake, actual end-of-frame PNGs, ffprobe original-speed checks and atomic allowlist export.
- Existing imported asset/scene authoring is not modified. No KVM, devices, ACL, host networking, user computer or new cloud task is requested.

The small derivative image installs official Ubuntu ffmpeg, xdotool, x11-utils, Openbox and required Python/Pillow/dbus. Openbox is a window manager only, with no desktop/session/terminal launched. GameView uses the same private Xvfb DISPLAY and raw `/opt/unity/Editor/Unity -force-glcore -job-worker-count 2`; it never uses the GameCI wrapper for the rendered process.

## License lifetime and logs

The exact official GameCI repository is checked out at its existing commit; four relevant files are verified against recorded Git blob hashes. Its `dist` directory is mounted read-only. The official activate/return scripts run unchanged. Personal serial extraction follows the pinned Input.ts algorithm and is passed only through captured shell substitution, never logged. Existing UNITY_LICENSE/EMAIL/PASSWORD secrets are inherited from the explicitly authorized caller, not stored as action inputs.

Activation, Unity process and return output goes only to a mode-0700 temporary container directory. No raw log is copied into public export. Before starting the render shell, all license/serial/email/password environment variables are removed from that child. The same activated container profile and machine identity are retained so the actual Editor can use its license. The parent retains credentials solely for the official return script.

EXIT/TERM/INT cleanup attempts the official return after every activation attempt, including activation or render failure. Return has a bounded timeout, changes the exit status on failure and produces only fixed-enum control status. Container-private logs are removed. A runner outage/SIGKILL can prevent any cleanup; the code does not claim that unavoidable case is guaranteed. Normal bounded failures and TERM have the explicit return path.

Private-directory removal now requires both a zero removal result and verified path absence before privateCleanup=SUCCEEDED is written. Status write/readback/permission failures force a nonzero main exit. The host guard requires both the actual GitHub steps.native.outcome=success and privateCleanup=SUCCEEDED, so a stale success-shaped control file cannot authorize video after a failed native step.

Only safe artifact files get public read permission for the host-side guard. Raw evidence/handshake/activation directories do not. The outer host guard checks tracked-source changes, license return, strict export names and hashes. A fresh atomic public export must set `export_ready=true`; the workflow will not upload stale/partial output merely because an `always()` branch ran.

## Independent 30-second window smoke

The smoke opens only the existing saved `Assets/DesertRV/Scenes/BodyStudy.unity`. Its bytes matched main's Git blob `e6c4fb36d948f5215e48f8523de94f2498a00b13` at the reviewed base. It never opens or grants JourneyDiagnosticScope, starts a Journey, adds a fake input plan, grants resources, modifies actors, alters state or weakens a build gate.

It enters actual non-batch PlayMode to render the existing scene. After one actual encoded frame from the exclusively identified floating GameView, an Editor-only recorder runs for 30 wall seconds. It samples rendering frames and captures 1Hz screenshots; a yellow watermark states window-only scope. The native recorder requires OpenGLCore/llvmpipe, the expected saved scene, and no JourneyDirector. It does not move the camera or inject controls.

The C# recorder and exporter explicitly label this WINDOW_SMOKE_ONLY_NOT_GAMEPLAY, with gameplaySessionStarted=false, gameplayInputsApplied=false, gameplayAccepted=false, visualApproved=false and androidVerified=false. The exporter requires at least 29 seconds of samples, at least 25 valid PNGs, actual 30fps video provenance and successful end signal. No audio is captured.

The Linux GameView floating-title behavior, raw binary activation continuity, X11 window identity and first-frame/end-frame timing remain unexecuted until this candidate is reviewed and run once in public Actions. Unsupported title/window/graphics behavior fails closed. No desktop/root-window fallback is present. A nonzero Editor stop withholds video, including focus/window failures. Normal encoder shutdown now uses an owned stdin pipe with q (no -nostdin), and requires the actual wait result to be integer zero. Premature encoder exit, broken pipe, timeout, nonzero exit or missing video produces a fixed failure and no successful video hash. Both journey and smoke export require explicit null failure fields, a successful Editor stop acknowledgment, integer-zero Editor/encoder statuses and the verified stdin-q method. A sourceVerified=true assertion cannot override contradictory failure/status fields.

## Later short actual-game segment

After `JourneyCandidateAssetIntegration.IntegrateFromEnvironment` succeeds in the same job, generate the existing diagnostic scope from those final actual bytes. Call this composite with mode `journey` and exact repository-relative paths/SHA256s for:
1. Actual `JourneyEvidence/journey-candidate-integration.json` with STRICT_CANDIDATES_BOUND_UNREVIEWED, candidateOnly, unchanged protected source, empty failures and real outputs.
2. Final `EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT` scope for the current GITHUB_SHA.
3. An observed/reviewed input plan whose maximum and sum of step durations are at most 120 seconds. Include `observedEvidence.runUrl` (this repository's actual Actions run) and `observedEvidence.artifactSha256`; these are provenance requirements, not fabricated observations or an automatic semantic review.

Missing files/hashes/preparation facts stop before credential activation. The composite does not create a dummy route. Full prefab/Animator/FX/scene wiring still belongs to the existing scene integration worker. Main production Validate/Build gate and acceptance fields remain untouched.

## Integrator checklist

- Merge only the manifest's source paths after review; rebase existing file edits against the recorded Git blobs.
- Append `.github/actions/desert-rv-rendered/action.yml` and `.github/workflows/desert-rv-rendered-smoke.yml` to `verify_evidence.py` SOURCE_FILES without replacing any existing entry. Regenerate/review SOURCE-STATE.json using the existing tool. This is a required integration hunk, not done against another worker's active source file here.
- Keep current expected native test inventory; new helper compilation is required, but this candidate does not invent a native test pass/count.
- First run is the separate smoke, not gameplay and not a default long replay. Root/scene publisher owns publication and the one authorized dispatch.
- Upload only `tasks/desert-rv/rendered-public-export/` after export_ready; do not upload source folders, logs, private evidence or Docker/home directories.
- For real-game use call once per fresh job after actual preparation. Existing output directories are rejected, preventing stale evidence reuse.

## Checks completed here

Bash syntax, Python syntax, YAML parse and 46 local source/protocol/export fixtures passed: 11 rendered-shell guards, 7 capture shutdown cases, 5 cleanup/native-outcome truth cases and 23 safe-export fixtures. These include the independent reviewer’s encoder-exit-1, contradictory-success-receipt, rm-failure, status-write-failure and stale-control counterexamples. Fixtures use synthetic bytes and mocked video probes, not Unity/activation.

One separately authorized real FFmpeg check used only a tiny synthetic solid-color source, an owned stdin q command and ffprobe. It confirmed normal q returns zero and finalizes a readable MP4 on the dot computer’s FFmpeg 7.1.5; its scoped receipt is in review/ffmpeg-q-synthetic-check.json. It does not establish X11/GameView behavior or the container’s FFmpeg runtime. No Docker image was built, license accessed, Unity or X11 process launched, actual game video captured, APK built, workflow published or dispatch sent during this preparation.
