#!/usr/bin/env python3
"""Install, verify, or uninstall conservative Plan Docs guardrails."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL_ROOT / "templates" / "guards"
HOOK_NAMES = ("pre-commit", "commit-msg", "pre-push")
PYTHON_NAMES = ("scope_guard.py", "feedback_stop_check.py", "pre_commit.py")
OWNED_HEADER = "# PLAN_DOCS_OWNED v1"
MANIFEST = Path(".plan-docs/install-manifest.json")
CURRENT_TASK = Path("docs/plan-docs/05-execution/current-task.json")


class GuardError(RuntimeError):
    pass


def run_git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def is_git_repo(project: Path) -> bool:
    return run_git(project, "rev-parse", "--show-toplevel").returncode == 0


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GuardError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GuardError(f"expected a JSON object in {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
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


def backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = path.with_name(f"{path.name}.plan-docs.{stamp}.bak")
    shutil.copy2(path, destination)
    return destination


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def is_owned(path: Path) -> bool:
    if not path.exists():
        return False
    first_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:3]
    return OWNED_HEADER in first_lines


def copy_owned(source: Path, destination: Path, force_owned: bool) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source.read_bytes() == destination.read_bytes():
            return "unchanged"
        if not (force_owned and is_owned(destination)):
            raise GuardError(
                f"refusing to overwrite {destination}; rerun with --force-owned only if it is Plan Docs-owned"
            )
        backup(destination)
    shutil.copy2(source, destination)
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return "written"


def merged_settings(project: Path) -> tuple[dict[str, Any], bool]:
    destination = project / ".claude/settings.json"
    existing = load_json(destination)
    incoming = load_json(TEMPLATES / "settings.hooks.json")
    hooks = existing.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise GuardError(f"{destination} hooks must be a JSON object")
    changed = False
    for event, entries in (incoming.get("hooks") or {}).items():
        if not isinstance(entries, list):
            raise GuardError(f"incoming hooks.{event} must be a list")
        current = hooks.setdefault(event, [])
        if not isinstance(current, list):
            raise GuardError(f"{destination} hooks.{event} must be a list")
        seen = {canonical(item) for item in current}
        for entry in entries:
            key = canonical(entry)
            if key not in seen:
                current.append(entry)
                seen.add(key)
                changed = True
    return existing, changed or not destination.exists()


def write_settings(project: Path, settings: dict[str, Any], changed: bool) -> None:
    if not changed:
        print("[plan-docs] unchanged: .claude/settings.json")
        return
    destination = project / ".claude/settings.json"
    if destination.exists():
        saved = backup(destination)
        print(f"[plan-docs] backup: {saved.relative_to(project)}")
    atomic_json(destination, settings)
    print("[plan-docs] merged: .claude/settings.json")


def remove_settings(project: Path) -> bool:
    destination = project / ".claude/settings.json"
    if not destination.exists():
        return False
    existing = load_json(destination)
    incoming = load_json(TEMPLATES / "settings.hooks.json")
    hooks = existing.get("hooks")
    if not isinstance(hooks, dict):
        return False
    changed = False
    for event, entries in (incoming.get("hooks") or {}).items():
        current = hooks.get(event)
        if not isinstance(current, list):
            continue
        remove = {canonical(item) for item in entries}
        kept = [item for item in current if canonical(item) not in remove]
        if kept != current:
            changed = True
            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event, None)
    if hooks == {}:
        existing.pop("hooks", None)
    if changed:
        backup(destination)
        atomic_json(destination, existing)
    return changed


def active_default_hooks(project: Path) -> list[Path]:
    result = run_git(project, "rev-parse", "--git-path", "hooks")
    if result.returncode != 0 or not result.stdout.strip():
        return []
    directory = Path(result.stdout.strip())
    if not directory.is_absolute():
        directory = project / directory
    if not directory.is_dir():
        return []
    return [
        path
        for path in directory.iterdir()
        if path.is_file() and not path.name.endswith(".sample") and path.stat().st_size > 0
    ]


def is_linked_worktree(project: Path) -> bool:
    git_dir_result = run_git(project, "rev-parse", "--git-dir")
    common_dir_result = run_git(project, "rev-parse", "--git-common-dir")
    if git_dir_result.returncode != 0 or common_dir_result.returncode != 0:
        return False
    git_dir = Path(git_dir_result.stdout.strip())
    common_dir = Path(common_dir_result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = project / git_dir
    if not common_dir.is_absolute():
        common_dir = project / common_dir
    return git_dir.resolve() != common_dir.resolve()


def template_copy_plan(project: Path) -> list[tuple[Path, Path]]:
    plan: list[tuple[Path, Path]] = []
    for name in PYTHON_NAMES:
        plan.append((TEMPLATES / "hooks" / name, project / ".plan-docs/hooks" / name))
    for name in HOOK_NAMES:
        plan.append((TEMPLATES / "githooks" / name, project / ".plan-docs/git-hooks" / name))
    return plan


def preflight_copy(plan: list[tuple[Path, Path]], force_owned: bool) -> None:
    conflicts: list[str] = []
    for source, destination in plan:
        if not source.exists():
            conflicts.append(f"missing template {source}")
        elif destination.exists() and source.read_bytes() != destination.read_bytes():
            if not (force_owned and is_owned(destination)):
                conflicts.append(f"existing non-matching file {destination}")
    if conflicts:
        raise GuardError("preflight failed; no guard files changed:\n- " + "\n- ".join(conflicts))


def integrate_git_hooks(project: Path, force_owned: bool) -> tuple[str, list[tuple[Path, Path]]]:
    if not is_git_repo(project):
        return "not-a-git-repo", []
    configured = run_git(project, "config", "--get", "core.hooksPath")
    hooks_path = configured.stdout.strip() if configured.returncode == 0 else ""
    wrappers = [
        (TEMPLATES / "githooks" / name, project / ".githooks" / name)
        for name in HOOK_NAMES
    ]
    if hooks_path and hooks_path != ".githooks":
        return f"pending-existing-hooksPath:{hooks_path}", []
    if not hooks_path and is_linked_worktree(project):
        return "pending-linked-worktree-shared-git-config", []
    if not hooks_path and active_default_hooks(project):
        return "pending-existing-dot-git-hooks", []
    conflicts = [
        destination
        for source, destination in wrappers
        if destination.exists()
        and source.read_bytes() != destination.read_bytes()
        and not (force_owned and is_owned(destination))
    ]
    if conflicts:
        return "pending-existing-githooks-files", []
    return "active-.githooks", wrappers


def install(project: Path, force_owned: bool) -> int:
    project = project.resolve()
    if not project.is_dir():
        raise GuardError(f"project not found: {project}")

    # Parse and validate settings before touching any file.
    settings, settings_changed = merged_settings(project)
    base_plan = template_copy_plan(project)
    preflight_copy(base_plan, force_owned)
    integration, wrappers = integrate_git_hooks(project, force_owned)
    preflight_copy(wrappers, force_owned)

    print(f"[plan-docs] project: {project}")
    installed: list[str] = []
    for source, destination in base_plan + wrappers:
        result = copy_owned(source, destination, force_owned)
        print(f"[plan-docs] {result}: {destination.relative_to(project)}")
        installed.append(destination.relative_to(project).as_posix())

    write_settings(project, settings, settings_changed)

    current_task = project / CURRENT_TASK
    if not current_task.exists():
        source = SKILL_ROOT / "templates/project-tree/05-execution/current-task.json"
        current_task.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, current_task)
        print(f"[plan-docs] written: {CURRENT_TASK}")
    else:
        print(f"[plan-docs] preserved: {CURRENT_TASK}")

    if integration == "active-.githooks":
        configured = run_git(project, "config", "--get", "core.hooksPath")
        if configured.returncode != 0 or not configured.stdout.strip():
            result = run_git(project, "config", "core.hooksPath", ".githooks")
            if result.returncode != 0:
                raise GuardError(f"failed to set core.hooksPath: {result.stderr.strip()}")
        print("[plan-docs] git hooks active via core.hooksPath=.githooks")
    else:
        print(f"[plan-docs] git hook integration pending: {integration}")
        print("[plan-docs] existing hooks were preserved; chain .plan-docs/git-hooks explicitly")

    manifest = {
        "version": 1,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "git_integration": integration,
        "files": {
            relative: digest(project / relative)
            for relative in installed
            if (project / relative).exists()
        },
    }
    atomic_json(project / MANIFEST, manifest)
    return 0


def settings_has_entries(project: Path) -> list[str]:
    errors: list[str] = []
    settings = load_json(project / ".claude/settings.json")
    incoming = load_json(TEMPLATES / "settings.hooks.json")
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return ["missing .claude/settings.json hooks object"]
    for event, entries in (incoming.get("hooks") or {}).items():
        current = hooks.get(event)
        keys = {canonical(item) for item in current} if isinstance(current, list) else set()
        for entry in entries:
            if canonical(entry) not in keys:
                errors.append(f"missing Plan Docs Claude hook entry: {event}")
    return errors


def effective_hooks_directory(project: Path, hooks_path: str) -> Path | None:
    if hooks_path:
        directory = Path(hooks_path)
        return directory if directory.is_absolute() else project / directory
    result = run_git(project, "rev-parse", "--git-path", "hooks")
    if result.returncode != 0 or not result.stdout.strip():
        return None
    directory = Path(result.stdout.strip())
    return directory if directory.is_absolute() else project / directory


def chained_hooks_verified(project: Path, hooks_path: str) -> list[str]:
    directory = effective_hooks_directory(project, hooks_path)
    if directory is None:
        return ["cannot resolve the active Git hooks directory"]
    errors: list[str] = []
    for name in HOOK_NAMES:
        hook = directory / name
        if not hook.exists():
            errors.append(f"existing hook manager is missing {hook}")
            continue
        if not os.access(hook, os.X_OK):
            errors.append(f"existing chained hook is not executable: {hook}")
        text = hook.read_text(encoding="utf-8", errors="ignore")
        expected = f".plan-docs/git-hooks/{name}"
        visible_calls = [
            line for line in text.splitlines()
            if expected in line and not line.lstrip().startswith("#")
        ]
        if not visible_calls:
            errors.append(f"{hook} does not visibly chain {expected}")
    return errors


def verify(project: Path, allow_existing_hooks_path: bool) -> int:
    project = project.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    for source, destination in template_copy_plan(project):
        if not destination.exists():
            errors.append(f"missing {destination.relative_to(project)}")
            continue
        if source.read_bytes() != destination.read_bytes():
            errors.append(f"content mismatch {destination.relative_to(project)}")
        if destination.suffix == ".py":
            try:
                compile(destination.read_text(encoding="utf-8"), str(destination), "exec")
            except SyntaxError as exc:
                errors.append(f"invalid Python {destination.relative_to(project)}: {exc}")
    errors.extend(settings_has_entries(project))

    current_task = project / CURRENT_TASK
    if not current_task.exists():
        errors.append(f"missing {CURRENT_TASK}")
    else:
        current = load_json(current_task)
        required = {
            "task_id",
            "phase",
            "owner",
            "coordinator",
            "merge_authority",
            "allowed_scope",
            "forbidden_scope",
            "protected_append_only",
            "allow_user_words_append",
            "write_lock",
            "shared_interfaces",
            "input_contracts",
            "output_contracts",
            "merge_order",
            "conflict_resolution",
            "verification_commands",
            "test_commands",
            "feedback_record",
            "stop_conditions",
        }
        for key in sorted(required - current.keys()):
            errors.append(f"current-task.json missing {key}")

    if not is_git_repo(project):
        errors.append("target is not a Git repository; git guardrails cannot be active")
    else:
        configured = run_git(project, "config", "--get", "core.hooksPath")
        hooks_path = configured.stdout.strip() if configured.returncode == 0 else ""
        if hooks_path != ".githooks":
            if allow_existing_hooks_path:
                errors.extend(chained_hooks_verified(project, hooks_path))
            else:
                errors.append(
                    f"git hooks are not verified active (core.hooksPath={hooks_path or '<unset>'}); "
                    "chain .plan-docs/git-hooks from the existing manager and rerun "
                    "verify with --allow-existing-hooks-path"
                )
        else:
            for name in HOOK_NAMES:
                source = TEMPLATES / "githooks" / name
                destination = project / ".githooks" / name
                if not destination.exists() or source.read_bytes() != destination.read_bytes():
                    errors.append(f"active hook missing or mismatched: .githooks/{name}")
                elif not os.access(destination, os.X_OK):
                    errors.append(f"active hook is not executable: .githooks/{name}")

    if errors:
        print("[plan-docs] guard verification: FAILED")
        for error in errors:
            print(f"  error: {error}")
        for warning in warnings:
            print(f"  warning: {warning}")
        return 1
    print("[plan-docs] guard verification: OK")
    for warning in warnings:
        print(f"  warning: {warning}")
    return 0


def remove_if_unmodified(project: Path, path: Path, expected_hash: str | None) -> bool:
    if not path.exists():
        return False
    if expected_hash and digest(path) != expected_hash:
        print(f"[plan-docs] preserved modified owned file: {path.relative_to(project)}")
        return False
    if not is_owned(path):
        print(f"[plan-docs] preserved non-owned file: {path.relative_to(project)}")
        return False
    path.unlink()
    print(f"[plan-docs] removed: {path.relative_to(project)}")
    return True


def uninstall(project: Path, unset_hooks_path: bool) -> int:
    project = project.resolve()
    manifest = load_json(project / MANIFEST)
    hashes = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    removed = False
    candidates = [destination for _, destination in template_copy_plan(project)]
    candidates.extend(project / ".githooks" / name for name in HOOK_NAMES)
    for path in candidates:
        expected = hashes.get(path.relative_to(project).as_posix()) if hashes else None
        removed = remove_if_unmodified(project, path, expected) or removed
    if remove_settings(project):
        print("[plan-docs] removed only Plan Docs entries from .claude/settings.json")
        removed = True
    if (project / MANIFEST).exists():
        (project / MANIFEST).unlink()
        removed = True

    if unset_hooks_path and is_git_repo(project):
        configured = run_git(project, "config", "--get", "core.hooksPath")
        if configured.returncode == 0 and configured.stdout.strip() == ".githooks":
            remaining = [
                path
                for path in (project / ".githooks").glob("*")
                if path.is_file()
            ]
            if remaining:
                print("[plan-docs] preserved core.hooksPath=.githooks because other hook files remain")
            else:
                result = run_git(project, "config", "--unset", "core.hooksPath")
                if result.returncode != 0:
                    raise GuardError(result.stderr.strip())
                print("[plan-docs] unset core.hooksPath")
    if not removed:
        print("[plan-docs] no unmodified Plan Docs guard files found")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "verify", "uninstall"))
    parser.add_argument("--project", default=".")
    parser.add_argument(
        "--force-owned",
        action="store_true",
        help="update only files carrying the exact PLAN_DOCS_OWNED header; backups are created",
    )
    parser.add_argument(
        "--unset-hooks-path",
        action="store_true",
        help="uninstall: unset .githooks only if no hook files remain",
    )
    parser.add_argument(
        "--allow-existing-hooks-path",
        action="store_true",
        help="verify: accept an existing hook manager only when all three hooks visibly chain Plan Docs",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.command == "install":
            return install(Path(args.project), force_owned=args.force_owned)
        if args.command == "verify":
            return verify(
                Path(args.project),
                allow_existing_hooks_path=args.allow_existing_hooks_path,
            )
        return uninstall(Path(args.project), unset_hooks_path=args.unset_hooks_path)
    except (GuardError, OSError, json.JSONDecodeError) as exc:
        print(f"[plan-docs] guard error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
