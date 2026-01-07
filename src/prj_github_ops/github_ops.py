from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


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
        "live_gate": {
            "enabled": False,
            "require_env_key_present": True,
            "env_flag": "KERNEL_API_GITHUB_LIVE",
            "env_key": "GITHUB_TOKEN",
        },
        "allowed_ops": ["pr_list", "pr_open", "pr_update", "merge", "deploy_trigger", "status_poll"],
        "auth": {"mode": "bearer", "token_env": "GITHUB_TOKEN"},
        "retry_count": 0,
        "job": {"keep_last_n": 50, "ttl_seconds": 604800, "poll_interval_seconds": 300},
        "notes": ["network_default_off"],
    }


def _load_policy(workspace_root: Path) -> tuple[dict[str, Any], str, str, list[str]]:
    notes: list[str] = []
    policy = _policy_defaults()
    policy_source = "core"

    core_path = _repo_root() / "policies" / "policy_github_ops.v1.json"
    ws_path = workspace_root / "policies" / "policy_github_ops.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_github_ops.override.v1.json"

    for path, source_label in [(core_path, "core"), (ws_path, "workspace"), (override_path, "workspace_override")]:
        if not path.exists():
            continue
        try:
            obj = _load_json(path)
        except Exception:
            notes.append(f"policy_invalid:{source_label}")
            continue
        if isinstance(obj, dict):
            policy = _deep_merge(policy, obj)
            if source_label != "core":
                policy_source = "core+workspace_override"

    policy_hash = _hash_text(_canonical_json(policy))
    return policy, policy_source, policy_hash, notes


def _env_truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _live_gate(policy: dict[str, Any]) -> dict[str, Any]:
    live = policy.get("live_gate") if isinstance(policy.get("live_gate"), dict) else {}
    enabled = bool(live.get("enabled", False))
    env_flag = str(live.get("env_flag") or "")
    env_key = str(live.get("env_key") or "")
    require_key = bool(live.get("require_env_key_present", True))

    env_flag_set = _env_truthy(os.getenv(env_flag)) if env_flag else False
    env_key_present = bool(os.getenv(env_key)) if require_key and env_key else True
    is_enabled = enabled and env_flag_set and env_key_present

    allowed_ops = policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else []
    allowed_ops = sorted({str(x) for x in allowed_ops if isinstance(x, str) and x})

    return {
        "enabled": is_enabled,
        "env_flag": env_flag,
        "env_key_present": env_key_present,
        "allowed_ops": allowed_ops,
    }


def _git_available(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_dir(root: Path) -> Path | None:
    if not _git_available(root):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path


def _git_branch(root: Path) -> str:
    if not _git_available(root):
        return ""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _git_dirty_tree(root: Path) -> bool:
    if not _git_available(root):
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def _git_ahead_behind(root: Path) -> tuple[int, int]:
    if not _git_available(root):
        return (0, 0)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return (0, 0)
    if proc.returncode != 0 or not proc.stdout.strip():
        return (0, 0)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--left-right", "--count", "@{u}...HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return (0, 0)
    if proc.returncode != 0:
        return (0, 0)
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return (0, 0)
    try:
        behind, ahead = int(parts[0]), int(parts[1])
    except Exception:
        return (0, 0)
    return (ahead, behind)


def _git_state(root: Path) -> dict[str, Any]:
    ahead, behind = _git_ahead_behind(root)
    git_dir = _git_dir(root)
    index_lock = bool(git_dir and (git_dir / "index.lock").exists())
    return {
        "dirty_tree": _git_dirty_tree(root),
        "branch": _git_branch(root),
        "ahead": max(ahead, 0),
        "behind": max(behind, 0),
        "index_lock": index_lock,
    }


def _jobs_index_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "github_ops" / "jobs_index.v1.json"


def _default_jobs_index(workspace_root: Path) -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": "IDLE",
        "jobs": [],
        "counts": {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0},
        "notes": [],
    }


