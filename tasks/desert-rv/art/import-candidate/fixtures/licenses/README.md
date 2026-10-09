# Licenses for the narrow official Unity test fixtures

These files accompany official source excerpts used solely to test this Unity
project's candidate-asset verification. They do not place Unity's work under the
repository's own license or grant unrestricted standalone reuse.

## Scope

- `../urp-17.3.0/Editor/AssetVersion.cs` and `.meta`,
  `../urp-17.3.0/Shaders/Lit.shader` and `.meta`, and `../urp-17.3-Lit.mat`
  are from `Unity-Technologies/Graphics`, `6000.3/staging`, package
  `com.unity.render-pipelines.universal`. The original package copyright and
  license notice are retained in `URP-LICENSE.md`.
- `../urp-17.3-CHNOS-Hex-Array.mat` is the unchanged official ShaderGraph terrain
  sample from `Packages/com.unity.shadergraph/Samples~/Terrain/Materials/CHNOS Hex Array.mat`.
  Its package copyright and license notice are retained in `ShaderGraph-LICENSE.md`.
  It is a negative parser fixture because it contains an additional HDRP document;
  the verifier must not accept that extra document as candidate metadata.
- `URP-Third-Party-Notices.md` preserves the original URP package notice. Its FXAA
  source component is not among the copied four-file snapshot or material fixtures.
- `Unity-Companion-License-v1.4.txt` is the complete official current license text
  linked by those package notices, retrieved 2026-10-09. Website navigation is
  excluded; only hyperlink expansion and whitespace were normalized. Original
  package notices are copied without edits. Source locations are in `sources.json`.

The Unity Companion License permits use in connection with authoring/distribution
under a valid Unity Engine License and requires the accompanying license/copyright
notices. These fixtures remain within this existing Unity-dependent project. No
competing engine/tool use or blanket public-domain/MIT grant is claimed.

These license/notice files are repository-side test-fixture documentation. They
are not extra inputs to the runtime private package snapshot, whose exact four
file identities and SHA-256 values remain unchanged, and that private snapshot is
not published by the safe-export artifact pipeline.
