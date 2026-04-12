"""Contract tests for prompt_registry — load, resolve, experiment lanes, lineage."""

from __future__ import annotations

from src.prj_kernel_api.prompt_registry import (
    LANE_CANARY,
    LANE_CONTROL,
    LANE_SHADOW,
    LANE_TREATMENT,
    PromptEntry,
    _compute_prompt_hash,
    load_prompt_registry,
    record_prompt_lineage,
    resolve_prompt,
    select_experiment_lane,
)


def _make_entry(**overrides) -> PromptEntry:
    defaults = {
        "prompt_id": "test-prompt",
        "version": "1.0.0",
        "prompt_hash": "abc123",
        "template": "Test template",
        "model_compatibility": ["claude-*", "gpt-*"],
        "tool_schema_version": None,
        "guardrail_version": "v1",
        "input_schema": None,
        "output_schema": None,
        "eval_score": None,
        "last_tested_at": None,
        "experiment_id": None,
        "lane": LANE_CONTROL,
        "rollout_pct": 100,
        "owner": None,
        "status": "active",
    }
    defaults.update(overrides)
    return PromptEntry(**defaults)


class TestComputePromptHash:
    def test_deterministic(self) -> None:
        h1 = _compute_prompt_hash("test template")
        h2 = _compute_prompt_hash("test template")
        assert h1 == h2

    def test_different_input(self) -> None:
        h1 = _compute_prompt_hash("template A")
        h2 = _compute_prompt_hash("template B")
        assert h1 != h2

    def test_length(self) -> None:
        h = _compute_prompt_hash("any")
        assert len(h) == 16


class TestLoadPromptRegistry:
    def test_loads_from_repo(self) -> None:
        registry = load_prompt_registry(".")
        assert "summarize_to_json" in registry

    def test_entry_shape(self) -> None:
        registry = load_prompt_registry(".")
        entry = registry.get("summarize_to_json")
        assert entry is not None
        assert entry.version == "1.0.0"
        assert entry.lane == LANE_CONTROL
        assert entry.rollout_pct == 100
        assert entry.status == "active"

    def test_missing_dir(self) -> None:
        registry = load_prompt_registry("/nonexistent/path")
        # Falls back to repo root
        assert isinstance(registry, dict)


class TestResolvePrompt:
    def test_found_compatible(self) -> None:
        registry = {"test-prompt": _make_entry()}
        result = resolve_prompt("test-prompt", provider_id="claude", model="claude-sonnet-4", registry=registry)
        assert result is not None
        assert result.prompt_id == "test-prompt"

    def test_not_found(self) -> None:
        result = resolve_prompt("nonexistent", provider_id="claude", model="claude-sonnet-4", registry={})
        assert result is None

    def test_incompatible_model(self) -> None:
        registry = {"test": _make_entry(model_compatibility=["gpt-*"])}
        result = resolve_prompt("test", provider_id="claude", model="claude-sonnet-4", registry=registry)
        assert result is None

    def test_wildcard_all(self) -> None:
        registry = {"test": _make_entry(model_compatibility=["*"])}
        result = resolve_prompt("test", provider_id="any", model="any-model", registry=registry)
        assert result is not None

    def test_archived_excluded(self) -> None:
        registry = {"test": _make_entry(status="archived")}
        result = resolve_prompt("test", provider_id="claude", model="claude-sonnet-4", registry=registry)
        assert result is None

    def test_prefix_match(self) -> None:
        registry = {"test": _make_entry(model_compatibility=["claude-*"])}
        result = resolve_prompt("test", provider_id="claude", model="claude-opus-4-5", registry=registry)
        assert result is not None


class TestSelectExperimentLane:
    def test_control_only(self) -> None:
        prompts = [_make_entry(lane=LANE_CONTROL)]
        result = select_experiment_lane(prompts)
        assert result is not None
        assert result.lane == LANE_CONTROL

    def test_empty_prompts(self) -> None:
        assert select_experiment_lane([]) is None

    def test_archived_excluded(self) -> None:
        prompts = [_make_entry(status="archived")]
        assert select_experiment_lane(prompts) is None

    def test_treatment_lane(self) -> None:
        # With 100% rollout treatment, it should always be selected
        prompts = [
            _make_entry(prompt_id="control", lane=LANE_CONTROL, rollout_pct=100),
            _make_entry(prompt_id="treatment", lane=LANE_TREATMENT, rollout_pct=100),
        ]
        # Run multiple times — treatment should win with 100% rollout
        results = set()
        for _ in range(10):
            r = select_experiment_lane(prompts)
            if r:
                results.add(r.lane)
        assert LANE_TREATMENT in results

    def test_zero_rollout_not_selected(self) -> None:
        prompts = [
            _make_entry(prompt_id="control", lane=LANE_CONTROL, rollout_pct=100),
            _make_entry(prompt_id="treatment", lane=LANE_TREATMENT, rollout_pct=0),
        ]
        for _ in range(20):
            r = select_experiment_lane(prompts)
            assert r is not None
            assert r.lane == LANE_CONTROL


class TestRecordPromptLineage:
    def test_writes_lineage(self, tmp_path) -> None:
        record_prompt_lineage(
            workspace_root=str(tmp_path),
            prompt_id="test-prompt",
            prompt_version="1.0.0",
            prompt_hash="abc123",
            model="claude-sonnet-4",
            provider_id="claude",
            experiment_id="exp-001",
            lane=LANE_TREATMENT,
            eval_score=0.95,
            run_id="run-123",
        )
        lineage_path = tmp_path / ".cache" / "index" / "prompt_lineage.v1.jsonl"
        assert lineage_path.exists()
        import json
        lines = lineage_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["prompt_id"] == "test-prompt"
        assert entry["lane"] == LANE_TREATMENT
        assert entry["eval_score"] == 0.95

    def test_appends_multiple(self, tmp_path) -> None:
        for i in range(3):
            record_prompt_lineage(
                workspace_root=str(tmp_path),
                prompt_id=f"prompt-{i}",
                prompt_version="1.0.0",
                prompt_hash=f"hash{i}",
                model="gpt-4o",
                provider_id="openai",
            )
        lineage_path = tmp_path / ".cache" / "index" / "prompt_lineage.v1.jsonl"
        lines = lineage_path.read_text().strip().split("\n")
        assert len(lines) == 3
