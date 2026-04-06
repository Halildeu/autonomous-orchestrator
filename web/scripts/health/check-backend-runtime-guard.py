#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpCheck:
    url: str
    expected_statuses: tuple[int, ...] = (200,)


BLOCKING_LIVE_CHECKS: dict[str, HttpCheck] = {
    "api-gateway-health": HttpCheck("http://127.0.0.1:8080/actuator/health"),
    "gateway-user-by-email-route": HttpCheck("http://127.0.0.1:8080/api/v1/users/by-email?email=admin%40example.com"),
    "gateway-theme-registry-route": HttpCheck("http://127.0.0.1:8080/api/v1/theme-registry"),
    "gateway-audit-route": HttpCheck("http://127.0.0.1:8080/api/audit/events?page=0&size=1"),
}

ADVISORY_LIVE_CHECKS: dict[str, HttpCheck] = {
    "gateway-roles-route": HttpCheck("http://127.0.0.1:8080/api/v1/roles"),
    "gateway-permissions-route": HttpCheck("http://127.0.0.1:8080/api/v1/permissions"),
}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(str(raw_path).strip())
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-file", default=".cache/runtime_guard/backend_start_session.v1.json")
    parser.add_argument("--backend-report", default=".cache/reports/backend_runtime_guard.v1.json")
    parser.add_argument("--report", default=".cache/reports/web_backend_guard_wait.v1.json")
    parser.add_argument("--wait-seconds", type=int, default=120)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    return parser.parse_args(argv)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _http_check(check: HttpCheck, timeout_seconds: float = 3.0) -> dict[str, Any]:
    request = Request(check.url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(response.getcode())
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        status_code = int(exc.code)
        body = exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return {
            "reachable": False,
            "status": "DOWN",
            "error": str(exc.reason),
            "url": check.url,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "reachable": False,
            "status": "DOWN",
            "error": str(exc),
            "url": check.url,
        }

    normalized_status = "UP" if status_code in check.expected_statuses else "DOWN"
    payload_status = None
    try:
        payload = json.loads(body)
        payload_status = payload.get("status")
        if isinstance(payload_status, str) and payload_status.upper() == "UP":
            normalized_status = "UP"
    except Exception:
        payload = None

    return {
        "reachable": True,
        "status": normalized_status,
        "http_status": status_code,
        "expected_statuses": list(check.expected_statuses),
        "payload_status": payload_status,
        "url": check.url,
        "body_tail": body[-400:] if body else "",
        "json": payload,
    }


def _backend_report_ready(session: dict[str, Any] | None, report: dict[str, Any] | None) -> tuple[bool, str]:
    if not isinstance(session, dict):
        return False, "backend_session_missing"
    if not isinstance(report, dict):
        return False, "backend_report_missing"

    report_status = str(report.get("status") or "").upper()
    if report_status not in {"OK", "WARN"}:
        return False, f"backend_report_status:{report_status or 'UNKNOWN'}"

    session_id = str(session.get("session_id") or "")
    report_session = report.get("session") if isinstance(report.get("session"), dict) else {}
    report_session_id = str(report_session.get("session_id") or "")
    if session_id and report_session_id != session_id:
        return False, "backend_report_not_fresh_for_current_session"

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("failed_services"):
        return False, "backend_failed_services_present"
    if summary.get("failed_infra"):
        return False, "backend_failed_infra_present"
    if summary.get("failed_gateway_routes"):
        return False, "backend_failed_gateway_routes_present"

    return True, "backend_guard_ready"


def _wait_for_backend_guard(
    session_path: Path,
    backend_report_path: Path,
    *,
    wait_seconds: int,
    poll_interval: float,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    deadline = time.time() + max(wait_seconds, 1)
    last_reason = "backend_guard_pending"
    last_session: dict[str, Any] = {}
    last_report: dict[str, Any] = {}

    while time.time() <= deadline:
        session = _load_json(session_path) if session_path.exists() else {}
        report = _load_json(backend_report_path) if backend_report_path.exists() else {}
        ready, reason = _backend_report_ready(session, report)
        last_reason = reason
        last_session = session if isinstance(session, dict) else {}
        last_report = report if isinstance(report, dict) else {}
        if ready:
            return last_session, last_report, reason
        time.sleep(max(poll_interval, 0.5))

    return last_session, last_report, last_reason


def _wait_for_live_checks(
    checks: dict[str, HttpCheck],
    *,
    wait_seconds: int,
    poll_interval: float,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    deadline = time.time() + max(wait_seconds, 1)
    results: dict[str, dict[str, Any]] = {
        name: {"status": "DOWN", "reachable": False} for name in checks
    }

    while time.time() <= deadline:
        failed: list[str] = []
        for name, check in checks.items():
            result = _http_check(check)
            results[name] = result
            if result.get("status") != "UP":
                failed.append(name)
        if not failed:
            return results, []
        time.sleep(max(poll_interval, 0.5))

    failed = [name for name, result in results.items() if result.get("status") != "UP"]
    return results, failed


def _run_live_checks(checks: dict[str, HttpCheck]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    results: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    for name, check in checks.items():
        result = _http_check(check)
        results[name] = result
        if result.get("status") != "UP":
            failed.append(name)
    return results, failed


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = _repo_root()
    session_path = _resolve_path(root, args.session_file)
    backend_report_path = _resolve_path(root, args.backend_report)
    report_path = _resolve_path(root, args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    session, backend_report, backend_reason = _wait_for_backend_guard(
        session_path,
        backend_report_path,
        wait_seconds=args.wait_seconds,
        poll_interval=args.poll_interval,
    )
    blocking_live_checks, failed_blocking_live_checks = _wait_for_live_checks(
        BLOCKING_LIVE_CHECKS,
        wait_seconds=args.wait_seconds,
        poll_interval=args.poll_interval,
    )
    advisory_live_checks, failed_advisory_live_checks = _run_live_checks(
        ADVISORY_LIVE_CHECKS,
    )

    failed_live_checks = failed_blocking_live_checks + failed_advisory_live_checks
    if backend_reason != "backend_guard_ready" or failed_blocking_live_checks:
        status = "FAIL"
    elif failed_advisory_live_checks:
        status = "WARN"
    else:
        status = "OK"

    live_checks = {
        **blocking_live_checks,
        **advisory_live_checks,
    }
    payload = {
        "version": "v1",
        "kind": "web-backend-guard-wait-report",
        "generated_at": _now_iso_utc(),
        "status": status,
        "session_file": str(session_path),
        "backend_report_path": str(backend_report_path),
        "report_path": str(report_path),
        "summary": {
            "backend_guard_reason": backend_reason,
            "failed_blocking_live_checks": failed_blocking_live_checks,
            "failed_advisory_live_checks": failed_advisory_live_checks,
            "failed_live_checks": failed_live_checks,
        },
        "live_check_groups": {
            "blocking": list(BLOCKING_LIVE_CHECKS),
            "advisory": list(ADVISORY_LIVE_CHECKS),
        },
        "session": {
            "session_id": session.get("session_id") if isinstance(session, dict) else None,
            "created_at": session.get("created_at") if isinstance(session, dict) else None,
        },
        "backend_report": backend_report,
        "live_checks": live_checks,
    }

    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "report_path": str(report_path),
                "backend_guard_reason": backend_reason,
                "failed_blocking_live_checks": failed_blocking_live_checks,
                "failed_advisory_live_checks": failed_advisory_live_checks,
                "failed_live_checks": failed_live_checks,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
