from __future__ import annotations

import json
import os
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


def run_scope_guard(
    project: Path,
    payload: dict[str, object] | str,
) -> subprocess.CompletedProcess[str]:
    raw_payload = payload if isinstance(payload, str) else json.dumps(payload)
    environment = os.environ.copy()
    environment["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["python3", str(project / ".plan-docs/hooks/scope_guard.py")],
        cwd=project,
        input=raw_payload,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def activate_scope(
    project: Path,
    *,
    allowed: list[str],
    locks: list[str],
    allow_user_words_append: bool = False,
) -> Path:
    current_path = project / "docs/plan-docs/05-execution/current-task.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    current.update(
        {
            "task_id": "TASK-SCOPE-001",
            "owner": "Claude",
            "allowed_scope": allowed,
            "forbidden_scope": ["secrets/**"],
            "write_lock": locks,
            "allow_user_words_append": allow_user_words_append,
        }
    )
    current_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return current_path


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
            self.assertTrue(
                any(
                    "Bash" in str(item.get("matcher"))
                    and "scope_guard.py"
                    in json.dumps(item.get("hooks"), ensure_ascii=False)
                    for item in installed["hooks"]["PreToolUse"]
                )
            )
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
                hook.write_text(
                    f"#!/bin/sh\n: .plan-docs/git-hooks/{name}; exit 0\n",
                    encoding="utf-8",
                )
                hook.chmod(0o755)
            no_op_verify = command(
                [
                    "python3",
                    str(GUARDS),
                    "verify",
                    "--project",
                    str(project),
                    "--allow-existing-hooks-path",
                ],
                check=False,
            )
            self.assertEqual(1, no_op_verify.returncode)
            self.assertIn("does not execute", no_op_verify.stdout)

            for name in ("pre-commit", "commit-msg", "pre-push"):
                hook = custom_hooks / name
                hook.write_text(
                    "#!/bin/sh\n"
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
            user_words = project / "docs/plan-docs/00-source/用户原话.md"
            user_words.write_text(
                """# 用户原话

## U-001

record_id: U-001

time: 2026-07-25T00:00:00Z

source: user

context: baseline

verbatim: |
  exact first message
""",
                encoding="utf-8",
            )
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

    def test_precommit_rejects_renaming_user_words_into_allowed_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            user_words = project / "docs/plan-docs/00-source/用户原话.md"
            user_words.write_text(
                """# 用户原话

## U-001

record_id: U-001

time: 2026-07-25T00:00:00Z

source: user

context: baseline

verbatim: |
  exact first message
""",
                encoding="utf-8",
            )
            (project / "src").mkdir()
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
            current_path = activate_scope(
                project,
                allowed=["src/**"],
                locks=["src/**"],
            )
            current = json.loads(current_path.read_text(encoding="utf-8"))
            current.update(
                {
                    "feedback_record": "FB-SCOPE-001",
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
                + "\nfeedback_id: FB-SCOPE-001\ntask_id: TASK-SCOPE-001\n",
                encoding="utf-8",
            )
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "mv",
                    user_words.relative_to(project).as_posix(),
                    "src/stolen.md",
                ]
            )
            command(
                [
                    "git",
                    "-C",
                    str(project),
                    "add",
                    current_path.relative_to(project).as_posix(),
                    feedback_path.relative_to(project).as_posix(),
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
            user_words = project / "docs/plan-docs/00-source/用户原话.md"
            user_words.write_text(
                """# 用户原话

## U-001

record_id: U-001

time: 2026-07-25T00:00:00Z

source: user

context: baseline

verbatim: |
  exact first message
""",
                encoding="utf-8",
            )
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
            original = user_words.read_text(encoding="utf-8")
            user_words.write_text(
                original.replace("\n", "\nAI_NOT_USER\n", 1),
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
            user_words.write_text(
                original
                + """

## U-002

record_id: U-002

time: 2026-07-25T00:01:00Z

source: user

context: follow-up

verbatim: |
  exact second message
""",
                encoding="utf-8",
            )
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

    def test_scope_guard_allows_read_only_bash_and_scopes_literal_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            activate_scope(project, allowed=["src/**"], locks=["src/**"])

            read_only = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": (
                            'rg -n TODO src && cat "$INPUT" 2>/dev/null; '
                            "git diff -- src"
                        )
                    },
                },
            )
            inside = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "printf '%s\\n' ok > src/result.txt"},
                },
            )
            outside = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "echo bad > outside.txt"},
                },
            )
            copied_outside = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "cp src/input.txt outside.txt"},
                },
            )

            self.assertEqual(0, read_only.returncode, read_only.stderr)
            self.assertEqual(0, inside.returncode, inside.stderr)
            self.assertEqual(2, outside.returncode)
            self.assertIn("outside allowed scope", outside.stderr)
            self.assertEqual(2, copied_outside.returncode)
            self.assertIn("outside allowed scope", copied_outside.stderr)

    def test_scope_guard_requires_an_active_contract_only_for_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])

            read_only = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "git status --short && cat README.md"},
                },
            )
            bash_write = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "printf x > src/result.txt"},
                },
            )
            edit_write = run_scope_guard(
                project,
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/result.txt"},
                },
            )

            self.assertEqual(0, read_only.returncode, read_only.stderr)
            self.assertEqual(2, bash_write.returncode)
            self.assertIn("without an activated task contract", bash_write.stderr)
            self.assertEqual(2, edit_write.returncode)
            self.assertIn("without an activated task contract", edit_write.stderr)

    def test_scope_guard_only_allows_verifiable_shell_append_to_user_words(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            user_words = "docs/plan-docs/00-source/用户原话.md"
            activate_scope(
                project,
                allowed=[user_words],
                locks=[user_words],
                allow_user_words_append=True,
            )

            appended = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": f"printf '\\nU-002\\n' >> {user_words}"},
                },
            )
            overwritten = run_scope_guard(
                project,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": f"printf rewritten > {user_words}"},
                },
            )

            self.assertEqual(0, appended.returncode, appended.stderr)
            self.assertEqual(2, overwritten.returncode)
            self.assertIn("may only use a verifiable append", overwritten.stderr)

    def test_scope_guard_fails_closed_for_ambiguous_high_risk_bash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            activate_scope(project, allowed=["src/**"], locks=["src/**"])

            cases = (
                'rm -rf "$TARGET"',
                "cd src && printf x > result.txt",
                "git reset --hard",
                "sed -i s/old/new/ src/result.txt",
                "python3 -c \"open('src/result.txt', 'w').write('x')\"",
                "sh -c 'printf hacked > outside.txt'",
                """printf '%s' "$(touch outside2.txt)" """,
            )
            for shell_command in cases:
                with self.subTest(shell_command=shell_command):
                    result = run_scope_guard(
                        project,
                        {
                            "tool_name": "Bash",
                            "tool_input": {"command": shell_command},
                        },
                    )
                    self.assertEqual(2, result.returncode)
                    self.assertIn("ambiguous high-risk", result.stderr)

    def test_scope_guard_internal_errors_fail_closed_for_configured_write_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_repo(project)
            command(["python3", str(GUARDS), "install", "--project", str(project)])
            current_path = activate_scope(
                project,
                allowed=["src/**"],
                locks=["src/**"],
            )
            current_path.write_text("{ invalid json\n", encoding="utf-8")

            payloads = (
                {"tool_name": "Edit", "tool_input": {"file_path": "src/a.txt"}},
                {"tool_name": "Write", "tool_input": {"file_path": "src/a.txt"}},
                {"tool_name": "Bash", "tool_input": {"command": "cat src/a.txt"}},
            )
            for payload in payloads:
                with self.subTest(tool_name=payload["tool_name"]):
                    result = run_scope_guard(project, payload)
                    self.assertEqual(2, result.returncode)
                    self.assertIn("internal scope-guard error", result.stderr)


if __name__ == "__main__":
    unittest.main()
