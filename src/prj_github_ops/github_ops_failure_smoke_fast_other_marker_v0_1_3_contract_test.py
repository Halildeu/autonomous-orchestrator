from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _extract_lines(stderr_text: str) -> list[str]:
    lines: list[str] = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line[:200])
        if len(lines) >= 10:
            break
    return lines


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.prj_github_ops.github_ops import classify_github_ops_failure
    from src.prj_github_ops.github_ops_support_v2 import _hash_text

    stderr_text = (
        "Smoke test failed: M9.2 apply must write pack index: "
        "/tmp/ws_demo/.cache/index/pack_capability_index.v1.json\n"
    )
    failure_class, signature_hash = classify_github_ops_failure(stderr_text)
    if failure_class != "DEMO_PACK_CAPABILITY_INDEX_MISSING":
        raise SystemExit("github_ops_failure_smoke_fast_other_marker_v0_1_3_contract_test failed: class mismatch")

    expected = _hash_text("DEMO_PACK_CAPABILITY_INDEX_MISSING|" + "|".join(_extract_lines(stderr_text)))
    if signature_hash != expected:
        raise SystemExit("github_ops_failure_smoke_fast_other_marker_v0_1_3_contract_test failed: signature mismatch")

    failure_class_two, signature_hash_two = classify_github_ops_failure(stderr_text)
    if failure_class_two != failure_class or signature_hash_two != signature_hash:
        raise SystemExit("github_ops_failure_smoke_fast_other_marker_v0_1_3_contract_test failed: non-deterministic")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
