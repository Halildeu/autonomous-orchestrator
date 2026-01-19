"""PRJ-KERNEL-API: LLM provider actions extracted from adapter.py (script-budget refactor-only)."""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib import error as url_error
from urllib import request as url_request

from jsonschema import Draft202012Validator

from src.prj_kernel_api.api_guardrails import llm_live_allowed
from src.prj_kernel_api.dotenv_loader import resolve_env_presence, resolve_env_value
from src.prj_kernel_api.llm_clients import build_http_request
from src.prj_kernel_api.provider_guardrails import live_call_allowed, load_guardrails, model_allowed, provider_settings
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry

LLM_LIVE_POLICY_PATH = "policies/policy_llm_live.v1.json"
LLM_LIVE_POLICY_SCHEMA = "schemas/policy-llm-live.schema.json"


BuildResponseFn = Callable[..., Dict[str, Any]]


def _estimate_request_bytes(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float | None,
    max_tokens: int | None,
    request_id: str | None,
) -> int:
    payload: Dict[str, Any] = {"model": model, "messages": messages}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if request_id:
        payload["request_id"] = request_id
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return len(encoded)


def _load_llm_live_policy(*, workspace_root: str | Path, repo_root: Path) -> Dict[str, Any]:
    ws_root = Path(workspace_root).resolve() if workspace_root else None
    ws_policy = (ws_root / "policies" / "policy_llm_live.v1.json") if ws_root else None
    policy_path = ws_policy if (ws_policy and ws_policy.exists()) else (repo_root / LLM_LIVE_POLICY_PATH)
    if not policy_path.exists():
        raise ValueError("POLICY_LLM_LIVE_MISSING")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    schema_path = repo_root / LLM_LIVE_POLICY_SCHEMA
    if not schema_path.exists():
        raise ValueError("POLICY_LLM_LIVE_SCHEMA_MISSING")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda e: e.json_path)
    if errors:
        raise ValueError("POLICY_LLM_LIVE_INVALID")
    return policy


def _llm_live_enabled(*, live_policy: Dict[str, Any], workspace_root: str | Path, env_mode: str) -> bool:
    if not bool(live_policy.get("live_enabled", False)):
        return False
    enable_key = live_policy.get("enable_env_key") if isinstance(live_policy.get("enable_env_key"), str) else ""
    if not enable_key:
        return False
    present, value = resolve_env_value(enable_key, str(workspace_root), env_mode=env_mode)
    return bool(present and isinstance(value, str) and value.strip() == "1")


def _provider_allowed_by_llm_live_policy(provider_id: str, allowed: List[str]) -> bool:
    if provider_id in allowed:
        return True
    if provider_id == "gemini" and "google" in allowed:
        return True
    if provider_id == "google" and "gemini" in allowed:
        return True
    if provider_id == "grok" and "xai" in allowed:
        return True
    if provider_id == "xai" and "grok" in allowed:
        return True
    return False


def _canonical_provider_id(provider_id: str) -> str:
    pid = str(provider_id or "").strip().lower()
    if pid == "gemini":
        return "google"
    if pid == "grok":
        return "xai"
    return pid


def _bucket_elapsed_ms(elapsed_ms: float) -> int:
    return int(round(elapsed_ms / 10.0) * 10)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_tls_cafile() -> str | None:
    env_candidates = [
        os.environ.get("SSL_CERT_FILE"),
        os.environ.get("REQUESTS_CA_BUNDLE"),
        os.environ.get("CURL_CA_BUNDLE"),
    ]
    for cand in env_candidates:
        if isinstance(cand, str) and cand.strip():
            try:
                if Path(cand).exists():
                    return cand
            except Exception:
                continue
    system_candidates = [
        "/etc/ssl/cert.pem",  # macOS (and some linux distros)
    ]
    for cand in system_candidates:
        try:
            if Path(cand).exists():
                return cand
        except Exception:
            continue
    return None


@lru_cache(maxsize=2)
def _resolve_tls_context() -> tuple[ssl.SSLContext | None, str | None]:
    cafile = _resolve_tls_cafile()
    if not cafile:
        return None, None
    try:
        return ssl.create_default_context(cafile=cafile), cafile
    except Exception:
        return None, cafile


def _extract_llm_output_text(resp_bytes: bytes) -> str:
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return resp_bytes.decode("utf-8", errors="ignore").strip()

    if not isinstance(obj, dict):
        return resp_bytes.decode("utf-8", errors="ignore").strip()

    choices = obj.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else None
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg.get("content", "").strip()
            if isinstance(first.get("text"), str):
                return first.get("text", "").strip()

    if isinstance(obj.get("output_text"), str):
        return str(obj.get("output_text", "")).strip()

    return resp_bytes.decode("utf-8", errors="ignore").strip()


