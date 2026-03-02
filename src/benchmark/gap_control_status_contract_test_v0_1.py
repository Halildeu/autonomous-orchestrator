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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import run_assessment
    from jsonschema import Draft202012Validator

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "gap_control_status_contract"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    run_assessment(workspace_root=ws_root, dry_run=False)

    gap_path = ws_root / ".cache" / "index" / "gap_register.v1.json"
    _assert(gap_path.exists(), "gap_register missing")

    reg = json.loads(gap_path.read_text(encoding="utf-8"))
    gaps = reg.get("gaps") if isinstance(reg, dict) else []
    gaps = gaps if isinstance(gaps, list) else []
    gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}

    _assert(
        "GAP-GHOPS-NETWORK_POLICY_DEFAULT_OFF" not in gap_ids,
        "GHOPS network policy control should be satisfied",
    )
    _assert(
        "GAP-REL-NETWORK_POLICY_DEFAULT_OFF" not in gap_ids,
        "REL network policy control should be satisfied",
    )

    maturity_path = ws_root / ".cache" / "index" / "north_star_maturity_tracking.v1.json"
    _assert(maturity_path.exists(), "north_star_maturity_tracking missing")
    maturity_obj = json.loads(maturity_path.read_text(encoding="utf-8"))
    schema_path = repo_root / "schemas" / "north_star.maturity.schema.json"
    schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema_obj).validate(maturity_obj)

    print("OK")


if __name__ == "__main__":
    main()
