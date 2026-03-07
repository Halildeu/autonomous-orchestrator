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


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            out = _post(
                base + "/api/frontend_telemetry",
                {
                    "event_type": "console_error",
                    "message": "token=abc123 frontend boom",
                    "stack": "Error: boom\n at app.js:10:2",
                    "source": "app.js",
                    "line": 10,
                    "column": 2,
                    "href": "http://127.0.0.1:8787/#overview",
                    "user_agent": "contract-test",
                },
            )
            if out.get("status") != "OK":
                raise SystemExit("frontend_telemetry_contract_test failed: status not OK")

            summary_path = ws / ".cache" / "reports" / "cockpit_frontend_telemetry_summary.v1.json"
            events_path = ws / ".cache" / "reports" / "cockpit_frontend_telemetry.v1.jsonl"
            if not summary_path.exists():
                raise SystemExit("frontend_telemetry_contract_test failed: summary missing")
            if not events_path.exists():
                raise SystemExit("frontend_telemetry_contract_test failed: events missing")

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if str(summary.get("status") or "") != "WARN":
                raise SystemExit("frontend_telemetry_contract_test failed: summary status mismatch")
            if int(summary.get("console_error_count") or 0) != 1:
                raise SystemExit("frontend_telemetry_contract_test failed: console count mismatch")
            if str(summary.get("last_event_type") or "") != "console_error":
                raise SystemExit("frontend_telemetry_contract_test failed: last event type mismatch")
            last_message = str(summary.get("last_message") or "")
            if "abc123" in last_message:
                raise SystemExit("frontend_telemetry_contract_test failed: secret not redacted")
            if "token=<redacted>" not in last_message:
                raise SystemExit("frontend_telemetry_contract_test failed: redaction token missing")

            rows = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if len(rows) != 1:
                raise SystemExit("frontend_telemetry_contract_test failed: expected single event row")
            event = json.loads(rows[0])
            if str(event.get("message") or "").find("abc123") >= 0:
                raise SystemExit("frontend_telemetry_contract_test failed: raw event leaked secret")
        finally:
            utils.stop_server(server)

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
