from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/plan-docs-activate-task.py"


COMPLETE_TASK = """# Codex任务文档

coordinator: Claude
merge_authority: Lead

## TASK-123

task_id: TASK-123
phase: intake
owner: Codex
source_user_words: [U-001]
requirement_ids: [REQ-001]
change_refs: [GAP-001]
input_docs: [docs/plan-docs/01-requirements/AI可读需求文档.md]
dependencies: []
allowed_scope:
  - docs/plan-docs/00-source/用户原话.md
forbidden_scope:
  - docs/plan-docs/00-source/**
shared_interfaces: [API-001:read]
input_contracts: [SCHEMA-REQUEST-001]
output_contracts: [SCHEMA-RESPONSE-001]
merge_order: after TASK-100
conflict_resolution: coordinator decides
exact_steps:
  1. Implement one endpoint.
expected_outputs:
  - src/api.py
acceptance_criteria: endpoint returns the contracted schema
verification_commands:
  - python3 -m py_compile src/api.py
test_commands:
  - python3 -m unittest
write_lock:
  - docs/plan-docs/00-source/用户原话.md
git_checkpoint: CP-123
feedback_record: FB-123
stop_conditions: stop on contract conflict
status: ready
"""


class ActivateTaskTests(unittest.TestCase):
    def test_activates_canonical_runtime_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            document = project / "docs/plan-docs/04-tasks/Codex任务文档.md"
            document.parent.mkdir(parents=True)
            document.write_text(COMPLETE_TASK, encoding="utf-8")
            task_block = "## TASK-123" + COMPLETE_TASK.split("## TASK-123", 1)[1]
            (document.parent / "总任务文档.md").write_text(
                "# 总任务文档\n\n" + task_block,
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--project",
                    str(project),
                    "--task-doc",
                    str(document.relative_to(project)),
                    "--task-id",
                    "TASK-123",
                    "--allow-user-words-append",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            current = json.loads(
                (
                    project / "docs/plan-docs/05-execution/current-task.json"
                ).read_text(encoding="utf-8")
            )
            self.assertIn("activated TASK-123", result.stdout)
            self.assertEqual("Codex", current["owner"])
            self.assertEqual("Claude", current["coordinator"])
            self.assertEqual("Lead", current["merge_authority"])
            self.assertEqual(
                ["docs/plan-docs/00-source/用户原话.md"],
                current["allowed_scope"],
            )
            self.assertEqual(
                ["docs/plan-docs/00-source/用户原话.md"],
                current["write_lock"],
            )
            self.assertEqual(["API-001:read"], current["shared_interfaces"])
            self.assertEqual(["SCHEMA-REQUEST-001"], current["input_contracts"])
            self.assertEqual(["SCHEMA-RESPONSE-001"], current["output_contracts"])
            self.assertEqual("coordinator decides", current["conflict_resolution"])
            self.assertEqual(["python3 -m unittest"], current["test_commands"])
            self.assertNotIn("allow", current)
            self.assertNotIn("acceptance_cmds", current)

    def test_rejects_incomplete_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            document = project / "docs/plan-docs/04-tasks/Codex任务文档.md"
            document.parent.mkdir(parents=True)
            document.write_text(
                "## TASK-1\n\ntask_id: TASK-1\nowner: Codex\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--project",
                    str(project),
                    "--task-doc",
                    str(document),
                    "--task-id",
                    "TASK-1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("contract is incomplete", result.stderr)

    def test_rejects_project_external_task_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            external = Path(temporary) / "task.md"
            external.write_text(COMPLETE_TASK, encoding="utf-8")
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--project",
                    str(project),
                    "--task-doc",
                    str(external),
                    "--task-id",
                    "TASK-123",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("must be inside docs/plan-docs/04-tasks", result.stderr)

    def test_rejects_task_drift_and_pre_gate_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            task_directory = project / "docs/plan-docs/04-tasks"
            task_directory.mkdir(parents=True)
            document = task_directory / "Codex任务文档.md"
            document.write_text(COMPLETE_TASK, encoding="utf-8")
            task_block = "## TASK-123" + COMPLETE_TASK.split("## TASK-123", 1)[1]
            total = task_directory / "总任务文档.md"
            total.write_text(
                "# 总任务文档\n\n" + task_block.replace("owner: Codex", "owner: Claude"),
                encoding="utf-8",
            )
            drift = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--project",
                    str(project),
                    "--task-doc",
                    str(document.relative_to(project)),
                    "--task-id",
                    "TASK-123",
                    "--allow-user-words-append",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, drift.returncode)
            self.assertIn("differs from 总任务文档.md", drift.stderr)

            execution_document = COMPLETE_TASK.replace("phase: intake", "phase: implementation")
            document.write_text(execution_document, encoding="utf-8")
            total.write_text(
                "# 总任务文档\n\n"
                + (
                    "## TASK-123"
                    + execution_document.split("## TASK-123", 1)[1]
                ),
                encoding="utf-8",
            )
            blocked = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--project",
                    str(project),
                    "--task-doc",
                    str(document.relative_to(project)),
                    "--task-id",
                    "TASK-123",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, blocked.returncode)
            self.assertIn("automatic-mode gate is not ready", blocked.stderr)


if __name__ == "__main__":
    unittest.main()
