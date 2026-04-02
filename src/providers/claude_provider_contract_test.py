"""Claude provider contract test — validates parity with OpenAI provider contract."""
from __future__ import annotations

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

    from src.providers.claude_provider import (
        ClaudeDeterministicStubProvider,
        ClaudeProvider,
        get_provider,
        _to_anthropic_messages,
    )

    passed = 0
    failed = 0

    # --- T1: stub provider works without API key ---
    try:
        stub = ClaudeDeterministicStubProvider()
        result = stub.summarize_markdown_to_json("# Hello\n- bullet one\n- bullet two")
        assert result["provider"] == "claude"
        assert "summary" in result
        assert "bullets" in result
        assert isinstance(result["bullets"], list)
        print("T1 PASS: stub provider produces valid summary")
        passed += 1
    except Exception as e:
        print(f"T1 FAIL: {e}")
        failed += 1

    # --- T2: stub call_chat returns expected shape ---
    try:
        stub = ClaudeDeterministicStubProvider()
        result = stub.call_chat(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
        )
        assert result["provider"] == "claude"
        assert result["model"] == "stub"
        assert "text" in result
        assert "provider_state" in result
        assert result["provider_state"]["provider"] == "claude"
        print("T2 PASS: stub call_chat returns expected shape")
        passed += 1
    except Exception as e:
        print(f"T2 FAIL: {e}")
        failed += 1

    # --- T3: provider_id returns 'claude' ---
    try:
        stub = ClaudeDeterministicStubProvider()
        assert stub.provider_id() == "claude"
        print("T3 PASS: provider_id returns 'claude'")
        passed += 1
    except Exception as e:
        print(f"T3 FAIL: {e}")
        failed += 1

    # --- T4: supports_capability ---
    try:
        stub = ClaudeDeterministicStubProvider()
        assert stub.supports_capability("chat") is True
        assert stub.supports_capability("streaming") is False
        assert stub.supports_capability("tool_use") is False
        assert stub.supports_capability("batch") is False
        print("T4 PASS: supports_capability correct")
        passed += 1
    except Exception as e:
        print(f"T4 FAIL: {e}")
        failed += 1

    # --- T5: _to_anthropic_messages conversion ---
    try:
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "Thanks"},
        ]
        system, out = _to_anthropic_messages(messages)
        assert system == "You are helpful."
        assert len(out) == 3  # user, assistant, user (system extracted)
        assert out[0]["role"] == "user"
        assert out[1]["role"] == "assistant"
        assert out[2]["role"] == "user"
        # Verify content is in Anthropic format
        assert out[0]["content"][0]["type"] == "text"
        assert out[0]["content"][0]["text"] == "Hello"
        print("T5 PASS: _to_anthropic_messages conversion correct")
        passed += 1
    except Exception as e:
        print(f"T5 FAIL: {e}")
        failed += 1

    # --- T6: _to_anthropic_messages with no system ---
    try:
        messages = [{"role": "user", "content": "ping"}]
        system, out = _to_anthropic_messages(messages)
        assert system is None
        assert len(out) == 1
        print("T6 PASS: no system message handled correctly")
        passed += 1
    except Exception as e:
        print(f"T6 FAIL: {e}")
        failed += 1

    # --- T7: get_provider returns stub without env ---
    try:
        import os
        old_keys = {}
        for k in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
            old_keys[k] = os.environ.pop(k, None)
        try:
            p = get_provider()
            assert isinstance(p, ClaudeDeterministicStubProvider)
        finally:
            for k, v in old_keys.items():
                if v is not None:
                    os.environ[k] = v
        print("T7 PASS: get_provider returns stub without API key")
        passed += 1
    except Exception as e:
        print(f"T7 FAIL: {e}")
        failed += 1

    # --- T8: ClaudeProvider instantiation ---
    try:
        p = ClaudeProvider(api_key="test-key", model="claude-haiku-4-5-20251001")
        assert p.provider_id() == "claude"
        assert p.supports_capability("chat") is True
        assert p.supports_capability("batch") is False
        print("T8 PASS: ClaudeProvider instantiation correct")
        passed += 1
    except Exception as e:
        print(f"T8 FAIL: {e}")
        failed += 1

    # --- T9: contract parity — both providers produce provider_state ---
    try:
        from src.providers.openai_provider import DeterministicStubProvider
        openai_stub = DeterministicStubProvider()
        claude_stub = ClaudeDeterministicStubProvider()

        openai_result = openai_stub.summarize_markdown_to_json("# Test\n- a\n- b")
        claude_result = claude_stub.summarize_markdown_to_json("# Test\n- a\n- b")

        # Both must have: provider, summary, bullets
        for key in ("provider", "summary", "bullets"):
            assert key in openai_result, f"openai missing '{key}'"
            assert key in claude_result, f"claude missing '{key}'"

        assert openai_result["provider"] == "stub"
        assert claude_result["provider"] == "claude"
        print("T9 PASS: contract parity — both stubs produce compatible output")
        passed += 1
    except Exception as e:
        print(f"T9 FAIL: {e}")
        failed += 1

    print(f"\n{'='*40}")
    print(f"Claude Provider Contract: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
