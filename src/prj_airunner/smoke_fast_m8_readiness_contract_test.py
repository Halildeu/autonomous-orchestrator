from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _read_schema(repo_root: Path) -> dict:
    schema_path = repo_root / "schemas" / "autopilot-readiness.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _semantic_ok(obj: dict) -> bool:
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"READY", "NOT_READY"}:
        return False
    checks = obj.get("checks") if isinstance(obj, dict) else None
    if not isinstance(checks, list):
        return False
    return any(isinstance(c, dict) and c.get("category") == "WORKSPACE" for c in checks)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner import smoke_full_job

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        out_path = ws_root / ".cache" / "ops" / "autopilot_readiness.v1.json"

        smoke_full_job._ensure_demo_autopilot_readiness(ws_root)
        if not out_path.exists():
            raise SystemExit("autopilot_readiness missing after ensure")
        try:
            obj = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit("autopilot_readiness invalid JSON") from exc

        schema = _read_schema(repo_root)
        Draft202012Validator(schema).validate(obj)
        if not _semantic_ok(obj):
            raise SystemExit("autopilot_readiness missing WORKSPACE check or status")

        first = out_path.read_text(encoding="utf-8")
        smoke_full_job._ensure_demo_autopilot_readiness(ws_root)
        second = out_path.read_text(encoding="utf-8")
        if first != second:
            raise SystemExit("autopilot_readiness ensure not deterministic")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
