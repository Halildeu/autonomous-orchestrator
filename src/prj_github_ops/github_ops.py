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
    _rel_from_workspace,
    _repo_root,
    _save_jobs_index,
    _write_job_report,
)
from src.prj_github_ops.failure_classifier import classify_github_ops_failure, _signature_hash_from_stderr
from src.ops.trace_meta import build_run_id, build_trace_meta, date_bucket_from_iso
def _dotenv_env_presence(key_name: str, *, workspace_root: Path) -> bool:
    try:
        from src.prj_kernel_api.dotenv_loader import resolve_env_presence
        present, _source = resolve_env_presence(key_name, str(workspace_root), env_mode="dotenv")
        return bool(present)
    except Exception:
        return False
def _dotenv_env_value(key_name: str, *, workspace_root: Path) -> str:
    try:
        from src.prj_kernel_api.dotenv_loader import resolve_env_value
        present, value = resolve_env_value(key_name, str(workspace_root), env_mode="dotenv")
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
def _run_pr_open_job(
    rc_path: str,
    request_path: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    import json as _json
    import urllib.error as _urllib_error
    import urllib.request as _urllib_request
    from pathlib import Path as _Path
    def _write(payload: dict[str, Any]) -> None:
        _Path(rc_path).parent.mkdir(parents=True, exist_ok=True)
        _Path(rc_path).write_text(_dump_json(payload), encoding="utf-8")
    payload: dict[str, Any] = {"rc": 1, "fingerprint": fingerprint}
    try:
        req_obj = _json.loads(_Path(request_path).read_text(encoding="utf-8"))
    except Exception:
        payload["error_code"] = "REQUEST_LOAD_FAIL"
        _write(payload)
        return
    owner = _clean_str(req_obj.get("repo_owner"))
    repo = _clean_str(req_obj.get("repo_name"))
    base_branch = _clean_str(req_obj.get("base_branch"))
    head_branch = _clean_str(req_obj.get("head_branch"))
    title = _clean_str(req_obj.get("title"))
    body = _clean_str(req_obj.get("body"))
    draft = req_obj.get("draft")
    if not isinstance(draft, bool):
        draft = True
    missing = [key for key, value in [
        ("repo_owner", owner),
        ("repo_name", repo),
        ("base_branch", base_branch),
        ("head_branch", head_branch),
        ("title", title),
    ] if not value]
    if missing:
        payload["error_code"] = "REQUEST_INVALID"
        payload["missing"] = missing
        _write(payload)
        return
    token = os.getenv(token_env, "") or _dotenv_env_value(token_env, workspace_root=_Path(workspace_root))
    if not token:
        payload["error_code"] = "AUTH_MISSING"
        _write(payload)
        return
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    request_body: dict[str, Any] = {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "draft": bool(draft),
    }
    if body:
        request_body["body"] = body
    auth_value = token
    mode = _clean_str(auth_mode).lower()
    if mode == "token":
        auth_header = f"token {auth_value}"
    else:
        auth_header = f"Bearer {auth_value}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "Authorization": auth_header,
        "User-Agent": "autonomous-orchestrator",
    }
    data = _json.dumps(request_body).encode("utf-8")
    req = _urllib_request.Request(api_url, data=data, headers=headers, method="POST")
    try:
        status_code, body_bytes, headers, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
            req,
            workspace_root=_Path(workspace_root),
            timeout_seconds=30,
        )
        payload["ssl_context_selected"] = ssl_selected
        payload["ssl_context_tried"] = ssl_tried
    except _SSLVerifyFailed as exc:
        redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
        payload.update(
            {
                "error_code": "SSL_CERT_VERIFY_FAILED",
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "ssl_context_tried": getattr(exc, "tried", None),
            }
        )
        payload["failure_class"] = "NETWORK"
        _write(payload)
        return
    except _urllib_error.HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0)
        headers = getattr(exc, "headers", {}) or {}
        ssl_selected = _clean_str(getattr(exc, "_ssl_context_selected", ""))
        ssl_tried = getattr(exc, "_ssl_context_tried", None)
        try:
            body_bytes = exc.read()
        except Exception:
            body_bytes = b""
        message = ""
        gh_error_code = ""
        try:
            err_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            err_obj = {}
        if isinstance(err_obj, dict):
            message = _clean_str(err_obj.get("message"))
            errors = err_obj.get("errors") if isinstance(err_obj.get("errors"), list) else []
            if errors:
                first = errors[0] if isinstance(errors[0], dict) else {}
                gh_error_code = _clean_str(first.get("code"))
                if not message:
                    message = _clean_str(first.get("message"))
        if not message:
            message = _clean_str(getattr(exc, "reason", "")) or "HTTP_ERROR"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_ERROR",
                "http_status": int(status_code or 0),
                "gh_error_code": gh_error_code or None,
                "gh_request_id": _clean_str(headers.get("X-GitHub-Request-Id") if hasattr(headers, "get") else ""),
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "retry_after_seconds": int(headers.get("Retry-After") or 0) if hasattr(headers, "get") and str(headers.get("Retry-After") or "").isdigit() else None,
                "ssl_context_selected": ssl_selected or None,
                "ssl_context_tried": ssl_tried if isinstance(ssl_tried, list) else None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_ERROR", redacted)
        _write(payload)
        return
    except Exception as exc:
        message = _clean_str(str(exc)) or "REQUEST_FAILED"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "REQUEST_FAILED",
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
        _write(payload)
        return
    payload["http_status"] = int(status_code or 0)
    if int(status_code or 0) not in {200, 201}:
        message = "HTTP_STATUS"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_STATUS",
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_STATUS", redacted)
        _write(payload)
        return
    try:
        response_obj = _json.loads(body_bytes.decode("utf-8"))
    except Exception:
        response_obj = {}
    payload["rc"] = 0
    payload.update(_extract_pr_metadata(response_obj))
    _write(payload)


