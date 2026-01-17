from __future__ import annotations

from .github_ops_support_v2 import _hash_text


_CUSTOM_SMOKE_FAST_MARKER_SUBSTRING = "m8 apply must write"
_CUSTOM_SMOKE_FAST_MARKER_CLASS = "DEMO_OTHER_MARKER_2472D115C490"
_CUSTOM_SMOKE_FAST_MARKER_SOURCE = "marker_extract_v0.1.7-m9_4-r3"


def _custom_smoke_fast_marker_override(stderr_text: str) -> dict[str, str] | None:
    lowered = stderr_text.lower()
    if _CUSTOM_SMOKE_FAST_MARKER_SUBSTRING and _CUSTOM_SMOKE_FAST_MARKER_SUBSTRING in lowered:
        return {
            "marker_substring": _CUSTOM_SMOKE_FAST_MARKER_SUBSTRING,
            "mapped_class": _CUSTOM_SMOKE_FAST_MARKER_CLASS,
            "source": _CUSTOM_SMOKE_FAST_MARKER_SOURCE,
        }
    return None


def _signature_hash_from_stderr(*, failure_class: str, stderr_text: str) -> str:
    lines: list[str] = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(line[:200])
        if len(lines) >= 10:
            break
    signature_class = failure_class
    if failure_class == "POLICY_TIME_LIMIT":
        signature_class = "OTHER"
    return _hash_text(f"{signature_class}|" + "|".join(lines))


def _detect_smoke_markers(stderr_text: str) -> list[str]:
    lowered = stderr_text.lower()
    markers: list[str] = []

    def _add(name: str, hit: bool) -> None:
        if hit and name not in markers:
            markers.append(name)

    _add("TIME_LIMIT", "time_limit" in lowered or "time limit" in lowered)
    _add(
        "ADVISOR_SUGGESTIONS_MISSING",
        ("advisor_suggestions" in lowered or "advisor suggestions" in lowered)
        and ("must write" in lowered or "missing" in lowered),
    )
    _add(
        "DEMO_CATALOG_MISSING",
        "demo_catalog_missing" in lowered
        or ("ws_integration_demo" in lowered and "catalog" in lowered and "missing" in lowered)
        or ("catalog" in lowered and "pack-demo" in lowered and "must include" in lowered),
    )
    _add(
        "DEMO_CATALOG_PARSE",
        "demo_catalog_parse" in lowered
        or ("ws_integration_demo" in lowered and "catalog" in lowered and "parse" in lowered)
        or ("catalog" in lowered and "valid json" in lowered),
    )
    _add(
        "DEMO_PREREQ_APPLY_FAIL",
        "prerequisite apply failed" in lowered and "ws_integration_demo" in lowered,
    )
    _add(
        "DEMO_PREREQ_FAIL",
        ("formats.v1.json" in lowered and "must write" in lowered)
        or ("formats index" in lowered and "must write" in lowered)
        or ("m2.5 apply" in lowered and "formats" in lowered),
    )
    _add(
        "DEMO_QUALITY_GATE_REPORT_MISSING",
        ("quality_gate_report.v1.json" in lowered and ("missing" in lowered or "must write" in lowered))
        or ("quality gate report" in lowered and "must write" in lowered)
        or ("m6 apply" in lowered and "quality" in lowered and "must write" in lowered),
    )
    _add(
        "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING",
        ("public_candidates.pointer.v1.json" in lowered and ("must write" in lowered or "missing" in lowered))
        or ("m6.8 apply" in lowered and "pointer" in lowered and "must write" in lowered),
    )
    _add(
        "DEMO_PACK_CAPABILITY_INDEX_MISSING",
        ("pack_capability_index.v1.json" in lowered and ("must write" in lowered or "missing" in lowered))
        or ("pack capability index" in lowered and "must write" in lowered)
        or ("m9.2 apply" in lowered and "pack index" in lowered and "must write" in lowered),
    )
    _add(
        "DEMO_M9_3_APPLY_MUST_WRITE_PACK_SELECTION_TRACE_V1_JSON",
        ("pack_selection_trace.v1.json" in lowered and ("must write" in lowered or "missing" in lowered))
        or ("m9.3 apply" in lowered and "pack_selection_trace" in lowered),
    )
    _add(
        "DEMO_SESSION_CONTEXT_HASH_MISMATCH",
        ("session_context_hash" in lowered and "matching" in lowered and "session sha" in lowered)
        or ("roadmap-finish" in lowered and "output.json" in lowered and "session_context_hash" in lowered),
    )
    _add(
        "DEMO_SESSION_CONTEXT_MISSING",
        ("session_context.v1.json" in lowered and ("missing" in lowered or "must write" in lowered))
        or ("session context" in lowered and "must write" in lowered),
    )
    _add("SCHEMA_VALIDATION_FAIL", "schema validation" in lowered or "integrity verify" in lowered)
    _add(
        "CONTEXT_ROUTER_CRASH",
        "context-router" in lowered or "context_router" in lowered or "context router" in lowered,
    )
    _add("ARGPARSE_ERROR", "argparse" in lowered or "unrecognized arguments" in lowered)
    return markers


def _classify_from_markers(markers: list[str]) -> str:
    mapping = {
        "TIME_LIMIT": "POLICY_TIME_LIMIT",
        "ADVISOR_SUGGESTIONS_MISSING": "DEMO_ADVISOR_SUGGESTIONS_MISSING",
        "DEMO_CATALOG_MISSING": "DEMO_CATALOG_MISSING",
        "DEMO_CATALOG_PARSE": "DEMO_CATALOG_PARSE",
        "DEMO_PREREQ_APPLY_FAIL": "DEMO_PREREQ_APPLY_FAIL",
        "DEMO_PREREQ_FAIL": "DEMO_PREREQ_FAIL",
        "DEMO_QUALITY_GATE_REPORT_MISSING": "DEMO_QUALITY_GATE_REPORT_MISSING",
        "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING": "DEMO_PUBLIC_CANDIDATES_POINTER_MISSING",
        "DEMO_PACK_CAPABILITY_INDEX_MISSING": "DEMO_PACK_CAPABILITY_INDEX_MISSING",
        "DEMO_M9_3_APPLY_MUST_WRITE_PACK_SELECTION_TRACE_V1_JSON": "DEMO_M9_3_APPLY_MUST_WRITE_PACK_SELECTION_TRACE_V1_JSON",
        "DEMO_SESSION_CONTEXT_HASH_MISMATCH": "DEMO_SESSION_CONTEXT_HASH_MISMATCH",
        "DEMO_SESSION_CONTEXT_MISSING": "DEMO_SESSION_CONTEXT_MISSING",
        "SCHEMA_VALIDATION_FAIL": "CORE_BREAK",
        "CONTEXT_ROUTER_CRASH": "CORE_BREAK",
        "ARGPARSE_ERROR": "CORE_BREAK",
    }
    for marker in markers:
        mapped = mapping.get(marker)
        if mapped:
            return mapped
    return "OTHER"


def classify_github_ops_failure(stderr_text: str) -> tuple[str, str]:
    markers = _detect_smoke_markers(stderr_text)
    failure_class = _classify_from_markers(markers)
    override = _custom_smoke_fast_marker_override(stderr_text)
    if override:
        failure_class = override["mapped_class"]
    signature_hash = _signature_hash_from_stderr(failure_class=failure_class, stderr_text=stderr_text)
    return failure_class, signature_hash
