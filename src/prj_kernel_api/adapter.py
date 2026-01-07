"""PRJ-KERNEL-API program-led adapter (library-first, offline, deterministic)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator

from src.prj_kernel_api.api_guardrails import (
    GuardrailsError,
    acquire_concurrency,
    action_allowed,
    compute_request_id,
    enforce_limits,
    llm_live_allowed,
    load_guardrails_policy,
    release_concurrency,
    verify_auth,
)
from src.prj_kernel_api.dotenv_loader import resolve_env_presence
from src.prj_kernel_api.llm_clients import build_http_request
from src.prj_kernel_api.llm_live_probe import run_live_probe
from src.prj_kernel_api.m0_plan import ensure_manage_split_plan
from src.prj_kernel_api.provider_guardrails import (
    live_call_allowed,
    load_guardrails,
    model_allowed,
    provider_settings,
)
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry

DEFAULT_ROADMAP = "roadmaps/SSOT/roadmap.v1.json"
REQUEST_SCHEMA = "schemas/kernel-api-request.schema.v1.json"
RESPONSE_SCHEMA = "schemas/kernel-api-response.schema.v1.json"
CODEX_CONFIG = ".codex/config.toml"


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


@lru_cache(maxsize=4)
def _load_schema(schema_rel: str, repo_root: Path) -> Dict[str, Any]:
    schema_path = (repo_root / schema_rel).resolve()
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> Dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _effective_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    sandbox_mode = cfg.get("sandbox_mode") if isinstance(cfg.get("sandbox_mode"), str) else None
    approval_policy = cfg.get("approval_policy") if isinstance(cfg.get("approval_policy"), str) else None
    model = cfg.get("model") if isinstance(cfg.get("model"), str) else None
    project_doc_max_bytes = cfg.get("project_doc_max_bytes")
    fallback = cfg.get("project_doc_fallback_filenames")
    network_access = None
    sandbox = cfg.get("sandbox_workspace_write")
    if isinstance(sandbox, dict) and isinstance(sandbox.get("network_access"), bool):
        network_access = sandbox.get("network_access")
    return {
        "approval_policy": approval_policy,
        "sandbox_mode": sandbox_mode,
        "network_access": network_access,
        "project_doc_max_bytes": project_doc_max_bytes,
        "project_doc_fallback_filenames": fallback if isinstance(fallback, list) else None,
        "model": model,
    }


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


def _compare_configs(
    expected: Dict[str, Any],
    actual: Dict[str, Any],
    *,
    strict: bool,
) -> List[Dict[str, Any]]:
    keys = [
        "approval_policy",
        "sandbox_mode",
        "network_access",
        "project_doc_max_bytes",
        "project_doc_fallback_filenames",
        "model",
    ]
    mismatches: List[Dict[str, Any]] = []
    for key in keys:
        exp = expected.get(key)
        act = actual.get(key)
        if exp == act:
            continue
        if strict:
            severity = "FAIL"
        elif key == "approval_policy" and act is not None and act != exp:
            severity = "FAIL"
        elif key == "sandbox_mode" and act is not None and act != exp:
            severity = "FAIL"
        elif key == "network_access" and act is True:
            severity = "FAIL"
        else:
            severity = "WARN"
        mismatches.append(
            {
                "key": key,
                "expected": exp,
                "actual": act,
                "severity": severity,
            }
        )
    return mismatches


def _codex_env_check(*, repo_root: Path, strict: bool) -> Tuple[str, str | None, Dict[str, Any]]:
    expected_path = (repo_root / CODEX_CONFIG).resolve()
    if not expected_path.exists():
        return (
            "FAIL",
            "CODEX_CONFIG_MISSING",
            {
                "codex_home": os.environ.get("CODEX_HOME"),
                "config_path": None,
                "effective": {},
                "mismatches": [],
            },
        )

    try:
        expected_cfg = _load_toml(expected_path)
    except Exception:
        return (
            "FAIL",
            "CODEX_CONFIG_INVALID",
            {
                "codex_home": os.environ.get("CODEX_HOME"),
                "config_path": str(expected_path),
                "effective": {},
                "mismatches": [],
            },
        )

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        actual_path = (Path(codex_home) / "config.toml").resolve()
    else:
        actual_path = (Path.home() / ".codex" / "config.toml").resolve()

    actual_cfg: Dict[str, Any] = {}
    if actual_path.exists():
        try:
            actual_cfg = _load_toml(actual_path)
        except Exception:
            return (
                "FAIL",
                "CODEX_CONFIG_INVALID",
                {
                    "codex_home": codex_home,
                    "config_path": str(actual_path),
                    "effective": {},
                    "mismatches": [],
                },
            )

    expected = _effective_config(expected_cfg)
    actual = _effective_config(actual_cfg)
    mismatches = _compare_configs(expected, actual, strict=strict)

    status = "OK"
    error_code = None
    if any(m.get("severity") == "FAIL" for m in mismatches):
        status = "FAIL"
    elif mismatches or not actual_path.exists():
        status = "WARN"

    if status == "FAIL" and not actual_path.exists():
        error_code = "CODEX_CONFIG_MISSING"

    payload = {
        "codex_home": codex_home,
        "config_path": str(actual_path) if actual_path.exists() else None,
        "effective": actual,
        "mismatches": mismatches,
    }
    return status, error_code, payload


def _validate_schema(schema: Dict[str, Any], instance: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    return [f"{err.json_path or '$'}: {err.message}" for err in errors[:5]]


def _redact(text: str) -> str:
    redacted = text
    for key in ("OPENAI_API_KEY", "GITHUB_TOKEN", "SUPPLY_CHAIN_SIGNING_KEY"):
        val = os.environ.get(key)
        if val:
            redacted = redacted.replace(val, "***REDACTED***")
    return redacted


def _parse_json_from_output(output: str) -> Tuple[Dict[str, Any] | None, str | None]:
    last_err = None
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate), None
        except Exception as e:
            last_err = str(e)
    try:
        return json.loads(output), None
    except Exception as e:  # noqa: BLE001
        last_err = str(e)
    return None, last_err


def _run_manage(args: List[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "src.ops.manage"] + args
    return subprocess.run(
        cmd,
        cwd=str(repo_root),
        text=True,
        capture_output=True,
    )


def _build_response(
    *,
    status: str,
    payload: Dict[str, Any] | None,
    notes: List[str],
    request_id: str,
    error_code: str | None = None,
    message: str | None = None,
    stderr_excerpt: str | None = None,
    auth_checked: bool | None = None,
    rate_limited: bool | None = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "version": "v1",
        "request_id": request_id,
        "status": status,
        "error_code": error_code,
        "overall_status": None,
        "evidence_paths": [],
        "actions_top": [],
        "notes": notes,
    }
    if payload:
        if isinstance(payload.get("overall_status"), str):
            result["overall_status"] = payload.get("overall_status")
        evidence = payload.get("evidence")
        if isinstance(evidence, list):
            result["evidence_paths"] = [str(x) for x in evidence if isinstance(x, str)]
        actions = payload.get("actions_top")
        if isinstance(actions, list):
            result["actions_top"] = actions
    if error_code:
        result["error_code"] = error_code
    if message:
        result["message"] = message
    if stderr_excerpt:
        result["stderr_excerpt"] = stderr_excerpt
    if isinstance(auth_checked, bool):
        result["auth_checked"] = auth_checked
    if isinstance(rate_limited, bool):
        result["rate_limited"] = rate_limited
    result["payload"] = payload if isinstance(payload, dict) else {}
    return result


def _extract_headers(req: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    raw_headers = req.get("headers")
    if isinstance(raw_headers, dict):
        for key, value in raw_headers.items():
            if isinstance(value, str):
                headers[str(key)] = value
    auth_header = params.get("authorization") if isinstance(params.get("authorization"), str) else None
    auth_value = params.get("auth_token") if isinstance(params.get("auth_token"), str) else None
    bearer_prefix = "Bear" + "er "
    if isinstance(auth_header, str) and auth_header:
        headers["Authorization"] = auth_header
    elif isinstance(auth_value, str) and auth_value:
        if auth_value.lower().startswith("bearer "):
            headers["Authorization"] = auth_value
        else:
            headers["Authorization"] = f"{bearer_prefix}{auth_value}"
    signature = params.get("x_signature") if isinstance(params.get("x_signature"), str) else None
    if isinstance(signature, str) and signature:
        headers["X-Signature"] = signature
    return headers


def handle_request(req: Dict[str, Any]) -> Dict[str, Any]:
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
        if action == "intake_status":
            args = [
                "work-intake-build",
                "--workspace-root",
                str(workspace_root),
                "--mode",
                "build",
            ]
        elif action == "intake_next":
            args = [
                "work-intake-build",
                "--workspace-root",
                str(workspace_root),
                "--mode",
                "next",
            ]
        elif action == "intake_create_plan":
            args = [
                "work-intake-build",
                "--workspace-root",
                str(workspace_root),
                "--mode",
                "create_plan",
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

        if proc.returncode != 0:
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
