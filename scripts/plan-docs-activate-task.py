#!/usr/bin/env python3
"""Activate one structured Markdown task into current-task.json."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


FIELDS = (
    "task_id",
    "phase",
    "owner",
    "source_user_words",
    "requirement_ids",
    "change_refs",
    "input_docs",
    "dependencies",
    "allowed_scope",
    "forbidden_scope",
    "shared_interfaces",
    "input_contracts",
    "output_contracts",
    "merge_order",
    "conflict_resolution",
    "exact_steps",
    "expected_outputs",
    "acceptance_criteria",
    "verification_commands",
    "test_commands",
    "write_lock",
    "git_checkpoint",
    "feedback_record",
    "stop_conditions",
    "status",
)
LIST_FIELDS = {
    "source_user_words",
    "requirement_ids",
    "change_refs",
    "input_docs",
    "dependencies",
    "allowed_scope",
    "forbidden_scope",
    "shared_interfaces",
    "input_contracts",
    "output_contracts",
    "exact_steps",
    "expected_outputs",
    "verification_commands",
    "test_commands",
    "write_lock",
}
REQUIRED_NONEMPTY = {
    "task_id",
    "phase",
    "owner",
    "source_user_words",
    "requirement_ids",
    "change_refs",
    "input_docs",
    "allowed_scope",
    "forbidden_scope",
    "input_contracts",
    "output_contracts",
    "merge_order",
    "conflict_resolution",
    "exact_steps",
    "expected_outputs",
    "acceptance_criteria",
    "verification_commands",
    "test_commands",
    "write_lock",
    "git_checkpoint",
    "feedback_record",
    "stop_conditions",
    "status",
}
CURRENT_TASK = Path("docs/plan-docs/05-execution/current-task.json")
TOTAL_TASKS = Path("docs/plan-docs/04-tasks/总任务文档.md")
SUPPORTED_TASK_DOCUMENTS = {
    "Claude任务文档.md",
    "Codex任务文档.md",
    "Reviewer（Claude）任务文档.md",
    "OpenCode任务文档.md",
}


class ActivationError(RuntimeError):
    pass


def find_task_block(text: str, task_id: str) -> str:
    headings = list(
        re.finditer(r"(?m)^#{2,6}\s+(TASK-[A-Za-z0-9-]+)\s*$", text)
    )
    for index, heading in enumerate(headings):
        if heading.group(1) != task_id:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        return text[heading.end() : end]
    raise ActivationError(f"task heading not found: {task_id}")


def raw_field(block: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:[ \t]*(.*)$", block)
    if not match:
        return ""
    inline = match.group(1).strip()
    if inline:
        return inline
    following = block[match.end() :]
    next_field = re.search(r"(?m)^[a-z][a-z0-9_]*:\s*", following)
    return following[: next_field.start() if next_field else len(following)].strip()


def parse_list(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw or raw == "[]":
        return []
    if raw.startswith("[") and raw.endswith("]"):
        inside = raw[1:-1].strip()
        if not inside:
            return []
        return [item.strip().strip("'\"") for item in inside.split(",") if item.strip()]
    values: list[str] = []
    for line in raw.splitlines():
        match = re.match(r"\s*(?:-\s+|\d+[.)]\s*)(.+?)\s*$", line)
        if match and match.group(1).strip():
            values.append(match.group(1).strip())
    return values


def parse_task(text: str, task_id: str) -> dict[str, object]:
    block = find_task_block(text, task_id)
    task: dict[str, object] = {}
    for field in FIELDS:
        raw = raw_field(block, field)
        task[field] = parse_list(raw) if field in LIST_FIELDS else raw.strip()
    missing = [
        field
        for field in sorted(REQUIRED_NONEMPTY)
        if not task.get(field)
    ]
    if task.get("task_id") != task_id:
        missing.append(f"task_id must equal {task_id}")
    if missing:
        raise ActivationError("task contract is incomplete: " + ", ".join(missing))
    return task


def top_level_field(text: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:[ \t]*(.+?)[ \t]*$", text)
    return match.group(1).strip() if match else ""


def atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def activate(
    project: Path,
    task_document: Path,
    task_id: str,
    allow_user_words_append: bool,
) -> int:
    project = project.resolve()
    document = task_document if task_document.is_absolute() else project / task_document
    document = document.resolve()
    task_directory = (project / "docs/plan-docs/04-tasks").resolve()
    try:
        document.relative_to(task_directory)
    except ValueError as exc:
        raise ActivationError("task document must be inside docs/plan-docs/04-tasks") from exc
    if document.parent != task_directory or document.name not in SUPPORTED_TASK_DOCUMENTS:
        raise ActivationError(
            "task document must be a supported canonical AI task document"
        )
    text = document.read_text(encoding="utf-8")
    task = parse_task(text, task_id)
    if task["status"] != "ready":
        raise ActivationError(
            f"task status must be ready before activation, got {task['status']!r}"
        )
    coordinator = top_level_field(text, "coordinator")
    merge_authority = top_level_field(text, "merge_authority")
    if not coordinator or not merge_authority:
        raise ActivationError(
            "task document must name coordinator and merge_authority before activation"
        )
    total_path = project / TOTAL_TASKS
    total_task = parse_task(total_path.read_text(encoding="utf-8"), task_id)
    mismatched = [
        field for field in FIELDS if task.get(field) != total_task.get(field)
    ]
    if mismatched:
        raise ActivationError(
            "AI task differs from 总任务文档.md: " + ", ".join(mismatched)
        )
    allowed_scope = task["allowed_scope"]
    assert isinstance(allowed_scope, list)
    if allow_user_words_append:
        if task["phase"] != "intake":
            raise ActivationError(
                "--allow-user-words-append is restricted to a canonical intake task"
            )
        protected_paths = {
            "docs/plan-docs/00-source/用户原话.md",
            "docs/用户原话.md",
        }
        write_lock = task["write_lock"]
        assert isinstance(write_lock, list)
        authorized_paths = protected_paths.intersection(allowed_scope)
        if not authorized_paths or not authorized_paths.intersection(write_lock):
            raise ActivationError(
                "--allow-user-words-append requires the exact user-words path "
                "in both allowed_scope and write_lock"
            )
        if set(allowed_scope) - protected_paths or set(write_lock) - protected_paths:
            raise ActivationError(
                "an intake append task may lock only an exact user-words path"
            )
    else:
        audit_script = Path(__file__).with_name("plan-docs-audit.py")
        result = subprocess.run(
            [
                sys.executable,
                str(audit_script),
                "--project",
                str(project),
                "--require-gate-ready",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stdout.strip() or result.stderr.strip()
            raise ActivationError(
                "automatic-mode gate is not ready; activation refused"
                + (f": {detail}" if detail else "")
            )
    runtime = {
        "task_id": task_id,
        "phase": task["phase"],
        "owner": task["owner"],
        "coordinator": coordinator,
        "merge_authority": merge_authority,
        "allowed_scope": task["allowed_scope"],
        "forbidden_scope": task["forbidden_scope"],
        "protected_append_only": [
            "docs/plan-docs/00-source/用户原话.md",
            "docs/用户原话.md",
        ],
        "allow_user_words_append": allow_user_words_append,
        "write_lock": task["write_lock"],
        "shared_interfaces": task["shared_interfaces"],
        "input_contracts": task["input_contracts"],
        "output_contracts": task["output_contracts"],
        "merge_order": task["merge_order"],
        "conflict_resolution": task["conflict_resolution"],
        "verification_commands": task["verification_commands"],
        "test_commands": task["test_commands"],
        "feedback_record": task["feedback_record"],
        "stop_conditions": task["stop_conditions"],
        "updated_at": "",
    }
    destination = project / CURRENT_TASK
    atomic_json(destination, runtime)
    print(f"[plan-docs] activated {task_id} from {document}")
    print(f"[plan-docs] wrote {destination}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-doc", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--allow-user-words-append", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    arguments = parse_args(sys.argv[1:])
    try:
        raise SystemExit(
            activate(
                Path(arguments.project),
                Path(arguments.task_doc),
                arguments.task_id,
                arguments.allow_user_words_append,
            )
        )
    except (ActivationError, OSError) as exc:
        print(f"[plan-docs] activation error: {exc}", file=sys.stderr)
        raise SystemExit(2)
