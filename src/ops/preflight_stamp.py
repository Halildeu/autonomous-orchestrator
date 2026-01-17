from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _normalize_script_budget_report(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {"status": "FAIL", "hard_exceeded": 0, "soft_exceeded": 0}
    exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []
    exceeded_soft = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
    function_hard = report.get("function_hard") if isinstance(report.get("function_hard"), list) else []
    function_soft = report.get("function_soft") if isinstance(report.get("function_soft"), list) else []
    hard_exceeded = len(exceeded_hard) + len(function_hard)
    soft_exceeded = len(exceeded_soft) + len(function_soft)
    report["hard_exceeded"] = hard_exceeded
    report["soft_exceeded"] = soft_exceeded
    report.setdefault("soft_only", hard_exceeded == 0 and soft_exceeded > 0)
    return report


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "stamp_ttl_minutes": 30,
        "require_pass_for_apply": True,
        "notes": [],
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _smoke_fast_job_gate(*, workspace_root: Path) -> tuple[str, list[str]]:
    try:
        from src.prj_github_ops.github_ops import start_github_ops_job, poll_github_ops_job
    except Exception:
        return "FAIL", ["SMOKE_JOB_IMPORT_FAIL"]

    start_res = start_github_ops_job(workspace_root=workspace_root, kind="SMOKE_FAST", dry_run=False)
    job_id = str(start_res.get("job_id") or "")
    if not job_id:
        return "FAIL", ["SMOKE_JOB_START_FAILED"]

    poll_res = poll_github_ops_job(workspace_root=workspace_root, job_id=job_id)
    status = str(poll_res.get("status") or "")
    if status == "RUNNING":
        return "FAIL", ["SMOKE_JOB_RUNNING"]
    if status == "PASS":
        return "PASS", []
    reason = f"SMOKE_JOB_{status or 'UNKNOWN'}"
    return "FAIL", [reason]


def _load_policy(workspace_root: Path) -> tuple[dict[str, Any], str, list[str]]:
    core_root = _repo_root()
    notes: list[str] = []
    policy = _policy_defaults()
    policy_source = "core"

    core_path = core_root / "policies" / "policy_preflight_stamp.v1.json"
    if core_path.exists():
        try:
            obj = _load_json(core_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
        except Exception:
            notes.append("core_policy_invalid")
    else:
        notes.append("core_policy_missing")

    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_preflight_stamp.override.v1.json"
    if override_path.exists():
        try:
            obj = _load_json(override_path)
            if isinstance(obj, dict):
                policy = _deep_merge(policy, obj)
                policy_source = "core+workspace_override"
        except Exception:
            notes.append("override_policy_invalid")

    return policy, policy_source, notes


def _parse_stamp(stamp: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    gates = stamp.get("gates") if isinstance(stamp.get("gates"), dict) else {}
    overall = str(stamp.get("overall") or "FAIL")
    return overall, gates


def run_preflight_stamp(*, workspace_root: Path, mode: str = "write") -> dict[str, Any]:
    policy, policy_source, policy_notes = _load_policy(workspace_root)
    stamp_ttl = int(policy.get("stamp_ttl_minutes", 0) or 0)
    require_pass = bool(policy.get("require_pass_for_apply", True))
    report_path = workspace_root / ".cache" / "reports" / "preflight_stamp.v1.json"

    if mode == "read":
        if not report_path.exists():
            return {
                "status": "IDLE",
                "overall": "MISSING",
                "error_code": "NO_PREFLIGHT_STAMP",
                "report_path": "",
                "require_pass_for_apply": require_pass,
                "policy_source": policy_source,
                "notes": sorted(set(policy_notes + ["PROGRAM_LED=true", "NO_WAIT=true"]))
            }
        try:
            stamp = _load_json(report_path)
        except Exception:
            return {
                "status": "WARN",
                "overall": "FAIL",
                "error_code": "INVALID_PREFLIGHT_STAMP",
                "report_path": _rel_path(workspace_root, report_path),
                "require_pass_for_apply": require_pass,
                "policy_source": policy_source,
                "notes": sorted(set(policy_notes + ["PROGRAM_LED=true", "NO_WAIT=true"]))
            }
        overall, gates = _parse_stamp(stamp if isinstance(stamp, dict) else {})
        error_code = ""
        status = "OK" if overall == "PASS" else "WARN"
        if stamp_ttl > 0:
            generated_at = stamp.get("generated_at") if isinstance(stamp, dict) else None
            try:
                if isinstance(generated_at, str):
                    ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
                else:
                    ts = None
            except Exception:
                ts = None
            if ts is None:
                status = "WARN"
                error_code = "INVALID_PREFLIGHT_TIMESTAMP"
                overall = "FAIL"
            else:
                age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
                if age_seconds > stamp_ttl * 60:
                    status = "WARN"
                    error_code = "PRECHECK_STALE"
                    overall = "STALE"
        if overall != "PASS" and not error_code:
            error_code = "PRECHECK_FAILED"
        return {
            "status": status,
            "overall": overall,
            "error_code": error_code,
            "report_path": _rel_path(workspace_root, report_path),
            "gates": gates if isinstance(gates, dict) else {},
            "require_pass_for_apply": require_pass,
            "policy_source": policy_source,
            "notes": sorted(set(policy_notes + ["PROGRAM_LED=true", "NO_WAIT=true"]))
        }

    repo_root = _repo_root()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    validate_rc = subprocess.run([sys.executable, "ci/validate_schemas.py"], cwd=repo_root).returncode
    validate_status = "PASS" if validate_rc == 0 else "FAIL"

    smoke_status, smoke_notes = _smoke_fast_job_gate(workspace_root=workspace_root)

    sb_path = workspace_root / ".cache" / "script_budget" / "report.json"
    sb_path.parent.mkdir(parents=True, exist_ok=True)
    sb_rc = subprocess.run(
        [sys.executable, "ci/check_script_budget.py", "--out", str(sb_path)],
        cwd=repo_root,
    ).returncode

    hard_exceeded = 0
    soft_exceeded = 0
    sb_status = "FAIL"
    if sb_path.exists():
        try:
            report = _load_json(sb_path)
            if isinstance(report, dict):
                report = _normalize_script_budget_report(report)
                sb_status = str(report.get("status") or "FAIL")
                hard_exceeded = int(report.get("hard_exceeded", hard_exceeded) or 0)
                soft_exceeded = int(report.get("soft_exceeded", soft_exceeded) or 0)
                sb_path.write_text(_dump_json(report), encoding="utf-8")
        except Exception:
            sb_status = "FAIL"

    if sb_rc != 0 and sb_status == "OK":
        sb_status = "WARN"

    overall = "PASS" if validate_status == "PASS" and smoke_status == "PASS" and hard_exceeded == 0 else "FAIL"

    notes = sorted(set(policy_notes + ["PROGRAM_LED=true", "NO_WAIT=true"] + smoke_notes))
    stamp = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "gates": {
            "validate_schemas": validate_status,
            "smoke_fast": smoke_status,
            "script_budget": {
                "hard_exceeded": hard_exceeded,
                "soft_exceeded": soft_exceeded,
                "status": sb_status,
            },
        },
        "overall": overall,
        "notes": notes,
    }

    report_path.write_text(_dump_json(stamp), encoding="utf-8")
    md_path = workspace_root / ".cache" / "reports" / "preflight_stamp.v1.md"
    md_lines = [
        "PREFLIGHT STAMP",
        "",
        f"Overall: {overall}",
        f"validate_schemas: {validate_status}",
        f"smoke_fast: {smoke_status}",
        f"script_budget: {sb_status}",
        f"hard_exceeded: {hard_exceeded}",
        f"soft_exceeded: {soft_exceeded}",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": "OK" if overall == "PASS" else "WARN",
        "overall": overall,
        "report_path": _rel_path(workspace_root, report_path),
        "gates": stamp.get("gates"),
        "require_pass_for_apply": require_pass,
        "policy_source": policy_source,
        "notes": notes,
    }
