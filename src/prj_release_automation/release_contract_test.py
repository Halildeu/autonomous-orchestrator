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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_generated_at(obj: dict) -> dict:
    trimmed = dict(obj)
    trimmed.pop("generated_at", None)
    return trimmed


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_release_automation.release_engine import (
        _compute_approvals_required,
        _load_policy,
        build_release_plan,
        prepare_release,
        publish_release,
        run_release_check,
    )

    ws = repo_root / ".cache" / "ws_release_automation_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    plan = build_release_plan(workspace_root=ws, channel="rc", detail=True)
    if plan.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("release_contract_test failed: plan status invalid.")

    plan_path = ws / ".cache" / "reports" / "release_plan.v1.json"
    if not plan_path.exists():
        raise SystemExit("release_contract_test failed: plan path missing.")

    plan_schema_path = repo_root / "schemas" / "release-plan.schema.v1.json"
    Draft202012Validator(_load_json(plan_schema_path)).validate(_load_json(plan_path))

    plan_obj_1 = _strip_generated_at(_load_json(plan_path))
    plan2 = build_release_plan(workspace_root=ws, channel="rc", detail=True)
    plan_obj_2 = _strip_generated_at(_load_json(plan_path))
    if plan_obj_1.get("version_plan") != plan_obj_2.get("version_plan"):
        raise SystemExit("release_contract_test failed: plan version_plan not deterministic.")

    ws_empty = repo_root / ".cache" / "ws_release_automation_empty"
    if ws_empty.exists():
        shutil.rmtree(ws_empty)
    ws_empty.mkdir(parents=True, exist_ok=True)

    prepare_idle = prepare_release(workspace_root=ws_empty, channel="rc")
    if prepare_idle.get("status") != "IDLE":
        raise SystemExit("release_contract_test failed: prepare should be IDLE when plan missing.")

    manifest = prepare_release(workspace_root=ws, channel="rc")
    if manifest.get("status") not in {"OK", "WARN"}:
        raise SystemExit("release_contract_test failed: prepare manifest status invalid.")

    manifest_path = ws / ".cache" / "reports" / "release_manifest.v1.json"
    notes_path = ws / ".cache" / "reports" / "release_notes.v1.md"
    if not manifest_path.exists() or not notes_path.exists():
        raise SystemExit("release_contract_test failed: manifest or notes missing.")

    manifest_schema_path = repo_root / "schemas" / "release-manifest.schema.v1.json"
    Draft202012Validator(_load_json(manifest_schema_path)).validate(_load_json(manifest_path))

    check = run_release_check(workspace_root=ws, channel="rc", chat=False)
    if check.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("release_contract_test failed: release-check status invalid.")
    check_manifest = check.get("release_manifest_path")
    check_notes = check.get("release_notes_path")
    if not (isinstance(check_manifest, str) and isinstance(check_notes, str)):
        raise SystemExit("release_contract_test failed: release-check missing evidence paths.")

    publish = publish_release(workspace_root=ws, channel="rc", allow_network=False, trusted_context=False)
    if publish.get("status") not in {"IDLE", "SKIP"}:
        raise SystemExit("release_contract_test failed: publish should be IDLE or SKIP by default.")

    policy = _load_policy(ws)
    approvals = _compute_approvals_required(policy, ["core", "catalog"])
    if not {"core", "catalog"}.issubset(set(approvals)):
        raise SystemExit("release_contract_test failed: approvals must include core + catalog when changed.")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
