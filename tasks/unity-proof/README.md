# Desert RV CI proof

## Verified run: 2026-10-08

The [first Actions run](https://github.com/yangerstar1/task-workbench/actions/runs/37761201389)
passed all four native tests and built the ARM64 IL2CPP APK from commit
`b63d73cdf8dc1fe6cd91a8f7b53acb9acd2b45b4`. Downloaded bytes, receipts and
AArch64 ELF headers were independently verified. The reviewed outputs are archived
in [unity-proof-v0.0.1](https://github.com/yangerstar1/task-workbench/releases/tag/unity-proof-v0.0.1).
This archival was explicit, not an automatic step of the read-only workflow below.
The development APK has not been installed or device-tested and is not a finished game.
Both disposable CI jobs used repository secrets without another interactive login;
no indefinite authentication guarantee is implied.

## Original proof scope

An original, disposable Unity **6000.3.19f1** project that tests the free,
standard GitHub-hosted Ubuntu → GameCI → Android path. It contains no Desert RV
game source, models, textures, audio, recovered data, or credentials.

## Run once

The workflow only supports manual **workflow_dispatch**. A maintainer must first
configure the three repository **Secrets** described by
[GameCI's Personal activation guide](https://game.ci/docs/github/activation/):
`UNITY_LICENSE`, `UNITY_EMAIL`, and `UNITY_PASSWORD`. Use the actual Personal
entitlement/account. Never commit these values or post them in issues or logs.
This repository neither supplies credentials nor disables MFA. If the account
has no compatible ULF or activation fails, that is a failed proof, not a pass.

1. Dispatch **Unity 6000.3.19f1 free CI proof** once.
2. The first job must execute all four named native EditMode tests. Missing
   secrets, missing reports, zero tests, failures, and skipped tests fail closed.
3. Only after those tests pass does a new runner build the original cube sample
   as an ARM64 IL2CPP development APK. Python independently checks its receipt,
   SHA256, ZIP CRC and Android/ARM64 entries.
4. Download both artifacts within seven days. The receipts bind the exact
   commit and workflow run. A green workflow with no APK is not success.

The sample can be installed for manual inspection: it displays a rotating cube,
the Unity version, and a pause button. Installation and device execution are
**not performed by this workflow**. This is not a gameplay, graphics-performance,
or production-signing acceptance test.

## Resource and access boundaries

- Only the public repository's standard `ubuntu-24.04` runners; no paid/larger
  runner, self-hosted machine, UBA, cloud subscription, LFS or cache overage.
- Two sequential jobs, 30/45 minute timeouts, one workflow at a time. No push,
  pull-request, schedule or recursive trigger.
- Repository permission is `contents: read`. Checkout does not retain its token.
  Secrets are passed only to the presence check and pinned GameCI actions.
- The preparation script refuses anything except GitHub-hosted Linux manual
  runs. It removes only explicitly listed unrelated preinstalled SDK directories
  on that disposable runner to make room for the Android image.
- No Editor/license log upload; only the selected NUnit XML, small receipts and
  APK are uploaded. Artifacts expire after seven days. This is not a backup plan.
- Permanent Release publication is not implemented in this read-only workflow.
  A maintainer may separately archive reviewed outputs after a successful proof.
- The original build method creates its scene and settings in the temporary CI
  checkout. No game repository is changed.

## Versions and provenance

The workflow shape follows [GameCI's simple example](https://game.ci/docs/github/getting-started/).
Actions are pinned by complete commit SHA: checkout v4.2.2, upload-artifact v4.6.2,
Unity test-runner v4.3.1, and Unity builder v5.0.0. GameCI's documentation site is
labelled v4; the actual builder's stable v5.0.0 release is separately pinned.
There is no floating `latest` action reference.

Unity Test Framework **1.4.6** and NUnit **2.0.3** are pinned to versions actually
listed by Unity's public package registry during preparation. Unity's newer 1.6
documentation exists, but 1.6.0 was absent from that unauthenticated registry
response, so this proof does not assume it can resolve. First native CI import
must still validate the pinned package set. Unity may generate its normal
ProjectSettings and package lock files on first import.

All project scripts and tests here are original minimal proof code. External
actions and the Unity Editor retain their own licenses and terms. No successful
run is claimed merely because these files exist.
