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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.smoke_full_job import _pin_advisor_output

    job_id = "contract-advisor-pin-fallback"
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        rc_path = ws_root / ".cache" / "github_ops" / "jobs" / job_id / "rc.json"
        rc_path.parent.mkdir(parents=True, exist_ok=True)
        rc_path.write_text(json.dumps({"rc": 1}) + "\n", encoding="utf-8")

        _pin_advisor_output(workspace_root=ws_root, rc_path=rc_path)

        artifact_path = (
            ws_root
            / ".cache"
            / "reports"
            / "jobs"
            / f"smoke_full_{job_id}"
            / "advisor_suggestions.v1.json"
        )
        if not artifact_path.exists():
            raise SystemExit("advisor_pin_fallback_contract_test failed: artifact missing")
        payload = _load_json(artifact_path)
        if payload.get("workspace_root") != str(ws_root):
            raise SystemExit("advisor_pin_fallback_contract_test failed: workspace_root mismatch")
        suggestions = payload.get("suggestions") if isinstance(payload, dict) else None
        if not isinstance(suggestions, list) or not suggestions:
            raise SystemExit("advisor_pin_fallback_contract_test failed: suggestions list empty")

        schema_path = repo_root / "schemas" / "advisor-suggestions.schema.json"
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(payload)

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
