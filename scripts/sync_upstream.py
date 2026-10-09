#!/usr/bin/env python3
"""Import a Home Assistant release of the UniFi integration onto the `upstream` branch.

    python scripts/sync_upstream.py --core ../ha-core --ref 2026.10.0

What it does (nothing touches your working tree or `main`):

1. fetches the tag `--ref` from the core checkout at `--core` (no checkout needed)
2. exports `homeassistant/components/unifi` and `homeassistant/strings.json` from that tag
3. packages it as a custom component: adds `"version"` to the manifest and generates
   `translations/en.json` from `strings.json` (core does this at build time)
4. commits the result on the `upstream` branch and tags it `upstream/<ref>`

Afterwards bring it into `main` with:  git merge upstream
Conflicts, if any, are only where our patch touches code that upstream also changed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
COMPONENT = "custom_components/unifi"
CORE_COMPONENT = "homeassistant/components/unifi"
KEY_PREFIX, KEY_SUFFIX = "[%key:", "%]"


def run(*args: str, cwd: Path = REPO, check: bool = True, capture: bool = False) -> str:
    res = subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=capture)
    return (res.stdout or "").strip() if capture else ""


def resolve_refs(node, own: dict, common: dict):
    """Replace every ``[%key:a::b::c%]`` reference with the text it points to."""
    if isinstance(node, dict):
        return {k: resolve_refs(v, own, common) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve_refs(v, own, common) for v in node]
    if isinstance(node, str) and KEY_PREFIX in node:
        out = node
        while KEY_PREFIX in out:
            start = out.index(KEY_PREFIX)
            end = out.index(KEY_SUFFIX, start)
            path = out[start + len(KEY_PREFIX) : end].split("::")
            if path[0] == "common":
                target = common
            elif path[:2] == ["component", "unifi"]:
                target, path = own, path[2:]
                path = ["_root"] + path
            else:
                raise SystemExit(f"unsupported reference: {out[start:end + len(KEY_SUFFIX)]}")
            value = {"_root": own} if path[0] == "_root" else target
            for part in path:
                value = value[part]
            if not isinstance(value, str):
                raise SystemExit(f"reference does not point to text: {out[start:end + len(KEY_SUFFIX)]}")
            value = resolve_refs(value, own, common)
            out = out[:start] + value + out[end + len(KEY_SUFFIX) :]
        return out
    return node


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--core", required=True, type=Path, help="path to a home-assistant/core checkout (any state)")
    parser.add_argument("--ref", required=True, help="core release tag, e.g. 2026.10.0")
    args = parser.parse_args()
    core = args.core.resolve()

    run("git", "fetch", "--depth", "1", "origin", f"refs/tags/{args.ref}:refs/tags/{args.ref}", cwd=core)
    core_sha = run("git", "rev-parse", f"{args.ref}^{{commit}}", cwd=core, capture=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "core.tar"
        run("git", "archive", "-o", str(archive), args.ref, CORE_COMPONENT, "homeassistant/strings.json", cwd=core)
        run("tar", "-xf", str(archive), "-C", str(tmp_path))
        src = tmp_path / CORE_COMPONENT
        common = json.loads((tmp_path / "homeassistant" / "strings.json").read_text(encoding="utf-8"))

        # work in a temporary worktree of the `upstream` branch so main is never touched
        wt = tmp_path / "wt"
        branches = run("git", "branch", "--list", "upstream", capture=True)
        if branches:
            run("git", "worktree", "add", str(wt), "upstream")
        else:
            run("git", "worktree", "add", "--orphan", "-b", "upstream", str(wt))
        try:
            dest = wt / COMPONENT
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))

            manifest_path = dest / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = args.ref  # required for custom integrations
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            strings = json.loads((dest / "strings.json").read_text(encoding="utf-8"))
            translations = resolve_refs(strings, strings, common)
            (dest / "translations").mkdir(exist_ok=True)
            (dest / "translations" / "en.json").write_text(
                json.dumps(translations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            run("git", "add", "-A", cwd=wt)
            status = run("git", "status", "--porcelain", cwd=wt, capture=True)
            if not status:
                print(f"upstream already at {args.ref}; nothing to do")
                return
            run(
                "git",
                "-c", "user.name=upstream-sync",
                "-c", "user.email=upstream-sync@localhost",
                "commit", "-q", "-m",
                f"Upstream: homeassistant/components/unifi @ {args.ref}\n\nhome-assistant/core {core_sha}",
                cwd=wt,
            )
            run("git", "tag", "-f", f"upstream/{args.ref}", cwd=wt)
            print(f"committed upstream/{args.ref} (core {core_sha[:10]})")
        finally:
            run("git", "worktree", "remove", "--force", str(wt), check=False)


if __name__ == "__main__":
    sys.exit(main())
