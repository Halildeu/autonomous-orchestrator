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

    from src.prj_airunner import smoke_full_job

    tmp_parent = repo_root / ".cache"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_parent) as tmp_dir:
        tmp_root = Path(tmp_dir)
        ws_dry_run = tmp_root / "ws_dry_run"
        ws_integration = tmp_root / "ws_integration"
        ws_dry_run.mkdir(parents=True, exist_ok=True)
        ws_integration.mkdir(parents=True, exist_ok=True)

        result = smoke_full_job._ensure_demo_system_status(ws_integration)
        if result.get("status") != "OK":
            raise SystemExit(f"system_status ensure failed: {result}")

        out_json = ws_integration / ".cache" / "reports" / "system_status.v1.json"
        out_md = ws_integration / ".cache" / "reports" / "system_status.v1.md"
        if not out_json.exists() or not out_md.exists():
            raise SystemExit("system_status outputs missing after ensure")

        try:
            report = json.loads(out_json.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit("system_status invalid JSON") from exc

        schema_path = repo_root / "schemas" / "system-status.schema.json"
        if not schema_path.exists():
            raise SystemExit("system_status schema missing")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)

        md_text = out_md.read_text(encoding="utf-8")
        required_headings = [
            "ISO Core",
            "Spec Core",
            "Core integrity",
            "Core lock",
            "Project boundary",
            "Projects",
            "Extensions",
            "Release",
            "Catalog",
            "Packs",
            "Formats",
            "Session",
            "Quality",
            "Harvest",
            "Advisor",
            "Pack Advisor",
            "Readiness",
            "Actions",
            "Repo hygiene",
            "Doc graph",
            "Auto-heal",
        ]
        for heading in required_headings:
            if heading not in md_text:
                raise SystemExit(f"system_status MD missing heading: {heading}")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
