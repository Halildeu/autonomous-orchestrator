"""Auth consistency contract test for PRJ-KERNEL-API HTTP gateway."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

from jsonschema import Draft202012Validator

from src.prj_kernel_api.http_gateway import KernelApiServer


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema: dict, instance: dict, label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        raise SystemExit(f"Auth consistency test failed: {label} invalid at {where}.")


def _start_server(repo_root: Path, workspace_root: Path) -> tuple[KernelApiServer, threading.Thread]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server = KernelApiServer(("127.0.0.1", port), workspace_root=str(workspace_root), repo_root=repo_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _post_json(port: int, payload: dict, headers: dict[str, str]) -> dict:
    conn = HTTPConnection("127.0.0.1", port, timeout=30)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers)
    conn.request("POST", "/v1/kernel-api", body=data, headers=req_headers)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    try:
        return json.loads(body)
    except Exception:
        raise SystemExit("Auth consistency test failed: response is not JSON.")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_auth_consistency"
    ws.mkdir(parents=True, exist_ok=True)

    req_schema = _load_json(repo_root / "schemas" / "kernel-api-request.schema.v1.json")
    resp_schema = _load_json(repo_root / "schemas" / "kernel-api-response.schema.v1.json")

    token = "TEST_TOKEN"
    prev_token = os.environ.get("KERNEL_API_TOKEN")
    prev_auth_mode = os.environ.get("KERNEL_API_AUTH_MODE")
    prev_live = os.environ.get("KERNEL_API_LLM_LIVE")
    os.environ["KERNEL_API_TOKEN"] = token
    os.environ["KERNEL_API_AUTH_MODE"] = "bearer"
    os.environ.pop("KERNEL_API_LLM_LIVE", None)

    auth_headers = {"Authorization": f"Bearer {token}"}

    server, thread = _start_server(repo_root, ws)
    time.sleep(0.05)

    probe_req = {
        "version": "v1",
        "request_id": "REQ-AUTH-PROBE",
        "kind": "llm_live_probe",
        "workspace_root": str(ws),
        "mode": "json",
        "env_mode": "process",
    }
    _validate(req_schema, probe_req, "request")

    response = _post_json(server.server_address[1], probe_req, headers=auth_headers)
    _validate(resp_schema, response, "response")

    if response.get("status") != "OK":
        raise SystemExit("Auth consistency test failed: llm_live_probe should return OK when live disabled.")
    if response.get("error_code") == "KERNEL_API_UNAUTHORIZED":
        raise SystemExit("Auth consistency test failed: auth headers not forwarded.")

    response_text = json.dumps(response, ensure_ascii=False)
    if token in response_text:
        raise SystemExit("Auth consistency test failed: response leaked token.")

    server.shutdown()
    thread.join(timeout=2)

    if prev_token is None:
        os.environ.pop("KERNEL_API_TOKEN", None)
    else:
        os.environ["KERNEL_API_TOKEN"] = prev_token
    if prev_auth_mode is None:
        os.environ.pop("KERNEL_API_AUTH_MODE", None)
    else:
        os.environ["KERNEL_API_AUTH_MODE"] = prev_auth_mode
    if prev_live is None:
        os.environ.pop("KERNEL_API_LLM_LIVE", None)
    else:
        os.environ["KERNEL_API_LLM_LIVE"] = prev_live

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
