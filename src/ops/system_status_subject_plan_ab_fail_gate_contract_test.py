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
        raise SystemExit(f"system_status_subject_plan_ab_fail_gate_contract_test failed: {message}")


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


def _seed_subject_plan_ab(ws: Path, *, missing_profiles: list[str]) -> None:
    available_profiles = [p for p in ["A", "B", "C"] if p not in set(missing_profiles)]
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
                        "status": "FAIL" if missing_profiles else "OK",
                        "available_profiles": available_profiles,
                        "missing_profiles": missing_profiles,
                        "best_profile": available_profiles[0] if available_profiles else "",
                        "best_score": 1.0 if available_profiles else 0.0,
                        "profiles": [],
                    },
                }
            },
        },
    )


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_system_status_subject_plan_ab_fail_gate"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _seed_minimum_benchmark_inputs(ws)

    _seed_subject_plan_ab(ws, missing_profiles=["A", "B"])
    policy = _load_policy(core_root=repo_root, workspace_root=ws)
    report_fail = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections_fail = report_fail.get("sections") if isinstance(report_fail.get("sections"), dict) else {}
    bench_fail = sections_fail.get("benchmark") if isinstance(sections_fail.get("benchmark"), dict) else {}
    ab_fail = bench_fail.get("subject_plan_ab_summary") if isinstance(bench_fail.get("subject_plan_ab_summary"), dict) else {}
    _must(str(bench_fail.get("status") or "") == "FAIL", "benchmark status must be FAIL when profiles are missing")
    _must(str(ab_fail.get("status") or "") == "FAIL", "subject_plan_ab_summary status must be FAIL when profiles are missing")
    _must(
        sorted(str(x) for x in (ab_fail.get("missing_profiles") if isinstance(ab_fail.get("missing_profiles"), list) else []))
        == ["A", "B"],
        "missing_profiles mismatch on fail run",
    )

    _seed_subject_plan_ab(ws, missing_profiles=[])
    report_ok = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections_ok = report_ok.get("sections") if isinstance(report_ok.get("sections"), dict) else {}
    bench_ok = sections_ok.get("benchmark") if isinstance(sections_ok.get("benchmark"), dict) else {}
    ab_ok = bench_ok.get("subject_plan_ab_summary") if isinstance(bench_ok.get("subject_plan_ab_summary"), dict) else {}
    _must(str(bench_ok.get("status") or "") == "OK", "benchmark status must be OK when A/B/C profiles are complete")
    _must(str(ab_ok.get("status") or "") == "OK", "subject_plan_ab_summary status must be OK when A/B/C profiles are complete")
    _must(
        (ab_ok.get("missing_profiles") if isinstance(ab_ok.get("missing_profiles"), list) else []) == [],
        "missing_profiles must be empty on OK run",
    )
    _must(
        sorted(str(x) for x in (ab_ok.get("available_profiles") if isinstance(ab_ok.get("available_profiles"), list) else []))
        == ["A", "B", "C"],
        "available_profiles must include A/B/C on OK run",
    )

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
