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

    from src.ops.policy_report import generate_policy_report_markdown

    outdir = repo_root / ".cache" / "policy_report_deprecation_contract"
    outdir.mkdir(parents=True, exist_ok=True)

    sim_path = outdir / "sim_report.json"
    diff_path = outdir / "policy_diff_report.json"

    sim_path.write_text(
        json.dumps(
            {
                "source": "fixtures",
                "counts": {
                    "allow": 1,
                    "suspend": 0,
                    "block_unknown_intent": 0,
                    "invalid_envelope": 0,
                },
                "examples": {
                    "allow": [],
                    "suspend": [],
                    "block_unknown_intent": [],
                    "invalid_envelope": [],
                },
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    diff_path.write_text(
        json.dumps({"status": "SKIPPED", "reason": "NO_BASELINE"}, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    md = generate_policy_report_markdown(in_dir=outdir, root=repo_root)
    if "## Deprecation warnings" not in md:
        raise SystemExit("policy_report_deprecation_contract_test failed: missing deprecation heading")
    if "rule_engine.legacy_compat=true" not in md:
        raise SystemExit("policy_report_deprecation_contract_test failed: missing legacy_compat warning line")
    if "remove_release=v2" not in md:
        raise SystemExit("policy_report_deprecation_contract_test failed: missing v2 removal milestone")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
