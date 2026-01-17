from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_system_status_integration_coherence_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "index" / "north_star_catalog.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "packs": [],
            "controls": [],
            "metrics": [],
            "warnings": [],
        },
    )
    _write_json(
        ws / ".cache" / "index" / "assessment_eval.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "status": "OK",
            "report_only": False,
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "raw_ref": ".cache/index/assessment_raw.v1.json",
            "bp_catalog_ref": ".cache/index/bp_catalog.v1.json",
            "trend_catalog_ref": ".cache/index/trend_catalog.v1.json",
            "scores": {"maturity_avg": 0.0, "coverage": 0.0},
            "inputs": {"controls": 0, "metrics": 0, "bp_items": 0, "trend_items": 0},
            "lenses": {
                "integration_coherence": {
                    "status": "WARN",
                    "score": 0.5,
                    "classification": "WARN",
                    "coverage": 1.0,
                    "reasons": ["pack_conflicts_warn"],
                }
            },
            "notes": [],
        },
    )
    _write_json(
        ws / ".cache" / "index" / "gap_register.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "gaps": [
                {
                    "id": "GAP-EVAL-LENS-integration_coherence-pack_conflicts_warn",
                    "metric_id": "eval_lens:integration_coherence:pack_conflicts_warn",
                    "severity": "medium",
                    "risk_class": "medium",
                    "effort": "medium",
                    "status": "open",
                    "notes": "Integration coherence WARN: pack conflicts.",
                }
            ],
        },
    )

    policy = _load_policy(core_root=repo_root, workspace_root=ws)
    system_status = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = system_status.get("sections") if isinstance(system_status.get("sections"), dict) else {}
    bench = sections.get("benchmark") if isinstance(sections.get("benchmark"), dict) else {}
    eval_lenses = bench.get("eval_lenses") if isinstance(bench.get("eval_lenses"), dict) else {}
    integration = eval_lenses.get("integration_coherence")
    if not isinstance(integration, dict):
        raise SystemExit("system_status_integration_coherence_surface_contract_test failed: lens missing")
    if integration.get("classification") != "WARN":
        raise SystemExit("system_status_integration_coherence_surface_contract_test failed: classification mismatch")
    if integration.get("reasons_count") != 1:
        raise SystemExit("system_status_integration_coherence_surface_contract_test failed: reasons_count mismatch")
    if integration.get("gap_count") != 1:
        raise SystemExit("system_status_integration_coherence_surface_contract_test failed: gap_count mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
