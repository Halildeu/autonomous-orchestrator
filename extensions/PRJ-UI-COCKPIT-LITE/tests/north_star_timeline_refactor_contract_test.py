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


def _get_json(url: str, *, timeout: int = 15) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="ignore")
        return int(resp.status), json.loads(data)


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"north_star_timeline_refactor_contract_test failed: {message}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        timeline_path = ws / ".cache" / "reports" / "codex_timeline_summary.v1.json"
        timeline_path.parent.mkdir(parents=True, exist_ok=True)
        timeline_path.write_text(
            json.dumps(
                {
                    "version": "v1",
                    "generated_at": "2026-02-07T00:00:00Z",
                    "detail": {
                        "stats": {},
                        "selected_rollout": {},
                        "tool_call_summary": {},
                        "timeline": [],
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            ns_code, ns_payload = _get_json(f"{base}/api/north_star")
            tl_code, tl_payload = _get_json(f"{base}/api/timeline")

            _must(ns_code == 200, "north_star endpoint must return 200")
            _must(tl_code == 200, "timeline endpoint must return 200")
            _must(isinstance(ns_payload.get("summary"), dict), "north_star summary missing")
            _must(isinstance(ns_payload.get("runner_meta"), dict), "north_star runner_meta missing")
            _must(str(tl_payload.get("status") or "") == "OK", "timeline status must be OK")
            _must(isinstance(tl_payload.get("dashboard"), dict), "timeline dashboard missing")
        finally:
            utils.stop_server(server)

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
