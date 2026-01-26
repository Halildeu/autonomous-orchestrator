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

    # Qdrant driver internals: deterministic u64 point-id conversion + API feature-detect.
    from src.orchestrator.memory.adapters.qdrant_driver import _qdrant_query_points, _to_u64_point_id

    rid = "record_id_example.v1"
    u1 = _to_u64_point_id(rid)
    u2 = _to_u64_point_id(rid)
    _assert(isinstance(u1, int), "qdrant point-id conversion must return int")
    _assert(u1 == u2, "qdrant point-id conversion must be deterministic")
    _assert(0 <= u1 < (2**64), "qdrant point-id conversion must fit uint64")

    class _Resp:
        def __init__(self, points):
            self.points = points

    class _ClientQueryPoints:
        def __init__(self):
            self.called: list[str] = []

        def query_points(self, **kwargs):
            self.called.append("query_points")
            return _Resp(points=[{"id": 1}])

    c1 = _ClientQueryPoints()
    got = _qdrant_query_points(
        c1,
        collection_name="c",
        query_vector=[0.0],
        limit=1,
        with_payload=True,
        with_vectors=True,
    )
    _assert(c1.called == ["query_points"], "qdrant query must prefer query_points when present")
    _assert(isinstance(got, list) and len(got) == 1, "qdrant query_points must return list")

    class _Resp2:
        def __init__(self, result):
            self.result = result

    class _ClientSearchPoints:
        def __init__(self):
            self.called: list[str] = []

        def search_points(self, **kwargs):
            self.called.append("search_points")
            return _Resp2(result=[{"id": 2}])

    c2 = _ClientSearchPoints()
    got2 = _qdrant_query_points(
        c2,
        collection_name="c",
        query_vector=[0.0],
        limit=1,
        with_payload=True,
        with_vectors=True,
    )
    _assert(c2.called == ["search_points"], "qdrant query must use search_points when query_points missing")
    _assert(isinstance(got2, list) and len(got2) == 1, "qdrant search_points must return list")

    class _ClientSearch:
        def __init__(self):
            self.called: list[str] = []

        def search(self, **kwargs):
            self.called.append("search")
            return [{"id": 3}]

    c3 = _ClientSearch()
    got3 = _qdrant_query_points(
        c3,
        collection_name="c",
        query_vector=[0.0],
        limit=1,
        with_payload=True,
        with_vectors=True,
    )
    _assert(c3.called == ["search"], "qdrant query must fall back to search when available")
    _assert(isinstance(got3, list) and len(got3) == 1, "qdrant search must return list")

    class _ClientNone:
        pass

    try:
        _qdrant_query_points(
            _ClientNone(),
            collection_name="c",
            query_vector=[0.0],
            limit=1,
            with_payload=True,
            with_vectors=True,
        )
    except Exception as e:
        _assert("QDRANT_API_MISSING_QUERY_METHOD" in str(e), "missing query method must fail-closed with reason_code")
    else:
        raise SystemExit("memoryport real_backend_contract_test: FAIL (expected QDRANT_API_MISSING_QUERY_METHOD)")

    print("memoryport real_backend_contract_test: PASS")


if __name__ == "__main__":
    main()
