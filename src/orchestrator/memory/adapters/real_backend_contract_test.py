from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _patched_env(values: dict[str, str | None]):
    old: dict[str, str | None] = {}
    for k, v in values.items():
        old[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"memoryport real_backend_contract_test: FAIL ({message})")


def _expect_unavailable(fn, *, must_contain: str) -> None:
    try:
        fn()
    except Exception as e:
        msg = str(e)
        _assert(must_contain in msg, f"expected error to contain {must_contain!r}, got {msg!r}")
        return
    raise SystemExit("memoryport real_backend_contract_test: FAIL (expected MemoryAdapterUnavailable)")


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".cache/ws_customer_default")
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.orchestrator.memory.adapters import resolve_memory_port

    ws_root = Path(args.workspace_root).resolve()
    _assert(ws_root.exists(), "workspace-root does not exist")
    ws = ws_root / ".cache" / "ws_extension_contract"
    ws.mkdir(parents=True, exist_ok=True)

    base_env = {
        "ORCH_MEMORY_ADAPTER": None,
        "ORCH_NETWORK_MODE": None,
        "VECTOR_BACKEND_ENABLE": None,
        "ORCH_QDRANT_URL": None,
        "ORCH_PGVECTOR_DSN": None,
    }

    with _patched_env(base_env):
        port = resolve_memory_port(workspace=ws)
        _assert(getattr(port, "adapter_id", None) == "local_first", "default adapter must be local_first")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "OFF",
            "VECTOR_BACKEND_ENABLE": "1",
        }
    ):
        _expect_unavailable(lambda: resolve_memory_port(workspace=ws), must_contain="ORCH_NETWORK_MODE")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "0",
        }
    ):
        _expect_unavailable(lambda: resolve_memory_port(workspace=ws), must_contain="VECTOR_BACKEND_ENABLE")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "1",
            "ORCH_QDRANT_URL": "http://localhost:6333",
        }
    ):
        if importlib.util.find_spec("qdrant_client") is None:
            _expect_unavailable(lambda: resolve_memory_port(workspace=ws), must_contain="qdrant-client")
        else:
            port = resolve_memory_port(workspace=ws)
            _assert(getattr(port, "adapter_id", None) == "qdrant_driver", "qdrant_driver expected when deps are installed")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "1",
            "ORCH_QDRANT_URL": "http://example.com:6333",
        }
    ):
        _expect_unavailable(lambda: resolve_memory_port(workspace=ws), must_contain="localhost-only")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "pgvector_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "1",
            "ORCH_PGVECTOR_DSN": "postgresql://postgres:dummy@localhost:5433/vector_db",
        }
    ):
        if importlib.util.find_spec("psycopg") is None:
            _expect_unavailable(lambda: resolve_memory_port(workspace=ws), must_contain="psycopg")
        elif importlib.util.find_spec("pgvector") is None:
            _expect_unavailable(lambda: resolve_memory_port(workspace=ws), must_contain="pgvector")
        else:
            port = resolve_memory_port(workspace=ws)
            _assert(getattr(port, "adapter_id", None) == "pgvector_driver", "pgvector_driver expected when deps are installed")

    print("memoryport real_backend_contract_test: PASS")


if __name__ == "__main__":
    main()
