from __future__ import annotations
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from .github_ops_support_v2 import (
    _allowed_actions,
    _canonical_json,
    _clean_str,
    _deep_merge,
    _default_jobs_index,
    _dump_json,
    _env_truthy,
    _git_ahead_behind,
    _git_available,
    _git_branch,
    _git_dir,
    _git_dirty_tree,
    _git_remote_url,
    _git_state,
    _hash_text,
    _infer_repo_from_git,
    _job_output_paths,
    _job_report_path,
    _job_store_dir,
    _job_time,
    _jobs_index_path,
    _load_jobs_index,
    _load_json,
    _load_network_live_summary,
    _load_policy,
    _normalize_kind,
    _normalize_pr_open_request,
    _normalize_str_list,
    _now_iso,
    _parse_github_remote,
    _parse_iso,
    _policy_defaults,
    _resolve_env_presence_from_dotenv,
    _resolve_env_value_from_dotenv,
    _rel_from_workspace,
    _repo_root,
    _save_jobs_index,
    _write_job_report,
)
from src.prj_github_ops.failure_classifier import classify_github_ops_failure, _signature_hash_from_stderr
from src.ops.trace_meta import build_run_id, build_trace_meta, date_bucket_from_iso
def _dotenv_env_presence(key_name: str, *, workspace_root: Path) -> bool:
    try:
        present, _source = _resolve_env_presence_from_dotenv(key_name, workspace_root=workspace_root)
        return bool(present)
    except Exception:
        return False
def _dotenv_env_value(key_name: str, *, workspace_root: Path) -> str:
    try:
        present, value = _resolve_env_value_from_dotenv(key_name, workspace_root=workspace_root)
        return str(value or "") if present and value else ""
    except Exception:
        return ""
def _gate_details(policy: dict[str, Any], *, workspace_root: Path) -> dict[str, Any]:
    live = policy.get("live_gate") if isinstance(policy.get("live_gate"), dict) else {}
    enabled = bool(live.get("enabled", False))
    env_flag = str(live.get("env_flag") or "")
    env_key = str(live.get("env_key") or "")
    require_key = bool(live.get("require_env_key_present", True))
    env_flag_value = os.getenv(env_flag, "") if env_flag else ""
    if not env_flag_value and env_flag:
        env_flag_value = _dotenv_env_value(env_flag, workspace_root=workspace_root)
    env_flag_set = _env_truthy(env_flag_value) if env_flag else True
    env_key_present = True
    if require_key and env_key:
        env_key_present = bool(os.getenv(env_key, "")) or _dotenv_env_presence(env_key, workspace_root=workspace_root)
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
def _write_pr_open_request(workspace_root: Path, job_id: str, request_payload: dict[str, Any]) -> tuple[Path, str]:
    path = _job_store_dir(workspace_root, job_id) / "request.v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(request_payload), encoding="utf-8")
    return path, _rel_from_workspace(path, workspace_root)
