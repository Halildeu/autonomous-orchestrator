from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIRM = "APPLY_BOARD_GOVERNANCE_BOG_7A"
PROJECT_ID = "PVT_fixture_project"


def _fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "gh_calls.jsonl"
    script_path = tmp_path / "fake-gh"
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"log_path = {str(log_path)!r}\n"
        "args = sys.argv[1:]\n"
        "if os.environ.get('REQUIRE_GH_TOKEN') == '1' and not os.environ.get('GH_TOKEN'):\n"
        "    print('GH_TOKEN missing', file=sys.stderr)\n"
        "    sys.exit(9)\n"
        "with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(args, sort_keys=True) + '\\n')\n"
        "if args[:2] == ['auth', 'status']:\n"
        "    print('github.com')\n"
        "    print('  - Token scopes: \\'project\\', \\'repo\\'')\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['label', 'list']:\n"
        "    print(json.dumps([{'name': 'bug'}]))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['issue', 'list']:\n"
        "    print(json.dumps([]))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'field-list']:\n"
        "    print(json.dumps({'fields': [\n"
        "        {'id': 'field_status', 'name': 'Status', 'type': 'ProjectV2SingleSelectField', 'options': [{'id': 'opt_todo', 'name': 'Todo'}]},\n"
        "        {'id': 'field_faz', 'name': 'Faz', 'type': 'ProjectV2SingleSelectField', 'options': [{'id': 'opt_f5', 'name': 'F5 Projection Drift'}]},\n"
        "        {'id': 'field_track', 'name': 'Track', 'type': 'ProjectV2SingleSelectField', 'options': [{'id': 'opt_github_ops', 'name': 'github-ops'}]},\n"
        "        {'id': 'field_priority', 'name': 'Priority', 'type': 'ProjectV2SingleSelectField', 'options': [{'id': 'opt_p1', 'name': 'P1'}]},\n"
        "        {'id': 'field_kind', 'name': 'Kind', 'type': 'ProjectV2SingleSelectField', 'options': [{'id': 'opt_gate', 'name': 'gate'}]}\n"
        "    ], 'totalCount': 5}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'item-list']:\n"
        "    print(json.dumps({'items': [], 'totalCount': 0}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['label', 'create']:\n"
        "    print('created')\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['issue', 'create']:\n"
        "    print('https://github.com/Halildeu/autonomous-orchestrator/issues/77')\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'item-add']:\n"
        "    print(json.dumps({'id': 'PVTI_seed_77'}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'item-edit']:\n"
        "    print(json.dumps({'id': 'PVTI_seed_77'}))\n"
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


def _base_args(fake_gh: Path | None = None) -> list[str]:
    args = [
        "board-seed",
        "--seed",
        "fixtures/board/board_seed_bog7.v1.json",
        "--repo",
        "Halildeu/autonomous-orchestrator",
        "--project-owner",
        "Halildeu",
        "--project-number",
        "5",
        "--project-id",
        PROJECT_ID,
        "--out",
        "none",
    ]
    if fake_gh is not None:
        args.extend(["--gh-bin", str(fake_gh)])
    return args


def test_board_seed_dry_run_digest_and_plan() -> None:
    payload = _run([*_base_args(), "--mode", "dry-run"])
    assert payload["status"] == "OK"
    assert len(payload["seed_digest"]) == 64
    action_types = [action["type"] for action in payload["planned_actions"]]
    assert "ensure_label" in action_types
    assert "ensure_issue" in action_types
    assert "ensure_project_item" in action_types
    assert "set_project_field" in action_types
    assert payload["applied_actions"] == []


def test_board_seed_apply_requires_digest_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [*_base_args(fake_gh), "--mode", "apply", "--apply-confirm", CONFIRM, "--accepted-digest", "bad"],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "BLOCKED"
    assert "ACCEPTED_DIGEST_MISMATCH" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_seed_apply_requires_token_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    dry = _run([*_base_args(fake_gh), "--mode", "dry-run"])
    payload = _run(
        [*_base_args(fake_gh), "--mode", "apply", "--apply-confirm", CONFIRM, "--accepted-digest", dry["seed_digest"], "--token-env", "BOARD_TEST_TOKEN"],
        expect=1,
    )
    assert payload["status"] == "BLOCKED"
    assert "TOKEN_ENV_MISSING:BOARD_TEST_TOKEN" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_seed_apply_executes_fake_gh_without_token_leak(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    dry = _run([*_base_args(fake_gh), "--mode", "dry-run"])
    payload = _run(
        [
            *_base_args(fake_gh),
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--accepted-digest",
            dry["seed_digest"],
            "--token-env",
            "BOARD_TEST_TOKEN",
        ],
        env={"BOARD_TEST_TOKEN": "secret-token-value-123", "REQUIRE_GH_TOKEN": "1"},
    )
    assert payload["status"] == "OK"
    assert "secret-token-value-123" not in json.dumps(payload)
    calls = _calls(log_path)
    assert any(call[:2] == ["label", "create"] for call in calls)
    assert any(call[:2] == ["issue", "create"] for call in calls)
    assert any(call[:2] == ["project", "item-add"] for call in calls)
    assert any(call[:2] == ["project", "item-edit"] for call in calls)
    assert all(call[:2] != ["issue", "close"] for call in calls)
    assert all(action.get("value") != "Done" for action in payload["applied_actions"])
