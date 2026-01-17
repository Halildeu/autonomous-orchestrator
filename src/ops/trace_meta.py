from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), indent=None)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _date_bucket(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%d")


def date_bucket_from_iso(value: str) -> str:
    raw = str(value or "")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return _date_bucket(datetime.now(timezone.utc))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return _date_bucket(parsed)


def build_run_id(
    *,
    workspace_root: Path,
    op_name: str,
    inputs: dict[str, Any],
    date_bucket: str | None = None,
) -> str:
    payload = {
        "workspace_root": str(workspace_root.resolve()),
        "op_name": str(op_name or ""),
        "date_bucket": str(date_bucket or _date_bucket(datetime.now(timezone.utc))),
        "inputs_hash": _hash_text(_canonical_json(inputs)),
    }
    return _hash_text(_canonical_json(payload))


def build_inputs_hash(payload: dict[str, Any]) -> str:
    return _hash_text(_canonical_json(payload))


def build_run_fingerprint(
    *,
    work_item_id: str,
    plan_hash: str,
    inputs_hash: str,
    policy_hash: str | None,
    tool_versions_hash: str | None,
) -> str:
    payload = {
        "work_item_id": str(work_item_id or ""),
        "plan_hash": str(plan_hash or ""),
        "inputs_hash": str(inputs_hash or ""),
        "policy_hash": str(policy_hash or ""),
        "tool_versions_hash": str(tool_versions_hash or ""),
    }
    return _hash_text(_canonical_json(payload))


def build_trace_meta(
    *,
    work_item_id: str,
    work_item_kind: str,
    run_id: str,
    policy_hash: str | None,
    evidence_paths: Iterable[str] | None,
    planner_tag: str | None = None,
    doer_tag: str | None = None,
    chat_tag: str | None = None,
    owner_session: str | None = None,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    paths = sorted({str(p) for p in (evidence_paths or []) if str(p).strip()})
    env_tag = os.environ.get("CODEX_CHAT_TAG")
    default_tag = str(env_tag).strip() if isinstance(env_tag, str) and env_tag.strip() else "unknown"
    payload = {
        "version": "v1",
        "work_item_id": str(work_item_id or ""),
        "work_item_kind": str(work_item_kind or ""),
        "run_id": str(run_id or ""),
        "policy_hash": str(policy_hash) if isinstance(policy_hash, str) and policy_hash else None,
        "evidence_paths": paths,
        "planner_tag": str(planner_tag or default_tag),
        "doer_tag": str(doer_tag or default_tag),
        "chat_tag": str(chat_tag or default_tag),
        "owner_session": str(owner_session or default_tag),
    }
    if workspace_root:
        payload["workspace_root"] = str(workspace_root)
    return payload
