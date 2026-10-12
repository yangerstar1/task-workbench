# Lottery project progress

Updated: 2026-10-12 10:41 UTC

- G0: real Unity 6000.3.19f1 technical probe, six native EditMode tests and ARM64 Android build passed in run 38226292711. This is not the finished game.
- G1: rule specification and independent calibrated review passed. Accepted private candidate and bounded evidence are backed up in the authorized private repository.
- G2: one-ticket 3D scratch scene, transactional persistence, same-request FakeAd recovery, 38 Core EditMode cases and 8 graphical PlayMode cases are implemented as source candidates. Six G0 regression cases are retained.
- This checkpoint is WIP, uncompiled, and does not trigger CI. Independent source preflight is underway. No G2 native tests, rendered frames, APK, device checks or final-art acceptance are claimed.
- Source publication safety: an unused generated PlayStation credential field was detected before upload. Publication requires an empty field and fail-closed export screening. No credential value belongs in source or evidence exports.
- Normal first-day advertising remains disabled; ad eligibility tests use explicit synthetic fixtures. Cross-process first-launch elapsed timing is not yet implemented.
- Next: freeze reviewed sanitized source, start exact native EditMode/PlayMode and process-recovery checks, inspect actual rendered frames, then build the G2 Android technical slice.
