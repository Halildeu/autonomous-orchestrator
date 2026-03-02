from __future__ import annotations

import importlib.util
import json
import tempfile
import time
import urllib.parse
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


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        (ws / ".cache" / "state").mkdir(parents=True, exist_ok=True)

        token = "unique_token_search_contract_v1"
        (ws / ".cache" / "reports" / "search_contract_sample.v1.md").write_text(
            f"Hello\\n{token}\\n", encoding="utf-8"
        )

        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"

            # 1) Index should start missing.
            status = _get_json(f"{base}/api/search/index?action=status&scope=ssot")
            if str(status.get("status") or "").upper() not in {"MISSING", "OK", "STALE"}:
                raise SystemExit(f"search_keyword_index_contract_test failed: unexpected status {status.get('status')}")

            # 2) First search should auto-build (may return INDEX_BUILDING).
            q = urllib.parse.quote(token)
            payload = _get_json(f"{base}/api/search?q={q}&scope=ssot&mode=keyword")
            st = str(payload.get("status") or "").upper()
            if st not in {"OK", "INDEX_BUILDING"}:
                raise SystemExit(f"search_keyword_index_contract_test failed: search status {payload.get('status')}")

            # 3) Wait for build to finish (best effort).
            deadline = time.time() + 30.0
            while time.time() < deadline:
                idx = _get_json(f"{base}/api/search/index?action=status&scope=ssot")
                idx_st = str(idx.get("status") or "").upper()
                if idx_st != "BUILDING":
                    break
                time.sleep(0.25)

            # 4) Search must find our token (if build finished).
            payload2 = _get_json(f"{base}/api/search?q={q}&scope=ssot&mode=keyword")
            if str(payload2.get("status") or "").upper() != "OK":
                raise SystemExit(
                    f"search_keyword_index_contract_test failed: final search not OK ({payload2.get('status')})"
                )
            hits = payload2.get("hits")
            if not isinstance(hits, list) or not hits:
                snippet = json.dumps(payload2, ensure_ascii=True, sort_keys=True)[:800]
                raise SystemExit(f"search_keyword_index_contract_test failed: expected hits, got none; payload={snippet}")
            if not any(token in str(h.get("preview") or "") for h in hits if isinstance(h, dict)):
                raise SystemExit("search_keyword_index_contract_test failed: token not found in previews")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
