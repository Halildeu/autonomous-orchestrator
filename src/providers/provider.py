from __future__ import annotations

from typing import Protocol


class Provider(Protocol):
    def summarize_markdown_to_json(self, markdown: str) -> dict:
        """Return a JSON-serializable summary dict."""

