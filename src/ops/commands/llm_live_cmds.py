from __future__ import annotations
import argparse
import hashlib
import json
import os
import socket
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse
from src.ops.commands.common import repo_root
from src.prj_kernel_api.dotenv_loader import load_env_presence, resolve_env_presence, resolve_env_value
from src.prj_kernel_api.provider_guardrails import load_guardrails, model_allowed, provider_settings
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry


def _write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json_maybe(path: Path) -> Tuple[Dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "MISSING"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, "INVALID_JSON"
    if not isinstance(obj, dict):
        return None, "INVALID_TYPE"
    return obj, None


def _effective_policy_path(ws_root: Path, repo_root_path: Path, relpath: str) -> Path:
    ws_path = ws_root / relpath
    if ws_path.exists():
        return ws_path
    return repo_root_path / relpath


@dataclass(frozen=True)
class ProviderReadiness:
    provider_id: str
    enabled: bool
    base_url_present: bool
    base_url_placeholder: bool
    default_model: str | None
    model_allowed: bool
    expected_env_keys: List[str]
    api_key_present: bool
    api_key_found_in: str


def _provider_readiness(
    *,
    provider_id: str,
    provider_obj: Dict[str, Any],
    guardrails: Dict[str, Any],
    workspace_root: str,
    env_mode: str,
) -> ProviderReadiness:
    guard = provider_settings(guardrails, provider_id)
    enabled = bool(provider_obj.get("enabled", False)) and bool(guard.get("enabled", False))
    base_url = provider_obj.get("base_url") if isinstance(provider_obj.get("base_url"), str) else ""
    base_url_present = bool(base_url)
    base_url_placeholder = "__REPLACE__" in base_url
    default_model = guard.get("default_model")
    if not isinstance(default_model, str):
        default_model = provider_obj.get("default_model") if isinstance(provider_obj.get("default_model"), str) else None
    allow_models = guard.get("allow_models", ["*"])
    model_ok = isinstance(default_model, str) and model_allowed(default_model, allow_models)

    expected_env_keys = guard.get("expected_env_keys", [])
    if not isinstance(expected_env_keys, list):
        expected_env_keys = []
    expected_env_keys = [str(x) for x in expected_env_keys if isinstance(x, str) and x]
    api_key_env = provider_obj.get("api_key_env") if isinstance(provider_obj.get("api_key_env"), str) else ""
    if not expected_env_keys and api_key_env:
        expected_env_keys = [api_key_env]

    api_key_present = False
    found_in = "none"
    for key_name in expected_env_keys:
        api_key_present, found_in = resolve_env_presence(key_name, workspace_root, env_mode=env_mode)
        if api_key_present:
            break

    return ProviderReadiness(
        provider_id=provider_id,
        enabled=enabled,
        base_url_present=base_url_present,
        base_url_placeholder=base_url_placeholder,
        default_model=default_model if isinstance(default_model, str) else None,
        model_allowed=bool(model_ok),
        expected_env_keys=expected_env_keys,
        api_key_present=bool(api_key_present),
        api_key_found_in=str(found_in or "none"),
    )


def _resolve_tls_verify_paths() -> Dict[str, Any]:
    # Mirror adapter TLS behavior: prefer explicit env overrides, then fall back
    # to known system CA bundle locations. Do NOT disable verification.
    default_cafile: str | None = None
    default_capath: str | None = None
    default_cafile_exists = False
    default_capath_exists = False
    try:
        paths = ssl.get_default_verify_paths()
        default_cafile = paths.cafile if isinstance(paths.cafile, str) and paths.cafile else None
        default_capath = paths.capath if isinstance(paths.capath, str) and paths.capath else None
        if default_cafile:
            default_cafile_exists = Path(default_cafile).exists()
        if default_capath:
            default_capath_exists = Path(default_capath).exists()
    except Exception:
        pass

    env_candidates = [
        os.environ.get("SSL_CERT_FILE"),
        os.environ.get("REQUESTS_CA_BUNDLE"),
        os.environ.get("CURL_CA_BUNDLE"),
    ]
    env_cafile: str | None = None
    env_cafile_exists = False
    for cand in env_candidates:
        if isinstance(cand, str) and cand.strip():
            p = Path(cand)
            if p.exists():
                env_cafile = str(p)
                env_cafile_exists = True
                break

    system_candidates = [
        "/etc/ssl/cert.pem",  # macOS (and some linux distros)
        "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
        "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
    ]
    system_cafile: str | None = None
    system_cafile_exists = False
    for cand in system_candidates:
        p = Path(cand)
        if p.exists():
            system_cafile = str(p)
            system_cafile_exists = True
            break

    chosen_cafile: str | None = None
    chosen_source = "none"
    if env_cafile_exists and env_cafile:
        chosen_cafile = env_cafile
        chosen_source = "env"
    elif default_cafile_exists and default_cafile:
        chosen_cafile = default_cafile
        chosen_source = "ssl_default"
    elif system_cafile_exists and system_cafile:
        chosen_cafile = system_cafile
        chosen_source = "system"

    return {
        "cafile": chosen_cafile,
        "cafile_exists": bool(chosen_cafile and Path(chosen_cafile).exists()),
        "cafile_source": chosen_source,
        "capath": default_capath,
        "capath_exists": bool(default_capath_exists),
        "ssl_default": {
            "cafile": default_cafile,
            "cafile_exists": bool(default_cafile_exists),
            "capath": default_capath,
            "capath_exists": bool(default_capath_exists),
        },
    }


def _build_tls_context(*, cafile: str | None) -> ssl.SSLContext | None:
    try:
        if cafile and Path(cafile).exists():
            ctx = ssl.create_default_context(cafile=cafile)
        else:
            ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx
    except Exception:
        return None


def _bucket_elapsed_ms(elapsed_ms: float) -> int:
    return int(round(elapsed_ms / 10.0) * 10)


def _extract_host_port_from_url(url: str) -> tuple[str | None, int | None, str | None]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None, None, "URL_PARSE_FAILED"
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"https", "http"}:
        return None, None, "UNSUPPORTED_URL_SCHEME"
    host = parsed.hostname
    if not host:
        return None, None, "URL_HOST_MISSING"
    port = parsed.port or (443 if scheme == "https" else 80)
    return str(host), int(port), None


