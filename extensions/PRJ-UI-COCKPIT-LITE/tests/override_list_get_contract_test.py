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


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        overrides_dir = ws / ".cache" / "policy_overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)
        override_path = overrides_dir / "policy_auto_mode.override.v1.json"
        override_path.write_text(json.dumps({"version": "v1", "enabled": True}, indent=2, sort_keys=True), encoding="utf-8")

        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            listing = _get(base + "/api/overrides/list")
            items = listing.get("items") if isinstance(listing.get("items"), list) else []
            match = [item for item in items if item.get("name") == "policy_auto_mode.override.v1.json"]
            if not match or not match[0].get("exists"):
                raise SystemExit("override_list_get_contract_test failed: override not listed as exists")

            detail = _get(base + "/api/overrides/get?name=policy_auto_mode.override.v1.json")
            if detail.get("name") != "policy_auto_mode.override.v1.json":
                raise SystemExit("override_list_get_contract_test failed: override get mismatch")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
