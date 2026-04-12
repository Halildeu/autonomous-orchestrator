"""LLM response normalization — provider-agnostic text + metadata extraction.

Extracted from adapter_llm_actions.py (PR0 seam extraction).
Single responsibility: given raw response bytes, extract text content,
usage info, and (future) tool calls into a normalized dict.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def extract_llm_output_text(resp_bytes: bytes) -> str:
    """Extract text content from provider response bytes.

    Handles:
    - Anthropic Messages API: content[].type=="text"
    - OpenAI Chat Completions: choices[].message.content
    - OpenAI Responses API: output[].content[].text / output_text
    - Fallback: raw UTF-8 text
    """
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

    # OpenAI Chat Completions: {"choices":[{"message":{"content":"..."}}]}
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

    # OpenAI Responses API: {"output":[{"content":[{"text":"..."}]}]}
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


def extract_usage(resp_bytes: bytes) -> Dict[str, Any] | None:
    """Extract token usage from provider response.

    Returns dict with input_tokens, output_tokens or None.
    """
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return None

    if not isinstance(obj, dict):
        return None

    usage = obj.get("usage")
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens") or 0,
            "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens") or 0,
        }
    return None


def normalize_response(
    resp_bytes: bytes,
    *,
    provider_id: str,
) -> Dict[str, Any]:
    """Normalize a provider response into a standard dict.

    Returns: {text, usage, raw_json, provider_id}
    Future PRs will add: tool_calls, parsed_json, validation_errors
    """
    text = extract_llm_output_text(resp_bytes)
    usage = extract_usage(resp_bytes)

    raw_json: dict[str, Any] | None = None
    try:
        parsed = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
        if isinstance(parsed, dict):
            raw_json = parsed
    except Exception:
        pass

    return {
        "text": text,
        "usage": usage,
        "raw_json": raw_json,
        "provider_id": provider_id,
    }