def _tls_handshake(
    *,
    host: str,
    port: int,
    timeout_seconds: float,
    ctx: ssl.SSLContext,
) -> Dict[str, Any]:
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
            if port == 443:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    ssock.do_handshake()
            else:
                # Non-443 handshake is still supported (some providers may expose alt ports),
                # but requires SNI as well.
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    ssock.do_handshake()
        ok = True
        error_type = None
        error_detail = None
    except Exception as exc:
        ok = False
        error_type = exc.__class__.__name__
        error_detail = str(exc)[:220]
    elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
    return {
        "status": "OK" if ok else "FAIL",
        "elapsed_ms": elapsed_ms,
        "error_type": error_type,
        "error_detail": error_detail,
    }


def _build_llm_live_readiness_payload(
    *,
    ws_root: Path,
    env_mode: str,
    out_path: Path,
    tls_preflight_mode: str = "auto",
    tls_timeout_seconds: float = 2.5,
) -> tuple[dict[str, Any], bool]:
    start = time.time()
    root = repo_root()

    # Policies (workspace override wins)
    kernel_policy_path = _effective_policy_path(ws_root, root, "policies/policy_kernel_api_guardrails.v1.json")
    llm_live_policy_path = _effective_policy_path(ws_root, root, "policies/policy_llm_live.v1.json")
    providers_guardrails_path = _effective_policy_path(ws_root, root, "policies/policy_llm_providers_guardrails.v1.json")

    kernel_policy, kernel_err = _read_json_maybe(kernel_policy_path)
    llm_live_policy, llm_live_err = _read_json_maybe(llm_live_policy_path)
    providers_guardrails, providers_err = _read_json_maybe(providers_guardrails_path)

    # Env presence (no secrets)
    expected_env_keys = [
        "KERNEL_API_TOKEN",
        "KERNEL_API_LLM_LIVE",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "XAI_API_KEY",
    ]
    presence = load_env_presence(str(ws_root), expected_keys=expected_env_keys, repo_root=root, env_mode=env_mode)
    present_keys = sorted([str(k) for k in (presence.get("present_keys") or [])])
    missing_keys = sorted([str(k) for k in (presence.get("missing_expected_keys") or [])])
    source_used = str(presence.get("source_used") or "none")
    parse_errors = sorted([str(x) for x in (presence.get("parse_errors") or [])])

    # Derived gates (fail-closed).
    kernel_actions = kernel_policy.get("actions") if isinstance(kernel_policy, dict) else {}
    kernel_allowlist = kernel_actions.get("allowlist") if isinstance(kernel_actions, dict) else []
    kernel_allowlist = [str(x) for x in kernel_allowlist] if isinstance(kernel_allowlist, list) else []
    kernel_llm_live_allowed = bool(kernel_actions.get("llm_call_live_allowed", False)) if isinstance(kernel_actions, dict) else False

    # Explicit env flag value, but never log the value; only status and source.
    live_flag_key = "KERNEL_API_LLM_LIVE"
    live_flag_present, live_flag_value = resolve_env_value(live_flag_key, str(ws_root), repo_root=root, env_mode=env_mode)
    live_flag_on = bool(live_flag_present and isinstance(live_flag_value, str) and live_flag_value.strip() == "1")

    token_present, token_source = resolve_env_presence("KERNEL_API_TOKEN", str(ws_root), repo_root=root, env_mode=env_mode)

    llm_live_enabled = bool(llm_live_policy.get("live_enabled", False)) if isinstance(llm_live_policy, dict) else False
    allowed_providers = llm_live_policy.get("allowed_providers") if isinstance(llm_live_policy, dict) else []
    allowed_providers = [str(x) for x in allowed_providers] if isinstance(allowed_providers, list) else []
    allowed_providers = sorted([p for p in allowed_providers if p])

    # Providers registry + guardrails (read-only; ensures baseline registry exists if missing)
    provider_registry_paths = ensure_providers_registry(str(ws_root))
    registry_obj = read_registry(Path(provider_registry_paths["providers_path"]))
    provider_policy = read_policy(Path(provider_registry_paths["policy_path"]))
    provider_allow = provider_policy.get("allow_providers") if isinstance(provider_policy, dict) else []
    provider_allow = [str(x) for x in provider_allow] if isinstance(provider_allow, list) else []
    guardrails = load_guardrails(str(ws_root))
    providers = registry_obj.get("providers") if isinstance(registry_obj.get("providers"), list) else []
    providers_by_id: Dict[str, Dict[str, Any]] = {
        str(p.get("id")): p for p in providers if isinstance(p, dict) and isinstance(p.get("id"), str)
    }

    readiness_items: List[Dict[str, Any]] = []
    ready_providers: List[str] = []
    for provider_id_input in allowed_providers:
        provider_id = _canonical_provider_id(provider_id_input)
        p_obj = providers_by_id.get(provider_id) or {}
        pr = _provider_readiness(
            provider_id=provider_id,
            provider_obj=p_obj,
            guardrails=guardrails,
            workspace_root=str(ws_root),
            env_mode=env_mode,
        )
        provider_ready = (
            pr.enabled
            and pr.base_url_present
            and not pr.base_url_placeholder
            and pr.default_model is not None
            and pr.model_allowed
            and pr.api_key_present
            and _provider_allowed_by_policy(provider_id, provider_allow)
        )
        if provider_ready:
            ready_providers.append(provider_id)
        readiness_items.append(
            {
                "provider_id_input": str(provider_id_input),
                "provider_id": pr.provider_id,
                "provider_id_canonicalized": bool(str(provider_id_input).strip().lower() != provider_id),
                "enabled": pr.enabled,
                "base_url_present": pr.base_url_present,
                "base_url_placeholder": pr.base_url_placeholder,
                "default_model": pr.default_model,
                "model_allowed": pr.model_allowed,
                "expected_env_keys": pr.expected_env_keys,
                "api_key_present": pr.api_key_present,
                "api_key_found_in": pr.api_key_found_in,
                "provider_policy_allowed": _provider_allowed_by_policy(provider_id, provider_allow),
                "provider_ready": provider_ready,
            }
        )

    # Optional TLS preflight (CA presence + handshake; still no API calls).
    tls_mode_raw = str(tls_preflight_mode or "auto").strip().lower()
    if tls_mode_raw not in {"auto", "off", "on"}:
        tls_mode_raw = "auto"
    tls_attempt = False
    if tls_mode_raw == "on":
        tls_attempt = True
    elif tls_mode_raw == "off":
        tls_attempt = False
    else:
        # auto: only when the explicit live flag is ON (user opted into network).
        tls_attempt = bool(live_flag_on)

    tls_verify_paths = _resolve_tls_verify_paths()
    tls_ctx = _build_tls_context(cafile=tls_verify_paths.get("cafile") if tls_verify_paths.get("cafile_exists") else None)
    tls_provider_rows: List[Dict[str, Any]] = []
    tls_ok_providers: List[str] = []
    tls_elapsed_ms = 0
    if tls_attempt:
        tls_start = time.monotonic()
        # Deterministic: sort by canonical provider id.
        unique_provider_ids = sorted({_canonical_provider_id(p) for p in allowed_providers})
        for pid in unique_provider_ids:
            p_obj = providers_by_id.get(pid) or {}
            base_url = p_obj.get("base_url") if isinstance(p_obj.get("base_url"), str) else ""
            row: Dict[str, Any] = {
                "provider_id": pid,
                "base_url_present": bool(base_url),
                "base_url_placeholder": "__REPLACE__" in base_url if base_url else False,
                "host": None,
                "port": None,
                "status": "SKIPPED",
                "error_code": None,
                "elapsed_ms": None,
                "error_type": None,
                "error_detail": None,
            }
            if not base_url:
                row["error_code"] = "PROVIDER_BASE_URL_MISSING"
                tls_provider_rows.append(row)
                continue
            if "__REPLACE__" in base_url:
                row["error_code"] = "PROVIDER_BASE_URL_PLACEHOLDER"
                tls_provider_rows.append(row)
                continue
            host, port, parse_err = _extract_host_port_from_url(base_url)
            if parse_err:
                row["error_code"] = str(parse_err)
                tls_provider_rows.append(row)
                continue
            row["host"] = host
            row["port"] = port
            if tls_ctx is None:
                row["error_code"] = "TLS_CONTEXT_BUILD_FAILED"
                row["status"] = "FAIL"
                tls_provider_rows.append(row)
                continue

            hs = _tls_handshake(host=str(host), port=int(port or 443), timeout_seconds=float(tls_timeout_seconds), ctx=tls_ctx)
            row["status"] = hs.get("status")
            row["elapsed_ms"] = hs.get("elapsed_ms")
            row["error_type"] = hs.get("error_type")
            row["error_detail"] = hs.get("error_detail")
            if row["status"] == "OK":
                tls_ok_providers.append(pid)
            else:
                row["error_code"] = "TLS_HANDSHAKE_FAILED"
            tls_provider_rows.append(row)

        tls_elapsed_ms = _bucket_elapsed_ms((time.monotonic() - tls_start) * 1000.0)

    ready_providers_effective = ready_providers
    if tls_attempt:
        ready_providers_effective = sorted([p for p in ready_providers if p in set(tls_ok_providers)])

    # Effective readiness (no provider API calls; TLS handshake optional).
    live_ready = (
        bool(token_present)
        and "llm_call_live" in set(kernel_allowlist)
        and kernel_llm_live_allowed
        and llm_live_enabled
        and live_flag_on
        and len(ready_providers_effective) > 0
    )

    status = "OK" if live_ready else "WARN"
    reasons: List[str] = []
    if not token_present:
        reasons.append("KERNEL_API_TOKEN_MISSING")
    if "llm_call_live" not in set(kernel_allowlist):
        reasons.append("KERNEL_API_ACTION_NOT_ALLOWLISTED_llm_call_live")
    if not kernel_llm_live_allowed:
        reasons.append("KERNEL_API_LLM_CALL_LIVE_DISABLED_BY_POLICY")
    if not llm_live_enabled:
        reasons.append("POLICY_LLM_LIVE_DISABLED")
    if not live_flag_on:
        reasons.append("KERNEL_API_LLM_LIVE_FLAG_NOT_ON")
    if not ready_providers_effective:
        reasons.append("NO_PROVIDER_READY")
    if tls_attempt and not tls_ok_providers:
        reasons.append("TLS_PREFLIGHT_NO_PROVIDER_OK")
    if tls_attempt and tls_ctx is None:
        reasons.append("TLS_CONTEXT_BUILD_FAILED")

    payload = {
        "version": "v1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_root": str(ws_root),
        "env_mode": env_mode,
        "status": status,
        "ready": bool(live_ready),
        "ready_providers": sorted(ready_providers_effective),
        "ready_providers_logical": sorted(ready_providers),
        "reasons": sorted(reasons),
        "inputs": {
            "kernel_api_guardrails_policy_path": str(kernel_policy_path),
            "llm_live_policy_path": str(llm_live_policy_path),
            "llm_providers_guardrails_path": str(providers_guardrails_path),
            "providers_registry_path": str(provider_registry_paths["providers_path"]),
            "providers_policy_path": str(provider_registry_paths["policy_path"]),
        },
        "policy_parse": {
            "kernel_api_guardrails": None if kernel_err is None else kernel_err,
            "llm_live": None if llm_live_err is None else llm_live_err,
            "llm_providers_guardrails": None if providers_err is None else providers_err,
        },
        "env_presence": {
            "source_used": source_used,
            "parse_errors": parse_errors,
            "present_keys": present_keys,
            "missing_expected_keys": missing_keys,
        },
        "gates": {
            "kernel_api_llm_call_live_allowed": bool(kernel_llm_live_allowed),
            "kernel_api_allowlist_has_llm_call_live": bool("llm_call_live" in set(kernel_allowlist)),
            "policy_llm_live_enabled": bool(llm_live_enabled),
            "env_live_flag_present": bool(live_flag_present),
            "env_live_flag_on": bool(live_flag_on),
            "kernel_api_token_present": bool(token_present),
            "kernel_api_token_source": str(token_source),
        },
        "allowed_providers": allowed_providers,
        "providers": readiness_items,
        "tls_verify_preflight": {
            "mode": tls_mode_raw,
            "attempted": bool(tls_attempt),
            "timeout_seconds": float(tls_timeout_seconds),
            "verify_paths": tls_verify_paths,
            "tls_context_built": bool(tls_ctx is not None),
            "providers": tls_provider_rows,
            "ok_providers": sorted(set(tls_ok_providers)),
            "elapsed_ms": int(tls_elapsed_ms),
        },
        "elapsed_ms": int((time.time() - start) * 1000),
        "notes": [
            "PROGRAM_LED=true",
            "NO_NETWORK=false" if tls_attempt else "NO_NETWORK=true",
            "NO_SECRETS=true",
            "readiness_only=true",
        ],
    }

    return payload, bool(live_ready)


