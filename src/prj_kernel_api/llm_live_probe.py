"""Live LLM probe for PRJ-KERNEL-API (explicit opt-in, deterministic, no secrets)."""

from __future__ import annotations

import hashlib
import json
import ssl
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error, request

from jsonschema import Draft202012Validator

from src.prj_kernel_api.dotenv_loader import resolve_env_value
from src.prj_kernel_api.provider_guardrails import load_guardrails, model_allowed, provider_settings
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry

POLICY_PATH = "policies/policy_llm_live.v1.json"
POLICY_SCHEMA = "schemas/policy-llm-live.schema.json"
REPORT_PATH = ".cache/reports/llm_live_probe.v1.json"


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _validate_policy(policy: Dict[str, Any], schema: Dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda e: e.json_path)
    if errors:
        raise ValueError("POLICY_LLM_LIVE_INVALID")


def _load_policy(workspace_root: str) -> Dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws_policy = Path(workspace_root) / "policies" / "policy_llm_live.v1.json"
    policy_path = ws_policy if ws_policy.exists() else repo_root / POLICY_PATH
    if not policy_path.exists():
        raise ValueError("POLICY_LLM_LIVE_MISSING")
    policy = _load_json(policy_path)
    schema_path = repo_root / POLICY_SCHEMA
    if not schema_path.exists():
        raise ValueError("POLICY_LLM_LIVE_SCHEMA_MISSING")
    schema = _load_json(schema_path)
    _validate_policy(policy, schema)
    return policy


def _live_enabled(policy: Dict[str, Any], workspace_root: str, *, env_mode: str) -> bool:
    if not bool(policy.get("live_enabled", False)):
        return False
    enable_key = policy.get("enable_env_key") if isinstance(policy.get("enable_env_key"), str) else ""
    if not enable_key:
        return False
    present, value = resolve_env_value(enable_key, workspace_root, env_mode=env_mode)
    return bool(present and isinstance(value, str) and value.strip() == "1")


def _provider_allowed(provider_id: str, allowed: List[str]) -> bool:
    if provider_id in allowed:
        return True
    if provider_id == "gemini" and "google" in allowed:
        return True
    if provider_id == "google" and "gemini" in allowed:
        return True
    return False


def _bucket_elapsed_ms(elapsed_ms: float) -> int:
    return int(round(elapsed_ms / 10.0) * 10)


def _preview_hash(payload: Dict[str, Any]) -> str:
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _resolve_tls_cafile() -> str | None:
    try:
        paths = ssl.get_default_verify_paths()
        if isinstance(paths.cafile, str) and paths.cafile and Path(paths.cafile).exists():
            return paths.cafile
    except Exception:
        pass
    fallback = Path("/etc/ssl/cert.pem")
    if fallback.exists():
        return str(fallback)
    return None


def _build_tls_context(tls_cafile: str | None) -> ssl.SSLContext | None:
    if not tls_cafile:
        return None
    try:
        ctx = ssl.create_default_context(cafile=tls_cafile)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx
    except Exception:
        return None


