from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "gh_calls.jsonl"
    script_path = tmp_path / "fake-gh"
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "import time\n"
        f"log_path = {str(log_path)!r}\n"
        "args = sys.argv[1:]\n"
        "with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(args, sort_keys=True) + '\\n')\n"
        "    fh.flush()\n"
        "if args[:2] == ['auth', 'status']:\n"
        "    if os.environ.get('FAKE_AUTH_SLEEP_SECONDS'):\n"
        "        time.sleep(float(os.environ['FAKE_AUTH_SLEEP_SECONDS']))\n"
        "    if os.environ.get('REQUIRE_GH_TOKEN') == '1' and not os.environ.get('GH_TOKEN'):\n"
        "        print('GH_TOKEN missing', file=sys.stderr)\n"
        "        sys.exit(9)\n"
        "    if os.environ.get('FAKE_AUTH_FAIL') == '1':\n"
        "        print('auth failed', file=sys.stderr)\n"
        "        sys.exit(1)\n"
        "    if os.environ.get('FAKE_SCOPE_MISSING') == '1':\n"
        "        print('github.com')\n"
        "        print('  ✓ Logged in to github.com account Halildeu')\n"
        "        print(\"  - Token scopes: 'repo'\")\n"
        "        sys.exit(0)\n"
        "    print('github.com')\n"
        "    print('  ✓ Logged in to github.com account Halildeu')\n"
        "    print(\"  - Token scopes: 'project', 'repo', 'workflow'\")\n"
        "    sys.exit(0)\n"
        "print('unsupported fake gh call: ' + json.dumps(args), file=sys.stderr)\n"
        "sys.exit(2)\n",
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


def test_auth_preflight_missing_token_blocks_without_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-auth-preflight",
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
    assert "KEYRING_AUTH_NOT_ATTEMPTED" in payload["blocked_reasons"]
    assert payload["read_only_commands"] == []
    assert _calls(log_path) == []


def test_auth_preflight_token_bridges_to_child_gh_token(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-auth-preflight",
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
    assert payload["token_env_present"] is True
    assert payload["auth"]["required_scopes_present"] is True
    assert payload["auth"]["account"] == "Halildeu"
    assert "secret-token-value-123" not in json.dumps(payload)
    assert _calls(log_path) == [["auth", "status"]]


def test_auth_preflight_scope_missing_blocks(tmp_path: Path) -> None:
    fake_gh, _log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-auth-preflight",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--out",
            "none",
        ],
        expect=1,
        env={"BOARD_TEST_TOKEN": "secret-token-value-123", "REQUIRE_GH_TOKEN": "1", "FAKE_SCOPE_MISSING": "1"},
    )
    assert payload["status"] == "BLOCKED"
    assert "TOKEN_SCOPE_MISSING:project_or_repo" in payload["blocked_reasons"]


def test_auth_preflight_apply_mode_blocks_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-auth-preflight",
            "--mode",
            "apply",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--out",
            "none",
        ],
        expect=1,
        env={"BOARD_TEST_TOKEN": "secret-token-value-123"},
    )
    assert payload["status"] == "BLOCKED"
    assert "APPLY_NOT_SUPPORTED_FOR_AUTH_PREFLIGHT" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_auth_preflight_allow_keyring_timeout_blocks(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-auth-preflight",
            "--gh-bin",
            str(fake_gh),
            "--token-env",
            "BOARD_TEST_TOKEN",
            "--allow-keyring-auth",
            "--gh-timeout-seconds",
            "0.5",
            "--out",
            "none",
        ],
        expect=1,
        env={"FAKE_AUTH_SLEEP_SECONDS": "2"},
    )
    assert payload["status"] == "BLOCKED"
    assert payload["read_only_commands"] == ["auth status"]
    assert any(reason.startswith("GH_COMMAND_TIMEOUT:auth status:") for reason in payload["blocked_reasons"])
    assert _calls(log_path) == [["auth", "status"]]
