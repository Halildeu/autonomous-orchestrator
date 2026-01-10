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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class _StubResult:
    returncode = 0


def _stub_run(*_args, **_kwargs):
    return _StubResult()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    import src.ops.preflight_stamp as stamp_mod

    ws = repo_root / ".cache" / "ws_preflight_stamp_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    res_missing = stamp_mod.run_preflight_stamp(workspace_root=ws, mode="read")
    if res_missing.get("status") != "IDLE" or res_missing.get("error_code") != "NO_PREFLIGHT_STAMP":
        raise SystemExit("preflight_stamp_contract_test failed: missing stamp should return IDLE")

    sb_path = ws / ".cache" / "script_budget" / "report.json"
    _write_json(
        sb_path,
        {
            "status": "OK",
            "exceeded_hard": [],
            "exceeded_soft": [],
            "function_hard": [],
            "function_soft": [],
        },
    )

    original_run = stamp_mod.subprocess.run
    stamp_mod.subprocess.run = _stub_run
    try:
        res_write = stamp_mod.run_preflight_stamp(workspace_root=ws, mode="write")
    finally:
        stamp_mod.subprocess.run = original_run

    report_path = ws / ".cache" / "reports" / "preflight_stamp.v1.json"
    if not report_path.exists():
        raise SystemExit("preflight_stamp_contract_test failed: report missing")

    schema_path = repo_root / "schemas" / "preflight-stamp.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(_load_json(report_path))

    if res_write.get("overall") != "PASS":
        raise SystemExit("preflight_stamp_contract_test failed: expected overall PASS")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
