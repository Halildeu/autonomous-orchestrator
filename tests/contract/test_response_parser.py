"""Contract tests for response_parser — DRY JSON extraction + schema validation."""

from __future__ import annotations

import pytest

from src.providers.response_parser import (
    extract_first_json_object,
    parse_structured_response,
    validate_json_response,
)


class TestExtractFirstJsonObject:
    """Parity with old _extract_first_json_object in claude/openai providers."""

    def test_valid_json(self) -> None:
        assert extract_first_json_object('{"a": 1}') == {"a": 1}

    def test_json_with_surrounding_text(self) -> None:
        result = extract_first_json_object('Some text {"key": "val"} more text')
        assert result == {"key": "val"}

    def test_empty_string(self) -> None:
        assert extract_first_json_object("") is None

    def test_whitespace_only(self) -> None:
        assert extract_first_json_object("   ") is None

    def test_non_dict_json(self) -> None:
        assert extract_first_json_object("[1, 2, 3]") is None

    def test_invalid_json(self) -> None:
        assert extract_first_json_object("not json at all") is None

    def test_nested_json(self) -> None:
        result = extract_first_json_object('{"outer": {"inner": true}}')
        assert result == {"outer": {"inner": True}}

    def test_json_in_markdown_code_block(self) -> None:
        text = '```json\n{"summary": "test", "bullets": []}\n```'
        result = extract_first_json_object(text)
        assert result is not None
        assert result["summary"] == "test"

    def test_multiline_json(self) -> None:
        text = '{\n  "key": "value",\n  "num": 42\n}'
        result = extract_first_json_object(text)
        assert result == {"key": "value", "num": 42}


class TestValidateJsonResponse:
    def test_valid_schema(self) -> None:
        schema = {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        }
        valid, errors = validate_json_response({"summary": "ok"}, schema)
        assert valid is True
        assert errors == []

    def test_invalid_schema(self) -> None:
        schema = {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        }
        valid, errors = validate_json_response({"other": 1}, schema)
        assert valid is False
        assert len(errors) > 0

    def test_type_mismatch(self) -> None:
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }
        valid, errors = validate_json_response({"count": "not_int"}, schema)
        assert valid is False

    def test_max_5_errors(self) -> None:
        schema = {
            "type": "object",
            "required": ["a", "b", "c", "d", "e", "f", "g"],
            "properties": {k: {"type": "string"} for k in "abcdefg"},
        }
        valid, errors = validate_json_response({}, schema)
        assert valid is False
        assert len(errors) <= 5


class TestParseStructuredResponse:
    def test_direct_json(self) -> None:
        result = parse_structured_response('{"key": "val"}')
        assert result["parsed_json"] == {"key": "val"}
        assert result["parse_method"] == "json_direct"

    def test_regex_fallback(self) -> None:
        result = parse_structured_response('prefix {"key": "val"} suffix')
        assert result["parsed_json"] == {"key": "val"}
        assert result["parse_method"] == "regex_fallback"

    def test_no_json(self) -> None:
        result = parse_structured_response("plain text without json")
        assert result["parsed_json"] is None
        assert result["parse_method"] == "failed"

    def test_empty_input(self) -> None:
        result = parse_structured_response("")
        assert result["parsed_json"] is None
        assert result["parse_method"] == "failed"

    def test_with_schema_valid(self) -> None:
        schema = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
        result = parse_structured_response('{"summary": "ok"}', expected_schema=schema)
        assert result["validation_passed"] is True
        assert result["validation_errors"] == []

    def test_with_schema_invalid(self) -> None:
        schema = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
        result = parse_structured_response('{"other": 1}', expected_schema=schema)
        assert result["validation_passed"] is False
        assert len(result["validation_errors"]) > 0

    def test_no_schema_no_validation(self) -> None:
        result = parse_structured_response('{"key": "val"}')
        assert result["validation_passed"] is None
        assert result["validation_errors"] == []
