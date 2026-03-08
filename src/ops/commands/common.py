from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CUSTOMER_WORKSPACE_REL = Path(".cache/ws_customer_default")


def repo_root() -> Path:
    # src/ops/commands/common.py -> commands -> ops -> src -> repo root
    return Path(__file__).resolve().parents[3]


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)


def resolve_workspace_root_arg(
    root: Path,
    workspace_arg: str | Path,
    *,
    prefer_customer_workspace: bool = False,
) -> Path | None:
    raw = str(workspace_arg or "").strip()
    if not raw:
        return None

    ws = Path(raw)
    candidate = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()

    if prefer_customer_workspace:
        customer_root = (root / DEFAULT_CUSTOMER_WORKSPACE_REL).resolve()
        if customer_root.exists() and customer_root.is_dir() and candidate == root.resolve():
            candidate = customer_root

    if not candidate.exists() or not candidate.is_dir():
        return None
    return candidate


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
