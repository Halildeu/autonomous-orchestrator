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
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.extension_run_dispatch_e2e_test_utils import run_dispatch_case

    payload = run_dispatch_case(
        test_name=Path(__file__).stem,
        extension_id="PRJ-RELEASE-AUTOMATION",
        expected_gate="release-check",
        required_output_keys=["release_plan_path", "release_manifest_path", "release_notes_path"],
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "extension_id": "PRJ-RELEASE-AUTOMATION",
                "single_gate_status": payload.get("single_gate_status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
