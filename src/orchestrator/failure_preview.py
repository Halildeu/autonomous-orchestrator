from __future__ import annotations

import json
from typing import Any


def _tail_text(value: Any, *, max_lines: int = 8, max_chars: int = 1200) -> str | None:
    if not isinstance(value, str):
        return None
    lines = [line.rstrip() for line in value.splitlines() if line.strip()]
    if not lines:
        return None
    tail = "\n".join(lines[-max_lines:])
    if len(tail) > max_chars:
        return tail[-max_chars:]
    return tail


def _normalize_cmd(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (list, tuple)):
        parts = [str(part).strip() for part in value if str(part).strip()]
        if parts:
            return " ".join(parts)
    return None


def _normalize_return_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _details_from_exception(exc: Exception) -> dict[str, Any] | None:
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        return details
    try:
        parsed = json.loads(str(exc))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def failure_preview_from_exception(exc: Exception) -> dict[str, Any]:
    preview = {
        "failed_cmd": _normalize_cmd(getattr(exc, "cmd", None)),
        "failed_return_code": _normalize_return_code(getattr(exc, "returncode", None)),
        "failed_stdout_preview": _tail_text(getattr(exc, "stdout", None) or getattr(exc, "output", None)),
        "failed_stderr_preview": _tail_text(getattr(exc, "stderr", None)),
    }

    details = _details_from_exception(exc)
    if isinstance(details, dict):
        cmd = _normalize_cmd(details.get("cmd") or details.get("argv"))
        if cmd is not None:
            preview["failed_cmd"] = cmd
        return_code = _normalize_return_code(details.get("return_code"))
        if return_code is not None:
            preview["failed_return_code"] = return_code
        stdout_preview = _tail_text(details.get("stdout_tail") or details.get("stdout"))
        if stdout_preview is not None:
            preview["failed_stdout_preview"] = stdout_preview
        stderr_preview = _tail_text(details.get("stderr_tail") or details.get("stderr"))
        if stderr_preview is not None:
            preview["failed_stderr_preview"] = stderr_preview

    return preview
