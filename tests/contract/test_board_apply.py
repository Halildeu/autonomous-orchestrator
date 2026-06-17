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
        "import json, os, sys\n"
        f"log_path = {str(log_path)!r}\n"
        "if os.environ.get('REQUIRE_GH_TOKEN') == '1' and not os.environ.get('GH_TOKEN'):\n"
        "    print('GH_TOKEN missing', file=sys.stderr)\n"
        "    sys.exit(9)\n"
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


def _read_calls(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_apply_requires_explicit_confirmation_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-verify",
            "--mode",
            "apply",
            "--fixture",
            "fixtures/board/board_apply_project_status.v1.json",
            "--issue",
            "203",
            "--evidence",
            "pytest tests/contract/test_board_apply.py",
            "--evidence-type",
            "source",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--out",
            "none",
        ],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "BLOCKED"
    assert "APPLY_CONFIRMATION_REQUIRED" in payload["blocked_reasons"]
    assert payload["applied_actions"] == []
    assert _read_calls(log_path) == []


def test_apply_requires_token_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-verify",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--fixture",
            "fixtures/board/board_apply_project_status.v1.json",
            "--issue",
            "203",
            "--evidence",
            "pytest tests/contract/test_board_apply.py",
            "--evidence-type",
            "source",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--out",
            "none",
        ],
        expect=1,
    )
    assert payload["status"] == "BLOCKED"
    assert "TOKEN_ENV_MISSING:BOARD_TEST_TOKEN" in payload["blocked_reasons"]
    assert payload["applied_actions"] == []
    assert _read_calls(log_path) == []


def test_apply_executes_supported_verify_actions_with_fake_gh(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-verify",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--fixture",
            "fixtures/board/board_apply_project_status.v1.json",
            "--issue",
            "203",
            "--evidence",
            "pytest tests/contract/test_board_apply.py",
            "--evidence-type",
            "source",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--out",
            "none",
        ],
        env={"BOARD_TEST_TOKEN": "secret-token-value-123", "REQUIRE_GH_TOKEN": "1"},
    )
    assert payload["status"] == "OK"
    assert "secret-token-value-123" not in json.dumps(payload)
    assert len(payload["applied_actions"]) == 2
    calls = _read_calls(log_path)
    assert calls[0][:2] == ["issue", "comment"]
    assert calls[1][:2] == ["project", "item-edit"]
    assert "PVTSSO_needs_verify" in calls[1]


def test_apply_blocks_unsupported_agent_state_action_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-claim",
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--fixture",
            "fixtures/board/board_apply_happy.v1.json",
            "--issue",
            "201",
            "--session",
            "this-session",
            "--agent",
            "codex",
            "--worktree",
            "/tmp/worktree",
            "--branch",
            "main",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--out",
            "none",
        ],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "BLOCKED"
    assert "UNSUPPORTED_APPLY_ACTION:update_agent_state" in payload["blocked_reasons"]
    assert payload["applied_actions"] == []
    assert _read_calls(log_path) == []
