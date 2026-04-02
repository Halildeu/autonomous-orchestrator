from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_WORKSPACE_DIRS = ("schemas", "policies", "registry")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clone_workspace(*, root: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in _WORKSPACE_DIRS:
        shutil.copytree(root / rel, workspace / rel)


def main() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from src.ops.ai_entry_pack_build import (
        ai_entry_pack_path,
        ai_entry_pack_runtime_state,
        build_ai_entry_pack,
        ensure_ai_entry_pack,
    )
    from src.utils.jsonio import load_json

    with tempfile.TemporaryDirectory(prefix="ai-entry-pack-build-") as td:
        workspace = Path(td) / "ws"
        _clone_workspace(root=root, workspace=workspace)
        result = build_ai_entry_pack(workspace_root=workspace)
        if result.get("status") != "OK":
            raise SystemExit("ai_entry_pack_build_contract_test failed: status")
        state = ai_entry_pack_runtime_state(workspace_root=workspace)
        if not bool(state.get("health", {}).get("valid", False)):
            raise SystemExit("ai_entry_pack_build_contract_test failed: runtime state invalid")
        if bool(state.get("needs_refresh", False)):
            raise SystemExit("ai_entry_pack_build_contract_test failed: fresh pack should not need refresh")
        payload = load_json(ai_entry_pack_path(workspace))
        refs = payload.get("refs") if isinstance(payload.get("refs"), dict) else {}
        for key in (
            "active_execution_registry",
            "apps_and_launch_registry",
            "version_registry",
            "authority_matrix",
            "duplicate_surface_register",
        ):
            if not str(refs.get(key) or "").strip():
                raise SystemExit(f"ai_entry_pack_build_contract_test failed: missing ref {key}")
        if str(payload.get("status") or "").strip() != "READY":
            raise SystemExit("ai_entry_pack_build_contract_test failed: status READY expected")
        (workspace / "registry" / "version_registry.v1.json").write_text(
            (workspace / "registry" / "version_registry.v1.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        refreshed = ensure_ai_entry_pack(workspace_root=workspace, allow_write=True)
        if not bool(refreshed.get("auto_refreshed", False)):
            raise SystemExit("ai_entry_pack_build_contract_test failed: expected auto refresh")
    print("ai_entry_pack_build_contract_test: PASS")


if __name__ == "__main__":
    main()
