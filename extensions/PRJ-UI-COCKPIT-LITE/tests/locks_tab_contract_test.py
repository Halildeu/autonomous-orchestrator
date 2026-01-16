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
        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            payload = _get(base + "/api/locks")
            if "lock_state" not in payload:
                raise SystemExit("locks_tab_contract_test failed: lock_state missing")
            if "leases_summary" not in payload:
                raise SystemExit("locks_tab_contract_test failed: leases_summary missing")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
