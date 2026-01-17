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


def _load_expected_shape(report_path: Path) -> list[str]:
    obj = json.loads(report_path.read_text(encoding="utf-8"))
    keys = obj.get("required_keys_heuristic") if isinstance(obj, dict) else None
    if not isinstance(keys, list):
        return []
    return [k for k in keys if isinstance(k, str) and k.strip()]


def _semantic_ok(obj: dict, required_keys: list[str]) -> bool:
    if not isinstance(obj, dict):
        return False
    for key in required_keys:
        if key not in obj:
            return False
    selected = obj.get("selected_pack_ids")
    if not isinstance(selected, list):
        return False
    return any(isinstance(s, str) and s.strip() for s in selected)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner import smoke_full_job

    shape_report = (
        repo_root
        / ".cache"
        / "ws_customer_default"
        / ".cache"
        / "reports"
        / "pack_selection_trace_expected_shape.v0.1.7.json"
    )
    if not shape_report.exists():
        raise SystemExit("expected shape report missing")
    required_keys = _load_expected_shape(shape_report)

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        smoke_full_job._ensure_demo_pack_selection_trace(ws_root)

        selection_paths = smoke_full_job._load_expected_pack_selection_paths(ws_root)
        if not selection_paths:
            raise SystemExit("pack_selection_trace paths missing")

        for selection_path in selection_paths:
            if not selection_path.exists():
                raise SystemExit("pack_selection_trace missing after ensure")
            try:
                obj = json.loads(selection_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise SystemExit("pack_selection_trace invalid JSON") from exc
            if not _semantic_ok(obj, required_keys):
                raise SystemExit("pack_selection_trace semantic check failed")

        before = {str(p): p.read_text(encoding="utf-8") for p in selection_paths}
        smoke_full_job._ensure_demo_pack_selection_trace(ws_root)
        after = {str(p): p.read_text(encoding="utf-8") for p in selection_paths}
        if before != after:
            raise SystemExit("pack_selection_trace ensure not deterministic")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
