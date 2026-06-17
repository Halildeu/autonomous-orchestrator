from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.ops.board.apply import APPLY_CONFIRMATION
from src.ops.board.drift import summarize_drift
from src.ops.board.gh_env import gh_subprocess_env, token_present
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(path_value: str) -> tuple[dict[str, Any], str | None]:
    path = Path(str(path_value or "").strip())
    if not path.exists():
        return ({}, f"json file not found: {path.as_posix()}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ({}, f"json parse failed: {exc.__class__.__name__}")
    if not isinstance(obj, dict):
        return ({}, "json root must be object")
    return (obj, None)


def _schema_errors(projection: dict[str, Any]) -> list[str]:
    schema_path = _repo_root() / "schemas" / "board-projection.schema.v1.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"schema load failed: {exc.__class__.__name__}"]
    errors = sorted(Draft202012Validator(schema).iter_errors(projection), key=lambda err: err.json_path)
    return [f"{err.json_path or '$'}: {err.message}" for err in errors]


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _issue_number(item: dict[str, Any]) -> int | None:
    try:
        value = int(item.get("issue_number"))
    except Exception:
        return None
    return value if value > 0 else None


def _observed_by_issue(projection: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    observed = projection.get("observed_board_items") if isinstance(projection.get("observed_board_items"), list) else []
    for item in observed:
        if not isinstance(item, dict):
            continue
        number = _issue_number(item)
        if number is not None:
            out[number] = item
    return out


def _metadata_item(metadata: dict[str, Any], issue: int) -> dict[str, Any]:
    items = metadata.get("items") if isinstance(metadata.get("items"), dict) else {}
    item = items.get(str(issue))
    return item if isinstance(item, dict) else {}


def _field_meta(metadata: dict[str, Any], field: str) -> dict[str, Any]:
    fields = metadata.get("fields") if isinstance(metadata.get("fields"), dict) else {}
    item = fields.get(field)
    return item if isinstance(item, dict) else {}


def _base_report(*, mode: str, projection_path: str, metadata_path: str, accepted_digest: str, target_board_id: str) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "command": "board-sync",
        "mode": mode,
        "status": "OK",
        "started_at": started,
        "completed_at": started,
        "projection_path": projection_path,
        "metadata_path": metadata_path,
        "projection_digest": "",
        "accepted_digest": accepted_digest,
        "target_board_id": target_board_id,
        "planned_actions": [],
        "applied_actions": [],
        "mutation_ledger": [],
        "before_inventory": [],
        "after_inventory": [],
        "blocked_reasons": [],
        "drift_summary": {"total": 0, "by_severity": {"ERROR": 0, "WARN": 0, "INFO": 0}, "by_code": {}, "max_severity": "OK"},
        "evidence": {
            "source": [projection_path] if projection_path else [],
            "desired_state": ["schemas/board-projection.schema.v1.json"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Runtime/live acceptance remains pending.",
                "Issue closure remains deliberate.",
                "Board sync output does not prove user-path acceptance.",
            ],
        },
    }


def _set_project_field_action(*, issue: int, item_id: str, field: str, value: str, metadata: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    field_meta = _field_meta(metadata, field)
    field_id = str(field_meta.get("field_id") or "")
    field_type = str(field_meta.get("type") or "single_select")
    if not field_id:
        return (None, f"FIELD_METADATA_MISSING:{field}")
    action = {
        "type": "set_project_field",
        "issue": issue,
        "field": field,
        "value": value,
        "project_item_id": item_id,
        "field_id": field_id,
        "field_type": field_type,
    }
    if field_type == "single_select":
        options = field_meta.get("options") if isinstance(field_meta.get("options"), dict) else {}
        option_id = str(options.get(value) or "")
        if not option_id:
            return (None, f"FIELD_OPTION_METADATA_MISSING:{field}:{value}")
        action["option_id"] = option_id
    elif field_type == "text":
        action["text"] = value
    else:
        return (None, f"FIELD_TYPE_UNSUPPORTED:{field}:{field_type}")
    return (action, None)


def _planned_actions(projection: dict[str, Any], metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    planned: list[dict[str, Any]] = []
    blocked: list[str] = []
    before: list[dict[str, Any]] = []
    observed = _observed_by_issue(projection)
    expected_items = projection.get("expected_items") if isinstance(projection.get("expected_items"), list) else []
    for item in expected_items:
        if not isinstance(item, dict):
            continue
        issue = _issue_number(item)
        if issue is None:
            continue
        desired = item.get("desired_fields") if isinstance(item.get("desired_fields"), dict) else {}
        if desired.get("Status") == "Done":
            blocked.append(f"DONE_AUTOMATION_FORBIDDEN:{issue}")
            continue
        observed_item = observed.get(issue)
        if not observed_item:
            blocked.append(f"MISSING_BOARD_ITEM_APPLY_DEFERRED:{issue}")
            continue
        metadata_item = _metadata_item(metadata, issue)
        project_item_id = str(metadata_item.get("project_item_id") or observed_item.get("item_id") or "")
        if not project_item_id:
            blocked.append(f"PROJECT_ITEM_ID_MISSING:{issue}")
            continue
        before.append({"issue": issue, "item_id": project_item_id, "fields": observed_item.get("fields", {}), "labels": observed_item.get("labels", [])})
        observed_fields = observed_item.get("fields") if isinstance(observed_item.get("fields"), dict) else {}
        for field, value in desired.items():
            value_s = str(value)
            if str(observed_fields.get(field) or "") == value_s:
                continue
            action, error = _set_project_field_action(issue=issue, item_id=project_item_id, field=field, value=value_s, metadata=metadata)
            if error:
                blocked.append(f"{error}:{issue}")
                continue
            if action is not None:
                planned.append(action)
        observed_labels = {str(x) for x in observed_item.get("labels", []) if isinstance(x, str)}
        for label in item.get("desired_labels", []):
            label_s = str(label)
            if label_s and label_s not in observed_labels:
                planned.append({"type": "add_label", "issue": issue, "label": label_s})
    return (planned, blocked, before)


def _cmd_for_action(action: dict[str, Any], *, repo: str, project_id: str, gh_bin: str) -> list[str]:
    if action.get("type") == "set_project_field":
        cmd = [
            gh_bin,
            "project",
            "item-edit",
            "--project-id",
            project_id,
            "--id",
            str(action.get("project_item_id")),
            "--field-id",
            str(action.get("field_id")),
        ]
        if action.get("field_type") == "single_select":
            cmd.extend(["--single-select-option-id", str(action.get("option_id"))])
        elif action.get("field_type") == "text":
            cmd.extend(["--text", str(action.get("text") or action.get("value") or "")])
        return cmd
    if action.get("type") == "add_label":
        return [
            gh_bin,
            "issue",
            "edit",
            str(action.get("issue")),
            "--repo",
            repo,
            "--add-label",
            str(action.get("label")),
        ]
    raise ValueError(f"unsupported action: {action.get('type')}")


def run_board_sync(args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    projection_path = str(getattr(args, "projection", "") or "")
    metadata_path = str(getattr(args, "metadata", "") or "")
    accepted_digest = str(getattr(args, "accepted_digest", "") or "")
    target_board_id = str(getattr(args, "target_board_id", "") or "")
    token_env = str(getattr(args, "token_env", "") or "GITHUB_TOKEN")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    confirm = str(getattr(args, "apply_confirm", "") or "")
    report = _base_report(
        mode=mode,
        projection_path=projection_path,
        metadata_path=metadata_path,
        accepted_digest=accepted_digest,
        target_board_id=target_board_id,
    )
    if mode not in {"report", "dry-run", "apply"}:
        report["blocked_reasons"].append(f"invalid mode: {mode}")
        return finish_report(report, status="BLOCKED")
    projection, error = _load_json(projection_path)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="ERROR")
    schema_errors = _schema_errors(projection)
    if schema_errors:
        report["blocked_reasons"].append("BOARD_PROJECTION_SCHEMA_INVALID")
        report["schema_errors"] = schema_errors
        return finish_report(report, status="ERROR")
    metadata, error = _load_json(metadata_path)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="ERROR")
    if metadata_path:
        report["evidence"]["source"].append(metadata_path)
    projection_digest = str(projection.get("digest", {}).get("value") if isinstance(projection.get("digest"), dict) else "")
    report["projection_digest"] = projection_digest
    drift = projection.get("drift") if isinstance(projection.get("drift"), list) else []
    report["drift_summary"] = summarize_drift([item for item in drift if isinstance(item, dict)])
    metadata_project_id = str(metadata.get("project_id") or "")
    metadata_board_title = str(metadata.get("board_title") or "")
    repo = str(projection.get("repo") or "")
    report["repo"] = repo
    report["board_title"] = str(projection.get("board_title") or "")

    if not accepted_digest:
        report["blocked_reasons"].append("ACCEPTED_DIGEST_REQUIRED")
    elif accepted_digest != projection_digest:
        report["blocked_reasons"].append("ACCEPTED_DIGEST_MISMATCH")
    if not target_board_id:
        report["blocked_reasons"].append("TARGET_BOARD_ID_REQUIRED")
    elif target_board_id != metadata_project_id:
        report["blocked_reasons"].append("TARGET_BOARD_ID_MISMATCH")
    if metadata_board_title and metadata_board_title != report.get("board_title"):
        report["blocked_reasons"].append("TARGET_BOARD_TITLE_MISMATCH")
    if report["drift_summary"].get("by_severity", {}).get("ERROR", 0):
        report["blocked_reasons"].append("ERROR_DRIFT_BLOCKS_SYNC_APPLY")

    planned, planned_blocks, before = _planned_actions(projection, metadata)
    report["planned_actions"] = planned
    report["before_inventory"] = before
    report["blocked_reasons"].extend(planned_blocks)

    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    if not planned:
        report["noop"] = True
        report["evidence"]["runtime_live"].append("projection already matches observed board state; no sync actions required")
        return finish_report(report, status="OK")
    if mode != "apply":
        return finish_report(report, status="OK")
    report["inputs"] = {
        "apply_confirmation_required": APPLY_CONFIRMATION,
        "apply_confirmation_present": confirm == APPLY_CONFIRMATION,
        "token_env": token_env,
    }
    if confirm != APPLY_CONFIRMATION:
        report["blocked_reasons"].append("APPLY_CONFIRMATION_REQUIRED")
    if not token_present(token_env):
        report["blocked_reasons"].append(f"TOKEN_ENV_MISSING:{token_env}")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
    if report["blocked_reasons"]:
        report["applied_actions"] = []
        return finish_report(report, status="BLOCKED")

    applied: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    for action in planned:
        cmd = _cmd_for_action(action, repo=repo, project_id=metadata_project_id, gh_bin=gh_bin)
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=gh_subprocess_env(token_env))
        entry = {
            "type": action.get("type"),
            "issue": action.get("issue"),
            "field": action.get("field"),
            "value": action.get("value") or action.get("label"),
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[:500],
        }
        ledger.append(
            {
                "issue": action.get("issue"),
                "action": action.get("type"),
                "field": action.get("field"),
                "value": action.get("value") or action.get("label"),
                "before": "recorded in before_inventory",
                "after": "gh command completed" if proc.returncode == 0 else "gh command failed; manual recovery required",
            }
        )
        if proc.returncode != 0:
            entry["stderr"] = (proc.stderr or "").strip()[:500]
            report["applied_actions"] = applied + [entry]
            report["mutation_ledger"] = ledger
            report["blocked_reasons"].append(f"GH_COMMAND_FAILED:{action.get('type')}")
            report["recovery_note"] = "Stop further sync. Inspect mutation_ledger and rerun dry-run before retry."
            return finish_report(report, status="ERROR")
        applied.append({k: v for k, v in entry.items() if v not in (None, "", [])})
        after.append({"issue": action.get("issue"), "action": action.get("type"), "field": action.get("field"), "value": action.get("value") or action.get("label")})
    report["applied_actions"] = applied
    report["mutation_ledger"] = ledger
    report["after_inventory"] = after
    report["evidence"]["runtime_live"].append("gh command execution completed")
    report["recovery_note"] = "If live board state differs, rerun board-sync in dry-run and compare before/after inventory."
    return finish_report(report, status="OK")


def write_board_sync_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_board_sync(payload: dict[str, Any]) -> str:
    return dump_json(payload)
