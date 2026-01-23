"""Contract test for llm_router: deterministic, verified-only selection."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    state_path = repo_root / ".cache" / "ws_customer_default" / ".cache" / "state" / "llm_probe_state.v1.json"
    prior_state_text = state_path.read_text(encoding="utf-8") if state_path.exists() else None

    # 1) Run synthetic probe to mark pinned models as ok (no network).
    from src.prj_kernel_api.llm_probe_runner import main as probe_main

    probe_main()

    # 2) Resolve DISCOVERY (BALANCED_TEXT) and ensure a provider/model is selected.
    from src.prj_kernel_api.llm_router import resolve

    req = {"intent": "DISCOVERY", "perspective": "demo"}
    result = resolve(req, repo_root=repo_root, now=datetime.now(timezone.utc))
    if result.get("status") != "OK":
        raise SystemExit(f"Router test failed: DISCOVERY did not resolve: {result}")
    if not result.get("selected_provider") or not result.get("selected_model"):
        raise SystemExit("Router test failed: selection fields missing.")

    # 2b) Resolve APPLY (CODE_AGENTIC) should be NOT READY unless a verified code
    # promotion workflow has pinned an eligible model.
    apply_req = {"intent": "APPLY", "perspective": "demo"}
    apply_result = resolve(apply_req, repo_root=repo_root, now=datetime.now(timezone.utc))
    if apply_result.get("status") != "FAIL":
        raise SystemExit(f"Router test failed: APPLY expected FAIL(not-ready): {apply_result}")
    if apply_result.get("reason") != "APPLY_BLOCKED_NO_VERIFIED_CODE_AGENTIC":
        raise SystemExit(f"Router test failed: APPLY reason mismatch: {apply_result}")
    if apply_result.get("selected_class") != "CODE_AGENTIC":
        raise SystemExit(f"Router test failed: APPLY selected_class mismatch: {apply_result}")

    # 3) Ensure model/param override is rejected.
    bad = resolve({"intent": "DISCOVERY", "model": "hack"}, repo_root=repo_root)
    if bad.get("status") != "FAIL" or bad.get("reason") != "MODEL_OVERRIDE_NOT_ALLOWED":
        raise SystemExit("Router test failed: model override not rejected.")

    # Restore state file to avoid clobbering real workspace state.
    if prior_state_text is None:
        try:
            state_path.unlink(missing_ok=True)
        except Exception:
            pass
    else:
        state_path.write_text(prior_state_text, encoding="utf-8")

    print("llm_router_contract_test: PASS")


if __name__ == "__main__":
    main()
