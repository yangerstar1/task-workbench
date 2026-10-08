# Scrapyard Bulwark · source-only candidate

This independent candidate is NOT rendered, visually reviewed, Unity-imported, approved, or published. No Blender/Unity process was executed while authoring. Existing pouncer sources and their canceled publication remain untouched. No game scene or gameplay code changes.

## Design and provenance

A low, wide salvage-armored quadruped with a chisel ram, overlapping cream/oxide dorsal plates, dark recessed linkages, wide cleated load feet, raised reinforcing keels, and hinged flank shields. Opening the shields exposes warm amber tissue on the sides/rear after impact. This is new geometry, not a recolored pouncer. The warm cream, rust, olive iron and sand palette responds to the approved desert RV reference; that private image is not copied, embedded, or uploaded. Geometry, atlas pixels, skeleton and motion are original programmatic work. No external model, texture, animation, font or audio is used. Blender itself should come from https://download.blender.org/release/Blender4.2/ with its official matching checksum, version 4.2.3. Blender licensing: https://www.blender.org/about/license/.

## Source files

- parameters.json: pinned versions, timings, technical budgets and declared status
- motion.py: dependency-free exact two-link legs, foot targets, support phases, charge travel contract and synthetic interruptions
- generate.py: mesh construction, original 512px basecolor/ORM atlases, rigid armor skinning combined into one skinned mesh / one atlas material, early static views, neutral studio and evaluated mesh framing/floor checks
- animate.py: seven complete sampled clips, evaluated pose checks, root-travel review footage, three interruption examples, turntable stills and conditional export
- test_static.py: syntax, configuration, reachability, support speed, transition continuity, loops, interruption continuity, weak-point/death behavior and source integrity checks
- artifact_io.py: refuses nonempty/non-directory outputs before generation to prevent stale exports entering a new run
- validate_runtime_contract.py: read-only regex/source-hash check against the actual BeastActor constants
- source-manifest.json: SHA-256 of the complete authored source set

## Approval-gated public GitHub Actions execution plan

These are commands for a future approved workflow, not instructions to launch work now. Do not create a cloud Codex task, run locally, publish a branch, upload the private reference, or run Blender without the parent's authorized route.

1. Run `python test_static.py` in this directory, then `python validate_runtime_contract.py --actor PATH/TO/BeastActor.cs`. Both must pass. Outputs must use new/empty directories; a nonempty path is rejected without deletion or reuse.
2. Obtain official Blender 4.2.3 and verify its upstream checksum. Record source commit, workflow run URL, binary SHA-256 and checksum URL in provenance.json.
3. First run `blender -b --python generate.py -- --output "$RUNNER_TEMP/bulwark-static" --phase static`.
4. Upload the static directory with `if: always()` BEFORE starting the motion command. It contains eight neutral-lit views and a separate open-weak-point view. A static process failure must still upload available evidence. Do not infer visual approval from successful generation. Human review may stop the pipeline here.
5. Only after static review permits it, run the same command with `--phase motion` and another output directory. Upload outputs with `if: always()` on failure too. Seven H.264 action videos, five stills per action, three explicitly labeled synthetic interrupt videos, sixteen turntable views, evaluated-validation.json and clip-manifest.json are retained. Technical failures block FBX/GLB export, not evidence retention.
6. Verify exported GLB/FBX in a fresh importer. The source currently does not implement a round-trip importer; do not claim exported clip/texture parity until one runs. Unity 6000.3.19f1 validation remains mandatory.

## Animation and integration contract

- Blender coordinates Z-up, -Y-forward, metres; export to Unity Y-up. Root motion off. Gameplay moves the capsule; the renderer preview supplies synthetic world translation only and removes it before export.
- Idle/Walk loop. Walk supports the actual 2.1 m/s stalk motor with a 0.6-second diagonal gait and 0.63m stance travel. Charge supports the actual 10 m/s motor with a 0.15-second cycle, eight strides / 1.2 seconds and 0.75m stance travel. Attack loops at its boundary to cover the runtime's strict `attackClock > 1.2` condition without freezing feet during a possible final tick. Root movement remains exclusively gameplay-owned. High-speed leg cadence still requires actual visual review.
- Windup matches the runtime's 1.1 seconds. It first deliberately repositions feet one diagonal pair at a time; its final 0.55 seconds lowers the body against planted feet. Its end pose matches Attack's start.
- Attack remains closed-armored throughout. Impact compression and opening belong to Recover. Recover spans the real 2.0-second weak-point interval and keeps the gates fully open for the entire clip, including its last sample. Foot repositioning uses lifted diagonal steps. Gate discontinuities at Attack→Recover and Recover→Stalk are deliberately not hidden through early opening/closing; the existing 0.12-second Animator CrossFade needs Unity visual review against gameplay vulnerability timing. This is not yet proof of a seamless state-machine transition.
- Hit matches the runtime's 0.28 seconds. Death is a weighted collapse that holds, with a -0.26m settle instead of the rejected -0.30m pose. Every shared chisel-ram ring vertex is checked analytically throughout Death against the unchanged 4mm penetration threshold.
- parameters.json exposes the exact runtime constants, and validate_runtime_contract.py checks them against BeastActor source. Current source proof is recorded in runtime-contract-check.json. Nonstandard motion remains an explicit integration risk: BeastActor returns home at 2m/s and uses a 0.6x blocked tangent speed without passing speed to Animator. Those paths require runtime speed synchronization and Unity verification; this source candidate must not be presented as fully integrated.
- Weak-point opening is an actual bone-driven geometric operation. Whether the weak tissue is sufficiently occluded when closed and sufficiently readable from side/rear when open is an unverified visual gate.
- Animations NEVER apply health damage, enable invulnerability, move the collision capsule, or decide weak-point damage. Runtime code must own telegraph timing, charge movement/collision, impact stop, damage eligibility and interruption policy. Avoid duplicate damage from both animation and game logic.
- Three synthetic hard stops begin from exact charge samples at 0.07, 0.42 and 0.91 seconds. Airborne feet settle vertically and planted feet do not slide back. Videos include the lead-in charge and stationary-root stop. These do not prove actual Unity crossfades, hit interrupts, collider handling or death blending.
- A generic crossfade from moving Attack directly into frame-zero Recover is NOT established as safe. Runtime needs an actual pose-preserving interrupt/settle route, followed by supported foot repositioning, and must be tested in Unity. No runtime implementation is supplied here.

