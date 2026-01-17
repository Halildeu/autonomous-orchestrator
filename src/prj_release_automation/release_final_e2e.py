from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.prj_kernel_api.dotenv_loader import resolve_env_value
from src.prj_release_automation.release_engine import build_release_plan, prepare_release, publish_release


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, _dump_json(payload))


def _redact_git_stderr(stderr_text: str) -> str:
    # Best-effort redaction: avoid leaking token-like strings if git echoes them (should not).
    text = (stderr_text or "").replace("\r\n", "\n")
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.getenv(key, "")
        if val and val in text:
            text = text.replace(val, "***REDACTED***")
    return text


@dataclass(frozen=True)
class _GitResult:
    returncode: int
    stdout: str
    stderr: str


def _run_git(
    args: list[str],
    *,
    repo_root: Path,
    env: dict[str, str] | None = None,
) -> _GitResult:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return _GitResult(
        returncode=int(proc.returncode),
        stdout=(proc.stdout or "").strip(),
        stderr=_redact_git_stderr(proc.stderr or ""),
    )


def _load_env_value(key_name: str, *, workspace_root: Path) -> str:
    raw = os.getenv(key_name, "")
    if raw:
        return raw
    present, value = resolve_env_value(key_name, str(workspace_root), env_mode="dotenv")
    return str(value or "") if present and value else ""


def _ensure_git_askpass(workspace_root: Path) -> Path:
    # Askpass script contains no secrets; it reads the token from env at runtime.
    out = workspace_root / ".cache" / "tmp" / "git_askpass.sh"
    content = "\n".join(
        [
            "#!/bin/sh",
            'case \"$1\" in',
            '  *Username*) echo \"x-access-token\" ;;',
            '  *Password*) echo \"${GITHUB_TOKEN}\" ;;',
            "  *) echo \"\" ;;",
            "esac",
            "",
        ]
    )
    _atomic_write_text(out, content)
    try:
        out.chmod(0o700)
    except Exception:
        pass
    return out


def _git_env_with_token(*, workspace_root: Path) -> tuple[dict[str, str], str | None]:
    token = _load_env_value("GITHUB_TOKEN", workspace_root=workspace_root)
    if not token:
        return {}, "AUTH_MISSING"
    askpass = _ensure_git_askpass(workspace_root)
    env = os.environ.copy()
    env.update(
        {
            "GITHUB_TOKEN": token,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": str(askpass),
        }
    )
    return env, None


