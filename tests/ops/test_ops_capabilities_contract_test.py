from __future__ import annotations

import json
from pathlib import Path

from src.ops.ops_capabilities import run_ops_capabilities


def test_ops_capabilities_sorted(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    out_path = ws / ".cache" / "reports" / "ops_capabilities.v1.json"

    result = run_ops_capabilities(workspace_root=ws, out_path=out_path)
    assert result.get("status") == "OK"
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    subcommands = payload.get("subcommands", [])
    names = [item.get("name") for item in subcommands]
    assert names == sorted(names)
    for item in subcommands:
        flags = item.get("flags", [])
        assert flags == sorted(flags)
