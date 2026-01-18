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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import _write_seed_catalogs

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "north_star_seed_fallback_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    core_root = ws_root / "tmp_core_root"
    if core_root.exists():
        shutil.rmtree(core_root)

    bp_seed = core_root / "docs" / "OPERATIONS" / "north_star_bp_catalog.seed.v1.json"
    trend_seed = core_root / "docs" / "OPERATIONS" / "north_star_trend_catalog.seed.v1.json"

    _write_json(
        bp_seed,
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": "REPO_SEED",
            "items": [
                {
                    "id": "bp-001",
                    "title": "Evidence-first",
                    "source": "seed",
                    "tags": ["core", "evidence"],
                    "summary": "Her iddia kanıtla desteklenir.",
                    "evidence_expectations": ["Closeout JSON + evidence_paths."],
                    "remediation": ["Closeout-write standardize et."],
                }
            ],
        },
    )
    _write_json(
        trend_seed,
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": "REPO_SEED",
            "items": [
                {
                    "id": "trend-core-001",
                    "title": "AI otomasyon potansiyeli",
                    "source": "seed",
                    "tags": ["core", "topic:ai_otomasyon"],
                    "summary": "Otomasyon guardrail ile yapılır.",
                    "evidence_expectations": ["NO_NETWORK default."],
                    "remediation": ["Policy ile sınırla."],
                }
            ],
        },
    )

    out_bp = ws_root / ".cache" / "index" / "bp_catalog.v1.json"
    out_trend = ws_root / ".cache" / "index" / "trend_catalog.v1.json"
    result = _write_seed_catalogs(
        workspace_root=ws_root,
        out_bp_catalog=out_bp,
        out_trend_catalog=out_trend,
        core_root=core_root,
    )

    _assert(out_bp.exists(), "bp_catalog should be written via fallback seed")
    _assert(out_trend.exists(), "trend_catalog should be written via fallback seed")
    used = result.get("seed_paths_used") if isinstance(result, dict) else None
    _assert(isinstance(used, list) and used, "seed_paths_used must be present")
    _assert(any("north_star_bp_catalog.seed.v1.json" in p for p in used), "bp fallback seed path must be used")
    _assert(any("north_star_trend_catalog.seed.v1.json" in p for p in used), "trend fallback seed path must be used")

    first_bp = out_bp.read_text(encoding="utf-8")
    first_trend = out_trend.read_text(encoding="utf-8")
    _write_seed_catalogs(
        workspace_root=ws_root,
        out_bp_catalog=out_bp,
        out_trend_catalog=out_trend,
        core_root=core_root,
    )
    _assert(out_bp.read_text(encoding="utf-8") == first_bp, "bp catalog should be deterministic")
    _assert(out_trend.read_text(encoding="utf-8") == first_trend, "trend catalog should be deterministic")

    print("OK")


if __name__ == "__main__":
    main()

