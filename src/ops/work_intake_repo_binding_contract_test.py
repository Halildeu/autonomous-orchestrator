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
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_work_intake_repo_binding"
    if ws.exists():
        shutil.rmtree(ws)

    repo_id = "repo-binding-test"
    repo_root_target = str((repo_root / "src").resolve())

    _write_json(
        ws / ".cache" / "index" / "workspace_repo_binding.v1.json",
        {
            "version": "v1",
            "kind": "workspace-repo-binding",
            "generated_at": _now_iso(),
            "workspace_root": str(ws.resolve()),
            "repo_root": repo_root_target,
            "repo_slug": "binding-test",
            "repo_id": repo_id,
            "source": "work_intake_repo_binding_contract_test",
        },
    )

    request_id = "REQ-BINDING-TEST"
    _write_json(
        ws / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json",
        {
            "version": "v1",
            "request_id": request_id,
            "created_at": _now_iso(),
            "source": {"type": "human"},
            "artifact_type": "request",
            "domain": "general",
            "kind": "note",
            "impact_scope": "doc-only",
            "text": "Repo binding stamp test.",
        },
    )

    res = run_work_intake_build(workspace_root=ws)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("work_intake_repo_binding_contract_test failed: build status")

    intake_path = ws / ".cache" / "index" / "work_intake.v1.json"
    if not intake_path.exists():
        raise SystemExit("work_intake_repo_binding_contract_test failed: intake output missing")
    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    manual_items = [
        i
        for i in items
        if isinstance(i, dict) and str(i.get("source_type") or "") == "MANUAL_REQUEST" and str(i.get("source_ref") or "") == request_id
    ]
    if not manual_items:
        raise SystemExit("work_intake_repo_binding_contract_test failed: manual request item missing")
    item = manual_items[0]
    if str(item.get("repo_id") or "") != repo_id:
        raise SystemExit("work_intake_repo_binding_contract_test failed: repo_id not stamped")
    if str(item.get("source_repo_root") or "") != repo_root_target:
        raise SystemExit("work_intake_repo_binding_contract_test failed: source_repo_root not stamped")

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    top_next = summary.get("top_next_actions") if isinstance(summary.get("top_next_actions"), list) else []
    top_item = next((x for x in top_next if isinstance(x, dict) and str(x.get("source_ref") or "") == request_id), None)
    if not isinstance(top_item, dict):
        raise SystemExit("work_intake_repo_binding_contract_test failed: top_next_actions missing manual item")
    if str(top_item.get("repo_id") or "") != repo_id:
        raise SystemExit("work_intake_repo_binding_contract_test failed: summary repo_id not stamped")
    if str(top_item.get("source_repo_root") or "") != repo_root_target:
        raise SystemExit("work_intake_repo_binding_contract_test failed: summary source_repo_root not stamped")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
