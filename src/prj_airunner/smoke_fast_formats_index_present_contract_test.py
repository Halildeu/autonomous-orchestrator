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

    from src.prj_airunner.smoke_full_job import _ensure_demo_formats_index, _formats_index_path

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        result = _ensure_demo_formats_index(ws_root)
        formats_path = _formats_index_path(ws_root)
        if not formats_path.exists():
            raise SystemExit("smoke_fast_formats_index_present_contract_test failed: formats index missing")
        try:
            obj = json.loads(formats_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit("smoke_fast_formats_index_present_contract_test failed: invalid JSON") from exc
        if not isinstance(obj, dict):
            raise SystemExit("smoke_fast_formats_index_present_contract_test failed: formats index not dict")
        if not isinstance(obj.get("formats"), list):
            raise SystemExit("smoke_fast_formats_index_present_contract_test failed: formats list missing")
        if result.get("status") not in {"OK", "FALLBACK"}:
            raise SystemExit("smoke_fast_formats_index_present_contract_test failed: unexpected status")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
