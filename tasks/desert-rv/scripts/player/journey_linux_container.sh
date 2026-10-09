#!/usr/bin/env bash
# Same job, official batch build only. No player launch or account change.
set +x
set -euo pipefail
umask 077
[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY_VISIBILITY:-}" == public ]] || exit 2
[[ "${UNITY_PATH:-}" == /opt/unity && "$(cat /opt/unity/version)" == 6000.3.19f1 ]] || exit 2
: "${UNITY_LICENSE:?}"; : "${UNITY_EMAIL:?}"; : "${UNITY_PASSWORD:?}"
# Only this container's child Git commands trust the exact mounted reviewed workspace.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=/github/workspace
scripts=/github/workspace/tasks/desert-rv/scripts
build=/github/workspace/tasks/desert-rv/journey-linux-private-build
[[ ! -e "$build" && ! -L "$build" ]] || exit 2
private="$(mktemp -d)"
activation=NOT_ATTEMPTED; built=NOT_ATTEMPTED; returned=NOT_ATTEMPTED; attempted=0
cleanup() {
  original=$?; trap - EXIT INT TERM; set +e
  if [[ "$attempted" == 1 ]]; then
    timeout --signal=TERM --kill-after=15s 180s bash -c 'source /gameci/platforms/ubuntu/return_license.sh' >"$private/return.log" 2>&1
    if [[ "$?" == 0 ]]; then returned=SUCCEEDED; else returned=FAILED; original=1; fi
  fi
  cleaned=SUCCEEDED
  if ! rm -rf "$private" "$build"; then cleaned=FAILED; original=1; fi
  if [[ -e "$private" || -L "$private" || -e "$build" || -L "$build" ]]; then cleaned=FAILED; original=1; fi
  if ! python3 "$scripts/player/journey_linux_export.py" control "$activation" "$built" "$returned" "$cleaned" >/dev/null 2>&1; then original=1; fi
  printf 'JOURNEY_LINUX_CONTROL activation=%s build=%s return=%s cleanup=%s\n' "$activation" "$built" "$returned" "$cleaned"
  exit "$original"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
export UNITY_SERIAL="$(python3 "$scripts/rendered/serial_from_license.py")"
[[ -n "$UNITY_SERIAL" ]] || exit 2
if [[ "$UNITY_SERIAL" = F* ]]; then dbus-uuidgen > /etc/machine-id; mkdir -p /var/lib/dbus; ln -sf /etc/machine-id /var/lib/dbus/machine-id; fi
cp -a /gameci/BlankProject /BlankProject
attempted=1
if timeout --signal=TERM --kill-after=15s 12m bash -c 'source /gameci/platforms/ubuntu/activate.sh' >"$private/activation.log" 2>&1; then activation=SUCCEEDED; else activation=FAILED; exit 1; fi
cd /github/workspace/tasks/desert-rv/unity
python3 "$scripts/player/journey_linux_export.py" snapshot "$private" >/dev/null 2>&1
export DESERTRV_PERFORMANCE_PRIVATE="$private"
if timeout --signal=TERM --kill-after=30s 65m unity-editor -projectPath "$PWD" -executeMethod DesertRV.Editor.JourneyCandidateLinuxBuild.BuildPreparedLinuxDiagnostic -quit -force-glcore -job-worker-count 2 -logFile "$private/editor.log" >"$private/rendered.log" 2>&1; then
  build_exit=0
else
  build_exit=$?
fi
observed=1
if ! python3 "$scripts/player/journey_linux_export.py" record "$private" "$build_exit" >/dev/null 2>&1; then observed=0; fi
restored=1
if ! python3 "$scripts/player/journey_linux_export.py" restore "$private" >/dev/null 2>&1; then restored=0; fi
if [[ "$build_exit" != 0 || "$observed" != 1 || "$restored" != 1 ]]; then built=FAILED; exit 1; fi
if ! python3 /github/workspace/tasks/desert-rv/art/journey-preparation/linux_build_input.py verify >"$private/verify.log" 2>&1; then built=FAILED; exit 1; fi
if python3 "$scripts/player/journey_linux_export.py" stage >"$private/stage.log" 2>&1; then built=SUCCEEDED; else built=FAILED; exit 1; fi
