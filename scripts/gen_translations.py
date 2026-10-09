#!/usr/bin/env python3
"""Regenerate custom_components/unifi/translations/en.json from strings.json.

Core generates the translations at build time; a custom component has to ship them.
Run this after editing strings.json:

    python scripts/gen_translations.py --core ../ha-core

`--core` only has to contain homeassistant/strings.json (for the shared `common::` texts).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_upstream import COMPONENT, REPO, resolve_refs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()

    component = REPO / COMPONENT
    strings = json.loads((component / "strings.json").read_text(encoding="utf-8"))
    common = json.loads((args.core / "homeassistant" / "strings.json").read_text(encoding="utf-8"))
    translations = resolve_refs(strings, strings, common)
    out = component / "translations" / "en.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(translations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
