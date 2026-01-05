from __future__ import annotations

from pathlib import Path


def resolve_workspace(workspace_arg: str) -> Path:
    return Path(workspace_arg).resolve()


def resolve_out_dir(*, workspace: Path, out_arg: str) -> Path:
    out_dir = Path(out_arg)
    out_dir = (workspace / out_dir).resolve() if not out_dir.is_absolute() else out_dir.resolve()
    try:
        out_dir.relative_to(workspace)
    except ValueError:
        raise SystemExit("--out must be within --workspace for safety.")
    return out_dir
