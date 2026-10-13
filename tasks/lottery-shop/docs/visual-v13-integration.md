# v1.3 visual candidate integration

Status: candidate for native Unity validation. Not a G3/G4 gate pass, art approval, or device-quality result.

## Frozen input and actual defect evidence

The complete 330-file v1.2 source was copied byte-for-byte before editing. The original tree was left intact. First Unity diagnostic run 38336234596 stopped in the capture prebuild because imported Anchor_ScratchTicket was (-2.05, .824, -.1), while the declared runtime coordinate was (+2.05, .824, -.1). The same run passed 287 EditMode cases; ordinary PlayMode passed 31/32, with the QA body-fit case failing.

## Repairs in this candidate

- The importer applies the declared, measured X-handedness correction once to both room and tool hierarchies. Reflected mesh triangles are reversed before combining; tangents are regenerated from the resulting mesh. No negative-scale generated prefab is used. Three independent FBX anchors must still match declared metres within the original 15 mm tolerance. Missing normalized room/tool resources now fail rather than displaying a mirrored source fallback.
- New art-v1.3 room FBX SHA256: `29a71f0dfaac26ab3409c42f3eeac60e20d334b255e01e23ba5f6b83670f427f`. Artist reports 558 source meshes / 67,858 triangles. These are authoring counts, not device performance measurements.
- Material factors are explicit per material. The new oak/green/plaster colours are baked and use their declared white factors; the importer does not globally invent white factors. Base UV scale and normal strength are consumed. Linear roughness is inverted into generated URP metallic-map alpha, with scalar smoothness retained for scalar-only materials. Glass keeps its declared alpha and casts no opaque shadow. Daytime window materials retain their authored factor.
- The ticket is 0.40 × 0.266667 m, with its top at y=.81825 and 0.24 mm stock resting on the felt at y=.818. The enlarged black backing box is removed. Ink/silver offsets are 0.06/0.12 mm. Both entire ticket display roots rotate 180° in-plane so the approved paper reads upright from the +Z seat. The original texture bytes, reviewed UVs, masked result data and scratch authority are unchanged.
- Seated camera is based on paper + (0,.725,.38) m, FOV 32°, with safe-area compensation. There is no new gameplay zoom mode. Tools use .55/.53/.55 of their original authored size and retain explicit current-ticket versus next-ticket configuration authority.
- In a mathematical pinhole check, 1280×720 paper bounds are approximately x330–994, y175–538; at the inset 1208×684 safe area they are x347–974, y185–529. All three tool renderer bounds remain in the safe viewport. This is projection evidence only, not a rendered Unity screenshot.
- A real tool-sample tray and price cards replace the counter-wide shop click identity. Runtime price labels use matching confirmed stock; unavailable samples say no stock. The obsolete counter interaction volume is removed, but the physical counter base still blocks walking. Normal fixture approach is (.045,0,-.45), targeting (.045,1.04,-1.765), above the bottom HUD.
- 起身/货架/收纳/手机 remain visible at the table. More is an actual input-routed local menu, with 购票/抽屉/账单/设置 behind it. The primary settlement action is distinguished at the bottom-right. Controls remain at least 96 reference pixels high and text 32 reference pixels, equivalent to the existing 720px/360dp design reference, not a physical-device measurement.
- The QA fit defect had a deterministic vertical cause: 14 × 24px lines with 1.16 line spacing required 385.92px but the original viewport provided 378px. QA now uses 10 measured-width wrapped lines at 32px and a 394px body viewport. Original full snapshot copy and read-only scrolling semantics remain intact.

## Exact presenter exception

Only two presentation-only edits to `G3Presenter.cs` were authorized:
1. `EvidencePageLines`: 14 → 10.
2. Diagnostic display wrapping calls `view.WrapEvidenceDisplayLines(evidence.DisplayText)` instead of the old fixed-column splitter.

No Core, Persistence or Ads source changed. No probability, money, persistence, challenge selection or 75-step business assertions were removed. Existing tests use genuine mouse/touch More navigation; no hidden button bypass was added.

## Native evidence requested

The capture receipt now records visible button IDs, More state, union opaque HUD area, paper/tool projections and actual room renderer/material counts. These values are observations, not automatic art-pass thresholds. Unity must still verify axis normalization, lighting/normal direction, upright paper, half-scratch, tool silhouettes, world price cards, physical interaction, QA fit and both landscape ratios. Audio is a separate unfinished checkpoint, not included in this visual freeze.
