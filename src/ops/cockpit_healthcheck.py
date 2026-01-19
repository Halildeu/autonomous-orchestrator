from __future__ import annotations

import importlib.util
import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_server_module(repo_root: Path):
    server_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "server.py"
    spec = importlib.util.spec_from_file_location("cockpit_lite_server", server_path)
    module = importlib.util.module_from_spec(spec)
    if not spec or not spec.loader:
        raise RuntimeError("cockpit_server_load_failed")
    spec.loader.exec_module(module)
    return module


def _fetch(url: str, timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = resp.read()
            return {"ok": True, "status": resp.status, "bytes": len(payload)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}

def _fetch_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload_bytes = resp.read()
            status = resp.status
        text = payload_bytes.decode("utf-8", errors="replace") if payload_bytes else ""
        if not text.strip():
            return {"ok": False, "status": status, "error": "EMPTY_BODY"}
        try:
            json.loads(text)
        except Exception as exc:
            snippet = text.strip().replace("\n", " ")[:200]
            return {"ok": False, "status": status, "error": f"NON_JSON_BODY: {str(exc)[:120]}", "body": snippet}
        return {"ok": True, "status": status, "bytes": len(payload_bytes)}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        snippet = body.strip().replace("\n", " ")[:200]
        return {"ok": False, "status": exc.code, "error": str(exc)[:200], "body": snippet}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}

def _request_json(req: urllib.request.Request, timeout: float) -> dict[str, Any]:
    status = None
    payload_bytes = b""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload_bytes = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            payload_bytes = exc.read() or b""
        except Exception:
            payload_bytes = b""
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}

    text = payload_bytes.decode("utf-8", errors="replace") if payload_bytes else ""
    if status is None:
        return {"ok": False, "error": "NO_STATUS"}
    if not text.strip():
        return {"ok": False, "status": int(status), "error": "EMPTY_BODY"}
    try:
        obj = json.loads(text)
    except Exception as exc:
        snippet = text.strip().replace("\n", " ")[:200]
        return {"ok": False, "status": int(status), "error": f"NON_JSON_BODY: {str(exc)[:120]}", "body": snippet}
    if not isinstance(obj, dict):
        return {"ok": False, "status": int(status), "error": "JSON_NOT_OBJECT"}

    ok = 200 <= int(status) < 300
    payload: dict[str, Any] = {"ok": bool(ok), "status": int(status), "bytes": len(payload_bytes), "json": obj}
    if not ok:
        payload["error"] = str(obj.get("error") or f"HTTP_{status}")
    return payload


def _get_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    return _request_json(req, timeout=timeout)


def _post(url: str, payload: dict[str, Any], timeout: float = 3.0) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    return _request_json(req, timeout=timeout)


def _op_result_status_ok(op_status: str, error_code: str | None) -> bool:
    norm = str(op_status or "").strip().upper()
    if not norm:
        return False
    if "FAIL" in norm:
        return False
    if str(error_code or "").strip().upper() == "TIMEOUT":
        return False
    return "OK" in norm or "WARN" in norm or "IDLE" in norm


