#!/usr/bin/env bash
# Run the checks a Home Assistant core PR needs, for the UniFi integration.
#
#   wsl -d Ubuntu-24.04 -- bash /mnt/d/source/ha-unifi-vlan-sensors/scripts/pr_checks.sh [step ...]
#
# Steps (default: all): sync tests lint types pylint hassfest spell
# Extra step: format  (ruff-format + ruff --fix, then copy the result back to $SRC)
# The branch is edited in $SRC (a Windows checkout); it is copied into the Linux checkout
# $CORE (created by setup_core_dev.sh) where the tools run.
set -uo pipefail

SRC="${SRC:-/mnt/d/source/ha-core}"
CORE="${CORE:-$HOME/ha-core-dev}"
VENV="${VENV:-$HOME/ha-test-venv}"
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
INT=homeassistant/components/unifi
TESTS=tests/components/unifi
steps=("$@"); [ ${#steps[@]} -eq 0 ] && steps=(sync tests lint types pylint hassfest spell)
status=0

run() { echo; echo "=== $*"; "$@" || status=1; }
want() { for s in "${steps[@]}"; do [ "$s" = "$1" ] && return 0; done; return 1; }

cd "$CORE"

if want sync; then
  echo "=== sync $SRC -> $CORE"
  rsync -a --exclude .git --exclude .venv --exclude __pycache__ --exclude '.req-*' \
    "$SRC/$INT/" "$CORE/$INT/"
  rsync -a --exclude __pycache__ "$SRC/$TESTS/" "$CORE/$TESTS/"
  "$PY" -m script.translations develop --integration unifi >/dev/null
fi

if want format; then
  "$VENV/bin/ruff" check --fix "$INT" "$TESTS" || status=1
  "$VENV/bin/ruff" format "$INT" "$TESTS"
  rsync -a --exclude __pycache__ "$CORE/$INT/" "$SRC/$INT/"
  rsync -a --exclude __pycache__ "$CORE/$TESTS/" "$SRC/$TESTS/"
fi

if want tests; then
  # sysmon is far faster than the default tracer on Python 3.14
  COVERAGE_CORE=sysmon run "$PY" -m pytest "$TESTS" -q -p no:cacheprovider -p no:sugar --timeout=180 -n 0     --cov=homeassistant.components.unifi --cov-report=json:coverage.json 2>&1 | tail -4
  run "$PY" "$(dirname "${BASH_SOURCE[0]}")/new_line_coverage.py" coverage.json
fi
if want lint; then
  run "$VENV/bin/ruff" check "$INT" "$TESTS"
  run "$VENV/bin/ruff" format --check "$INT" "$TESTS"
fi
if want types; then
  echo; echo "=== mypy $INT (errors in other integrations are ignored: their dependencies are not installed)"
  out=$("$VENV/bin/mypy" "$INT" 2>&1)
  echo "$out" | grep -E "^$INT" || echo "no mypy errors in $INT"
  echo "$out" | grep -qE "^$INT" && status=1
fi
if want pylint; then
  run "$VENV/bin/pylint" "$INT" "$TESTS/test_sensor.py" "$TESTS/test_config_flow.py"
fi
if want hassfest; then
  run "$PY" -m script.hassfest --integration-path "$INT" --action validate
fi
if want spell; then
  run "$VENV/bin/codespell" --ignore-words-list=aiport,astroid,checkin,currenty,hass,iif,incomfort,lookin,nam,NotIn     --skip="*.json,*.ambr" --quiet-level=2 "$INT" "$TESTS/test_sensor.py" "$TESTS/test_config_flow.py"
fi

echo; [ $status -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $status
