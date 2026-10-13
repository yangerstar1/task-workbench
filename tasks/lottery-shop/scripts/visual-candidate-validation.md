# Diagnostic 3D visual candidate capture

Scope: `DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS`. This is a reversible G3 presentation candidate, not G4, a device pass, natural-seed evidence, or final visual acceptance. The existing G3 request, contracts, guard, and formal workflow are unchanged.

## Source review and launch

1. Freeze/publish the complete candidate source, including FBX, textures, importer, runtime presentation, perspective-compatible regression assertions, and these diagnostic fixtures.
2. An independent source reviewer checks that exact candidate commit. The root records the explicit review result. Publishing source alone does not start this workflow.
3. Only after approval, make a separate commit that changes solely `tasks/lottery-shop/ci/visual-candidate-request.json`. Do not create or edit the old `g3-request.json`.
4. The new request has `schemaVersion: 1`, a unique `requestId` of `lottery-visual-YYYYMMDD-NN`, `sourceCommit` equal to the directly preceding reviewed candidate commit, `purpose: DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS`, and this bounded `sourceReview` object:
   - `sourceCommit`: that same reviewed candidate commit
   - `status`: `APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY`
   - `reviewedAtUtc`: actual UTC approval time
   - `reviewId`: `visual-source-YYYYMMDD-NN`
   - `reviewer`: `independent-source-review`

The fixed repository actor attests that this independent review happened. This is not a cryptographic reviewer signature or a reuse of any prior G3 review.

## Native run

Pinned Unity 6000.3.19f1, URP 17.3.0, the existing Unity license concurrency group, existing secret references, SHA-pinned Actions, and read-only GitHub permissions are retained. `G3Build.Prepare()` imports original art via the supported Unity prebuild fixture hook. The fixture requires one active project bootstrap/view/camera, imported renderers, real routed Input System actions, and a live perspective camera. The HUD is never disabled: enabled renderers are checked against the camera's layer mask and frustum; the receipt labels this as geometry-based visibility, not a pixel-occlusion proof.

The new capture runs first and promptly uploads bounded originals for visual review. Existing 287 EditMode and 32 PlayMode test identities then run without skips; their original safe NUnit reports are preserved. Native tests are not considered passed merely because validator unit tests pass. The old 75-step scenario and original 14-frame capture remain in the existing PlayMode suite.

## Original frames

11 PNGs: entry whole shop; empty seated desk; number ticket with exactly three cells scratched; identical number state at 20:9; challenge with two safe cells and three currently equipped tools; shelf before/after actual world-ray click; same challenge after keyboard return; day closing desk; identical camera at night with bill closed; night bill.

The entry view and initial stand start are explicitly fixture-positioned. The walk to the shelf and return use queued keyboard events through the real input router and character controller. Physical and shortcut shop contents must match and the ticket state hash must remain unchanged. This is simulated input, not Android touch or a continuous screen recording. Day/night use legally reached game phases after normal settlement of 12 tickets; the fixture never edits the phase directly to hold an active ticket overnight.

Receipts bind source, run, run attempt, fixed diagnostic seed hash, confirmed state/mask, revision, camera pose/FOV, output dimensions, quality name, imported renderer count, HUD observations, and action history. They omit secret values, full save payloads and unrevealed outcomes. Only explicit PNG paths, bounded screened original NUnit XML, and limited JSON receipts are uploaded. Unity logs, Library, ProjectSettings contents and source-file contents are not artifacts. Source-before/after records cover tracked files only and are not a full audit of new generated files. FBX importer remaps in .meta, derived materials, the dedicated pipeline, and generated scenes are expected build products; no claim of byte-immutable generated output is made.

## Local verification boundary

The validator unit tests are synthetic and run without Unity. No native compile, model import, runtime frame, visual acceptance or device result is claimed until the corresponding actual run completes and is inspected.

## V13 measured presentation extension

Receipt schema 2 records actual visible control IDs and More visibility, the union of visible opaque HUD plates divided by safe-area size, projected bounds of the visible ticket and three runtime tools, and rendered shop renderer/material counts. Secondary navigation is opened only through genuine mouse events on the visible `open-more` control before clicking its destination. Geometry measurements are observations for manual review of the native PNGs. Passing their shape/finite-value checks is not an art quality or pixel-occlusion verdict; offscreen or very large but well-formed bounds remain visible in the evidence.

## Bounded fixture diagnostics candidate

The day-closing loop snapshots the remaining quota (0–12), uses a finite `for`, and yields after every ticket. Each real routed purchase must create a new ID, debit exactly the ticket price, increase purchased count by one without a settlement, and enter ACTIVE. Numeric quick reveal must finish the same ticket without purchase/settlement/cash side effects. Every claim must settle that same ID exactly once, increment settlement count by one, credit its settlement amount and clear the occupied-ticket state. Closing still requires all 12 unique purchases and 12 settlements, CLOSING_PREP, all 11 frames, and the unchanged original regressions. No game state is modified by the checks.

Cooperative monotonic limits are 900 seconds from runtime setup, 120 seconds per keyboard turn, 180 seconds per waypoint including turning, and 10 seconds/600 frames for scene unloading. Original turn/walk iteration caps (600/1200) remain. A blocked synchronous native call cannot be interrupted by a main-thread clock. The diagnostic capture action therefore has a separate 30-minute step timeout inside the existing 60-minute job. This is based on run01's observed 6m40s cold capture-to-prebuild-failure path; its EditMode and PlayMode steps took 2m59s and 4m54s. These observations do not establish a successful render duration. The step budget allows cold setup plus the runtime budget while leaving room for bounded evidence upload and exact regressions. A timeout is failure, never a skip or pass. A whole-job timeout or runner loss may still prevent upload; absent files must be reported absent.

Two optional fixed-schema receipts, `prebuild-progress.json` and `runtime-progress.json`, identify completed milestones with elapsed time, UTC, source/run/attempt and bounded counters. They contain at most 128 events/64 KiB each. They never include exception bodies, logs, seeds, arbitrary text or environment values. Only these exact paths pass the strict export validator and upload allowlist. Missing progress does not fabricate a completed phase. Runtime begin/end, each camera capture, each walk/turn, day ticket completion and teardown are marked. These aid diagnosis but are not proof of pixel quality or test success.

The source loop risk was found statically. It is not an established cause of run02's long capture step without native evidence. Local checks for this candidate comprise Python synthetic validator tests and source-structure/diff review. Unity compilation, import, native screenshots and gameplay remain unrun until a separately reviewed candidate is actually launched.
