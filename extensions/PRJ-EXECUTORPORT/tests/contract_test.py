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
        raise SystemExit("executorport contract_test: FAIL (manifest missing)")

    manifest = _load_json(manifest_path)
    schema_path = repo_root / "schemas" / "extension-manifest.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(manifest)

    docs_ref = manifest.get("docs_ref")
    if not isinstance(docs_ref, str) or not docs_ref:
        raise SystemExit("executorport contract_test: FAIL (docs_ref missing)")
    docs_path = docs_ref.split("#", 1)[0]
    if docs_path and not (repo_root / docs_path).exists():
        raise SystemExit("executorport contract_test: FAIL (docs_ref path missing)")

    ai_context_refs = manifest.get("ai_context_refs")
    if not isinstance(ai_context_refs, list) or not ai_context_refs:
        raise SystemExit("executorport contract_test: FAIL (ai_context_refs missing)")
    for ref in ai_context_refs:
        if not isinstance(ref, str) or not ref:
            raise SystemExit("executorport contract_test: FAIL (ai_context_refs invalid)")
        if not (repo_root / ref).exists():
            raise SystemExit("executorport contract_test: FAIL (ai_context_refs path missing)")

    from src.orchestrator.executor_adapters import resolve_executor_port

    old_adapter = os.environ.pop("ORCH_EXECUTOR_ADAPTER", None)
    old_network = os.environ.pop("ORCH_NETWORK_MODE", None)
    old_codex = os.environ.pop("ORCH_EXECUTOR_CODEX_ENABLED", None)
    try:
        ex = resolve_executor_port(workspace=repo_root)
        if getattr(ex, "adapter_id", None) != "local_manual":
            raise SystemExit("executorport contract_test: FAIL (default adapter must be local_manual)")

        os.environ["ORCH_EXECUTOR_ADAPTER"] = "codex_optional"
        os.environ["ORCH_NETWORK_MODE"] = "OFF"
        os.environ["ORCH_EXECUTOR_CODEX_ENABLED"] = "1"
        ex2 = resolve_executor_port(workspace=repo_root)
        if getattr(ex2, "adapter_id", None) != "codex_optional":
            raise SystemExit("executorport contract_test: FAIL (codex_optional selection failed)")
    finally:
        for k, v in [
            ("ORCH_EXECUTOR_ADAPTER", old_adapter),
            ("ORCH_NETWORK_MODE", old_network),
            ("ORCH_EXECUTOR_CODEX_ENABLED", old_codex),
        ]:
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    from src.ops.extension_run import run_extension_run

    ws_root = _resolve_contract_workspace_root(repo_root=repo_root)
    ws = ws_root / ".cache" / "ws_extension_contract"
    ws.mkdir(parents=True, exist_ok=True)

    extension_id = str(manifest.get("extension_id") or "").strip()
    res = run_extension_run(workspace_root=ws, extension_id=extension_id, mode="report", chat=False)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("executorport contract_test: FAIL (extension_run status invalid)")
    if res.get("network_allowed") is not False:
        raise SystemExit("executorport contract_test: FAIL (network must be disabled)")

    print("executorport contract_test: PASS")
    print(json.dumps({"status": "OK", "extension_id": extension_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
