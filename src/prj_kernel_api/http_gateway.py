"""PRJ-KERNEL-API HTTP gateway (stdlib-only, program-led, deterministic)."""

from __future__ import annotations

import argparse
import json
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

from jsonschema import Draft202012Validator

from src.prj_kernel_api.adapter import handle_request
from src.prj_kernel_api.api_guardrails import (
    GuardrailsError,
    acquire_concurrency,
    action_allowed,
    compute_request_id,
    effective_limits,
    enforce_limits,
    load_guardrails_policy,
    release_concurrency,
    verify_auth,
    write_audit_log,
)

REQUEST_SCHEMA = "schemas/kernel-api-request.schema.v1.json"
RESPONSE_SCHEMA = "schemas/kernel-api-response.schema.v1.json"


def _repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_schema(repo_root: Path, rel: str) -> Dict[str, Any]:
    path = repo_root / rel
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema: Dict[str, Any], instance: Dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    return [f"{err.json_path or '$'}: {err.message}" for err in errors[:5]]


def _error_response(
    *,
    request_id: str,
    error_code: str,
    message: str,
    notes: list[str],
    auth_checked: bool | None = None,
    rate_limited: bool | None = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "version": "v1",
        "request_id": request_id,
        "status": "FAIL",
        "error_code": error_code,
        "payload": {"message": message},
        "evidence_paths": [],
        "notes": notes,
    }
    if isinstance(auth_checked, bool):
        body["auth_checked"] = auth_checked
    if isinstance(rate_limited, bool):
        body["rate_limited"] = rate_limited
    return body


def _json_response(handler: BaseHTTPRequestHandler, body: Dict[str, Any], status: int = 200) -> None:
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


