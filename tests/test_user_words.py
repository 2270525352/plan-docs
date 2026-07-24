from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPEND = ROOT / "scripts/plan-docs-append-user-words.py"
PRE_COMMIT = ROOT / "templates/guards/hooks/pre_commit.py"
TEMPLATE = ROOT / "templates/project-tree/00-source/用户原话.md"


class UserWordsTests(unittest.TestCase):
    def test_atomic_append_assigns_monotonic_ids_and_preserves_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = project / "docs/plan-docs/00-source/用户原话.md"
            target.parent.mkdir(parents=True)
            target.write_bytes(TEMPLATE.read_bytes())
            first = subprocess.run(
                [
                    "python3",
                    str(APPEND),
                    "--project",
                    str(project),
                    "--source",
                    "user message",
                    "--context",
                    "initial request",
                    "--verbatim",
                    "Keep `<daily|weekly>` exact.\nSecond line.",
                    "--time",
                    "2026-07-25T00:00:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            first_bytes = target.read_bytes()
            second = subprocess.run(
                [
                    "python3",
                    str(APPEND),
                    "--project",
                    str(project),
                    "--source",
                    "user reply",
                    "--context",
                    "decision",
                    "--verbatim",
                    "Use Codex.",
                    "--time",
                    "2026-07-25T00:01:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            final_bytes = target.read_bytes()
            self.assertIn("appended U-001", first.stdout)
            self.assertIn("appended U-002", second.stdout)
            self.assertTrue(final_bytes.startswith(first_bytes))
            self.assertIn(b"  Keep `<daily|weekly>` exact.\n  Second line.\n", final_bytes)

    def test_rejects_invalid_existing_sequence_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = project / "docs/plan-docs/00-source/用户原话.md"
            target.parent.mkdir(parents=True)
            target.write_text(
                "# 用户原话\n\n## U-002\n\nrecord_id: U-002\n\nverbatim: |\n  bad\n",
                encoding="utf-8",
            )
            before = target.read_bytes()
            result = subprocess.run(
                [
                    "python3",
                    str(APPEND),
                    "--project",
                    str(project),
                    "--source",
                    "user",
                    "--context",
                    "test",
                    "--verbatim",
                    "new",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual(before, target.read_bytes())

    def test_precommit_rejects_malformed_first_user_words_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "plan-docs@example.invalid"],
                cwd=project,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Plan Docs Test"],
                cwd=project,
                check=True,
            )
            target = project / "docs/plan-docs/00-source/用户原话.md"
            target.parent.mkdir(parents=True)
            target.write_text(
                """# 用户原话

## U-001

record_id: U-001
time: 2026-07-25T00:00:00Z
source: user
context: test
verbatim: |
  exact words

AI summary that must never be stored here.
""",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            result = subprocess.run(
                ["python3", str(PRE_COMMIT)],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("strict append-only", result.stderr)


if __name__ == "__main__":
    unittest.main()
