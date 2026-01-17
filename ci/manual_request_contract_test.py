from __future__ import annotations

import json
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

    from src.ops.manual_request_cli import build_manual_request

    schema_path = repo_root / "schemas" / "manual-request.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    now_iso = "2026-01-05T00:00:00Z"
    req_id_1, req_obj_1, digest_1 = build_manual_request(
        text="Context router request sample.",
        artifact_type="context_pack",
        domain="ops",
        kind="support",
        tenant_id="TENANT-DEFAULT",
        source_type="human",
        now_iso=now_iso,
    )
    req_id_2, req_obj_2, digest_2 = build_manual_request(
        text="Context router request sample.",
        artifact_type="context_pack",
        domain="ops",
        kind="support",
        tenant_id="TENANT-DEFAULT",
        source_type="human",
        now_iso=now_iso,
    )

    if req_id_1 != req_id_2 or digest_1 != digest_2:
        raise SystemExit("Manual request test failed: request_id must be deterministic.")

    errors = sorted(validator.iter_errors(req_obj_1), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        raise SystemExit(f"Manual request test failed: schema invalid at {where}.")

    errors = sorted(validator.iter_errors(req_obj_2), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        raise SystemExit(f"Manual request test failed: schema invalid at {where}.")

    print(json.dumps({"status": "OK", "request_id": req_id_1}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
