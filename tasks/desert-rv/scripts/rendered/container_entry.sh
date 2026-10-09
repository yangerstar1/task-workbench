#!/usr/bin/env bash
# Invoked only by the reviewed composite on a disposable public Actions worker.
set +x
set -euo pipefail
umask 077
[[ "${GITHUB_ACTIONS:-}" == true && "${GITHUB_REPOSITORY_VISIBILITY:-}" == public ]] || exit 2
[[ "${UNITY_PATH:-}" == /opt/unity && "$(cat /opt/unity/version)" == 6000.3.19f1 ]] || exit 2
: "${UNITY_LICENSE:?}"; : "${UNITY_EMAIL:?}"; : "${UNITY_PASSWORD:?}"
private="$(mktemp -d)"
activation=NOT_ATTEMPTED; returned=NOT_ATTEMPTED; render=NOT_ATTEMPTED; attempted=0
cleanup() {
  original=$?
  trap - EXIT INT TERM
  set +e
  if [[ "$attempted" == 1 ]]; then
    timeout --signal=TERM --kill-after=15s 180s bash -c 'source /gameci/platforms/ubuntu/return_license.sh' >"$private/return.log" 2>&1
    if [[ "$?" == 0 ]]; then returned=SUCCEEDED; else returned=FAILED; original=1; fi
  fi
  # Record cleanup only after checking the real removal result and path absence.
  cleaned=SUCCEEDED
  if ! rm -rf "$private"; then cleaned=FAILED; original=1; fi
  if [[ -e "$private" || -L "$private" ]]; then cleaned=FAILED; original=1; fi
  # A status-write failure cannot leave the main process successful, even if a partial old file exists.
  if ! python3 /github/workspace/tasks/desert-rv/scripts/rendered/write_control_status.py "$activation" "$returned" "$render" "$cleaned" >/dev/null 2>&1; then
    original=1
    printf 'RENDERED_CONTROL_WRITE_FAILED\n' >&2
  fi
  printf 'RENDERED_CONTROL activation=%s return=%s render=%s cleanup=%s\n' "$activation" "$returned" "$render" "$cleaned"
  exit "$original"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
export UNITY_SERIAL="$(python3 /github/workspace/tasks/desert-rv/scripts/rendered/serial_from_license.py)"
[[ -n "$UNITY_SERIAL" ]] || exit 2
# Exact personal-license machine identity preparation from pinned official entrypoint.sh.
if [[ "$UNITY_SERIAL" = F* ]]; then dbus-uuidgen > /etc/machine-id; mkdir -p /var/lib/dbus; ln -sf /etc/machine-id /var/lib/dbus/machine-id; fi
cp -a /gameci/BlankProject /BlankProject
timeout --signal=TERM --kill-after=1s 3s python3 /github/workspace/tasks/desert-rv/scripts/rendered/launcher_context.py before "$private" >/dev/null 2>&1 || :
attempted=1
if timeout --signal=TERM --kill-after=15s 12m bash -c 'source /gameci/platforms/ubuntu/activate.sh' >"$private/activation.log" 2>&1; then activation=SUCCEEDED; else activation=FAILED; exit 1; fi
export UNITY_EDITOR=/opt/unity/Editor/Unity
export DESERTRV_PRIVATE_LOG_DIR="$private"
cd "$DESERTRV_UNITY_PROJECT"
# The rendered game process receives no account credentials. Parent retains them only for official return.
if env -u UNITY_LICENSE -u UNITY_EMAIL -u UNITY_PASSWORD -u UNITY_SERIAL \
    bash /github/workspace/tasks/desert-rv/scripts/run_rendered_diagnostic.sh >"$private/rendered.log" 2>&1; then render=SUCCEEDED; else render=FAILED; exit 1; fi
