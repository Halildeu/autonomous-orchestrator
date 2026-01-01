from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.sdk import OrchestratorClient


def main() -> int:
    client = OrchestratorClient(workspace=str(repo_root), evidence_dir="evidence")

    res = client.run(
        intent="urn:core:summary:summary_to_file",
        tenant_id="TENANT-LOCAL",
        dry_run=True,
        side_effect_policy="none",
        risk_score=0.1,
    )

    print(json.dumps(res, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
