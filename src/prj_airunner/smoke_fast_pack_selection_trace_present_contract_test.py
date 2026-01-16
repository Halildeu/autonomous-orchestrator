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


def _write_expected_paths_report(report_path: Path) -> None:
    payload = {
        "version": "v1",
        "source": "contract_test",
        "raw_hits_sorted": ["pack_selection_trace.v1.json"],
        "expected_paths_sorted": [".cache/index/pack_selection_trace.v1.json"],
        "rule": "must exist and be json_valid (parseable JSON)",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner import smoke_full_job

    report_path = (
        repo_root
        / ".cache"
        / "ws_customer_default"
        / ".cache"
        / "reports"
        / "pack_selection_trace_expected_paths.v1.json"
    )
    original = report_path.read_text(encoding="utf-8") if report_path.exists() else None

    try:
        _write_expected_paths_report(report_path)
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_root = Path(tmp_dir)
            smoke_full_job._ensure_demo_pack_selection_trace(ws_root)

            trace_path = ws_root / ".cache" / "index" / "pack_selection_trace.v1.json"
            if not trace_path.exists():
                raise SystemExit("pack_selection_trace missing after ensure")
            try:
                obj = json.loads(trace_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise SystemExit("pack_selection_trace invalid JSON") from exc
            selected = obj.get("selected_pack_ids") if isinstance(obj, dict) else None
            selected_ids = [s for s in selected if isinstance(s, str)] if isinstance(selected, list) else []
            if not selected_ids:
                raise SystemExit("pack_selection_trace missing selected_pack_ids")

            first = trace_path.read_text(encoding="utf-8")
            smoke_full_job._ensure_demo_pack_selection_trace(ws_root)
            second = trace_path.read_text(encoding="utf-8")
            if first != second:
                raise SystemExit("pack_selection_trace ensure not deterministic")
    finally:
        if original is None:
            if report_path.exists():
                report_path.unlink()
        else:
            report_path.write_text(original, encoding="utf-8")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
