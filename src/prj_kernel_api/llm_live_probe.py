"""Live LLM probe for PRJ-KERNEL-API (explicit opt-in, deterministic, no secrets)."""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error, request
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from src.prj_kernel_api.dotenv_loader import resolve_env_value
from src.prj_kernel_api.provider_guardrails import load_guardrails, model_allowed, provider_settings
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_policy, read_registry

POLICY_PATH = "policies/policy_llm_live.v1.json"
POLICY_SCHEMA = "schemas/policy-llm-live.schema.json"
KNOWN_SKIP_POLICY_PATH = "policies/policy_llm_live_known_skips.v1.json"
REPORT_PATH = ".cache/reports/llm_live_probe.v1.json"

_XAI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

_VIDEO_GEN_ENDPOINT_CANDIDATES = (
    "/videos",
    "/videos/generations",
    "/video/generations",
    "/sora/generations",
)

_VIDEO_GEN_PROMPT = "Generate a very short silent video of the text 'HELLO' on a plain background."
_VIDEO_GEN_SUCCESS_STATUSES = {"completed", "succeeded"}
_VIDEO_GEN_FAILURE_STATUSES = {"failed", "cancelled", "canceled", "expired"}
_VIDEO_GEN_POLL_INTERVAL_SECONDS = 2.0
_VIDEO_GEN_POLL_MAX_SECONDS = 120.0
_VIDEO_GEN_MAX_POLLS_PER_JOB = 24

_OPENAI_CHAT_PRIORITY = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-5",
    "gpt-5.1",
    "gpt-5.2",
)

_GOOGLE_IMAGE_GEN_PRECHECK_UNSUPPORTED = {
    "gemini-2.0-flash-preview-image-generation",
}

_QWEN_HTTP_PRECHECK_UNSUPPORTED = {
    "qvq-max",
}

_VISION_PROBE_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAS0lEQVR42u3PMQ0AAAwDoPo33UrYvQQckD4XAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAYHLAMpT0sIcNbcEAAAAAElFTkSuQmCC"
)

_PROBE_READ_MAX_BYTES = 4_000_000


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


def _load_known_skip_policy(workspace_root: str) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], str | None]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws_path = Path(workspace_root) / KNOWN_SKIP_POLICY_PATH
    repo_path = repo_root / KNOWN_SKIP_POLICY_PATH
    policy_path = ws_path if ws_path.exists() else repo_path
    if not policy_path.exists():
        return [], [], None
    try:
        payload = _load_json(policy_path)
    except Exception:
        return [], [], str(policy_path.resolve())
    rules_raw = payload.get("known_skips") if isinstance(payload.get("known_skips"), list) else []
    rules: List[Dict[str, str]] = []
    for raw in rules_raw:
        if not isinstance(raw, dict):
            continue
        provider_id = str(raw.get("provider_id") or "").strip().lower()
        model = str(raw.get("model") or "").strip().lower()
        if not provider_id or not model:
            continue
        probe_family = str(raw.get("probe_family") or "").strip().lower()
        error_code = str(raw.get("error_code") or "KNOWN_SKIP_POLICY").strip()
        reason = str(raw.get("reason") or "policy_rule").strip()
        rule_id = str(raw.get("rule_id") or "").strip()
        rules.append(
            {
                "provider_id": provider_id,
                "model": model,
                "probe_family": probe_family,
                "error_code": error_code,
                "reason": reason,
                "rule_id": rule_id,
            }
        )
    http_rules_raw = payload.get("known_http_skips") if isinstance(payload.get("known_http_skips"), list) else []
    http_rules: List[Dict[str, Any]] = []
    for raw in http_rules_raw:
        if not isinstance(raw, dict):
            continue
        provider_id = str(raw.get("provider_id") or "").strip().lower()
        if not provider_id:
            continue
        model = str(raw.get("model") or "*").strip().lower() or "*"
        probe_family = str(raw.get("probe_family") or "*").strip().lower() or "*"
        error_code = str(raw.get("error_code") or "KNOWN_SKIP_POLICY").strip()
        reason = str(raw.get("reason") or "policy_rule").strip()
        rule_id = str(raw.get("rule_id") or "").strip()
        http_status_raw = raw.get("http_status")
        http_status = int(http_status_raw) if isinstance(http_status_raw, int) and http_status_raw > 0 else 0
        detail_contains_raw = raw.get("detail_contains") if isinstance(raw.get("detail_contains"), list) else []
        detail_contains = [
            str(tok).strip().lower()
            for tok in detail_contains_raw
            if isinstance(tok, str) and str(tok).strip()
        ]
        http_rules.append(
            {
                "provider_id": provider_id,
                "model": model,
                "probe_family": probe_family,
                "error_code": error_code,
                "reason": reason,
                "rule_id": rule_id,
                "http_status": http_status,
                "detail_contains": detail_contains,
            }
        )
    return rules, http_rules, str(policy_path.resolve())


