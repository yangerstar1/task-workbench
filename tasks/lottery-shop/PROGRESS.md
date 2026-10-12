# Lottery project progress

Updated: 2026-10-12 13:07 UTC.

## Current verified status

Current source: `93b88d2d81824d35abc4bdb14fcd0b82ccf5c7ef`.
Current execution: [run 38248877036](https://github.com/yangerstar1/task-workbench/actions/runs/38248877036), request 07, attempt 1.

- G0 capability work completed: Unity 6000.3.19f1, six native EditMode checks, source audits and an ARM64 IL2CPP Android probe APK passed in run 38226292711.
- G1 rule specification and independent test calibration passed. Later implementation still requires its own actual execution and review.
- G2 candidate 007 implements the minimum one-ticket 3D scratch scene, transactional persistence and same-request FakeAd recovery. Overall G2 acceptance remains pending.
- The current tests job completed **45/45 native EditMode tests, 8/8 native PlayMode tests and 24/24 Linux/.NET process-kill recovery cases**, with zero failed or skipped native cases. The process cases use real child-process termination with synthetic transaction fixtures; they do not establish Android force-stop behavior.
- Both source audits passed. Edit settings were unchanged by normalization. Play exported settings are explicitly **NORMALIZED_NOT_RAW**, with normalization-receipt hashes bound by the source-audit and generated-asset manifests. No original credential value is exported.
- The tests artifact contains exactly **28 files**. Its SHA-256 is `ea9fc853e25039223a5ada27cb9bad85ca5b66ad1403ede9e2f2e31b3f5b333b`. Original XML, process receipts, generated archives, normalization records and frame bindings are retained.
- Four actual URP frames show the initial ticket, partial scratch, full reveal and settlement. Independent review passed the narrow technical tests and P3 observation scope: spatial masking, retained untouched covering, a stable locked ticket and zero-prize settlement. Frame byte lengths and hashes are bound by the render receipt to this source, run and recorded state hashes.
- Android job `114813204465` completed successfully. The 49,630,478-byte ARM64 IL2CPP technical APK has SHA-256 `289f6f091f4c39b8773a5024451f64011a31b47b362bae4a6856c3a859498a68`. It was saved durably and independently downloaded again with identical bytes/hash. This does not establish device behavior or overall G2 acceptance.

## Render findings and next candidate

The four images are actual Unity camera renders using URP StandardRequest/ReadPixels, OpenGLCore and llvmpipe software rendering. Input tests use the simulated Input System fixture.

The source viewport was **640 x 480**, while the output images are **1280 x 720**. This introduces visible horizontal stretch. The top decorative background sign is also clipped. The technical graybox assets do not meet final visual-quality requirements.

A follow-up candidate is being prepared to correct the aspect/layout and sign framing. Corrections must produce new actual frames and fresh verification; the existing frames are not relabeled as fixed. The first scene target images were explicitly rejected; new flat ticket-art candidates are being reviewed and are not approved or integrated. Technical P3 success does not approve final art or later visual gates.

## Scope limits and next checks

- Independent review identified a missing actual process kill in the ad waiting state. Request 08 adds it without removing the original 24 cases, alongside the render-aspect correction; native execution and fresh recheck remain pending.
- Normal first-day advertising is disabled. Eligibility and delayed-callback tests use explicit synthetic fixtures; recovery querying is manual. Persistent first-launch elapsed timing remains unimplemented.
- Generated-asset archives are job-specific. Preserve source, lock, manifest and normalization bindings when restoring them; do not mix test and Android overlays or describe normalized settings as raw Unity output.
- Android installation, physical touch, force-stop, device performance, real advertising SDK, full-game progression and final visual/gameplay acceptance remain unverified.
- The narrow technical and P3 review does not establish final image quality, aspect-safe device UI, positive-prize visual settlement or complete-game acceptance.
- Export checks continue to block unsafe credential settings. No raw credential values or unrestricted job logs are included in this progress summary.

## Historical failures and repairs

These are retained as past outcomes and must not be read as the current run's status.

- **Run 38239514579**, source `331f0cc94d2b65e646a8374351f287f3dacc0d19`: 24 process cases passed; EditMode passed 42/45 with three corrupt/unknown-schema recovery failures. Explicit invalid-data classification repaired the defect without removing tests. Android was skipped.
- **Run 38241168487**, source `2b62b4769a02ca00d528b27b3ffcf7e227b6b7c1`: EditMode 45/45 and process 24/24 passed. PlayMode reached the 30-minute job timeout, producing no Play XML or frames. The Play source audit reported leftover test-initialization scene paths after cancellation. Android was skipped.
- **Run 38244728404**, source `731e97ad8ffabb398ff37bf3a6d806ce331791bc`: EditMode 45/45 and process 24/24 passed. PlayMode completed with one pass and seven failures because the input fixture did not create the expected ticket. The post-Play guard withheld unsafe settings/archive content and exported bounded audit metadata only. Android was skipped.
- **Run 38246742337**, source `181a574d685cb8c39383d9f16777ab770d263cc8`: EditMode 45/45 and process 24/24 passed; all eight Play cases failed at the strengthened press-edge prerequisite. Both source audits passed with explicit, hash-bound normalization. The Editor-background input-buffer fixture was subsequently corrected; request 07 provides the actual successful retry evidence.
- Earlier sparse-checkout and C# project-extension startup defects were fixed. Bounded diagnostics preserve error identities without exporting raw logs or credentials.

## Current unexecuted repair candidate

Request 09 also fixes an actual APK metadata discrepancy: run07 binary manifest
reported versionCode 1 while the workflow declared 2. The custom builder now
sets 2 explicitly; binary verification and device upgrade remain pending.
The two flat ticket artwork candidates have since been explicitly approved;
the rejected whole-scene images remain excluded. Artwork approval is not a
full visual, device or G5 acceptance.
