from __future__ import annotations

from typing import Any

from src.ops.board.models import KINDS, PRIORITIES, STATUSES, TRACKS


def _labels(item: dict[str, Any]) -> set[str]:
    raw = item.get("labels")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if isinstance(x, str)}


def _fields(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("fields")
    return raw if isinstance(raw, dict) else {}


def _issue_number(item: dict[str, Any]) -> int | None:
    raw = item.get("issue_number")
    try:
        value = int(raw)
    except Exception:
        return None
    return value if value > 0 else None


def _drift(code: str, severity: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {"code": code, "severity": severity, "message": message}
    payload.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    return payload


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = (
            str(item.get("code") or ""),
            str(item.get("severity") or ""),
            str(item.get("issue_number") or ""),
            str(item.get("message") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def derive_projection_drift(projection: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive deterministic board projection drift from observed and expected items."""
    existing = projection.get("drift") if isinstance(projection.get("drift"), list) else []
    drift = [item for item in existing if isinstance(item, dict)]
    field_contract = projection.get("field_contract") if isinstance(projection.get("field_contract"), dict) else {}
    required_fields = field_contract.get("required_fields") if isinstance(field_contract.get("required_fields"), list) else []
    required_fields = [str(x) for x in required_fields if isinstance(x, str)]
    expected = projection.get("expected_items") if isinstance(projection.get("expected_items"), list) else []
    observed = projection.get("observed_board_items") if isinstance(projection.get("observed_board_items"), list) else []
    observed_numbers = {
        _issue_number(item)
        for item in observed
        if isinstance(item, dict) and _issue_number(item) is not None
    }

    for item in expected:
        if not isinstance(item, dict):
            continue
        number = _issue_number(item)
        if number is not None and number not in observed_numbers:
            drift.append(
                _drift(
                    "MISSING_BOARD_ITEM",
                    "WARN",
                    "project-roadmap expected item is absent from observed board items",
                    issue_number=number,
                    source_ref=str(item.get("ssot_ref") or ""),
                )
            )

    for item in observed:
        if not isinstance(item, dict):
            continue
        number = _issue_number(item)
        labels = _labels(item)
        fields = _fields(item)
        if "project-roadmap" not in labels:
            drift.append(
                _drift(
                    "UNEXPECTED_BOARD_ITEM",
                    "WARN",
                    "observed board item lacks project-roadmap",
                    issue_number=number,
                )
            )
        for field in required_fields:
            if str(fields.get(field) or "").strip() == "":
                drift.append(
                    _drift(
                        "MISSING_FIELD",
                        "WARN",
                        f"observed board item missing required field {field}",
                        issue_number=number,
                    )
                )
        if fields.get("Status") and fields.get("Status") not in STATUSES:
            drift.append(_drift("INVALID_FIELD_VALUE", "WARN", "invalid Status field", issue_number=number))
        if fields.get("Track") and fields.get("Track") not in TRACKS:
            drift.append(_drift("INVALID_FIELD_VALUE", "WARN", "invalid Track field", issue_number=number))
        if fields.get("Priority") and fields.get("Priority") not in PRIORITIES:
            drift.append(_drift("INVALID_FIELD_VALUE", "WARN", "invalid Priority field", issue_number=number))
        if fields.get("Kind") and fields.get("Kind") not in KINDS:
            drift.append(_drift("INVALID_FIELD_VALUE", "WARN", "invalid Kind field", issue_number=number))
        if fields.get("Status") == "Needs Verify" and "needs-verification" not in labels:
            drift.append(
                _drift(
                    "NEEDS_VERIFY_LABEL_MISMATCH",
                    "WARN",
                    "Needs Verify item lacks needs-verification label",
                    issue_number=number,
                )
            )
        if fields.get("Status") == "Blocked" and "blocked" not in labels:
            drift.append(
                _drift("BLOCKED_STATE_MISMATCH", "WARN", "Blocked item lacks blocked label", issue_number=number)
            )
        if fields.get("Status") == "Done" and ({"needs-verification", "blocked"} & labels):
            drift.append(
                _drift(
                    "FORBIDDEN_DONE",
                    "ERROR",
                    "Done item still has blocking verification labels",
                    issue_number=number,
                )
            )

    return _dedupe(drift)


def summarize_drift(drift: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity = {"ERROR": 0, "WARN": 0, "INFO": 0}
    by_code: dict[str, int] = {}
    for item in drift:
        severity = str(item.get("severity") or "INFO")
        if severity not in by_severity:
            severity = "INFO"
        by_severity[severity] += 1
        code = str(item.get("code") or "UNKNOWN")
        by_code[code] = by_code.get(code, 0) + 1
    if by_severity["ERROR"]:
        max_severity = "ERROR"
    elif by_severity["WARN"]:
        max_severity = "WARN"
    else:
        max_severity = "OK"
    return {
        "total": len(drift),
        "by_severity": by_severity,
        "by_code": dict(sorted(by_code.items())),
        "max_severity": max_severity,
    }

