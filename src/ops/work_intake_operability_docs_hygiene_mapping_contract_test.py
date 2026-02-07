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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_docs_hygiene"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    gap_register_path = ws / ".cache" / "index" / "gap_register.v1.json"
    _write_json(
        gap_register_path,
        {
            "version": "v1",
            "generated_at": "2026-01-07T00:00:00Z",
            "gaps": [
                {
                    "id": "GAP-EVAL-LENS-operability-docs-test1",
                    "metric_id": "eval_lens:operability:operability_docs_ops_md_count_gt",
                    "severity": "medium",
                    "risk_class": "medium",
                    "effort": "medium",
                    "status": "open",
                    "notes": "docs ops count",
                },
                {
                    "id": "GAP-EVAL-LENS-operability-docs-test2",
                    "metric_id": "eval_lens:operability:operability_repo_md_total_count_gt",
                    "severity": "medium",
                    "risk_class": "medium",
                    "effort": "medium",
                    "status": "open",
                    "notes": "repo md count",
                },
            ],
        },
    )

    run_work_intake_build(workspace_root=ws)
    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("work_intake_operability_docs_hygiene_mapping_contract_test failed: intake missing")

    intake = _load_json(intake_path)
    items = intake.get("items") if isinstance(intake, dict) else None
    if not isinstance(items, list):
        raise SystemExit("work_intake_operability_docs_hygiene_mapping_contract_test failed: items missing")

    expected = {
        "operability_docs_ops_md_count_gt": "TICKET",
        "operability_repo_md_total_count_gt": "PROJECT",
    }
    for reason, bucket in expected.items():
        match = [i for i in items if isinstance(i, dict) and i.get("lens_reason") == reason]
        if not match:
            raise SystemExit(
                "work_intake_operability_docs_hygiene_mapping_contract_test failed: missing reason " + reason
            )
        for item in match:
            if item.get("bucket") != bucket:
                raise SystemExit(
                    "work_intake_operability_docs_hygiene_mapping_contract_test failed: bucket mismatch for " + reason
                )
            suggested = item.get("suggested_extension")
            if isinstance(suggested, list) and "PRJ-AIRUNNER" in suggested:
                raise SystemExit(
                    "work_intake_operability_docs_hygiene_mapping_contract_test failed: suggested_extension invalid"
                )

    print(json.dumps({"status": "OK", "items": len(items)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
