from __future__ import annotations

import argparse
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
        port = resolve_memory_port(workspace=ws)
        _assert(getattr(port, "adapter_id", None) == "local_first", "qdrant_driver must not connect under network OFF")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "0",
        }
    ):
        port = resolve_memory_port(workspace=ws)
        _assert(getattr(port, "adapter_id", None) == "local_first", "qdrant_driver must require VECTOR_BACKEND_ENABLE=1")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "1",
            "ORCH_QDRANT_URL": "http://localhost:6333",
        }
    ):
        port = resolve_memory_port(workspace=ws)
        _assert(getattr(port, "adapter_id", None) in {"qdrant_driver", "local_first"}, "qdrant_driver selection logic invalid")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "qdrant_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "1",
            "ORCH_QDRANT_URL": "http://example.com:6333",
        }
    ):
        port = resolve_memory_port(workspace=ws)
        _assert(getattr(port, "adapter_id", None) == "local_first", "qdrant_driver must be localhost-only")

    with _patched_env(
        {
            **base_env,
            "ORCH_MEMORY_ADAPTER": "pgvector_driver",
            "ORCH_NETWORK_MODE": "ON",
            "VECTOR_BACKEND_ENABLE": "1",
            "ORCH_PGVECTOR_DSN": "postgresql://postgres:dummy@localhost:5433/vector_db",
        }
    ):
        port = resolve_memory_port(workspace=ws)
        _assert(getattr(port, "adapter_id", None) in {"pgvector_driver", "local_first"}, "pgvector_driver selection logic invalid")

    print("memoryport real_backend_contract_test: PASS")


if __name__ == "__main__":
    main()

