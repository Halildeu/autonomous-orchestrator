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


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        (ws / ".cache" / "index" / "work_item_claims.v1.json").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "generated_at": "2999-01-01T00:00:00Z",
                    "claims": [
                        {
                            "work_item_id": "INTAKE-contract-1",
                            "owner_tag": "contract",
                            "owner_session": "contract",
                            "acquired_at": "2999-01-01T00:00:00Z",
                            "expires_at": "2999-01-01T01:00:00Z",
                            "ttl_seconds": 3600,
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            payload = _get(base + "/api/locks")
            if "lock_state" not in payload:
                raise SystemExit("locks_tab_contract_test failed: lock_state missing")
            if "leases_summary" not in payload:
                raise SystemExit("locks_tab_contract_test failed: leases_summary missing")
            claims_summary = payload.get("claims_summary") if isinstance(payload, dict) else None
            if not isinstance(claims_summary, dict):
                raise SystemExit("locks_tab_contract_test failed: claims_summary invalid")
            if int(claims_summary.get("active_count") or 0) != 1:
                raise SystemExit("locks_tab_contract_test failed: active claims count mismatch")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
