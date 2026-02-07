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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.learning.advisor_suggest import run_advisor_for_workspace

    schema_path = repo_root / "schemas" / "advisor-suggestions.schema.json"
    if not schema_path.exists():
        raise SystemExit("advisor_suggestions_demo_root_contract_test failed: schema missing")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        run_advisor_for_workspace(workspace_root=ws_root, core_root=repo_root, dry_run=False)
        out_path = ws_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
        if not out_path.exists():
            raise SystemExit("advisor_suggestions_demo_root_contract_test failed: output missing")
        bundle = json.loads(out_path.read_text(encoding="utf-8"))
        validator.validate(bundle)

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
