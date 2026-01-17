from __future__ import annotations

import http.client
import importlib.util
import json
import tempfile
from pathlib import Path


def _load_utils(repo_root: Path):
    utils_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "tests" / "test_utils.py"
    spec = importlib.util.spec_from_file_location("ui_cockpit_test_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _post_json(conn: http.client.HTTPConnection, path: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8"))
    return resp.status, data


def _get_json(conn: http.client.HTTPConnection, path: str) -> dict:
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    if resp.status != 200:
        raise SystemExit(f"planner_notes_op_allowlist_contract_test failed: {path} status={resp.status}")
    return json.loads(body)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        server, port = utils.start_server(repo_root, ws, poll_interval=0.2)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            status, data = _post_json(
                conn,
                "/api/op",
                {
                    "op": "planner-notes-create",
                    "args": {"title": "Test note", "body": "Body", "tags": "alpha,beta", "links_json": "[]"},
                    "confirm": True,
                },
            )
            if status != 200:
                raise SystemExit(f"planner_notes_op_allowlist_contract_test failed: status={status}")
            if data.get("status") == "FAIL":
                raise SystemExit("planner_notes_op_allowlist_contract_test failed: op status FAIL")

            notes = _get_json(conn, "/api/notes")
            if int(notes.get("notes_count", 0)) < 1:
                raise SystemExit("planner_notes_op_allowlist_contract_test failed: notes_count < 1")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
