# V4 R2: corrections from actual Unity frames

Baseline: commit `a9bb99ff9dec15d2b44ee914239f8b70393e287a`, actual public Actions run `37950970878`. The first V4 run passed native authoring and export, but visual review rejected it as insufficiently detailed. This revision has no native/art approval until its own actual twenty-camera run is reviewed.

## Evidence and diagnosis

- `Scrapyard-overview.png`: strong periodic grid across far sand and dunes. Native serialized ground UVs were verified as world X/Z divided by 2 m, normals upward and tangents consistent; the source has mipmaps and linear normal-map import. A large repeated low-frequency normal pattern remained a plausible cause, not a proven isolated cause. This revision removes the ground normal path entirely rather than adding noise. Sand and distant Dune use separate materials; Dune has only 8% local diffuse variation. Both converge to the diffuse texture's final mip with distance. The original 2 m UV scale remains measurable. Two diffuse importers change from bilinear to trilinear; all image bytes stay unchanged.
- `FirstStation-forecourt-eye-height.png`: black sharp polygon stains resembled holes; the sand edge repeated the same stamped shape. Thin overlays now use zero-alpha outer vertices with four opacity rings and smooth 32-sided boundaries. Oil has maximum material alpha 0.23. The road shoulder is a continuous smoothly varying narrow ribbon. These are mesh overlays, not simulated fluid or new collision.
- Original pumps had hoses and meters, but their inherited geometry was too small/hidden in the actual camera. Additions derive the face direction from actual meter/head world bounds, with physical bezel depth, two small analogue gauges, needles, flexible 18-section hose loops and nozzle geometry. Original pump body/colliders remain.
- The yard needed process-scale organization. Two retaining bays and grouped folded-sheet heaps frame the existing stripping lane; a feed conveyor reaches the receiving hopper; a press/cradle identifies the powered work area. Container end rails, doors and locking rods replace texture-only flatness. Hardstand is broken into bounded slabs with softened outer edges, while original road, salvage and power approach zones stay open.
- Night baseline used a 0.62 directional fill and several overlapping low-output point lamps; the new 3-strength downward spots made small isolated pools. The retained URP is already per-pixel with eight additional lights per object. R2 has seven active local fixtures total, removes duplicate fills, aims stronger physically aligned spot housings toward the player's approach, and reduces only the night directional factor to 0.48. Existing ambient colors and original RV materials remain. Native authoring checks the exact seven-light count and retained URP mode/limit; no project settings are modified.

## Exact new producer outputs

- 121 generated payloads: R1 37 meshes, R2 45 meshes, R3 23 meshes, 16 shared materials.
- 122 generated metadata files, including the generated directory metadata.
- `generated-contract.json` and native `PolishExpectedMeshNames` contain the same exact sorted set. The validator rejects any missing or extra asset, including files under the generated directory.
- All 29 CC0 asset binary payloads remain byte-identical to V4. The new `EnvironmentSurface.shader` and geometry are self-authored source, with no additional external asset or license. Existing provenance remains valid.
- The new shader is confined to Sand/Dune/Dust/TrackSand/Oil materials. It uses existing URP PBR lighting, fog and additional-light functions, vertex opacity and one original diffuse map; no new render feature, pipeline asset, global shader replacement or AI image is involved. Native single-case validation checks shader support and errors after rendering all twenty frames.
- Original 18 camera poses and the two 1.62 m station closeups remain unchanged. The case remains one explicit test with a 600000 ms timeout. Source protection, original clearance checks, and export allowlists remain mandatory.

## Review gate

Compare the new original-resolution frames against the same twenty frames from run 37950970878. Reject continued sand grids, dark star-shaped patches, hidden pump details, weak night hierarchy, blocked access, or a yard that still reads as boxes on a bare slab. Offline tests and a successful native job alone are not visual approval, gameplay integration, Android performance evidence or commercial-quality acceptance.

Container detail meshes are separately batched per physical container (three spatial groups), so no renderer or collider bounding box bridges the road. The original native renderer-AABB clearance gate remains unchanged.
