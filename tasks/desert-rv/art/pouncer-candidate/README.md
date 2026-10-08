# Death continuity correction: shared joint path and explicit rotation branches

The first technical-first run correctly refused to render. It found a 477.7mm hind-paw plunge at a half-keyframe and a genuine 74.83mm rigid translation jump in10ms. The same exported GLB at1.275s, using shortest-arc quaternion interpolation, is only -2.58mm; its100Hz endpoints are near+1mm. This exposes a native rotation-representation/interpolation problem, separate from the real18.52-degree visual-body and19.64-degree hind-hip jumps between1.27 and1.28s inherited from unrelated per-frame search outcomes.

This revision does not smooth an already-grounded result or add a large global lift. It constructs one synchronized local joint path from coherent baseline control poses at0,.30,.60,.90,1.20,1.44,1.80s, using hemisphere-compatible shortest-arc quaternion interpolation and a shared continuous blend parameter. Actual all-mesh contact placement happens AFTER that joint path is evaluated. A read-only FK probe predicted a maximum11.18mm translation per10ms, below the unchanged30mm limit; this remains mathematical evidence, not native approval.

When baking, each quaternion is converted to XYZ Euler using the previous frame's compatible Euler representation explicitly, rather than allowing independent matrix decomposition branches. Native audit files record raw versus compatible branch changes and full local transforms around0.81–0.82 and1.27–1.29s. Gameplay root,1.8s duration,4mm penetration limit, new physically correct anatomical support definition and protected non-Death actions remain unchanged.

The gate is now three-way: the authored .blend at200Hz, a clean native import of actual GLB at200Hz, and an independent clean native import of actual FBX at200Hz. A native-source pass is only PENDING_IMPORTS until both serialized imports pass. All three report worst depth and time. Any failure blocks every image; only the exact final passing candidate can render the same four opaque stills. No other visual scope has been added.

---

# Death technical-first: physically correct proximal anatomy

This entry point supersedes the earlier iterative Death render loop below. It uses the exact already-examined native baseline from run 37844163484, artifact 11579478380, pinned by source SHA and blend SHA256 in death-baseline.json. No new sculpt, external mesh, weights, materials or other action is created or changed. Baseline expiry/mismatch is a hard blocker, not permission to substitute another file.

## Explicit support-definition correction

The former >=60% trunk-only rule was wrong for this generated anatomy. Its genuinely exterior proximal shoulder flesh is almost 100% fore_upper.L weighted, and the proximal hip flesh is mostly hind_upper.L. The old rule excluded the real load-bearing meat and forced it approximately 166mm into the floor to place an interior trunk subset on the plane. The task's direction explicitly approved correcting that definition after examining the actual GLB evidence. The all-mesh 4mm collision tolerance is unchanged.

Support is now selected by anatomical space, combined local muscle/trunk influence, and the first proximal portion of the appropriate upper-limb bone: segment fraction [-0.50,0.45], within 0.34m of its root, with explicit shoulder and pelvis bounds. Head, distal elbow/knee, and paws cannot substitute. Every witness reports its actual weights and segment fraction. Separate two-region multi-point and low-percentile checks remain. The former trunk-only result is still reported for comparison, but is no longer allowed to force exterior flesh through the floor.

## Numerical candidate, then native gate

Read-only probes of the existing GLB found a close-to-current pose with approximately five degrees of longitudinal tilt, real shoulder/hip muscle support, and relaxed neck. A refined final-pose probe had all-mesh minimum +0.126mm, face skin +14.36mm, shoulder +4.36mm, hip +1mm. These numbers are mathematical feasibility, not a rendered or native pass. Full evidence is retained in death-feasibility-math.json.

The native Actions-only script loads the pinned .blend, preserves all baseline meshes/weights/rig data and every non-Death action by digest, and authors Death's visual-body rigid placement plus neck relaxation. It uses the real all-mesh support envelope rather than the invalid inner-trunk plane. It does not scale or squash a model. Gameplay root remains fixed and duration remains 1.8s. The complete baked Death is sampled at 200Hz, including half-keyframes, checked for ground penetration, contact patches, face proximity, final hold and discontinuous placement jumps. GLB and FBX are exported and their actual seven clip durations are read back.

A failed native technical gate uploads its numeric output and renders NOTHING. A pass may render exactly four opaque stills of that exact SHA-verified candidate: terminal views 03/07 and fixed 1.02s/1.35s side views. No video or full seven-action rendering is run. The report explicitly remains DEATH_TECHNICAL_FIRST_NOT_FULL, with no visual or production approval. Full native Unity action/interruption/collision review is still required.

