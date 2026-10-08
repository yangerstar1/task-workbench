# Original APK Android evidence, bounded and fail closed

This manual owner/main-only workflow uses a free standard public GitHub ubuntu-24.04 runner. It does not run an emulator on dot's computer or the user's computer, create an independent Codex task, rebuild/modify/resign the game, or accept gameplay merely because screenshots exist.

## Modes and evidence boundary

- `capture-only`: verifies the allowlisted successful original build/run/attempt/artifact ZIP/APK and published sanitized receipt bytes. Installs the exact ARM64 APK with `--abi arm64-v8a` into Android 11/API 30 Google APIs x86_64 revision 16 using ARM translation. Launches at 1280×720 and 1600×720, validates actual PNG dimensions, backgrounds with HOME for five seconds, resumes, captures screenshots and original-speed silent recordings (at most 120 seconds each), and scans logcat for crash/ANR indicators. Screenshots still require human visual review; process existence is not evidence that gameplay works.
- `input-check`: deliberately BLOCKED until `coordinates.json` contains reviewed coordinates from these exact APK screenshots for both resolutions. Records separate source screenshot hashes and capture run IDs. The independent helper targets itself and calls `UiAutomation.injectInputEvent`, with pointer IDs 0/1, a common downTime, strictly increasing real eventTime, DOWN → POINTER_DOWN → MOVE → POINTER_UP → UP, and asserts each injection result. It never calls game code, changes health, grants victory or substitutes parallel single-touch adb commands for multitouch. Successful injection does not prove the game handled the gesture correctly.

The currently approved APK is the saved no-combat TraversalHarness from run 37796490106, commit 6dc675517db262c72dcb8c1507239d4bf10acc5d. It is not the latest game's build and not a complete game. The QA script commit is separately recorded. Adding another build requires independent verification and a reviewed pin entry; numeric input alone cannot approve arbitrary APKs. Package `com.desertrv.traversal.dev` was read from the actual APK binary AndroidManifest; it is checked again with aapt at execution.

Audio, physical GPU compatibility, ARM-hardware compatibility, real touch latency, sustained performance, combat, and full game acceptance remain NOT_EVALUATED. SwiftShader and silent emulator video cannot establish these properties. Full raw native build-receipt bytes were not published; the hash pinned here is the published reconstructed/sanitized JSON, not its recorded original-native hash.

## Safety and bounded execution

KVM must already be readable/writable and pass `emulator -accel-check`. No permission edits, sudo, udev, user-group edits, adb root, SELinux changes, Google Play account, paid runner, dependency cache or permanent service is used. SDK tools install only from official SDK manager packages with closed stdin; no bulk license acceptance. An unaccepted SDK license, changed image/emulator revision, unavailable artifact, failed ARM translation or denied cross-app input injection is a blocker. Do not work around it silently. Emulator stable 37.2.12 and image revision 16 are verified after install; this intentionally fails on unreviewed upgrades. The job has a 60-minute maximum and EXIT/INT/TERM cleanup. GitHub destroys the ephemeral runner on hard timeout.

Only job-scoped contents/actions read permissions are granted. Official checkout/upload actions use fixed SHAs. No Unity credentials are needed. Artifacts expire after seven days. Downloads and helper signing keys remain in runner temp; the game APK is not re-uploaded. Device logs contain only this fresh test environment, not user device data.

## Before dispatch

Run `python3 tasks/desert-rv/qa/android/test_qa.py` and `bash -n tasks/desert-rv/qa/android/run.sh tasks/desert-rv/qa/android/build-helper.sh`. Review changed workflow and pins. The helper's actual compilation and device injection are not claimed until GitHub execution. Initial capture should be reviewed before populating either screen's input plan. Each screen entry requires `sourceScreenshotSha256`, `captureRunId`, `intervalMs` (16–100), and `frames` (2–120), each frame containing exactly two [x,y] points in observed screen coordinates. No guessed examples are supplied.

A successful workflow means bounded evidence was captured; `execution-status.json` remains EVIDENCE_CAPTURED_REQUIRES_REVIEW with gameAcceptance NOT_EVALUATED. A blocked or failed run still uploads available diagnostic evidence.

## Independent review hardening

Before any SDK/emulator action, run.sh now revalidates the live QA run/attempt/commit/workflow and running ubuntu-24.04 hosted job through GitHub, checks the checkout and prior source identity, and rehashes the actual APK. Environment variables alone are not accepted as proof. Its temporary read-only API token is unset before SDK/ADB/emulator processes. Missing runner identity is a blocker, not permission to change runner or KVM access.

PNG evidence requires complete bounded chunk/CRC/IHDR/IDAT/IEND and decompressed pixel rows, then an actual FFmpeg decode. MP4 evidence requires matching dimensions, finite 1–121 second duration, decoded frames and a complete error-failing FFmpeg decode. Missing ffmpeg/ffprobe blocks without automatic software installation. Decodable evidence still requires human visual review; it does not establish correct gameplay, audio or physical-device compatibility.
