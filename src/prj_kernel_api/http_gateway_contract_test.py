"""Contract test for PRJ-KERNEL-API HTTP gateway (stdlib-only)."""

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
        raise SystemExit(f"HTTP gateway test failed: {label} invalid at {where}.")


def _start_server(repo_root: Path, workspace_root: Path) -> tuple[KernelApiServer, threading.Thread]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server = KernelApiServer(("127.0.0.1", port), workspace_root=str(workspace_root), repo_root=repo_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _post_json(port: int, payload: dict, headers: dict[str, str] | None = None) -> dict:
    conn = HTTPConnection("127.0.0.1", port, timeout=30)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    conn.request("POST", "/v1/kernel-api", body=data, headers=req_headers)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    try:
        return json.loads(body)
    except Exception:
        raise SystemExit("HTTP gateway test failed: response is not JSON.")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_http_demo"
    ws.mkdir(parents=True, exist_ok=True)

    req_schema = _load_json(repo_root / "schemas" / "kernel-api-request.schema.v1.json")
    resp_schema = _load_json(repo_root / "schemas" / "kernel-api-response.schema.v1.json")

    token = "TEST_TOKEN"
    prev_token = os.environ.get("KERNEL_API_TOKEN")
    prev_auth_mode = os.environ.get("KERNEL_API_AUTH_MODE")
    os.environ["KERNEL_API_TOKEN"] = token
    os.environ["KERNEL_API_AUTH_MODE"] = "bearer"
    auth_headers = {"Authorization": f"Bearer {token}"}

    server, thread = _start_server(repo_root, ws)
    time.sleep(0.05)

    minimal_req = {
        "version": "v1",
        "request_id": "REQ-HTTP-OK",
        "kind": "project_status",
        "workspace_root": str(ws),
        "mode": "json",
        "env_mode": "process",
    }
    _validate(req_schema, minimal_req, "request")
    resp = _post_json(server.server_address[1], minimal_req, headers=auth_headers)
    _validate(resp_schema, resp, "response")

    unauth_resp = _post_json(server.server_address[1], minimal_req)
    _validate(resp_schema, unauth_resp, "unauthorized_response")
    if unauth_resp.get("error_code") != "KERNEL_API_UNAUTHORIZED":
        raise SystemExit("HTTP gateway test failed: missing auth should be unauthorized.")

    wrong_resp = _post_json(server.server_address[1], minimal_req, headers={"Authorization": "Bearer WRONG"})
    _validate(resp_schema, wrong_resp, "wrong_token_response")
    if wrong_resp.get("error_code") != "KERNEL_API_UNAUTHORIZED":
        raise SystemExit("HTTP gateway test failed: wrong token should be unauthorized.")

    llm_req = {
        "version": "v1",
        "request_id": "REQ-HTTP-LLM",
        "kind": "llm_providers_init",
        "workspace_root": str(ws),
        "mode": "json",
        "env_mode": "process",
    }
    _validate(req_schema, llm_req, "request")
    llm_resp = _post_json(server.server_address[1], llm_req, headers=auth_headers)
    _validate(resp_schema, llm_resp, "llm_response")

    probe_req = {
        "version": "v1",
        "request_id": "REQ-HTTP-PROBE",
        "kind": "llm_live_probe",
        "workspace_root": str(ws),
        "mode": "json",
        "env_mode": "process",
    }
    _validate(req_schema, probe_req, "request")
    probe_resp = _post_json(server.server_address[1], probe_req, headers=auth_headers)
    _validate(resp_schema, probe_resp, "llm_probe_response")
    if probe_resp.get("status") != "OK":
        raise SystemExit("HTTP gateway test failed: llm_live_probe should return OK when live disabled.")

    bad_json = "{"  # invalid
    conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    conn.request("POST", "/v1/kernel-api", body=bad_json, headers={"Content-Type": "application/json"})
    bad_resp = conn.getresponse()
    bad_body = bad_resp.read().decode("utf-8")
    conn.close()
    bad_obj = json.loads(bad_body)
    _validate(resp_schema, bad_obj, "bad_json_response")
    if bad_obj.get("error_code") not in {"KERNEL_API_BAD_JSON", "KERNEL_API_SCHEMA_INVALID"}:
        raise SystemExit("HTTP gateway test failed: bad JSON error_code mismatch.")

    invalid_req = {
        "version": "v1",
        "request_id": "REQ-HTTP-INVALID",
        "workspace_root": str(ws),
    }
    invalid_resp = _post_json(server.server_address[1], invalid_req, headers=auth_headers)
    _validate(resp_schema, invalid_resp, "invalid_request_response")
    if invalid_resp.get("error_code") != "KERNEL_API_SCHEMA_INVALID":
        raise SystemExit("HTTP gateway test failed: schema invalid error_code mismatch.")

    audit_path = ws / ".cache" / "reports" / "kernel_api_audit.v1.jsonl"
    if not audit_path.exists():
        raise SystemExit("HTTP gateway test failed: audit log missing.")
    audit_text = audit_path.read_text(encoding="utf-8")
    if token in audit_text:
        raise SystemExit("HTTP gateway test failed: audit log leaked token.")

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

    print(json.dumps({"status": "OK", "port": server.server_address[1]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
