from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIRM = "APPLY_BOARD_GOVERNANCE_BOG_3C"
DIGEST = "8888888888888888888888888888888888888888888888888888888888888888"


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


def _calls(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _base_args() -> list[str]:
    return [
        "board-sync",
        "--projection",
        "fixtures/board/board_sync_projection_status_drift.v1.json",
        "--metadata",
        "fixtures/board/board_sync_metadata_happy.v1.json",
        "--accepted-digest",
        DIGEST,
        "--target-board-id",
        "PVT_fixture_project",
        "--out",
        "none",
    ]


def test_board_sync_dry_run_plans_operator_bound_actions() -> None:
    payload = _run([*_base_args(), "--mode", "dry-run"])
    assert payload["status"] == "OK"
    assert payload["projection_digest"] == DIGEST
    action_types = [action["type"] for action in payload["planned_actions"]]
    assert "set_project_field" in action_types
    assert "add_label" in action_types
    assert payload["applied_actions"] == []
    assert payload["mutation_ledger"] == []


def test_board_sync_dry_run_noop_is_ok() -> None:
    payload = _run(
        [
            "board-sync",
            "--projection",
            "fixtures/board/board_projection_happy.v1.json",
            "--metadata",
            "fixtures/board/board_sync_metadata_happy.v1.json",
            "--accepted-digest",
            "2222222222222222222222222222222222222222222222222222222222222222",
            "--target-board-id",
            "PVT_fixture_project",
            "--mode",
            "dry-run",
            "--out",
            "none",
        ]
    )
    assert payload["status"] == "OK"
    assert payload["planned_actions"] == []
    assert payload["noop"] is True


def test_board_sync_apply_requires_accepted_digest_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-sync",
            "--projection",
            "fixtures/board/board_sync_projection_status_drift.v1.json",
            "--metadata",
            "fixtures/board/board_sync_metadata_happy.v1.json",
            "--accepted-digest",
            "bad-digest",
            "--target-board-id",
            "PVT_fixture_project",
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
    assert "ACCEPTED_DIGEST_MISMATCH" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_sync_apply_requires_token_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            *_base_args(),
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--gh-bin",
            str(fake_gh),
        ],
        expect=1,
    )
    assert payload["status"] == "BLOCKED"
    assert "TOKEN_ENV_MISSING:BOARD_TEST_TOKEN" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_sync_apply_executes_fake_gh_and_records_ledger(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            *_base_args(),
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--gh-bin",
            str(fake_gh),
        ],
        env={"BOARD_TEST_TOKEN": "secret-token-value-123", "REQUIRE_GH_TOKEN": "1"},
    )
    assert payload["status"] == "OK"
    assert "secret-token-value-123" not in json.dumps(payload)
    assert payload["mutation_ledger"]
    assert payload["before_inventory"]
    assert payload["after_inventory"]
    calls = _calls(log_path)
    assert any(call[:2] == ["project", "item-edit"] for call in calls)
    assert any(call[:2] == ["issue", "edit"] for call in calls)
    assert all(call[:2] != ["issue", "close"] for call in calls)
    assert "Done" not in json.dumps(payload)


def test_board_sync_done_target_blocks_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-sync",
            "--projection",
            "fixtures/board/board_sync_projection_done_forbidden.v1.json",
            "--metadata",
            "fixtures/board/board_sync_metadata_happy.v1.json",
            "--accepted-digest",
            "9999999999999999999999999999999999999999999999999999999999999999",
            "--target-board-id",
            "PVT_fixture_project",
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
    assert "DONE_AUTOMATION_FORBIDDEN:402" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_sync_missing_metadata_blocks_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-sync",
            "--projection",
            "fixtures/board/board_sync_projection_status_drift.v1.json",
            "--metadata",
            "fixtures/board/board_sync_metadata_missing_ids.v1.json",
            "--accepted-digest",
            DIGEST,
            "--target-board-id",
            "PVT_fixture_project",
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
    assert any(reason.startswith("FIELD_METADATA_MISSING") for reason in payload["blocked_reasons"])
    assert _calls(log_path) == []
