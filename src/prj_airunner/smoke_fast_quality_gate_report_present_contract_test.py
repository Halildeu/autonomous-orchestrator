from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.smoke_full_job import _ensure_demo_quality_gate_report, _quality_gate_report_path

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        result = _ensure_demo_quality_gate_report(ws_root)
        report_path = _quality_gate_report_path(ws_root)
        if not report_path.exists():
            raise SystemExit("smoke_fast_quality_gate_report_present_contract_test failed: report missing")
        try:
            obj = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit("smoke_fast_quality_gate_report_present_contract_test failed: invalid JSON") from exc
        if not isinstance(obj, dict):
            raise SystemExit("smoke_fast_quality_gate_report_present_contract_test failed: report not dict")
        status = obj.get("status")
        if not isinstance(status, str) or not status:
            raise SystemExit("smoke_fast_quality_gate_report_present_contract_test failed: missing status")
        if result.get("status") not in {"OK", "FALLBACK"}:
            raise SystemExit("smoke_fast_quality_gate_report_present_contract_test failed: unexpected ensure status")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
