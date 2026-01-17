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
    # NOTE: Avoid .strip() here; porcelain outputs are space-sensitive.
    stdout = (proc.stdout or "").replace("\r\n", "\n").rstrip("\n")
    return _GitResult(
        returncode=int(proc.returncode),
        stdout=stdout,
        stderr=_redact_git_stderr(proc.stderr or ""),
    )


def _load_env_value(key_name: str, *, workspace_root: Path) -> str:
    raw = os.getenv(key_name, "")
    if raw:
        return raw
    present, value = resolve_env_value(key_name, str(workspace_root), env_mode="dotenv")
    return str(value or "") if present and value else ""


def _ensure_git_askpass(workspace_root: Path) -> Path:
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


def _parse_status_porcelain(porcelain: str) -> list[str]:
    paths: list[str] = []
    for raw in (porcelain or "").splitlines():
        line = raw.strip("\n")
        if not line:
            continue
        # Examples:
        #  ' M src/file.py'
        #  '?? new_file.py'
        #  'R  old.py -> new.py'
        rest = line[3:] if len(line) >= 4 else ""
        if "->" in rest:
            a, b = rest.split("->", 1)
            for p in (a.strip(), b.strip()):
                if p:
                    paths.append(p)
        else:
            p = rest.strip()
            if p:
                paths.append(p)
    return sorted(set(paths))


def _is_safe_commit_path(path: str) -> bool:
    p = str(path or "").lstrip("./")
    allowed_prefixes = (
        "src/",
        "docs/",
        "policies/",
        "schemas/",
        "extensions/",
        "roadmaps/",
        "registry/",
        "workflows/",
        "orchestrator/",
    )
    return any(p.startswith(prefix) for prefix in allowed_prefixes)


