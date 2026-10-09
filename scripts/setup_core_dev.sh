#!/usr/bin/env bash
# Prepare a Home Assistant core checkout (Linux/WSL) for working on the PR branch.
#
#   bash scripts/setup_core_dev.sh
#
# Creates $CORE (default ~/ha-core-dev) from upstream `dev`, a Python venv at $VENV with
# core's requirements + test requirements + this integration's requirements, and generates
# the development translations the test suite needs.
set -euo pipefail

CORE="${CORE:-$HOME/ha-core-dev}"
VENV="${VENV:-$HOME/ha-test-venv}"
UV="${UV:-$HOME/.local/bin/uv}"

if [ ! -d "$CORE/.git" ]; then
  git clone --depth 1 https://github.com/home-assistant/core.git "$CORE"
fi
cd "$CORE"

[ -d "$VENV" ] || "$UV" venv "$VENV" --python 3.14

# test requirements without the linters/typing packages (installed separately below)
grep -E "^(freezegun|pytest|pytest-asyncio|pytest-aiohttp|pytest-freezer|pytest-socket|pytest-timeout|pytest-unordered|pytest-xdist|pytest-cov|requests-mock|syrupy|respx|mock-open|pydantic|requests|coverage)==" \
  requirements_test.txt > .req-test.txt

extra=$(python3 - <<'PY'
import json
reqs = []
for name in ("unifi", "unifi_discovery"):
    reqs += json.load(open(f"homeassistant/components/{name}/manifest.json"))["requirements"]
print(" ".join(reqs))
PY
)

"$UV" pip install --python "$VENV/bin/python" -q \
  -c homeassistant/package_constraints.txt \
  -r requirements.txt -r .req-test.txt $extra paho-mqtt aiohasupervisor

# linters / typing used by the pre-commit checks
"$UV" pip install --python "$VENV/bin/python" -q \
  "$(grep -E '^ruff==' requirements_test_pre_commit.txt)" \
  "$(grep -E '^mypy==' requirements_test.txt)" \
  "$(grep -E '^pylint==' requirements_test.txt)" \
  "$(grep -E '^pylint-per-file-ignores==' requirements_test.txt)" \
  "$(grep -E '^astroid==' requirements_test.txt)" \
  "$(grep -E '^codespell==' requirements_test_pre_commit.txt || echo codespell)" \
  types-requests 2>&1 | tail -2 || true

"$VENV/bin/python" -m script.translations develop --all >/dev/null
echo "core: $(git log -1 --format='%h %s')"
"$VENV/bin/python" -c "import aiounifi; print('aiounifi', aiounifi.__file__)"
echo "SETUP DONE"
