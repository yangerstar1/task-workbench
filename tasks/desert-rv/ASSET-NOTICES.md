# Asset notices

## Project-authored content

The RV body, upgrade modules, cabin, station, props, collision meshes, materials, procedural/baked surface textures, shaders, and sound effects in this export are project-authored content. Source production records identify Blender procedural modeling and baking for the RV and station and synthesized original sound effects. The hand-painted sand albedo was generated for this project with an image-generation tool. No downloaded external vehicle or animal model is included.

These provenance statements do not imply that every candidate asset has received final visual acceptance. The source tree is a recovered development baseline.

## Surface art candidate: sand and asphalt

The surface-only candidate reuses existing, byte-verified Poly Haven textures under
CC0 1.0: `sand_03` by Charlotte Baglioni (https://polyhaven.com/a/sand_03) and
`asphalt_02` by Rob Tuytel (https://polyhaven.com/a/asphalt_02).
License: https://polyhaven.com/license and https://creativecommons.org/publicdomain/zero/1.0/.
The original diffuse JPGs are retained unchanged. The separate illumination-corrected
sand PNG is an existing derivative of `sand_03`; its original/derived hashes and
historical recipe are recorded in `art/journey-preparation/surface-art-provenance.json`.
No new asset download, external model, historical environment authoring code or
visual-acceptance claim is part of this candidate.

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