class KernelApiHandler(BaseHTTPRequestHandler):
    server: "KernelApiServer"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/kernel-api":
            resp = _error_response(
                request_id="REQ-INVALID",
                error_code="KERNEL_API_NOT_FOUND",
                message="Unknown endpoint.",
                notes=["PROGRAM_LED=true"],
            )
            _json_response(self, resp, status=HTTPStatus.NOT_FOUND)
            return

        workspace_root = self.server.workspace_root
        env_mode = "dotenv"
        try:
            policy = load_guardrails_policy(workspace_root)
        except GuardrailsError as exc:
            resp = _error_response(
                request_id="REQ-INVALID",
                error_code=str(exc),
                message="Kernel API guardrails policy missing or invalid.",
                notes=["PROGRAM_LED=true"],
            )
            _json_response(self, resp, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        limits = effective_limits(policy, workspace_root, env_mode=env_mode)
        length = int(self.headers.get("Content-Length", "0"))
        if length > limits["max_body_bytes"]:
            resp = _error_response(
                request_id="REQ-INVALID",
                error_code="KERNEL_API_BODY_TOO_LARGE",
                message="Request body too large.",
                notes=["PROGRAM_LED=true"],
            )
            _json_response(self, resp, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        raw = self.rfile.read(length) if length > 0 else b""
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            resp = _error_response(
                request_id="REQ-INVALID",
                error_code="KERNEL_API_BAD_JSON",
                message="Invalid JSON payload.",
                notes=["PROGRAM_LED=true"],
            )
            _json_response(self, resp, status=HTTPStatus.BAD_REQUEST)
            return

        if not isinstance(data, dict):
            resp = _error_response(
                request_id="REQ-INVALID",
                error_code="KERNEL_API_SCHEMA_INVALID",
                message="Request must be a JSON object.",
                notes=["PROGRAM_LED=true"],
            )
            _json_response(self, resp, status=HTTPStatus.BAD_REQUEST)
            return

        action = data.get("kind") if isinstance(data.get("kind"), str) else data.get("action")
        request_id = data.get("request_id") if isinstance(data.get("request_id"), str) else compute_request_id(
            str(action or "").strip(),
            data,
        )
        if "workspace_root" in data and data.get("workspace_root") != workspace_root:
            resp = _error_response(
                request_id=request_id,
                error_code="KERNEL_API_WORKSPACE_MISMATCH",
                message="workspace_root mismatch.",
                notes=["PROGRAM_LED=true"],
            )
            _json_response(self, resp, status=HTTPStatus.BAD_REQUEST)
            return

        data["workspace_root"] = workspace_root
        data.setdefault("version", "v1")
        if isinstance(data.get("env_mode"), str):
            env_mode = data.get("env_mode")
        if env_mode not in {"dotenv", "process"}:
            env_mode = "dotenv"
        errors = _validate(self.server.request_schema, data)
        if errors:
            resp = _error_response(
                request_id=request_id,
                error_code="KERNEL_API_SCHEMA_INVALID",
                message="Request schema validation failed.",
                notes=["PROGRAM_LED=true", "errors=" + "; ".join(errors)],
            )
            _json_response(self, resp, status=HTTPStatus.BAD_REQUEST)
            return

        auth_checked = False
        rate_limited = False

        ok, error_code, rate_limited = enforce_limits(
            policy=policy,
            workspace_root=workspace_root,
            env_mode=env_mode,
            body_bytes=raw,
            json_obj=data,
        )
        if not ok:
            resp = _error_response(
                request_id=request_id,
                error_code=error_code or "KERNEL_API_LIMITS_FAILED",
                message="Kernel API guardrails limits failed.",
                notes=["PROGRAM_LED=true"],
                auth_checked=False,
                rate_limited=rate_limited,
            )
            _json_response(self, resp, status=HTTPStatus.TOO_MANY_REQUESTS)
            return

        ok, error_code, sem = acquire_concurrency(policy, workspace_root, env_mode=env_mode)
        if not ok:
            resp = _error_response(
                request_id=request_id,
                error_code=error_code or "KERNEL_API_CONCURRENCY_LIMIT",
                message="Kernel API concurrency limit reached.",
                notes=["PROGRAM_LED=true"],
                auth_checked=False,
                rate_limited=rate_limited,
            )
            _json_response(self, resp, status=HTTPStatus.TOO_MANY_REQUESTS)
            return

        response: Dict[str, Any] = {}
        status_code = HTTPStatus.OK
        error_code = None
        try:
            auth_ok, auth_error, auth_checked = verify_auth(
                headers={k: v for k, v in self.headers.items()},
                body_bytes=raw,
                policy=policy,
                workspace_root=workspace_root,
                env_mode=env_mode,
            )
            if not auth_ok:
                response = _error_response(
                    request_id=request_id,
                    error_code=auth_error or "KERNEL_API_UNAUTHORIZED",
                    message="Kernel API authorization failed.",
                    notes=["PROGRAM_LED=true"],
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
                status_code = HTTPStatus.UNAUTHORIZED
                error_code = response.get("error_code")
                _json_response(self, response, status=status_code)
                return

            action_name = str(action or "").strip()
            if not action_allowed(policy, action_name):
                response = _error_response(
                    request_id=request_id,
                    error_code="KERNEL_API_ACTION_DENIED",
                    message="Kernel API action not allowed.",
                    notes=["PROGRAM_LED=true"],
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
                status_code = HTTPStatus.FORBIDDEN
                error_code = response.get("error_code")
                _json_response(self, response, status=status_code)
                return

            auth_header = self.headers.get("Authorization")
            signature = self.headers.get("X-Signature")
            if auth_header or signature:
                data["headers"] = {}
                if isinstance(auth_header, str) and auth_header:
                    data["headers"]["Authorization"] = auth_header
                if isinstance(signature, str) and signature:
                    data["headers"]["X-Signature"] = signature
            response = handle_request(data)
            response["auth_checked"] = auth_checked
            response["rate_limited"] = rate_limited
            resp_errors = _validate(self.server.response_schema, response)
            if resp_errors:
                response = _error_response(
                    request_id=request_id,
                    error_code="KERNEL_API_RESPONSE_INVALID",
                    message="Response schema validation failed.",
                    notes=["PROGRAM_LED=true", "errors=" + "; ".join(resp_errors)],
                    auth_checked=auth_checked,
                    rate_limited=rate_limited,
                )
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR
                error_code = response.get("error_code")
                _json_response(self, response, status=status_code)
                return

            _json_response(self, response, status=HTTPStatus.OK)
        finally:
            release_concurrency(sem)
            try:
                record = {
                    "request_id": request_id,
                    "action": str(action or "").strip(),
                    "status": response.get("status") if isinstance(response, dict) else None,
                    "error_code": error_code or (response.get("error_code") if isinstance(response, dict) else None),
                    "auth_present": bool(auth_checked),
                    "rate_limited": bool(rate_limited),
                }
                action_name = str(action or "").strip()
                if action_name == "llm_live_probe" and isinstance(response, dict):
                    payload = response.get("payload")
                    if isinstance(payload, dict):
                        report = payload.get("probe_report")
                        if isinstance(report, dict):
                            providers = report.get("providers")
                            if isinstance(providers, list):
                                summary = []
                                for item in providers:
                                    if not isinstance(item, dict):
                                        continue
                                    provider_id = item.get("provider_id")
                                    status = item.get("status")
                                    error_code = item.get("error_code")
                                    if isinstance(provider_id, str):
                                        summary.append(
                                            {
                                                "provider_id": provider_id,
                                                "status": status if isinstance(status, str) else None,
                                                "error_code": error_code if isinstance(error_code, str) else None,
                                            }
                                        )
                                if summary:
                                    record["probe_summary"] = summary
                audit = policy.get("audit") if isinstance(policy.get("audit"), dict) else {}
                if bool(audit.get("store_request_preview", True)):
                    record["request_preview"] = {
                        "kind": str(action or "").strip(),
                        "workspace_root": workspace_root,
                        "params_keys": sorted([str(k) for k in data.get("params", {}).keys()]) if isinstance(data.get("params"), dict) else [],
                    }
                write_audit_log(workspace_root=workspace_root, policy=policy, record=record)
            except GuardrailsError:
                return


class KernelApiServer(ThreadingHTTPServer):
    def __init__(self, server_address: Tuple[str, int], workspace_root: str, repo_root: Path):
        super().__init__(server_address, KernelApiHandler)
        self.workspace_root = workspace_root
        self.request_schema = _load_schema(repo_root, REQUEST_SCHEMA)
        self.response_schema = _load_schema(repo_root, RESPONSE_SCHEMA)


def main() -> None:
    parser = argparse.ArgumentParser(description="Program-led Kernel API HTTP gateway (stdlib).")
    parser.add_argument("--workspace-root", required=True, help="Workspace root (required).")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    args = parser.parse_args()

    repo_root = _repo_root(Path(__file__).resolve())
    server = KernelApiServer((args.host, args.port), workspace_root=str(args.workspace_root), repo_root=repo_root)

    print(f"KERNEL_API_HTTP_READY host={args.host} port={server.server_address[1]} workspace={args.workspace_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
