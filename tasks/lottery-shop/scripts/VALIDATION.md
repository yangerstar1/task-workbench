# G0 CI validator scope

The local Python suite uses synthetic fixtures. Its 61 passing test methods
on 2026-10-12 validate guard, XML, font-restoration, source-mutation and APK
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

This artifact policy does not hide the public Actions job log. Before our XML
screening step can run, the pinned GameCI test action prints its Unity log and
raw test XML using `cat`; the pinned builder streams Unity output to stdout.
[Test action source](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh),
[builder source](https://github.com/game-ci/unity-builder/blob/d829bfc901f2347c8fe18898f06712b66916ef42/dist/platforms/ubuntu/steps/build.sh).
GitHub masks known job secrets, and the pinned test action explicitly calls
`core.setSecret` for the derived Unity serial and its masked-last-four variant.
[Serial masking source](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/src/model/input.ts#L194-L208).
GitHub warns that transformed secret values may evade automatic masking.
[GitHub secret-redaction limits](https://docs.github.com/en/actions/concepts/security/secrets).
Our later artifact scan cannot retroactively protect text already emitted in
those public logs. No absolute no-leak guarantee is claimed. Do not enable
additional debug/environment dumps or add arbitrary user text to native tests.
Suspected disclosure blocks promotion and requires an authorized incident
response; helpers must not echo a suspected value during diagnosis.

## Evidence and limitations

- Exact six named NUnit cases must pass with zero skipped/inconclusive/failed
  cases and matching assembly/counts. A missing, extra or duplicate report fails.
  Every case must be a descendant of the unique expected Assembly; an empty
  passing Assembly beside unrelated cases is rejected.
- The bounded original XML is kept byte-for-byte after DTD/entity rejection and
  conservative credential/private-identifier pattern screening of both the raw
  bytes and every XML-decoded attribute, text and tail value. Numeric character
  entities do not bypass these same checks. A separate XML
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
  semantic manifest changes fail. Generated assets/settings are archived with a separate hash
  inventory, not described as an unchanged source checkout.
  On failure, source audit writes a `FAIL` receipt before returning an error.
  It contains fixed stage/status fields and bounded canonical relative paths,
  classifications and SHA-256 values, never source contents or exception text.
  Invalid diagnostic metadata is withheld and marked rejected. The archive is
  assembled under a temporary name only after lock validation and promoted after
  completion; these files alone are not a success verdict.
- A manifest rewrite is classified `MANIFEST_FORMAT_ONLY` only when actual
  pre-import bytes match the source baseline SHA-256, both byte sequences pass
  a 64 KiB exact-schema check, and their decoded dependency maps are identical.
  Only `com.unity.*` package identities with explicit numeric versions are
  permitted in this diagnostic schema; URLs, credentials, arbitrary fields,
  arrays and duplicate JSON keys are rejected. Dependency/version additions,
  removals or changes still fail the source audit. Safe actual before/after bytes
  and a separate bounded semantic-diff receipt are preserved through explicit
  artifact paths; unsafe raw bytes are withheld, not silently approved.
  The internal baseline is not an artifact input. Before/after public export
  paths are cleared before revalidation and written only after their own checks
  succeed, so a refused baseline cannot remain at an upload-listed path.
- Resolved-lock root, dependencies, package entries and transitive dependency
  maps are type-checked before lookup. Array-shaped malformed locks produce a
  bounded `FAIL` source-audit receipt instead of escaping through AttributeError.
- URP initialization has an additional exact four-path allowance, classified
  separately as `URP_GENERATED_GLOBAL_SETTING`: `Assets/UniversalRenderPipelineGlobalSettings.asset`,
  `Assets/UniversalRenderPipelineGlobalSettings.asset.meta`, `Assets/DefaultVolumeProfile.asset`,
  and `Assets/DefaultVolumeProfile.asset.meta`. All four are retained in the
  generated archive and its hash manifest. Nearby unknown asset names remain
  rejected; there is no `Assets/*.asset` wildcard allowance. The two asset paths
  are defined by `defaultPath` and `GetOrCreateDefaultVolumeProfile` in the fixed
  [official URP source](https://github.com/Unity-Technologies/Graphics/blob/2d2e78cc9d6254bc6e7c9c5552cea053508e86cb/Packages/com.unity.render-pipelines.universal/Runtime/UniversalRenderPipelineGlobalSettings.cs#L272-L334).
  Unity creates the companion metadata files on import. This source inspection
  establishes expected paths; only a real run establishes which are generated.
- Tests and Android jobs import and generate their assets independently. The
  preserved outputs must be reviewed before a generated lock/settings checkpoint
  is adopted. Nothing is written back to GitHub by this workflow.
- Artifact upload paths are explicit. Full logs, Library, credentials and the
  entire build/artifacts directory are never artifact inputs. APK upload requires
  successful byte verification and source audit. Artifacts expire after 7 days;
  retain the exact native XML, receipts, generated archive and APK in an approved
  durable project archive before expiry.
- Android failure diagnostics are a separate non-candidate artifact containing
  only the fixed diagnostic receipt, guard/font receipts, source audit receipt,
  and the three bounded manifest diagnostic files when safely available.
  They contain no APK, native arbitrary output or complete log. The APK candidate
  upload still requires both independent APK verification and source audit to
  succeed. Failure diagnostics do not turn skipped or incomplete work into PASS.
- Durable evidence retention is coordinator-owned, separate from this read-only
  workflow: retrieve the run's artifacts in the same working batch, store them in
  previously authorized long-term destinations, and verify their hashes and
  returned storage identities. Until actual storage and readback are verified,
  the state is `EVIDENCE_PERSISTENCE_PENDING`; a 7-day artifact upload is not durable
  retention. This workflow adds no Release publication or write token.

Every result remains a technical probe. Rendering, physical input, installation,
gameplay and product/visual acceptance remain NOT_RUN / NOT_DEVICE_TESTED until
separate actual evidence exists.
