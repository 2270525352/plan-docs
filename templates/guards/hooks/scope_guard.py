#!/usr/bin/env python3
# PLAN_DOCS_OWNED v1
"""Claude write-scope guard for active Plan Docs tasks.

The Bash inspection is deliberately conservative.  It understands common
shell writes and redirections, allows commands that are demonstrably
read-only, and rejects write forms whose destination cannot be resolved.
The staged Git hook remains the authoritative second line of defence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import sys
from typing import Any


CURRENT_TASK = Path("docs/plan-docs/05-execution/current-task.json")
SHELL_SEPARATORS = {";", "&&", "||", "|", "&"}
WRITE_REDIRECTIONS = {">", ">>", ">|", "<>", "&>", "&>>"}
FD_REDIRECTIONS = {">&", "<&"}
SAFE_SINKS = {"/dev/null", "/dev/stdout", "/dev/stderr"}
DYNAMIC_PATH = re.compile(r"[$`*?[\]{}~]")
INLINE_WRITE_SIGNAL = re.compile(
    r"(?:write_text|write_bytes|open\s*\([^)]*,\s*['\"][wax+]|"
    r"os\.(?:remove|unlink|rename|replace|mkdir|makedirs)|"
    r"shutil\.(?:copy|copy2|copytree|move|rmtree)|"
    r"fs\.(?:writeFile|appendFile|rm|rename|mkdir))"
)


class GuardBlocked(RuntimeError):
    """A user-facing scope or shell ambiguity violation."""


@dataclass(frozen=True)
class ShellWrite:
    path: str
    append_only: bool = False


def glob_regex(pattern: str) -> re.Pattern[str]:
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/"):
        pattern += "**"
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
            parts.append(".*")
            i += 2
        elif char == "*":
            parts.append("[^/]*")
            i += 1
        elif char == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(char))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def matching(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if pattern.endswith("/**") and path == pattern[:-3].rstrip("/"):
            return pattern
        if pattern and glob_regex(pattern).match(path):
            return pattern
    return None


def string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return value


def relative_target(root: Path, raw_target: str) -> str:
    if not isinstance(raw_target, str) or not raw_target.strip():
        raise ValueError("write target must be a non-empty string")
    raw_path = Path(raw_target)
    target = (raw_path if raw_path.is_absolute() else root / raw_path).resolve()
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        raise GuardBlocked("target path escapes the project root") from None


def validate_target(
    root: Path,
    current: dict[str, Any],
    raw_target: str,
    *,
    shell_append_only: bool | None = None,
) -> None:
    task_id = str(current.get("task_id") or "").strip()
    relative = relative_target(root, raw_target)
    protected = string_list(current.get("protected_append_only"), "protected_append_only")
    protected_hit = matching(relative, protected)
    if protected_hit and not current.get("allow_user_words_append", False):
        raise GuardBlocked(
            f"{relative} is append-only source material ({protected_hit}); "
            "use a dedicated intake task and enable allow_user_words_append"
        )
    if protected_hit and shell_append_only is False:
        raise GuardBlocked(
            f"{relative} is append-only source material ({protected_hit}); "
            "Bash may only use a verifiable append operation"
        )

    forbidden = string_list(current.get("forbidden_scope"), "forbidden_scope")
    forbidden_hit = matching(relative, forbidden)
    if forbidden_hit:
        raise GuardBlocked(
            f"{relative} matches forbidden scope {forbidden_hit} for {task_id}"
        )

    allowed = string_list(current.get("allowed_scope"), "allowed_scope")
    if not allowed:
        raise GuardBlocked(
            f"{task_id} has no allowed_scope; activate a complete task contract first"
        )
    if not matching(relative, allowed):
        raise GuardBlocked(
            f"[plan-docs] blocked: {relative} is outside allowed scope for {task_id}: "
            + ", ".join(allowed)
        )

    locks = string_list(current.get("write_lock"), "write_lock")
    if locks and not matching(relative, locks) and not protected_hit:
        raise GuardBlocked(
            f"[plan-docs] blocked: {relative} is not owned by this task's write lock: "
            + ", ".join(locks)
        )


def shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def dynamic_target(target: str) -> bool:
    return bool(DYNAMIC_PATH.search(target)) or target in {".", "..", "/"}


def add_shell_target(writes: list[ShellWrite], target: str, append: bool = False) -> None:
    if target in SAFE_SINKS or target.startswith("/dev/fd/") or target.isdigit():
        return
    if dynamic_target(target):
        raise GuardBlocked(
            f"ambiguous high-risk Bash write target {target!r}; use a literal project path"
        )
    writes.append(ShellWrite(target, append))


def operands(arguments: list[str]) -> list[str]:
    """Return simple operands; option-value-heavy forms are rejected by callers."""
    result: list[str] = []
    after_options = False
    for argument in arguments:
        if argument == "--":
            after_options = True
        elif not after_options and argument.startswith("-"):
            continue
        else:
            result.append(argument)
    return result


def command_writes(segment: list[str], writes: list[ShellWrite]) -> None:
    words = [word for word in segment if word not in WRITE_REDIRECTIONS]
    if not words:
        return
    while words and ("=" in words[0] and not words[0].startswith(("/", "./", "../"))):
        name, _, _ = words[0].partition("=")
        if not name.isidentifier():
            break
        words.pop(0)
    while words and words[0] in {"command", "builtin", "sudo"}:
        words.pop(0)
    if words and words[0] == "env":
        words.pop(0)
        while words and (words[0].startswith("-") or "=" in words[0]):
            words.pop(0)
    if not words:
        return

    executable = Path(words[0]).name
    arguments = words[1:]
    simple = operands(arguments)

    if executable in {"sh", "bash", "zsh", "dash", "fish", "eval"}:
        raise GuardBlocked(
            f"ambiguous high-risk nested shell execution: {executable}; "
            "run a literal command that the scope guard can inspect"
        )
    if executable == "xargs":
        raise GuardBlocked(
            "ambiguous nested command execution: xargs; "
            "run a literal command that the scope guard can inspect"
        )
    if executable in {"rm", "unlink", "rmdir", "touch", "mkdir", "mkfifo"}:
        if not simple:
            raise GuardBlocked(f"ambiguous high-risk Bash command: {executable}")
        for target in simple:
            add_shell_target(writes, target)
    elif executable == "truncate":
        if any(option in arguments for option in ("-r", "--reference")):
            raise GuardBlocked("ambiguous high-risk Bash command: truncate with reference")
        if "-s" in arguments:
            index = arguments.index("-s")
            simple = operands(arguments[:index] + arguments[index + 2 :])
        if not simple:
            raise GuardBlocked("ambiguous high-risk Bash command: truncate")
        for target in simple:
            add_shell_target(writes, target)
    elif executable in {"chmod", "chown", "chgrp"}:
        if len(simple) < 2:
            raise GuardBlocked(f"ambiguous high-risk Bash command: {executable}")
        for target in simple[1:]:
            add_shell_target(writes, target)
    elif executable == "cp":
        if len(simple) < 2 or any(
            option in arguments for option in ("-t", "--target-directory")
        ):
            raise GuardBlocked("ambiguous high-risk Bash command: cp")
        add_shell_target(writes, simple[-1])
    elif executable in {"ln", "rsync"}:
        if len(simple) < 2:
            raise GuardBlocked(f"ambiguous high-risk Bash command: {executable}")
        add_shell_target(writes, simple[-1])
    elif executable == "mv":
        if len(simple) < 2 or any(
            option in arguments for option in ("-t", "--target-directory")
        ):
            raise GuardBlocked("ambiguous high-risk Bash command: mv")
        for target in simple:
            add_shell_target(writes, target)
    elif executable == "tee":
        append = "-a" in arguments or "--append" in arguments
        for target in simple:
            add_shell_target(writes, target, append)
    elif executable == "dd":
        destinations = [
            argument.partition("=")[2]
            for argument in arguments
            if argument.startswith("of=")
        ]
        for target in destinations:
            add_shell_target(writes, target)
    elif executable in {"curl", "wget"}:
        for option in ("-o", "--output", "-O", "--output-document"):
            if option in arguments:
                index = arguments.index(option)
                if index + 1 >= len(arguments):
                    raise GuardBlocked(f"ambiguous high-risk Bash command: {executable}")
                add_shell_target(writes, arguments[index + 1])
        for argument in arguments:
            for prefix in ("--output=", "--output-document="):
                if argument.startswith(prefix):
                    add_shell_target(writes, argument[len(prefix) :])
            if executable == "wget" and argument.startswith("-O") and len(argument) > 2:
                add_shell_target(writes, argument[2:])
    elif executable == "sed" and any(
        argument == "-i" or argument.startswith("-i") for argument in arguments
    ):
        raise GuardBlocked(
            "ambiguous high-risk Bash command: sed -i; use an Edit tool or an explicit temporary-file write"
        )
    elif executable == "find" and any(
        marker in arguments for marker in ("-delete", "-exec", "-execdir")
    ):
        raise GuardBlocked(f"ambiguous high-risk Bash command: {executable}")
    elif executable in {"install", "patch"}:
        raise GuardBlocked(f"ambiguous high-risk Bash command: {executable}")
    elif executable in {"tar", "unzip", "7z"} and any(
        flag in arguments for flag in ("-x", "--extract", "x")
    ):
        raise GuardBlocked(f"ambiguous high-risk Bash extraction: {executable}")
    elif executable == "git" and arguments:
        action = arguments[0]
        if action in {"mv", "rm"}:
            command_writes([action, *arguments[1:]], writes)
        elif action in {
            "checkout",
            "switch",
            "restore",
            "reset",
            "clean",
            "merge",
            "rebase",
            "cherry-pick",
            "am",
            "apply",
            "stash",
        }:
            raise GuardBlocked(
                f"ambiguous high-risk Bash command: git {action}; "
                "use an activated task and perform the operation explicitly outside the realtime hook"
            )
    elif executable in {"python", "python3", "node", "ruby", "perl"}:
        inline = " ".join(arguments)
        if INLINE_WRITE_SIGNAL.search(inline):
            raise GuardBlocked(
                f"ambiguous high-risk inline {executable} write; use Edit/Write or literal shell destinations"
            )


def bash_writes(command: str) -> list[ShellWrite]:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Bash command must be a non-empty string")
    if re.search(r"\$\(|`|(?:^|[\s;&|])(?:<|>)\(", command):
        raise GuardBlocked(
            "ambiguous high-risk Bash command or process substitution; "
            "run a literal command that the scope guard can inspect"
        )
    tokens = shell_tokens(command)
    writes: list[ShellWrite] = []
    segments: list[list[str]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in SHELL_SEPARATORS:
            segments.append([])
            index += 1
            continue
        if token in WRITE_REDIRECTIONS:
            if index + 1 >= len(tokens):
                raise GuardBlocked("ambiguous Bash redirection without a destination")
            destination = tokens[index + 1]
            add_shell_target(writes, destination, token in {">>", "&>>"})
            index += 2
            continue
        if token in FD_REDIRECTIONS:
            if index + 1 >= len(tokens) or not tokens[index + 1].isdigit():
                raise GuardBlocked("ambiguous Bash file-descriptor redirection")
            index += 2
            continue
        segments[-1].append(token)
        index += 1

    if writes and (
        any(segment and Path(segment[0]).name == "cd" for segment in segments)
        or re.search(r"(?:^|[;&|]\s*)[({]", command)
    ):
        raise GuardBlocked(
            "ambiguous high-risk Bash write after directory/group context change"
        )
    for segment in segments:
        command_writes(segment, writes)
    return writes


def main() -> int:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be a JSON object")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise ValueError("tool_input must be a JSON object")
    tool_name = str(payload.get("tool_name") or "").strip()

    root = Path(
        os.environ.get("CLAUDE_PROJECT_DIR")
        or payload.get("cwd")
        or os.getcwd()
    ).resolve()
    current_path = root / CURRENT_TASK
    if not current_path.exists():
        return 0
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if not isinstance(current, dict):
        raise ValueError("current-task.json must be a JSON object")
    task_id = str(current.get("task_id") or "").strip()
    is_bash = tool_name == "Bash" or (not tool_name and "command" in tool_input)
    if is_bash:
        writes = bash_writes(tool_input.get("command"))
        if writes and not task_id:
            raise GuardBlocked(
                "Bash write requested without an activated task contract"
            )
        for write in writes:
            validate_target(
                root,
                current,
                write.path,
                shell_append_only=write.append_only,
            )
        return 0

    raw_target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_target:
        return 0
    if not task_id:
        raise GuardBlocked(
            f"{tool_name or 'write tool'} requested without an activated task contract"
        )
    validate_target(root, current, raw_target)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GuardBlocked as exc:
        sys.stderr.write(f"[plan-docs] blocked: {exc}.\n")
        raise SystemExit(2)
    except Exception as exc:  # configured write tools must fail closed
        sys.stderr.write(f"[plan-docs] blocked after internal scope-guard error: {exc}\n")
        raise SystemExit(2)
