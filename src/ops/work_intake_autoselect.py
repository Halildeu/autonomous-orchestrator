from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root
from src.ops.doer_loop_lock import owner_tag_from_env
from src.ops.work_intake_from_sources import _load_autopilot_policy, run_work_intake_build
from src.ops.work_item_claims import get_active_claim


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _policy_hash(policy: dict[str, Any]) -> str:
    payload = json.dumps(policy, ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(priority, 99)


def _severity_rank(severity: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}.get(severity, 99)


def _load_manual_request(workspace_root: Path, request_id: str, evidence_paths: list[str]) -> dict[str, Any] | None:
    candidates: list[Path] = []
    if request_id:
        candidates.append(workspace_root / ".cache" / "index" / "manual_requests" / f"{request_id}.v1.json")
    for rel in evidence_paths:
        rel_path = Path(rel)
        candidates.append((workspace_root / rel_path).resolve() if not rel_path.is_absolute() else rel_path.resolve())
    for path in candidates:
        if not path.exists():
            continue
        try:
            obj = _load_json(path)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _manual_request_safe_first(
    *, workspace_root: Path, item: dict[str, Any]
) -> bool:
    if str(item.get("source_type") or "") != "MANUAL_REQUEST":
        return False
    source_ref = str(item.get("source_ref") or "")
    manual_req = _load_manual_request(workspace_root, source_ref, list(item.get("evidence_paths") or []))
    if not isinstance(manual_req, dict):
        return False
    if str(manual_req.get("impact_scope") or "") != "doc-only":
        return False
    kind = str(manual_req.get("kind") or "")
    if kind not in {"note", "doc-fix"}:
        return False
    requires_core = bool(manual_req.get("requires_core_change", False))
    constraints = manual_req.get("constraints") if isinstance(manual_req.get("constraints"), dict) else {}
    if requires_core or bool(constraints.get("requires_core_change", False)):
        return False
    return True


def _safe_first_candidates(*, workspace_root: Path, items: list[dict[str, Any]], limit: int) -> list[str]:
    group1: list[dict[str, Any]] = []
    group2: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("bucket") or "") != "TICKET":
            continue
        if str(item.get("status") or "").upper() not in {"OPEN", "PLANNED"}:
            continue
        if not bool(item.get("autopilot_allowed", False)):
            continue
        source_type = str(item.get("source_type") or "")
        if source_type == "MANUAL_REQUEST":
            if _manual_request_safe_first(workspace_root=workspace_root, item=item):
                group1.append(item)
            continue
        if source_type == "DOC_NAV":
            group2.append(item)
            continue
        if source_type == "SCRIPT_BUDGET":
            source_ref = str(item.get("source_ref") or "")
            if source_ref.startswith("ci/"):
                group2.append(item)
    group1.sort(
        key=lambda x: (
            _priority_rank(str(x.get("priority") or "")),
            _severity_rank(str(x.get("severity") or "")),
            str(x.get("intake_id") or ""),
        )
    )
    group2.sort(
        key=lambda x: (
            _priority_rank(str(x.get("priority") or "")),
            _severity_rank(str(x.get("severity") or "")),
            str(x.get("intake_id") or ""),
        )
    )
    selected = group1[: max(0, int(limit))] + group2[: max(0, int(limit))]
    return [str(x.get("intake_id") or "") for x in selected if str(x.get("intake_id") or "")]


