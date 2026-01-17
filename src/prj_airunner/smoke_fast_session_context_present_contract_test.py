from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_airunner.smoke_full_job import _ensure_demo_session_context, _session_context_path
    from src.session.context_store import load_context

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_root = Path(tmp_dir)
        result = _ensure_demo_session_context(ws_root, session_id="default")
        ctx_path = _session_context_path(ws_root, session_id="default")
        if not ctx_path.exists():
            raise SystemExit("smoke_fast_session_context_present_contract_test failed: session context missing")
        try:
            ctx = load_context(ctx_path)
        except Exception as exc:
            raise SystemExit("smoke_fast_session_context_present_contract_test failed: invalid session context") from exc
        if not isinstance(ctx, dict):
            raise SystemExit("smoke_fast_session_context_present_contract_test failed: context not dict")
        if result.get("status") != "OK":
            raise SystemExit("smoke_fast_session_context_present_contract_test failed: ensure status not OK")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
