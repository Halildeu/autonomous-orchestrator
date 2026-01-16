from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from typing import Callable
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from ci.smoke_helpers.utils import prepare_workspace, print_timer, run_ci_smoke, run_cmd, write_completeness_state
from ci.smoke_helpers.integration_smoke_steps import (
    _smoke_bootstrap_m3_5,
    _smoke_json_idempotency_guard,
    _smoke_m10_2_benchmark,
    _smoke_py_budget_report,
    _smoke_spec_core,
)
from ci.smoke_helpers.integration_smoke_steps2 import (
    _smoke_debt_pipeline,
    _smoke_doc_graph,
    _smoke_doc_nav_check,
    _smoke_auto_loop_counts,
    _smoke_airunner_async,
    _smoke_full_async_job_start,
    _smoke_github_ops_job_pipeline,
    _smoke_extension_help,
    _smoke_extension_isolation,
    _smoke_extension_registry,
    _smoke_release_automation,
    _smoke_promotion_bundle,
    _smoke_repo_hygiene,
    _smoke_system_status,
)
from ci.smoke_helpers.roadmap_smoke import (
    _smoke_actions_self_heal,
    _smoke_artifact_completeness,
    _smoke_roadmap_drift,
)
from src.roadmap.step_templates import RoadmapStepError, VirtualFS, step_create_file, step_create_json_from_template


