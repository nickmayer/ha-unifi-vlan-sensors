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

# 2. pristine unifi tests of the core release this integration is based on, then ours
CORE_REPO="${CORE_REPO:-/mnt/d/source/ha-core}"   # any core clone that has the tag
CORE_REF="${CORE_REF:-2026.10.0}"
rm -rf "$CORE/tests/components/unifi"
git -C "$CORE_REPO" archive "$CORE_REF" tests/components/unifi | tar -x -C "$CORE"
for patch_file in "$REPO"/tests/core-patches/*.patch; do
  (cd "$CORE" && patch -p1 -s < "$patch_file")
done
cp "$REPO"/tests/test_*.py "$CORE/tests/components/unifi/"

# 3. regenerate the unifi translations from strings.json
(cd "$CORE" && "$PY" -m script.translations develop --integration unifi >/dev/null)

# 4. run the whole unifi suite
cd "$CORE"
exec "$PY" -m pytest tests/components/unifi -q -p no:cacheprovider -p no:sugar \
  --timeout=180 -n "${WORKERS:-4}" "$@"
