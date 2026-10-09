# Environment V4 native-render handoff

## Ready candidate, not visual acceptance

Candidate source locations: `tasks/desert-rv/` and the explicitly listed repository workflow files.
Base public commit: `8b45b3c40e0752eed65ede5f3136a50761bd1a38`.
The only pre-existing payload edits are `JourneySceneAuthoring.cs` (one added call) and `ASSET-NOTICES.md` (CC0 notices). All original RV, cabin, Runtime, original scene, shader, ProjectSettings and Packages bytes were compared with the baseline and are unchanged. No Unity or Blender has been run locally.

## Delivered

- `JourneySceneAuthoring.EnvironmentPolish.cs`: independent deterministic authoring partial; meter-projected PBR surfaces, station upgrade, industrial equipment, three region identities, layered terrain, physically attached task lighting, bounded shared-material mesh batches.
- `JourneySceneAuthoring.EnvironmentPolishCapture.cs`: 2 extra eye-height views. Existing 18 camera poses and FOVs remain unchanged.
- `Art/EnvironmentV4`: 7 complete Poly Haven 1K material sets (diffuse, OpenGL normal, derived linear metallic/smoothness), 7 original Kenney models, original color atlas and license, per-file provenance. 29 art payloads, 13,334,988 bytes. All are CC0. The 7 derived masks retain the source roughness SHA and formula. No commercial/QAL or unverified asset is included.
- `generated-contract.json`: exact expected 97 native mesh/material files plus 98 metadata files (including the generated directory meta). Meshes: R1 35, R2 25, R3 23. Shared materials: 14. Native authoring rejects missing/extra mesh keys before saving. These are expected native outputs, not already-generated files.
- 13 passing offline preflight tests, plus delimiter and byte-preservation checks. These are not C# compilation, Unity import, native collision, gameplay, screenshot acceptance, or device performance evidence.

## Integration boundary

Copy only the explicit entries in `candidate-file-manifest.json`. Do not transplant the full copied baseline over another worker's latest tree. Register all exact generated paths in the new preparation producer/export closure. Do not broaden a wildcard and do not merge into the old byte-fixed restoration package. Refresh `SOURCE-STATE.json` in the coordinator's reviewed integration tree after resolving all intentional source changes. This candidate deliberately leaves that shared inventory untouched.

## Native Actions sequence

1. Fresh import Unity 6000.3.19f1 + URP 17.3 and compile.
2. Author new candidate scenes using the normal new producer. The unchanged authoring flow now calls `AuthorEnvironmentPolish` before optional supplies.
3. Run original renderer/collider driving corridor, source-preservation, salvage/power and optional supply approach checks. The static offline envelope tests are not replacements.
4. Capture the unchanged 18 real cameras with `CaptureEnvironmentCandidates`.
5. Also execute `DesertRV.Editor.JourneySceneAuthoring.CaptureEnvironmentPolishCloseups` to produce `FirstStation-forecourt-eye-height.png` and `FirstStation-garage-eye-height.png` under `JourneyEvidence/environment-v4`.
6. Include all 20 images, the native clearance evidence, closeup capture report, and per-region `environment-v4/region-N-authoring.json` in the result artifact. Retain exact source commit/receipt and compare same-camera frames with prior R3 images.
7. Verify import/save stability of new materials and input `.meta` files. The source author never modifies importers. New FBX metadata copies the current native ModelImporter 24300 schema; texture metadata copies the native TextureImporter 13 schema. Any first-import normalization must be explicitly reconciled, not waved away or allowed to alter old source assets.

## Texture scale and budgets

- Fine empty desert: sand_03, 2 m repeats, normal strength 0.19, smooth continuous terrain. Its contrast is low. Aerial_sand's photographed tire tracks are restricted to pull-offs at 15 m scale.
- Asphalt and forecourt concrete: 3 m repeats.
- Plaster and corrugated sheet: 2 m repeats.
- Oxidized steel: 1 m repeats. Rust is intentionally dielectric. A=smoothness=1-roughness; normals import as NormalMap, all masks linear.
- Retained station major walls, roof and fascia receive copied visual meshes with world-meter UVs. Original colliders remain intact. Original source FBX/material bytes are not edited.
- New geometry is combined by material and spatial group; no thousands of independent cube objects. Terrain is split west/east. Generated meshes are capped at 80 per region / 90k triangles; imported industrial pieces at 20 renderers / 18k triangles; new fixture lights at 3 per region. Actual counts are written by Unity. These caps are not a performance claim; existing scene costs and Android frame time still require measurement.
- Large terrain and shed structures have authored static collision. Small pipes/fixtures have no extra collision. The RV's road corridor, original gameplay bindings, progress, enemy spawns, optional supplies and trigger coordinates are unchanged.

## Review focus

Check actual driving and dismounted frames first. Reject enlarged UV grain, repeated track patterns off-site, dark crushed night surfaces, blocked pump access, disconnected floating fixtures, glossy clay-looking sand, factory color-map toy saturation, and oversized bounding batches. The current monster art is deliberately unchanged; this environment candidate does not satisfy a separate monster-detail revision.
