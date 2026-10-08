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