def run_work_intake_autoselect(*, workspace_root: Path, limit: int, mode: str = "policy") -> dict[str, Any]:
    core_root = repo_root()
    build_res = run_work_intake_build(workspace_root=workspace_root)
    work_intake_path = build_res.get("work_intake_path") if isinstance(build_res, dict) else None
    if not isinstance(work_intake_path, str) or not work_intake_path:
        return {
            "status": "IDLE",
            "error_code": "WORK_INTAKE_MISSING",
            "work_intake_path": None,
            "selection_path": str(Path(".cache") / "index" / "work_intake_selection.v1.json"),
            "selected_ids": [],
            "selected_count": 0,
            "evidence_paths": [],
        }

    intake_path = (workspace_root / work_intake_path).resolve()
    try:
        intake_obj = _load_json(intake_path)
    except Exception:
        intake_obj = {}
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []

    autopilot_policy, policy_source, notes = _load_autopilot_policy(
        core_root=core_root, workspace_root=workspace_root
    )
    mode = str(mode or "policy").strip().lower()
    if mode not in {"policy", "safe_first"}:
        return {"status": "WARN", "error_code": "INVALID_MODE"}

    selected_ids: list[str] = []
    rank_rule = "priority asc -> severity asc -> intake_id asc"
    enabled = True
    if mode == "safe_first":
        selected_ids = _safe_first_candidates(workspace_root=workspace_root, items=items, limit=limit)
        notes.append("autoselect_safe_first")
    else:
        auto_select = autopilot_policy.get("auto_select") if isinstance(autopilot_policy.get("auto_select"), dict) else {}
        enabled = bool(auto_select.get("enabled", False))
        max_select = auto_select.get("max_select")
        max_select = int(max_select) if isinstance(max_select, int) else 0
        if limit < 0:
            limit = 0
        if max_select > 0:
            limit = min(limit, max_select)

        allow_buckets = auto_select.get("allow_buckets") if isinstance(auto_select.get("allow_buckets"), list) else []
        allow_source_types = (
            auto_select.get("allow_source_types") if isinstance(auto_select.get("allow_source_types"), list) else []
        )
        require_impact_scope = str(auto_select.get("require_impact_scope") or "").strip()
        deny_requires_core_change = bool(auto_select.get("deny_if_requires_core_change", False))
        rank_rule = str(auto_select.get("rank_rule") or "priority asc -> severity asc -> intake_id asc")

        allow_buckets_set = {str(x) for x in allow_buckets if isinstance(x, str)} if allow_buckets else set()
        allow_source_types_set = {str(x) for x in allow_source_types if isinstance(x, str)} if allow_source_types else set()

        candidates: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if allow_buckets_set and str(item.get("bucket") or "") not in allow_buckets_set:
                continue
            if allow_source_types_set and str(item.get("source_type") or "") not in allow_source_types_set:
                continue
            if not bool(item.get("autopilot_allowed", False)):
                continue
            if str(item.get("status") or "").upper() not in {"OPEN", "PLANNED"}:
                continue

            source_type = str(item.get("source_type") or "")
            if source_type == "MANUAL_REQUEST" and require_impact_scope:
                manual_req = _load_manual_request(
                    workspace_root, str(item.get("source_ref") or ""), list(item.get("evidence_paths") or [])
                )
                if not isinstance(manual_req, dict):
                    continue
                if str(manual_req.get("impact_scope") or "") != require_impact_scope:
                    continue
                if deny_requires_core_change and bool(manual_req.get("requires_core_change", False)):
                    continue

            candidates.append(item)

        candidates.sort(
            key=lambda x: (
                _priority_rank(str(x.get("priority") or "")),
                _severity_rank(str(x.get("severity") or "")),
                str(x.get("intake_id") or ""),
            )
        )
        if rank_rule.lower().strip() != "priority asc -> severity asc -> intake_id asc":
            notes.append("autoselect_rank_rule_fallback")

        selected = candidates[:limit] if limit > 0 else []
        selected_ids = [str(x.get("intake_id") or "") for x in selected if str(x.get("intake_id") or "")]

    claim_guard_owner = owner_tag_from_env()
    claim_guard_skipped: list[str] = []
    claim_guard_selected: list[str] = []
    for intake_id in selected_ids:
        claim = get_active_claim(workspace_root, intake_id)
        if isinstance(claim, dict):
            owner = str(claim.get("owner_tag") or "").strip()
            if not owner or owner != claim_guard_owner:
                claim_guard_skipped.append(intake_id)
                continue
        claim_guard_selected.append(intake_id)
    if claim_guard_skipped:
        notes.append(f"claim_guard_skipped={len(claim_guard_skipped)}")
    selected_ids = claim_guard_selected

    selection_path = workspace_root / ".cache" / "index" / "work_intake_selection.v1.json"
    selection_notes = ["PROGRAM_LED=true", "AUTOSELECT=true"]
    if mode == "safe_first":
        selection_notes.append("AUTOSELECT_SAFE_FIRST=true")
    selection_notes.append("CLAIM_GUARD=true")
    selection_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "selected_ids": selected_ids,
        "content_hash": hashlib.sha256(
            json.dumps(selected_ids, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "notes": selection_notes,
    }
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(
        json.dumps(selection_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    status = "OK"
    error_code = None
    if mode == "policy" and not enabled:
        status = "IDLE"
        error_code = "AUTO_SELECT_DISABLED"
    elif limit <= 0:
        status = "IDLE"
        error_code = "AUTO_SELECT_LIMIT_ZERO"
    elif not selected_ids:
        status = "IDLE"
        error_code = "NO_ELIGIBLE_ITEMS"

    return {
        "status": status,
        "error_code": error_code,
        "policy_source": policy_source,
        "policy_hash": _policy_hash(autopilot_policy),
        "work_intake_path": work_intake_path,
        "selection_path": str(Path(".cache") / "index" / "work_intake_selection.v1.json"),
        "selected_ids": selected_ids,
        "selected_count": len(selected_ids),
        "rank_rule": rank_rule,
        "mode": mode,
        "evidence_paths": [work_intake_path, str(Path(".cache") / "index" / "work_intake_selection.v1.json")],
        "notes": notes,
    }
