from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Callable

import pytest


def _find_repo_root(start: Path) -> Path:
    for path in [start] + list(start.parents):
        if (path / "pyproject.toml").exists():
            return path
    return Path.cwd()


@pytest.fixture
def repo_root() -> Path:
    return _find_repo_root(Path(__file__).resolve())


@pytest.fixture
def workspace_root_tmp(tmp_path: Path) -> Path:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir(parents=True, exist_ok=True)
    return workspace_root


@pytest.fixture
def kernel_api_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def _apply(**env: str | None) -> None:
        for key, value in env.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    return _apply


@pytest.fixture
def request_response_schemas(repo_root: Path) -> tuple[dict, dict]:
    request_schema = json.loads((repo_root / "schemas" / "kernel-api-request.schema.v1.json").read_text(encoding="utf-8"))
    response_schema = json.loads((repo_root / "schemas" / "kernel-api-response.schema.v1.json").read_text(encoding="utf-8"))
    return (request_schema, response_schema)


@pytest.fixture
def http_gateway_server(repo_root: Path) -> Callable[[Path], tuple[object, int]]:
    from src.prj_kernel_api.http_gateway import KernelApiServer

    servers: list[tuple[KernelApiServer, threading.Thread]] = []

    def _start(workspace_root: Path) -> tuple[KernelApiServer, int]:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        server = KernelApiServer(("127.0.0.1", port), workspace_root=str(workspace_root), repo_root=repo_root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.05)
        servers.append((server, thread))
        return (server, port)

    yield _start

    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def guardrails_state_reset() -> None:
    import src.prj_kernel_api.api_guardrails as guardrails

    def _reset() -> None:
        guardrails._rate_state["minute"] = None
        guardrails._rate_state["count"] = 0
        guardrails._rate_state["limit"] = None
        guardrails._concurrency_state["limit"] = None
        guardrails._concurrency_state["semaphore"] = None

    _reset()
    yield
    _reset()
