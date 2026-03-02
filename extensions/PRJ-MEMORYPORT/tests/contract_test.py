from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_contract_workspace_root(*, repo_root: Path) -> Path:
    ws = repo_root / ".cache" / "ws_customer_default"
    if ws.exists():
        return ws
    fallback = repo_root / ".cache" / "ws_extension_contract"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    manifest_path = Path(__file__).resolve().parents[1] / "extension.manifest.v1.json"
    if not manifest_path.exists():
        raise SystemExit("memoryport contract_test: FAIL (manifest missing)")

    manifest = _load_json(manifest_path)
    schema_path = repo_root / "schemas" / "extension-manifest.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(manifest)

    docs_ref = manifest.get("docs_ref")
    if not isinstance(docs_ref, str) or not docs_ref:
        raise SystemExit("memoryport contract_test: FAIL (docs_ref missing)")
    docs_path = docs_ref.split("#", 1)[0]
    if docs_path and not (repo_root / docs_path).exists():
        raise SystemExit("memoryport contract_test: FAIL (docs_ref path missing)")

    ai_context_refs = manifest.get("ai_context_refs")
    if not isinstance(ai_context_refs, list) or not ai_context_refs:
        raise SystemExit("memoryport contract_test: FAIL (ai_context_refs missing)")
    for ref in ai_context_refs:
        if not isinstance(ref, str) or not ref:
            raise SystemExit("memoryport contract_test: FAIL (ai_context_refs invalid)")
        if not (repo_root / ref).exists():
            raise SystemExit("memoryport contract_test: FAIL (ai_context_refs path missing)")

    from src.orchestrator.memory.adapters import resolve_memory_port
    from src.orchestrator.memory.memory_port import MemoryAdapterUnavailable

    ws_root = _resolve_contract_workspace_root(repo_root=repo_root)
    ws = ws_root / ".cache" / "ws_extension_contract"
    ws.mkdir(parents=True, exist_ok=True)

    old_adapter = os.environ.pop("ORCH_MEMORY_ADAPTER", None)
    old_network = os.environ.pop("ORCH_NETWORK_MODE", None)
    try:
        os.environ["ORCH_NETWORK_MODE"] = "OFF"
        port = resolve_memory_port(workspace=ws)
        if getattr(port, "adapter_id", None) != "local_first":
            raise SystemExit("memoryport contract_test: FAIL (default adapter must be local_first)")

        r1 = port.upsert_text(namespace="default", text="hello world", metadata={"kind": "greeting"})
        r2 = port.upsert_text(namespace="default", text="goodbye world", metadata={"kind": "farewell"})
        hits = port.query_text(namespace="default", query="hello", top_k=1)
        if not hits or hits[0].record.record_id != r1.record_id:
            raise SystemExit("memoryport contract_test: FAIL (local-first query mismatch)")

        deleted = port.delete(namespace="default", record_ids=[r2.record_id])
        if deleted != 1:
            raise SystemExit("memoryport contract_test: FAIL (delete mismatch)")

        os.environ["ORCH_MEMORY_ADAPTER"] = "qdrant_optional"
        try:
            resolve_memory_port(workspace=ws)
            raise SystemExit("memoryport contract_test: FAIL (qdrant_optional must be unavailable by default)")
        except MemoryAdapterUnavailable:
            pass
    finally:
        for k, v in [
            ("ORCH_MEMORY_ADAPTER", old_adapter),
            ("ORCH_NETWORK_MODE", old_network),
        ]:
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    from src.ops.extension_run import run_extension_run

    extension_id = str(manifest.get("extension_id") or "").strip()
    res = run_extension_run(workspace_root=ws, extension_id=extension_id, mode="report", chat=False)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("memoryport contract_test: FAIL (extension_run status invalid)")
    if res.get("network_allowed") is not False:
        raise SystemExit("memoryport contract_test: FAIL (network must be disabled)")

    print("memoryport contract_test: PASS")
    print(json.dumps({"status": "OK", "extension_id": extension_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
