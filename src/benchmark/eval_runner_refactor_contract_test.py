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


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"eval_runner_refactor_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.benchmark.eval_runner import run_eval

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        (ws / ".cache" / "index").mkdir(parents=True, exist_ok=True)
        out = run_eval(workspace_root=ws, dry_run=True)
        _must(isinstance(out, dict), "run_eval response must be dict")
        _must(str(out.get("status") or "") == "WOULD_WRITE", "dry_run status must be WOULD_WRITE")
        _must(str(out.get("out") or "").endswith("assessment_eval.v1.json"), "output path mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
