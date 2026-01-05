from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ci.smoke_helpers.utils import (
    assert_debt_autopilot_applied,
    assert_system_status_auto_heal,
    prepare_debt_autopilot_fixture,
    run_cmd,
    write_completeness_state,
)


def _smoke_roadmap_drift(repo_root: Path) -> None:
    # Avoid recursion: roadmap-follow/finish runs smoke_test.py as a gate, so when we are invoked by
    # the orchestrator (ORCH_ROADMAP_ORCHESTRATOR=1), we must not call roadmap-finish again.
    if os.environ.get("ORCH_ROADMAP_ORCHESTRATOR") == "1":
        return
    ws = repo_root / ".cache" / "ws_drift_demo"
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    env.setdefault("SMOKE_MODE", "1")
    env["SMOKE_LEVEL"] = "fast"
    env["SMOKE_DRIFT_MINIMAL"] = "1"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg="Smoke test failed: drift workspace-bootstrap failed.",
    )
    roadmap_path = (repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json").resolve()
    current_sha = hashlib.sha256(roadmap_path.read_bytes()).hexdigest()
    old_sha = ("0" if current_sha[0] != "0" else "1") + current_sha[1:]
    # Ensure ISO core docs exist so orchestrator can run non-M1 milestones deterministically.
    iso_dir = ws / "tenant" / "TENANT-DEFAULT"
    iso_dir.mkdir(parents=True, exist_ok=True)
    for name in ["context.v1.md", "stakeholders.v1.md", "scope.v1.md", "criteria.v1.md"]:
        (iso_dir / name).write_text(f"# {name}\n\nTODO\n", encoding="utf-8")
    milestones_obj = json.loads(roadmap_path.read_text(encoding="utf-8"))
    milestone_ids = []
    for ms in milestones_obj.get("milestones", []) if isinstance(milestones_obj.get("milestones"), list) else []:
        if isinstance(ms, dict) and isinstance(ms.get("id"), str):
            milestone_ids.append(ms["id"])
    state_path = (ws / ".cache" / "roadmap_state.v1.json").resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_obj = {
        "version": "v1",
        "roadmap_path": str(roadmap_path),
        "workspace_root": str(ws.resolve()),
        "roadmap_sha256": old_sha,
        "last_roadmap_sha256": None,
        "drift_detected": False,
        "completed_milestones_meta": {
            "M3": {"roadmap_sha256_at_completion": old_sha, "completed_at": "2000-01-01T00:00:00Z"}
        },
        "bootstrapped": True,
        "completed_milestones": milestone_ids,
        "current_milestone": None,
        "attempts": {},
        "last_result": {"status": "OK", "milestone": None, "evidence_path": None, "error_code": None},
        "quarantine": {"milestone": None, "until": None, "reason": None},
        "backoff": {"seconds": 0, "next_try_at": None},
    }
    state_path.write_text(json.dumps(state_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    actions_path = (ws / ".cache" / "roadmap_actions.v1.json").resolve()
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    placeholder_msg = "Milestone M6 appears to be placeholder-only (synthetic drift smoke)."
    action_id = hashlib.sha256(("PLACEHOLDER_MILESTONE:" + placeholder_msg).encode("utf-8")).hexdigest()[:16]
    actions_obj = {
        "version": "v1",
        "roadmap_path": str(roadmap_path),
        "workspace_root": str(ws.resolve()),
        "actions": [
            {
                "action_id": action_id,
                "severity": "WARN",
                "kind": "PLACEHOLDER_MILESTONE",
                "milestone_hint": "M6",
                "message": placeholder_msg,
                "resolved": False,
            }
        ],
    }
    actions_path.write_text(json.dumps(actions_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    proc_finish = subprocess.run(
        [
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
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=env,
    )
    try:
        payload = json.loads(proc_finish.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: roadmap-finish must print JSON.") from e
    if payload.get("drift_detected") is not True:
        raise SystemExit("Smoke test failed: drift_detected must be true.")
    stale_reset = payload.get("stale_reset_milestones")
    if not (isinstance(stale_reset, list) and "M3" in stale_reset):
        raise SystemExit("Smoke test failed: stale_reset_milestones must include M3.")
    status = payload.get("status")
    if status not in {"DONE_WITH_DEBT", "DONE", "BLOCKED"}:
        raise SystemExit("Smoke test failed: expected DONE/DONE_WITH_DEBT or BLOCKED for drift run.")
    evidence_paths = payload.get("evidence") if isinstance(payload, dict) else None
    if isinstance(evidence_paths, list) and evidence_paths:
        run_dir = (repo_root / str(evidence_paths[-1])).resolve()
        out_path = run_dir / "output.json"
        if not out_path.exists():
            raise SystemExit("Smoke test failed: roadmap-finish evidence must include output.json.")
        out_obj = json.loads(out_path.read_text(encoding="utf-8"))
        if out_obj.get("smoke_drift_minimal") is not True:
            raise SystemExit("Smoke test failed: smoke_drift_minimal flag must be true in output.json.")
        skipped = out_obj.get("skipped_ingest")
        if not (isinstance(skipped, list) and "harvest" in skipped):
            raise SystemExit("Smoke test failed: skipped_ingest must include harvest in drift minimal mode.")
    catalog_path = ws / ".cache" / "index" / "catalog.v1.json"
    if not catalog_path.exists():
        raise SystemExit("Smoke test failed: drift rerun should build catalog: " + str(catalog_path))
    catalog_obj = json.loads(catalog_path.read_text(encoding="utf-8"))
    packs = catalog_obj.get("packs") if isinstance(catalog_obj, dict) else None
    if not (isinstance(packs, list) and any(isinstance(p, dict) and p.get("pack_id") == "pack-demo" for p in packs)):
        raise SystemExit("Smoke test failed: drift rerun catalog must include pack-demo.")
    print(f"CRITICAL_ROADMAP_DRIFT ok=true status={payload.get('status')} m3_reran=true")


def _smoke_actions_self_heal(repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_actions_self_heal"
    if ws.exists():
        shutil.rmtree(ws)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws.relative_to(repo_root))],
        env=env,
        fail_msg="Smoke test failed: self-heal workspace-bootstrap failed.",
    )
    roadmap_path = (repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json").resolve()
    current_sha = hashlib.sha256(roadmap_path.read_bytes()).hexdigest()
    roadmap_obj = json.loads(roadmap_path.read_text(encoding="utf-8"))
    milestone_ids = []
    for ms in roadmap_obj.get("milestones", []) if isinstance(roadmap_obj.get("milestones"), list) else []:
        if isinstance(ms, dict) and isinstance(ms.get("id"), str):
            milestone_ids.append(ms["id"])
    # Mark all milestones as completed so roadmap-finish can run in a bounded, deterministic mode (no apply loop),
    # while still performing action-register self-healing.
    state_path = ws / ".cache" / "roadmap_state.v1.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "roadmap_path": str(roadmap_path),
                "workspace_root": str(ws.resolve()),
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
    actions_path = ws / ".cache" / "roadmap_actions.v1.json"
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    msg_m2_5 = "Milestone M2.5 appears to be placeholder-only (synthetic self-heal smoke)."
    msg_m3 = "Milestone M3 appears to be placeholder-only (synthetic self-heal smoke)."
    msg_m4_1 = "Milestone M4.1 appears to be placeholder-only (synthetic self-heal smoke)."
    msg_m3_5 = "Milestone M3.5 appears to be placeholder-only (synthetic self-heal smoke)."
    a_m2_5 = hashlib.sha256(("PLACEHOLDER_MILESTONE:" + msg_m2_5).encode("utf-8")).hexdigest()[:16]
    a_m3 = hashlib.sha256(("PLACEHOLDER_MILESTONE:" + msg_m3).encode("utf-8")).hexdigest()[:16]
    a_m4_1 = hashlib.sha256(("PLACEHOLDER_MILESTONE:" + msg_m4_1).encode("utf-8")).hexdigest()[:16]
    a_m3_5 = hashlib.sha256(("PLACEHOLDER_MILESTONE:" + msg_m3_5).encode("utf-8")).hexdigest()[:16]
    msg_unknown = "Unknown roadmap step types: assert_core_paths_exist"
    a_unknown = hashlib.sha256(("UNKNOWN_STEP_TYPES:" + msg_unknown).encode("utf-8")).hexdigest()[:16]
    actions_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "roadmap_path": str(roadmap_path),
                "workspace_root": str(ws.resolve()),
                "actions": [
                    {"action_id": a_m2_5, "severity": "WARN", "kind": "PLACEHOLDER_MILESTONE", "milestone_hint": "M2.5", "message": msg_m2_5, "resolved": False},
                    {"action_id": a_m3, "severity": "WARN", "kind": "PLACEHOLDER_MILESTONE", "milestone_hint": "M3", "message": msg_m3, "resolved": False},
                    {"action_id": a_m4_1, "severity": "WARN", "kind": "PLACEHOLDER_MILESTONE", "milestone_hint": "M4.1", "message": msg_m4_1, "resolved": False},
                    {"action_id": a_m3_5, "severity": "WARN", "kind": "PLACEHOLDER_MILESTONE", "milestone_hint": "M3.5", "message": msg_m3_5, "resolved": False},
                    {"action_id": a_unknown, "severity": "FAIL", "kind": "UNKNOWN_STEP_TYPES", "milestone_hint": "M4.1", "message": msg_unknown, "resolved": False},
                ],
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
            str(ws.relative_to(repo_root)),
            "--max-minutes",
            "1",
            "--sleep-seconds",
            "0",
            "--max-steps-per-iteration",
            "1",
        ],
        env=env,
        fail_msg="Smoke test failed: roadmap-finish self-heal run failed.",
        capture=True,
    )
    try:
        _ = json.loads(proc_finish.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: roadmap-finish self-heal must print JSON.") from e
    healed = json.loads(actions_path.read_text(encoding="utf-8"))
    actions = healed.get("actions") if isinstance(healed, dict) else None
    if not isinstance(actions, list):
        raise SystemExit("Smoke test failed: roadmap_actions.v1.json must contain actions list.")

    def is_resolved(mid: str) -> bool:
        for a in actions:
            if not isinstance(a, dict):
                continue
            if a.get("kind") != "PLACEHOLDER_MILESTONE":
                continue
            if a.get("milestone_hint") != mid:
                continue
            return a.get("resolved") is True
        return False

    if not is_resolved("M2.5"):
        raise SystemExit("Smoke test failed: M2.5 placeholder action must be resolved by self-heal.")
    if not is_resolved("M3"):
        raise SystemExit("Smoke test failed: M3 placeholder action must be resolved by self-heal.")
    if not is_resolved("M4.1"):
        raise SystemExit("Smoke test failed: M4.1 placeholder action must be resolved by self-heal.")
    if not is_resolved("M3.5"):
        raise SystemExit("Smoke test failed: M3.5 placeholder action must be resolved by self-heal.")
    unknown_resolved = False
    for a in actions:
        if not isinstance(a, dict):
            continue
        if a.get("kind") == "UNKNOWN_STEP_TYPES" and a.get("milestone_hint") == "M4.1":
            unknown_resolved = a.get("resolved") is True
            break
    if not unknown_resolved:
        raise SystemExit("Smoke test failed: UNKNOWN_STEP_TYPES action must be resolved by self-heal.")
    print("CRITICAL_ACTIONS_SELF_HEAL ok=true")
    print("CRITICAL_STALE_FAIL_CLEANUP ok=true")


def _smoke_artifact_completeness(repo_root: Path) -> None:
    ws = repo_root / ".cache" / "ws_completeness_demo"
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
        fail_msg="Smoke test failed: completeness workspace-bootstrap failed.",
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
            "--milestones",
            "M1,M2.5",
            "--workspace-root",
            str(ws.relative_to(repo_root)),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: completeness apply M1,M2.5 failed.",
    )
    formats_path = ws / ".cache" / "index" / "formats.v1.json"
    if formats_path.exists():
        formats_path.unlink()
    roadmap_path = (repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json").resolve()
    current_sha = hashlib.sha256(roadmap_path.read_bytes()).hexdigest()
    milestones_obj = json.loads(roadmap_path.read_text(encoding="utf-8"))
    milestone_ids = []
    for ms in milestones_obj.get("milestones", []) if isinstance(milestones_obj.get("milestones"), list) else []:
        if isinstance(ms, dict) and isinstance(ms.get("id"), str):
            milestone_ids.append(ms["id"])
    completed_ids = [mid for mid in milestone_ids if mid != "M8.1"]
    write_completeness_state(
        ws=ws,
        roadmap_path=roadmap_path,
        roadmap_sha=current_sha,
        milestone_ids=completed_ids,
    )
    prepare_debt_autopilot_fixture(ws)
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
            str(ws.relative_to(repo_root)),
            "--max-minutes",
            "1",
            "--sleep-seconds",
            "0",
            "--max-steps-per-iteration",
            "1",
        ],
        env=env,
        fail_msg="Smoke test failed: completeness roadmap-finish failed.",
        capture=True,
    )
    try:
        finish_out = json.loads(proc_finish.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: completeness roadmap-finish must print JSON.") from e
    evidence = finish_out.get("evidence") if isinstance(finish_out, dict) else None
    if not (isinstance(evidence, list) and evidence and isinstance(evidence[0], str)):
        raise SystemExit("Smoke test failed: completeness finish output must include evidence path list.")
    run_dir = (repo_root / evidence[0]).resolve()
    report_path = run_dir / "artifact_completeness_report.json"
    if not report_path.exists():
        raise SystemExit("Smoke test failed: completeness evidence missing artifact_completeness_report.json.")
    assert_debt_autopilot_applied(ws=ws, run_dir=run_dir)
    if not formats_path.exists():
        raise SystemExit("Smoke test failed: formats index was not auto-healed.")
    actions_path = ws / ".cache" / "roadmap_actions.v1.json"
    if actions_path.exists():
        actions_obj = json.loads(actions_path.read_text(encoding="utf-8"))
        actions = actions_obj.get("actions") if isinstance(actions_obj, dict) else None
        if isinstance(actions, list):
            for a in actions:
                if not isinstance(a, dict):
                    continue
                if a.get("kind") == "QUALITY_GATE_WARN" and "FORMATS_INDEX_MISSING" in str(a.get("message") or ""):
                    raise SystemExit("Smoke test failed: quality gate FORMATS_INDEX_MISSING should be auto-healed.")
    healed_count = assert_system_status_auto_heal(
        repo_root=repo_root,
        workspace_root=ws,
        env=env,
        evidence_path=evidence[0],
    )
    print(f"CRITICAL_SYSTEM_STATUS_AUTO_HEAL ok=true healed={healed_count}")
    print("CRITICAL_DEBT_AUTOPILOT ok=true applied=true")
    print("CRITICAL_ARTIFACT_COMPLETENESS ok=true healed_formats=true")
