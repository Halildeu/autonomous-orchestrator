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


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.manual_request_cli import submit_manual_request
    from src.ops.work_intake_from_sources import run_work_intake_build

    ws = repo_root / ".cache" / "ws_manual_intake_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    submit = submit_manual_request(
        workspace_root=ws,
        text="Feature request for context router.",
        artifact_type="context_pack",
        domain="ops",
        kind="feature",
        tenant_id="TENANT-DEFAULT",
        source_type="human",
        dry_run=False,
    )
    request_id = submit.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise SystemExit("Manual ingest test failed: missing request_id.")

    build_res = run_work_intake_build(workspace_root=ws)
    intake_rel = build_res.get("work_intake_path") if isinstance(build_res, dict) else None
    if not isinstance(intake_rel, str) or not intake_rel:
        raise SystemExit("Manual ingest test failed: work_intake_path missing.")

    intake_path = (ws / intake_rel).resolve()
    if not intake_path.exists():
        raise SystemExit("Manual ingest test failed: work_intake.v1.json missing.")

    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    items = intake.get("items") if isinstance(intake, dict) else None
    if not isinstance(items, list):
        raise SystemExit("Manual ingest test failed: items missing.")

    manual_items = [i for i in items if isinstance(i, dict) and i.get("source_type") == "MANUAL_REQUEST"]
    if not manual_items:
        raise SystemExit("Manual ingest test failed: MANUAL_REQUEST item missing.")

    target = None
    for item in manual_items:
        if item.get("source_ref") == request_id:
            target = item
            break
    if not target:
        raise SystemExit("Manual ingest test failed: MANUAL_REQUEST item not found for request_id.")

    if target.get("bucket") != "PROJECT":
        raise SystemExit("Manual ingest test failed: expected PROJECT bucket for feature request.")

    print(json.dumps({"status": "OK", "bucket": target.get("bucket")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
