from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

from ci.smoke_helpers.utils import run_cmd, write_completeness_state
from src.roadmap.step_templates import RoadmapStepError, VirtualFS, step_create_file, step_create_json_from_template


def _smoke_m3_runnable(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_catalog_path = ws_dry_run / ".cache" / "index" / "catalog.v1.json"
    if dry_catalog_path.exists():
        raise SystemExit("Smoke test failed: M3 dry-run must not write derived catalog: " + str(dry_catalog_path))
    catalog_path = ws_integration / ".cache" / "index" / "catalog.v1.json"
    try:
        catalog_obj = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: catalog.v1.json must be valid JSON: " + str(catalog_path)) from e
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


def _smoke_system_status(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_json = ws_dry_run / ".cache" / "reports" / "system_status.v1.json"
    dry_md = ws_dry_run / ".cache" / "reports" / "system_status.v1.md"
    if dry_json.exists() or dry_md.exists():
        raise SystemExit("Smoke test failed: M8.1 dry-run must not write system status reports.")
    out_json = ws_integration / ".cache" / "reports" / "system_status.v1.json"
    out_md = ws_integration / ".cache" / "reports" / "system_status.v1.md"
    if not out_json.exists() or not out_md.exists():
        raise SystemExit("Smoke test failed: M8.1 apply must write system status JSON + MD.")
    try:
        report = json.loads(out_json.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: system_status.v1.json must be valid JSON.") from e
    schema_path = repo_root / "schemas" / "system-status.schema.json"
    if not schema_path.exists():
        raise SystemExit("Smoke test failed: missing system status schema: " + str(schema_path))
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
    except Exception as e:
        raise SystemExit("Smoke test failed: system status must validate against schema.") from e
    md_text = out_md.read_text(encoding="utf-8")
    required_headings = [
        "ISO Core",
        "Spec Core",
        "Core integrity",
        "Core lock",
        "Project boundary",
        "Projects",
        "Catalog",
        "Packs",
        "Formats",
        "Session",
        "Quality",
        "Harvest",
        "Advisor",
        "Pack Advisor",
        "Readiness",
        "Actions",
        "Repo hygiene",
        "Doc graph",
        "Auto-heal",
    ]
    for heading in required_headings:
        if heading not in md_text:
            raise SystemExit("Smoke test failed: system status MD missing heading: " + heading)
    overall = report.get("overall_status") if isinstance(report, dict) else None
    if overall not in {"OK", "WARN", "NOT_READY"}:
        raise SystemExit("Smoke test failed: system status overall_status must be OK, WARN, or NOT_READY.")
    spec_core = report.get("sections", {}).get("spec_core") if isinstance(report, dict) else None
    if not isinstance(spec_core, dict):
        raise SystemExit("Smoke test failed: system status must include spec_core section.")
    spec_paths = spec_core.get("paths") if isinstance(spec_core.get("paths"), list) else None
    if not isinstance(spec_paths, list):
        raise SystemExit("Smoke test failed: spec_core.paths must be a list.")
    required_paths = {"schemas/spec-core.schema.json", "schemas/spec-capability.schema.json"}
    if not required_paths.issubset(set(str(p) for p in spec_paths)):
        raise SystemExit("Smoke test failed: spec_core.paths must include spec-core schemas.")
    core_integrity = report.get("sections", {}).get("core_integrity") if isinstance(report, dict) else None
    if not isinstance(core_integrity, dict):
        raise SystemExit("Smoke test failed: system status must include core_integrity section.")
    if core_integrity.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: core_integrity.status must be OK, WARN, or FAIL.")
    if core_integrity.get("git_clean") is not True:
        raise SystemExit("Smoke test failed: core_integrity.git_clean must be true in smoke.")
    core_lock = report.get("sections", {}).get("core_lock") if isinstance(report, dict) else None
    if not isinstance(core_lock, dict):
        raise SystemExit("Smoke test failed: system status must include core_lock section.")
    if core_lock.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: core_lock.status must be OK or WARN.")
    project_boundary = report.get("sections", {}).get("project_boundary") if isinstance(report, dict) else None
    if not isinstance(project_boundary, dict):
        raise SystemExit("Smoke test failed: system status must include project_boundary section.")
    if project_boundary.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: project_boundary.status must be OK or WARN.")
    projects = report.get("sections", {}).get("projects") if isinstance(report, dict) else None
    if not isinstance(projects, dict):
        raise SystemExit("Smoke test failed: system status must include projects section.")
    if projects.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: projects.status must be OK or WARN.")
    if not isinstance(projects.get("active_projects"), list):
        raise SystemExit("Smoke test failed: projects.active_projects must be a list.")
    bench = report.get("sections", {}).get("benchmark") if isinstance(report, dict) else None
    if not isinstance(bench, dict):
        raise SystemExit("Smoke test failed: system status must include benchmark section.")
    if not isinstance(bench.get("gaps_by_severity"), dict):
        raise SystemExit("Smoke test failed: benchmark.gaps_by_severity must be a dict.")
    if not isinstance(bench.get("top_next_actions"), list):
        raise SystemExit("Smoke test failed: benchmark.top_next_actions must be a list.")
    packs = report.get("sections", {}).get("packs") if isinstance(report, dict) else None
    if not isinstance(packs, dict):
        raise SystemExit("Smoke test failed: system status must include packs section.")
    if packs.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: packs.status must be OK, WARN, or FAIL.")
    if not isinstance(packs.get("selected_pack_ids"), list):
        raise SystemExit("Smoke test failed: packs.selected_pack_ids must be a list.")
    if not isinstance(packs.get("selection_trace_path"), str):
        raise SystemExit("Smoke test failed: packs.selection_trace_path must be a string.")
    pack_adv = report.get("sections", {}).get("pack_advisor") if isinstance(report, dict) else None
    if not isinstance(pack_adv, dict):
        raise SystemExit("Smoke test failed: system status must include pack_advisor section.")
    if pack_adv.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: pack_advisor.status must be OK, WARN, or FAIL.")
    repo_hygiene = report.get("sections", {}).get("repo_hygiene") if isinstance(report, dict) else None
    if not isinstance(repo_hygiene, dict):
        raise SystemExit("Smoke test failed: system status must include repo_hygiene section.")
    if repo_hygiene.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: repo_hygiene.status must be OK or WARN.")
    if not isinstance(repo_hygiene.get("unexpected_top_level_dirs"), int):
        raise SystemExit("Smoke test failed: repo_hygiene.unexpected_top_level_dirs must be int.")
    if not isinstance(repo_hygiene.get("tracked_generated_files"), int):
        raise SystemExit("Smoke test failed: repo_hygiene.tracked_generated_files must be int.")
    doc_graph = report.get("sections", {}).get("doc_graph") if isinstance(report, dict) else None
    if not isinstance(doc_graph, dict):
        raise SystemExit("Smoke test failed: system status must include doc_graph section.")
    if doc_graph.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: doc_graph.status must be OK, WARN, or FAIL.")
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "system-status",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: manage system-status command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: system-status must print JSON.") from e
    if not isinstance(out, dict) or "overall_status" not in out:
        raise SystemExit("Smoke test failed: system-status output must include overall_status.")
    print("CRITICAL_CORE_IMMUTABILITY ok=true git_clean=true")
    proj = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "project-status",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "autopilot_chat",
        ],
        env=env,
        fail_msg="Smoke test failed: project-status command failed.",
        capture=True,
    )
    proj_text = proj.stdout.strip()
    for heading in ["PREVIEW:", "RESULT:", "EVIDENCE:", "ACTIONS:", "NEXT:"]:
        if heading not in proj_text:
            raise SystemExit("Smoke test failed: project-status missing heading: " + heading)
    try:
        proj_json = json.loads(proj_text.splitlines()[-1])
    except Exception as e:
        raise SystemExit("Smoke test failed: project-status trailing JSON invalid.") from e
    if not isinstance(proj_json, dict):
        raise SystemExit("Smoke test failed: project-status JSON must be an object.")
    if proj_json.get("core_lock") != "ENABLED":
        raise SystemExit("Smoke test failed: project-status core_lock must be ENABLED.")
    if proj_json.get("project_manifest_present") is not True:
        raise SystemExit("Smoke test failed: project manifest must be present.")
    print(
        f"CRITICAL_PROJECT_STATUS ok=true next={proj_json.get('next_milestone')} status={proj_json.get('status')}"
    )
    core_lock_enabled = proj_json.get("core_lock") == "ENABLED"
    boundary_ok = proj_json.get("project_manifest_present") is True
    print("CRITICAL_PROJECT_BOUNDARY ok=true core_lock=true manifest=true")
    print(f"CRITICAL_CORE_LOCK ok=true locked={core_lock_enabled} boundary_ok={boundary_ok}")
    portfolio = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "portfolio-status",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "autopilot_chat",
        ],
        env=env,
        fail_msg="Smoke test failed: portfolio-status command failed.",
        capture=True,
    )
    portfolio_text = portfolio.stdout.strip()
    for heading in ["PREVIEW:", "RESULT:", "EVIDENCE:", "ACTIONS:", "NEXT:"]:
        if heading not in portfolio_text:
            raise SystemExit("Smoke test failed: portfolio-status missing heading: " + heading)
    try:
        portfolio_json = json.loads(portfolio_text.splitlines()[-1])
    except Exception as e:
        raise SystemExit("Smoke test failed: portfolio-status trailing JSON invalid.") from e
    if not isinstance(portfolio_json, dict):
        raise SystemExit("Smoke test failed: portfolio-status JSON must be an object.")
    print(
        f"CRITICAL_PORTFOLIO_STATUS ok=true projects={portfolio_json.get('projects_count')} "
        f"next={portfolio_json.get('next_project_focus')}"
    )
    print(f"CRITICAL_SYSTEM_STATUS ok=true overall={overall}")


