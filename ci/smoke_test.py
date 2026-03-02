from __future__ import annotations

import os
import sys
from pathlib import Path

# Support both `python ci/smoke_test.py` and `python -m ci.smoke_test`.
if __package__ in {None, ""}:
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from ci.smoke_helpers.integration_smoke import run_smoke_sequence


def _resolve_workspace_override(repo_root: Path) -> Path | None:
    raw = (os.environ.get("SMOKE_WORKSPACE_ROOT") or "").strip()
    if not raw:
        return None
    ws = Path(raw)
    ws = (repo_root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    try:
        ws.relative_to(repo_root.resolve())
    except Exception as e:
        raise SystemExit("Smoke test failed: SMOKE_WORKSPACE_ROOT must be within repo_root.") from e
    if not ws.exists() or not ws.is_dir():
        raise SystemExit("Smoke test failed: SMOKE_WORKSPACE_ROOT is missing or not a directory.")
    print(f"SMOKE_NOTE=workspace_override path={ws}")
    return ws


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("SMOKE_MODE", "1")
    smoke_level = os.environ.get("SMOKE_LEVEL", "full").lower()
    print(f"SMOKE_LEVEL={smoke_level}", flush=True)
    run_smoke_sequence(
        repo_root=repo_root,
        smoke_level=smoke_level,
        resolve_workspace_override=_resolve_workspace_override,
    )


if __name__ == "__main__":
    main()
