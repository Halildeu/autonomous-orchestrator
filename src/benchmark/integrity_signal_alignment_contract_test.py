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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import run_assessment

    ws = repo_root / ".cache" / "ws_integrity_signal_alignment"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    _write_json(
        ws / ".cache" / "reports" / "system_status.v1.json",
        {"version": "v1", "generated_at": "2026-01-09T00:00:00Z", "status": "OK"},
    )
    _write_json(
        ws / ".cache" / "index" / "pack_capability_index.v1.json",
        {"version": "v1", "generated_at": "2026-01-09T00:00:00Z", "packs": []},
    )
    _write_json(
        ws / ".cache" / "script_budget" / "report.json",
        {"exceeded_hard": [], "exceeded_soft": [], "function_hard": [], "function_soft": []},
    )

    res = run_assessment(workspace_root=ws, dry_run=False)
    out_raw = Path(res.get("out") or "").parent / "assessment_raw.v1.json"
    integrity_path = ws / ".cache" / "reports" / "integrity_verify.v1.json"
    if not out_raw.exists() or not integrity_path.exists():
        raise SystemExit("integrity_signal_alignment_contract_test failed: outputs missing")

    raw = _load_json(out_raw)
    integrity = _load_json(integrity_path)
    raw_status = str(((raw.get("signals") or {}).get("integrity") or {}).get("status") or "")
    verify_status = str(integrity.get("verify_on_read_result") or "")
    if raw_status != verify_status:
        raise SystemExit(
            f"integrity_signal_alignment_contract_test failed: raw={raw_status} verify={verify_status}"
        )

    print(json.dumps({"status": "OK", "raw": raw_status, "verify": verify_status}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
