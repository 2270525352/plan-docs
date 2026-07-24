#!/usr/bin/env python3
# PLAN_DOCS_OWNED v1
"""Staged-snapshot gate for Plan Docs tasks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys


CURRENT_TASK = Path("docs/plan-docs/05-execution/current-task.json")
FEEDBACK = Path("docs/plan-docs/05-execution/执行反馈日志.md")
USER_WORDS = (
    Path("docs/plan-docs/00-source/用户原话.md"),
    Path("docs/用户原话.md"),
)
CONTROL_PATHS = (
    CURRENT_TASK.as_posix(),
    FEEDBACK.as_posix(),
    "CURRENT_STATE.md",
)


def git(root: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
        capture_output=True,
        text=text,
        check=False,
    )


def fail(message: str) -> int:
    sys.stderr.write(f"[plan-docs] commit blocked: {message}\n")
    return 1


def glob_regex(pattern: str) -> re.Pattern[str]:
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/"):
        pattern += "**"
    output: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
            output.append(".*")
            i += 2
        elif char == "*":
            output.append("[^/]*")
            i += 1
        elif char == "?":
            output.append("[^/]")
            i += 1
        else:
            output.append(re.escape(char))
            i += 1
    return re.compile("^" + "".join(output) + "$")


def matches(path: str, patterns: list[str]) -> bool:
    return any(pattern and glob_regex(pattern).match(path) for pattern in patterns)


def staged_paths(root: Path) -> list[str]:
    # Disable rename collapsing so both sides are checked. Otherwise moving a
    # protected source file into an allowed path hides the protected old path.
    result = git(
        root,
        "diff",
        "--cached",
        "--name-only",
        "--no-renames",
        "--diff-filter=ACDMRTUXB",
        "-z",
        text=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def staged_text(root: Path, path: Path) -> str:
    result = git(root, "show", f":{path.as_posix()}")
    return result.stdout if result.returncode == 0 else ""


def valid_new_user_words(blob: bytes) -> bool:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not text.startswith("# 用户原话\n"):
        return False
    matches = list(re.finditer(r"(?m)^## U-(\d{3,})\s*$", text))
    if not matches:
        return text.strip() == "# 用户原话"
    if text[: matches[0].start()].strip() != "# 用户原话":
        return False
    numbers = [int(match.group(1)) for match in matches]
    if numbers != list(range(1, len(numbers) + 1)):
        return False
    for index, match in enumerate(matches):
        record_id = f"U-{int(match.group(1)):03d}"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : end]
        record = re.fullmatch(
            rf"\s*record_id:[ \t]*{re.escape(record_id)}[ \t]*\n"
            r"\s*time:[ \t]*[^\n]+[ \t]*\n"
            r"\s*source:[ \t]*[^\n]+[ \t]*\n"
            r"\s*context:[ \t]*[^\n]+[ \t]*\n"
            r"\s*verbatim:[ \t]*[|>][ \t]*\n"
            r"(?P<verbatim>(?:[ \t]+[^\n]*(?:\n|$))+)\s*",
            block,
        )
        if not record or not record.group("verbatim").strip():
            return False
    return True


def user_words_is_append_only(root: Path, path: Path) -> bool:
    staged = git(root, "show", f":{path.as_posix()}", text=False)
    if staged.returncode != 0:
        return False
    head = git(root, "show", f"HEAD:{path.as_posix()}", text=False)
    if head.returncode != 0:
        return valid_new_user_words(staged.stdout)
    return staged.stdout.startswith(head.stdout) and valid_new_user_words(staged.stdout)


def run_commands(root: Path, commands: list[str], label: str) -> int:
    for command in commands:
        if not command.strip():
            continue
        sys.stderr.write(f"[plan-docs] running {label}: {command}\n")
        result = subprocess.run(command, cwd=root, shell=True, check=False)
        if result.returncode != 0:
            return fail(f"{label} failed: {command}")
    return 0


def main() -> int:
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if root_result.returncode != 0:
        return 0
    root = Path(root_result.stdout.strip()).resolve()
    paths = staged_paths(root)
    current_path = root / CURRENT_TASK
    current = (
        json.loads(current_path.read_text(encoding="utf-8"))
        if current_path.exists()
        else {}
    )
    for user_words_path in USER_WORDS:
        user_words_name = user_words_path.as_posix()
        if user_words_name not in paths:
            continue
        if not user_words_is_append_only(root, user_words_path):
            return fail(
                f"{user_words_name} is strict append-only; "
                "the staged blob must preserve the entire HEAD blob as an exact byte prefix"
            )
        head = git(root, "show", f"HEAD:{user_words_name}", text=False)
        if head.returncode != 0 and not re.search(
            r"(?m)^## U-\d{3,}\s*$",
            staged_text(root, user_words_path),
        ):
            # A bootstrap may commit only the validated empty record set.
            continue
        if not current.get("allow_user_words_append", False):
            return fail(
                f"{user_words_name} append requires an activated intake task "
                "with allow_user_words_append=true"
            )
        allowed = current.get("allowed_scope") or []
        locks = current.get("write_lock") or []
        if user_words_name not in allowed or user_words_name not in locks:
            return fail(
                f"{user_words_name} append requires its exact path in "
                "allowed_scope and write_lock"
            )

    protected_names = {path.as_posix() for path in USER_WORDS}
    business = [
        path
        for path in paths
        if path not in CONTROL_PATHS and path not in protected_names
    ]
    if not business:
        return 0
    if not current_path.exists():
        return fail(f"business files are staged but {CURRENT_TASK.as_posix()} is missing")
    task_id = str(current.get("task_id") or "").strip()
    if not task_id:
        return fail("business files are staged but task_id is empty")

    owner = str(current.get("owner") or "").strip()
    allow = current.get("allowed_scope") or []
    forbid = current.get("forbidden_scope") or []
    protected = current.get("protected_append_only") or []
    locks = current.get("write_lock") or []
    verification_commands = current.get("verification_commands") or []
    test_commands = current.get("test_commands") or []
    stop_conditions = str(current.get("stop_conditions") or "").strip()
    if not owner:
        return fail(f"{task_id} has no owner")
    if not isinstance(allow, list) or not allow:
        return fail(f"{task_id} has no allowed_scope")
    if not isinstance(forbid, list) or not forbid:
        return fail(f"{task_id} has no forbidden_scope")
    if not isinstance(locks, list) or not locks:
        return fail(f"{task_id} has no write_lock")
    if not isinstance(verification_commands, list) or not verification_commands:
        return fail(f"{task_id} has no verification_commands")
    if not isinstance(test_commands, list) or not test_commands:
        return fail(f"{task_id} has no test_commands; use an explicit N/A command with a reason")
    if not stop_conditions:
        return fail(f"{task_id} has no stop_conditions")
    for path in business:
        if matches(path, protected):
            return fail(f"{path} is protected append-only source")
        if matches(path, forbid):
            return fail(f"{path} is in forbidden scope for {task_id}")
        if not matches(path, allow):
            return fail(f"{path} is outside allowed scope for {task_id}")
        if not matches(path, locks):
            return fail(f"{path} is outside this task's write lock")

    feedback_id = str(current.get("feedback_record") or "").strip()
    if not feedback_id:
        return fail(f"{task_id} has no feedback_record ID")
    if FEEDBACK.as_posix() not in paths:
        return fail(f"{FEEDBACK.as_posix()} must be staged with business changes")
    feedback = staged_text(root, FEEDBACK)
    if not re.search(
        rf"(?m)^feedback_id:[ \t]*{re.escape(feedback_id)}[ \t]*$",
        feedback,
    ):
        return fail(f"staged feedback does not contain exact feedback_id {feedback_id}")
    if not re.search(
        rf"(?m)^task_id:[ \t]*{re.escape(task_id)}[ \t]*$",
        feedback,
    ):
        return fail(f"staged feedback does not contain exact task_id {task_id}")

    unstaged = git(root, "diff", "--quiet")
    if unstaged.returncode != 0:
        return fail("unstaged tracked changes exist; tests would not represent the staged snapshot")
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z", text=False)
    untracked_paths = [
        item.decode("utf-8", errors="surrogateescape")
        for item in untracked.stdout.split(b"\0")
        if item and item.decode("utf-8", errors="surrogateescape") not in paths
    ]
    if any(path not in CONTROL_PATHS for path in untracked_paths):
        return fail("unstaged untracked business files exist; stage, ignore, or remove them before testing")

    result = run_commands(root, verification_commands, "verification")
    if result:
        return result
    return run_commands(root, test_commands, "test")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit(f"[plan-docs] commit blocked after guard error: {exc}")
