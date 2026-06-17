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
        "import json, sys\n"
        f"log_path = {str(log_path)!r}\n"
        "args = sys.argv[1:]\n"
        "with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(args, sort_keys=True) + '\\n')\n"
        "if args[:2] == ['auth', 'status']:\n"
        "    print('github.com')\n"
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
        "    print(json.dumps({'items': [{'id': 'PVTI_seed_78', 'content': {'number': 78, 'title': 'BOG-7: Live board item population and sync acceptance', 'url': 'https://github.com/Halildeu/autonomous-orchestrator/issues/78'}}], 'totalCount': 1}))\n"
        "    sys.exit(0)\n"
        "print('unsupported fake gh call: ' + json.dumps(args), file=sys.stderr)\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path, log_path


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


def _calls(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_board_metadata_live_generates_metadata_map(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-metadata-live",
            "--repo",
            "Halildeu/autonomous-orchestrator",
            "--project-owner",
            "Halildeu",
            "--project-number",
            "5",
            "--project-id",
            "PVT_fixture_project",
            "--gh-bin",
            str(fake_gh),
            "--out",
            "none",
        ]
    )
    assert payload["status"] == "OK"
    assert payload["field_count"] == 5
    assert payload["item_count"] == 1
    assert len(payload["metadata_digest"]) == 64
    assert all(call[:2] in [["auth", "status"], ["project", "field-list"], ["project", "item-list"]] for call in _calls(log_path))


def test_board_metadata_live_apply_blocks_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run(
        [
            "board-metadata-live",
            "--repo",
            "Halildeu/autonomous-orchestrator",
            "--project-owner",
            "Halildeu",
            "--project-number",
            "5",
            "--project-id",
            "PVT_fixture_project",
            "--gh-bin",
            str(fake_gh),
            "--mode",
            "apply",
            "--out",
            "none",
        ],
        expect=1,
    )
    assert payload["status"] == "BLOCKED"
    assert "APPLY_NOT_SUPPORTED_FOR_BOARD_METADATA_LIVE" in payload["blocked_reasons"]
    assert _calls(log_path) == []
