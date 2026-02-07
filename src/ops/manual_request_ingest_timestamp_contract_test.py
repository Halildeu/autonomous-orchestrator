from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.manual_request_cli import build_manual_request
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_manual_request_ingest_timestamp_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    created_at = _now_iso()
    request_id, req, _ = build_manual_request(
        text="contract test: manual request created_at",
        artifact_type="request",
        domain="ops",
        kind="note",
        impact_scope="workspace-only",
        now_iso=created_at,
    )
    _write_json(ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json", req)

    run_work_intake_build(workspace_root=ws)

    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("manual_request_ingest_timestamp_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise SystemExit("manual_request_ingest_timestamp_contract_test failed: items missing")

    manual_items = [it for it in items if isinstance(it, dict) and it.get("source_type") == "MANUAL_REQUEST"]
    if not manual_items:
        raise SystemExit("manual_request_ingest_timestamp_contract_test failed: manual request item missing")

    item = manual_items[0]
    updated_at = item.get("updated_at")
    ingested_at = item.get("ingested_at")
    if updated_at != created_at:
        raise SystemExit("manual_request_ingest_timestamp_contract_test failed: updated_at mismatch")
    if not ingested_at:
        raise SystemExit("manual_request_ingest_timestamp_contract_test failed: ingested_at missing")


if __name__ == "__main__":
    main()
