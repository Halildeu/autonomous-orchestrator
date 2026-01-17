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

    ws = repo_root / ".cache" / "ws_system_status_release_apply_proof_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    proof_payload = {
        "version": "v1",
        "workspace_root": str(ws),
        "apply_mode": "NOOP",
        "generated_at": "2026-01-08T00:00:00Z",
    }
    _write_json(ws / ".cache" / "reports" / "release_apply_proof.v1.json", proof_payload)
    _write_json(ws / ".cache" / "reports" / "release_plan.v1.json", {"version": "v1", "status": "OK"})
    _write_json(ws / ".cache" / "reports" / "release_manifest.v1.json", {"version": "v1", "status": "OK"})

    policy = _load_policy(repo_root, ws)
    report = build_system_status(workspace_root=ws, core_root=repo_root, policy=policy, dry_run=True)
    sections = report.get("sections") if isinstance(report, dict) else {}
    release = sections.get("release") if isinstance(sections, dict) else None
    if not isinstance(release, dict):
        raise SystemExit("system_status_release_apply_proof_contract_test failed: missing release section")
    if release.get("last_apply_proof_path") != ".cache/reports/release_apply_proof.v1.json":
        raise SystemExit("system_status_release_apply_proof_contract_test failed: path mismatch")
    if release.get("last_apply_mode") != "NOOP":
        raise SystemExit("system_status_release_apply_proof_contract_test failed: mode mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
