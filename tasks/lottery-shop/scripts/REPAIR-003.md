# G0 first-run repair candidate

Date: 2026-10-12 UTC. This is a local repair candidate, not Unity/native PASS.

## Observed failure

[Run 38177246584, attempt 1](https://github.com/yangerstar1/task-workbench/actions/runs/38177246584)
used source `972638da017b4c70c65b1d803fe66d153c2d74c2` and failed before native
test results. The Android job was skipped. Read-only job inspection and bounded
error/package log excerpts confirm `ProbeBuild.cs(34,13): CS0200` on assigning
`UniversalRenderPipelineAsset.supportsMainLightShadows`.

The reported source-audit manifest hashes are:

- Before: `b8bc23b9a479e87ef923606c7f137fc27a8c4e60b3dd08adf41a743743b0b541`
- After: `bebba50d0c71fadc69ed6542c7c0156410bd46d41f6de2e34b7997510a4741dd`

The before hash matches this candidate's unchanged manifest file. The previous
artifact did not preserve the actual after-manifest bytes, so its semantic diff
and exact writer remain unverified. Do not label that mutation harmless or claim
it was caused by GameCI code-coverage injection.

## Applied patch

1. Replace the inaccessible shadow-support setter with the public
   `pipeline.shadowDistance = 0f` and set the probe's directional light to
   `LightShadows.None`. The six existing native test names remain unchanged;
   their existing URP/scene tests now also check these controls after reimport.
   The feature-support flag itself is not claimed to have been changed.
2. Type-check resolved-lock root, dependencies, every package entry and nested
   dependency maps before field access. Malformed arrays must leave a bounded
   FAIL diagnostic receipt and cannot upload an APK candidate.
3. Preserve actual before/after manifest bytes only after the bounded exact
   package/version schema and source-hash checks. Only semantic identity may be
   classified as format-only; every dependency/version change stays a failure.
   Add exact artifact paths for these two byte files and their diagnostic JSON.
   The normal runtime/editor source and APK dual-success gates remain strict.

The URP reference contains an internal setter for the shadow-support property
and a public setter for shadow distance:
[fixed URP asset API source](https://github.com/Unity-Technologies/Graphics/blob/2d2e78cc9d6254bc6e7c9c5552cea053508e86cb/Packages/com.unity.render-pipelines.universal/Runtime/Data/UniversalRenderPipelineAsset.cs#L1304-L1313),
[public shadow-distance setter](https://github.com/Unity-Technologies/Graphics/blob/2d2e78cc9d6254bc6e7c9c5552cea053508e86cb/Packages/com.unity.render-pipelines.universal/Runtime/Data/UniversalRenderPipelineAsset.cs#L1462-L1466).
The real compiler error is authoritative for the attempted build; the fixed
Graphics source is supporting API evidence, not an assertion that every byte
equals the installed Editor package.

## Manifest investigation boundary

The pinned GameCI shell writes a temporary manifest and adds code coverage only
inside its `PACKAGE_MODE=true` branch. This workflow uses project mode, and the
native command points to `tasks/lottery-shop/unity`. Its observed registration
list includes the requested URP 17.3.0, Input System 1.20.1 and Test Framework
1.6.0, but no code-coverage package. This is evidence against that particular
injection explanation, not proof that no component rewrote the manifest.
[Pinned test-runner script](https://github.com/game-ci/unity-test-runner/blob/0ff419b913a3630032cbe0de48a0099b5a9f0ed9/dist/platforms/ubuntu/run_tests.sh).

No Unity session was run locally for this repair. Bounded reconstruction of
formatting/package-addition hypotheses did not match the after hash and is not
substituted for native bytes. The next run will preserve the actual safe-shaped
bytes and diff so that an unexpected mutation yields new, useful evidence.

## Checks and next candidate

- 60 local synthetic Python test methods pass, including malformed-lock arrays,
  exact-semantic manifest rewrites, semantic changes, missing baseline, unsafe
  metadata, URLs and duplicate keys. These are validator tests, not Unity tests.
- The shell preflight still passes syntax checking. Workflow permission/action
  pins and GameCI-only secret placement remain unchanged. Added artifact paths
  are explicit and the APK still requires verify plus source audit success.
- A new native run is still required to compile the revised C#, produce the
  real six-case XML, confirm import mutations, and reach Android.
- Suggested next identity: `lottery-g0-20261012-02`. The coordinator should update
  the guard expectation and review request together before freezing the next
  source candidate, while leaving the existing trigger file unchanged. After
  independent review, verify the branch head and parent SHA with compare-and-swap
  and change only the reviewed trigger JSON to start the new run. This repair
  does not change request identity or trigger any workflow itself.
- Preserve actual success or failure artifacts to previously authorized durable
  storage and verify hashes/storage IDs. Until verified, retain
  `EVIDENCE_PERSISTENCE_PENDING`. Rendering and physical-device QA remain NOT_RUN.
