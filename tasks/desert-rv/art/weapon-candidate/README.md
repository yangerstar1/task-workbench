# DesertRV original weapon + hands candidate

This is a newly authored candidate, not a recovered or approved production model. No original concept image, third-party model or paid service is included. All mesh forms and material definitions are authored in this source. Parent review must inspect actual rendered pixels and motion before acceptance.

## Reproduce

Owner manually dispatches `desert-rv-weapon-art.yml`. Standard GitHub-hosted Ubuntu runner downloads official Blender **4.2.3**, verifies Blender's published SHA256, generates, exports and renders. Do not run Blender on the dot cloud computer or the user's computer. Local checks are Python AST/compilation only.

Exports: `weapon_hands.blend`, skinned `weapon_hands.glb`, `weapon_hands.fbx`; metallic/roughness Principled BSDF materials are directly exportable PBR (solid material color, no external procedural texture dependency). Animation clips use no game damage, ammunition or input callbacks.

## Coordinate / runtime contract

- Metric units; source +Y toward muzzle, +Z up, +X right. GLB and FBX exporters perform axis conversion. FBX `-Z` forward / `Y` up.
- Armature: `root`, `weapon`, `magazine`, `follower`, `trigger`, `arm.L/R`, `hand.L/R`, three-segment fingers (two thumb segments).
- Named `Grip`, `Trigger`, `Magazine` empties are authoring anchors. They are not game event callbacks.
- Idle: 2 s. Fire: exactly 0.22 s, with subframe endpoint. Reload: exactly 1.65 s. Motion evidence sampled at 60 fps; integer-frame Fire video is 15/60 s including endpoint sampling, distinct from animation action duration.
- Initial budget checks report weapon 8–12k / hands 10–16k triangles; budget compliance is neither a quality certificate nor silently forced by unnecessary subdivision.
- Source stores <=4 normalized weights per vertex. Explicit union creates connected glove form before skinning.
- Export only asset objects; studio lights/cameras are kept in the `.blend`, excluded from GLB/FBX.

## Evidence and rejection criteria

Eight studio views, complete side-view Idle/Fire/Reload videos, 1280x720 and 1600x720 model composition captures, clip/weight/triangle validation, exported GLB animation validation and SHA256 manifest. Output has no game HUD; actual phone-button overlap requires a real HUD overlay, so it is explicitly **not passed** by this package.

Reload first candidate keeps the same magazine and left hand synchronized through withdrawal/reinsertion, then reaches for follower. This is not yet a certified fresh-magazine transfer. Finger contact/penetration and the follower interaction remain visual-review gates. Hand anatomy is voxel-unioned geometry with distance-weight skinning, not production retopology. A successful runner only proves artifacts were generated; it must not be described as commercial-quality acceptance.

No production scene, game controller, damage system or ammunition logic is modified.

The initial straight-forward viewmodel may fall below target horizontal occupancy due to gun foreshortening. `target_fit` reports this explicitly; reviewer should reject or revise camera/pose rather than accept a cropped or stretched model.
