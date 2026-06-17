from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIRM = "APPLY_BOARD_GOVERNANCE_BOG_3C"


def _fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "gh_calls.jsonl"
    script_path = tmp_path / "fake-gh"
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"log_path = {str(log_path)!r}\n"
        "with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(sys.argv[1:], sort_keys=True) + '\\n')\n"
        "print('fake-gh-ok')\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path, log_path


def _run(args: list[str], *, expect: int = 0, env: dict[str, str] | None = None) -> dict:
    run_env = os.environ.copy()
    run_env.pop("BOARD_TEST_TOKEN", None)
    if env:
        run_env.update(env)
    proc = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
        check=False,
    )
    if proc.returncode != expect:
        raise AssertionError(f"unexpected exit {proc.returncode} != {expect}\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except Exception as exc:
        raise AssertionError(f"stdout is not json: {exc}\n{proc.stdout}") from exc


def _calls(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_board_pr_merge_apply_executes_needs_verify_actions(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-pr-merge",
            "--event",
            "fixtures/board/pr_merge_event_merged.v1.json",
            "--issue-fixture",
            "fixtures/board/pr_merge_issues_happy.v1.json",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--gh-bin",
            str(fake_gh),
            "--out",
            "none",
        ],
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "OK"
    assert payload["tracked_issues"][0]["planned_status"] == "Needs Verify"
    assert len(payload["applied_actions"]) == 3
    calls = _calls(log_path)
    assert calls[0][:2] == ["issue", "comment"]
    assert calls[1][:2] == ["issue", "edit"]
    assert calls[2][:2] == ["project", "item-edit"]
    assert all(call[:2] != ["issue", "close"] for call in calls)
    assert "Done" not in json.dumps(payload)


def test_board_pr_merge_missing_token_falls_back_without_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-pr-merge",
            "--event",
            "fixtures/board/pr_merge_event_merged.v1.json",
            "--issue-fixture",
            "fixtures/board/pr_merge_issues_happy.v1.json",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--gh-bin",
            str(fake_gh),
            "--out",
            "none",
        ]
    )
    assert payload["status"] == "WARN"
    assert "TOKEN_ENV_MISSING:BOARD_TEST_TOKEN" in payload["blocked_reasons"]
    assert payload["applied_actions"] == []
    assert _calls(log_path) == []


def test_board_pr_merge_ignores_unmerged_and_no_tracked_prs() -> None:
    unmerged = _run(
        [
            "board-pr-merge",
            "--event",
            "fixtures/board/pr_merge_event_unmerged.v1.json",
            "--issue-fixture",
            "fixtures/board/pr_merge_issues_happy.v1.json",
            "--out",
            "none",
        ]
    )
    assert unmerged["status"] == "OK"
    assert unmerged["tracked_issues"] == []

    no_tracked = _run(
        [
            "board-pr-merge",
            "--event",
            "fixtures/board/pr_merge_event_no_tracked.v1.json",
            "--issue-fixture",
            "fixtures/board/pr_merge_issues_happy.v1.json",
            "--out",
            "none",
        ]
    )
    assert no_tracked["status"] == "OK"
    assert no_tracked["tracked_issues"] == []


def test_board_pr_merge_blocks_forbidden_close_keyword_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-pr-merge",
            "--event",
            "fixtures/board/pr_merge_event_forbidden_close.v1.json",
            "--issue-fixture",
            "fixtures/board/pr_merge_issues_happy.v1.json",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--gh-bin",
            str(fake_gh),
            "--out",
            "none",
        ],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "BLOCKED"
    assert "UNSAFE_PR_BODY" in payload["blocked_reasons"]
    assert payload["findings"][0]["code"] == "FORBIDDEN_CLOSE_KEYWORD"
    assert _calls(log_path) == []


def test_board_pr_merge_existing_marker_does_not_duplicate_comment(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-pr-merge",
            "--event",
            "fixtures/board/pr_merge_event_merged.v1.json",
            "--issue-fixture",
            "fixtures/board/pr_merge_issues_existing_marker.v1.json",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--gh-bin",
            str(fake_gh),
            "--out",
            "none",
        ],
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "OK"
    calls = _calls(log_path)
    assert all(call[:2] != ["issue", "comment"] for call in calls)
    assert any(call[:2] == ["project", "item-edit"] for call in calls)


def test_board_pr_merge_workflow_static_contract() -> None:
    workflow = (ROOT / ".github/workflows/board-pr-merge-evidence.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "types: [closed]" in workflow
    assert "pull_request_target" not in workflow
    assert "issues: write" in workflow
    assert "board-pr-merge" in workflow
    assert "APPLY_BOARD_GOVERNANCE_BOG_3C" in workflow
    assert "issue close" not in workflow
    assert "Done" not in workflow
