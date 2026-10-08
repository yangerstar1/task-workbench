# Desert RV: restored Unity baseline

This is a public, independently exportable Unity source baseline, not a finished or accepted game. The export preserves the recovered RV and self-authored station assets, their Unity GUIDs, runtime scripts, and traversal scenes. Android compilation, device behavior, gameplay completeness, and visual quality require separate verification.

## Build layout

- Unity project: `unity/`
- Editor version: `6000.3.19f1` (revision `7689f4515d75`)
- Font preparation: run `python scripts/backup/restore_unity_font.py`, then run the same command with `--verify-only`.
- Android build entry point: `DesertRV.Editor.AndroidBuild.BuildTraversalHarness`, using Android as the active build target.
- The build entry point consumes the existing `TraversalHarness.unity`; it does not silently regenerate or author a replacement scene.
- Build output is under `build/android-traversal-harness/`. A fresh output directory is required. The APK and safe build receipt are separate from source provenance and verification evidence.

The controlled build and tests run in GitHub Actions. No Unity build was performed while preparing this source export. A successful build alone is not gameplay or visual acceptance.

## Provenance and exclusions

`PUBLIC-EXPORT.json` records the pinned source commit and the SHA-256, size, and Git blob hash of every exported payload file. It deliberately excludes itself; its hash is pinned by the import procedure. Revisions must update the manifest together with the affected files.

The export excludes the surrounding monorepo, reference images, internal handoff and conversation records, research/authoring studies, unknown-rights references, downloaded animal candidates, caches, logs, credentials, and compiled build products. Nonessential signing and account configuration was blanked in the public copy; Unity online reporting was disabled. The original source repository remains private.

Third-party font notices and asset provenance are in `ASSET-NOTICES.md`. Public availability does not grant a new blanket software or artwork license; existing rights and the font's OFL remain applicable.
