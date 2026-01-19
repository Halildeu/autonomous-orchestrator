"""LLM client helpers for PRJ-KERNEL-API (dry-run, deterministic)."""

from __future__ import annotations

from typing import Any, Dict, List


def build_http_request(
    *,
    provider_id: str,
    base_url: str,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float | None,
    max_tokens: int | None,
    request_id: str | None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    # Some providers reject unknown top-level request fields. Keep request_id for
    # internal correlation only (audit/response), and avoid sending it to these
    # provider APIs.
    if request_id and provider_id not in {"google", "openai", "qwen", "xai"}:
        body["request_id"] = request_id

    return {
        "provider_id": provider_id,
        "method": "POST",
        "url": base_url,
        "headers": {"Authorization": "Bearer ***REDACTED***", "Content-Type": "application/json"},
        "body_json": body,
        "redacted": True,
    }


def live_call_disabled(*, provider_id: str) -> Dict[str, Any]:
    return {"status": "FAIL", "error_code": "LIVE_CALL_DISABLED", "provider_id": provider_id}
