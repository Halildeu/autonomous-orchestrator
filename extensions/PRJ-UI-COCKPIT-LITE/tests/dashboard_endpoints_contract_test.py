from __future__ import annotations

import importlib.util
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


def _get(url: str) -> int:
    with urllib.request.urlopen(url, timeout=3) as resp:
        resp.read()
        return resp.status


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            endpoints = [
                "/",
                "/api/ws",
                "/api/health",
                "/api/overview",
                "/api/status",
                "/api/ui_snapshot",
                "/api/intake",
                "/api/decisions",
                "/api/extensions",
                "/api/settings/overrides",
                "/api/notes",
                "/api/chat",
                "/api/jobs",
                "/api/airunner_jobs",
                "/api/locks",
                "/api/run_card",
                "/api/budget",
                "/api/evidence/list",
            ]
            for path in endpoints:
                status = _get(base + path)
                if status != 200:
                    raise SystemExit(f"dashboard_endpoints_contract_test failed: {path} {status}")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
