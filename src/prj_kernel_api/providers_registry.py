"""Workspace-scoped provider registry for PRJ-KERNEL-API (offline, deterministic)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.prj_kernel_api.providers_registry_schema import validate_policy, validate_registry

PROVIDERS_DIR = ".cache/providers"
PROVIDERS_FILE = "providers.v1.json"
POLICY_FILE = "provider_policy.v1.json"


def _write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _default_registry() -> Dict[str, Any]:
    providers = [
        {
            "id": "openai",
            "enabled": True,
            "base_url": "https://api.openai.com/v1/chat/completions",
            "api_key_env": "OPENAI_API_KEY",
            "default_model": "gpt-4o-mini",
            "timeout_seconds": 30,
        },
        {
            "id": "google",
            "enabled": True,
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "api_key_env": "GEMINI_API_KEY",
            "default_model": "gemini-2.0-flash",
            "timeout_seconds": 30,
        },
        {
            "id": "deepseek",
            "enabled": True,
            "base_url": "https://api.deepseek.com/v1/chat/completions",
            "api_key_env": "DEEPSEEK_API_KEY",
            "default_model": "deepseek-chat",
            "timeout_seconds": 30,
        },
        {
            "id": "qwen",
            "enabled": True,
            "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
            "api_key_env": "DASHSCOPE_API_KEY",
            "default_model": "qwen-plus",
            "timeout_seconds": 30,
        },
        {
            "id": "xai",
            "enabled": True,
            "base_url": "https://api.x.ai/v1/chat/completions",
            "api_key_env": "XAI_API_KEY",
            "default_model": "grok-4-latest",
            "timeout_seconds": 30,
        },
    ]
    return {
        "version": "v1",
        "generated_at": "1970-01-01T00:00:00Z",
        "providers": providers,
    }


def _default_provider_settings(provider_id: str) -> Dict[str, str] | None:
    provider_id = str(provider_id or "").strip().lower()
    registry = _default_registry()
    providers = registry.get("providers", [])
    if not isinstance(providers, list):
        return None
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if provider.get("id") != provider_id:
            continue
        base_url = provider.get("base_url")
        default_model = provider.get("default_model")
        if isinstance(base_url, str) and isinstance(default_model, str):
            return {"base_url": base_url, "default_model": default_model}
    return None


def _env_key_for_provider(provider_id: str) -> str:
    mapping = {
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "xai": "XAI_API_KEY",
        "grok": "XAI_API_KEY",
    }
    return mapping.get(provider_id, "API_KEY")


def _normalize_registry(obj: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Normalize legacy registry shape into current schema (idempotent)."""
    modified = False
    providers = obj.get("providers")
    if not isinstance(providers, list):
        return obj, modified
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        provider_id = provider.get("id")
        defaults = _default_provider_settings(provider_id) if isinstance(provider_id, str) else None
        if isinstance(provider_id, str) and not provider.get("api_key_env"):
            provider["api_key_env"] = _env_key_for_provider(provider_id)
            modified = True
        if defaults:
            base_url = provider.get("base_url")
            if not isinstance(base_url, str) or "__REPLACE__" in base_url:
                provider["base_url"] = defaults["base_url"]
                modified = True
            default_model = provider.get("default_model")
            if not isinstance(default_model, str) or "__REPLACE__" in default_model:
                provider["default_model"] = defaults["default_model"]
                modified = True
        if "api_key" in provider:
            provider.pop("api_key", None)
            modified = True
    return obj, modified


def _default_policy() -> Dict[str, Any]:
    return {
        "version": "v1",
        "allow_providers": ["openai", "google", "deepseek", "qwen", "xai"],
        "default_dry_run": True,
        "max_timeout_seconds": 60,
        "max_retries": 2,
        "rate_limit_rps": 1,
        "redaction": {"enabled": True, "fields": ["api_key", "authorization", "x-api-key"]},
        "network_required_for_live_calls": True,
    }


def ensure_providers_registry(workspace_root: str) -> Dict[str, str]:
    base = Path(workspace_root) / PROVIDERS_DIR
    providers_path = base / PROVIDERS_FILE
    policy_path = base / POLICY_FILE

    if not providers_path.exists():
        registry = _default_registry()
        validate_registry(registry)
        _write_json_atomic(providers_path, registry)
    else:
        registry = json.loads(providers_path.read_text(encoding="utf-8"))
        registry, modified = _normalize_registry(registry)
        try:
            validate_registry(registry)
        except ValueError:
            registry = _default_registry()
            validate_registry(registry)
            modified = True
        if modified:
            _write_json_atomic(providers_path, registry)

    if not policy_path.exists():
        policy = _default_policy()
        validate_policy(policy)
        _write_json_atomic(policy_path, policy)
    else:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        validate_policy(policy)

    return {
        "providers_path": str(providers_path),
        "policy_path": str(policy_path),
    }


def read_registry(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    validate_registry(obj)
    return obj


def read_policy(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    validate_policy(obj)
    return obj
