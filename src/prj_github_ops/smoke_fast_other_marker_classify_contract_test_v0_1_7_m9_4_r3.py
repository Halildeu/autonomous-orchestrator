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

    from src.prj_github_ops.failure_classifier import (
        _CUSTOM_SMOKE_FAST_MARKER_CLASS,
        classify_github_ops_failure,
    )

    stderr_text = "Smoke test failed: M8 apply must write readiness report"
    failure_class, signature_hash = classify_github_ops_failure(stderr_text)
    if failure_class != _CUSTOM_SMOKE_FAST_MARKER_CLASS:
        raise SystemExit("smoke_fast_other_marker_classify_contract_test_v0_1_7_m9_4_r3 failed: class mismatch")

    unknown_class, _ = classify_github_ops_failure("unrelated stderr line")
    if unknown_class != "OTHER":
        raise SystemExit("smoke_fast_other_marker_classify_contract_test_v0_1_7_m9_4_r3 failed: OTHER fallback mismatch")

    failure_class_two, signature_hash_two = classify_github_ops_failure(stderr_text)
    if failure_class_two != failure_class or signature_hash_two != signature_hash:
        raise SystemExit("smoke_fast_other_marker_classify_contract_test_v0_1_7_m9_4_r3 failed: non-deterministic")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
