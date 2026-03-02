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


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"system_status_profile_order_compare_surface_contract_test failed: {message}")


def _seed_minimum_benchmark_inputs(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "index" / "north_star_catalog.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "workspace_root": str(ws),
            "packs": [],
            "controls": [{"id": "CTRL-1"}],
            "metrics": [{"id": "METRIC-1"}],
            "warnings": [],
        },
    )
    _write_json(
        ws / ".cache" / "index" / "assessment_raw.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "status": "OK",
            "scores": {"maturity_avg": 1.0, "coverage": 1.0},
        },
    )
    _write_json(
        ws / ".cache" / "index" / "assessment_eval.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "status": "OK",
            "assessment": {},
            "scores": {"maturity_avg": 1.0, "coverage": 1.0},
            "notes": [],
        },
    )
    _write_json(
        ws / ".cache" / "index" / "gap_register.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "gaps": [],
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "integrity_verify.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "status": "OK",
            "missing": [],
        },
    )
    _write_json(
        ws / ".cache" / "reports" / "benchmark_scorecard.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "status": "OK",
            "controls_count": 1,
            "metrics_count": 1,
            "gaps_count": 0,
            "maturity_avg": 1.0,
        },
    )


def _seed_subject_plan_ab(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "north_star_subject_plan_ab_test.v1.json",
        {
            "version": "v1",
            "updated_at": "2026-03-02T00:00:00Z",
            "last_subject_id": "subject_demo",
            "subjects": {
                "subject_demo": {
                    "subject_id": "subject_demo",
                    "updated_at": "2026-03-02T00:00:00Z",
                    "last_requested_profile": "C",
                    "last_run_set": "abc",
                    "latest_by_profile": {},
                    "history": [],
                    "comparison": {
                        "status": "OK",
                        "available_profiles": ["A", "B", "C"],
                        "missing_profiles": [],
                        "best_profile": "C",
                        "best_score": 1.0,
                        "profiles": [],
                    },
                }
            },
        },
    )


def _seed_profile_order_compare(ws: Path) -> None:
    _write_json(
        ws / ".cache" / "reports" / "north_star_profile_order_ab_compare.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-02T00:00:00Z",
            "workspace_root": str(ws),
            "subject_id": "subject_demo",
            "policy_override_path": str(
                ws / ".cache" / "policy_overrides" / "policy_north_star_subject_plan.override.v1.json"
            ),
            "restore_state": "removed",
            "orders_spec": "CBA",
            "scenarios": [
                {
                    "scenario_id": "order_1",
                    "preferred_profile_order": ["C", "B", "A"],
                    "run_status": "OK",
                    "comparison_status": "OK",
                    "best_profile": "C",
                    "best_score": 1.0,
                    "available_profiles": ["A", "B", "C"],
                    "missing_profiles": [],
                    "comparison_preferred_profile_order": ["C", "B", "A"],
                    "error_code": "",
                    "report_path": ".cache/reports/north_star_subject_plan_ab_test.v1.json",
                }
            ],
            "summary": {
                "total_scenarios": 1,
                "all_runs_ok": True,
                "all_comparisons_ok": True,
                "best_profile_counts": {"C": 1},
            },
            "notes": ["subject_id=subject_demo", "orders_spec=CBA"],
            "errors": [],
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_system_status_profile_order_compare_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _seed_minimum_benchmark_inputs(ws)
    _seed_subject_plan_ab(ws)
    _seed_profile_order_compare(ws)

    policy = _load_policy(core_root=repo_root, workspace_root=ws)
    report = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = report.get("sections") if isinstance(report.get("sections"), dict) else {}
    bench = sections.get("benchmark") if isinstance(sections.get("benchmark"), dict) else {}
    compare = bench.get("profile_order_compare_summary") if isinstance(bench.get("profile_order_compare_summary"), dict) else {}

    _must(str(compare.get("status") or "") == "OK", "profile_order_compare_summary status must be OK")
    _must(str(compare.get("subject_id") or "") == "subject_demo", "subject_id mismatch")
    _must(str(compare.get("orders_spec") or "") == "CBA", "orders_spec mismatch")
    _must(int(compare.get("scenarios_count") or 0) == 1, "scenarios_count mismatch")
    _must(bool(compare.get("all_runs_ok")), "all_runs_ok mismatch")
    _must(bool(compare.get("all_comparisons_ok")), "all_comparisons_ok mismatch")
    best_counts = compare.get("best_profile_counts") if isinstance(compare.get("best_profile_counts"), dict) else {}
    _must(int(best_counts.get("C") or 0) == 1, "best_profile_counts.C mismatch")
    _must(str(compare.get("report_path") or "") == ".cache/reports/north_star_profile_order_ab_compare.v1.json", "report_path mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
