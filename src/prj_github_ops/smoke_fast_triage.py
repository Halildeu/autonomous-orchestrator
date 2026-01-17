from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .failure_classifier import (
    _custom_smoke_fast_marker_override,
    _detect_smoke_markers,
    classify_github_ops_failure,
)
from .github_ops import _redact_message
from .github_ops_support_v2 import _dump_json, _job_report_path, _load_json, _rel_from_workspace


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_text_tail(path: Path, max_bytes: int = 4096) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _redacted_lines(text: str, max_lines: int = 30) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        redacted, _ = _redact_message(raw)
        if not redacted:
            continue
        lines.append(redacted)
        if len(lines) >= max_lines:
            break
    return lines


def _json_valid(path: Path) -> bool:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(obj, dict)


def _pack_advisor_semantic_ok(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"version", "generated_at", "workspace_root", "selected_pack_ids", "suggestions", "safety"}
    if not required.issubset(obj.keys()):
        return False
    selected = obj.get("selected_pack_ids")
    if not isinstance(selected, list):
        return False
    suggestions = obj.get("suggestions")
    if not isinstance(suggestions, list):
        return False
    safety = obj.get("safety") if isinstance(obj.get("safety"), dict) else None
    status = safety.get("status") if isinstance(safety, dict) else None
    return status in {"OK", "WARN", "FAIL"}


def _pack_advisor_schema_ok(obj: dict) -> bool:
    if not _pack_advisor_semantic_ok(obj):
        return False
    schema_path = _repo_root() / "schemas" / "pack-advisor-suggestions.schema.json"
    if not schema_path.exists():
        return True
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return _pack_advisor_semantic_ok(obj)
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(obj)
        return True
    except Exception:
        return False