def _load_jobs_index(workspace_root: Path) -> tuple[dict[str, Any], list[str]]:
    path = _jobs_index_path(workspace_root)
    if not path.exists():
        return _default_jobs_index(workspace_root), ["jobs_index_missing"]
    try:
        obj = _load_json(path)
    except Exception:
        return _default_jobs_index(workspace_root), ["jobs_index_invalid"]
    if not isinstance(obj, dict):
        return _default_jobs_index(workspace_root), ["jobs_index_invalid"]
    if not isinstance(obj.get("jobs"), list):
        obj["jobs"] = []
    return obj, []


def _save_jobs_index(workspace_root: Path, index: dict[str, Any]) -> str:
    jobs = index.get("jobs") if isinstance(index.get("jobs"), list) else []
    jobs = [j for j in jobs if isinstance(j, dict)]
    jobs.sort(key=lambda j: (str(j.get("created_at") or ""), str(j.get("job_id") or "")))

    counts = {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0}
    for job in jobs:
        status = str(job.get("status") or "").upper()
        counts["total"] += 1
        if status == "QUEUED":
            counts["queued"] += 1
        elif status == "RUNNING":
            counts["running"] += 1
        elif status == "PASS":
            counts["pass"] += 1
        elif status == "FAIL":
            counts["fail"] += 1
        elif status == "TIMEOUT":
            counts["timeout"] += 1
        elif status == "KILLED":
            counts["killed"] += 1
        elif status == "SKIP":
            counts["skip"] += 1

    index["jobs"] = jobs
    index["counts"] = counts
    index["generated_at"] = _now_iso()
    index.setdefault("version", "v1")
    index.setdefault("workspace_root", str(workspace_root))

    path = _jobs_index_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(index), encoding="utf-8")
    rel = Path(".cache") / "github_ops" / path.name
    return rel.as_posix()


def _job_report_path(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "reports" / "github_ops_jobs" / f"github_ops_job_{job_id}.v1.json"


def _write_job_report(workspace_root: Path, job: dict[str, Any]) -> str:
    path = _job_report_path(workspace_root, str(job.get("job_id") or "unknown"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(job), encoding="utf-8")
    return (Path(".cache") / "reports" / "github_ops_jobs" / path.name).as_posix()


def _job_signature(job: dict[str, Any]) -> str:
    payload = {
        "kind": job.get("kind"),
        "status": job.get("status"),
        "error_code": job.get("error_code"),
        "failure_class": job.get("failure_class"),
    }
    return _hash_text(_canonical_json(payload))


def build_github_ops_report(*, workspace_root: Path) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    live_gate = _live_gate(policy)
    git_state = _git_state(_repo_root())

    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)

    jobs_index_rel = _save_jobs_index(workspace_root, jobs_index)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    counts = jobs_index.get("counts") if isinstance(jobs_index.get("counts"), dict) else {}

    signals: list[str] = []
    if git_state.get("dirty_tree"):
        signals.append("dirty_tree")
    if int(git_state.get("behind") or 0) > 0:
        signals.append("behind_remote")
    if git_state.get("index_lock"):
        signals.append("index_lock")
    if not live_gate.get("enabled", False):
        signals.append("live_gate_disabled")
    signals = sorted({str(s) for s in signals if isinstance(s, str) and s})

    status = "OK"
    if signals:
        status = "WARN"
    if int(counts.get("fail", 0)) > 0:
        status = "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "live_gate": {
            "enabled": bool(live_gate.get("enabled", False)),
            "env_flag": str(live_gate.get("env_flag") or ""),
            "env_key_present": bool(live_gate.get("env_key_present", False)),
            "allowed_ops": live_gate.get("allowed_ops") or [],
        },
        "git_state": git_state,
        "signals": signals,
        "jobs_summary": {
            "total": int(counts.get("total", 0)),
            "by_status": {
                "QUEUED": int(counts.get("queued", 0)),
                "RUNNING": int(counts.get("running", 0)),
                "PASS": int(counts.get("pass", 0)),
                "FAIL": int(counts.get("fail", 0)),
                "TIMEOUT": int(counts.get("timeout", 0)),
                "KILLED": int(counts.get("killed", 0)),
                "SKIP": int(counts.get("skip", 0)),
            },
        },
        "jobs_index_path": jobs_index_rel,
        "notes": notes,
    }
    if jobs:
        report["jobs"] = sorted(jobs, key=lambda j: str(j.get("job_id") or ""))

    report_path = workspace_root / ".cache" / "reports" / "github_ops_report.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(report), encoding="utf-8")
    return report


