from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_release_summary(workspace_root: Path) -> dict[str, Any]:
    plan_rel = str(Path(".cache") / "reports" / "release_plan.v1.json")
    manifest_rel = str(Path(".cache") / "reports" / "release_manifest.v1.json")
    plan_path = workspace_root / plan_rel
    manifest_path = workspace_root / manifest_rel

    summary = {
        "status": "IDLE",
        "channel": "",
        "release_version": "",
        "plan_path": plan_rel,
        "manifest_path": manifest_rel,
        "dirty_tree": False,
        "notes": [],
    }

    if plan_path.exists():
        try:
            plan = _load_json(plan_path)
        except Exception:
            plan = {}
            summary["notes"].append("plan_invalid_json")
        if isinstance(plan, dict):
            status = plan.get("status")
            if status in {"OK", "WARN", "IDLE", "FAIL"}:
                summary["status"] = str(status)
            summary["channel"] = str(plan.get("channel") or "")
            summary["dirty_tree"] = bool(plan.get("dirty_tree", False))
            version_plan = plan.get("version_plan") if isinstance(plan.get("version_plan"), dict) else {}
            summary["release_version"] = str(version_plan.get("channel_version") or "")

    if manifest_path.exists():
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            manifest = {}
            summary["notes"].append("manifest_invalid_json")
        if isinstance(manifest, dict):
            status = manifest.get("status")
            if status in {"OK", "WARN", "IDLE", "FAIL"}:
                summary["status"] = str(status)
            summary["channel"] = str(manifest.get("channel") or summary.get("channel") or "")
            summary["release_version"] = str(manifest.get("release_version") or summary.get("release_version") or "")

    return summary
