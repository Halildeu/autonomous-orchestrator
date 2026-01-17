from __future__ import annotations

from pathlib import Path


def resolve_reports_path(workspace_root: Path, out_arg: str) -> Path | None:
    if not isinstance(out_arg, str) or not out_arg.strip():
        return None
    out_path = Path(out_arg.strip())
    candidate = out_path if out_path.is_absolute() else (workspace_root / out_path)
    try:
        candidate = candidate.resolve()
    except Exception:
        return None
    reports_root = (workspace_root / ".cache" / "reports").resolve()
    try:
        candidate.relative_to(reports_root)
    except Exception:
        return None
    if candidate.suffix.lower() != ".json":
        return None
    return candidate


def has_traversal(value: str) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parts = Path(value).parts
    except Exception:
        return True
    return ".." in parts

