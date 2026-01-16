from __future__ import annotations

import importlib.util
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def _load_utils(repo_root: Path):
    utils_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "tests" / "test_utils.py"
    spec = importlib.util.spec_from_file_location("ui_cockpit_test_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        server, port = utils.start_server(repo_root, ws)
        try:
            url = f"http://127.0.0.1:{port}/api/evidence/read?path=../.."
            try:
                urllib.request.urlopen(url, timeout=3)
                raise SystemExit("evidence_browser_path_traversal_contract_test failed: expected 400")
            except urllib.error.HTTPError as exc:
                if exc.code != 400:
                    raise SystemExit(f"evidence_browser_path_traversal_contract_test failed: {exc.code}")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
