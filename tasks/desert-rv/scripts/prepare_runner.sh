#!/usr/bin/env bash
set -euo pipefail
# Only disposable standard GitHub-hosted Ubuntu workers. Never run on a workstation.
test "${RUNNER_ENVIRONMENT:-}" = github-hosted
test "${RUNNER_OS:-}" = Linux
test "${GITHUB_ACTIONS:-}" = true
if [[ "${GITHUB_EVENT_NAME:-}" != workflow_dispatch ]]; then
  if [[ "${GITHUB_WORKFLOW_REF:-}" == 'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r3.yml@refs/heads/main' ]]; then
    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r3_dispatch.py" --verify-only
  elif [[ "${GITHUB_WORKFLOW_REF:-}" == 'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r2.yml@refs/heads/main' ]]; then
    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r2_dispatch.py" --verify-only
  elif [[ "${GITHUB_WORKFLOW_REF:-}" == 'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4.yml@refs/heads/main' ]]; then
    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_dispatch.py" --verify-only
  elif [[ "${GITHUB_WORKFLOW_REF:-}" == 'yangerstar1/task-workbench/.github/workflows/desert-rv-armored-v004-r1-strict.yml@refs/heads/main' ]]; then
    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/armored_v004_strict_dispatch.py" --verify-only
  elif [[ "${GITHUB_WORKFLOW_REF:-}" == 'yangerstar1/task-workbench/.github/workflows/desert-rv-armored-v004-r1-discovery.yml@refs/heads/main' ]]; then
    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/armored_v004_discovery_dispatch.py" --verify-only
  else
    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/journey_rebuild_dispatch.py" --verify-only
  fi
fi
test -n "${UNITY_LICENSE:-}" || { echo '::error::UNITY_LICENSE is missing; native proof cannot run.'; exit 1; }
test -n "${UNITY_EMAIL:-}" || { echo '::error::UNITY_EMAIL is missing; native proof cannot run.'; exit 1; }
test -n "${UNITY_PASSWORD:-}" || { echo '::error::UNITY_PASSWORD is missing; native proof cannot run.'; exit 1; }
# These are unrelated preinstalled SDKs on the disposable runner. GameCI uses its
# container's own Android SDK/NDK. No project, artifact, or account directory is removed.
sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/.ghcup /usr/local/lib/android /opt/hostedtoolcache/CodeQL
df -h .
python3 - <<'PY'
import shutil
free = shutil.disk_usage('.').free
if free < 30 * 1024**3:
    raise SystemExit('Insufficient free disk for the cold Unity image: need 30 GiB.')
print('Cold image disk preflight passed.')
PY