def cmd_llm_live_readiness(args: argparse.Namespace) -> int:
    ws_root = Path(str(args.workspace_root)).resolve()

    env_mode = str(getattr(args, "env_mode", "dotenv") or "dotenv").strip().lower()
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    out_path_raw = str(getattr(args, "out", "") or "").strip()
    out_path = (ws_root / ".cache" / "reports" / "llm_live_readiness.v1.json") if not out_path_raw else Path(out_path_raw)

    tls_preflight = str(getattr(args, "tls_preflight", "auto") or "auto")
    tls_timeout = float(getattr(args, "tls_timeout_seconds", 0.0) or 0.0)
    if tls_timeout <= 0:
        tls_timeout = 2.5

    payload, live_ready = _build_llm_live_readiness_payload(
        ws_root=ws_root,
        env_mode=env_mode,
        out_path=out_path,
        tls_preflight_mode=tls_preflight,
        tls_timeout_seconds=tls_timeout,
    )
    _write_json_atomic(out_path, payload)
    print(str(out_path))
    return 0 if live_ready else 2


def _parse_csv_list(value: str) -> List[str]:
    items = []
    for raw in (value or "").split(","):
        v = str(raw).strip()
        if v:
            items.append(v)
    return items


def _canonical_provider_id(provider_id: str) -> str:
    pid = str(provider_id or "").strip().lower()
    if pid == "gemini":
        return "google"
    if pid == "grok":
        return "xai"
    return pid


