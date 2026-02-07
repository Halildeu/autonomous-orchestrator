from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    # src/ops/commands/common.py -> commands -> ops -> src -> repo root
    return Path(__file__).resolve().parents[3]


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return (json.loads(path.read_text(encoding="utf-8")), None)
    except Exception as e:
        return (None, str(e))


def parse_iso8601_ts(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print(" | ".join(headers))
        print("count=0")
        return

    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))

    def fmt(r: list[str]) -> str:
        return " | ".join((r[i] if i < len(r) else "").ljust(widths[i]) for i in range(len(headers)))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt(r))
    print(f"count={len(rows)}")


def is_git_work_tree(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return proc.returncode == 0 and (proc.stdout or "").strip() == "true"


def git_ref_exists(root: Path, ref: str) -> bool:
    if not ref or not isinstance(ref, str):
        return False
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return proc.returncode == 0


def run_step(root: Path, cmd: list[str], *, stage: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=root,
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        # Keep outputs minimal/safe; do not print secrets.
        print(f"POLICY_CHECK_FAIL stage={stage}")
        return (proc.returncode, proc.stdout or "", proc.stderr or "")
    return (0, proc.stdout or "", proc.stderr or "")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
