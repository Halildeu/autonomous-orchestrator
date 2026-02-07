from __future__ import annotations

import json
import sys
from pathlib import Path


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
    from src.extensions.prj_search.search_check import run_search_check

    ws = repo_root / ".cache" / "ws_search_check_test"
    ws.mkdir(parents=True, exist_ok=True)

    payload = run_search_check(
        workspace_root=ws,
        scope="ssot",
        query="policy",
        mode="keyword",
        chat=False,
    )
    status = str(payload.get("status") or "")
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("search_check_contract_test failed: invalid status")

    report_rel = str(payload.get("report_path") or "")
    report_md_rel = str(payload.get("report_md_path") or "")
    if not report_rel or not report_md_rel:
        raise SystemExit("search_check_contract_test failed: missing report path")

    report_json = ws / report_rel
    report_md = ws / report_md_rel
    if not report_json.exists():
        raise SystemExit("search_check_contract_test failed: report json missing")
    if not report_md.exists():
        raise SystemExit("search_check_contract_test failed: report md missing")

    obj = _load_json(report_json)
    required_keys = {"status", "scope", "query", "mode_requested", "report_path", "report_md_path", "evidence_paths"}
    missing = sorted(k for k in required_keys if k not in obj)
    if missing:
        raise SystemExit(f"search_check_contract_test failed: missing keys {missing}")

    print(json.dumps({"status": "OK", "report_path": report_rel}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
