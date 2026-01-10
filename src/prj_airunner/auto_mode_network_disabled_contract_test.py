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

    from src.prj_airunner.auto_mode_dispatch import _policy_defaults, auto_mode_network_allowed

    policy = _policy_defaults()
    allowed, reason = auto_mode_network_allowed(
        workspace_root=repo_root,
        policy=policy,
        extension_id="PRJ-GITHUB-OPS",
    )
    if allowed or reason != "NETWORK_DISABLED":
        raise SystemExit("auto_mode_network_disabled_contract_test failed: network gate expected disabled")

    print(json.dumps({"status": "OK", "reason": reason}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
