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

    ws = repo_root / ".cache" / "ws_integration_coherence_raw_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    raw_path = ws / ".cache" / "index" / "assessment_raw.v1.json"
    _write_json(
        raw_path,
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "workspace_root": str(ws),
            "status": "OK",
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "source_hashes": {
                "system_status": None,
                "pack_index": None,
                "quality_gate": None,
                "repo_hygiene": None,
                "harvest": None,
                "script_budget": None,
            },
            "inputs": {"packs": 0, "controls": 0, "metrics": 0, "warnings": []},
            "signals": {
                "script_budget": {"hard_exceeded": 0, "soft_exceeded": 0},
                "doc_nav": {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0},
                "airunner_jobs": {"queued": 0, "running": 0, "fail": 0, "pass": 0, "stuck": 0},
                "pdca_cursor": {"stale_hours": 0.0},
                "airunner_heartbeat": {"stale_seconds": 0},
                "work_intake_noise": {"new_items_24h": 0, "suppressed_24h": 0},
                "integrity": {"status": "PASS"},
            },
            "integration_coherence_signals": {
                "layer_boundary_violations_count": 0,
                "pack_conflict_count": 0,
                "core_unlock_scope_widen_count": 0,
                "schema_fail_count": 0,
            },
            "notes": [],
        },
    )

    schema_path = repo_root / "schemas" / "assessment-raw.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(_load_json(raw_path))

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
