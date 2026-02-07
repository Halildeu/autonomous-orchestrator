from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.tools.errors import PolicyViolation
from src.tools import secrets_get


def _load_policy_security(workspace: Path) -> dict[str, Any]:
    path = workspace / "policies" / "policy_security.v1.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise PolicyViolation("NETWORK_DISABLED", f"Network policy missing/invalid: {path}")
    if not isinstance(raw, dict):
        raise PolicyViolation("NETWORK_DISABLED", f"Network policy invalid (not an object): {path}")
    return raw


def _enforce_network_allowlist(*, workspace: Path, host: str) -> None:
    if not isinstance(host, str) or not host.strip():
        raise PolicyViolation("NETWORK_HOST_NOT_ALLOWED", "Missing network host.")
    policy = _load_policy_security(workspace)
    if policy.get("network_access") is not True:
        raise PolicyViolation("NETWORK_DISABLED", "Network access disabled by policy.")
    allowlist = policy.get("network_allowlist", [])
    allow = [x.strip() for x in allowlist if isinstance(x, str) and x.strip()] if isinstance(allowlist, list) else []
    if host not in set(allow):
        raise PolicyViolation("NETWORK_HOST_NOT_ALLOWED", f"Network host not in allowlist: {host}")


def _require_integration_mode() -> None:
    if os.environ.get("ORCH_INTEGRATION_MODE") != "1":
        raise PolicyViolation(
            "INTEGRATION_MODE_REQUIRED",
            "Integration mode required (set ORCH_INTEGRATION_MODE=1).",
        )


def _require_non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyViolation("INVALID_ARGS", f"Missing or invalid {field}.")
    return value.strip()


def _github_api_error_message(raw: bytes, *, limit: int = 300) -> str:
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        text = raw.decode("utf-8", errors="replace")
        return (text.strip() or "GITHUB_API_ERROR")[:limit]

    msg = obj.get("message") if isinstance(obj, dict) else None
    if isinstance(msg, str) and msg.strip():
        return msg.strip()[:limit]
    return "GITHUB_API_ERROR"


@dataclass(frozen=True)
class GitHubCreatePullRequestResult:
    number: int | None
    url: str | None


def _create_pull_request(
    *,
    repo: str,
    base: str,
    head: str,
    title: str,
    body: str,
    draft: bool,
    token: str,
    timeout_s: float,
) -> tuple[GitHubCreatePullRequestResult, int, int]:
    url = f"https://api.github.com/repos/{repo}/pulls"
    payload: dict[str, Any] = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "draft": bool(draft),
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        method="POST",
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "autonomous-orchestrator",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=float(timeout_s)) as resp:
            raw = resp.read()
            code = getattr(resp, "status", 200)
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        msg = _github_api_error_message(raw)
        raise PolicyViolation("GITHUB_API_ERROR", f"GitHub API error (HTTP {e.code}): {msg}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise PolicyViolation("GITHUB_API_ERROR", f"GitHub request failed: {e}") from e

    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise PolicyViolation("GITHUB_API_ERROR", "GitHub API returned invalid JSON.") from e

    number = obj.get("number") if isinstance(obj, dict) else None
    pr_url = obj.get("html_url") if isinstance(obj, dict) else None
    out = GitHubCreatePullRequestResult(
        number=int(number) if isinstance(number, int) else None,
        url=str(pr_url) if isinstance(pr_url, str) and pr_url else None,
    )
    return (out, len(data), len(raw))


def run(
    *,
    repo: str,
    base: str,
    head: str,
    title: str,
    body: str,
    draft: bool,
    workspace: str,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    ws = Path(workspace).resolve()
    repo_s = _require_non_empty(repo, "repo")
    base_s = _require_non_empty(base, "base")
    head_s = _require_non_empty(head, "head")
    title_s = _require_non_empty(title, "title")
    body_s = body if isinstance(body, str) else ""
    draft_b = bool(draft)

    _require_integration_mode()
    _enforce_network_allowlist(workspace=ws, host="api.github.com")

    secret_meta = secrets_get.run(secret_id="GITHUB_TOKEN", workspace=str(ws))
    if secret_meta.get("status") != "OK":
        raise PolicyViolation("MISSING_GITHUB_TOKEN", "Missing GITHUB_TOKEN secret.")
    handle = secret_meta.get("handle")
    token = secrets_get.consume(handle) if isinstance(handle, str) else None
    if not token:
        raise PolicyViolation("MISSING_GITHUB_TOKEN", "Missing GITHUB_TOKEN secret.")

    pr, bytes_in, bytes_out = _create_pull_request(
        repo=repo_s,
        base=base_s,
        head=head_s,
        title=title_s,
        body=body_s,
        draft=draft_b,
        token=token,
        timeout_s=float(timeout_s),
    )

    return {
        "tool": "github_pr_create",
        "status": "OK",
        "bytes_in": int(bytes_in),
        "bytes_out": int(bytes_out),
        "repo": repo_s,
        "number": pr.number,
        "pr_url": pr.url,
        "redacted": True,
    }