def _provider_allowed_by_policy(provider_id: str, allowlist: List[str]) -> bool:
    pid = str(provider_id or "").strip().lower()
    allow = [str(x).strip().lower() for x in (allowlist or []) if isinstance(x, str)]
    if pid in allow:
        return True
    if pid == "gemini" and "google" in allow:
        return True
    if pid == "google" and "gemini" in allow:
        return True
    if pid == "grok" and "xai" in allow:
        return True
    if pid == "xai" and "grok" in allow:
        return True
    return False


def _load_allowed_providers_from_policy(ws_root: Path, root: Path) -> List[str]:
    policy_path = _effective_policy_path(ws_root, root, "policies/policy_llm_live.v1.json")
    obj, err = _read_json_maybe(policy_path)
    if err or not isinstance(obj, dict):
        return []
    allowed = obj.get("allowed_providers")
    if not isinstance(allowed, list):
        return []
    return sorted({str(x) for x in allowed if isinstance(x, str) and str(x).strip()})


def _atomic_write_env_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except Exception:
        pass


def _set_env_kv(path: Path, key: str, value: str) -> tuple[bool, str]:
    if not key or "=" in key:
        return False, "KEY_INVALID"
    raw = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    lines = raw.splitlines()
    updated = False
    out_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        s = stripped
        if s.startswith("export "):
            s = s[len("export ") :].lstrip()
        if "=" not in s:
            out_lines.append(line)
            continue
        k, _v = s.split("=", 1)
        if k.strip() == key and not updated:
            out_lines.append(f"{key}={value}")
            updated = True
            continue
        out_lines.append(line)
    if not updated:
        if out_lines and out_lines[-1] != "":
            out_lines.append("")
        out_lines.append(f"{key}={value}")
    content = "\n".join(out_lines).rstrip("\n") + "\n"
    _atomic_write_env_file(path, content)
    return True, "OK"


