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


def _must(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"lensless_eval_contract_test failed: {msg}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.benchmark.eval_runner import run_eval

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        (ws / ".cache" / "index").mkdir(parents=True, exist_ok=True)
        (ws / "policies").mkdir(parents=True, exist_ok=True)
        (ws / "policies" / "policy_north_star_eval_lenses.v1.json").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "mode": "lensless",
                    "workflow_axes": ["reference", "assessment", "gap"],
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        res = run_eval(workspace_root=ws, dry_run=False)
        _must(isinstance(res, dict), "run_eval result must be dict")
        out_path = ws / ".cache" / "index" / "assessment_eval.v1.json"
        _must(out_path.exists(), "assessment_eval must be written")
        obj = json.loads(out_path.read_text(encoding="utf-8"))
        _must("lenses" not in obj, "assessment_eval must not contain lenses")
        assessment = obj.get("assessment") if isinstance(obj, dict) else None
        _must(isinstance(assessment, dict), "assessment section missing")
        axes = assessment.get("workflow_axes") if isinstance(assessment, dict) else None
        _must(isinstance(axes, list), "workflow_axes missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
