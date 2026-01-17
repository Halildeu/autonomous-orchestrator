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


def _post(url: str, payload: dict[str, Any], timeout: float = 3.0) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        return {"ok": True, "status": resp.status, "body": body}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        return {"ok": False, "status": exc.code, "body": body[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


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
        "/api/health": _fetch(base + "/api/health"),
        "/api/status": _fetch(base + "/api/status"),
    }
    op_payload = {
        "op": "system-status",
        "args": {"dry_run": "false"},
        "confirm": True,
    }
    op_result = _post(base + "/api/op", op_payload)

    try:
        server.shutdown()
    finally:
        server.server_close()

    status = "OK"
    if not all(v.get("ok") for v in checks.values()) or not op_result.get("ok"):
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
    md_lines.append(f"- /api/op system-status: {op_result.get('ok')}")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": status,
        "out_json": str(Path(".cache") / "reports" / out_json.name),
        "out_md": str(Path(".cache") / "reports" / out_md.name),
    }
