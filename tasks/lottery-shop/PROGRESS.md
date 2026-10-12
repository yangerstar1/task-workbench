# Lottery project progress

Updated: 2026-10-12 11:23 UTC

## Current verified status

- G0: real Unity6000.3.19f1 technical probe, six native EditMode tests and ARM64 Android build passed in run38226292711. This was a capability probe, not the finished game.
- G1: rule specification and independent calibrated review passed. Accepted private candidate and bounded evidence are backed up in the authorized private repository.
- G2: one-ticket 3D scratch scene, transactional persistence and same-request FakeAd recovery are implemented. No G2 gate acceptance or finished-game claim yet.
- Current actual run38241168487, source2b62b4769a02ca00d528b27b3ffcf7e227b6b7c1: Python helpers and Linux/.NET process-recovery step passed. Unity EditMode, exact45-case validation and source audit passed. Graphical PlayMode is running; its eight tests, four rendered frames and Android build are not yet verified.
- The previous actual run38239514579 passed24 Linux/.NET SIGKILL cases, but Unity reported42/45 PASS and3 corrupt/unknown-schema recovery failures. An explicit InvalidDataException classification fixed that defect without removing tests. The original failure evidence is saved in the private repository at c411cfa1eb66b326feb071aa933b91261d13babf.
- Earlier CI defects (missing sparse-checkout input, wrong C# project extension) were fixed. Bounded diagnostics now preserve error identities without raw log or credential export.

## Scope limits

- Normal first-day advertising is disabled. Eligibility and delayed callback tests use explicit synthetic fixtures; recovery querying is manual. Persistent first-launch elapsed timing remains unimplemented.
- Android force-stop, real-device input/performance, real ad SDK, final art and full-game progression have not passed.
- The unused PlayStation credential field is blank; pre-publication and post-Unity export checks reject nonempty credential fields.
- Next: inspect real PlayMode results and original rendered frames, repair if necessary, then build and independently review the Android technical slice.