Manual workflow input is scope=death-technical-first; render_after_pass defaults true and can be disabled for a strictly numerical run. Technical output is uploaded before the optional four images. Both artifacts have independent checksum lists. This is all on a standard free GitHub Actions runner; no local Blender or Unity execution is required.

## Archived iteration context (not the current execution entry)

# Death precision correction: head-axis feedback and hidden shoulder collision

Actual support diagnostic 37840535651 kept the improved low side-lying appearance, but its worst exported penetration was 203.8mm at 1.02s on the lower jaw. The former hardcoded negative neck-Z response was the wrong sign after side-roll. Read-only GLB axis probes found positive local neck-Z raises the jaw. They also exposed a separate hidden 150mm proximal fore_upper.L skin penetration and its joint origin 15mm below the floor; raising the mouth alone would not fix that second problem.

This revision uses evaluated-geometry feedback to test both rotation signs on neck/head axes, within bounded relaxation angles. It resolves proximal shoulder geometry through bounded limb bend-plane rotation/reach changes; only when necessary, it tests a small side-roll change while restoring the same shoulder/pelvis support targets. The basic accepted-direction low side-lying pose and the mesh are retained; no disconnected bone-root translation, mesh squash, or whole-body downward offset is used to fake clearance. A small chest rotation can broaden the true shoulder patch, whose third point previously missed the original 30mm line by only 0.352mm. All original thresholds remain.

`death-diagnostic-summary.json` directly states maximum penetration in metres, worst time, evaluated mesh/vertex/bone weights, endpoint depth, and both support patches. It should be read before any technical-pass claim. The same finite Death-only visual scope remains NOT_FULL. Head, hidden shoulder surface and the three-point shoulder patch must all be inspected in the actual new artifact; this source revision has no native or visual approval yet.

---

# Death: separate genuine shoulder and pelvis support candidate

The previous visually rejected pose touched the floor with a limb-root point while trunk-dominant skin remained 153–184mm above it. Read-only actual GLB reconstruction also found an 8.64mm penetration at 0.95s on Skin vertex 4581, weighted 88.85% hind_upper.L and 11.15% pelvis. These are evidence of a bad support definition and an insufficient proximal-joint contact response, not a reason to relax the 4mm threshold.

This candidate uses two disjoint anatomical support regions, shoulder and pelvis. Both exclude head and distal limbs and require each vertex to carry at least 60% combined pelvis/spine/chest/neck weight. Each region reports its minimum, 5th/10th height percentiles, near-floor vertex count, world coordinates, bind coordinates and exact skin weights of six witnesses. Both must genuinely rest near the floor; one low point cannot conceal the other region hanging in the air.

The authored corpse rolls into a lower oblique side-lying pose with slight spine relaxation. Its front/rear support is balanced through rigid-body pose and bounded angular adjustment, not by scaling or flattening the mesh. Individual limbs yield through bounded IK pole/reach changes, including the previously missed proximal hip surface. The same coupled contact solver preserves exact timing, stationary root and all-mesh penetration checks. Every non-Death motion branch, geometry, materials and rig remain hash-locked.

The limited Death diagnostic delivers original opaque rest views plus clearly named death-support-overlay images. Only those separate witness overlays use translucent materials to expose orange shoulder and cyan pelvis markers through the skin; labels and JSON give actual world contact values and weights. Their transparency is never exported to the GLB/FBX, and the original opaque renders remain the visual-quality evidence. No visual approval is inferred from successful geometry/contact numbers. SCOPE=DEATH_DIAGNOSTIC_NOT_FULL remains mandatory until a full native Unity review is completed.

---

# Death rest-pose revision: relaxed side-supported corpse

The preceding death-diagnostic run 37829068773 passed technical contacts, but its actual rest-07 image was visually rejected: all four paws remained horizontal and weight-bearing, with the torso twisted above them. No visual or production approval is implied by that technical pass.

This revision changes only Death pose intent. The lower-side limbs extend sideways rather than beneath the shoulders and hips. The upper-side limbs fold loosely nearby at a different height; their paws no longer seek a standing ground plant. Paw surfaces progressively roll sideways with mild asymmetric yaw. Head and neck pitch are reduced so the skull follows the side-lying trunk. The torso remains the primary side-contact target. Existing per-joint contact solving, no root motion, exact 1.8-second Death timing and unchanged 4mm penetration rejection remain.

