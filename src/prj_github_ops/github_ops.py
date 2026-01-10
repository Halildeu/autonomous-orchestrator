from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _job_time(job: dict[str, Any]) -> datetime:
    for key in ("started_at", "updated_at", "created_at"):
        ts = _parse_iso(str(job.get(key) or ""))
        if ts:
            return ts
    return datetime.fromtimestamp(0, tz=timezone.utc)


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
        "network_enabled": False,
        "live_gate": {
            "enabled": False,
            "require_env_key_present": True,
            "env_flag": "KERNEL_API_GITHUB_LIVE",
            "env_key": "GITHUB_TOKEN",
        },
        "allowed_actions": ["PR_OPEN", "PR_POLL", "CI_POLL", "MERGE", "RELEASE_RC", "RELEASE_FINAL"],
        "allowed_ops": ["pr_list", "pr_open", "pr_update", "merge", "deploy_trigger", "status_poll"],
        "auth": {"mode": "bearer", "token_env": "GITHUB_TOKEN"},
        "retry_count": 0,
        "rate_limit": {"cooldown_seconds": 300, "max_per_tick": 1},
        "job": {"keep_last_n": 50, "ttl_seconds": 604800, "poll_interval_seconds": 300, "cooldown_seconds": 3600},
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


def _allowed_actions(policy: dict[str, Any]) -> list[str]:
    actions = policy.get("allowed_actions") if isinstance(policy.get("allowed_actions"), list) else []
    actions = [str(x) for x in actions if isinstance(x, str) and x.strip()]
    if actions:
        return sorted(set(actions))
    allowed_ops = policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else []
    mapped = []
    for op in allowed_ops:
        op_raw = str(op).strip().lower()
        if not op_raw:
            continue
        mapped.append(
            {
                "pr_list": "PR_LIST",
                "pr_open": "PR_OPEN",
                "pr_update": "PR_UPDATE",
                "merge": "MERGE",
                "deploy_trigger": "DEPLOY_TRIGGER",
                "status_poll": "STATUS_POLL",
            }.get(op_raw, op_raw.upper())
        )
    return sorted(set(mapped))


