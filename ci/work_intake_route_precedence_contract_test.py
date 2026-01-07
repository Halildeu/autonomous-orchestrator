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

    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_intake_route_precedence_test"
    if ws.exists():
        shutil.rmtree(ws)

    manual_dir = ws / ".cache" / "index" / "manual_requests"
    manual_dir.mkdir(parents=True, exist_ok=True)

    requests = [
        {
            "version": "v1",
            "request_id": "REQ-CTX-PROJECT",
            "created_at": _now_iso(),
            "source": {"type": "human"},
            "artifact_type": "request",
            "domain": "ops",
            "kind": "context-router",
            "impact_scope": "workspace-only",
            "requires_core_change": False,
            "text": "Context router request (project).",
        },
        {
            "version": "v1",
            "request_id": "REQ-CTX-ROADMAP",
            "created_at": _now_iso(),
            "source": {"type": "human"},
            "artifact_type": "request",
            "domain": "ops",
            "kind": "context-router",
            "impact_scope": "core-change",
            "requires_core_change": True,
            "text": "Context router request (roadmap).",
        },
        {
            "version": "v1",
            "request_id": "REQ-DOC-LINK-FIX",
            "created_at": _now_iso(),
            "source": {"type": "human"},
            "artifact_type": "request",
            "domain": "docs",
            "kind": "doc-link-fix",
            "impact_scope": "doc-only",
            "requires_core_change": False,
            "text": "Doc link fix request.",
        },
    ]

    for req in requests:
        _write_json(manual_dir / f"{req['request_id']}.v1.json", req)

    build_result = run_work_intake_build(workspace_root=ws)
    status = build_result.get("status") if isinstance(build_result, dict) else None
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Route precedence test failed: intake build status invalid.")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("Route precedence test failed: work_intake.v1.json missing.")

    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    bucket_by_ref = {
        str(item.get("source_ref")): str(item.get("bucket"))
        for item in items
        if isinstance(item, dict) and item.get("source_type") == "MANUAL_REQUEST"
    }

    expected = {
        "REQ-CTX-PROJECT": "PROJECT",
        "REQ-CTX-ROADMAP": "ROADMAP",
        "REQ-DOC-LINK-FIX": "TICKET",
    }
    for ref, bucket in expected.items():
        got = bucket_by_ref.get(ref)
        if got != bucket:
            raise SystemExit(f"Route precedence test failed: {ref} expected {bucket}, got {got}.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
