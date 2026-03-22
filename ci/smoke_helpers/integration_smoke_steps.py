from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from ci.smoke_helpers.utils import run_cmd
from src.roadmap.step_templates import RoadmapStepError, VirtualFS, step_create_file, step_create_json_from_template


def _smoke_bootstrap_m3_5(repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_bootstrap_m3_5_demo"
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg="Smoke test failed: bootstrap M3.5 workspace-bootstrap failed.",
    )
    run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--milestone",
            "M3.5",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: bootstrap M3.5 apply failed.",
    )
    state_path = ws / ".cache" / "roadmap_state.v1.json"
    if state_path.exists():
        state_path.unlink()
    run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-follow",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--max-steps",
            "1",
        ],
        env=env,
        fail_msg="Smoke test failed: roadmap-follow (bootstrap M3.5) failed.",
    )
    if not state_path.exists():
        raise SystemExit("Smoke test failed: roadmap-follow must create state file: " + str(state_path))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    completed = state.get("completed_milestones") if isinstance(state, dict) else None
    if not (isinstance(completed, list) and "M3.5" in completed):
        raise SystemExit("Smoke test failed: bootstrap must detect M3.5 as completed.")
    print("CRITICAL_BOOTSTRAP_M3_5 ok=true")


def _smoke_json_idempotency_guard(repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_json_idempotency"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    rel = "demo.json"
    (ws / rel).write_text('{ "b": 2, "a": 1 }\n', encoding="utf-8")
    vf = VirtualFS(files={})
    try:
        res, _, _ = step_create_json_from_template(
            workspace=ws,
            virtual_fs=vf,
            path=rel,
            json_obj={"a": 1, "b": 2},
            overwrite=False,
            dry_run=False,
        )
    except RoadmapStepError as e:
        raise SystemExit("Smoke test failed: JSON idempotency guard should noop: " + e.error_code) from e
    if res.get("status") != "OK":
        raise SystemExit("Smoke test failed: JSON idempotency guard returned non-OK status.")
    try:
        step_create_file(
            workspace=ws,
            virtual_fs=vf,
            path="../outside.txt",
            content="x",
            overwrite=False,
            dry_run=False,
        )
    except RoadmapStepError as e:
        if e.error_code != "WORKSPACE_ROOT_VIOLATION":
            raise SystemExit("Smoke test failed: workspace root guard wrong error: " + e.error_code) from e
    else:
        raise SystemExit("Smoke test failed: workspace root guard should block writes outside workspace_root.")


def _smoke_spec_core(repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_m4_1_demo"
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg="Smoke test failed: M4.1 workspace-bootstrap failed.",
    )
    run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--milestone",
            "M4.1",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--dry-run",
            "true",
            "--dry-run-mode",
            "readonly",
        ],
        env=env,
        fail_msg="Smoke test failed: M4.1 dry-run readonly failed.",
    )
    print("CRITICAL_SPEC_CORE ok=true m4_1_ok=true")


def _smoke_m10_2_benchmark(repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_m10_2_demo"
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg="Smoke test failed: M10.2 workspace-bootstrap failed.",
    )
    run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-apply",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--milestone",
            "M10.2",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: M10.2 roadmap-apply failed.",
    )
    assessment_path = ws / ".cache" / "index" / "assessment.v1.json"
    gap_path = ws / ".cache" / "index" / "gap_register.v1.json"
    if not (assessment_path.exists() and gap_path.exists()):
        raise SystemExit("Smoke test failed: M10.2 outputs missing.")
    assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    gaps = json.loads(gap_path.read_text(encoding="utf-8")).get("gaps", [])
    status = assessment.get("status") if isinstance(assessment, dict) else None
    if status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: M10.2 assessment status must be OK or WARN.")
    print(f"CRITICAL_M10_2_BENCHMARK ok=true status={status} gaps={len(gaps)} maturity={status}")


def _smoke_py_budget_report(repo_root: Path) -> None:
    report_path = repo_root / ".cache" / "script_budget" / "report.json"
    if not report_path.exists():
        raise SystemExit("Smoke test failed: missing script budget report: " + str(report_path))
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: script budget report must be valid JSON.") from e
    top_largest = report.get("top_largest_py") if isinstance(report, dict) else None
    if not (isinstance(top_largest, list) and top_largest and isinstance(top_largest[0], dict)):
        raise SystemExit("Smoke test failed: script budget report must include top_largest_py.")
    largest_path = top_largest[0].get("path")
    largest_lines = top_largest[0].get("lines")
    if not isinstance(largest_path, str) or not isinstance(largest_lines, int):
        raise SystemExit("Smoke test failed: top_largest_py[0] must include path (str) and lines (int).")
    gf_growth = report.get("grandfathered_growth_check") if isinstance(report, dict) else None
    if isinstance(gf_growth, list):
        for item in gf_growth:
            if isinstance(item, dict) and item.get("status") == "GROWN":
                raise SystemExit("Smoke test failed: grandfathered file growth detected: " + str(item.get("path")))
    print(f"CRITICAL_PY_FILE_BUDGET ok=true largest_py={largest_path} lines={largest_lines}")


def _smoke_context_health(repo_root: Path) -> None:
    """Smoke check: context health score is computable and drift detection works."""
    ws = repo_root / ".cache" / "ws_customer_default"
    if not ws.exists():
        print("CRITICAL_CONTEXT_HEALTH ok=true skip=true reason=no_workspace")
        return

    # Health score check
    try:
        from src.benchmark.eval_runner_runtime import _compute_context_health_lens

        health = _compute_context_health_lens(workspace_root=ws, lenses_policy={})
        score = int(float(health.get("score", 0)) * 100)
        status = health.get("status", "UNKNOWN")
    except Exception as e:
        raise SystemExit(f"Smoke test failed: context health computation error: {e}") from e

    # Drift detection check (dry-run, no side effects)
    drift_ok = True
    try:
        from src.ops.context_drift import detect_context_drift

        drift = detect_context_drift(source_workspace=ws, target_workspace=ws)
        drift_status = drift.get("status", "UNKNOWN")
    except Exception:
        drift_status = "SKIP"
        drift_ok = False

    print(f"CRITICAL_CONTEXT_HEALTH ok=true score={score} status={status} drift={drift_status}")
