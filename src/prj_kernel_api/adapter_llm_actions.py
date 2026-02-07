"""PRJ-KERNEL-API: LLM provider actions extracted from adapter.py (script-budget refactor-only)."""

from __future__ import annotations

import hashlib
import json
import os
import re
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


def _sanitize_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text).strip("_.")[:120] or "item"


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
            if isinstance(msg, dict):
                content_val = msg.get("content")
                if isinstance(content_val, str):
                    return content_val.strip()
                if isinstance(content_val, list) and content_val:
                    parts = []
                    for block in content_val:
                        if not isinstance(block, dict):
                            continue
                        text = block.get("text")
                        if isinstance(text, str) and text.strip():
                            parts.append(text)
                    if parts:
                        return "\n".join(parts).strip()
            if isinstance(first.get("text"), str):
                return first.get("text", "").strip()

    output = obj.get("output")
    if isinstance(output, list) and output:
        texts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)
        if texts:
            return "\n".join(texts).strip()

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


def maybe_handle_llm_actions(*, action: str, params: Dict[str, Any], workspace_root: str, repo_root: Path, env_mode: str, request_id: str, auth_checked: bool, rate_limited: bool, policy: Dict[str, Any], build_response: BuildResponseFn) -> Dict[str, Any] | None:
    from src.prj_kernel_api.adapter_llm_actions_runtime import maybe_handle_llm_actions as _impl

    return _impl(
        action=action,
        params=params,
        workspace_root=workspace_root,
        repo_root=repo_root,
        env_mode=env_mode,
        request_id=request_id,
        auth_checked=auth_checked,
        rate_limited=rate_limited,
        policy=policy,
        build_response=build_response,
    )
