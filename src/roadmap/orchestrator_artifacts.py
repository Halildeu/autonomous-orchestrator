from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_hex(s: str) -> str:
    return sha256(s.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _ArtifactCheck:
    check_id: str
    path: str
    owner_milestone: str
    severity: str
    auto_heal: bool


def _load_artifact_completeness_policy(*, core_root: Path, workspace_root: Path) -> tuple[bool, list[_ArtifactCheck]]:
    defaults = [
        _ArtifactCheck("formats_index", ".cache/index/formats.v1.json", "M2.5", "warn", True),
        _ArtifactCheck("catalog_index", ".cache/index/catalog.v1.json", "M3", "warn", True),
        _ArtifactCheck("session_context", ".cache/sessions/default/session_context.v1.json", "M3.5", "warn", True),
        _ArtifactCheck("ops_run_index", ".cache/index/run_index.v1.json", "M6.6", "warn", True),
        _ArtifactCheck("ops_dlq_index", ".cache/index/dlq_index.v1.json", "M6.6", "warn", True),
        _ArtifactCheck("harvest_cursor", ".cache/learning/harvest_cursor.v1.json", "M6.7", "warn", True),
        _ArtifactCheck("advisor_suggestions", ".cache/learning/advisor_suggestions.v1.json", "M7", "warn", False),
        _ArtifactCheck("readiness_report", ".cache/ops/autopilot_readiness.v1.json", "M8", "warn", False),
        _ArtifactCheck("system_status", ".cache/reports/system_status.v1.json", "M8.1", "warn", False),
    ]

    ws_policy = workspace_root / "policies" / "policy_artifact_completeness.v1.json"
    core_policy = core_root / "policies" / "policy_artifact_completeness.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return (True, defaults)

    try:
        obj = _load_json(policy_path)
    except Exception:
        return (True, defaults)
    if not isinstance(obj, dict):
        return (True, defaults)

    enabled = bool(obj.get("enabled", True))
    raw_checks = obj.get("checks")
    if not isinstance(raw_checks, list):
        return (enabled, defaults)

    out: list[_ArtifactCheck] = []
    for item in raw_checks:
        if not isinstance(item, dict):
            continue
        check_id = item.get("id")
        path = item.get("path")
        owner = item.get("owner_milestone")
        if not (isinstance(check_id, str) and isinstance(path, str) and isinstance(owner, str)):
            continue
        severity = item.get("severity", "warn")
        if severity not in {"warn", "block"}:
            severity = "warn"
        auto_heal = bool(item.get("auto_heal", False))
        out.append(_ArtifactCheck(check_id.strip(), path.strip(), owner.strip(), str(severity), auto_heal))

    if not out:
        out = defaults
    out.sort(key=lambda c: c.check_id)
    return (enabled, out)


def _promotion_outputs_exist(workspace_root: Path) -> bool:
    required = [
        ".cache/promotion/promotion_bundle.v1.zip",
        ".cache/promotion/promotion_report.v1.json",
        ".cache/promotion/core_patch_summary.v1.md",
    ]
    return all((workspace_root / p).exists() for p in required)


def _incubator_has_files(workspace_root: Path) -> bool:
    incubator_root = workspace_root / "incubator"
    if not incubator_root.exists():
        return False
    for root, _, files in os.walk(incubator_root):
        if files:
            return True
    return False


def _ensure_promotion_seed_note(workspace_root: Path) -> tuple[bool, str | None]:
    note_path = workspace_root / "incubator" / "notes" / "PROMOTION_SEED.md"
    content = "Promotion seed note (auto-generated).\n"
    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        if existing == content:
            return (False, str(note_path))
        raise ValueError("CONTENT_MISMATCH")
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return (True, str(note_path))


def _artifact_missing(*, checks: list[_ArtifactCheck], workspace_root: Path) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for chk in checks:
        rel = Path(chk.path)
        target = (workspace_root / rel).resolve()
        if not target.exists():
            missing.append(
                {
                    "id": chk.check_id,
                    "path": chk.path,
                    "owner_milestone": chk.owner_milestone,
                    "severity": chk.severity,
                    "auto_heal": chk.auto_heal,
                }
            )
    missing.sort(key=lambda x: str(x.get("id") or ""))
    return missing


def _artifact_missing_action(item: dict[str, Any]) -> dict[str, Any]:
    check_id = str(item.get("id") or "")
    path = str(item.get("path") or "")
    owner = str(item.get("owner_milestone") or "")
    severity = "WARN" if item.get("severity") != "block" else "FAIL"
    msg = f"Missing derived artifact: {check_id} path={path} owner={owner}"
    return {
        "action_id": _sha256_hex(f"DERIVED_ARTIFACT_MISSING|{check_id}|{path}|{owner}")[:16],
        "severity": severity,
        "kind": "DERIVED_ARTIFACT_MISSING",
        "milestone_hint": owner,
        "source": "ARTIFACT_COMPLETENESS",
        "title": "Derived artifact missing",
        "details": {
            "id": check_id,
            "path": path,
            "owner_milestone": owner,
            "severity": item.get("severity"),
            "auto_heal": bool(item.get("auto_heal")),
        },
        "message": msg[:300],
        "resolved": False,
    }


def _artifact_heal_failed_action(item: dict[str, Any]) -> dict[str, Any]:
    check_id = str(item.get("id") or "")
    path = str(item.get("path") or "")
    owner = str(item.get("owner_milestone") or "")
    msg = f"Auto-heal failed for derived artifact: {check_id} path={path} owner={owner}"
    return {
        "action_id": _sha256_hex(f"DERIVED_ARTIFACT_HEAL_FAILED|{check_id}|{path}|{owner}")[:16],
        "severity": "WARN",
        "kind": "DERIVED_ARTIFACT_HEAL_FAILED",
        "milestone_hint": owner,
        "source": "ARTIFACT_COMPLETENESS",
        "title": "Derived artifact auto-heal failed",
        "details": {
            "id": check_id,
            "path": path,
            "owner_milestone": owner,
        },
        "message": msg[:300],
        "resolved": False,
    }
