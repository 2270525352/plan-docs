#!/usr/bin/env python3
# PLAN_DOCS_OWNED v1
"""Claude Stop hook requiring an exact feedback record for active business work."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


CURRENT_TASK = Path("docs/plan-docs/05-execution/current-task.json")
FEEDBACK = Path("docs/plan-docs/05-execution/执行反馈日志.md")


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0
    root = Path(
        os.environ.get("CLAUDE_PROJECT_DIR")
        or payload.get("cwd")
        or os.getcwd()
    ).resolve()
    current_path = root / CURRENT_TASK
    if not current_path.exists():
        return 0
    current = json.loads(current_path.read_text(encoding="utf-8"))
    task_id = str(current.get("task_id") or "").strip()
    feedback_id = str(current.get("feedback_record") or "").strip()
    if not task_id:
        return 0

    status = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotePath=false", "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        return 0
    control_prefixes = (
        "docs/plan-docs/",
        ".plan-docs/",
        ".githooks/",
        ".claude/settings.json",
        "AGENTS.md",
        "CURRENT_STATE.md",
    )
    business = []
    for line in status.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path and not path.startswith(control_prefixes):
            business.append(path)
    if not business:
        return 0
    if not feedback_id:
        sys.stderr.write(f"[plan-docs] {task_id} has business changes but no feedback_record ID.\n")
        return 2

    feedback_path = root / FEEDBACK
    feedback = feedback_path.read_text(encoding="utf-8") if feedback_path.exists() else ""
    id_ok = re.search(
        rf"(?m)^feedback_id:[ \t]*{re.escape(feedback_id)}[ \t]*$",
        feedback,
    )
    task_ok = re.search(
        rf"(?m)^task_id:[ \t]*{re.escape(task_id)}[ \t]*$",
        feedback,
    )
    if id_ok and task_ok:
        return 0
    sys.stderr.write(
        f"[plan-docs] stop blocked once: add exact feedback_id {feedback_id} "
        f"and task_id {task_id} to {FEEDBACK.as_posix()}.\n"
    )
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"[plan-docs] feedback stop check skipped after internal error: {exc}\n")
        raise SystemExit(0)
