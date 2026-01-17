from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.extension_help import build_extension_help

    ws = repo_root / ".cache" / "ws_extension_help_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res1 = build_extension_help(workspace_root=ws, detail=False)
    if res1.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("extension_help_contract_test failed: invalid status.")

    report_path = ws / ".cache" / "reports" / "extension_help.v1.json"
    if not report_path.exists():
        raise SystemExit("extension_help_contract_test failed: report missing.")

    schema_path = repo_root / "schemas" / "extension-help.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(_load_json(report_path))

    obj1 = _load_json(report_path)
    if not isinstance(obj1.get("tests_coverage"), dict):
        raise SystemExit("extension_help_contract_test failed: tests_coverage missing.")
    res2 = build_extension_help(workspace_root=ws, detail=False)
    if res2.get("report_path") != res1.get("report_path"):
        raise SystemExit("extension_help_contract_test failed: report path mismatch.")

    obj2 = _load_json(report_path)
    ids1 = [e.get("extension_id") for e in obj1.get("extensions", []) if isinstance(e, dict)]
    ids2 = [e.get("extension_id") for e in obj2.get("extensions", []) if isinstance(e, dict)]
    if ids1 != sorted(ids1):
        raise SystemExit("extension_help_contract_test failed: extension order not stable.")
    if ids1 != ids2:
        raise SystemExit("extension_help_contract_test failed: extension list not deterministic.")

    raw = json.dumps(obj1, ensure_ascii=False, sort_keys=True)
    if "token" in raw.lower():
        raise SystemExit("extension_help_contract_test failed: potential secret exposure.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