The new death-rest-pose.json makes these artistic targets inspectable. Posture checks reject the prior four-horizontal-palm pattern, but cannot approve an image. The same bounded DEATH_DIAGNOSTIC_NOT_FULL rendering must be inspected again: whole Death, near-ground frames, and both opposing rest views. Mesh, materials, rig, parameters and all non-Death source motion remain hash-locked to R3.

---

# Pouncer R3 Death-only repair candidate

SCOPE=DEATH_DIAGNOSTIC_NOT_FULL when using the default manual workflow input. No asset approval is granted. The accepted-for-Unity-candidate R3 shape, materials and non-Death actions are unchanged. The exact preceding source SHA and unchanged-region hashes are recorded in death-change-boundary.json.

## Exact R3 failure and repair

Read-only reconstruction of the actual exported R3 GLB locates worst penetration at 1.07 seconds: Claw.005 vertex 71, fully weighted to hind_paw.L, at -18.155mm. At the last pose, three claws on that same paw are at approximately 4/20/36mm instead of a common plane. The previous script aligned paw orientation, then changed IK targets/poles again. That final change re-tilted the paw and disturbed shoulder/torso contact. The actual end torso contact was still +50.225mm.

Death now has one coupled authoring solver: update the torso contact target, correct each offending foot or joint individually, evaluate IK, then compute paw local basis from its final evaluated parent. Repeat to convergence and end with paw orientation and contact measurement, with no later target changes. It records every iteration in death-contact-solver.json. It does not clamp vertices, move rendered images, or globally drop the exported output onto the floor. A failed solve still fails the unchanged 4mm penetration and 12mm torso-contact gates.

## Bounded diagnostic

Manual input scope=death-diagnostic still builds the real asset, seven exported animations, materials and serialized GLB/FBX timing/structure checks. It renders only the full Death at 30fps, opposing rest views, and ten near-ground stills covering 0.75–1.80 seconds including the measured 1.07-second failure. review-scope.json and validation.json identify DEATH_DIAGNOSTIC_NOT_FULL; full-motion visual review is NOT_RUN, even if its technical checks pass. No accepted flag is written. scope=full restores complete static and motion rendering. Nothing is automatically installed in a game scene. Full Unity animation, contact and interrupted-transition validation remains required.

---

# Original pouncer candidate R3

UNREVIEWED. R1 was rejected after actual render review. R3 continues the controlled-section anatomical construction, not a recolor or a triangle-count claim. No official game scene, RV, Unity import manifest or runtime script is changed. All generation and rendering run only on GitHub Actions.

## Early review before full animation

Manually dispatch the owner-only `Desert RV original pouncer candidate` workflow. Blender 4.2.3 is downloaded from its official distribution and checked against the matching official checksum. The first phase builds and UV-bakes the sculpt, renders eight neutral-lit static views, and uploads `pouncer-static-r3-RUN_ID`. This artifact becomes available before the animation phase. The second phase authors/bakes seven clips, validates the actual baked skeleton, exports GLB/FBX/blend, and renders movement/interrupt evidence. Existing R1 artifacts are not deleted.

## R3 corrections after actual R2 static rejection

R2 is also rejected. Its world-up-per-ring correction flipped adjacent limb cross-section frames by approximately 97–147 degrees, producing pointed shoulder covers and disc-like hips. R3 replaces this with continuously parallel-transported orthonormal frames. Pure numeric regression tests cap the actual authored limb-frame increments below 65 degrees; this is a source test, not a rendered mesh approval. Nine-section muscle transitions start inside the torso, with thicker forearms; smaller inset eyes gain fused upper orbital ledges. Wedge head, distinct jaw, claws, color separation and baked UV texture remain.

`topology-stages.json` reports voxel-union and decimated surfaces separately: connected components, boundary edges, nonmanifold edges, nonmanifold vertex fans and diagnostic coordinates. Euler alone does not prove an opening. Genus is inferred only on a closed connected manifold surface; any unintended handle still fails. Actual static and motion renders must be reviewed again.

## R3 motion changes after R2 run 37811796028

Actual R2 evidence found accurate planted gait speed and complete motion framing, but Death was held up by limbs (0.960m highest point) and 25%/75% interrupted blends penetrated by 19.2mm/8.1mm. R3 keeps the 4mm penetration rejection limit. Death now solves side-of-torso contact and gives each leg a separate IK endpoint and relaxed pole, rather than rotating a rigid animal and grounding its lowest claw. Additional opposing three-quarter death-rest images expose the final support. Acceptance tests require actual torso contact, low relaxed paws, stable hold, and a side-lying height limit derived from the body's real width rather than an unrelated fixed height.

