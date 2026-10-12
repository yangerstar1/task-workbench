#!/usr/bin/env bash
set -euo pipefail
# Runs only after the pure-Core .NET process probe, before loading Unity's image.
python3 tasks/lottery-shop/scripts/g2_ci.py guard
# Disposable GitHub-hosted Linux only; the guard verifies repository/actors/event.
# Never run against a user's machine, saved environment, or arbitrary directory.
sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/.ghcup /usr/local/lib/android /opt/hostedtoolcache/CodeQL
python3 - <<'PY'
import shutil
if shutil.disk_usage('.').free < 30 * 1024**3:
    raise SystemExit('Need at least 30 GiB free space for the cold Unity image.')
print('G2 disposable-runner disk preflight passed.')
PY
