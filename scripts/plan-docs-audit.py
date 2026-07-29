#!/usr/bin/env python3
"""Validate a generated Plan Docs tree and its automatic-execution gate."""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import hashlib
from pathlib import Path
import re
import subprocess
import sys


BASE_FILES = (
    "00-source/用户原话.md",
    "00-source/AI推断与事实查证.md",
    "00-source/项目事实基线.md",
    "01-requirements/开放问题.md",
    "01-requirements/AI可读需求文档.md",
    "01-requirements/现状与目标差异.md",
    "01-requirements/需求追踪矩阵.md",
    "02-architecture/总体架构.md",
    "02-architecture/接口契约.md",
    "03-product/项目说明书.md",
    "03-product/产品及交互索引.md",
    "03-product/数据字典.md",
    "03-product/API文档.md",
    "03-product/测试用例.md",
    "04-tasks/总任务文档.md",
    "04-tasks/任务合同注册表.md",
    "04-tasks/任务依赖与并行计划.md",
    "04-tasks/Claude任务文档.md",
    "04-tasks/Codex任务文档.md",
    "04-tasks/Reviewer（Claude）任务文档.md",
    "05-execution/环境与分工确认.md",
    "05-execution/执行反馈日志.md",
    "05-execution/current-task.json",
    "06-reviews/Codex App 六代理审查提示词.md",
    "06-reviews/审查分发与写锁.md",
    "06-reviews/审查汇总.md",
    "06-reviews/自动模式门禁.md",
    "09-git/Git纪律.md",
    "10-guards/护栏说明.md",
)
FINAL_PROMPT_PLACEHOLDER = re.compile(r"<[^>\n]+>")
USER_WORD_TEMPLATE_PLACEHOLDER = re.compile(
    r"(?m)^\s*<逐字粘贴用户原话>\s*$"
)
TASK_FIELDS = (
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
LIST_TASK_FIELDS = {
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


def task_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^#{2,6}\s+(TASK-[A-Za-z0-9-]+)\s*$", text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), text[match.end() : end]))
    return blocks


def finding_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^#{2,6}\s+(REV-[A-Za-z0-9-]+)\s*$", text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), text[match.end() : end]))
    return blocks


def id_blocks(text: str, prefix: str) -> list[tuple[str, str]]:
    matches = list(
        re.finditer(
            rf"(?m)^#{{2,6}}\s+({re.escape(prefix)}-[A-Za-z0-9-]+)\s*$",
            text,
        )
    )
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), text[match.end() : end]))
    return blocks


