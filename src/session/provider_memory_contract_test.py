from __future__ import annotations

import json
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _fail(message: str) -> None:
    raise SystemExit(f"provider_memory_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())

    import sys

    sys.path.insert(0, str(repo_root))

    from src.session.context_store import SessionPaths, load_context, new_context, save_context_atomic, upsert_provider_state
    from src.session.provider_memory import maybe_auto_compact_markdown, persist_provider_result, read_provider_session_state

    with tempfile.TemporaryDirectory() as temp_dir:
        ws = Path(temp_dir).resolve()
        session_id = "default"
        ctx_path = SessionPaths(workspace_root=ws, session_id=session_id).context_path
        ctx = new_context(session_id=session_id, workspace_root=str(ws), ttl_seconds=3600)
        upsert_provider_state(
            ctx,
            provider="openai",
            wire_api="responses",
            conversation_id="conv-main",
            last_response_id="resp-prev",
        )
        save_context_atomic(ctx_path, ctx)

        state = read_provider_session_state(
            workspace_root=ws,
            session_id=session_id,
            provider="openai",
            wire_api="responses",
        )
        continuation = state.get("continuation") if isinstance(state.get("continuation"), dict) else {}
        if str(continuation.get("previous_response_id") or "") != "resp-prev":
            _fail("continuation previous_response_id mismatch")

        markdown = "# Title\n\n" + "\n".join([f"- item {idx}" for idx in range(400)])
        compacted = maybe_auto_compact_markdown(
            workspace_root=ws,
            session_id=session_id,
            markdown=markdown,
            provider="openai",
            wire_api="responses",
            threshold_tokens=40,
        )
        if not bool(compacted.get("applied")):
            _fail("compaction not applied")
        summary_ref = str(compacted.get("summary_ref") or "")
        if not summary_ref:
            _fail("summary_ref missing")
        if len(str(compacted.get("input_markdown") or "")) >= len(markdown):
            _fail("compacted markdown not reduced")

        ctx2 = load_context(ctx_path)
        compaction = ctx2.get("compaction") if isinstance(ctx2.get("compaction"), dict) else {}
        if str(compaction.get("status") or "") != "completed":
            _fail("compaction status mismatch")
        provider_state = ctx2.get("provider_state") if isinstance(ctx2.get("provider_state"), dict) else {}
        if str(provider_state.get("summary_ref") or "") != summary_ref:
            _fail("provider_state summary_ref mismatch")
        if str(provider_state.get("last_response_id") or "") != "resp-prev":
            _fail("provider_state last_response_id unexpectedly changed")

        persist_res = persist_provider_result(
            workspace_root=ws,
            session_id=session_id,
            provider="openai",
            wire_api="responses",
            response_id="resp-next",
            conversation_id="conv-main",
            summary_ref=summary_ref,
        )
        if not bool(persist_res.get("updated")):
            _fail("provider result was not persisted")

        ctx3 = load_context(ctx_path)
        provider_state = ctx3.get("provider_state") if isinstance(ctx3.get("provider_state"), dict) else {}
        if str(provider_state.get("last_response_id") or "") != "resp-next":
            _fail("provider_state last_response_id not updated")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
