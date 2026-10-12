# G2 CI implementation scope and first-run limits

This is a candidate implementation, not a Unity or APK success report.
The coordinator must freeze/review it and separately commit the single actual
`tasks/lottery-shop/ci/g2-request.json` trigger. Only its review fixture is present
in this working candidate. No external cache is used in this first iteration.

## Native test and build sequence

1. Run local CI-validator regression and compile the same pure-Core C# sources
   with an already installed .NET 8 SDK on the existing Ubuntu runner. No NuGet
   feed or new SDK installation is allowed. A real child process is SIGKILLed
   and restarted for Buy/Scratch/Claim/AdCommit at six explicit commit windows.
   The 24 cases use synthetic state and are Linux/.NET process evidence only.
   They do not prove Unity-process, Android force-stop or power-loss behavior.
2. Run native EditMode with the preserved six G0 case identities and 39 new G2
   cases, each under its own expected assembly. Preserve screened original XML.
   Validate exact identities, counts, ownership and zero failed/skipped cases.
3. After EditMode validation and source audit succeed, run eight exact PlayMode
   cases in the same job/workspace. A new container mounts the same workspace,
   so this job's imported Library is reused without restoring an external cache.
4. Require four state-bound, actual URP camera renders. Then audit source again.
5. Only the whole successful tests job permits the independent cold Android
   checkout/build. APK export still requires native APK verification AND source
   audit. Failed build diagnostics cannot become a candidate APK.

After successful exact EditMode validation AND its source audit, a separate
`lottery-g2-edit-checkpoint-<run>-<attempt>` artifact preserves the same 14
already-screened EditMode/process files before PlayMode begins. This checkpoint
uses the pinned upload action and a subset of the existing final export list;
it contains no Play result, raw log or unverified APK. Final combined export
remains in place. This protects completed evidence from a later job timeout;
it does not bypass any PlayMode/Android gate or extend execution timeouts.

The exact case contract is `ci/g2-test-contract.json`; changes require review.
The G0 helper's default test contract is unchanged. Its only shared audit API
addition is an optional set of explicitly named generated classifications.
The G2 adapter allows exactly `Assets/G2/Scenes/G2Slice.unity`, its metadata and
`Assets/G2/Scenes.meta`; neighboring unknown assets are not exempted.
Recovered G0 generated assets/settings remain accounted separately. Every
stage snapshots its actual pre-Unity baseline and archives permitted outputs.

## Settings publication and generated-evidence preflight

Before any source publication, run `python3 tasks/lottery-shop/scripts/g2_ci.py
source-preflight --root .` from the repository root. This read-only local command
needs neither a request file nor GitHub credentials. It rejects nonempty
credential-like YAML settings fields, unsupported/symlink paths and oversized or
non-UTF-8 files, without printing any settings values. Empty unused credential
fields are retained as empty. This is a bounded structural screen, not a promise
that arbitrary obfuscated secrets are discoverable.

The same screen runs at CI source guard/snapshot and immediately before every
generated-assets archive. If Unity regenerates a nonempty credential field,
the stage fails and its generated archive/lock are withheld; source bytes are
not silently sanitized after execution. The failure receipt contains only
canonical relative path, classification and SHA-256 for the unsafe file, plus
fixed status/identity metadata. The artifact whitelist never includes raw
ProjectSettings files independently of this gated archive. Synthetic tests
cover empty scalars, nonempty keys, block values, symlinks and stale-export
removal. Original G0 sources and historical evidence are not changed.

## Official graphics-path evidence