def _normalize_kind(kind: str, *, policy: dict[str, Any]) -> str:
    raw = str(kind or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    lower = raw.lower()
    allowed_actions = set(_allowed_actions(policy))
    allowed_ops = {
        str(x).strip().lower()
        for x in (policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else [])
        if isinstance(x, str)
    }
    aliases = {
        "pr_list": "PR_LIST",
        "pr_open": "PR_OPEN",
        "pr_update": "PR_UPDATE",
        "merge": "MERGE",
        "deploy_trigger": "DEPLOY_TRIGGER",
        "status_poll": "STATUS_POLL",
    }
    if upper in allowed_actions:
        return upper
    if lower in allowed_ops:
        return aliases.get(lower, upper)
    if upper in {
        "PR_LIST",
        "PR_OPEN",
        "PR_UPDATE",
        "PR_POLL",
        "CI_POLL",
        "MERGE",
        "RELEASE_RC",
        "RELEASE_FINAL",
        "SMOKE_FULL",
        "DEPLOY_TRIGGER",
        "STATUS_POLL",
    }:
        return upper
    return upper


def _gate_details(policy: dict[str, Any]) -> dict[str, Any]:
    live = policy.get("live_gate") if isinstance(policy.get("live_gate"), dict) else {}
    enabled = bool(live.get("enabled", False))
    env_flag = str(live.get("env_flag") or "")
    env_key = str(live.get("env_key") or "")
    require_key = bool(live.get("require_env_key_present", True))
    env_flag_set = _env_truthy(os.getenv(env_flag)) if env_flag else False
    env_key_present = bool(os.getenv(env_key)) if require_key and env_key else True
    network_enabled = bool(policy.get("network_enabled", False))
    effective = network_enabled and enabled and env_flag_set and env_key_present
    return {
        "enabled": effective,
        "network_enabled": network_enabled,
        "live_enabled": enabled,
        "env_flag": env_flag,
        "env_flag_set": env_flag_set,
        "env_key_present": env_key_present,
    }


def _live_gate(policy: dict[str, Any]) -> dict[str, Any]:
    details = _gate_details(policy)
    allowed_ops = policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else []
    allowed_ops = sorted({str(x) for x in allowed_ops if isinstance(x, str) and x})

    return {
        "enabled": bool(details.get("enabled", False)),
        "network_enabled": bool(details.get("network_enabled", False)),
        "env_flag": str(details.get("env_flag") or ""),
        "env_key_present": bool(details.get("env_key_present", False)),
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
    status = "IDLE"
    if counts["total"] > 0:
        status = "OK"
    if counts["fail"] > 0 or counts["timeout"] > 0 or counts["killed"] > 0:
        status = "WARN"
    elif counts["running"] > 0 or counts["queued"] > 0:
        status = "WARN"
    index["status"] = status
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


def _job_store_dir(workspace_root: Path, job_id: str) -> Path:
    return workspace_root / ".cache" / "github_ops" / "jobs" / job_id


def _job_output_paths(workspace_root: Path, job_id: str) -> tuple[Path, Path, Path]:
    base = _job_store_dir(workspace_root, job_id)
    return (base / "stdout.log", base / "stderr.log", base / "rc.json")


def _rel_from_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()

def _job_signature(job: dict[str, Any]) -> str:
    payload = {
        "kind": job.get("kind"),
        "status": job.get("status"),
        "error_code": job.get("error_code"),
        "failure_class": job.get("failure_class"),
    }
    return _hash_text(_canonical_json(payload))


def _gate_error(policy: dict[str, Any]) -> str:
    details = _gate_details(policy)
    if not details.get("network_enabled", False):
        return "NETWORK_DISABLED"
    if not details.get("live_enabled", False):
        return "LIVE_GATE_DISABLED"
    if details.get("env_flag") and not details.get("env_flag_set", False):
        return "LIVE_GATE_ENV_FLAG_MISSING"
    if not details.get("env_key_present", False):
        return "AUTH_MISSING"
    return ""


def _cooldown_active(jobs: list[dict[str, Any]], *, kind: str, cooldown_seconds: int) -> tuple[bool, str]:
    if cooldown_seconds <= 0:
        return False, ""
    now = datetime.now(timezone.utc)
    recent_id = ""
    for job in sorted(jobs, key=_job_time, reverse=True):
        if str(job.get("kind") or "") != kind:
            continue
        ts = _job_time(job)
        if now - ts <= timedelta(seconds=cooldown_seconds):
            recent_id = str(job.get("job_id") or "")
            return True, recent_id
        break
    return False, recent_id


def _spawn_job_process(
    workspace_root: Path,
    job_id: str,
    *,
    command_fingerprint: str,
    kind: str,
) -> tuple[int | None, list[str]]:
    stdout_path, stderr_path, rc_path = _job_output_paths(workspace_root, job_id)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    if kind == "SMOKE_FULL":
        stub = (
            "import json,os,subprocess,sys;"
            "env=os.environ.copy();"
            "env['SMOKE_LEVEL']='full';"
            "env['SMOKE_FULL_ASYNC_JOB']='1';"
            "rc=subprocess.call([sys.executable,'smoke_test.py'], env=env, cwd=os.getcwd());"
            "json.dump({'rc':rc,'fingerprint':sys.argv[2]}, open(sys.argv[1],'w'));"
        )
        cmd = [sys.executable, "-c", stub, str(rc_path), command_fingerprint]
    else:
        stub = (
            "import json,sys,time;"
            "time.sleep(0.1);"
            "json.dump({'rc':0,'fingerprint':sys.argv[2]}, open(sys.argv[1],'w'));"
        )
        cmd = [sys.executable, "-c", stub, str(rc_path), command_fingerprint]
    try:
        stdout_f = stdout_path.open("w", encoding="utf-8")
        stderr_f = stderr_path.open("w", encoding="utf-8")
    except Exception:
        return None, []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=stdout_f,
            stderr=stderr_f,
            cwd=str(_repo_root()),
            env=os.environ.copy(),
        )
    except Exception:
        return None, []
    finally:
        try:
            stdout_f.close()
        except Exception:
            pass
        try:
            stderr_f.close()
        except Exception:
            pass

    rel_paths = [
        _rel_from_workspace(stdout_path, workspace_root),
        _rel_from_workspace(stderr_path, workspace_root),
        _rel_from_workspace(rc_path, workspace_root),
    ]
    return proc.pid, rel_paths


def classify_github_ops_failure(stderr_text: str) -> tuple[str, str]:
    lowered = stderr_text.lower()
    if "ws_integration_demo" in lowered and "prerequisite apply failed" in lowered:
        failure_class = "DEMO_PREREQ_FAIL"
    elif "ws_integration_demo" in lowered and "catalog" in lowered and "parse" in lowered:
        failure_class = "DEMO_CATALOG_PARSE"
    elif "schema validation" in lowered or "integrity verify" in lowered:
        failure_class = "CORE_BREAK"
    else:
        failure_class = "OTHER"

    lines: list[str] = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line[:200])
        if len(lines) >= 10:
            break
    signature_hash = _hash_text(f"{failure_class}|" + "|".join(lines))
    return failure_class, signature_hash