def _poll_job(
    *,
    workspace_root: Path,
    job_id: str,
    max_polls: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    from src.prj_github_ops.github_ops import poll_github_ops_job

    last: dict[str, Any] = {"status": "FAIL", "error_code": "POLL_NOT_STARTED", "job_id": job_id}
    for _i in range(max(1, int(max_polls))):
        last = poll_github_ops_job(workspace_root=workspace_root, job_id=job_id)
        status = str(last.get("status") or "")
        if status in {"PASS", "FAIL", "SKIP", "IDLE", "TIMEOUT", "KILLED"}:
            return last
        time.sleep(max(0.0, float(sleep_seconds)))
    last["status"] = "TIMEOUT"
    last["error_code"] = "POLL_TIMEOUT"
    return last


def _load_job_rc(*, workspace_root: Path, job_id: str) -> dict[str, Any] | None:
    rc_path = workspace_root / ".cache" / "github_ops" / "jobs" / job_id / "rc.json"
    if not rc_path.exists():
        return None
    try:
        obj = json.loads(rc_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def run_release_final_e2e(
    *,
    workspace_root: Path,
    base_branch: str = "main",
    allow_network: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    ws = workspace_root
    repo_root = _repo_root()
    now = _now_iso_z()

    # --- Preflight: infer repo identity + policy gate ---
    from src.prj_github_ops.github_ops_support_v2 import _infer_repo_from_git
    from src.prj_github_ops.github_ops import run_github_ops_check, start_github_ops_job

    owner, repo = _infer_repo_from_git(repo_root)
    if not owner or not repo:
        return {"status": "FAIL", "error_code": "REPO_INFER_FAIL"}

    gh_check = run_github_ops_check(workspace_root=ws, chat=False)
    live_gate_enabled = bool(gh_check.get("live_gate_enabled", False))
    live_gate_network = bool(gh_check.get("live_gate_network_enabled", False))
    env_key_present = bool(gh_check.get("env_key_present", False))

    if allow_network and (not live_gate_enabled or not live_gate_network or not env_key_present):
        return {
            "status": "FAIL",
            "error_code": "GITHUB_OPS_GATE_BLOCKED",
            "gate": {
                "live_gate_enabled": live_gate_enabled,
                "live_gate_network_enabled": live_gate_network,
                "env_key_present": env_key_present,
            },
        }

    # --- Determine release version + branch name deterministically ---
    plan = build_release_plan(workspace_root=ws, channel="final", detail=False)
    version_plan = plan.get("version_plan") if isinstance(plan.get("version_plan"), dict) else {}
    release_version = str(version_plan.get("channel_version") or "").strip()
    if not release_version:
        return {"status": "FAIL", "error_code": "RELEASE_VERSION_MISSING"}
    tag = release_version if release_version.startswith("v") else f"v{release_version}"

    head_sha = _run_git(["rev-parse", "HEAD"], repo_root=repo_root)
    if head_sha.returncode != 0 or not head_sha.stdout:
        return {"status": "FAIL", "error_code": "GIT_HEAD_SHA_FAIL", "git_stderr": head_sha.stderr}
    short_sha = _run_git(["rev-parse", "--short", "HEAD"], repo_root=repo_root)
    short = short_sha.stdout.strip() if short_sha.returncode == 0 else ""
    branch_name = f"release/final/{tag}-{short}" if short else f"release/final/{tag}"

    report: dict[str, Any] = {
        "version": "v0.1",
        "ts": now,
        "status": "RUNNING",
        "workspace_root": str(ws),
        "repo": {"owner": owner, "name": repo, "remote": "origin"},
        "inputs": {"base_branch": base_branch, "allow_network": bool(allow_network), "dry_run": bool(dry_run)},
        "release": {"channel": "final", "tag": tag, "release_version": release_version},
        "branch": {"name": branch_name, "head_sha": head_sha.stdout},
        "jobs": {},
        "git": {"dirty_before": None},
        "notes": [],
    }

    if dry_run or not allow_network:
        report["status"] = "IDLE"
        report["notes"].append("dry_run_or_network_disabled: no git push / no github ops jobs started")
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    git_env, git_env_err = _git_env_with_token(workspace_root=ws)
    if git_env_err:
        report["status"] = "FAIL"
        report["error_code"] = git_env_err
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    # --- Ensure clean commit ---
    status_res = _run_git(["status", "--porcelain"], repo_root=repo_root)
    report["git"]["dirty_before"] = bool(status_res.stdout.strip())
    if status_res.stdout.strip():
        add_res = _run_git(["add", "-A"], repo_root=repo_root, env=git_env)
        if add_res.returncode != 0:
            report["status"] = "FAIL"
            report["error_code"] = "GIT_ADD_FAIL"
            report["git"]["add_stderr"] = add_res.stderr
            out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
            _atomic_write_json(out_path, report)
            report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
            return report
        commit_msg = f"chore: prep {tag} (release flow)"
        commit_res = _run_git(["commit", "-m", commit_msg], repo_root=repo_root, env=git_env)
        if commit_res.returncode != 0:
            report["status"] = "FAIL"
            report["error_code"] = "GIT_COMMIT_FAIL"
            report["git"]["commit_stderr"] = commit_res.stderr
            out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
            _atomic_write_json(out_path, report)
            report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
            return report

    # --- Create/switch branch and push ---
    checkout_res = _run_git(["checkout", "-B", branch_name], repo_root=repo_root, env=git_env)
    if checkout_res.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_CHECKOUT_BRANCH_FAIL"
        report["git"]["checkout_stderr"] = checkout_res.stderr
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    push_res = _run_git(["push", "-u", "origin", branch_name], repo_root=repo_root, env=git_env)
    if push_res.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_PUSH_FAIL"
        report["git"]["push_stderr"] = push_res.stderr
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    # --- PR_OPEN job ---
    pr_title = f"Release FINAL {tag}"
    pr_request = {
        "repo_owner": owner,
        "repo_name": repo,
        "base_branch": base_branch,
        "head_branch": branch_name,
        "title": pr_title,
        "body": f"Automated release flow for {tag}.",
        "draft": False,
    }
    pr_open = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False, request=pr_request)
    pr_job_id = str(pr_open.get("job_id") or "")
    report["jobs"]["pr_open"] = {"job_id": pr_job_id, "start": pr_open}
    if not pr_job_id:
        report["status"] = "FAIL"
        report["error_code"] = pr_open.get("error_code") or "PR_OPEN_START_FAIL"
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    pr_poll = _poll_job(workspace_root=ws, job_id=pr_job_id, max_polls=60, sleep_seconds=1.0)
    report["jobs"]["pr_open"]["poll"] = pr_poll
    if pr_poll.get("status") != "PASS":
        report["status"] = "FAIL"
        report["error_code"] = "PR_OPEN_FAIL"
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    pr_rc = _load_job_rc(workspace_root=ws, job_id=pr_job_id) or {}
    pr_number = pr_rc.get("pr_number") if isinstance(pr_rc.get("pr_number"), int) else None
    report["jobs"]["pr_open"]["rc"] = {k: pr_rc.get(k) for k in sorted(pr_rc.keys()) if k in {"pr_url", "pr_number", "pr_state", "noop"}}

    # --- MERGE job ---
    merge = start_github_ops_job(workspace_root=ws, kind="MERGE", dry_run=False, request=None)
    merge_job_id = str(merge.get("job_id") or "")
    report["jobs"]["merge"] = {"job_id": merge_job_id, "start": merge}
    if not merge_job_id:
        report["status"] = "FAIL"
        report["error_code"] = merge.get("error_code") or "MERGE_START_FAIL"
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    merge_poll = _poll_job(workspace_root=ws, job_id=merge_job_id, max_polls=60, sleep_seconds=1.0)
    report["jobs"]["merge"]["poll"] = merge_poll
    if merge_poll.get("status") != "PASS":
        report["status"] = "FAIL"
        report["error_code"] = "MERGE_FAIL"
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    merge_rc = _load_job_rc(workspace_root=ws, job_id=merge_job_id) or {}
    merge_commit_sha = str(merge_rc.get("merge_commit_sha") or "").strip() or None
    report["jobs"]["merge"]["rc"] = {k: merge_rc.get(k) for k in sorted(merge_rc.keys()) if k in {"merge_commit_sha", "pr_number_inferred", "noop"}}

    # --- Sync local base branch to origin/base ---
    checkout_main = _run_git(["checkout", base_branch], repo_root=repo_root, env=git_env)
    if checkout_main.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_CHECKOUT_BASE_FAIL"
        report["git"]["checkout_base_stderr"] = checkout_main.stderr
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    fetch_main = _run_git(["fetch", "origin", base_branch], repo_root=repo_root, env=git_env)
    if fetch_main.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_FETCH_BASE_FAIL"
        report["git"]["fetch_base_stderr"] = fetch_main.stderr
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    reset_main = _run_git(["reset", "--hard", f"origin/{base_branch}"], repo_root=repo_root, env=git_env)
    if reset_main.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_RESET_BASE_FAIL"
        report["git"]["reset_base_stderr"] = reset_main.stderr
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    head_after = _run_git(["rev-parse", "HEAD"], repo_root=repo_root)
    report["git"]["head_after_merge"] = head_after.stdout if head_after.returncode == 0 else None
    report["git"]["merge_commit_sha"] = merge_commit_sha
    if merge_commit_sha and head_after.stdout and merge_commit_sha != head_after.stdout:
        report["notes"].append("merge_sha_mismatch_vs_local_head: proceeding with local HEAD for release job")

    # --- Prepare + publish FINAL release ---
    build_release_plan(workspace_root=ws, channel="final", detail=False)
    prepare_release(workspace_root=ws, channel="final")
    publish = publish_release(workspace_root=ws, channel="final", allow_network=True, trusted_context=True)
    report["jobs"]["release_publish"] = {"start": publish}
    release_job_id = str(publish.get("related_job_id") or "")
    report["jobs"]["release_publish"]["job_id"] = release_job_id
    if not release_job_id:
        report["status"] = "FAIL"
        report["error_code"] = publish.get("error_code") or "RELEASE_PUBLISH_START_FAIL"
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    release_poll = _poll_job(workspace_root=ws, job_id=release_job_id, max_polls=90, sleep_seconds=1.0)
    report["jobs"]["release_publish"]["poll"] = release_poll
    if release_poll.get("status") != "PASS":
        report["status"] = "FAIL"
        report["error_code"] = "RELEASE_FINAL_FAIL"
        out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    release_rc = _load_job_rc(workspace_root=ws, job_id=release_job_id) or {}
    report["jobs"]["release_publish"]["rc"] = {k: release_rc.get(k) for k in sorted(release_rc.keys()) if k in {"release_url", "release_tag", "noop"}}

    # --- Success ---
    report["status"] = "OK"
    report["notes"].append(f"pr_number={pr_number}" if pr_number else "pr_number_missing")
    out_path = ws / ".cache" / "reports" / "release_final_e2e.v1.json"
    _atomic_write_json(out_path, report)
    report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
    return report