def _match_known_skip_rule(
    rules: List[Dict[str, str]],
    *,
    provider_id: str,
    model_id: str,
    probe_family: str,
) -> Dict[str, str] | None:
    provider = str(provider_id or "").strip().lower()
    model = str(model_id or "").strip().lower()
    family = str(probe_family or "").strip().lower()
    for rule in rules:
        rp = str(rule.get("provider_id") or "").strip().lower()
        rm = str(rule.get("model") or "").strip().lower()
        rf = str(rule.get("probe_family") or "").strip().lower()
        if rp not in {"*", provider}:
            continue
        if rm not in {"*", model}:
            continue
        if rf and rf not in {"*", family}:
            continue
        return rule
    return None


def _match_known_http_skip_rule(
    rules: List[Dict[str, Any]],
    *,
    provider_id: str,
    model_id: str,
    probe_family: str,
    http_status: int,
    error_detail: str,
) -> Dict[str, Any] | None:
    provider = str(provider_id or "").strip().lower()
    model = str(model_id or "").strip().lower()
    family = str(probe_family or "").strip().lower()
    detail = str(error_detail or "").strip().lower()
    for rule in rules:
        rp = str(rule.get("provider_id") or "").strip().lower()
        rm = str(rule.get("model") or "*").strip().lower() or "*"
        rf = str(rule.get("probe_family") or "*").strip().lower() or "*"
        rhs = rule.get("http_status")
        rhs_value = int(rhs) if isinstance(rhs, int) and rhs > 0 else 0
        detail_contains = rule.get("detail_contains") if isinstance(rule.get("detail_contains"), list) else []

        if rp not in {"*", provider}:
            continue
        if rm not in {"*", model}:
            continue
        if rf not in {"*", family}:
            continue
        if rhs_value and rhs_value != int(http_status or 0):
            continue
        if detail_contains and not any(
            isinstance(tok, str) and tok and tok in detail for tok in detail_contains
        ):
            continue
        return rule
    return None


def _live_enabled(policy: Dict[str, Any], workspace_root: str, *, env_mode: str) -> bool:
    if not bool(policy.get("live_enabled", False)):
        return False
    enable_key = policy.get("enable_env_key") if isinstance(policy.get("enable_env_key"), str) else ""
    if not enable_key:
        return False
    present, value = resolve_env_value(enable_key, workspace_root, env_mode=env_mode)
    return bool(present and isinstance(value, str) and value.strip() == "1")


def _env_flag_enabled(key_name: str, workspace_root: str, *, env_mode: str) -> bool:
    present, value = resolve_env_value(key_name, workspace_root, env_mode=env_mode)
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


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _derive_openai_compatible_root(base_url: str) -> str | None:
    suffix = "/chat/completions"
    if isinstance(base_url, str) and base_url.endswith(suffix):
        return base_url[: -len(suffix)]
    return None


def _derive_google_native_root(base_url: str) -> str | None:
    parsed = urlparse(base_url or "")
    if not parsed.scheme or not parsed.netloc:
        return None
    path = parsed.path or ""
    marker = "/v1beta"
    if marker in path:
        return f"{parsed.scheme}://{parsed.netloc}{marker}"
    return f"{parsed.scheme}://{parsed.netloc}{marker}"


def _google_generatecontent_inline_part(data: Dict[str, Any]) -> Dict[str, Any] | None:
    candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        content = cand.get("content") if isinstance(cand.get("content"), dict) else {}
        parts = content.get("parts") if isinstance(content.get("parts"), list) else []
        for part in parts:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") if isinstance(part.get("inlineData"), dict) else None
            if not inline:
                continue
            mime = inline.get("mimeType")
            blob = inline.get("data")
            if isinstance(mime, str) and mime.strip() and isinstance(blob, str) and blob:
                return inline
    return None


def _google_embedding_values(data: Dict[str, Any]) -> List[Any] | None:
    emb = data.get("embedding") if isinstance(data.get("embedding"), dict) else None
    if emb and isinstance(emb.get("values"), list):
        return emb.get("values")
    emb_items = data.get("embeddings") if isinstance(data.get("embeddings"), list) else []
    if emb_items and isinstance(emb_items[0], dict):
        values = emb_items[0].get("values")
        if isinstance(values, list):
            return values
    return None


def _http_error_detail(exc: error.HTTPError, *, max_chars: int) -> str:
    try:
        raw = exc.read(20_000)
        txt = raw.decode("utf-8", errors="replace").strip()
        if txt:
            return txt[:max_chars]
    except Exception:
        pass
    return str(exc)[:max_chars]


