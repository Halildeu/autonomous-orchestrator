from __future__ import annotations

from typing import Any


def _run_pr_merge_job_impl(
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
        _infer_repo_from_git,
        _map_failure_class,
        _redact_message,
        _repo_root,
        _urlopen_read_with_ssl_fallback,
    )

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

    if pr_number is None:
        # Best-effort inference: if no request payload is provided, use the most recent PR_OPEN
        # job result that still reports pr_state=open. This makes `github-ops-job-start --kind MERGE`
        # usable without an explicit request file.
        jobs_index_path = ws / ".cache" / "github_ops" / "jobs_index.v1.json"
        try:
            if jobs_index_path.exists():
                jobs_index = _json.loads(jobs_index_path.read_text(encoding="utf-8"))
            else:
                jobs_index = {}
        except Exception:
            jobs_index = {}

        jobs = jobs_index.get("jobs") if isinstance(jobs_index, dict) else None
        candidates: list[dict[str, Any]] = []
        if isinstance(jobs, list):
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                if str(job.get("kind") or "") != "PR_OPEN":
                    continue
                pn = job.get("pr_number")
                if not isinstance(pn, int) or pn <= 0:
                    continue
                pr_state = str(job.get("pr_state") or "").strip().lower()
                if pr_state and pr_state != "open":
                    continue
                candidates.append(job)

        if candidates:
            candidates.sort(key=lambda j: (str(j.get("created_at") or ""), str(j.get("job_id") or "")), reverse=True)
            chosen = candidates[0]
            pr_number = int(chosen.get("pr_number"))
            payload["pr_number_inferred"] = pr_number
            payload["pr_number_inferred_from_job_id"] = str(chosen.get("job_id") or "")
            payload["pr_number_inferred_source"] = str(jobs_index_path)

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
        "Accept": "application/vnd.github+json, application/vnd.github.shadow-cat-preview+json",
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

    repo_obj: dict[str, Any] = {}
    try:
        repo_obj = _json.loads(repo_body.decode("utf-8")) if repo_body else {}
    except Exception:
        repo_obj = {}

    allowed_methods: list[str] = []
    if isinstance(repo_obj, dict):
        if bool(repo_obj.get("allow_squash_merge", False)):
            allowed_methods.append("squash")
        if bool(repo_obj.get("allow_merge_commit", False)):
            allowed_methods.append("merge")
        if bool(repo_obj.get("allow_rebase_merge", False)):
            allowed_methods.append("rebase")
    allowed_methods = sorted(set([m for m in allowed_methods if m]))

    merge_method = merge_method_override.lower().strip() if merge_method_override else ""
    if merge_method and merge_method not in allowed_methods:
        payload["error_code"] = "MERGE_METHOD_NOT_ALLOWED"
        payload["allowed_merge_methods"] = allowed_methods
        payload["requested_merge_method"] = merge_method
        payload["failure_class"] = "VALIDATION"
        _write(payload)
        return
    if not merge_method:
        # deterministic preference: squash > merge > rebase
        for candidate in ("squash", "merge", "rebase"):
            if candidate in allowed_methods:
                merge_method = candidate
                break
    if not merge_method:
        payload["error_code"] = "MERGE_METHOD_UNAVAILABLE"
        payload["allowed_merge_methods"] = allowed_methods
        payload["failure_class"] = "VALIDATION"
        _write(payload)
        return

    # determine PR number if not provided
    if pr_number is None:
        payload["error_code"] = "PR_NUMBER_MISSING"
        payload["failure_class"] = "VALIDATION"
        _write(payload)
        return

    # Fetch PR details
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    pr_obj: dict[str, Any] = {}
    try:
        pr_status, pr_body, _pr_headers = _http_json("GET", pr_url)
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
    payload["http_status"] = int(pr_status or 0)
    if pr_status != 200:
        message = "HTTP_STATUS"
        redacted, message_hash = _redact_message(message)
        payload.update(
            {
                "error_code": "HTTP_STATUS",
                "endpoint": pr_url,
                "message_redacted": redacted or None,
                "message_hash": message_hash or None,
            }
        )
        payload["failure_class"] = _map_failure_class(int(pr_status or 0), "HTTP_STATUS", redacted)
        _write(payload)
        return
    try:
        pr_obj = _json.loads(pr_body.decode("utf-8")) if pr_body else {}
    except Exception:
        pr_obj = {}

    if isinstance(pr_obj, dict):
        payload["pr_number"] = pr_number
        draft = pr_obj.get("draft")
        if isinstance(draft, bool):
            payload["pr_draft"] = draft
        mergeable = pr_obj.get("mergeable")
        if isinstance(mergeable, bool):
            payload["pr_mergeable"] = mergeable
        mergeable_state = pr_obj.get("mergeable_state")
        if isinstance(mergeable_state, str):
            payload["pr_mergeable_state"] = mergeable_state

    # Enforce expected head sha (optional)
    if expected_head_sha:
        head_sha = ""
        head = pr_obj.get("head") if isinstance(pr_obj, dict) else None
        if isinstance(head, dict):
            head_sha = _clean_str(head.get("sha"))
        if head_sha and head_sha != expected_head_sha:
            payload["error_code"] = "PR_HEAD_SHA_MISMATCH"
            payload["expected_head_sha"] = expected_head_sha
            payload["actual_head_sha"] = head_sha
            payload["failure_class"] = "CONFLICT"
            _write(payload)
            return

    # Draft PR must be marked ready before merge
    is_draft = bool(payload.get("pr_draft", False))
    if is_draft:
        payload["pr_marked_ready_for_review"] = False
        payload["pr_marked_ready_method"] = None

        # Prefer REST endpoint; fallback to GraphQL when REST is 404 (observed on some repos)
        ready_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/ready_for_review"
        ready_req = _urllib_request.Request(ready_url, headers=headers, method="POST")
        try:
            status_code, body_bytes, _headers2, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
                ready_req,
                workspace_root=ws,
                timeout_seconds=30,
            )
            payload.setdefault("ssl_context_selected", ssl_selected)
            payload.setdefault("ssl_context_tried", ssl_tried)
            if int(status_code or 0) in {200, 201}:
                payload["pr_marked_ready_for_review"] = True
                payload["pr_marked_ready_method"] = "rest"
            else:
                payload["pr_mark_ready_http_status"] = int(status_code or 0)
        except _urllib_error.HTTPError as exc:
            status_code = int(getattr(exc, "code", 0) or 0)
            if status_code != 404:
                _write_http_error(exc, endpoint=ready_url)
                return
            payload["pr_mark_ready_http_status"] = status_code
        except _SSLVerifyFailed as exc:
            redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
            payload.update(
                {
                    "error_code": "SSL_CERT_VERIFY_FAILED",
                    "endpoint": ready_url,
                    "message_redacted": redacted or None,
                    "message_hash": message_hash or None,
                    "ssl_context_tried": getattr(exc, "tried", None),
                }
            )
            payload["failure_class"] = "NETWORK"
            _write(payload)
            return
        except Exception as exc:
            message = _clean_str(str(exc)) or "REQUEST_FAILED"
            redacted, message_hash = _redact_message(message)
            payload.update(
                {
                    "error_code": "REQUEST_FAILED",
                    "endpoint": ready_url,
                    "message_redacted": redacted or None,
                    "message_hash": message_hash or None,
                }
            )
            payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
            _write(payload)
            return

        if not payload.get("pr_marked_ready_for_review"):
            # GraphQL fallback
            try:
                pr_node_id = _clean_str(pr_obj.get("node_id") if isinstance(pr_obj, dict) else "")
                if not pr_node_id:
                    payload["error_code"] = "PR_NODE_ID_MISSING"
                    payload["failure_class"] = "VALIDATION"
                    _write(payload)
                    return
                graphql_url = "https://api.github.com/graphql"
                mutation = (
                    "mutation($prId:ID!){markPullRequestReadyForReview(input:{pullRequestId:$prId}){pullRequest{isDraft}}}"
                )
                graphql_body = {"query": mutation, "variables": {"prId": pr_node_id}}
                gql_req = _urllib_request.Request(
                    graphql_url,
                    data=_json.dumps(graphql_body).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                status_code, body_bytes, _headers2, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
                    gql_req,
                    workspace_root=ws,
                    timeout_seconds=30,
                )
                payload.setdefault("ssl_context_selected", ssl_selected)
                payload.setdefault("ssl_context_tried", ssl_tried)
                if int(status_code or 0) != 200:
                    payload["error_code"] = "PR_MARK_READY_GRAPHQL_HTTP_STATUS"
                    payload["http_status"] = int(status_code or 0)
                    payload["failure_class"] = _map_failure_class(int(status_code or 0), "HTTP_STATUS", "")
                    _write(payload)
                    return
                try:
                    gql_obj = _json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                except Exception:
                    gql_obj = {}
                if isinstance(gql_obj, dict) and isinstance(gql_obj.get("errors"), list) and gql_obj.get("errors"):
                    first = gql_obj["errors"][0] if isinstance(gql_obj["errors"][0], dict) else {}
                    message = _clean_str(first.get("message")) or "GRAPHQL_ERROR"
                    redacted, message_hash = _redact_message(message)
                    payload.update(
                        {
                            "error_code": "PR_MARK_READY_GRAPHQL_ERROR",
                            "endpoint": graphql_url,
                            "message_redacted": redacted or None,
                            "message_hash": message_hash or None,
                        }
                    )
                    payload["failure_class"] = "VALIDATION"
                    _write(payload)
                    return
                # success
                payload["pr_marked_ready_for_review"] = True
                payload["pr_marked_ready_method"] = "graphql"
            except _SSLVerifyFailed as exc:
                redacted, message_hash = _redact_message(str(exc) or "SSL_CERT_VERIFY_FAILED")
                payload.update(
                    {
                        "error_code": "SSL_CERT_VERIFY_FAILED",
                        "endpoint": graphql_url,
                        "message_redacted": redacted or None,
                        "message_hash": message_hash or None,
                        "ssl_context_tried": getattr(exc, "tried", None),
                    }
                )
                payload["failure_class"] = "NETWORK"
                _write(payload)
                return
            except _urllib_error.HTTPError as exc:
                _write_http_error(exc, endpoint=graphql_url)
                return
            except Exception as exc:
                message = _clean_str(str(exc)) or "REQUEST_FAILED"
                redacted, message_hash = _redact_message(message)
                payload.update(
                    {
                        "error_code": "REQUEST_FAILED",
                        "endpoint": graphql_url,
                        "message_redacted": redacted or None,
                        "message_hash": message_hash or None,
                    }
                )
                payload["failure_class"] = _map_failure_class(None, "REQUEST_FAILED", redacted)
                _write(payload)
                return

    # Merge PR
    merge_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge"
    merge_body: dict[str, Any] = {"merge_method": merge_method}
    merge_req = _urllib_request.Request(
        merge_url,
        data=_json.dumps(merge_body).encode("utf-8"),
        headers=headers,
        method="PUT",
    )
    try:
        status_code, body_bytes, _headers2, ssl_selected, ssl_tried = _urlopen_read_with_ssl_fallback(
            merge_req,
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
