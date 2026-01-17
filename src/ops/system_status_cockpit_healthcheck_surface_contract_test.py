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

    from src.ops.system_status_builder import _load_policy, build_system_status

    ws = repo_root / ".cache" / "ws_system_status_cockpit_healthcheck_surface"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    healthcheck_path = ws / ".cache" / "reports" / "cockpit_healthcheck.v1.json"
    _write_json(healthcheck_path, {"version": "v1", "status": "OK", "port": 8787})

    policy = _load_policy(repo_root, ws)
    report = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = report.get("sections") if isinstance(report, dict) else {}
    ext = sections.get("extensions") if isinstance(sections, dict) else None
    if not isinstance(ext, dict):
        raise SystemExit("system_status_cockpit_healthcheck_surface_contract_test failed: extensions missing")
    expected = ".cache/reports/cockpit_healthcheck.v1.json"
    if ext.get("last_cockpit_healthcheck_path") != expected:
        raise SystemExit("system_status_cockpit_healthcheck_surface_contract_test failed: path mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
