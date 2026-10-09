# Fixed-camera sand channel diagnosis

Production reference: R3 commit `120f6d6f0d34dbe432854c31ae91945ccd8496ab`, actual Unity run `37961223152`. Its twenty frames restored continuous Lit dune shape and shadow contact, but all three overview frames still showed obvious sand repetition. This is a visual failure despite passing native authoring. Pump detail, softened oil, original RV, yard structures and the tower light improvement are retained.

Read-only source analysis found the original `sand_03` diffuse has low-frequency brightness variation inside each 2 m tile: the two axis fundamental amplitudes are approximately 4% of mean linear luminance. A 32-by-32 box reduction retains about 16% P5–P95 luminance span. Opposite-edge differences are comparable to ordinary adjacent pixel differences, so an exceptional texture seam was not found. Actual R3 material serialization binds the expected diffuse and normal maps, scale 1/offset 0, normal strength 0.035, metallic zero and scalar smoothness 0.04. No roughness or occlusion texture participates. These observations make diffuse repetition the leading hypothesis, not a substitute for native channel ablation.

## Fixed eight captures

The new, separate EditorTerrainProbeTests assembly has one test and a 600000 ms limit. It authors the unchanged R3 environment, runs the original candidate-layout and clearance gates, then captures only the original Scrapyard overview and ground camera poses, each under four fixed states:

1. `original`: unchanged standard Lit diffuse and weak normal.
2. `normal-off`: original diffuse; normal keyword disabled, normal map cleared and scale zero.
3. `diffuse-flat`: original weak normal; diffuse replaced by one constant pixel with the source's average linear color.
4. `diffuse-flat-normal-off`: constant diffuse and normal disabled.

The diffuse source is decoded sRGB to linear before averaging each channel. Linear RGB mean is approximately (0.150479870, 0.117845279, 0.078111876). Encoding that mean back to sRGB and rounding gives (108, 96, 79). The one-pixel in-memory sRGB texture uses those bytes. The original material base tint remains unchanged. An offline histogram test recomputes this constant from the exact verified JPEG.

Only temporary material clones are bound. Native assertions verify the clones' actual shader, map/keyword state, normal strength, base tint, smoothness and metallic before drawing. Lights, fog, exposure, geometry, camera poses and all original source materials are not edited. The original saved scenes and two generated terrain material files are byte-compared after cleanup. This diagnostic never saves its flat materials as assets.

The evidence wrapper exports exactly eight PNGs, one sanitized receipt and one SHA manifest. It requires the unique native diagnostic case to pass, the exact eight camera/channel records, actual OpenGLCore/llvmpipe, original layout/clearance, tracked-source preservation and explicit scene/material-byte preservation. Failure does not produce an accepted partial set. The existing production twenty-camera test, wrapper, generated contract and all 29 CC0 source binaries remain unchanged.

Flat-color images are diagnostic controls, not finished art. Any selected correction needs its own original twenty-view review. No visual acceptance, integrated gameplay, Android performance or shipping approval is claimed here.
