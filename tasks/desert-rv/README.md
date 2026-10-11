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

## Local Pouncer ground-support candidate (2026-10-11)

This local repair candidate starts from published feedback source
`2915b8b1e5be8b800a3d71f186b5316a8f626bc8`. Native run `38099017094`
showed a Pouncer retaining foundation-root Y = -0.04 after walking onto the
road at +0.035. Its actual Walk→Windup paw correction exceeded the original
100 mm limit. This candidate is not yet compiled or accepted by native Unity.

`JourneyCandidateAssetIntegration.BindPouncerGroundSupport` explicitly binds the
region's existing, unique foundation and road BoxColliders and adds a support
component only to actual regional Pouncer instances. The production `WireRegion`
path uses that binder. Derived prepared scenes must call the same binder and
save/reload its references under a distinct new-source receipt. Original producer
scenes/receipts, imported prefabs and strict model captures remain historical
inputs; their earlier verdicts do not certify this runtime change.

The Pouncer root follows the highest actual finite support under its root and
complete selected paw geometry. Mixed road edges are never averaged, and props,
vehicles and other beasts are ineligible supports. Eligible support normals must
have Y >= 0.9, matching spawn authoring. A step/drop cannot exceed half the actual
capsule radius; unsupported edges stop movement. Rise, horizontal travel and fall
are separately capsule-swept and checked for penetration before a single root
commit. Original horizontal 40 mm collision look-ahead remains; vertical segments
use only their actual length plus 0.1 mm numeric tolerance. Walls, ceilings, props
and dynamic colliders still block the path.

The original paw constraint's pre-query sync is reused for stationary
reconciliation. Explicit movement queries synchronize first, and successful root
displacements synchronize the capsule afterward. Stationary sub-0.1 mm differences
write nothing and do not introduce an overlap rejection. Death retains the disabled
hurtbox and fixed corpse root while continuing original paw validation. Pauses and
the explicit failure-reset latch are preserved. Armored movement, animation/bones,
mesh/collider sizes, terrain and combat damage rules are unchanged; paw limits
remain 100 mm correction and 4 mm penetration. The original strict report schema
and 26-case inventory remain unchanged.

A separate native EditMode suite, `DesertRV.Tests.PouncerGroundSupportTests`, contains
13 cases for normal/low cadence, up/down and mixed finite support, gentle/steep
slopes, blocked rise, walls, invalid/dynamic/foreign support, unbound solid props,
physics synchronization, paused/stationary contact, death and reset. It reuses the
existing native skin fixture via a test-only friend assembly. Run this suite on the
approved GitHub Actions Unity path, followed by actual prepared-R3 Walk→Windup and
road-edge cases and the original continuous contact probe on explicitly overlaid
new source. No Unity installation/player execution was performed locally.

Support sampling uses exact mathematical vertical-ray intersections with two
cached oriented BoxCollider shapes, with no per-vertex physics queries. Current
source paws select 1,832 vertices (484/477/436/435). At the production 0.1 s dt cap,
a Pouncer attack moves at most 0.8 m: at most nine movement subsegments plus one
initial support sample, or 36,660 simple two-box intersections including the root.
The later stationary reconciliation adds 3,666; pre/post paw checks add at most
7,328, plus up to 3,664 if a failed correction is rolled back. At most 19 nonzero
path segments need a capsule cast and endpoint overlap per move in the worst case.
Zero-length points are discarded and collinear travel is merged, so ordinary flat
travel uses one complete cast, endpoint overlap and initial overlap while all
step/rise/fall corners remain. Stationary reconciliation needs no physics cast/overlap
unless support height changes. Query arrays and lists are reused after warm-up;
existing calibration and report allocations remain. Native timing/GC behavior is
still unmeasured. This repair does not establish a fix for vehicle-contact deadlock
or explain the older unidentified +0.5473 m support event.
