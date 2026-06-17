from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

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


def _assert_wrapper_shape(payload: dict) -> None:
    for key in [
        "version",
        "command",
        "mode",
        "status",
        "projection_path",
        "drift_summary",
        "applied_actions",
        "blocked_reasons",
        "evidence",
    ]:
        assert key in payload
    assert payload["version"] == "v1"
    assert payload["command"] == "board-projection"
    assert payload["applied_actions"] == []
    assert payload["evidence"]["does_not_prove"]


def _validate_projection(path: Path) -> dict:
    schema = json.loads((ROOT / "schemas/board-projection.schema.v1.json").read_text(encoding="utf-8"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda err: err.json_path)
    assert errors == []
    return payload


def test_board_projection_happy_writes_schema_valid_projection(tmp_path: Path) -> None:
    out = ".cache/reports/board_projection.v1.json"
    payload = _run(
        [
            "board-projection",
            "--workspace-root",
            str(tmp_path),
            "--fixture",
            "fixtures/board/board_projection_happy.v1.json",
            "--out",
            out,
        ]
    )
    _assert_wrapper_shape(payload)
    assert payload["status"] == "OK"
    assert payload["drift_summary"]["total"] == 0
    assert payload["projection_path"] == out

    projection = _validate_projection(tmp_path / out)
    assert projection["kind"] == "board_projection"
    assert projection["drift"] == []


def test_board_projection_forbidden_done_reports_error_drift_without_apply() -> None:
    payload = _run(
        [
            "board-projection",
            "--fixture",
            "fixtures/board/board_projection_forbidden_done.v1.json",
            "--out",
            "none",
        ]
    )
    _assert_wrapper_shape(payload)
    assert payload["status"] == "WARN"
    assert payload["drift_summary"]["by_code"]["FORBIDDEN_DONE"] >= 1
    assert payload["drift_summary"]["by_severity"]["ERROR"] >= 1
    assert payload["applied_actions"] == []


def test_board_projection_missing_field_reports_warn_drift() -> None:
    payload = _run(
        [
            "board-projection",
            "--fixture",
            "fixtures/board/projection_missing_field.v1.json",
            "--out",
            "none",
        ]
    )
    _assert_wrapper_shape(payload)
    assert payload["status"] == "WARN"
    assert payload["drift_summary"]["by_code"]["MISSING_FIELD"] >= 1
    assert payload["drift_summary"]["max_severity"] == "WARN"
    assert payload["applied_actions"] == []


def test_board_projection_apply_mode_is_blocked_until_bog_5c() -> None:
    payload = _run(
        [
            "board-projection",
            "--fixture",
            "fixtures/board/board_projection_happy.v1.json",
            "--mode",
            "apply",
            "--out",
            "none",
        ],
        expect=1,
    )
    _assert_wrapper_shape(payload)
    assert payload["status"] == "BLOCKED"
    assert "APPLY_MODE_NOT_AVAILABLE_UNTIL_BOG_5C" in payload["blocked_reasons"]
    assert payload["applied_actions"] == []
