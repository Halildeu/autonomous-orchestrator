from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime | None:
    raw = str(value or "")
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _claims_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "work_item_claims.v1.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _claim_is_stale(claim: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(str(claim.get("expires_at") or ""))
    if expires_at is None:
        return True
    return now >= expires_at


def _normalize_claims(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        claims = raw.get("claims")
    else:
        claims = raw
    if not isinstance(claims, list):
        return []
    return [item for item in claims if isinstance(item, dict)]


def load_claims(workspace_root: Path) -> list[dict[str, Any]]:
    path = _claims_path(workspace_root)
    if not path.exists():
        return []
    try:
        raw = _load_json(path)
    except Exception:
        return []
    return _normalize_claims(raw)


def save_claims(workspace_root: Path, claims: list[dict[str, Any]]) -> None:
    claims_sorted = sorted(claims, key=lambda c: (str(c.get("work_item_id") or ""), str(c.get("claim_id") or "")))
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "claims": claims_sorted,
    }
    _write_json(_claims_path(workspace_root), payload)


def list_claims_by_agent(workspace_root: Path, agent_tag: str) -> list[dict[str, Any]]:
    """Return active claims owned by a specific agent."""
    now = datetime.now(timezone.utc)
    tag = str(agent_tag or "").strip()
    return [
        claim
        for claim in load_claims(workspace_root)
        if isinstance(claim, dict)
        and not _claim_is_stale(claim, now)
        and str(claim.get("agent_tag") or "") == tag
    ]


def acquire_claim(
    *,
    workspace_root: Path,
    work_item_id: str,
    owner_tag: str,
    owner_session: str | None = None,
    run_id: str | None = None,
    ttl_seconds: int,
    agent_tag: str = "",
) -> dict[str, Any]:
    ttl = max(1, int(ttl_seconds))
    now = datetime.now(timezone.utc)
    claims = load_claims(workspace_root)
    stale_cleared: dict[str, Any] | None = None

    for idx, claim in enumerate(list(claims)):
        if str(claim.get("work_item_id") or "") != work_item_id:
            continue
        if _claim_is_stale(claim, now):
            stale_cleared = dict(claim)
            claims.pop(idx)
            break
        if str(claim.get("owner_tag") or "") == str(owner_tag or ""):
            claim = dict(claim)
            claim["ttl_seconds"] = ttl
            claim["expires_at"] = (now + timedelta(seconds=ttl)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            claim["heartbeat_at"] = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            claims[idx] = claim
            save_claims(workspace_root, claims)
            return {"status": "RENEWED", "claim": claim, "stale_cleared": None}
        return {"status": "LOCKED", "claim": claim, "stale_cleared": None}

    claim_id = sha256(f"{work_item_id}:{owner_tag}".encode("utf-8")).hexdigest()
    claim_run_id = str(run_id or claim_id)
    session = str(owner_session or owner_tag)
    claim = {
        "work_item_id": work_item_id,
        "claim_id": claim_id,
        "owner_tag": str(owner_tag or ""),
        "owner_session": session,
        "agent_tag": str(agent_tag or ""),
        "run_id": claim_run_id,
        "acquired_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": ttl,
        "expires_at": (now + timedelta(seconds=ttl)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "heartbeat_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    claims.append(claim)
    save_claims(workspace_root, claims)
    return {"status": "ACQUIRED", "claim": claim, "stale_cleared": stale_cleared}


def release_claim(
    *,
    workspace_root: Path,
    work_item_id: str,
    owner_tag: str | None = None,
    agent_tag: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    claims = load_claims(workspace_root)
    for idx, claim in enumerate(list(claims)):
        if str(claim.get("work_item_id") or "") != str(work_item_id or ""):
            continue
        if force:
            claims.pop(idx)
            save_claims(workspace_root, claims)
            return {"status": "RELEASED_FORCED", "claim": claim}
        if agent_tag and str(claim.get("agent_tag") or "") != str(agent_tag or ""):
            return {"status": "AGENT_MISMATCH", "claim": claim}
        if owner_tag and str(claim.get("owner_tag") or "") != str(owner_tag or ""):
            return {"status": "MISMATCH", "claim": claim}
        claims.pop(idx)
        save_claims(workspace_root, claims)
        return {"status": "RELEASED", "claim": claim}
    return {"status": "NOOP", "claim": None}


def count_active_claims(workspace_root: Path) -> int:
    now = datetime.now(timezone.utc)
    claims = load_claims(workspace_root)
    return sum(1 for claim in claims if isinstance(claim, dict) and not _claim_is_stale(claim, now))


def get_active_claim(workspace_root: Path, work_item_id: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    for claim in load_claims(workspace_root):
        if str(claim.get("work_item_id") or "") != str(work_item_id or ""):
            continue
        if _claim_is_stale(claim, now):
            continue
        return claim
    return None
