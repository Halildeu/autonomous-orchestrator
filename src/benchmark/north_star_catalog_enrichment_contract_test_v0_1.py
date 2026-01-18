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
    from src.benchmark.eval_runner import run_eval

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "north_star_catalog_enrich_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    seed_root = ws_root / ".cache" / "inputs"
    bp_seed = seed_root / "bp_catalog.seed.v1.json"
    trend_seed = seed_root / "trend_catalog.seed.v1.json"

    bp_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws_root),
        "items": [
            {
                "id": "bp-ops-003",
                "title": "No-network default",
                "source": "seed",
                "tags": ["core", "topic:uygunluk_risk_guvence_kontrol", "policy", "security"],
                "summary": "Varsayılan ağ kapalı olmalı; network gerektiren adımlar açıkça işaretlenmeli.",
                "evidence_expectations": [
                    "Run loglarında NO_NETWORK=true notu bulunmalı.",
                    "Ağ gerektiren adımlar policy/allowlist ile kontrollü açılmalı.",
                ],
                "remediation": [
                    "Network gerektiren adımlar için explicit allowlist/policy ekle.",
                    "Varsayılan modu NO_NETWORK olacak şekilde fail-closed koru.",
                ],
            }
        ],
    }

    trend_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(ws_root),
        "items": [
            {
                "id": "trend-core-002",
                "title": "Bağlam yönetimi ve uyum (context alignment)",
                "source": "seed",
                "tags": ["core", "topic:baglam_uyum", "drift", "context"],
                "summary": "Bağlam (scope) sınırlarını netleştirip drift’i ölç; kontrat uyumsuzluklarını erken yakala.",
                "evidence_expectations": [
                    "Scope sınırları için kontrat/şema veya doküman referansı bulunmalı.",
                    "Drift sinyali çıktıları deterministik raporlanmalı (sort_keys/stable ordering).",
                ],
                "remediation": [
                    "Scope/kontrat girişlerini tek kaynakta (SSOT) tut ve validate et.",
                    "Triage çıktısında drift ile ilgili net marker ve evidence pointer üret.",
                ],
            }
        ],
    }

    _write_json(bp_seed, bp_payload)
    _write_json(trend_seed, trend_payload)

    out_bp = ws_root / ".cache" / "index" / "bp_catalog.v1.json"
    out_trend = ws_root / ".cache" / "index" / "trend_catalog.v1.json"
    result = _write_seed_catalogs(workspace_root=ws_root, out_bp_catalog=out_bp, out_trend_catalog=out_trend)

    _assert(out_bp.exists(), "bp_catalog should be written")
    _assert(out_trend.exists(), "trend_catalog should be written")
    _assert(result.get("bp_items", 0) == 1, "bp_items should be 1")
    _assert(result.get("trend_items", 0) == 1, "trend_items should be 1")

    out_bp_obj = json.loads(out_bp.read_text(encoding="utf-8"))
    out_trend_obj = json.loads(out_trend.read_text(encoding="utf-8"))
    _assert(out_bp_obj.get("items", [{}])[0].get("summary"), "bp_catalog item.summary should be preserved")
    _assert(out_bp_obj.get("items", [{}])[0].get("evidence_expectations"), "bp_catalog item.evidence_expectations should be preserved")
    _assert(out_bp_obj.get("items", [{}])[0].get("remediation"), "bp_catalog item.remediation should be preserved")
    _assert(out_trend_obj.get("items", [{}])[0].get("summary"), "trend_catalog item.summary should be preserved")
    _assert(out_trend_obj.get("items", [{}])[0].get("evidence_expectations"), "trend_catalog item.evidence_expectations should be preserved")
    _assert(out_trend_obj.get("items", [{}])[0].get("remediation"), "trend_catalog item.remediation should be preserved")

    # Minimal assessment_raw + integrity snapshot so run_eval() can produce findings.
    integrity_path = ws_root / ".cache" / "reports" / "integrity_verify.v1.json"
    _write_json(integrity_path, {"verify_on_read_result": "PASS", "generated_at": _now_iso()})

    raw_path = ws_root / ".cache" / "index" / "assessment_raw.v1.json"
    _write_json(
        raw_path,
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws_root),
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "inputs": {"controls": 1, "metrics": 1},
            "signals": {
                "airrunner_state": {"enabled_effective": True, "auto_mode_enabled_effective": True},
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 0, "report_path": ".cache/script_budget/report.json"},
                "doc_nav": {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0, "report_path": ".cache/reports/doc_graph_report.strict.v1.json"},
                "docs_hygiene": {"repo_md_total_count": 0},
                "docs_drift": {"unmapped_md_count": 0},
                "airunner_jobs": {"stuck": 0, "fail": 0, "jobs_index_path": ".cache/airrunner/jobs_index.v1.json"},
                "pdca_cursor": {"stale_hours": 0.0},
                "airunner_heartbeat": {"stale_seconds": 0, "heartbeat_path": ".cache/airrunner/airrunner_heartbeat.v1.json"},
                "work_intake_noise": {"new_items_24h": 0, "suppressed_24h": 0},
                "integrity": {"status": "PASS"},
            },
            "integration_coherence_signals": {
                "layer_boundary_violations_count": 0,
                "pack_conflict_count": 0,
                "core_unlock_scope_widen_count": 1,
                "schema_fail_count": 0,
            },
        },
    )

    run_eval(workspace_root=ws_root, dry_run=False)
    eval_path = ws_root / ".cache" / "index" / "assessment_eval.v1.json"
    _assert(eval_path.exists(), "assessment_eval should be written")
    eval_obj = json.loads(eval_path.read_text(encoding="utf-8"))
    lens = eval_obj.get("lenses", {}).get("trend_best_practice", {})
    findings = lens.get("findings", {})
    items = findings.get("items", [])
    _assert(isinstance(items, list) and items, "trend_best_practice.findings.items should be non-empty")

    enriched = [it for it in items if isinstance(it, dict) and it.get("id") == "trend-core-002"]
    _assert(enriched, "trend-core-002 must exist in findings")
    it0 = enriched[0]
    _assert(isinstance(it0.get("summary"), str) and it0.get("summary"), "findings item.summary must be present")
    _assert(isinstance(it0.get("evidence_expectations"), list) and it0.get("evidence_expectations"), "findings item.evidence_expectations must be present")
    _assert(isinstance(it0.get("remediation"), list) and it0.get("remediation"), "findings item.remediation must be present")

    print("OK")


if __name__ == "__main__":
    main()

