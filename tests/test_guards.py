from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts/plan-docs-bootstrap.py"
GUARDS = ROOT / "scripts/plan-docs-guards.py"


def command(arguments: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def init_repo(project: Path) -> None:
    command(["git", "init", "-q", str(project)])
    command(["git", "-C", str(project), "config", "user.email", "tests@example.invalid"])
    command(["git", "-C", str(project), "config", "user.name", "Plan Docs Tests"])
    command(
        [
            "python3",
            str(BOOTSTRAP),
            "install",
            "--project",
            str(project),
            "--init-tree",
        ]
    )


class GuardTests(unittest.TestCase):
    def test_install_verify_idempotent_and_settings_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            settings = {
                "permissions": {"allow": ["Read"]},
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "echo custom"}],
                        }
                    ],
                    "PostToolUse": [{"hooks": [{"type": "command", "command": "echo post"}]}],
                },
            }
            settings_path = project / ".claude/settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(settings, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8",
            )

            command(["python3", str(GUARDS), "install", "--project", str(project)])
            installed = json.loads(settings_path.read_text(encoding="utf-8"))
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            command(["python3", str(GUARDS), "verify", "--project", str(project)])
            installed_twice = json.loads(settings_path.read_text(encoding="utf-8"))

            self.assertEqual({"allow": ["Read"]}, installed["permissions"])
            self.assertIn("PostToolUse", installed["hooks"])
            bash_entries = [
                item
                for item in installed["hooks"]["PreToolUse"]
                if item.get("matcher") == "Bash"
            ]
            self.assertEqual(1, len(bash_entries))
            self.assertEqual(installed, installed_twice)
            self.assertEqual(
                ".githooks",
                command(
                    ["git", "-C", str(project), "config", "--get", "core.hooksPath"]
                ).stdout.strip(),
            )

    def test_existing_hook_manager_and_settings_are_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            custom_hooks = project / "custom-hooks"
            custom_hooks.mkdir()
            custom_precommit = custom_hooks / "pre-commit"
            custom_bytes = b"#!/bin/sh\necho custom-hook\n"
            custom_precommit.write_bytes(custom_bytes)
            command(
                ["git", "-C", str(project), "config", "core.hooksPath", "custom-hooks"]
            )
            settings_path = project / ".claude/settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                '{"custom": true, "hooks": {"PreToolUse": []}}\n',
                encoding="utf-8",
            )

            install = command(
                ["python3", str(GUARDS), "install", "--project", str(project)]
            )
            verify = command(
                ["python3", str(GUARDS), "verify", "--project", str(project)],
                check=False,
            )

            self.assertIn("integration pending", install.stdout)
            self.assertEqual("custom-hooks", command(
                ["git", "-C", str(project), "config", "--get", "core.hooksPath"]
            ).stdout.strip())
            self.assertEqual(custom_bytes, custom_precommit.read_bytes())
            self.assertTrue(json.loads(settings_path.read_text(encoding="utf-8"))["custom"])
            self.assertEqual(1, verify.returncode)
            self.assertIn("not verified active", verify.stdout)

            for name in ("pre-commit", "commit-msg", "pre-push"):
                hook = custom_hooks / name
                original = hook.read_text(encoding="utf-8") if hook.exists() else "#!/bin/sh\n"
                hook.write_text(
                    original
                    + f'"$(git rev-parse --show-toplevel)/.plan-docs/git-hooks/{name}" "$@"\n',
                    encoding="utf-8",
                )
                hook.chmod(0o755)
            chained_verify = command(
                [
                    "python3",
                    str(GUARDS),
                    "verify",
                    "--project",
                    str(project),
                    "--allow-existing-hooks-path",
                ]
            )
            self.assertIn("verification: OK", chained_verify.stdout)

    def test_uninstall_preserves_unrelated_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            settings_path = project / ".claude/settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text('{"custom": "keep"}\n', encoding="utf-8")
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            command(
                [
                    "python3",
                    str(GUARDS),
                    "uninstall",
                    "--project",
                    str(project),
                    "--unset-hooks-path",
                ]
            )
            remaining = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual("keep", remaining["custom"])
            self.assertNotIn("hooks", remaining)

    def test_linked_worktree_does_not_change_shared_hooks_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            main = base / "main"
            linked = base / "linked"
            main.mkdir()
            command(["git", "init", "-q", str(main)])
            command(["git", "-C", str(main), "config", "user.email", "tests@example.invalid"])
            command(["git", "-C", str(main), "config", "user.name", "Plan Docs Tests"])
            (main / "tracked.txt").write_text("baseline\n", encoding="utf-8")
            command(["git", "-C", str(main), "add", "tracked.txt"])
            command(["git", "-C", str(main), "commit", "-qm", "baseline"])
            hooks_dir_raw = command(
                ["git", "-C", str(main), "rev-parse", "--git-path", "hooks"]
            ).stdout.strip()
            hooks_dir = Path(hooks_dir_raw)
            if not hooks_dir.is_absolute():
                hooks_dir = main / hooks_dir
            existing_hook = hooks_dir / "pre-commit"
            existing_hook.write_text("#!/bin/sh\necho shared\n", encoding="utf-8")
            existing_hook.chmod(0o755)
            command(["git", "-C", str(main), "worktree", "add", "-q", "-b", "linked-test", str(linked)])
            command(
                [
                    "python3",
                    str(BOOTSTRAP),
                    "install",
                    "--project",
                    str(linked),
                    "--init-tree",
                ]
            )

            install = command(
                ["python3", str(GUARDS), "install", "--project", str(linked)]
            )
            main_hooks_path = command(
                ["git", "-C", str(main), "config", "--get", "core.hooksPath"],
                check=False,
            )
            linked_hooks_path = command(
                ["git", "-C", str(linked), "config", "--get", "core.hooksPath"],
                check=False,
            )

            self.assertIn("pending-linked-worktree", install.stdout)
            self.assertNotEqual(0, main_hooks_path.returncode)
            self.assertNotEqual(0, linked_hooks_path.returncode)
            self.assertEqual("#!/bin/sh\necho shared\n", existing_hook.read_text(encoding="utf-8"))

            linked_hooks_dir_raw = command(
                ["git", "-C", str(linked), "rev-parse", "--git-path", "hooks"]
            ).stdout.strip()
            linked_hooks_dir = Path(linked_hooks_dir_raw)
            if not linked_hooks_dir.is_absolute():
                linked_hooks_dir = linked / linked_hooks_dir
            for name in ("pre-commit", "commit-msg", "pre-push"):
                hook = linked_hooks_dir / name
                original = hook.read_text(encoding="utf-8") if hook.exists() else "#!/bin/sh\n"
                hook.write_text(
                    original
                    + f'"$(git rev-parse --show-toplevel)/.plan-docs/git-hooks/{name}" "$@"\n',
                    encoding="utf-8",
                )
                hook.chmod(0o755)
            verified = command(
                [
                    "python3",
                    str(GUARDS),
                    "verify",
                    "--project",
                    str(linked),
                    "--allow-existing-hooks-path",
                ]
            )
            self.assertIn("verification: OK", verified.stdout)

    def test_precommit_rejects_out_of_scope_staged_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            (project / "src").mkdir()
            (project / "src/allowed.txt").write_text("baseline\n", encoding="utf-8")
            (project / "outside.txt").write_text("baseline\n", encoding="utf-8")
            command(["git", "-C", str(project), "add", "."])
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "commit",
                    "-qm",
                    "baseline",
                ]
            )

            current_path = project / "docs/plan-docs/05-execution/current-task.json"
            current = json.loads(current_path.read_text(encoding="utf-8"))
            current.update(
                {
                    "task_id": "TASK-900",
                    "owner": "Codex",
                    "allowed_scope": ["src/**"],
                    "forbidden_scope": ["secrets/**"],
                    "write_lock": ["src/**"],
                    "feedback_record": "FB-900",
                    "verification_commands": ["true"],
                    "test_commands": ["true"],
                    "stop_conditions": "stop on failure",
                }
            )
            current_path.write_text(
                json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            feedback_path = project / "docs/plan-docs/05-execution/执行反馈日志.md"
            feedback_path.write_text(
                feedback_path.read_text(encoding="utf-8")
                + "\nfeedback_id: FB-900\ntask_id: TASK-900\n",
                encoding="utf-8",
            )
            (project / "outside.txt").write_text("changed\n", encoding="utf-8")
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "add",
                    current_path.relative_to(project).as_posix(),
                    feedback_path.relative_to(project).as_posix(),
                    "outside.txt",
                ]
            )
            result = command(
                ["python3", str(project / ".plan-docs/hooks/pre_commit.py")],
                cwd=project,
                check=False,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("outside allowed scope", result.stderr)

    def test_precommit_rejects_user_words_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            command(["git", "-C", str(project), "add", "."])
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "commit",
                    "-qm",
                    "baseline",
                ]
            )
            user_words = project / "docs/plan-docs/00-source/用户原话.md"
            original = user_words.read_text(encoding="utf-8")
            user_words.write_text(original.replace("# 用户原话", "# 改写"), encoding="utf-8")
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "add",
                    user_words.relative_to(project).as_posix(),
                ]
            )
            result = command(
                ["python3", str(project / ".plan-docs/hooks/pre_commit.py")],
                cwd=project,
                check=False,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("append-only", result.stderr)

    def test_precommit_rejects_middle_insert_but_allows_exact_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            command(["git", "-C", str(project), "add", "."])
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "commit",
                    "-qm",
                    "baseline",
                ]
            )
            user_words = project / "docs/plan-docs/00-source/用户原话.md"
            original = user_words.read_text(encoding="utf-8")
            user_words.write_text(
                original.replace("## U-001", "AI_NOT_USER\n\n## U-001"),
                encoding="utf-8",
            )
            command(["git", "-C", str(project), "add", user_words.relative_to(project).as_posix()])
            inserted = command(
                ["python3", str(project / ".plan-docs/hooks/pre_commit.py")],
                cwd=project,
                check=False,
            )
            self.assertEqual(1, inserted.returncode)
            self.assertIn("exact byte prefix", inserted.stderr)

            command(["git", "-C", str(project), "reset", "-q", "HEAD", "--", user_words.relative_to(project).as_posix()])
            current_path = project / "docs/plan-docs/05-execution/current-task.json"
            current = json.loads(current_path.read_text(encoding="utf-8"))
            current.update(
                {
                    "task_id": "TASK-INTAKE-001",
                    "owner": "Claude",
                    "allow_user_words_append": True,
                    "allowed_scope": [user_words.relative_to(project).as_posix()],
                    "write_lock": [user_words.relative_to(project).as_posix()],
                }
            )
            current_path.write_text(
                json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            user_words.write_text(original + "\n## U-002\n", encoding="utf-8")
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "add",
                    user_words.relative_to(project).as_posix(),
                    current_path.relative_to(project).as_posix(),
                ]
            )
            appended = command(
                ["python3", str(project / ".plan-docs/hooks/pre_commit.py")],
                cwd=project,
                check=False,
            )
            self.assertEqual(0, appended.returncode, appended.stderr)

    def test_precommit_treats_planning_documents_as_scoped_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            command(["git", "-C", str(project), "add", "."])
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "commit",
                    "-qm",
                    "baseline",
                ]
            )
            current_path = project / "docs/plan-docs/05-execution/current-task.json"
            current = json.loads(current_path.read_text(encoding="utf-8"))
            current.update(
                {
                    "task_id": "TASK-900",
                    "owner": "Codex",
                    "allowed_scope": ["src/**"],
                    "forbidden_scope": ["docs/plan-docs/**"],
                    "write_lock": ["src/**"],
                    "feedback_record": "FB-900",
                    "verification_commands": ["true"],
                    "test_commands": ["true"],
                    "stop_conditions": "stop on failure",
                }
            )
            current_path.write_text(
                json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            requirement_path = (
                project / "docs/plan-docs/01-requirements/AI可读需求文档.md"
            )
            requirement_path.write_text(
                requirement_path.read_text(encoding="utf-8") + "\nunauthorized\n",
                encoding="utf-8",
            )
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "add",
                    current_path.relative_to(project).as_posix(),
                    requirement_path.relative_to(project).as_posix(),
                ]
            )
            result = command(
                ["python3", str(project / ".plan-docs/hooks/pre_commit.py")],
                cwd=project,
                check=False,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("forbidden scope", result.stderr)


if __name__ == "__main__":
    unittest.main()
