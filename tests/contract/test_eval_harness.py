"""Contract tests for eval_harness — 6 checks + scorecard."""

from __future__ import annotations

import json

from src.orchestrator.eval_harness import (
    check_citation_completeness,
    check_groundedness,
    check_json_conformance,
    check_refusal_correctness,
    check_tool_result_consistency,
    check_truncation_safety,
    eval_scorecard,
    run_eval_suite,
)


class TestJsonConformance:
    def test_valid_json(self) -> None:
        r = check_json_conformance('{"key": "value"}')
        assert r.passed is True
        assert r.score == 1.0

    def test_invalid_json(self) -> None:
        r = check_json_conformance("not json")
        assert r.passed is False
        assert r.score == 0.0

    def test_array_not_object(self) -> None:
        r = check_json_conformance("[1, 2, 3]")
        assert r.passed is False
        assert r.score == 0.2

    def test_with_schema_valid(self) -> None:
        schema = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
        r = check_json_conformance('{"summary": "ok"}', schema)
        assert r.passed is True

    def test_with_schema_invalid(self) -> None:
        schema = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
        r = check_json_conformance('{"other": 1}', schema)
        assert r.passed is False


class TestGroundedness:
    def test_grounded(self) -> None:
        output = "The system status shows healthy services with good latency."
        context = ["system status report: healthy services, latency under threshold"]
        r = check_groundedness(output, context)
        assert r.passed is True
        assert r.score > 0.3

    def test_ungrounded(self) -> None:
        output = "The quantum computer achieved superluminal teleportation yesterday."
        context = ["system status report: all services healthy"]
        r = check_groundedness(output, context)
        assert r.score < 0.5

    def test_empty_context(self) -> None:
        r = check_groundedness("any output", [])
        assert r.passed is True
        assert r.score == 1.0

    def test_empty_output(self) -> None:
        r = check_groundedness("", ["some context"])
        assert r.passed is True  # no words to check


class TestCitationCompleteness:
    def test_all_refs_found(self) -> None:
        output = "See policy_security.v1.json and policy_llm_live.v1.json for details."
        refs = ["policy_security.v1.json", "policy_llm_live.v1.json"]
        r = check_citation_completeness(output, refs)
        assert r.passed is True
        assert r.score == 1.0

    def test_missing_refs(self) -> None:
        output = "See policy_security.v1.json for details."
        refs = ["policy_security.v1.json", "policy_llm_live.v1.json"]
        r = check_citation_completeness(output, refs)
        assert r.score == 0.5

    def test_no_expected_refs(self) -> None:
        r = check_citation_completeness("any output", [])
        assert r.passed is True


class TestToolResultConsistency:
    def test_consistent(self) -> None:
        calls = [{"name": "system-status", "input": {}}]
        results = [{"output": {"status": "OK", "services": 18}}]
        output = "The system status is OK with 18 services running."
        r = check_tool_result_consistency(calls, results, output)
        assert r.passed is True

    def test_inconsistent(self) -> None:
        calls = [{"name": "system-status", "input": {}}]
        results = [{"output": {"status": "OK", "services": 18}}]
        output = "I don't know the system status."
        r = check_tool_result_consistency(calls, results, output)
        assert r.score < 1.0

    def test_no_tool_calls(self) -> None:
        r = check_tool_result_consistency([], [], "any output")
        assert r.passed is True


class TestRefusalCorrectness:
    def test_correct_refusal(self) -> None:
        r = check_refusal_correctness("I cannot help with that request.", should_refuse=True)
        assert r.passed is True

    def test_missed_refusal(self) -> None:
        r = check_refusal_correctness("Sure, here is the answer.", should_refuse=True)
        assert r.passed is False

    def test_incorrect_refusal(self) -> None:
        r = check_refusal_correctness("I'm sorry, but I cannot do that.", should_refuse=False)
        assert r.passed is False

    def test_correct_acceptance(self) -> None:
        r = check_refusal_correctness("Here is the system status.", should_refuse=False)
        assert r.passed is True


class TestTruncationSafety:
    def test_complete_output(self) -> None:
        r = check_truncation_safety("The system is healthy.")
        assert r.passed is True
        assert r.score == 1.0

    def test_empty_output(self) -> None:
        r = check_truncation_safety("")
        assert r.passed is False

    def test_truncated_json(self) -> None:
        r = check_truncation_safety('{"key": "value", "nested": {')
        assert r.passed is False
        assert "truncated mid-JSON" in r.reason

    def test_complete_json(self) -> None:
        r = check_truncation_safety('{"key": "value"}')
        assert r.passed is True


class TestRunEvalSuite:
    def test_basic_suite(self) -> None:
        results = run_eval_suite("The system is healthy.")
        assert len(results) >= 2  # truncation + refusal

    def test_suite_with_json(self) -> None:
        results = run_eval_suite('{"summary": "ok"}')
        check_ids = [r.check_id for r in results]
        assert "json_conformance" in check_ids
        assert "truncation_safety" in check_ids

    def test_suite_with_context(self) -> None:
        results = run_eval_suite(
            "System healthy.",
            context_sources=["system status: healthy"],
        )
        check_ids = [r.check_id for r in results]
        assert "groundedness" in check_ids

    def test_suite_with_tools(self) -> None:
        results = run_eval_suite(
            "Status OK.",
            tool_calls=[{"name": "test"}],
            tool_results=[{"output": {"status": "OK"}}],
        )
        check_ids = [r.check_id for r in results]
        assert "tool_consistency" in check_ids


class TestEvalScorecard:
    def test_all_passed(self) -> None:
        results = run_eval_suite("The system is healthy and operational.")
        card = eval_scorecard(results)
        assert card["total_checks"] >= 2
        assert card["all_passed"] is True

    def test_scorecard_shape(self) -> None:
        results = run_eval_suite("test")
        card = eval_scorecard(results)
        assert "total_checks" in card
        assert "passed" in card
        assert "failed" in card
        assert "avg_score" in card
        assert "checks" in card

    def test_empty_results(self) -> None:
        card = eval_scorecard([])
        assert card["total_checks"] == 0
        assert card["all_passed"] is True