Windup shifts weight back by up to 0.105m and compresses by 0.14m against support. Recover has a more visible absorbing compression and controlled return. Before export, every Attack frame is probed against Recover with quaternion interpolation. The minimum needed flight clearance is baked into Attack (maximum added lift 0.16m); a second full probe rejects residual penetration. This is source-animation repair, not image-time ground correction. All values and pre/post minima are saved in transition-clearance.json.

Important runtime finding: existing BeastActor calls Animator.CrossFade(state, .12f). That argument is normalized, not fixed seconds. At nominal 0.8s source duration it is estimated as 0.096s; import speed/controller behavior still requires measurement. Current-duration simulations advance both source Attack and target Recover within the 1.3-second Recover budget, assuming linear quaternion blending. They remain explicitly synthetic; exact Unity Animator sampling is not measured. One additional midpoint comparison proposes 0.24s fixed-time recovery to avoid a visually abrupt drop. It does not change the runtime code and is not a verified Unity transition. Recover's state budget remains 1.3 seconds. Official API references: https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Animator.CrossFade.html and https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Animator.CrossFadeInFixedTime.html.

R2 serialized GLB timing also contained an unwanted leading frame. R3 authors at 100fps so .78s/.28s endpoints are exact, temporarily shifts export curves and NLA ranges to frame zero, enables glTF zero-start sliding, and then independently reads actual GLB sampler and FBX AnimationStack timestamps. Both formats must start at zero and end at the requested game duration within 1 microsecond. Game clocks are not changed to match an export error.

## Foundation changes from rejected R1

- Controlled torso, head, limb and tail cross sections replace ellipsoid piles. Deliberate cheek/brow/muzzle planes, thin lumbar tuck, slimmer articulated lower legs and small hocks address R1's round body and rear-limb tunnel. Fine voxel union closes anatomical branch junctions, with just one low-strength relax pass. Euler-characteristic and connected-component checks reject unexpected skin tunnels.
- Separate moving lower jaw, visible mouth cavity, amber eyes in dark sockets, upper fangs and pointed swept claws replace a surface seam and round beads.
- Strong dark ventral/leg pigmentation and matte sandstone dorsal layers are baked into a real 1024px UV base-color PNG. Standard Principled PBR uses the image; GLB embeds it and FBX embeds/copies it. A standard Unity Lit shader can use the provided BaseColor image and roughness equivalent. Unity import parity still requires actual verification.
- Original IK-authored, baked two-bone limbs replace rotating paddles. A 0.4-second diagonal trot has 0.2-second stance with 0.54m backward local foot travel, matching 2.7m/s forward root movement. Baked ankle travel is tested against speed. The root remains stationary in exported clips; gameplay moves the capsule.
- Windup compresses against planted feet. Attack has a visual-body leap and readable mouth opening, landing compression and ground checks. Death falls on its side and holds. Recover absorbs weight; Hit recoils against support.
- All-mesh floor bounds are checked per frame with a 4mm penetration limit, not R1's missing penetration gate. Static contact and endpoint contact use a 20mm maximum gap. These are technical rejection limits, not visual acceptance standards.
- Side-view framing is 960x540 with a 4.35m field to keep the head in frame at leap apex. Three current-duration interrupted Attack-to-Recover simulations and one proposed fixed-time comparison are rendered and explicitly identified as synthetic. They do not verify Unity's actual state machine or collision behavior.

## Outputs and limitations

Seven exported states: Idle, Walk, Windup, Attack, Recover, Hit, Death. Requested timing and 100fps sampled timing appear in clip-manifest.json. root_motion=false. Gait target and actual baked samples are separate evidence files. Motion videos, eight-view images, contact sheets, checksums, source SHA and Blender upstream checksum are preserved. Technical failures do not prevent rendering or uploading evidence.

Do not insert this candidate automatically. A technical pass never approves appearance. Review all eight directions, shoulder/hip deformation, floor load, foot sliding, complete head framing, bite readability, the interrupted landing and Unity texture parity. Remaining defects must be repaired using actual images rather than assuming the source design worked.

All geometry, skeleton, motions and image pigmentation are original procedural work created for DesertRV. No private concept image is uploaded. No third-party model or animation is used. Blender licensing: https://www.blender.org/about/license/.
