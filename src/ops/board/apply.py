from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from src.ops.board.gh_env import gh_subprocess_env, token_present
from src.ops.board.reports import finish_report

APPLY_CONFIRMATION = "APPLY_BOARD_GOVERNANCE_BOG_3C"
SUPPORTED_ACTIONS = {"append_comment", "set_board_status", "create_issue"}


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _append_body(action: dict[str, Any]) -> str:
    prefix = str(action.get("prefix") or "BOARD")
    issue = action.get("issue")
    lines = [f"{prefix} issue=#{issue}"]
    evidence_type = str(action.get("evidence_type") or "")
    evidence = str(action.get("evidence") or "")
    reason = str(action.get("reason") or "")
    session = str(action.get("session") or "")
    if evidence_type:
        lines.append(f"evidence_type={evidence_type}")
    if evidence:
        lines.append(f"evidence={evidence}")
    if reason:
        lines.append(f"reason={reason}")
    if session:
        lines.append(f"session={session}")
    lines.append("")
    lines.append("Applied by board-governance BOG-3C gated apply.")
    return "\n".join(lines)


def _issue_body(action: dict[str, Any]) -> str:
    body = [
        "Created by board-governance BOG-3C gated apply.",
        "",
        "agent-state:v1",
        f"kind={action.get('kind', '')}",
        f"faz={action.get('faz', '')}",
        f"track={action.get('track', '')}",
        f"priority={action.get('priority', '')}",
    ]
    return "\n".join(str(x) for x in body)


def _command_for(action: dict[str, Any], *, repo: str, gh_bin: str) -> list[str]:
    action_type = str(action.get("type") or "")
    if action_type == "append_comment":
        return [
            gh_bin,
            "issue",
            "comment",
            str(action.get("issue")),
            "--repo",
            repo,
            "--body",
            _append_body(action),
        ]
    if action_type == "set_board_status":
        return [
            gh_bin,
            "project",
            "item-edit",
            "--project-id",
            str(action.get("project_id")),
            "--id",
            str(action.get("project_item_id")),
            "--field-id",
            str(action.get("status_field_id")),
            "--single-select-option-id",
            str(action.get("status_option_id")),
        ]
    if action_type == "create_issue":
        cmd = [
            gh_bin,
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            str(action.get("title") or ""),
            "--body",
            _issue_body(action),
        ]
        labels = action.get("labels") if isinstance(action.get("labels"), list) else []
        for label in labels:
            cmd.extend(["--label", str(label)])
        return cmd
    raise ValueError(f"unsupported action: {action_type}")


def _metadata_errors(action: dict[str, Any]) -> list[str]:
    action_type = str(action.get("type") or "")
    if action_type not in SUPPORTED_ACTIONS:
        return [f"UNSUPPORTED_APPLY_ACTION:{action_type}"]
    if action.get("status") == "Done":
        return ["DONE_AUTOMATION_FORBIDDEN"]
    if action_type == "append_comment":
        missing = [field for field in ("issue", "prefix") if not action.get(field)]
    elif action_type == "set_board_status":
        missing = [
            field
            for field in ("issue", "status", "project_id", "project_item_id", "status_field_id", "status_option_id")
            if not action.get(field)
        ]
    elif action_type == "create_issue":
        missing = [field for field in ("title", "kind", "faz", "track", "priority") if not action.get(field)]
    else:
        missing = []
    return [f"APPLY_ACTION_MISSING_{field.upper()}" for field in missing]


def apply_report(report: dict[str, Any], args: Any) -> dict[str, Any]:
    """Apply already-planned board actions through gh after fail-closed preflight."""
    confirm = str(getattr(args, "apply_confirm", "") or "")
    token_env = str(getattr(args, "token_env", "") or "GITHUB_TOKEN")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    repo = str(report.get("repo") or getattr(args, "repo", "") or "")
    planned = report.get("planned_actions") if isinstance(report.get("planned_actions"), list) else []

    report.setdefault("inputs", {})["token_env"] = token_env
    report.setdefault("inputs", {})["apply_confirmation_required"] = APPLY_CONFIRMATION
    report.setdefault("inputs", {})["apply_confirmation_present"] = confirm == APPLY_CONFIRMATION

    blocked: list[str] = []
    if confirm != APPLY_CONFIRMATION:
        blocked.append("APPLY_CONFIRMATION_REQUIRED")
    if not repo or "/" not in repo:
        blocked.append("REPO_REQUIRED_FOR_APPLY")
    if not token_present(token_env):
        blocked.append(f"TOKEN_ENV_MISSING:{token_env}")
    if not _gh_available(gh_bin):
        blocked.append("GH_BIN_NOT_AVAILABLE")
    if not planned:
        blocked.append("NO_PLANNED_ACTIONS")
    for action in planned:
        if not isinstance(action, dict):
            blocked.append("INVALID_PLANNED_ACTION")
            continue
        blocked.extend(_metadata_errors(action))

    if blocked:
        report["blocked_reasons"].extend(blocked)
        report["applied_actions"] = []
        return finish_report(report, status="BLOCKED")

    applied: list[dict[str, Any]] = []
    for action in planned:
        cmd = _command_for(action, repo=repo, gh_bin=gh_bin)
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=gh_subprocess_env(token_env))
        safe_action = {
            "type": action.get("type"),
            "issue": action.get("issue"),
            "status": action.get("status"),
            "prefix": action.get("prefix"),
            "returncode": proc.returncode,
        }
        if proc.returncode != 0:
            safe_action["stderr"] = (proc.stderr or "").strip()[:500]
            report["applied_actions"].extend(applied)
            report["blocked_reasons"].append(f"GH_COMMAND_FAILED:{action.get('type')}")
            return finish_report(report, status="ERROR")
        safe_action["stdout"] = (proc.stdout or "").strip()[:500]
        applied.append({k: v for k, v in safe_action.items() if v not in (None, "", [])})

    report["applied_actions"] = applied
    evidence = report.setdefault("evidence", {})
    evidence.setdefault("runtime_live", []).append("gh command execution completed")
    does_not = evidence.setdefault("does_not_prove", [])
    if isinstance(does_not, list):
        while "Live GitHub Project mutation has not been applied." in does_not:
            does_not.remove("Live GitHub Project mutation has not been applied.")
        note = "GitHub command completion does not prove runtime or user-path acceptance."
        if note not in does_not:
            does_not.append(note)
    return finish_report(report, status="OK")