def run_github_ops_check(*, workspace_root: Path, chat: bool = True) -> dict[str, Any]:
    report = build_github_ops_report(workspace_root=workspace_root)
    report_path = str(Path(".cache") / "reports" / "github_ops_report.v1.json")

    signals = report.get("signals") if isinstance(report.get("signals"), list) else []
    status = report.get("status", "WARN")

    preview_lines = [
        "PROGRAM-LED: github-ops-check; user_command=false",
        f"workspace_root={workspace_root}",
    ]
    result_lines = [
        f"status={status}",
        f"signals={','.join(str(s) for s in signals) if signals else 'none'}",
        f"dirty_tree={report.get('git_state', {}).get('dirty_tree', False)}",
        f"behind={report.get('git_state', {}).get('behind', 0)}",
    ]
    evidence_lines = [f"github_ops_report={report_path}"]
    actions_lines = ["github-ops-job-start", "github-ops-job-poll"]
    next_lines = ["Devam et", "Durumu goster", "Duraklat"]

    final_json = {
        "status": status,
        "report_path": report_path,
        "signals": signals,
        "dirty_tree": report.get("git_state", {}).get("dirty_tree", False),
        "behind": report.get("git_state", {}).get("behind", 0),
        "index_lock": report.get("git_state", {}).get("index_lock", False),
        "live_gate_enabled": report.get("live_gate", {}).get("enabled", False),
        "jobs_index_path": report.get("jobs_index_path"),
    }

    if chat:
        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join(str(x) for x in evidence_lines if x))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))
        print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))

    return final_json


def start_github_ops_job(*, workspace_root: Path, kind: str, dry_run: bool) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    live_gate = _live_gate(policy)
    now = _now_iso()

    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)

    job_id = _hash_text(_canonical_json({"kind": kind, "created_at": now, "policy_hash": policy_hash}))

    status = "SKIP" if dry_run or not live_gate.get("enabled", False) else "QUEUED"
    skip_reason = ""
    if dry_run:
        skip_reason = "DRY_RUN"
    elif not live_gate.get("enabled", False):
        skip_reason = "LIVE_GATE_DISABLED"

    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": kind,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(workspace_root),
        "dry_run": bool(dry_run),
        "live_gate": bool(live_gate.get("enabled", False)),
        "attempts": 0,
        "skip_reason": skip_reason,
        "error_code": "" if status != "SKIP" else skip_reason,
        "notes": notes,
        "evidence_paths": [],
        "result_paths": [],
    }

    job["signature_hash"] = _job_signature(job)

    job_report = _write_job_report(workspace_root, job)
    job["evidence_paths"].append(job_report)

    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    jobs.append(job)
    jobs_index["jobs"] = jobs
    jobs_index_path = _save_jobs_index(workspace_root, jobs_index)

    return {
        "status": status,
        "job_id": job_id,
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "policy_source": policy_source,
    }


def poll_github_ops_job(*, workspace_root: Path, job_id: str) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    _ = policy
    _ = policy_hash
    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)

    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    target: dict[str, Any] | None = None
    for job in jobs:
        if str(job.get("job_id") or "") == job_id:
            target = job
            break

    if target is None:
        return {"status": "FAIL", "error_code": "JOB_NOT_FOUND", "job_id": job_id}

    status = str(target.get("status") or "")
    if status in {"QUEUED", "RUNNING"}:
        target["status"] = "SKIP"
        target["skip_reason"] = "NO_WORKER"
        target["error_code"] = "NO_WORKER"
    target["updated_at"] = _now_iso()
    target["last_poll_at"] = _now_iso()
    target["signature_hash"] = _job_signature(target)

    job_report = _write_job_report(workspace_root, target)
    evidence = target.get("evidence_paths") if isinstance(target.get("evidence_paths"), list) else []
    if job_report not in evidence:
        evidence.append(job_report)
    target["evidence_paths"] = evidence

    jobs_index["jobs"] = jobs
    jobs_index_path = _save_jobs_index(workspace_root, jobs_index)

    return {
        "status": str(target.get("status") or ""),
        "job_id": job_id,
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "policy_source": policy_source,
    }