def cmd_llm_live_set(args: argparse.Namespace) -> int:
    ws_root = Path(str(args.workspace_root)).resolve()
    env_mode = str(getattr(args, "env_mode", "dotenv") or "dotenv").strip().lower()
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    value_raw = str(getattr(args, "value", "") or "").strip()
    if value_raw not in {"0", "1"}:
        enabled = bool(getattr(args, "enabled", False))
        value_raw = "1" if enabled else "0"
    value = value_raw

    out_path_raw = str(getattr(args, "out", "") or "").strip()
    out_path = (ws_root / ".cache" / "reports" / "llm_live_set.v1.json") if not out_path_raw else Path(out_path_raw)

    if env_mode == "process":
        payload = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": "FAIL",
            "changed": False,
            "error_code": "ENV_MODE_PROCESS_NO_WRITE",
            "note": "env_mode=process cannot persist KERNEL_API_LLM_LIVE; use env_mode=dotenv.",
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true"],
        }
        _write_json_atomic(out_path, payload)
        print(str(out_path))
        return 2

    ws_env = ws_root / ".env"
    ok, code = _set_env_kv(ws_env, "KERNEL_API_LLM_LIVE", value)
    payload = {
        "version": "v1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_root": str(ws_root),
        "env_mode": env_mode,
        "status": "OK" if ok else "FAIL",
        "changed": True if ok else False,
        "set": {"KERNEL_API_LLM_LIVE": value},
        "written_path": str(ws_env),
        "result_code": code,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true"],
    }
    _write_json_atomic(out_path, payload)
    print(str(out_path))
    return 0 if ok else 2


def cmd_llm_live_setup(args: argparse.Namespace) -> int:
    ws_root = Path(str(args.workspace_root)).resolve()
    root = repo_root()

    env_mode = str(getattr(args, "env_mode", "dotenv") or "dotenv").strip().lower()
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    out_path_raw = str(getattr(args, "out", "") or "").strip()
    out_path = (ws_root / ".cache" / "reports" / "llm_live_setup.v1.json") if not out_path_raw else Path(out_path_raw)

    # 1) Ensure token (dotenv mode only). Never print token.
    token_present, token_source = resolve_env_presence("KERNEL_API_TOKEN", str(ws_root), repo_root=root, env_mode=env_mode)
    token_changed = False
    token_sha256 = None
    token_written_path = None
    token_error = None

    if not token_present:
        if env_mode == "process":
            token_error = "KERNEL_API_TOKEN_MISSING"
        else:
            import hashlib
            import secrets

            token_value = secrets.token_hex(32)
            token_sha256 = hashlib.sha256(token_value.encode("utf-8")).hexdigest()
            ws_env = ws_root / ".env"
            ok, _code = _set_env_kv(ws_env, "KERNEL_API_TOKEN", token_value)
            if ok:
                token_changed = True
                token_present = True
                token_source = "workspace_env"
                token_written_path = str(ws_env)
            else:
                token_error = "TOKEN_WRITE_FAILED"

    # 2) Write readiness report (no network).
    readiness_path = ws_root / ".cache" / "reports" / "llm_live_readiness.v1.json"
    readiness_payload, live_ready = _build_llm_live_readiness_payload(
        ws_root=ws_root,
        env_mode=env_mode,
        out_path=readiness_path,
        tls_preflight_mode="off",
    )
    _write_json_atomic(readiness_path, readiness_payload)

    status = "OK" if live_ready else "WARN"
    if token_error:
        status = "WARN"

    report = {
        "version": "v1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_root": str(ws_root),
        "env_mode": env_mode,
        "status": status,
        "ready": bool(live_ready),
        "token": {
            "present": bool(token_present),
            "source": str(token_source),
            "changed": bool(token_changed),
            "token_sha256": token_sha256,
            "written_path": token_written_path,
            "error": token_error,
        },
        "outputs": {
            "llm_live_readiness": str(readiness_path),
        },
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true", "setup=true"],
    }
    _write_json_atomic(out_path, report)
    print(str(out_path))
    return 0 if live_ready else 2


