#!/usr/bin/env bash
set -euo pipefail
# Existing authorized disposable GitHub-hosted disk preparation. No SDK downloads.
python3 tasks/lottery-shop/scripts/g3_ci.py guard
sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/.ghcup /usr/local/lib/android /opt/hostedtoolcache/CodeQL
python3 - <<'PY'
import shutil
if shutil.disk_usage('.').free < 30*1024**3:
    raise SystemExit('Need at least30GiB for cold Unity image.')
print('G3 disposable-runner disk preflight passed.')
PY
