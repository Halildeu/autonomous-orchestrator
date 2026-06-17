from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ops.board.apply import APPLY_CONFIRMATION
from src.ops.board.reports import dump_json, finish_report, now_iso
from src.shared.utils import write_json_atomic

_TRACKED_RE = re.compile(r"(?im)^\s*Tracked\s+by\s+#(?P<issue>[0-9]+)\b")
_CLOSE_RE = re.compile(r"(?im)^\s*(Closes|Fixes|Resolves)\s+#(?P<issue>[0-9]+)\b")


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


def _issue_index(fixture: dict[str, Any]) -> dict[int, dict[str, Any]]:
    issues = fixture.get("issues") if isinstance(fixture.get("issues"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        try:
            number = int(issue.get("number"))
        except Exception:
            continue
        out[number] = issue
    return out


def _labels(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels") if isinstance(issue.get("labels"), list) else []
    return {str(x) for x in labels if isinstance(x, str)}


def _fields(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields")
    return fields if isinstance(fields, dict) else {}


def _marker(pr_number: int, sha: str, issue: int) -> str:
    return f"board-pr-merge-evidence:v1 pr={pr_number} sha={sha} issue={issue}"


def _evidence_body(*, pr_number: int, sha: str, issue: int, url: str, run_url: str) -> str:
    marker = _marker(pr_number, sha, issue)
    return "\n".join(
        [
            f"<!-- {marker} -->",
            "",
            f"EVIDENCE type=pr-merged status=source-ready pr=#{pr_number} sha={sha}",
            "",
            "Source:",
            f"- {url}",
            f"- {sha}",
            f"- {run_url or 'workflow-run-url-unavailable'}",
            "",
            "Runtime/live:",
            "- pending after merge",
            "",
            "Browser/user-path:",
            "- pending after merge",
            "",
            "Does not prove:",
            "- runtime acceptance is complete",
            "- user-path acceptance is complete",
            "- issue is ready to close",
        ]
    )


def _token_present(token_env: str) -> bool:
    return bool(os.environ.get(token_env, "").strip())


def _gh_available(gh_bin: str) -> bool:
    if "/" in gh_bin:
        return os.path.exists(gh_bin) and os.access(gh_bin, os.X_OK)
    return shutil.which(gh_bin) is not None


def _base_report(*, mode: str, repo: str, event_path: str, issue_fixture: str) -> dict[str, Any]:
    started = now_iso()
    return {
        "version": "v1",
        "workflow": "board-pr-merge-evidence",
        "command": "board-pr-merge",
        "mode": mode,
        "status": "OK",
        "repo": repo,
        "started_at": started,
        "completed_at": started,
        "inputs": {"event": event_path, "issue_fixture": issue_fixture},
        "pr": {},
        "tracked_issues": [],
        "findings": [],
        "applied_actions": [],
        "blocked_reasons": [],
        "evidence": {
            "source": [event_path] if event_path else [],
            "desired_state": [".github/workflows/board-pr-merge-evidence.yml"],
            "runtime_live": [],
            "browser_user_path": [],
            "does_not_prove": [
                "Runtime/live acceptance remains pending.",
                "Issue closure remains deliberate.",
            ],
        },
    }


def _project_action(issue: dict[str, Any]) -> dict[str, Any] | None:
    project = issue.get("project") if isinstance(issue.get("project"), dict) else {}
    required = ("project_id", "project_item_id", "status_field_id", "needs_verify_option_id")
    if not all(project.get(k) for k in required):
        return None
    return {
        "type": "set_board_status",
        "issue": issue.get("number"),
        "status": "Needs Verify",
        "project_id": str(project["project_id"]),
        "project_item_id": str(project["project_item_id"]),
        "status_field_id": str(project["status_field_id"]),
        "status_option_id": str(project["needs_verify_option_id"]),
    }


def _planned_for_issue(
    *,
    issue_number: int,
    issue: dict[str, Any] | None,
    pr_number: int,
    sha: str,
    pr_url: str,
    run_url: str,
    close_forbidden: bool,
) -> dict[str, Any]:
    marker = _marker(pr_number, sha, issue_number)
    item = {
        "issue": issue_number,
        "eligible": False,
        "current_status": "",
        "planned_status": "",
        "evidence_marker": marker,
        "planned_actions": [],
        "applied_actions": [],
        "blocked_reasons": [],
    }
    if close_forbidden:
        item["blocked_reasons"].append("FORBIDDEN_CLOSE_KEYWORD")
        return item
    if issue is None:
        item["blocked_reasons"].append("ISSUE_METADATA_UNAVAILABLE")
        return item
    labels = _labels(issue)
    fields = _fields(issue)
    status = str(fields.get("Status") or "")
    kind = str(fields.get("Kind") or "")
    item["current_status"] = status
    if "project-roadmap" not in labels:
        item["blocked_reasons"].append("ISSUE_MISSING_PROJECT_ROADMAP")
    if not bool(issue.get("agent_state", False)):
        item["blocked_reasons"].append("AGENT_STATE_MISSING")
    if kind == "umbrella":
        item["blocked_reasons"].append("UMBRELLA_NOT_EXECUTABLE")
    if status in {"Blocked", "Done"}:
        item["blocked_reasons"].append(f"ISSUE_STATUS_{status.upper().replace(' ', '_')}")
    if item["blocked_reasons"]:
        return item

    item["eligible"] = True
    item["planned_status"] = "Needs Verify"
    existing = issue.get("existing_markers") if isinstance(issue.get("existing_markers"), list) else []
    if marker not in {str(x) for x in existing}:
        item["planned_actions"].append(
            {
                "type": "append_evidence_comment",
                "issue": issue_number,
                "marker": marker,
                "body": _evidence_body(pr_number=pr_number, sha=sha, issue=issue_number, url=pr_url, run_url=run_url),
            }
        )
    item["planned_actions"].append({"type": "add_label", "issue": issue_number, "label": "needs-verification"})
    project_action = _project_action(issue)
    if project_action:
        item["planned_actions"].append(project_action)
    else:
        item["blocked_reasons"].append("PROJECT_STATUS_METADATA_MISSING")
    return item


def _apply_action(action: dict[str, Any], *, repo: str, gh_bin: str) -> tuple[int, str, str, list[str]]:
    action_type = str(action.get("type") or "")
    if action_type == "append_evidence_comment":
        cmd = [
            gh_bin,
            "issue",
            "comment",
            str(action.get("issue")),
            "--repo",
            repo,
            "--body",
            str(action.get("body") or ""),
        ]
    elif action_type == "add_label":
        cmd = [
            gh_bin,
            "issue",
            "edit",
            str(action.get("issue")),
            "--repo",
            repo,
            "--add-label",
            str(action.get("label") or "needs-verification"),
        ]
    elif action_type == "set_board_status":
        cmd = [
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
    else:
        return (1, "", f"unsupported action: {action_type}", [])
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return (proc.returncode, proc.stdout or "", proc.stderr or "", cmd)


def run_pr_merge_command(args: Any) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "report") or "report")
    event_path = str(getattr(args, "event", "") or "")
    issue_fixture_path = str(getattr(args, "issue_fixture", "") or "")
    repo = str(getattr(args, "repo", "") or "")
    report = _base_report(mode=mode, repo=repo, event_path=event_path, issue_fixture=issue_fixture_path)
    if mode not in {"report", "dry-run", "apply"}:
        report["blocked_reasons"].append(f"invalid mode: {mode}")
        return finish_report(report, status="BLOCKED")
    event, error = _load_json(event_path)
    if error:
        report["blocked_reasons"].append(error)
        return finish_report(report, status="ERROR")
    issue_fixture: dict[str, Any] = {}
    if issue_fixture_path:
        issue_fixture, error = _load_json(issue_fixture_path)
        if error:
            report["blocked_reasons"].append(error)
            return finish_report(report, status="ERROR")
        report["evidence"]["source"].append(issue_fixture_path)

    pr = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
    pr_number = int(pr.get("number") or event.get("number") or 0)
    merged = bool(pr.get("merged", False))
    sha = str(pr.get("merge_commit_sha") or "")
    pr_url = str(pr.get("html_url") or "")
    body = str(pr.get("body") or "")
    repo = repo or str(event.get("repository", {}).get("full_name") if isinstance(event.get("repository"), dict) else "")
    report["repo"] = repo
    report["pr"] = {
        "number": pr_number,
        "merged": merged,
        "merge_sha": sha,
        "base_branch": str(pr.get("base", {}).get("ref") if isinstance(pr.get("base"), dict) else ""),
    }
    if not merged:
        return finish_report(report, status="OK")

    tracked = []
    for match in _TRACKED_RE.finditer(body):
        issue = int(match.group("issue"))
        if issue not in tracked:
            tracked.append(issue)
    if len(tracked) > 10:
        report["blocked_reasons"].append("TOO_MANY_TRACKED_ISSUES")
        return finish_report(report, status="BLOCKED")
    close_forbidden = bool(_CLOSE_RE.search(body)) and "Close keyword allowed: yes" not in body
    if close_forbidden:
        report["findings"].append(
            {"code": "FORBIDDEN_CLOSE_KEYWORD", "severity": "ERROR", "message": "PR uses close keyword where Tracked by is required"}
        )
    issues = _issue_index(issue_fixture)
    run_url = str(getattr(args, "run_url", "") or os.environ.get("GITHUB_RUN_URL", ""))
    for issue_number in tracked:
        report["tracked_issues"].append(
            _planned_for_issue(
                issue_number=issue_number,
                issue=issues.get(issue_number),
                pr_number=pr_number,
                sha=sha,
                pr_url=pr_url,
                run_url=run_url,
                close_forbidden=close_forbidden,
            )
        )
    if not tracked:
        return finish_report(report, status="OK")

    if mode != "apply":
        return finish_report(report, status="WARN" if report["findings"] else "OK")

    confirm = str(getattr(args, "apply_confirm", "") or "")
    token_env = str(getattr(args, "token_env", "") or "GITHUB_TOKEN")
    gh_bin = str(getattr(args, "gh_bin", "") or "gh")
    report["inputs"]["token_env"] = token_env
    report["inputs"]["apply_confirmation_required"] = APPLY_CONFIRMATION
    report["inputs"]["apply_confirmation_present"] = confirm == APPLY_CONFIRMATION
    if confirm != APPLY_CONFIRMATION:
        report["blocked_reasons"].append("APPLY_CONFIRMATION_REQUIRED")
        return finish_report(report, status="BLOCKED")
    if not _token_present(token_env):
        report["blocked_reasons"].append(f"TOKEN_ENV_MISSING:{token_env}")
        return finish_report(report, status="WARN")
    if not repo or "/" not in repo:
        report["blocked_reasons"].append("REPO_REQUIRED_FOR_APPLY")
        return finish_report(report, status="BLOCKED")
    if not _gh_available(gh_bin):
        report["blocked_reasons"].append("GH_BIN_NOT_AVAILABLE")
        return finish_report(report, status="BLOCKED")
    if report["findings"]:
        report["blocked_reasons"].append("UNSAFE_PR_BODY")
        return finish_report(report, status="BLOCKED")

    applied_all: list[dict[str, Any]] = []
    for item in report["tracked_issues"]:
        if item.get("blocked_reasons"):
            continue
        for action in item.get("planned_actions", []):
            rc, stdout, stderr, cmd = _apply_action(action, repo=repo, gh_bin=gh_bin)
            applied = {
                "type": action.get("type"),
                "issue": action.get("issue"),
                "returncode": rc,
                "stdout": stdout.strip()[:500],
            }
            if rc != 0:
                applied["stderr"] = stderr.strip()[:500]
                item["applied_actions"].append(applied)
                applied_all.append(applied)
                report["applied_actions"] = applied_all
                report["blocked_reasons"].append(f"GH_COMMAND_FAILED:{action.get('type')}")
                return finish_report(report, status="ERROR")
            item["applied_actions"].append(applied)
            applied_all.append(applied)
    report["applied_actions"] = applied_all
    if applied_all:
        report["evidence"]["runtime_live"].append("gh command execution completed")
    return finish_report(report, status="OK")


def write_pr_merge_report(*, workspace_root: Path, out_value: str, payload: dict[str, Any]) -> str:
    rel = Path(out_value)
    out_path = rel if rel.is_absolute() else workspace_root / rel
    out_path = out_path.resolve()
    out_path.relative_to(workspace_root.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, payload)
    return out_path.relative_to(workspace_root.resolve()).as_posix()


def dump_pr_merge_report(payload: dict[str, Any]) -> str:
    return dump_json(payload)
