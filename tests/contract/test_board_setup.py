from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIRM = "APPLY_BOARD_GOVERNANCE_BOG_6B"
READ_ONLY_PREFIXES = {
    ("auth", "status"),
    ("repo", "view"),
    ("project", "list"),
    ("project", "view"),
    ("project", "field-list"),
}
MUTATION_PREFIXES = {
    ("project", "create"),
    ("project", "field-create"),
    ("project", "link"),
    ("api", "graphql"),
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
        "    print('github.com')\n"
        "    print('  ✓ Logged in to github.com account Halildeu (keyring)')\n"
        "    print(\"  - Token scopes: 'project', 'repo', 'workflow'\")\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['repo', 'view']:\n"
        "    print(json.dumps({'nameWithOwner': 'Halildeu/autonomous-orchestrator', 'viewerPermission': 'ADMIN', 'isPrivate': False, 'url': 'https://github.com/Halildeu/autonomous-orchestrator'}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'list']:\n"
        "    if os.environ.get('FAKE_SETUP_EXISTING') == '1' or os.environ.get('FAKE_SETUP_EXISTING_MISMATCH') == '1':\n"
        "        print(open(project_list_path, encoding='utf-8').read())\n"
        "    else:\n"
        "        print(json.dumps({'projects': [], 'totalCount': 0}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'view']:\n"
        "    data = json.load(open(project_list_path, encoding='utf-8'))\n"
        "    print(json.dumps(data['projects'][0]))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'field-list']:\n"
        "    if os.environ.get('FAKE_SETUP_DEFAULT_STATUS_MISSING_OPTIONS') == '1':\n"
        "        print(json.dumps({'fields': [{'id': 'PVTSSF_default_status', 'name': 'Status', 'type': 'ProjectV2SingleSelectField', 'options': [{'id': 'todo_id', 'name': 'Todo'}, {'id': 'in_progress_id', 'name': 'In Progress'}, {'id': 'done_id', 'name': 'Done'}]}], 'totalCount': 1}))\n"
        "        sys.exit(0)\n"
        "    if os.environ.get('FAKE_SETUP_EMPTY_FIELDS') == '1':\n"
        "        print(json.dumps({'fields': [], 'totalCount': 0}))\n"
        "        sys.exit(0)\n"
        "    data = json.load(open(field_list_path, encoding='utf-8'))\n"
        "    if os.environ.get('FAKE_SETUP_EXISTING_MISMATCH') == '1':\n"
        "        for field in data['fields']:\n"
        "            if field.get('name') == 'Track':\n"
        "                field['options'] = [item for item in field.get('options', []) if item.get('name') != 'github-ops']\n"
        "    print(json.dumps(data))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'create']:\n"
        "    print(json.dumps({'number': 9, 'id': 'PVT_created_governance', 'title': 'autonomous-orchestrator Governance Board', 'url': 'https://github.com/users/Halildeu/projects/9'}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'field-create']:\n"
        "    name = args[args.index('--name') + 1] if '--name' in args else 'unknown'\n"
        "    print(json.dumps({'id': 'field_' + name.replace(' ', '_'), 'name': name}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'link']:\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['api', 'graphql']:\n"
        "    print(json.dumps({'data': {'updateProjectV2Field': {'projectV2Field': {'id': 'PVTSSF_default_status', 'name': 'Status', 'options': []}}}}))\n"
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


def _base_args(fake_gh: Path) -> list[str]:
    return [
        "board-setup",
        "--repo",
        "Halildeu/autonomous-orchestrator",
        "--project-owner",
        "Halildeu",
        "--gh-bin",
        str(fake_gh),
        "--token-env",
        "BOARD_TEST_TOKEN",
        "--out",
        "none",
    ]


def test_board_setup_dry_run_plans_missing_project_without_mutation(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "dry-run"])
    assert payload["status"] == "OK"
    assert len(payload["setup_digest"]) == 64
    assert payload["planned_actions"][0]["type"] == "create_project"
    assert any(action["type"] == "reconcile_required_fields_after_create" for action in payload["planned_actions"])
    assert payload["applied_actions"] == []
    calls = _calls(log_path)
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES for call in calls)


