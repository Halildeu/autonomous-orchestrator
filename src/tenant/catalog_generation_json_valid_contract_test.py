from __future__ import annotations

import json
import shutil
import sys
from hashlib import sha256
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.tenant.build_catalog import main as build_catalog_main

    ws_root = repo_root / ".cache" / "ws_catalog_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    ws_root.mkdir(parents=True, exist_ok=True)

    out_path = ws_root / ".cache" / "index" / "catalog.v1.json"

    rc = build_catalog_main(["--workspace-root", str(ws_root), "--out", str(out_path), "--dry-run", "false"])
    if rc != 0:
        raise SystemExit("catalog_generation_json_valid_contract_test failed: first run rc != 0")
    if not out_path.exists():
        raise SystemExit("catalog_generation_json_valid_contract_test failed: output missing")
    content = out_path.read_text(encoding="utf-8")
    try:
        json.loads(content)
    except Exception as e:
        raise SystemExit("catalog_generation_json_valid_contract_test failed: output not valid JSON") from e
    first_hash = _hash_text(content)

    rc = build_catalog_main(["--workspace-root", str(ws_root), "--out", str(out_path), "--dry-run", "false"])
    if rc != 0:
        raise SystemExit("catalog_generation_json_valid_contract_test failed: second run rc != 0")
    content_second = out_path.read_text(encoding="utf-8")
    second_hash = _hash_text(content_second)
    if first_hash != second_hash:
        raise SystemExit("catalog_generation_json_valid_contract_test failed: output hash drift")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
