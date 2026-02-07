from __future__ import annotations

import importlib.util
import json
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


def _load_utils(repo_root: Path):
    utils_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "tests" / "test_utils.py"
    spec = importlib.util.spec_from_file_location("ui_cockpit_test_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        reports = ws / ".cache" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "alpha_closeout.v1.json").write_text("{}", encoding="utf-8")
        (reports / "beta_report.v1.json").write_text("{}", encoding="utf-8")

        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            closeout = _get_json(base + "/api/evidence/list?filter=" + urllib.parse.quote("closeout"))
            items = closeout.get("items", [])
            if not items:
                raise SystemExit("evidence_search_contract_test failed: no closeout items")
            for item in items:
                rel = item.get("relative_path", "")
                if "closeout" not in rel:
                    raise SystemExit("evidence_search_contract_test failed: filter not applied")

            beta = _get_json(base + "/api/evidence/list?filter=" + urllib.parse.quote("beta"))
            items = beta.get("items", [])
            if not items:
                raise SystemExit("evidence_search_contract_test failed: no beta items")
            for item in items:
                rel = item.get("relative_path", "")
                if "beta" not in rel:
                    raise SystemExit("evidence_search_contract_test failed: beta filter not applied")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
