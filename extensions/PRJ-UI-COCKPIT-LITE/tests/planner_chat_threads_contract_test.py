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
        raise SystemExit(f"planner_chat_threads_contract_test failed: {path} status={resp.status}")
    return json.loads(body)


def _write_note(notes_root: Path, note_id: str, tag: str) -> None:
    payload = {
        "version": "v1",
        "note_id": note_id,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "title": f"Thread {tag}",
        "body": "Body",
        "tags": [tag],
        "links": [],
    }
    notes_root.mkdir(parents=True, exist_ok=True)
    (notes_root / f"{note_id}.v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        notes_root = ws / ".cache" / "notes" / "planner"
        _write_note(notes_root, "NOTE-" + ("a" * 64), "thread:alpha")
        _write_note(notes_root, "NOTE-" + ("b" * 64), "thread:beta")

        server, port = utils.start_server(repo_root, ws)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            payload = _get_json(conn, "/api/planner_chat/threads")
            threads = payload.get("threads") if isinstance(payload.get("threads"), list) else []
            ids = {item.get("thread_id") for item in threads if isinstance(item, dict)}
            if "default" not in ids:
                raise SystemExit("planner_chat_threads_contract_test failed: default thread missing")
            alpha = [item for item in threads if item.get("thread_id") == "alpha"]
            if not alpha or alpha[0].get("count") != 1:
                raise SystemExit("planner_chat_threads_contract_test failed: alpha thread count mismatch")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
