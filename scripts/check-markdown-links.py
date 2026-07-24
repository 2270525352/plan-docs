#!/usr/bin/env python3
"""Check local Markdown links inside the skill repository."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote


LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
STRUCTURED_REF_RE = re.compile(
    r"(?m)^(?:contract_ref|[A-Za-z0-9_]+_ref):\s*(\S+)\s*$"
)


def check(root: Path) -> int:
    errors: list[str] = []
    for markdown in sorted(root.rglob("*.md")):
        if ".git" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = raw.strip().split(maxsplit=1)[0].strip("<>")
            if (
                not target
                or target.startswith(("#", "http://", "https://", "mailto:"))
                or "<" in target
                or ">" in target
            ):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if not path_text:
                continue
            destination = (markdown.parent / path_text).resolve()
            if not destination.exists():
                errors.append(
                    f"{markdown.relative_to(root)} -> {target} (missing {destination})"
                )
        for target in STRUCTURED_REF_RE.findall(text):
            if (
                not target
                or target.startswith(("http://", "https://"))
                or target in ("[]", "{}")
                or "<" in target
                or ">" in target
            ):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if not path_text:
                continue
            destination = (markdown.parent / path_text).resolve()
            if not destination.exists():
                errors.append(
                    f"{markdown.relative_to(root)} structured ref -> {target} "
                    f"(missing {destination})"
                )
    if errors:
        print("[plan-docs] Markdown link check: FAILED")
        for error in errors:
            print(f"  error: {error}")
        return 1
    print("[plan-docs] Markdown link check: OK")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    raise SystemExit(check(Path(args.root).resolve()))
