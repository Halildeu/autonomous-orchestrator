from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.prj_airunner.airunner_tick_utils import _load_json


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _work_intake_hash(workspace_root: Path) -> str:
    path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not path.exists():
        return "missing"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return "invalid"
    return _hash_text(text)


def _intake_suggests_extension(workspace_root: Path, work_intake_path: str | None, extension_id: str) -> bool:
    if not work_intake_path:
        return False
    path = (workspace_root / work_intake_path).resolve()
    try:
        obj = _load_json(path)
    except Exception:
        return False
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict):
            continue
        suggested = item.get("suggested_extension")
        if isinstance(suggested, list) and extension_id in {str(x) for x in suggested if isinstance(x, str)}:
            return True
    return False


def _load_github_ops_jobs_index(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / ".cache" / "github_ops" / "jobs_index.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list):
        return []
    return [j for j in jobs if isinstance(j, dict)]


def _load_deploy_jobs_index(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / ".cache" / "deploy" / "jobs_index.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list):
        return []
    return [j for j in jobs if isinstance(j, dict)]


def _load_airunner_jobs_running(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list):
        return []
    running = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if str(job.get("status") or "") in {"RUNNING", "QUEUED"}:
            running.append(job)
    return running


def _has_github_ops_signals(workspace_root: Path) -> bool:
    report_path = workspace_root / ".cache" / "reports" / "github_ops_report.v1.json"
    if not report_path.exists():
        return False
    try:
        report = _load_json(report_path)
    except Exception:
        return False
    signals = report.get("signals") if isinstance(report, dict) else None
    if not isinstance(signals, list):
        return False
    return any(isinstance(s, str) and s.strip() for s in signals)


def _allow_repeat_tick(workspace_root: Path, allowed_ops: list[str]) -> bool:
    if "github-ops-job-start" in allowed_ops and _has_github_ops_signals(workspace_root):
        return True
    work_intake_path = str(Path(".cache") / "index" / "work_intake.v1.json")
    if _intake_suggests_extension(workspace_root, work_intake_path, "PRJ-GITHUB-OPS"):
        return True
    return False


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
