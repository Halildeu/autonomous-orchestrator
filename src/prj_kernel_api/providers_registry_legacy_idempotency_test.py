"""Legacy registry normalization idempotency test (project scope)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from src.prj_kernel_api.providers_registry import ensure_providers_registry
from src.prj_kernel_api.providers_registry_schema import validate_registry


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _hash_file(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _write_legacy_registry(path: Path) -> None:
    legacy = {
        "version": "v1",
        "generated_at": "1970-01-01T00:00:00Z",
        "providers": [
            {
                "id": "openai",
                "enabled": True,
                "base_url": "__REPLACE__",
                "api_key": "PLACEHOLDER_OPENAI_ABC",
                "default_model": "__REPLACE__",
                "timeout_seconds": 30,
            },
            {
                "id": "google",
                "enabled": True,
                "base_url": "__REPLACE__",
                "api_key": "PLACEHOLDER_GOOGLE_DEF",
                "default_model": "__REPLACE__",
                "timeout_seconds": 30,
            },
            {
                "id": "deepseek",
                "enabled": True,
                "base_url": "__REPLACE__",
                "api_key": "PLACEHOLDER_DEEPSEEK_GHI",
                "default_model": "__REPLACE__",
                "timeout_seconds": 30,
            },
            {
                "id": "qwen",
                "enabled": True,
                "base_url": "__REPLACE__",
                "api_key": "PLACEHOLDER_QWEN_JKL",
                "default_model": "__REPLACE__",
                "timeout_seconds": 30,
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(legacy, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_registry_legacy_demo"
    if ws.exists():
        shutil.rmtree(ws)

    providers_path = ws / ".cache" / "providers" / "providers.v1.json"
    _write_legacy_registry(providers_path)

    ensure_providers_registry(str(ws))
    first_hash = _hash_file(providers_path)
    registry = json.loads(providers_path.read_text(encoding="utf-8"))
    validate_registry(registry)
    for provider in registry.get("providers", []):
        if isinstance(provider, dict) and "api_key" in provider:
            raise SystemExit("Legacy registry test failed: api_key field still present after normalize.")
        if isinstance(provider, dict) and not provider.get("api_key_env"):
            raise SystemExit("Legacy registry test failed: api_key_env missing after normalize.")

    ensure_providers_registry(str(ws))
    second_hash = _hash_file(providers_path)
    if first_hash != second_hash:
        raise SystemExit("Legacy registry test failed: normalization is not idempotent.")

    print(json.dumps({"status": "OK", "hash": first_hash[:12]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
