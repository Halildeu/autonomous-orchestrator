from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.ui_snapshot_bundle import run_ui_snapshot_bundle

    ws = repo_root / ".cache" / "ws_ui_snapshot_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(ws / ".cache" / "reports" / "system_status.v1.json", {"status": "OK"})
    _write_json(ws / ".cache" / "reports" / "portfolio_status.v1.json", {"status": "OK"})
    _write_json(
        ws / ".cache" / "index" / "work_intake.v1.json",
        {"version": "v1", "items": [{"bucket": "TICKET"}, {"bucket": "PROJECT"}]},
    )
    _write_json(ws / ".cache" / "reports" / "airunner_tick.v1.json", {"version": "v1", "status": "OK"})
    _write_json(ws / ".cache" / "reports" / "airunner_deltas.v1.json", {"version": "v1"})
    _write_json(ws / ".cache" / "reports" / "airunner_proof_bundle.v1.json", {"version": "v1"})
    _write_json(
        ws / ".cache" / "airunner" / "jobs_index.v1.json",
        {"version": "v1", "counts": {"queued": 1, "running": 0, "pass": 0, "fail": 0}},
    )
    _write_json(
        ws / ".cache" / "index" / "extension_registry.v1.json",
        {"version": "v1", "count_total": 2, "extensions": []},
    )
    _write_json(ws / ".cache" / "reports" / "release_plan.v1.json", {"version": "v1", "status": "OK"})
    _write_json(
        ws / ".cache" / "reports" / "release_manifest.v1.json",
        {"version": "v1", "status": "OK"},
    )
    _write_json(
        ws / ".cache" / "reports" / "release_apply_proof.v1.json",
        {"version": "v1", "apply_mode": "NOOP"},
    )
    (ws / ".cache" / "reports" / "release_notes.v1.md").write_text("Release notes\n", encoding="utf-8")
    _write_json(
        ws / ".cache" / "reports" / "github_ops_report.v1.json",
        {"version": "v1", "status": "OK", "jobs_index_path": ".cache/github_ops/jobs_index.v1.json"},
    )
    _write_json(
        ws / ".cache" / "github_ops" / "jobs_index.v1.json",
        {"version": "v1", "counts": {"queued": 0, "running": 0, "pass": 0, "fail": 0}},
    )
    _write_json(
        ws / ".cache" / "reports" / "airunner_proof_bundle.v1.json",
        {"version": "v1", "poll_only_observed": True, "start_only_observed": True},
    )

    out_one = run_ui_snapshot_bundle(workspace_root=ws)
    report_path = ws / ".cache" / "reports" / "ui_snapshot_bundle.v1.json"
    if not report_path.exists():
        raise SystemExit("ui_snapshot_contract_test failed: report missing")

    schema_path = repo_root / "schemas" / "ui-snapshot-bundle.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(_load_json(report_path))

    first = _load_json(report_path)
    out_two = run_ui_snapshot_bundle(workspace_root=ws)
    second = _load_json(report_path)
    first["generated_at"] = "fixed"
    second["generated_at"] = "fixed"
    if first != second:
        raise SystemExit("ui_snapshot_contract_test failed: output not deterministic")

    if out_one.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("ui_snapshot_contract_test failed: status invalid")

    if first.get("last_airunner_proof_bundle_path") != ".cache/reports/airunner_proof_bundle.v1.json":
        raise SystemExit("ui_snapshot_contract_test failed: proof bundle path missing")
    if first.get("paths", {}).get("release_apply_proof") != ".cache/reports/release_apply_proof.v1.json":
        raise SystemExit("ui_snapshot_contract_test failed: release apply proof path missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
