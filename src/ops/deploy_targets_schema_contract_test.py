from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    schema_path = repo_root / "schemas" / "policy-deploy-targets.schema.v1.json"
    policy_path = repo_root / "policies" / "policy_deploy_targets.v1.json"
    if not schema_path.exists():
        raise SystemExit("deploy_targets_schema_contract_test failed: schema missing.")
    if not policy_path.exists():
        raise SystemExit("deploy_targets_schema_contract_test failed: policy missing.")

    schema = _load_json(schema_path)
    policy = _load_json(policy_path)
    Draft202012Validator(schema).validate(policy)

    kinds = policy.get("deploy_job_kinds") if isinstance(policy, dict) else []
    if not isinstance(kinds, list) or not kinds:
        raise SystemExit("deploy_targets_schema_contract_test failed: deploy_job_kinds missing.")
    if kinds != sorted(kinds):
        raise SystemExit("deploy_targets_schema_contract_test failed: deploy_job_kinds not sorted.")

    raw = json.dumps(policy, ensure_ascii=False, sort_keys=True)
    if "token" in raw.lower():
        raise SystemExit("deploy_targets_schema_contract_test failed: potential secret exposure.")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