def run_pr_merge_e2e(
    *,
    workspace_root: Path,
    base_branch: str = "main",
    allow_network: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    ws = workspace_root
    repo_root = _repo_root()
    now = _now_iso_z()

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

    head_sha = _run_git(["rev-parse", "HEAD"], repo_root=repo_root)
    if head_sha.returncode != 0 or not head_sha.stdout:
        return {"status": "FAIL", "error_code": "GIT_HEAD_SHA_FAIL", "git_stderr": head_sha.stderr}
    short_sha = _run_git(["rev-parse", "--short", "HEAD"], repo_root=repo_root)
    short = short_sha.stdout.strip() if short_sha.returncode == 0 else ""

    current_branch_res = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root)
    current_branch = current_branch_res.stdout.strip() if current_branch_res.returncode == 0 else ""
    branch_mode = "create_new"
    if current_branch and current_branch not in {"HEAD", base_branch}:
        branch_name = current_branch
        branch_mode = "reuse_current"
    else:
        branch_name = f"automerge/{short}" if short else "automerge/head"

    report: dict[str, Any] = {
        "version": "v0.1",
        "ts": now,
        "status": "RUNNING",
        "workspace_root": str(ws),
        "repo": {"owner": owner, "name": repo, "remote": "origin"},
        "inputs": {"base_branch": base_branch, "allow_network": bool(allow_network), "dry_run": bool(dry_run)},
        "branch": {"name": branch_name, "mode": branch_mode, "head_sha": head_sha.stdout},
        "jobs": {},
        "git": {"dirty_before": None, "dirty_paths": [], "unsafe_paths": []},
        "notes": [],
    }

    out_path = ws / ".cache" / "reports" / "pr_merge_e2e.v1.json"

    if dry_run or not allow_network:
        report["status"] = "IDLE"
        report["notes"].append("dry_run_or_network_disabled: no git push / no github ops jobs started")
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    git_env, git_env_err = _git_env_with_token(workspace_root=ws)
    if git_env_err:
        report["status"] = "FAIL"
        report["error_code"] = git_env_err
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    # --- Branch first (avoid committing on base branch) ---
    if branch_mode == "create_new":
        checkout_res = _run_git(["checkout", "-B", branch_name], repo_root=repo_root, env=git_env)
        if checkout_res.returncode != 0:
            report["status"] = "FAIL"
            report["error_code"] = "GIT_CHECKOUT_BRANCH_FAIL"
            report["git"]["checkout_stderr"] = checkout_res.stderr
            _atomic_write_json(out_path, report)
            report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
            return report

    # --- Ensure clean commit (safe roots only) ---
    status_res = _run_git(["status", "--porcelain"], repo_root=repo_root)
    dirty_paths = _parse_status_porcelain(status_res.stdout)
    unsafe_paths = [p for p in dirty_paths if not _is_safe_commit_path(p)]
    report["git"]["dirty_before"] = bool(dirty_paths)
    report["git"]["dirty_paths"] = dirty_paths[:200]
    report["git"]["unsafe_paths"] = unsafe_paths[:200]

    if unsafe_paths:
        report["status"] = "FAIL"
        report["error_code"] = "DIRTY_TREE_OUT_OF_SCOPE"
        report["notes"].append("Refusing to commit paths outside safe roots (prevents secret/cached files).")
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    if dirty_paths:
        add_res = _run_git(["add", "-A", "--", *dirty_paths], repo_root=repo_root, env=git_env)
        if add_res.returncode != 0:
            report["status"] = "FAIL"
            report["error_code"] = "GIT_ADD_FAIL"
            report["git"]["add_stderr"] = add_res.stderr
            _atomic_write_json(out_path, report)
            report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
            return report

        commit_msg = "chore: pr merge e2e (sync)"
        commit_res = _run_git(["commit", "-m", commit_msg], repo_root=repo_root, env=git_env)
        if commit_res.returncode != 0:
            report["status"] = "FAIL"
            report["error_code"] = "GIT_COMMIT_FAIL"
            report["git"]["commit_stderr"] = commit_res.stderr
            _atomic_write_json(out_path, report)
            report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
            return report

    push_res = _run_git(["push", "-u", "origin", branch_name], repo_root=repo_root, env=git_env)
    if push_res.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_PUSH_FAIL"
        report["git"]["push_stderr"] = push_res.stderr
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    # --- PR_OPEN job ---
    pr_title_res = _run_git(["log", "-1", "--pretty=%s"], repo_root=repo_root)
    pr_title = pr_title_res.stdout.strip() if pr_title_res.returncode == 0 and pr_title_res.stdout else "Auto PR merge"
    pr_request = {
        "repo_owner": owner,
        "repo_name": repo,
        "base_branch": base_branch,
        "head_branch": branch_name,
        "title": pr_title,
        "body": "Program-led PR open -> merge (no release).",
        "draft": False,
    }
    pr_open = start_github_ops_job(workspace_root=ws, kind="PR_OPEN", dry_run=False, request=pr_request)
    pr_job_id = str(pr_open.get("job_id") or "")
    report["jobs"]["pr_open"] = {"job_id": pr_job_id, "start": pr_open}
    if not pr_job_id:
        report["status"] = "FAIL"
        report["error_code"] = pr_open.get("error_code") or "PR_OPEN_START_FAIL"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    pr_poll = _poll_job(workspace_root=ws, job_id=pr_job_id, max_polls=60, sleep_seconds=1.0)
    report["jobs"]["pr_open"]["poll"] = pr_poll
    if pr_poll.get("status") != "PASS":
        report["status"] = "FAIL"
        report["error_code"] = "PR_OPEN_FAIL"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    pr_rc = _load_job_rc(workspace_root=ws, job_id=pr_job_id) or {}
    pr_number = pr_rc.get("pr_number") if isinstance(pr_rc.get("pr_number"), int) else None
    report["jobs"]["pr_open"]["rc"] = {k: pr_rc.get(k) for k in sorted(pr_rc.keys()) if k in {"pr_url", "pr_number", "pr_state", "noop"}}

    # --- MERGE job (explicit pr_number; fail-closed) ---
    if not pr_number:
        report["status"] = "FAIL"
        report["error_code"] = "PR_NUMBER_MISSING"
        report["notes"].append("Cannot safely merge without explicit pr_number from PR_OPEN rc.json.")
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    expected_head_sha = _run_git(["rev-parse", "HEAD"], repo_root=repo_root)
    merge_req = {"pr_number": int(pr_number), "expected_head_sha": expected_head_sha.stdout if expected_head_sha.returncode == 0 else ""}
    merge = start_github_ops_job(workspace_root=ws, kind="MERGE", dry_run=False, request=merge_req)
    merge_job_id = str(merge.get("job_id") or "")
    report["jobs"]["merge"] = {"job_id": merge_job_id, "start": merge}
    if not merge_job_id:
        report["status"] = "FAIL"
        report["error_code"] = merge.get("error_code") or "MERGE_START_FAIL"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    merge_poll = _poll_job(workspace_root=ws, job_id=merge_job_id, max_polls=90, sleep_seconds=1.0)
    report["jobs"]["merge"]["poll"] = merge_poll
    if merge_poll.get("status") != "PASS":
        report["status"] = "FAIL"
        report["error_code"] = "MERGE_FAIL"
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    merge_rc = _load_job_rc(workspace_root=ws, job_id=merge_job_id) or {}
    report["jobs"]["merge"]["rc"] = {k: merge_rc.get(k) for k in sorted(merge_rc.keys()) if k in {"merge_commit_sha", "pr_number", "pr_number_inferred", "noop"}}

    # --- Sync local base branch to origin/base (clean tree) ---
    checkout_base = _run_git(["checkout", base_branch], repo_root=repo_root, env=git_env)
    if checkout_base.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_CHECKOUT_BASE_FAIL"
        report["git"]["checkout_base_stderr"] = checkout_base.stderr
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    fetch_base = _run_git(["fetch", "origin", base_branch], repo_root=repo_root, env=git_env)
    if fetch_base.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_FETCH_BASE_FAIL"
        report["git"]["fetch_base_stderr"] = fetch_base.stderr
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    reset_base = _run_git(["reset", "--hard", f"origin/{base_branch}"], repo_root=repo_root, env=git_env)
    if reset_base.returncode != 0:
        report["status"] = "FAIL"
        report["error_code"] = "GIT_RESET_BASE_FAIL"
        report["git"]["reset_base_stderr"] = reset_base.stderr
        _atomic_write_json(out_path, report)
        report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
        return report

    status_after = _run_git(["status", "--porcelain"], repo_root=repo_root)
    report["git"]["dirty_after"] = bool(status_after.stdout.strip())
    if report["git"]["dirty_after"]:
        report["notes"].append("dirty_tree_after_merge_sync: investigate gitignore / generated files")

    report["status"] = "OK"
    _atomic_write_json(out_path, report)
    report["report_path"] = str(Path(".cache") / "reports" / out_path.name)
    return report
