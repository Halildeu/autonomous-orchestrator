from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.gh_env import gh_subprocess_env
from src.ops.board.models import BOARD_TITLE_DEFAULT
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic

READ_ONLY_PREFIXES = {
    ("auth", "status"),
    ("project", "field-list"),
    ("project", "item-list"),
}


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _safe_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "<redacted-token>", text)
    text = re.sub(r"(?i)(token:\s*)([A-Za-z0-9_.\-]+)", r"\1<redacted>", text)
    return text.strip()[:1000]


def _json_loads(text: str) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(text or "{}")
    except Exception as exc:
        return ({}, f"json parse failed: {exc.__class__.__name__}")
    if not isinstance(payload, dict):
        return ({}, "json root must be object")
    return (payload, None)


def _run_gh(report: dict[str, Any], gh_bin: str, args: list[str], *, token_env: str) -> tuple[dict[str, Any], str | None]:
    key = (args[0], args[1]) if len(args) >= 2 else ("", "")
    command_name = " ".join(args[:2])
    if key not in READ_ONLY_PREFIXES:
        return ({}, f"FORBIDDEN_READ_COMMAND:{command_name}")
    report["read_only_commands"].append(command_name)
    proc = subprocess.run([gh_bin, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=gh_subprocess_env(token_env))
    if proc.returncode != 0:
        return ({}, f"GH_COMMAND_FAILED:{command_name}:{_safe_text(proc.stderr or proc.stdout)}")
    if args[:2] == ["auth", "status"]:
        return ({"raw": _safe_text("\n".join(part for part in (proc.stdout, proc.stderr) if part))}, None)
    return _json_loads(proc.stdout)


def _digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _base_report(*, mode: str, repo: str, board_title: str, owner: str, number: str, project_id: str) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "command": "board-metadata-live",
        "mode": mode,
        "status": "OK",
        "started_at": started,
        "completed_at": started,
        "repo": repo,
        "board_title": board_title,
        "project_owner": owner,
        "project_number": number,
        "project_id": project_id,
        "metadata_path": "",
        "metadata_digest": "",
        "read_only_commands": [],
        "applied_actions": [],
        "blocked_reasons": [],
        "evidence": {
            "source": [f"GitHub ProjectV2 {owner}#{number}"],
            "desired_state": ["ProjectV2 field and item id map for board-sync"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Metadata map generation does not apply board mutations.",
                "Sync apply and issue closure remain out of scope.",
            ],
        },
    }


def _fields_map(field_payload: dict[str, Any]) -> dict[str, Any]:
    fields = field_payload.get("fields") if isinstance(field_payload.get("fields"), list) else []
    out: dict[str, Any] = {}
    for field in fields:
        if not isinstance(field, dict) or not field.get("name") or not field.get("id"):
            continue
        field_type = "single_select" if str(field.get("type") or "") == "ProjectV2SingleSelectField" else "text"
        options_raw = field.get("options") if isinstance(field.get("options"), list) else []
        options = {
            str(option.get("name")): str(option.get("id"))
            for option in options_raw
            if isinstance(option, dict) and option.get("name") and option.get("id")
        }
        item: dict[str, Any] = {"field_id": str(field["id"]), "type": field_type}
        if options:
            item["options"] = options
        out[str(field["name"])] = item
    return out


def _items_map(item_payload: dict[str, Any]) -> dict[str, Any]:
    items = item_payload.get("items") if isinstance(item_payload.get("items"), list) else []
    out: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        number = content.get("number") or item.get("issue_number")
        if number is None:
            continue
        out[str(number)] = {
            "project_item_id": str(item["id"]),
            "title": str(content.get("title") or item.get("title") or ""),
            "url": str(content.get("url") or ""),
        }
    return out


def build_live_metadata(args: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    mode = str(getattr(args, "mode", "report") or "report")
    repo = str(getattr(args, "repo", "") or "")
    board_title = str(getattr(args, "board_title", "") or BOARD_TITLE_DEFAULT)
    owner = str(getattr(args, "project_owner", "") or (repo.split("/", 1)[0] if "/" in repo else ""))
    number = str(getattr(args, "project_number", "") or "")
    project_id = str(getattr(args, "project_id", "") or "")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    token_env = str(getattr(args, "token_env", "") or "")
    report = _base_report(mode=mode, repo=repo, board_title=board_title, owner=owner, number=number, project_id=project_id)
    if mode == "apply":
        report["blocked_reasons"].append("APPLY_NOT_SUPPORTED_FOR_BOARD_METADATA_LIVE")
        return (finish_report(report, status="BLOCKED"), None)
    if mode not in {"report", "dry-run"}:
        report["blocked_reasons"].append(f"invalid mode: {mode}")
    if not owner:
        report["blocked_reasons"].append("PROJECT_OWNER_REQUIRED")
    if not number:
        report["blocked_reasons"].append("PROJECT_NUMBER_REQUIRED")
    if not project_id:
        report["blocked_reasons"].append("PROJECT_ID_REQUIRED")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
    if report["blocked_reasons"]:
        return (finish_report(report, status="BLOCKED"), None)

    _auth, error = _run_gh(report, gh_bin, ["auth", "status"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return (finish_report(report, status="BLOCKED"), None)
    field_payload, error = _run_gh(report, gh_bin, ["project", "field-list", number, "--owner", owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return (finish_report(report, status="BLOCKED"), None)
    item_payload, error = _run_gh(report, gh_bin, ["project", "item-list", number, "--owner", owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return (finish_report(report, status="BLOCKED"), None)
    metadata = {
        "version": "v1",
        "board_title": board_title,
        "project_owner": owner,
        "project_number": number,
        "project_id": project_id,
        "fields": _fields_map(field_payload),
        "items": _items_map(item_payload),
    }
    metadata["digest"] = {"algorithm": "sha256", "value": _digest(metadata)}
    report["metadata_digest"] = metadata["digest"]["value"]
    report["field_count"] = len(metadata["fields"])
    report["item_count"] = len(metadata["items"])
    report["evidence"]["runtime_live"] = ["gh project field-list completed", "gh project item-list completed"]
    return (finish_report(report, status="OK"), metadata)


def write_board_metadata(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_board_metadata(payload: dict[str, Any]) -> str:
    return dump_json(payload)
