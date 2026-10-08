#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
# Re-check live GitHub run/job plus original source/APK before SDK or emulator actions.
python3 "$HERE/qa.py" preflight
# The read-only API credential is needed only by preflight, never by SDK/emulator/ADB.
unset GH_TOKEN GITHUB_TOKEN
mkdir -p "$QA_OUT" "$QA_WORK"
EMUPID=''; RECORDPID=''
cleanup() {
  code=$?
  if [[ -n "$RECORDPID" ]]; then kill "$RECORDPID" 2>/dev/null || true; fi
  if [[ -n "$EMUPID" ]]; then adb -s emulator-5554 emu kill >/dev/null 2>&1 || true; kill "$EMUPID" 2>/dev/null || true; fi
  python3 "$HERE/kvm_acl.py" restore || code=1
  if (( code != 0 )); then printf '{"status":"BLOCKED_OR_FAILED","exitCode":%s,"gameAcceptance":"NOT_EVALUATED"}\n' "$code" > "$QA_OUT/execution-status.json"; fi
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "${ALLOW_ONCE_KVM_ACL:-false}" == true ]]; then
  command -v getfacl >/dev/null; command -v setfacl >/dev/null
  python3 "$HERE/kvm_acl.py" grant
fi
[[ -r /dev/kvm && -w /dev/kvm ]] || { echo 'BLOCKED: /dev/kvm must already be readable and writable; no permission modification allowed' | tee "$QA_OUT/blocker.txt"; exit 1; }
# FFmpeg is a necessary evidence decoder, installed only on this verified disposable runner.
missing=()
for tool in ffmpeg ffprobe; do
  if ! command -v "$tool" >/dev/null; then missing+=("$tool"); fi
