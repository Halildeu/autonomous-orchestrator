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

    from src.prj_airunner import smoke_full_job

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        smoke_full_job._ensure_demo_pack_capability_index(ws_root)

        index_path = ws_root / ".cache" / "index" / "pack_capability_index.v1.json"
        if not index_path.exists():
            raise SystemExit("pack_capability_index missing after ensure")
        try:
            obj = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("pack_capability_index invalid JSON") from e
        packs = obj.get("packs") if isinstance(obj, dict) else None
        pack_ids = {
            p.get("pack_id")
            for p in packs
            if isinstance(p, dict) and isinstance(p.get("pack_id"), str)
        } if isinstance(packs, list) else set()
        expected = {"pack-document-management", "pack-software-architecture"}
        if not expected.issubset(pack_ids):
            raise SystemExit("pack_capability_index missing expected pack ids")

        first = index_path.read_text(encoding="utf-8")
        smoke_full_job._ensure_demo_pack_capability_index(ws_root)
        second = index_path.read_text(encoding="utf-8")
        if first != second:
            raise SystemExit("pack_capability_index ensure not deterministic")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
