# Lottery project progress

Updated: 2026-10-12 22:39 UTC

## Current status

G3 native tests and the cold Android APK passed independent build verification in run38312982947. APK SHA256: c2be0b3bbaf11fe6f28a3f45246591b6d694d0d5d2e6ff40faa8217c4ad98d93. Physical-device acceptance is NOT_RUN; G3/G4 gates remain unpassed. See the latest dated entry below.

## Previously accepted G2 technical stage

G2 technical stage has passed independent review and durable evidence verification. This is a one-ticket graybox capability stage, not final game or visual-quality acceptance.

- Accepted source: `06814f520041676a50601f4e70d5ee09eae10078`.
- Actual run: [38256015857](https://github.com/yangerstar1/task-workbench/actions/runs/38256015857).
- Native results: 45 EditMode, 8 PlayMode, 25 actual Linux/.NET SIGKILL cases; zero failed/skipped native cases.
- Four original state-bound URP frames independently inspected. Output uses an actual 1280 x 720 presentation target. The 640 x 480 Editor environment remains separately recorded. Aspect distortion and clipped decorative sign were corrected.
- Independent cold ARM64 IL2CPP development APK: 49,628,694 bytes; SHA-256 `6e7e8cee8e465ed7ca19d9c35586ca2cc9193d2fc3dc24ff2809be75e007d128`; binary Android versionCode 2 verified.
- APK saved durably and downloaded again with the same byte hash. Original tests, build/source evidence and independent reports are saved separately. Unity-regenerated settings explicitly retain NORMALIZED_NOT_RAW provenance.
- Physical Android touch, install/upgrade/force-stop/performance, real ad SDK and final T/V/P have not passed. G2 does not waive any of these later requirements.

## G3 implementation starting point (historical 14:35 UTC)

G3 is the complete first-day functional slice: both tickets, initially offerable tools and upgrades, consumables, current/next configuration, shared physical/quick shopping, phone borrowing/repayment, closing and first-night interest. The core, shop/ticket presentation and verification pipeline are being implemented in parallel in an isolated worktree.

Two original generated flat ticket artworks are approved and saved in this source branch, with matching importer metadata. They are printed background assets only: numbers, awards, scratch layers and state labels must be driven by confirmed runtime data. The previous whole-scene visual concepts were rejected and are not used. Approved art does not establish successful Unity integration or final visual quality.

G3 has not been compiled, built, device-tested or accepted yet. Its legal diagnostic day scenario is preparation material, not a claim of normal player execution. G4 remains blocked until the same-build G3 six-action physical-device gate passes. No whole-game or release candidate is claimed.

## Preserved repair history

- Runs 38238410614 and 38238794780: sparse-checkout and C# project-extension startup defects; corrected with bounded diagnostics.
- Run 38239514579: 42/45 EditMode; corrupt/unknown-schema exception classification repaired without removing cases.
- Run 38241168487: Edit/process passed, Play timed out; no Play frames claimed.
- Runs 38244728404 and 38246742337: actual input-fixture failures; corrected against Input System player/manual buffers. Unsafe generated settings were withheld until explicit narrow normalization and source audit existed.
- Run 38248877036: 45/8/24 plus Android passed; independent review still found viewport distortion, missing ad-waiting SIGKILL and binary versionCode mismatch. It was not promoted as overall G2.
- Run 38254407558: 45 Edit and 25 SIGKILL passed; Play 6/8 failed because the new fixture raycast before the ticket existed. Android skipped. The assertions were retained and moved after actual purchase, with added pre-purchase negative checks.
- Run 38256015857: corrected native run and APK, independent review and durable closeout completed. Earlier candidates/evidence remain immutable.

## G3 WIP checkpoint 001

Saved at 2026-10-12 14:45 UTC. Partial uncompiled source only, no CI request or playable-G3 claim. Core/persistence/FakeAd structures and their draft tests, the verification scaffold, approved art and partial presentation are checkpointed. The scene view, input/bootstrap wiring, final exact test identities, native compilation and real execution are unfinished. Existing G2 source and evidence remain unchanged. Local helper results (108 baseline plus 17 G3 synthetic checks) are not C# or Unity results.

## G3 source candidate 001

Prepared at 2026-10-12 15:07 UTC for independent source preflight. First-day service/store, all initially offerable tools and consumables, shop/input/paper rendering, 225 authored EditMode cases, 12 authored PlayMode cases and 14 planned original captures are now present. Counts describe source identities, not passing execution. The captures use disclosed diagnostic fixtures; they are not physical-device or exact 75-step UI evidence. Native C# compilation, Unity execution, G3 process kills, APK and six-action physical-device acceptance remain NOT_RUN. No actual G3 request has been created.

## G3 source candidate 002 repair checkpoint

2026-10-12 15:42 UTC. Independent candidate001 source preflight rejected six major gaps before CI: current/next tool presentation, supported diagnostic entry and exact UI trace, cancellable boost preselection, ordinary uninjected startup coverage, unreviewed executable build inputs, and G3 ad-waiting process-kill coverage. Candidate001 remains failed and preserved. Repairs add persisted slot/run identity, schema2 fail-closed recovery, explicit first-save normal/QA entry, exact scenario input trace, visible cell numbering, cancellation/resume coverage, complete reviewed-tree locking and a G3 waiting-state kill probe. Authored identities now236 Edit and18 Play; native discovery and all G3 native/device results remain NOT_RUN. Candidate002 requires independent re-review before any request.

## G3 first native request and candidate005

2026-10-12 16:10 UTC. Candidate004 passed independent source preflight only. Request01 run38275073822 (commit15f3d2aaf146c3e7e5f7fb7c91bec484d107ac7b) passed its guard and108 existing Python checks but failed one of42 G3 helper checks: an authoring-manifest test incorrectly inspected the runner after guard had created its legitimate evidence. All .NET/Unity/Android stages were skipped; no native result or APK exists for G3. Candidate005 isolates that helper fixture and adds a real temporary-Git guard-then-entire-helper-suite regression without loosening production input checks. Request02 remains untriggered until its own independent source review.

## G3 request02 and candidate006

2026-10-12 16:29 UTC. Request02 run38276542600 passed the guard and108+43 helper checks, then failed before the existing process suite produced evidence. Unity and Android were skipped. Independent local reproduction identified Python import-time bytecode created before the process entry disabled caching; the strict input check correctly rejected that new file. Candidate006 disables bytecode before project imports and adds complete separate-process CLI sequencing without allowing cached input. The local SDK-inventory stub checks Python routing only and executes no .NET code. Native verification remains pending independent review and request03.

## G3 request03 actual native results and candidate007 preparation

2026-10-12 17:09 UTC. Run38278840035 at473176f3e3ce26cddc31966695a10eed4d82d512 completed native tests: existing45 Edit/8 Play, new236 Edit/18 Play, existing25 and new37 actual Linux process-kill cases, all passed with original evidence. Four baseline frames and14 G3 frames were saved. The independent cold Android job failed in approved-artwork source/import validation before producing an APK; source audit passed. The compound check did not identify which import property failed, so the missing platform settings remain a supported hypothesis, not proven sole cause. Candidate007 is preparing explicit default/Android uncompressed original-size import metadata, granular bounded validation, and a development-only read-only device evidence view. The latter is needed to collect required IDs/hashes/ledger without exposing unrevealed results. No native pass transfers to those new changes; no physical-device/final-quality/G3 gate pass is claimed.

## G3 request04 actual results and candidate008 preparation

2026-10-12 18:24 UTC. Run38283877042 at685320b55dbcf9cea7532c09135be919900d7338 passed baseline45 Edit/8 Play, G3 242 Edit/24 Play, and25+37 actual process-kill cases. Its cold Android Unity build step succeeded, but APK verification, source audit and diagnostic preparation each rejected UNSAFE_FILE_TYPE_OR_ALIAS. There are zero Android artifacts and no verified recoverable G3 APK; the offending path and type remain unknown. Candidate008 adds bounded error classification and narrowly permits fully accounted internal Library hardlink groups only at the three post-Android stages with matching cold-start evidence. Source, output, cross-boundary links and unproved aliases remain rejected. Local108+58 helper methods passed; native results do not transfer to candidate008 until its own run. G3 physical-device and final-quality gates remain NOT_RUN; G4 remains blocked.

## G3 request05 and candidate009 diagnostic-only preparation

2026-10-12 19:44 UTC. Run38292246641 at acbac91770fee44aa406660d44057d819af6e5f7 again passed exact native tests and process suites. Its Unity Android build step succeeded, but all three post-build checks rejected the same OTHER_CHECKOUT regular file with link count2 (relative-path SHA256 fa14f161227dcfbb4b38d856921acff371fb120e2bdcbe617293df6462dc72c7). The concrete path and second link remain unknown; this does not establish request04's cause. No Android artifact or verified G3 APK exists. Candidate009 adds a separately bounded, metadata-only diagnostic collector; it does not expand accepted source/cache/output scope or turn a rejected build into a pass. Local helpers report108+58+42 passed, with one real Unix-socket case explicitly skipped due to this environment's PermissionError; the synthetic socket branch is separate. Full GitHub execution and independent review remain required. Physical-device and G3/G4 gates remain unpassed.

## G3 candidate009 rejected; candidate010 repairs prepared

2026-10-12 20:02 UTC. Independent source review rejected009 before any native request: Git object replacement could change the diagnostic script selected by commit, output-directory anchors could drift before publication, and two timeout boundaries were incomplete. Candidate010 isolates Git resolution, verifies both fixed blob identity and SHA-256 before executing diagnostics, rechecks original output anchors, and bounds the complete acquisition/execution and both scans. Local108+63+58 helper tests passed; one real socket test remains explicitly skipped locally. This only repairs diagnostic reliability and does not change production acceptance scope. Request06 has not been triggered. No G3 APK or physical-device/G3/G4 acceptance is claimed.

## G3 request07 diagnosis and candidate011 preparation

2026-10-12 21:14 UTC. Run38302759586 at9d32e0e86c6428a90e1dc869fa2dc4ace3ddaae2 passed all native tests,62 real process kills and230 Python helpers with zero skips, including the real socket case. Android Unity build succeeded; three post-build checks still failed. The new diagnostic-only artifact reports two complete stable metadata traversals and exactly one two-member hardlink group. Independent path hashing identifies the refused path as unity/.utmp/tools/debug/arm64-v8a/compile_commands.json; the second member is under .utmp/Debug with an unknown configuration segment. File contents and actual creator remain unverified; no prior-run cause is inferred. There is one Android diagnostic artifact and no verified APK. Candidate011 prepares an exact cold-created .utmp temporary-tree policy at only the three post-Android checks, with independent inode groups per Library/.utmp root, strict cross-root rejection and no inclusion of .utmp in published artifacts. Source review and native rerun remain pending. G3 physical-device/final-quality and G4 gates remain unpassed.

## G3 candidate011 rejected; candidate012 first-observation repair

2026-10-12 21:34 UTC. Independent preflight rejected011 before request08: registration of the second cold-cache root overwrote the initial stamp for shared ancestors. A deterministic temporary-Git reproduction replaced the Unity parent between registrations and was incorrectly accepted, including a source-drift variant. Candidate012 retains the first observation and rejects any later mismatch, in addition to the final directory check. No frozen011 file or previous evidence is changed; request08 remains untriggered and review09 is pending. The exact cold .utmp scope is otherwise unchanged. Native/Android execution for012 and all physical-device/G3/G4 acceptance remain pending.

## G3 request09 actual build verified; physical gate still blocked

2026-10-12 22:39 UTC. Run38312982947 at51f535247689f43d5470848a54f5abcf1062b609 completed SUCCESS. Independent actual audit confirms baseline45 Edit/8 Play, G3 242 Edit/24 Play,25+37 actual Linux process kills,241 helper tests with no skips, and18 original frames. The cold Android package, AXML versionCode3, six ARM64 ELF libraries, both approved original ticket imports, source mutation audit and APK v2 signature were independently verified. APK size59,126,454 bytes; SHA256 c2be0b3bbaf11fe6f28a3f45246591b6d694d0d5d2e6ff40faa8217c4ad98d93. Its certificate differs from the archived G2 package, so upgrade compatibility is not assumed and existing data must not be cleared to work around a conflict.

The APK is durably saved in the owner's Library and a separate materialized copy matched its hash. Chat attachment delivery was rejected by the size limit; only instructions/checklists were sent as attachments, and the owner was directed to Library. No APK chat-delivery claim is made. All six same-build physical Android actions and independent normal-input device acceptance remain NOT_RUN. G3 is not passed; G4 remains blocked. Store/UI whitebox presentation is not final art quality. This progress-only commit does not change the reviewed build source or trigger another run.
