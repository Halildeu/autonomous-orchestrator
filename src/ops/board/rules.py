from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.ops.board.fixtures import load_fixture
from src.ops.board.models import KINDS, PRIORITIES, REQUIRED_FIELDS, STATUSES, TRACKS
from src.ops.board.reports import base_report, finish_report

_CLOSE_RE = re.compile(r"(?im)^\s*(Closes|Fixes|Resolves)\s+#(?P<issue>[0-9]+)\b")


def _labels(item: dict[str, Any]) -> set[str]:
    labels = item.get("labels")
    if not isinstance(labels, list):
        return set()
    return {str(x) for x in labels if isinstance(x, str)}


def _fields(item: dict[str, Any]) -> dict[str, Any]:
    fields = item.get("fields")
    return fields if isinstance(fields, dict) else {}


def _issue_number(item: dict[str, Any]) -> int | None:
    raw = item.get("number", item.get("issue_number"))
    try:
        value = int(raw)
    except Exception:
        return None
    return value if value > 0 else None


def _has_agent_state(issue: dict[str, Any]) -> bool:
    if isinstance(issue.get("agent_state"), dict):
        return True
    body = issue.get("body")
    return isinstance(body, str) and "agent-state:v1" in body


def _finding(code: str, severity: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {"code": code, "severity": severity, "message": message}
    payload.update({k: v for k, v in extra.items() if v not in (None, "", [])})
    return payload


def _parse_dt(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _active_competing_claims(issue: dict[str, Any], session: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    claims = issue.get("active_claims")
    if not isinstance(claims, list):
        return []
    active: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_session = str(claim.get("session") or "")
        if claim_session == session:
            continue
        exp = _parse_dt(str(claim.get("expires_at") or ""))
        if exp is None or exp > now:
            active.append(claim)
    return active


def _find_issue(fixture: dict[str, Any], issue_number: int) -> dict[str, Any] | None:
    issues = fixture.get("issues")
    if not isinstance(issues, list):
        return None
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        if _issue_number(issue) == issue_number:
            return issue
    return None


def _apply_blocked(report: dict[str, Any]) -> dict[str, Any]:
    report["blocked_reasons"].append("APPLY_MODE_NOT_AVAILABLE_UNTIL_BOG_3C")
    report["planned_actions"] = []
    report["applied_actions"] = []
    return finish_report(report, status="BLOCKED")


def _apply_if_requested(report: dict[str, Any], args: Any) -> dict[str, Any]:
    if report.get("mode") != "apply":
        return report
    if report.get("status") not in {"OK", "WARN"}:
        return report
    from src.ops.board.apply import apply_report

    return apply_report(report, args)


def _load_report_fixture(report: dict[str, Any], fixture_path: str | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    fixture, error = load_fixture(fixture_path)
    if error:
        report["blocked_reasons"].append(error)
        return (finish_report(report, status="ERROR"), None)
    source = str(fixture_path or "").strip()
    if source:
        report["evidence"]["source"].append(source)
    return (report, fixture)


def run_board_command(command: str, args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    fixture_path = str(getattr(args, "fixture", "") or "")
    report = base_report(
        command=command,
        mode=mode,
        repo=str(getattr(args, "repo", "") or ""),
        board_title=str(getattr(args, "board_title", "") or ""),
        inputs={
            "fixture": fixture_path,
            "gh_bin": str(getattr(args, "gh_bin", "") or "gh"),
        },
    )
    if mode not in {"report", "dry-run", "apply"}:
        report["blocked_reasons"].append(f"invalid mode: {mode}")
        return finish_report(report, status="BLOCKED")
    report, fixture = _load_report_fixture(report, fixture_path)
    if fixture is None:
        return report
    fixture_repo = str(fixture.get("repo") or "")
    fixture_board = str(fixture.get("board_title") or "")
    if not report["repo"] and fixture_repo:
        report["repo"] = fixture_repo
    if fixture_board:
        report["board_title"] = fixture_board
    if command == "board-list":
        return _apply_if_requested(_run_board_list(report, fixture), args)
    if command == "board-claim":
        return _apply_if_requested(_run_board_claim(report, fixture, args), args)
    if command == "board-heartbeat":
        return _apply_if_requested(_run_board_heartbeat(report, fixture, args), args)
    if command == "board-release":
        return _apply_if_requested(_run_board_release(report, fixture, args), args)
    if command == "board-verify":
        return _apply_if_requested(_run_board_verify(report, fixture, args), args)
    if command == "board-backlog-add":
        return _apply_if_requested(_run_board_backlog_add(report, args), args)
    report["blocked_reasons"].append(f"unknown command: {command}")
    return finish_report(report, status="ERROR")


def _run_board_list(report: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    issues = fixture.get("issues") if isinstance(fixture.get("issues"), list) else []
    board_items = fixture.get("board_items") if isinstance(fixture.get("board_items"), list) else []
    board_issue_numbers = {
        _issue_number(item)
        for item in board_items
        if isinstance(item, dict) and _issue_number(item) is not None
    }
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        number = _issue_number(issue)
        labels = _labels(issue)
        fields = _fields(issue)
        if "project-roadmap" in labels and number not in board_issue_numbers:
            report["findings"].append(_finding("MISSING_BOARD_ITEM", "WARN", "project-roadmap issue missing from board", issue_number=number))
        if "project-roadmap" in labels and fields.get("Kind") != "umbrella" and not _has_agent_state(issue):
            report["findings"].append(_finding("AGENT_STATE_MISSING", "WARN", "board issue missing agent-state:v1", issue_number=number))
        _field_findings(report, fields, number)
        _status_label_findings(report, fields, labels, number)
    for item in board_items:
        if not isinstance(item, dict):
            continue
        labels = _labels(item)
        number = _issue_number(item)
        fields = _fields(item)
        if "project-roadmap" not in labels:
            report["findings"].append(_finding("UNEXPECTED_BOARD_ITEM", "WARN", "board item lacks project-roadmap", issue_number=number))
        _field_findings(report, fields, number)
        _status_label_findings(report, fields, labels, number)
    _pr_findings(report, fixture)
    status = "WARN" if report["findings"] else "OK"
    return finish_report(report, status=status)


def _field_findings(report: dict[str, Any], fields: dict[str, Any], issue_number: int | None) -> None:
    for field in REQUIRED_FIELDS:
        if str(fields.get(field) or "").strip() == "":
            report["findings"].append(_finding("MISSING_FIELD", "WARN", f"missing board field {field}", issue_number=issue_number))
    if fields.get("Status") and fields.get("Status") not in STATUSES:
        report["findings"].append(_finding("INVALID_FIELD_VALUE", "WARN", "invalid Status field", issue_number=issue_number))
    if fields.get("Track") and fields.get("Track") not in TRACKS:
        report["findings"].append(_finding("INVALID_FIELD_VALUE", "WARN", "invalid Track field", issue_number=issue_number))
    if fields.get("Priority") and fields.get("Priority") not in PRIORITIES:
        report["findings"].append(_finding("INVALID_FIELD_VALUE", "WARN", "invalid Priority field", issue_number=issue_number))
    if fields.get("Kind") and fields.get("Kind") not in KINDS:
        report["findings"].append(_finding("INVALID_FIELD_VALUE", "WARN", "invalid Kind field", issue_number=issue_number))


def _status_label_findings(report: dict[str, Any], fields: dict[str, Any], labels: set[str], issue_number: int | None) -> None:
    status = fields.get("Status")
    kind = fields.get("Kind")
    if kind == "umbrella" and status == "In Progress":
        report["findings"].append(_finding("CLAIM_CONFLICT", "ERROR", "umbrella item must not be In Progress", issue_number=issue_number))
    if status == "Needs Verify" and "needs-verification" not in labels:
        report["findings"].append(_finding("NEEDS_VERIFY_LABEL_MISMATCH", "WARN", "Needs Verify item lacks needs-verification label", issue_number=issue_number))
    if status == "Done" and ({"needs-verification", "blocked"} & labels):
        report["findings"].append(_finding("FORBIDDEN_DONE", "ERROR", "Done item still has blocking verification labels", issue_number=issue_number))
    if status == "Blocked" and "blocked" not in labels:
        report["findings"].append(_finding("BLOCKED_STATE_MISMATCH", "WARN", "Blocked item lacks blocked label", issue_number=issue_number))


def _pr_findings(report: dict[str, Any], fixture: dict[str, Any]) -> None:
    prs = fixture.get("pull_requests")
    if not isinstance(prs, list):
        return
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        body = str(pr.get("body") or "")
        close_allowed = bool(pr.get("close_keyword_allowed", False))
        if body and _CLOSE_RE.search(body) and not close_allowed:
            report["findings"].append(
                _finding(
                    "FORBIDDEN_CLOSE_KEYWORD",
                    "ERROR",
                    "PR uses close keyword where Tracked by is required",
                    source_ref=str(pr.get("url") or pr.get("number") or ""),
                )
            )


def _status_project_metadata(fixture: dict[str, Any], issue_number: int, status: str) -> dict[str, Any]:
    project = fixture.get("project_v2") if isinstance(fixture.get("project_v2"), dict) else {}
    options = project.get("status_options") if isinstance(project.get("status_options"), dict) else {}
    board_items = fixture.get("board_items") if isinstance(fixture.get("board_items"), list) else []
    item_id = ""
    for item in board_items:
        if isinstance(item, dict) and _issue_number(item) == issue_number:
            item_id = str(item.get("project_item_id") or item.get("item_id") or "")
            break
    return {
        "project_id": str(project.get("project_id") or ""),
        "status_field_id": str(project.get("status_field_id") or ""),
        "status_option_id": str(options.get(status) or ""),
        "project_item_id": item_id,
    }


def _run_board_claim(report: dict[str, Any], fixture: dict[str, Any], args: Any) -> dict[str, Any]:
    issue_number = int(getattr(args, "issue"))
    session = str(getattr(args, "session", "") or "")
    issue = _find_issue(fixture, issue_number)
    if issue is None:
        report["blocked_reasons"].append("ISSUE_NOT_FOUND")
        return finish_report(report, status="BLOCKED")
    labels = _labels(issue)
    fields = _fields(issue)
    if "project-roadmap" not in labels:
        report["blocked_reasons"].append("ISSUE_MISSING_PROJECT_ROADMAP")
    if fields.get("Status") != "Todo":
        report["blocked_reasons"].append("ISSUE_NOT_TODO")
    if fields.get("Kind") == "umbrella":
        report["blocked_reasons"].append("UMBRELLA_NOT_CLAIMABLE")
    if not _has_agent_state(issue):
        report["blocked_reasons"].append("AGENT_STATE_MISSING")
    competing = _active_competing_claims(issue, session)
    if competing:
        report["blocked_reasons"].append("ACTIVE_COMPETING_CLAIM")
        report["findings"].append(_finding("CLAIM_CONFLICT", "ERROR", "active competing claim exists", issue_number=issue_number))
    if report["blocked_reasons"]:
        return finish_report(report, status="BLOCKED")
    report["planned_actions"].extend(
        [
            {"type": "append_comment", "prefix": "CLAIM", "issue": issue_number, "session": session},
            {"type": "update_agent_state", "issue": issue_number, "status": "in_progress"},
            {
                "type": "set_board_status",
                "issue": issue_number,
                "status": "In Progress",
                **_status_project_metadata(fixture, issue_number, "In Progress"),
            },
        ]
    )
    return finish_report(report, status="OK")


def _run_board_heartbeat(report: dict[str, Any], fixture: dict[str, Any], args: Any) -> dict[str, Any]:
    issue_number = int(getattr(args, "issue"))
    session = str(getattr(args, "session", "") or "")
    issue = _find_issue(fixture, issue_number)
    if issue is None:
        report["blocked_reasons"].append("ISSUE_NOT_FOUND")
        return finish_report(report, status="BLOCKED")
    claims = issue.get("active_claims") if isinstance(issue.get("active_claims"), list) else []
    if not any(isinstance(c, dict) and str(c.get("session") or "") == session for c in claims):
        report["blocked_reasons"].append("CLAIM_SESSION_NOT_ACTIVE")
        return finish_report(report, status="BLOCKED")
    report["planned_actions"].append({"type": "append_comment", "prefix": "HEARTBEAT", "issue": issue_number, "session": session})
    report["planned_actions"].append({"type": "update_agent_state", "issue": issue_number, "claim_updated_at": "now"})
    return finish_report(report, status="OK")


def _run_board_release(report: dict[str, Any], fixture: dict[str, Any], args: Any) -> dict[str, Any]:
    issue_number = int(getattr(args, "issue"))
    reason = str(getattr(args, "reason", "") or "")
    if _find_issue(fixture, issue_number) is None:
        report["blocked_reasons"].append("ISSUE_NOT_FOUND")
        return finish_report(report, status="BLOCKED")
    prefix = "BLOCKED" if reason == "blocked" else "HANDOFF"
    report["planned_actions"].append({"type": "append_comment", "prefix": prefix, "issue": issue_number, "reason": reason})
    report["planned_actions"].append({"type": "clear_claim", "issue": issue_number})
    if reason == "blocked":
        report["planned_actions"].append(
            {
                "type": "set_board_status",
                "issue": issue_number,
                "status": "Blocked",
                **_status_project_metadata(fixture, issue_number, "Blocked"),
            }
        )
    return finish_report(report, status="OK")


def _run_board_verify(report: dict[str, Any], fixture: dict[str, Any], args: Any) -> dict[str, Any]:
    issue_number = int(getattr(args, "issue"))
    evidence_type = str(getattr(args, "evidence_type", "") or "")
    evidence = str(getattr(args, "evidence", "") or "")
    if _find_issue(fixture, issue_number) is None:
        report["blocked_reasons"].append("ISSUE_NOT_FOUND")
        return finish_report(report, status="BLOCKED")
    if not evidence:
        report["blocked_reasons"].append("EVIDENCE_REQUIRED")
        return finish_report(report, status="BLOCKED")
    report["planned_actions"].append({"type": "append_comment", "prefix": "EVIDENCE", "issue": issue_number, "evidence_type": evidence_type, "evidence": evidence})
    if evidence_type in {"source", "desired-state"}:
        report["planned_actions"].append(
            {
                "type": "set_board_status",
                "issue": issue_number,
                "status": "Needs Verify",
                **_status_project_metadata(fixture, issue_number, "Needs Verify"),
            }
        )
    return finish_report(report, status="OK")


def _run_board_backlog_add(report: dict[str, Any], args: Any) -> dict[str, Any]:
    report["planned_actions"].append(
        {
            "type": "create_issue",
            "title": str(getattr(args, "title", "") or ""),
            "kind": str(getattr(args, "kind", "") or ""),
            "faz": str(getattr(args, "faz", "") or ""),
            "track": str(getattr(args, "track", "") or ""),
            "priority": str(getattr(args, "priority", "") or ""),
            "labels": ["project-roadmap"],
            "status": "Backlog",
        }
    )
    return finish_report(report, status="OK")
