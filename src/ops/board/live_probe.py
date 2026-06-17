from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.gh_env import gh_subprocess_env
from src.ops.board.models import BOARD_TITLE_DEFAULT, KINDS, PRIORITIES, REQUIRED_FIELDS, STATUSES, TRACKS
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic

REQUIRED_FAZ = (
    "F0 Written Boundary",
    "F1 Board Contract",
    "F2 Issue PR Contract",
    "F3 Board Script",
    "F4 PR Evidence",
    "F5 Projection Drift",
    "FZ Managed Repo",
)

READ_ONLY_COMMANDS = {
    ("auth", "status"),
    ("repo", "view"),
    ("project", "list"),
    ("project", "view"),
    ("project", "field-list"),
}


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _safe_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(token:\s*)([A-Za-z0-9_.\-]+)", r"\1<redacted>", text)
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "<redacted-token>", text)
    return text.strip()[:1000]


def _json_loads(text: str) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(text or "{}")
    except Exception as exc:
        return ({}, f"json parse failed: {exc.__class__.__name__}")
    if not isinstance(payload, dict):
        return ({}, "json root must be object")
    return (payload, None)


def _command_allowed(args: list[str]) -> bool:
    if len(args) < 2:
        return False
    return (args[0], args[1]) in READ_ONLY_COMMANDS


