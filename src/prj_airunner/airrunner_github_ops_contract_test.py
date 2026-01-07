from __future__ import annotations

import json
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    policy_path = repo_root / "policies" / "policy_airunner.v1.json"
    if not policy_path.exists():
        raise SystemExit("airrunner_github_ops_contract_test failed: policy missing")

    policy = _load_json(policy_path)
    single_gate = policy.get("single_gate") if isinstance(policy, dict) else None
    allowed_ops = single_gate.get("allowed_ops") if isinstance(single_gate, dict) else []
    allowed_ops = [str(x) for x in allowed_ops if isinstance(x, str)]

    required = {"github-ops-check", "github-ops-job-start", "github-ops-job-poll"}
    if not required.issubset(set(allowed_ops)):
        raise SystemExit("airrunner_github_ops_contract_test failed: missing allowed_ops")

    print(json.dumps({"status": "OK", "allowed_ops": sorted(set(allowed_ops))}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
