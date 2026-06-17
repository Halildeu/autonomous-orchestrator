from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

READ_ONLY_PREFIXES = {
    ("auth", "status"),
    ("repo", "view"),
    ("project", "list"),
    ("project", "view"),
    ("project", "field-list"),
}


def _fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "gh_calls.jsonl"
    script_path = tmp_path / "fake-gh"
    project_list = ROOT / "fixtures" / "board" / "board_live_probe_project_list.v1.json"
    field_list = ROOT / "fixtures" / "board" / "board_live_probe_field_list.v1.json"
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"log_path = {str(log_path)!r}\n"
        f"project_list_path = {str(project_list)!r}\n"
        f"field_list_path = {str(field_list)!r}\n"
        "args = sys.argv[1:]\n"
        "if os.environ.get('REQUIRE_GH_TOKEN') == '1' and not os.environ.get('GH_TOKEN'):\n"
        "    print('GH_TOKEN missing', file=sys.stderr)\n"
        "    sys.exit(9)\n"
        "with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(args, sort_keys=True) + '\\n')\n"
        "if args[:2] == ['auth', 'status']:\n"
        "    if os.environ.get('FAKE_GH_AUTH_FAIL') == '1':\n"
        "        print('not logged in', file=sys.stderr)\n"
        "        sys.exit(1)\n"
        "    print('github.com')\n"
        "    print('  ✓ Logged in to github.com account Halildeu (keyring)')\n"
        "    print(\"  - Token scopes: 'project', 'repo', 'workflow'\")\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['repo', 'view']:\n"
        "    print(json.dumps({'nameWithOwner': 'Halildeu/autonomous-orchestrator', 'viewerPermission': 'ADMIN', 'isPrivate': False, 'url': 'https://github.com/Halildeu/autonomous-orchestrator'}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'list']:\n"
        "    if os.environ.get('FAKE_GH_EMPTY_PROJECTS') == '1':\n"
        "        print(json.dumps({'projects': [], 'totalCount': 0}))\n"
        "        sys.exit(0)\n"
        "    print(open(project_list_path, encoding='utf-8').read())\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'view']:\n"
        "    data = json.load(open(project_list_path, encoding='utf-8'))\n"
        "    print(json.dumps(data['projects'][0]))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'field-list']:\n"
        "    data = json.load(open(field_list_path, encoding='utf-8'))\n"
        "    if os.environ.get('FAKE_GH_FIELD_MISMATCH') == '1':\n"
        "        for field in data['fields']:\n"
        "            if field.get('name') == 'Kind':\n"
        "                field['options'] = [item for item in field.get('options', []) if item.get('name') != 'issue']\n"
        "    print(json.dumps(data))\n"
        "    sys.exit(0)\n"
        "print('unsupported fake gh call: ' + json.dumps(args), file=sys.stderr)\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path, log_path


def _run(args: list[str], *, expect: int = 0, env: dict[str, str] | None = None) -> dict:
    run_env = os.environ.copy()
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


def _base_args(fake_gh: Path) -> list[str]:
    return [
        "board-live-probe",
        "--repo",
        "Halildeu/autonomous-orchestrator",
        "--project-owner",
        "Halildeu",
        "--gh-bin",
        str(fake_gh),
        "--out",
        "none",
    ]


def test_board_live_probe_happy_path_is_read_only(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--token-env", "BOARD_TEST_TOKEN"], env={"BOARD_TEST_TOKEN": "secret-token-value-123", "REQUIRE_GH_TOKEN": "1"})
    assert payload["status"] == "OK"
    assert "secret-token-value-123" not in json.dumps(payload)
    assert payload["auth"]["required_scopes_present"] is True
    assert payload["repo_access"]["viewerPermission"] == "ADMIN"
    assert payload["resolved_project"]["id"] == "PVT_fixture_governance"
    assert payload["field_compatibility"]["status"] == "OK"
    assert payload["applied_actions"] == []
    calls = _calls(log_path)
    assert calls
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES for call in calls)
    assert all(call[:2] != ["project", "item-edit"] for call in calls)
    assert all(call[:2] != ["issue", "edit"] for call in calls)
    assert all(call[:2] != ["issue", "close"] for call in calls)


def test_board_live_probe_apply_mode_blocks_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "apply"], expect=1)
    assert payload["status"] == "BLOCKED"
    assert "APPLY_NOT_SUPPORTED_FOR_LIVE_PROBE" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_live_probe_auth_failure_blocks(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(_base_args(fake_gh), expect=1, env={"FAKE_GH_AUTH_FAIL": "1"})
    assert payload["status"] == "BLOCKED"
    assert any(reason.startswith("GH_COMMAND_FAILED:auth status") for reason in payload["blocked_reasons"])
    assert _calls(log_path) == [["auth", "status"]]


def test_board_live_probe_missing_project_reports_warn_without_field_probe(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(_base_args(fake_gh), env={"FAKE_GH_EMPTY_PROJECTS": "1"})
    assert payload["status"] == "WARN"
    assert "PROJECT_NOT_FOUND_BY_NUMBER_OR_TITLE" in payload["blocked_reasons"]
    calls = _calls(log_path)
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES for call in calls)
    assert ["project", "field-list", "8", "--owner", "Halildeu", "--format", "json", "--limit", "100"] not in calls


def test_board_live_probe_field_contract_mismatch_reports_warn(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(_base_args(fake_gh), env={"FAKE_GH_FIELD_MISMATCH": "1"})
    assert payload["status"] == "WARN"
    assert "PROJECT_FIELD_CONTRACT_MISMATCH" in payload["blocked_reasons"]
    assert payload["field_compatibility"]["missing_options"]["Kind"] == ["issue"]
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES for call in _calls(log_path))