## Required rejection checks after execution

Source tests prove mathematics and source integrity only. Review every static angle for recognizable scrap armor rather than generic blocks; side/rear weak-point exposure, closed-shield occlusion, joint assembly intersections, clean silhouettes, texture readability and mobile screen size. Inspect all seven clips and interruptions for weight, toe contact, limb collisions, camera cropping, excessive plate intersection and state transitions. Evaluated mesh checks reject >4mm floor penetration and framing outside a 3.5% safe border. Support checks compare actual baked ankle targets, limb lengths and evaluated sole height (12mm maximum contact gap); they still cannot replace visual load/contact review. Atlas UV seams and PBR/texture import parity need actual Blender/Unity inspection. No commercial-quality or acceptance claim is made before this evidence exists.


## Prepared owner-only Actions overlay

`.github/workflows/desert-rv-armored-art.yml` is manual-only on public main, owner-only, contents-read, standard ubuntu-24.04, fixed action commits, checkout credentials not persisted. No workflow has been published or dispatched by this preparation task.

Default dispatch `phase=static` produces early images only. After actual visual review, a separate `phase=full` dispatch requires `reviewed_source_sha` equal to that run's source commit. Full reruns static generation/upload before motion, and is blocked if static generation or validation fails. The input asserts a human review; it is not an automated visual-approval system. Every package still says visual_approved=false until actual review is recorded separately.

Each run/attempt uses unique empty output directories. Time limits: 120-minute job, 20-minute static Blender command, 80-minute motion command. Artifact retention is 14 days. Package allowlists contain 58 static files or 84 motion files before provenance/status/checksums. Maximum individual output is 256MiB and copied output total is capped at 1GiB. Video frame counts, duration, H.264 format and dimensions are checked using ffprobe; PNG headers/dimensions, binary export signatures, generator checksums, technical reports and exact seven-clip timing are checked. These are file-integrity gates, not FBX/GLB importer parity.

write_provenance.py binds source commit, run ID/attempt, run URL, per-source SHA-256, workflow SHA-256 and verified official Blender archive checksum. package_evidence.py binds each exported file, still, video, log and provenance record in SHA256SUMS. Missing files or process/technical failures produce PARTIAL_FAILED_NOT_A_SUCCESS and a nonzero step. Partial evidence is still uploaded; diagnostics are separately allowlisted. The workflows neither upload the reference image nor other folders, and contain no secrets or publishing rights.

Run `python test_pipeline.py` for the additional four stdlib packaging/workflow tests. The missing-output test deliberately exercises failure packaging and repeated-package rejection; it does not launch Blender or contact GitHub.


## R2 changes based on actual R1 images

All nine images from Actions run 37813199753 were individually inspected. Closed rear views leaked thin orange seams, the opened lateral shields formed an awning over the tissue, and repeated diagonal texture bands resembled wood grain. R2 retains the plow, four weight-bearing legs and overlapping front dorsal plates. The old rear plate and low side tissue are replaced by an elevated rear bay with three broad orange lobes. Two three-sided hatch doors cover side/rear/top when closed, and open 110 degrees about front-mounted vertical hinges. This removes the old awning path; actual occlusion/readability remains unverified until the next static run.

The current BeastActor rule is whole-body vulnerability during the two-second Recover window. There is NO rear hit cone or dedicated tissue hitbox in that code. The bay is readable feedback for that existing state, not a new directional damage rule. No arrows, fake hit markers or emissive substitutes are added.

R2 removes periodic stripe texture and adds sparse broad paint-loss patches plus a shared ORM atlas: matte paint/organic material and exposed metal have distinct roughness/metalness. Color, geometry and PBR import parity remain visual-review gates.

Static evidence now includes 44 additional fixed-perspective FPS images: 1.65m camera height, 60-degree vertical FOV, rear-side/rear views at 2/4/6m plus both side-boundary views at 4m. Each viewpoint shares identical camera position and aim across closed, Recover 0.0s, 1.0s and 1.95s images. Framing is not auto-fit. fps-visibility.json records evaluated-mesh ray occlusion and projected tissue size; closed leaks and near-total open occlusion fail the technical check. These samples do not prove a player can recognize a two-second opportunity; rendered image and actual motion/Unity review are still required.

This revision contains no workflow replacement. The existing owner-only workflow's publisher fixes for GITHUB_ENV initialization and explicit step outcomes are retained unchanged. Only the precise model/evidence source allowlist should be published. Do not run full motion until the new static images are actually reviewed.
