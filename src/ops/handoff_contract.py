from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_VALID_ROLES = frozenset([
    "architect", "planner", "implementer", "reviewer",
    "verifier", "consultant", "assurance_owner", "operator",
])


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schema_path() -> Path:
    return _repo_root() / "schemas" / "handoff-envelope.schema.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_handoff_envelope(
    *,
    from_role: str,
    from_actor: str,
    from_provider: str,
    from_model: str,
    from_session_id: str,
    to_role: str,
    work_item_id: str,
    handoff_reason: str,
    evidence_paths: list[str] | None = None,
    scope_glob: str | None = None,
    to_actor: str | None = None,
    to_provider: str | None = None,
    to_model: str | None = None,
) -> dict[str, Any]:
    handoff_id = f"HO-{uuid.uuid4().hex[:12]}"
    now_iso = _now_iso()
    normalized_evidence = sorted({str(p) for p in (evidence_paths or []) if str(p).strip()})
    if not normalized_evidence:
        normalized_evidence = [f".cache/reports/handoffs/{handoff_id}.json"]
    envelope: dict[str, Any] = {
        "version": "v1",
        "kind": "handoff-envelope",
        "generated_at": now_iso,
        "handoff_id": handoff_id,
        "from_role": str(from_role or "").strip(),
        "from_actor": str(from_actor or "").strip(),
        "from_provider": str(from_provider or "").strip(),
        "from_model": str(from_model or "").strip(),
        "from_session_id": str(from_session_id or "").strip(),
        "to_role": str(to_role or "").strip(),
        "work_item_id": str(work_item_id or "").strip(),
        "handoff_reason": str(handoff_reason or "").strip(),
        "evidence_paths": normalized_evidence,
        "created_at": now_iso,
    }
    if str(scope_glob or "").strip():
        envelope["scope_glob"] = str(scope_glob).strip()
    if str(to_actor or "").strip():
        envelope["to_actor"] = str(to_actor).strip()
    if str(to_provider or "").strip():
        envelope["to_provider"] = str(to_provider).strip()
    if str(to_model or "").strip():
        envelope["to_model"] = str(to_model).strip()
    return envelope


def validate_handoff(handoff: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_path = _schema_path()
    if not schema_path.exists():
        errors.append("SCHEMA_NOT_FOUND: handoff-envelope.schema.v1.json missing")
        return errors

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for e in sorted(validator.iter_errors(handoff), key=lambda x: x.json_path):
        errors.append(f"{e.json_path or '$'}: {e.message}")

    from_role = str(handoff.get("from_role") or "").strip()
    if from_role and from_role not in _VALID_ROLES:
        errors.append(f"from_role '{from_role}' not in valid roles")

    to_role = str(handoff.get("to_role") or "").strip()
    if to_role and to_role not in _VALID_ROLES:
        errors.append(f"to_role '{to_role}' not in valid roles")

    return errors
