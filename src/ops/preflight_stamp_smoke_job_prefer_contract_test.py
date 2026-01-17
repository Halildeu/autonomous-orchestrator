from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    import src.ops.preflight_stamp as stamp_mod

    ws = repo_root / ".cache" / "ws_preflight_stamp_smoke_job_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    sb_path = ws / ".cache" / "script_budget" / "report.json"
    _write_json(
        sb_path,
        {
            "status": "OK",
            "exceeded_hard": [],
            "exceeded_soft": [],
            "function_hard": [],
            "function_soft": [],
        },
    )

    original_run = stamp_mod.subprocess.run
    original_gate = stamp_mod._smoke_fast_job_gate
    called = {"gate": False}
    stamp_mod.subprocess.run = lambda *args, **kwargs: type("R", (), {"returncode": 0})()

    def _stub_gate(*, workspace_root: Path) -> tuple[str, list[str]]:
        called["gate"] = True
        return "PASS", []

    stamp_mod._smoke_fast_job_gate = _stub_gate
    try:
        res = stamp_mod.run_preflight_stamp(workspace_root=ws, mode="write")
    finally:
        stamp_mod.subprocess.run = original_run
        stamp_mod._smoke_fast_job_gate = original_gate

    if not called["gate"]:
        raise SystemExit("preflight_stamp_smoke_job_prefer_contract_test failed: job gate not used")
    if res.get("overall") != "PASS":
        raise SystemExit("preflight_stamp_smoke_job_prefer_contract_test failed: expected PASS")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
