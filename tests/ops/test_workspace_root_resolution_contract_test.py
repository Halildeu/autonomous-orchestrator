from __future__ import annotations

from pathlib import Path

from src.ops.commands.common import resolve_workspace_root_arg
from src.ops.test_run import _test_roadmap_state_path


def test_resolve_workspace_root_prefers_customer_workspace_for_repo_root_argument(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    customer_ws = root / ".cache" / "ws_customer_default"
    customer_ws.mkdir(parents=True, exist_ok=True)

    resolved = resolve_workspace_root_arg(root, ".", prefer_customer_workspace=True)

    assert resolved == customer_ws.resolve()


def test_resolve_workspace_root_preserves_explicit_workspace(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    explicit_ws = root / "sandbox-ws"
    explicit_ws.mkdir(parents=True, exist_ok=True)
    (root / ".cache" / "ws_customer_default").mkdir(parents=True, exist_ok=True)

    resolved = resolve_workspace_root_arg(root, "sandbox-ws", prefer_customer_workspace=True)

    assert resolved == explicit_ws.resolve()


def test_test_run_uses_index_state_path(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir(parents=True, exist_ok=True)

    state_path = _test_roadmap_state_path(workspace_root)

    assert state_path == workspace_root / ".cache" / "index" / "roadmap_state.v1.json"