def _run_pr_merge_job(
    rc_path: str,
    request_path: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    import json as _json
    import urllib.error as _urllib_error
    import urllib.request as _urllib_request
    from pathlib import Path as _Path

    def _write(payload: dict[str, Any]) -> None:
        _Path(rc_path).parent.mkdir(parents=True, exist_ok=True)
        _Path(rc_path).write_text(_dump_json(payload), encoding="utf-8")

    payload: dict[str, Any] = {"rc": 1, "fingerprint": fingerprint, "kind": "MERGE"}
    ws = _Path(workspace_root)

    req_obj: dict[str, Any] = {}
    if request_path:
        try:
            p = _Path(request_path)
            if p.exists():
                req_obj = _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            req_obj = {}

    pr_number = req_obj.get("pr_number") if isinstance(req_obj.get("pr_number"), int) else None
    merge_method_override = _clean_str(req_obj.get("merge_method"))
    expected_head_sha = _clean_str(req_obj.get("expected_head_sha") or req_obj.get("head_sha"))

    owner, repo = _infer_repo_from_git(_repo_root())
    if not owner or not repo:
        payload["error_code"] = "REPO_INFER_FAIL"
        _write(payload)
        return

    token = os.getenv(token_env, "") or _dotenv_env_value(token_env, workspace_root=ws)
    if not token:
        payload["error_code"] = "AUTH_MISSING"
        _write(payload)
        return

    mode = _clean_str(auth_mode).lower()
    if mode == "token":
        auth_header = f"token {token}"
    else:
        auth_header = f"Bearer {token}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "Authorization": auth_header,
        "User-Agent": "autonomous-orchestrator",
    }

    def _http_json(method: str, url: str, body: dict[str, Any] | None = None) -> tuple[int, bytes, Any]:
        data = _json.dumps(body).encode("utf-8") if isinstance(body, dict) else None
        req = _urllib_request.Request(url, data=data, headers=headers, method=str(method).upper())
        status_code, body_bytes, resp_headers, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
            req,
            workspace_root=ws,
            timeout_seconds=30,
        )
        payload.setdefault("ssl_context_selected", ssl_selected)
        payload.setdefault("ssl_context_tried", ssl_tried)
        return status_code, body_bytes, resp_headers

    def _write_http_error(exc: _urllib_error.HTTPError, *, endpoint: str) -> None:
        status_code = int(getattr(exc, "code", 0) or 0)
        headers2 = getattr(exc, "headers", {}) or {}
        ssl_selected = _clean_str(getattr(exc, "_ssl_context_selected", ""))
        ssl_tried = getattr(exc, "_ssl_context_tried", None)
        try:
            body_bytes = exc.read()
        except Exception:
            body_bytes = b""
        message = ""
        gh_error_code = ""
        try:
            err_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            err_obj = {}
        if isinstance(err_obj, dict):
            message = _clean_str(err_obj.get("message"))
            errors = err_obj.get("errors") if isinstance(err_obj.get("errors"), list) else []
            if errors:
                first = errors[0] if isinstance(errors[0], dict) else {}
                gh_error_code = _clean_str(first.get("code"))
                if not message:
                    message = _clean_str(first.get("message"))
        if not message:
            message = _clean_str(getattr(exc, "reason", "")) or "HTTP_ERROR"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_ERROR",
                "http_status": int(status_code or 0),
                "gh_error_code": gh_error_code or None,
                "gh_request_id": _clean_str(headers2.get("X-GitHub-Request-Id") if hasattr(headers2, "get") else ""),
                "endpoint": endpoint,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "retry_after_seconds": int(headers2.get("Retry-After") or 0)
                if hasattr(headers2, "get") and str(headers2.get("Retry-After") or "").isdigit()
                else None,
                "ssl_context_selected": ssl_selected or None,
                "ssl_context_tried": ssl_tried if isinstance(ssl_tried, list) else None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_ERROR", redacted)
        _write(payload)

    # Decide merge method deterministically from repo settings
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        repo_status, repo_body, _repo_headers = _http_json("GET", repo_url)
    except _SSLVerifyFailed as exc:
        redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
        payload.update(
            {
                "error_code": "SSL_CERT_VERIFY_FAILED",
                "endpoint": repo_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "ssl_context_tried": getattr(exc, "tried", None),
            }
        )
        payload["failure_class"] = "NETWORK"
        _write(payload)
        return
    except _urllib_error.HTTPError as exc:
        _write_http_error(exc, endpoint=repo_url)
        return
    except Exception as exc:
        message = _clean_str(str(exc)) or "REQUEST_FAILED"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "REQUEST_FAILED",
                "endpoint": repo_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
        _write(payload)
        return
    if repo_status != 200:
        message = "HTTP_STATUS"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_STATUS",
                "http_status": int(repo_status or 0),
                "endpoint": repo_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(repo_status or 0), "HTTP_STATUS", redacted)
        _write(payload)
        return
    try:
        repo_obj = _json.loads(repo_body.decode("utf-8")) if repo_body else {}
    except Exception:
        repo_obj = {}

    allowed_methods: list[str] = []
    if isinstance(repo_obj, dict):
        if bool(repo_obj.get("allow_merge_commit", False)):
            allowed_methods.append("merge")
        if bool(repo_obj.get("allow_squash_merge", False)):
            allowed_methods.append("squash")
        if bool(repo_obj.get("allow_rebase_merge", False)):
            allowed_methods.append("rebase")
    allowed_methods = sorted(set(allowed_methods))
    if not allowed_methods:
        payload["error_code"] = "MERGE_METHODS_UNAVAILABLE"
        _write(payload)
        return

    merge_method = ""
    if merge_method_override:
        if merge_method_override not in {"merge", "squash", "rebase"}:
            payload["error_code"] = "MERGE_METHOD_INVALID"
            payload["merge_method"] = merge_method_override
            _write(payload)
            return
        if merge_method_override not in allowed_methods:
            payload["error_code"] = "MERGE_METHOD_NOT_ALLOWED"
            payload["merge_method"] = merge_method_override
            payload["allowed_merge_methods"] = allowed_methods
            _write(payload)
            return
        merge_method = merge_method_override
    else:
        for candidate in ["merge", "squash", "rebase"]:
            if candidate in allowed_methods:
                merge_method = candidate
                break
    if not merge_method:
        payload["error_code"] = "MERGE_METHOD_SELECT_FAIL"
        payload["allowed_merge_methods"] = allowed_methods
        _write(payload)
        return

    # Determine PR number
    try:
        jobs_index, _notes = _load_jobs_index(ws)
    except Exception:
        jobs_index = {}
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    if pr_number is None:
        candidates = [j for j in jobs if isinstance(j, dict) and str(j.get("kind") or "") == "PR_OPEN"]
        candidates.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")), reverse=True)
        for j in candidates:
            pn = j.get("pr_number")
            if isinstance(pn, int) and pn > 0:
                pr_number = pn
                break
    if pr_number is None:
        last_request = _load_last_pr_open_request(ws, jobs)
        if isinstance(last_request, dict):
            head_branch = _clean_str(last_request.get("head_branch"))
            base_branch = _clean_str(last_request.get("base_branch"))
            if head_branch:
                list_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&head={owner}:{head_branch}"
                try:
                    status_code, body_bytes, _headers2 = _http_json("GET", list_url)
                except _SSLVerifyFailed as exc:
                    redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
                    payload.update(
                        {
                            "error_code": "SSL_CERT_VERIFY_FAILED",
                            "endpoint": list_url,
                            "message_redacted": redacted or None,
                            "message_hash": message_hash or None,
                            "ssl_context_tried": getattr(exc, "tried", None),
                        }
                    )
                    payload["failure_class"] = "NETWORK"
                    _write(payload)
                    return
                except _urllib_error.HTTPError as exc:
                    _write_http_error(exc, endpoint=list_url)
                    return
                except Exception as exc:
                    message = _clean_str(str(exc)) or "REQUEST_FAILED"
                    redacted, message_hash = _redact_message(message)
                    payload.update(
                        {
                            "error_code": "REQUEST_FAILED",
                            "endpoint": list_url,
                            "message_redacted": redacted or None,
                            "message_hash": message_hash or None,
                        }
                    )
                    payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
                    _write(payload)
                    return
                if status_code == 200:
                    try:
                        arr = _json.loads(body_bytes.decode("utf-8")) if body_bytes else []
                    except Exception:
                        arr = []
                    if isinstance(arr, list):
                        # best-effort: pick unique PR, or filter by base branch
                        prs = [p for p in arr if isinstance(p, dict) and isinstance(p.get("number"), int)]
                        if base_branch:
                            prs_base = [
                                p
                                for p in prs
                                if isinstance(p.get("base"), dict) and _clean_str(p.get("base", {}).get("ref")) == base_branch
                            ]
                            if prs_base:
                                prs = prs_base
                        prs.sort(key=lambda p: int(p.get("number") or 0))
                        if len(prs) == 1:
                            pr_number = int(prs[0].get("number") or 0) or None

    if pr_number is None:
        payload["error_code"] = "PR_NUMBER_MISSING"
        _write(payload)
        return

    payload["pr_number"] = int(pr_number)

    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    try:
        status_code, body_bytes, _headers2 = _http_json("GET", pr_url)
    except _SSLVerifyFailed as exc:
        redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
        payload.update(
            {
                "error_code": "SSL_CERT_VERIFY_FAILED",
                "endpoint": pr_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "ssl_context_tried": getattr(exc, "tried", None),
            }
        )
        payload["failure_class"] = "NETWORK"
        _write(payload)
        return
    except _urllib_error.HTTPError as exc:
        _write_http_error(exc, endpoint=pr_url)
        return
    except Exception as exc:
        message = _clean_str(str(exc)) or "REQUEST_FAILED"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "REQUEST_FAILED",
                "endpoint": pr_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
        _write(payload)
        return
    if status_code != 200:
        message = "HTTP_STATUS"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_STATUS",
                "http_status": int(status_code or 0),
                "endpoint": pr_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_STATUS", redacted)
        _write(payload)
        return
    try:
        pr_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        pr_obj = {}

    if isinstance(pr_obj, dict):
        payload.update(_extract_pr_metadata(pr_obj))
    state = _clean_str(pr_obj.get("state") if isinstance(pr_obj, dict) else "")
    merged_at = pr_obj.get("merged_at") if isinstance(pr_obj, dict) else None
    if state == "closed" and isinstance(merged_at, str) and merged_at:
        payload["rc"] = 0
        payload["noop"] = True
        _write(payload)
        return
    if state == "closed":
        payload["error_code"] = "PR_CLOSED"
        _write(payload)
        return
    if bool(pr_obj.get("draft", False)) is True:
        payload["error_code"] = "PR_DRAFT"
        _write(payload)
        return

    head_sha = ""
    if isinstance(pr_obj.get("head"), dict):
        head_sha = _clean_str(pr_obj.get("head", {}).get("sha"))
    if expected_head_sha and head_sha and expected_head_sha != head_sha:
        payload["error_code"] = "HEAD_SHA_MISMATCH"
        payload["expected_head_sha"] = expected_head_sha
        payload["head_sha"] = head_sha
        _write(payload)
        return

    merge_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge"
    merge_body: dict[str, Any] = {"merge_method": merge_method}
    if expected_head_sha:
        merge_body["sha"] = expected_head_sha
    try:
        status_code, body_bytes, _headers2 = _http_json("PUT", merge_url, merge_body)
    except _SSLVerifyFailed as exc:
        redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
        payload.update(
            {
                "error_code": "SSL_CERT_VERIFY_FAILED",
                "endpoint": merge_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "ssl_context_tried": getattr(exc, "tried", None),
            }
        )
        payload["failure_class"] = "NETWORK"
        _write(payload)
        return
    except _urllib_error.HTTPError as exc:
        _write_http_error(exc, endpoint=merge_url)
        return
    except Exception as exc:
        message = _clean_str(str(exc)) or "REQUEST_FAILED"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "REQUEST_FAILED",
                "endpoint": merge_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
        _write(payload)
        return
    payload["http_status"] = int(status_code or 0)
    if status_code != 200:
        message = "HTTP_STATUS"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_STATUS",
                "endpoint": merge_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_STATUS", redacted)
        _write(payload)
        return
    try:
        merge_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        merge_obj = {}
    payload["rc"] = 0
    payload["merge_method"] = merge_method
    if isinstance(merge_obj, dict):
        sha = merge_obj.get("sha")
        if isinstance(sha, str) and sha:
            payload["merge_commit_sha"] = sha
        merged = merge_obj.get("merged")
        if isinstance(merged, bool):
            payload["merged"] = merged
        message = merge_obj.get("message")
        if isinstance(message, str) and message:
            redacted, message_hash = _redact_message(message)
            payload["merge_message_redacted"] = redacted or None
            payload["merge_message_hash"] = message_hash or None
    _write(payload)