def raw_field(block: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:[ \t]*(.*)$", block)
    if not match:
        return ""
    inline = match.group(1).strip()
    if inline:
        return inline
    tail = block[match.end() :]
    next_field = re.search(r"(?m)^[a-z][a-z0-9_]*:\s*", tail)
    return tail[: next_field.start() if next_field else len(tail)].strip()


def list_values(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw or raw == "[]":
        return []
    if raw.startswith("[") and raw.endswith("]"):
        return [
            item.strip().strip("'\"")
            for item in raw[1:-1].split(",")
            if item.strip()
        ]
    values: list[str] = []
    for line in raw.splitlines():
        match = re.match(r"\s*(?:-\s+|\d+[.)]\s*)(.+?)\s*$", line)
        if match and match.group(1).strip():
            values.append(match.group(1).strip())
    return values


def parsed_task(task_id: str, block: str) -> dict[str, object]:
    task: dict[str, object] = {}
    for field in TASK_FIELDS:
        raw = raw_field(block, field)
        task[field] = list_values(raw) if field in LIST_TASK_FIELDS else raw.strip()
    task["_heading_id"] = task_id
    return task


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = text.splitlines()
    output: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index + 1 < len(lines):
        header_line = lines[index].strip()
        separator_line = lines[index + 1].strip()
        if (
            header_line.startswith("|")
            and separator_line.startswith("|")
            and re.fullmatch(r"[|:\-\s]+", separator_line)
        ):
            header = [cell.strip() for cell in header_line.strip("|").split("|")]
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if len(row) == len(header):
                    rows.append(row)
                index += 1
            output.append((header, rows))
            continue
        index += 1
    return output


def scalar(text: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:[ \t]*(.*?)[ \t]*$", text)
    return match.group(1).strip() if match else ""


def user_words_schema_is_strict(text: str) -> bool:
    matches = list(re.finditer(r"(?m)^## (U-\d{3,})\s*$", text))
    if not matches:
        return text.strip() == "# 用户原话"
    if text[: matches[0].start()].strip() != "# 用户原话":
        return False
    for index, match in enumerate(matches):
        record_id = match.group(1)
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


def review_source_paths(root: Path) -> list[Path]:
    relative_files: list[Path] = [Path("AGENTS.md")]
    tree = root / "docs/plan-docs"
    for directory in (
        "00-source",
        "01-requirements",
        "02-architecture",
        "03-product",
        "04-tasks",
        "09-git",
        "10-guards",
    ):
        base = tree / directory
        if base.exists():
            relative_files.extend(
                path.relative_to(root)
                for path in base.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
    relative_files.append(
        Path("docs/plan-docs/05-execution/环境与分工确认.md")
    )
    return sorted(set(relative_files), key=lambda item: item.as_posix())


def snapshot_digest(entries: list[tuple[Path, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, payload in entries:
        name = relative.as_posix().encode("utf-8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def without_user_records(payload: bytes, excluded: set[str]) -> bytes:
    if not excluded:
        return payload
    text = payload.decode("utf-8")
    matches = list(re.finditer(r"(?m)^## (U-\d{3,})\s*$", text))
    output: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if match.group(1) in excluded:
            output.append(text[cursor : match.start()])
            cursor = end
    output.append(text[cursor:])
    return "".join(output).encode("utf-8")


def review_source_snapshot(
    root: Path,
    excluded_user_sources: set[str] | None = None,
) -> str:
    entries: list[tuple[Path, bytes]] = []
    for relative in review_source_paths(root):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        payload = path.read_bytes()
        if relative == Path("docs/plan-docs/00-source/用户原话.md"):
            payload = without_user_records(
                payload,
                excluded_user_sources or set(),
            )
            payload = payload.rstrip(b"\r\n") + b"\n"
        entries.append((relative, payload))
    return snapshot_digest(entries)


def review_source_snapshot_at_commit(root: Path, commit: str) -> str | None:
    entries: list[tuple[Path, bytes]] = []
    for relative in review_source_paths(root):
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{relative.as_posix()}"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        payload = result.stdout
        if relative == Path("docs/plan-docs/00-source/用户原话.md"):
            payload = payload.rstrip(b"\r\n") + b"\n"
        entries.append((relative, payload))
    return snapshot_digest(entries)


def git_command(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def validate_git_checkpoint(
    root: Path,
    tree: Path,
    environment: str,
    summary: str,
    known_user_sources: set[str],
    user_verbatim_by_id: dict[str, str],
    approval_source: str,
    require_final_artifacts: bool,
    errors: list[str],
) -> None:
    policy = scalar(environment, "git_policy")
    if policy == "disabled":
        source = scalar(environment, "git_disabled_approval_source_user_words")
        quote = scalar(environment, "git_disabled_approval_quote")
        verbatim = user_verbatim_by_id.get(source, "")
        if (
            source not in known_user_sources
            or not quote
            or quote not in verbatim
            or not re.search(
                r"(?i)(git|commit|版本|提交).*(disable|disabled|禁用|不用|不提交)",
                quote,
            )
        ):
            errors.append(
                "git-disabled automatic mode lacks an explicit U-* degradation approval"
            )
        return
    checkpoint = scalar(summary, "reviewed_checkpoint")
    if not re.fullmatch(r"[0-9a-f]{40}", checkpoint):
        errors.append("reviewed_checkpoint must be a full 40-character Git commit")
        return
    top = git_command(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root:
        errors.append("automatic mode requires the target root to be its Git worktree root")
        return
    exists = git_command(root, "cat-file", "-e", f"{checkpoint}^{{commit}}")
    if exists.returncode != 0:
        errors.append("reviewed_checkpoint does not resolve to a Git commit")
        return
    ancestor = git_command(root, "merge-base", "--is-ancestor", checkpoint, "HEAD")
    if ancestor.returncode != 0:
        errors.append("reviewed_checkpoint is not an ancestor of HEAD")
    checkpoint_snapshot = review_source_snapshot_at_commit(root, checkpoint)
    if (
        checkpoint_snapshot is None
        or checkpoint_snapshot
        != review_source_snapshot(root, {approval_source})
    ):
        errors.append("planning source differs from the reviewed checkpoint")
    status = git_command(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if status.returncode != 0:
        errors.append("cannot inspect Git worktree status")
        return
    dirty_paths: list[str] = []
    entries = [value for value in status.stdout.split("\0") if value]
    for entry in entries:
        path = entry[3:] if len(entry) >= 4 else entry
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        dirty_paths.append(path)
    if require_final_artifacts:
        allowed_prefixes = (
            "docs/plan-docs/07-goals/",
            "docs/plan-docs/08-automation/",
            ".plan-docs/",
            ".githooks/",
        )
        allowed_exact = {".claude/settings.json"}
        unexpected = [
            path
            for path in dirty_paths
            if path not in allowed_exact
            and not any(path.startswith(prefix) for prefix in allowed_prefixes)
        ]
        if unexpected:
            errors.append(
                "post-checkpoint worktree has unexpected changes: "
                + ", ".join(sorted(unexpected))
            )
        guard_script = Path(__file__).with_name("plan-docs-guards.py")
        verify_results = [
            subprocess.run(
                [
                    sys.executable,
                    str(guard_script),
                    "verify",
                    "--project",
                    str(root),
                    *extra,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            for extra in ([], ["--allow-existing-hooks-path"])
        ]
        if all(result.returncode != 0 for result in verify_results):
            errors.append("guard verification failed before final execution artifacts")
    elif dirty_paths:
        errors.append(
            "gate-ready requires a clean worktree at the reviewed checkpoint: "
            + ", ".join(sorted(dirty_paths))
        )


def validate_task(task: dict[str, object], label: str, errors: list[str]) -> None:
    for field in TASK_FIELDS:
        value = task.get(field)
        if field in LIST_TASK_FIELDS:
            if field in {"dependencies", "shared_interfaces"}:
                continue
            if not isinstance(value, list) or not value:
                errors.append(f"{label} has empty {field}")
        elif not str(value or "").strip():
            errors.append(f"{label} has empty {field}")
    heading = str(task.get("_heading_id") or "")
    if task.get("task_id") != heading:
        errors.append(f"{label} task_id does not match heading {heading}")
    if not any(re.fullmatch(r"(?:U|LEGACY-U)-[A-Za-z0-9-]+", value) for value in task.get("source_user_words", [])):
        errors.append(f"{label} has no valid U-* or LEGACY-U-* source")
    if not any(re.fullmatch(r"REQ-[A-Za-z0-9-]+", value) for value in task.get("requirement_ids", [])):
        errors.append(f"{label} has no valid REQ-* source")
    if not any(re.fullmatch(r"GAP-[A-Za-z0-9-]+", value) for value in task.get("change_refs", [])):
        errors.append(f"{label} has no valid GAP-* source")
    if str(task.get("status")) not in {"ready", "in_progress", "blocked", "review", "done"}:
        errors.append(f"{label} has non-executable status {task.get('status')!r}")
    for interface in task.get("shared_interfaces", []):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*:(?:read|write)", interface):
            errors.append(
                f"{label} has invalid shared interface mode {interface!r}; "
                "use ID:read or ID:write"
            )


def scope_prefix(pattern: str) -> tuple[str, ...]:
    parts: list[str] = []
    normalized = pattern.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    for part in normalized.split("/"):
        if not part or any(character in part for character in "*?["):
            break
        parts.append(part)
    return tuple(parts)


def scopes_overlap(left: str, right: str) -> bool:
    left = left.strip()
    right = right.strip()
    if left.startswith("./"):
        left = left[2:]
    if right.startswith("./"):
        right = right[2:]
    if left.endswith("/"):
        left += "**"
    if right.endswith("/"):
        right += "**"
    if not left or not right:
        return False
    if left == right or fnmatchcase(left, right) or fnmatchcase(right, left):
        return True
    left_has_glob = any(character in left for character in "*?[")
    right_has_glob = any(character in right for character in "*?[")
    if not left_has_glob and not right_has_glob:
        return False
    left_prefix = scope_prefix(left)
    right_prefix = scope_prefix(right)
    if not left_prefix or not right_prefix:
        return True
    shortest = min(len(left_prefix), len(right_prefix))
    return left_prefix[:shortest] == right_prefix[:shortest]


def dependency_reaches(
    start: str,
    target: str,
    dependencies: dict[str, set[str]],
) -> bool:
    pending = list(dependencies.get(start, set()))
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(dependencies.get(current, set()) - visited)
    return False


def dependency_cycles(dependencies: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(task_id: str) -> None:
        marker = state.get(task_id, 0)
        if marker == 2:
            return
        if marker == 1:
            start = stack.index(task_id)
            cycle = stack[start:] + [task_id]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        state[task_id] = 1
        stack.append(task_id)
        for dependency in sorted(dependencies.get(task_id, set())):
            if dependency in dependencies:
                visit(dependency)
        stack.pop()
        state[task_id] = 2

    for task_id in sorted(dependencies):
        visit(task_id)
    return cycles


def interface_modes(task: dict[str, object]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in task.get("shared_interfaces", []):
        if ":" not in value:
            continue
        interface_id, mode = value.rsplit(":", 1)
        output[interface_id] = mode
    return output


def verified_fact_ids(tree: Path, errors: list[str]) -> set[str]:
    facts_path = tree / "00-source/AI推断与事实查证.md"
    text = facts_path.read_text(encoding="utf-8") if facts_path.exists() else ""
    matches = list(re.finditer(r"(?m)^#{2,6}\s+(F-[A-Za-z0-9-]+)\s*$", text))
    verified: set[str] = set()
    for index, match in enumerate(matches):
        fact_id = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : end]
        if (
            raw_field(block, "fact_id") == fact_id
            and raw_field(block, "type") == "verified-fact"
            and raw_field(block, "status") == "verified"
            and raw_field(block, "claim")
            and raw_field(block, "evidence")
            and raw_field(block, "verification_source")
            and raw_field(block, "verified_at")
        ):
            verified.add(fact_id)
    return verified


def validate_final_artifacts(
    tree: Path,
    environment: str,
    errors: list[str],
) -> None:
    available_ais = set(list_values(scalar(environment, "available_ais")))
    required: list[str] = [
        "08-automation/Codex App定时审查提示词.md",
        "08-automation/设置说明.md",
    ]
    evidence_fields: list[tuple[str, str, str]] = []
    if "Claude" in available_ais:
        required.append("07-goals/Claude-goal.md")
        evidence_fields.append(
            (
                "claude_prompt_mode",
                "claude_capability_evidence",
                "Claude",
            )
        )
    if "Codex" in available_ais or scalar(environment, "ccb_installed") == "yes":
        required.append("07-goals/Codex或CCB-goal.md")
        evidence_fields.append(
            (
                "codex_or_ccb_prompt_mode",
                "codex_or_ccb_capability_evidence",
                "Codex/CCB",
            )
        )
    if "OpenCode" in available_ais:
        required.append("07-goals/OpenCode普通任务提示词.md")
    if "single-ai-cli" in available_ais:
        required.append("07-goals/单AI CLI串行执行提示词.md")
    if scalar(environment, "ccb_installed") == "yes":
        required.append("07-goals/CCB任务分发提示词.md")
    for relative in required:
        path = tree / relative
        if not path.is_file():
            errors.append(f"final tree missing docs/plan-docs/{relative}")
            continue
        if FINAL_PROMPT_PLACEHOLDER.search(path.read_text(encoding="utf-8")):
            errors.append(f"final artifact still contains placeholders: {relative}")

    facts = verified_fact_ids(tree, errors)
    for mode_field, evidence_field, label in evidence_fields:
        mode = scalar(environment, mode_field)
        evidence = scalar(environment, evidence_field)
        if mode not in {"verified-goal", "ordinary-prompt"}:
            errors.append(f"{label} has no concrete prompt capability mode")
        if not evidence or evidence not in facts:
            errors.append(f"{label} capability evidence is not a verified F-* record")
        artifact_relative = (
            "07-goals/Claude-goal.md"
            if label == "Claude"
            else "07-goals/Codex或CCB-goal.md"
        )
        artifact = tree / artifact_relative
        if artifact.is_file():
            artifact_text = artifact.read_text(encoding="utf-8")
            if scalar(artifact_text, "prompt_mode") != mode:
                errors.append(f"{label} final prompt mode differs from environment")
            if scalar(artifact_text, "capability_evidence") != evidence:
                errors.append(f"{label} final prompt evidence differs from environment")


def validate_ready(
    tree: Path,
    errors: list[str],
    require_final_artifacts: bool,
    known_user_sources: set[str],
    user_verbatim_by_id: dict[str, str],
) -> None:
    gate_path = tree / "06-reviews/自动模式门禁.md"
    gate = gate_path.read_text(encoding="utf-8") if gate_path.exists() else ""
    if scalar(gate, "status") != "READY":
        errors.append("automatic mode gate is not READY")
    if scalar(gate, "final_execution_prompts_allowed") != "yes":
        errors.append("final execution prompts are not allowed by the gate")
    approved = scalar(gate, "approved_by_user")
    if not approved or approved.lower() in {"no", "false", "todo"}:
        errors.append("automatic mode gate has no concrete user approval")
    approval_source = scalar(gate, "approval_source_user_words")
    approval_quote = scalar(gate, "approval_quote")
    approval_verbatim = user_verbatim_by_id.get(approval_source, "")
    if approval_source not in user_verbatim_by_id:
        errors.append("automatic mode approval is not bound to an existing U-* source")
    elif (
        not approval_quote
        or approval_quote not in approval_verbatim
        or not re.search(
            r"(?i)(approve|confirm|批准|确认|同意|认可|可以按|就按)",
            approval_quote,
        )
    ):
        errors.append("automatic mode approval quote is not an exact confirmation")
    if user_verbatim_by_id and approval_source != next(reversed(user_verbatim_by_id)):
        errors.append("automatic mode approval must be the latest U-* record")
    if not scalar(gate, "approved_at"):
        errors.append("automatic mode approval has no timestamp")
    gate_tables = [table for table in tables(gate) if table[0][:3] == ["gate", "status", "evidence"]]
    if not gate_tables:
        errors.append("automatic mode gate table is missing")
    else:
        for row in gate_tables[0][1]:
            gate_name, status, evidence, *_ = row
            if status != "PASS":
                errors.append(f"gate is not PASS: {gate_name}")
            if not evidence or evidence in {"-", "TODO"}:
                errors.append(f"gate has no evidence: {gate_name}")

    environment_path = tree / "05-execution/环境与分工确认.md"
    environment = environment_path.read_text(encoding="utf-8") if environment_path.exists() else ""
    project_mode = scalar(environment, "project_mode")
    brownfield_scope = scalar(environment, "brownfield_scope")
    if project_mode not in {"greenfield", "brownfield"}:
        errors.append("environment confirmation has no concrete project_mode")
    if project_mode == "greenfield" and brownfield_scope != "not-applicable":
        errors.append("greenfield project must use brownfield_scope=not-applicable")
    if project_mode == "brownfield" and brownfield_scope not in {"incremental", "full"}:
        errors.append("brownfield project has no concrete incremental/full scope")
    state_path = tree.parent.parent / "CURRENT_STATE.md"
    state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
    if scalar(state, "plan_docs_schema") != "plan-docs/v2":
        errors.append("gate-ready project must declare plan_docs_schema: plan-docs/v2")
    if scalar(state, "project_mode") != project_mode:
        errors.append("CURRENT_STATE project_mode differs from environment confirmation")
    if scalar(state, "brownfield_scope") != brownfield_scope:
        errors.append("CURRENT_STATE brownfield_scope differs from environment confirmation")
    facts_path = tree / "00-source/项目事实基线.md"
    facts = facts_path.read_text(encoding="utf-8") if facts_path.exists() else ""
    changes_path = tree / "01-requirements/现状与目标差异.md"
    changes = changes_path.read_text(encoding="utf-8") if changes_path.exists() else ""
    for label, text in (("项目事实基线.md", facts), ("现状与目标差异.md", changes)):
        if scalar(text, "project_mode") != project_mode:
            errors.append(f"{label} project_mode differs from environment confirmation")
        if scalar(text, "brownfield_scope") != brownfield_scope:
            errors.append(f"{label} brownfield_scope differs from environment confirmation")
    available_ais = list_values(scalar(environment, "available_ais"))
    if not available_ais:
        errors.append("environment confirmation has no available_ais")
    elif any(
        ai not in {"Claude", "Codex", "OpenCode", "single-ai-cli"}
        for ai in available_ais
    ):
        errors.append("environment confirmation has unsupported available_ais value")
    if scalar(environment, "confirmed_by_user") != "yes":
        errors.append("environment and role split are not confirmed by the user")
    confirmation_source = scalar(environment, "confirmation_source_user_words")
    confirmation_quote = scalar(environment, "confirmation_quote")
    confirmation_verbatim = user_verbatim_by_id.get(confirmation_source, "")
    if confirmation_source not in user_verbatim_by_id:
        errors.append("environment confirmation is not bound to an existing U-* source")
    elif not confirmation_quote or confirmation_quote not in confirmation_verbatim:
        errors.append("environment confirmation quote is not exact user wording")
    for field in ("planning_owner", "coordinator", "merge_authority", "reviewer"):
        if not scalar(environment, field):
            errors.append(f"environment confirmation has empty {field}")
    if scalar(environment, "git_policy") not in {"auto", "confirm", "disabled"}:
        errors.append("environment confirmation has no concrete git_policy")
    if scalar(environment, "parallel_allowed") not in {"yes", "no"}:
        errors.append("environment confirmation has no concrete parallel_allowed value")
    if scalar(environment, "ccb_installed") not in {"yes", "no"}:
        errors.append("environment confirmation has no verified CCB answer")
    if scalar(environment, "codex_app_scheduled_review") not in {"yes", "no"}:
        errors.append("environment confirmation has no scheduled-review decision")
    scheduled_review = scalar(environment, "codex_app_scheduled_review")
    scheduled_stop = scalar(environment, "scheduled_review_stop_policy")
    if scheduled_review == "no" and scheduled_stop != "disabled":
        errors.append("disabled scheduled review must use scheduled_review_stop_policy=disabled")
    if scheduled_review == "yes" and scheduled_stop not in {"after-2-green", "user-managed"}:
        errors.append("enabled scheduled review has no concrete stop policy")
    if scalar(environment, "review_policy") != "development-ready":
        errors.append("environment confirmation must use review_policy=development-ready")
    if scalar(environment, "full_review_round_limit") != "1":
        errors.append("full_review_round_limit must default to 1")
    if scalar(environment, "targeted_rereview_round_limit") != "1":
        errors.append("targeted_rereview_round_limit must default to 1")
    try:
        review_call_budget = int(scalar(environment, "review_call_budget"))
    except ValueError:
        review_call_budget = 0
    if review_call_budget < 6:
        errors.append("review_call_budget must be an integer of at least 6")
    if require_final_artifacts:
        validate_final_artifacts(tree, environment, errors)

    summary_path = tree / "06-reviews/审查汇总.md"
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    if scalar(summary, "review_policy") != "development-ready":
        errors.append("review summary must use review_policy=development-ready")
    try:
        full_rounds_used = int(scalar(summary, "full_review_rounds_used"))
        targeted_rounds_used = int(scalar(summary, "targeted_rereview_rounds_used"))
        review_calls_used = int(scalar(summary, "review_calls_used"))
        summary_call_budget = int(scalar(summary, "review_call_budget"))
    except ValueError:
        full_rounds_used = targeted_rounds_used = review_calls_used = summary_call_budget = -1
        errors.append("review summary budget fields must be integers")
    if full_rounds_used != 1:
        errors.append("gate-ready review must use exactly one full review round")
    if targeted_rounds_used not in {0, 1}:
        errors.append("targeted rereview rounds exceed the confirmed default limit")
    if review_calls_used < 6:
        errors.append("review summary has fewer than six Reviewer calls")
    if summary_call_budget != review_call_budget:
        errors.append("review summary call budget differs from environment confirmation")
    if review_calls_used > review_call_budget:
        errors.append("review calls exceed the confirmed budget")
    if scalar(summary, "review_budget_status") != "within-budget":
        errors.append("review budget is not within-budget")
    validate_git_checkpoint(
        tree.parent.parent,
        tree,
        environment,
        summary,
        known_user_sources,
        user_verbatim_by_id,
        approval_source,
        require_final_artifacts,
        errors,
    )
    summary_round = scalar(summary, "review_round")
    if not summary_round:
        errors.append("review summary has no review_round")
    if not scalar(summary, "reviewed_checkpoint"):
        errors.append("review summary has no reviewed_checkpoint")
    if scalar(gate, "approved_checkpoint") != scalar(summary, "reviewed_checkpoint"):
        errors.append("user approval is not bound to the reviewed checkpoint")
    reviewed_checkpoint = scalar(summary, "reviewed_checkpoint")
    if reviewed_checkpoint and reviewed_checkpoint not in approval_quote:
        errors.append("exact user approval quote does not name the reviewed checkpoint")
    if scalar(summary, "overall") not in {"GREEN", "YELLOW"}:
        errors.append("review summary overall verdict is blocking or missing")
    summary_finding_rows: dict[str, dict[str, str]] = {}
    for header, rows in tables(summary):
        if not {"finding_id", "severity", "status"}.issubset(header):
            continue
        for row in rows:
            mapped = dict(zip(header, row))
            if mapped.get("finding_id"):
                summary_finding_rows[mapped["finding_id"]] = mapped
    verdict_tables = [
        table
        for table in tables(summary)
        if table[0][:3] == ["reviewer_id", "context_isolation", "verdict"]
    ]
    found_reviewers: set[str] = set()
    found_report_paths: set[Path] = set()
    raw_finding_ids: set[str] = set()
    dispatch_path = tree / "06-reviews/审查分发与写锁.md"
    dispatch = (
        dispatch_path.read_text(encoding="utf-8") if dispatch_path.exists() else ""
    )
    dispatch_rows: dict[str, dict[str, str]] = {}
    dispatch_ids: list[str] = []
    dispatch_run_ids: list[str] = []
    dispatch_nonces: list[str] = []
    expected_source_snapshot = review_source_snapshot(
        tree.parent.parent,
        {approval_source},
    )
    for header, rows in tables(dispatch):
        if not {
            "reviewer_id",
            "owner",
            "report_path",
            "status",
            "sha256",
            "bytes",
            "run_id",
            "dispatch_nonce",
            "source_snapshot_sha256",
        }.issubset(header):
            continue
        for row in rows:
            mapped = dict(zip(header, row))
            if mapped.get("reviewer_id"):
                dispatch_ids.append(mapped["reviewer_id"])
                dispatch_run_ids.append(mapped.get("run_id", ""))
                dispatch_nonces.append(mapped.get("dispatch_nonce", ""))
                dispatch_rows[mapped["reviewer_id"]] = mapped
    if len(dispatch_ids) != len(set(dispatch_ids)):
        errors.append("review dispatch registry has duplicate reviewer_id rows")
    if scalar(dispatch, "review_round") != summary_round:
        errors.append("review dispatch round differs from review summary")
    if (
        any(not value for value in dispatch_run_ids)
        or len(dispatch_run_ids) != len(set(dispatch_run_ids))
    ):
        errors.append("review dispatch run_id values must be non-empty and unique")
    if (
        any(not value for value in dispatch_nonces)
        or len(dispatch_nonces) != len(set(dispatch_nonces))
    ):
        errors.append("review dispatch nonce values must be non-empty and unique")
    if not verdict_tables:
        errors.append("review summary has no A1-A6 verdict table")
    else:
        header, rows = verdict_tables[0]
        report_index = header.index("report_ref") if "report_ref" in header else -1
        verdict_index = header.index("verdict")
        isolation_index = header.index("context_isolation")
        for row in rows:
            reviewer = row[0]
            if reviewer not in {f"A{number}" for number in range(1, 7)}:
                continue
            found_reviewers.add(reviewer)
            if row[verdict_index] not in {"GREEN", "YELLOW"}:
                errors.append(f"{reviewer} has blocking or missing verdict")
            if row[isolation_index] != "clean":
                errors.append(f"{reviewer} latest report is not from a clean context")
            report_ref = row[report_index] if report_index >= 0 else ""
            if not report_ref:
                errors.append(f"{reviewer} has no report_ref")
            else:
                report_path = (summary_path.parent / report_ref.split("#", 1)[0]).resolve()
                try:
                    report_path.relative_to(summary_path.parent.resolve())
                except ValueError:
                    errors.append(f"{reviewer} report_ref escapes 06-reviews/: {report_ref}")
                    continue
                if report_path in found_report_paths:
                    errors.append(f"{reviewer} reuses another reviewer's report: {report_ref}")
                found_report_paths.add(report_path)
                if not report_path.is_file():
                    errors.append(f"{reviewer} report_ref does not exist: {report_ref}")
                else:
                    report = report_path.read_text(encoding="utf-8")
                    dispatch_row = dispatch_rows.get(reviewer)
                    if dispatch_row is None:
                        errors.append(f"{reviewer} has no review dispatch provenance")
                    else:
                        if dispatch_row.get("owner") != f"Reviewer-{reviewer}":
                            errors.append(f"{reviewer} dispatch owner is not Reviewer-{reviewer}")
                        if dispatch_row.get("report_path") != report_ref.split("#", 1)[0]:
                            errors.append(f"{reviewer} dispatch path differs from report_ref")
                        if dispatch_row.get("status") != "immutable":
                            errors.append(f"{reviewer} raw report is not marked immutable")
                        report_bytes = report_path.read_bytes()
                        expected_hash = hashlib.sha256(report_bytes).hexdigest()
                        if dispatch_row.get("sha256") != expected_hash:
                            errors.append(f"{reviewer} raw report SHA-256 provenance mismatch")
                        if dispatch_row.get("bytes") != str(len(report_bytes)):
                            errors.append(f"{reviewer} raw report byte-count provenance mismatch")
                        if (
                            dispatch_row.get("source_snapshot_sha256")
                            != expected_source_snapshot
                        ):
                            errors.append(
                                f"{reviewer} review source snapshot does not match current planning"
                            )
                        for report_field, dispatch_field in (
                            ("review_run_id", "run_id"),
                            ("dispatch_nonce", "dispatch_nonce"),
                            ("source_snapshot_sha256", "source_snapshot_sha256"),
                        ):
                            if scalar(report, report_field) != dispatch_row.get(
                                dispatch_field
                            ):
                                errors.append(
                                    f"{reviewer} raw {report_field} differs from dispatch provenance"
                                )
                    raw_severity_counts = {"P0": 0, "P1": 0, "P2": 0}
                    if scalar(report, "reviewer_id") != reviewer:
                        errors.append(f"{reviewer} raw report has mismatched reviewer_id")
                    if scalar(report, "verdict") != row[verdict_index]:
                        errors.append(f"{reviewer} raw report verdict does not match summary")
                    if scalar(report, "context_isolation") != row[isolation_index]:
                        errors.append(f"{reviewer} raw report isolation does not match summary")
                    if scalar(report, "review_round") != summary_round:
                        errors.append(f"{reviewer} raw report review_round does not match summary")
                    coverage = scalar(report, "coverage_checked")
                    if not coverage or coverage in {"TODO", "-"}:
                        errors.append(f"{reviewer} raw report has no coverage_checked evidence")
                    if not scalar(report, "unverified_items"):
                        errors.append(f"{reviewer} raw report has no unverified_items declaration")
                    for finding_id, finding_block in finding_blocks(report):
                        raw_finding_ids.add(finding_id)
                        if raw_field(finding_block, "finding_id") != finding_id:
                            errors.append(
                                f"{reviewer} raw finding_id does not match heading {finding_id}"
                            )
                        severity = raw_field(finding_block, "severity")
                        status = raw_field(finding_block, "status")
                        if severity not in {"P0", "P1", "P2"}:
                            errors.append(f"{finding_id} has invalid severity")
                        else:
                            raw_severity_counts[severity] += 1
                        if status not in {"OPEN", "RESOLVED", "CLOSED"}:
                            errors.append(f"{finding_id} has invalid status")
                        for field in (
                            "evidence",
                            "development_impact",
                            "problem",
                            "required_resolution",
                        ):
                            if not raw_field(finding_block, field):
                                errors.append(f"{finding_id} has empty {field}")
                        for field in ("blocking_task_ids", "affected_paths"):
                            if not raw_field(finding_block, field):
                                errors.append(f"{finding_id} has no {field} declaration")
                        if (
                            severity in {"P0", "P1"}
                            and not list_values(raw_field(finding_block, "blocking_task_ids"))
                        ):
                            errors.append(f"{finding_id} {severity} has no blocking TASK-*")
                        summary_finding = summary_finding_rows.get(finding_id)
                        if summary_finding is None:
                            errors.append(f"{reviewer} finding missing from summary: {finding_id}")
                            continue
                        if summary_finding.get("severity") != severity:
                            errors.append(f"{finding_id} severity differs between raw report and summary")
                        if summary_finding.get("status") != status:
                            errors.append(f"{finding_id} status differs between raw report and summary")
                        if (
                            "development_impact" not in summary_finding
                            or not summary_finding.get("development_impact")
                        ):
                            errors.append(f"{finding_id} summary has no development impact")
                    for severity in ("P0", "P1", "P2"):
                        if severity not in header:
                            errors.append(f"review summary verdict table has no {severity} column")
                            continue
                        if row[header.index(severity)] != str(raw_severity_counts[severity]):
                            errors.append(
                                f"{reviewer} {severity} count differs between raw report and summary"
                            )
        missing_reviewers = sorted({f"A{number}" for number in range(1, 7)} - found_reviewers)
        if missing_reviewers:
            errors.append("missing independent reviewer rows: " + ", ".join(missing_reviewers))
    for finding_id in sorted(set(summary_finding_rows) - raw_finding_ids):
        errors.append(f"summary finding has no raw-report source: {finding_id}")

    for finding_id, finding in summary_finding_rows.items():
        if (
            finding.get("severity") in {"P0", "P1"}
            and finding.get("status") not in {"RESOLVED", "CLOSED"}
        ):
            errors.append(f"open {finding.get('severity')} finding: {finding_id}")

    task_documents = [
        tree / "04-tasks/总任务文档.md",
        tree / "04-tasks/Claude任务文档.md",
        tree / "04-tasks/Codex任务文档.md",
        tree / "04-tasks/Reviewer（Claude）任务文档.md",
    ]
    opencode = tree / "04-tasks/OpenCode任务文档.md"
    if opencode.exists():
        task_documents.append(opencode)
    parsed_by_document: dict[Path, list[dict[str, object]]] = {}
    for document in task_documents:
        text = document.read_text(encoding="utf-8") if document.exists() else ""
        parsed_by_document[document] = [
            parsed_task(task_id, block) for task_id, block in task_blocks(text)
        ]
        if document.name != "总任务文档.md":
            assignment_status = scalar(text, "assignment_status")
            no_tasks_reason = scalar(text, "no_tasks_reason")
            if assignment_status not in {"active", "none"}:
                errors.append(f"{document.name} has invalid assignment_status")
            elif assignment_status == "active" and not parsed_by_document[document]:
                errors.append(f"{document.name} is active but contains no task contracts")
            elif assignment_status == "none":
                if parsed_by_document[document]:
                    errors.append(f"{document.name} is none but still contains task contracts")
                if not no_tasks_reason:
                    errors.append(f"{document.name} is none but has no no_tasks_reason")
            for field in ("coordinator", "merge_authority"):
                expected = scalar(environment, field)
                actual = scalar(text, field)
                if assignment_status == "active" and actual != expected:
                    errors.append(
                        f"{document.name} {field} does not match environment confirmation"
                    )
        elif not parsed_by_document[document]:
            errors.append(f"{document.name} contains no task contracts")
        for task in parsed_by_document[document]:
            validate_task(task, f"{document.name}:{task.get('_heading_id')}", errors)
            for source in task.get("source_user_words") or []:
                if source not in known_user_sources:
                    errors.append(
                        f"{document.name}:{task.get('_heading_id')} references unknown user source {source}"
                    )
            if document.name != "总任务文档.md":
                expected_owner = scalar(text, "role")
                if expected_owner and task.get("owner") != expected_owner:
                    errors.append(
                        f"{document.name}:{task.get('_heading_id')} owner "
                        f"{task.get('owner')!r} does not match document role {expected_owner!r}"
                    )

    total_tasks = parsed_by_document.get(tree / "04-tasks/总任务文档.md", [])
    total_ids = {str(task["task_id"]) for task in total_tasks}
    if len(total_ids) != len(total_tasks):
        errors.append("总任务文档.md contains duplicate task_id values")
    total_by_id = {str(task["task_id"]): task for task in total_tasks}
    as_is_blocks = id_blocks(facts, "ASIS")
    as_is_ids = {as_is_id for as_is_id, _ in as_is_blocks}
    if not as_is_blocks:
        errors.append("项目事实基线.md contains no ASIS-* block")
    for as_is_id, block in as_is_blocks:
        if raw_field(block, "as_is_id") != as_is_id:
            errors.append(f"{as_is_id} as_is_id does not match heading")
        for field in (
            "source_type",
            "source_paths",
            "evidence",
            "observed_behavior",
            "affected_scope",
            "confidence",
            "status",
        ):
            if not raw_field(block, field):
                errors.append(f"{as_is_id} has empty {field}")
        if raw_field(block, "confidence") not in {"verified", "partial"}:
            errors.append(f"{as_is_id} has invalid confidence")
        if raw_field(block, "status") not in {"active", "superseded"}:
            errors.append(f"{as_is_id} has invalid status")
    gap_blocks = id_blocks(changes, "GAP")
    gap_ids = {gap_id for gap_id, _ in gap_blocks}
    gap_targets: dict[str, set[str]] = {}
    if not gap_blocks:
        errors.append("现状与目标差异.md contains no GAP-* block")
    for gap_id, block in gap_blocks:
        if raw_field(block, "gap_id") != gap_id:
            errors.append(f"{gap_id} gap_id does not match heading")
        as_is_refs = set(list_values(raw_field(block, "as_is_refs")))
        target_refs = set(list_values(raw_field(block, "target_requirement_refs")))
        task_refs = set(list_values(raw_field(block, "task_refs")))
        gap_targets[gap_id] = target_refs
        if not as_is_refs or not as_is_refs.issubset(as_is_ids):
            errors.append(f"{gap_id} has missing or unknown ASIS-* refs")
        if not target_refs:
            errors.append(f"{gap_id} has no target requirement refs")
        for field in ("affected_scope", "development_outcome", "acceptance_criteria"):
            if not raw_field(block, field):
                errors.append(f"{gap_id} has empty {field}")
        if raw_field(block, "change_type") not in {
            "create",
            "modify",
            "preserve",
            "migrate",
            "remove",
        }:
            errors.append(f"{gap_id} has invalid change_type")
        if raw_field(block, "status") not in {"confirmed", "implemented", "verified"}:
            errors.append(f"{gap_id} is not confirmed")
        if not task_refs:
            errors.append(f"{gap_id} has no task_refs")
        for task_id in sorted(task_refs - total_ids):
            errors.append(f"{gap_id} references unknown task {task_id}")
    for task in total_tasks:
        task_id = str(task["task_id"])
        for gap_id in task.get("change_refs") or []:
            if gap_id not in gap_ids:
                errors.append(f"{task_id} references unknown change {gap_id}")
    assignment_counts: dict[str, int] = {task_id: 0 for task_id in total_ids}
    for document, tasks_in_document in parsed_by_document.items():
        if document.name == "总任务文档.md":
            continue
        for task in tasks_in_document:
            task_id = str(task["task_id"])
            if task_id not in total_ids:
                errors.append(f"{document.name}:{task_id} is not derived from 总任务文档.md")
            else:
                assignment_counts[task_id] += 1
                total_task = total_by_id[task_id]
                for field in TASK_FIELDS:
                    if task.get(field) != total_task.get(field):
                        errors.append(
                            f"{document.name}:{task_id} field {field} differs from 总任务文档.md"
                        )
    for task_id, count in assignment_counts.items():
        if count != 1:
            errors.append(f"{task_id} must appear in exactly one AI task document; found {count}")

    dependencies_by_id: dict[str, set[str]] = {
        str(task["task_id"]): set(task.get("dependencies") or [])
        for task in total_tasks
    }
    for task_id, dependencies in dependencies_by_id.items():
        for dependency in sorted(dependencies):
            if dependency not in total_ids:
                errors.append(f"{task_id} depends on unknown task {dependency}")
        upstream_outputs = {
            dependency: set(total_by_id[dependency].get("output_contracts") or [])
            for dependency in dependencies
            if dependency in total_by_id
        }
        inputs = set(total_by_id[task_id].get("input_contracts") or [])
        for dependency, outputs in upstream_outputs.items():
            if not inputs.intersection(outputs):
                errors.append(
                    f"{task_id} input_contracts do not match {dependency} output_contracts"
                )
    for cycle in dependency_cycles(dependencies_by_id):
        errors.append("task dependency cycle: " + " -> ".join(cycle))

    registry_path = tree / "04-tasks/任务合同注册表.md"
    registry_text = registry_path.read_text(encoding="utf-8") if registry_path.exists() else ""
    contracts: dict[str, dict[str, object]] = {}
    contract_blocks = id_blocks(registry_text, "CONTRACT")
    contract_ids = [contract_id for contract_id, _ in contract_blocks]
    if len(contract_ids) != len(set(contract_ids)):
        errors.append("任务合同注册表.md contains duplicate CONTRACT-* headings")
    for contract_id, block in contract_blocks:
        contract = {
            "contract_id": raw_field(block, "contract_id"),
            "producer_tasks": list_values(raw_field(block, "producer_tasks")),
            "consumer_tasks": list_values(raw_field(block, "consumer_tasks")),
            "artifact_refs": list_values(raw_field(block, "artifact_refs")),
            "required_content": raw_field(block, "required_content"),
            "completion_condition": raw_field(block, "completion_condition"),
            "verification": raw_field(block, "verification"),
            "compatibility": raw_field(block, "compatibility"),
            "status": raw_field(block, "status"),
        }
        contracts[contract_id] = contract
        if contract["contract_id"] != contract_id:
            errors.append(f"{contract_id} contract_id does not match heading")
        for field in (
            "producer_tasks",
            "consumer_tasks",
            "artifact_refs",
            "required_content",
            "completion_condition",
            "verification",
            "compatibility",
        ):
            if not contract[field]:
                errors.append(f"{contract_id} has empty {field}")
        if contract["status"] != "frozen":
            errors.append(f"{contract_id} is not frozen")
        for field in ("producer_tasks", "consumer_tasks"):
            for task_id in contract[field]:
                if task_id not in total_ids:
                    errors.append(f"{contract_id} {field} references unknown task {task_id}")
        for task_id in contract["producer_tasks"]:
            if task_id in total_by_id and contract_id not in (
                total_by_id[task_id].get("output_contracts") or []
            ):
                errors.append(
                    f"{contract_id} names {task_id} as a producer but the task does not output it"
                )
        for task_id in contract["consumer_tasks"]:
            if task_id in total_by_id and contract_id not in (
                total_by_id[task_id].get("input_contracts") or []
            ):
                errors.append(
                    f"{contract_id} names {task_id} as a consumer but the task does not input it"
                )

    for task in total_tasks:
        task_id = str(task["task_id"])
        for contract_id in task.get("input_contracts") or []:
            contract = contracts.get(contract_id)
            if contract is None:
                errors.append(f"{task_id} references undefined input contract {contract_id}")
            elif task_id not in contract["consumer_tasks"]:
                errors.append(f"{contract_id} does not name {task_id} as a consumer")
        for contract_id in task.get("output_contracts") or []:
            contract = contracts.get(contract_id)
            if contract is None:
                errors.append(f"{task_id} references undefined output contract {contract_id}")
            elif task_id not in contract["producer_tasks"]:
                errors.append(f"{contract_id} does not name {task_id} as a producer")

    for index, left in enumerate(total_tasks):
        left_id = str(left["task_id"])
        left_locks = list(left.get("write_lock") or [])
        left_interfaces = interface_modes(left)
        for right in total_tasks[index + 1 :]:
            right_id = str(right["task_id"])
            ordered = dependency_reaches(
                left_id, right_id, dependencies_by_id
            ) or dependency_reaches(right_id, left_id, dependencies_by_id)
            overlap = sorted(
                {
                    f"{left_lock} <> {right_lock}"
                    for left_lock in left_locks
                    for right_lock in right.get("write_lock") or []
                    if scopes_overlap(left_lock, right_lock)
                }
            )
            if overlap and not ordered:
                errors.append(
                    f"parallel write-lock conflict without dependency: {left_id} / {right_id}: "
                    + ", ".join(sorted(overlap))
                )
            right_interfaces = interface_modes(right)
            for interface_id in sorted(set(left_interfaces) & set(right_interfaces)):
                if (
                    "write" in {left_interfaces[interface_id], right_interfaces[interface_id]}
                    and not ordered
                ):
                    errors.append(
                        "parallel shared-interface write conflict without dependency: "
                        f"{left_id} / {right_id}: {interface_id}"
                    )

    requirements_path = tree / "01-requirements/AI可读需求文档.md"
    requirements_text = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    requirement_matches = list(
        re.finditer(r"(?m)^#{2,6}\s+(REQ-[A-Za-z0-9-]+)\s*$", requirements_text)
    )
    requirement_ids: set[str] = set()
    for index, match in enumerate(requirement_matches):
        requirement_id = match.group(1)
        requirement_ids.add(requirement_id)
        end = (
            requirement_matches[index + 1].start()
            if index + 1 < len(requirement_matches)
            else len(requirements_text)
        )
        block = requirements_text[match.end() : end]
        if raw_field(block, "requirement_id") != requirement_id:
            errors.append(f"{requirement_id} requirement_id does not match heading")
        if not any(
            value in known_user_sources
            for value in list_values(raw_field(block, "source_user_words"))
        ):
            errors.append(f"{requirement_id} has no existing user-word source")
        if not raw_field(block, "acceptance_criteria"):
            errors.append(f"{requirement_id} has empty acceptance_criteria")
        if raw_field(block, "status") != "confirmed":
            errors.append(f"{requirement_id} is not confirmed")
        requirement_changes = set(list_values(raw_field(block, "change_refs")))
        if not requirement_changes:
            errors.append(f"{requirement_id} has no GAP-* change_refs")
        for gap_id in sorted(requirement_changes - gap_ids):
            errors.append(f"{requirement_id} references unknown change {gap_id}")
        referenced_tasks = set(list_values(raw_field(block, "task_refs")))
        if not referenced_tasks:
            errors.append(f"{requirement_id} has no task_refs")
        for task_id in sorted(referenced_tasks - total_ids):
            errors.append(f"{requirement_id} references unknown task {task_id}")
    for task in total_tasks:
        task_id = str(task["task_id"])
        for requirement_id in task.get("requirement_ids") or []:
            if requirement_id not in requirement_ids:
                errors.append(f"{task_id} references unknown requirement {requirement_id}")
    for gap_id, target_refs in gap_targets.items():
        for requirement_id in sorted(target_refs - requirement_ids):
            errors.append(f"{gap_id} references unknown requirement {requirement_id}")

    tests_path = tree / "03-product/测试用例.md"
    tests_text = tests_path.read_text(encoding="utf-8") if tests_path.exists() else ""
    test_ids = set(re.findall(r"(?m)^#{2,6}\s+(TEST-[A-Za-z0-9-]+)\s*$", tests_text))
    trace_path = tree / "01-requirements/需求追踪矩阵.md"
    trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
    trace_tables = [
        table
        for table in tables(trace_text)
        if {"requirement", "change", "total_task", "test"}.issubset(table[0])
    ]
    if not trace_tables:
        errors.append("traceability matrix is missing required columns")
    else:
        header, rows = trace_tables[0]
        req_index = header.index("requirement")
        change_index = header.index("change")
        user_index = header.index("user_words") if "user_words" in header else -1
        task_index = header.index("total_task")
        test_index = header.index("test")
        for requirement_id in sorted(requirement_ids):
            matching_rows = [row for row in rows if requirement_id in row[req_index]]
            if not matching_rows:
                errors.append(f"{requirement_id} is absent from the traceability matrix")
                continue
            has_known_trace = False
            for row in matching_rows:
                if user_index >= 0:
                    row_sources = set(
                        re.findall(r"(?:LEGACY-)?U-[A-Za-z0-9-]+", row[user_index])
                    )
                    for source in sorted(row_sources - known_user_sources):
                        errors.append(
                            f"traceability matrix references unknown user source {source}"
                        )
                row_tasks = set(re.findall(r"TASK-[A-Za-z0-9-]+", row[task_index]))
                row_tests = set(re.findall(r"TEST-[A-Za-z0-9-]+", row[test_index]))
                row_changes = set(re.findall(r"GAP-[A-Za-z0-9-]+", row[change_index]))
                for gap_id in sorted(row_changes - gap_ids):
                    errors.append(f"traceability matrix references unknown change {gap_id}")
                if (
                    row_changes.intersection(gap_ids)
                    and row_tasks.intersection(total_ids)
                    and row_tests.intersection(test_ids)
                ):
                    has_known_trace = True
                    break
            if not has_known_trace:
                errors.append(
                    f"{requirement_id} has no trace through known GAP-*, TASK-* and TEST-*"
                )


def audit(
    project: Path,
    require_gate_ready: bool,
    require_final_artifacts: bool,
) -> int:
    root = project.resolve()
    tree = root / "docs/plan-docs"
    errors: list[str] = []
    for relative in BASE_FILES:
        candidate = tree / relative
        if not candidate.is_file():
            errors.append(f"missing docs/plan-docs/{relative}")
        elif candidate.is_symlink():
            errors.append(f"unsafe symlink at docs/plan-docs/{relative}")
    if not (root / "AGENTS.md").is_file():
        errors.append("missing AGENTS.md")
    elif (root / "AGENTS.md").is_symlink():
        errors.append("unsafe symlink at AGENTS.md")
    if not (root / "CURRENT_STATE.md").is_file():
        errors.append("missing CURRENT_STATE.md")
    elif (root / "CURRENT_STATE.md").is_symlink():
        errors.append("unsafe symlink at CURRENT_STATE.md")

    user_words = tree / "00-source/用户原话.md"
    known_user_sources: set[str] = set()
    user_verbatim_by_id: dict[str, str] = {}
    if user_words.exists():
        user_text = user_words.read_text(encoding="utf-8")
        if not user_words_schema_is_strict(user_text):
            errors.append("用户原话.md contains content outside the strict U-* schema")
        user_matches = list(
            re.finditer(r"(?m)^#{2,6}\s+(U-\d{3,})\s*$", user_text)
        )
        ids: list[str] = []
        for index, match in enumerate(user_matches):
            user_id = match.group(1)
            end = (
                user_matches[index + 1].start()
                if index + 1 < len(user_matches)
                else len(user_text)
            )
            block = user_text[match.end() : end]
            record_id = raw_field(block, "record_id")
            if record_id != user_id:
                errors.append(f"{user_id} record_id does not match heading")
                continue
            ids.append(user_id)
            known_user_sources.add(user_id)
            verbatim_match = re.search(
                r"(?m)^verbatim:[ \t]*[|>][ \t]*\n((?:[ \t]+[^\n]*(?:\n|$))*)",
                block,
            )
            verbatim = verbatim_match.group(1).strip() if verbatim_match else ""
            if (require_gate_ready or require_final_artifacts) and (
                not verbatim or USER_WORD_TEMPLATE_PLACEHOLDER.search(verbatim)
            ):
                errors.append(f"{user_id} has empty or placeholder verbatim content")
            user_verbatim_by_id[user_id] = verbatim
        if len(ids) != len(set(ids)):
            errors.append("duplicate user-word record_id values")
        numbers = [int(value.split("-", 1)[1]) for value in ids]
        if numbers != list(range(1, len(numbers) + 1)):
            errors.append("user-word IDs must be contiguous from U-001")

    trace_path = tree / "01-requirements/需求追踪矩阵.md"
    if trace_path.exists():
        legacy_ids: set[str] = set()
        for header, rows in tables(trace_path.read_text(encoding="utf-8")):
            if not {"legacy_id", "source_path", "content_hash"}.issubset(header):
                continue
            legacy_index = header.index("legacy_id")
            source_index = header.index("source_path")
            hash_index = header.index("content_hash")
            anchor_index = header.index("source_anchor") if "source_anchor" in header else -1
            for row in rows:
                legacy_id = row[legacy_index]
                if re.fullmatch(r"LEGACY-U-[A-Za-z0-9-]+", legacy_id):
                    if legacy_id in legacy_ids:
                        errors.append(f"duplicate legacy_id mapping: {legacy_id}")
                        continue
                    legacy_ids.add(legacy_id)
                    source_value = row[source_index].strip()
                    hash_value = row[hash_index].strip()
                    anchor_value = row[anchor_index].strip() if anchor_index >= 0 else ""
                    if not source_value or not hash_value or anchor_value != "whole-file":
                        errors.append(
                            f"{legacy_id} requires source_path, source_anchor=whole-file "
                            "and SHA-256 content_hash"
                        )
                        continue
                    source_relative = Path(source_value)
                    if source_relative.is_absolute():
                        errors.append(f"{legacy_id} source_path must be project-relative")
                        continue
                    source_path = (root / source_relative).resolve()
                    try:
                        source_path.relative_to(root)
                    except ValueError:
                        errors.append(f"{legacy_id} source_path escapes the project")
                        continue
                    if not source_path.is_file() or source_path.is_symlink():
                        errors.append(f"{legacy_id} source_path is missing or unsafe")
                        continue
                    normalized_hash = (
                        hash_value.split(":", 1)[1]
                        if hash_value.startswith("sha256:")
                        else hash_value
                    )
                    if not re.fullmatch(r"[0-9a-f]{64}", normalized_hash):
                        errors.append(f"{legacy_id} content_hash is not SHA-256")
                        continue
                    actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
                    if normalized_hash != actual_hash:
                        errors.append(f"{legacy_id} content_hash does not match source bytes")
                        continue
                    known_user_sources.add(legacy_id)

    total_tasks = tree / "04-tasks/总任务文档.md"
    if total_tasks.exists() and not task_blocks(total_tasks.read_text(encoding="utf-8")):
        errors.append("总任务文档.md contains no TASK-* block")

    if require_gate_ready or require_final_artifacts:
        validate_ready(
            tree,
            errors,
            require_final_artifacts=require_final_artifacts,
            known_user_sources=known_user_sources,
            user_verbatim_by_id=user_verbatim_by_id,
        )

    if errors:
        print("[plan-docs] tree audit: FAILED")
        for item in errors:
            print(f"  error: {item}")
        return 1
    print("[plan-docs] tree audit: OK")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--require-gate-ready",
        action="store_true",
        help="validate planning, reviews and user approval before final prompts are generated",
    )
    modes.add_argument(
        "--require-final-artifacts",
        action="store_true",
        help="validate a READY gate plus all final goal and automation prompt files",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    arguments = parse_args(sys.argv[1:])
    raise SystemExit(
        audit(
            Path(arguments.project),
            require_gate_ready=arguments.require_gate_ready,
            require_final_artifacts=arguments.require_final_artifacts,
        )
    )
