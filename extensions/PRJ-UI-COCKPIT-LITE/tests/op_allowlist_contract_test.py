from __future__ import annotations

import importlib.util
import json
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


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        server, port = utils.start_server(repo_root, ws)
        try:
            bad_url = f"http://127.0.0.1:{port}/api/op"
            try:
                _post(bad_url, {"op": "unknown-op"})
                raise SystemExit("op_allowlist_contract_test failed: expected 400")
            except urllib.error.HTTPError as exc:
                if exc.code != 400:
                    raise SystemExit(f"op_allowlist_contract_test failed: {exc.code}")

            good = _post(bad_url, {"op": "system-status", "args": {"dry_run": "true"}, "confirm": True})
            if good.get("op") != "system-status":
                raise SystemExit("op_allowlist_contract_test failed: op mismatch")
            if not isinstance(good.get("trace_meta"), dict):
                raise SystemExit("op_allowlist_contract_test failed: trace_meta missing")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
