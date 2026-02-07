from __future__ import annotations

import shutil
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

    from src.ops.work_item_claims import acquire_claim, load_claims, release_claim

    ws = repo_root / ".cache" / "ws_work_item_claims_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    intake_id = "INTAKE-CLAIM-TEST-001"

    res1 = acquire_claim(workspace_root=ws, work_item_id=intake_id, owner_tag="A", ttl_seconds=60)
    if res1.get("status") != "ACQUIRED":
        raise SystemExit(f"work_item_claims_contract_test failed: expected ACQUIRED, got {res1.get('status')}")

    res2 = acquire_claim(workspace_root=ws, work_item_id=intake_id, owner_tag="B", ttl_seconds=60)
    if res2.get("status") != "LOCKED":
        raise SystemExit(f"work_item_claims_contract_test failed: expected LOCKED, got {res2.get('status')}")

    res3 = acquire_claim(workspace_root=ws, work_item_id=intake_id, owner_tag="A", ttl_seconds=60)
    if res3.get("status") != "RENEWED":
        raise SystemExit(f"work_item_claims_contract_test failed: expected RENEWED, got {res3.get('status')}")

    rel_mismatch = release_claim(workspace_root=ws, work_item_id=intake_id, owner_tag="B", force=False)
    if rel_mismatch.get("status") != "MISMATCH":
        raise SystemExit(
            f"work_item_claims_contract_test failed: expected MISMATCH, got {rel_mismatch.get('status')}"
        )

    rel_ok = release_claim(workspace_root=ws, work_item_id=intake_id, owner_tag="A", force=False)
    if rel_ok.get("status") != "RELEASED":
        raise SystemExit(f"work_item_claims_contract_test failed: expected RELEASED, got {rel_ok.get('status')}")

    res4 = acquire_claim(workspace_root=ws, work_item_id=intake_id, owner_tag="B", ttl_seconds=60)
    if res4.get("status") != "ACQUIRED":
        raise SystemExit(f"work_item_claims_contract_test failed: expected ACQUIRED after release, got {res4.get('status')}")

    claims = load_claims(ws)
    active = [c for c in claims if isinstance(c, dict) and str(c.get("work_item_id") or "") == intake_id]
    if not active:
        raise SystemExit("work_item_claims_contract_test failed: active claim missing")


if __name__ == "__main__":
    main()

