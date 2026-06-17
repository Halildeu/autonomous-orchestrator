from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.live_probe import (
    _derive_owner,
    _field_compatibility,
    _field_map,
    _find_project,
    _json_loads,
    _project_candidates,
    _required_option_sets,
    _safe_text,
)
from src.ops.board.gh_env import gh_subprocess_env, token_present
from src.ops.board.models import BOARD_TITLE_DEFAULT, REQUIRED_FIELDS
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic

SETUP_CONFIRMATION = "APPLY_BOARD_GOVERNANCE_BOG_6B"
READ_ONLY_PREFIXES = {
    ("auth", "status"),
    ("repo", "view"),
    ("project", "list"),
    ("project", "view"),
    ("project", "field-list"),
}
MUTATION_PREFIXES = {
    ("project", "create"),
    ("project", "field-create"),
    ("project", "link"),
    ("api", "graphql"),
}
OPTION_COLOR_DEFAULT = "GRAY"


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _base_report(*, mode: str, repo: str, board_title: str, project_owner: str, project_number: str) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "command": "board-setup",
        "mode": mode,
        "status": "OK",
        "started_at": started,
        "completed_at": started,
        "repo": repo,
        "board_title": board_title or BOARD_TITLE_DEFAULT,
        "project_owner": project_owner,
        "requested_project_number": project_number,
        "resolved_project": {},
        "field_compatibility": {},
        "setup_digest": "",
        "accepted_digest": "",
        "planned_actions": [],
        "applied_actions": [],
        "mutation_ledger": [],
        "read_only_commands": [],
        "mutation_commands": [],
        "blocked_reasons": [],
        "evidence": {
            "source": [
                "docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md",
                "docs/OPERATIONS/BOARD-LIVE-ACCEPTANCE-PROBE-EVIDENCE.v1.md",
            ],
            "desired_state": ["autonomous-orchestrator Governance Board ProjectV2"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Issue creation, issue closure, and ProjectV2 item movement remain out of scope.",
                "Runtime or user-path acceptance is not proven by setup.",
                "Live sync apply requires a later accepted projection digest.",
            ],
        },
    }


