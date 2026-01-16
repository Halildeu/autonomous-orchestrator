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


def _load_network_live_summary(workspace_root: Path) -> dict[str, Any]:
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_network_live.override.v1.json"
    if not override_path.exists():
        return {
            "enabled_by_decision": False,
            "allow_domains_count": 0,
            "allow_actions_count": 0,
            "policy_source": "missing",
        }
    try:
        payload = _load_json(override_path)
    except Exception:
        return {
            "enabled_by_decision": False,
            "allow_domains_count": 0,
            "allow_actions_count": 0,
            "policy_source": "override_invalid",
        }
    if not isinstance(payload, dict):
        return {
            "enabled_by_decision": False,
            "allow_domains_count": 0,
            "allow_actions_count": 0,
            "policy_source": "override_invalid",
        }
    return {
        "enabled_by_decision": bool(payload.get("enabled_by_decision", False)),
        "allow_domains_count": int(payload.get("allow_domains_count") or 0),
        "allow_actions_count": int(payload.get("allow_actions_count") or 0),
        "policy_source": "workspace_override",
    }


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


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    items: list[Any]
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    cleaned = {str(item).strip() for item in items if str(item).strip()}
    return sorted(cleaned)


def _git_remote_url(root: Path, remote: str = "origin") -> str:
    if not _git_available(root):
        return ""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", remote],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _parse_github_remote(remote_url: str) -> tuple[str, str]:
    raw = remote_url.strip()
    if not raw:
        return "", ""
    if raw.endswith(".git"):
        raw = raw[:-4]
    if raw.startswith("git@github.com:"):
        path = raw.split("git@github.com:", 1)[1]
    elif raw.startswith("ssh://git@github.com/"):
        path = raw.split("ssh://git@github.com/", 1)[1]
    elif raw.startswith("https://github.com/"):
        path = raw.split("https://github.com/", 1)[1]
    elif raw.startswith("http://github.com/"):
        path = raw.split("http://github.com/", 1)[1]
    else:
        return "", ""
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]


def _infer_repo_from_git(root: Path) -> tuple[str, str]:
    env_repo = _clean_str(os.getenv("GITHUB_REPOSITORY"))
    if env_repo and "/" in env_repo:
        owner, name = env_repo.split("/", 1)
        return owner.strip(), name.strip()
    remote_url = _git_remote_url(root, remote="origin")
    return _parse_github_remote(remote_url)


def _normalize_pr_open_request(
    request: dict[str, Any] | None,
    *,
    repo_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    req = request if isinstance(request, dict) else {}

    repo_owner = _clean_str(req.get("repo_owner"))
    repo_name = _clean_str(req.get("repo_name"))
    base_branch = _clean_str(req.get("base_branch"))
    head_branch = _clean_str(req.get("head_branch"))
    title = _clean_str(req.get("title"))
    body = _clean_str(req.get("body"))
    draft = req.get("draft")
    if not isinstance(draft, bool):
        draft = True
    labels = _normalize_str_list(req.get("labels"))
    reviewers = _normalize_str_list(req.get("reviewers"))
    assignees = _normalize_str_list(req.get("assignees"))

    missing: list[str] = []
    if not repo_owner or not repo_name:
        repo_owner, repo_name = _infer_repo_from_git(repo_root)
    if not repo_owner:
        missing.append("repo_owner")
    if not repo_name:
        missing.append("repo_name")
    if not base_branch:
        missing.append("base_branch")
    if not head_branch:
        missing.append("head_branch")
    if not title:
        missing.append("title")

    payload = {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "title": title,
        "body": body,
        "draft": bool(draft),
    }
    if labels:
        payload["labels"] = labels
    if reviewers:
        payload["reviewers"] = reviewers
    if assignees:
        payload["assignees"] = assignees
    return payload, missing


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
