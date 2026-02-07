from __future__ import annotations

import json
import shutil
import sys
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

    from src.ops.manual_request_cli import submit_manual_request
    from src.ops.context_pack_router import build_context_pack

    ws = repo_root / ".cache" / "ws_context_pack_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    submit = submit_manual_request(
        workspace_root=ws,
        text="Context pack contract test.",
        artifact_type="context_pack",
        domain="ops",
        kind="support",
        tenant_id="TENANT-DEFAULT",
        source_type="human",
        dry_run=False,
    )
    request_id = submit.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise SystemExit("Context pack test failed: missing request_id.")

    build_res = build_context_pack(workspace_root=ws, request_id=request_id, mode="detail")
    pack_rel = build_res.get("context_pack_path") if isinstance(build_res, dict) else None
    if not isinstance(pack_rel, str) or not pack_rel:
        raise SystemExit("Context pack test failed: context_pack_path missing.")
    pack_path = (ws / pack_rel).resolve()
    if not pack_path.exists():
        raise SystemExit("Context pack test failed: context pack file missing.")

    schema_path = repo_root / "schemas" / "context-pack.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    pack_obj = json.loads(pack_path.read_text(encoding="utf-8"))
    errors = sorted(validator.iter_errors(pack_obj), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        raise SystemExit(f"Context pack test failed: schema invalid at {where}.")

    request_meta = pack_obj.get("request_meta") if isinstance(pack_obj, dict) else {}
    if "text" in request_meta:
        raise SystemExit("Context pack test failed: request_meta must not include raw text.")

    build_res_2 = build_context_pack(workspace_root=ws, request_id=request_id, mode="detail")
    if build_res.get("context_pack_id") != build_res_2.get("context_pack_id"):
        raise SystemExit("Context pack test failed: context_pack_id must be deterministic.")

    print(json.dumps({"status": "OK", "context_pack_id": build_res.get("context_pack_id")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
