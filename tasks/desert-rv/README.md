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

`PUBLIC-EXPORT.json` records the pinned source commit and the SHA-256, size, and Git blob hash of every exported payload file. It deliberately excludes itself; its hash is pinned by the import procedure. This manifest is immutable historical provenance for the initial 803-file export. It must not be rewritten to imply later game changes came from that private source commit.

`SOURCE-STATE.json` records the current reviewed source bytes, explicitly linked to the historical export manifest hash and public baseline commit `6dc675517db262c72dcb8c1507239d4bf10acc5d`. It covers the entire Unity project, deterministic font restoration inputs, CI scripts and workflow. New unlisted source fails preflight. Regenerate it with `python scripts/update_source_state.py` on a clean source checkout, then review the diff. It excludes itself to avoid self-hashing; the native run receipt binds the actual GitHub commit and the independent evidence records this source-state hash.

The current candidate adds journey/combat rules and director integration. It has 71 reviewed EditMode cases and one separate PlayMode case awaiting Unity execution. The prior baseline passed 34 EditMode cases in run 37796490106, attempt 1; this does not certify the new source. Three authored, accepted region scenes and finished combat assets are still absent, and the Android entry point remains the saved TraversalHarness.

The export excludes the surrounding monorepo, reference images, internal handoff and conversation records, research/authoring studies, unknown-rights references, downloaded animal candidates, caches, logs, credentials, and compiled build products. Nonessential signing and account configuration was blanked in the public copy; Unity online reporting was disabled. The original source repository remains private.

Third-party font notices and asset provenance are in `ASSET-NOTICES.md`. Public availability does not grant a new blanket software or artwork license; existing rights and the font's OFL remain applicable.

## Local combat feedback candidate (2026-10-10)

This patch is prepared against published source `9dd81678b649ac7a13eb7e47354afeaf62acf323`
(player run `38070456519`). It has not been published, compiled, built or played.

- Actual beast/vehicle contacts show a brief camera-relative direction and the actual
  player/vehicle health lost. Nondirectional health loss keeps a generic damage cue.
- A rear warning exists only for a live current-region enemy in an attacking or
  approaching phase, behind the camera, inside its existing attack range, with a
  clear attack line. It clears when those conditions end.
- Repair explains that it restores vehicle health only, and reports the capped gain.
- Driver prompts and failure messages use the same existing cable, distance and
  line-of-sight gate as entry. Disconnect explains paused charging and surviving enemies.

Damage values, health/repair limits, speed, collision, reach, wave and charge rules
are unchanged. Seven new `JourneyCombatFeedbackTests` cases are registered in the
existing EditMode inventory (210 total); they still require native Unity execution.
The existing source/evidence verifier tests pass (50), as do workbench tests (32).
Source inventory verification passes. Those host checks do not certify compilation,
physics behavior, font layout or gameplay. Next verification must run the native
cases and check ordinary play: real contacts from four directions; rear-threat
appear/disappear through turn, cover, death, pause and region/restart; near-cap repair;
cable/blocked-door rejection and successful re-entry; and unplugged active waves.
