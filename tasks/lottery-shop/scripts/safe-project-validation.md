# Private-output project verification candidate

Status: LOCAL_CANDIDATE_NOT_RUN. This candidate changes only diagnostic CI/scripts. Unity project source, models, audio, old test contracts and formal G3 workflows are unchanged. The current reviewed r3 project remains the input. Activation-only run 38359552370 succeeded, but is not project/test evidence.

## Chosen route

Reuse the already reviewed bounded-process, image-digest, serial derivation and container cleanup helpers in activation_probe.py. Create one uniquely named disposable container, activate once, then run three independent Unity Editor processes in that same container/root: new capture fixture, exact original EditMode, exact original PlayMode. This avoids moving a license or repeating activation for every test group. It does not run the raw-logging GameCI Node action or source run_steps.sh/run_tests.sh, which print whole native logs/XML.

The public input reference is game-ci/unity-test-runner commit 0ff419b913a3630032cbe0de48a0099b5a9f0ed9. The checked-out pin and normalized activation/return commands are checked before activation. Same observed image digest: unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264. No new credential or permission is introduced. Only the existing three secret references are passed at container start. Test and finish steps inherit no new host secret values.

The lottery workspace is mounted as in the original runner. Public BlankProject/config inputs are read-only mounts; BlankProject is copied inside the container. Unlike the original runner, host home/license directories are not mounted. Container root holds only this disposable session's licensing state. This is an intentional isolation difference, not proof that all prior environment factors are unchanged. The same container is retained across all three Editor invocations and removed after this attempt.

## Test invocation parity

The exact three argv lists have synthetic literal comparisons against the pinned invocation pattern and original workflow parameters. All keep batchmode, projectPath, coverageResultsPath, runTests, correct testPlatform/testResults, enableCodeCoverage, debugCodeOptimization, original coverageOptions, exact assembly list, worker count and source/run arguments. Capture alone keeps its original probeRunAttempt. Capture and original Play keep force-glcore and 1280x720. No project invocation adds quit, nographics or executeMethod. The existing unity-editor executable supplies its established xvfb wrapper; no nested display launcher is added.

Only native log transport changes from a host .log plus cat to /dev/stdout captured by the private bounded subprocess path. No native log or XML is printed. The existing IPrebuildSetup and r3 scene-preservation guard still execute naturally. Capture stays a separate assembly/Editor invocation, preserving its lifecycle-probe identity.

Original PNG/XML paths remain identical. Stage-specific XML is cleared only at its fixed destination before its one invocation. Existing exports validate exact 11 frames, original 287/32 identities/results and the original separate 14-frame group without changing their gates. Source/media snapshots and finite raw-XML screening remain the original validators. Every failed native or validator step still fails the overall job; continue-on-error is not used. A capture test assertion failure may be followed by original regressions to collect evidence. A timeout, missing exit marker, native activation failure or invalid session blocks subsequent native execution.

## Process status, output and cleanup

Each start/capture/Edit/Play/finish receipt binds phase, source/run/attempt, image/pin, real Docker exit, observed native exit marker and fixed activation-response counts. Missing native or process exit stays null. The scanner never exports free-form messages, identifiers, raw XML, command output or exception text. It preserves observed native markers if a later timeout happens. Contradictory explicit native activation-failure counts cannot produce a successful result.

Native stdout and stderr are combined, never decoded or echoed, bounded to 8 MiB with 256-byte carry. Docker logging is disabled. Exception/cancellation/timeout paths use fixed enums. No credential value is in host argv or any receipt. Each phase uses the same attempt-owned container; phase repetition and second activation are rejected. The source-bound session file contains no secrets.

Only a recorded successful activation in this attempt's still-ready container permits the original return-license command. It operates within that same container and BlankProject context, never selects a user's other machine, and has its own native exit/receipt. If ownership/readiness cannot be established, return is skipped and cleanup is attempted only on this attempt's unique container name. A timed-out native call causes container destruction rather than trying to run another Unity process alongside it. Cleanup requires a successful exact-name query proving absence; unknown or remaining containers fail closed. Return/cleanup cannot replace or erase any earlier test failure.

Abrupt runner loss or forced termination may prevent final cleanup/upload; no receipt is then fabricated. Destroying the temporary container does not itself prove Unity service-side allocation return. A skipped/failed return is explicitly recorded.

## Bounded timing

Image pull: 600 seconds; container creation: 60; activation: 180. Capture: 1800 seconds, same 30-minute native upper bound; Edit and Play: 480 seconds each (past observed cold steps were under three/five minutes, and project import occurs first in capture). Return: 180; cleanup calls: at most 20 seconds each. Stage action windows are 14/32/10/10/5 minutes. The diagnostic job cap becomes 75 minutes to leave a cleanup/upload window rather than allowing the old 60-minute job boundary to cut off evidence. These are infrastructure limits, not skipped tests or relaxed pass thresholds. Synthetic timeout assertions were adjusted only to match the new explicit infrastructure bounds.

## Source/trigger/artifacts

The existing request-only visual workflow trigger and independent source guard remain. A normal source checkpoint does not change the request. Root must separately review/freeze/publish the source, then create its one request-only child commit. The helper also requires first run attempt and unique session creation. No new trigger is included in this candidate.

Capture upload gains only safe-start.json and safe-capture.json. The final regression upload gains the six exact safe-{start,capture,regression-edit,regression-play,finish,session}.json files. Existing explicit PNG/XML/source receipt allowlists are unchanged; no wildcard or native raw log is introduced. Tests never receive real credentials.

## Verification scope

91 synthetic/local-process tests passed: original 56 validator/source tests, the already reviewed 20 activation tests and 15 safe-project boundary tests. Checks cover exact native argv, arbitrary payload suppression across stdout/stderr, invalid UTF-8, bounded scanning/timeouts, native/process exit truth, one activation, stage repetition, capture-failure continuation, timeout blocking, source/run ownership, return scope and cleanup failure. They execute only invented local fixtures and do not invoke Docker/Unity or establish native project success.