def test_board_setup_apply_requires_confirmation_before_mutation(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [*_base_args(fake_gh), "--mode", "apply", "--accepted-digest", "0" * 64],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "BLOCKED"
    assert "APPLY_CONFIRMATION_REQUIRED" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_setup_apply_requires_token_before_mutation(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "apply", "--apply-confirm", CONFIRM, "--accepted-digest", "0" * 64], expect=1)
    assert payload["status"] == "BLOCKED"
    assert "TOKEN_ENV_MISSING:BOARD_TEST_TOKEN" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_setup_apply_requires_accepted_digest_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "apply", "--apply-confirm", CONFIRM], expect=1, env={"BOARD_TEST_TOKEN": "present"})
    assert payload["status"] == "BLOCKED"
    assert "ACCEPTED_DIGEST_REQUIRED" in payload["blocked_reasons"]
    assert _calls(log_path) == []


def test_board_setup_apply_creates_project_and_fields_with_fake_gh(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    dry_run = _run([*_base_args(fake_gh), "--mode", "dry-run", "--link-repo"])
    if log_path.exists():
        log_path.unlink()
    payload = _run(
        [
            *_base_args(fake_gh),
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--accepted-digest",
            dry_run["setup_digest"],
            "--link-repo",
        ],
        env={"BOARD_TEST_TOKEN": "secret-token-value-123", "FAKE_SETUP_EMPTY_FIELDS": "1", "REQUIRE_GH_TOKEN": "1"},
    )
    assert payload["status"] == "OK"
    assert "secret-token-value-123" not in json.dumps(payload)
    assert any(action["type"] == "create_project" for action in payload["applied_actions"])
    assert {action["field"] for action in payload["applied_actions"] if action["type"] == "create_project_field"} == {
        "Status",
        "Faz",
        "Track",
        "Priority",
        "Kind",
    }
    calls = _calls(log_path)
    assert any(call[:2] == ["project", "create"] for call in calls)
    assert any(call[:2] == ["project", "field-create"] for call in calls)
    assert any(call[:2] == ["project", "link"] for call in calls)
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES | MUTATION_PREFIXES for call in calls)
    assert all(call[:2] != ["project", "item-edit"] for call in calls)
    assert all(call[:1] != ["issue"] for call in calls)


def test_board_setup_apply_updates_new_default_status_options(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    dry_run = _run([*_base_args(fake_gh), "--mode", "dry-run", "--link-repo"])
    if log_path.exists():
        log_path.unlink()
    payload = _run(
        [
            *_base_args(fake_gh),
            "--mode",
            "apply",
            "--apply-confirm",
            CONFIRM,
            "--accepted-digest",
            dry_run["setup_digest"],
            "--link-repo",
        ],
        env={
            "BOARD_TEST_TOKEN": "secret-token-value-123",
            "FAKE_SETUP_DEFAULT_STATUS_MISSING_OPTIONS": "1",
            "REQUIRE_GH_TOKEN": "1",
        },
    )
    assert payload["status"] == "OK"
    assert any(action["type"] == "update_project_field_options" and action["field"] == "Status" for action in payload["applied_actions"])
    calls = _calls(log_path)
    assert any(call[:2] == ["api", "graphql"] for call in calls)
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES | MUTATION_PREFIXES for call in calls)


def test_board_setup_apply_digest_mismatch_blocks_before_mutation(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [*_base_args(fake_gh), "--mode", "apply", "--apply-confirm", CONFIRM, "--accepted-digest", "0" * 64],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present"},
    )
    assert payload["status"] == "BLOCKED"
    assert "ACCEPTED_DIGEST_MISMATCH" in payload["blocked_reasons"]
    calls = _calls(log_path)
    assert calls
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES for call in calls)


def test_board_setup_existing_field_option_mismatch_blocks_before_mutation(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [*_base_args(fake_gh), "--mode", "apply", "--apply-confirm", CONFIRM, "--accepted-digest", "0" * 64],
        expect=1,
        env={"BOARD_TEST_TOKEN": "present", "FAKE_SETUP_EXISTING_MISMATCH": "1"},
    )
    assert payload["status"] == "BLOCKED"
    assert "FIELD_OPTION_MISMATCH_REQUIRES_MANUAL_MIGRATION" in payload["blocked_reasons"]
    assert all(tuple(call[:2]) in READ_ONLY_PREFIXES for call in _calls(log_path))
