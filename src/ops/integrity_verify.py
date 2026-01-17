from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.benchmark.integrity_utils import build_integrity_snapshot, load_policy_integrity, load_previous_snapshot


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _write_md(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Integrity Verify Report",
        "",
        f"Generated at: {snapshot.get('generated_at', '')}",
        f"Workspace: {snapshot.get('workspace_root', '')}",
        f"Verify result: {snapshot.get('verify_on_read_result', '')}",
        f"Mismatch count: {snapshot.get('mismatch_count', 0)}",
        "",
        "Mismatches:",
    ]
    mismatches = snapshot.get("mismatches") if isinstance(snapshot, dict) else None
    if isinstance(mismatches, list) and mismatches:
        for item in mismatches:
            if isinstance(item, str) and item.strip():
                lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_integrity_verify(*, workspace_root: Path, mode: str) -> dict[str, Any]:
    core_root = _repo_root()
    policy = load_policy_integrity(core_root=core_root, workspace_root=workspace_root)
    if not isinstance(policy, dict) or not policy.get("enabled", True):
        return {"status": "SKIPPED", "reason": "policy_disabled"}

    previous_snapshot = load_previous_snapshot(workspace_root=workspace_root) if mode == "strict" else None
    snapshot = build_integrity_snapshot(
        workspace_root=workspace_root,
        core_root=core_root,
        policy=policy,
        previous_snapshot=previous_snapshot,
    )

    out_json = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "integrity_verify.v1.md"
    _ensure_inside_workspace(workspace_root, out_json)
    _ensure_inside_workspace(workspace_root, out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    schema_path = core_root / "schemas" / "integrity-snapshot.schema.v1.json"
    if schema_path.exists():
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(snapshot)

    out_json.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _write_md(out_md, snapshot)

    return {
        "status": "OK",
        "verify_on_read_result": snapshot.get("verify_on_read_result"),
        "out_json": str(out_json),
        "out_md": str(out_md),
        "mismatch_count": int(snapshot.get("mismatch_count") or 0),
    }
