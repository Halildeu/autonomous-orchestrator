from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_fixture(path_value: str | None) -> tuple[dict[str, Any], str | None]:
    """Load a local fixture. No network or gh process is used in BOG-3B."""
    raw = str(path_value or "").strip()
    if not raw:
        return (
            {
                "version": "v1",
                "repo": "",
                "board_title": "",
                "issues": [],
                "board_items": [],
                "pull_requests": [],
                "notes": ["NO_FIXTURE_PROVIDED"],
            },
            None,
        )
    path = Path(raw)
    if not path.exists():
        return ({}, f"fixture not found: {path.as_posix()}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ({}, f"fixture json parse failed: {exc.__class__.__name__}")
    if not isinstance(obj, dict):
        return ({}, "fixture root must be object")
    if bool(obj.get("gh_json_malformed")):
        return ({}, "fixture simulates malformed gh JSON")
    return (obj, None)

