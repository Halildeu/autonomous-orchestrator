from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _seed_body() -> str:
    seed = json.loads((ROOT / "fixtures" / "board" / "board_seed_bog7.v1.json").read_text(encoding="utf-8"))
    return seed["items"][0]["body"]


def _fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "gh_calls.jsonl"
    script_path = tmp_path / "fake-gh"
    body = _seed_body()
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"log_path = {str(log_path)!r}\n"
        f"body = {body!r}\n"
        "args = sys.argv[1:]\n"
        "with open(log_path, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(args, sort_keys=True) + '\\n')\n"
        "if args[:2] == ['auth', 'status']:\n"
        "    print('github.com')\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['issue', 'list']:\n"
        "    print(json.dumps([{'number': 78, 'title': 'BOG-7: Live board item population and sync acceptance', 'url': 'https://github.com/Halildeu/autonomous-orchestrator/issues/78', 'state': 'OPEN', 'body': body, 'labels': [{'name': 'project-roadmap'}, {'name': 'gate'}, {'name': 'quality'}]}]))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'field-list']:\n"
        "    print(json.dumps({'fields': [], 'totalCount': 0}))\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['project', 'item-list']:\n"
        "    status = 'Todo' if os.environ.get('FAKE_FIELD_MISMATCH') != '1' else 'In Progress'\n"
        "    print(json.dumps({'items': [{'id': 'PVTI_seed_78', 'content': {'number': 78, 'title': 'BOG-7: Live board item population and sync acceptance', 'url': 'https://github.com/Halildeu/autonomous-orchestrator/issues/78'}, 'labels': ['project-roadmap', 'gate', 'quality'], 'status': status, 'faz': 'F5 Projection Drift', 'track': 'github-ops', 'priority': 'P1', 'kind': 'gate'}], 'totalCount': 1}))\n"
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
        "board-projection-live",
        "--repo",
        "Halildeu/autonomous-orchestrator",
        "--project-owner",
        "Halildeu",
        "--project-number",
        "5",
        "--gh-bin",
        str(fake_gh),
        "--out",
        "none",
    ]


def test_board_projection_live_generates_schema_valid_projection(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "dry-run"])
    assert payload["status"] == "OK"
    assert payload["expected_count"] == 1
    assert payload["observed_count"] == 1
    assert len(payload["projection_digest"]) == 64
    calls = _calls(log_path)
    assert calls
    assert all(call[:2] in [["auth", "status"], ["issue", "list"], ["project", "field-list"], ["project", "item-list"]] for call in calls)


def test_board_projection_live_reports_field_mismatch(tmp_path: Path) -> None:
    fake_gh, _log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "dry-run"], env={"FAKE_FIELD_MISMATCH": "1"})
    assert payload["status"] == "WARN"
    assert payload["drift_summary"]["by_code"]["DIGEST_MISMATCH"] == 1


def test_board_projection_live_apply_mode_blocks_before_gh_call(tmp_path: Path) -> None:
    fake_gh, log_path = _fake_gh(tmp_path)
    payload = _run([*_base_args(fake_gh), "--mode", "apply"], expect=1)
    assert payload["status"] == "BLOCKED"
    assert "APPLY_NOT_SUPPORTED_FOR_LIVE_PROJECTION" in payload["blocked_reasons"]
    assert _calls(log_path) == []