def _http_post_json(
    *,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: float,
    tls_context: ssl.SSLContext | None,
    max_bytes: int,
) -> Tuple[int, Dict[str, Any]]:
    req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with request.urlopen(req, timeout=float(timeout_seconds), context=tls_context) as resp:
        body = resp.read(max_bytes)
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except Exception:
            data = {}
        return int(getattr(resp, "status", 0) or 0), (data if isinstance(data, dict) else {})


def _http_get_json(
    *,
    url: str,
    headers: Dict[str, str],
    timeout_seconds: float,
    tls_context: ssl.SSLContext | None,
    max_bytes: int,
) -> Tuple[int, Dict[str, Any]]:
    req = request.Request(url, headers=headers, method="GET")
    with request.urlopen(req, timeout=float(timeout_seconds), context=tls_context) as resp:
        body = resp.read(max_bytes)
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except Exception:
            data = {}
        return int(getattr(resp, "status", 0) or 0), (data if isinstance(data, dict) else {})


def _infer_probe_family(model_id: str) -> str:
    name = str(model_id or "").strip().lower()
    if not name:
        return "chat"
    if "embedding" in name:
        return "embeddings"
    if "moderation" in name:
        return "moderation"
    if "realtime" in name:
        return "realtime"
    if "audio" in name or "tts" in name or "transcribe" in name:
        return "audio"
    if "ocr" in name or "vision" in name or "vl" in name or "qvq" in name:
        return "vision"
    if "sora" in name or "video" in name:
        return "video_gen"
    if "dall-e" in name or "gpt-image" in name or "chatgpt-image" in name or "image" in name or "img" in name:
        return "image_gen"
    return "chat"


def _policy_enabled_families(policy: Dict[str, Any]) -> List[str]:
    raw = policy.get("enabled_probe_families")
    if not isinstance(raw, list):
        return ["chat"]
    items = [str(x).strip() for x in raw if isinstance(x, str) and x.strip()]
    if not items:
        return ["chat"]
    if "chat" not in items:
        items = ["chat", *items]
    return _dedupe_keep_order(items)


def _semantic_realtime_handshake_openai(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: float,
    tls_context: ssl.SSLContext | None,
) -> Tuple[int, bool, str | None]:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if not host:
        return 0, False, "PROVIDER_BASE_URL_UNSUPPORTED"

    path = f"/v1/realtime?model={model_id}"
    key = "dGhlIHNhbXBsZSBub25jZQ=="
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "OpenAI-Beta: realtime=v1\r\n"
        f"Authorization: Bearer {api_key}\r\n"
        "\r\n"
    ).encode("utf-8")

    sock: socket.socket | None = None
    ssock: ssl.SSLSocket | None = None
    try:
        sock = socket.create_connection((host, 443), timeout=float(timeout_seconds))
        ssock = (tls_context or ssl.create_default_context()).wrap_socket(sock, server_hostname=host)
        ssock.settimeout(float(timeout_seconds))
        ssock.sendall(req)
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 8192:
            chunk = ssock.recv(2048)
            if not chunk:
                break
            buf += chunk
        head = buf.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")
        ok = " 101 " in head or head.endswith(" 101")
        return 101 if ok else 0, ok, None if ok else "REALTIME_HANDSHAKE_NOT_101"
    finally:
        try:
            if ssock:
                ssock.close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass


def _model_targets_for_provider(provider_id: str, *, provider: Dict[str, Any], guard: Dict[str, Any]) -> List[str]:
    targets: List[str] = []
    if provider_id == "openai":
        targets.extend(list(_OPENAI_CHAT_PRIORITY))

    allow_models = guard.get("allow_models")
    if isinstance(allow_models, list):
        allow_models = [str(m).strip() for m in allow_models if isinstance(m, str) and m.strip()]
    else:
        allow_models = []
    if "*" not in allow_models:
        targets.extend(allow_models)

    guard_default = guard.get("default_model")
    if isinstance(guard_default, str) and guard_default.strip():
        targets.insert(0, guard_default.strip())
    else:
        provider_default = provider.get("default_model")
        if isinstance(provider_default, str) and provider_default.strip():
            targets.insert(0, provider_default.strip())

    return _dedupe_keep_order(targets)


def run_live_probe(*, workspace_root: str, detail: bool = False, env_mode: str = "dotenv") -> Tuple[str, str | None, Dict[str, Any]]:
    from src.prj_kernel_api.llm_live_probe_runtime import run_live_probe as _impl

    return _impl(workspace_root=workspace_root, detail=detail, env_mode=env_mode)
