#!/usr/bin/env bash
# Candidate public Actions runner only; no local or automatic execution.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY_VISIBILITY:-}" == public ]] || exit 2
: "${UNITY_EDITOR:?Existing licensed Unity 6000.3.19f1 executable required}"
: "${DESERTRV_DIAGNOSTIC_SCOPE:?Pinned request required}"
: "${DESERTRV_INPUT_PLAN:?Observed short-segment plan required}"
: "${DESERTRV_EVIDENCE_DIR:?Fresh evidence directory required}"
: "${DESERTRV_UNITY_PROJECT:?Absolute project required}"
[[ ! -e "$DESERTRV_EVIDENCE_DIR" || -z "$(ls -A "$DESERTRV_EVIDENCE_DIR")" ]] || exit 2
export DISPLAY=:91
export DESERTRV_CAPTURE_HANDSHAKE_DIR="$(mktemp -d)"
private_capture="$(mktemp -d)"
Xvfb "$DISPLAY" -screen 0 1600x1000x24 -nolisten tcp >xvfb-private.log 2>&1 & xvfb_pid=$!
unity_pid=''
cleanup() {
  [[ -z "$unity_pid" ]] || kill "$unity_pid" 2>/dev/null || true
  kill "$xvfb_pid" 2>/dev/null || true
}
trap cleanup EXIT
for i in $(seq 1 100); do xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && break; sleep .1; done
xdpyinfo -display "$DISPLAY" >/dev/null
# No batchmode/nographics/quit and no screen capture before the dedicated-window handshake.
timeout --signal=TERM 40m "$UNITY_EDITOR" -projectPath "$DESERTRV_UNITY_PROJECT" \
  -executeMethod DesertRV.Editor.JourneyRenderedDiagnosticRunner.Run -logFile unity-private.log & unity_pid=$!
set +e
python "$(dirname "$0")/capture_game_window.py" "$DESERTRV_CAPTURE_HANDSHAKE_DIR" "$private_capture/real-time.mp4" "$private_capture/capture-receipt.json" "$unity_pid"
capture_status=$?
wait "$unity_pid"; editor_status=$?
set -e
unity_pid=''
mkdir -p "$DESERTRV_EVIDENCE_DIR"
cp "$private_capture/capture-receipt.json" "$DESERTRV_EVIDENCE_DIR/capture-receipt.json"
if [[ "$capture_status" == 0 ]]; then mv "$private_capture/real-time.mp4" "$DESERTRV_EVIDENCE_DIR/real-time.mp4"; fi
# Only an explicit fresh safe-export directory may ever be uploaded by a separate reviewed workflow.
if [[ -n "${DESERTRV_SAFE_EXPORT_DIR:-}" ]]; then
  python "$(dirname "$0")/prepare_safe_diagnostic_export.py" "$DESERTRV_EVIDENCE_DIR" "$DESERTRV_SAFE_EXPORT_DIR"
fi
[[ "$capture_status" == 0 && "$editor_status" == 0 ]]