def cmd_llm_live_consult(args: argparse.Namespace) -> int:
    ws_root = Path(str(args.workspace_root)).resolve()
    root = repo_root()

    env_mode = str(getattr(args, "env_mode", "dotenv") or "dotenv").strip().lower()
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    prompt = str(getattr(args, "prompt", "") or "").strip()
    prompt_file = str(getattr(args, "prompt_file", "") or "").strip()
    if not prompt and prompt_file:
        p = Path(prompt_file)
        prompt = p.read_text(encoding="utf-8", errors="replace").strip() if p.exists() else ""

    if not prompt:
        raise SystemExit("prompt is required (use --prompt or --prompt-file)")

    provider_csv = str(getattr(args, "providers", "") or "").strip()
    providers = _parse_csv_list(provider_csv) if provider_csv else _load_allowed_providers_from_policy(ws_root, root)
    providers = [p for p in providers if p]
    if not providers:
        raise SystemExit("no providers selected (pass --providers deepseek,google or set policy_llm_live.allowed_providers)")

    out_path_raw = str(getattr(args, "out", "") or "").strip()
    out_path = (ws_root / ".cache" / "reports" / "llm_live_consult.v1.json") if not out_path_raw else Path(out_path_raw)

    # Preflight gates: fail-closed without network if not ready.
    readiness_path = ws_root / ".cache" / "reports" / "llm_live_readiness.v1.json"
    readiness_payload, live_ready = _build_llm_live_readiness_payload(
        ws_root=ws_root, env_mode=env_mode, out_path=readiness_path
    )
    _write_json_atomic(readiness_path, readiness_payload)
    if not live_ready:
        report = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": "FAIL",
            "error_code": "LLM_LIVE_NOT_READY",
            "providers": providers,
            "readiness_path": str(readiness_path),
            "reasons": readiness_payload.get("reasons") if isinstance(readiness_payload, dict) else [],
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true"],
        }
        _write_json_atomic(out_path, report)
        print(str(out_path))
        return 2

    # Resolve auth token through dotenv-aware resolver; never print token.
    token_present, token_value = resolve_env_value("KERNEL_API_TOKEN", str(ws_root), repo_root=root, env_mode=env_mode)
    if not token_present or not token_value:
        report = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": "FAIL",
            "error_code": "KERNEL_API_TOKEN_MISSING",
            "providers": providers,
            "notes": ["PROGRAM_LED=true", "NO_NETWORK_UNKNOWN=true", "no_secrets=true"],
        }
        _write_json_atomic(out_path, report)
        print(str(out_path))
        return 2

    # Execute calls via Kernel API adapter (audited + policy-gated).
    from src.prj_kernel_api.adapter import handle_request
    from src.prj_kernel_api.api_guardrails import load_guardrails_policy, write_audit_log

    results: List[Dict[str, Any]] = []
    overall = "OK"
    kernel_policy = load_guardrails_policy(str(ws_root))
    audit_relpath = (
        kernel_policy.get("audit", {}).get("path")
        if isinstance(kernel_policy.get("audit"), dict)
        else ".cache/reports/kernel_api_audit.v1.jsonl"
    )
    audit_relpath = str(audit_relpath or ".cache/reports/kernel_api_audit.v1.jsonl")
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    for provider_id_input in providers:
        provider_id = _canonical_provider_id(provider_id_input)
        req = {
            "version": "v1",
            "kind": "llm_call_live",
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "params": {
                "auth_token": token_value,
                "provider_id": provider_id,
                "dry_run": False,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": int(getattr(args, "max_tokens", 0) or 0) or None,
                "temperature": float(getattr(args, "temperature", 0.0)) if getattr(args, "temperature", None) is not None else None,
            },
        }
        # prune nulls for determinism
        params = req["params"]
        if params.get("max_tokens") is None:
            params.pop("max_tokens", None)
        if params.get("temperature") is None:
            params.pop("temperature", None)

        resp = handle_request(req)
        status = str(resp.get("status") or "").upper() if isinstance(resp, dict) else "FAIL"
        if status != "OK":
            overall = "WARN"
        try:
            write_audit_log(
                workspace_root=str(ws_root),
                policy=kernel_policy,
                record={
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "kind": "llm_call_live",
                    "env_mode": env_mode,
                    "provider_id_input": str(provider_id_input),
                    "provider_id": str(provider_id),
                    "provider_id_canonicalized": bool(str(provider_id_input).strip().lower() != provider_id),
                    "request_id": resp.get("request_id") if isinstance(resp, dict) else None,
                    "status": status,
                    "error_code": resp.get("error_code") if isinstance(resp, dict) else "UNKNOWN",
                    "prompt_sha256": prompt_sha256,
                    "prompt_chars": len(prompt),
                    "max_tokens": params.get("max_tokens"),
                    "temperature": params.get("temperature"),
                },
            )
        except Exception:
            overall = "WARN"
        results.append(
            {
                "provider_id_input": str(provider_id_input),
                "provider_id": provider_id,
                "provider_id_canonicalized": bool(str(provider_id_input).strip().lower() != provider_id),
                "status": status,
                "error_code": resp.get("error_code") if isinstance(resp, dict) else "UNKNOWN",
                "request_id": resp.get("request_id") if isinstance(resp, dict) else None,
                "message": resp.get("message") if isinstance(resp, dict) else None,
                "payload": resp.get("payload") if isinstance(resp, dict) else None,
            }
        )

    report = {
        "version": "v1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_root": str(ws_root),
        "env_mode": env_mode,
        "status": overall,
        "prompt_sha256": prompt_sha256,
        "providers": results,
        "notes": [
            "PROGRAM_LED=true",
            "llm_live_consult=true",
            "audited=true",
            "no_secrets=true",
        ],
        "evidence_paths": [],
    }
    evidence_paths: List[str] = [
        str((ws_root / audit_relpath).resolve()),
        str((ws_root / ".cache" / "reports" / "llm_live_readiness.v1.json").resolve()),
    ]
    probe_path = (ws_root / ".cache" / "reports" / "llm_live_probe.v1.json").resolve()
    if probe_path.exists():
        evidence_paths.append(str(probe_path))
    report["evidence_paths"] = evidence_paths
    _write_json_atomic(out_path, report)
    print(str(out_path))
    return 0 if overall == "OK" else 2


