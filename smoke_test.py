from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from ci.smoke_helpers.integration_smoke import (
    _smoke_bootstrap_m3_5,
    _smoke_debt_pipeline,
    _smoke_doc_nav_check,
    _smoke_doc_graph,
    _smoke_json_idempotency_guard,
    _smoke_m10_2_benchmark,
    _smoke_m2_5_runnable,
    _smoke_m3_5_session_ram,
    _smoke_m3_runnable,
    _smoke_m6_5_harvest,
    _smoke_m6_6_ops_index,
    _smoke_m6_7_harvest_cursor,
    _smoke_m6_8_artifact_pointer,
    _smoke_m6_quality_gate,
    _smoke_m7_advisor,
    _smoke_m8_readiness,
    _smoke_pack_conflict_block,
    _smoke_pack_ecosystem,
    _smoke_promotion_bundle,
    _smoke_py_budget_report,
    _smoke_repo_hygiene,
    _smoke_spec_core,
    _smoke_system_status,
)
from ci.smoke_helpers.roadmap_smoke import (
    _smoke_actions_self_heal,
    _smoke_artifact_completeness,
    _smoke_roadmap_drift,
)
from ci.smoke_helpers.utils import prepare_workspace, print_timer, run_ci_smoke, run_cmd


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    os.environ.setdefault("SMOKE_MODE", "1")
    smoke_level = os.environ.get("SMOKE_LEVEL", "full").lower()
    print(f"SMOKE_LEVEL={smoke_level}", flush=True)
    if smoke_level != "fast":
        include_ci = os.environ.get("SMOKE_FULL_INCLUDE_CI", "0") == "1"
        if include_ci:
            t_ci = time.monotonic()
            run_ci_smoke(repo_root)
            print_timer("ci_smoke", t_ci)
        else:
            print("SMOKE_NOTE=ci_smoke_skipped (set SMOKE_FULL_INCLUDE_CI=1 to enable)")
        quota_store_path = repo_root / ".cache" / "tenant_quota_store.v1.json"
        if quota_store_path.exists():
            quota_store_path.unlink()
    if os.environ.get("ORCH_ROADMAP_ORCHESTRATOR") == "1":
        return
    t_ws = time.monotonic()
    ws_dry_run = prepare_workspace(repo_root=repo_root, name="ws_integration_dry_run", prereq_milestones=[])
    ws_integration = prepare_workspace(
        repo_root=repo_root,
        name="ws_integration_demo",
        prereq_milestones=[
            "M1",
            "M2.5",
            "M3",
            "M3.5",
            "M6",
            "M6.5",
            "M6.6",
            "M6.7",
            "M6.8",
            "M7",
            "M8",
            "M8.1",
            "M8.2",
            "M9.1",
            "M9.2",
            "M9.3",
            "M9.4",
        ],
    )
    print_timer("workspace_prepare", t_ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    env.setdefault("SMOKE_MODE", "1")
    env["SMOKE_LEVEL"] = "fast"
    dry_run_milestones = "M2.5,M3,M3.5,M6,M6.5,M6.6,M6.7,M6.8,M7,M8,M8.1,M8.2,M9.1,M9.2,M9.3,M9.4"
    t_dry = time.monotonic()
    run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--milestones",
            dry_run_milestones,
            "--workspace-root",
            str(ws_dry_run.relative_to(repo_root)),
            "--dry-run",
            "true",
            "--dry-run-mode",
            "readonly",
        ],
        env=env,
        fail_msg=f"Smoke test failed: roadmap dry-run readonly failed ({dry_run_milestones}).",
    )
    print_timer("dry_run_readonly", t_dry)
    t_checks = time.monotonic()
    for fn in (
        _smoke_m3_runnable,
        _smoke_m2_5_runnable,
        _smoke_m3_5_session_ram,
        _smoke_m6_quality_gate,
        _smoke_m6_5_harvest,
        _smoke_m6_6_ops_index,
        _smoke_m6_7_harvest_cursor,
        _smoke_m6_8_artifact_pointer,
        _smoke_pack_ecosystem,
    ):
        fn(repo_root=repo_root, ws_dry_run=ws_dry_run, ws_integration=ws_integration)
    _smoke_pack_conflict_block(repo_root=repo_root)
    _smoke_m7_advisor(repo_root=repo_root, ws_dry_run=ws_dry_run, ws_integration=ws_integration)
    _smoke_m8_readiness(repo_root=repo_root, ws_dry_run=ws_dry_run, ws_integration=ws_integration)
    _smoke_system_status(repo_root=repo_root, ws_dry_run=ws_dry_run, ws_integration=ws_integration)
    _smoke_doc_graph(repo_root=repo_root, ws_integration=ws_integration)
    _smoke_doc_nav_check(repo_root=repo_root, ws_integration=ws_integration)
    _smoke_repo_hygiene(repo_root)
    _smoke_debt_pipeline(repo_root=repo_root, ws_integration=ws_integration)
    _smoke_promotion_bundle(repo_root=repo_root, ws_integration=ws_integration)
    print_timer("milestone_checks", t_checks)
    _smoke_bootstrap_m3_5(repo_root)
    _smoke_json_idempotency_guard(repo_root)
    _smoke_spec_core(repo_root)
    _smoke_m10_2_benchmark(repo_root)
    _smoke_py_budget_report(repo_root)
    if smoke_level != "fast":
        t_drift = time.monotonic()
        _smoke_roadmap_drift(repo_root)
        print_timer("roadmap_drift", t_drift)
    t_actions = time.monotonic()
    _smoke_actions_self_heal(repo_root)
    print_timer("actions_self_heal", t_actions)
    if smoke_level != "fast":
        _smoke_artifact_completeness(repo_root)
    if smoke_level == "fast":
        print("SMOKE_OK")


if __name__ == "__main__":
    main()
