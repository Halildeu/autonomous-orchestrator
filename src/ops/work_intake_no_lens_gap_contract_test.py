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
        raise SystemExit(f"work_intake_no_lens_gap_contract_test failed: {msg}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.work_intake_from_sources import _load_gap_sources

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        gap_path = ws / ".cache" / "index" / "gap_register.v1.json"
        gap_path.parent.mkdir(parents=True, exist_ok=True)
        gap_payload = {
            "version": "v1",
            "generated_at": "2026-02-07T00:00:00Z",
            "gaps": [
                {
                    "id": "GAP-EVAL-LENS-operability-hard_exceeded_gt",
                    "metric_id": "eval_lens:operability:hard_exceeded_gt",
                    "severity": "high",
                    "risk_class": "high",
                    "effort": "medium",
                    "status": "open",
                }
            ],
        }
        gap_path.write_text(json.dumps(gap_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes: list[str] = []
        sources = _load_gap_sources(ws, notes)
        _must(len(sources) == 1, "expected one source")
        src = sources[0] if isinstance(sources[0], dict) else {}
        _must(src.get("source_type") == "GAP", "source_type must be GAP")
        _must("lens_id" not in src, "lens_id must not be present")
        _must("lens_reason" not in src, "lens_reason must not be present")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