def cmd_llm_live_probe(args: argparse.Namespace) -> int:
    ws_root = Path(str(args.workspace_root)).resolve()
    root = repo_root()

    env_mode = str(getattr(args, "env_mode", "dotenv") or "dotenv").strip().lower()
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    detail = bool(getattr(args, "detail", False))

    out_path_raw = str(getattr(args, "out", "") or "").strip()
    canonical_path = ws_root / ".cache" / "reports" / "llm_live_probe.v1.json"
    out_path = canonical_path if not out_path_raw else Path(out_path_raw)

    # Resolve auth token through dotenv-aware resolver; never print token.
    token_present, token_value = resolve_env_value("KERNEL_API_TOKEN", str(ws_root), repo_root=root, env_mode=env_mode)
    if not token_present or not token_value:
        report = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": "FAIL",
            "error_code": "KERNEL_API_TOKEN_MISSING",
            "notes": ["PROGRAM_LED=true", "NO_NETWORK_UNKNOWN=true", "no_secrets=true", "llm_live_probe=true"],
        }
        _write_json_atomic(out_path, report)
        print(str(out_path))
        return 2

    from src.prj_kernel_api.adapter import handle_request
    from src.prj_kernel_api.api_guardrails import load_guardrails_policy, write_audit_log

    req = {
        "version": "v1",
        "kind": "llm_live_probe",
        "workspace_root": str(ws_root),
        "env_mode": env_mode,
        "params": {
            "auth_token": token_value,
            "detail": detail,
        },
    }

    resp = handle_request(req)
    status = str(resp.get("status") or "").upper() if isinstance(resp, dict) else "FAIL"
    error_code = resp.get("error_code") if isinstance(resp, dict) else "UNKNOWN"

    probe_report: Dict[str, Any] = {}
    if isinstance(resp, dict) and isinstance(resp.get("payload"), dict):
        pr = resp["payload"].get("probe_report")
        if isinstance(pr, dict):
            probe_report = pr

    # Audit (best-effort; never include secrets).
    try:
        kernel_policy = load_guardrails_policy(str(ws_root))
        audit_relpath = (
            kernel_policy.get("audit", {}).get("path")
            if isinstance(kernel_policy.get("audit"), dict)
            else ".cache/reports/kernel_api_audit.v1.jsonl"
        )
        audit_relpath = str(audit_relpath or ".cache/reports/kernel_api_audit.v1.jsonl")
        write_audit_log(
            workspace_root=str(ws_root),
            policy=kernel_policy,
            record={
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "kind": "llm_live_probe",
                "env_mode": env_mode,
                "detail": detail,
                "request_id": resp.get("request_id") if isinstance(resp, dict) else None,
                "status": status,
                "error_code": error_code,
                "attempted": probe_report.get("attempted") if isinstance(probe_report, dict) else None,
                "ok": probe_report.get("ok") if isinstance(probe_report, dict) else None,
                "fail": probe_report.get("fail") if isinstance(probe_report, dict) else None,
                "skipped": probe_report.get("skipped") if isinstance(probe_report, dict) else None,
                "preview_sha256": probe_report.get("preview_sha256") if isinstance(probe_report, dict) else None,
            },
        )
    except Exception:
        pass

    # The probe writes its canonical report path itself. If a custom --out is requested,
    # copy the canonical report to --out deterministically.
    if out_path.resolve() != canonical_path.resolve() and canonical_path.exists():
        try:
            obj = json.loads(canonical_path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                _write_json_atomic(out_path, obj)
        except Exception:
            pass

    # If the probe didn't write (unexpected), fall back to a minimal wrapper report.
    if not canonical_path.exists():
        wrapper = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": status,
            "error_code": error_code,
            "probe_report": probe_report,
            "notes": ["PROGRAM_LED=true", "no_secrets=true", "llm_live_probe=true"],
        }
        _write_json_atomic(out_path, wrapper)

    print(str(out_path))
    return 0 if status == "OK" else 2


