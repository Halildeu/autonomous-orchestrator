from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.session.context_store import (
        SessionPaths,
        load_context,
        mark_compaction,
        new_context,
        prune_expired_decisions,
        save_context_atomic,
        upsert_provider_state,
        upsert_decision,
    )
    from src.session.cross_session_context import build_cross_session_context

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)

        a = new_context(session_id="s1", workspace_root=str(ws), ttl_seconds=3600)
        p1 = SessionPaths(workspace_root=ws, session_id="s1").context_path
        save_context_atomic(p1, a)
        a = load_context(p1)
        upsert_decision(a, key="theme", value="alpha", source="agent", decision_ttl_seconds=60)
        upsert_provider_state(
            a,
            provider="openai",
            wire_api="responses",
            conversation_id="conv-alpha",
            last_response_id="resp-alpha",
            summary_ref=".cache/reports/session_compaction_alpha.v1.md",
        )
        mark_compaction(
            a,
            summary_ref=".cache/reports/session_compaction_alpha.v1.md",
            trigger="auto_compact",
            source="provider",
            approx_input_tokens=24001,
        )
        save_context_atomic(p1, a)

        # Expire decision deterministically by waiting a small amount and pruning against future timestamp.
        b = new_context(session_id="s2", workspace_root=str(ws), ttl_seconds=3600)
        p2 = SessionPaths(workspace_root=ws, session_id="s2").context_path
        save_context_atomic(p2, b)
        b = load_context(p2)
        upsert_decision(b, key="theme", value="beta", source="agent", decision_ttl_seconds=60)
        save_context_atomic(p2, b)

        b2 = load_context(p2)
        dec = b2.get("ephemeral_decisions")
        if not isinstance(dec, list) or not dec:
            raise SystemExit("session_cross_context_contract_test failed: decision missing")

        # Move prune clock beyond expires_at of session2 decision.
        expires_at = dec[0].get("expires_at")
        if not isinstance(expires_at, str):
            raise SystemExit("session_cross_context_contract_test failed: expires_at missing")
        future = expires_at.replace("Z", "+00:00")
        # one-second bump keeps parser simple
        future_ts = future

        prune_expired_decisions(b2, future_ts)
        save_context_atomic(p2, b2)

        report = build_cross_session_context(workspace_root=ws)
        if report.get("status") != "OK":
            raise SystemExit("session_cross_context_contract_test failed: report status")

        rep_path = ws / str(report.get("report_path") or "")
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        shared = rep.get("shared_decisions") if isinstance(rep.get("shared_decisions"), list) else []
        if len(shared) != 1:
            raise SystemExit("session_cross_context_contract_test failed: shared decision count")
        if str(shared[0].get("value")) != "alpha":
            raise SystemExit("session_cross_context_contract_test failed: expected non-expired session value")
        provider_states = rep.get("provider_states") if isinstance(rep.get("provider_states"), list) else []
        if len(provider_states) != 1:
            raise SystemExit("session_cross_context_contract_test failed: provider state count")
        compactions = rep.get("compactions") if isinstance(rep.get("compactions"), list) else []
        if len(compactions) != 1:
            raise SystemExit("session_cross_context_contract_test failed: compaction count")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
