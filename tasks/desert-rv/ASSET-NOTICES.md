# Asset notices

## Project-authored content

The RV body, upgrade modules, cabin, station, props, collision meshes, materials, procedural/baked surface textures, shaders, and sound effects in this export are project-authored content. Source production records identify Blender procedural modeling and baking for the RV and station and synthesized original sound effects. The hand-painted sand albedo was generated for this project with an image-generation tool. No downloaded external vehicle or animal model is included.

These provenance statements do not imply that every candidate asset has received final visual acceptance. The source tree is a recovered development baseline.

## Noto Sans CJK SC

The exact font is preserved as `backup-assets/fonts/NotoSansCJKsc-Regular.otf.xz` and restored by the included checksum-verifying script. The restored bytes retain their embedded attribution and licensing metadata:

- Copyright: © 2014–2021 Adobe (http://www.adobe.com/).
- Noto is a trademark of Google Inc.
- License: SIL Open Font License 1.1.
- Full license: `unity/Assets/DesertRV/UI/Fonts/OFL.txt`.
- Restored font SHA-256: `a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b`.

No font glyphs or names were modified.

## Unity dependencies

Unity packages are declared by pinned versions in `unity/Packages/manifest.json` and `packages-lock.json` and are obtained from Unity's package registry. The Unity Editor and package distributions are not bundled in this export and retain their own applicable licenses.


## Environment V4 independent candidate (2026-10-09)

New scenery resources in `unity/Assets/DesertRV/Art/EnvironmentV4` are CC0 1.0. This addition does not change the original RV or any earlier resource's license. These files are candidates, not an assertion of visual acceptance.

- Poly Haven: aerial_sand (Rob Tuytel; 15 m), asphalt_02 (Rob Tuytel; 3 m), concrete_floor_worn_001 (Dimitrios Savva / Rico Cilliers; 3 m), rusty_metal_02 (Rob Tuytel; 1 m), sand_03 (Charlotte Baglioni; 2 m), painted_plaster_wall (Amal Kumar; 2 m), corrugated_iron_03 (Charlotte Baglioni; 2 m). Per-asset source: https://polyhaven.com/a/ followed by the exact asset ID. License: https://polyhaven.com/license and https://creativecommons.org/publicdomain/zero/1.0/. Commercial use, modification, and raw redistribution permitted; attribution voluntary.
- Kenney Factory Kit 3.0: https://kenney.nl/assets/factory-kit ; CC0 1.0. Seven original FBX files and the original atlas. The archive's original license is preserved at `EnvironmentV4/Factory/LICENSE.txt`.

`EnvironmentV4/asset-provenance.json` records every copied asset hash and the exact roughness-to-URP mask derivation. `art/environment-v4/upstream-download-evidence.json` retains verified original download identities, and `license-evidence.json` the license-page verification. No web preview image, Quaternius QAL resource, paywalled model, or unverified candidate is included.

Environment V4 R2 adds self-authored metric ground/vertex-opacity shader and procedural pump/yard geometry. No new third-party assets are introduced; the 29 CC0 binary asset files and their recorded source hashes are unchanged. See art/environment-v4/REVISION-R2.md.

### Diagnostic sand diffuse derivative

`Assets/DesertRV/Art/TerrainDiffuseCorrection/sand_03_diff_illumination_corrected_1k.png` is a CC0 derivative of Poly Haven `sand_03` by Charlotte Baglioni. Original: https://polyhaven.com/a/sand_03 ; license: https://polyhaven.com/license . It applies recorded linear-light low-frequency illumination correction while retaining the source grain and mean color. Original bytes, recipe, source/derived SHA256 and numerical checks are recorded in `art/environment-v4/diffuse-correction/derived-provenance.json`. It is pending native visual comparison, not production acceptance.
