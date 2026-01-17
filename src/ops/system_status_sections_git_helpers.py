from __future__ import annotations

import subprocess
from pathlib import Path


def _git_status_lines(core_root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _parse_git_status_paths(lines: list[str]) -> list[str]:
    paths: list[str] = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        raw = parts[1].strip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1].strip()
        if raw:
            paths.append(raw)
    return sorted({p for p in paths if p})
