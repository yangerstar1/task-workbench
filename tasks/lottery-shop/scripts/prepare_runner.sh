#!/usr/bin/env bash
set -euo pipefail
# Only call this on the verified disposable GitHub-hosted Linux job.
# No credential values are passed to or inspected by this script.
test "${RUNNER_ENVIRONMENT:-}" = github-hosted
test "${RUNNER_OS:-}" = Linux
test "${GITHUB_ACTIONS:-}" = true
test "${GITHUB_EVENT_NAME:-}" = push
test "${GITHUB_REPOSITORY:-}" = yangerstar1/task-workbench
test "${GITHUB_REF:-}" = refs/heads/lottery-shop-g0-20261011
python3 tasks/lottery-shop/scripts/probe_ci.py guard
# These preinstalled SDKs are unrelated to the pinned Unity Android container.
# This is not a user workstation or a saved cloud task environment.
sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/.ghcup /usr/local/lib/android /opt/hostedtoolcache/CodeQL
python3 - <<'PY'
import shutil
if shutil.disk_usage('.').free < 30 * 1024**3:
    raise SystemExit('Need at least 30 GiB free space for a cold Unity image.')
print('Disposable runner disk preflight passed.')
PY
