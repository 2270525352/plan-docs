from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts/plan-docs-bootstrap.py"
AUDIT = ROOT / "scripts/plan-docs-audit.py"
TREE_TEMPLATES = ROOT / "templates/project-tree"
AUDIT_SPEC = importlib.util.spec_from_file_location("plan_docs_audit", AUDIT)
assert AUDIT_SPEC and AUDIT_SPEC.loader
AUDIT_MODULE = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT_MODULE)


class AuditTests(unittest.TestCase):
    def test_complete_evidence_tree_passes_gate_ready_without_final_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(
                [
                    "python3",
                    str(BOOTSTRAP),
                    "install",
                    "--project",
                    str(project),
                    "--init-tree",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            tree = project / "docs/plan-docs"
            (tree / "00-source/用户原话.md").write_text(
                """# 用户原话

## U-001

record_id: U-001
time: 2026-07-25
source: user message
context: forward planning
verbatim: |
  Build the confirmed feature without inventing behavior.
""",
                encoding="utf-8",
            )
            (tree / "00-source/AI推断与事实查证.md").write_text(
                """# AI 推断与事实查证

## F-001

fact_id: F-001
type: verified-fact
source_user_words: [U-001]
claim: This environment requires an ordinary Codex prompt.
evidence: Local capability check did not expose a goal command.
verification_source: local CLI help
verified_at: 2026-07-25T00:00:00Z
confidence: high
affected_requirements: [REQ-001]
status: verified
""",
                encoding="utf-8",
            )
            contract = """## TASK-001

task_id: TASK-001
phase: implementation
owner: Codex
source_user_words: [U-001]
requirement_ids: [REQ-001]
input_docs: [docs/plan-docs/01-requirements/AI可读需求文档.md]
dependencies: []
allowed_scope: [src/feature.py]
forbidden_scope: [docs/plan-docs/00-source/用户原话.md]
shared_interfaces: []
input_contracts: [CONTRACT-001]
output_contracts: [CONTRACT-001]
merge_order: N/A: single task
conflict_resolution: N/A: single writer
exact_steps: [Implement the confirmed feature.]
expected_outputs: [src/feature.py]
acceptance_criteria: TEST-001 passes
verification_commands: [python3 -m py_compile src/feature.py]
test_commands: [python3 -m unittest]
write_lock: [src/feature.py]
git_checkpoint: CP-001
feedback_record: FB-001
stop_conditions: stop on contract conflict
status: ready
"""
            (tree / "04-tasks/总任务文档.md").write_text(
                "# 总任务文档\n\n" + contract,
                encoding="utf-8",
            )
            (tree / "04-tasks/Codex任务文档.md").write_text(
                "# Codex任务文档\n\n"
                "role: Codex\n\n"
                "assignment_status: active\n\n"
                "no_tasks_reason:\n\n"
                "coordinator: Claude\n\n"
                "merge_authority: Codex\n\n"
                + contract,
                encoding="utf-8",
            )
            for name, role in (
                ("Claude任务文档.md", "Claude"),
                ("Reviewer（Claude）任务文档.md", "Reviewer（Claude）"),
            ):
                (tree / "04-tasks" / name).write_text(
                    f"# {name.removesuffix('.md')}\n\n"
                    f"role: {role}\n\n"
                    "assignment_status: none\n\n"
                    "no_tasks_reason: no task assigned in this execution plan\n",
                    encoding="utf-8",
                )
            (tree / "01-requirements/AI可读需求文档.md").write_text(
                """# AI 可读需求文档

## REQ-001

requirement_id: REQ-001
source_user_words: [U-001]
acceptance_criteria: TEST-001 passes
task_refs: [TASK-001]
status: confirmed
""",
                encoding="utf-8",
            )
            (tree / "01-requirements/需求追踪矩阵.md").write_text(
                """# 需求追踪矩阵

| user_words | requirement | total_task | test |
|---|---|---|---|
| U-001 | REQ-001 | TASK-001 | TEST-001 |
""",
                encoding="utf-8",
            )
            (tree / "03-product/测试用例.md").write_text(
                "# 测试用例\n\n## TEST-001\n\ntest_id: TEST-001\n",
                encoding="utf-8",
            )
            (tree / "05-execution/环境与分工确认.md").write_text(
                """# 环境与分工确认

ccb_installed: no
available_ais: [Codex]
claude_prompt_mode: not-selected
claude_capability_evidence:
codex_or_ccb_prompt_mode: ordinary-prompt
codex_or_ccb_capability_evidence: F-001
planning_owner: Claude
coordinator: Claude
merge_authority: Codex
reviewer: independent Codex App agents
parallel_allowed: no
git_policy: confirm
codex_app_scheduled_review: no
confirmed_by_user: yes
""",
                encoding="utf-8",
            )
            agents = tree / "06-reviews/agents"
            agents.mkdir()
            verdict_rows: list[str] = []
            for reviewer in (f"A{number}" for number in range(1, 7)):
                report_ref = f"agents/1-{reviewer}.md"
                (tree / "06-reviews" / report_ref).write_text(
                    f"""# {reviewer} 审查报告

reviewer_id: {reviewer}
review_round: 1
context_isolation: clean
scope: assigned scope
verdict: GREEN
coverage_checked: all assigned documents and IDs
unverified_items: none
""",
                    encoding="utf-8",
                )
                verdict_rows.append(
                    f"| {reviewer} | clean | GREEN | 0 | 0 | 0 | {report_ref} |"
                )
            (tree / "06-reviews/审查汇总.md").write_text(
                """# 审查汇总

review_round: 1

reviewed_checkpoint: CP-PLAN-001

| reviewer_id | context_isolation | verdict | P0 | P1 | P2 | report_ref |
|---|---|---|---|---|---|---|
"""
                + "\n".join(verdict_rows)
                + "\n\n## Round result\n\noverall: GREEN\n",
                encoding="utf-8",
            )
            gate_path = tree / "06-reviews/自动模式门禁.md"
            gate = gate_path.read_text(encoding="utf-8")
            gate = gate.replace("| TODO | | |", "| PASS | verified evidence | |")
            gate = gate.replace("status: BLOCKED / READY", "status: READY")
            gate = gate.replace(
                "final_execution_prompts_allowed: no / yes",
                "final_execution_prompts_allowed: yes",
            )
            gate = gate.replace("approved_by_user:", "approved_by_user: user-confirmed")
            gate_path.write_text(gate, encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(AUDIT),
                    "--project",
                    str(project),
                    "--require-gate-ready",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stdout)
            self.assertIn("tree audit: OK", result.stdout)

            shutil.copytree(
                TREE_TEMPLATES / "07-goals",
                tree / "07-goals",
                dirs_exist_ok=True,
            )
            shutil.copytree(
                TREE_TEMPLATES / "08-automation",
                tree / "08-automation",
                dirs_exist_ok=True,
            )
            codex_prompt = tree / "07-goals/Codex或CCB-goal.md"
            prompt_text = codex_prompt.read_text(encoding="utf-8")
            prompt_text = prompt_text.replace(
                "<verified-goal | ordinary-prompt>",
                "ordinary-prompt",
            ).replace("<F-*>", "F-001")
            prompt_text = re.sub(r"<[^>\n]+>", "resolved", prompt_text)
            codex_prompt.write_text(prompt_text, encoding="utf-8")
            automation_prompt = (
                tree / "08-automation/Codex App定时审查提示词.md"
            )
            automation_prompt.write_text(
                re.sub(
                    r"<[^>\n]+>",
                    "resolved",
                    automation_prompt.read_text(encoding="utf-8"),
                ),
                encoding="utf-8",
            )
            final_result = subprocess.run(
                [
                    "python3",
                    str(AUDIT),
                    "--project",
                    str(project),
                    "--require-final-artifacts",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, final_result.returncode, final_result.stdout)

            codex_prompt.write_text(
                prompt_text + "\nproject: <PROJECT_ROOT>\n",
                encoding="utf-8",
            )
            unresolved = subprocess.run(
                [
                    "python3",
                    str(AUDIT),
                    "--project",
                    str(project),
                    "--require-final-artifacts",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, unresolved.returncode)
            self.assertIn("still contains placeholders", unresolved.stdout)
            codex_prompt.write_text(prompt_text, encoding="utf-8")

            requirements_path = tree / "01-requirements/AI可读需求文档.md"
            requirements_path.write_text(
                requirements_path.read_text(encoding="utf-8").replace(
                    "source_user_words: [U-001]",
                    "source_user_words: [U-999]",
                ),
                encoding="utf-8",
            )
            unknown_source = subprocess.run(
                [
                    "python3",
                    str(AUDIT),
                    "--project",
                    str(project),
                    "--require-gate-ready",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, unknown_source.returncode)
            self.assertIn("has no existing user-word source", unknown_source.stdout)

    def test_template_tree_passes_structural_audit_but_not_ready_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(
                [
                    "python3",
                    str(BOOTSTRAP),
                    "install",
                    "--project",
                    str(project),
                    "--init-tree",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            structural = subprocess.run(
                ["python3", str(AUDIT), "--project", str(project)],
                check=False,
                capture_output=True,
                text=True,
            )
            ready = subprocess.run(
                [
                    "python3",
                    str(AUDIT),
                    "--project",
                    str(project),
                    "--require-gate-ready",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, structural.returncode, structural.stdout)
            self.assertEqual(1, ready.returncode)
            self.assertIn("automatic mode gate is not READY", ready.stdout)
            self.assertNotIn("final tree missing", ready.stdout)

    def test_superficial_ready_labels_cannot_bypass_evidence_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(
                [
                    "python3",
                    str(BOOTSTRAP),
                    "install",
                    "--project",
                    str(project),
                    "--init-tree",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            tree = project / "docs/plan-docs"
            shutil.copytree(TREE_TEMPLATES / "07-goals", tree / "07-goals", dirs_exist_ok=True)
            shutil.copytree(
                TREE_TEMPLATES / "08-automation",
                tree / "08-automation",
                dirs_exist_ok=True,
            )
            gate_path = tree / "06-reviews/自动模式门禁.md"
            gate = gate_path.read_text(encoding="utf-8")
            gate = gate.replace("| TODO | | |", "| PASS | fake | |")
            gate = gate.replace("status: BLOCKED / READY", "status: READY")
            gate = gate.replace(
                "final_execution_prompts_allowed: no / yes",
                "final_execution_prompts_allowed: yes",
            )
            gate = gate.replace("approved_by_user:", "approved_by_user: user")
            gate_path.write_text(gate, encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(AUDIT),
                    "--project",
                    str(project),
                    "--require-final-artifacts",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("not confirmed by the user", result.stdout)
            self.assertIn("has no report_ref", result.stdout)
            self.assertIn("has empty owner", result.stdout)
            self.assertIn("field owner differs from 总任务文档.md", result.stdout)

    def test_glob_scope_overlap_and_dependency_cycle_detection(self) -> None:
        self.assertTrue(AUDIT_MODULE.scopes_overlap("src/**", "src/api.py"))
        self.assertTrue(AUDIT_MODULE.scopes_overlap("src/", "src/api.py"))
        self.assertTrue(AUDIT_MODULE.scopes_overlap("src/**", "src/api/**"))
        self.assertFalse(AUDIT_MODULE.scopes_overlap("src/api/**", "src/web/**"))
        self.assertFalse(AUDIT_MODULE.scopes_overlap("src/api.py", "src/web.py"))
        cycles = AUDIT_MODULE.dependency_cycles(
            {
                "TASK-001": {"TASK-003"},
                "TASK-002": {"TASK-001"},
                "TASK-003": {"TASK-002"},
            }
        )
        self.assertEqual(
            [["TASK-001", "TASK-003", "TASK-002", "TASK-001"]],
            cycles,
        )


if __name__ == "__main__":
    unittest.main()
