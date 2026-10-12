# Linux Editor toolchain dependencies: request 03 preparation

## Native observation

[Run 38223507667](https://github.com/yangerstar1/task-workbench/actions/runs/38223507667)
tested source `99645798cf1df6b8f9daecd28c78ccb1c518c92b`, request
`lottery-g0-20261012-02`. Its six expected native EditMode cases passed, with
zero failed, skipped or inconclusive cases. The source audit still failed, so
the Android job did not run. This is not an APK or full G0 acceptance result.

The sole unexpected source mutation was `Packages/manifest.json`. All seven
original dependency versions were unchanged. Unity added these three entries,
each at exactly `1.1.0`:

- `com.unity.sdk.linux-arm64`
- `com.unity.sdk.linux-x86_64`
- `com.unity.toolchain.linux-x86_64-linux`

The bounded, screened original before/after files were exported by the audit.
Their SHA-256 values are:

- Before: `b8bc23b9a479e87ef923606c7f137fc27a8c4e60b3dd08adf41a743743b0b541`
- After: `bebba50d0c71fadc69ed6542c7c0156410bd46d41f6de2e34b7997510a4741dd`

The after hash matches the first failed run's mutation. The complete 10-file
test artifact, ID `11735203996`, has archive SHA-256
`218dfd29066cf43a1eff5045926189c64369572d232788c218974e0c4006fc47`.
Original XML SHA-256 is
`40d4be6200d0cbc1f0811a3f1fcc70f88a5c399e0a6b80afeba77c7b1f77e30d`.
These existing observations precede the code changes described below.

## Official provenance and its limit

Unity's [6000.3 Linux IL2CPP manual](https://docs.unity3d.com/6000.3/Documentation/Manual/linux-il2cpp-crosscompiler.html)
documents automatic installation of Linux sysroot/toolchain packages when a
Linux target and the relevant prerequisites apply. It also identifies Toolchain
Management as the opt-out setting. The official package manuals identify
[ARM64 Linux SDK 1.1.0](https://docs.unity3d.com/Packages/com.unity.sdk.linux-arm64@1.1/manual/index.html),
[x86_64 Linux SDK 1.1.0](https://docs.unity3d.com/Packages/com.unity.sdk.linux-x86_64@1.1/manual/index.html)
and the [Linux x86_64 host toolchain 1.1.0](https://docs.unity3d.com/Packages/com.unity.toolchain.linux-x86_64-linux@1.1/manual/index.html).
They provide Linux sysroots and host compiler/linker tools, respectively. They
are build-environment dependencies, not Android SDK/NDK/JDK replacements or a
new game-platform commitment.

At UnityCsReference's `6000.3.19f1` commit
`79f16640303119112ca5caed4d71c607d0dff6fb`,
[ModuleManager.cs](https://github.com/Unity-Technologies/UnityCsReference/blob/79f16640303119112ca5caed4d71c607d0dff6fb/Editor/Mono/Modules/ModuleManager.cs)
loads platform modules and invokes their initialization and active-platform
hooks. [IL2CPPUtils.cs](https://github.com/Unity-Technologies/UnityCsReference/blob/79f16640303119112ca5caed4d71c607d0dff6fb/Editor/Mono/BuildPipeline/Il2Cpp/IL2CPPUtils.cs)
describes registration and selection of installed sysroot/toolchain packages.
These establish the public platform-module mechanism; the exact Linux module
implementation which requests these three packages was not located in that
public source tree. The automatic-toolchain explanation is supported by the
official manual and repeat native diff, not a claimed line-level trace through
the closed platform module.

The pinned GameCI [Ubuntu test script](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh)
writes a manifest for its separate package-mode temporary project. This probe
uses ordinary project mode. That script contains no Linux SDK/toolchain package
injection corresponding to the observed additions. We therefore do not
misattribute this diff to GameCI's package-mode coverage setup.

## Narrow change

1. Adopt the actual safe `manifest-after.json` bytes as the reviewed project
   manifest. The resulting source hash is exactly the after hash above. There
   is no wildcard or semantic-mutation exception.
2. Extend the resolved-lock and APK registered-package checks with the three
   exact `1.1.0` versions. The existing native `RequiredPackagesResolved` case
   gains the same assertions. The six native case identities stay unchanged.
3. Keep the source audit strict: a missing, added or changed dependency after
   the pre-import snapshot still fails. Formatting-only changes retain the
   existing bounded schema/equality checks and safe raw-byte exports.
4. Prepare guard and review fixture for `lottery-g0-20261012-03`. The actual
   trigger file is copied byte-for-byte from the verified remote request 02,
   blob `ab19994dcbd672b52368a20ced0b18f4c4ce475e`, source commit above.
   Its SHA-256 is
   `3b49a0974f263e6bdb44b856b3170a8c5f26aaade4d6982ef23e5d7ebd61d310`.
   This staging mismatch intentionally prevents an early probe run.

No generated package lock is fabricated. The failed run recorded the actual
lock hash, but its bytes were not among the 10 exported files. The next run must
resolve and archive its actual lock and generated settings/assets.

## Local regression and next native check

On 2026-10-12, all 63 local Python test methods passed using explicitly synthetic
fixtures; runner shell syntax also passed. The new tests reject each missing
or wrong-version Linux dependency and reject a post-snapshot toolchain version
change. Existing checks retain exact-six/assembly ownership, raw and decoded XML
screening, refused-manifest export cleanup, malformed-lock failure receipts and
the independent APK-verification/source-audit candidate gate.

The coordinator must freeze and independently review this candidate, checkpoint
it without changing request 02, then verify the expected remote parent and a
single-file diff before the final request-03 trigger. No workflow, action pin,
secret scope, timeout or upload gate is changed by this repair. Request 03 must
first produce six native PASS results and a successful source audit; only then
may the existing Android job build and validate its APK.

The updated native assertions and Android build have not run yet. Rendering,
physical touch, installation and gameplay remain `NOT_RUN` /
`NOT_DEVICE_TESTED`. Evidence remains `EVIDENCE_PERSISTENCE_PENDING` until the
coordinator verifies durable archive storage and readback independently of the
7-day Actions retention.
