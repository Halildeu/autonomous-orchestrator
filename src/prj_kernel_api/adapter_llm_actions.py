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
LLM_BATCH_POLICY_PATH = "policies/policy_llm_batch.v1.json"
LLM_BATCH_POLICY_SCHEMA = "schemas/policy-llm-batch.schema.json"

_XAI_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


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


def _load_llm_batch_policy(*, workspace_root: str | Path, repo_root: Path) -> Dict[str, Any]:
    ws_root = Path(workspace_root).resolve() if workspace_root else None
    ws_policy = (ws_root / "policies" / "policy_llm_batch.v1.json") if ws_root else None
    policy_path = ws_policy if (ws_policy and ws_policy.exists()) else (repo_root / LLM_BATCH_POLICY_PATH)
    if not policy_path.exists():
        raise ValueError("POLICY_LLM_BATCH_MISSING")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    schema_path = repo_root / LLM_BATCH_POLICY_SCHEMA
    if not schema_path.exists():
        raise ValueError("POLICY_LLM_BATCH_SCHEMA_MISSING")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda e: e.json_path)
    if errors:
        raise ValueError("POLICY_LLM_BATCH_INVALID")
    return policy


def _llm_batch_enabled(*, batch_policy: Dict[str, Any], workspace_root: str | Path, env_mode: str) -> bool:
    if not bool(batch_policy.get("batch_enabled", False)):
        return False
    enable_key = batch_policy.get("enable_env_key") if isinstance(batch_policy.get("enable_env_key"), str) else ""
    if not enable_key:
        return False
    present, value = resolve_env_value(enable_key, str(workspace_root), env_mode=env_mode)
    return bool(present and isinstance(value, str) and value.strip() == "1")


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


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json_obj(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _openai_api_root(base_url: str) -> str:
    url = str(base_url or "").strip()
    if "/v1/" in url:
        return url.split("/v1/")[0].rstrip("/") + "/v1"
    if url.endswith("/v1"):
        return url
    return url.rstrip("/")


def _http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[str, int | None, bytes, str | None, str | None]:
    tls_context, _tls_cafile = _resolve_tls_context()
    req = url_request.Request(url, data=body, headers=headers, method=method)
    start = time.monotonic()
    http_status = None
    resp_bytes = b""
    error_code = None
    error_detail = None
    status = "OK"
    try:
        with url_request.urlopen(req, timeout=timeout_seconds, context=tls_context) as resp:
            http_status = int(getattr(resp, "status", 0) or 0)
            resp_bytes = resp.read(max_response_bytes)
    except url_error.HTTPError as exc:
        http_status = int(getattr(exc, "code", 0) or 0)
        try:
            resp_bytes = exc.read(max_response_bytes)
        except Exception:
            resp_bytes = b""
        status = "FAIL"
        error_code = "PROVIDER_HTTP_ERROR"
    except Exception as exc:
        status = "FAIL"
        error_code = "PROVIDER_REQUEST_FAILED"
        error_detail = _redact(str(exc))[:400] if str(exc) else None
    finally:
        _ = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
    return status, http_status, resp_bytes, error_code, error_detail


def _json_or_error(resp_bytes: bytes) -> tuple[dict[str, Any], str | None]:
    if not resp_bytes:
        return {}, "EMPTY_BODY"
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return {}, "JSON_DECODE_ERROR"
    return (obj if isinstance(obj, dict) else {}), None


def _multipart_form_data(fields: list[tuple[str, str]], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----codexbatch" + hashlib.sha256(str(time.time()).encode("utf-8")).hexdigest()[:16]
    crlf = "\r\n"
    lines: list[bytes] = []
    for name, value in fields:
        lines.append(f"--{boundary}{crlf}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}'.encode("utf-8"))
        lines.append(str(value).encode("utf-8"))
        lines.append(crlf.encode("utf-8"))
    for name, filename, content, content_type in files:
        lines.append(f"--{boundary}{crlf}".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"{crlf}'.encode("utf-8")
        )
        lines.append(f"Content-Type: {content_type}{crlf}{crlf}".encode("utf-8"))
        lines.append(content)
        lines.append(crlf.encode("utf-8"))
    lines.append(f"--{boundary}--{crlf}".encode("utf-8"))
    return b"".join(lines), boundary


def _load_llm_batch_job_index(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "llm_batch_jobs_index.v1.json"
    if not path.exists():
        return {"version": "v1", "generated_at": _now_iso(), "jobs": []}
    obj = _load_json_obj(path)
    if not isinstance(obj.get("jobs"), list):
        obj["jobs"] = []
    if not isinstance(obj.get("version"), str):
        obj["version"] = "v1"
    return obj


def _write_llm_batch_job_index(workspace_root: Path, index_obj: dict[str, Any]) -> Path:
    path = workspace_root / ".cache" / "index" / "llm_batch_jobs_index.v1.json"
    index_obj = dict(index_obj)
    index_obj["version"] = "v1"
    index_obj["generated_at"] = _now_iso()
    jobs = index_obj.get("jobs") if isinstance(index_obj.get("jobs"), list) else []
    index_obj["jobs"] = jobs
    _atomic_write_json(path, index_obj)
    return path


def _upsert_job(index_obj: dict[str, Any], job: dict[str, Any]) -> None:
    jobs = index_obj.get("jobs") if isinstance(index_obj.get("jobs"), list) else []
    jobs_list = [j for j in jobs if isinstance(j, dict)]
    job_id = str(job.get("job_id") or "")
    out: list[dict[str, Any]] = []
    seen = False
    for j in jobs_list:
        if str(j.get("job_id") or "") == job_id:
            out.append(job)
            seen = True
        else:
            out.append(j)
    if not seen:
        out.append(job)
    out.sort(
        key=lambda x: (str(x.get("created_at") or ""), str(x.get("job_id") or "")),
        reverse=True,
    )
    index_obj["jobs"] = out


def _resolve_run_entry(workspace_root: Path, run_id: str) -> dict[str, Any] | None:
    index_path = workspace_root / ".cache" / "index" / "assessment_eval_runs_index.v1.json"
    if not index_path.exists():
        return None
    obj = _load_json_obj(index_path)
    runs = obj.get("runs") if isinstance(obj.get("runs"), list) else []
    for r in runs:
        if not isinstance(r, dict):
            continue
        if str(r.get("run_id") or "") == run_id:
            return r
    return None


def _resolve_run_paths(workspace_root: Path, run_id: str) -> dict[str, Path]:
    rid = str(run_id or "").strip()
    if not rid or rid.lower() == "latest":
        return {
            "assessment_eval": workspace_root / ".cache" / "index" / "assessment_eval.v1.json",
            "gap_register": workspace_root / ".cache" / "index" / "gap_register.v1.json",
        }
    entry = _resolve_run_entry(workspace_root, rid)
    if not entry:
        return {
            "assessment_eval": workspace_root / ".cache" / "index" / "assessment_eval.v1.json",
            "gap_register": workspace_root / ".cache" / "index" / "gap_register.v1.json",
        }
    eval_rel = str(entry.get("assessment_eval_path") or "")
    gap_rel = str(entry.get("gap_register_path") or "")
    paths: dict[str, Path] = {}
    if eval_rel:
        paths["assessment_eval"] = (workspace_root / eval_rel).resolve()
    if gap_rel:
        paths["gap_register"] = (workspace_root / gap_rel).resolve()
    if "assessment_eval" not in paths:
        paths["assessment_eval"] = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    if "gap_register" not in paths:
        paths["gap_register"] = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    return paths


def _build_north_star_batch_snapshot(*, workspace_root: Path, run_id: str) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    paths = _resolve_run_paths(workspace_root, run_id)
    eval_path = paths["assessment_eval"]
    gap_path = paths["gap_register"]
    eval_obj = _load_json_obj(eval_path) if eval_path.exists() else {}
    gap_obj = _load_json_obj(gap_path) if gap_path.exists() else {}
    if not eval_obj:
        notes.append("assessment_eval_missing_or_invalid")
    if not gap_obj:
        notes.append("gap_register_missing_or_invalid")

    lenses = eval_obj.get("lenses") if isinstance(eval_obj.get("lenses"), dict) else {}
    lens_slim: dict[str, Any] = {}
    for lens_id in sorted(lenses.keys()):
        lens = lenses.get(lens_id)
        if not isinstance(lens, dict):
            continue
        lens_slim[lens_id] = {
            "status": str(lens.get("status") or ""),
            "score": lens.get("score"),
            "coverage": lens.get("coverage"),
            "classification": str(lens.get("classification") or ""),
            "reasons": lens.get("reasons") if isinstance(lens.get("reasons"), list) else [],
        }

    gaps = gap_obj.get("gaps") if isinstance(gap_obj.get("gaps"), list) else []
    sev_counts: dict[str, int] = {}
    for g in gaps:
        if not isinstance(g, dict):
            continue
        sev = str(g.get("severity") or "").strip().lower() or "unknown"
        sev_counts[sev] = int(sev_counts.get(sev, 0)) + 1

    snapshot = {
        "run_id": str(run_id or "latest"),
        "generated_at": str(eval_obj.get("generated_at") or ""),
        "eval": {
            "status": str(eval_obj.get("status") or ""),
            "scores": eval_obj.get("scores") if isinstance(eval_obj.get("scores"), dict) else {},
            "lenses": lens_slim,
        },
        "gap": {
            "status": str(gap_obj.get("status") or ""),
            "gaps_total": len(gaps),
            "severity_counts": sev_counts,
        },
    }
    return snapshot, notes


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _to_anthropic_messages(messages: List[Dict[str, Any]]) -> tuple[str | None, List[Dict[str, Any]]]:
    system_parts: List[str] = []
    out: List[Dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role == "system":
            system_parts.append(_as_text(content).strip())
            continue
        role_str = str(role or "").strip().lower()
        if role_str not in {"user", "assistant"}:
            role_str = "user"
        text = _as_text(content)
        out.append({"role": role_str, "content": [{"type": "text", "text": text}]})
    system = "\n\n".join([p for p in system_parts if p]).strip()
    return (system if system else None), out


def _extract_llm_output_text(resp_bytes: bytes) -> str:
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return resp_bytes.decode("utf-8", errors="ignore").strip()

    if not isinstance(obj, dict):
        return resp_bytes.decode("utf-8", errors="ignore").strip()

    # Anthropic Messages API: {"content":[{"type":"text","text":"..."}], ...}
    content = obj.get("content")
    if isinstance(content, list) and content:
        texts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
        if texts:
            return "\n".join(texts).strip()

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
        "CLAUDE_API_KEY",
        "ANTHROPIC_API_KEY",
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
    if action not in {
        "llm_providers_init",
        "llm_list_providers",
        "llm_call",
        "llm_call_live",
        "llm_batch_submit",
        "llm_batch_poll",
    }:
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

    if action in {"llm_batch_submit", "llm_batch_poll"}:
        if provider_id != "openai":
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=["PROGRAM_LED=true", "no_secrets=true", "llm_batch=true"],
                request_id=request_id,
                error_code="PROVIDER_NOT_ALLOWED",
                message="Batch lane currently supports provider_id=openai only.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        try:
            batch_policy = _load_llm_batch_policy(workspace_root=workspace_root, repo_root=repo_root)
        except ValueError as exc:
            return build_response(
                status="FAIL",
                payload=None,
                notes=["PROGRAM_LED=true", "no_secrets=true", "llm_batch=true"],
                request_id=request_id,
                error_code=str(exc).strip() or "POLICY_LLM_BATCH_INVALID",
                message="LLM batch policy missing or invalid.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        allowed_providers = (
            batch_policy.get("allowed_providers") if isinstance(batch_policy.get("allowed_providers"), list) else []
        )
        if "openai" not in [str(x) for x in allowed_providers]:
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=["PROGRAM_LED=true", "no_secrets=true", "llm_batch=true"],
                request_id=request_id,
                error_code="PROVIDER_NOT_ALLOWED",
                message="Provider not allowed by batch policy.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        # Fail-closed: no network unless enabled and dry_run=false.
        if not dry_run and not _llm_batch_enabled(batch_policy=batch_policy, workspace_root=workspace_root, env_mode=env_mode):
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model, "dry_run": False},
                notes=["PROGRAM_LED=true", "no_secrets=true", "llm_batch=true"],
                request_id=request_id,
                error_code="BATCH_DISABLED",
                message="LLM batch disabled (env gate).",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if not dry_run and "__REPLACE__" in str(base_url):
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=["PROGRAM_LED=true", "no_secrets=true", "llm_batch=true"],
                request_id=request_id,
                error_code="PROVIDER_CONFIG_MISSING",
                message="Provider base_url placeholder must be replaced for batch calls.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        timeout_ms = batch_policy.get("timeout_ms")
        timeout_ms_value = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 else 60000
        timeout_seconds_batch = max(0.1, timeout_ms_value / 1000.0)
        timeout_seconds_batch = min(float(timeout_value), float(timeout_seconds_batch))

        max_response_bytes = guard.get("max_response_bytes", 131072)
        max_response_bytes_value = (
            int(max_response_bytes) if isinstance(max_response_bytes, int) and max_response_bytes > 0 else 131072
        )

        openai_root = _openai_api_root(base_url)
        notes = ["PROGRAM_LED=true", "no_secrets=true", "llm_batch=true"]

        if action == "llm_batch_submit":
            run_id = str(params.get("run_id") or "latest").strip() or "latest"
            raw_job_types = params.get("job_types") if isinstance(params.get("job_types"), list) else None
            job_types = [str(x) for x in raw_job_types] if raw_job_types else []
            if not job_types:
                job_types = ["run_summary", "taxonomy_suggest", "remediation_pack_suggest", "run_diff_optional"]

            allowed_job_types = (
                batch_policy.get("allowed_job_types") if isinstance(batch_policy.get("allowed_job_types"), list) else []
            )
            allowed_set = {str(x) for x in allowed_job_types if isinstance(x, str) and x.strip()}
            cleaned_job_types = sorted({str(x).strip() for x in job_types if isinstance(x, str) and str(x).strip()})
            if allowed_set and any(jt not in allowed_set for jt in cleaned_job_types):
                return build_response(
                    status="FAIL",
                    payload={"job_types": cleaned_job_types, "allowed_job_types": sorted(allowed_set)},
                    notes=notes,
                    request_id=request_id,
                    error_code="JOB_TYPE_NOT_ALLOWED",
                    message="One or more job_types are not allowed by batch policy.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            snapshot, snap_notes = _build_north_star_batch_snapshot(workspace_root=Path(workspace_root), run_id=run_id)
            notes.extend([f"snapshot_note:{n}" for n in snap_notes])

            completion_window = (
                str(batch_policy.get("completion_window") or "24h").strip()
                if isinstance(batch_policy.get("completion_window"), str)
                else "24h"
            )
            max_output_chars = batch_policy.get("max_output_chars")
            max_output_chars_value = (
                int(max_output_chars) if isinstance(max_output_chars, int) and max_output_chars >= 0 else 8000
            )

            def _mk_req(custom_id: str, purpose: str, payload_obj: dict[str, Any], max_tokens_hint: int) -> dict[str, Any]:
                system_prompt = (
                    "Sen bir operasyon analisti asistanısın. Sana verilen JSON snapshot üzerinden çalış.\n"
                    "Çıktıyı mümkünse geçerli JSON olarak döndür; markdown/etiket ekleme.\n"
                    "Secrets/PII yok varsay; sadece verilen alanları yorumla.\n"
                    f"Amaç: {purpose}"
                )
                return {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(payload_obj, ensure_ascii=False, sort_keys=True)},
                        ],
                        "temperature": 0.2,
                        "max_tokens": max_tokens_hint,
                    },
                }

            reqs: list[dict[str, Any]] = []
            for jt in cleaned_job_types:
                if jt == "run_summary":
                    reqs.append(_mk_req("run_summary", "run özeti + top next actions", {"snapshot": snapshot}, 800))
                elif jt == "taxonomy_suggest":
                    reqs.append(_mk_req("taxonomy_suggest", "topic/domain/taxonomy önerileri", {"snapshot": snapshot}, 900))
                elif jt == "remediation_pack_suggest":
                    reqs.append(_mk_req("remediation_pack_suggest", "remediation pack önerileri (plan-only)", {"snapshot": snapshot}, 900))
                elif jt == "run_diff_optional":
                    prev_snapshot: dict[str, Any] = {}
                    idx_path = Path(workspace_root) / ".cache" / "index" / "assessment_eval_runs_index.v1.json"
                    if idx_path.exists():
                        idx = _load_json_obj(idx_path)
                        runs = idx.get("runs") if isinstance(idx.get("runs"), list) else []
                        for r in runs:
                            if not isinstance(r, dict):
                                continue
                            rid = str(r.get("run_id") or "")
                            if rid and rid != run_id:
                                prev_snapshot, _ = _build_north_star_batch_snapshot(
                                    workspace_root=Path(workspace_root), run_id=rid
                                )
                                break
                    reqs.append(_mk_req("run_diff_optional", "run diff özeti", {"current": snapshot, "previous": prev_snapshot}, 900))
                elif jt == "historical_trends":
                    idx_path = Path(workspace_root) / ".cache" / "index" / "assessment_eval_runs_index.v1.json"
                    max_runs = batch_policy.get("max_runs_for_trends")
                    max_runs_value = int(max_runs) if isinstance(max_runs, int) and max_runs > 0 else 20
                    history: list[dict[str, Any]] = []
                    if idx_path.exists():
                        idx = _load_json_obj(idx_path)
                        runs = idx.get("runs") if isinstance(idx.get("runs"), list) else []
                        for r in runs[:max_runs_value]:
                            if not isinstance(r, dict):
                                continue
                            rid = str(r.get("run_id") or "")
                            if not rid:
                                continue
                            snap, _ = _build_north_star_batch_snapshot(workspace_root=Path(workspace_root), run_id=rid)
                            history.append(snap)
                    reqs.append(_mk_req("historical_trends", "son N run trend analizi", {"runs": history}, 1200))

            input_bytes = ("\n".join([json.dumps(r, ensure_ascii=False, sort_keys=True) for r in reqs]) + "\n").encode("utf-8")
            input_sha = _sha256_hex(input_bytes)
            job_key = json.dumps(
                {"run_id": run_id, "provider_id": provider_id, "model": model, "job_types": cleaned_job_types, "input_sha256": input_sha},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            job_id = "BATCH-" + hashlib.sha256(job_key).hexdigest()[:12]

            if dry_run:
                return build_response(
                    status="OK",
                    payload={
                        "provider_id": provider_id,
                        "model": model,
                        "dry_run": True,
                        "job_id": job_id,
                        "run_id": run_id,
                        "job_types": cleaned_job_types,
                        "request_count": len(reqs),
                        "completion_window": completion_window,
                        "input_sha256": input_sha,
                        "max_output_chars": max_output_chars_value,
                    },
                    notes=notes + ["dry_run=true"],
                    request_id=request_id,
                    error_code=None,
                    message="LLM batch submit preview generated.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            if not key_used:
                return build_response(
                    status="FAIL",
                    payload={"provider_id": provider_id, "model": model},
                    notes=notes,
                    request_id=request_id,
                    error_code="API_KEY_MISSING",
                    message="API key missing.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
            api_key_present_value, api_key_value = resolve_env_value(str(key_used), str(workspace_root), env_mode=env_mode)
            if not api_key_present_value or not api_key_value:
                return build_response(
                    status="FAIL",
                    payload={"provider_id": provider_id, "model": model, "api_key_present": False},
                    notes=notes,
                    request_id=request_id,
                    error_code="API_KEY_MISSING",
                    message="API key missing.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            body, boundary = _multipart_form_data(
                fields=[("purpose", "batch")],
                files=[("file", f"{job_id}.jsonl", input_bytes, "application/jsonl")],
            )
            status_u, http_u, resp_u, err_u, err_detail_u = _http_request(
                method="POST",
                url=f"{openai_root}/files",
                headers={
                    "Authorization": f"Bearer {api_key_value}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                body=body,
                timeout_seconds=timeout_seconds_batch,
                max_response_bytes=max_response_bytes_value,
            )
            file_obj, parse_u = _json_or_error(resp_u)
            file_id = str(file_obj.get("id") or "")
            if status_u != "OK" or not file_id or parse_u:
                return build_response(
                    status="FAIL",
                    payload={"http_status": http_u, "error_detail": err_detail_u, "response_sha256": _sha256_hex(resp_u)},
                    notes=notes,
                    request_id=request_id,
                    error_code=err_u or "BATCH_SUBMIT_FAILED",
                    message="OpenAI batch file upload failed.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            batch_req = {
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": completion_window or "24h",
                "metadata": {"job_id": job_id, "run_id": run_id},
            }
            status_b, http_b, resp_b, err_b, err_detail_b = _http_request(
                method="POST",
                url=f"{openai_root}/batches",
                headers={"Authorization": f"Bearer {api_key_value}", "Content-Type": "application/json"},
                body=json.dumps(batch_req, ensure_ascii=False).encode("utf-8"),
                timeout_seconds=timeout_seconds_batch,
                max_response_bytes=max_response_bytes_value,
            )
            batch_obj, parse_b = _json_or_error(resp_b)
            batch_remote_id = str(batch_obj.get("id") or "")
            remote_status = str(batch_obj.get("status") or "")
            if status_b != "OK" or not batch_remote_id or parse_b:
                return build_response(
                    status="FAIL",
                    payload={"http_status": http_b, "error_detail": err_detail_b, "response_sha256": _sha256_hex(resp_b)},
                    notes=notes,
                    request_id=request_id,
                    error_code=err_b or "BATCH_SUBMIT_FAILED",
                    message="OpenAI batch create failed.",
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )

            ws_root = Path(workspace_root).resolve()
            index_obj = _load_llm_batch_job_index(ws_root)
            job_rec = {
                "job_id": job_id,
                "run_id": run_id,
                "provider_id": provider_id,
                "model": model,
                "status": "RUNNING" if remote_status else "PENDING",
                "created_at": _now_iso(),
                "batch_remote_id": batch_remote_id,
                "input_file_id": file_id,
                "job_types": cleaned_job_types,
                "input_sha256": input_sha,
                "result_path": "",
                "error": "",
                "nondeterministic": True,
            }
            _upsert_job(index_obj, job_rec)
            index_path = _write_llm_batch_job_index(ws_root, index_obj)
            return build_response(
                status="OK",
                payload={
                    "evidence": [str(index_path.relative_to(ws_root).as_posix())],
                    "provider_id": provider_id,
                    "model": model,
                    "dry_run": False,
                    "job_id": job_id,
                    "run_id": run_id,
                    "batch_remote_id": batch_remote_id,
                    "batch_status": remote_status,
                    "job_index_path": str(index_path.relative_to(ws_root).as_posix()),
                },
                notes=notes,
                request_id=request_id,
                error_code=None,
                message="OpenAI batch submitted.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        # action == llm_batch_poll
        job_id = str(params.get("job_id") or "").strip()
        if not job_id:
            return build_response(
                status="FAIL",
                payload=None,
                notes=notes,
                request_id=request_id,
                error_code="JOB_ID_REQUIRED",
                message="job_id is required.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        ws_root = Path(workspace_root).resolve()
        index_obj = _load_llm_batch_job_index(ws_root)
        jobs = index_obj.get("jobs") if isinstance(index_obj.get("jobs"), list) else []
        job = next((j for j in jobs if isinstance(j, dict) and str(j.get("job_id") or "") == job_id), None)
        if job is None:
            return build_response(
                status="FAIL",
                payload={"job_id": job_id},
                notes=notes,
                request_id=request_id,
                error_code="JOB_NOT_FOUND",
                message="Batch job not found.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        terminal = str(job.get("status") or "").upper() in {"DONE", "FAILED", "SKIPPED", "DISABLED"}
        if dry_run or terminal:
            payload = dict(job)
            payload["dry_run"] = bool(dry_run)
            return build_response(
                status="OK",
                payload=payload,
                notes=notes + (["dry_run=true"] if dry_run else []),
                request_id=request_id,
                error_code=None,
                message="Batch job status.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        batch_remote_id = str(job.get("batch_remote_id") or "").strip()
        if not batch_remote_id:
            return build_response(
                status="FAIL",
                payload={"job_id": job_id},
                notes=notes,
                request_id=request_id,
                error_code="BATCH_REMOTE_ID_MISSING",
                message="batch_remote_id missing.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        if not key_used:
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model},
                notes=notes,
                request_id=request_id,
                error_code="API_KEY_MISSING",
                message="API key missing.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )
        api_key_present_value, api_key_value = resolve_env_value(str(key_used), str(workspace_root), env_mode=env_mode)
        if not api_key_present_value or not api_key_value:
            return build_response(
                status="FAIL",
                payload={"provider_id": provider_id, "model": model, "api_key_present": False},
                notes=notes,
                request_id=request_id,
                error_code="API_KEY_MISSING",
                message="API key missing.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        status_p, http_p, resp_p, err_p, err_detail_p = _http_request(
            method="GET",
            url=f"{openai_root}/batches/{batch_remote_id}",
            headers={"Authorization": f"Bearer {api_key_value}"},
            body=None,
            timeout_seconds=timeout_seconds_batch,
            max_response_bytes=max_response_bytes_value,
        )
        batch_obj, parse_p = _json_or_error(resp_p)
        remote_status = str(batch_obj.get("status") or "").strip()
        output_file_id = str(batch_obj.get("output_file_id") or "").strip()
        error_file_id = str(batch_obj.get("error_file_id") or "").strip()
        if status_p != "OK" or parse_p:
            job["status"] = "FAILED"
            job["error"] = err_detail_p or (remote_status or "poll_failed")
            _upsert_job(index_obj, job)
            _write_llm_batch_job_index(ws_root, index_obj)
            return build_response(
                status="FAIL",
                payload={"job_id": job_id, "http_status": http_p, "error_detail": err_detail_p, "response_sha256": _sha256_hex(resp_p)},
                notes=notes,
                request_id=request_id,
                error_code=err_p or "BATCH_POLL_FAILED",
                message="OpenAI batch poll failed.",
                auth_checked=auth_checked,
                rate_limited=rate_limited,
            )

        mapped = "RUNNING"
        if remote_status in {"completed", "completed_with_errors"}:
            mapped = "DONE"
        elif remote_status in {"failed", "expired", "cancelled"}:
            mapped = "FAILED"

        result_rel = str(job.get("result_path") or "").strip()
        if mapped == "DONE" and output_file_id and not result_rel:
            status_o, http_o, out_bytes, err_o, err_detail_o = _http_request(
                method="GET",
                url=f"{openai_root}/files/{output_file_id}/content",
                headers={"Authorization": f"Bearer {api_key_value}"},
                body=None,
                timeout_seconds=timeout_seconds_batch,
                max_response_bytes=max(max_response_bytes_value, 262144),
            )
            if status_o != "OK":
                mapped = "FAILED"
                job["error"] = err_detail_o or "output_download_failed"
            else:
                max_output_chars = batch_policy.get("max_output_chars")
                max_output_chars_value = (
                    int(max_output_chars) if isinstance(max_output_chars, int) and max_output_chars >= 0 else 8000
                )
                items: dict[str, Any] = {}
                for line in out_bytes.decode("utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    cid = str(rec.get("custom_id") or "").strip() or "unknown"
                    resp = rec.get("response") if isinstance(rec.get("response"), dict) else {}
                    status_code = int(resp.get("status_code", 0) or 0) if isinstance(resp, dict) else 0
                    body_obj = resp.get("body")
                    body_bytes = json.dumps(body_obj, ensure_ascii=False).encode("utf-8") if body_obj is not None else b""
                    output_text = _extract_llm_output_text(body_bytes) if body_bytes else ""
                    preview = output_text
                    truncated = False
                    if max_output_chars_value > 0 and len(preview) > max_output_chars_value:
                        preview = preview[:max_output_chars_value]
                        truncated = True
                    items[cid] = {
                        "status_code": status_code,
                        "output_preview": preview,
                        "output_truncated": truncated,
                        "output_sha256": _sha256_hex(body_bytes),
                    }

                run_id = str(job.get("run_id") or "latest")
                out_path = ws_root / ".cache" / "reports" / "llm_batch" / run_id / "batch_insights.v0.1.json"
                out_obj = {
                    "version": "v0.1",
                    "generated_at": _now_iso(),
                    "run_id": run_id,
                    "job_id": job_id,
                    "provider_id": provider_id,
                    "model": model,
                    "batch_remote_id": batch_remote_id,
                    "batch_status": remote_status,
                    "output_file_id": output_file_id,
                    "error_file_id": error_file_id,
                    "items": items,
                    "nondeterministic": True,
                    "notes": ["PROGRAM_LED=true", "no_secrets=true"],
                }
                _atomic_write_json(out_path, out_obj)
                result_rel = str(out_path.relative_to(ws_root).as_posix())
                job["result_path"] = result_rel

        job["status"] = mapped
        if mapped == "FAILED" and error_file_id and not str(job.get("error") or "").strip():
            job["error"] = f"error_file_id={error_file_id}"

        _upsert_job(index_obj, job)
        index_path = _write_llm_batch_job_index(ws_root, index_obj)
        payload = {"job_id": job_id, "status": mapped, "batch_status": remote_status, "result_path": result_rel}
        return build_response(
            status="OK" if mapped in {"DONE", "RUNNING"} else "FAIL",
            payload={
                **payload,
                "evidence": [
                    str(index_path.relative_to(ws_root).as_posix()),
                    *( [result_rel] if result_rel else [] ),
                ],
            },
            notes=notes,
            request_id=request_id,
            error_code=None if mapped in {"DONE", "RUNNING"} else "BATCH_FAILED",
            message="Batch job polled.",
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

        if provider_id == "claude":
            system, anthropic_messages = _to_anthropic_messages(messages)
            req_body = {
                "model": model,
                "messages": anthropic_messages,
                # Anthropic Messages API requires max_tokens.
                "max_tokens": int(max_tokens) if isinstance(max_tokens, int) and max_tokens > 0 else 256,
            }
            if system:
                req_body["system"] = system
            if temperature is not None:
                req_body["temperature"] = temperature
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key_value,
                "anthropic-version": "2023-06-01",
            }
        else:
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
            if req_id and provider_id not in {"google", "openai", "qwen", "xai", "claude"}:
                req_body["request_id"] = req_id

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key_value}",
            }
        if provider_id == "xai":
            # xAI is fronted by Cloudflare and may block requests without a
            # browser-like User-Agent (error 1010 / 403).
            headers["Accept"] = "application/json"
            headers["User-Agent"] = _XAI_USER_AGENT
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
