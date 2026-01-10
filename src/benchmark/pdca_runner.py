from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.benchmark.integrity_utils import load_policy_integrity


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_bytes(data: bytes) -> str:
    return __import__("hashlib").sha256(data).hexdigest()


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _load_policy_pdca(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_pdca.v1.json"
    core_policy = core_root / "policies" / "policy_pdca.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {
            "version": "v1",
            "enabled": True,
            "quota": {"max_gaps_per_run": 50},
            "cooldown": {"days": 1},
            "retention": {"max_reports": 10},
        }
    obj = _load_json(path)
    return obj if isinstance(obj, dict) else {}


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def run_pdca(*, workspace_root: Path, dry_run: bool) -> dict[str, Any]:
    core_root = Path(__file__).resolve().parents[2]
    policy = _load_policy_pdca(core_root=core_root, workspace_root=workspace_root)
    if not isinstance(policy, dict) or not policy.get("enabled", True):
        return {"status": "SKIPPED", "reason": "policy_disabled"}

    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    if not gap_path.exists():
        return {"status": "FAIL", "error_code": "GAP_REGISTER_MISSING"}

    gap_obj = _load_json(gap_path)
    gaps = gap_obj.get("gaps") if isinstance(gap_obj, dict) else None
    gaps_list = gaps if isinstance(gaps, list) else []

    gap_statuses: dict[str, str] = {}
    for g in gaps_list:
        if not isinstance(g, dict):
            continue
        gid = g.get("id") if isinstance(g.get("id"), str) else None
        status = g.get("status") if isinstance(g.get("status"), str) else None
        if gid and status:
            gap_statuses[gid] = status

    prev_cursor_path = workspace_root / ".cache" / "index" / "pdca_cursor.v1.json"
    prev_cursor = _load_json(prev_cursor_path) if prev_cursor_path.exists() else {}
    prev_statuses = prev_cursor.get("gap_statuses") if isinstance(prev_cursor, dict) else {}
    prev_statuses = prev_statuses if isinstance(prev_statuses, dict) else {}

    regressions: list[dict[str, Any]] = []
    for gid, status in sorted(gap_statuses.items()):
        prev = prev_statuses.get(gid)
        if prev == "closed" and status == "open":
            regressions.append(
                {
                    "gap_id": gid,
                    "previous_status": "closed",
                    "current_status": "open",
                    "severity": "medium",
            }
        )

    operability_status = None
    operability_reasons: list[str] = []
    eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    if eval_path.exists():
        try:
            eval_obj = _load_json(eval_path)
            lenses = eval_obj.get("lenses") if isinstance(eval_obj, dict) else None
            if isinstance(lenses, dict):
                operability = lenses.get("operability")
                if isinstance(operability, dict):
                    status = operability.get("status")
                    if isinstance(status, str):
                        operability_status = status
                    reasons = operability.get("reasons")
                    if isinstance(reasons, list):
                        operability_reasons = [str(r) for r in reasons if isinstance(r, str) and r.strip()]
        except Exception:
            operability_status = None
            operability_reasons = []

    prev_operability = prev_cursor.get("operability_status") if isinstance(prev_cursor, dict) else None
    if isinstance(prev_operability, str) and isinstance(operability_status, str):
        rank = {"OK": 0, "WARN": 1, "FAIL": 2}
        if rank.get(operability_status, 0) > rank.get(prev_operability, 0):
            regressions.append(
                {
                    "gap_id": "OPERABILITY_DRIFT",
                    "previous_status": prev_operability,
                    "current_status": operability_status,
                    "severity": "high" if operability_status == "FAIL" else "medium",
                }
            )

    integrity_status = None
    integrity_path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    if integrity_path.exists():
        try:
            obj = _load_json(integrity_path)
            integrity_status = obj.get("verify_on_read_result") if isinstance(obj, dict) else None
        except Exception:
            integrity_status = None
    if integrity_status == "FAIL":
        regressions.append(
            {
                "gap_id": "INTEGRITY_DRIFT",
                "previous_status": "pass",
                "current_status": "fail",
                "severity": "high",
            }
        )

    quota = policy.get("quota") if isinstance(policy.get("quota"), dict) else {}
    cooldown = policy.get("cooldown") if isinstance(policy.get("cooldown"), dict) else {}
    retention = policy.get("retention") if isinstance(policy.get("retention"), dict) else {}
    max_gaps = int(quota.get("max_gaps_per_run", 0) or 0)
    cooldown_days = int(cooldown.get("days", 0) or 0)
    retention_max = int(retention.get("max_reports", 0) or 0)

    def _severity_rank(value: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(value, 1)

    sorted_gaps = []
    for g in gaps_list:
        if not isinstance(g, dict):
            continue
        gid = g.get("id") if isinstance(g.get("id"), str) else ""
        sev = g.get("severity") if isinstance(g.get("severity"), str) else "medium"
        sorted_gaps.append((_severity_rank(sev), gid, g))
    sorted_gaps.sort(key=lambda item: (item[0], item[1]))
    selected = [g for _, _, g in sorted_gaps]
    quota_state = "OK"
    if max_gaps > 0 and len(selected) > max_gaps:
        selected = selected[:max_gaps]
        quota_state = "WARN"

    cooldown_state = "NONE"
    last_run_at = prev_cursor.get("last_run_at") if isinstance(prev_cursor, dict) else None
    last_run = _parse_iso(last_run_at) if isinstance(last_run_at, str) else None
    if cooldown_days > 0 and last_run is not None:
        delta_days = (datetime.now(timezone.utc) - last_run).days
        if delta_days < cooldown_days:
            cooldown_state = "COOLDOWN_ACTIVE"
            selected = []

    policy_integrity = load_policy_integrity(core_root=core_root, workspace_root=workspace_root)
    allow_report_only = bool(policy_integrity.get("allow_report_only_when_missing_sources", True))
    report_only = False
    status = "OK"
    if integrity_status == "FAIL":
        if allow_report_only:
            report_only = True
            status = "WARN"
        else:
            return {"status": "FAIL", "error_code": "INTEGRITY_BLOCKED"}

    report_path = workspace_root / ".cache" / "reports" / "pdca_recheck_report.v1.json"
    regression_path = workspace_root / ".cache" / "index" / "regression_index.v1.json"
    cursor_path = workspace_root / ".cache" / "index" / "pdca_cursor.v1.json"
    _ensure_inside_workspace(workspace_root, report_path)
    _ensure_inside_workspace(workspace_root, regression_path)
    _ensure_inside_workspace(workspace_root, cursor_path)

    current_hashes = {
        "gap_register": _hash_bytes(gap_path.read_bytes()) if gap_path.exists() else None,
        "assessment_raw": None,
        "assessment_eval": None,
        "integrity_snapshot": _hash_bytes(integrity_path.read_bytes()) if integrity_path.exists() else None,
    }
    raw_path = workspace_root / ".cache" / "index" / "assessment_raw.v1.json"
    if raw_path.exists():
        current_hashes["assessment_raw"] = _hash_bytes(raw_path.read_bytes())
    eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    if eval_path.exists():
        current_hashes["assessment_eval"] = _hash_bytes(eval_path.read_bytes())

    operability_state = f"{operability_status or 'UNKNOWN'}|{','.join(sorted(set(operability_reasons)))}"
    lens_state_hash = _hash_bytes(operability_state.encode("utf-8"))

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "report_only": bool(report_only),
        "integrity_status": integrity_status or "UNKNOWN",
        "regressions_count": len(regressions),
        "open_gaps": len([1 for s in gap_statuses.values() if s == "open"]),
        "closed_gaps": len([1 for s in gap_statuses.values() if s == "closed"]),
        "quota_state": quota_state,
        "cooldown_state": cooldown_state,
        "targets_count": len(selected),
    }

    regression_index = {
        "version": "v1",
        "generated_at": _now_iso(),
        "regressions": regressions,
    }

    history = prev_cursor.get("history_reports") if isinstance(prev_cursor, dict) else None
    history_list = history if isinstance(history, list) else []
    history_paths = [p for p in history_list if isinstance(p, str)]
    history_paths.append(str(Path(".cache") / "reports" / "pdca_recheck_report.v1.json"))
    if retention_max > 0:
        history_paths = history_paths[-retention_max:]

    cursor = {
        "version": "v1",
        "generated_at": _now_iso(),
        "last_run_at": _now_iso(),
        "hashes": current_hashes,
        "gap_statuses": gap_statuses,
        "history_reports": history_paths,
        "operability_status": operability_status or "UNKNOWN",
        "operability_reasons": sorted(set(operability_reasons)),
        "lens_state_hash": lens_state_hash,
    }

    if dry_run:
        return {"status": "WOULD_WRITE", "out": str(report_path)}

    report_path.parent.mkdir(parents=True, exist_ok=True)
    regression_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.parent.mkdir(parents=True, exist_ok=True)

    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    regression_path.write_text(json.dumps(regression_index, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    cursor_path.write_text(json.dumps(cursor, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return {"status": "OK", "out": str(report_path), "regressions": len(regressions)}
