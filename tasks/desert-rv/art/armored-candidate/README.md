# Scrapyard Bulwark R3 — source candidate, not approved

R3 is a source-only response to all 53 actual R2 static/FPS images from run 37816833415. No local Blender or Unity process was launched. R2's rectangular cargo-box silhouette, uncovered front, three exposed rods, closed-state leaks and animated-door ownership mismatch were rejected. Prior artifacts remain evidence, not approval.

## Revised geometry and presentation contract

The plow, four load-bearing legs and front overlapping dorsal plates remain. The posterior assembly is a shallow oval cavity with a complete front/side/rear rim and matching sealed bottom. A flattened radial core is embedded inside it. Two shallow curved half-shells close along the back contour. They open outward around the longitudinal axis rather than forming a box or an awning. Geometry lives in cavity_geometry.py and receives closed-edge/manifold tests; actual silhouette and visibility still need another static run.

- Bulwark_Body: skinned body outside the presentation branch; one original basecolor/ORM atlas material
- Bulwark_Rig/body/WeakPointAssembly: follows the carrier bone; branch itself and every descendant are unkeyed
- WeakPointAssembly/Core_Renderer: independent rigid mesh, single submesh, material slot 0
- WeakPointAssembly/ArmorPlate_L_Pivot/ArmorPlate_L_Renderer
- WeakPointAssembly/ArmorPlate_R_Pivot/ArmorPlate_R_Renderer
- Closed pivot local rotations are identity. Unity open-angle intent is L=(0,0,-140), R=(0,0,140). Blender source rotations are local Y +140/-140. Imported axes must be measured before approval.
- Two atlas-using plate renderers plus one body and one core renderer: four renderers, two active materials. This deliberately allows runtime ownership instead of forcing all parts into one skinned/material renderer.

BeastWeakPointPresentation must exclusively control both pivots from actor.WeakPointExposed and replace only the independent core slot. Its Core_Open material is specified in binding-contract.json, including modest core-only emission; no body-wide recolor, arrow or substitute hitbox is used. Core_Open is runtime material metadata, not guaranteed as an unused exported material. Unity must create/verify its shader properties and _EMISSION keyword. Current gameplay is two-second whole-body recovery vulnerability, with no directional hit cone.

binding_contract.py rejects animation data/drivers or action channels under the dedicated branch, body leakage into it, or skinned core/plate meshes. Animation review uses a temporary unkeyed presenter emulation, explicitly not Unity runtime validation. The geometry FBX disables animation baking; bulwark-animations.fbx carries the rig-only seven clips separately so FBX cannot add constant tracks to presentation children. GLB channels are inspected after export and rejected if they target a presentation node. A real Unity importer must still reject any generated constant/TRS/material/visibility curves in the branch and confirm separate mesh renderer/material ownership.

## Evidence and framing

Static phase retains nine studio views with the original full-body safe-frame requirement. Forty-seven FPS evidence images use 1.65m physical eye height, 60-degree vertical FOV, rear-side/rear 2/4/6m views plus side boundaries at 4m and new closed front-quarter views. Each rear/side viewpoint compares closed with Recover 0, 1 and 1.95 seconds at the same camera pose. No auto-fit is used.

FPS records partial-body cropping as a diagnostic; close-range limbs or opened plates may be outside the view. The actual core must remain inside the unchanged 3.5% safe border. Closed-state leakage thresholds and open visible-area/height/ray-sample thresholds remain unchanged. All floor-penetration checks remain active. fps-visibility.json uses evaluated-mesh occlusion against the independent core. It is technical evidence, not proof of two-second player recognition.

## Motion and integration

Original runtime-aligned speeds/times remain: Walk 2.1m/s, Charge 10m/s, Windup 1.1s, Attack 1.2s loop, Recover 2s, Hit .28s, Death 1.8s. Root motion stays off; game motor alone moves and damages. Analytical stance speed, reachability, transitions, Death floor regression and interruptions are tested with Python. Return-home 2m/s, blocked tangent speeds, crossfades, arbitrary impact stops, imported axes and pause/reset behavior require actual runtime verification. Do not infer that the synthetic interrupt preview implements those rules.

## Safe execution and packaging

Publish only the exact R3 changed-source allowlist. No workflow replacement is included; preserve the publisher's GITHUB_ENV and explicit-outcome guards. Default manual dispatch stays static. Do not request full motion until the next actual static images are reviewed.

The existing public owner/main/manual-only standard Ubuntu workflow uses official Blender 4.2.3 plus its official checksum, fixed actions commits, read-only permissions and no persistent checkout credentials. No private concept image or third-party asset is bundled. All geometry, texture pixels and motion are original authored source. Official Blender distribution: https://download.blender.org/release/Blender4.2/ ; license: https://www.blender.org/about/license/.

Run test_static.py and test_pipeline.py, then validate_runtime_contract.py against current BeastActor.cs. Nonempty output and reused package paths are rejected. The existing 20m static / 80m motion / 120m job limits and 14-day retention are unchanged. Allowlisted payloads now expect 62 static or 86 motion files before package provenance/status/checksum metadata. Each run binds source, workflow, official binary archive, generated files, images, videos and reports with SHA-256. Missing files or technical failures remain PARTIAL_FAILED_NOT_A_SUCCESS, with evidence/logs retained. No source test or technical pass constitutes visual approval or Unity acceptance.
