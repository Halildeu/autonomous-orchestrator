from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.gh_env import gh_subprocess_env, token_present
from src.ops.board.models import BOARD_TITLE_DEFAULT, REQUIRED_LABELS
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic

SEED_CONFIRMATION = "APPLY_BOARD_GOVERNANCE_BOG_7A"
LABEL_DEFAULTS = {
    "project-roadmap": ("5319e7", "Board ingestion gate for repo-authoritative roadmap work"),
    "risk": ("d73a4a", "Board-visible risk or RAID item"),
    "gate": ("fbca04", "Board-visible readiness or acceptance gate"),
    "needs-verification": ("0e8a16", "Source-ready; acceptance evidence pending"),
    "blocked": ("b60205", "Blocked by an external dependency or decision"),
    "security": ("ee0701", "Security-sensitive work"),
    "quality": ("c5def5", "Quality, test, validation, or evidence work"),
}
READ_ONLY_PREFIXES = {
    ("auth", "status"),
    ("label", "list"),
    ("issue", "list"),
    ("project", "field-list"),
    ("project", "item-list"),
}
MUTATION_PREFIXES = {
    ("label", "create"),
    ("issue", "create"),
    ("issue", "edit"),
    ("project", "item-add"),
    ("project", "item-edit"),
}
FIELD_NAMES = ("Status", "Faz", "Track", "Priority", "Kind")


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _safe_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "<redacted-token>", text)
    text = re.sub(r"(?i)(token:\s*)([A-Za-z0-9_.\-]+)", r"\1<redacted>", text)
    return text.strip()[:1000]


def _json_loads(text: str, *, default: Any) -> tuple[Any, str | None]:
    try:
        payload = json.loads(text or "")
    except Exception as exc:
        return (default, f"json parse failed: {exc.__class__.__name__}")
    return (payload, None)