def _run_gh(report: dict[str, Any], gh_bin: str, args: list[str], *, token_env: str = "") -> tuple[dict[str, Any], str | None]:
    command_key = " ".join(args[:2])
    if not _command_allowed(args):
        report.setdefault("forbidden_actions_observed", []).append(args[:2])
        return ({}, f"FORBIDDEN_GH_COMMAND:{command_key}")
    report.setdefault("read_only_commands", []).append(command_key)
    proc = subprocess.run([gh_bin, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=gh_subprocess_env(token_env))
    if proc.returncode != 0:
        return (
            {},
            f"GH_COMMAND_FAILED:{command_key}:{_safe_text(proc.stderr or proc.stdout)}",
        )
    if args[:2] == ["auth", "status"]:
        combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        return ({"raw": _safe_text(combined)}, None)
    return _json_loads(proc.stdout)


def _parse_auth(raw: str) -> dict[str, Any]:
    account = ""
    scopes: list[str] = []
    account_match = re.search(r"Logged in to github\.com account\s+([^\s]+)", raw)
    if account_match:
        account = account_match.group(1)
    scope_match = re.search(r"Token scopes:\s*(.+)", raw)
    if scope_match:
        scopes = [part.strip().strip("'\"") for part in scope_match.group(1).split(",") if part.strip()]
    return {
        "status": "OK",
        "account": account,
        "token_scopes": sorted(set(scopes)),
        "required_scopes": ["project", "repo"],
        "required_scopes_present": all(scope in set(scopes) for scope in ("project", "repo")) if scopes else None,
    }


def _derive_owner(repo: str, project_owner: str) -> str:
    if project_owner:
        return project_owner
    if "/" in repo:
        return repo.split("/", 1)[0]
    return ""


def _project_candidates(projects_payload: dict[str, Any]) -> list[dict[str, Any]]:
    projects = projects_payload.get("projects") if isinstance(projects_payload.get("projects"), list) else []
    return [item for item in projects if isinstance(item, dict)]


def _find_project(projects: list[dict[str, Any]], *, number: str, title: str) -> dict[str, Any] | None:
    if number:
        for project in projects:
            if str(project.get("number") or "") == number:
                return project
    if title:
        for project in projects:
            if str(project.get("title") or "") == title:
                return project
    return None


def _field_map(fields_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = fields_payload.get("fields") if isinstance(fields_payload.get("fields"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        if isinstance(field, dict) and field.get("name"):
            out[str(field["name"])] = field
    return out


def _option_names(field: dict[str, Any]) -> set[str]:
    options = field.get("options") if isinstance(field.get("options"), list) else []
    return {str(item.get("name")) for item in options if isinstance(item, dict) and item.get("name")}


def _required_option_sets() -> dict[str, set[str]]:
    return {
        "Status": set(STATUSES),
        "Faz": set(REQUIRED_FAZ),
        "Track": set(TRACKS),
        "Priority": set(PRIORITIES),
        "Kind": set(KINDS),
    }


def _field_compatibility(fields_payload: dict[str, Any]) -> dict[str, Any]:
    fields = _field_map(fields_payload)
    required_options = _required_option_sets()
    missing_fields = [field for field in REQUIRED_FIELDS if field not in fields]
    missing_options: dict[str, list[str]] = {}
    field_types: dict[str, str] = {}
    for field_name in REQUIRED_FIELDS:
        field = fields.get(field_name, {})
        if not field:
            continue
        field_types[field_name] = str(field.get("type") or "")
        options = _option_names(field)
        missing = sorted(required_options[field_name] - options)
        if missing:
            missing_options[field_name] = missing
    status = "OK" if not missing_fields and not missing_options else "WARN"
    return {
        "status": status,
        "required_fields": list(REQUIRED_FIELDS),
        "missing_fields": missing_fields,
        "missing_options": missing_options,
        "field_types": field_types,
        "field_count": len(fields),
    }


def _base_report(*, mode: str, repo: str, board_title: str, project_owner: str, project_number: str) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "command": "board-live-probe",
        "mode": mode,
        "status": "OK",
        "started_at": started,
        "completed_at": started,
        "repo": repo,
        "board_title": board_title or BOARD_TITLE_DEFAULT,
        "project_owner": project_owner,
        "requested_project_number": project_number,
        "auth": {},
        "repo_access": {},
        "project_inventory": [],
        "resolved_project": {},
        "field_inventory": {},
        "field_compatibility": {},
        "read_only_commands": [],
        "planned_actions": [],
        "applied_actions": [],
        "blocked_reasons": [],
        "forbidden_actions_observed": [],
        "evidence": {
            "source": [
                "docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md",
                "policies/policy_board_governance.v1.json",
            ],
            "desired_state": ["GitHub ProjectV2 read-only metadata discovery"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "No GitHub Project, issue, PR, label, or field mutation was applied.",
                "Project creation is not performed by this probe.",
                "Issue closure remains deliberate and out of scope.",
                "Runtime or user-path acceptance is not proven by read-only metadata discovery.",
            ],
        },
    }


def run_board_live_probe(args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    repo = str(getattr(args, "repo", "") or "")
    board_title = str(getattr(args, "board_title", "") or BOARD_TITLE_DEFAULT)
    requested_owner = str(getattr(args, "project_owner", "") or "")
    project_owner = _derive_owner(repo, requested_owner)
    project_number = str(getattr(args, "project_number", "") or "")
    limit = max(1, int(getattr(args, "limit", 30) or 30))
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    token_env = str(getattr(args, "token_env", "") or "")
    report = _base_report(mode=mode, repo=repo, board_title=board_title, project_owner=project_owner, project_number=project_number)

    if mode == "apply":
        report["blocked_reasons"].append("APPLY_NOT_SUPPORTED_FOR_LIVE_PROBE")
        return finish_report(report, status="BLOCKED")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
        return finish_report(report, status="BLOCKED")

    auth_payload, error = _run_gh(report, gh_bin, ["auth", "status"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    report["auth"] = _parse_auth(str(auth_payload.get("raw") or ""))
    if report["auth"].get("required_scopes_present") is False:
        report["blocked_reasons"].append("TOKEN_SCOPE_MISSING:project_or_repo")
    report["evidence"]["runtime_live"].append("gh auth status completed")

    if repo:
        repo_payload, error = _run_gh(report, gh_bin, ["repo", "view", repo, "--json", "nameWithOwner,viewerPermission,isPrivate,url"], token_env=token_env)
        if error:
            report["blocked_reasons"].append(error)
            return finish_report(report, status="BLOCKED")
        report["repo_access"] = {
            "nameWithOwner": repo_payload.get("nameWithOwner"),
            "viewerPermission": repo_payload.get("viewerPermission"),
            "isPrivate": repo_payload.get("isPrivate"),
            "url": repo_payload.get("url"),
        }
        report["evidence"]["runtime_live"].append("gh repo view completed")

    if not project_owner:
        report["blocked_reasons"].append("PROJECT_OWNER_REQUIRED")
        return finish_report(report, status="WARN")

    projects_payload, error = _run_gh(report, gh_bin, ["project", "list", "--owner", project_owner, "--format", "json", "--limit", str(limit)], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    projects = _project_candidates(projects_payload)
    report["project_inventory"] = [
        {
            "number": project.get("number"),
            "title": project.get("title"),
            "id": project.get("id"),
            "closed": project.get("closed"),
            "url": project.get("url"),
            "fields_total": (project.get("fields") or {}).get("totalCount") if isinstance(project.get("fields"), dict) else None,
            "items_total": (project.get("items") or {}).get("totalCount") if isinstance(project.get("items"), dict) else None,
        }
        for project in projects
    ]
    report["evidence"]["runtime_live"].append("gh project list completed")

    resolved = _find_project(projects, number=project_number, title=board_title)
    if not resolved:
        report["blocked_reasons"].append("PROJECT_NOT_FOUND_BY_NUMBER_OR_TITLE")
        return finish_report(report, status="WARN")
    resolved_number = str(resolved.get("number") or project_number)
    view_payload, error = _run_gh(report, gh_bin, ["project", "view", resolved_number, "--owner", project_owner, "--format", "json"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    report["resolved_project"] = {
        "number": view_payload.get("number") or resolved.get("number"),
        "title": view_payload.get("title") or resolved.get("title"),
        "id": view_payload.get("id") or resolved.get("id"),
        "closed": view_payload.get("closed") if "closed" in view_payload else resolved.get("closed"),
        "url": view_payload.get("url") or resolved.get("url"),
    }
    report["evidence"]["runtime_live"].append("gh project view completed")

    fields_payload, error = _run_gh(report, gh_bin, ["project", "field-list", resolved_number, "--owner", project_owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    compatibility = _field_compatibility(fields_payload)
    report["field_compatibility"] = compatibility
    report["field_inventory"] = {
        "totalCount": fields_payload.get("totalCount"),
        "names": sorted(_field_map(fields_payload).keys()),
    }
    report["evidence"]["runtime_live"].append("gh project field-list completed")
    if compatibility["status"] != "OK":
        report["blocked_reasons"].append("PROJECT_FIELD_CONTRACT_MISMATCH")
        return finish_report(report, status="WARN")
    return finish_report(report, status="OK")


def write_board_live_probe_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_board_live_probe(payload: dict[str, Any]) -> str:
    return dump_json(payload)
