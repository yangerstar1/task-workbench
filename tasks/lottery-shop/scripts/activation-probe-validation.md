# Single activation diagnostic candidate

Status: LOCAL_CANDIDATE_NOT_EXECUTED. No new trigger is included. The four added source files do not match the new workflow's request-only path, nor the existing visual/formal workflow trigger paths. Root remains the sole publisher.

## Scope and actual side effect

Exactly one invocation of the existing Unity activation command, with the existing UNITY_LICENSE, UNITY_EMAIL and UNITY_PASSWORD secret references. DeveloperData/base64/four-byte-prefix serial derivation follows the current pinned runner's input.ts. Inputs are consumed transiently inside the runner process for their already authorized activation purpose; they are never printed, written to source receipts, added to host process argv, or exposed to tests. No new credentials, account login, secret values, license export/upload, persistent access or broader permissions are introduced.

This is a real activation request, not a read-only check. It contacts Unity licensing and can create transient license state in that one disposable container, as the prior runner did. The existing Personal conditional machine-ID initialization is retained inside the container; no identity is read/exported. No other machine's license is returned. It cannot guarantee anything about Unity's service-side activation bookkeeping. Any requirement to replace/regenerate credentials or change account licensing remains user-managed and outside this diagnostic.

## Exact pinned mechanism, deliberate narrow adapter

Public reference pin: game-ci/unity-test-runner 0ff419b913a3630032cbe0de48a0099b5a9f0ed9.

- [input.ts](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/src/model/input.ts): derive the serial from the already-provided license.
- [activate.sh](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/activate.sh): serial activation command and real process exit status.
- [entrypoint.sh](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/entrypoint.sh): existing Personal machine-ID initialization.

The adapter checks the checked-out upstream commit and verifies its exact normalized native command. It invokes that command once, not the original five-attempt shell loop. It never calls run_steps.sh, run_tests.sh or return_license.sh. The same run04/05 image bytes are selected by digest: unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264 (observed tag ubuntu-6000.3.19f1-linux-il2cpp-3).

Only the pinned public BlankProject and config are mounted read-only. BlankProject is copied inside the disposable container before activation. The lottery project, host home/license directories, Docker socket and unrelated credentials are not mounted/passed. This isolation differs from the full runner's workspace/home mounts and is disclosed: a successful diagnostic is evidence of this activation-only environment, not a test run or proof that every full-run environment factor is fixed.

## Output and bounds

All docker pull/run stdout and stderr are merged into a bounded pipe. Raw bytes remain in memory only, are never decoded/printed, and cannot become traceback output. The scanner emits only four fixed message counts and the final shell exit marker. 8 MiB maximum process output, 256-byte retained overlap, 10-minute pull bound and 3-minute native-process bound. The action has 14 minutes inside a 20-minute job, leaving upload time. No retry loop and no rerun attempts: GITHUB_RUN_ATTEMPT must be 1.

Docker uses --log-driver=none and --rm. The finally path terminates a blocked child process group and requests force-removal only of the named container for this run/attempt. A bounded exact-name docker ps query must then succeed and return no container; --rm already having removed it is normal. Query failure, timeout or a remaining container blocks overall success. Separate activationStatus and cleanup status preserve both outcomes. No broad container/license cleanup. A hard runner loss or forced kill can prevent cleanup or receipts; absence is not success. Container-local license/log state is transient, never an artifact. No raw log temp file is produced.

Real docker process status and a single native exit marker are both required for activation-only success. Missing native marker means native status unknown; docker 125/126/127 is not relabelled a Unity exit code. Entitlement-success text cannot override any process failure. Code400 is an observation counter, not a guessed account diagnosis. A zero native/process exit accompanied by an explicit Code400 or native-abort observation is an inconsistent result and fails closed. Known native markers/counters survive a later timeout; unknown process exits remain null. Timeout, cancellation, malformed inputs, output overflow and unexpected exceptions all fail with fixed statuses and no exception/argv/env dump.

Two exact JSON paths may upload: source-receipt.json and activation-receipt.json. No wildcard, raw log, project data, license file or native exception text is uploaded. Source/run/attempt, image digest, upstream pin and explicit NOT_RUN game/device/G3 fields remain attached. Even successful activation cannot pass the visual candidate or any existing 287/32 gate.

## Source review and request

The first source checkpoint adds only these four files. After independent review freezes that commit, root can make one direct child commit changing only tasks/lottery-shop/ci/activation-probe-request.json. Required bounded fields:

- schemaVersion: 1
- requestId: lottery-activation-YYYYMMDD-NN
- sourceCommit: exact reviewed parent SHA
- purpose: ACTIVATION_DIAGNOSTIC_ONLY_NOT_GAME_OR_G3_PASS
- sourceReview: sourceCommit, reviewedAtUtc, reviewId (activation-source-YYYYMMDD-NN), reviewer (independent-source-review), status (APPROVED_FOR_ACTIVATION_DIAGNOSTIC_ONLY)

The guard binds fixed repo/branch/actor, non-fork public push, first run attempt, current HEAD and request-only diff. Review is a fixed-actor attestation, not a cryptographic signature. It does not reuse visual/G3 approval.

## Verification

20 synthetic/local-process tests exercise source/actor/review/attempt rejection, mixed-stream arbitrary XML and invalid UTF-8 suppression, chunked fixed-message counting, output and time limits, missing executable, real nonzero exit precedence, unknown native exit, cancel/exception cleanup and fixed upload scope. The subprocess fixtures contain invented sentinels only. They do not invoke Docker/Unity, use real secrets, activate a license or establish native success.

## Review revision r2

The original 14ba04c308a7a705ae390e497e70888eab9fa176398d82136123e2e0ec1707a9 candidate remains frozen and was returned for two concrete issues: cleanup was requested but unverified, and contradictory native failure text could coexist with a zero-exit success verdict. This revision verifies container absence, refuses inconsistent native results, and retains observations obtained before a later timeout. Five additional synthetic tests cover these paths. No workflow, project, runtime or authentication-scope changes were added.
