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


def _parse_iso(value: str) -> None:
    if not value:
        raise ValueError("missing timestamp")
    if value.endswith("Z"):
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        datetime.fromisoformat(value)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.manual_request_cli import build_manual_request
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_timestamp_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now = _now_iso()
    request_id, req, _ = build_manual_request(
        text="contract test: timestamp required",
        artifact_type="request",
        domain="ops",
        kind="note",
        impact_scope="workspace-only",
        now_iso=now,
    )
    _write_json(ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json", req)

    run_work_intake_build(workspace_root=ws)

    out_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not out_path.exists():
        raise SystemExit("work_intake_timestamp_required_contract_test failed: output missing")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise SystemExit("work_intake_timestamp_required_contract_test failed: items missing")

    for item in items:
        if not isinstance(item, dict):
            raise SystemExit("work_intake_timestamp_required_contract_test failed: item not dict")
        updated_at = item.get("updated_at")
        ingested_at = item.get("ingested_at")
        if not (updated_at or ingested_at):
            raise SystemExit("work_intake_timestamp_required_contract_test failed: timestamp missing")
        if isinstance(updated_at, str) and updated_at:
            _parse_iso(updated_at)
        if isinstance(ingested_at, str) and ingested_at:
            _parse_iso(ingested_at)


if __name__ == "__main__":
    main()