def _apply_job_retention(jobs: list[dict[str, Any]], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    job_cfg = policy.get("job") if isinstance(policy.get("job"), dict) else {}
    keep_last_n = int(job_cfg.get("keep_last_n", 0) or 0)
    ttl_seconds = int(job_cfg.get("ttl_seconds", 0) or 0)
    now = datetime.now(timezone.utc)
    kept: list[dict[str, Any]] = []
    for job in sorted([j for j in jobs if isinstance(j, dict)], key=_job_time, reverse=True):
        if ttl_seconds and now - _job_time(job) > timedelta(seconds=ttl_seconds):
            continue
        kept.append(job)
        if keep_last_n and len(kept) >= keep_last_n:
            break
    return sorted(kept, key=lambda j: (str(j.get("created_at") or ""), str(j.get("job_id") or "")))


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
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []

    normalized_kind = _normalize_kind(kind, policy=policy)
    local_only = normalized_kind == "SMOKE_FULL"
    allowed_actions = set(_allowed_actions(policy))
    allowed_ops = {
        str(x).strip().lower()
        for x in (policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else [])
        if isinstance(x, str)
    }
    allowed_aliases = {
        "pr_list": "PR_LIST",
        "pr_open": "PR_OPEN",
        "pr_update": "PR_UPDATE",
        "merge": "MERGE",
        "deploy_trigger": "DEPLOY_TRIGGER",
        "status_poll": "STATUS_POLL",
    }
    allowed_kinds = allowed_actions | {allowed_aliases.get(op, op.upper()) for op in allowed_ops}
    if normalized_kind not in allowed_kinds:
        return {
            "status": "IDLE",
            "error_code": "KIND_NOT_ALLOWED",
            "job_id": "",
            "job_kind": normalized_kind,
            "cooldown_hit": False,
            "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
            "policy_source": policy_source,
        }

    if not local_only:
        rate_cfg = policy.get("rate_limit") if isinstance(policy.get("rate_limit"), dict) else {}
        rate_cooldown = int(rate_cfg.get("cooldown_seconds", 0) or 0)
        max_per_tick = int(rate_cfg.get("max_per_tick", 0) or 0)
        if rate_cooldown and max_per_tick:
            now_dt = datetime.now(timezone.utc)
            recent_jobs = [j for j in jobs if now_dt - _job_time(j) <= timedelta(seconds=rate_cooldown)]
            if len(recent_jobs) >= max_per_tick:
                return {
                    "status": "IDLE",
                    "error_code": "RATE_LIMIT",
                    "job_id": "",
                    "job_kind": normalized_kind,
                    "cooldown_hit": True,
                    "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                    "policy_source": policy_source,
                }

    if not local_only:
        cooldown_seconds = int(
            (policy.get("job") or {}).get("cooldown_seconds", 0) if isinstance(policy.get("job"), dict) else 0
        )
        cooldown_hit, recent_id = _cooldown_active(jobs, kind=normalized_kind, cooldown_seconds=cooldown_seconds)
        if cooldown_hit:
            return {
                "status": "IDLE",
                "error_code": "COOLDOWN_ACTIVE",
                "job_id": recent_id,
                "job_kind": normalized_kind,
                "cooldown_hit": True,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
            }

    for job in jobs:
        if str(job.get("kind") or "") == normalized_kind and str(job.get("status") or "") in {"QUEUED", "RUNNING"}:
            return {
                "status": "IDLE",
                "error_code": "JOB_ALREADY_RUNNING",
                "job_id": str(job.get("job_id") or ""),
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
            }

    job_id = _hash_text(_canonical_json({"kind": normalized_kind, "policy_hash": policy_hash, "dry_run": dry_run}))
    gate_error = _gate_error(policy)

    status = "RUNNING"
    skip_reason = ""
    error_code = ""
    return_status = "RUNNING"
    pid: int | None = None
    result_paths: list[str] = []

    if dry_run:
        status = "SKIP"
        skip_reason = "DRY_RUN"
        error_code = "DRY_RUN"
        return_status = "SKIP"
    elif not live_gate.get("enabled", False) and not local_only:
        status = "SKIP"
        skip_reason = gate_error or "LIVE_GATE_DISABLED"
        if skip_reason == "NETWORK_DISABLED":
            skip_reason = "NO_NETWORK"
        error_code = gate_error or "LIVE_GATE_DISABLED"
        return_status = "IDLE"
    else:
        command_fingerprint = _hash_text(_canonical_json({"kind": normalized_kind, "policy_hash": policy_hash}))
        pid, result_paths = _spawn_job_process(
            workspace_root,
            job_id,
            command_fingerprint=command_fingerprint,
            kind=normalized_kind,
        )
        if pid is None:
            status = "FAIL"
            error_code = "SPAWN_FAILED"
            return_status = "WARN"
        else:
            status = "RUNNING"

    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": normalized_kind,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(workspace_root),
        "dry_run": bool(dry_run),
        "live_gate": bool(live_gate.get("enabled", False)),
        "attempts": 1 if status in {"RUNNING", "PASS", "FAIL"} else 0,
        "error_code": error_code,
        "skip_reason": skip_reason,
        "notes": notes,
        "evidence_paths": [],
        "result_paths": result_paths,
    }
    if pid is not None:
        job["pid"] = pid
        job["started_at"] = now
    if status == "PASS":
        job["failure_class"] = "PASS"
    elif status == "FAIL" and error_code:
        job["failure_class"] = "OTHER"
    elif status == "TIMEOUT":
        job["failure_class"] = "TIMEOUT"

    job["signature_hash"] = _job_signature(job)

    job_report = _write_job_report(workspace_root, job)
    job["evidence_paths"].append(job_report)

    jobs = [j for j in jobs if str(j.get("job_id") or "") != job_id]
    jobs.append(job)
    jobs_index["jobs"] = _apply_job_retention(jobs, policy=policy)
    jobs_index_path = _save_jobs_index(workspace_root, jobs_index)

    return {
        "status": return_status,
        "job_id": job_id,
        "job_kind": normalized_kind,
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "policy_source": policy_source,
        "error_code": error_code or None,
        "cooldown_hit": False,
    }


