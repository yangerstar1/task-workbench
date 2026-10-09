#!/usr/bin/env bash
# Official batch activation/build; standalone player receives no account credentials.
set +x
set -euo pipefail
umask 077
[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY_VISIBILITY:-}" == public ]] || exit 2
[[ "${UNITY_PATH:-}" == /opt/unity && "$(cat /opt/unity/version)" == 6000.3.19f1 ]] || exit 2
: "${UNITY_LICENSE:?}"; : "${UNITY_EMAIL:?}"; : "${UNITY_PASSWORD:?}"
scripts=/github/workspace/tasks/desert-rv/scripts
private="$(mktemp -d)"
activation=NOT_ATTEMPTED; built=NOT_ATTEMPTED; player=NOT_ATTEMPTED; returned=NOT_ATTEMPTED; attempted=0; xvfb_pid=''; wm_pid=''
cleanup() {
  original=$?; trap - EXIT INT TERM; set +e
  [[ -z "$wm_pid" ]] || kill "$wm_pid" 2>/dev/null
  [[ -z "$xvfb_pid" ]] || kill "$xvfb_pid" 2>/dev/null
  if [[ "$attempted" == 1 ]]; then
    timeout --signal=TERM --kill-after=15s 180s bash -c 'source /gameci/platforms/ubuntu/return_license.sh' >"$private/return.log" 2>&1
    if [[ "$?" == 0 ]]; then returned=SUCCEEDED; else returned=FAILED; original=1; fi
  fi
  cleaned=SUCCEEDED
  if ! rm -rf "$private"; then cleaned=FAILED; original=1; fi
  if [[ -e "$private" || -L "$private" ]]; then cleaned=FAILED; original=1; fi
  if ! python3 "$scripts/player/player_window_smoke.py" control "$activation" "$built" "$player" "$returned" "$cleaned" >/dev/null 2>&1; then original=1; fi
  printf 'PLAYER_CONTROL activation=%s build=%s player=%s return=%s cleanup=%s\n' "$activation" "$built" "$player" "$returned" "$cleaned"
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
export DESERTRV_PLAYER_BUILD="$private/build/DesertRV.x86_64"
cd /github/workspace/tasks/desert-rv/unity
if timeout --signal=TERM --kill-after=30s 25m unity-editor -projectPath "$PWD" -executeMethod DesertRV.Editor.PlayerBuild.BuildLinuxWindowSmoke -quit -force-glcore -job-worker-count 2 -logFile "$private/build.log" >"$private/build-stdout.log" 2>&1; then
  built=SUCCEEDED
else
  built=FAILED
  python3 "$scripts/player/player_window_smoke.py" build-failure "$private/build.log" >/dev/null 2>&1 || :
  exit 1
fi
export DISPLAY=:91
Xvfb "$DISPLAY" -screen 0 1600x1000x24 -nolisten tcp >"$private/xvfb.log" 2>&1 & xvfb_pid=$!
for attempt in $(seq 1 50); do if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then break; fi; sleep .1; done
xdpyinfo -display "$DISPLAY" >/dev/null 2>&1
openbox --sm-disable >"$private/wm.log" 2>&1 & wm_pid=$!
if timeout --signal=TERM --kill-after=5s 150s env -u UNITY_LICENSE -u UNITY_EMAIL -u UNITY_PASSWORD -u UNITY_SERIAL \
  python3 "$scripts/player/player_window_smoke.py" capture "$private/build" "$private" >"$private/capture.log" 2>&1; then player=SUCCEEDED; else player=FAILED; exit 1; fi
