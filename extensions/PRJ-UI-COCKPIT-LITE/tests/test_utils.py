from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def load_server_module(repo_root: Path):
    server_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "server.py"
    spec = importlib.util.spec_from_file_location("cockpit_lite_server", server_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
    (ws / ".cache" / "index").mkdir(parents=True, exist_ok=True)
    (ws / ".cache" / "github_ops").mkdir(parents=True, exist_ok=True)

    (ws / ".cache" / "reports" / "system_status.v1.json").write_text(
        json.dumps({"status": "OK"}, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ws / ".cache" / "reports" / "ui_snapshot_bundle.v1.json").write_text(
        json.dumps({"status": "OK"}, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ws / ".cache" / "index" / "work_intake.v1.json").write_text(
        json.dumps({"items": []}, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ws / ".cache" / "index" / "decision_inbox.v1.json").write_text(
        json.dumps({"items": []}, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ws / ".cache" / "github_ops" / "jobs_index.v1.json").write_text(
        json.dumps({"jobs": []}, indent=2, sort_keys=True), encoding="utf-8"
    )
    return ws


def start_server(repo_root: Path, workspace_root: Path, poll_interval: float = 0.1):
    module = load_server_module(repo_root)
    server = module.build_server(repo_root, workspace_root, "127.0.0.1", 0, poll_interval)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    time.sleep(0.05)
    return server, port


def stop_server(server) -> None:
    server.shutdown()
    server.server_close()
