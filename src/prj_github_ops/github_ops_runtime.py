from __future__ import annotations

import src.prj_github_ops.github_ops as _core

for _name in dir(_core):
    if _name.startswith("__"):
        continue
    globals().setdefault(_name, getattr(_core, _name))

_RC_PENDING_ERROR_CODE = "RC_PENDING"
_RC_PENDING_GRACE_SECONDS = 3


def _run_pr_open_job(
    rc_path: str,
    request_path: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    from src.prj_github_ops.github_ops_job_runners import _run_pr_open_job as _impl

    _impl(
        rc_path=rc_path,
        request_path=request_path,
        token_env=token_env,
        auth_mode=auth_mode,
        fingerprint=fingerprint,
        workspace_root=workspace_root,
    )


def _run_pr_merge_job(
    rc_path: str,
    request_path: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    from src.prj_github_ops.github_ops_merge_job import _run_pr_merge_job_impl

    _run_pr_merge_job_impl(
        rc_path=rc_path,
        request_path=request_path,
        token_env=token_env,
        auth_mode=auth_mode,
        fingerprint=fingerprint,
        workspace_root=workspace_root,
    )

def _run_release_create_job(
    rc_path: str,
    kind: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    from src.prj_github_ops.github_ops_job_runners import _run_release_create_job as _impl

    _impl(
        rc_path=rc_path,
        kind=kind,
        token_env=token_env,
        auth_mode=auth_mode,
        fingerprint=fingerprint,
        workspace_root=workspace_root,
    )
def _live_gate(policy: dict[str, Any], *, workspace_root: Path) -> dict[str, Any]:
    details = _gate_details(policy, workspace_root=workspace_root)
    allowed_ops = policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else []
    allowed_ops = sorted({str(x) for x in allowed_ops if isinstance(x, str) and x})
    return {
        "enabled": bool(details.get("enabled", False)),
        "network_enabled": bool(details.get("network_enabled", False)),
        "env_flag": str(details.get("env_flag") or ""),
        "env_flag_set": bool(details.get("env_flag_set", False)),
        "env_key_present": bool(details.get("env_key_present", False)),
        "allowed_ops": allowed_ops,
    }
def _job_signature(job: dict[str, Any]) -> str:
    payload = {
        "kind": job.get("kind"),
        "status": job.get("status"),
        "error_code": job.get("error_code"),
        "failure_class": job.get("failure_class"),
    }
    return _hash_text(_canonical_json(payload))
def _job_report_rel(job_id: str) -> str:
    return (Path(".cache") / "reports" / "github_ops_jobs" / f"github_ops_job_{job_id}.v1.json").as_posix()
def _ensure_job_trace_meta(job: dict[str, Any], *, workspace_root: Path, policy_hash: str) -> None:
    if isinstance(job.get("trace_meta"), dict):
        return
    job_id = str(job.get("job_id") or "")
    if not job_id:
        return
    created_at = str(job.get("created_at") or _now_iso())
    run_id = build_run_id(
        workspace_root=workspace_root,
        op_name="github-ops-job",
        inputs={"job_id": job_id, "kind": job.get("kind"), "policy_hash": policy_hash},
        date_bucket=date_bucket_from_iso(created_at),
    )
    evidence_paths = job.get("evidence_paths") if isinstance(job.get("evidence_paths"), list) else []
    report_rel = _job_report_rel(job_id)
    if report_rel not in evidence_paths:
        evidence_paths.append(report_rel)
    job["evidence_paths"] = evidence_paths
    job["trace_meta"] = build_trace_meta(
        work_item_id=job_id,
        work_item_kind="JOB",
        run_id=run_id,
        policy_hash=policy_hash,
        evidence_paths=evidence_paths,
        workspace_root=workspace_root,
    )
def _gate_error(policy: dict[str, Any], *, workspace_root: Path) -> str:
    details = _gate_details(policy, workspace_root=workspace_root)
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
    request_path: Path | None = None,
    auth_mode: str = "bearer",
    token_env: str = "GITHUB_TOKEN",
) -> tuple[int | None, list[str]]:
    stdout_path, stderr_path, rc_path = _job_output_paths(workspace_root, job_id)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    if kind in {"SMOKE_FULL", "SMOKE_FAST"}:
        repo_root = _repo_root()
        venv_py = repo_root / ".venv" / "bin" / "python"
        python_bin = str(venv_py) if venv_py.exists() else sys.executable
        job_ws_root = _resolve_smoke_workspace_root()
        level = "full" if kind == "SMOKE_FULL" else "fast"
        cmd = [
            python_bin,
            "-m",
            "src.prj_airunner.smoke_full_job",
            "--workspace-root",
            str(job_ws_root),
            "--rc-path",
            str(rc_path),
            "--level",
            level,
            "--fingerprint",
            command_fingerprint,
        ]
    elif kind == "PR_OPEN":
        request_arg = str(request_path) if isinstance(request_path, Path) else ""
        stub = (
            "import sys;"
            "from src.prj_github_ops.github_ops import _run_pr_open_job;"
            "_run_pr_open_job(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6]);"
        )
        cmd = [
            sys.executable,
            "-c",
            stub,
            str(rc_path),
            request_arg,
            token_env,
            auth_mode,
            command_fingerprint,
            str(workspace_root),
        ]
    elif kind in {"RELEASE_RC", "RELEASE_FINAL"}:
        stub = (
            "import sys;"
            "from src.prj_github_ops.github_ops import _run_release_create_job;"
            "_run_release_create_job(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6]);"
        )
        cmd = [
            sys.executable,
            "-c",
            stub,
            str(rc_path),
            str(kind),
            token_env,
            auth_mode,
            command_fingerprint,
            str(workspace_root),
        ]
    elif kind == "MERGE":
        request_arg = str(request_path) if isinstance(request_path, Path) else ""
        stub = (
            "import sys;"
            "from src.prj_github_ops.github_ops import _run_pr_merge_job;"
            "_run_pr_merge_job(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6]);"
        )
        cmd = [
            sys.executable,
            "-c",
            stub,
            str(rc_path),
            request_arg,
            token_env,
            auth_mode,
            command_fingerprint,
            str(workspace_root),
        ]
    else:
        stub = (
            "import json,sys,time;"
            "time.sleep(0.1);"
            "json.dump({'rc':1,'error_code':'KIND_NOT_IMPLEMENTED','fingerprint':sys.argv[2],'kind':sys.argv[3]}, open(sys.argv[1],'w'));"
        )
        cmd = [sys.executable, "-c", stub, str(rc_path), command_fingerprint, str(kind)]
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
def _failure_summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    classes = [
        "AUTH",
        "PERMISSION",
        "VALIDATION",
        "NOT_FOUND",
        "CONFLICT",
        "RATE_LIMIT",
        "NETWORK",
        "POLICY_TIME_LIMIT",
        "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING",
        "DEMO_PACK_CAPABILITY_INDEX_MISSING",
        "DEMO_M9_3_APPLY_MUST_WRITE_PACK_SELECTION_TRACE_V1_JSON",
        "DEMO_OTHER_MARKER_2472D115C490",
        "DEMO_QUALITY_GATE_REPORT_MISSING",
        "DEMO_SESSION_CONTEXT_HASH_MISMATCH",
        "OTHER",
    ]
    counts = {cls: 0 for cls in classes}
    total_fail = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if str(job.get("status") or "") != "FAIL":
            continue
        total_fail += 1
        failure_class = str(job.get("failure_class") or "OTHER")
        if failure_class not in counts:
            failure_class = "OTHER"
        counts[failure_class] += 1
    return {"total_fail": total_fail, "by_class": counts}


def _job_in_workspace_scope(job: dict[str, Any], workspace_root: Path) -> bool:
    raw = job.get("workspace_root")
    if not isinstance(raw, str) or not raw.strip():
        return True
    job_ws = Path(raw)
    if not job_ws.is_absolute():
        job_ws = (_repo_root() / job_ws).resolve()
    else:
        job_ws = job_ws.resolve()
    try:
        return job_ws == workspace_root.resolve()
    except Exception:
        return False


def _count_jobs_by_status(jobs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": 0, "queued": 0, "running": 0, "pass": 0, "fail": 0, "timeout": 0, "killed": 0, "skip": 0}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        counts["total"] += 1
        status = str(job.get("status") or "").upper()
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
    return counts
def build_github_ops_report(*, workspace_root: Path) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    live_gate = _live_gate(policy, workspace_root=workspace_root)
    git_state = _git_state(_repo_root())
    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)
    jobs_raw = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    jobs = [job for job in jobs_raw if isinstance(job, dict)]
    retained_jobs = _apply_job_retention(jobs, policy=policy)
    stale_pruned_count = max(0, len(jobs) - len(retained_jobs))
    jobs = retained_jobs
    jobs_index["jobs"] = jobs
    jobs_index_rel = _save_jobs_index(workspace_root, jobs_index)

    scoped_jobs = [job for job in jobs if _job_in_workspace_scope(job, workspace_root)]
    external_jobs_count = max(0, len(jobs) - len(scoped_jobs))
    counts = _count_jobs_by_status(scoped_jobs)
    if stale_pruned_count > 0:
        notes.append(f"jobs_stale_pruned={stale_pruned_count}")
    if external_jobs_count > 0:
        notes.append(f"jobs_workspace_filtered={external_jobs_count}")
    last_pr_open: dict[str, Any] | None = None
    pr_jobs = [j for j in scoped_jobs if str(j.get("kind") or "") == "PR_OPEN"]
    if pr_jobs:
        pr_jobs.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")), reverse=True)
        job = pr_jobs[0]
        last_pr_open = {
            "job_id": str(job.get("job_id") or ""),
            "status": str(job.get("status") or ""),
        }
        pr_url = job.get("pr_url")
        if isinstance(pr_url, str) and pr_url:
            last_pr_open["pr_url"] = pr_url
        pr_number = job.get("pr_number")
        if isinstance(pr_number, int) and pr_number > 0:
            last_pr_open["pr_number"] = pr_number
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
    failure_summary = _failure_summary(scoped_jobs)
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
            "network_enabled": bool(live_gate.get("network_enabled", False)),
            "env_flag": str(live_gate.get("env_flag") or ""),
            "env_flag_set": bool(live_gate.get("env_flag_set", False)),
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
        "network_live": _load_network_live_summary(workspace_root),
        "failure_summary": failure_summary,
        "notes": sorted({str(n) for n in notes if isinstance(n, str) and n.strip()}),
    }
    if last_pr_open is not None:
        report["last_pr_open"] = last_pr_open
    if scoped_jobs:
        report["jobs"] = sorted(scoped_jobs, key=lambda j: str(j.get("job_id") or ""))
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
        "live_gate="
        + f"net={report.get('live_gate', {}).get('network_enabled', False)}"
        + f" live={report.get('live_gate', {}).get('enabled', False)}"
        + f" env_flag_set={report.get('live_gate', {}).get('env_flag_set', False)}"
        + f" env_key_present={report.get('live_gate', {}).get('env_key_present', False)}",
        "network_live="
        + f"enabled_by_decision={report.get('network_live', {}).get('enabled_by_decision', False)}"
        + f" allow_domains_count={report.get('network_live', {}).get('allow_domains_count', 0)}"
        + f" allow_actions_count={report.get('network_live', {}).get('allow_actions_count', 0)}",
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
        "live_gate_network_enabled": report.get("live_gate", {}).get("network_enabled", False),
        "env_flag_set": report.get("live_gate", {}).get("env_flag_set", False),
        "env_key_present": report.get("live_gate", {}).get("env_key_present", False),
        "network_live_enabled_by_decision": report.get("network_live", {}).get("enabled_by_decision", False),
        "allow_domains_count": report.get("network_live", {}).get("allow_domains_count", 0),
        "allow_actions_count": report.get("network_live", {}).get("allow_actions_count", 0),
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
def start_github_ops_job(
    *,
    workspace_root: Path,
    kind: str,
    dry_run: bool,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    live_gate = _live_gate(policy, workspace_root=workspace_root)
    gate_details = _gate_details(policy, workspace_root=workspace_root)
    git_state = _git_state(_repo_root())
    now = _now_iso()
    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    normalized_kind = _normalize_kind(kind, policy=policy)
    local_only = normalized_kind in {"SMOKE_FULL", "SMOKE_FAST"}
    allowed_actions = set(_allowed_actions(policy))
    allowed_ops = {str(x).strip().lower() for x in (policy.get("allowed_ops") if isinstance(policy.get("allowed_ops"), list) else []) if isinstance(x, str)}
    allowed_aliases = {"pr_list": "PR_LIST", "pr_open": "PR_OPEN", "pr_update": "PR_UPDATE", "merge": "MERGE", "deploy_trigger": "DEPLOY_TRIGGER", "status_poll": "STATUS_POLL"}
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
            "decision_needed": False,
            "decision_seed_path": None,
            "decision_inbox_path": None,
            "gate_state": {
                "network_enabled": bool(gate_details.get("network_enabled", False)),
                "live_enabled": bool(gate_details.get("live_enabled", False)),
                "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                "env_key_present": bool(gate_details.get("env_key_present", False)),
            },
        }

    if normalized_kind in {"RELEASE_RC", "RELEASE_FINAL"} and not dry_run:
        ahead = int(git_state.get("ahead") or 0)
        behind = int(git_state.get("behind") or 0)
        if git_state.get("dirty_tree"):
            return {
                "status": "IDLE",
                "error_code": "DIRTY_TREE",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        if ahead > 0:
            return {
                "status": "IDLE",
                "error_code": "AHEAD_REMOTE",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        if behind > 0:
            return {
                "status": "IDLE",
                "error_code": "BEHIND_REMOTE",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        if git_state.get("index_lock"):
            return {
                "status": "IDLE",
                "error_code": "INDEX_LOCK",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": False,
                "decision_seed_path": None,
                "decision_inbox_path": None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
    gate_error = _gate_error(policy, workspace_root=workspace_root)
    pr_request_payload: dict[str, Any] | None = None
    pr_request_missing: list[str] = []
    if normalized_kind == "PR_OPEN":
        pr_request_payload, pr_request_missing = _normalize_pr_open_request(request, repo_root=_repo_root())
        if pr_request_missing:
            last_request = _load_last_pr_open_request(workspace_root, jobs)
            if isinstance(last_request, dict):
                pr_request_payload, pr_request_missing = _normalize_pr_open_request(last_request, repo_root=_repo_root())
    decision_seed_path = ""
    decision_inbox_path = ""
    decision_needed = False
    if normalized_kind == "PR_OPEN" and not dry_run and gate_error and not local_only:
        decision_needed = True
        decision_inbox_path = str(Path(".cache") / "index" / "decision_inbox.v1.json")
        try:
            from src.ops.decision_inbox import run_decision_seed
            seed = run_decision_seed(
                workspace_root=workspace_root,
                decision_kind="NETWORK_LIVE_ENABLE",
                target="github_ops:PR_OPEN",
            )
            decision_seed_path = str(seed.get("seed_path") or "")
        except Exception:
            notes.append("decision_seed_failed")
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
                    "decision_needed": bool(decision_needed),
                    "decision_seed_path": decision_seed_path or None,
                    "decision_inbox_path": decision_inbox_path or None,
                    "request_missing": pr_request_missing if pr_request_missing else None,
                    "gate_state": {
                        "network_enabled": bool(gate_details.get("network_enabled", False)),
                        "live_enabled": bool(gate_details.get("live_enabled", False)),
                        "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                        "env_key_present": bool(gate_details.get("env_key_present", False)),
                    },
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
                "decision_needed": bool(decision_needed),
                "decision_seed_path": decision_seed_path or None,
                "decision_inbox_path": decision_inbox_path or None,
                "request_missing": pr_request_missing if pr_request_missing else None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
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
                "decision_needed": bool(decision_needed),
                "decision_seed_path": decision_seed_path or None,
                "decision_inbox_path": decision_inbox_path or None,
                "request_missing": pr_request_missing if pr_request_missing else None,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
    job_id_payload: dict[str, Any] = {"kind": normalized_kind, "policy_hash": policy_hash, "dry_run": dry_run}
    if normalized_kind in {"RELEASE_RC", "RELEASE_FINAL"} and not dry_run:
        manifest_path = workspace_root / ".cache" / "reports" / "release_manifest.v1.json"
        try:
            manifest = _load_json(manifest_path) if manifest_path.exists() else None
        except Exception:
            manifest = None
        if isinstance(manifest, dict):
            release_version = manifest.get("release_version")
            if isinstance(release_version, str) and release_version.strip():
                job_id_payload["release_version"] = release_version.strip()
            channel = manifest.get("channel")
            if isinstance(channel, str) and channel.strip():
                job_id_payload["channel"] = channel.strip()
    job_id = _hash_text(_canonical_json(job_id_payload))
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
        if normalized_kind == "PR_OPEN" and gate_error:
            decision_needed = True
    else:
        if normalized_kind == "PR_OPEN" and pr_request_missing and not local_only:
            return {
                "status": "IDLE",
                "error_code": "PR_OPEN_MISSING_INPUTS",
                "job_id": "",
                "job_kind": normalized_kind,
                "cooldown_hit": False,
                "jobs_index_path": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
                "policy_source": policy_source,
                "decision_needed": bool(decision_needed),
                "decision_seed_path": decision_seed_path or None,
                "decision_inbox_path": decision_inbox_path or None,
                "request_missing": pr_request_missing,
                "gate_state": {
                    "network_enabled": bool(gate_details.get("network_enabled", False)),
                    "live_enabled": bool(gate_details.get("live_enabled", False)),
                    "env_flag_set": bool(gate_details.get("env_flag_set", False)),
                    "env_key_present": bool(gate_details.get("env_key_present", False)),
                },
            }
        request_path = None
        request_rel = ""
        if normalized_kind == "PR_OPEN" and pr_request_payload and not local_only:
            request_path, request_rel = _write_pr_open_request(workspace_root, job_id, pr_request_payload)
        auth_cfg = policy.get("auth") if isinstance(policy.get("auth"), dict) else {}
        auth_mode = _clean_str(auth_cfg.get("mode") or "bearer") or "bearer"
        token_env = _clean_str(auth_cfg.get("token_env") or "GITHUB_TOKEN") or "GITHUB_TOKEN"
        command_fingerprint = _hash_text(_canonical_json({"kind": normalized_kind, "policy_hash": policy_hash}))
        pid, result_paths = _spawn_job_process(
            workspace_root,
            job_id,
            command_fingerprint=command_fingerprint,
            kind=normalized_kind,
            request_path=request_path,
            auth_mode=auth_mode,
            token_env=token_env,
        )
        if request_rel:
            result_paths.append(request_rel)
        if pid is None:
            status = "FAIL"
            error_code = "SPAWN_FAILED"
            return_status = "WARN"
        else:
            status = "RUNNING"
    job_workspace_root = workspace_root
    if normalized_kind == "SMOKE_FULL":
        job_workspace_root = _resolve_smoke_workspace_root()
    job = {
        "version": "v1",
        "job_id": job_id,
        "kind": normalized_kind,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "workspace_root": str(job_workspace_root),
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
    _ensure_job_trace_meta(job, workspace_root=workspace_root, policy_hash=policy_hash)
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
        "decision_needed": bool(decision_needed),
        "decision_seed_path": decision_seed_path or None,
        "decision_inbox_path": decision_inbox_path or None,
        "gate_state": {
            "network_enabled": bool(gate_details.get("network_enabled", False)),
            "live_enabled": bool(gate_details.get("live_enabled", False)),
            "env_flag_set": bool(gate_details.get("env_flag_set", False)),
            "env_key_present": bool(gate_details.get("env_key_present", False)),
        },
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
    retry_budget = int(policy.get("retry_count", 0) or 0)
    if retry_budget < 0:
        retry_budget = 0
    rc_pending_grace_seconds = min(15, _RC_PENDING_GRACE_SECONDS + retry_budget)
    rc_pending_note_prefix = "rc_pending_since:"
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
                if str(target.get("error_code") or "") == _RC_PENDING_ERROR_CODE:
                    target["error_code"] = ""
                notes_list = target.get("notes") if isinstance(target.get("notes"), list) else []
                cleaned_notes = [
                    note
                    for note in notes_list
                    if isinstance(note, str) and not note.startswith(rc_pending_note_prefix)
                ]
                if len(cleaned_notes) != len(notes_list):
                    target["notes"] = cleaned_notes
            else:
                rc_path = _job_output_paths(workspace_root, job_id)[2]
                rc = None
                rc_obj: dict[str, Any] | None = None
                if rc_path.exists():
                    try:
                        loaded = _load_json(rc_path)
                        rc_obj = loaded if isinstance(loaded, dict) else None
                        rc = int(rc_obj.get("rc")) if rc_obj is not None and isinstance(rc_obj.get("rc"), int) else None
                    except Exception:
                        rc = None
                if rc is None:
                    notes_list = target.get("notes") if isinstance(target.get("notes"), list) else []
                    was_pending = str(target.get("error_code") or "") == _RC_PENDING_ERROR_CODE
                    pending_since_value = ""
                    for note in notes_list:
                        if isinstance(note, str) and note.startswith(rc_pending_note_prefix):
                            pending_since_value = note[len(rc_pending_note_prefix) :]
                            break
                    pending_since = _parse_iso(pending_since_value)
                    pending_elapsed = (
                        now - pending_since if pending_since is not None else timedelta(seconds=0)
                    )
                    pending_window_active = (
                        not was_pending
                        or pending_since is None
                        or pending_elapsed <= timedelta(seconds=rc_pending_grace_seconds)
                    )
                    if pending_window_active:
                        target["status"] = "RUNNING"
                        target["error_code"] = _RC_PENDING_ERROR_CODE
                        pending_marker = f"{rc_pending_note_prefix}{_now_iso()}"
                        if was_pending and pending_since_value:
                            pending_marker = f"{rc_pending_note_prefix}{pending_since_value}"
                        cleaned_notes = [
                            note
                            for note in notes_list
                            if isinstance(note, str) and not note.startswith(rc_pending_note_prefix)
                        ]
                        cleaned_notes.append(pending_marker)
                        target["notes"] = cleaned_notes
                    else:
                        target["status"] = "FAIL"
                        target["error_code"] = "RC_MISSING"
                        cleaned_notes = [
                            note
                            for note in notes_list
                            if isinstance(note, str) and not note.startswith(rc_pending_note_prefix)
                        ]
                        if len(cleaned_notes) != len(notes_list):
                            target["notes"] = cleaned_notes
                elif rc == 0:
                    target["status"] = "PASS"
                    target["failure_class"] = "PASS"
                    if str(target.get("error_code") or "") == _RC_PENDING_ERROR_CODE:
                        target["error_code"] = ""
                    notes_list = target.get("notes") if isinstance(target.get("notes"), list) else []
                    cleaned_notes = [
                        note
                        for note in notes_list
                        if isinstance(note, str) and not note.startswith(rc_pending_note_prefix)
                    ]
                    if len(cleaned_notes) != len(notes_list):
                        target["notes"] = cleaned_notes
                else:
                    target["status"] = "FAIL"
                    target["error_code"] = "RC_NONZERO"
                    target["rc"] = rc
                    notes_list = target.get("notes") if isinstance(target.get("notes"), list) else []
                    cleaned_notes = [
                        note
                        for note in notes_list
                        if isinstance(note, str) and not note.startswith(rc_pending_note_prefix)
                    ]
                    if len(cleaned_notes) != len(notes_list):
                        target["notes"] = cleaned_notes
                if rc_obj is not None:
                    pr_meta = _extract_pr_metadata_from_rc(rc_obj)
                    for meta_key, meta_value in pr_meta.items():
                        target[meta_key] = meta_value
                    release_meta = _extract_release_metadata_from_rc(rc_obj)
                    for meta_key, meta_value in release_meta.items():
                        target[meta_key] = meta_value
                    if target.get("status") == "FAIL":
                        # Prefer the rc_obj error_code over the generic RC_NONZERO marker when present.
                        rc_error_code = rc_obj.get("error_code")
                        if (
                            isinstance(rc_error_code, str)
                            and rc_error_code
                            and str(target.get("error_code") or "") in {"", "RC_MISSING", "RC_NONZERO"}
                        ):
                            target["error_code"] = rc_error_code
                        has_error = bool(rc_obj.get("error_code")) or int(rc_obj.get("rc") or 0) != 0
                        http_status = rc_obj.get("http_status")
                        if isinstance(http_status, int) and http_status >= 400:
                            has_error = True
                        if has_error:
                            failure_fields = _extract_failure_fields_from_rc(rc_obj)
                            for key, value in failure_fields.items():
                                target[key] = value
                if target.get("status") == "FAIL":
                    stderr_path = _job_output_paths(workspace_root, job_id)[1]
                    try:
                        stderr_text = stderr_path.read_text(encoding="utf-8")
                    except Exception:
                        stderr_text = ""
                    if not target.get("failure_class") or target.get("failure_class") == "OTHER":
                        failure_class, signature_hash = classify_github_ops_failure(stderr_text)
                        target["failure_class"] = failure_class
                        target["signature_hash"] = signature_hash
                        if failure_class in {
                            "DEMO_ADVISOR_SUGGESTIONS_MISSING",
                            "DEMO_CATALOG_MISSING",
                            "DEMO_CATALOG_PARSE",
                            "DEMO_PREREQ_APPLY_FAIL",
                            "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING",
                            "DEMO_QUALITY_GATE_REPORT_MISSING",
                            "DEMO_SESSION_CONTEXT_HASH_MISMATCH",
                            "DEMO_SESSION_CONTEXT_MISSING",
                        }:
                            if target.get("error_code") in {None, "", "RC_NONZERO"}:
                                target["error_code"] = failure_class
    if str(target.get("status") or "") == "FAIL":
        if not target.get("failure_class") or target.get("failure_class") == "OTHER":
            stderr_path = _job_output_paths(workspace_root, job_id)[1]
            try:
                stderr_text = stderr_path.read_text(encoding="utf-8")
            except Exception:
                stderr_text = ""
            failure_class, signature_hash = classify_github_ops_failure(stderr_text)
            target["failure_class"] = failure_class
            target["signature_hash"] = signature_hash
            if failure_class in {
                "DEMO_ADVISOR_SUGGESTIONS_MISSING",
                "DEMO_CATALOG_MISSING",
                "DEMO_CATALOG_PARSE",
                "DEMO_PREREQ_APPLY_FAIL",
                "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING",
                "DEMO_QUALITY_GATE_REPORT_MISSING",
                "DEMO_SESSION_CONTEXT_HASH_MISMATCH",
                "DEMO_SESSION_CONTEXT_MISSING",
            }:
                if target.get("error_code") in {None, "", "RC_NONZERO"}:
                    target["error_code"] = failure_class
        stderr_path = _job_output_paths(workspace_root, job_id)[1]
        try:
            stderr_text = stderr_path.read_text(encoding="utf-8")
        except Exception:
            stderr_text = ""
        _maybe_override_advisor_missing(target=target, stderr_text=stderr_text)
    target["updated_at"] = _now_iso()
    target["last_poll_at"] = _now_iso()
    _ensure_job_trace_meta(target, workspace_root=workspace_root, policy_hash=policy_hash)
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
def poll_github_ops_jobs(*, workspace_root: Path, max_jobs: int = 1) -> dict[str, Any]:
    max_jobs = max(0, int(max_jobs))
    jobs_index, notes = _load_jobs_index(workspace_root)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    candidates = [
        j
        for j in jobs
        if isinstance(j, dict) and str(j.get("status") or "") in {"QUEUED", "RUNNING"}
    ]
    candidates.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")))
    polled: list[dict[str, Any]] = []
    for job in candidates[:max_jobs]:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            continue
        polled.append(poll_github_ops_job(workspace_root=workspace_root, job_id=job_id))
    status = "OK" if polled else "IDLE"
    jobs_index_path = str(Path(".cache") / "github_ops" / "jobs_index.v1.json")
    if polled:
        jobs_index_path = str(polled[-1].get("jobs_index_path") or jobs_index_path)
    return {
        "status": status,
        "polled_count": len(polled),
        "polled_jobs": polled,
        "jobs_index_path": jobs_index_path,
        "notes": notes,
    }
