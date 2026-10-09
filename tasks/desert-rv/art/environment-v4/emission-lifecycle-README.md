# Warm beacon emission lifecycle candidate

This producer retains the original twenty-camera environment test, all existing terrain/RV/road gates, the R4 corrected-sand proof and the freeze/postcapture/postexit audit. It additionally corrects the authored GI mode of exactly one generated material, `Assets/DesertRV/Scenes/Journey/Layout-FFC261.mat`, to `BakedEmissive` while preserving its original nonzero HDR emission color.

`BakedEmissive` is a real material-authoring intent: this surface is eligible to contribute to a future GI bake. This fix invokes no bake and changes no Light, LightingSettings or existing baked data. It is not a global material-normalization pass and does not turn emission off to hide instability.

A successful downloaded package is self-described by `emission-proof.json`. Its producer revision is `SINGLE_BEACON_EMISSION_LIFECYCLE_R1`. The unchanged `receipt.json` still carries historical `candidateRevision: R4_DIFFUSE_ONLY`; that field describes only its two generated sand-material subproofs. It does not describe every change in the whole package. The additional proof explicitly records this distinction and binds the original receipt hash.

The additional host gate accepts exactly the original Passed NUnit render case and its three bounded native JSON markers. It requires the real installed Lit validator, two stable save/import cycles, original HDR preserved, emission keyword enabled, clean scene observations, matching material and metadata hashes in all three phases, and matching typed serialized material values. Scene restoration may unload the target before an audit snapshot; a genuine zero-object snapshot is retained as zero, while both scene observations must have a loaded target and all actually audited target objects must be clean.

Only the fixed `emission-proof.json` is added to the old successful artifact closure. Raw native XML, logs and internal audit copies are not exported. The old strict gates and receipt bytes remain unchanged. If any additional proof or readback check fails, no final strict package is published; the existing failure diagnostic can still preserve the original twenty images and honest phase availability.

Host package entry: `python scripts/environment_emission_lifecycle_evidence.py package`. The existing audit diagnostic entry remains valid. `validate_exported_proof(stage)` verifies an extracted successful bundle without reading the original native XML/project or run environment. Initial production packaging still requires the original native XML and complete three-phase evidence.

Offline Python fixtures verify parsers and failure behavior only. They are not Unity compilation, native rendering, finished art, gameplay acceptance or a successful production package. Dune intersection seams remain outside this correction.
