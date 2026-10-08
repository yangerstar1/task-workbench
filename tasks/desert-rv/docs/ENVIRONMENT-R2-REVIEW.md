# Environment revision 2: actual-image rejection and source repair

Base: public main `35b84ffb462c5e0ef264359346a6c7bb89f0b80e`.
Base JourneySceneAuthoring.cs SHA256: `0f8d6cfb83c5c950e30f8d39f73bd07eb78c1f543cc4f1ac34fdcf37a5ec060b`.
This revision changes that one Editor source file only. Preserve its existing .meta/GUID. It is not a replacement from the older frozen author package. The latest nested finally, empty-scene restoration, protected-file diagnostics, three render-target allocation/release accounting and graphics receipt are retained.

## Images actually inspected

All 12 real PNGs from run 37815292637, plus the user-provided approved concept, were visually inspected. The concept is not included in this source package or published.

- FirstStation overview: mesa skirts engulf the station and road; black terrain regions and purple road fringes are visible.
- FirstStation ground: a rock skirt occludes most of the lower image and hides the walkable space.
- FirstStation landmark: image predominantly shows the outside wall, not a useful interaction approach.
- Scrapyard overview: same giant mesas and road, with a few scattered primitive blocks; no legible scrapyard spatial identity.
- Scrapyard ground: the foreground mesa again cuts off the player view and road.
- Scrapyard landmark: unexpectedly shows the spawn RV instead of the actual cabinet expected around z=23.
- NightBeacon overview: virtually the scrapyard with cooler light; a thin pole is not a sufficiently legible beacon.
- NightBeacon ground: same physically obstructed foreground.
- NightBeacon landmark: again resembles the spawn view rather than the cabinet area.
- The three cabin images: the retained RV cabin/workbench is substantially more coherent and is preserved. Environment outside the windows is not accepted merely because the cabin is intact.

The package-protection failure in that run is separate from these visual deficiencies. PNGs are actual rendered evidence, but neither those images nor this repair are accepted release content.

## Root causes and corrections

1. CopyCluster only recentered world-baked meshes. Source mesas include very large talus skirts, and placing them at x≈48 did not make them small. CopySized now measures actual combined renderer world bounds, uniformly scales to an explicit maximum in metres, recenters and checks the result. Four distant mesas are bounded by 28×17×25 m, placed outside the open roadside basin; the original giant terrain/mesa instances are disabled only in the newly saved FirstStation copy.
2. The three regions previously shared the same block-row dressing. That routine is replaced with distinct structure:
   - FirstStation retains the full original station and forecourt, with a few restrained workshop props.
   - Scrapyard has corrugated stacked sorting containers, perimeter fencing, a visible gantry/hoist, gears on sorting pallets, drum groups and a working canopy around the power/coil area.
   - NightBeacon has an actual 10 m lattice tower, emissive lantern, relay shelter, solar collectors, warm route bollards and an open arrival arch.
3. FirstStation retained old ground/transparent sand/road-overlay geometry while a second road was drawn on top. Those obsolete instances are disabled in the candidate only. New ground/road materials use supported URP/Lit and existing sand/asphalt textures, with white texture tint (avoiding double-darkening). Source materials, shaders, importers and meshes are not edited. The source of purple must still be checked in the next actual render; the revision does not label it proven fixed in advance.
4. The reference has blue sky/cloud shapes and warm light, not a green procedural sunset. New sky materials reference the existing SoftDesertSky shader, with region-specific daylight/dust/night colors. No new shader file or change to the source shader is made.
5. Both new-region landmark images point back toward the spawn instead of the expected power cabinet. Immediate reading of newly created Collider.bounds without transform synchronization is a plausible binding failure. Solid/ExactSurface now explicitly synchronize before callers read world bounds. The clearance gate additionally rejects an interaction point detached from its actual surface. This diagnosis must be confirmed against next-run scene coordinates; it is not treated as measured certainty.
6. Moved copies no longer retain stale source lightmap indices/static flags. Only copies are changed.

## Executable geometry safeguards

CheckNewLayoutClearance runs during authoring and again while recapturing the saved Bootstrap+region. It checks both actual new renderer bounds and active collider bounds against:
- an 8.6 m wide road-core volume;
- vehicle spawn clearance;
- a dismount volume derived from the real retained entry step;
- the retained cabin workbench location;
- salvage/power standing areas and short approaches.

It separately rejects mesa skirts intruding into the open basin, or power/salvage markers disconnected from their exact surfaces. Ground-height surfaces, intentionally solid ramGate, the actual interaction surface/pickup visual and bound enemies are explicit exceptions; arbitrary new scenery is not exempt. This is a conservative static geometry gate, not a substitute for driving/walking/turning PlayMode validation.

New evidence files:
- JourneyEvidence/clearance-region-1.json
- JourneyEvidence/clearance-region-2.json
- JourneyEvidence/clearance-region-3.json

Schema remains `region`, `passed`, `checkedZones`, `distantMeshes` (four). These are candidate geometry evidence, not gameplay/visual acceptance. Exact permitted zone names are the common four plus applicable salvage-access/power-access and short-approach-Ram salvage interaction / short-approach-Coil interaction / short-approach-Power interaction.

## Camera comparison and protected scope

The overview, ground and cabin camera positions remain unchanged so the next PNGs expose the result at the same viewpoints. The previously wall-filled landmark pose now uses the actual surface and the approach toward the RV, at eye height. This change does not replace the unchanged player-ground image or the physical clearance checks.

All generated Unity asset names remain within the existing allowlist: four scenes, JourneyContent.asset, Region-[123]-Sky.mat, Layout-HEX.mat and metadata. No FBX, mesh asset, texture, source material, original scene or ProjectSettings is edited. Runtime ownership, missing-combat fail-closed policy and existing approval records are unchanged. The original RV/cabin models/materials/GUIDs are retained exactly.

## Verification status

Source lexical/contracts and preservation-of-helper diff checks were performed. No Unity editor, model renderer, C# compilation or device simulator was run here. No revision-2 PNGs exist yet. Before executing Actions, reconcile this source change with the package diagnostic update and refresh the complete source inventory. Review all 12 resulting PNGs and clearance evidence before accepting or further revising the environment.
