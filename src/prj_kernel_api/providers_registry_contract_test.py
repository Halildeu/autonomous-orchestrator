"""Contract test for PRJ-KERNEL-API providers registry (offline)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_kernel_api.provider_guardrails import load_guardrails, model_allowed, provider_settings
    from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry

    ws = repo_root / ".cache" / "ws_providers_demo"
    if ws.exists():
        shutil.rmtree(ws)

    paths = ensure_providers_registry(str(ws))
    providers_path = Path(paths["providers_path"])
    policy_path = Path(paths["policy_path"])

    registry = read_registry(providers_path)
    policy = read_policy(policy_path)

    providers = registry.get("providers")
    if not isinstance(providers, list) or len(providers) < 4:
        raise SystemExit("Providers registry test failed: providers list missing.")

    allow = policy.get("allow_providers")
    if not isinstance(allow, list) or set(allow) != {"openai", "google", "deepseek", "qwen", "xai"}:
        raise SystemExit("Providers registry test failed: allow_providers mismatch.")

    guardrails = load_guardrails(str(ws))
    for provider_id in ["deepseek", "google", "openai", "qwen", "xai"]:
        guard = provider_settings(guardrails, provider_id)
        if not bool(guard.get("enabled", False)):
            continue
        default_model = guard.get("default_model")
        if not isinstance(default_model, str) or not default_model:
            raise SystemExit("Providers registry test failed: default_model missing in guardrails.")
        if not model_allowed(default_model, guard.get("allow_models", [])):
            raise SystemExit("Providers registry test failed: default_model not allowed by guardrails.")

    for provider in providers:
        if not isinstance(provider, dict):
            raise SystemExit("Providers registry test failed: provider entry invalid.")
        provider_id = provider.get("id")
        api_key_env = provider.get("api_key_env")
        if not isinstance(provider_id, str) or not isinstance(api_key_env, str):
            raise SystemExit("Providers registry test failed: provider id/api_key_env missing.")
        if not api_key_env.endswith("_API_KEY") and not api_key_env.endswith("_KEY"):
            raise SystemExit("Providers registry test failed: api_key_env format mismatch.")

    print(
        json.dumps(
            {"status": "OK", "providers_path": str(providers_path), "policy_path": str(policy_path)},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