def _redact(text: str) -> str:
    redacted = text
    for key in (
        "KERNEL_API_TOKEN",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "XAI_API_KEY",
        "GITHUB_TOKEN",
        "SUPPLY_CHAIN_SIGNING_KEY",
    ):
        val = os.environ.get(key)
        if val:
            redacted = redacted.replace(val, "***REDACTED***")
    return redacted


def maybe_handle_llm_actions(
    *,
    action: str,
    params: Dict[str, Any],
    workspace_root: str,
    repo_root: Path,
    env_mode: str,
    request_id: str,
    auth_checked: bool,
    rate_limited: bool,
    policy: Dict[str, Any],
    build_response: BuildResponseFn,
) -> Dict[str, Any] | None:
    if action not in {"llm_providers_init", "llm_list_providers", "llm_call", "llm_call_live"}:
        return None

    try:
        paths = ensure_providers_registry(str(workspace_root))
        providers_path = Path(paths["providers_path"])
        policy_path = Path(paths["policy_path"])
        registry = read_registry(providers_path)
        provider_policy = read_policy(policy_path)
    except ValueError as exc:
        code = str(exc).split(":", 1)[0]
        error_code = code if code.startswith("PROVIDER_") else "PROVIDER_REGISTRY_INVALID"
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=error_code,
            message="Provider registry validation failed.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )
    except Exception:
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="PROVIDER_REGISTRY_INVALID",
            message="Provider registry load failed.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )
    try:
        guardrails = load_guardrails(str(workspace_root))
    except ValueError as exc:
        code = str(exc).strip()
        error_code = code if code.startswith("PROVIDER_GUARDRAILS_") else "PROVIDER_GUARDRAILS_INVALID"
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=error_code,
            message="Provider guardrails missing or invalid.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    if action == "llm_providers_init":
        return build_response(
            status="OK",
            payload={"providers_path": str(providers_path), "policy_path": str(policy_path)},
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=None,
            message="Provider registry initialized.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    allow = provider_policy.get("allow_providers") if isinstance(provider_policy.get("allow_providers"), list) else []
    providers = registry.get("providers") if isinstance(registry.get("providers"), list) else []

    if action == "llm_list_providers":
        summary = []
        for p in providers:
            if not isinstance(p, dict):
                continue
            provider_id = p.get("id")
            if not isinstance(provider_id, str):
                continue
            api_key_env = p.get("api_key_env") if isinstance(p.get("api_key_env"), str) else ""
            guard = provider_settings(guardrails, provider_id)
            expected_env_keys = guard.get("expected_env_keys", [])
            if not expected_env_keys and api_key_env:
                expected_env_keys = [api_key_env]
            api_key_present = False
            found_in = "none"
            for key_name in expected_env_keys:
                api_key_present, found_in = resolve_env_presence(
                    key_name,
                    str(workspace_root),
                    env_mode=env_mode,
                )
                if api_key_present:
                    break
            default_model = guard.get("default_model")
            if not isinstance(default_model, str):
                default_model = p.get("default_model") if isinstance(p.get("default_model"), str) else None
            summary.append(
                {
                    "id": provider_id,
                    "enabled": bool(p.get("enabled", False)) and bool(guard.get("enabled", False)),
                    "allow_models": guard.get("allow_models", []),
                    "base_url_present": bool(p.get("base_url")),
                    "default_model_present": bool(default_model),
                    "default_model": default_model,
                    "api_key_env": api_key_env,
                    "expected_env_keys": expected_env_keys,
                    "api_key_present": bool(api_key_present),
                    "found_in": found_in,
                }
            )
        return build_response(
            status="OK",
            payload={"providers_summary": summary},
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=None,
            message="Providers listed.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    provider_id_input = params.get("provider_id") if isinstance(params.get("provider_id"), str) else None
    provider_id = _canonical_provider_id(provider_id_input or "")
    if not provider_id:
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="PROVIDER_NOT_FOUND",
            message="provider_id is required.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )
    if not _provider_allowed_by_llm_live_policy(provider_id, [str(x) for x in allow]):
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="PROVIDER_NOT_ALLOWED",
            message="Provider not allowed.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    provider = next((p for p in providers if isinstance(p, dict) and p.get("id") == provider_id), None)
    if provider is None:
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="PROVIDER_NOT_FOUND",
            message="Provider not found.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )
    guard = provider_settings(guardrails, provider_id)
    if not bool(provider.get("enabled", False)) or not bool(guard.get("enabled", False)):
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="PROVIDER_DISABLED",
            message="Provider disabled.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    base_url = provider.get("base_url")
    model = params.get("model") if isinstance(params.get("model"), str) else guard.get("default_model")
    if not isinstance(model, str):
        model = provider.get("default_model") if isinstance(provider.get("default_model"), str) else None
    if not isinstance(base_url, str):
        return build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="PROVIDER_CONFIG_MISSING",
            message="Provider config missing required fields.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )
    if not isinstance(model, str):
        return build_response(
            status="FAIL",
            payload={"provider_id": provider_id},
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="MODEL_REQUIRED",
            message="Model is required or must be set by policy default.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    timeout = provider.get("timeout_seconds")
    timeout_value = guard.get("timeout_seconds", 20)
    if isinstance(timeout, int) and timeout > 0:
        timeout_value = min(timeout_value, timeout) if timeout_value > 0 else timeout

    dry_run = params.get("dry_run")
    if not isinstance(dry_run, bool):
        dry_run = bool(provider_policy.get("default_dry_run", True))

    messages = params.get("messages") if isinstance(params.get("messages"), list) else []
    temperature = params.get("temperature") if isinstance(params.get("temperature"), (int, float)) else None
    max_tokens = params.get("max_tokens") if isinstance(params.get("max_tokens"), int) else None
    req_id = params.get("request_id") if isinstance(params.get("request_id"), str) else request_id

    api_key_env = provider.get("api_key_env") if isinstance(provider.get("api_key_env"), str) else ""
    expected_env_keys = guard.get("expected_env_keys", [])
    if not expected_env_keys and api_key_env:
        expected_env_keys = [api_key_env]
    api_key_present = False
    found_in = "none"
    key_used: str | None = None
    for key_name in expected_env_keys:
        api_key_present, found_in = resolve_env_presence(
            key_name,
            str(workspace_root),
            env_mode=env_mode,
        )
        if api_key_present:
            key_used = key_name
            break

    if not isinstance(model, str) or not model_allowed(model, guard.get("allow_models", ["*"])):
        return build_response(
            status="FAIL",
            payload={
                "provider_id": provider_id,
                "model": model if isinstance(model, str) else None,
                "allow_models": guard.get("allow_models", []),
            },
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code="MODEL_NOT_ALLOWED",
            message="Model not allowed by guardrails.",
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    max_request_bytes = guard.get("max_request_bytes", 0)
    if isinstance(max_request_bytes, int) and max_request_bytes > 0:
        req_bytes = _estimate_request_bytes(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_id=req_id,
        )
        if req_bytes > max_request_bytes:
            return build_response(
                status="FAIL",
                payload={
                    "provider_id": provider_id,
                    "model": model,
                    "request_bytes": req_bytes,
                    "max_request_bytes": max_request_bytes,
                },
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="REQUEST_TOO_LARGE",
                message="LLM request exceeds guardrails limit.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

    if not dry_run:
        if not llm_live_allowed(policy):
            return build_response(
                status="FAIL",
                payload={
                    "provider_id": provider_id,
                    "model": model,
                    "dry_run": False,
                    "api_key_present": bool(api_key_present),
                },
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="LIVE_CALL_DISABLED",
                message="Live calls disabled by policy.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        allowed, reason = live_call_allowed(
            policy=guardrails,
            workspace_root=str(workspace_root),
            env_mode=env_mode,
            api_key_present=bool(api_key_present),
        )
        if not allowed:
            return build_response(
                status="FAIL",
                payload={
                    "provider_id": provider_id,
                    "model": model,
                    "dry_run": False,
                    "api_key_present": bool(api_key_present),
                    "live_gate_reason": reason,
                },
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="LIVE_CALL_DISABLED",
                message="Live calls disabled by provider guardrails.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if action != "llm_call_live":
            return build_response(
                status="FAIL",
                payload={
                    "provider_id": provider_id,
                    "model": model,
                    "dry_run": False,
                    "api_key_present": bool(api_key_present),
                },
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="LIVE_CALL_DISABLED",
                message="Live calls disabled (offline mode).",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        try:
            live_policy = _load_llm_live_policy(workspace_root=workspace_root, repo_root=repo_root)
        except ValueError as exc:
            return build_response(
                status="FAIL",
                payload=None,
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code=str(exc).strip() or "POLICY_LLM_LIVE_INVALID",
                message="LLM live policy missing or invalid.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if not _llm_live_enabled(live_policy=live_policy, workspace_root=workspace_root, env_mode=env_mode):
            return build_response(
                status="FAIL",
                payload={
                    "provider_id": provider_id,
                    "model": model,
                    "dry_run": False,
                },
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="LIVE_DISABLED",
                message="LLM live disabled (env gate).",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        allowed_providers = live_policy.get("allowed_providers") if isinstance(live_policy.get("allowed_providers"), list) else []
        if not _provider_allowed_by_llm_live_policy(provider_id, [str(x) for x in allowed_providers]):
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="PROVIDER_NOT_ALLOWED",
                message="Provider not allowed by live policy.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if "__REPLACE__" in str(base_url):
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="PROVIDER_CONFIG_MISSING",
                message="Provider base_url placeholder must be replaced for live calls.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if not key_used:
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="API_KEY_MISSING",
                message="API key missing.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        api_key_present_value, api_key_value = resolve_env_value(
            key_used,
            str(workspace_root),
            env_mode=env_mode,
        )
        if not api_key_present_value or not api_key_value:
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model, "api_key_present": False},
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="API_KEY_MISSING",
                message="API key missing.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        max_output_chars = live_policy.get("max_output_chars")
        max_output_chars_value = int(max_output_chars) if isinstance(max_output_chars, int) and max_output_chars >= 0 else 0
        timeout_ms = live_policy.get("timeout_ms")
        timeout_ms_value = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 else 5000
        timeout_seconds_live = max(0.1, timeout_ms_value / 1000.0)
        timeout_seconds_live = min(float(timeout_value), float(timeout_seconds_live))

        max_response_bytes = guard.get("max_response_bytes", 131072)
        max_response_bytes_value = int(max_response_bytes) if isinstance(max_response_bytes, int) and max_response_bytes > 0 else 131072

        req_body = {
            "model": model,
            "messages": messages,
        }
        if temperature is not None:
            req_body["temperature"] = temperature
        if max_tokens is not None:
            req_body["max_tokens"] = max_tokens
        # Some providers reject unknown top-level request fields. Keep
        # request_id for internal correlation only (audit/response),
        # and avoid sending it to these provider APIs.
        if req_id and provider_id not in {"google", "openai", "qwen", "xai"}:
            req_body["request_id"] = req_id

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key_value}",
        }
        req = url_request.Request(
            base_url,
            data=json.dumps(req_body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        start = time.monotonic()
        http_status = None
        resp_bytes = b""
        error_code = None
        error_type: str | None = None
        error_detail: str | None = None
        status = "OK"
        message = "LLM live call completed."
        tls_context, tls_cafile = _resolve_tls_context()
        try:
            with url_request.urlopen(
                req,
                timeout=timeout_seconds_live,
                context=tls_context,
            ) as resp:
                http_status = int(getattr(resp, "status", 0) or 0)
                resp_bytes = resp.read(max_response_bytes_value)
        except url_error.HTTPError as exc:
            http_status = int(getattr(exc, "code", 0) or 0)
            try:
                resp_bytes = exc.read(max_response_bytes_value)
            except Exception:
                resp_bytes = b""
            status = "FAIL"
            error_code = "PROVIDER_HTTP_ERROR"
            message = "LLM provider HTTP error."
        except Exception as exc:
            status = "FAIL"
            error_code = "PROVIDER_REQUEST_FAILED"
            message = "LLM provider request failed."
            error_type = type(exc).__name__
            error_detail = _redact(str(exc))[:400] if str(exc) else None
        finally:
            elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)

        output_text = _extract_llm_output_text(resp_bytes) if resp_bytes else ""
        output_sha256 = _sha256_hex(resp_bytes) if resp_bytes else _sha256_hex(b"")

        output_preview = ""
        output_truncated = False
        if max_output_chars_value > 0:
            if len(output_text) > max_output_chars_value:
                output_preview = output_text[:max_output_chars_value]
                output_truncated = True
            else:
                output_preview = output_text
        else:
            if output_text:
                output_truncated = True

        payload = {
            "provider_id": provider_id,
            "model": model,
            "dry_run": False,
            "api_key_present": True,
            "timeout_seconds": timeout_seconds_live,
            "tls_cafile": tls_cafile,
            "http_status": http_status,
            "elapsed_ms": elapsed_ms,
            "error_type": error_type,
            "error_detail": error_detail,
            "output_sha256": output_sha256,
            "output_preview": output_preview,
            "output_truncated": output_truncated,
            "nondeterministic": True,
        }

        return build_response(
            status=status,
            payload=payload,
            notes=["PROGRAM_LED=true", "no_secrets=true", "llm_live=true"],
            request_id=request_id,
            error_code=error_code,
            message=message,
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )

    preview = build_http_request(
        provider_id=provider_id,
        base_url=base_url,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        request_id=req_id,
    )
    payload = {
        "provider_id": provider_id,
        "model": model,
        "dry_run": True,
        "timeout_seconds": timeout_value,
        "api_key_present": bool(api_key_present),
        "key_source": found_in,
        "allow_models": guard.get("allow_models", []),
        "max_request_bytes": guard.get("max_request_bytes", 0),
        "max_response_bytes": guard.get("max_response_bytes", 0),
        "retry_count": guard.get("retry_count", 0),
        "llm_request_preview": preview,
    }
    return build_response(
        status="OK",
        payload=payload,
        notes=["PROGRAM_LED=true", "no_secrets=true", "dry_run=true"],
        request_id=request_id,
        error_code=None,
        message="LLM request preview generated.",
        auth_checked=auth_checked,
        rate_limited=rate_limited,
    )

