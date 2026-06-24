from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.prj_kernel_api.adapter import (
    DEFAULT_ROADMAP,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    GuardrailsError,
    _build_response,
    _codex_env_check,
    _estimate_request_bytes,
    _extract_headers,
    _find_repo_root,
    _load_schema,
    _normalize_intake_payload,
    _parse_json_from_output,
    _redact,
    _run_manage,
    _validate_schema,
    acquire_concurrency,
    action_allowed,
    compute_request_id,
    enforce_limits,
    llm_live_allowed,
    load_guardrails_policy,
    release_concurrency,
    verify_auth,
)
from src.prj_kernel_api.adapter_llm_actions import maybe_handle_llm_actions
from src.prj_kernel_api.dotenv_loader import resolve_env_presence
from src.prj_kernel_api.llm_clients import build_http_request
from src.prj_kernel_api.llm_live_probe import run_live_probe
from src.prj_kernel_api.m0_plan import ensure_manage_split_plan
from src.prj_kernel_api.provider_guardrails import live_call_allowed, load_guardrails, model_allowed, provider_settings
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry

def handle_request_impl(req: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(req, dict):
        return _build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true"],
            request_id="REQ-INVALID",
            error_code="INVALID_REQUEST",
            message="Request must be a JSON object.",
        )

    repo_root = _find_repo_root(Path(__file__).resolve())
    kind = req.get("kind") if isinstance(req.get("kind"), str) else req.get("action")
    action = str(kind).strip() if isinstance(kind, str) else ""
    params = req.get("params") if isinstance(req.get("params"), dict) else {}
    if isinstance(req.get("detail"), bool) and "detail" not in params:
        params["detail"] = bool(req.get("detail"))
    if isinstance(req.get("strict"), bool) and "strict" not in params:
        params["strict"] = bool(req.get("strict"))

    env_mode = req.get("env_mode") if isinstance(req.get("env_mode"), str) else params.get("env_mode")
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    workspace_root = req.get("workspace_root")
    workspace_root_str = str(workspace_root) if isinstance(workspace_root, str) else ""
    request_id = req.get("request_id") if isinstance(req.get("request_id"), str) else compute_request_id(
        action,
        {
            "workspace_root": workspace_root_str,
            "params": params,
            "env_mode": env_mode,
            "mode": req.get("mode", "json"),
        },
    )
    normalized = {
        "version": "v1",
        "request_id": request_id,
        "kind": action,
        "workspace_root": workspace_root_str,
        "params": params,
        "env_mode": env_mode,
        "mode": req.get("mode", "json"),
    }
    try:
        schema = _load_schema(REQUEST_SCHEMA, repo_root)
    except Exception:
        return _build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true"],
            request_id=request_id,
            error_code="KERNEL_API_SCHEMA_INVALID",
            message="Request schema load failed.",
        )
    errors = _validate_schema(schema, normalized)
    if errors:
        return _build_response(
            status="FAIL",
            payload={"errors": errors},
            notes=["PROGRAM_LED=true"],
            request_id=request_id,
            error_code="KERNEL_API_SCHEMA_INVALID",
            message="Request schema validation failed.",
        )

    workspace_root = str(normalized.get("workspace_root", ""))
    headers = _extract_headers(req, params)
    auth_checked = False
    rate_limited = False

    try:
        policy = load_guardrails_policy(workspace_root)
    except GuardrailsError as exc:
        error_code = str(exc)
        return _build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=error_code,
            message="Kernel API guardrails policy missing or invalid.",
            auth_checked=False,
            rate_limited=False,
        )

    body_bytes = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ok, error_code, rate_limited = enforce_limits(
        policy=policy,
        workspace_root=workspace_root,
        env_mode=env_mode,
        body_bytes=body_bytes,
        json_obj=normalized,
    )
    if not ok:
        return _build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=error_code,
            message="Kernel API guardrails limits failed.",
            auth_checked=False,
            rate_limited=rate_limited,
        )

    ok, error_code, sem = acquire_concurrency(policy, workspace_root, env_mode=env_mode)
    if not ok:
        return _build_response(
            status="FAIL",
            payload=None,
            notes=["PROGRAM_LED=true", "no_secrets=true"],
            request_id=request_id,
            error_code=error_code,
            message="Kernel API concurrency limit reached.",
            auth_checked=False,
            rate_limited=rate_limited,
        )

    try:
        auth_ok, auth_error, auth_checked = verify_auth(
            headers=headers,
            body_bytes=body_bytes,
            policy=policy,
            workspace_root=workspace_root,
            env_mode=env_mode,
        )
        if not auth_ok:
            return _build_response(
                status="FAIL",
                payload=None,
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code=auth_error or "KERNEL_API_UNAUTHORIZED",
                message="Kernel API authorization failed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if not action_allowed(policy, action):
            return _build_response(
                status="FAIL",
                payload=None,
                notes=["PROGRAM_LED=true", "no_secrets=true"],
                request_id=request_id,
                error_code="KERNEL_API_ACTION_DENIED",
                message="Kernel API action not allowed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        llm_resp = maybe_handle_llm_actions(
            action=action,
            params=params,
            workspace_root=workspace_root,
            repo_root=repo_root,
            env_mode=env_mode,
            request_id=request_id,
            auth_checked=auth_checked,
            rate_limited=rate_limited,
            policy=policy,
            build_response=_build_response,
        )
        if llm_resp is not None:
            return llm_resp

        detail = bool(params.get("detail", False))
        strict = bool(params.get("strict", False))
        args: List[str] = []

        if action == "codex_home_init":
            try:
                from src.prj_kernel_api.codex_home import ensure_codex_home

                env_overrides = ensure_codex_home(str(workspace_root))
                codex_home = env_overrides.get("CODEX_HOME")
            except Exception:
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="CODEX_HOME_INIT_FAILED",
                    message="CODEX_HOME bootstrap failed.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            return _build_response(
                status="OK",
                payload={"codex_home": codex_home},
                notes=["PROGRAM_LED=true", "no_secrets=true", "SET_CODEX_HOME_FOR_RUNNERS=true"],
                request_id=request_id,
                error_code=None,
                message="CODEX_HOME initialized.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        if action == "codex_env_check":
            status, error_code, payload = _codex_env_check(repo_root=repo_root, strict=strict)
            notes = ["PROGRAM_LED=true", "no_secrets=true"]
            if strict:
                notes.append("strict=true")
            return _build_response(
                status=status,
                payload=payload,
                notes=notes,
                request_id=request_id,
                error_code=error_code,
                message="Codex env check completed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        if action == "m0_plan_ensure":
            plan_id = params.get("plan_id") if isinstance(params.get("plan_id"), str) else "manage_split"
            if plan_id != "manage_split":
                return _build_response(
                    status="FAIL",
                    payload={"plan_id": plan_id},
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="PLAN_ID_NOT_SUPPORTED",
                    message="Unsupported plan_id.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            try:
                result = ensure_manage_split_plan(str(workspace_root))
            except Exception:
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="M0_PLAN_ENSURE_FAILED",
                    message="M0 plan ensure failed.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            payload = {
                "plan_path": result.get("plan_path"),
                "plan_source": result.get("plan_source"),
            }
            discovery_path = result.get("discovery_report_path")
            if isinstance(discovery_path, str):
                payload["discovery_report_path"] = discovery_path
            return _build_response(
                status="OK",
                payload=payload,
                notes=["PROGRAM_LED=true", "no_secrets=true", "plan_id=manage_split"],
                request_id=request_id,
                error_code=None,
                message="M0 plan ensured.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        if action in {"llm_providers_init", "llm_list_providers", "llm_call"}:
            try:
                paths = ensure_providers_registry(str(workspace_root))
                providers_path = Path(paths["providers_path"])
                policy_path = Path(paths["policy_path"])
                registry = read_registry(providers_path)
                provider_policy = read_policy(policy_path)
            except ValueError as exc:
                code = str(exc).split(":", 1)[0]
                error_code = code if code.startswith("PROVIDER_") else "PROVIDER_REGISTRY_INVALID"
                return _build_response(
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
                return _build_response(
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
                return _build_response(
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
                return _build_response(
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
                return _build_response(
                    status="OK",
                    payload={"providers_summary": summary},
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code=None,
                    message="Providers listed.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            provider_id = params.get("provider_id") if isinstance(params.get("provider_id"), str) else None
            if not provider_id:
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="PROVIDER_NOT_FOUND",
                    message="provider_id is required.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            if provider_id not in allow:
                return _build_response(
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
                return _build_response(
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
                return _build_response(
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
                return _build_response(
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
                return _build_response(
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
            for key_name in expected_env_keys:
                api_key_present, found_in = resolve_env_presence(
                    key_name,
                    str(workspace_root),
                    env_mode=env_mode,
                )
                if api_key_present:
                    break

            if not isinstance(model, str) or not model_allowed(model, guard.get("allow_models", ["*"])):
                return _build_response(
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
                    return _build_response(
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
                    return _build_response(
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
                    return _build_response(
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
                return _build_response(
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
            return _build_response(
                status="OK",
                payload=payload,
                notes=["PROGRAM_LED=true", "no_secrets=true", "dry_run=true"],
                request_id=request_id,
                error_code=None,
                message="LLM request preview generated.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        if action == "llm_live_probe":
            detail = bool(params.get("detail", False))
            try:
                status, error_code, report = run_live_probe(
                    workspace_root=str(workspace_root),
                    detail=detail,
                    env_mode=env_mode,
                )
            except ValueError as exc:
                code = str(exc).strip()
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code=code or "POLICY_LLM_LIVE_INVALID",
                    message="LLM live probe policy invalid.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            except Exception:
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="KERNEL_API_INTERNAL_ERROR",
                    message="LLM live probe failed.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            notes = ["PROGRAM_LED=true", "no_secrets=true", "live_probe=true"]
            if detail:
                notes.append("detail=true")
            payload = {"probe_report": report} if report else {"probe_report": {}}
            return _build_response(
                status=status,
                payload=payload,
                notes=notes,
                request_id=request_id,
                error_code=error_code,
                message="LLM live probe completed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        if action == "github_ops_check":
            args = [
                "github-ops-check",
                "--workspace-root",
                str(workspace_root),
                "--chat",
                "false",
            ]
        elif action == "github_ops_job_start":
            kind = str(params.get("kind") or "").strip()
            if not kind:
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="KIND_REQUIRED",
                    message="GitHub ops job kind required.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            dry_run = bool(params.get("dry_run", True))
            args = [
                "github-ops-job-start",
                "--workspace-root",
                str(workspace_root),
                "--kind",
                kind,
                "--dry-run",
                "true" if dry_run else "false",
            ]
        elif action == "github_ops_job_poll":
            job_id = str(params.get("job_id") or "").strip()
            if not job_id:
                return _build_response(
                    status="FAIL",
                    payload=None,
                    notes=["PROGRAM_LED=true", "no_secrets=true"],
                    request_id=request_id,
                    error_code="JOB_ID_REQUIRED",
                    message="GitHub ops job id required.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            args = [
                "github-ops-job-poll",
                "--workspace-root",
                str(workspace_root),
                "--job-id",
                job_id,
            ]
        elif action == "intake_status":
            args = [
                "work-intake-build",
                "--workspace-root",
                str(workspace_root),
            ]
        elif action == "intake_next":
            args = [
                "work-intake-build",
                "--workspace-root",
                str(workspace_root),
            ]
        elif action == "intake_create_plan":
            args = [
                "work-intake-build",
                "--workspace-root",
                str(workspace_root),
            ]
        elif action == "project_status":
            args = [
                "project-status",
                "--roadmap",
                DEFAULT_ROADMAP,
                "--workspace-root",
                str(workspace_root),
                "--mode",
                "autopilot_chat",
            ]
        elif action == "system_status":
            args = [
                "system-status",
                "--workspace-root",
                str(workspace_root),
                "--dry-run",
                "false",
            ]
        elif action == "doc_nav_check":
            args = [
                "doc-nav-check",
                "--workspace-root",
                str(workspace_root),
            ]
            if detail:
                args += ["--detail", "true"]
            if strict:
                args += ["--strict", "true"]
        elif action == "roadmap_finish":
            max_minutes = int(params.get("max_minutes", 5))
            sleep_seconds = int(params.get("sleep_seconds", 0))
            max_steps = int(params.get("max_steps_per_iteration", 2))
            args = [
                "roadmap-finish",
                "--roadmap",
                DEFAULT_ROADMAP,
                "--workspace-root",
                str(workspace_root),
                "--max-minutes",
                str(max_minutes),
                "--sleep-seconds",
                str(sleep_seconds),
                "--max-steps-per-iteration",
                str(max_steps),
            ]
        elif action == "roadmap_follow":
            max_steps = int(params.get("max_steps", 1))
            args = [
                "roadmap-follow",
                "--roadmap",
                DEFAULT_ROADMAP,
                "--workspace-root",
                str(workspace_root),
                "--max-steps",
                str(max_steps),
            ]

        proc = _run_manage(args, repo_root)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        payload, parse_err = _parse_json_from_output(stdout)

        notes = ["PROGRAM_LED=true", f"action={action}"]
        if strict:
            notes.append("strict=true")
        if detail:
            notes.append("detail=true")

        if proc.returncode != 0 and not (action == "doc_nav_check" and isinstance(payload, dict)):
            err_excerpt = _redact(stderr.strip())[:300] if stderr else ""
            return _build_response(
                status="FAIL",
                payload=payload,
                notes=notes,
                request_id=request_id,
                error_code="SUBPROCESS_FAILED",
                message="Program-led command failed.",
                stderr_excerpt=err_excerpt or None,
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if payload is None:
            err_excerpt = _redact(stdout.strip())[:300] if stdout else ""
            return _build_response(
                status="FAIL",
                payload=None,
                notes=notes,
                request_id=request_id,
                error_code="JSON_PARSE_FAILED",
                message="Could not parse JSON output.",
                stderr_excerpt=err_excerpt or (parse_err or None),
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        status = payload.get("status") if isinstance(payload, dict) else None
        status_str = str(status) if isinstance(status, str) and status else "OK"
        if action in {"intake_status", "intake_next", "intake_create_plan"} and isinstance(payload, dict):
            payload = _normalize_intake_payload(action=action, payload=payload)
        if action == "doc_nav_check":
            raw = str(status or "")
            if raw == "FAIL":
                status_str = "WARN"
        if action in {"github_ops_check", "github_ops_job_start", "github_ops_job_poll"}:
            raw = str(status or "")
            if raw in {"SKIP"}:
                status_str = "IDLE"
            elif raw in {"RUNNING", "QUEUED", "PASS", "OK"}:
                status_str = "OK"
            elif raw in {"FAIL"}:
                status_str = "WARN"
        response = _build_response(
            status=status_str,
            payload=payload,
            notes=notes,
            request_id=request_id,
            auth_checked=auth_checked,
            rate_limited=rate_limited,
        )
        try:
            resp_schema = _load_schema(RESPONSE_SCHEMA, repo_root)
        except Exception:
            return _build_response(
                status="FAIL",
                payload=None,
                notes=notes,
                request_id=request_id,
                error_code="KERNEL_API_SCHEMA_INVALID",
                message="Response schema load failed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        resp_errors = _validate_schema(resp_schema, response)
        if resp_errors:
            return _build_response(
                status="FAIL",
                payload={"errors": resp_errors},
                notes=notes,
                request_id=request_id,
                error_code="KERNEL_API_SCHEMA_INVALID",
                message="Response schema validation failed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        return response
    finally:
        release_concurrency(sem)