def poll_github_ops_job(*, workspace_root: Path, job_id: str) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
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
    now = datetime.now(timezone.utc)
    timeout_seconds = int(
        (policy.get("job") or {}).get("ttl_seconds", 0) if isinstance(policy.get("job"), dict) else 0
    )

    if status in {"QUEUED", "RUNNING"}:
        pid = target.get("pid")
        job_time = _job_time(target)
        if timeout_seconds and now - job_time > timedelta(seconds=timeout_seconds):
            if isinstance(pid, int):
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
            target["status"] = "TIMEOUT"
            target["failure_class"] = "TIMEOUT"
            target["error_code"] = "TIMEOUT"
        else:
            running = False
            if isinstance(pid, int):
                try:
                    os.kill(pid, 0)
                    running = True
                except Exception:
                    running = False
            if running:
                target["status"] = "RUNNING"
            else:
                rc_path = _job_output_paths(workspace_root, job_id)[2]
                rc = None
                if rc_path.exists():
                    try:
                        rc_obj = _load_json(rc_path)
                        rc = int(rc_obj.get("rc")) if isinstance(rc_obj, dict) else None
                    except Exception:
                        rc = None
                if rc is None:
                    target["status"] = "FAIL"
                    target["error_code"] = "RC_MISSING"
                elif rc == 0:
                    target["status"] = "PASS"
                    target["failure_class"] = "PASS"
                else:
                    target["status"] = "FAIL"
                    target["error_code"] = "RC_NONZERO"
                    target["rc"] = rc

                if target.get("status") == "FAIL":
                    stderr_path = _job_output_paths(workspace_root, job_id)[1]
                    try:
                        stderr_text = stderr_path.read_text(encoding="utf-8")
                    except Exception:
                        stderr_text = ""
                    failure_class, signature_hash = classify_github_ops_failure(stderr_text)
                    target["failure_class"] = failure_class
                    target["signature_hash"] = signature_hash

    target["updated_at"] = _now_iso()
    target["last_poll_at"] = _now_iso()
    if not target.get("signature_hash"):
        target["signature_hash"] = _job_signature(target)

    job_report = _write_job_report(workspace_root, target)
    evidence = target.get("evidence_paths") if isinstance(target.get("evidence_paths"), list) else []
    if job_report not in evidence:
        evidence.append(job_report)
    target["evidence_paths"] = evidence

    jobs_index["jobs"] = _apply_job_retention(jobs, policy=policy)
    jobs_index_path = _save_jobs_index(workspace_root, jobs_index)

    return {
        "status": str(target.get("status") or ""),
        "job_id": job_id,
        "job_kind": str(target.get("kind") or ""),
        "failure_class": str(target.get("failure_class") or ""),
        "signature_hash": str(target.get("signature_hash") or ""),
        "job_report_path": job_report,
        "jobs_index_path": jobs_index_path,
        "policy_source": policy_source,
    }
