from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"lensless_gap_contract_test failed: {msg}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.benchmark.gap_engine import build_gap_register

    gap = build_gap_register(
        controls=[],
        metrics=[],
    )
    gaps = gap.get("gaps") if isinstance(gap, dict) else []
    gap_ids = [str(g.get("id") or "") for g in gaps if isinstance(g, dict)]
    _must(not any(gid.startswith("GAP-EVAL-LENS-") for gid in gap_ids), "lens gaps must not be produced")
    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
