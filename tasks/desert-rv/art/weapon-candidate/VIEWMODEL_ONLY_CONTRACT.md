# Bounded R9 framing correction and evidence reuse

This task reads the exact R9 full-run artifact 11579827076 from run 37841477090. The ZIP, asset files, original validation, videos and original checksum manifest are pinned and verified. An expired or changed artifact is a blocker; no alternate baseline is selected.

Only the displayed weapon rig moves 15mm left along the preview camera's horizontal plane. Both aspect ratios use the same displacement, original orientation, original 37.75mm lens and original per-aspect vertical framing. No horizontal camera projection shift is applied. Meshes, skin weights, bone rest hierarchy, materials and animation data are fingerprinted before and after. The original blend/FBX/GLB bytes remain unchanged and no model is re-exported or saved.

The runner renders only the two full viewmodel PNGs and their two core-only masks. It does not rerender eight studio views, three motion videos, contact samples or reach samples. The output says new_full_run=false, preserves the original full run's failure result, and reports which framing checks replaced the failed ones. Other technical evidence is reused only because source-file identity and in-memory model equivalence are explicitly verified. A combined technical evidence pass is not a new full run, visual approval, Unity import approval or gameplay acceptance.

## Unity boundary

The 15mm preview displacement is an instance-presentation adjustment, not permission to change the game camera's projection or move the reticle. Unity must calibrate the actual imported camera-relative weapon instance and measure an equivalent small instance displacement, accounting for real scale and axes. The imported Muzzle position/forward-axis and tracer/flash direction still require actual Unity evidence. Blender's viewmodel screenshot is not proof of Unity reticle alignment. Do not silently copy camera parameters or assume the preview's coordinate system is Unity's.

## Outputs

- viewmodel-validation.json: only newly measured framing checks
- asset-equivalence.json: pinned source identities and before/after semantic fingerprints
- combined-technical-evidence.json: explicit old/new evidence relationship and remaining failures
- Four PNGs, completed log and final SHA256SUMS

The original full-run report is never edited or renamed as passing.
