#!/usr/bin/env python3
"""Safely bootstrap Plan Docs coordination files and planning tree."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = SKILL_ROOT / "templates" / "bootstrap"
TREE = SKILL_ROOT / "templates" / "project-tree"
START = "<!-- PLAN_DOCS_START -->"
END = "<!-- PLAN_DOCS_END -->"
BLOCK_RE = re.compile(rf"{re.escape(START)}.*?{re.escape(END)}", re.DOTALL)
STATE_START = "<!-- PLAN_DOCS_STATE_START -->"
STATE_END = "<!-- PLAN_DOCS_STATE_END -->"
STATE_BLOCK_RE = re.compile(
    rf"{re.escape(STATE_START)}.*?{re.escape(STATE_END)}",
    re.DOTALL,
)
BASE_TREE_DIRS = {
    "00-source",
    "01-requirements",
    "02-architecture",
    "03-product",
    "04-tasks",
    "05-execution",
    "06-reviews",
    "09-git",
    "10-guards",
}
ALL_TREE_DIRS = BASE_TREE_DIRS | {"07-goals", "08-automation"}


class BootstrapError(RuntimeError):
    pass


def normalized(text: str) -> str:
    return text.rstrip() + "\n"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(normalized(text))
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = path.with_name(f"{path.name}.plan-docs.{stamp}.bak")
    shutil.copy2(path, destination)
    return destination


def marker_state(text: str) -> str:
    starts = text.count(START)
    ends = text.count(END)
    matches = len(BLOCK_RE.findall(text))
    if starts == ends == matches == 0:
        return "absent"
    if starts == ends == matches == 1:
        return "valid"
    raise BootstrapError(
        "AGENTS.md contains duplicate or incomplete PLAN_DOCS markers; "
        "repair them manually before bootstrap to avoid data loss"
    )


def template_block() -> str:
    template = (BOOTSTRAP / "AGENTS.md").read_text(encoding="utf-8")
    if marker_state(template) != "valid":
        raise BootstrapError("bootstrap AGENTS template has invalid PLAN_DOCS markers")
    match = BLOCK_RE.search(template)
    assert match
    return match.group(0)


def state_marker_state(text: str) -> str:
    starts = text.count(STATE_START)
    ends = text.count(STATE_END)
    matches = len(STATE_BLOCK_RE.findall(text))
    if starts == ends == matches == 0:
        return "absent"
    if starts == ends == matches == 1:
        return "valid"
    raise BootstrapError(
        "CURRENT_STATE.md contains duplicate or incomplete PLAN_DOCS_STATE markers; "
        "repair them manually before bootstrap to avoid data loss"
    )


def template_state_block() -> str:
    template = (BOOTSTRAP / "CURRENT_STATE.md").read_text(encoding="utf-8")
    if state_marker_state(template) != "valid":
        raise BootstrapError("CURRENT_STATE template has invalid PLAN_DOCS_STATE markers")
    match = STATE_BLOCK_RE.search(template)
    assert match
    return match.group(0)


def merge_agents(project: Path) -> str:
    destination = project / "AGENTS.md"
    template = normalized((BOOTSTRAP / "AGENTS.md").read_text(encoding="utf-8"))
    if not destination.exists():
        atomic_write(destination, template)
        return "created AGENTS.md"

    existing = normalized(destination.read_text(encoding="utf-8"))
    state = marker_state(existing)
    if state == "valid":
        merged = normalized(BLOCK_RE.sub(template_block(), existing, count=1))
    else:
        merged = normalized(existing.rstrip() + "\n\n" + template_block())
    if merged == existing:
        return "AGENTS.md unchanged"
    saved = backup(destination)
    atomic_write(destination, merged)
    return f"updated only PLAN_DOCS block in AGENTS.md (backup: {saved.name})"


def merge_current_state(project: Path, append_log: bool) -> str:
    destination = project / "CURRENT_STATE.md"
    template = normalized((BOOTSTRAP / "CURRENT_STATE.md").read_text(encoding="utf-8"))
    if not destination.exists():
        merged = template
        action = "created CURRENT_STATE.md"
        existing = ""
    else:
        existing = normalized(destination.read_text(encoding="utf-8"))
        state = state_marker_state(existing)
        if state == "valid":
            merged = existing
            action = "preserved existing PLAN_DOCS_STATE block"
        else:
            merged = normalized(existing.rstrip() + "\n\n" + template_state_block())
            action = "appended PLAN_DOCS_STATE block to CURRENT_STATE.md"

    if append_log:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        record = (
            f"\n\n### STATE-BOOTSTRAP-{stamp}\n\n"
            f"time: {stamp}\n\n"
            "actor: Plan Docs bootstrap\n\n"
            "event: bootstrap\n\n"
            "summary: Bootstrap was explicitly recorded after preserving existing state.\n\n"
            "files: [AGENTS.md, CURRENT_STATE.md]\n\n"
            "verification: refresh the current snapshot before execution\n\n"
            "next: continue requirement planning\n"
        )
        merged = normalized(merged.rstrip() + record)
        action += " and appended a unique bootstrap log"

    if existing and merged == existing:
        return "CURRENT_STATE.md unchanged"
    saved = backup(destination) if destination.exists() else None
    atomic_write(destination, merged)
    if saved:
        action += f" (backup: {saved.name})"
    return action


def init_tree(project: Path, include_opencode: bool) -> tuple[int, int]:
    destination_root = project / "docs" / "plan-docs"
    for source_dir in sorted(path for path in TREE.iterdir() if path.is_dir()):
        (destination_root / source_dir.name).mkdir(parents=True, exist_ok=True)
    created = 0
    preserved = 0
    for source in sorted(TREE.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(TREE)
        if relative.parts[0] not in BASE_TREE_DIRS:
            continue
        if relative.name == "OpenCode任务文档.md" and not include_opencode:
            continue
        destination = destination_root / relative
        if destination.exists():
            preserved += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        created += 1
    return created, preserved


def install(project: Path, append_state_log: bool, init_docs: bool, include_opencode: bool) -> int:
    project = project.resolve()
    if not project.is_dir():
        raise BootstrapError(f"project directory not found: {project}")
    print(f"[plan-docs] project: {project}")
    print(f"[plan-docs] {merge_agents(project)}")
    print(f"[plan-docs] {merge_current_state(project, append_state_log)}")
    if init_docs:
        created, preserved = init_tree(project, include_opencode)
        print(f"[plan-docs] planning tree: created {created}, preserved {preserved}")
        print("[plan-docs] final goals/automation were not created; generate them only after the gate is READY")
    return 0


def verify(project: Path, require_tree: bool) -> int:
    project = project.resolve()
    errors: list[str] = []
    agents = project / "AGENTS.md"
    state = project / "CURRENT_STATE.md"
    if not agents.exists():
        errors.append("missing AGENTS.md")
    else:
        try:
            if marker_state(agents.read_text(encoding="utf-8")) != "valid":
                errors.append("invalid PLAN_DOCS block")
        except BootstrapError as exc:
            errors.append(str(exc))
    if not state.exists():
        errors.append("missing CURRENT_STATE.md")
    else:
        try:
            state_text = state.read_text(encoding="utf-8")
            if state_marker_state(state_text) != "valid":
                errors.append("invalid PLAN_DOCS_STATE block")
            for field in (
                "plan_docs_schema:",
                "project_mode:",
                "brownfield_scope:",
                "current_phase:",
                "current_task:",
                "current_owner:",
                "task_started_at:",
                "last_progress_at:",
                "last_progress_kind:",
                "locked_files:",
                "completed_work:",
                "latest_commit:",
                "blockers:",
                "next_step:",
            ):
                if field not in state_text:
                    errors.append(f"CURRENT_STATE.md missing field {field}")
        except BootstrapError as exc:
            errors.append(str(exc))
    if require_tree:
        for directory in sorted(ALL_TREE_DIRS):
            if not (project / "docs" / "plan-docs" / directory).is_dir():
                errors.append(f"missing docs/plan-docs/{directory}/")
    if errors:
        print("[plan-docs] bootstrap verification: FAILED")
        for error in errors:
            print(f"  error: {error}")
        return 1
    print("[plan-docs] bootstrap verification: OK")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--project", required=True)
    install_parser.add_argument(
        "--append-state-log",
        action="store_true",
        help="explicitly append a unique bootstrap event to an existing CURRENT_STATE.md",
    )
    install_parser.add_argument(
        "--init-tree",
        action="store_true",
        help="copy missing planning templates, excluding final goals and automation",
    )
    install_parser.add_argument(
        "--include-opencode",
        action="store_true",
        help="with --init-tree, include OpenCode task docs after the user selects OpenCode",
    )
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project", required=True)
    verify_parser.add_argument("--require-tree", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.command == "install":
            return install(
                Path(args.project),
                append_state_log=args.append_state_log,
                init_docs=args.init_tree,
                include_opencode=args.include_opencode,
            )
        return verify(Path(args.project), require_tree=args.require_tree)
    except (BootstrapError, OSError) as exc:
        print(f"[plan-docs] bootstrap error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