done
printf 'Missing video verification tools: %s\n' "${missing[*]:-none}" | tee "$QA_OUT/dependency-check.txt"
if (( ${#missing[@]} )); then
  timeout 180 sudo apt-get update > "$QA_OUT/apt-update.txt" 2>&1
  apt-cache policy ffmpeg > "$QA_OUT/ffmpeg-package-policy.txt"
  # Use the standard Ubuntu repositories already configured by the official runner.
  # Do not add repositories, disable signature checks, or accept unauthenticated packages.
  timeout 300 sudo apt-get install -y --no-install-recommends ffmpeg > "$QA_OUT/ffmpeg-install.txt" 2>&1
fi
for tool in ffmpeg ffprobe; do
  command -v "$tool" >> "$QA_OUT/dependency-check.txt" || { echo "BLOCKED: $tool unavailable after official Ubuntu package installation" | tee "$QA_OUT/blocker.txt"; exit 1; }
done
ffmpeg -version > "$QA_OUT/ffmpeg-version.txt"
ffprobe -version > "$QA_OUT/ffprobe-version.txt"
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:?Android SDK missing}}
export ANDROID_SDK_ROOT="$SDK" ANDROID_HOME="$SDK"
export PATH="$SDK/platform-tools:$SDK/emulator:$SDK/cmdline-tools/latest/bin:$PATH"
# No --licenses, yes, chmod, udev, or user-group modifications.
# New/unaccepted SDK terms must block instead of being auto-accepted.
timeout 600 sdkmanager 'platform-tools' 'emulator' 'platforms;android-30' 'build-tools;35.0.0' 'system-images;android-30;google_apis;x86_64' </dev/null > "$QA_OUT/sdk-install.txt" 2>&1
emulator -version > "$QA_OUT/emulator-version.txt" 2>&1
emulator -accel-check > "$QA_OUT/acceleration.txt" 2>&1
cp "$SDK/system-images/android-30/google_apis/x86_64/source.properties" "$QA_OUT/image-source.properties"
grep -Eq '^Pkg.Revision *= *16[[:space:]]*$' "$QA_OUT/image-source.properties" || { echo 'BLOCKED: unreviewed image revision' > "$QA_OUT/blocker.txt"; exit 1; }
grep -Eq 'version 37\.2\.12([[:space:]]|\.)' "$QA_OUT/emulator-version.txt" || { echo 'BLOCKED: unreviewed emulator revision' > "$QA_OUT/blocker.txt"; exit 1; }
"$SDK/build-tools/35.0.0/apksigner" verify --verbose --print-certs "$QA_WORK/DesertRV.apk" > "$QA_OUT/apk-signature.txt"
"$SDK/build-tools/35.0.0/aapt" dump badging "$QA_WORK/DesertRV.apk" > "$QA_OUT/apk-badging.txt"
grep -Fq "package: name='com.desertrv.traversal.dev'" "$QA_OUT/apk-badging.txt"
if [[ "$QA_MODE" == input-check ]]; then bash "$HERE/build-helper.sh"; fi
export ANDROID_AVD_HOME="$QA_WORK/avd"
mkdir -p "$ANDROID_AVD_HOME"
printf 'no\n' | avdmanager create avd -n qa -k 'system-images;android-30;google_apis;x86_64' --force > "$QA_OUT/avd-create.txt" 2>&1
ADB=(adb -s emulator-5554)
for WIDTH in 1280 1600; do
  D="$QA_OUT/${WIDTH}x720"; mkdir -p "$D"
  setsid emulator -avd qa -port 5554 -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data -gpu swiftshader_indirect -memory 3072 -cores 2 -skin "${WIDTH}x720" > "$D/emulator.log" 2>&1 & EMUPID=$!
  printf '%s\n' "$EMUPID" > "$QA_WORK/emulator-group.pid"
  timeout 180 adb -s emulator-5554 wait-for-device
  READY=false
  for ((i=0;i<120;i++)); do
    if [[ $("${ADB[@]}" shell getprop sys.boot_completed | tr -d '\r') == 1 ]]; then READY=true; break; fi
    kill -0 "$EMUPID"; sleep 2
  done
  [[ "$READY" == true ]] || { echo 'BLOCKED: Android boot timeout' > "$D/blocker.txt"; exit 1; }
  "${ADB[@]}" shell settings put system accelerometer_rotation 0
  "${ADB[@]}" shell settings put system user_rotation 0
  "${ADB[@]}" shell wm size "${WIDTH}x720"
  "${ADB[@]}" shell wm density 160
  "${ADB[@]}" shell getprop > "$D/device-properties.txt"
  "${ADB[@]}" install --abi arm64-v8a "$QA_WORK/DesertRV.apk" | tee "$D/install.txt"
  grep -q '^Success' "$D/install.txt"
  "${ADB[@]}" shell cmd package resolve-activity --brief com.desertrv.traversal.dev | tr -d '\r' > "$D/activity.txt"
  ACTIVITY=$(tail -n1 "$D/activity.txt")
  [[ "$ACTIVITY" =~ ^com\.desertrv\.traversal\.dev/[A-Za-z0-9._]+$ ]]
  if [[ "$QA_MODE" == input-check ]]; then "${ADB[@]}" install "$QA_WORK/helper/helper.apk"; fi
  "${ADB[@]}" logcat -c
  "${ADB[@]}" shell screenrecord --time-limit 120 /sdcard/qa.mp4 > "$D/recording.txt" 2>&1 & RECORDPID=$!
  "${ADB[@]}" shell am start -W -n "$ACTIVITY" > "$D/launch.txt"
  grep -q 'Status: ok' "$D/launch.txt"
  sleep 15
  "${ADB[@]}" shell pidof com.desertrv.traversal.dev > "$D/pid-before.txt"
  "${ADB[@]}" shell dumpsys activity activities > "$D/foreground-before.txt"
  grep -E 'mResumedActivity.*com\.desertrv\.traversal\.dev|topResumedActivity.*com\.desertrv\.traversal\.dev' "$D/foreground-before.txt"
  "${ADB[@]}" exec-out screencap -p > "$D/launch.png"
  python3 "$HERE/qa.py" screenshot "$D/launch.png" "$WIDTH" 720
  "${ADB[@]}" shell input keyevent KEYCODE_HOME
  sleep 5
  "${ADB[@]}" shell am start -W -n "$ACTIVITY" > "$D/resume.txt"
  sleep 5
  "${ADB[@]}" shell pidof com.desertrv.traversal.dev > "$D/pid-after.txt"
  "${ADB[@]}" shell dumpsys activity activities > "$D/foreground-after.txt"
  grep -E 'mResumedActivity.*com\.desertrv\.traversal\.dev|topResumedActivity.*com\.desertrv\.traversal\.dev' "$D/foreground-after.txt"
  "${ADB[@]}" exec-out screencap -p > "$D/resume.png"
  python3 "$HERE/qa.py" screenshot "$D/resume.png" "$WIDTH" 720
  if [[ "$QA_MODE" == input-check ]]; then
    PLAN=$(python3 "$HERE/input_plan.py" "$WIDTH")
    "${ADB[@]}" shell am instrument -w -r -e plan "$PLAN" com.desertrv.qa/.TouchInstrumentation > "$D/input-result.txt"
    grep -q 'QA_INPUT_OK' "$D/input-result.txt"
    "${ADB[@]}" exec-out screencap -p > "$D/after-input.png"
    python3 "$HERE/qa.py" screenshot "$D/after-input.png" "$WIDTH" 720
  fi
  # Stop screenrecord gracefully on the device, preserving a playable original-speed MP4.
  "${ADB[@]}" shell 'kill -2 $(pidof screenrecord)' || true
  wait "$RECORDPID" || true; RECORDPID=''
  "${ADB[@]}" pull /sdcard/qa.mp4 "$D/original-speed-no-audio.mp4"
  python3 "$HERE/qa.py" video "$D/original-speed-no-audio.mp4" "$WIDTH" 720
  "${ADB[@]}" logcat -d -v threadtime > "$D/logcat.txt"
  "${ADB[@]}" shell dumpsys activity activities > "$D/activity-state.txt"
  "${ADB[@]}" shell pidof com.desertrv.traversal.dev > "$D/pid-final.txt"
  if grep -Ei 'FATAL EXCEPTION|Fatal signal|ANR in |am_anr|am_crash' "$D/logcat.txt" > "$D/crash-indicators.txt"; then echo 'FAILED: crash or ANR indicators require review' > "$D/blocker.txt"; exit 1; fi
  "${ADB[@]}" emu kill; wait "$EMUPID" || true; EMUPID=''
  sleep 3
done
python3 - <<'PY'
import os,json,pathlib,hashlib
p=pathlib.Path(os.environ['QA_OUT'])
files={f.relative_to(p).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob('*')) if f.is_file()}
(p/'execution-status.json').write_text(json.dumps({'status':'EVIDENCE_CAPTURED_REQUIRES_REVIEW','mode':os.environ['QA_MODE'],'gameAcceptance':'NOT_EVALUATED','audio':'NOT_EVALUATED','physicalGpuTouchLatencyPerformance':'NOT_EVALUATED','filesSha256':files},indent=2)+'\n')
PY
