from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import _write_seed_catalogs

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "trend_seed_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    seed_root = ws_root / ".cache" / "inputs"
    bp_seed = seed_root / "bp_catalog.seed.v1.json"
    trend_seed = seed_root / "trend_catalog.seed.v1.json"
    seed_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws_root),
        "items": [
            {"id": "bp-001", "title": "Evidence-first artifacts", "source": "seed", "tags": ["ops"]},
            {"id": "bp-002", "title": "Deterministic outputs", "source": "seed", "tags": ["determinism"]},
            {"id": "bp-003", "title": "No-network default", "source": "seed", "tags": ["policy"]},
            {"id": "bp-004", "title": "Policy-driven gates", "source": "seed", "tags": ["policy"]},
            {"id": "bp-005", "title": "Doc-nav strict coverage", "source": "seed", "tags": ["docs"]},
        ],
    }
    trend_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws_root),
        "items": [
            {"id": "trend-001", "title": "Jobify long ops", "source": "seed", "tags": ["ops"]},
            {"id": "trend-002", "title": "No-wait polling", "source": "seed", "tags": ["ops"]},
            {"id": "trend-003", "title": "Gap remediation packs", "source": "seed", "tags": ["gaps"]},
            {"id": "trend-004", "title": "Explicit job_id triage", "source": "seed", "tags": ["ops"]},
            {"id": "trend-005", "title": "Work intake dedup timestamps", "source": "seed", "tags": ["intake"]},
        ],
    }

    _write_json(bp_seed, seed_payload)
    _write_json(trend_seed, trend_payload)

    out_bp = ws_root / ".cache" / "index" / "bp_catalog.v1.json"
    out_trend = ws_root / ".cache" / "index" / "trend_catalog.v1.json"
    result = _write_seed_catalogs(workspace_root=ws_root, out_bp_catalog=out_bp, out_trend_catalog=out_trend)

    _assert(out_bp.exists(), "bp_catalog should be written")
    _assert(out_trend.exists(), "trend_catalog should be written")
    _assert(result.get("bp_items", 0) >= 5, "bp_items should be >= 5")
    _assert(result.get("trend_items", 0) >= 5, "trend_items should be >= 5")

    first_bp = out_bp.read_text(encoding="utf-8")
    first_trend = out_trend.read_text(encoding="utf-8")
    _write_seed_catalogs(workspace_root=ws_root, out_bp_catalog=out_bp, out_trend_catalog=out_trend)
    _assert(out_bp.read_text(encoding="utf-8") == first_bp, "bp_catalog should be deterministic")
    _assert(out_trend.read_text(encoding="utf-8") == first_trend, "trend_catalog should be deterministic")

    print("OK")


if __name__ == "__main__":
    main()
