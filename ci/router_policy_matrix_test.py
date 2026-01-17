from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.context_pack_router import route_request

    policy_path = repo_root / "policies" / "policy_context_pack_router.v1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    contexts = [
        (
            {"doc_nav": {"critical_nav_gaps": 1}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 0, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "support"}, "target_path": ""},
            "INCIDENT",
        ),
        (
            {"doc_nav": {"critical_nav_gaps": 0}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 0, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "strategy"}, "target_path": ""},
            "ROADMAP",
        ),
        (
            {"doc_nav": {"critical_nav_gaps": 0}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 0, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "support"}, "target_path": ""},
            "TICKET",
        ),
        (
            {"doc_nav": {"critical_nav_gaps": 0}, "integrity": {"status": "OK"}, "script_budget": {"hard_exceeded": 2, "soft_only": False}, "pdca": {"regression_count": 0}, "gap": {"severity": "LOW", "effort": "S"}, "manual_request": {"kind": "support"}, "target_path": ""},
            "INCIDENT",
        ),
    ]

    for ctx, expected in contexts:
        bucket, reasons = route_request(policy=policy, context=ctx)
        if bucket != expected:
            raise SystemExit(f"Router policy test failed: expected {expected}, got {bucket}.")
        if not isinstance(reasons, list):
            raise SystemExit("Router policy test failed: reasons must be list.")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
