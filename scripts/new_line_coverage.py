#!/usr/bin/env python3
"""Report which lines added by the current git diff are not covered by tests.

Run inside the core checkout after `pytest --cov=... --cov-report=json:coverage.json`:

    python new_line_coverage.py [coverage.json]
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys


def added_lines(path_prefix: str) -> dict[str, set[int]]:
    diff = subprocess.run(
        ["git", "diff", "-U0", "HEAD", "--", path_prefix],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    result: dict[str, set[int]] = {}
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif m := re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line):
            start, count = int(m[1]), int(m[2] or 1)
            result.setdefault(current, set()).update(range(start, start + count))
    return result


def main() -> int:
    report = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json").read_text())
    uncovered_total = 0
    statements_total = 0
    for file, lines in added_lines("homeassistant/components/unifi").items():
        if file not in report["files"] or not file.endswith(".py"):
            continue
        data = report["files"][file]
        executable = set(data["executed_lines"]) | set(data["missing_lines"])
        mine = lines & executable
        missing = sorted(mine & set(data["missing_lines"]))
        statements_total += len(mine)
        uncovered_total += len(missing)
        print(f"{file}: {len(mine) - len(missing)}/{len(mine)} new statements covered" + (f"  MISSING {missing}" if missing else ""))
    print(f"TOTAL: {statements_total - uncovered_total}/{statements_total} new statements covered")
    return 1 if uncovered_total else 0


if __name__ == "__main__":
    sys.exit(main())
