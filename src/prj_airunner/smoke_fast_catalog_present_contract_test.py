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

    from src.prj_airunner.smoke_full_job import _catalog_has_pack_demo, _catalog_path, _ensure_demo_catalog

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        result = _ensure_demo_catalog(ws_root)
        catalog_path = _catalog_path(ws_root)
        if not catalog_path.exists():
            raise SystemExit("smoke_fast_catalog_present_contract_test failed: catalog missing")
        if not _catalog_has_pack_demo(catalog_path):
            raise SystemExit("smoke_fast_catalog_present_contract_test failed: pack-demo missing")
        try:
            obj = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit("smoke_fast_catalog_present_contract_test failed: invalid JSON") from exc
        if not isinstance(obj, dict):
            raise SystemExit("smoke_fast_catalog_present_contract_test failed: catalog not dict")
        if result.get("status") not in {"OK", "FALLBACK"}:
            raise SystemExit("smoke_fast_catalog_present_contract_test failed: unexpected status")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
