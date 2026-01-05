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

    secret_call = secrets_get.secrets_get(secret_id="OPENAI_API_KEY", workspace=str(root), module_id="OPS_PING")
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

    # 3) Perform the minimal API call via OpenAIProvider (real network)
    from src.providers.openai_provider import OpenAIProvider

    t0 = time.perf_counter()
    try:
        provider = OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            policy_path=policy_path,
        )
        _ = provider.summarize_markdown_to_json("# Ping\n\nping\n")
        latency_ms = int((time.perf_counter() - t0) * 1000)
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
        "redacted": True,
    }
    (root / ".cache").mkdir(parents=True, exist_ok=True)
    write_json(root / ".cache" / "openai_ping_last.json", payload)
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

    ap_gh = parent.add_parser("github-pr-test", help="Integration-only GitHub PR create test (policy + secrets enforced).")
    ap_gh.add_argument("--repo", required=True, help="GitHub repo in owner/name form.")
    ap_gh.add_argument("--head", required=True, help="PR head branch (e.g. branch-name or owner:branch).")
    ap_gh.add_argument("--base", default="main", help="PR base branch (default: main).")
    ap_gh.add_argument("--title", default=None, help="PR title (default: a safe placeholder).")
    ap_gh.add_argument("--body", default="", help="PR body (default: empty).")
    ap_gh.add_argument("--draft", default="true", help="true|false (default: true).")
    ap_gh.set_defaults(func=cmd_github_pr_test)
