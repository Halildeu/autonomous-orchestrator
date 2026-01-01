from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from src.secrets.env_provider import EnvSecretsProvider
from src.secrets.vault_stub_provider import VaultStubSecretsProvider
from src.tools.errors import PolicyViolation

# Ephemeral in-memory store for secret values.
# Values MUST never be written to disk or stdout.
_EPHEMERAL_VALUES: dict[str, str] = {}


def consume(handle: str) -> str | None:
    if not isinstance(handle, str) or not handle:
        return None
    return _EPHEMERAL_VALUES.pop(handle, None)


def _default_policy() -> dict[str, Any]:
    return {
        "provider": "env",
        "allowed_secret_ids": ["OPENAI_API_KEY"],
    }


def _load_policy(workspace: Path) -> dict[str, Any]:
    path = workspace / "policies" / "policy_secrets.v1.json"
    if not path.exists():
        return _default_policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_policy()
    return raw if isinstance(raw, dict) else _default_policy()


def _policy_provider_name(policy: dict[str, Any]) -> str:
    provider = policy.get("provider")
    if provider in ("env", "vault_stub"):
        return provider
    return "env"


def _policy_allowed_secret_ids(policy: dict[str, Any]) -> set[str]:
    allowed = policy.get("allowed_secret_ids")
    if not isinstance(allowed, list):
        return {"OPENAI_API_KEY"}
    out: set[str] = set()
    for item in allowed:
        if isinstance(item, str) and item.strip():
            out.add(item.strip())
    return out or {"OPENAI_API_KEY"}


def run(*, secret_id: str, workspace: str | None = None) -> dict[str, Any]:
    ws = Path(workspace).resolve() if isinstance(workspace, str) and workspace else Path.cwd().resolve()
    policy = _load_policy(ws)
    provider_used = _policy_provider_name(policy)
    allowed_ids = _policy_allowed_secret_ids(policy)

    if secret_id not in allowed_ids:
        raise PolicyViolation("SECRET_ID_NOT_ALLOWED", f"Secret id not allowed by policy: {secret_id}")

    provider = (
        VaultStubSecretsProvider(secrets_path=ws / ".cache" / "vault_stub_secrets.json")
        if provider_used == "vault_stub"
        else EnvSecretsProvider(environ=os.environ)
    )

    value = provider.get(secret_id)
    if not value:
        return {
            "tool": "secrets_get",
            "status": "NOT_FOUND",
            "secret_id": secret_id,
            "provider_used": provider_used,
            "value": "***REDACTED***",
            "redacted": True,
            "found": False,
        }

    handle = secrets.token_hex(16)
    _EPHEMERAL_VALUES[handle] = value
    return {
        "tool": "secrets_get",
        "status": "OK",
        "secret_id": secret_id,
        "provider_used": provider_used,
        "value": "***REDACTED***",
        "redacted": True,
        "found": True,
        "handle": handle,
    }
