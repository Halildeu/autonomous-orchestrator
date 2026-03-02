from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List
from urllib import error

from src.prj_kernel_api.provider_guardrails import live_call_allowed, load_guardrails, model_allowed, provider_settings

from src.prj_kernel_api.llm_allowlist_probe import (
    REPORT_PATH,
    STATE_PATH,
    _bucket_elapsed_ms,
    _build_tls_context,
    _http_error_detail,
    _load_json_optional,
    _now_iso,
    _patch_report_item,
    _providers_registry_by_id,
    _qwen_semantic_ocr_call,
    _resolve_api_key,
    _resolve_tls_cafile,
    _select_allowed_model_id,
    _semantic_audio_call_openai_compatible,
    _semantic_image_gen_call,
    _semantic_probe_cost_ack,
    _semantic_probe_gate,
    _semantic_realtime_handshake_openai,
    _semantic_video_gen_call_openai_compatible,
    _upsert_state_probe,
    _write_json_atomic,
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
