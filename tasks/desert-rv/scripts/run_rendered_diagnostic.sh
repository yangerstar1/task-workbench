#!/usr/bin/env bash
# Candidate public Actions runner only; no local or automatic execution.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY_VISIBILITY:-}" == public ]] || exit 2
: "${UNITY_EDITOR:?Existing licensed Unity 6000.3.19f1 executable required}"
mode="${DESERTRV_RENDER_MODE:-journey}"
case "$mode" in
  journey) : "${DESERTRV_DIAGNOSTIC_SCOPE:?Pinned request required}"; : "${DESERTRV_INPUT_PLAN:?Observed short-segment plan required}"; entry=DesertRV.Editor.JourneyRenderedDiagnosticRunner.Run ;;
  window-smoke) entry=DesertRV.Editor.JourneyRenderedDiagnosticRunner.RunWindowSmoke ;;
  *) exit 2 ;;
esac
: "${DESERTRV_EVIDENCE_DIR:?Fresh evidence directory required}"
: "${DESERTRV_UNITY_PROJECT:?Absolute project required}"
[[ ! -e "$DESERTRV_EVIDENCE_DIR" || -z "$(ls -A "$DESERTRV_EVIDENCE_DIR")" ]] || exit 2
private_logs="${DESERTRV_PRIVATE_LOG_DIR:-$(mktemp -d)}"
export DISPLAY=:91
export DESERTRV_CAPTURE_HANDSHAKE_DIR="$(mktemp -d)"
private_capture="$(mktemp -d)"
export DESERTRV_PROGRESS_DIR="$(mktemp -d)"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
Xvfb "$DISPLAY" -screen 0 1600x1000x24 -nolisten tcp >"$private_logs/xvfb.log" 2>&1 & xvfb_pid=$!
unity_pid=''
wm_pid=''
cleanup() {
  original=$?
  trap - EXIT
  [[ -z "$unity_pid" ]] || kill "$unity_pid" 2>/dev/null || true
  [[ -z "$wm_pid" ]] || kill "$wm_pid" 2>/dev/null || true
  kill "$xvfb_pid" 2>/dev/null || true
  if ! python3 "$script_dir/rendered/write_control_status.py" --record-progress "$DESERTRV_PROGRESS_DIR" "$DESERTRV_EVIDENCE_DIR" >/dev/null 2>&1; then original=1; fi
  exit "$original"
}
trap cleanup EXIT
for i in $(seq 1 100); do xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && break; sleep .1; done
xdpyinfo -display "$DISPLAY" >/dev/null
# Minimal WM provides floating-window mapping/focus; no desktop or terminal is started.
openbox --sm-disable >"$private_logs/openbox.log" 2>&1 & wm_pid=$!
for i in $(seq 1 100); do xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id' && break; sleep .1; done
xprop -root _NET_SUPPORTING_WM_CHECK | grep -q 'window id'
# No batchmode/nographics/quit and no screen capture before the dedicated-window handshake.
timeout --signal=TERM --kill-after=30s 15m "$UNITY_EDITOR" -projectPath "$DESERTRV_UNITY_PROJECT" \
  -executeMethod "$entry" -force-glcore -job-worker-count 2 -logFile "$private_logs/editor.log" & unity_pid=$!
printf 1 > "$DESERTRV_PROGRESS_DIR/editor-spawn"
set +e
python3 "$(dirname "$0")/capture_game_window.py" "$DESERTRV_CAPTURE_HANDSHAKE_DIR" "$private_capture/real-time.mp4" "$private_capture/capture-receipt.json" "$unity_pid"
capture_status=$?
# Recording failure is terminal. Do not wait five more minutes for the unrelated outer watchdog.
if [[ "$capture_status" != 0 ]]; then kill -TERM "$unity_pid" 2>/dev/null || true; fi
wait "$unity_pid"; editor_status=$?
set -e
unity_pid=''
mkdir -p "$DESERTRV_EVIDENCE_DIR"
cp "$private_capture/capture-receipt.json" "$DESERTRV_EVIDENCE_DIR/capture-receipt.json"
if [[ "$capture_status" == 0 ]]; then mv "$private_capture/real-time.mp4" "$DESERTRV_EVIDENCE_DIR/real-time.mp4"; fi
# Only an explicit fresh safe-export directory may ever be uploaded by a separate reviewed workflow.
if [[ -n "${DESERTRV_SAFE_EXPORT_DIR:-}" ]]; then
  python3 "$(dirname "$0")/prepare_safe_diagnostic_export.py" "$DESERTRV_EVIDENCE_DIR" "$DESERTRV_SAFE_EXPORT_DIR" --mode "$mode"
fi
[[ "$capture_status" == 0 && "$editor_status" == 0 ]]