def cmd_kernel_api_token_ensure(args: argparse.Namespace) -> int:
    ws_root = Path(str(args.workspace_root)).resolve()
    root = repo_root()

    env_mode = str(getattr(args, "env_mode", "dotenv") or "dotenv").strip().lower()
    if env_mode not in {"dotenv", "process"}:
        env_mode = "dotenv"

    out_path_raw = str(getattr(args, "out", "") or "").strip()
    out_path = (ws_root / ".cache" / "reports" / "kernel_api_token_ensure.v1.json") if not out_path_raw else Path(out_path_raw)

    # Respect existing token in either workspace .env or repo .env.
    present, source = resolve_env_presence("KERNEL_API_TOKEN", str(ws_root), repo_root=root, env_mode=env_mode)
    if present:
        payload = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": "OK",
            "changed": False,
            "token_present": True,
            "token_source": str(source),
            "note": "Token already present; no changes made.",
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true"],
        }
        _write_json_atomic(out_path, payload)
        print(str(out_path))
        return 0

    if env_mode == "process":
        payload = {
            "version": "v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace_root": str(ws_root),
            "env_mode": env_mode,
            "status": "FAIL",
            "changed": False,
            "token_present": False,
            "error_code": "KERNEL_API_TOKEN_MISSING",
            "note": "env_mode=process cannot write a token; switch env_mode=dotenv to generate workspace .env token.",
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true"],
        }
        _write_json_atomic(out_path, payload)
        print(str(out_path))
        return 2

    # Generate and store in workspace .env (local-only). Never print the token.
    import secrets
    import hashlib

    token = secrets.token_hex(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    ws_env = ws_root / ".env"
    ws_env.parent.mkdir(parents=True, exist_ok=True)
    existing = ws_env.read_text(encoding="utf-8", errors="replace") if ws_env.exists() else ""
    newline = "" if (not existing or existing.endswith("\n")) else "\n"
    ws_env.write_text(existing + newline + f"KERNEL_API_TOKEN={token}\n", encoding="utf-8")
    try:
        ws_env.chmod(0o600)
    except Exception:
        pass

    payload = {
        "version": "v1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_root": str(ws_root),
        "env_mode": env_mode,
        "status": "OK",
        "changed": True,
        "token_present": True,
        "token_source": "workspace_env",
        "token_sha256": token_hash,
        "written_path": str(ws_env),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "no_secrets=true"],
    }
    _write_json_atomic(out_path, payload)
    print(str(out_path))
    return 0


def register_llm_live_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    s = parent.add_parser(
        "llm-live-setup",
        help="Local setup: ensure KERNEL_API_TOKEN and write llm-live-readiness report (no network, no secrets).",
    )
    s.add_argument("--workspace-root", required=True)
    s.add_argument("--out", default="")
    s.add_argument("--env-mode", choices=["dotenv", "process"], default="dotenv")
    s.set_defaults(func=cmd_llm_live_setup)

    x = parent.add_parser(
        "llm-live-set",
        help="Set KERNEL_API_LLM_LIVE=1/0 in workspace .env (dotenv-only; no secrets).",
    )
    x.add_argument("--workspace-root", required=True)
    x.add_argument("--value", choices=["0", "1"], default="", help="Explicit value (0 or 1).")
    x.add_argument("--enabled", action="store_true", help="Shortcut for --value 1.")
    x.add_argument("--out", default="")
    x.add_argument("--env-mode", choices=["dotenv", "process"], default="dotenv")
    x.set_defaults(func=cmd_llm_live_set)

    p = parent.add_parser(
        "llm-live-readiness",
        help="Report-only: checks LLM live call readiness (dotenv-aware, no secrets; optional TLS preflight).",
    )
    p.add_argument("--workspace-root", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--env-mode", choices=["dotenv", "process"], default="dotenv")
    p.add_argument(
        "--tls-preflight",
        choices=["auto", "off", "on"],
        default="auto",
        help="TLS verify preflight: auto=handshake when KERNEL_API_LLM_LIVE=1, off=skip, on=always.",
    )
    p.add_argument(
        "--tls-timeout-seconds",
        type=float,
        default=2.5,
        help="TLS handshake timeout in seconds (only when TLS preflight is attempted).",
    )
    p.set_defaults(func=cmd_llm_live_readiness)

    c = parent.add_parser(
        "llm-live-consult",
        help="Live consult via Kernel API (audited + allowlisted; requires KERNEL_API_LLM_LIVE=1).",
    )
    c.add_argument("--workspace-root", required=True)
    c.add_argument("--providers", default="", help="Comma-separated providers (default: policy_llm_live.allowed_providers)")
    c.add_argument("--prompt", default="")
    c.add_argument("--prompt-file", default="")
    c.add_argument("--out", default="")
    c.add_argument("--env-mode", choices=["dotenv", "process"], default="dotenv")
    c.add_argument("--max-tokens", default=256, type=int)
    c.add_argument("--temperature", default=None, type=float)
    c.set_defaults(func=cmd_llm_live_consult)

    q = parent.add_parser(
        "llm-live-probe",
        help="Live provider probe (minimal ping, audited; requires KERNEL_API_LLM_LIVE=1 for network).",
    )
    q.add_argument("--workspace-root", required=True)
    q.add_argument("--out", default="", help="Optional: copy canonical probe report to this path.")
    q.add_argument("--env-mode", choices=["dotenv", "process"], default="dotenv")
    q.add_argument("--detail", action="store_true", help="Include policy details in the probe report.")
    q.set_defaults(func=cmd_llm_live_probe)

    t = parent.add_parser(
        "kernel-api-token-ensure",
        help="Writes KERNEL_API_TOKEN into workspace .env if missing (local-only, no secrets printed).",
    )
    t.add_argument("--workspace-root", required=True)
    t.add_argument("--out", default="")
    t.add_argument("--env-mode", choices=["dotenv", "process"], default="dotenv")
    t.set_defaults(func=cmd_kernel_api_token_ensure)
