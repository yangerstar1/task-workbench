# Lottery project progress

Updated: 2026-10-12 11:09 UTC

- G0: real Unity 6000.3.19f1 technical probe, six native EditMode tests and ARM64 Android build passed in run 38226292711. This is not the finished game.
- G1: rule specification and independent calibrated review passed. Accepted private candidate and bounded evidence are backed up in the authorized private repository.
- G2: one-ticket 3D scratch scene, transactional persistence, same-request FakeAd recovery, 39 Core EditMode cases and 8 graphical PlayMode cases are implemented as source candidates. Six G0 regression cases are retained.
- G2 native CI attempt 1 failed before native execution because sparse checkout omitted a legacy workflow; this was repaired and independently reproduced/retested. Attempt 2 passed all 85 Python helpers on GitHub, then failed the Linux/.NET process probe. Its exact exception was not exported; bounded diagnostics and a confirmed project-extension correction are being prepared. No Unity execution has started. No G2 native tests, rendered frames, APK, device checks or final-art acceptance are claimed.
- Source publication safety: an unused generated PlayStation credential field was detected before upload. Publication requires an empty field and fail-closed export screening. No credential value belongs in source or evidence exports.
- Normal first-day advertising remains disabled; ad eligibility tests use explicit synthetic fixtures. Cross-process first-launch elapsed timing is not yet implemented.
- Next: retry the reviewed process-probe repair with bounded failure diagnostics, then exact native EditMode/PlayMode, inspect actual rendered frames, and build the G2 Android technical slice.

## Actual native checkpoint

Run 38239514579, source 331f0cc94d2b65e646a8374351f287f3dacc0d19: 92 helper checks passed; 24 real Linux/.NET SIGKILL recovery fixtures passed on SDK8.0.425. Unity compiled and executed all45 EditMode cases:42 passed,3 failed,0 skipped. The3 corrupt/unknown-schema save cases exposed an uncaught InvalidDataException. Source mutation/export audit passed. PlayMode and Android were correctly blocked. A precise recovery exception-classification repair is underway; no G2 acceptance or game completion is claimed.
