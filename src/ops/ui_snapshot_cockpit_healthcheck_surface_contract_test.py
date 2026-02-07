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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.system_status_report import run_system_status
    from src.ops.ui_snapshot_bundle import build_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_ui_snapshot_cockpit_healthcheck_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    healthcheck_rel = Path(".cache") / "reports" / "cockpit_healthcheck.v1.json"
    _write_json(ws / healthcheck_rel, {"version": "v1", "status": "OK", "port": 8787})

    run_system_status(workspace_root=ws, core_root=repo_root, dry_run=False)
    ui_payload = build_ui_snapshot_bundle(workspace_root=ws)

    expected = str(healthcheck_rel)
    if ui_payload.get("last_cockpit_healthcheck_path") != expected:
        raise SystemExit("ui_snapshot_cockpit_healthcheck_surface_contract_test failed: path mismatch")
    if ui_payload.get("cockpit_port") != 8787:
        raise SystemExit("ui_snapshot_cockpit_healthcheck_surface_contract_test failed: port mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
