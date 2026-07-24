#!/usr/bin/env python3
# PLAN_DOCS_OWNED v1
"""Claude write-scope guard for active Plan Docs tasks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys


CURRENT_TASK = Path("docs/plan-docs/05-execution/current-task.json")


def glob_regex(pattern: str) -> re.Pattern[str]:
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/"):
        pattern += "**"
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
            parts.append(".*")
            i += 2
        elif char == "*":
            parts.append("[^/]*")
            i += 1
        elif char == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(char))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def matching(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if pattern and glob_regex(pattern).match(path):
            return pattern
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}
    raw_target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_target:
        return 0

    root = Path(
        os.environ.get("CLAUDE_PROJECT_DIR")
        or payload.get("cwd")
        or os.getcwd()
    ).resolve()
    raw_path = Path(raw_target)
    target = (raw_path if raw_path.is_absolute() else root / raw_path).resolve()
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError:
        sys.stderr.write("[plan-docs] blocked: target path escapes the project root.\n")
        return 2

    current_path = root / CURRENT_TASK
    if not current_path.exists():
        return 0
    current = json.loads(current_path.read_text(encoding="utf-8"))
    task_id = str(current.get("task_id") or "").strip()
    if not task_id:
        return 0

    protected = current.get("protected_append_only") or []
    protected_hit = matching(relative, protected)
    if protected_hit and not current.get("allow_user_words_append", False):
        sys.stderr.write(
            f"[plan-docs] blocked: {relative} is append-only source material ({protected_hit}). "
            "Use a dedicated intake task and enable allow_user_words_append; staged diff will still reject rewrites.\n"
        )
        return 2

    forbidden_hit = matching(relative, current.get("forbidden_scope") or [])
    if forbidden_hit:
        sys.stderr.write(
            f"[plan-docs] blocked: {relative} matches forbidden scope {forbidden_hit} for {task_id}.\n"
        )
        return 2

    allowed = current.get("allowed_scope") or []
    if not allowed:
        sys.stderr.write(
            f"[plan-docs] blocked: {task_id} has no allowed_scope; activate a complete task contract first.\n"
        )
        return 2
    if not matching(relative, allowed):
        sys.stderr.write(
            f"[plan-docs] blocked: {relative} is outside allowed scope for {task_id}: "
            + ", ".join(allowed)
            + "\n"
        )
        return 2

    locks = current.get("write_lock") or []
    if locks and not matching(relative, locks) and not protected_hit:
        sys.stderr.write(
            f"[plan-docs] blocked: {relative} is not owned by this task's write lock: "
            + ", ".join(locks)
            + "\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail open so a broken hook does not brick the project
        sys.stderr.write(f"[plan-docs] scope guard skipped after internal error: {exc}\n")
        raise SystemExit(0)
