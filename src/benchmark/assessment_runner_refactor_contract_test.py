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
        raise SystemExit(f"assessment_runner_refactor_contract_test failed: {message}")


def _seed_payload(item_id: str, title: str) -> dict[str, object]:
    return {
        "version": "v1",
        "generated_at": "2026-02-07T00:00:00Z",
        "items": [
            {
                "id": item_id,
                "title": title,
                "source": "contract",
                "tags": ["core", "refactor"],
            }
        ],
    }


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import _write_seed_catalogs

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        bp_seed = ws / ".cache" / "inputs" / "bp_catalog.seed.v1.json"
        trend_seed = ws / ".cache" / "inputs" / "trend_catalog.seed.v1.json"
        bp_seed.parent.mkdir(parents=True, exist_ok=True)
        bp_seed.write_text(json.dumps(_seed_payload("BP-1", "Best Practice"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        trend_seed.write_text(
            json.dumps(_seed_payload("TR-1", "Trend Item"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        out_bp = ws / ".cache" / "index" / "bp_catalog.v1.json"
        out_trend = ws / ".cache" / "index" / "trend_catalog.v1.json"
        res = _write_seed_catalogs(
            workspace_root=ws,
            out_bp_catalog=out_bp,
            out_trend_catalog=out_trend,
            core_root=repo_root,
        )

        _must(isinstance(res, dict), "response must be dict")
        _must(int(res.get("bp_items", 0)) == 1, "bp_items must be 1")
        _must(int(res.get("trend_items", 0)) == 1, "trend_items must be 1")
        _must(out_bp.exists(), "bp catalog must be written")
        _must(out_trend.exists(), "trend catalog must be written")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
