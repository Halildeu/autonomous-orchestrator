"""Contract tests for capability_model — registry load, manifest resolve, negotiation."""

from __future__ import annotations

from src.providers.capability_model import (
    CapabilityManifest,
    ProviderCapability,
    get_provider_capabilities,
    load_capability_registry,
    negotiate,
    resolve_manifest,
)


class TestLoadCapabilityRegistry:
    def test_loads_from_repo(self) -> None:
        registry = load_capability_registry()
        assert registry.get("version") == "v1"
        assert "providers" in registry
        assert "claude" in registry["providers"]

    def test_has_all_providers(self) -> None:
        registry = load_capability_registry()
        providers = registry["providers"]
        for pid in ("claude", "openai", "google", "deepseek", "qwen", "xai"):
            assert pid in providers, f"Missing provider: {pid}"

    def test_capabilities_list(self) -> None:
        registry = load_capability_registry()
        caps = registry.get("capabilities", [])
        assert "chat" in caps
        assert "tool_use" in caps
        assert "streaming" in caps


class TestResolveManifest:
    def test_claude_manifest(self) -> None:
        manifest = resolve_manifest("claude")
        assert manifest.provider_id == "claude"
        assert ProviderCapability.CHAT in manifest.capabilities
        assert manifest.wire_api == "messages"
        assert manifest.auth_header == "x-api-key"

    def test_openai_manifest(self) -> None:
        manifest = resolve_manifest("openai")
        assert ProviderCapability.CHAT in manifest.capabilities
        assert ProviderCapability.BATCH in manifest.capabilities
        assert ProviderCapability.CONTINUATION in manifest.capabilities
        assert manifest.wire_api == "responses"

    def test_google_manifest(self) -> None:
        manifest = resolve_manifest("google")
        assert ProviderCapability.CHAT in manifest.capabilities
        assert ProviderCapability.EMBEDDING in manifest.capabilities

    def test_deepseek_extended_thinking(self) -> None:
        manifest = resolve_manifest("deepseek")
        assert ProviderCapability.EXTENDED_THINKING in manifest.capabilities

    def test_xai_code_agentic(self) -> None:
        manifest = resolve_manifest("xai")
        assert ProviderCapability.CODE_AGENTIC in manifest.capabilities

    def test_unknown_provider(self) -> None:
        manifest = resolve_manifest("unknown_provider")
        assert manifest.capabilities == frozenset()
        assert manifest.wire_api == "unknown"

    def test_supports_method(self) -> None:
        manifest = resolve_manifest("claude")
        assert manifest.supports(ProviderCapability.CHAT) is True
        assert manifest.supports(ProviderCapability.BATCH) is False

    def test_supports_str_method(self) -> None:
        manifest = resolve_manifest("claude")
        assert manifest.supports_str("chat") is True
        assert manifest.supports_str("batch") is False
        assert manifest.supports_str("nonexistent") is False

    def test_experimental_capabilities(self) -> None:
        manifest = resolve_manifest("claude")
        # code_agentic is experimental for claude
        assert ProviderCapability.CODE_AGENTIC in manifest.experimental

    def test_supports_includes_experimental(self) -> None:
        manifest = resolve_manifest("claude")
        # experimental should be included in supports()
        assert manifest.supports(ProviderCapability.CODE_AGENTIC) is True

    def test_with_model(self) -> None:
        manifest = resolve_manifest("claude", "claude-sonnet-4-20250514")
        assert manifest.model == "claude-sonnet-4-20250514"

    def test_probe_state_overlay(self) -> None:
        probe_state = {
            "providers": {
                "claude": {
                    "streaming": {"probe_status": "ok", "latency_ms": 50},
                },
            },
        }
        manifest = resolve_manifest("claude", probe_state=probe_state)
        # streaming was unsupported in registry, but probe says ok → experimental
        assert ProviderCapability.STREAMING in manifest.experimental


class TestNegotiate:
    def test_all_satisfied(self) -> None:
        manifest = resolve_manifest("openai")
        satisfied, missing = negotiate({ProviderCapability.CHAT, ProviderCapability.BATCH}, manifest)
        assert satisfied is True
        assert missing == set()

    def test_missing_capability(self) -> None:
        manifest = resolve_manifest("claude")
        satisfied, missing = negotiate({ProviderCapability.CHAT, ProviderCapability.BATCH}, manifest)
        assert satisfied is False
        assert ProviderCapability.BATCH in missing

    def test_empty_required(self) -> None:
        manifest = resolve_manifest("claude")
        satisfied, missing = negotiate(set(), manifest)
        assert satisfied is True
        assert missing == set()


class TestGetProviderCapabilities:
    def test_claude_capabilities_strings(self) -> None:
        caps = get_provider_capabilities("claude")
        assert "chat" in caps
        assert isinstance(caps, frozenset)

    def test_openai_includes_batch(self) -> None:
        caps = get_provider_capabilities("openai")
        assert "batch" in caps
        assert "continuation" in caps

    def test_unknown_empty(self) -> None:
        caps = get_provider_capabilities("unknown")
        assert caps == frozenset()
