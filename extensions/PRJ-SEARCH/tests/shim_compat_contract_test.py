from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"shim_compat_contract_test failed: cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE"))

    adapter_path = repo_root / "extensions" / "PRJ-SEARCH" / "search_adapter.py"
    shim_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "keyword_search.py"

    if not adapter_path.exists():
        raise SystemExit("shim_compat_contract_test failed: search_adapter.py missing")
    if not shim_path.exists():
        raise SystemExit("shim_compat_contract_test failed: keyword_search.py missing")

    adapter = _load_module(adapter_path, "prj_search_search_adapter")
    shim = _load_module(shim_path, "prj_ui_keyword_search_shim")

    expected = str(getattr(adapter, "SEARCH_ADAPTER_CONTRACT_ID", ""))
    actual = str(getattr(shim, "SEARCH_ADAPTER_CONTRACT_ID", ""))
    if not expected or expected != actual:
        raise SystemExit("shim_compat_contract_test failed: contract_id mismatch")

    if not hasattr(shim, "KeywordIndexManager"):
        raise SystemExit("shim_compat_contract_test failed: KeywordIndexManager missing")

    print('{"status":"OK","test":"shim_compat_contract_test"}')


if __name__ == "__main__":
    main()
