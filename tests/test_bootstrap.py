from __future__ import annotations

import subprocess
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/plan-docs-bootstrap.py"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=check,
    )


class BootstrapTests(unittest.TestCase):
    def test_empty_project_is_idempotent_and_delays_final_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            first = run("install", "--project", str(project), "--init-tree")
            agents_before = (project / "AGENTS.md").read_bytes()
            state_before = (project / "CURRENT_STATE.md").read_bytes()
            second = run("install", "--project", str(project), "--init-tree")

            self.assertIn("created AGENTS.md", first.stdout)
            self.assertIn("AGENTS.md unchanged", second.stdout)
            self.assertEqual(agents_before, (project / "AGENTS.md").read_bytes())
            self.assertEqual(state_before, (project / "CURRENT_STATE.md").read_bytes())
            self.assertEqual(
                1,
                (project / "AGENTS.md").read_text(encoding="utf-8").count(
                    "<!-- PLAN_DOCS_START -->"
                ),
            )
            self.assertTrue((project / "docs/plan-docs/07-goals").is_dir())
            self.assertTrue((project / "docs/plan-docs/08-automation").is_dir())
            self.assertFalse(
                (project / "docs/plan-docs/07-goals/Claude-goal.md").exists()
            )
            self.assertFalse(
                (
                    project
                    / "docs/plan-docs/08-automation/Codex App定时审查提示词.md"
                ).exists()
            )
            self.assertFalse(
                (project / "docs/plan-docs/04-tasks/OpenCode任务文档.md").exists()
            )
            self.assertIn(
                "plan_docs_schema: plan-docs/v2",
                (project / "CURRENT_STATE.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "web_dashboard: disabled / npx / installed",
                (
                    project
                    / "docs/plan-docs/05-execution/环境与分工确认.md"
                ).read_text(encoding="utf-8"),
            )
            self.assertTrue(
                (
                    project
                    / "docs/plan-docs/00-source/项目事实基线.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    project
                    / "docs/plan-docs/01-requirements/现状与目标差异.md"
                ).is_file()
            )
            self.assertFalse((project / "package.json").exists())
            self.assertFalse((project / "node_modules").exists())
            self.assertEqual([], list(project.glob("AGENTS.md.plan-docs.*.bak")))

    def test_existing_agents_merge_and_current_state_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            original_agents = "# My Rules\n\nKeep this exact.\n"
            original_state = b"# Live state\n\nCUSTOM\x0a"
            (project / "AGENTS.md").write_text(original_agents, encoding="utf-8")
            (project / "CURRENT_STATE.md").write_bytes(original_state)

            run("install", "--project", str(project))
            merged_once = (project / "AGENTS.md").read_text(encoding="utf-8")
            run("install", "--project", str(project))
            merged_twice = (project / "AGENTS.md").read_text(encoding="utf-8")

            self.assertTrue(merged_once.startswith(original_agents.rstrip()))
            self.assertEqual(merged_once, merged_twice)
            self.assertEqual(1, merged_once.count("<!-- PLAN_DOCS_START -->"))
            self.assertEqual(1, merged_once.count("<!-- PLAN_DOCS_END -->"))
            merged_state = (project / "CURRENT_STATE.md").read_bytes()
            self.assertTrue(merged_state.startswith(original_state.rstrip()))
            self.assertEqual(1, merged_state.count(b"<!-- PLAN_DOCS_STATE_START -->"))
            self.assertEqual(1, merged_state.count(b"<!-- PLAN_DOCS_STATE_END -->"))

    def test_invalid_marker_is_rejected_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            broken = "before\n<!-- PLAN_DOCS_START -->\nunfinished\n"
            (project / "AGENTS.md").write_text(broken, encoding="utf-8")
            result = run("install", "--project", str(project), check=False)
            self.assertEqual(2, result.returncode)
            self.assertEqual(broken, (project / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertFalse((project / "CURRENT_STATE.md").exists())

    def test_existing_managed_current_state_is_never_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            run("install", "--project", str(project))
            state_path = project / "CURRENT_STATE.md"
            live = state_path.read_text(encoding="utf-8").replace(
                "current_task:",
                "current_task: TASK-LIVE-9",
            )
            state_path.write_text(live, encoding="utf-8")
            run("install", "--project", str(project))
            self.assertEqual(live, state_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