def _load_seed(path_value: str) -> tuple[dict[str, Any], str | None]:
    path = Path(str(path_value or "").strip())
    if not path.exists():
        return ({}, f"seed file not found: {path.as_posix()}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ({}, f"seed parse failed: {exc.__class__.__name__}")
    if not isinstance(payload, dict):
        return ({}, "seed root must be object")
    return (payload, None)


def _seed_digest(seed: dict[str, Any], *, project_owner: str, project_number: str, project_id: str) -> str:
    payload = {
        "version": seed.get("version"),
        "kind": seed.get("kind"),
        "repo": seed.get("repo"),
        "board_title": seed.get("board_title"),
        "project_owner": project_owner,
        "project_number": project_number,
        "project_id": project_id,
        "items": seed.get("items", []),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _base_report(*, mode: str, seed_path: str, repo: str, board_title: str, project_owner: str, project_number: str, project_id: str, accepted_digest: str) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "command": "board-seed",
        "mode": mode,
        "status": "OK",
        "started_at": started,
        "completed_at": started,
        "seed_path": seed_path,
        "repo": repo,
        "board_title": board_title or BOARD_TITLE_DEFAULT,
        "project_owner": project_owner,
        "project_number": project_number,
        "project_id": project_id,
        "seed_digest": "",
        "accepted_digest": accepted_digest,
        "read_only_commands": [],
        "mutation_commands": [],
        "planned_actions": [],
        "applied_actions": [],
        "mutation_ledger": [],
        "blocked_reasons": [],
        "evidence": {
            "source": [seed_path] if seed_path else [],
            "desired_state": ["GitHub issue and ProjectV2 seed item are traceable to repo SSOT"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Issue creation does not prove implementation completion.",
                "ProjectV2 item field population does not prove runtime or user-path acceptance.",
                "No issue closure or Done automation is performed.",
            ],
        },
    }


def _derive_owner(repo: str, owner: str) -> str:
    if owner:
        return owner
    if "/" in repo:
        return repo.split("/", 1)[0]
    return ""


def _run_gh(report: dict[str, Any], gh_bin: str, args: list[str], *, mutation: bool, token_env: str) -> tuple[Any, str | None]:
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
    if args[:2] in (["label", "create"], ["issue", "create"], ["issue", "edit"]):
        return ({"raw": _safe_text(proc.stdout)}, None)
    default: Any = [] if args[:2] in (["label", "list"], ["issue", "list"]) else {}
    return _json_loads(proc.stdout, default=default)


def _validate_seed(seed: dict[str, Any], report: dict[str, Any]) -> None:
    if seed.get("version") != "v1":
        report["blocked_reasons"].append("SEED_VERSION_INVALID")
    if seed.get("kind") != "board_seed":
        report["blocked_reasons"].append("SEED_KIND_INVALID")
    items = seed.get("items") if isinstance(seed.get("items"), list) else []
    if not items:
        report["blocked_reasons"].append("SEED_ITEMS_REQUIRED")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            report["blocked_reasons"].append(f"SEED_ITEM_INVALID:{index}")
            continue
        for field in ("title", "body", "desired_fields", "desired_labels", "ssot_refs"):
            if not item.get(field):
                report["blocked_reasons"].append(f"SEED_ITEM_MISSING_{field.upper()}:{index}")
        fields = item.get("desired_fields") if isinstance(item.get("desired_fields"), dict) else {}
        for field in FIELD_NAMES:
            if not fields.get(field):
                report["blocked_reasons"].append(f"SEED_ITEM_MISSING_FIELD_{field}:{index}")
        if fields.get("Status") == "Done":
            report["blocked_reasons"].append(f"DONE_AUTOMATION_FORBIDDEN:{index}")
        labels = {str(label) for label in item.get("desired_labels", []) if isinstance(label, str)}
        if "project-roadmap" not in labels:
            report["blocked_reasons"].append(f"PROJECT_ROADMAP_LABEL_REQUIRED:{index}")


def _planned_actions(seed: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    needed_labels = set(REQUIRED_LABELS)
    for item in seed.get("items", []):
        if isinstance(item, dict):
            needed_labels.update(str(label) for label in item.get("desired_labels", []) if isinstance(label, str))
    for label in sorted(needed_labels):
        actions.append({"type": "ensure_label", "label": label})
    for item in seed.get("items", []):
        if not isinstance(item, dict):
            continue
        actions.append({"type": "ensure_issue", "title": item.get("title"), "labels": item.get("desired_labels", [])})
        actions.append({"type": "ensure_project_item", "title": item.get("title")})
        for field, value in (item.get("desired_fields") or {}).items():
            actions.append({"type": "set_project_field", "title": item.get("title"), "field": field, "value": value})
    return actions


def _labels_by_name(payload: Any) -> set[str]:
    labels = payload if isinstance(payload, list) else []
    return {str(item.get("name")) for item in labels if isinstance(item, dict) and item.get("name")}


def _issues_by_title(payload: Any) -> dict[str, dict[str, Any]]:
    issues = payload if isinstance(payload, list) else []
    out: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if isinstance(issue, dict) and issue.get("title"):
            out[str(issue["title"])] = issue
    return out


def _field_map(payload: Any) -> dict[str, dict[str, Any]]:
    fields = payload.get("fields") if isinstance(payload, dict) and isinstance(payload.get("fields"), list) else []
    return {str(field["name"]): field for field in fields if isinstance(field, dict) and field.get("name")}


def _option_id(field: dict[str, Any], value: str) -> str:
    options = field.get("options") if isinstance(field.get("options"), list) else []
    for option in options:
        if isinstance(option, dict) and str(option.get("name") or "") == value:
            return str(option.get("id") or "")
    return ""


def _project_item_by_issue(payload: Any, issue_number: int, issue_url: str) -> dict[str, Any]:
    items = payload.get("items") if isinstance(payload, dict) and isinstance(payload.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        number = content.get("number") or item.get("content_number") or item.get("issue_number")
        url = str(content.get("url") or item.get("content_url") or item.get("url") or "")
        if str(number) == str(issue_number) or (issue_url and url == issue_url):
            return item
    return {}


def _issue_number_from_url(url: str) -> int | None:
    match = re.search(r"/issues/(\d+)(?:$|[/?#])", url)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _label_cmd(repo: str, label: str) -> list[str]:
    color, description = LABEL_DEFAULTS.get(label, ("ededed", "Board governance label"))
    return ["label", "create", label, "--repo", repo, "--color", color, "--description", description]


def _issue_body(item: dict[str, Any]) -> str:
    return str(item.get("body") or "").strip()


def _ensure_labels(report: dict[str, Any], gh_bin: str, repo: str, labels: set[str], existing: set[str], token_env: str) -> bool:
    for label in sorted(labels - existing):
        _payload, error = _run_gh(report, gh_bin, _label_cmd(repo, label), mutation=True, token_env=token_env)
        if error:
            report["blocked_reasons"].append(error)
            return False
        report["applied_actions"].append({"type": "create_label", "label": label})
        report["mutation_ledger"].append({"action": "create_label", "label": label, "after": "gh command completed"})
    return True


def _set_project_fields(report: dict[str, Any], gh_bin: str, item_id: str, fields_meta: dict[str, dict[str, Any]], desired: dict[str, Any], token_env: str) -> bool:
    for field_name in FIELD_NAMES:
        value = str(desired.get(field_name) or "")
        field = fields_meta.get(field_name, {})
        field_id = str(field.get("id") or "")
        option_id = _option_id(field, value)
        if not field_id or not option_id:
            report["blocked_reasons"].append(f"FIELD_OPTION_METADATA_MISSING:{field_name}:{value}")
            return False
        _payload, error = _run_gh(
            report,
            gh_bin,
            [
                "project",
                "item-edit",
                "--project-id",
                str(report["project_id"]),
                "--id",
                item_id,
                "--field-id",
                field_id,
                "--single-select-option-id",
                option_id,
                "--format",
                "json",
            ],
            mutation=True,
            token_env=token_env,
        )
        if error:
            report["blocked_reasons"].append(error)
            return False
        report["applied_actions"].append({"type": "set_project_field", "field": field_name, "value": value})
        report["mutation_ledger"].append({"action": "set_project_field", "field": field_name, "value": value, "after": "gh command completed"})
    return True


def _apply_seed(report: dict[str, Any], seed: dict[str, Any], gh_bin: str, token_env: str) -> dict[str, Any]:
    repo = str(report["repo"])
    owner = str(report["project_owner"])
    number = str(report["project_number"])
    _auth, error = _run_gh(report, gh_bin, ["auth", "status"], mutation=False, token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    label_payload, error = _run_gh(report, gh_bin, ["label", "list", "--repo", repo, "--limit", "200", "--json", "name"], mutation=False, token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    issue_payload, error = _run_gh(report, gh_bin, ["issue", "list", "--repo", repo, "--state", "all", "--limit", "100", "--json", "number,title,labels,url,state"], mutation=False, token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    field_payload, error = _run_gh(report, gh_bin, ["project", "field-list", number, "--owner", owner, "--format", "json", "--limit", "100"], mutation=False, token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")
    item_payload, error = _run_gh(report, gh_bin, ["project", "item-list", number, "--owner", owner, "--format", "json", "--limit", "100"], mutation=False, token_env=token_env)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="BLOCKED")

    items = [item for item in seed.get("items", []) if isinstance(item, dict)]
    needed_labels = set(REQUIRED_LABELS)
    for item in items:
        needed_labels.update(str(label) for label in item.get("desired_labels", []) if isinstance(label, str))
    if not _ensure_labels(report, gh_bin, repo, needed_labels, _labels_by_name(label_payload), token_env):
        return finish_report(report, status="ERROR")

    issues = _issues_by_title(issue_payload)
    fields_meta = _field_map(field_payload)
    for item in items:
        title = str(item.get("title") or "")
        labels = [str(label) for label in item.get("desired_labels", []) if isinstance(label, str)]
        issue = issues.get(title, {})
        issue_url = str(issue.get("url") or "")
        issue_number = issue.get("number")
        if not issue:
            args = ["issue", "create", "--repo", repo, "--title", title, "--body", _issue_body(item)]
            for label in labels:
                args.extend(["--label", label])
            payload, error = _run_gh(report, gh_bin, args, mutation=True, token_env=token_env)
            if error:
                report["blocked_reasons"].append(error)
                return finish_report(report, status="ERROR")
            issue_url = str(payload.get("raw") or "").strip()
            issue_number = _issue_number_from_url(issue_url)
            report["applied_actions"].append({"type": "create_issue", "title": title, "issue": issue_number, "url": issue_url})
            report["mutation_ledger"].append({"action": "create_issue", "title": title, "after": issue_url})
        else:
            existing_labels = {str(label.get("name")) for label in issue.get("labels", []) if isinstance(label, dict) and label.get("name")}
            missing = sorted(set(labels) - existing_labels)
            if missing and issue_number:
                args = ["issue", "edit", str(issue_number), "--repo", repo]
                for label in missing:
                    args.extend(["--add-label", label])
                _payload, error = _run_gh(report, gh_bin, args, mutation=True, token_env=token_env)
                if error:
                    report["blocked_reasons"].append(error)
                    return finish_report(report, status="ERROR")
                report["applied_actions"].append({"type": "add_issue_labels", "issue": issue_number, "labels": missing})
                report["mutation_ledger"].append({"action": "add_issue_labels", "issue": issue_number, "after": missing})
        if not issue_number or not issue_url:
            report["blocked_reasons"].append(f"ISSUE_IDENTITY_MISSING:{title}")
            return finish_report(report, status="ERROR")
        project_item = _project_item_by_issue(item_payload, int(issue_number), issue_url)
        item_id = str(project_item.get("id") or "")
        if not item_id:
            payload, error = _run_gh(report, gh_bin, ["project", "item-add", number, "--owner", owner, "--url", issue_url, "--format", "json"], mutation=True, token_env=token_env)
            if error:
                report["blocked_reasons"].append(error)
                return finish_report(report, status="ERROR")
            item_id = str(payload.get("id") or "")
            report["applied_actions"].append({"type": "add_project_item", "issue": issue_number, "project_item_id": item_id})
            report["mutation_ledger"].append({"action": "add_project_item", "issue": issue_number, "after": item_id})
        if not item_id:
            report["blocked_reasons"].append(f"PROJECT_ITEM_ID_MISSING:{issue_number}")
            return finish_report(report, status="ERROR")
        if not _set_project_fields(report, gh_bin, item_id, fields_meta, item.get("desired_fields") or {}, token_env):
            return finish_report(report, status="ERROR")
    report["evidence"]["runtime_live"].append("gh board seed mutation commands completed")
    return finish_report(report, status="OK")


def run_board_seed(args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    seed_path = str(getattr(args, "seed", "") or getattr(args, "fixture", "") or "")
    seed, error = _load_seed(seed_path)
    repo = str(getattr(args, "repo", "") or seed.get("repo") or "")
    board_title = str(getattr(args, "board_title", "") or seed.get("board_title") or BOARD_TITLE_DEFAULT)
    project_owner = _derive_owner(repo, str(getattr(args, "project_owner", "") or seed.get("project_owner") or ""))
    project_number = str(getattr(args, "project_number", "") or seed.get("project_number") or "")
    project_id = str(getattr(args, "project_id", "") or seed.get("project_id") or "")
    accepted_digest = str(getattr(args, "accepted_digest", "") or "")
    token_env = str(getattr(args, "token_env", "") or "GITHUB_TOKEN")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    confirm = str(getattr(args, "apply_confirm", "") or "")
    report = _base_report(
        mode=mode,
        seed_path=seed_path,
        repo=repo,
        board_title=board_title,
        project_owner=project_owner,
        project_number=project_number,
        project_id=project_id,
        accepted_digest=accepted_digest,
    )
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="ERROR")
    if mode not in {"report", "dry-run", "apply"}:
        report["blocked_reasons"].append(f"invalid mode: {mode}")
        return finish_report(report, status="BLOCKED")
    if not repo or "/" not in repo:
        report["blocked_reasons"].append("REPO_REQUIRED")
    if not project_owner:
        report["blocked_reasons"].append("PROJECT_OWNER_REQUIRED")
    if not project_number:
        report["blocked_reasons"].append("PROJECT_NUMBER_REQUIRED")
    if not project_id:
        report["blocked_reasons"].append("PROJECT_ID_REQUIRED")
    _validate_seed(seed, report)
    report["seed_digest"] = _seed_digest(seed, project_owner=project_owner, project_number=project_number, project_id=project_id)
    report["planned_actions"] = _planned_actions(seed)
    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    if mode != "apply":
        return finish_report(report, status="OK")
    report["inputs"] = {
        "apply_confirmation_required": SEED_CONFIRMATION,
        "apply_confirmation_present": confirm == SEED_CONFIRMATION,
        "accepted_digest_present": bool(accepted_digest),
        "token_env": token_env,
    }
    if confirm != SEED_CONFIRMATION:
        report["blocked_reasons"].append("APPLY_CONFIRMATION_REQUIRED")
    if not accepted_digest:
        report["blocked_reasons"].append("ACCEPTED_DIGEST_REQUIRED")
    elif accepted_digest != report["seed_digest"]:
        report["blocked_reasons"].append("ACCEPTED_DIGEST_MISMATCH")
    if not token_present(token_env):
        report["blocked_reasons"].append(f"TOKEN_ENV_MISSING:{token_env}")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    return _apply_seed(report, seed, gh_bin, token_env)


def write_board_seed_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_board_seed(payload: dict[str, Any]) -> str:
    return dump_json(payload)
