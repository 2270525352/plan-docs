#!/usr/bin/env python3
"""Atomically append one verbatim U-* record without rewriting prior bytes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile


RELATIVE_PATH = Path("docs/plan-docs/00-source/用户原话.md")
HEADER = "# 用户原话\n"


class AppendError(RuntimeError):
    pass


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def append_record(
    project: Path,
    source: str,
    context: str,
    verbatim: str,
    recorded_at: str,
) -> str:
    if not verbatim:
        raise AppendError("verbatim content must not be empty")
    if any("\n" in value or "\r" in value for value in (source, context, recorded_at)):
        raise AppendError("source, context and time must be single-line values")
    project = project.resolve()
    target = project / RELATIVE_PATH
    lock_name = hashlib.sha256(str(target).encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"plan-docs-user-words-{lock_name}.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        before = target.read_bytes() if target.exists() else HEADER.encode("utf-8")
        text = before.decode("utf-8")
        if not text.startswith("# 用户原话\n"):
            raise AppendError(f"{RELATIVE_PATH} has an invalid header")
        ids = [int(value) for value in re.findall(r"(?m)^## U-(\d{3,})\s*$", text)]
        if ids != list(range(1, len(ids) + 1)):
            raise AppendError("existing U-* IDs are duplicated or out of order")
        record_id = f"U-{(ids[-1] + 1 if ids else 1):03d}"
        separator = "" if before.endswith(b"\n\n") else ("\n" if before.endswith(b"\n") else "\n\n")
        indented = "\n".join(f"  {line}" for line in verbatim.splitlines())
        record = (
            f"{separator}## {record_id}\n\n"
            f"record_id: {record_id}\n\n"
            f"time: {recorded_at}\n\n"
            f"source: {source}\n\n"
            f"context: {context}\n\n"
            "verbatim: |\n"
            f"{indented}\n"
        )
        after = before + record.encode("utf-8")
        if not after.startswith(before):
            raise AppendError("internal append-only invariant failed")
        atomic_write(target, after)
    print(f"[plan-docs] appended {record_id} to {target}")
    return record_id


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--context", required=True)
    content = parser.add_mutually_exclusive_group(required=True)
    content.add_argument("--verbatim")
    content.add_argument("--verbatim-file")
    parser.add_argument(
        "--time",
        default=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    arguments = parse_args(sys.argv[1:])
    try:
        value = (
            Path(arguments.verbatim_file).read_text(encoding="utf-8")
            if arguments.verbatim_file
            else arguments.verbatim
        )
        raise SystemExit(
            0
            if append_record(
                Path(arguments.project),
                arguments.source,
                arguments.context,
                value,
                arguments.time,
            )
            else 2
        )
    except (AppendError, OSError, UnicodeError) as exc:
        print(f"[plan-docs] append error: {exc}", file=sys.stderr)
        raise SystemExit(2)
