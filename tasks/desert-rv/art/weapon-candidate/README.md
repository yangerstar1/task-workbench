# DesertRV original weapon + hands candidate

This is a newly authored candidate, not a recovered or approved production model. No original concept image, third-party model or paid service is included. All mesh forms and material definitions are authored in this source. Parent review must inspect actual rendered pixels and motion before acceptance.

## Reproduce

Owner manually dispatches `desert-rv-weapon-art.yml`. Standard GitHub-hosted Ubuntu runner downloads official Blender **4.2.3**, verifies Blender's published SHA256, generates, exports and renders. Do not run Blender on the dot cloud computer or the user's computer. Local checks are Python AST/compilation only.

Exports: `weapon_hands.blend`, skinned `weapon_hands.glb`, `weapon_hands.fbx`; metallic/roughness Principled BSDF materials are directly exportable PBR (solid material color, no external procedural texture dependency). Animation clips use no game damage, ammunition or input callbacks.

## Coordinate / runtime contract

- Metric units; source +Y toward muzzle, +Z up, +X right. GLB and FBX exporters perform axis conversion. FBX `-Z` forward / `Y` up.
- Armature: `root`, `weapon`, `magazine`, `follower`, `loaded_nails`, `reload_strip`, `trigger`, `arm.L/R`, `hand.L/R`, three-segment fingers (two thumb segments).
- Named `Grip`, `Trigger`, `Magazine` empties are authoring anchors. They are not game event callbacks.
- Idle: 2 s. Fire: exactly 0.22 s, with subframe endpoint. Reload: exactly 1.65 s. Motion evidence sampled at 60 fps; integer-frame Fire video is 15/60 s including endpoint sampling, distinct from animation action duration.
- Initial budget checks report weapon 8–12k / hands 10–16k triangles; budget compliance is neither a quality certificate nor silently forced by unnecessary subdivision.
- Source stores <=4 normalized weights per vertex. Explicit union creates connected glove form before skinning.
- Export only asset objects; studio lights/cameras are kept in the `.blend`, excluded from GLB/FBX.

## Evidence and rejection criteria

Eight studio views, complete side-view Idle/Fire/Reload videos, 1280x720 and 1600x720 model composition captures, clip/weight/triangle validation, exported GLB animation validation and SHA256 manifest. Output has no game HUD; actual phone-button overlap requires a real HUD overlay, so it is explicitly **not passed** by this package.

Revision 2 uses a fixed open-top magazine. The left hand pulls back its follower, retrieves a genuinely count-controlled collated strip from below frame, guides it into the exposed channel, releases the follower and returns to support. The runtime count snapshot preserves existing rounds and inserts only min(12-loaded, reserve); no game state is changed by animation. Hand and tool contact reference distances are sampled throughout the three contact phases, but reference alignment does not certify surface penetration. Finger contact/penetration and the follower interaction remain visual-review gates. Hand anatomy is voxel-unioned geometry with distance-weight skinning, not production retopology. A successful runner only proves artifacts were generated; it must not be described as commercial-quality acceptance.

No production scene, game controller, damage system or ammunition logic is modified.

Revision 2 replaces the rejected straight-rear orthographic view with a fixed +Y 35mm perspective camera and oblique tool pose. The camera is not rolled or rotated to fake composition. A pose search targets 29% width and 32.5% height in both aspect ratios. Final `target_fit` uses actual rendered alpha pixels. Sleeves extend through the lower frame edge; they have no visible end caps. Each aspect ratio records the rig transform for integration. No image stretching or post-render repositioning is used.

Private approved concept was actually inspected: it contains hands but no gun. Orange hand-back reinforcement and wrist bands over graphite gloves extend its glove design; ivory/oxide gun colors are an original interpretation of its environment palette, not a recovered gun. The reference image is not part of this package.

## R1 pixel rejection fixes included in R2

Four fingers now stack along the grip axis, with explicit inter-digit gaps, a separate thumb web, flattened palm/back planes and shallow leather/seam detail. The open sleeve mesh blends wrist motion toward a stationary proximal arm. A real underbarrel rubber grip supports the left hand. Split shell service covers, darker gaskets, an open magazine channel and safety return spring express assembly/function; coatings use higher roughness. Fire adds moving safety-tip travel. These are candidate fixes, not evidence of visual acceptance.

Reload adds separate IK targets for opposing thumb/index/middle fingertips, keyed acquisition/release influence, and left/right contact stills at frames 30, 35, 60, 68, 91. Sampled IK residuals and grip-reference residuals are reported separately from untested surface intersection. The 1.65-second action remains purely visual.

## R2 runtime failure recovery and count contract

Run 37804225247 produced the first viewmodel PNG and then failed before the second. Actual Traceback could not be retrieved because the GitHub job-log connector returned Transport closed; a headless Render Result empty pixel buffer is the leading hypothesis, not a confirmed log diagnosis. Readback now reloads the actual saved RGBA PNG and validates dimensions, channels and buffer length; regressions cover empty/transparent/non-RGBA buffers. Runner stdout/stderr is also uploaded as blender.log, and the blend plus validation checkpoint is saved before viewmodel processing.

