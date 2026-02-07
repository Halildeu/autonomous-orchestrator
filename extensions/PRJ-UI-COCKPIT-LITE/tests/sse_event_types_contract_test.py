from __future__ import annotations

import http.client
import importlib.util
import json
import tempfile
import threading
import time
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
        server, port = utils.start_server(repo_root, ws, poll_interval=0.2)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/stream")
            resp = conn.getresponse()
            if resp.status != 200:
                raise SystemExit(f"sse_event_types_contract_test failed: status {resp.status}")

            def _touch() -> None:
                time.sleep(0.4)
                overrides = ws / ".cache" / "policy_overrides"
                overrides.mkdir(parents=True, exist_ok=True)
                path = overrides / "policy_auto_mode.override.v1.json"
                payload = {"version": "v1", "enabled": False}
                path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            threading.Thread(target=_touch, daemon=True).start()

            start = time.time()
            found = False
            while time.time() - start < 4:
                line = resp.fp.readline()
                if not line:
                    continue
                if line.startswith(b"event:"):
                    event = line.decode("utf-8", errors="replace").strip().split(":", 1)[-1].strip()
                    if event == "settings_tick":
                        found = True
                        break
            if not found:
                raise SystemExit("sse_event_types_contract_test failed: settings_tick not emitted")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
