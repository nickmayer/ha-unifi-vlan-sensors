#!/usr/bin/env bash
# Run Home Assistant core's UniFi test suite against the integration in this repo.
#
# Home Assistant core only supports Linux/macOS, so on Windows run this inside WSL:
#   wsl -d Ubuntu-24.04 -- bash /mnt/d/source/ha-unifi-vlan-sensors/scripts/run_core_tests.sh
#
# One-time setup (see README "Development"): a core checkout at $CORE and a Python 3.14
# venv at $VENV with core's requirements + test requirements installed, and translations
# generated once with `python -m script.translations develop --all`.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE="${CORE:-$HOME/ha-core}"
VENV="${VENV:-$HOME/ha-test-venv}"
PY="$VENV/bin/python"

# 1. put our integration over core's copy (keep core's manifest: no custom "version" key;
#    translations are regenerated below)
rsync -a --delete \
  --exclude translations --exclude manifest.json --exclude __pycache__ \
  "$REPO/custom_components/unifi/" "$CORE/homeassistant/components/unifi/"

# 2. our tests, plus the small changes our option needs in core's existing tests
cp "$REPO"/tests/test_*.py "$CORE/tests/components/unifi/"
for patch_file in "$REPO"/tests/core-patches/*.patch; do
  # -N: skip hunks that are already applied (script is re-runnable)
  (cd "$CORE" && patch -p1 -N -s -r - < "$patch_file" >/dev/null || true)
done

# 3. regenerate the unifi translations from strings.json
(cd "$CORE" && "$PY" -m script.translations develop --integration unifi >/dev/null)

# 4. run the whole unifi suite
cd "$CORE"
exec "$PY" -m pytest tests/components/unifi -q -p no:cacheprovider -p no:sugar \
  --timeout=180 -n "${WORKERS:-4}" "$@"