def _run_op_and_wait(
    *,
    base: str,
    op_payload: dict[str, Any],
    poll_timeout_seconds: float = 8.0,
    poll_interval_seconds: float = 0.25,
) -> dict[str, Any]:
    started_at = time.time()
    start = _post(base + "/api/op", op_payload, timeout=3.0)
    if not start.get("ok"):
        return {"ok": False, "mode": "start_failed", "start": start}
    start_obj = start.get("json")
    if not isinstance(start_obj, dict):
        return {"ok": False, "mode": "start_invalid", "start": start}

    poll_url = start_obj.get("poll_url")
    job_id = str(start_obj.get("job_id") or "")
    if not poll_url:
        op_status = str(start_obj.get("status") or "")
        error_code = start_obj.get("error") or start_obj.get("error_code")
        ok = _op_result_status_ok(op_status, str(error_code) if error_code else None)
        return {
            "ok": bool(ok),
            "mode": "sync",
            "job_id": job_id,
            "job_status": "DONE",
            "op_status": op_status,
            "error": str(error_code) if error_code else "",
            "start": start,
            "final": start_obj,
            "poll": {"attempts": 0, "elapsed_ms": int((time.time() - started_at) * 1000)},
        }

    if not isinstance(poll_url, str) or not poll_url.strip().startswith("/"):
        return {"ok": False, "mode": "async_invalid", "start": start, "error": "POLL_URL_INVALID"}

    deadline = started_at + max(0.5, float(poll_timeout_seconds))
    attempts = 0
    last_poll: dict[str, Any] | None = None
    while time.time() < deadline:
        attempts += 1
        poll = _get_json(base + poll_url, timeout=2.0)
        last_poll = poll
        if not poll.get("ok"):
            return {
                "ok": False,
                "mode": "async_poll_failed",
                "job_id": job_id,
                "start": start,
                "last_poll": poll,
                "poll": {
                    "attempts": attempts,
                    "elapsed_ms": int((time.time() - started_at) * 1000),
                    "timeout_seconds": float(poll_timeout_seconds),
                    "interval_seconds": float(poll_interval_seconds),
                },
            }
        poll_obj = poll.get("json")
        if not isinstance(poll_obj, dict):
            return {"ok": False, "mode": "async_poll_invalid", "job_id": job_id, "start": start, "last_poll": poll}
        job_status = str(poll_obj.get("job_status") or "")
        if job_status.upper() == "DONE":
            op_status = str(poll_obj.get("status") or "")
            error_code = poll_obj.get("error") or poll_obj.get("error_code")
            ok = _op_result_status_ok(op_status, str(error_code) if error_code else None)
            return {
                "ok": bool(ok),
                "mode": "async",
                "job_id": str(poll_obj.get("job_id") or job_id),
                "job_status": job_status,
                "op_status": op_status,
                "error": str(error_code) if error_code else "",
                "start": start,
                "final": poll_obj,
                "poll": {
                    "attempts": attempts,
                    "elapsed_ms": int((time.time() - started_at) * 1000),
                    "timeout_seconds": float(poll_timeout_seconds),
                    "interval_seconds": float(poll_interval_seconds),
                },
            }
        if job_status.upper() in {"CANCELLED", "FAILED"}:
            return {
                "ok": False,
                "mode": "async_cancelled",
                "job_id": str(poll_obj.get("job_id") or job_id),
                "job_status": job_status,
                "start": start,
                "last_poll": poll_obj,
                "poll": {
                    "attempts": attempts,
                    "elapsed_ms": int((time.time() - started_at) * 1000),
                    "timeout_seconds": float(poll_timeout_seconds),
                    "interval_seconds": float(poll_interval_seconds),
                },
            }
        time.sleep(max(0.05, float(poll_interval_seconds)))

    return {
        "ok": False,
        "mode": "async_timeout",
        "job_id": job_id,
        "start": start,
        "last_poll": last_poll,
        "poll": {
            "attempts": attempts,
            "elapsed_ms": int((time.time() - started_at) * 1000),
            "timeout_seconds": float(poll_timeout_seconds),
            "interval_seconds": float(poll_interval_seconds),
        },
        "error": "POLL_TIMEOUT",
    }


def run_cockpit_healthcheck(*, workspace_root: Path, port: int, host: str = "127.0.0.1") -> dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    module = _load_server_module(repo_root)

    requested_port = int(port)
    try:
        server = module.build_server(repo_root, workspace_root, host, requested_port, poll_interval=0.2)
    except OSError:
        server = module.build_server(repo_root, workspace_root, host, 0, poll_interval=0.2)
    actual_port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.15)

    base = f"http://{host}:{actual_port}"
    checks = {
        "/": _fetch(base + "/"),
        "/api/health": _fetch_json(base + "/api/health"),
        "/api/status": _fetch_json(base + "/api/status"),
        "/api/locks": _fetch_json(base + "/api/locks"),
    }
    op_payload = {
        "op": "ui-snapshot-bundle",
        "args": {"out": ".cache/reports/ui_snapshot_bundle.v1.json"},
        "confirm": True,
    }
    op_result = _run_op_and_wait(base=base, op_payload=op_payload)

    try:
        server.shutdown()
    finally:
        server.server_close()

    status = "OK"
    if not all(v.get("ok") for v in checks.values()) or not bool(op_result.get("ok")):
        status = "WARN"

    out_json = workspace_root / ".cache" / "reports" / "cockpit_healthcheck.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "cockpit_healthcheck.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    request_seed = {
        "workspace_root": str(workspace_root),
        "host": host,
        "requested_port": int(requested_port),
        "port": int(actual_port),
    }
    request_id = hashlib.sha256(json.dumps(request_seed, sort_keys=True).encode("utf-8")).hexdigest()
    payload = {
        "version": "v1",
        "status": status,
        "workspace_root": str(workspace_root),
        "host": host,
        "port": int(actual_port),
        "requested_port": int(requested_port),
        "request_id": request_id,
        "checks": checks,
        "op_check": op_result,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "LOCAL_ONLY=true"],
    }
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    md_lines = [
        "# Cockpit Healthcheck",
        f"- status: {status}",
        f"- host: {host}",
        f"- port: {int(port)}",
        "",
        "## Checks",
    ]
    for key in sorted(checks):
        md_lines.append(f"- {key}: {checks[key].get('ok')}")
    op_name = str(op_payload.get("op") or "op")
    op_summary = f"{op_result.get('ok')} ({op_result.get('job_status')}/{op_result.get('op_status')})"
    md_lines.append(f"- /api/op {op_name}: {op_summary}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": status,
        "out_json": str(Path(".cache") / "reports" / out_json.name),
        "out_md": str(Path(".cache") / "reports" / out_md.name),
    }