def run_smoke_sequence(
    *,
    repo_root: Path,
    smoke_level: str,
    resolve_workspace_override: Callable[[Path], Path | None],
) -> None:
    async_job = os.environ.get("SMOKE_FULL_ASYNC_JOB") == "1"
    launcher_mode = smoke_level != "fast" and not async_job
    if smoke_level != "fast" and not launcher_mode:
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
    ws_override = resolve_workspace_override(repo_root)
    demo_prereq_ready = True
    if ws_override is None:
        prereq_milestones = [
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
        ]
        if smoke_level == "fast" or launcher_mode:
            ws_integration = prepare_workspace(
                repo_root=repo_root,
                name="ws_integration_demo",
                prereq_milestones=[],
            )
            demo_prereq_ready = False
            print("CRITICAL_SMOKE_DEMO_PREREQ skipped=true reason=PLAN_ONLY_PREREQ")
        else:
            try:
                ws_integration = prepare_workspace(
                    repo_root=repo_root,
                    name="ws_integration_demo",
                    prereq_milestones=prereq_milestones,
                )
            except SystemExit:
                print("CRITICAL_SMOKE_DEMO_PREREQ attempted=true result=FAIL")
                raise
            print("CRITICAL_SMOKE_DEMO_PREREQ attempted=true result=PASS")
    else:
        ws_integration = ws_override
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
    if demo_prereq_ready:
        for fn in (
            _smoke_m3_runnable,
            _smoke_m2_5_runnable,
            _smoke_m3_5_session_ram,
            _smoke_m6_quality_gate,
            _smoke_m6_5_harvest,
            _smoke_m6_6_ops_index,
            _smoke_layer_boundary,
            _smoke_work_intake_check,
            _smoke_context_router,
            _smoke_m6_7_harvest_cursor,
            _smoke_m6_8_artifact_pointer,
            _smoke_pack_ecosystem,
            _smoke_extension_registry,
            _smoke_extension_help,
            _smoke_extension_isolation,
            _smoke_release_automation,
            _smoke_airunner_async,
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
    else:
        print("SMOKE_NOTE=demo_prereq_skipped_fast")
    _smoke_auto_loop_counts(repo_root=repo_root)
    _smoke_github_ops_job_pipeline(repo_root=repo_root, ws_dry_run=ws_dry_run, ws_integration=ws_integration)
    print_timer("milestone_checks", t_checks)
    _smoke_bootstrap_m3_5(repo_root)
    _smoke_json_idempotency_guard(repo_root)
    _smoke_spec_core(repo_root)
    _smoke_m10_2_benchmark(repo_root)
    _smoke_py_budget_report(repo_root)
    if smoke_level != "fast" and not launcher_mode:
        t_drift = time.monotonic()
        _smoke_roadmap_drift(repo_root)
        print_timer("roadmap_drift", t_drift)
    t_actions = time.monotonic()
    _smoke_actions_self_heal(repo_root)
    print_timer("actions_self_heal", t_actions)
    if launcher_mode:
        _smoke_full_async_job_start(repo_root=repo_root, ws_integration=ws_integration)
    if smoke_level != "fast" and not launcher_mode:
        _smoke_artifact_completeness(repo_root)
    if smoke_level == "fast":
        print("SMOKE_OK")
def _smoke_m3_runnable(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_catalog_path = ws_dry_run / ".cache" / "index" / "catalog.v1.json"
    if dry_catalog_path.exists():
        raise SystemExit("Smoke test failed: M3 dry-run must not write derived catalog: " + str(dry_catalog_path))
    catalog_path = ws_integration / ".cache" / "index" / "catalog.v1.json"
    if not catalog_path.exists():
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["ORCH_ROADMAP_RUNNER"] = "1"
        env.setdefault("SMOKE_MODE", "1")
        env["SMOKE_LEVEL"] = "fast"
        run_cmd(
            repo_root=repo_root,
            argv=[
                sys.executable,
                "-m",
                "src.tenant.build_catalog",
                "--workspace-root",
                str(ws_integration.relative_to(repo_root)),
                "--dry-run",
                "false",
            ],
            env=env,
            fail_msg="Smoke test failed: DEMO_CATALOG_MISSING build_catalog failed: " + str(catalog_path),
        )
    if not catalog_path.exists():
        raise SystemExit("Smoke test failed: DEMO_CATALOG_MISSING catalog.v1.json missing: " + str(catalog_path))
    try:
        catalog_obj = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: DEMO_CATALOG_PARSE catalog.v1.json must be valid JSON: " + str(catalog_path)) from e
    packs = catalog_obj.get("packs") if isinstance(catalog_obj, dict) else None
    if not (isinstance(packs, list) and any(isinstance(p, dict) and p.get("pack_id") == "pack-demo" for p in packs)):
        raise SystemExit("Smoke test failed: catalog must include pack-demo.")
    packs_found = len([p for p in packs if isinstance(p, dict)]) if isinstance(packs, list) else 0
    print(f"CRITICAL_M3_RUNNABLE ok=true packs_found={packs_found}")


def _smoke_m2_5_runnable(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_formats_index_path = ws_dry_run / ".cache" / "index" / "formats.v1.json"
    if dry_formats_index_path.exists():
        raise SystemExit("Smoke test failed: M2.5 dry-run must not write formats index: " + str(dry_formats_index_path))
    formats_index_path = ws_integration / ".cache" / "index" / "formats.v1.json"
    if not formats_index_path.exists():
        raise SystemExit("Smoke test failed: M2.5 apply must write formats index: " + str(formats_index_path))
    try:
        idx = json.loads(formats_index_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: formats.v1.json must be valid JSON.") from e
    formats = idx.get("formats") if isinstance(idx, dict) else None
    if not isinstance(formats, list):
        raise SystemExit("Smoke test failed: formats index must contain formats[] list.")
    ids = []
    for f in formats:
        if isinstance(f, dict) and isinstance(f.get("id"), str):
            ids.append(f["id"])
    ids = sorted(set(ids))
    if "FORMAT-AUTOPILOT-CHAT" not in ids:
        raise SystemExit("Smoke test failed: formats index must include FORMAT-AUTOPILOT-CHAT.")
    print(f"CRITICAL_M2_5_RUNNABLE ok=true formats_found={len(ids)}")


def _smoke_m3_5_session_ram(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_session_path = ws_dry_run / ".cache" / "sessions" / "default" / "session_context.v1.json"
    if dry_session_path.exists():
        raise SystemExit("Smoke test failed: M3.5 dry-run must not write session context: " + str(dry_session_path))
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    session_path = ws_integration / ".cache" / "sessions" / "default" / "session_context.v1.json"
    if not session_path.exists():
        raise SystemExit("Smoke test failed: M3.5 apply must write session context: " + str(session_path))
    try:
        from src.session.context_store import load_context
        ctx = load_context(session_path)
    except Exception as e:
        raise SystemExit("Smoke test failed: session_context.v1.json must be schema-valid.") from e
    hashes = ctx.get("hashes") if isinstance(ctx, dict) else None
    sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    if not (isinstance(sha, str) and len(sha) == 64):
        raise SystemExit("Smoke test failed: session context must include hashes.session_context_sha256.")
    roadmap_path = (repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json").resolve()
    current_sha = hashlib.sha256(roadmap_path.read_bytes()).hexdigest()
    milestones_obj = json.loads(roadmap_path.read_text(encoding="utf-8"))
    milestone_ids = []
    for ms in milestones_obj.get("milestones", []) if isinstance(milestones_obj.get("milestones"), list) else []:
        if isinstance(ms, dict) and isinstance(ms.get("id"), str):
            milestone_ids.append(ms["id"])
    state_path = ws_integration / ".cache" / "roadmap_state.v1.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "roadmap_path": str(roadmap_path),
                "workspace_root": str(ws_integration.resolve()),
                "roadmap_sha256": current_sha,
                "last_roadmap_sha256": None,
                "drift_detected": False,
                "completed_milestones_meta": {},
                "bootstrapped": True,
                "completed_milestones": milestone_ids,
                "current_milestone": None,
                "attempts": {},
                "last_result": {"status": "OK", "milestone": None, "evidence_path": None, "error_code": None},
                "quarantine": {"milestone": None, "until": None, "reason": None},
                "backoff": {"seconds": 0, "next_try_at": None},
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    proc_finish = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-finish",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--max-minutes",
            "1",
            "--sleep-seconds",
            "0",
            "--max-steps-per-iteration",
            "1",
        ],
        env=env,
        fail_msg="Smoke test failed: roadmap-finish (session hash) failed.",
        capture=True,
    )
    try:
        finish_out = json.loads(proc_finish.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: roadmap-finish must print JSON.") from e
    evidence = finish_out.get("evidence") if isinstance(finish_out, dict) else None
    if not (isinstance(evidence, list) and evidence and isinstance(evidence[0], str)):
        raise SystemExit("Smoke test failed: roadmap-finish output must include evidence path list.")
    run_dir = (repo_root / evidence[0]).resolve()
    out_path = run_dir / "output.json"
    if not out_path.exists():
        raise SystemExit("Smoke test failed: roadmap-finish evidence must include output.json: " + str(out_path))
    out_obj = json.loads(out_path.read_text(encoding="utf-8"))
    session_hash = out_obj.get("session_context_hash") if isinstance(out_obj, dict) else None
    if session_hash != sha:
        raise SystemExit("Smoke test failed: roadmap-finish output.json must include session_context_hash matching session sha.")
    print(f"CRITICAL_M3_5_SESSION_RAM ok=true sha_prefix={sha[:8]}")


def _smoke_m6_quality_gate(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_report_path = ws_dry_run / ".cache" / "index" / "quality_gate_report.v1.json"
    if dry_report_path.exists():
        raise SystemExit("Smoke test failed: M6 dry-run must not write quality report: " + str(dry_report_path))
    report_path = ws_integration / ".cache" / "index" / "quality_gate_report.v1.json"
    if not report_path.exists():
        raise SystemExit("Smoke test failed: M6 apply must write quality report: " + str(report_path))
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: quality_gate_report must be valid JSON.") from e
    status = report.get("status") if isinstance(report, dict) else None
    if status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: quality gate status must be OK or WARN.")
    print(f"CRITICAL_M6_QUALITY_GATE ok=true status={status}")


def _smoke_m6_5_harvest(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_out_path = ws_dry_run / ".cache" / "learning" / "public_candidates.v1.json"
    if dry_out_path.exists():
        raise SystemExit("Smoke test failed: M6.5 dry-run must not write public candidates: " + str(dry_out_path))
    out_path = ws_integration / ".cache" / "learning" / "public_candidates.v1.json"
    if not out_path.exists():
        raise SystemExit("Smoke test failed: M6.5 apply must write public candidates: " + str(out_path))
    bundle = json.loads(out_path.read_text(encoding="utf-8"))
    candidates = bundle.get("candidates") if isinstance(bundle, dict) else None
    if not isinstance(candidates, list):
        raise SystemExit("Smoke test failed: public candidates must include candidates list.")
    kinds_set: set[str] = set()
    for c in candidates:
        if isinstance(c, dict):
            k = c.get("kind")
            if isinstance(k, str):
                kinds_set.add(k)
    kinds = sorted(kinds_set)
    if "PACK_HINT" not in kinds or "FORMAT_HINT" not in kinds:
        raise SystemExit("Smoke test failed: candidates must include PACK_HINT and FORMAT_HINT.")
    sani = bundle.get("sanitization") if isinstance(bundle, dict) else None
    sani_status = sani.get("status") if isinstance(sani, dict) else None
    if sani_status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: sanitization.status must be OK or WARN.")
    print(f"CRITICAL_M6_5_HARVEST ok=true candidates={len(candidates)} sanitization={sani_status}")


def _smoke_m6_6_ops_index(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_run_index = ws_dry_run / ".cache" / "index" / "run_index.v1.json"
    dry_dlq_index = ws_dry_run / ".cache" / "index" / "dlq_index.v1.json"
    if dry_run_index.exists():
        raise SystemExit("Smoke test failed: M6.6 dry-run must not write run_index: " + str(dry_run_index))
    if dry_dlq_index.exists():
        raise SystemExit("Smoke test failed: M6.6 dry-run must not write dlq_index: " + str(dry_dlq_index))
    run_index_path = ws_integration / ".cache" / "index" / "run_index.v1.json"
    dlq_index_path = ws_integration / ".cache" / "index" / "dlq_index.v1.json"
    if not run_index_path.exists():
        raise SystemExit("Smoke test failed: M6.6 apply must write run_index: " + str(run_index_path))
    if not dlq_index_path.exists():
        raise SystemExit("Smoke test failed: M6.6 apply must write dlq_index: " + str(dlq_index_path))
    run_index = json.loads(run_index_path.read_text(encoding="utf-8"))
    dlq_index = json.loads(dlq_index_path.read_text(encoding="utf-8"))
    run_items = run_index.get("items") if isinstance(run_index, dict) else None
    dlq_items = dlq_index.get("items") if isinstance(dlq_index, dict) else None
    runs = len(run_items) if isinstance(run_items, list) else 0
    dlq = len(dlq_items) if isinstance(dlq_items, list) else 0
    print(f"CRITICAL_M6_6_OPS_INDEX ok=true runs={runs} dlq={dlq}")


def _smoke_layer_boundary(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    ws = prepare_workspace(repo_root=repo_root, name="ws_layer_boundary_demo", prereq_milestones=[])
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    env.setdefault("SMOKE_MODE", "1")
    run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "layer-boundary-check",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--mode",
            "report",
        ],
        env=env,
        fail_msg="Smoke test failed: layer-boundary-check report failed.",
    )
    report_path = ws / ".cache" / "reports" / "layer_boundary_report.v1.json"
    if not report_path.exists():
        raise SystemExit("Smoke test failed: layer boundary report missing.")
    schema_path = repo_root / "schemas" / "layer-boundary-report.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    report_obj = json.loads(report_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report_obj)
    blocked = report_obj.get("would_block") if isinstance(report_obj, dict) else None
    blocked_count = len(blocked) if isinstance(blocked, list) else 0
    print(f"CRITICAL_LAYER_BOUNDARY ok=true blocked={blocked_count}")


def _smoke_work_intake_check(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    gap_path = ws_integration / ".cache" / "index" / "gap_register.v1.json"
    if not gap_path.exists():
        gap_path.parent.mkdir(parents=True, exist_ok=True)
        gap_payload = {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "gaps": [
                {
                    "id": "GAP-SMOKE-1",
                    "severity": "low",
                    "status": "open",
                    "risk_class": "low",
                    "effort": "low",
                    "evidence_pointers": [".cache/index/assessment_raw.v1.json"],
                }
            ],
        }
        gap_path.write_text(json.dumps(gap_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "work-intake-check",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chat",
            "false",
            "--detail",
            "true",
        ],
        env=env,
        fail_msg="Smoke test failed: work-intake-check command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: work-intake-check must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: work-intake-check output must be JSON object.")

    work_intake_path = payload.get("work_intake_path")
    if not isinstance(work_intake_path, str) or not work_intake_path:
        raise SystemExit("Smoke test failed: work_intake_path missing in work-intake-check output.")
    intake_abs = (ws_integration / work_intake_path).resolve()
    if not intake_abs.exists():
        raise SystemExit("Smoke test failed: work_intake.v1.json missing at " + str(intake_abs))

    schema_path = repo_root / "schemas" / "work-intake.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    intake_obj = json.loads(intake_abs.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(intake_obj)

    counts = payload.get("counts_by_bucket") if isinstance(payload.get("counts_by_bucket"), dict) else {}
    incidents = int(counts.get("INCIDENT", 0)) if isinstance(counts, dict) else 0
    tickets = int(counts.get("TICKET", 0)) if isinstance(counts, dict) else 0
    projects = int(counts.get("PROJECT", 0)) if isinstance(counts, dict) else 0
    print(f"CRITICAL_WORK_INTAKE ok=true incidents={incidents} tickets={tickets} projects={projects}")


def _smoke_context_router(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "context-router-check",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chat",
            "false",
            "--text",
            "Context router smoke request.",
            "--artifact-type",
            "context_pack",
            "--domain",
            "ops",
            "--kind",
            "support",
        ],
        env=env,
        fail_msg="Smoke test failed: context-router-check command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: context-router-check must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: context-router-check output must be JSON object.")

    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise SystemExit("Smoke test failed: context-router-check missing request_id.")

    manual_path = ws_integration / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json"
    if not manual_path.exists():
        raise SystemExit("Smoke test failed: manual request file missing: " + str(manual_path))

    router_path = ws_integration / ".cache" / "reports" / "context_pack_router_result.v1.json"
    if not router_path.exists():
        raise SystemExit("Smoke test failed: context_pack_router_result missing.")
    router_obj = json.loads(router_path.read_text(encoding="utf-8"))

    schema_path = repo_root / "schemas" / "context-pack-router-result.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(router_obj)

    bucket = router_obj.get("bucket") if isinstance(router_obj, dict) else None
    if bucket not in {"INCIDENT", "TICKET", "PROJECT", "ROADMAP"}:
        raise SystemExit("Smoke test failed: context router bucket invalid.")
    print(f"CRITICAL_CONTEXT_ROUTER ok=true bucket={bucket}")


def _smoke_m6_7_harvest_cursor(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_cursor_path = ws_dry_run / ".cache" / "learning" / "harvest_cursor.v1.json"
    if dry_cursor_path.exists():
        raise SystemExit("Smoke test failed: M6.7 dry-run must not write harvest cursor: " + str(dry_cursor_path))
    cursor_path = ws_integration / ".cache" / "learning" / "harvest_cursor.v1.json"
    if not cursor_path.exists():
        raise SystemExit("Smoke test failed: M6.7 apply must write harvest cursor: " + str(cursor_path))
    cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
    if not isinstance(cursor, dict) or cursor.get("version") != "v1":
        raise SystemExit("Smoke test failed: harvest cursor must be a v1 object.")
    print("CRITICAL_M6_7_HARVEST_CURSOR ok=true")


def _smoke_m6_8_artifact_pointer(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_pointer_path = ws_dry_run / ".cache" / "artifacts" / "public_candidates.pointer.v1.json"
    if dry_pointer_path.exists():
        raise SystemExit("Smoke test failed: M6.8 dry-run must not write pointer: " + str(dry_pointer_path))
    pointer_path = ws_integration / ".cache" / "artifacts" / "public_candidates.pointer.v1.json"
    if not pointer_path.exists():
        raise SystemExit("Smoke test failed: M6.8 apply must write pointer: " + str(pointer_path))
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    stored_rel = pointer.get("stored_path") if isinstance(pointer, dict) else None
    if not isinstance(stored_rel, str) or not stored_rel:
        raise SystemExit("Smoke test failed: pointer must include stored_path.")
    stored_path = (ws_integration / stored_rel).resolve()
    if not stored_path.exists():
        raise SystemExit("Smoke test failed: pointer stored_path missing: " + str(stored_path))
    print("CRITICAL_M6_8_ARTIFACT_POINTER ok=true")


def _smoke_pack_ecosystem(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_index_path = ws_dry_run / ".cache" / "index" / "pack_capability_index.v1.json"
    if dry_index_path.exists():
        raise SystemExit("Smoke test failed: M9.2 dry-run must not write pack index: " + str(dry_index_path))
    index_path = ws_integration / ".cache" / "index" / "pack_capability_index.v1.json"
    if not index_path.exists():
        raise SystemExit("Smoke test failed: M9.2 apply must write pack index: " + str(index_path))
    try:
        obj = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: pack_capability_index must be valid JSON.") from e
    packs = obj.get("packs") if isinstance(obj, dict) else None
    pack_ids_set: set[str] = set()
    if isinstance(packs, list):
        for pack in packs:
            if not isinstance(pack, dict):
                continue
            pack_id = pack.get("pack_id")
            if isinstance(pack_id, str):
                pack_ids_set.add(pack_id)
    pack_ids = sorted(pack_ids_set)
    expected = {"pack-software-architecture", "pack-document-management"}
    if not expected.issubset(set(pack_ids)):
        raise SystemExit("Smoke test failed: pack index must include example pack ids.")
    hard = len(obj.get("hard_conflicts", [])) if isinstance(obj.get("hard_conflicts"), list) else 0
    soft = len(obj.get("soft_conflicts", [])) if isinstance(obj.get("soft_conflicts"), list) else 0
    print(f"CRITICAL_PACK_ECOSYSTEM ok=true packs={len(pack_ids)} hard={hard} soft={soft}")
    selection_path = ws_integration / ".cache" / "index" / "pack_selection_trace.v1.json"
    if not selection_path.exists():
        raise SystemExit("Smoke test failed: M9.3 apply must write pack_selection_trace: " + str(selection_path))
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selected = selection.get("selected_pack_ids") if isinstance(selection, dict) else None
    selected_ids = [s for s in selected if isinstance(s, str)] if isinstance(selected, list) else []
    if not selected_ids:
        raise SystemExit("Smoke test failed: pack selection must include selected_pack_ids.")
    print(f"CRITICAL_PACK_SELECTION ok=true selected={len(selected_ids)}")
    pack_adv_path = ws_integration / ".cache" / "learning" / "pack_advisor_suggestions.v1.json"
    if not pack_adv_path.exists():
        raise SystemExit("Smoke test failed: M9.4 apply must write pack_advisor_suggestions: " + str(pack_adv_path))
    pack_adv = json.loads(pack_adv_path.read_text(encoding="utf-8"))
    suggestions = pack_adv.get("suggestions") if isinstance(pack_adv, dict) else None
    if not isinstance(suggestions, list):
        raise SystemExit("Smoke test failed: pack advisor suggestions must be a list.")
    print(f"CRITICAL_PACK_ADVISOR ok=true suggestions={len(suggestions)}")


def _smoke_pack_conflict_block(*, repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_pack_conflict_demo"
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    env.setdefault("SMOKE_MODE", "1")
    env["SMOKE_LEVEL"] = "fast"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg="Smoke test failed: pack conflict workspace-bootstrap failed.",
    )
    pack_dir = ws / "packs" / "pack-conflict-demo"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_manifest = {
        "pack_id": "pack-conflict-demo",
        "version": "1.0.0",
        "lifecycle_state": "active",
        "iso_kernel_refs": {
            "context_ref": "tenant/TENANT-DEFAULT/context.v1.md",
            "stakeholders_ref": "tenant/TENANT-DEFAULT/stakeholders.v1.md",
            "scope_ref": "tenant/TENANT-DEFAULT/scope.v1.md",
            "criteria_ref": "tenant/TENANT-DEFAULT/criteria.v1.md",
            "gate_level": "warn",
        },
        "provides": {
            "intents": ["urn:pack:arch:adr_draft"],
            "workflows": ["WF_ALT"],
            "formats": ["FORMAT-AUTOPILOT-CHAT"],
            "capability_refs": ["capabilities/CAP_ARCH_ADR_DRAFT.v1.json"],
            "format_refs": ["formats/format-autopilot-chat.v1.json"],
        },
        "namespace_prefix": "CAP_ARCH",
        "conflict_policy": {
            "hard_conflict": "fail",
            "soft_conflict": "warn",
            "deterministic_tie_break": "pack_id_lexicographic",
        },
    }
    (pack_dir / "pack.manifest.v1.json").write_text(json.dumps(pack_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    roadmap_path = (repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json").resolve()
    current_sha = hashlib.sha256(roadmap_path.read_bytes()).hexdigest()
    roadmap_obj = json.loads(roadmap_path.read_text(encoding="utf-8"))
    milestone_ids = [ms["id"] for ms in roadmap_obj.get("milestones", []) if isinstance(ms, dict) and isinstance(ms.get("id"), str)]
    write_completeness_state(ws=ws, roadmap_path=roadmap_path, roadmap_sha=current_sha, milestone_ids=milestone_ids)
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "roadmap-finish",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--max-minutes",
            "1",
            "--sleep-seconds",
            "0",
            "--max-steps-per-iteration",
            "1",
        ],
        env=env,
        fail_msg="Smoke test failed: pack conflict roadmap-finish failed.",
        capture=True,
    )
    out = json.loads(proc.stdout.strip() or "{}")
    if not out.get("pack_conflict_blocked"):
        raise SystemExit("Smoke test failed: pack_conflict_blocked must be true.")
    report_path = ws / ".cache" / "index" / "pack_validation_report.json"
    if not report_path.exists():
        raise SystemExit("Smoke test failed: pack_validation_report.json missing.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    hard_conflicts = report.get("hard_conflicts") if isinstance(report, dict) else None
    hard_count = len(hard_conflicts) if isinstance(hard_conflicts, list) else 0
    actions_path = ws / ".cache" / "roadmap_actions.v1.json"
    actions = json.loads(actions_path.read_text(encoding="utf-8")).get("actions", []) if actions_path.exists() else []
    if not any(isinstance(a, dict) and a.get("kind") == "PACK_CONFLICT" and a.get("severity") == "FAIL" for a in actions):
        raise SystemExit("Smoke test failed: PACK_CONFLICT action missing.")
    if (ws / ".cache" / "index" / "pack_capability_index.v1.json").exists():
        raise SystemExit("Smoke test failed: pack index must not be rebuilt under hard conflict.")
    print(f"CRITICAL_PACK_CONFLICT_BLOCK ok=true hard_conflicts={hard_count}")


def _smoke_m7_advisor(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_out_path = ws_dry_run / ".cache" / "learning" / "advisor_suggestions.v1.json"
    if dry_out_path.exists():
        raise SystemExit("Smoke test failed: M7 dry-run must not write advisor suggestions: " + str(dry_out_path))
    out_path = ws_integration / ".cache" / "learning" / "advisor_suggestions.v1.json"
    if not out_path.exists():
        raise SystemExit("Smoke test failed: M7 apply must write advisor suggestions: " + str(out_path))
    try:
        bundle = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: advisor_suggestions.v1.json must be valid JSON.") from e
    schema_path = repo_root / "schemas" / "advisor-suggestions.schema.json"
    if not schema_path.exists():
        raise SystemExit("Smoke test failed: missing advisor suggestions schema: " + str(schema_path))
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(bundle)
    except Exception as e:
        raise SystemExit("Smoke test failed: advisor suggestions must validate against schema.") from e
    suggestions = bundle.get("suggestions") if isinstance(bundle, dict) else None
    if not (isinstance(suggestions, list) and suggestions):
        raise SystemExit("Smoke test failed: advisor suggestions must include non-empty suggestions list.")
    kinds_set: set[str] = set()
    for s in suggestions:
        if isinstance(s, dict):
            k = s.get("kind")
            if isinstance(k, str):
                kinds_set.add(k)
    if not kinds_set.intersection({"NEXT_MILESTONE", "MAINTAINABILITY", "QUALITY"}):
        raise SystemExit("Smoke test failed: advisor suggestions missing expected kinds.")
    safety = bundle.get("safety") if isinstance(bundle, dict) else None
    safety_status = safety.get("status") if isinstance(safety, dict) else None
    if safety_status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: advisor safety.status must be OK or WARN.")
    print(f"CRITICAL_M7_ADVISOR ok=true suggestions={len(suggestions)}")


def _smoke_m8_readiness(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_out_path = ws_dry_run / ".cache" / "ops" / "autopilot_readiness.v1.json"
    if dry_out_path.exists():
        raise SystemExit("Smoke test failed: M8 dry-run must not write readiness report: " + str(dry_out_path))
    out_path = ws_integration / ".cache" / "ops" / "autopilot_readiness.v1.json"
    if not out_path.exists():
        raise SystemExit("Smoke test failed: M8 apply must write readiness report: " + str(out_path))
    try:
        report = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: autopilot_readiness.v1.json must be valid JSON.") from e
    schema_path = repo_root / "schemas" / "autopilot-readiness.schema.json"
    if not schema_path.exists():
        raise SystemExit("Smoke test failed: missing autopilot readiness schema: " + str(schema_path))
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
    except Exception as e:
        raise SystemExit("Smoke test failed: autopilot readiness must validate against schema.") from e
    status = report.get("status") if isinstance(report, dict) else None
    if status not in {"READY", "NOT_READY"}:
        raise SystemExit("Smoke test failed: autopilot readiness status must be READY or NOT_READY.")
    checks = report.get("checks") if isinstance(report, dict) else None
    if not isinstance(checks, list):
        raise SystemExit("Smoke test failed: autopilot readiness must include checks list.")
    has_workspace = any(isinstance(c, dict) and c.get("category") == "WORKSPACE" for c in checks)
    if not has_workspace:
        raise SystemExit("Smoke test failed: autopilot readiness must include WORKSPACE check.")
    fails = len([c for c in checks if isinstance(c, dict) and c.get("status") == "FAIL"])
    print(f"CRITICAL_M8_READINESS ok=true status={status} fails={fails}")
