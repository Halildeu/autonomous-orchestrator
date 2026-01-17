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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.decision_inbox import run_decision_inbox_build

    ws = repo_root / ".cache" / "ws_decision_seed_ingest_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    legacy_seed = {
        "version": "v1",
        "seed_id": "seed-doc-nav-timeout",
        "decision_kind": "DOC_NAV_TIMEOUT_POLICY",
        "target": "policy_doc_graph.override.v1.json",
        "question": "Doc nav timeout override policy",
        "default_option_id": "B",
        "options": [
            {"option_id": "A", "title": "KEEP_OVERRIDE", "details": "Keep override as-is"},
            {"option_id": "B", "title": "PROOF_ONLY", "details": "Keep with proof-only note"},
            {"option_id": "C", "title": "REVERT_OVERRIDE", "details": "Backup then remove"},
        ],
    }
    seed_path = ws / ".cache" / "index" / "decision_seed_doc_nav_timeout.v1.json"
    _write_json(seed_path, legacy_seed)

    res = run_decision_inbox_build(workspace_root=ws)
    if res.get("status") not in {"OK", "IDLE"}:
        raise SystemExit("decision_seed_ingest_contract_test failed: inbox status invalid")

    inbox_path = ws / ".cache" / "index" / "decision_inbox.v1.json"
    if not inbox_path.exists():
        raise SystemExit("decision_seed_ingest_contract_test failed: decision_inbox missing")
    inbox = _load_json(inbox_path)
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    if not any(item.get("decision_id") == "seed-doc-nav-timeout" for item in items if isinstance(item, dict)):
        raise SystemExit("decision_seed_ingest_contract_test failed: seed not ingested")

    ingested_path = ws / ".cache" / "index" / "decision_seeds_ingested.v1.jsonl"
    if not ingested_path.exists():
        raise SystemExit("decision_seed_ingest_contract_test failed: ingested index missing")

    decisions_applied = ws / ".cache" / "index" / "decisions_applied.v1.jsonl"
    decisions_applied.parent.mkdir(parents=True, exist_ok=True)
    decisions_applied.write_text(
        json.dumps(
            {
                "decision_id": "seed-doc-nav-timeout",
                "decision_kind": "DOC_NAV_TIMEOUT_POLICY",
                "option_id": "B",
                "applied_at": "2026-01-01T00:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    run_decision_inbox_build(workspace_root=ws)
    inbox_after = _load_json(inbox_path)
    items_after = inbox_after.get("items") if isinstance(inbox_after.get("items"), list) else []
    if any(item.get("decision_id") == "seed-doc-nav-timeout" for item in items_after if isinstance(item, dict)):
        raise SystemExit("decision_seed_ingest_contract_test failed: applied seed still present")


if __name__ == "__main__":
    main()
