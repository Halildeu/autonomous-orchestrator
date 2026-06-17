from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(args: list[str], *, expect: int = 0) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != expect:
        raise AssertionError(f"unexpected exit {proc.returncode} != {expect}\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except Exception as exc:
        raise AssertionError(f"stdout is not json: {exc}\n{proc.stdout}") from exc


def _assert_report_shape(payload: dict) -> None:
    for key in [
        "version",
        "command",
        "mode",
        "status",
        "findings",
        "planned_actions",
        "applied_actions",
        "blocked_reasons",
        "evidence",
    ]:
        assert key in payload
    assert payload["applied_actions"] == []
    assert payload["evidence"]["does_not_prove"]


def test_board_list_happy_report_only() -> None:
    payload = _run(
        [
            "board-list",
            "--fixture",
            "fixtures/board/board_list_happy.v1.json",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    assert payload["status"] == "OK"
    assert payload["findings"] == []


def test_board_claim_conflict_blocks_without_mutation() -> None:
    payload = _run(
        [
            "board-claim",
            "--fixture",
            "fixtures/board/board_claim_conflict.v1.json",
            "--issue",
            "102",
            "--session",
            "this-session",
            "--agent",
            "codex",
            "--worktree",
            "/tmp/worktree",
            "--branch",
            "main",
            "--out",
            "none",
        ],
        expect=1,
    )
    _assert_report_shape(payload)
    assert payload["status"] == "BLOCKED"
    assert "ACTIVE_COMPETING_CLAIM" in payload["blocked_reasons"]
    assert payload["planned_actions"] == []


def test_board_list_reports_needs_verify_and_close_keyword_drift() -> None:
    payload = _run(
        [
            "board-list",
            "--fixture",
            "fixtures/board/board_needs_verify_drift.v1.json",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    codes = {item["code"] for item in payload["findings"]}
    assert "NEEDS_VERIFY_LABEL_MISMATCH" in codes
    assert "FORBIDDEN_CLOSE_KEYWORD" in codes
    assert payload["status"] == "WARN"


def test_malformed_gh_json_fixture_errors_without_mutation() -> None:
    payload = _run(
        [
            "board-list",
            "--fixture",
            "fixtures/board/board_malformed_gh_json.v1.json",
            "--out",
            "none",
        ],
        expect=1,
    )
    _assert_report_shape(payload)
    assert payload["status"] == "ERROR"
    assert payload["applied_actions"] == []


def test_apply_mode_requires_explicit_bog_3c_confirmation() -> None:
    payload = _run(
        [
            "board-list",
            "--fixture",
            "fixtures/board/board_list_happy.v1.json",
            "--mode",
            "apply",
            "--out",
            "none",
        ],
        expect=1,
    )
    _assert_report_shape(payload)
    assert payload["status"] == "BLOCKED"
    assert "APPLY_CONFIRMATION_REQUIRED" in payload["blocked_reasons"]
    assert payload["applied_actions"] == []


def test_board_claim_happy_plans_no_applied_actions() -> None:
    payload = _run(
        [
            "board-claim",
            "--fixture",
            "fixtures/board/board_list_happy.v1.json",
            "--issue",
            "101",
            "--session",
            "this-session",
            "--agent",
            "codex",
            "--worktree",
            "/tmp/worktree",
            "--branch",
            "main",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    assert payload["status"] == "OK"
    assert payload["planned_actions"]
    assert payload["applied_actions"] == []


def test_board_heartbeat_plans_no_applied_actions() -> None:
    payload = _run(
        [
            "board-heartbeat",
            "--fixture",
            "fixtures/board/board_claim_conflict.v1.json",
            "--issue",
            "102",
            "--session",
            "other-session",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    assert payload["status"] == "OK"
    assert any(action["prefix"] == "HEARTBEAT" for action in payload["planned_actions"])
    assert payload["applied_actions"] == []


def test_board_release_plans_no_done_transition() -> None:
    payload = _run(
        [
            "board-release",
            "--fixture",
            "fixtures/board/board_list_happy.v1.json",
            "--issue",
            "101",
            "--session",
            "this-session",
            "--reason",
            "blocked",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    assert payload["status"] == "OK"
    statuses = [action.get("status") for action in payload["planned_actions"] if action.get("status")]
    assert "Done" not in statuses
    assert "Blocked" in statuses


def test_board_verify_source_moves_only_to_needs_verify() -> None:
    payload = _run(
        [
            "board-verify",
            "--fixture",
            "fixtures/board/board_list_happy.v1.json",
            "--issue",
            "101",
            "--evidence",
            "pytest tests/contract/test_board_commands.py",
            "--evidence-type",
            "source",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    assert payload["status"] == "OK"
    statuses = [action.get("status") for action in payload["planned_actions"] if action.get("status")]
    assert statuses == ["Needs Verify"]


def test_board_backlog_add_is_plan_only() -> None:
    payload = _run(
        [
            "board-backlog-add",
            "--title",
            "Curated board candidate",
            "--kind",
            "issue",
            "--faz",
            "F3 Board Script",
            "--track",
            "github-ops",
            "--priority",
            "P2",
            "--ssot-ref",
            "docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md#BOG-3B",
            "--next-action",
            "Run board-list dry-run",
            "--out",
            "none",
        ]
    )
    _assert_report_shape(payload)
    assert payload["status"] == "OK"
    assert payload["planned_actions"][0]["type"] == "create_issue"
    assert payload["applied_actions"] == []
