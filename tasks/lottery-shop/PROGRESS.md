# Lottery project progress

Updated: 2026-10-12 12:19 UTC

## Current verified status

- G0: real Unity6000.3.19f1 technical probe, six native EditMode tests and ARM64 Android build passed in run38226292711. This was a capability probe, not the finished game.
- G1: rule specification and independent calibrated review passed. Accepted private candidate and bounded evidence are backed up in the authorized private repository.
- G2: one-ticket 3D scratch scene, transactional persistence and same-request FakeAd recovery are implemented. No G2 gate acceptance or finished-game claim yet.
- Current actual run38241168487, source2b62b4769a02ca00d528b27b3ffcf7e227b6b7c1: Python helpers and Linux/.NET process-recovery step passed. Unity EditMode, exact45-case validation and source audit passed. That run later hit its30-minute job timeout in PlayMode; no Play XML or frames were produced.
- The previous actual run38239514579 passed24 Linux/.NET SIGKILL cases, but Unity reported42/45 PASS and3 corrupt/unknown-schema recovery failures. An explicit InvalidDataException classification fixed that defect without removing tests. The original failure evidence is saved in the private repository at c411cfa1eb66b326feb071aa933b91261d13babf.
- Earlier CI defects (missing sparse-checkout input, wrong C# project extension) were fixed. Bounded diagnostics now preserve error identities without raw log or credential export.

## Scope limits

- Normal first-day advertising is disabled. Eligibility and delayed callback tests use explicit synthetic fixtures; recovery querying is manual. Persistent first-launch elapsed timing remains unimplemented.
- Android force-stop, real-device input/performance, real ad SDK, final art and full-game progression have not passed.
- The unused PlayStation credential field is blank; pre-publication and post-Unity export checks reject nonempty credential fields.
- Next: inspect real PlayMode results and original rendered frames, repair if necessary, then build and independently review the Android technical slice.

## Latest actual run and repair candidate

Run38244728404/source731e97ad8ffabb398ff37bf3a6d806ce331791bc: 45/45 Edit and24 process-recovery cases passed again. After a fixture lifecycle repair, all8 Play tests completed promptly:1 passed and7 failed. Buy input did not create a ticket, causing downstream failures; a focused input/focus/layout repair and stronger non-vacuous prerequisites are being reviewed. No graphics acceptance or Android build is claimed.

Post-Play source screening blocked a nonempty credential setting before any Play settings/archive content was exported. The next candidate introduces explicit, narrowly scoped unused-platform-setting normalization, with baseline/operation/hash provenance and NORMALIZED_NOT_RAW labeling. Other credentials still block export; the identity of the previous nonempty field has not been established from the withheld output.

Run05 actual evidence is safely backed up in the private repository at6bd018ae7121ab45f2f31590751000a745bee57d. Native retry remains pending independent review and source checkpoint.

Run06 38246742337/source181a574d685cb8c39383d9f16777ab770d263cc8:45/45 Edit and24 process cases passed; all8 Play cases failed at a newly strengthened mouse press-edge prerequisite (pressed state true, edge false). Both source audits passed. Play settings normalization actually identified ps4Passcode, recorded changed=true, restored the exact empty baseline and exported NORMALIZED_NOT_RAW with receipts. Actual evidence22files saved privately at87b542873557baee081632e457bd56814b480eed. An official Input System1.20.1 Editor-background input-buffer fixture correction is being reviewed; no Play gate success yet.
