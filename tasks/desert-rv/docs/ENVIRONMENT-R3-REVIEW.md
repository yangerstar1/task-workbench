# Environment revision 3 — still unrendered/unaccepted

Source base: published revision-2 JourneySceneAuthoring.cs SHA256 `ce986331d323a478d6977efce9b2c611a8c9da83567671807c264327c2a3d37b`. The concurrent supply-fixture/package-validator changes do not modify this file. Integrate this candidate on current main rather than replacing unrelated newer work.

All twelve actual revision-2 PNGs from run 37819991994 were inspected. R2 fixed the giant foreground mesas, purple road fringes, black ground and misplaced cabinet view; its three clearance reports passed. Those fixes are retained. It still shows a finite rectangular ground plane, abrupt road ends, brown uniform texture, very sparse new-region planting, a rectangular orange gate, an underdressed sorting yard and minimally recognizable signal equipment. The three cabin views remain intact and are not reauthored. The approved reference itself is not included in this package.

## Bounded changes

- Reuse the existing self-authored hand-painted sand texture with supported candidate-only URP/Lit material. No new texture, shader, source material mutation or importer change. Increase visual ground extent beyond the 450 m camera far plane while compensating the BoxCollider's local size so physical ground remains exactly 230×310 m. Push neutralized fog beyond the nearby playable area rather than washing foreground colors away.
- Extend road appearance beyond the unchanged playable region into full fog. The two extensions have no collider. Exit/safe-zone locations, world-progress offsets, speed, timer, encounter count and supply slots are unchanged. Low irregular sand lobes cover selected road shoulders.
- Extract plants by actual spatial adjacency around existing mesh seeds, not by unrelated name suffixes. Normalize real world bounds, reject collapsed plant dimensions, group small/middle stones and cacti while preserving the open corridor and dismount/interaction clearances. Four remote mesas remain.
- Replace the orange gate renderer with supported metal panels, braces, feet, hazard strips and fasteners, plus a separate fallen-panel assembly. The original authoritative collider's size/position remains unchanged. A new tiny presentation component observes its enabled state; it does not grant gate progress or damage anything.
- Add a grouped self-authored tire pile, stripped steel chassis with reused tire mesh, dismantled sheet metal, an engine/radiator impression, a gear worktable and source-mesh oil marks to the existing scrapyard layout. These are decoration, not additional supply rewards or new mandatory objectives. Accepted RV source meshes/materials are reused read-only; its live vehicle and cabin are unchanged.
- Add a reflector/feed to the existing lattice beacon, relay equipment/vents, visible conduits and ground cables, warm task-light fixture, cabinet gauges/handle/vents and evacuation chevrons. Preserve current tower, shelter, lights, route and safe-zone collider.

No approved RV asset, source scene/meta, renderer settings asset or ProjectSettings is edited. Existing nested finally, RenderTexture lifetime accounting, package/source diagnostic protection and no-overwrite behavior are retained. All generated scene/material filenames still fit the prior exact allowlist.

## New gate presentation: authority boundary

`JourneyRamGateVisual` reads `gate.enabled` only. It toggles two decoration-only children. Validation rejects null/equal/ancestor roots, roots with colliders or MonoBehaviour business scripts, and any root that contains the gate collider. It never disables the parent carrying the collider/script and never writes Collider.enabled, GateOpen, health, damage or vehicle speed. Empty references leave visuals unchanged rather than inventing a successful break. Re-enabling rereads the real collider; a freshly loaded scene uses its intact default state.

Four new EditMode NUnit fullnames (authored, NOT RUN):
- DesertRV.Tests.JourneyRamGateVisualTests.ColliderStateChangesOnlyDecoration
- DesertRV.Tests.JourneyRamGateVisualTests.DisableReenableAndResetRereadRealCollider
- DesertRV.Tests.JourneyRamGateVisualTests.MissingColliderCannotPretendGateBroke
- DesertRV.Tests.JourneyRamGateVisualTests.BusinessParentAndPhysicalChildrenAreRejected

These tests explicitly invoke the Unity callback methods in EditMode and test real GameObject/Collider fields. They do not claim a live Director ram collision or PlayMode traversal. The latter must still be captured in actual Actions testing.

## Eighteen editor renders, not gameplay proof

Original `overview`, `ground`, `landmark`, `cabin` views remain unchanged. Add two views per region:
- `motor-driving-editor`: JourneyMotor.LateUpdate parameters, FOV 44°, camera pitch 74°, distance 26 m, center RV+1.3 m up+2.2 m forward.
- `motor-walking-editor`: exact authored dismount point formula and 1.52 m eye offset, FOV 66°, zero pitch and a legal forward look after dismount. This is not a simulated input sequence or a claim that the motor was running.

Filenames: `{FirstStation,Scrapyard,NightBeacon}-{motor-driving-editor,motor-walking-editor}.png`. All remain 1440×900. New per-image fields: `cameraModel` (`regression-editor`, `JourneyMotor-driving-editor`, `JourneyMotor-walking-editor`) and `fieldOfView` (54/58/58/68 for original views; 44/66 for new views). The top-level receipt still says environment-only/not-gameplay-acceptance. Three scene-buffer checks and explicit buffer-release accounting remain unchanged. The exact validator names/count and unique native render test name must match these eighteen editor renders; they are not PlayMode proof.

## Verification and remaining risks

Only source lexical/contract/GUID checks were done here; no local Unity or Blender ran. No R3 screenshots exist yet. The new plant extraction may reveal a legitimate source-mesh grouping or clearance failure in the actual editor; it must fail visibly, not be silently skipped. The tire/chassis/signal details and lighter sand are candidates until the next images are judged against the reference at the preserved viewpoints and actual Motor-parameter editor views. Rendering success and clearance success do not establish reference-quality art, complete combat or a good full game.
