from __future__ import annotations

import src.prj_kernel_api.llm_live_probe as _core

for _name in dir(_core):
    if _name.startswith("__"):
        continue
    globals().setdefault(_name, getattr(_core, _name))


def run_live_probe(
    *,
    workspace_root: str,
    detail: bool = False,
    env_mode: str = "dotenv",
) -> Tuple[str, str | None, Dict[str, Any]]:
    policy = _load_policy(workspace_root)
    known_skip_rules, known_http_skip_rules, known_skip_policy_path = _load_known_skip_policy(workspace_root)
    live_enabled = _live_enabled(policy, workspace_root, env_mode=env_mode)
    enabled_families = _policy_enabled_families(policy)
    known_skip_hits = 0

    paths = ensure_providers_registry(workspace_root)
    registry = read_registry(Path(paths["providers_path"]))
    read_policy(Path(paths["policy_path"]))
    guardrails = load_guardrails(workspace_root)

    allowed = policy.get("allowed_providers") if isinstance(policy.get("allowed_providers"), list) else []
    max_calls = policy.get("max_calls_per_run")
    timeout_ms = policy.get("timeout_ms")
    max_output_chars = policy.get("max_output_chars")
    max_calls_value = int(max_calls) if isinstance(max_calls, int) and max_calls >= 0 else 0
    timeout_value = int(timeout_ms) if isinstance(timeout_ms, int) and timeout_ms > 0 else 5000
    output_limit = int(max_output_chars) if isinstance(max_output_chars, int) and max_output_chars >= 0 else 0
    timeout_seconds = float(timeout_value) / 1000.0

    providers = registry.get("providers") if isinstance(registry.get("providers"), list) else []
    providers_sorted = sorted(
        [p for p in providers if isinstance(p, dict)],
        key=lambda p: str(p.get("id", "")),
    )
    providers_sorted.sort(key=lambda p: (0 if str(p.get("id", "")) == "openai" else 1, str(p.get("id", ""))))

    results: List[Dict[str, Any]] = []
    attempted = 0
    ok_count = 0
    fail_count = 0
    skipped_count = 0

    for provider in providers_sorted:
        provider_id = provider.get("id")
        if not isinstance(provider_id, str):
            continue

        guard = provider_settings(guardrails, provider_id)
        guard_timeout_seconds = guard.get("timeout_seconds")
        guard_timeout_seconds = (
            float(guard_timeout_seconds)
            if isinstance(guard_timeout_seconds, (int, float)) and float(guard_timeout_seconds) > 0
            else None
        )
        provider_timeout_seconds = provider.get("timeout_seconds")
        provider_timeout_seconds = (
            float(provider_timeout_seconds)
            if isinstance(provider_timeout_seconds, (int, float)) and float(provider_timeout_seconds) > 0
            else None
        )
        targets = _model_targets_for_provider(provider_id, provider=provider, guard=guard) or [""]

        provider_skip_code: str | None = None
        if not live_enabled:
            provider_skip_code = "LIVE_DISABLED"
        elif not _provider_allowed(provider_id, allowed):
            provider_skip_code = "PROVIDER_NOT_ALLOWED"
        elif not bool(provider.get("enabled", False)) or not bool(guard.get("enabled", False)):
            provider_skip_code = "PROVIDER_DISABLED"

        base_url = provider.get("base_url") if isinstance(provider.get("base_url"), str) else None
        if provider_skip_code is None and not base_url:
            provider_skip_code = "PROVIDER_CONFIG_MISSING"

        expected_env_keys = guard.get("expected_env_keys", [])
        if not isinstance(expected_env_keys, list):
            expected_env_keys = []
        expected_env_keys = [str(x) for x in expected_env_keys if isinstance(x, str) and x.strip()]
        api_key_env = provider.get("api_key_env") if isinstance(provider.get("api_key_env"), str) else ""
        if not expected_env_keys and api_key_env:
            expected_env_keys = [api_key_env]

        api_key_value: str | None = None
        api_key_used: str | None = None
        if provider_skip_code is None:
            for key_name in expected_env_keys:
                api_key_present, candidate_value = resolve_env_value(key_name, workspace_root, env_mode=env_mode)
                if api_key_present and candidate_value:
                    api_key_value = candidate_value
                    api_key_used = key_name
                    break

        tls_cafile = _resolve_tls_cafile()
        tls_context = _build_tls_context(tls_cafile)

        if provider_skip_code is None and not api_key_value:
            provider_skip_code = "API_KEY_MISSING"

        if provider_skip_code is not None:
            for model_id in targets:
                results.append(
                    {
                        "provider_id": provider_id,
                        "status": "SKIPPED",
                        "error_code": provider_skip_code,
                        "model": model_id or None,
                        "probe_family": _infer_probe_family(model_id) if isinstance(model_id, str) and model_id else None,
                        "probe_url": None,
                        "http_status": None,
                        "elapsed_ms": None,
                        "tls_cafile": tls_cafile,
                        "error_type": None,
                        "error_detail": None,
                        "api_key_env": api_key_env,
                        "api_key_env_used": api_key_used,
                        "expected_env_keys": expected_env_keys,
                    }
                )
                skipped_count += 1
            continue

        for model_id in targets:
            entry: Dict[str, Any] = {
                "provider_id": provider_id,
                "status": "SKIPPED",
                "error_code": None,
                "model": model_id or None,
                "probe_family": None,
                "probe_url": None,
                "http_status": None,
                "elapsed_ms": None,
                "tls_cafile": tls_cafile,
                "error_type": None,
                "error_detail": None,
                "api_key_env": api_key_env,
                "api_key_env_used": api_key_used,
                "expected_env_keys": expected_env_keys,
            }

            if not isinstance(model_id, str) or not model_id.strip():
                entry["error_code"] = "MODEL_REQUIRED"
                results.append(entry)
                skipped_count += 1
                continue

            probe_family = _infer_probe_family(model_id)
            entry["probe_family"] = probe_family

            if probe_family not in enabled_families:
                entry["error_code"] = "PROBE_FAMILY_DISABLED"
                results.append(entry)
                skipped_count += 1
                continue

            if not model_allowed(model_id, guard.get("allow_models", ["*"])):
                entry["error_code"] = "MODEL_NOT_ALLOWED"
                results.append(entry)
                skipped_count += 1
                continue

            known_skip_rule = _match_known_skip_rule(
                known_skip_rules,
                provider_id=provider_id,
                model_id=model_id,
                probe_family=probe_family,
            )
            if isinstance(known_skip_rule, dict):
                reason = str(known_skip_rule.get("reason") or "policy_rule").strip()
                rule_id = str(known_skip_rule.get("rule_id") or "").strip()
                detail = f"preflight_skip:known_skip_policy:{reason}"
                if rule_id:
                    detail = f"{detail}:{rule_id}"
                entry["status"] = "SKIPPED"
                entry["error_code"] = str(known_skip_rule.get("error_code") or "KNOWN_SKIP_POLICY")
                entry["error_detail"] = detail
                entry["known_skip_policy"] = {
                    "reason": reason,
                    "rule_id": rule_id or None,
                }
                skipped_count += 1
                known_skip_hits += 1
                results.append(entry)
                continue

            if max_calls_value and attempted >= max_calls_value:
                entry["error_code"] = "MAX_CALLS_REACHED"
                results.append(entry)
                skipped_count += 1
                continue

            start = time.monotonic()
            try:
                call_timeout_seconds = timeout_seconds
                if provider_id == "claude":
                    if probe_family != "chat":
                        entry["error_code"] = "PROVIDER_FAMILY_UNSUPPORTED"
                        results.append(entry)
                        skipped_count += 1
                        continue

                    attempted += 1
                    entry["probe_url"] = base_url
                    headers = {
                        "Content-Type": "application/json",
                        "x-api-key": api_key_value,
                        "anthropic-version": "2023-06-01",
                    }
                    payload = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 8,
                    }
                    http_status, _data = _http_post_json(
                        url=base_url,
                        headers=headers,
                        payload=payload,
                        timeout_seconds=max(
                            call_timeout_seconds,
                            guard_timeout_seconds or 0.0,
                            provider_timeout_seconds or 0.0,
                        ),
                        tls_context=tls_context,
                        max_bytes=_PROBE_READ_MAX_BYTES,
                    )
                    entry["http_status"] = http_status
                    entry["status"] = "OK" if http_status == 200 else "FAIL"
                    if http_status == 200:
                        ok_count += 1
                    else:
                        fail_count += 1
                        entry["error_code"] = "PROVIDER_HTTP_ERROR"
                else:
                    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key_value}"}
                    if provider_id == "xai":
                        headers["Accept"] = "application/json"
                        headers["User-Agent"] = _XAI_USER_AGENT

                    if probe_family == "realtime":
                        if provider_id != "openai":
                            entry["error_code"] = "PROVIDER_FAMILY_UNSUPPORTED"
                            skipped_count += 1
                            continue
                        attempted += 1
                        entry["probe_url"] = "wss://(derived)/v1/realtime"
                        http_status, ok, err_code = _semantic_realtime_handshake_openai(
                            base_url=base_url,
                            api_key=api_key_value,
                            model_id=model_id,
                            timeout_seconds=max(
                                call_timeout_seconds,
                                guard_timeout_seconds or 0.0,
                                provider_timeout_seconds or 0.0,
                            ),
                            tls_context=tls_context,
                        )
                        entry["http_status"] = http_status or None
                        if ok:
                            entry["status"] = "OK"
                            ok_count += 1
                        else:
                            entry["status"] = "FAIL"
                            entry["error_code"] = err_code or "PROVIDER_REQUEST_FAILED"
                            fail_count += 1
                        continue

                    if probe_family == "video_gen":
                        if provider_id != "openai":
                            entry["error_code"] = "PROVIDER_FAMILY_UNSUPPORTED"
                            skipped_count += 1
                            continue

                        if not _env_flag_enabled("LLM_PROBE_SEMANTIC", workspace_root, env_mode=env_mode):
                            entry["error_code"] = "VIDEO_GEN_GATE_DISABLED"
                            skipped_count += 1
                            continue
                        if not _env_flag_enabled("LLM_PROBE_SEMANTIC_VIDEO_GEN", workspace_root, env_mode=env_mode):
                            entry["error_code"] = "VIDEO_GEN_GATE_DISABLED"
                            skipped_count += 1
                            continue
                        if not _env_flag_enabled("LLM_PROBE_SEMANTIC_VIDEO_GEN_ACK", workspace_root, env_mode=env_mode):
                            entry["error_code"] = "VIDEO_GEN_ACK_REQUIRED"
                            skipped_count += 1
                            continue

                        root = _derive_openai_compatible_root(base_url)
                        if not root:
                            entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                            skipped_count += 1
                            continue

                        last_http_status: int | None = None
                        for path in _VIDEO_GEN_ENDPOINT_CANDIDATES:
                            if max_calls_value and attempted >= max_calls_value:
                                entry["error_code"] = "MAX_CALLS_REACHED"
                                skipped_count += 1
                                break

                            attempted += 1
                            url = root + path
                            entry["probe_url"] = url

                            payload = {
                                "model": model_id,
                                "prompt": _VIDEO_GEN_PROMPT,
                            }

                            try:
                                http_status, data = _http_post_json(
                                    url=url,
                                    headers=headers,
                                    payload=payload,
                                    timeout_seconds=max(
                                        call_timeout_seconds,
                                        guard_timeout_seconds or 0.0,
                                        provider_timeout_seconds or 0.0,
                                    ),
                                    tls_context=tls_context,
                                    max_bytes=_PROBE_READ_MAX_BYTES,
                                )
                            except error.HTTPError as exc:
                                http_status = int(getattr(exc, "code", 0) or 0)
                                last_http_status = http_status
                                entry["http_status"] = http_status
                                entry["error_type"] = exc.__class__.__name__
                                entry["error_detail"] = _http_error_detail(exc, max_chars=220)
                                if http_status in {404, 405}:
                                    continue
                                entry["status"] = "FAIL"
                                entry["error_code"] = "PROVIDER_HTTP_ERROR"
                                fail_count += 1
                                http_skip_rule = _match_known_http_skip_rule(
                                    known_http_skip_rules,
                                    provider_id=provider_id,
                                    model_id=model_id,
                                    probe_family=probe_family,
                                    http_status=http_status,
                                    error_detail=str(entry.get("error_detail") or ""),
                                )
                                if isinstance(http_skip_rule, dict):
                                    reason = str(http_skip_rule.get("reason") or "policy_rule").strip()
                                    rule_id = str(http_skip_rule.get("rule_id") or "").strip()
                                    detail = f"http_skip:known_skip_policy:{reason}"
                                    if rule_id:
                                        detail = f"{detail}:{rule_id}"
                                    entry["status"] = "SKIPPED"
                                    entry["error_code"] = str(http_skip_rule.get("error_code") or "KNOWN_SKIP_POLICY")
                                    entry["error_detail"] = detail
                                    entry["known_skip_policy"] = {
                                        "reason": reason,
                                        "rule_id": rule_id or None,
                                    }
                                    fail_count -= 1
                                    skipped_count += 1
                                    known_skip_hits += 1
                                break
                            except Exception as exc:
                                entry["status"] = "FAIL"
                                entry["error_code"] = "PROVIDER_REQUEST_FAILED"
                                entry["error_type"] = exc.__class__.__name__
                                entry["error_detail"] = str(exc)[:220]
                                fail_count += 1
                                break

                            entry["http_status"] = http_status
                            last_http_status = http_status
                            if http_status not in {200, 201, 202}:
                                entry["status"] = "FAIL"
                                entry["error_code"] = "PROVIDER_HTTP_ERROR"
                                fail_count += 1
                                break

                            job_id = data.get("id")
                            if not isinstance(job_id, str) or not job_id:
                                entry["status"] = "FAIL"
                                entry["error_code"] = "VIDEO_GEN_NO_JOB_DATA"
                                fail_count += 1
                                break

                            poll_url = root + f"/videos/{job_id}"
                            entry["probe_url"] = poll_url
                            poll_timeout_seconds = max(
                                10.0,
                                min(
                                    max(
                                        call_timeout_seconds,
                                        guard_timeout_seconds or 0.0,
                                        provider_timeout_seconds or 0.0,
                                    ),
                                    _VIDEO_GEN_POLL_MAX_SECONDS,
                                ),
                            )
                            poll_deadline = time.monotonic() + poll_timeout_seconds
                            last_poll_status: str | None = None
                            poll_done = False
                            poll_attempts = 0

                            while time.monotonic() < poll_deadline and poll_attempts < _VIDEO_GEN_MAX_POLLS_PER_JOB:
                                poll_attempts += 1

                                try:
                                    poll_http_status, poll_data = _http_get_json(
                                        url=poll_url,
                                        headers=headers,
                                        timeout_seconds=max(
                                            call_timeout_seconds,
                                            guard_timeout_seconds or 0.0,
                                            provider_timeout_seconds or 0.0,
                                        ),
                                        tls_context=tls_context,
                                        max_bytes=_PROBE_READ_MAX_BYTES,
                                    )
                                except error.HTTPError as exc:
                                    poll_http_status = int(getattr(exc, "code", 0) or 0)
                                    entry["http_status"] = poll_http_status
                                    entry["error_type"] = exc.__class__.__name__
                                    entry["error_detail"] = _http_error_detail(exc, max_chars=220)
                                    if poll_http_status in {404, 405}:
                                        entry["status"] = "SKIPPED"
                                        entry["error_code"] = "VIDEO_GEN_POLL_ENDPOINT_UNSUPPORTED"
                                        skipped_count += 1
                                    else:
                                        entry["status"] = "FAIL"
                                        entry["error_code"] = "PROVIDER_HTTP_ERROR"
                                        fail_count += 1
                                    poll_done = True
                                    break
                                except Exception as exc:
                                    entry["status"] = "FAIL"
                                    entry["error_code"] = "PROVIDER_REQUEST_FAILED"
                                    entry["error_type"] = exc.__class__.__name__
                                    entry["error_detail"] = str(exc)[:220]
                                    fail_count += 1
                                    poll_done = True
                                    break

                                entry["http_status"] = poll_http_status
                                if poll_http_status != 200:
                                    entry["status"] = "FAIL"
                                    entry["error_code"] = "PROVIDER_HTTP_ERROR"
                                    fail_count += 1
                                    poll_done = True
                                    break

                                status_text = str(poll_data.get("status") or "").strip().lower()
                                last_poll_status = status_text or None
                                if status_text in _VIDEO_GEN_SUCCESS_STATUSES:
                                    entry["status"] = "OK"
                                    entry["error_code"] = None
                                    ok_count += 1
                                    poll_done = True
                                    break
                                if status_text in _VIDEO_GEN_FAILURE_STATUSES:
                                    entry["status"] = "FAIL"
                                    entry["error_code"] = "VIDEO_GEN_JOB_FAILED"
                                    fail_count += 1
                                    poll_done = True
                                    break
                                time.sleep(_VIDEO_GEN_POLL_INTERVAL_SECONDS)

                            entry["video_poll_attempts"] = poll_attempts
                            if not poll_done:
                                entry["status"] = "SKIPPED"
                                entry["error_code"] = "VIDEO_GEN_POLL_TIMEOUT"
                                if last_poll_status:
                                    entry["error_detail"] = f"last_status={last_poll_status}"
                                skipped_count += 1
                            break

                        if entry["status"] == "SKIPPED" and entry.get("error_code") is None:
                            entry["http_status"] = last_http_status
                            entry["error_code"] = "VIDEO_GEN_ENDPOINT_UNSUPPORTED"
                            skipped_count += 1
                        continue

                    url = base_url
                    payload: Dict[str, Any]

                    if (
                        provider_id == "google"
                        and probe_family == "image_gen"
                        and model_id.strip().lower() in _GOOGLE_IMAGE_GEN_PRECHECK_UNSUPPORTED
                    ):
                        native_root = _derive_google_native_root(base_url)
                        entry["probe_url"] = (
                            f"{native_root}/models/{model_id}:generateContent" if isinstance(native_root, str) else None
                        )
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "MODEL_NOT_SUPPORTED_FOR_ENDPOINT"
                        entry["error_detail"] = "preflight_skip:google_image_gen_model_matrix"
                        skipped_count += 1
                        results.append(entry)
                        continue

                    if (
                        provider_id == "qwen"
                        and model_id.strip().lower() in _QWEN_HTTP_PRECHECK_UNSUPPORTED
                    ):
                        entry["probe_url"] = base_url
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "PROVIDER_HTTP_UNSUPPORTED_FOR_MODEL"
                        entry["error_detail"] = "preflight_skip:qwen_transport_http_unsupported"
                        skipped_count += 1
                        results.append(entry)
                        continue

                    if provider_id == "google" and probe_family in {"image_gen", "audio"}:
                        native_root = _derive_google_native_root(base_url)
                        if not native_root:
                            entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                            results.append(entry)
                            skipped_count += 1
                            continue
                        url = f"{native_root}/models/{model_id}:generateContent"
                        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key_value}
                        if probe_family == "image_gen":
                            payload = {
                                "contents": [
                                    {
                                        "role": "user",
                                        "parts": [{"text": "Generate a simple image that contains the text 'HELLO'."}],
                                    }
                                ],
                                "generationConfig": {"responseModalities": ["IMAGE"]},
                            }
                        else:
                            payload = {
                                "contents": [
                                    {
                                        "role": "user",
                                        "parts": [{"text": "Say 'hello'."}],
                                    }
                                ],
                                "generationConfig": {"responseModalities": ["AUDIO"]},
                            }
                    elif probe_family == "embeddings":
                        if provider_id == "google":
                            native_root = _derive_google_native_root(base_url)
                            if not native_root:
                                entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                                results.append(entry)
                                skipped_count += 1
                                continue
                            url = f"{native_root}/models/{model_id}:embedContent"
                            headers = {"Content-Type": "application/json", "x-goog-api-key": api_key_value}
                            payload = {
                                "content": {"parts": [{"text": "ping"}]},
                                "taskType": "SEMANTIC_SIMILARITY",
                            }
                        else:
                            root = _derive_openai_compatible_root(base_url)
                            if not root:
                                entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                                results.append(entry)
                                skipped_count += 1
                                continue
                            url = root + "/embeddings"
                            payload = {"model": model_id, "input": "ping"}
                    elif probe_family == "moderation":
                        root = _derive_openai_compatible_root(base_url)
                        if not root:
                            entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                            results.append(entry)
                            skipped_count += 1
                            continue
                        url = root + "/moderations"
                        payload = {"model": model_id, "input": "ping"}
                    elif probe_family == "image_gen":
                        root = _derive_openai_compatible_root(base_url)
                        if not root:
                            entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                            results.append(entry)
                            skipped_count += 1
                            continue
                        url = root + "/images/generations"
                        payload = {
                            "model": model_id,
                            "prompt": "Generate a simple image that contains the text 'HELLO'.",
                            "n": 1,
                        }
                        if provider_id != "xai":
                            if provider_id == "openai":
                                payload["size"] = "1024x1024"
                            else:
                                payload["size"] = "256x256"
                    elif probe_family == "audio":
                        audio_format = "wav" if provider_id == "google" else "mp3"
                        payload = {
                            "model": model_id,
                            "messages": [{"role": "user", "content": "Say 'hello'."}],
                            "max_tokens": 16,
                            "stream": False,
                            "modalities": ["text", "audio"],
                            "audio": {"voice": "alloy", "format": audio_format},
                        }
                    elif probe_family == "vision":
                        payload = {
                            "model": model_id,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "What is in this image? Reply briefly."},
                                        {"type": "image_url", "image_url": {"url": _VISION_PROBE_IMAGE_DATA_URL}},
                                    ],
                                }
                            ],
                            "max_tokens": 32,
                        }
                    else:
                        if provider_id == "openai" and "codex" in model_id:
                            root = _derive_openai_compatible_root(base_url)
                            if not root:
                                entry["error_code"] = "PROVIDER_BASE_URL_UNSUPPORTED"
                                results.append(entry)
                                skipped_count += 1
                                continue
                            url = root + "/responses"
                            payload = {
                                "model": model_id,
                                "input": "Say pong.",
                                "max_output_tokens": 64,
                            }
                        elif provider_id == "openai" and model_id.startswith("gpt-5"):
                            payload = {
                                "model": model_id,
                                "messages": [{"role": "user", "content": "ping"}],
                                "max_completion_tokens": 128,
                            }
                        else:
                            max_tokens = 8
                            lowered = model_id.lower()
                            if any(tok in lowered for tok in ("thinking", "reasoner", "reasoning")):
                                max_tokens = 1
                                call_timeout_seconds = max(
                                    call_timeout_seconds,
                                    guard_timeout_seconds or 0.0,
                                    provider_timeout_seconds or 0.0,
                                )
                            payload = {
                                "model": model_id,
                                "messages": [{"role": "user", "content": "ping"}],
                                "temperature": 0,
                                "max_tokens": max_tokens,
                            }

                    attempted += 1
                    entry["probe_url"] = url
                    http_status, data = _http_post_json(
                        url=url,
                        headers=headers,
                        payload=payload,
                        timeout_seconds=call_timeout_seconds,
                        tls_context=tls_context,
                        max_bytes=max(_PROBE_READ_MAX_BYTES, output_limit or 0),
                    )
                    entry["http_status"] = http_status

                    if http_status != 200:
                        entry["status"] = "FAIL"
                        entry["error_code"] = "PROVIDER_HTTP_ERROR"
                        fail_count += 1
                    else:
                        ok = True
                        if probe_family == "embeddings":
                            ok = False
                            if provider_id == "google":
                                vec = _google_embedding_values(data)
                                ok = isinstance(vec, list) and len(vec) > 0
                            else:
                                items = data.get("data") if isinstance(data.get("data"), list) else []
                                if items and isinstance(items[0], dict):
                                    vec = items[0].get("embedding")
                                    ok = isinstance(vec, list) and len(vec) > 0
                            if not ok:
                                entry["error_code"] = "EMBEDDINGS_NO_VECTOR"
                        elif probe_family == "moderation":
                            ok = False
                            results_list = data.get("results") if isinstance(data.get("results"), list) else []
                            ok = bool(results_list)
                            if not ok:
                                entry["error_code"] = "MODERATION_NO_RESULTS"
                        elif probe_family == "image_gen":
                            ok = False
                            if provider_id == "google":
                                inline = _google_generatecontent_inline_part(data)
                                ok = bool(inline and str(inline.get("mimeType") or "").lower().startswith("image/"))
                            else:
                                items = data.get("data") if isinstance(data.get("data"), list) else []
                                if items and isinstance(items[0], dict):
                                    ok = bool(items[0].get("b64_json") or items[0].get("url") or items[0].get("id"))
                            if not ok:
                                entry["error_code"] = "IMAGE_GEN_NO_IMAGE_DATA"
                        elif probe_family == "audio":
                            ok = False
                            if provider_id == "google":
                                inline = _google_generatecontent_inline_part(data)
                                ok = bool(inline and str(inline.get("mimeType") or "").lower().startswith("audio/"))
                            else:
                                choices = data.get("choices") if isinstance(data.get("choices"), list) else []
                                if choices and isinstance(choices[0], dict):
                                    msg = (
                                        choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
                                    )
                                    audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
                                    if audio and isinstance(audio.get("data"), str) and audio.get("data"):
                                        ok = True
                            if not ok:
                                entry["error_code"] = "AUDIO_NO_AUDIO_DATA"
                        elif provider_id == "openai" and "codex" in model_id:
                            ok = False
                            rid = data.get("id")
                            status_txt = str(data.get("status") or "").strip().lower()
                            ok = bool(isinstance(rid, str) and rid.strip() and status_txt == "completed")
                            if not ok:
                                entry["error_code"] = "RESPONSES_NO_COMPLETION"

                        if ok:
                            entry["status"] = "OK"
                            ok_count += 1
                            entry["error_code"] = None
                        else:
                            entry["status"] = "FAIL"
                            fail_count += 1
            except error.HTTPError as exc:
                entry["http_status"] = int(getattr(exc, "code", 0) or 0)
                http_status = int(entry["http_status"] or 0)
                entry["status"] = "FAIL"
                entry["error_code"] = "PROVIDER_HTTP_ERROR"
                entry["error_type"] = exc.__class__.__name__
                entry["error_detail"] = _http_error_detail(exc, max_chars=220)
                fail_count += 1

                detail = str(entry.get("error_detail") or "").lower()
                if probe_family == "image_gen" and provider_id == "google" and http_status == 404:
                    entry["status"] = "SKIPPED"
                    entry["error_code"] = "MODEL_NOT_SUPPORTED_FOR_ENDPOINT"
                    fail_count -= 1
                    skipped_count += 1
                elif probe_family == "audio" and provider_id == "google" and http_status == 400:
                    if "response modalities" in detail or "modalities" in detail:
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "AUDIO_MODALITIES_UNSUPPORTED"
                        fail_count -= 1
                        skipped_count += 1
                elif probe_family == "embeddings" and provider_id == "google" and http_status == 404:
                    if "is not found" in detail or "not supported for embedcontent" in detail:
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "MODEL_NOT_SUPPORTED_FOR_ENDPOINT"
                        fail_count -= 1
                        skipped_count += 1
                elif probe_family == "image_gen" and provider_id == "openai" and http_status == 403:
                    if "organization must be verified" in detail or "must be verified" in detail:
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "ORG_VERIFICATION_REQUIRED"
                        fail_count -= 1
                        skipped_count += 1
                elif provider_id == "qwen" and model_id == "qvq-max" and http_status in {400, 403}:
                    if "does not support http call" in detail:
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "PROVIDER_HTTP_UNSUPPORTED_FOR_MODEL"
                        fail_count -= 1
                        skipped_count += 1
                if entry.get("status") == "FAIL":
                    http_skip_rule = _match_known_http_skip_rule(
                        known_http_skip_rules,
                        provider_id=provider_id,
                        model_id=model_id,
                        probe_family=probe_family,
                        http_status=http_status,
                        error_detail=str(entry.get("error_detail") or ""),
                    )
                    if isinstance(http_skip_rule, dict):
                        reason = str(http_skip_rule.get("reason") or "policy_rule").strip()
                        rule_id = str(http_skip_rule.get("rule_id") or "").strip()
                        detail = f"http_skip:known_skip_policy:{reason}"
                        if rule_id:
                            detail = f"{detail}:{rule_id}"
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = str(http_skip_rule.get("error_code") or "KNOWN_SKIP_POLICY")
                        entry["error_detail"] = detail
                        entry["known_skip_policy"] = {
                            "reason": reason,
                            "rule_id": rule_id or None,
                        }
                        fail_count -= 1
                        skipped_count += 1
                        known_skip_hits += 1
            except Exception as exc:
                entry["status"] = "FAIL"
                entry["error_code"] = "PROVIDER_REQUEST_FAILED"
                entry["error_type"] = exc.__class__.__name__
                entry["error_detail"] = str(exc)[:220]
                fail_count += 1

                detail = str(entry.get("error_detail") or "").lower()
                if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in detail:
                    lowered = model_id.lower() if isinstance(model_id, str) else ""
                    if any(tok in lowered for tok in ("thinking", "reasoner", "reasoning")):
                        entry["status"] = "SKIPPED"
                        entry["error_code"] = "PROBE_TIMEOUT"
                        fail_count -= 1
                        skipped_count += 1
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000.0
                entry["elapsed_ms"] = _bucket_elapsed_ms(elapsed_ms)
                results.append(entry)

    status = "OK" if fail_count == 0 else "WARN"
    report = {
        "version": "v1",
        "workspace_root": workspace_root,
        "status": status,
        "known_skip_policy_path": known_skip_policy_path,
        "known_skip_hits": known_skip_hits,
        "enabled_probe_families": enabled_families,
        "attempted": attempted,
        "ok": ok_count,
        "fail": fail_count,
        "skipped": skipped_count,
        "providers": results,
        "preview_sha256": _preview_hash(
            {
                "allowed": allowed,
                "enabled_probe_families": enabled_families,
                "attempted": attempted,
                "ok": ok_count,
                "fail": fail_count,
                "skipped": skipped_count,
            }
        ),
    }

    if detail:
        report["policy"] = {
            "allowed_providers": allowed,
            "enabled_probe_families": enabled_families,
            "max_calls_per_run": max_calls_value,
            "timeout_ms": timeout_value,
        }

    _write_json_atomic(Path(workspace_root) / REPORT_PATH, report)
    return status, None, report
