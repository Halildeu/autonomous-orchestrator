from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"llm_live_probe_refactor_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_kernel_api.llm_live_probe import run_live_probe

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir(parents=True, exist_ok=True)
        os.environ["KERNEL_API_LLM_LIVE"] = "0"

        status, error_code, report = run_live_probe(
            workspace_root=str(ws),
            detail=False,
            env_mode="process",
        )
        _must(str(status) in {"OK", "WARN"}, "status must be OK/WARN")
        _must(error_code is None, "error_code must be None")
        _must(isinstance(report, dict), "report must be dict")
        _must(isinstance(report.get("providers"), list), "providers list missing")

    print(
        json.dumps(
            {
                "status": "OK",
                "probe_status": status,
                "providers_count": len(report.get("providers") or []),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
