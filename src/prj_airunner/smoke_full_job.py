from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--rc-path", required=True)
    args = parser.parse_args()

    repo_root = _repo_root()
    ws_root = Path(str(args.workspace_root))
    rc_path = Path(str(args.rc_path))

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "full"
    venv_py = repo_root / ".venv" / "bin" / "python"
    python_bin = str(venv_py) if venv_py.exists() else sys.executable
    proc = subprocess.run(
        [python_bin, "smoke_test.py"],
        cwd=str(repo_root),
        env=env,
        text=True,
        check=False,
    )

    rc_payload = {
        "rc": int(proc.returncode),
        "completed_at": _now_iso(),
        "workspace_root": str(ws_root),
    }
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    rc_path.write_text(_dump_json(rc_payload), encoding="utf-8")
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