def _smoke_doc_graph(*, repo_root: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    out_path = ws_integration / ".cache" / "reports" / "doc_graph_report.v1.json"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "doc-graph",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "report",
            "--out",
            str(out_path.relative_to(ws_integration)),
        ],
        env=env,
        fail_msg="Smoke test failed: doc-graph command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: doc-graph must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: doc-graph output must be JSON object.")
    if not out_path.exists():
        raise SystemExit("Smoke test failed: doc_graph_report.v1.json missing.")
    try:
        report = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: doc graph report must be valid JSON.") from e
    schema_path = repo_root / "schemas" / "doc-graph-report.schema.json"
    if not schema_path.exists():
        raise SystemExit("Smoke test failed: missing doc-graph report schema.")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
    except Exception as e:
        raise SystemExit("Smoke test failed: doc graph report must validate against schema.") from e
    status = report.get("status") if isinstance(report, dict) else None
    broken = report.get("counts", {}).get("broken_refs", 0) if isinstance(report, dict) else 0
    if status not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: doc graph status must be OK, WARN, or FAIL.")
    print(f"CRITICAL_DOC_GRAPH ok=true broken={broken} status={status}")


def _smoke_doc_nav_check(*, repo_root: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    smoke_level = os.environ.get("SMOKE_LEVEL", "full").lower()
    env["SMOKE_LEVEL"] = smoke_level
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "doc-nav-check",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
        ],
        env=env,
        fail_msg="Smoke test failed: doc-nav-check command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: doc-nav-check must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: doc-nav-check output must be JSON object.")
    if not isinstance(payload.get("doc_graph"), dict) or not isinstance(payload.get("cockpit"), dict):
        raise SystemExit("Smoke test failed: doc-nav-check payload missing doc_graph/cockpit.")
    doc_graph_summary = payload.get("doc_graph") if isinstance(payload, dict) else {}
    if not isinstance(doc_graph_summary.get("placeholder_refs_count"), int):
        raise SystemExit("Smoke test failed: doc-nav-check missing placeholder_refs_count.")
    evidence = payload.get("evidence_paths") if isinstance(payload.get("evidence_paths"), list) else []
    for p in evidence:
        if not isinstance(p, str):
            continue
        path = Path(p)
        if not path.is_absolute():
            path = ws_integration / path
        if not path.exists():
            raise SystemExit("Smoke test failed: doc-nav-check evidence path missing: " + str(path))

    if smoke_level != "fast":
        proc_detail = run_cmd(
            repo_root=repo_root,
            argv=[
                sys.executable,
                "-m",
                "src.ops.manage",
                "doc-nav-check",
                "--workspace-root",
                str(ws_integration.relative_to(repo_root)),
                "--detail",
                "true",
            ],
            env=env,
            fail_msg="Smoke test failed: doc-nav-check --detail command failed.",
            capture=True,
        )
        try:
            payload_detail = json.loads(proc_detail.stdout.strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: doc-nav-check --detail must print JSON.") from e
        doc_graph_detail = payload_detail.get("doc_graph") if isinstance(payload_detail, dict) else None
        if not isinstance(doc_graph_detail, dict):
            raise SystemExit("Smoke test failed: doc-nav-check --detail missing doc_graph.")
        if not isinstance(doc_graph_detail.get("top_broken"), list) or not isinstance(doc_graph_detail.get("top_orphans"), list):
            raise SystemExit("Smoke test failed: doc-nav-check --detail must include top lists.")

        proc_strict = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "doc-nav-check",
                "--workspace-root",
                str(ws_integration.relative_to(repo_root)),
                "--strict",
                "true",
                "--detail",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=env,
        )
        if proc_strict.returncode not in (0, 2):
            raise SystemExit("Smoke test failed: doc-nav-check --strict command failed.")
        try:
            payload_strict = json.loads(proc_strict.stdout.strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: doc-nav-check --strict must print JSON.") from e
        notes = payload_strict.get("notes") if isinstance(payload_strict, dict) else None
        if not isinstance(notes, list) or "strict=true" not in [str(x) for x in notes]:
            raise SystemExit("Smoke test failed: doc-nav-check --strict must set strict flag in notes.")
        strict_path = ws_integration / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
        if not strict_path.exists():
            raise SystemExit("Smoke test failed: strict doc graph report missing: " + str(strict_path))
        system_status_path = ws_integration / ".cache" / "reports" / "system_status.v1.json"
        if not system_status_path.exists():
            raise SystemExit("Smoke test failed: system_status report missing: " + str(system_status_path))
        try:
            sys_obj = json.loads(system_status_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("Smoke test failed: system_status report must be valid JSON.") from e
        overall = sys_obj.get("overall_status") if isinstance(sys_obj, dict) else None
        if str(overall) == "NOT_READY":
            raise SystemExit("Smoke test failed: strict doc-nav-check must not flip cockpit to NOT_READY.")
        print("CRITICAL_DOC_NAV_PUBLISH_ISOLATION ok=true")

    status = payload.get("status")
    doc_graph = payload.get("doc_graph") if isinstance(payload, dict) else {}
    broken = doc_graph.get("broken_refs", 0)
    ambiguity = doc_graph.get("ambiguity", 0)
    nav_gaps = doc_graph.get("critical_nav_gaps", 0)
    placeholders = doc_graph.get("placeholder_refs_count", 0)
    orphan = doc_graph.get("orphan_critical", 0)
    if status == "FAIL":
        raise SystemExit("Smoke test failed: doc-nav-check summary must not be FAIL.")
    if not isinstance(orphan, int) or orphan != 0:
        raise SystemExit("Smoke test failed: doc-nav-check orphan_critical must be 0.")
    print(f"CRITICAL_DOC_NAV_CHECK ok=true status={status} broken={broken} nav_gaps={nav_gaps} ambiguity={ambiguity}")
    print(
        "CRITICAL_DOC_NAV_SINGLE_GATE ok=true status="
        f"{status} broken={broken} nav_gaps={nav_gaps} ambiguity={ambiguity} mode=summary"
    )
    print(f"CRITICAL_DOC_NAV_LOCK ok=true broken={broken} placeholders={placeholders} orphan={orphan} status={status}")


def _smoke_repo_hygiene(repo_root: Path) -> None:
    out_path = repo_root / ".cache" / "repo_hygiene" / "smoke_report.json"
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "repo-hygiene",
            "--mode",
            "report",
            "--out",
            str(out_path.relative_to(repo_root)),
        ],
        env=env,
        fail_msg="Smoke test failed: repo-hygiene command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: repo-hygiene must print JSON.") from e
    if not isinstance(out, dict):
        raise SystemExit("Smoke test failed: repo-hygiene output must be JSON object.")
    if not out_path.exists():
        raise SystemExit("Smoke test failed: repo-hygiene report file missing.")
    report = json.loads(out_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise SystemExit("Smoke test failed: repo-hygiene report must be JSON object.")
    status = report.get("status") if isinstance(report, dict) else None
    if status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: repo-hygiene status must be OK or WARN.")
    summary = report.get("summary") if isinstance(report, dict) else None
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(summary, dict) or not isinstance(findings, list):
        raise SystemExit("Smoke test failed: repo-hygiene must include summary and findings.")
    print(f"CRITICAL_REPO_HYGIENE ok=true status={status}")


def _smoke_debt_pipeline(*, repo_root: Path, ws_integration: Path) -> None:
    actions_path = ws_integration / ".cache" / "roadmap_actions.v1.json"
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    if actions_path.exists():
        try:
            actions_obj = json.loads(actions_path.read_text(encoding="utf-8"))
        except Exception:
            actions_obj = {}
    else:
        actions_obj = {}
    actions = actions_obj.get("actions") if isinstance(actions_obj, dict) else None
    if not isinstance(actions, list):
        actions = []
        if isinstance(actions_obj, dict):
            actions_obj["actions"] = actions
    if not any(isinstance(a, dict) and a.get("action_id") == "TEST_DEBT_SCRIPT_BUDGET" for a in actions):
        actions.append(
            {
                "action_id": "TEST_DEBT_SCRIPT_BUDGET",
                "severity": "WARN",
                "kind": "MAINTAINABILITY_DEBT",
                "milestone_hint": "M0",
                "source": "SCRIPT_BUDGET",
                "title": "Script budget soft limit exceeded (test)",
                "details": {},
                "message": "Script budget soft limit exceeded (test)",
                "resolved": False,
            }
        )
        actions_obj["actions"] = actions
        actions_path.write_text(json.dumps(actions_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.debt_drafter",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--outdir",
            str((ws_integration / ".cache" / "debt_chg").relative_to(repo_root)),
            "--max-items",
            "5",
        ],
        env=env,
        fail_msg="Smoke test failed: debt_drafter command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: debt_drafter must print JSON.") from e
    if not isinstance(out, dict) or out.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: debt_drafter status must be OK or WARN.")
    drafted = int(out.get("drafted") or 0)
    chg_files = out.get("chg_files") if isinstance(out.get("chg_files"), list) else []
    if drafted < 1 or not chg_files:
        raise SystemExit("Smoke test failed: debt_drafter must draft at least one CHG.")
    chg_path = Path(str(chg_files[0])).resolve()
    proc_apply = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.debt_apply_incubator",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chg",
            str(chg_path),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: debt_apply_incubator failed.",
        capture=True,
    )
    try:
        applied = json.loads(proc_apply.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: debt_apply_incubator must print JSON.") from e
    if not isinstance(applied, dict) or applied.get("status") != "OK":
        raise SystemExit("Smoke test failed: debt_apply_incubator must return OK.")
    incubator_paths = applied.get("incubator_paths") if isinstance(applied.get("incubator_paths"), list) else []
    if not incubator_paths:
        raise SystemExit("Smoke test failed: debt_apply_incubator must report incubator_paths.")
    for p in incubator_paths[:3]:
        if not (Path(str(p)).exists()):
            raise SystemExit("Smoke test failed: incubator path missing: " + str(p))
    print(f"CRITICAL_DEBT_PIPELINE ok=true drafted={drafted} applied=true")


def _smoke_promotion_bundle(*, repo_root: Path, ws_integration: Path) -> None:
    incubator_root = ws_integration / "incubator"
    allowed_dirs = [incubator_root / "notes", incubator_root / "templates", incubator_root / "patches"]
    has_allowed = any(
        p.is_file()
        for d in allowed_dirs
        if d.exists()
        for p in d.rglob("*")
    )
    if not has_allowed:
        note_path = incubator_root / "notes" / "SMOKE_PROMOTION_NOTE.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("Promotion bundle smoke fixture.\n", encoding="utf-8")
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "promotion-bundle",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "customer_clean",
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: promotion-bundle command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: promotion-bundle must print JSON.") from e
    if not isinstance(out, dict) or out.get("status") != "OK":
        raise SystemExit("Smoke test failed: promotion-bundle must return OK.")
    out_zip = out.get("out_zip")
    out_report = out.get("out_report")
    out_patch_md = out.get("out_patch_md")
    if not (isinstance(out_zip, str) and isinstance(out_report, str) and isinstance(out_patch_md, str)):
        raise SystemExit("Smoke test failed: promotion-bundle outputs missing.")
    zip_path = Path(out_zip)
    report_path = Path(out_report)
    patch_md_path = Path(out_patch_md)
    if not (zip_path.exists() and report_path.exists() and patch_md_path.exists()):
        raise SystemExit("Smoke test failed: promotion-bundle outputs must exist.")
    report_obj = json.loads(report_path.read_text(encoding="utf-8"))
    included = report_obj.get("included_files") if isinstance(report_obj, dict) else None
    if not (isinstance(included, list) and included):
        raise SystemExit("Smoke test failed: promotion report must include at least one file.")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = sorted(zf.namelist())
    if "PROMOTION_REPORT.json" not in names:
        raise SystemExit("Smoke test failed: promotion bundle must include PROMOTION_REPORT.json.")
    extra_files = [n for n in names if n not in {"PROMOTION_REPORT.json", "PROMOTION_README.txt"}]
    if not extra_files:
        raise SystemExit("Smoke test failed: promotion bundle must include at least one payload file.")
    md_text = patch_md_path.read_text(encoding="utf-8")
    if "Draft only" not in md_text:
        raise SystemExit("Smoke test failed: core patch summary must mention Draft only.")
    zip_bytes = zip_path.stat().st_size
    print(f"CRITICAL_PROMOTION_BUNDLE ok=true included={len(included)} zip_bytes={zip_bytes}")
    print("CRITICAL_M8_2_COMPLETE ok=true")


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