def run_live_probe(
    *,
    workspace_root: str,
    detail: bool = False,
    env_mode: str = "dotenv",
) -> Tuple[str, str | None, Dict[str, Any]]:
    policy = _load_policy(workspace_root)
    live_enabled = _live_enabled(policy, workspace_root, env_mode=env_mode)

    paths = ensure_providers_registry(workspace_root)
    registry = read_registry(Path(paths["providers_path"]))
    read_policy(Path(paths["policy_path"]))
    guardrails = load_guardrails(workspace_root)

    allowed = policy.get("allowed_providers") if isinstance(policy.get("allowed_providers"), list) else []
    max_calls = policy.get("max_calls_per_run")
    timeout_ms = policy.get("timeout_ms")
    max_output_chars = policy.get("max_output_chars")
    max_calls_value = int(max_calls) if isinstance(max_calls, int) and max_calls >= 0 else 0
    timeout_value = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 else 5000
    output_limit = int(max_output_chars) if isinstance(max_output_chars, int) and max_output_chars >= 0 else 0

    providers = registry.get("providers") if isinstance(registry.get("providers"), list) else []
    providers_sorted = sorted(
        [p for p in providers if isinstance(p, dict)],
        key=lambda p: str(p.get("id", "")),
    )

    results: List[Dict[str, Any]] = []
    attempted = 0
    ok_count = 0
    fail_count = 0
    skipped_count = 0

    for provider in providers_sorted:
        provider_id = provider.get("id")
        if not isinstance(provider_id, str):
            continue

        entry: Dict[str, Any] = {
            "provider_id": provider_id,
            "status": "SKIPPED",
            "error_code": None,
            "model": None,
            "http_status": None,
            "elapsed_ms": None,
            "tls_cafile": None,
            "error_type": None,
            "error_detail": None,
        }

        guard = provider_settings(guardrails, provider_id)
        model = guard.get("default_model")
        if isinstance(provider.get("default_model"), str) and not isinstance(model, str):
            model = provider.get("default_model")
        entry["model"] = model if isinstance(model, str) else None

        if not live_enabled:
            entry["error_code"] = "LIVE_DISABLED"
            results.append(entry)
            skipped_count += 1
            continue

        if not _provider_allowed(provider_id, allowed):
            entry["error_code"] = "PROVIDER_NOT_ALLOWED"
            results.append(entry)
            skipped_count += 1
            continue

        if not bool(provider.get("enabled", False)) or not bool(guard.get("enabled", False)):
            entry["error_code"] = "PROVIDER_DISABLED"
            results.append(entry)
            skipped_count += 1
            continue

        base_url = provider.get("base_url") if isinstance(provider.get("base_url"), str) else None
        if not base_url:
            entry["error_code"] = "PROVIDER_CONFIG_MISSING"
            results.append(entry)
            skipped_count += 1
            continue
        if not isinstance(model, str):
            entry["error_code"] = "MODEL_REQUIRED"
            results.append(entry)
            skipped_count += 1
            continue
        if not model_allowed(model, guard.get("allow_models", ["*"])):
            entry["error_code"] = "MODEL_NOT_ALLOWED"
            results.append(entry)
            skipped_count += 1
            continue

        expected_env_keys = guard.get("expected_env_keys", [])
        if not isinstance(expected_env_keys, list):
            expected_env_keys = []
        expected_env_keys = [str(x) for x in expected_env_keys if isinstance(x, str) and x.strip()]
        api_key_env = provider.get("api_key_env") if isinstance(provider.get("api_key_env"), str) else ""
        if not expected_env_keys and api_key_env:
            expected_env_keys = [api_key_env]

        api_key_value: str | None = None
        api_key_used: str | None = None
        for key_name in expected_env_keys:
            api_key_present, candidate_value = resolve_env_value(key_name, workspace_root, env_mode=env_mode)
            if api_key_present and candidate_value:
                api_key_value = candidate_value
                api_key_used = key_name
                break

        entry["api_key_env"] = api_key_env
        entry["api_key_env_used"] = api_key_used
        entry["expected_env_keys"] = expected_env_keys

        if not api_key_value:
            entry["error_code"] = "API_KEY_MISSING"
            results.append(entry)
            skipped_count += 1
            continue

        if max_calls_value and attempted >= max_calls_value:
            entry["error_code"] = "MAX_CALLS_REACHED"
            results.append(entry)
            skipped_count += 1
            continue

        attempted += 1
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key_value}",
        }
        req = request.Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

        tls_cafile = _resolve_tls_cafile()
        tls_context = _build_tls_context(tls_cafile)
        entry["tls_cafile"] = tls_cafile

        start = time.monotonic()
        try:
            with request.urlopen(req, timeout=timeout_value / 1000.0, context=tls_context) as resp:
                entry["http_status"] = resp.status
                if output_limit > 0:
                    resp.read(output_limit)
                entry["status"] = "OK"
                ok_count += 1
        except error.HTTPError as exc:
            entry["http_status"] = int(getattr(exc, "code", 0) or 0)
            entry["status"] = "FAIL"
            entry["error_code"] = "PROVIDER_HTTP_ERROR"
            entry["error_type"] = exc.__class__.__name__
            entry["error_detail"] = str(exc)[:220]
            fail_count += 1
        except Exception as exc:
            entry["status"] = "FAIL"
            entry["error_code"] = "PROVIDER_REQUEST_FAILED"
            entry["error_type"] = exc.__class__.__name__
            entry["error_detail"] = str(exc)[:220]
            fail_count += 1
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            entry["elapsed_ms"] = _bucket_elapsed_ms(elapsed_ms)
            results.append(entry)

    status = "OK"
    if fail_count:
        status = "WARN"
    report = {
        "version": "v1",
        "workspace_root": workspace_root,
        "status": status,
        "attempted": attempted,
        "ok": ok_count,
        "fail": fail_count,
        "skipped": skipped_count,
        "providers": results,
        "preview_sha256": _preview_hash(
            {
                "allowed": allowed,
                "attempted": attempted,
                "ok": ok_count,
                "fail": fail_count,
                "skipped": skipped_count,
            }
        ),
    }

    if detail:
        report["policy"] = {
            "allowed_providers": allowed,
            "max_calls_per_run": max_calls_value,
            "timeout_ms": timeout_value,
        }

    _write_json_atomic(Path(workspace_root) / REPORT_PATH, report)
    return status, None, report
