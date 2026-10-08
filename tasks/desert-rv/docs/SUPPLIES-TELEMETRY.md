# Optional supplies and pacing observations

This source increment adds optional scene-bound supplies and read-only pacing diagnostics. Existing scene supply arrays default empty; no supply assets, placement, art approval, gameplay duration, or release APK is established by this change.

A supply is one-use per journey, requires current region/generation and an on-foot, unpaused interaction within 2.2 m with an unobstructed world ray. Optional nonempty choice groups allow only one successful reward across that journey. A loaded but inactive previous region is rejected. Restart clears reward/choice facts; region transitions preserve them.

Ammo caches grant at most 24 reserve rounds, capped at 144 reserve; repair caches grant one kit, capped at three. Full capacity gives a clear notice and retains both cache and choice. Original starting inventory, loaded magazine, damage, repair, firing and storm rules are unchanged. Supplies cannot be taken during reload or installation; prompts explain that collection is available afterward. This protects the existing authoritative reload count snapshot and audio/visual lifecycle.

Pacing observations are scoped to the current SessionState/generation, deduplicate supply/shot events, and never advance a clock or mutate gameplay. Stationary empty-powered-wait observations exclude movement, nearby live threats and busy actions. Threat range is not a line-of-sight proof. Health observations are sampled net declines, not gross or terminal damage; the existing lethal-storm early return remains unchanged. Event-only rows use a presence flag instead of an infinite storm margin. No complete-run file export is added.

The strict EditMode inventory is 116 cases (89 existing plus 27 new supply/interaction/telemetry cases); PlayMode remains six. Source checks do not certify native execution. Exact-commit Actions results and uploaded NUnit XML must establish test status. No APK is requested by the checks-only verification workflow.
