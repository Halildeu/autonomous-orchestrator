from __future__ import annotations

from pathlib import Path

from src.ops.workspace_find import run_workspace_find


def test_workspace_find_blocks_traversal(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    out_path = ws / ".cache" / "reports" / "workspace_find.v1.json"

    result = run_workspace_find(
        workspace_root=ws,
        name="roadmap",
        out_path=out_path,
        allowlist=["../"],
        max_depth=1,
        max_files=10,
    )
    assert result.get("status") == "FAIL"
    assert result.get("error_code") == "ALLOWLIST_INVALID"

    result_abs = run_workspace_find(
        workspace_root=ws,
        name="roadmap",
        out_path=out_path,
        allowlist=["/tmp"],
        max_depth=1,
        max_files=10,
    )
    assert result_abs.get("status") == "FAIL"
    assert result_abs.get("error_code") == "ALLOWLIST_INVALID"
