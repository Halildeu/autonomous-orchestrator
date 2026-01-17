from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _priority_rank(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(value, 9)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))
    from src.ops.work_intake_from_sources import run_work_intake_build
    ws = repo_root / ".cache" / "ws_intake_test"
    if ws.exists():
        shutil.rmtree(ws)

    index_dir = ws / ".cache" / "index"
    report_dir = ws / ".cache" / "reports"
    budget_dir = ws / ".cache" / "script_budget"
    index_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    budget_dir.mkdir(parents=True, exist_ok=True)

    gap_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "gaps": [
            {
                "id": "GAP-LOW",
                "control_id": "CTRL-LOW",
                "metric_id": "METRIC-LOW",
                "severity": "low",
                "risk_class": "low",
                "effort": "low",
                "report_only": False,
                "evidence_pointers": [".cache/index/assessment_raw.v1.json"],
            },
            {
                "id": "GAP-MED",
                "control_id": "CTRL-MED",
                "metric_id": "METRIC-MED",
                "severity": "medium",
                "risk_class": "medium",
                "effort": "medium",
                "report_only": False,
                "evidence_pointers": [".cache/index/assessment_raw.v1.json"],
            }
        ],
    }
    _write_json(index_dir / "gap_register.v1.json", gap_payload)

    regression_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "regressions": [{"gap_id": "GAP-REG-1", "severity": "high"}],
    }
    _write_json(index_dir / "regression_index.v1.json", regression_payload)

    pdca_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "status": "OK",
        "notes": [],
    }
    _write_json(report_dir / "pdca_recheck_report.v1.json", pdca_payload)

    script_budget_payload = {
        "version": "v1",
        "status": "WARN",
        "exceeded_soft": [{"path": "src/ops/work_intake_from_sources.py", "lines": 999, "rule": "soft"}],
        "exceeded_hard": [],
    }
    _write_json(budget_dir / "report.json", script_budget_payload)

    result = run_work_intake_build(workspace_root=ws)
    status = result.get("status") if isinstance(result, dict) else None
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Work intake contract test failed: build status must be OK, WARN, or IDLE.")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("Work intake contract test failed: work_intake.v1.json missing.")

    schema_path = repo_root / "schemas" / "work-intake.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        raise SystemExit(f"Work intake contract test failed: schema invalid at {where}.")

    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("total_count") != len(items):
        raise SystemExit("Work intake contract test failed: summary.total_count mismatch.")
    if not isinstance(summary.get("counts_by_bucket"), dict):
        raise SystemExit("Work intake contract test failed: summary.counts_by_bucket missing.")
    top_next = summary.get("top_next_actions")
    if not isinstance(top_next, list):
        raise SystemExit("Work intake contract test failed: summary.top_next_actions missing.")
    if items and summary.get("next_intake_focus") in {None, "", "NONE"}:
        raise SystemExit("Work intake contract test failed: next_intake_focus must be set when items exist.")

    bucket_order = ["INCIDENT", "TICKET", "PROJECT", "ROADMAP"]
    bucket_rank = {b: i for i, b in enumerate(bucket_order)}
    prev_key = None
    for item in items:
        if not isinstance(item, dict):
            raise SystemExit("Work intake contract test failed: item must be object.")
        key = (
            bucket_rank.get(str(item.get("bucket")), 99),
            _priority_rank(str(item.get("priority"))),
            str(item.get("intake_id")),
        )
        if prev_key is not None and key < prev_key:
            raise SystemExit("Work intake contract test failed: ordering is not deterministic.")
        prev_key = key
        evidence = item.get("evidence_paths")
        if not isinstance(evidence, list):
            raise SystemExit("Work intake contract test failed: evidence_paths must be a list.")
        for p in evidence:
            if not isinstance(p, str):
                continue
            if p.startswith("/") or ".." in p.split("/"):
                raise SystemExit("Work intake contract test failed: evidence_paths must be workspace-relative.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
