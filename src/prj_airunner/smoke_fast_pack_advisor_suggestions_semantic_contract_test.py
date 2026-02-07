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


def _write_expected_paths_report(report_path: Path) -> None:
    payload = {
        "version": "v0.1",
        "source": "contract_test",
        "expected_paths": [".cache/learning/pack_advisor_suggestions.v1.json"],
        "rule": "must exist + json_valid + schema/semantic valid",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _schema_ok(repo_root: Path, obj: dict) -> bool:
    schema_path = repo_root / "schemas" / "pack-advisor-suggestions.schema.json"
    if not schema_path.exists():
        return False
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return False
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(obj)
        return True
    except Exception:
        return False


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner import smoke_full_job

    report_path = (
        repo_root
        / ".cache"
        / "ws_customer_default"
        / ".cache"
        / "reports"
        / "pack_advisor_suggestions_expected_paths.v0.1.json"
    )
    original = report_path.read_text(encoding="utf-8") if report_path.exists() else None

    try:
        _write_expected_paths_report(report_path)
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_root = Path(tmp_dir)
            smoke_full_job._ensure_demo_pack_advisor_suggestions(ws_root)

            paths = smoke_full_job._load_expected_pack_advisor_paths(ws_root)
            if not paths:
                raise SystemExit("pack_advisor_suggestions paths missing")
            for path in paths:
                if not path.exists():
                    raise SystemExit("pack_advisor_suggestions missing after ensure")
                try:
                    obj = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    raise SystemExit("pack_advisor_suggestions invalid JSON") from exc
                if not smoke_full_job._pack_advisor_semantic_ok(obj):
                    raise SystemExit("pack_advisor_suggestions semantic check failed")
                if not _schema_ok(repo_root, obj):
                    raise SystemExit("pack_advisor_suggestions schema check failed")

            before = {str(p): p.read_text(encoding="utf-8") for p in paths}
            smoke_full_job._ensure_demo_pack_advisor_suggestions(ws_root)
            after = {str(p): p.read_text(encoding="utf-8") for p in paths}
            if before != after:
                raise SystemExit("pack_advisor_suggestions ensure not deterministic")
    finally:
        if original is None:
            if report_path.exists():
                report_path.unlink()
        else:
            report_path.write_text(original, encoding="utf-8")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