At pinned [GameCI test-runner source](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh),
EditMode and PlayMode launch the Editor with `-batchmode`, without `-nographics`.
The standalone branch instead adds `-nographics` and copies extra scripts, so
it is not used. The [pinned Docker orchestration](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/src/model/docker.ts)
orders `testMode: all` as PlayMode, EditMode, then combined results. We therefore
use two ordered action invocations rather than assuming `all` means Edit first.
The official [Editor-image wrapper](https://github.com/game-ci/docker/blob/75891f03fd6c243db6198f285313118cef0fc806/images/ubuntu/editor/Dockerfile#L51-L66)
uses Xvfb. That source supports the route; actual renderer identity and frames
must still be established in this run, not inferred from the Dockerfile.

Unity 6000.3 documents that [WaitForEndOfFrame](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/WaitForEndOfFrame.html)
does not execute in Editor batch mode. The Play fixture instead uses
[RenderPipeline.SubmitRenderRequest](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Rendering.RenderPipeline.SubmitRenderRequest.html)
with a `StandardRequest` destination. Unity documents sequential processing and
support for a complete URP base-camera stack. This is also implemented in the
[fixed URP source](https://github.com/Unity-Technologies/Graphics/blob/2d2e78cc9d6254bc6e7c9c5552cea053508e86cb/Packages/com.unity.render-pipelines.universal/Runtime/UniversalRenderPipeline.cs#L533-L599).
A small number of [ReadPixels](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Texture2D.ReadPixels.html)
calls copy those completed targets for PNG export; this is not a per-frame
scratch-progress readback technique.

No null graphics device, unsupported render request or flat image may pass.
The camera includes actual scene/HUD geometry; the export is not a screenshot
of a code-generated imitation or of an IMGUI overlay omitted from the camera.
The four 1280x720 PNGs are `initial`, `half`, `revealed`, `settled`. The receipt
records actual source viewport dimensions separately; command-line dimensions
are not assumed to prove the Editor Game view size. Input events are simulated
through the actual Input System and labeled accordingly. Independent visual
inspection is still PENDING after byte/CRC/hash and test assertions succeed.

## Explicit one-module dependency delta

G0 source and original evidence are immutable. This G2 candidate adds only
`com.unity.modules.imageconversion: 1.0.0` to the project manifest, and only its
`version=1.0.0, depth=0, source=builtin, dependencies={}` entry to the restored
lock. Existing dependency records remain byte-value equivalent. This is a
reviewed candidate lock, not a claim that the new module already imported.

Unity's [6000.3 Image Conversion manual](https://docs.unity3d.com/6000.3/Documentation/Manual/com.unity.modules.imageconversion.html)
identifies it as an Editor-matched built-in package. The exact Editor reference
[source](https://github.com/Unity-Technologies/UnityCsReference/blob/79f16640303119112ca5caed4d71c607d0dff6fb/Modules/ImageConversion/ScriptBindings/ImageConversion.bindings.cs#L39-L40)
places the `Texture2D.EncodeToPNG` extension in this module. It is needed for
actual PNG export, not an external paid graphics or screenshot dependency.
The lock shape is the same bounded built-in-module schema as the restored
modules; its actual resolution must be verified by Unity. Any different resolved
lock fails closed for explicit review, rather than accepting other package drift.

- Previous G0 lock SHA-256: `3380b8f602b673a86b9fa317cf364a6479ed2a6c50b9bf94793a9584646dc9ae`
- Candidate G2 lock SHA-256: `950e703b31453d45443719e88b1a37025d40d388df07c9c3bed31b507fd2f132`
- Frozen runtime rules SHA-256: `e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668`
- Frozen 16-face vector SHA-256: `22af609400604776d2801955946dacd35a057edb0563d3a6069848f6be8adcd9`

## Local verification and remaining work

On 2026-10-12 the local Python suite passed 93 methods (63 preserved plus 30 G2
validator fixtures). The PNG/XML fixtures are synthetic, not native evidence.
One test actually SIGKILLed only its own simple Python child to verify supervisor
behavior; that is not the C# process fixture. Shell syntax/Python parsing and
exact C# method-name/contract comparison were checked. No local Unity or .NET
compiler was available, so native compilation and all actual G2 cases remain
NOT_RUN until the authorized CI candidate executes.

The first G2 run `38238410614` stopped in the Python helper stage because the
sparse checkout omitted the preserved G0 workflow read by a regression test.
No .NET or Unity validation ran in that attempt. Both G2 jobs now include that
exact workflow. A local simulation materializes only the declared sparse input
paths and runs all 63 preserved G0 tests; a negative fixture removes that
workflow and reproduces the missing-file failure. The request-02 candidate still
requires independent review and a separate coordinator-owned actual trigger.

Run 02 (`38238794780`) passed all 85 helper methods, then failed in the process
probe before Unity started. Its fixed console message did not identify the
substage, so the exact observed cause is unknown. Source inspection identified
an independent project defect: `.proj` does not automatically select the C#
compiler targets in [.NET SDK 8.0.425](https://github.com/dotnet/sdk/blob/v8.0.425/src/Tasks/Microsoft.NET.Build.Tasks/sdk/Sdk.targets#L20-L31).
The project is now `scripts/process-probe/G2.ProcessProbe.csproj`, with only that
filename excepted from the existing `*.csproj` ignore rule; the former `.proj`
file must be deleted in the candidate tree. Production source includes, SDK and
all 24 recovery assertions are unchanged. This is a source-supported correction,
not proof that it was the hidden run-02 exception or that compilation now passed.

The request-03 candidate exports a small `process-diagnostic.json` on failure:
fixed stage, selected SDK version, exception type, scenario/commit window, and
at most 32 compiler error codes with allowlisted relative source file/line/column.
Unknown paths become `UNMAPPED`; compiler message text is never exported.
Worker diagnostics accept only fixed assertion IDs and exception-type enums.
Oversized, symlinked or unavailable logs produce `REFUSED_OR_UNAVAILABLE`, not
raw-log fallback. A failure removes any stale PASS receipt. Raw compiler/worker
logs, environment, command lines and save contents remain outside artifact paths.
Tests inject synthetic compiler payloads, unknown paths/IDs, oversized logs,
missing SDK and build failures to verify bounded diagnostics and stale removal.
Only actual request-03 CI can establish compiler/runtime results.

The approved runner's [official Ubuntu 24.04 software inventory](https://github.com/actions/runner-images/blob/bdac7c6000c3501174076ad6d6a06ce46871fa71/images/ubuntu/Ubuntu2404-Readme.md)
lists .NET 8 SDKs. The supervisor still detects the actual installed SDK and
records its exact version; missing SDK/reference packs fail without downloading
new software. It compiles the same Core/Persistence/Ads files with the explicit
`LOTTERY_G2_TEST_FIXTURE` flag and binds their hashes and the worker binary hash.
Only the bounded result receipt is an artifact input; raw worker/compile logs,
CLI home, intermediates and synthetic save directories are not uploaded.

The existing security limits in `VALIDATION.md` still apply: fixed action SHAs,
owner/non-fork/public hosted-Linux guard, contents:read, no cache or release
write-token, secrets only on GameCI steps, and explicitly enumerated artifact
paths. The pinned actions print some native logs before later screening; no
absolute leak-prevention promise is made. Durable evidence storage/readback is
coordinator-owned and remains EVIDENCE_PERSISTENCE_PENDING until verified.
Android installation, real touch, Unity/Android process kill, device performance,
full-day gameplay and product T/V/P acceptance are not implied by these gates.
