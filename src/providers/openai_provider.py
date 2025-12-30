from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from src.providers.provider import Provider


def _extract_first_json_object(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
        return None
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        value = json.loads(m.group(0))
        if isinstance(value, dict):
            return value
        return None
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class DeterministicStubProvider(Provider):
    max_bullets: int = 5

    def summarize_markdown_to_json(self, markdown: str) -> dict:
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
            if len(bullets) >= self.max_bullets:
                break

        summary = headings[0] if headings else (bullets[0] if bullets else "summary")
        if len(summary) > 120:
            summary = summary[:117] + "..."

        return {
            "provider": "stub",
            "summary": summary,
            "bullets": bullets,
            "stats": {
                "chars": len(normalized),
                "lines": len(lines),
                "sha256": digest,
            },
        }


class OpenAIProvider(Provider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def summarize_markdown_to_json(self, markdown: str) -> dict:
        url = f"{self._base_url}/responses"
        body: dict[str, Any] = {
            "model": self._model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "Return ONLY valid JSON. Summarize the markdown into: {summary: string, bullets: string[]}."
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": markdown}],
                },
            ],
            "temperature": 0,
        }

        req = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError(f"OpenAI request failed: {e}") from e

        payload = json.loads(raw)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
        response_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        text = ""
        for item in payload.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")

        obj = _extract_first_json_object(text)
        if not obj:
            raise RuntimeError("OpenAI returned non-JSON output.")

        obj["provider"] = "openai"
        obj.setdefault("model", self._model)
        if usage is not None:
            obj.setdefault("usage", usage)
        if response_id:
            obj.setdefault("response_id", response_id)
        return obj


def get_provider() -> Provider:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return DeterministicStubProvider()

    model = os.environ.get("OPENAI_MODEL", "gpt-5.2-codex").strip() or "gpt-5.2-codex"
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    try:
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
    except Exception:
        return DeterministicStubProvider()
