# Bulwark v004 refined art producer — UNRENDERED / UNAPPROVED

The actual v003 Unity side image was rejected as too simple. This is a separate original-geometry producer, not a modification of the accepted functional source or a relabeling of historical art evidence.

## Visual work
- Curved overlapping press-formed armor: visible steel rolled rims, inset paint crowns, broad spinal reinforcements and selected fasteners.
- Leg mechanics: recessed structural link, protective shroud, knee bearing/hub, exposed shin cylinder and side return link. All single-bone ownership; original joint positions/lengths retained.
- Load feet: independent instep plate, dark heel rubber, three articulated-looking but rigid weighted metal toe shoes, profile tread bridges. No new animated toes or sole ownership ambiguity.
- Rear reactor: six domed ceramic lobes in the existing closed cavity, rather than a flat orange polygon. Single independent core renderer and material slot remain. Sand painted door exterior, dark metallic inner faces, integral underside ribs and hinge shafts.
- One 1024px basecolor and ORM atlas. The CC0 Poly Haven rust surface is used at deliberately low contrast inside an original warm sand/oxide/steel palette. Geometry and material-region scale carry the improvement; texture noise does not replace structure.

The original source sampler motion.py SHA stays 4edc78bd7ff6ec22d8ad378a71871f983f76262857c8bf9cec03a06f8ed7e010. Seven clip durations, 2.1m/s Walk, 10m/s charge, 2-second whole-body Recover vulnerability, runtime-only unkeyed two-door assembly, root ownership and capsule-r2 remain unchanged. A new mesh needs fresh imported soles and vertex-based checks; old numerical results and videos cannot approve it.

## Provenance
Original geometry/code. Bundled rusty_metal_02_diff_1k.jpg is by Rob Tuytel / Poly Haven, CC0-1.0:
https://polyhaven.com/a/rusty_metal_02
https://polyhaven.com/license
See materials/ASSET-LICENSE.json for the exact file hash. The site permits commercial use and redistribution of assets. No website preview renders, private concept image, logo or reference artwork is bundled.

## Verification boundaries
Run standard Python unittest for test_static and test_refinement. check_refined_math.py uses pure numerical shortest-axis bone transforms at 240Hz to preflight the new source geometry; it is NOT an engine execution or Unity local-TRS crossfade proof. All seven source clip minima are approximately +6mm before engine export. Actual Blender evaluated 240Hz and Unity full mesh 4mm gates still apply unchanged. Foot sliding and scene visibility remain unverified.

## Public Actions only, static first
1. Official pinned Blender 4.2.3: generate.py --output <fresh> --phase static. This creates eight studio angles, open-core view and unchanged 1.65m-high FPS 2/4/6m closed/open evidence. Inspect first. Do not start full motion because generation succeeds.
2. Once static images are reviewed, use sibling armored-refined-staged-v004/staged.py --stage technical --output <fresh>. The adapted previous executor preserves 60Hz numeric and 240Hz baked subframe checks and exports FBX/GLB before any video.
3. Render only chosen short whole clips at original speed through fixed <=24-frame chunks, nominal30fps; start Walk, Windup, Attack, Recover and Death. Same original-time endpoint/VFR receipts. All are new v004 evidence. REUSED=[]; no historical video reuse.
4. Unity import requires a NEW contract with actual new file/neutral-bound/material/mesh hashes, original node contract, capsule-r2, actual foot calibration and real GPU-skinned capture. Do not overwrite old candidate contracts or alias the new art to v003 receipts.

No workflow is published here. The coordinator owns owner/main/manual/free-hosted Actions wiring and explicit file allowlists. Its existing official Blender SHA pin and actions commits must be retained. The legacy monolithic animate entry remains only as the source export/check definition used by the staged executor; do not run it for a long all-video job.
