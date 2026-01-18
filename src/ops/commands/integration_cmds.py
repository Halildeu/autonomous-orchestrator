from __future__ import annotations

import argparse
import json
import os
import time
from urllib.parse import urlparse

from src.ops.commands.common import repo_root, write_json
from src.ops.reaper import parse_bool as parse_reaper_bool


def cmd_openai_ping(args: argparse.Namespace) -> int:
    root = repo_root()

    # Inputs
    model = str(args.model).strip() if args.model else ""
    if not model:
        model = "gpt-5.2-codex"

    try:
        timeout_ms = int(args.timeout_ms)
    except Exception:
        timeout_ms = 5000
    if timeout_ms < 1:
        timeout_ms = 1
    timeout_s = timeout_ms / 1000.0

    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    if not base_url:
        base_url = "https://api.openai.com/v1"

    host_hint = ""
    try:
        host_hint = urlparse(base_url).hostname or ""
    except Exception:
        host_hint = ""

    # 1) Network policy enforcement (deterministic, no network call if blocked)
    from src.providers.openai_provider import network_check
    from src.tools.errors import PolicyViolation

    policy_path = root / "policies" / "policy_security.v1.json"
    try:
        host = network_check(policy_path=policy_path, base_url=base_url)
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "host": host_hint or "api.openai.com",
            "model": model,
            "latency_ms": None,
            "error_code": e.error_code,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    # 2) Secrets: use policy and secrets_get
    from src.tools import secrets_get

    secret_call = secrets_get.run(secret_id="OPENAI_API_KEY", workspace=str(root))
    if not secret_call or secret_call.get("status") != "OK":
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": None,
            "error_code": "MISSING_KEY",
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    handle = secret_call.get("handle")
    handle_str = handle if isinstance(handle, str) and handle else None
    api_key = secrets_get.consume(handle_str) if handle_str else None
    if not isinstance(api_key, str) or not api_key:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": None,
            "error_code": "MISSING_KEY",
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    # 3) Perform the minimal API call (real network): GET /models
    # This avoids model-specific failures while proving:
    # - DNS/TCP/TLS reachability
    # - token auth works
    t0 = time.perf_counter()
    try:
        from urllib import error as url_error
        from urllib import request as url_request
        import ssl

        models_url = f"{base_url.rstrip('/')}/models"
        req = url_request.Request(
            url=models_url,
            method="GET",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        cafile = os.environ.get("SSL_CERT_FILE") or "/etc/ssl/cert.pem"
        ctx = ssl.create_default_context(cafile=cafile) if cafile and os.path.exists(cafile) else ssl.create_default_context()

        with url_request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            http_status = int(getattr(resp, "status", 0) or 0) or int(resp.getcode())

        latency_ms = int((time.perf_counter() - t0) * 1000)
        obj = json.loads(raw)
        data = obj.get("data") if isinstance(obj, dict) else None
        items = data if isinstance(data, list) else []
        model_ids = [
            d.get("id") for d in items if isinstance(d, dict) and isinstance(d.get("id"), str) and d.get("id")
        ]
        model_present = model in set(model_ids) if model else None
        model_count = len(model_ids)
    except url_error.HTTPError as e:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": f"HTTP_{int(getattr(e, 'code', 0) or 0) or 'ERROR'}",
            "http_status": int(getattr(e, "code", 0) or 0) or None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": e.error_code,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": "OPENAI_ERROR",
            "http_status": None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    payload = {
        "status": "OK",
        "host": host,
        "model": model,
        "latency_ms": latency_ms,
        "error_code": None,
        "http_status": http_status,
        "model_count": model_count,
        "model_present": model_present,
        "redacted": True,
    }
    (root / ".cache").mkdir(parents=True, exist_ok=True)
    write_json(root / ".cache" / "openai_ping_last.json", payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_github_ping(args: argparse.Namespace) -> int:
    root = repo_root()

    # Inputs
    try:
        timeout_ms = int(args.timeout_ms)
    except Exception:
        timeout_ms = 5000
    if timeout_ms < 1:
        timeout_ms = 1
    timeout_s = timeout_ms / 1000.0

    base_url = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").strip()
    if not base_url:
        base_url = "https://api.github.com"

    host_hint = ""
    try:
        host_hint = urlparse(base_url).hostname or ""
    except Exception:
        host_hint = ""

    # 1) Network policy enforcement (deterministic, no network call if blocked)
    from src.providers.openai_provider import network_check
    from src.tools.errors import PolicyViolation

    policy_path = root / "policies" / "policy_security.v1.json"
    try:
        host = network_check(policy_path=policy_path, base_url=base_url)
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "host": host_hint or "api.github.com",
            "latency_ms": None,
            "error_code": e.error_code,
            "http_status": None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "github_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    # 2) Secrets: use policy and secrets_get
    from src.tools import secrets_get

    secret_call = secrets_get.run(secret_id="GITHUB_TOKEN", workspace=str(root))
    if not secret_call or secret_call.get("status") != "OK":
        payload = {
            "status": "FAIL",
            "host": host,
            "latency_ms": None,
            "error_code": "MISSING_KEY",
            "http_status": None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "github_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    handle = secret_call.get("handle")
    handle_str = handle if isinstance(handle, str) and handle else None
    token = secrets_get.consume(handle_str) if handle_str else None
    if not isinstance(token, str) or not token:
        payload = {
            "status": "FAIL",
            "host": host,
            "latency_ms": None,
            "error_code": "MISSING_KEY",
            "http_status": None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "github_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    # 3) Perform the minimal API call (real network): GET /rate_limit
    # This proves:
    # - DNS/TCP/TLS reachability
    # - token auth works (401/403 etc will fail)
    t0 = time.perf_counter()
    try:
        from urllib import error as url_error
        from urllib import request as url_request
        import ssl

        ping_url = f"{base_url.rstrip('/')}/rate_limit"
        req = url_request.Request(
            url=ping_url,
            method="GET",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "autonomous-orchestrator",
            },
        )
        cafile = os.environ.get("SSL_CERT_FILE") or "/etc/ssl/cert.pem"
        ctx = ssl.create_default_context(cafile=cafile) if cafile and os.path.exists(cafile) else ssl.create_default_context()

        with url_request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            http_status = int(getattr(resp, "status", 0) or 0) or int(resp.getcode())

        obj = json.loads(raw) if raw else {}
        core = None
        if isinstance(obj, dict):
            resources = obj.get("resources")
            if isinstance(resources, dict):
                core = resources.get("core") if isinstance(resources.get("core"), dict) else None
        core_limit = core.get("limit") if isinstance(core, dict) else None
        core_remaining = core.get("remaining") if isinstance(core, dict) else None
        core_reset = core.get("reset") if isinstance(core, dict) else None
        latency_ms = int((time.perf_counter() - t0) * 1000)
    except url_error.HTTPError as e:
        payload = {
            "status": "FAIL",
            "host": host,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": f"HTTP_{int(getattr(e, 'code', 0) or 0) or 'ERROR'}",
            "http_status": int(getattr(e, "code", 0) or 0) or None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "github_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception:
        payload = {
            "status": "FAIL",
            "host": host,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": "GITHUB_ERROR",
            "http_status": None,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "github_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    payload = {
        "status": "OK",
        "host": host,
        "latency_ms": latency_ms,
        "error_code": None,
        "http_status": http_status,
        "rate_limit_core": {
            "limit": core_limit,
            "remaining": core_remaining,
            "reset": core_reset,
        },
        "redacted": True,
    }
    (root / ".cache").mkdir(parents=True, exist_ok=True)
    write_json(root / ".cache" / "github_ping_last.json", payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_github_pr_test(args: argparse.Namespace) -> int:
    root = repo_root()

    repo = str(args.repo).strip() if args.repo else ""
    head = str(args.head).strip() if args.head else ""
    base = str(args.base).strip() if args.base else "main"
    title = str(args.title).strip() if args.title else ""
    body = str(args.body) if args.body is not None else ""
    if not title:
        title = "autonomous-orchestrator: github-pr-test"

    try:
        draft = parse_reaper_bool(str(args.draft))
    except ValueError:
        payload = {"status": "FAIL", "repo": repo, "error_code": "INVALID_ARGS", "redacted": True}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    from src.tools.errors import PolicyViolation
    from src.tools.gateway import ToolGateway

    gateway = ToolGateway()
    try:
        res = gateway.call(
            "github_pr_create",
            {
                "repo": repo,
                "base": base,
                "head": head,
                "title": title,
                "body": body,
                "draft": bool(draft),
            },
            capability={"allowed_tools": ["github_pr_create"]},
            workspace=str(root),
        )
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "repo": repo,
            "number": None,
            "pr_url": None,
            "error_code": e.error_code,
            "redacted": True,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception:
        payload = {
            "status": "FAIL",
            "repo": repo,
            "number": None,
            "pr_url": None,
            "error_code": "GITHUB_API_ERROR",
            "redacted": True,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    payload = {
        "status": "OK",
        "repo": res.get("repo") or repo,
        "number": res.get("number"),
        "pr_url": res.get("pr_url"),
        "error_code": None,
        "redacted": True,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def register_integration_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_ping = parent.add_parser("openai-ping", help="Integration-only OpenAI API ping (policy + secrets enforced).")
    ap_ping.add_argument("--model", default=None, help="OpenAI model id (default: gpt-5.2-codex).")
    ap_ping.add_argument("--timeout-ms", default="5000", help="HTTP timeout in milliseconds (default: 5000).")
    ap_ping.set_defaults(func=cmd_openai_ping)

    gh_ping = parent.add_parser("github-ping", help="Integration-only GitHub API ping (policy + secrets enforced).")
    gh_ping.add_argument("--timeout-ms", default="5000", help="HTTP timeout in milliseconds (default: 5000).")
    gh_ping.set_defaults(func=cmd_github_ping)

    ap_gh = parent.add_parser("github-pr-test", help="Integration-only GitHub PR create test (policy + secrets enforced).")
    ap_gh.add_argument("--repo", required=True, help="GitHub repo in owner/name form.")
    ap_gh.add_argument("--head", required=True, help="PR head branch (e.g. branch-name or owner:branch).")
    ap_gh.add_argument("--base", default="main", help="PR base branch (default: main).")
    ap_gh.add_argument("--title", default=None, help="PR title (default: a safe placeholder).")
    ap_gh.add_argument("--body", default="", help="PR body (default: empty).")
    ap_gh.add_argument("--draft", default="true", help="true|false (default: true).")
    ap_gh.set_defaults(func=cmd_github_pr_test)