The framing optimizer previously clamped off-screen core bounds, allowing cropped gun/hand geometry to score well. It now scores untruncated core bounds; partially or entirely out-of-frame core geometry has infinite score. Only exactly Forearm_L and Forearm_R are exempt; gloves, cuffs and grip markers are not.

Twelve LoadedNail_00..11 and twelve IncomingNail_00..11 independent mesh nodes each contain a complete nail, head and local collation connector. The carrier bones IncomingOffset and LeftReloadOffset have no authored animation curves. No ammunition ancestor is scaled to zero. Runtime uses Renderer.enabled with authoritative LoadedBefore/PlannedAdded, applies the same count-dependent pitch displacement to the incoming strip and carrying hand, and commits game ammunition only at 1.65 seconds. The first incoming nail is the grasped end, so even added=1 remains physically represented. weapon-presentation-contract.json describes the exact interface. Actions renders countable before/mid/after images for 0+12, 3+5 and 11+1. Import-space pitch must be verified from adjacent loaded-nail node origins.

## Fourth-pass fixes after inspecting run 37810690120

The previous pose search had no finite solution at 20:9, yet retained its first infinite-score candidate. It is removed entirely. Both images now use one fixed gun/camera transform and horizontal FOV. Only documented off-axis vertical lens shift compensates for aspect ratio. Static projection of actual third-pass GLB vertices independently reproduced its measured footprint, then established this shared candidate pose; actual PNG acceptance remains required. No per-size scale/pose jump is allowed by the gate.

Micro-cylinders no longer receive costly bevel rings. Larger cylinders use one bevel segment; housing profiles use two. Each glove preserves its form at a 5,200-triangle decimation target. Exact final counts and per-mesh totals are reported rather than estimated. Original triangle budgets remain unchanged.

The new nail strips have a continuous thin connector: each per-nail renderer owns one full 30mm segment, so prefix visibility truncates a physically connected strip. The hand's palm shifts further outside the rail while fingertip IK remains on the nail. Frames 55–68 are rendered from both sides, with additional nearly-full 11+1 contact views. BVH surface-intersection samples test the left glove against fixed rails/spine and the other glove at all 42 count/frame combinations. These are stricter than contact-reference distance and do not claim complete collision certification.

GLB post-export cleanup deletes animation channels only for IncomingOffset and LeftReloadOffset, preserving rest transforms and all other motion. FBX export disables all-actions duplication and uses only NLA strips. Packaging parses actual FBX AnimationStack nodes and requires exactly the same three action names as GLB. The Unity bridge still applies offsets after Animator evaluation, but this does not waive the export gate: any direct carrier curve found in either GLB or FBX rejects the candidate.

Packaging is now fail-closed: budget, core visibility, rendered aspect-fit, stable pose, overlap samples and export action-set failures produce REJECTED_TECHNICAL_GATE and a nonzero workflow result while evidence uploads still run. A technical pass still requires human visual approval. SHA256SUMS lists only files included by artifact patterns; Blender backups are disabled and .blend1 is excluded.

The official Blender 4.2.3 FBX exporter explicitly passes force_keep=True for NLA takes, preserving static curves even when all-bones keying is disabled. During this export only, the sampler is wrapped to disable forced constant retention; the original function is restored immediately afterward. Real sampled motion remains. Packaging traverses binary FBX Objects/Connections and rejects any AnimationCurveNode directly connected to either offset carrier. This parser detected all 36 offending connections in the rejected third-pass FBX. Unity import verification remains a separate required gate. Source reviewed: https://github.com/blender/blender/blob/v4.2.3/scripts/addons_core/io_scene_fbx/export_fbx_bin.py and https://github.com/blender/blender/blob/v4.2.3/scripts/addons_core/io_scene_fbx/fbx_utils.py .

## Fifth-pass changes from actual fourth-pass evidence

The fourth pass met both core-visibility checks, both unchanged triangle budgets (9,712 weapon / 13,480 hands), three FBX/GLB clips and zero carrier curves. It was correctly rejected for 1280 pixel width 0.32265625 and sampled loading intersections. This revision changes the shared lens from 35 to 34.5mm without per-aspect pose changes or threshold relaxation.

During strip carry, the hand now pronates over the loading slot: the palm and unused fingers are above the rails while the same fingertip IK targets remain on the actual nail. This replaces the previous below-strip palm placement implicated at frames 56–68; nearly-full 11+1 also collided with the other glove. All previous obstruction tests remain. Reports add representative triangle pairs and a ray-parity interior-vertex depth measurement, attributed to dominant finger/palm skin regions. This is sampled vertex interior depth, not a claim of complete continuous collision certification.

Binding contract A is explicit: IncomingNail renderers stay normally skinned at the same rig root. Every positive skin influence must belong to IncomingOffset's descendant chain (currently only reload_strip); exactly one Armature modifier must target that rig. No skinned renderer is reparented to fake a transform-subtree check. The runtime/importer must inspect actual imported positive weights and same-rig membership.

