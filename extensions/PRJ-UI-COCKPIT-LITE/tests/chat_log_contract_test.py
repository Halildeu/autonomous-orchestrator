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


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
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
            payload = {"confirm": True, "type": "NOTE", "text": "planner note"}
            out = _post(base + "/api/chat", payload)
            if out.get("status") != "OK":
                raise SystemExit("chat_log_contract_test failed: status not OK")

            chat = _get(base + "/api/chat?limit=5")
            items = chat.get("items") if isinstance(chat.get("items"), list) else []
            found = any(item.get("type") == "NOTE" for item in items if isinstance(item, dict))
            if not found:
                raise SystemExit("chat_log_contract_test failed: NOTE missing")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
