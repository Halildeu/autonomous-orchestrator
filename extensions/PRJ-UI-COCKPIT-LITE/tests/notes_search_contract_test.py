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


def _get_json(conn: http.client.HTTPConnection, path: str) -> dict:
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    if resp.status != 200:
        raise SystemExit(f"notes_search_contract_test failed: {path} status={resp.status}")
    return json.loads(body)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        notes_root = ws / ".cache" / "notes" / "planner"
        notes_root.mkdir(parents=True, exist_ok=True)
        note_id = "NOTE-" + ("b" * 64)
        note_path = notes_root / f"{note_id}.v1.json"
        note_payload = {
            "version": "v1",
            "note_id": note_id,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "title": "Hash mismatch triage",
            "body": "session_context hash mismatch",
            "tags": ["triage", "session"],
            "links": [],
        }
        note_path.write_text(json.dumps(note_payload, indent=2, sort_keys=True), encoding="utf-8")

        server, port = utils.start_server(repo_root, ws, poll_interval=0.2)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            payload = _get_json(conn, "/api/notes/search?q=session")
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            if not any(item.get("note_id") == note_id for item in items):
                raise SystemExit("notes_search_contract_test failed: note not found")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
