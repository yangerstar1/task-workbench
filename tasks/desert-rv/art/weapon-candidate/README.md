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