def _load_last_pr_open_request(workspace_root: Path, jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [j for j in jobs if isinstance(j, dict) and str(j.get("kind") or "") == "PR_OPEN"]
    if not candidates:
        return None
    candidates.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")), reverse=True)
    for job in candidates:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            continue
        req_path = _job_store_dir(workspace_root, job_id) / "request.v1.json"
        if not req_path.exists():
            continue
        try:
            obj = _load_json(req_path)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None
def _redact_message(message: str) -> tuple[str, str]:
    raw = str(message or "").strip()
    if not raw:
        return "", ""
    message_hash = _hash_text(raw)
    redacted = raw
    redacted = re.sub(r"(?i)(token|bearer)\\s+[-_a-z0-9\\.]+", r"\\1 [REDACTED]", redacted)
    redacted = re.sub(r"(?i)ghp_[a-z0-9]{10,}", "ghp_[REDACTED]", redacted)
    redacted = re.sub(r"(?i)github_pat_[a-z0-9_]{10,}", "github_pat_[REDACTED]", redacted)
    redacted = re.sub(r"[A-Za-z0-9_\\-]{20,}", "[REDACTED]", redacted)
    redacted = redacted[:200]
    return redacted, message_hash


class _SSLVerifyFailed(RuntimeError):
    def __init__(self, message: str, *, tried: list[str]):
        super().__init__(message)
        self.tried = tried


def _resolve_ssl_cafile(*, workspace_root: Path) -> str:
    candidates: list[str] = []
    for key in ("GITHUB_OPS_SSL_CAFILE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        raw = os.getenv(key, "") or _dotenv_env_value(key, workspace_root=workspace_root)
        if raw:
            candidates.append(str(raw).strip())
    for raw in candidates:
        if not raw:
            continue
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (_repo_root() / p).resolve()
        try:
            if p.exists() and p.is_file():
                return str(p)
        except Exception:
            continue
    return ""


def _ssl_context_candidates(*, workspace_root: Path) -> list[tuple[str, Any]]:
    import ssl
    contexts: list[tuple[str, Any]] = []
    env_cafile = _resolve_ssl_cafile(workspace_root=workspace_root)
    if env_cafile:
        contexts.append((f"cafile_env:{Path(env_cafile).name}", ssl.create_default_context(cafile=env_cafile)))
    contexts.append(("default", ssl.create_default_context()))
    for cafile in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        p = Path(cafile)
        try:
            if p.exists() and p.is_file():
                contexts.append((f"cafile:{cafile}", ssl.create_default_context(cafile=str(p))))
        except Exception:
            continue
    try:
        import certifi
        cafile = str(certifi.where() or "")
        if cafile:
            p = Path(cafile)
            if p.exists() and p.is_file():
                contexts.append(("certifi", ssl.create_default_context(cafile=str(p))))
    except Exception:
        pass
    out: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for name, ctx in contexts:
        if name in seen:
            continue
        seen.add(name)
        out.append((name, ctx))
    return out


def _is_ssl_cert_verify_error(exc: BaseException) -> bool:
    import ssl
    import urllib.error
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return True
        if reason and "CERTIFICATE_VERIFY_FAILED" in str(reason):
            return True
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


def _urlopen_read_with_ssl_fallback(
    req: Any,
    *,
    workspace_root: Path,
    timeout_seconds: int,
) -> tuple[int, bytes, Any, str, list[str]]:
    import urllib.error
    import urllib.request
    tried: list[str] = []
    last_exc: BaseException | None = None
    for name, ssl_ctx in _ssl_context_candidates(workspace_root=workspace_root):
        tried.append(name)
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds, context=ssl_ctx) as resp:
                return int(resp.getcode() or 0), resp.read(), resp.headers, name, tried
        except urllib.error.HTTPError as exc:
            try:
                setattr(exc, "_ssl_context_selected", name)
                setattr(exc, "_ssl_context_tried", list(tried))
            except Exception:
                pass
            raise
        except Exception as exc:
            if _is_ssl_cert_verify_error(exc):
                last_exc = exc
                continue
            raise
    raise _SSLVerifyFailed("SSL_CERT_VERIFY_FAILED", tried=tried) from last_exc
def _job_workspace_root_from_record(job: dict[str, Any], repo_root: Path) -> Path | None:
    raw = job.get("workspace_root")
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (repo_root / raw).resolve()
    else:
        path = path.resolve()
    return path
def _advisor_expected_path(job_workspace_root: Path) -> Path:
    return job_workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
def _advisor_job_artifact_path(job_workspace_root: Path, job_id: str) -> Path:
    return (
        job_workspace_root
        / ".cache"
        / "reports"
        / "jobs"
        / f"smoke_full_{job_id}"
        / "advisor_suggestions.v1.json"
    )
def _json_valid(path: Path) -> bool:
    try:
        obj = _load_json(path)
    except Exception:
        return False
    return isinstance(obj, dict)
def _maybe_override_advisor_missing(*, target: dict[str, Any], stderr_text: str) -> None:
    if str(target.get("kind") or "") != "SMOKE_FULL":
        return
    if str(target.get("failure_class") or "") != "DEMO_ADVISOR_SUGGESTIONS_MISSING":
        return
    job_id = str(target.get("job_id") or "")
    if not job_id:
        return
    repo_root = _repo_root()
    job_ws_root = _job_workspace_root_from_record(target, repo_root)
    if job_ws_root is None:
        return
    expected_path = _advisor_expected_path(job_ws_root)
    artifact_path = _advisor_job_artifact_path(job_ws_root, job_id)
    expected_ok = expected_path.exists() and _json_valid(expected_path)
    artifact_ok = artifact_path.exists() and _json_valid(artifact_path)
    if not (expected_ok or artifact_ok):
        return
    target["failure_class"] = "OTHER"
    target["signature_hash"] = _signature_hash_from_stderr(failure_class="OTHER", stderr_text=stderr_text)
    if target.get("error_code") == "DEMO_ADVISOR_SUGGESTIONS_MISSING":
        target["error_code"] = "SMOKE_FULL_FAIL"
    notes = target.get("notes") if isinstance(target.get("notes"), list) else []
    notes.append("advisor_pin_override"); target["notes"] = sorted({str(n) for n in notes if isinstance(n, str) and n.strip()})
def _resolve_smoke_workspace_root() -> Path:
    repo_root = _repo_root()
    raw = str(os.environ.get("SMOKE_WORKSPACE_ROOT") or "").strip()
    if raw:
        ws = Path(raw)
        ws = (repo_root / ws).resolve() if not ws.is_absolute() else ws.resolve()
        try:
            ws.relative_to(repo_root.resolve())
        except Exception:
            return repo_root / ".cache" / "ws_integration_demo"
        if ws.exists() and ws.is_dir():
            return ws
    return repo_root / ".cache" / "ws_integration_demo"
def _map_failure_class(http_status: int | None, error_code: str, message: str) -> str:
    status = int(http_status or 0)
    if status == 401:
        return "AUTH"
    if status == 403:
        return "PERMISSION"
    if status == 404:
        return "NOT_FOUND"
    if status == 409:
        return "CONFLICT"
    if status == 422:
        return "VALIDATION"
    if status == 429:
        return "RATE_LIMIT"
    if status >= 500:
        return "NETWORK"
    if "rate limit" in message.lower():
        return "RATE_LIMIT"
    if error_code in {"REQUEST_FAILED", "HTTP_ERROR", "HTTP_STATUS"}:
        return "NETWORK"
    return "OTHER"
def _extract_failure_fields_from_rc(rc_obj: dict[str, Any]) -> dict[str, Any]:
    failure: dict[str, Any] = {}
    http_status = rc_obj.get("http_status")
    if isinstance(http_status, int) and http_status > 0:
        failure["http_status"] = http_status
    gh_error_code = rc_obj.get("gh_error_code")
    if isinstance(gh_error_code, str) and gh_error_code:
        failure["gh_error_code"] = gh_error_code
    gh_request_id = rc_obj.get("gh_request_id")
    if isinstance(gh_request_id, str) and gh_request_id:
        failure["gh_request_id"] = gh_request_id
    endpoint = rc_obj.get("endpoint")
    if isinstance(endpoint, str) and endpoint:
        failure["endpoint"] = endpoint
    retry_after = rc_obj.get("retry_after_seconds")
    if isinstance(retry_after, int) and retry_after >= 0:
        failure["retry_after_seconds"] = retry_after
    message_redacted = rc_obj.get("message_redacted")
    message_hash = rc_obj.get("message_hash")
    if not isinstance(message_redacted, str) or not message_redacted:
        raw_message = rc_obj.get("message") or rc_obj.get("error_message") or ""
        message_redacted, message_hash = _redact_message(str(raw_message))
    if isinstance(message_redacted, str) and message_redacted:
        failure["message_redacted"] = message_redacted
    if isinstance(message_hash, str) and message_hash:
        failure["message_hash"] = message_hash
    failure_class = rc_obj.get("failure_class")
    if not isinstance(failure_class, str) or not failure_class:
        failure_class = _map_failure_class(failure.get("http_status"), str(rc_obj.get("error_code") or ""), message_redacted)
    failure["failure_class"] = failure_class
    return failure
def _extract_pr_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    pr_url = payload.get("pr_url")
    if isinstance(pr_url, str) and pr_url:
        meta["pr_url"] = pr_url
    html_url = payload.get("html_url") or payload.get("pr_html_url")
    if isinstance(html_url, str) and html_url:
        if "pr_url" not in meta:
            meta["pr_url"] = html_url
        meta["pr_html_url"] = html_url
    pr_number = payload.get("pr_number")
    if not isinstance(pr_number, int):
        pr_number = payload.get("number") if isinstance(payload.get("number"), int) else None
    if isinstance(pr_number, int) and pr_number > 0:
        meta["pr_number"] = pr_number
    pr_state = payload.get("pr_state")
    if not isinstance(pr_state, str):
        pr_state = payload.get("state") if isinstance(payload.get("state"), str) else None
    if isinstance(pr_state, str) and pr_state:
        meta["pr_state"] = pr_state
    base_ref = None
    base = payload.get("base")
    if isinstance(base, dict):
        base_ref = base.get("ref")
    if isinstance(base_ref, str) and base_ref:
        meta["pr_base"] = base_ref
    head_ref = None
    head = payload.get("head")
    if isinstance(head, dict):
        head_ref = head.get("ref")
    if isinstance(head_ref, str) and head_ref:
        meta["pr_head"] = head_ref
    return meta
def _extract_pr_metadata_from_rc(rc_obj: dict[str, Any]) -> dict[str, Any]:
    meta = _extract_pr_metadata(rc_obj)
    for key in ("payload", "response", "data", "result"):
        nested = rc_obj.get(key)
        if isinstance(nested, dict):
            for meta_key, meta_value in _extract_pr_metadata(nested).items():
                if meta_key not in meta:
                    meta[meta_key] = meta_value
    return meta
def _extract_release_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    release_url = payload.get("release_url")
    if not isinstance(release_url, str) or not release_url:
        release_url = payload.get("html_url") if isinstance(payload.get("html_url"), str) else ""
    if isinstance(release_url, str) and release_url:
        meta["release_url"] = release_url
    release_id = payload.get("release_id")
    if not isinstance(release_id, int):
        release_id = payload.get("id") if isinstance(payload.get("id"), int) else None
    if isinstance(release_id, int) and release_id > 0:
        meta["release_id"] = release_id
    release_tag = payload.get("release_tag")
    if not isinstance(release_tag, str) or not release_tag:
        release_tag = payload.get("tag_name") if isinstance(payload.get("tag_name"), str) else ""
    if isinstance(release_tag, str) and release_tag:
        meta["release_tag"] = release_tag
    release_name = payload.get("release_name")
    if not isinstance(release_name, str) or not release_name:
        release_name = payload.get("name") if isinstance(payload.get("name"), str) else ""
    if isinstance(release_name, str) and release_name:
        meta["release_name"] = release_name
    return meta
def _extract_release_metadata_from_rc(rc_obj: dict[str, Any]) -> dict[str, Any]:
    meta = _extract_release_metadata(rc_obj)
    for key in ("payload", "response", "data", "result"):
        nested = rc_obj.get(key)
        if isinstance(nested, dict):
            for meta_key, meta_value in _extract_release_metadata(nested).items():
                if meta_key not in meta:
                    meta[meta_key] = meta_value
    return meta
def _github_ops_runtime():
    import src.prj_github_ops.github_ops_runtime as _mod

    return _mod


def _run_pr_open_job(*args, **kwargs):
    return _github_ops_runtime()._run_pr_open_job(*args, **kwargs)


def _run_pr_merge_job(*args, **kwargs):
    return _github_ops_runtime()._run_pr_merge_job(*args, **kwargs)


def _run_release_create_job(*args, **kwargs):
    return _github_ops_runtime()._run_release_create_job(*args, **kwargs)


def _live_gate(*args, **kwargs):
    return _github_ops_runtime()._live_gate(*args, **kwargs)


def _job_signature(*args, **kwargs):
    return _github_ops_runtime()._job_signature(*args, **kwargs)


def _job_report_rel(*args, **kwargs):
    return _github_ops_runtime()._job_report_rel(*args, **kwargs)


def _ensure_job_trace_meta(*args, **kwargs):
    return _github_ops_runtime()._ensure_job_trace_meta(*args, **kwargs)


def _gate_error(*args, **kwargs):
    return _github_ops_runtime()._gate_error(*args, **kwargs)


def _cooldown_active(*args, **kwargs):
    return _github_ops_runtime()._cooldown_active(*args, **kwargs)


def _spawn_job_process(*args, **kwargs):
    return _github_ops_runtime()._spawn_job_process(*args, **kwargs)


def _apply_job_retention(*args, **kwargs):
    return _github_ops_runtime()._apply_job_retention(*args, **kwargs)


def _failure_summary(*args, **kwargs):
    return _github_ops_runtime()._failure_summary(*args, **kwargs)


def build_github_ops_report(*args, **kwargs):
    return _github_ops_runtime().build_github_ops_report(*args, **kwargs)


def run_github_ops_check(*args, **kwargs):
    return _github_ops_runtime().run_github_ops_check(*args, **kwargs)


def start_github_ops_job(*args, **kwargs):
    return _github_ops_runtime().start_github_ops_job(*args, **kwargs)


def poll_github_ops_job(*args, **kwargs):
    return _github_ops_runtime().poll_github_ops_job(*args, **kwargs)


def poll_github_ops_jobs(*args, **kwargs):
    return _github_ops_runtime().poll_github_ops_jobs(*args, **kwargs)
