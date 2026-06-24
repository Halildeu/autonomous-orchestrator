"""PRJ-KERNEL-API program-led adapter (library-first, offline, deterministic)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]
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
from src.prj_kernel_api.adapter_llm_actions import maybe_handle_llm_actions
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
        from src.prj_kernel_api.codex_home import resolve_effective_codex_config

        resolved = resolve_effective_codex_config(repo_root)
        expected_cfg = resolved.get("effective_config") if isinstance(resolved.get("effective_config"), dict) else {}
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


def _normalize_intake_payload(*, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    top_next_actions = normalized.get("top_next_actions")
    if action == "intake_next" and not isinstance(normalized.get("top_next"), list):
        normalized["top_next"] = top_next_actions[:5] if isinstance(top_next_actions, list) else []
    if action == "intake_create_plan" and "plan_path" not in normalized:
        normalized["plan_path"] = None
    return normalized


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
    from src.prj_kernel_api.adapter_request import handle_request_impl

    return handle_request_impl(req)
