from __future__ import annotations

import importlib.util
import json
import tempfile
import urllib.request
from pathlib import Path


def _load_utils(repo_root: Path):
    utils_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "tests" / "test_utils.py"
    spec = importlib.util.spec_from_file_location("ui_cockpit_test_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _get_json(url: str, *, timeout: int = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="ignore")
        return json.loads(data)


def _assert_base_contract(payload: dict) -> None:
    if str(payload.get("status") or "").upper() != "OK":
        raise SystemExit(f"search_capabilities_contract_test failed: status={payload.get('status')}")
    if str(payload.get("contract_id") or "") != "search_adapter_contract.v1":
        raise SystemExit("search_capabilities_contract_test failed: contract_id mismatch")
    adapters = payload.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise SystemExit("search_capabilities_contract_test failed: adapters missing")
    adapter_ids = {str(item.get("adapter_id") or "") for item in adapters if isinstance(item, dict)}
    required = {"keyword_fts5_rg", "keyword_python_fallback", "semantic_pgvector"}
    if not required.issubset(adapter_ids):
        raise SystemExit(
            f"search_capabilities_contract_test failed: required adapters missing {sorted(required - adapter_ids)}"
        )
    routing = payload.get("routing")
    if not isinstance(routing, dict):
        raise SystemExit("search_capabilities_contract_test failed: routing missing")
    supported = routing.get("supported_modes")
    if not isinstance(supported, list) or "keyword" not in supported or "auto" not in supported:
        raise SystemExit("search_capabilities_contract_test failed: supported_modes invalid")
    index = payload.get("index")
    if not isinstance(index, dict):
        raise SystemExit("search_capabilities_contract_test failed: index block missing")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        (ws / ".cache" / "state").mkdir(parents=True, exist_ok=True)

        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            ssot_payload = _get_json(f"{base}/api/search/capabilities?scope=ssot")
            _assert_base_contract(ssot_payload)
            if str(ssot_payload.get("scope") or "") != "ssot":
                raise SystemExit("search_capabilities_contract_test failed: ssot scope mismatch")

            repo_payload = _get_json(f"{base}/api/search/capabilities?scope=repo")
            _assert_base_contract(repo_payload)
            if str(repo_payload.get("scope") or "") != "repo":
                raise SystemExit("search_capabilities_contract_test failed: repo scope mismatch")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
