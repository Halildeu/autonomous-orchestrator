from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class SessionContextError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def _repo_root() -> Path:
    # src/session/context_store.py -> session -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _schema_path() -> Path:
    return _repo_root() / "schemas" / "session-context.schema.json"


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _validator() -> Draft202012Validator:
    schema_path = _schema_path()
    if not schema_path.exists():
        raise SessionContextError("SCHEMA_NOT_FOUND", "Missing schemas/session-context.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _context_for_hash(ctx: dict[str, Any]) -> dict[str, Any]:
    clone = deepcopy(ctx)
    hashes = clone.get("hashes")
    if not isinstance(hashes, dict):
        hashes = {}
    hashes = dict(hashes)
    hashes["session_context_sha256"] = ""
    clone["hashes"] = hashes
    return clone


def compute_context_sha256(ctx: dict[str, Any]) -> str:
    to_hash = _context_for_hash(ctx)
    return compute_sha256(_canonical_json_bytes(to_hash))


def load_context(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SessionContextError("JSON_INVALID", f"Invalid JSON: {path}") from e
    if not isinstance(obj, dict):
        raise SessionContextError("SCHEMA_INVALID", "Session context must be an object")

    validator = _validator()
    errors = sorted(validator.iter_errors(obj), key=lambda e: e.json_path)
    if errors:
        msg = errors[0].message
        where = errors[0].json_path or "$"
        raise SessionContextError("SCHEMA_INVALID", f"{where}: {msg}")

    hashes = obj.get("hashes")
    sha_in = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    if not isinstance(sha_in, str) or len(sha_in) != 64:
        raise SessionContextError("HASH_INVALID", "Missing hashes.session_context_sha256")

    sha_calc = compute_context_sha256(obj)
    if sha_calc != sha_in:
        raise SessionContextError("HASH_MISMATCH", "hashes.session_context_sha256 does not match computed hash")

    return obj


def save_context_atomic(path: Path, obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SessionContextError("SCHEMA_INVALID", "Session context must be an object")
    if "hashes" not in obj or not isinstance(obj.get("hashes"), dict):
        obj["hashes"] = {}

    sha = compute_context_sha256(obj)
    obj["hashes"]["session_context_sha256"] = sha

    validator = _validator()
    errors = sorted(validator.iter_errors(obj), key=lambda e: e.json_path)
    if errors:
        msg = errors[0].message
        where = errors[0].json_path or "$"
        raise SessionContextError("SCHEMA_INVALID", f"{where}: {msg}")

    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def new_context(session_id: str, workspace_root: str, ttl_seconds: int) -> dict[str, Any]:
    if not session_id or not isinstance(session_id, str):
        raise SessionContextError("INVALID_ARGS", "session_id must be non-empty")
    if not isinstance(ttl_seconds, int) or ttl_seconds < 60 or ttl_seconds > 604800:
        raise SessionContextError("INVALID_ARGS", "ttl_seconds must be in [60, 604800]")

    now = datetime.now(timezone.utc)
    created_at = now.isoformat().replace("+00:00", "Z")
    expires_at = (now + timedelta(seconds=int(ttl_seconds))).isoformat().replace("+00:00", "Z")

    ctx: dict[str, Any] = {
        "version": "v1",
        "session_id": session_id,
        "workspace_root": str(workspace_root),
        "created_at": created_at,
        "updated_at": created_at,
        "ttl_seconds": int(ttl_seconds),
        "expires_at": expires_at,
        "paused": False,
        "ephemeral_decisions": [],
        "hashes": {"session_context_sha256": ""},
    }
    ctx["hashes"]["session_context_sha256"] = compute_context_sha256(ctx)
    return ctx


def upsert_decision(context: dict[str, Any], key: str, value: Any, source: str) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")
    if not isinstance(key, str) or not key:
        raise SessionContextError("INVALID_ARGS", "key must be non-empty string")
    if source not in {"user_chat", "agent"}:
        raise SessionContextError("INVALID_ARGS", "source must be user_chat|agent")

    if isinstance(value, list) or value is None:
        raise SessionContextError("INVALID_ARGS", "value_json must be string|number|boolean|object")

    now = _now_iso8601()

    decisions = context.get("ephemeral_decisions")
    if not isinstance(decisions, list):
        decisions = []
    out: list[dict[str, Any]] = []
    replaced = False
    for d in decisions:
        if not isinstance(d, dict):
            continue
        if d.get("key") == key:
            out.append({"key": key, "value": value, "source": source, "created_at": now})
            replaced = True
        else:
            out.append(d)
    if not replaced:
        out.append({"key": key, "value": value, "source": source, "created_at": now})

    out.sort(key=lambda x: str(x.get("key") or ""))
    context["ephemeral_decisions"] = out
    context["updated_at"] = now
    return context


def is_expired(context: dict[str, Any], now_iso: str) -> bool:
    if not isinstance(context, dict):
        return True
    exp = context.get("expires_at")
    if not isinstance(exp, str) or not exp:
        return True
    now_dt = _parse_iso8601(str(now_iso) or "")
    exp_dt = _parse_iso8601(exp)
    if now_dt is None or exp_dt is None:
        return True
    return now_dt > exp_dt


def prune_expired_decisions(context: dict[str, Any], now_iso: str) -> dict[str, Any]:
    # v0.1: decisions don't have per-item TTL; keep API for future extension.
    _ = now_iso
    return context


@dataclass(frozen=True)
class SessionPaths:
    workspace_root: Path
    session_id: str

    @property
    def context_path(self) -> Path:
        return (self.workspace_root / ".cache" / "sessions" / self.session_id / "session_context.v1.json").resolve()