A real Muzzle bone is exported as weapon's child with source head (0, 0.35, 0.072) and tail (0, 0.385, 0.072), exactly at the front safety-tip plane. Its local +Y is the bone-forward axis; do not assume Transform.forward. GLB exports all bones, FBX explicitly exports armatures/meshes/empties with deform-only filtering disabled. Packaging checks an actual FBX Model Muzzle parented to weapon and the GLB node. Actual Unity import must verify position/orientation before binding the same marker to the shot tracer/flash.

## Sixth-pass diagnostic scope and weight-root correction

Actual fifth-pass witnesses showed split/stretch deformation, not just incidental contact. The continuous glove had inverse-distance weights spanning arm.L, hand.L and finger chains. Rotating hand.L left arm-weighted palm/wrist vertices behind while fingertip IK moved other regions. The new explicit partition assigns the palm/wrist to hand, and blends each finger only into its own local phalange chain plus hand. No continuous-glove vertex is weighted to arm. This must be visually reviewed for hand/wrist/sleeve distortion even if collision counts improve.

Manual workflow input mode=contact-diagnostic skips studio views, all Idle/Fire/Reload videos and viewmodel validation. It runs the bounded 42 loading-surface samples plus bilateral key witnesses and 0+12/3+5/11+1 count views. contact-diagnostic.json explicitly says full_asset_validation=false and approved=false. It fails on remaining sampled intersections; a diagnostic pass is not a full asset pass. Use full only after reviewing this diagnostic geometry.

The core framing metric is corrected: a second actual render hides exactly the two long forearms and measures the remaining core alpha, retaining full-scene alpha separately for HUD/edge diagnostics. Width and height thresholds remain 25–32% and 25–35%, and unclipped core geometry must remain in frame. The old 0.3203125 full-alpha width included sleeves and was not a legitimate core failure. Conversely, the approximately 24% core height was below target and is not excused by sleeve height. The one shared lens is increased to 37.75mm with documented aspect shift; actual core masks still must pass after full rendering.

## Seventh-pass diagnosis: arm skinning and finite reach

R6 removed palm/arm mixed weighting but retained another invalid structure: the entire sleeve blended a stationary root with a hand rotated 180 degrees, creating the observed long twisted ribbon. This pass removes that root/hand sleeve blend and the flipped wrist. A proper upper-arm/forearm chain uses fixed bone lengths with stretch disabled; sleeve weights are local to those two segments and blend only at the elbow. The left thumb has a continuous reachable pinch arc; all fingertip IK stretching is disabled. Contact thresholds and the three ammo snapshots are unchanged.

For every reload frame, both arms and all three ammo snapshots, 600 records measure forearm length error, wrist-target residual, sleeve-ring seam error and finite shoulder-to-wrist reach. These supplement the 42 surface-intersection samples and mandatory independent review for visible hand/arm distortion. A numeric pass is not visual acceptance.

WristTarget.L/R are explicitly selected/exported empties parented to their respective hand bones. Runtime integration must perform the same fixed-length two-bone reach after Animator sampling and partial-count carrier offsets; baked Blender constraints do not execute inside Unity. The arm_reach contract names upperarm/forearm/target transforms. Until this runtime solver and imported-frame evidence are verified, no full-game acceptance is claimed.

SHA256SUMS is now resealed in a separate always-running workflow step after Blender, tee and any encoding process has exited. This final seal includes the completed blender.log; earlier in-process checksums are overwritten before upload.

## Eighth-pass targeted contact correction

The R7 fixed arm lengths, wrist seams and fingertip reach passed and remain unchanged. Its remaining failures separated into two mechanisms: (1) in all counts, unused little/ring fingers swept the left rail at frames 65–68; (2) at 11+1, the last loading slot crowded the right gripping hand at frames 56–68. The ring/little fingers now fold against the palm only during strip carry; the index/thumb retain the real first-nail grasp and the middle finger contacts the connector immediately behind it.

The entire fixed Loaded/Incoming slot layout, grasp target and carry path move 19mm forward together; pitch and capacity remain unchanged. This was reduced from the initially considered 29mm after calculating the actual fixed feed block's rear plane at y=.250. First slot is now y=.242. Each collation segment covers 26mm behind and 4mm ahead of its nail, totaling the unchanged 30mm pitch with no gaps. The conservative front extent including radius is y=.2485 (at least 1.5mm clearance); the complete 12-slot rear extent remains ahead of y=-.1165, inside the -.160 rail limit. Generation additionally measures actual vertex extents and rejects less than 1mm front clearance in both diagnostic and full modes. No blocker mesh or collision threshold is removed.

The intermediate lift is lowered by 30mm to retain finite reach with the forward grasp point, not to detach the hand from the strip. The same 42 obstruction samples, 600 rigid-length/reach/seam records and fingertip residual checks are retained. This is still a contact-diagnostic candidate pending actual pixels and exported/runtime verification.
