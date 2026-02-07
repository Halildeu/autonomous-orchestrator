from __future__ import annotations

import io
import json
import os
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from ci.smoke_helpers.integration_smoke_steps2 import _smoke_full_async_job_start

    ws = repo_root / ".cache" / "ws_smoke_full_async"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    os.environ["SMOKE_FULL_ASYNC_DRY_RUN"] = "1"
    buf = io.StringIO()
    with redirect_stdout(buf):
        payload = _smoke_full_async_job_start(repo_root=repo_root, ws_integration=ws)
    output = buf.getvalue()
    if "CRITICAL_SMOKE_FULL_ASYNC" not in output:
        raise SystemExit("smoke_full_async_contract_test failed: CRITICAL line missing")
    status = str(payload.get("status") or "")
    if status not in {"OK", "WARN", "IDLE", "SKIP", "RUNNING", "QUEUED"}:
        raise SystemExit("smoke_full_async_contract_test failed: status invalid")

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
