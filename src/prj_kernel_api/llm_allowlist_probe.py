"""Allowlist probe for enabled LLM providers (best-effort, deterministic, no secrets).

This module is intentionally conservative:
- It never logs API keys (only the env var name used).
- It updates workspace state (`llm_probe_state.v1.json`) based on probe outcomes.
- Cost/side-effect prone semantic probes are opt-in (dotenv flags) + live gate.

Semantic probes (opt-in):
- OCR_DOC (Qwen): semantic_ocr
- AUDIO (OpenAI/Google): semantic_audio (best-effort)
- REALTIME_STREAMING (OpenAI): semantic_realtime_handshake (best-effort)
- IMAGE_GEN (OpenAI/xAI): semantic_image_gen (best-effort)
- VIDEO_GEN: semantic probe is intentionally opt-in and may remain unsupported per-provider.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import socket
import ssl
import struct
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error, request
from urllib.parse import urlparse

from src.prj_kernel_api.dotenv_loader import resolve_env_value
from src.prj_kernel_api.provider_guardrails import live_call_allowed, load_guardrails, model_allowed, provider_settings
from src.prj_kernel_api.providers_registry import ensure_providers_registry, read_registry


REPORT_PATH = ".cache/reports/llm_allowlist_probe.v0.1.json"
STATE_PATH = ".cache/state/llm_probe_state.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket_elapsed_ms(elapsed_ms: float) -> int:
    return int(round(elapsed_ms / 10.0) * 10)


def _write_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


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


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
    return length + chunk_type + data + struct.pack(">I", crc)


def _hello_png_data_url(*, text: str = "HELLO", scale: int = 4) -> str:
    # Minimal 5x7 font for required letters (uppercase).
    font: Dict[str, List[str]] = {
        "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
        "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
        "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
        "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
        " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    }
    text = "".join([c for c in (text or "").upper() if c in font])
    if not text:
        text = "HELLO"

    # Layout: 1px gap between glyphs, 2px margin around, scaled up.
    glyph_w = 5
    glyph_h = 7
    gap = 1
    margin = 2
    w_raw = len(text) * glyph_w + max(0, len(text) - 1) * gap + 2 * margin
    h_raw = glyph_h + 2 * margin
    width = w_raw * scale
    height = h_raw * scale

    # Initialize white background.
    img = [[255 for _ in range(width)] for _ in range(height)]

    def set_px(x: int, y: int, value: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            img[y][x] = value

    cursor_x = margin
    for ch in text:
        rows = font.get(ch, font[" "])
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "1":
                    # Draw scaled black pixel block.
                    for sy in range(scale):
                        for sx in range(scale):
                            set_px((cursor_x + rx) * scale + sx, (margin + ry) * scale + sy, 0)
        cursor_x += glyph_w + gap

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        raw.extend(bytes(img[y]))
    compressed = zlib.compress(bytes(raw), level=9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)  # grayscale
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _env_flag_is_1(*, workspace_root: str, env_mode: str, key: str) -> bool:
    present, value = resolve_env_value(key, workspace_root, env_mode=env_mode)
    return bool(present and isinstance(value, str) and value.strip() == "1")


def _semantic_probe_gate(
    *,
    workspace_root: str,
    env_mode: str,
    class_id: str,
    alias_keys: List[str] | None = None,
) -> Tuple[bool, str | None]:
    # Global semantic gate + per-class gate.
    if not _env_flag_is_1(workspace_root=workspace_root, env_mode=env_mode, key="LLM_PROBE_SEMANTIC"):
        return False, None
    keys = [f"LLM_PROBE_SEMANTIC_{class_id}"]
    if alias_keys:
        keys.extend([k for k in alias_keys if isinstance(k, str) and k.strip()])
    for k in keys:
        if _env_flag_is_1(workspace_root=workspace_root, env_mode=env_mode, key=k):
            return True, k
    return False, None


def _semantic_probe_cost_ack(
    *,
    workspace_root: str,
    env_mode: str,
    class_id: str,
    required: bool,
) -> Tuple[bool, str | None]:
    """Extra opt-in gate for probes that may cost money / have side-effects.

    We keep this separate from the main semantic gate so operators can turn on a
    semantic family but still require an explicit 'ACK' before any calls happen.
    """
    if not required:
        return True, None
    key = f"LLM_PROBE_SEMANTIC_{class_id}_ACK"
    ok = _env_flag_is_1(workspace_root=workspace_root, env_mode=env_mode, key=key)
    return ok, key


def _resolve_api_key(
    *, workspace_root: str, env_mode: str, expected_env_keys: List[str]
) -> Tuple[str | None, str | None]:
    for key_name in expected_env_keys:
        present, value = resolve_env_value(key_name, workspace_root, env_mode=env_mode)
        if present and value:
            return value, key_name
    return None, None


def _select_allowed_model_id(
    *,
    state: Dict[str, Any],
    class_id: str,
    provider_id: str,
    candidate_models: List[str],
    allow_models: List[Any],
    prefer_probe_kind: str | None,
) -> str | None:
    allowed = [
        m
        for m in candidate_models
        if isinstance(m, str) and m and model_allowed(m, allow_models)
    ]
    if not allowed:
        return None

    models_state = (
        (state.get("classes") or {})
        .get(class_id, {})
        .get("providers", {})
        .get(provider_id, {})
        .get("models", {})
    )

    def _prior(m: str) -> Tuple[str | None, str | None]:
        d = models_state.get(m) if isinstance(models_state, dict) else None
        if not isinstance(d, dict):
            return None, None
        return d.get("probe_status"), d.get("probe_kind")

    # 1) Prefer a previously semantic-OK model for this probe kind (if any).
    if isinstance(prefer_probe_kind, str) and prefer_probe_kind:
        for m in allowed:
            st, pk = _prior(m)
            if st == "ok" and pk == prefer_probe_kind:
                return m

    # 2) Otherwise prefer any previously OK model (availability or prior probe).
    for m in allowed:
        st, _pk = _prior(m)
        if st == "ok":
            return m

    # 3) Avoid repeating known semantic FAILs for the same probe kind (if possible).
    if isinstance(prefer_probe_kind, str) and prefer_probe_kind:
        for m in allowed:
            st, pk = _prior(m)
            if not (st == "fail" and pk == prefer_probe_kind):
                return m

    # 4) Fallback to the first allowed model in deterministic order.
    return allowed[0]


def _providers_registry_by_id(workspace_root: str) -> Dict[str, Dict[str, Any]]:
    paths = ensure_providers_registry(workspace_root)
    reg = read_registry(Path(paths["providers_path"]))
    providers = reg.get("providers") if isinstance(reg.get("providers"), list) else []
    out: Dict[str, Dict[str, Any]] = {}
    for p in providers:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        if isinstance(pid, str) and pid:
            out[pid] = p
    return out


def _qwen_semantic_ocr_call(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: int,
    tls_context: ssl.SSLContext | None,
) -> Tuple[int, str]:
    # Qwen (DashScope OpenAI-compatible): attempt a few known image payload shapes.
    #
    # Some providers accept:
    # - {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}} (OpenAI-style)
    # Others may accept:
    # - {"type":"image_url","image_url":"data:image/png;base64,..."} (legacy)
    # We keep this deterministic: try in a fixed order and stop on first HTTP 200.
    img_url = _hello_png_data_url(text="HELLO", scale=4)
    payloads: List[Dict[str, Any]] = [
        {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "OCR: Extract the visible text. Return only the text."},
                        {"type": "image_url", "image_url": {"url": img_url}},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 32,
            "stream": False,
        },
        {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "OCR: Extract the visible text. Return only the text."},
                        {"type": "image_url", "image_url": img_url},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 32,
            "stream": False,
        },
    ]

    last_http_status: int = 0
    last_content: str = ""
    last_exc: Exception | None = None

    for payload in payloads:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        req = request.Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=float(timeout_seconds), context=tls_context) as resp:
                body = resp.read(256_000)
                data = json.loads(body.decode("utf-8", errors="replace"))
                content = ""
                try:
                    choices = data.get("choices") if isinstance(data, dict) else None
                    if isinstance(choices, list) and choices:
                        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                            content = msg.get("content") or ""
                except Exception:
                    content = ""
                return int(getattr(resp, "status", 0) or 0), content
        except error.HTTPError as exc:
            last_http_status = int(getattr(exc, "code", 0) or 0)
            last_exc = exc
        except Exception as exc:
            last_exc = exc

    if last_exc:
        raise last_exc
    return last_http_status, last_content


def _derive_openai_compatible_root(base_url: str) -> str | None:
    # Providers registry usually stores chat/completions endpoints.
    suffix = "/chat/completions"
    if isinstance(base_url, str) and base_url.endswith(suffix):
        return base_url[: -len(suffix)]
    return None


def _http_error_detail(exc: error.HTTPError, *, max_chars: int = 420) -> str:
    """Best-effort extract provider error payload for debugging (no secrets)."""
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
    api_key: str,
    payload: Dict[str, Any],
    timeout_seconds: int,
    tls_context: ssl.SSLContext | None,
    max_bytes: int = 1_200_000,
) -> Tuple[int, Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with request.urlopen(req, timeout=float(timeout_seconds), context=tls_context) as resp:
        body = resp.read(max_bytes)
        data = json.loads(body.decode("utf-8", errors="replace"))
        return int(getattr(resp, "status", 0) or 0), (data if isinstance(data, dict) else {})


def _semantic_image_gen_call(
    *,
    provider_id: str,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: int,
    tls_context: ssl.SSLContext | None,
) -> Tuple[int, bool, str | None]:
    root = _derive_openai_compatible_root(base_url)
    if not root:
        return 0, False, "PROVIDER_BASE_URL_UNSUPPORTED"
    url = root + "/images/generations"
    payload: Dict[str, Any] = {
        "model": model_id,
        "prompt": "Generate a simple image that contains the text 'HELLO'.",
        "n": 1,
    }
    # Provider-specific drift:
    # - OpenAI currently rejects 256x256 for gpt-image-1 (supports 'auto' + larger sizes).
    # - Google OpenAI-compatible wrapper may require response_format=b64_json.
    if provider_id in {"openai", "google"}:
        payload["size"] = "auto"
    else:
        payload["size"] = "256x256"
    if provider_id == "openai" and isinstance(model_id, str) and model_id.startswith("dall-e-"):
        payload["size"] = "1024x1024"
    if provider_id == "google":
        payload["response_format"] = "b64_json"
    http_status, data = _http_post_json(
        url=url,
        api_key=api_key,
        payload=payload,
        timeout_seconds=timeout_seconds,
        tls_context=tls_context,
        max_bytes=2_000_000,
    )
    # Success = endpoint responds and returns at least one image payload.
    ok = False
    if http_status == 200:
        items = data.get("data") if isinstance(data.get("data"), list) else []
        if items and isinstance(items[0], dict):
            ok = bool(items[0].get("b64_json") or items[0].get("url"))
    return http_status, ok, None if ok else "IMAGE_GEN_NO_IMAGE_DATA"


def _semantic_video_gen_call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: int,
    tls_context: ssl.SSLContext | None,
) -> Tuple[int, bool, str | None]:
    """Best-effort video generation probe (OpenAI-compatible).

    WARNING: This may incur real cost. It must be protected by an explicit ACK gate.
    """
    root = _derive_openai_compatible_root(base_url)
    if not root:
        return 0, False, "PROVIDER_BASE_URL_UNSUPPORTED"

    # Provider-specific endpoint drift exists for video generation. Keep this deterministic:
    # - Try a small fixed list of candidate endpoints.
    # - Only advance to the next candidate on 404/405 (no-op/unsupported).
    endpoint_candidates = ["/videos", "/videos/generations", "/video/generations", "/sora/generations"]

    last_http_status: int = 0
    for path in endpoint_candidates:
        url = root + path
        payload: Dict[str, Any] = {
            "model": model_id,
            "prompt": "Generate a very short silent video of the text 'HELLO' on a plain background.",
        }
        try:
            http_status, data = _http_post_json(
                url=url,
                api_key=api_key,
                payload=payload,
                timeout_seconds=timeout_seconds,
                tls_context=tls_context,
                max_bytes=2_000_000,
            )
        except error.HTTPError as exc:
            http_status = int(getattr(exc, "code", 0) or 0)
            last_http_status = http_status
            if http_status in {404, 405}:
                continue
            raise

        last_http_status = http_status
        ok = False
        if http_status in {200, 201, 202}:
            if isinstance(data.get("id"), str) and data.get("id"):
                ok = True
            items = data.get("data") if isinstance(data.get("data"), list) else []
            if items:
                ok = True
        if ok:
            return http_status, True, None
        # Non-OK response: fail fast (do not try alternative endpoints, to avoid side-effects).
        return http_status, False, "VIDEO_GEN_NO_JOB_DATA"

    # All endpoints were unsupported.
    return last_http_status, False, "VIDEO_GEN_ENDPOINT_UNSUPPORTED"


def _semantic_audio_call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: int,
    tls_context: ssl.SSLContext | None,
) -> Tuple[int, bool, str | None]:
    # Best-effort audio semantics using OpenAI-compatible chat/completions.
    # If provider doesn't support audio output here, this probe will FAIL (opt-in).
    payload: Dict[str, Any] = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Say 'hello'."}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
        # Attempt audio output modality (ignored by providers that don't support it).
        "modalities": ["text", "audio"],
        "audio": {"voice": "alloy", "format": "wav"},
    }
    http_status, data = _http_post_json(
        url=base_url,
        api_key=api_key,
        payload=payload,
        timeout_seconds=timeout_seconds,
        tls_context=tls_context,
        max_bytes=2_000_000,
    )
    ok = False
    if http_status == 200:
        # Try to find any audio payload in known places.
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
            audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
            if audio and isinstance(audio.get("data"), str) and audio.get("data"):
                ok = True
    return http_status, ok, None if ok else "AUDIO_NO_AUDIO_DATA"


def _semantic_realtime_handshake_openai(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: int,
    tls_context: ssl.SSLContext | None,
) -> Tuple[int, bool, str | None]:
    # Best-effort WebSocket handshake. This is intentionally minimal to avoid side-effects.
    # NOTE: The realtime endpoint is provider-specific; for OpenAI we use /v1/realtime.
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if not host:
        return 0, False, "PROVIDER_BASE_URL_UNSUPPORTED"

    path = f"/v1/realtime?model={model_id}"
    key = "dGhlIHNhbXBsZSBub25jZQ=="  # deterministic sample nonce (base64)
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
        # Expect 101 Switching Protocols.
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


def _load_json_optional(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _ensure_state_shape(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state.get("classes"), dict):
        state["classes"] = {}
    return state


def _upsert_state_probe(
    *,
    state: Dict[str, Any],
    class_id: str,
    provider_id: str,
    model_id: str,
    probe_kind: str,
    status: str,
    error_code: str | None,
    latency_ms: int,
    now: str,
) -> None:
    state = _ensure_state_shape(state)
    classes = state["classes"]
    cls = classes.setdefault(class_id, {})
    providers = cls.setdefault("providers", {})
    prov = providers.setdefault(provider_id, {})
    models = prov.setdefault("models", {})
    entry = models.setdefault(model_id, {})
    entry["probe_kind"] = str(probe_kind)
    entry["probe_last_at"] = now
    entry["probe_latency_ms_p95"] = int(latency_ms)
    entry["probe_status"] = "ok" if status == "OK" else "fail"
    entry["probe_error_code"] = error_code
    entry["verified_at"] = now if status == "OK" else None


def _patch_report_item(
    *,
    report: Dict[str, Any],
    provider_id: str,
    model_id: str,
    probe_kind: str,
    status: str,
    http_status: int | None,
    error_code: str | None,
    error_detail: str | None,
    elapsed_ms: int,
    tls_cafile: str | None,
    api_key_env_used: str | None,
    classes_target: List[str],
    semantic_gate: str | None,
) -> None:
    if not isinstance(report.get("items"), list):
        report["items"] = []
    items: List[Dict[str, Any]] = [it for it in report["items"] if isinstance(it, dict)]
    report["items"] = items
    for it in items:
        if it.get("provider_id") == provider_id and it.get("model_id") == model_id and it.get("probe_kind") == probe_kind:
            it["status"] = status
            it["http_status"] = http_status
            it["error_code"] = error_code
            it["error_detail"] = error_detail
            it["elapsed_ms"] = int(elapsed_ms)
            it["tls_cafile"] = tls_cafile
            it["api_key_env_used"] = api_key_env_used
            if classes_target:
                it["classes_target"] = list(classes_target)
            if semantic_gate:
                it["semantic_gate"] = semantic_gate
            return
    # If missing, append a new item (deterministic, minimal fields).
    items.append(
        {
            "provider_id": provider_id,
            "model_id": model_id,
            "probe_kind": probe_kind,
            "status": status,
            "http_status": http_status,
            "error_code": error_code,
            "error_detail": error_detail,
            "elapsed_ms": int(elapsed_ms),
            "tls_cafile": tls_cafile,
            "api_key_env_used": api_key_env_used,
            "classes_target": list(classes_target),
            "semantic_gate": semantic_gate,
        }
    )


def run_allowlist_probe(
    *,
    workspace_root: str,
    env_mode: str = "dotenv",
    patch_only_semantic_ocr: bool = True,
) -> Dict[str, Any]:
    guardrails = load_guardrails(workspace_root)
    providers_by_id = _providers_registry_by_id(workspace_root)
    ws = Path(workspace_root)

    report_path = ws / REPORT_PATH
    state_path = ws / STATE_PATH
    report = _load_json_optional(report_path) or {}
    state = _load_json_optional(state_path) or {"classes": {}}

    tls_cafile = _resolve_tls_cafile()
    tls_context = _build_tls_context(tls_cafile)

    patched: List[Dict[str, Any]] = []

    # ---------------------------
    # OCR_DOC semantic (Qwen OCR)
    # ---------------------------
    ocr_enabled, ocr_gate = _semantic_probe_gate(
        workspace_root=workspace_root, env_mode=env_mode, class_id="OCR_DOC", alias_keys=["LLM_PROBE_SEMANTIC_OCR"]
    )
    if ocr_enabled:
        provider_id = "qwen"
        qwen = provider_settings(guardrails, provider_id)
        expected_env = qwen.get("expected_env_keys", [])
        api_key, api_key_env_used = _resolve_api_key(
            workspace_root=workspace_root,
            env_mode=env_mode,
            expected_env_keys=[str(x) for x in expected_env if isinstance(x, str) and x.strip()],
        )
        base_url = None
        if isinstance(providers_by_id.get(provider_id), dict):
            base_url = providers_by_id[provider_id].get("base_url")
        if not isinstance(base_url, str) or not base_url:
            base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

        model_id = "qwen-vl-ocr-2025-11-20"
        timeout_seconds = int(qwen.get("timeout_seconds", 60) or 60)

        start = time.monotonic()
        status = "FAIL"
        http_status: int | None = None
        err_code: str | None = None
        err_detail: str | None = None
        extracted = ""
        try:
            allowed, allow_reason = live_call_allowed(
                policy=guardrails, workspace_root=workspace_root, env_mode=env_mode, api_key_present=bool(api_key)
            )
            if not allowed:
                status = "SKIPPED"
                err_code = allow_reason
            elif not api_key:
                status = "SKIPPED"
                err_code = "API_KEY_MISSING"
            elif not model_allowed(model_id, qwen.get("allow_models", ["*"])):
                status = "SKIPPED"
                err_code = "MODEL_NOT_ALLOWED"
            else:
                http_status, extracted = _qwen_semantic_ocr_call(
                    base_url=base_url,
                    api_key=api_key,
                    model_id=model_id,
                    timeout_seconds=timeout_seconds,
                    tls_context=tls_context,
                )
                got = (extracted or "").upper()
                if http_status == 200 and "HELLO" in got:
                    status = "OK"
                else:
                    status = "FAIL"
                    err_code = "SEMANTIC_OCR_MISMATCH"
                    err_detail = f"expected_contains=HELLO got={got[:80]!r}"
        except error.HTTPError as exc:
            http_status = int(getattr(exc, "code", 0) or 0)
            err_code = "PROVIDER_HTTP_ERROR"
            err_detail = _http_error_detail(exc)
            status = "FAIL"
        except Exception as exc:
            err_code = "PROVIDER_REQUEST_FAILED"
            err_detail = str(exc)[:220]
            status = "FAIL"
        elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
        now = _now_iso()

        if status in {"OK", "FAIL"}:
            _upsert_state_probe(
                state=state,
                class_id="OCR_DOC",
                provider_id=provider_id,
                model_id=model_id,
                probe_kind="semantic_ocr",
                status=status,
                error_code=err_code,
                latency_ms=elapsed_ms,
                now=now,
            )
        _patch_report_item(
            report=report,
            provider_id=provider_id,
            model_id=model_id,
            probe_kind="semantic_ocr",
            status=status,
            http_status=http_status,
            error_code=err_code,
            error_detail=err_detail,
            elapsed_ms=elapsed_ms,
            tls_cafile=tls_cafile,
            api_key_env_used=api_key_env_used,
            classes_target=["OCR_DOC"],
            semantic_gate=ocr_gate or "LLM_PROBE_SEMANTIC_OCR_DOC",
        )
        patched.append(
            {
                "provider_id": provider_id,
                "model_id": model_id,
                "probe_kind": "semantic_ocr",
                "status": status,
                "http_status": http_status,
            }
        )

    # ---------------------------------
    # IMAGE_GEN semantic (best-effort)
    # ---------------------------------
    img_enabled, img_gate = _semantic_probe_gate(workspace_root=workspace_root, env_mode=env_mode, class_id="IMAGE_GEN")
    if img_enabled:
        ack_ok, ack_key = _semantic_probe_cost_ack(
            workspace_root=workspace_root,
            env_mode=env_mode,
            class_id="IMAGE_GEN",
            required=True,
        )
        # Provider-aware: OpenAI-compatible /images/generations for OpenAI + xAI (+ best-effort Google).
        img_candidates: Dict[str, List[str]] = {
            "openai": ["dall-e-3", "dall-e-2", "gpt-image-1", "chatgpt-image-latest", "gpt-image-1.5", "gpt-image-1-mini"],
            "xai": ["grok-2-image-1212"],
            "google": ["gemini-3-pro-image-preview", "gemini-2.5-flash-image"],
        }
        for provider_id, models in sorted(img_candidates.items(), key=lambda kv: kv[0]):
            guard = provider_settings(guardrails, provider_id)
            base_url = providers_by_id.get(provider_id, {}).get("base_url") if isinstance(providers_by_id.get(provider_id), dict) else None
            if not isinstance(base_url, str) or not base_url:
                continue
            model_id = _select_allowed_model_id(
                state=state,
                class_id="IMAGE_GEN",
                provider_id=provider_id,
                candidate_models=models,
                allow_models=guard.get("allow_models", ["*"]),
                prefer_probe_kind="semantic_image_gen",
            )
            if not isinstance(model_id, str) or not model_id:
                continue

            if not ack_ok:
                start = time.monotonic()
                elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
                _patch_report_item(
                    report=report,
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_image_gen",
                    status="SKIPPED",
                    http_status=None,
                    error_code="ACK_REQUIRED",
                    error_detail=str(ack_key or ""),
                    elapsed_ms=elapsed_ms,
                    tls_cafile=tls_cafile,
                    api_key_env_used=None,
                    classes_target=["IMAGE_GEN"],
                    semantic_gate=img_gate or "LLM_PROBE_SEMANTIC_IMAGE_GEN",
                )
                patched.append(
                    {
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "probe_kind": "semantic_image_gen",
                        "status": "SKIPPED",
                        "http_status": None,
                    }
                )
                continue

            api_key, api_key_env_used = _resolve_api_key(
                workspace_root=workspace_root,
                env_mode=env_mode,
                expected_env_keys=[str(x) for x in guard.get("expected_env_keys", []) if isinstance(x, str) and x.strip()],
            )
            timeout_seconds = int(guard.get("timeout_seconds", 60) or 60)

            start = time.monotonic()
            status = "FAIL"
            http_status: int | None = None
            err_code: str | None = None
            err_detail: str | None = None
            try:
                allowed, allow_reason = live_call_allowed(
                    policy=guardrails, workspace_root=workspace_root, env_mode=env_mode, api_key_present=bool(api_key)
                )
                if not allowed:
                    status = "SKIPPED"
                    err_code = allow_reason
                elif not api_key:
                    status = "SKIPPED"
                    err_code = "API_KEY_MISSING"
                else:
                    http_status, ok, err_code = _semantic_image_gen_call(
                        provider_id=provider_id,
                        base_url=base_url,
                        api_key=api_key,
                        model_id=model_id,
                        timeout_seconds=timeout_seconds,
                        tls_context=tls_context,
                    )
                    status = "OK" if ok else "FAIL"
            except error.HTTPError as exc:
                http_status = int(getattr(exc, "code", 0) or 0)
                err_code = "PROVIDER_HTTP_ERROR"
                err_detail = _http_error_detail(exc)
                status = "FAIL"
            except Exception as exc:
                err_code = "PROVIDER_REQUEST_FAILED"
                err_detail = str(exc)[:220]
                status = "FAIL"
            elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
            now = _now_iso()

            if status in {"OK", "FAIL"}:
                _upsert_state_probe(
                    state=state,
                    class_id="IMAGE_GEN",
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_image_gen",
                    status=status,
                    error_code=err_code,
                    latency_ms=elapsed_ms,
                    now=now,
                )
            _patch_report_item(
                report=report,
                provider_id=provider_id,
                model_id=model_id,
                probe_kind="semantic_image_gen",
                status=status,
                http_status=http_status,
                error_code=err_code,
                error_detail=err_detail,
                elapsed_ms=elapsed_ms,
                tls_cafile=tls_cafile,
                api_key_env_used=api_key_env_used,
                classes_target=["IMAGE_GEN"],
                semantic_gate=img_gate or "LLM_PROBE_SEMANTIC_IMAGE_GEN",
            )
            patched.append(
                {
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "probe_kind": "semantic_image_gen",
                    "status": status,
                    "http_status": http_status,
                }
            )

    # ------------------------------
    # AUDIO semantic (best-effort)
    # ------------------------------
    audio_enabled, audio_gate = _semantic_probe_gate(workspace_root=workspace_root, env_mode=env_mode, class_id="AUDIO")
    if audio_enabled:
        ack_ok, ack_key = _semantic_probe_cost_ack(
            workspace_root=workspace_root,
            env_mode=env_mode,
            class_id="AUDIO",
            required=True,
        )
        audio_candidates: Dict[str, List[str]] = {
            "openai": ["gpt-4o-mini-audio-preview", "gpt-4o-audio-preview"],
            "google": ["gemini-2.5-flash-preview-tts"],
        }
        for provider_id, models in sorted(audio_candidates.items(), key=lambda kv: kv[0]):
            guard = provider_settings(guardrails, provider_id)
            base_url = providers_by_id.get(provider_id, {}).get("base_url") if isinstance(providers_by_id.get(provider_id), dict) else None
            if not isinstance(base_url, str) or not base_url:
                continue
            model_id = next((m for m in models if model_allowed(m, guard.get("allow_models", ["*"]))), None)
            if not isinstance(model_id, str):
                continue

            if not ack_ok:
                start = time.monotonic()
                elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
                _patch_report_item(
                    report=report,
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_audio",
                    status="SKIPPED",
                    http_status=None,
                    error_code="ACK_REQUIRED",
                    error_detail=str(ack_key or ""),
                    elapsed_ms=elapsed_ms,
                    tls_cafile=tls_cafile,
                    api_key_env_used=None,
                    classes_target=["AUDIO"],
                    semantic_gate=audio_gate or "LLM_PROBE_SEMANTIC_AUDIO",
                )
                patched.append(
                    {
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "probe_kind": "semantic_audio",
                        "status": "SKIPPED",
                        "http_status": None,
                    }
                )
                continue

            api_key, api_key_env_used = _resolve_api_key(
                workspace_root=workspace_root,
                env_mode=env_mode,
                expected_env_keys=[str(x) for x in guard.get("expected_env_keys", []) if isinstance(x, str) and x.strip()],
            )
            timeout_seconds = int(guard.get("timeout_seconds", 60) or 60)

            start = time.monotonic()
            status = "FAIL"
            http_status: int | None = None
            err_code: str | None = None
            err_detail: str | None = None
            try:
                allowed, allow_reason = live_call_allowed(
                    policy=guardrails, workspace_root=workspace_root, env_mode=env_mode, api_key_present=bool(api_key)
                )
                if not allowed:
                    status = "SKIPPED"
                    err_code = allow_reason
                elif not api_key:
                    status = "SKIPPED"
                    err_code = "API_KEY_MISSING"
                else:
                    http_status, ok, err_code = _semantic_audio_call_openai_compatible(
                        base_url=base_url,
                        api_key=api_key,
                        model_id=model_id,
                        timeout_seconds=timeout_seconds,
                        tls_context=tls_context,
                    )
                    status = "OK" if ok else "FAIL"
            except error.HTTPError as exc:
                http_status = int(getattr(exc, "code", 0) or 0)
                err_code = "PROVIDER_HTTP_ERROR"
                err_detail = _http_error_detail(exc)
                status = "FAIL"
            except Exception as exc:
                err_code = "PROVIDER_REQUEST_FAILED"
                err_detail = str(exc)[:220]
                status = "FAIL"
            elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
            now = _now_iso()

            if status in {"OK", "FAIL"}:
                _upsert_state_probe(
                    state=state,
                    class_id="AUDIO",
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_audio",
                    status=status,
                    error_code=err_code,
                    latency_ms=elapsed_ms,
                    now=now,
                )
            _patch_report_item(
                report=report,
                provider_id=provider_id,
                model_id=model_id,
                probe_kind="semantic_audio",
                status=status,
                http_status=http_status,
                error_code=err_code,
                error_detail=err_detail,
                elapsed_ms=elapsed_ms,
                tls_cafile=tls_cafile,
                api_key_env_used=api_key_env_used,
                classes_target=["AUDIO"],
                semantic_gate=audio_gate or "LLM_PROBE_SEMANTIC_AUDIO",
            )
            patched.append(
                {
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "probe_kind": "semantic_audio",
                    "status": status,
                    "http_status": http_status,
                }
            )

    # -------------------------------------------
    # REALTIME_STREAMING semantic (best-effort)
    # -------------------------------------------
    rt_enabled, rt_gate = _semantic_probe_gate(
        workspace_root=workspace_root,
        env_mode=env_mode,
        class_id="REALTIME_STREAMING",
        alias_keys=["LLM_PROBE_SEMANTIC_REALTIME"],
    )
    if rt_enabled:
        ack_ok, ack_key = _semantic_probe_cost_ack(
            workspace_root=workspace_root,
            env_mode=env_mode,
            class_id="REALTIME_STREAMING",
            required=True,
        )
        provider_id = "openai"
        guard = provider_settings(guardrails, provider_id)
        base_url = providers_by_id.get(provider_id, {}).get("base_url") if isinstance(providers_by_id.get(provider_id), dict) else None
        if isinstance(base_url, str) and base_url:
            model_id = next(
                (
                    m
                    for m in ["gpt-4o-mini-realtime-preview", "gpt-4o-realtime-preview"]
                    if model_allowed(m, guard.get("allow_models", ["*"]))
                ),
                None,
            )
            if isinstance(model_id, str):
                if not ack_ok:
                    start = time.monotonic()
                    elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
                    _patch_report_item(
                        report=report,
                        provider_id=provider_id,
                        model_id=model_id,
                        probe_kind="semantic_realtime_handshake",
                        status="SKIPPED",
                        http_status=None,
                        error_code="ACK_REQUIRED",
                        error_detail=str(ack_key or ""),
                        elapsed_ms=elapsed_ms,
                        tls_cafile=tls_cafile,
                        api_key_env_used=None,
                        classes_target=["REALTIME_STREAMING"],
                        semantic_gate=rt_gate or "LLM_PROBE_SEMANTIC_REALTIME_STREAMING",
                    )
                    patched.append(
                        {
                            "provider_id": provider_id,
                            "model_id": model_id,
                            "probe_kind": "semantic_realtime_handshake",
                            "status": "SKIPPED",
                            "http_status": None,
                        }
                    )
                    # Do not touch state on ACK-required.
                    model_id = None

            if isinstance(model_id, str):
                api_key, api_key_env_used = _resolve_api_key(
                    workspace_root=workspace_root,
                    env_mode=env_mode,
                    expected_env_keys=[
                        str(x) for x in guard.get("expected_env_keys", []) if isinstance(x, str) and x.strip()
                    ],
                )
                timeout_seconds = int(guard.get("timeout_seconds", 30) or 30)

                start = time.monotonic()
                status = "FAIL"
                http_status: int | None = None
                err_code: str | None = None
                err_detail: str | None = None
                try:
                    allowed, allow_reason = live_call_allowed(
                        policy=guardrails,
                        workspace_root=workspace_root,
                        env_mode=env_mode,
                        api_key_present=bool(api_key),
                    )
                    if not allowed:
                        status = "SKIPPED"
                        err_code = allow_reason
                    elif not api_key:
                        status = "SKIPPED"
                        err_code = "API_KEY_MISSING"
                    else:
                        http_status, ok, err_code = _semantic_realtime_handshake_openai(
                            base_url=base_url,
                            api_key=api_key,
                            model_id=model_id,
                            timeout_seconds=timeout_seconds,
                            tls_context=tls_context,
                        )
                        status = "OK" if ok else "FAIL"
                except Exception as exc:
                    err_code = "PROVIDER_REQUEST_FAILED"
                    err_detail = str(exc)[:220]
                    status = "FAIL"
                elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
                now = _now_iso()

                if status in {"OK", "FAIL"}:
                    _upsert_state_probe(
                        state=state,
                        class_id="REALTIME_STREAMING",
                        provider_id=provider_id,
                        model_id=model_id,
                        probe_kind="semantic_realtime_handshake",
                        status=status,
                        error_code=err_code,
                        latency_ms=elapsed_ms,
                        now=now,
                    )
                _patch_report_item(
                    report=report,
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_realtime_handshake",
                    status=status,
                    http_status=http_status,
                    error_code=err_code,
                    error_detail=err_detail,
                    elapsed_ms=elapsed_ms,
                    tls_cafile=tls_cafile,
                    api_key_env_used=api_key_env_used,
                    classes_target=["REALTIME_STREAMING"],
                    semantic_gate=rt_gate or "LLM_PROBE_SEMANTIC_REALTIME_STREAMING",
                )
                patched.append(
                    {
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "probe_kind": "semantic_realtime_handshake",
                        "status": status,
                        "http_status": http_status,
                    }
                )

    # ------------------------------
    # VIDEO_GEN semantic (best-effort)
    # ------------------------------
    # NOTE: Video generation endpoints differ by provider and may be high-cost/side-effect.
    # We keep this probe opt-in per-class; it may remain unsupported per provider.
    vid_enabled, vid_gate = _semantic_probe_gate(workspace_root=workspace_root, env_mode=env_mode, class_id="VIDEO_GEN")
    if vid_enabled:
        ack_ok, ack_key = _semantic_probe_cost_ack(
            workspace_root=workspace_root,
            env_mode=env_mode,
            class_id="VIDEO_GEN",
            required=True,
        )
        provider_id = "openai"
        guard = provider_settings(guardrails, provider_id)
        base_url = providers_by_id.get(provider_id, {}).get("base_url") if isinstance(providers_by_id.get(provider_id), dict) else None
        model_id = _select_allowed_model_id(
            state=state,
            class_id="VIDEO_GEN",
            provider_id=provider_id,
            candidate_models=["sora-2", "sora-2-pro"],
            allow_models=guard.get("allow_models", ["*"]),
            prefer_probe_kind="semantic_video_gen",
        )
        if isinstance(base_url, str) and base_url and isinstance(model_id, str):
            if not ack_ok:
                start = time.monotonic()
                elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
                _patch_report_item(
                    report=report,
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_video_gen",
                    status="SKIPPED",
                    http_status=None,
                    error_code="ACK_REQUIRED",
                    error_detail=str(ack_key or ""),
                    elapsed_ms=elapsed_ms,
                    tls_cafile=tls_cafile,
                    api_key_env_used=None,
                    classes_target=["VIDEO_GEN"],
                    semantic_gate=vid_gate or "LLM_PROBE_SEMANTIC_VIDEO_GEN",
                )
                patched.append(
                    {
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "probe_kind": "semantic_video_gen",
                        "status": "SKIPPED",
                        "http_status": None,
                    }
                )
            else:
                api_key, api_key_env_used = _resolve_api_key(
                    workspace_root=workspace_root,
                    env_mode=env_mode,
                    expected_env_keys=[str(x) for x in guard.get("expected_env_keys", []) if isinstance(x, str) and x.strip()],
                )
                timeout_seconds = int(guard.get("timeout_seconds", 90) or 90)

                start = time.monotonic()
                status = "FAIL"
                http_status: int | None = None
                err_code: str | None = None
                err_detail: str | None = None
                try:
                    allowed, allow_reason = live_call_allowed(
                        policy=guardrails,
                        workspace_root=workspace_root,
                        env_mode=env_mode,
                        api_key_present=bool(api_key),
                    )
                    if not allowed:
                        status = "SKIPPED"
                        err_code = allow_reason
                    elif not api_key:
                        status = "SKIPPED"
                        err_code = "API_KEY_MISSING"
                    else:
                        http_status, ok, err_code = _semantic_video_gen_call_openai_compatible(
                            base_url=base_url,
                            api_key=api_key,
                            model_id=model_id,
                            timeout_seconds=timeout_seconds,
                            tls_context=tls_context,
                        )
                        status = "OK" if ok else "FAIL"
                except error.HTTPError as exc:
                    http_status = int(getattr(exc, "code", 0) or 0)
                    err_detail = _http_error_detail(exc)
                    # Common hard-fail: model gated behind org verification.
                    if http_status == 403 and "organization must be verified" in (err_detail or "").lower():
                        err_code = "ORG_VERIFICATION_REQUIRED"
                    else:
                        err_code = "PROVIDER_HTTP_ERROR"
                    status = "FAIL"
                except Exception as exc:
                    err_code = "PROVIDER_REQUEST_FAILED"
                    err_detail = str(exc)[:220]
                    status = "FAIL"
                elapsed_ms = _bucket_elapsed_ms((time.monotonic() - start) * 1000.0)
                now = _now_iso()

                if status in {"OK", "FAIL"}:
                    _upsert_state_probe(
                        state=state,
                        class_id="VIDEO_GEN",
                        provider_id=provider_id,
                        model_id=model_id,
                        probe_kind="semantic_video_gen",
                        status=status,
                        error_code=err_code,
                        latency_ms=elapsed_ms,
                        now=now,
                    )
                _patch_report_item(
                    report=report,
                    provider_id=provider_id,
                    model_id=model_id,
                    probe_kind="semantic_video_gen",
                    status=status,
                    http_status=http_status,
                    error_code=err_code,
                    error_detail=err_detail,
                    elapsed_ms=elapsed_ms,
                    tls_cafile=tls_cafile,
                    api_key_env_used=api_key_env_used,
                    classes_target=["VIDEO_GEN"],
                    semantic_gate=vid_gate or "LLM_PROBE_SEMANTIC_VIDEO_GEN",
                )
                patched.append(
                    {
                        "provider_id": provider_id,
                        "model_id": model_id,
                        "probe_kind": "semantic_video_gen",
                        "status": status,
                        "http_status": http_status,
                    }
                )

    # Preserve original note if present; else set canonical note (no secrets).
    if not isinstance(report.get("note"), str) or not report.get("note"):
        report["note"] = (
            "Best-effort probe. Chat is used by default; embeddings/moderations/responses are endpoint-aware for "
            "OpenAI-compatible providers. Non-chat families default to /models listing (availability-only; no generation). "
            "Opt-in semantic probes (cost/side-effect prone) are gated by env: LLM_PROBE_SEMANTIC=1 plus "
            "LLM_PROBE_SEMANTIC_<CLASS_ID>=1 (e.g., _OCR_DOC/_AUDIO/_REALTIME_STREAMING/_IMAGE_GEN/_VIDEO_GEN). "
            "All semantic probes also respect provider live gate (KERNEL_API_LLM_LIVE=1)."
        )
    report["version"] = str(report.get("version") or "v0.1")
    report["generated_at"] = _now_iso()
    report["tls_cafile"] = tls_cafile
    if not isinstance(report.get("providers_tested"), list):
        # Keep deterministic provider list for UI.
        report["providers_tested"] = sorted([k for k in providers_by_id.keys() if isinstance(k, str)])

    _write_json_atomic(report_path, report)
    _write_json_atomic(state_path, state)

    return {
        "status": "OK" if all(it.get("status") == "OK" for it in patched) else "WARN",
        "patched": patched,
        "report_path": str(report_path),
        "state_path": str(state_path),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--env-mode", default="dotenv", choices=["dotenv", "process"])
    args = parser.parse_args(argv)

    res = run_allowlist_probe(workspace_root=str(args.workspace_root), env_mode=str(args.env_mode))
    print(json.dumps(res, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
