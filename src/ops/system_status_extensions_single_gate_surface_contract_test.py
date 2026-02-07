from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"system_status_extensions_single_gate_surface_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_system_status_extensions_single_gate_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    registry_payload = {
        "version": "v1",
        "status": "OK",
        "counts": {"total": 1, "enabled": 1},
        "extensions": [
            {
                "extension_id": "PRJ-ENFORCEMENT-PACK",
                "enabled": True,
                "manifest_path": "extensions/PRJ-ENFORCEMENT-PACK/extension.manifest.v1.json",
            }
        ],
        "notes": [],
    }
    _write_json(ws / ".cache" / "index" / "extension_registry.v1.json", registry_payload)

    expected_contract = (
        ".cache/reports/enforcement_check/PRJ-ENFORCEMENT-PACK/"
        "enforcement_check.20260206T000000Z.v1.json"
    )
    extension_run_payload = {
        "version": "v1",
        "status": "WARN",
        "extension_id": "PRJ-ENFORCEMENT-PACK",
        "selected_single_gate": "enforcement-check",
        "single_gate_status": "BLOCKED",
        "single_gate_outputs": {"contract_json": expected_contract},
    }
    _write_json(
        ws / ".cache" / "reports" / "extension_run.PRJ-ENFORCEMENT-PACK.v1.json",
        extension_run_payload,
    )

    policy = _load_policy(repo_root, ws)
    report = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = report.get("sections") if isinstance(report, dict) else {}
    ext = sections.get("extensions") if isinstance(sections, dict) else None
    _must(isinstance(ext, dict), "extensions section missing")

    _must(ext.get("single_gate_status") == "BLOCKED", "single_gate_status mismatch")
    _must(ext.get("last_enforcement_contract_path") == expected_contract, "last_enforcement_contract_path mismatch")
    _must(
        ext.get("last_enforcement_extension_run_path") == ".cache/reports/extension_run.PRJ-ENFORCEMENT-PACK.v1.json",
        "last_enforcement_extension_run_path mismatch",
    )

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