def _run_gh(report: dict[str, Any], gh_bin: str, args: list[str], *, mutation: bool = False, token_env: str = "") -> tuple[dict[str, Any], str | None]:
    key = (args[0], args[1]) if len(args) >= 2 else ("", "")
    command_name = " ".join(args[:2])
    if mutation:
        if key not in MUTATION_PREFIXES:
            return ({}, f"FORBIDDEN_MUTATION_COMMAND:{command_name}")
        report["mutation_commands"].append(command_name)
    else:
        if key not in READ_ONLY_PREFIXES:
            return ({}, f"FORBIDDEN_READ_COMMAND:{command_name}")
        report["read_only_commands"].append(command_name)
    proc = subprocess.run([gh_bin, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=gh_subprocess_env(token_env))
    if proc.returncode != 0:
        return ({}, f"GH_COMMAND_FAILED:{command_name}:{_safe_text(proc.stderr or proc.stdout)}")
    if args[:2] == ["auth", "status"]:
        return ({"raw": _safe_text("\n".join(part for part in (proc.stdout, proc.stderr) if part))}, None)
    return _json_loads(proc.stdout)


def _repo_view(report: dict[str, Any], gh_bin: str, repo: str, *, token_env: str = "") -> bool:
    if not repo:
        report["blocked_reasons"].append("REPO_REQUIRED")
        return False
    payload, error = _run_gh(report, gh_bin, ["repo", "view", repo, "--json", "nameWithOwner,viewerPermission,isPrivate,url"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return False
    report["repo_access"] = {
        "nameWithOwner": payload.get("nameWithOwner"),
        "viewerPermission": payload.get("viewerPermission"),
        "isPrivate": payload.get("isPrivate"),
        "url": payload.get("url"),
    }
    report["evidence"]["runtime_live"].append("gh repo view completed")
    return True


def _read_project_state(report: dict[str, Any], gh_bin: str, project_owner: str, project_number: str, board_title: str, *, token_env: str = "") -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    payload, error = _run_gh(report, gh_bin, ["project", "list", "--owner", project_owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return (None, None)
    report["evidence"]["runtime_live"].append("gh project list completed")
    project = _find_project(_project_candidates(payload), number=project_number, title=board_title)
    if not project:
        return (None, None)
    number = str(project.get("number") or project_number)
    view, error = _run_gh(report, gh_bin, ["project", "view", number, "--owner", project_owner, "--format", "json"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return (None, None)
    fields, error = _run_gh(report, gh_bin, ["project", "field-list", number, "--owner", project_owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return (None, None)
    report["evidence"]["runtime_live"].extend(["gh project view completed", "gh project field-list completed"])
    report["resolved_project"] = {
        "number": view.get("number") or project.get("number"),
        "title": view.get("title") or project.get("title"),
        "id": view.get("id") or project.get("id"),
        "closed": view.get("closed") if "closed" in view else project.get("closed"),
        "url": view.get("url") or project.get("url"),
    }
    report["field_compatibility"] = _field_compatibility(fields)
    return (report["resolved_project"], fields)


def _field_create_action(field_name: str) -> dict[str, Any]:
    return {
        "type": "create_project_field",
        "field": field_name,
        "data_type": "SINGLE_SELECT",
        "options": sorted(_required_option_sets()[field_name]),
    }


def _setup_digest(report: dict[str, Any], *, link_repo: bool) -> str:
    payload = {
        "version": "v1",
        "repo": report.get("repo"),
        "board_title": report.get("board_title"),
        "project_owner": report.get("project_owner"),
        "resolved_project": report.get("resolved_project", {}),
        "planned_actions": report.get("planned_actions", []),
        "link_repo": link_repo,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _plan_actions(report: dict[str, Any], *, project: dict[str, Any] | None, fields: dict[str, Any] | None, link_repo: bool) -> None:
    if not project:
        report["planned_actions"].append({"type": "create_project", "title": report["board_title"], "owner": report["project_owner"]})
        report["planned_actions"].append({"type": "reconcile_required_fields_after_create", "fields": list(REQUIRED_FIELDS)})
        if link_repo:
            report["planned_actions"].append({"type": "link_project_repo_after_create", "repo": report["repo"]})
        return
    compatibility = report.get("field_compatibility") if isinstance(report.get("field_compatibility"), dict) else {}
    missing_options = compatibility.get("missing_options") if isinstance(compatibility.get("missing_options"), dict) else {}
    if missing_options:
        report["blocked_reasons"].append("FIELD_OPTION_MISMATCH_REQUIRES_MANUAL_MIGRATION")
        return
    existing_fields = _field_map(fields or {})
    for field_name in REQUIRED_FIELDS:
        if field_name not in existing_fields:
            report["planned_actions"].append(_field_create_action(field_name))
    if link_repo:
        report["planned_actions"].append({"type": "link_project_repo", "repo": report["repo"]})


def _field_create_cmd(gh_bin: str, project_number: str, owner: str, action: dict[str, Any]) -> list[str]:
    return [
        gh_bin,
        "project",
        "field-create",
        project_number,
        "--owner",
        owner,
        "--name",
        str(action["field"]),
        "--data-type",
        "SINGLE_SELECT",
        "--single-select-options",
        ",".join(str(item) for item in action["options"]),
        "--format",
        "json",
    ]


def _option_update_inputs(field: dict[str, Any], required_options: set[str]) -> list[dict[str, str]]:
    existing_options = field.get("options") if isinstance(field.get("options"), list) else []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for option in existing_options:
        if not isinstance(option, dict) or not option.get("name"):
            continue
        name = str(option["name"])
        seen.add(name)
        payload = {
            "name": name,
            "color": OPTION_COLOR_DEFAULT,
            "description": "",
        }
        if option.get("id"):
            payload["id"] = str(option["id"])
        out.append(payload)
    for name in sorted(required_options - seen):
        out.append({"name": name, "color": OPTION_COLOR_DEFAULT, "description": ""})
    return out


def _graphql_update_field_options_query(field_id: str, options: list[dict[str, str]]) -> str:
    option_parts: list[str] = []
    for option in options:
        fields = []
        if option.get("id"):
            fields.append(f"id: {json.dumps(option['id'])}")
        fields.extend(
            [
                f"name: {json.dumps(option['name'])}",
                f"color: {option.get('color') or OPTION_COLOR_DEFAULT}",
                f"description: {json.dumps(option.get('description', ''))}",
            ]
        )
        option_parts.append("{" + ", ".join(fields) + "}")
    return (
        "mutation { "
        "updateProjectV2Field(input: {"
        f"fieldId: {json.dumps(field_id)}, "
        f"singleSelectOptions: [{', '.join(option_parts)}]"
        "}) { projectV2Field { ... on ProjectV2SingleSelectField { id name options { id name } } } } "
        "}"
    )


def _update_missing_options_after_create(
    report: dict[str, Any],
    gh_bin: str,
    fields_payload: dict[str, Any],
    *,
    token_env: str,
) -> dict[str, Any] | None:
    compatibility = _field_compatibility(fields_payload)
    missing_options = compatibility.get("missing_options") if isinstance(compatibility.get("missing_options"), dict) else {}
    if not missing_options:
        return None
    fields = _field_map(fields_payload)
    required = _required_option_sets()
    for field_name in REQUIRED_FIELDS:
        if field_name not in missing_options:
            continue
        field = fields.get(field_name, {})
        field_id = str(field.get("id") or "")
        if str(field.get("type") or "") != "ProjectV2SingleSelectField" or not field_id:
            report["blocked_reasons"].append(f"FIELD_OPTION_UPDATE_UNSUPPORTED:{field_name}")
            return finish_report(report, status="ERROR")
        query = _graphql_update_field_options_query(field_id, _option_update_inputs(field, required[field_name]))
        proc = subprocess.run(
            [gh_bin, "api", "graphql", "-f", f"query={query}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=gh_subprocess_env(token_env),
        )
        report["mutation_commands"].append("api graphql:updateProjectV2Field")
        if proc.returncode != 0:
            report["blocked_reasons"].append(f"GH_COMMAND_FAILED:api graphql updateProjectV2Field:{_safe_text(proc.stderr or proc.stdout)}")
            return finish_report(report, status="ERROR")
        payload, error = _json_loads(proc.stdout)
        if error:
            report["blocked_reasons"].append(f"GH_COMMAND_FAILED:api graphql updateProjectV2Field:{error}")
            return finish_report(report, status="ERROR")
        report["applied_actions"].append({"type": "update_project_field_options", "field": field_name, "id": field_id})
        report["mutation_ledger"].append({"action": "update_project_field_options", "field": field_name, "after": payload})
    return None


def _apply_actions(report: dict[str, Any], gh_bin: str, *, link_repo: bool, token_env: str) -> dict[str, Any]:
    owner = str(report.get("project_owner") or "")
    repo = str(report.get("repo") or "")
    project_number = str(report.get("resolved_project", {}).get("number") or "")
    applied: list[dict[str, Any]] = []
    fields_payload: dict[str, Any] = {}

    if any(action.get("type") == "create_project" for action in report["planned_actions"]):
        payload, error = _run_gh(
            report,
            gh_bin,
            ["project", "create", "--owner", owner, "--title", str(report["board_title"]), "--format", "json"],
            mutation=True,
            token_env=token_env,
        )
        if error:
            report["blocked_reasons"].append(error)
            return finish_report(report, status="ERROR")
        project_number = str(payload.get("number") or "")
        report["resolved_project"] = {
            "number": payload.get("number"),
            "title": payload.get("title"),
            "id": payload.get("id"),
            "url": payload.get("url"),
        }
        applied.append({"type": "create_project", "number": payload.get("number"), "id": payload.get("id")})
        report["mutation_ledger"].append({"action": "create_project", "after": report["resolved_project"]})
        if not project_number:
            report["blocked_reasons"].append("PROJECT_CREATE_DID_NOT_RETURN_NUMBER")
            report["applied_actions"] = applied
            return finish_report(report, status="ERROR")
        fields_payload, error = _run_gh(report, gh_bin, ["project", "field-list", project_number, "--owner", owner, "--format", "json", "--limit", "100"], token_env=token_env)
        if error:
            report["blocked_reasons"].append(error)
            report["applied_actions"] = applied
            return finish_report(report, status="ERROR")
        report["applied_actions"] = applied
        update_result = _update_missing_options_after_create(report, gh_bin, fields_payload, token_env=token_env)
        if update_result is not None:
            return update_result
        applied = report["applied_actions"]
    elif project_number:
        fields_payload, error = _run_gh(report, gh_bin, ["project", "field-list", project_number, "--owner", owner, "--format", "json", "--limit", "100"], token_env=token_env)
        if error:
            report["blocked_reasons"].append(error)
            return finish_report(report, status="ERROR")
    else:
        report["blocked_reasons"].append("PROJECT_NUMBER_REQUIRED_FOR_APPLY")
        return finish_report(report, status="BLOCKED")

    existing_fields = _field_map(fields_payload)
    for field_name in REQUIRED_FIELDS:
        if field_name in existing_fields:
            continue
        action = _field_create_action(field_name)
        cmd = _field_create_cmd(gh_bin, project_number, owner, action)
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=gh_subprocess_env(token_env))
        report["mutation_commands"].append("project field-create")
        if proc.returncode != 0:
            report["blocked_reasons"].append(f"GH_COMMAND_FAILED:project field-create:{_safe_text(proc.stderr or proc.stdout)}")
            report["applied_actions"] = applied
            return finish_report(report, status="ERROR")
        payload, _ = _json_loads(proc.stdout)
        applied.append({"type": "create_project_field", "field": field_name, "id": payload.get("id")})
        report["mutation_ledger"].append({"action": "create_project_field", "field": field_name, "after": payload.get("id")})

    if link_repo:
        payload, error = _run_gh(report, gh_bin, ["project", "link", project_number, "--owner", owner, "--repo", repo], mutation=True, token_env=token_env)
        if error:
            report["blocked_reasons"].append(error)
            report["applied_actions"] = applied
            return finish_report(report, status="ERROR")
        applied.append({"type": "link_project_repo", "repo": repo, "result": payload or {}})
        report["mutation_ledger"].append({"action": "link_project_repo", "repo": repo, "after": "gh command completed"})

    report["applied_actions"] = applied
    report["evidence"]["runtime_live"].append("gh setup mutation commands completed")
    return finish_report(report, status="OK")


def run_board_setup(args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    repo = str(getattr(args, "repo", "") or "")
    board_title = str(getattr(args, "board_title", "") or BOARD_TITLE_DEFAULT)
    owner = _derive_owner(repo, str(getattr(args, "project_owner", "") or ""))
    project_number = str(getattr(args, "project_number", "") or "")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    token_env = str(getattr(args, "token_env", "") or "GITHUB_TOKEN")
    confirm = str(getattr(args, "apply_confirm", "") or "")
    accepted_digest = str(getattr(args, "accepted_digest", "") or "")
    link_repo = bool(getattr(args, "link_repo", False))
    report = _base_report(mode=mode, repo=repo, board_title=board_title, project_owner=owner, project_number=project_number)
    report["accepted_digest"] = accepted_digest
    report["inputs"] = {
        "apply_confirmation_required": SETUP_CONFIRMATION,
        "apply_confirmation_present": confirm == SETUP_CONFIRMATION,
        "accepted_digest_present": bool(accepted_digest),
        "token_env": token_env,
        "link_repo": link_repo,
    }
    if mode not in {"report", "dry-run", "apply"}:
        report["blocked_reasons"].append(f"invalid mode: {mode}")
        return finish_report(report, status="BLOCKED")
    if not owner:
        report["blocked_reasons"].append("PROJECT_OWNER_REQUIRED")
        return finish_report(report, status="BLOCKED")
    if mode == "apply":
        if confirm != SETUP_CONFIRMATION:
            report["blocked_reasons"].append("APPLY_CONFIRMATION_REQUIRED")
        if not token_present(token_env):
            report["blocked_reasons"].append(f"TOKEN_ENV_MISSING:{token_env}")
        if not accepted_digest:
            report["blocked_reasons"].append("ACCEPTED_DIGEST_REQUIRED")
        if report["blocked_reasons"]:
            return finish_report(report, status="BLOCKED")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
        return finish_report(report, status="BLOCKED")
    _, error = _run_gh(report, gh_bin, ["auth", "status"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    report["evidence"]["runtime_live"].append("gh auth status completed")
    if not _repo_view(report, gh_bin, repo, token_env=token_env):
        return finish_report(report, status="BLOCKED")
    project, fields = _read_project_state(report, gh_bin, owner, project_number, board_title, token_env=token_env)
    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    _plan_actions(report, project=project, fields=fields, link_repo=link_repo)
    report["setup_digest"] = _setup_digest(report, link_repo=link_repo)
    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    if mode != "apply":
        return finish_report(report, status="OK")
    if accepted_digest != report["setup_digest"]:
        report["blocked_reasons"].append("ACCEPTED_DIGEST_MISMATCH")
    if not report["planned_actions"]:
        report["blocked_reasons"].append("NO_SETUP_ACTIONS")
    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    return _apply_actions(report, gh_bin, link_repo=link_repo, token_env=token_env)


def write_board_setup_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_board_setup(payload: dict[str, Any]) -> str:
    return dump_json(payload)
