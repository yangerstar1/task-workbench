# Original pouncer candidate R2

UNREVIEWED. R1 was rejected after actual render review. R2 is a new controlled-section anatomical construction, not a recolor or a triangle-count claim. No official game scene, RV, Unity import manifest or runtime script is changed. All generation and rendering run only on GitHub Actions.

## Early review before full animation

Manually dispatch the owner-only `Desert RV original pouncer candidate` workflow. Blender 4.2.3 is downloaded from its official distribution and checked against the matching official checksum. The first phase builds and UV-bakes the sculpt, renders eight neutral-lit static views, and uploads `pouncer-static-r2-RUN_ID`. This artifact becomes available before the animation phase. The second phase authors/bakes seven clips, validates the actual baked skeleton, exports GLB/FBX/blend, and renders movement/interrupt evidence. Existing R1 artifacts are not deleted.

## Actual changes from rejected R1

- Controlled torso, head, limb and tail cross sections replace ellipsoid piles. Deliberate cheek/brow/muzzle planes, thin lumbar tuck, slimmer articulated lower legs and small hocks address R1's round body and rear-limb tunnel. Fine voxel union closes anatomical branch junctions, with just one low-strength relax pass. Euler-characteristic and connected-component checks reject unexpected skin tunnels.
- Separate moving lower jaw, visible mouth cavity, amber eyes in dark sockets, upper fangs and pointed swept claws replace a surface seam and round beads.
- Strong dark ventral/leg pigmentation and matte sandstone dorsal layers are baked into a real 1024px UV base-color PNG. Standard Principled PBR uses the image; GLB embeds it and FBX embeds/copies it. A standard Unity Lit shader can use the provided BaseColor image and roughness equivalent. Unity import parity still requires actual verification.
- Original IK-authored, baked two-bone limbs replace rotating paddles. A 0.4-second diagonal trot has 0.2-second stance with 0.54m backward local foot travel, matching 2.7m/s forward root movement. Baked ankle travel is tested against speed. The root remains stationary in exported clips; gameplay moves the capsule.
- Windup compresses against planted feet. Attack has a visual-body leap and readable mouth opening, landing compression and ground checks. Death falls on its side and holds. Recover absorbs weight; Hit recoils against support.
- All-mesh floor bounds are checked per frame with a 4mm penetration limit, not R1's missing penetration gate. Static contact and endpoint contact use a 20mm maximum gap. These are technical rejection limits, not visual acceptance standards.
- Side-view framing is 960x540 with a 4.35m field to keep the head in frame at leap apex. Three interrupted Attack-to-Recover simulations are rendered and explicitly identified as synthetic. They do not verify Unity's actual state machine or collision behavior.

## Outputs and limitations

Seven exported states: Idle, Walk, Windup, Attack, Recover, Hit, Death. Requested timing and 60fps sampled timing appear in clip-manifest.json. root_motion=false. Gait target and actual baked samples are separate evidence files. Motion videos, eight-view images, contact sheets, checksums, source SHA and Blender upstream checksum are preserved. Technical failures do not prevent rendering or uploading evidence.

Do not insert this candidate automatically. A technical pass never approves appearance. Review all eight directions, shoulder/hip deformation, floor load, foot sliding, complete head framing, bite readability, the interrupted landing and Unity texture parity. Remaining defects must be repaired using actual images rather than assuming the source design worked.

All geometry, skeleton, motions and image pigmentation are original procedural work created for DesertRV. No private concept image is uploaded. No third-party model or animation is used in R2. Blender licensing: https://www.blender.org/about/license/.
