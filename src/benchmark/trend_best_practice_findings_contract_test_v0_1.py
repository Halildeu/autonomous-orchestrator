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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _is_abs(path_value: str) -> bool:
    try:
        return Path(path_value).is_absolute()
    except Exception:
        return False


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.eval_runner import run_eval

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "trend_findings_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    # Minimal inputs for run_eval() with deterministic signal triggers.
    integrity_path = ws_root / ".cache" / "reports" / "integrity_verify.v1.json"
    _write_json(
        integrity_path,
        {
            "verify_on_read_result": "PASS",
            "generated_at": _now_iso(),
        },
    )

    # Evidence placeholders (paths used by findings; pointers must be non-absolute).
    doc_nav_report = ws_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    _write_json(doc_nav_report, {"status": "OK", "generated_at": _now_iso(), "placeholders_count": 40})
    budget_report = ws_root / ".cache" / "script_budget" / "report.json"
    _write_json(budget_report, {"status": "OK", "hard_exceeded": 0, "soft_exceeded": 2})
    jobs_index = ws_root / ".cache" / "github_ops" / "jobs_index.v1.json"
    _write_json(jobs_index, {"version": "v1", "generated_at": _now_iso(), "jobs": []})
    release_manifest = ws_root / ".cache" / "reports" / "release_manifest.v1.json"
    _write_json(release_manifest, {"version": "v1", "generated_at": _now_iso(), "status": "OK"})
    _write_json(ws_root / ".cache" / "airrunner" / "jobs_index.v1.json", {"version": "v1", "jobs": []})
    _write_json(
        ws_root / ".cache" / "airrunner" / "airrunner_heartbeat.v1.json",
        {"version": "v1", "generated_at": _now_iso(), "ended_at": _now_iso()},
    )
    _write_json(ws_root / ".cache" / "index" / "pdca_cursor.v1.json", {"version": "v1", "last_run_at": _now_iso()})
    _write_json(
        ws_root / ".cache" / "index" / "work_intake.v1.json",
        {"version": "v1", "generated_at": _now_iso(), "items": []},
    )
    _write_json(ws_root / ".cache" / "reports" / "repo_hygiene.v1.json", {"version": "v1", "status": "OK"})
    _write_json(ws_root / ".cache" / "reports" / "docs_drift_signal.v1.json", {"version": "v1", "unmapped_md_count": 0})
    _write_json(ws_root / ".cache" / "reports" / "layer_boundary_report.v1.json", {"version": "v1", "would_block": []})
    _write_json(ws_root / ".cache" / "index" / "pack_validation_report.json", {"hard_conflicts": [], "soft_conflicts": []})
    _write_json(ws_root / ".cache" / "reports" / "preflight_stamp.v1.json", {"gates": {"validate_schemas": "PASS"}})

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
                "script_budget": {
                    "hard_exceeded": 0,
                    "soft_exceeded": 2,
                    "report_path": ".cache/script_budget/report.json",
                },
                "doc_nav": {
                    "placeholders_count": 40,
                    "broken_refs": 0,
                    "orphan_critical": 0,
                    "report_path": ".cache/reports/doc_graph_report.strict.v1.json",
                },
                "docs_hygiene": {"repo_md_total_count": 0},
                "docs_drift": {"unmapped_md_count": 0},
                "airunner_jobs": {"stuck": 0, "fail": 0, "jobs_index_path": ".cache/airunner/jobs_index.v1.json"},
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

    trend_catalog = ws_root / ".cache" / "index" / "trend_catalog.v1.json"
    bp_catalog = ws_root / ".cache" / "index" / "bp_catalog.v1.json"
    _write_json(
        trend_catalog,
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws_root),
            "items": [
                {
                    "id": "trend-obs-001",
                    "title": "Doc navigation placeholders should stay low",
                    "source": "seed",
                    "tags": ["core", "topic:gozlemlenebilirlik_izleme_olcme", "doc_nav"],
                },
                {
                    "id": "trend-ctx-001",
                    "title": "Context alignment / drift control",
                    "source": "seed",
                    "tags": ["core", "topic:baglam_uyum", "drift"],
                },
            ],
        },
    )
    _write_json(
        bp_catalog,
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws_root),
            "items": [
                {
                    "id": "bp-ops-001",
                    "title": "Soft budget should stay under control",
                    "source": "seed",
                    "tags": ["core", "topic:maliyet_verimlilik_kaynak", "budget"],
                }
            ],
        },
    )

    # Run twice and compare the findings block (not whole file, because generated_at is expected to change).
    res1 = run_eval(workspace_root=ws_root, dry_run=False)
    _assert(res1.get("status") in {"OK", "WARN", "SKIPPED"}, "run_eval should return a status payload")

    eval_path = ws_root / ".cache" / "index" / "assessment_eval.v1.json"
    _assert(eval_path.exists(), "assessment_eval should be written")
    eval_obj_1 = json.loads(eval_path.read_text(encoding="utf-8"))

    lens_names = [
        "trend_best_practice",
        "ai_ops_fit",
        "github_ops_release",
        "integration_coherence",
        "operability",
    ]

    def _lens_findings(eval_obj: dict, lens: str) -> dict | None:
        lenses = eval_obj.get("lenses") if isinstance(eval_obj.get("lenses"), dict) else {}
        lens_obj = lenses.get(lens) if isinstance(lenses.get(lens), dict) else {}
        findings = lens_obj.get("findings")
        return findings if isinstance(findings, dict) else None

    findings_by_lens_1: dict[str, dict] = {}
    for lens in lens_names:
        f = _lens_findings(eval_obj_1, lens)
        _assert(isinstance(f, dict), f"{lens}.findings must be present")
        _assert(f.get("version") == "v1", f"{lens}.findings.version must be v1")
        items = f.get("items")
        _assert(isinstance(items, list) and items, f"{lens}.findings.items must be non-empty list")
        findings_by_lens_1[lens] = f

    trend_items_1 = findings_by_lens_1["trend_best_practice"].get("items")
    _assert(isinstance(trend_items_1, list) and len(trend_items_1) >= 3, "trend_best_practice must include catalog items")

    # Evidence pointers must be workspace-relative (no absolute leakage).
    for lens, findings in findings_by_lens_1.items():
        items = findings.get("items")
        _assert(isinstance(items, list), f"{lens}.findings.items must be a list")
        for entry in items:
            _assert(isinstance(entry, dict), f"{lens}: findings item must be object")
            ev = entry.get("evidence_pointers")
            _assert(isinstance(ev, list) and ev, f"{lens}: evidence_pointers must be non-empty list")
            _assert(all(isinstance(p, str) and p.strip() for p in ev), f"{lens}: evidence_pointers entries must be strings")
            _assert(all(not _is_abs(p) for p in ev), f"{lens}: evidence_pointers must be workspace-relative (no absolute paths)")

    # Deterministic ordering and stable mapping: second run yields identical findings block.
    run_eval(workspace_root=ws_root, dry_run=False)
    eval_obj_2 = json.loads(eval_path.read_text(encoding="utf-8"))
    findings_by_lens_2: dict[str, dict] = {}
    for lens in lens_names:
        f = _lens_findings(eval_obj_2, lens)
        _assert(isinstance(f, dict), f"{lens}.findings must be present on second run")
        findings_by_lens_2[lens] = f

    _assert(findings_by_lens_1 == findings_by_lens_2, "findings must be deterministic across runs (per-lens)")

    print("OK")


if __name__ == "__main__":
    main()
