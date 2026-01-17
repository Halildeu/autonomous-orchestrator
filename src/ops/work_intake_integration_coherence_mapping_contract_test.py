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

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_integration_coherence"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    gap_id = "GAP-EVAL-LENS-integration_coherence-pack_conflicts_fail"
    gap_register = {
        "version": "v1",
        "generated_at": "2026-01-07T00:00:00Z",
        "gaps": [
            {
                "id": gap_id,
                "metric_id": "eval_lens:integration_coherence:pack_conflicts_fail",
                "severity": "high",
                "risk_class": "high",
                "effort": "medium",
                "status": "open",
                "notes": "Integration coherence FAIL: pack conflicts.",
            }
        ],
    }
    _write_json(ws / ".cache" / "index" / "gap_register.v1.json", gap_register)

    run_work_intake_build(workspace_root=ws)
    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_integration_coherence_mapping_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_integration_coherence_mapping_contract_test failed: items missing")
    lens_items = [i for i in items if isinstance(i, dict) and i.get("source_ref") == gap_id]
    if not lens_items:
        raise SystemExit("work_intake_integration_coherence_mapping_contract_test failed: lens gap intake missing")
    buckets = {i.get("bucket") for i in lens_items if isinstance(i, dict)}
    if "INCIDENT" not in buckets:
        raise SystemExit(
            "work_intake_integration_coherence_mapping_contract_test failed: expected INCIDENT bucket"
        )

    print(json.dumps({"status": "OK", "bucket": sorted(buckets)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
