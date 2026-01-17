from __future__ import annotations

from pathlib import Path

from src.ops.closeout_write import run_closeout_write


def test_closeout_write_rejects_outside_reports(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    out_path = ws / "outside.json"

    result = run_closeout_write(
        workspace_root=ws,
        out_path=out_path,
        title="Closeout",
        evidence_paths=[],
    )
    assert result.get("status") == "FAIL"
    assert result.get("error_code") == "OUT_PATH_INVALID"
