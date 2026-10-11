# G0 CI validator scope

The local Python suite uses synthetic fixtures. Its 43 passing test methods
on 2026-10-11 validate guard, XML, font-restoration, source-mutation and APK
inspection code. They do not execute Unity, import a real font, build an app,
render a frame, or test a physical device.

Re-run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tasks/lottery-shop/scripts -p 'test_*.py' -v
    bash -n tasks/lottery-shop/scripts/prepare_runner.sh

The workflow is restricted to a push changing exactly the designated request
path on `lottery-shop-g0-20261011`; other source files may be in the same commit.
The guard requires the exact request JSON values, owner actor and triggering
actor, non-fork public repository, GitHub-hosted Linux, matching event/checkout
SHA and the pinned base ancestor. It does not accept manual dispatch or a PR.
Changing the request identity, actor, branch or environment requires a reviewed
workflow/guard update. A GitHub rerun retains the original push and is checked
again, including its triggering actor.

All four external actions are pinned to the SHAs already used in the repository's
prior Unity proof. The GameCI action manifests and Ubuntu execution scripts were
read at those SHAs. Custom build methods do not inject GameCI's default C# build
script. No previous game scene, source, art or whole restoration flow is reused.
Sparse checkout retrieves only this probe and its workflow. The historical font
is a separate licensed, checksum-verified asset.

Only GameCI steps receive the existing Unity license/email/password secrets.
No helper reads or prints their values. There is no token passed to GameCI for
writing GitHub checks, no saved checkout credential, and no cache or release step.
The runner cleanup script is guarded for disposable GitHub-hosted Linux only.

## Evidence and limitations

- Exact six named NUnit cases must pass with zero skipped/inconclusive/failed
  cases and matching assembly/counts. A missing, extra or duplicate report fails.
- The bounded original XML is kept byte-for-byte after DTD/entity rejection and
  conservative credential/private-identifier pattern screening. A separate XML
  omits arbitrary output/properties/command lines. Potential sensitive content
  refuses original export and fails validation; it is not silently laundered.
  Screening does not read actual secret values and is not a general DLP guarantee.
- APK verification binds native receipt to source SHA and run, checks the pinned
  editor revision/packages/SDK/GLES3/backend declaration, SHA-256/size, ZIP CRC and
  actual ELF64 AArch64 headers for IL2CPP and Unity. It does not install the APK,
  verify the signing certificate, parse every Android manifest field, or show
  that the binary is free of all defects.
- Font archive and restored font have separate fixed SHA-256 checks; restore is
  bounded and refuses a different existing font. The full OFL and copyright
  attribution are restored into an application resource. Synthetic fixtures do
  not prove the real font bytes or glyph coverage.
- Pre-Unity hashes are compared against the actual post-Unity tree. Only named
  generated assets, allowed ProjectSettings files, package lock and font importer
  metadata are accepted. Runtime/editor/test code, manifests and editor version
  changes fail. Generated assets/settings are archived with a separate hash
  inventory, not described as an unchanged source checkout.
- Tests and Android jobs import and generate their assets independently. The
  preserved outputs must be reviewed before a generated lock/settings checkpoint
  is adopted. Nothing is written back to GitHub by this workflow.
- Artifact upload paths are explicit. Full logs, Library, credentials and the
  entire build/artifacts directory are never artifact inputs. APK upload requires
  successful byte verification and source audit. Artifacts expire after 7 days;
  retain the exact native XML, receipts, generated archive and APK in an approved
  durable project archive before expiry.

Every result remains a technical probe. Rendering, physical input, installation,
gameplay and product/visual acceptance remain NOT_RUN / NOT_DEVICE_TESTED until
separate actual evidence exists.
