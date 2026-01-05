"""Program-led Codex home bootstrap (workspace-scoped, deterministic)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _copy_atomic(src: Path, dst: Path) -> None:
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_bytes(src.read_bytes())
    tmp.replace(dst)


def ensure_codex_home(workspace_root: str) -> Dict[str, str]:
    ws = Path(workspace_root).resolve()
    target = ws / ".cache" / "codex_home"
    target.mkdir(parents=True, exist_ok=True)

    repo_root = _find_repo_root(Path(__file__).resolve())
    template = repo_root / ".codex" / "config.toml"
    if not template.exists():
        raise SystemExit("CODEX_HOME bootstrap failed: missing template .codex/config.toml.")

    config_path = target / "config.toml"
    if not config_path.exists():
        _copy_atomic(template, config_path)

    return {"CODEX_HOME": str(target)}
