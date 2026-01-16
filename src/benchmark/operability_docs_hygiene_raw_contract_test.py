from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _docs_hygiene_from(raw: dict) -> dict:
    signals = raw.get("signals") if isinstance(raw, dict) else {}
    signals = signals if isinstance(signals, dict) else {}
    return signals.get("docs_hygiene") if isinstance(signals.get("docs_hygiene"), dict) else {}


def _validate_docs_hygiene(docs_hygiene: dict) -> None:
    for key in ("docs_ops_md_count", "docs_ops_md_bytes", "repo_md_total_count"):
        val = docs_hygiene.get(key)
        if not isinstance(val, int) or val < 0:
            raise SystemExit(f"operability_docs_hygiene_raw_contract_test failed: {key} missing or invalid")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import run_assessment

    ws = repo_root / ".cache" / "ws_operability_docs_hygiene_raw"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    run_assessment(workspace_root=ws, dry_run=False)
    raw_path = ws / ".cache" / "index" / "assessment_raw.v1.json"
    if not raw_path.exists():
        raise SystemExit("operability_docs_hygiene_raw_contract_test failed: assessment_raw missing")
    raw_first = _load_json(raw_path)
    docs_first = _docs_hygiene_from(raw_first)
    _validate_docs_hygiene(docs_first)

    run_assessment(workspace_root=ws, dry_run=False)
    raw_second = _load_json(raw_path)
    docs_second = _docs_hygiene_from(raw_second)
    _validate_docs_hygiene(docs_second)

    if docs_first != docs_second:
        raise SystemExit("operability_docs_hygiene_raw_contract_test failed: docs_hygiene drift")

    print(json.dumps({"status": "OK", "docs_hygiene": docs_first}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
