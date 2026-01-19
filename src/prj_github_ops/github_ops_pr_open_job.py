from __future__ import annotations

from typing import Any


def _run_pr_open_job_impl(
    rc_path: str,
    request_path: str,
    token_env: str,
    auth_mode: str,
    fingerprint: str,
    workspace_root: str,
) -> None:
    # Note: this implementation is intentionally isolated from src/prj_github_ops/github_ops.py
    # to keep that file within script budget constraints. It relies on stable helper functions
    # that are already part of the GitHub ops surface.
    import json as _json
    import os
    import urllib.error as _urllib_error
    import urllib.request as _urllib_request
    from pathlib import Path as _Path

    from src.prj_github_ops.github_ops import (
        _SSLVerifyFailed,
        _clean_str,
        _dotenv_env_value,
        _dump_json,
        _extract_pr_metadata,
        _map_failure_class,
        _redact_message,
        _urlopen_read_with_ssl_fallback,
    )

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

    missing = [
        key
        for key, value in [
            ("repo_owner", owner),
            ("repo_name", repo),
            ("base_branch", base_branch),
            ("head_branch", head_branch),
            ("title", title),
        ]
        if not value
    ]
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
        "Accept": "application/vnd.github+json, application/vnd.github.shadow-cat-preview+json",
        "Content-Type": "application/json",
        "Authorization": auth_header,
        "User-Agent": "autonomous-orchestrator",
    }

    # Idempotency: if an open PR already exists for (head_branch -> base_branch), treat as NOOP.
    # This makes repeated "one-button" flows safe without creating duplicate PRs.
    head_query = head_branch
    if ":" not in head_query:
        head_query = f"{owner}:{head_query}"
    list_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&base={base_branch}&head={head_query}&per_page=1"
    try:
        list_req = _urllib_request.Request(list_url, headers=headers, method="GET")
        list_status, list_body, _headers_list, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
            list_req,
            workspace_root=_Path(workspace_root),
            timeout_seconds=30,
        )
        payload.setdefault("ssl_context_selected", ssl_selected)
        payload.setdefault("ssl_context_tried", ssl_tried)
        if int(list_status or 0) == 200:
            try:
                arr = _json.loads(list_body.decode("utf-8")) if list_body else []
            except Exception:
                arr = []
            if isinstance(arr, list) and arr:
                first = arr[0] if isinstance(arr[0], dict) else {}
                payload["rc"] = 0
                payload["noop"] = True
                payload.update(_extract_pr_metadata(first))
                _write(payload)
                return
    except Exception:
        # Best-effort idempotency: ignore errors here and proceed to POST.
        pass

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
                "retry_after_seconds": int(headers.get("Retry-After") or 0)
                if hasattr(headers, "get") and str(headers.get("Retry-After") or "").isdigit()
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
    payload.update(_extract_pr_metadata(response_obj))
    _write(payload)

