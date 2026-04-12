"""Anthropic Claude provider — Messages API integration via urllib."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.providers.provider import Provider


_SUPPORTED_CAPABILITIES = frozenset(["chat"])
_BASE_URL = "https://api.anthropic.com/v1"
_API_VERSION = "2023-06-01"


from src.providers.response_parser import extract_first_json_object as _extract_first_json_object
from src.providers.structured_output import build_response_format_claude, model_supports_structured_output


def _to_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert generic message list to Anthropic Messages API format.

    Returns (system_prompt, anthropic_messages).
    System role messages are extracted into a separate system parameter.
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = str(msg.get("role") or "").strip()
        content = msg.get("content", "")
        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        system_parts.append(str(part.get("text", "")))
                    elif isinstance(part, str):
                        system_parts.append(part)
            continue
        if role not in ("user", "assistant"):
            continue
        if isinstance(content, str):
            out.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            out.append({"role": role, "content": content})
    system = "\n\n".join(system_parts).strip() if system_parts else None
    return system, out


@dataclass
class ClaudeProvider:
    """Anthropic Claude provider using Messages API."""

    api_key: str
    model: str = "claude-opus-4-5-20251101"
    base_url: str = _BASE_URL
    timeout_s: float = 30.0

    def provider_id(self) -> str:
        return "claude"

    def supports_capability(self, capability: str) -> bool:
        return capability in _SUPPORTED_CAPABILITIES

    def call_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 256,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
        response_schema: dict | None = None,
    ) -> dict[str, Any]:
        system, anthropic_messages = _to_anthropic_messages(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max(1, int(max_tokens)),
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature
        # Structured output: explicit response_format or auto-build from schema
        effective_format = response_format
        if effective_format is None and response_schema is not None:
            effective_format = build_response_format_claude(self.model, response_schema)
        if effective_format is not None:
            body["response_format"] = effective_format

        url = f"{self.base_url.rstrip('/')}/messages"
        req = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": _API_VERSION,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError(f"Claude request failed: {e}") from e

        payload = json.loads(raw)
        text = ""
        for block in payload.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")

        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
        response_id = payload.get("id") if isinstance(payload.get("id"), str) else None

        result: dict[str, Any] = {
            "provider": "claude",
            "model": self.model,
            "text": text,
        }
        if usage:
            result["usage"] = usage
        if response_id:
            result["response_id"] = response_id
        result["provider_state"] = {
            "provider": "claude",
            "wire_api": "messages",
        }
        if response_id:
            result["provider_state"]["last_response_id"] = response_id
        return result

    def summarize_markdown_to_json(
        self, markdown: str, *, continuation: dict[str, Any] | None = None
    ) -> dict:
        messages = [
            {
                "role": "system",
                "content": "Return ONLY valid JSON. Summarize the markdown into: {summary: string, bullets: string[]}.",
            },
            {"role": "user", "content": markdown},
        ]
        result = self.call_chat(messages=messages, max_tokens=512, temperature=0)
        text = result.get("text", "")
        obj = _extract_first_json_object(text)
        if not obj:
            raise RuntimeError("Claude returned non-JSON output.")
        obj["provider"] = "claude"
        obj.setdefault("model", self.model)
        if "usage" in result:
            obj.setdefault("usage", result["usage"])
        if "provider_state" in result:
            obj.setdefault("provider_state", result["provider_state"])
        return obj


class ClaudeDeterministicStubProvider:
    """Offline stub when no API key is available."""

    def provider_id(self) -> str:
        return "claude"

    def supports_capability(self, capability: str) -> bool:
        return capability in _SUPPORTED_CAPABILITIES

    def call_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 256,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        text = ""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    text = content
                break
        digest = sha256(text.encode("utf-8")).hexdigest()
        return {
            "provider": "claude",
            "model": "stub",
            "text": json.dumps({"summary": "stub", "bullets": []}),
            "provider_state": {"provider": "claude", "wire_api": "stub"},
            "stub": True,
            "input_sha256": digest,
        }

    def summarize_markdown_to_json(
        self, markdown: str, *, continuation: dict[str, Any] | None = None
    ) -> dict:
        normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
        digest = sha256(normalized.encode("utf-8")).hexdigest()
        lines = [ln.strip() for ln in normalized.split("\n")]
        headings = [ln.lstrip("#").strip() for ln in lines if ln.startswith("#")]
        bullets = []
        for ln in lines:
            if ln.startswith(("-", "*")):
                item = ln.lstrip("-*").strip()
                if item:
                    bullets.append(item)
                if len(bullets) >= 5:
                    break
        summary = headings[0] if headings else (bullets[0] if bullets else "summary")
        if len(summary) > 120:
            summary = summary[:117] + "..."
        return {
            "provider": "claude",
            "summary": summary,
            "bullets": bullets,
            "stats": {"chars": len(normalized), "lines": len(lines), "sha256": digest},
        }


def get_provider() -> ClaudeProvider | ClaudeDeterministicStubProvider:
    api_key = ""
    for key_name in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        val = os.environ.get(key_name, "").strip()
        if val:
            api_key = val
            break
    if not api_key:
        return ClaudeDeterministicStubProvider()

    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-5-20251101").strip()
    return ClaudeProvider(api_key=api_key, model=model)
