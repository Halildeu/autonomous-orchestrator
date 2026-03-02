from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_SEED_TS = "2026-01-01T00:00:00Z"
_SEED_REQ_ID = "REQ-CONTEXT-ROUTER-STRICT-SEED"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def seed_context_router_check_strict_preconditions(workspace_root: Path) -> None:
    manual_request_rel = Path(".cache") / "index" / "manual_requests" / f"{_SEED_REQ_ID}.v1.json"
    _write_json(
        workspace_root / manual_request_rel,
        {
            "version": "v1",
            "request_id": _SEED_REQ_ID,
            "received_at": _SEED_TS,
            "created_at": _SEED_TS,
            "source": {"type": "contract_test"},
            "text": "Strict dispatch precondition seed.",
            "artifact_type": "request",
            "domain": "ops",
            "kind": "minor_fix",
            "impact_scope": "workspace-only",
            "requires_core_change": False,
            "constraints": {"requires_core_change": False},
        },
    )

    doc_nav_strict_rel = Path(".cache") / "reports" / "doc_graph_report.strict.v1.json"
    _write_json(
        workspace_root / doc_nav_strict_rel,
        {
            "version": "v1",
            "generated_at": _SEED_TS,
            "workspace_root": str(workspace_root),
            "status": "OK",
            "mode": "strict",
            "counts": {
                "broken_refs": 0,
                "critical_nav_gaps": 0,
                "orphan_critical": 0,
                "ambiguity": 0,
                "placeholder_refs_count": 0,
                "workspace_bound_refs_count": 0,
                "external_pointer_refs_count": 0,
            },
            "doc_graph": {"critical_nav_gaps": 0},
            "top_broken": [],
            "top_orphans": [],
            "top_ambiguity": [],
            "top_placeholders": [],
        },
    )

    strict_plan_rel = Path(".cache") / "reports" / "chg" / "CHG-INTAKE-STRICT-SEED.plan.json"
    _write_json(
        workspace_root / strict_plan_rel,
        {
            "version": "v1",
            "generated_at": _SEED_TS,
            "plan_id": "CHG-INTAKE-STRICT-SEED",
            "status": "READY",
            "seed": True,
            "steps": [],
        },
    )
