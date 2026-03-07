from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _fail(message: str) -> None:
    raise SystemExit(f"openai_provider_contract_test failed: {message}")


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())

    import sys
    import urllib.request

    sys.path.insert(0, str(repo_root))

    from src.providers.openai_provider import OpenAIProvider

    with tempfile.TemporaryDirectory() as temp_dir:
        ws = Path(temp_dir).resolve()
        policy_path = ws / "policy_security.v1.json"
        policy_path.write_text(
            json.dumps(
                {
                    "network_access": True,
                    "network_allowlist": ["api.openai.com"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        captured: dict[str, Any] = {}
        original_urlopen = urllib.request.urlopen

        def _fake_urlopen(req: urllib.request.Request, timeout: float = 0.0) -> _FakeResponse:
            body = req.data.decode("utf-8") if isinstance(req.data, (bytes, bytearray)) else ""
            captured["request_body"] = json.loads(body)
            return _FakeResponse(
                {
                    "id": "resp-next",
                    "conversation_id": "conv-main",
                    "usage": {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
                    "output": [
                        {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "{\"summary\":\"ok\",\"bullets\":[\"b1\"]}",
                                }
                            ]
                        }
                    ],
                }
            )

        urllib.request.urlopen = _fake_urlopen
        try:
            provider = OpenAIProvider(
                api_key="test-key",
                model="gpt-5.3-codex",
                policy_path=policy_path,
            )
            result = provider.summarize_markdown_to_json(
                "# Title\n- item",
                continuation={"previous_response_id": "resp-prev", "conversation_id": "conv-main"},
            )
        finally:
            urllib.request.urlopen = original_urlopen

    body = captured.get("request_body") if isinstance(captured.get("request_body"), dict) else {}
    if str(body.get("previous_response_id") or "") != "resp-prev":
        _fail("request body missing previous_response_id")
    if str(result.get("response_id") or "") != "resp-next":
        _fail("response_id mismatch")
    if not bool(result.get("continuation_used")):
        _fail("continuation_used flag missing")
    provider_state = result.get("provider_state") if isinstance(result.get("provider_state"), dict) else {}
    if str(provider_state.get("last_response_id") or "") != "resp-next":
        _fail("provider_state last_response_id mismatch")
    if str(provider_state.get("conversation_id") or "") != "conv-main":
        _fail("provider_state conversation_id mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
