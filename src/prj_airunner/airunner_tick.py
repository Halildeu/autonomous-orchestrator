from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Any

from src.ops.commands.maintenance_cmds import (
    cmd_script_budget,
    cmd_system_status,
    cmd_work_intake_check,
    cmd_work_intake_exec_ticket,
)
from src.ops.roadmap_cli import cmd_portfolio_status
from src.prj_airunner.airunner_jobs import load_jobs_policy, update_jobs
from src.prj_airunner.airunner_perf import append_perf_event
from src.prj_airunner.airunner_time_sinks import build_time_sinks_report


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "enabled": False,
        "schedule": {"mode": "OFF", "interval_seconds": 0, "jitter_seconds": 0},
        "lock_ttl_seconds": 900,
        "heartbeat_interval_seconds": 300,
        "limits": {"max_ticks_per_run": 1, "max_actions_per_tick": 1, "max_plans_per_tick": 1},
        "single_gate": {"allowed_ops": [], "require_strict_isolation": True},
        "notes": [],
    }


def _load_policy(workspace_root: Path) -> tuple[dict[str, Any], str, str, list[str]]:
    core_root = _repo_root()
    notes: list[str] = []
    core_policy_path = core_root / "policies" / "policy_airunner.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    policy = _policy_defaults()
    policy_source = "core"

    if core_policy_path.exists():
        try:
            obj = _load_json(core_policy_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            notes.append("core_policy_invalid")
    else:
        notes.append("core_policy_missing")

    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
                policy_source = "core+workspace_override"
        except Exception:
            notes.append("override_policy_invalid")

    policy_hash = _hash_text(_canonical_json(policy))
    return policy, policy_source, policy_hash, notes


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _lock_paths(workspace_root: Path) -> tuple[Path, Path]:
    base = workspace_root / ".cache" / "airunner"
    return base / "airunner_lock.v1.json", base / "airunner_heartbeat.v1.json"


def _load_lock(lock_path: Path) -> dict[str, Any] | None:
    if not lock_path.exists():
        return None
    try:
        obj = _load_json(lock_path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _lock_is_stale(lock: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(lock.get("expires_at") if isinstance(lock, dict) else None)
    if expires_at is None:
        return True
    return now >= expires_at


def _write_lock(lock_path: Path, *, lock_id: str, now: datetime, ttl_seconds: int, workspace_root: Path) -> None:
    expires_at = now + timedelta(seconds=int(ttl_seconds))
    payload = {
        "version": "v1",
        "lock_id": lock_id,
        "acquired_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": int(ttl_seconds),
        "workspace_root": str(workspace_root),
        "notes": ["PROGRAM_LED=true"],
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(_dump_json(payload), encoding="utf-8")


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except Exception:
        return


def _load_heartbeat(heartbeat_path: Path) -> dict[str, Any] | None:
    if not heartbeat_path.exists():
        return None
    try:
        obj = _load_json(heartbeat_path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_heartbeat(
    heartbeat_path: Path,
    *,
    workspace_root: Path,
    tick_id: str,
    status: str,
    error_code: str | None,
    window_bucket: str,
    policy_hash: str,
    notes: list[str],
) -> str:
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "last_tick_id": tick_id,
        "last_tick_at": _now_iso(),
        "last_status": status,
        "last_error_code": error_code,
        "last_tick_window": window_bucket,
        "policy_hash": policy_hash,
        "notes": notes,
    }
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_path.write_text(_dump_json(payload), encoding="utf-8")
    return _rel_to_workspace(heartbeat_path, workspace_root) or str(heartbeat_path)


def _run_cmd_json(func, args: argparse.Namespace) -> dict[str, Any]:
    buf = StringIO()
    try:
        from contextlib import redirect_stdout, redirect_stderr

        with redirect_stdout(buf), redirect_stderr(buf):
            rc = func(args)
    except Exception:
        return {"status": "FAIL", "error_code": "COMMAND_EXCEPTION"}

    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    if not lines:
        return {"status": "WARN", "error_code": "COMMAND_NO_OUTPUT", "return_code": rc}
    try:
        payload = json.loads(lines[-1])
    except Exception:
        return {"status": "WARN", "error_code": "COMMAND_OUTPUT_INVALID", "return_code": rc}
    if isinstance(payload, dict):
        payload["return_code"] = rc
    return payload if isinstance(payload, dict) else {"status": "WARN", "return_code": rc}


def _perf_status(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "WARN")
    if payload.get("return_code") not in {None, 0}:
        return "FAIL"
    if status in {"OK"}:
        return "OK"
    if status in {"WARN", "IDLE"}:
        return "WARN"
    return "FAIL"


def _run_cmd_json_with_perf(
    *,
    op_name: str,
    func,
    args: argparse.Namespace,
    workspace_root: Path,
    perf_cfg: dict[str, Any],
) -> dict[str, Any]:
    started_at = _now_iso()
    start = time.monotonic()
    payload = _run_cmd_json(func, args)
    duration_ms = int((time.monotonic() - start) * 1000)
    ended_at = _now_iso()
    if perf_cfg.get("enable", True):
        max_lines = int(perf_cfg.get("event_log_max_lines", 0) or 0)
        append_perf_event(
            workspace_root,
            event={
                "event_type": "OP_CALL",
                "op_name": op_name,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "status": _perf_status(payload),
                "notes": ["PROGRAM_LED=true"],
            },
            max_lines=max_lines,
        )
    return payload


def _run_fast_gate(workspace_root: Path) -> dict[str, Any]:
    repo_root = _repo_root()
    results = {
        "validate_schemas": "FAIL",
        "smoke_fast": "FAIL",
        "script_budget": "FAIL",
        "hard_exceeded": 0,
        "report_path": "",
    }

    proc = subprocess.run([sys.executable, "ci/validate_schemas.py"], cwd=repo_root)
    results["validate_schemas"] = "PASS" if proc.returncode == 0 else "FAIL"

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = subprocess.run([sys.executable, "smoke_test.py"], cwd=repo_root, env=env)
    results["smoke_fast"] = "PASS" if proc.returncode == 0 else "FAIL"

    sb_path = workspace_root / ".cache" / "script_budget" / "report.json"
    sb_path.parent.mkdir(parents=True, exist_ok=True)
    sb_rc = cmd_script_budget(argparse.Namespace(out=str(sb_path)))
    hard_exceeded = 0
    if sb_path.exists():
        try:
            report = json.loads(sb_path.read_text(encoding="utf-8"))
            if isinstance(report, dict):
                exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []
                function_hard = report.get("function_hard") if isinstance(report.get("function_hard"), list) else []
                hard_exceeded = len(exceeded_hard) + len(function_hard)
        except Exception:
            hard_exceeded = max(hard_exceeded, 1)
    results["hard_exceeded"] = hard_exceeded
    results["script_budget"] = "PASS" if sb_rc == 0 and hard_exceeded == 0 else "FAIL"
    rel = _rel_to_workspace(sb_path, workspace_root)
    if rel:
        results["report_path"] = rel
    return results


def _write_tick_report(report: dict[str, Any], workspace_root: Path) -> tuple[str, str]:
    out_json = workspace_root / ".cache" / "reports" / "airunner_tick.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "airunner_tick.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")

    md_lines = [
        "AIRUNNER TICK",
        "",
        f"Status: {report.get('status')}",
        f"Policy source: {report.get('policy_source')}",
        f"Policy hash: {report.get('policy_hash')}",
        f"Applied: {report.get('actions', {}).get('applied', 0)}",
        f"Planned: {report.get('actions', {}).get('planned', 0)}",
        f"Idle: {report.get('actions', {}).get('idle', 0)}",
        "",
        "Evidence:",
    ]
    for p in report.get("evidence_paths", []):
        md_lines.append(f"- {p}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    rel_json = _rel_to_workspace(out_json, workspace_root) or str(out_json)
    rel_md = _rel_to_workspace(out_md, workspace_root) or str(out_md)
    return rel_json, rel_md


def _work_intake_hash(workspace_root: Path) -> str:
    path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not path.exists():
        return "missing"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return "invalid"
    return _hash_text(text)


def _window_bucket(schedule: dict[str, Any]) -> str:
    mode = str(schedule.get("mode") or "OFF")
    if mode != "interval":
        return "manual"
    interval = int(schedule.get("interval_seconds") or 0)
    if interval <= 0:
        return "manual"
    now = int(datetime.now(timezone.utc).timestamp())
    return f"interval:{interval}:{now // interval}"


def _compute_tick_id(policy_hash: str, work_intake_hash: str, window_bucket: str) -> str:
    return _hash_text(_canonical_json({"policy_hash": policy_hash, "work_intake_hash": work_intake_hash, "window": window_bucket}))


def run_airunner_tick(*, workspace_root: Path) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    enabled = bool(policy.get("enabled", False))
    schedule = policy.get("schedule") if isinstance(policy.get("schedule"), dict) else {}
    schedule_mode = str(schedule.get("mode") or "OFF")
    core_root = _repo_root()

    required_ops = ["work-intake-check", "work-intake-exec-ticket", "system-status", "portfolio-status"]
    allowed_ops = policy.get("single_gate", {}).get("allowed_ops") if isinstance(policy.get("single_gate"), dict) else []
    allowed_ops = [str(x) for x in allowed_ops if isinstance(x, str)]

    if not enabled:
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": "IDLE",
            "error_code": "POLICY_DISABLED",
            "tick_id": _hash_text(_canonical_json({"enabled": False, "policy_hash": policy_hash})),
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": "IDLE",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }

    if schedule_mode == "OFF":
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": "IDLE",
            "error_code": "SCHEDULE_OFF",
            "tick_id": _hash_text(_canonical_json({"schedule": schedule_mode, "policy_hash": policy_hash})),
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": "IDLE",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }

    missing_ops = [op for op in required_ops if op not in allowed_ops]
    if missing_ops:
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": "IDLE",
            "error_code": "ALLOWED_OPS_MISSING",
            "tick_id": _hash_text(_canonical_json({"missing_ops": missing_ops, "policy_hash": policy_hash})),
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"] + [f"missing_op={op}" for op in missing_ops],
        }
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": "IDLE",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }

    jobs_policy, jobs_policy_hash, jobs_notes = load_jobs_policy(core_root=core_root, workspace_root=workspace_root)
    perf_cfg = jobs_policy.get("perf") if isinstance(jobs_policy.get("perf"), dict) else {}
    notes.extend(jobs_notes)

    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    max_actions = int(limits.get("max_actions_per_tick", 1)) if isinstance(limits.get("max_actions_per_tick"), int) else 1
    max_plans = int(limits.get("max_plans_per_tick", 1)) if isinstance(limits.get("max_plans_per_tick"), int) else 1
    lock_ttl = int(policy.get("lock_ttl_seconds", 900) or 900)

    now = datetime.now(timezone.utc)
    lock_path, heartbeat_path = _lock_paths(workspace_root)
    lock = _load_lock(lock_path)
    if lock and not _lock_is_stale(lock, now):
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": "IDLE",
            "error_code": "LOCKED",
            "tick_id": _hash_text(_canonical_json({"locked": True, "policy_hash": policy_hash})),
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [str(Path(".cache") / "airunner" / "airunner_lock.v1.json")],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": "IDLE",
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }

    lock_id = _hash_text(f"{workspace_root}:{now.isoformat()}:{policy_hash}")
    _write_lock(lock_path, lock_id=lock_id, now=now, ttl_seconds=lock_ttl, workspace_root=workspace_root)

    ops_called: list[str] = []
    evidence_paths: list[str] = []
    error_code = None
    status = "OK"

    work_intake_hash = _work_intake_hash(workspace_root)
    window_bucket = _window_bucket(schedule)
    tick_id = _compute_tick_id(policy_hash, work_intake_hash, window_bucket)
    heartbeat = _load_heartbeat(heartbeat_path)
    last_tick_id = heartbeat.get("last_tick_id") if isinstance(heartbeat, dict) else None
    if isinstance(last_tick_id, str) and last_tick_id == tick_id:
        status = "IDLE"
        error_code = "NOOP_SAME_TICK"
        heartbeat_rel = _write_heartbeat(
            heartbeat_path,
            workspace_root=workspace_root,
            tick_id=tick_id,
            status=status,
            error_code=error_code,
            window_bucket=window_bucket,
            policy_hash=policy_hash,
            notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
        )
        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": status,
            "error_code": error_code,
            "tick_id": tick_id,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "ops_called": [],
            "actions": {"applied": 0, "planned": 0, "idle": 0},
            "evidence_paths": [heartbeat_rel],
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }
        rel_json, rel_md = _write_tick_report(report, workspace_root)
        _release_lock(lock_path)
        return {
            "status": status,
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "report_path": rel_json,
            "report_md_path": rel_md,
        }

    try:
        fast_gate = _run_fast_gate(workspace_root)
        fast_gate_ok = (
            fast_gate.get("validate_schemas") == "PASS"
            and fast_gate.get("smoke_fast") == "PASS"
            and fast_gate.get("script_budget") == "PASS"
        )
        if not fast_gate_ok:
            status = "FAIL"
            error_code = "FAST_GATE_FAIL"
            if fast_gate.get("report_path"):
                evidence_paths.append(str(fast_gate.get("report_path")))
            heartbeat_rel = _write_heartbeat(
                heartbeat_path,
                workspace_root=workspace_root,
                tick_id=tick_id,
                status=status,
                error_code=error_code,
                window_bucket=window_bucket,
                policy_hash=policy_hash,
                notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
            )
            evidence_paths.append(heartbeat_rel)
            report = {
                "version": "v1",
                "generated_at": _now_iso(),
                "status": status,
                "error_code": error_code,
                "tick_id": tick_id,
                "workspace_root": str(workspace_root),
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "fast_gate": fast_gate,
                "jobs_started": 0,
                "jobs_polled": 0,
                "jobs_running": 0,
                "jobs_failed": 0,
                "jobs_passed": 0,
                "last_smoke_full_job_id": "",
                "ops_called": [],
                "actions": {"applied": 0, "planned": 0, "idle": 0},
                "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
                "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
            }
            rel_json, rel_md = _write_tick_report(report, workspace_root)
            _release_lock(lock_path)
            return {
                "status": status,
                "policy_source": policy_source,
                "policy_hash": policy_hash,
                "report_path": rel_json,
                "report_md_path": rel_md,
            }

        if fast_gate.get("report_path"):
            evidence_paths.append(str(fast_gate.get("report_path")))
        jobs_index, _, job_stats = update_jobs(
            workspace_root=workspace_root,
            tick_id=tick_id,
            policy_hash=jobs_policy_hash,
            policy=jobs_policy,
        )
        jobs_index_path = str(Path(".cache") / "airunner" / "jobs_index.v1.json")
        evidence_paths.append(jobs_index_path)

        work_intake_payload = _run_cmd_json_with_perf(
            op_name="work-intake-check",
            func=cmd_work_intake_check,
            args=argparse.Namespace(workspace_root=str(workspace_root), mode="strict", chat="false", detail="false"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("work-intake-check")
        work_intake_path = work_intake_payload.get("work_intake_path") if isinstance(work_intake_payload, dict) else None
        if isinstance(work_intake_path, str) and work_intake_path:
            evidence_paths.append(work_intake_path)

        limit = max(1, min(3, max_actions))
        exec_payload = _run_cmd_json_with_perf(
            op_name="work-intake-exec-ticket",
            func=cmd_work_intake_exec_ticket,
            args=argparse.Namespace(workspace_root=str(workspace_root), limit=limit, chat="false"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("work-intake-exec-ticket")
        exec_path = exec_payload.get("work_intake_exec_path") if isinstance(exec_payload, dict) else None
        if isinstance(exec_path, str) and exec_path:
            evidence_paths.append(exec_path)

        sys_payload = _run_cmd_json_with_perf(
            op_name="system-status",
            func=cmd_system_status,
            args=argparse.Namespace(workspace_root=str(workspace_root), dry_run="false"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("system-status")
        sys_out = sys_payload.get("out_json") if isinstance(sys_payload, dict) else None
        if isinstance(sys_out, str):
            rel = _rel_to_workspace(Path(sys_out), workspace_root)
            if rel:
                evidence_paths.append(rel)

        portfolio_payload = _run_cmd_json_with_perf(
            op_name="portfolio-status",
            func=cmd_portfolio_status,
            args=argparse.Namespace(workspace_root=str(workspace_root), mode="json"),
            workspace_root=workspace_root,
            perf_cfg=perf_cfg,
        )
        ops_called.append("portfolio-status")
        portfolio_path = portfolio_payload.get("report_path") if isinstance(portfolio_payload, dict) else None
        if isinstance(portfolio_path, str) and portfolio_path:
            evidence_paths.append(portfolio_path)

        applied = int(exec_payload.get("applied_count") or 0) if isinstance(exec_payload, dict) else 0
        planned = int(exec_payload.get("planned_count") or 0) if isinstance(exec_payload, dict) else 0
        idle = int(exec_payload.get("idle_count") or 0) if isinstance(exec_payload, dict) else 0

        for payload in [work_intake_payload, exec_payload, sys_payload, portfolio_payload]:
            if not isinstance(payload, dict):
                status = "FAIL"
                error_code = "OP_OUTPUT_INVALID"
                break
            op_status = payload.get("status")
            if isinstance(op_status, str) and op_status not in {"OK", "WARN", "IDLE"}:
                status = "FAIL"
                error_code = "OP_FAILED"
                break
            if payload.get("return_code") not in {None, 0}:
                status = "FAIL"
                error_code = "OP_FAILED"
                break

        if planned > max_plans and status == "OK":
            status = "WARN"
            error_code = "PLANS_LIMIT_EXCEEDED"

        build_time_sinks_report(workspace_root, policy=jobs_policy)
        time_sinks_path = str(Path(".cache") / "reports" / "time_sinks.v1.json")
        evidence_paths.append(time_sinks_path)

        heartbeat_rel = _write_heartbeat(
            heartbeat_path,
            workspace_root=workspace_root,
            tick_id=tick_id,
            status=status,
            error_code=error_code,
            window_bucket=window_bucket,
            policy_hash=policy_hash,
            notes=notes + ["PROGRAM_LED=true", "NETWORK=false"],
        )
        evidence_paths.append(heartbeat_rel)

        report = {
            "version": "v1",
            "generated_at": _now_iso(),
            "status": status,
            "error_code": error_code,
            "tick_id": tick_id,
            "workspace_root": str(workspace_root),
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "fast_gate": fast_gate,
            "jobs_started": int(job_stats.get("started", 0)),
            "jobs_polled": int(job_stats.get("polled", 0)),
            "jobs_running": int(job_stats.get("running", 0)),
            "jobs_failed": int(job_stats.get("failed", 0)),
            "jobs_passed": int(job_stats.get("passed", 0)),
            "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
            "ops_called": ops_called,
            "actions": {"applied": applied, "planned": planned, "idle": idle},
            "evidence_paths": sorted({str(p) for p in evidence_paths if isinstance(p, str) and p}),
            "notes": notes + ["PROGRAM_LED=true", "STRICT_ISOLATED=true", "NETWORK=false"],
        }

        rel_json, rel_md = _write_tick_report(report, workspace_root)
        return {
            "status": status,
            "policy_source": policy_source,
            "policy_hash": policy_hash,
            "work_intake_path": work_intake_path,
            "work_intake_exec_path": exec_path,
            "system_status_path": sys_out,
            "portfolio_status_path": portfolio_path,
            "report_path": rel_json,
            "report_md_path": rel_md,
            "applied": applied,
            "planned": planned,
            "idle": idle,
            "jobs_started": int(job_stats.get("started", 0)),
            "jobs_polled": int(job_stats.get("polled", 0)),
            "jobs_running": int(job_stats.get("running", 0)),
            "jobs_failed": int(job_stats.get("failed", 0)),
            "jobs_passed": int(job_stats.get("passed", 0)),
            "last_smoke_full_job_id": str(job_stats.get("last_smoke_full_job_id") or ""),
        }
    finally:
        _release_lock(lock_path)


def run_airunner_status(*, workspace_root: Path) -> dict[str, Any]:
    report_path = workspace_root / ".cache" / "reports" / "airunner_tick.v1.json"
    lock_path, heartbeat_path = _lock_paths(workspace_root)
    if not report_path.exists():
        return {
            "status": "IDLE",
            "error_code": "NO_TICK_REPORT",
            "report_path": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
            "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
            "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        }
    try:
        report = _load_json(report_path)
    except Exception:
        return {
            "status": "WARN",
            "error_code": "TICK_REPORT_INVALID",
            "report_path": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
            "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
            "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        }
    status = report.get("status") if isinstance(report, dict) else "WARN"
    return {
        "status": status,
        "report_path": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
        "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json") if heartbeat_path.exists() else "",
        "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json") if lock_path.exists() else "",
        "tick_id": report.get("tick_id") if isinstance(report, dict) else None,
        "policy_source": report.get("policy_source") if isinstance(report, dict) else None,
        "policy_hash": report.get("policy_hash") if isinstance(report, dict) else None,
    }