def _load_expected_pack_advisor_paths(workspace_root: Path, root: Path) -> list[Path]:
    report_path = workspace_root / ".cache" / "reports" / "pack_advisor_suggestions_expected_paths.v0.1.json"
    expected: list[str] = []
    if report_path.exists():
        obj = _load_json(report_path)
        if isinstance(obj, dict):
            candidates = obj.get("expected_paths_sorted") or obj.get("expected_paths") or []
            if isinstance(candidates, list):
                expected = [str(p) for p in candidates if isinstance(p, str) and p.strip()]
    resolved: list[Path] = []
    root = root.resolve()
    for raw in expected:
        path = Path(raw)
        if not path.is_absolute():
            if path.name == "pack_advisor_suggestions.v1.json" and path.parent == Path("."):
                path = root / ".cache" / "learning" / path.name
            else:
                path = root / path
        try:
            path = path.resolve()
            path.relative_to(root)
        except Exception:
            continue
        if path.name != "pack_advisor_suggestions.v1.json":
            continue
        resolved.append(path)
    canonical = root / ".cache" / "learning" / "pack_advisor_suggestions.v1.json"
    if not resolved:
        resolved = [canonical]
    elif canonical not in resolved:
        resolved.append(canonical)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def _advisor_suggestions_semantic_ok(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"version", "generated_at", "workspace_root", "inputs_summary", "suggestions", "safety"}
    if not required.issubset(obj.keys()):
        return False
    suggestions = obj.get("suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return False
    kinds = {s.get("kind") for s in suggestions if isinstance(s, dict)}
    if not kinds.intersection({"NEXT_MILESTONE", "MAINTAINABILITY", "QUALITY"}):
        return False
    safety = obj.get("safety") if isinstance(obj.get("safety"), dict) else None
    status = safety.get("status") if isinstance(safety, dict) else None
    return status in {"OK", "WARN"}


def _load_expected_advisor_paths(workspace_root: Path, root: Path) -> list[Path]:
    report_path = workspace_root / ".cache" / "reports" / "advisor_suggestions_expected_paths.v0.1.json"
    expected: list[str] = []
    if report_path.exists():
        obj = _load_json(report_path)
        if isinstance(obj, dict):
            candidates = obj.get("expected_paths") or obj.get("expected_paths_sorted") or []
            if isinstance(candidates, list):
                expected = [str(p) for p in candidates if isinstance(p, str) and p.strip()]
    resolved: list[Path] = []
    root = root.resolve()
    for raw in expected:
        path = Path(raw)
        if not path.is_absolute():
            if path.name == "advisor_suggestions.v1.json" and path.parent == Path("."):
                path = root / ".cache" / "learning" / path.name
            else:
                path = root / path
        try:
            path = path.resolve()
            path.relative_to(root)
        except Exception:
            continue
        if path.name != "advisor_suggestions.v1.json":
            continue
        resolved.append(path)
    canonical = root / ".cache" / "learning" / "advisor_suggestions.v1.json"
    if not resolved:
        resolved = [canonical]
    elif canonical not in resolved:
        resolved.append(canonical)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def _selection_semantic_ok(obj: dict, required_keys: list[str]) -> bool:
    if not isinstance(obj, dict):
        return False
    for key in required_keys:
        if key not in obj:
            return False
    selected = obj.get("selected_pack_ids")
    if not isinstance(selected, list):
        return False
    return any(isinstance(s, str) and s.strip() for s in selected)


def _load_expected_pack_selection_schema_keys(workspace_root: Path) -> list[str]:
    report_path = (
        workspace_root
        / ".cache"
        / "reports"
        / "pack_selection_trace_expected_shape.v0.1.7.json"
    )
    if not report_path.exists():
        return []
    obj = _load_json(report_path)
    if not isinstance(obj, dict):
        return []
    keys = obj.get("required_keys_heuristic")
    if not isinstance(keys, list):
        return []
    return [k for k in keys if isinstance(k, str) and k.strip()]


def _load_expected_pack_selection_paths(workspace_root: Path, root: Path) -> list[Path]:
    report_path = workspace_root / ".cache" / "reports" / "pack_selection_trace_expected_paths.v1.json"
    expected: list[str] = []
    if report_path.exists():
        obj = _load_json(report_path)
        if isinstance(obj, dict):
            candidates = obj.get("expected_paths_sorted") or obj.get("expected_paths") or []
            if isinstance(candidates, list):
                expected = [str(p) for p in candidates if isinstance(p, str) and p.strip()]
    resolved: list[Path] = []
    root = root.resolve()
    for raw in expected:
        path = Path(raw)
        if not path.is_absolute():
            if path.name == "pack_selection_trace.v1.json" and path.parent == Path("."):
                path = root / ".cache" / "index" / path.name
            else:
                path = root / path
        try:
            path = path.resolve()
            path.relative_to(root)
        except Exception:
            continue
        if path.name != "pack_selection_trace.v1.json":
            continue
        resolved.append(path)
    if not resolved:
        resolved = [root / ".cache" / "index" / "pack_selection_trace.v1.json"]
    else:
        canonical = root / ".cache" / "index" / "pack_selection_trace.v1.json"
        if canonical not in resolved:
            resolved.append(canonical)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def _resolve_result_paths(
    workspace_root: Path, job_id: str, job_report: dict[str, Any]
) -> tuple[Path, Path, Path, list[str]]:
    stderr_rel = ""
    stdout_rel = ""
    rc_rel = ""
    result_paths = job_report.get("result_paths") if isinstance(job_report.get("result_paths"), list) else []
    if result_paths:
        for rel in sorted([str(p) for p in result_paths if isinstance(p, str)]):
            if rel.endswith("stderr.log") and not stderr_rel:
                stderr_rel = rel
            elif rel.endswith("stdout.log") and not stdout_rel:
                stdout_rel = rel
            elif rel.endswith("rc.json") and not rc_rel:
                rc_rel = rel
    base_dir = workspace_root / ".cache" / "github_ops" / "jobs" / job_id
    stderr_path = (workspace_root / stderr_rel) if stderr_rel else (base_dir / "stderr.log")
    stdout_path = (workspace_root / stdout_rel) if stdout_rel else (base_dir / "stdout.log")
    rc_path = (workspace_root / rc_rel) if rc_rel else (base_dir / "rc.json")
    evidence_paths = [
        _rel_from_workspace(stderr_path, workspace_root),
        _rel_from_workspace(stdout_path, workspace_root),
        _rel_from_workspace(rc_path, workspace_root),
    ]
    return stderr_path, stdout_path, rc_path, sorted({p for p in evidence_paths if p})


def run_smoke_fast_triage(*, workspace_root: Path, job_id: str, detail: bool = False) -> dict[str, Any]:
    report_path = _job_report_path(workspace_root, job_id)
    if not report_path.exists():
        return {"status": "FAIL", "error_code": "JOB_REPORT_MISSING", "job_id": job_id}
    try:
        job_report = _load_json(report_path)
    except Exception:
        return {"status": "FAIL", "error_code": "JOB_REPORT_INVALID", "job_id": job_id}

    job_status = str(job_report.get("status") or "")
    job_status_upper = job_status.upper()

    stderr_path, stdout_path, rc_path, evidence_paths = _resolve_result_paths(
        workspace_root, job_id, job_report
    )
    stderr_text = _read_text_tail(stderr_path)
    stdout_text = _read_text_tail(stdout_path)
    combined_text = stderr_text + "\n" + stdout_text

    markers = _detect_smoke_markers(stderr_text)
    recommended_class, signature_hash = classify_github_ops_failure(stderr_text)
    override = _custom_smoke_fast_marker_override(stderr_text)
    classification_override = {"used": False}
    if override:
        classification_override = {
            "used": True,
            "marker_substring": override.get("marker_substring", ""),
            "mapped_class": override.get("mapped_class", ""),
            "source": override.get("source", ""),
        }
    if job_status_upper == "PASS":
        recommended_class = "PASS"
        classification_override = {"used": False}
    catalog_path = workspace_root / ".cache" / "index" / "catalog.v1.json"
    catalog_exists = catalog_path.exists()
    catalog_json_valid: bool | None = None
    if catalog_exists:
        try:
            json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog_json_valid = True
        except Exception:
            catalog_json_valid = False

    triage_rel = str(Path(".cache") / "reports" / "smoke_fast_triage.v1.json")
    triage_path = workspace_root / triage_rel
    triage_path.parent.mkdir(parents=True, exist_ok=True)
    rc_value: int | None = None
    job_workspace_root = ""
    if rc_path.exists():
        try:
            rc_obj = _load_json(rc_path)
            rc_value = int(rc_obj.get("rc"))
            ws_raw = rc_obj.get("workspace_root")
            if isinstance(ws_raw, str) and ws_raw.strip():
                job_workspace_root = ws_raw.strip()
        except Exception:
            rc_value = None
    if job_workspace_root:
        catalog_path = Path(job_workspace_root) / ".cache" / "index" / "catalog.v1.json"
        catalog_exists = catalog_path.exists()
        catalog_json_valid = None
        if catalog_exists:
            try:
                json.loads(catalog_path.read_text(encoding="utf-8"))
                catalog_json_valid = True
            except Exception:
                catalog_json_valid = False

    pointer_root = Path(job_workspace_root) if job_workspace_root else workspace_root
    pointer_paths = sorted(
        {pointer_root / ".cache" / "artifacts" / "public_candidates.pointer.v1.json"},
        key=lambda p: str(p),
    )
    pointer_details: list[dict[str, object]] = []
    exists_all = True
    json_valid_all = True
    for pointer_path in pointer_paths:
        exists = pointer_path.exists()
        json_valid = _json_valid(pointer_path) if exists else False
        if not exists:
            exists_all = False
        if not json_valid:
            json_valid_all = False
        pointer_details.append(
            {
                "path": str(pointer_path),
                "exists": exists,
                "json_valid": json_valid if exists else None,
            }
        )

    pack_index_path = pointer_root / ".cache" / "index" / "pack_capability_index.v1.json"
    pack_index_exists = pack_index_path.exists()
    pack_index_json_valid = _json_valid(pack_index_path) if pack_index_exists else False

    pack_advisor_root = Path(job_workspace_root) if job_workspace_root else workspace_root
    pack_advisor_paths = _load_expected_pack_advisor_paths(workspace_root, pack_advisor_root)
    pack_advisor_details: list[dict[str, object]] = []
    pack_advisor_exists_all = True
    pack_advisor_json_valid_all = True
    pack_advisor_schema_valid_all = True
    for pack_advisor_path in pack_advisor_paths:
        exists = pack_advisor_path.exists()
        json_valid = _json_valid(pack_advisor_path) if exists else False
        schema_valid: bool | None = None
        if exists and json_valid:
            try:
                obj = json.loads(pack_advisor_path.read_text(encoding="utf-8"))
            except Exception:
                obj = None
            schema_valid = _pack_advisor_schema_ok(obj) if isinstance(obj, dict) else False
        if not exists:
            pack_advisor_exists_all = False
        if not json_valid:
            pack_advisor_json_valid_all = False
        if not exists or not json_valid or not schema_valid:
            pack_advisor_schema_valid_all = False
        pack_advisor_details.append(
            {
                "path": str(pack_advisor_path),
                "exists": exists,
                "json_valid": json_valid if exists else None,
                "schema_valid": schema_valid if exists and json_valid else None,
            }
        )

    advisor_root = Path(job_workspace_root) if job_workspace_root else workspace_root
    advisor_paths = _load_expected_advisor_paths(workspace_root, advisor_root)
    advisor_details: list[dict[str, object]] = []
    advisor_exists_all = True
    advisor_json_valid_all = True
    advisor_schema_valid_all = True
    for advisor_path in advisor_paths:
        exists = advisor_path.exists()
        json_valid = _json_valid(advisor_path) if exists else False
        schema_valid: bool | None = None
        if exists and json_valid:
            try:
                obj = json.loads(advisor_path.read_text(encoding="utf-8"))
            except Exception:
                obj = None
            schema_valid = _advisor_suggestions_semantic_ok(obj) if isinstance(obj, dict) else False
        if not exists:
            advisor_exists_all = False
        if not json_valid:
            advisor_json_valid_all = False
        if not exists or not json_valid or not schema_valid:
            advisor_schema_valid_all = False
        advisor_details.append(
            {
                "path": str(advisor_path),
                "exists": exists,
                "json_valid": json_valid if exists else None,
                "schema_valid": schema_valid if exists and json_valid else None,
            }
        )

    selection_root = Path(job_workspace_root) if job_workspace_root else workspace_root
    selection_required_keys = _load_expected_pack_selection_schema_keys(workspace_root)
    selection_paths = _load_expected_pack_selection_paths(workspace_root, selection_root)
    selection_details: list[dict[str, object]] = []
    selection_exists_all = True
    selection_json_valid_all = True
    selection_schema_valid_all = True
    for selection_path in selection_paths:
        exists = selection_path.exists()
        json_valid = _json_valid(selection_path) if exists else False
        schema_valid: bool | None = None
        if exists and json_valid:
            try:
                obj = json.loads(selection_path.read_text(encoding="utf-8"))
            except Exception:
                obj = None
            schema_valid = (
                _selection_semantic_ok(obj, selection_required_keys) if isinstance(obj, dict) else False
            )
        if not exists:
            selection_exists_all = False
        if not json_valid:
            selection_json_valid_all = False
        if not exists or not json_valid or not schema_valid:
            selection_schema_valid_all = False
        selection_details.append(
            {
                "path": str(selection_path),
                "exists": exists,
                "json_valid": json_valid if exists else None,
                "schema_valid": schema_valid if exists and json_valid else None,
            }
        )

    triage = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "job_id": job_id,
        "job_status": job_status,
        "job_kind": str(job_report.get("kind") or ""),
        "job_failure_class": str(job_report.get("failure_class") or ""),
        "recommended_class": recommended_class,
        "classification_override": classification_override,
        "signature_hash": signature_hash,
        "rc": rc_value,
        "job_workspace_root": job_workspace_root,
        "markers": markers,
        "marker_count": len(markers),
        "marker_detected": markers[0] if markers else None,
        "catalog": {
            "expected_path": str(catalog_path),
            "exists": bool(catalog_exists),
            "json_valid": catalog_json_valid if catalog_exists else None,
        },
        "public_candidates_pointer": {
            "expected_paths": [str(p) for p in pointer_paths],
            "exists_all": bool(exists_all),
            "json_valid_all": bool(json_valid_all),
            "details": pointer_details,
        },
        "pack_capability_index": {
            "expected_path": str(pack_index_path),
            "exists": bool(pack_index_exists),
            "json_valid": pack_index_json_valid if pack_index_exists else None,
        },
        "pack_advisor_suggestions": {
            "expected_paths": [str(p) for p in pack_advisor_paths],
            "exists_all": bool(pack_advisor_exists_all),
            "json_valid_all": bool(pack_advisor_json_valid_all),
            "schema_valid_all": bool(pack_advisor_schema_valid_all),
            "details": pack_advisor_details,
        },
        "advisor_suggestions": {
            "expected_paths": [str(p) for p in advisor_paths],
            "exists_all": bool(advisor_exists_all),
            "json_valid_all": bool(advisor_json_valid_all),
            "schema_valid_all": bool(advisor_schema_valid_all),
            "details": advisor_details,
        },
        "pack_selection_trace": {
            "expected_paths": [str(p) for p in selection_paths],
            "exists_all": bool(selection_exists_all),
            "json_valid_all": bool(selection_json_valid_all),
            "schema_valid_all": bool(selection_schema_valid_all),
            "details": selection_details,
        },
        "stderr_snippet_redacted": _redacted_lines(combined_text),
        "evidence_paths": sorted({str(_rel_from_workspace(report_path, workspace_root))} | set(evidence_paths)),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    if detail:
        triage["detail_paths"] = {
            "stderr_path": _rel_from_workspace(stderr_path, workspace_root),
            "stdout_path": _rel_from_workspace(stdout_path, workspace_root),
            "rc_path": _rel_from_workspace(rc_path, workspace_root),
        }
    triage_path.write_text(_dump_json(triage), encoding="utf-8")

    md_lines = [
        "# Smoke Fast Triage",
        "",
        f"- job_id: {job_id}",
        f"- status: {triage.get('job_status')}",
        f"- failure_class: {triage.get('job_failure_class')}",
        f"- recommended_class: {recommended_class}",
        f"- job_workspace_root: {job_workspace_root or 'n/a'}",
        f"- catalog_expected_path: {catalog_path}",
        f"- catalog_exists: {str(bool(catalog_exists)).lower()}",
        f"- marker_detected: {markers[0] if markers else 'none'}",
        f"- report_path: {triage_rel}",
    ]
    (workspace_root / ".cache" / "reports" / "smoke_fast_triage.v1.md").write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "OK",
        "job_id": job_id,
        "recommended_class": recommended_class,
        "signature_hash": signature_hash,
        "report_path": triage_rel,
    }
