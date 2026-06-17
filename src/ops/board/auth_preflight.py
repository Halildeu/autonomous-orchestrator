from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.gh_env import gh_subprocess_env, token_present
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic


DEFAULT_GH_AUTH_TIMEOUT_SECONDS = 20.0


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _safe_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "<redacted-token>", text)
    text = re.sub(r"(?i)(token:\s*)([A-Za-z0-9_.\-]+)", r"\1<redacted>", text)
    return text.strip()[:1000]


def _parse_scopes(raw: str) -> list[str]:
    match = re.search(r"Token scopes:\s*(.+)", raw)
    if not match:
        return []
    return sorted({part.strip().strip("'\"") for part in match.group(1).split(",") if part.strip()})


def _parse_account(raw: str) -> str:
    match = re.search(r"Logged in to github\.com account\s+([^\s]+)", raw)
    return match.group(1) if match else ""


def _base_report(*, mode: str, token_env: str, allow_keyring: bool) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "command": "board-auth-preflight",
        "mode": mode,
        "status": "OK",
        "started_at": started,
        "completed_at": started,
        "token_env": token_env,
        "token_env_present": token_present(token_env),
        "allow_keyring_auth": allow_keyring,
        "gh_available": False,
        "auth": {
            "account": "",
            "required_scopes": ["project", "repo"],
            "token_scopes": [],
            "required_scopes_present": None,
        },
        "read_only_commands": [],
        "planned_actions": [],
        "applied_actions": [],
        "blocked_reasons": [],
        "evidence": {
            "source": ["src/ops/board/gh_env.py"],
            "desired_state": ["token-boundary readiness for live GitHub ProjectV2 operations"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "No GitHub Project, issue, PR, label, or field mutation was applied.",
                "A successful auth preflight does not prove board setup or sync acceptance.",
                "Token values are intentionally not recorded.",
            ],
        },
    }


def run_board_auth_preflight(args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    token_env = str(getattr(args, "token_env", "") or "GITHUB_TOKEN")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    allow_keyring = bool(getattr(args, "allow_keyring_auth", False))
    report = _base_report(mode=mode, token_env=token_env, allow_keyring=allow_keyring)
    try:
        timeout_seconds = float(getattr(args, "gh_timeout_seconds", DEFAULT_GH_AUTH_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        report["blocked_reasons"].append("INVALID_GH_TIMEOUT_SECONDS")
        return finish_report(report, status="BLOCKED")
    if timeout_seconds <= 0:
        report["blocked_reasons"].append("INVALID_GH_TIMEOUT_SECONDS")
        return finish_report(report, status="BLOCKED")
    report["gh_timeout_seconds"] = timeout_seconds

    if mode == "apply":
        report["blocked_reasons"].append("APPLY_NOT_SUPPORTED_FOR_AUTH_PREFLIGHT")
        return finish_report(report, status="BLOCKED")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
        return finish_report(report, status="BLOCKED")
    report["gh_available"] = True
    if not report["token_env_present"] and not allow_keyring:
        report["blocked_reasons"].append(f"TOKEN_ENV_MISSING:{token_env}")
        report["blocked_reasons"].append("KEYRING_AUTH_NOT_ATTEMPTED")
        return finish_report(report, status="BLOCKED")

    report["read_only_commands"].append("auth status")
    try:
        proc = subprocess.run(
            [gh_bin, "auth", "status"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
            env=gh_subprocess_env(token_env) if report["token_env_present"] else os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        report["blocked_reasons"].append(f"GH_COMMAND_TIMEOUT:auth status:{timeout_seconds:g}s")
        return finish_report(report, status="BLOCKED")
    combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    if proc.returncode != 0:
        report["blocked_reasons"].append(f"GH_COMMAND_FAILED:auth status:{_safe_text(combined)}")
        return finish_report(report, status="BLOCKED")

    safe = _safe_text(combined)
    scopes = _parse_scopes(safe)
    scope_set = set(scopes)
    report["auth"] = {
        "account": _parse_account(safe),
        "required_scopes": ["project", "repo"],
        "token_scopes": scopes,
        "required_scopes_present": all(scope in scope_set for scope in ("project", "repo")) if scopes else None,
    }
    if report["auth"]["required_scopes_present"] is False:
        report["blocked_reasons"].append("TOKEN_SCOPE_MISSING:project_or_repo")
        return finish_report(report, status="BLOCKED")
    report["evidence"]["runtime_live"].append("gh auth status completed")
    return finish_report(report, status="OK")


def write_board_auth_preflight_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_board_auth_preflight(payload: dict[str, Any]) -> str:
    return dump_json(payload)
