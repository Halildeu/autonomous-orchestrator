from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.drift import derive_projection_drift, summarize_drift
from src.ops.board.gh_env import gh_subprocess_env
from src.ops.board.models import BOARD_TITLE_DEFAULT, REQUIRED_FIELDS, REQUIRED_LABELS
from src.ops.board.projection import _schema_errors
from src.ops.board.reports import dump_json, finish_report, now_iso

READ_ONLY_PREFIXES = {
    ("auth", "status"),
    ("issue", "list"),
    ("project", "item-list"),
    ("project", "field-list"),
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


def _json_loads(text: str, *, default: Any) -> tuple[Any, str | None]:
    try:
        payload = json.loads(text or "")
    except Exception as exc:
        return (default, f"json parse failed: {exc.__class__.__name__}")
    return (payload, None)


def _run_gh(report: dict[str, Any], gh_bin: str, args: list[str], *, token_env: str) -> tuple[Any, str | None]:
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
    default: Any = [] if args[:2] == ["issue", "list"] else {}
    return _json_loads(proc.stdout, default=default)


def _base_wrapper(*, mode: str) -> dict[str, Any]:
    return {
        "version": "v1",
        "command": "board-projection-live",
        "mode": mode,
        "status": "OK",
        "projection_path": "",
        "read_only_commands": [],
        "applied_actions": [],
        "blocked_reasons": [],
        "drift_summary": {"total": 0, "by_severity": {"ERROR": 0, "WARN": 0, "INFO": 0}, "by_code": {}, "max_severity": "OK"},
        "evidence": {
            "source": [],
            "desired_state": ["schemas/board-projection.schema.v1.json"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Live projection generation does not apply board mutations.",
                "Runtime or user-path acceptance is not proven by projection.",
                "Issue closure and Done automation remain out of scope.",
            ],
        },
    }


def _labels_from_issue(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels") if isinstance(issue.get("labels"), list) else []
    names = [str(label.get("name")) for label in labels if isinstance(label, dict) and label.get("name")]
    return sorted(set(names))


def _fields_from_body(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field in REQUIRED_FIELDS:
        match = re.search(rf"^\*\*{re.escape(field)}:\*\*\s*(.+?)\s*$", body, flags=re.MULTILINE)
        if match:
            fields[field] = match.group(1).strip()
    return fields


def _ssot_ref_from_body(body: str) -> str:
    marker = re.search(r"\*\*SSOT refs:\*\*\s*(?P<body>.*?)(?:\n\n|$)", body, flags=re.DOTALL)
    if not marker:
        return "docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md"
    for line in marker.group("body").splitlines():
        line = line.strip()
        if line.startswith("- "):
            return line[2:].strip()
    return "docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md"


def _stable_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _expected_digest(item: dict[str, Any]) -> str:
    payload = {
        "issue_number": item.get("issue_number"),
        "ssot_ref": item.get("ssot_ref"),
        "desired_fields": item.get("desired_fields"),
        "desired_labels": item.get("desired_labels"),
        "relation_policy": item.get("relation_policy"),
        "evidence_requirements": item.get("evidence_requirements"),
        "digest_inputs": item.get("digest_inputs"),
    }
    return "sha256:" + _stable_digest(payload)


def _expected_items(repo: str, issues: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for issue in issues if isinstance(issues, list) else []:
        if not isinstance(issue, dict):
            continue
        labels = _labels_from_issue(issue)
        if "project-roadmap" not in labels:
            continue
        body = str(issue.get("body") or "")
        desired_fields = _fields_from_body(body)
        item = {
            "issue_number": int(issue.get("number")),
            "title": str(issue.get("title") or ""),
            "ssot_ref": _ssot_ref_from_body(body),
            "owner_repo": repo,
            "desired_fields": {field: desired_fields.get(field, "") for field in REQUIRED_FIELDS},
            "desired_labels": labels,
            "relation_policy": {
                "pr_relation": "Tracked by",
                "close_keyword_allowed": False,
                "default_post_merge_status": "Needs Verify",
            },
            "claim_policy": {
                "claimable": desired_fields.get("Status") == "Todo" and desired_fields.get("Kind") != "umbrella",
                "non_claimable_reasons": [] if desired_fields.get("Status") == "Todo" else ["status_not_todo"],
            },
            "evidence_requirements": {
                "source": "required-before-needs-verify",
                "desired_state": "required-when-config-or-gitops",
                "runtime_live": "required-before-done-when-runtime",
                "browser_user_path": "required-before-done-when-user-facing",
                "does_not_prove": "required",
            },
            "digest_inputs": {
                "issue_body_agent_state": "agent-state:v1" in body,
                "field_contract_version": "v1",
                "pr_contract_version": "v1",
            },
            "digest": "",
        }
        item["digest"] = _expected_digest(item)
        out.append(item)
    return sorted(out, key=lambda item: int(item["issue_number"]))


def _observed_items(item_payload: Any) -> list[dict[str, Any]]:
    raw_items = item_payload.get("items") if isinstance(item_payload, dict) and isinstance(item_payload.get("items"), list) else []
    out: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        number = content.get("number") or item.get("issue_number")
        try:
            issue_number = int(number)
        except Exception:
            continue
        labels = item.get("labels") if isinstance(item.get("labels"), list) else []
        fields = {
            "Status": item.get("status"),
            "Faz": item.get("faz"),
            "Track": item.get("track"),
            "Priority": item.get("priority"),
            "Kind": item.get("kind"),
        }
        out.append(
            {
                "source": "github_project",
                "item_id": str(item.get("id") or ""),
                "issue_number": issue_number,
                "title": str(content.get("title") or item.get("title") or ""),
                "fields": {key: value for key, value in fields.items() if value not in (None, "")},
                "labels": sorted({str(label) for label in labels if isinstance(label, str)}),
                "url": str(content.get("url") or ""),
            }
        )
    return sorted(out, key=lambda item: int(item["issue_number"]))


def _value_mismatch_drift(expected: list[dict[str, Any]], observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_issue = {item.get("issue_number"): item for item in observed}
    drift: list[dict[str, Any]] = []
    for item in expected:
        observed_item = by_issue.get(item.get("issue_number"))
        if not observed_item:
            continue
        expected_fields = item.get("desired_fields") if isinstance(item.get("desired_fields"), dict) else {}
        observed_fields = observed_item.get("fields") if isinstance(observed_item.get("fields"), dict) else {}
        for field in REQUIRED_FIELDS:
            expected_value = str(expected_fields.get(field) or "")
            observed_value = str(observed_fields.get(field) or "")
            if expected_value and observed_value and expected_value != observed_value:
                drift.append(
                    {
                        "code": "DIGEST_MISMATCH",
                        "severity": "WARN",
                        "message": f"observed {field} differs from expected issue body field",
                        "issue_number": item.get("issue_number"),
                        "expected": expected_value,
                        "observed": observed_value,
                    }
                )
        expected_labels = set(str(label) for label in item.get("desired_labels", []) if isinstance(label, str))
        observed_labels = set(str(label) for label in observed_item.get("labels", []) if isinstance(label, str))
        missing = sorted(expected_labels - observed_labels)
        if missing:
            drift.append(
                {
                    "code": "DIGEST_MISMATCH",
                    "severity": "WARN",
                    "message": "observed labels differ from expected issue labels",
                    "issue_number": item.get("issue_number"),
                    "expected": sorted(expected_labels),
                    "observed": sorted(observed_labels),
                }
            )
    return drift


def build_live_projection(args: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    mode = str(getattr(args, "mode", "report") or "report")
    wrapper = _base_wrapper(mode=mode)
    if mode == "apply":
        wrapper["blocked_reasons"].append("APPLY_NOT_SUPPORTED_FOR_LIVE_PROJECTION")
        return (finish_report(wrapper, status="BLOCKED"), None)
    if mode not in {"report", "dry-run"}:
        wrapper["blocked_reasons"].append(f"invalid mode: {mode}")
        return (finish_report(wrapper, status="BLOCKED"), None)
    repo = str(getattr(args, "repo", "") or "")
    board_title = str(getattr(args, "board_title", "") or BOARD_TITLE_DEFAULT)
    owner = str(getattr(args, "project_owner", "") or (repo.split("/", 1)[0] if "/" in repo else ""))
    number = str(getattr(args, "project_number", "") or "")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    token_env = str(getattr(args, "token_env", "") or "")
    if not repo or "/" not in repo:
        wrapper["blocked_reasons"].append("REPO_REQUIRED")
    if not owner:
        wrapper["blocked_reasons"].append("PROJECT_OWNER_REQUIRED")
    if not number:
        wrapper["blocked_reasons"].append("PROJECT_NUMBER_REQUIRED")
    if not _gh_available(gh_bin):
        wrapper["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
    if wrapper["blocked_reasons"]:
        return (finish_report(wrapper, status="BLOCKED"), None)

    _auth, error = _run_gh(wrapper, gh_bin, ["auth", "status"], token_env=token_env)
    if error:
        wrapper["blocked_reasons"].append(error)
        return (finish_report(wrapper, status="BLOCKED"), None)
    issues, error = _run_gh(
        wrapper,
        gh_bin,
        ["issue", "list", "--repo", repo, "--state", "all", "--label", "project-roadmap", "--limit", "100", "--json", "number,title,labels,url,body,state"],
        token_env=token_env,
    )
    if error:
        wrapper["blocked_reasons"].append(error)
        return (finish_report(wrapper, status="BLOCKED"), None)
    _fields, error = _run_gh(wrapper, gh_bin, ["project", "field-list", number, "--owner", owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        wrapper["blocked_reasons"].append(error)
        return (finish_report(wrapper, status="BLOCKED"), None)
    project_items, error = _run_gh(wrapper, gh_bin, ["project", "item-list", number, "--owner", owner, "--format", "json", "--limit", "100"], token_env=token_env)
    if error:
        wrapper["blocked_reasons"].append(error)
        return (finish_report(wrapper, status="BLOCKED"), None)

    expected = _expected_items(repo, issues)
    observed = _observed_items(project_items)
    projection = {
        "version": "v1",
        "kind": "board_projection",
        "generated_at": now_iso(),
        "repo": repo,
        "board_title": board_title,
        "mode": mode,
        "authority": {
            "repo_ssot_is_authority": True,
            "board_is_authority": False,
            "issue_body_is_handoff_surface": True,
        },
        "source_refs": [
            {"kind": "query", "value": "gh issue list --label project-roadmap"},
            {"kind": "query", "value": f"gh project item-list {number} --owner {owner}"},
            {"kind": "path", "value": "docs/OPERATIONS/BOARD-PROJECTION-MANIFEST.v1.md"},
        ],
        "field_contract": {
            "required_fields": list(REQUIRED_FIELDS),
            "required_labels": list(REQUIRED_LABELS),
        },
        "expected_items": expected,
        "observed_board_items": observed,
        "drift": _value_mismatch_drift(expected, observed),
        "digest": {
            "algorithm": "sha256",
            "canonicalization": "json-stable-sort-v1",
            "value": "",
        },
        "evidence": {
            "source": ["GitHub issues with project-roadmap", f"GitHub ProjectV2 {owner}#{number}"],
            "desired_state": ["schemas/board-projection.schema.v1.json"],
            "runtime_live": ["gh issue list completed", "gh project field-list completed", "gh project item-list completed"],
            "browser_user_path": [],
            "does_not_prove": [
                "Live projection generation does not apply board mutations.",
                "Runtime or user-path acceptance is not proven by projection.",
                "Issue closure and Done automation remain out of scope.",
            ],
        },
    }
    projection["drift"] = derive_projection_drift(projection)
    projection["digest"]["value"] = _stable_digest(
        {
            "repo": projection["repo"],
            "board_title": projection["board_title"],
            "source_refs": projection["source_refs"],
            "expected_items": projection["expected_items"],
            "observed_board_items": projection["observed_board_items"],
            "drift": projection["drift"],
        }
    )
    errors = _schema_errors(projection)
    if errors:
        wrapper["blocked_reasons"].append("BOARD_PROJECTION_SCHEMA_INVALID")
        wrapper["schema_errors"] = errors
        return (finish_report(wrapper, status="ERROR"), projection)
    summary = summarize_drift(projection["drift"])
    wrapper["drift_summary"] = summary
    wrapper["status"] = "OK" if not projection["drift"] else "WARN"
    wrapper["projection_digest"] = projection["digest"]["value"]
    wrapper["expected_count"] = len(expected)
    wrapper["observed_count"] = len(observed)
    wrapper["evidence"]["runtime_live"] = list(projection["evidence"]["runtime_live"])
    return (finish_report(wrapper, status=str(wrapper["status"])), projection)


def dump_board_live_projection(payload: dict[str, Any]) -> str:
    return dump_json(payload)