def _run_release_create_job(
    rc_path: str,
    kind: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    import json as _json
    import subprocess as _subprocess
    import urllib.error as _urllib_error
    import urllib.request as _urllib_request
    from pathlib import Path as _Path
    def _write(payload: dict[str, Any]) -> None:
        _Path(rc_path).parent.mkdir(parents=True, exist_ok=True)
        _Path(rc_path).write_text(_dump_json(payload), encoding="utf-8")
    payload: dict[str, Any] = {"rc": 1, "fingerprint": fingerprint, "kind": str(kind or "")}
    ws = _Path(workspace_root)
    manifest_path = ws / ".cache" / "reports" / "release_manifest.v1.json"
    notes_path = ws / ".cache" / "reports" / "release_notes.v1.md"
    if not manifest_path.exists():
        payload["error_code"] = "RELEASE_MANIFEST_MISSING"
        _write(payload)
        return
    try:
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        payload["error_code"] = "RELEASE_MANIFEST_INVALID_JSON"
        _write(payload)
        return
    release_version = str(manifest.get("release_version") or "") if isinstance(manifest, dict) else ""
    if not release_version:
        payload["error_code"] = "RELEASE_VERSION_MISSING"
        _write(payload)
        return
    tag_name = release_version if release_version.startswith("v") else f"v{release_version}"
    owner, repo = _infer_repo_from_git(_repo_root())
    if not owner or not repo:
        payload["error_code"] = "REPO_INFER_FAIL"
        _write(payload)
        return
    prerelease = bool(str(kind or "") == "RELEASE_RC")
    name = tag_name if not prerelease else f"{tag_name} (rc)"
    body = ""
    try:
        if notes_path.exists():
            body = notes_path.read_text(encoding="utf-8")
    except Exception:
        body = ""
    body = body[:200000]
    commitish = ""
    try:
        proc = _subprocess.run(
            ["git", "-C", str(_repo_root()), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            commitish = proc.stdout.strip()
    except Exception:
        commitish = ""
    token = os.getenv(token_env, "") or _dotenv_env_value(token_env, workspace_root=ws)
    if not token:
        payload["error_code"] = "AUTH_MISSING"
        _write(payload)
        return
    mode = _clean_str(auth_mode).lower()
    if mode == "token":
        auth_header = f"token {token}"
    else:
        auth_header = f"Bearer {token}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "Authorization": auth_header,
        "User-Agent": "autonomous-orchestrator",
    }
    # idempotency: if release for this tag already exists, NOOP -> PASS
    get_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag_name}"
    get_req = _urllib_request.Request(get_url, headers=headers, method="GET")
    try:
        status_code, body_bytes, _headers3, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
            get_req,
            workspace_root=ws,
            timeout_seconds=30,
        )
        payload.setdefault("ssl_context_selected", ssl_selected)
        payload.setdefault("ssl_context_tried", ssl_tried)
        if int(status_code or 0) == 200:
            try:
                response_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                response_obj = {}
            payload["rc"] = 0
            payload["noop"] = True
            payload.update(_extract_release_metadata(response_obj))
            _write(payload)
            return
    except _SSLVerifyFailed as exc:
        redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
        payload.update(
            {
                "error_code": "SSL_CERT_VERIFY_FAILED",
                "endpoint": get_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "ssl_context_tried": getattr(exc, "tried", None),
            }
        )
        payload["failure_class"] = "NETWORK"
        _write(payload)
        return
    except _urllib_error.HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0)
        ssl_selected = _clean_str(getattr(exc, "_ssl_context_selected", ""))
        ssl_tried = getattr(exc, "_ssl_context_tried", None)
        if ssl_selected:
            payload.setdefault("ssl_context_selected", ssl_selected)
        if isinstance(ssl_tried, list):
            payload.setdefault("ssl_context_tried", ssl_tried)
        if status_code != 404:
            headers2 = getattr(exc, "headers", {}) or {}
            try:
                body_bytes = exc.read()
            except Exception:
                body_bytes = b""
            message = ""
            gh_error_code = ""
            try:
                err_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                err_obj = {}
            if isinstance(err_obj, dict):
                message = _clean_str(err_obj.get("message"))
                errors = err_obj.get("errors") if isinstance(err_obj.get("errors"), list) else []
                if errors:
                    first = errors[0] if isinstance(errors[0], dict) else {}
                    gh_error_code = _clean_str(first.get("code"))
                    if not message:
                        message = _clean_str(first.get("message"))
            if not message:
                message = _clean_str(getattr(exc, "reason", "")) or "HTTP_ERROR"
            redacted, message_hash = _redact_message(message)
            payload.update(
                {
                    "error_code": "HTTP_ERROR",
                    "http_status": int(status_code or 0),
                    "gh_error_code": gh_error_code or None,
                    "gh_request_id": _clean_str(headers2.get("X-GitHub-Request-Id") if hasattr(headers2, "get") else ""),
                    "endpoint": get_url,
                    "message_redacted": redacted or None,
                    "message_hash": message_hash or None,
                    "retry_after_seconds": int(headers2.get("Retry-After") or 0)
                    if hasattr(headers2, "get") and str(headers2.get("Retry-After") or "").isdigit()
                    else None,
                    "ssl_context_selected": ssl_selected or None,
                    "ssl_context_tried": ssl_tried if isinstance(ssl_tried, list) else None,
                }
            )
            payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_ERROR", redacted)
            _write(payload)
            return
    except Exception as exc:
        message = _clean_str(str(exc)) or "REQUEST_FAILED"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "REQUEST_FAILED",
                "endpoint": get_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
        _write(payload)
        return
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    request_body: dict[str, Any] = {
        "tag_name": tag_name,
        "name": name,
        "draft": False,
        "prerelease": bool(prerelease),
    }
    if commitish:
        request_body["target_commitish"] = commitish
    if body:
        request_body["body"] = body
    data = _json.dumps(request_body).encode("utf-8")
    req = _urllib_request.Request(api_url, data=data, headers=headers, method="POST")
    try:
        status_code, body_bytes, headers2, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
            req,
            workspace_root=ws,
            timeout_seconds=30,
        )
        payload.setdefault("ssl_context_selected", ssl_selected)
        payload.setdefault("ssl_context_tried", ssl_tried)
    except _SSLVerifyFailed as exc:
        redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
        payload.update(
            {
                "error_code": "SSL_CERT_VERIFY_FAILED",
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "ssl_context_tried": getattr(exc, "tried", None),
            }
        )
        payload["failure_class"] = "NETWORK"
        _write(payload)
        return
    except _urllib_error.HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0)
        headers2 = getattr(exc, "headers", {}) or {}
        ssl_selected = _clean_str(getattr(exc, "_ssl_context_selected", ""))
        ssl_tried = getattr(exc, "_ssl_context_tried", None)
        try:
            body_bytes = exc.read()
        except Exception:
            body_bytes = b""
        message = ""
        gh_error_code = ""
        try:
            err_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            err_obj = {}
        if isinstance(err_obj, dict):
            message = _clean_str(err_obj.get("message"))
            errors = err_obj.get("errors") if isinstance(err_obj.get("errors"), list) else []
            if errors:
                first = errors[0] if isinstance(errors[0], dict) else {}
                gh_error_code = _clean_str(first.get("code"))
                if not message:
                    message = _clean_str(first.get("message"))
        if not message:
            message = _clean_str(getattr(exc, "reason", "")) or "HTTP_ERROR"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_ERROR",
                "http_status": int(status_code or 0),
                "gh_error_code": gh_error_code or None,
                "gh_request_id": _clean_str(headers2.get("X-GitHub-Request-Id") if hasattr(headers2, "get") else ""),
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
                "retry_after_seconds": int(headers2.get("Retry-After") or 0)
                if hasattr(headers2, "get") and str(headers2.get("Retry-After") or "").isdigit()
                else None,
                "ssl_context_selected": ssl_selected or None,
                "ssl_context_tried": ssl_tried if isinstance(ssl_tried, list) else None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_ERROR", redacted)
        _write(payload)
        return
    except Exception as exc:
        message = _clean_str(str(exc)) or "REQUEST_FAILED"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "REQUEST_FAILED",
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
        _write(payload)
        return
    payload["http_status"] = int(status_code or 0)
    if int(status_code or 0) not in {200, 201}:
        message = "HTTP_STATUS"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_STATUS",
                "endpoint": api_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_STATUS", redacted)
        _write(payload)
        return
    try:
        response_obj = _json.loads(body_bytes.decode("utf-8"))
    except Exception:
        response_obj = {}
    payload["rc"] = 0
    payload.update(_extract_release_metadata(response_obj))
    _write(payload)
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
def build_github_ops_report(*, workspace_root: Path) -> dict[str, Any]:
    policy, policy_source, policy_hash, notes = _load_policy(workspace_root)
    live_gate = _live_gate(policy, workspace_root=workspace_root)
    git_state = _git_state(_repo_root())
    jobs_index, job_notes = _load_jobs_index(workspace_root)
    notes.extend(job_notes)
    jobs_index_rel = _save_jobs_index(workspace_root, jobs_index)
    jobs = jobs_index.get("jobs") if isinstance(jobs_index.get("jobs"), list) else []
    counts = jobs_index.get("counts") if isinstance(jobs_index.get("counts"), dict) else {}
    last_pr_open: dict[str, Any] | None = None
    pr_jobs = [j for j in jobs if str(j.get("kind") or "") == "PR_OPEN"]
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
    failure_summary = _failure_summary(jobs)
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
        "notes": notes,
    }
    if last_pr_open is not None:
        report["last_pr_open"] = last_pr_open
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
                rc_obj: dict[str, Any] | None = None
                if rc_path.exists():
                    try:
                        loaded = _load_json(rc_path)
                        rc_obj = loaded if isinstance(loaded, dict) else None
                        rc = int(rc_obj.get("rc")) if rc_obj is not None and isinstance(rc_obj.get("rc"), int) else None
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
