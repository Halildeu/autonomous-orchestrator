from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .github_ops import classify_github_ops_failure, _redact_message, _signature_hash_from_stderr
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


def _extract_catalog_path(text: str) -> str:
    for line in text.splitlines():
        if "catalog.v1.json" not in line:
            continue
        match = re.search(r"(/[^\\s]+catalog\\.v1\\.json)", line)
        if match:
            return match.group(1)
        parts = [p.strip() for p in line.split(":") if p.strip()]
        for part in reversed(parts):
            if "catalog.v1.json" in part:
                return part
    return ""


def _extract_json_error(text: str) -> tuple[str, int | None, int | None]:
    message = text.strip()
    if not message:
        return ("", None, None)
    match = re.search(r"line\\s+(\\d+)\\s+column\\s+(\\d+)", message)
    if match:
        return (message[:200], int(match.group(1)), int(match.group(2)))
    return (message[:200], None, None)


def _extract_advisor_paths(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        if "advisor_suggestions.v1.json" not in line:
            continue
        parts = re.split(r"[\\s\"'<>\\)\\]]+", line)
        for part in parts:
            if "advisor_suggestions.v1.json" not in part:
                continue
            cleaned = part.strip(",:;()[]")
            if cleaned.startswith("path="):
                cleaned = cleaned[len("path=") :]
            if not cleaned or "/" not in cleaned:
                continue
            if len(cleaned) > 512:
                continue
            candidates.append(cleaned)
    return sorted({c for c in candidates if c})


def _pick_advisor_path(candidates: list[str], repo_root: Path, job_workspace_root: Path | None) -> Path:
    if isinstance(job_workspace_root, Path):
        return job_workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
    normalized: list[Path] = []
    for raw in candidates:
        path = Path(raw)
        if not path.is_absolute():
            path = (repo_root / raw).resolve()
        normalized.append(path)
    if normalized:
        return sorted({p for p in normalized}, key=lambda p: p.as_posix())[0]
    return repo_root / ".cache" / "ws_integration_demo" / ".cache" / "learning" / "advisor_suggestions.v1.json"


def _job_workspace_root(job_report: dict[str, Any], repo_root: Path) -> Path | None:
    raw = job_report.get("workspace_root")
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (repo_root / raw).resolve()
    else:
        path = path.resolve()
    return path

def _advisor_job_artifact_path(job_workspace_root: Path | None, job_id: str) -> Path | None:
    if not isinstance(job_workspace_root, Path) or not job_id:
        return None
    return (
        job_workspace_root
        / ".cache"
        / "reports"
        / "jobs"
        / f"smoke_full_{job_id}"
        / "advisor_suggestions.v1.json"
    )

def _json_valid(path: Path) -> bool:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(obj, dict)


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


def run_smoke_full_triage(*, workspace_root: Path, job_id: str, detail: bool = False) -> dict[str, Any]:
    report_path = _job_report_path(workspace_root, job_id)
    if not report_path.exists():
        return {"status": "FAIL", "error_code": "JOB_REPORT_MISSING", "job_id": job_id}
    try:
        job_report = _load_json(report_path)
    except Exception:
        return {"status": "FAIL", "error_code": "JOB_REPORT_INVALID", "job_id": job_id}

    stderr_path, stdout_path, rc_path, evidence_paths = _resolve_result_paths(
        workspace_root, job_id, job_report
    )
    stderr_text = _read_text_tail(stderr_path)
    stdout_text = _read_text_tail(stdout_path)
    combined_text = stderr_text + "\n" + stdout_text
    repo_root = _repo_root()

    recommended_class, signature_hash = classify_github_ops_failure(stderr_text)
    catalog_path = _extract_catalog_path(combined_text)
    catalog_exists = False
    parse_error = ""
    error_line: int | None = None
    error_column: int | None = None

    if catalog_path:
        catalog_file = Path(catalog_path)
        catalog_exists = catalog_file.exists()
        if catalog_exists:
            try:
                json.loads(catalog_file.read_text(encoding="utf-8"))
            except Exception as e:
                parse_error, error_line, error_column = _extract_json_error(str(e))
        else:
            parse_error, error_line, error_column = _extract_json_error("catalog_file_missing")

    advisor_candidates = _extract_advisor_paths(combined_text)
    job_ws_root = _job_workspace_root(job_report, repo_root)
    advisor_expected_path = _pick_advisor_path(advisor_candidates, repo_root, job_ws_root)
    advisor_exists = advisor_expected_path.exists()
    advisor_json_valid: bool | None = None
    if advisor_exists:
        try:
            json.loads(advisor_expected_path.read_text(encoding="utf-8"))
            advisor_json_valid = True
        except Exception:
            advisor_json_valid = False
    advisor_artifact_path = _advisor_job_artifact_path(job_ws_root, job_id)
    advisor_artifact_exists = bool(advisor_artifact_path and advisor_artifact_path.exists())
    advisor_artifact_json_valid: bool | None = None
    if advisor_artifact_exists and advisor_artifact_path is not None:
        advisor_artifact_json_valid = _json_valid(advisor_artifact_path)
    advisor_workspace_ok = bool(advisor_exists and advisor_json_valid is True)
    advisor_artifact_ok = bool(advisor_artifact_exists and advisor_artifact_json_valid is True)
    if recommended_class == "DEMO_ADVISOR_SUGGESTIONS_MISSING" and (advisor_workspace_ok or advisor_artifact_ok):
        recommended_class = "OTHER"
        signature_hash = _signature_hash_from_stderr(failure_class="OTHER", stderr_text=stderr_text)

    triage_rel = str(Path(".cache") / "reports" / "smoke_full_triage.v1.json")
    triage_path = workspace_root / triage_rel
    triage_path.parent.mkdir(parents=True, exist_ok=True)
    rc_value: int | None = None
    if rc_path.exists():
        try:
            rc_value = int(_load_json(rc_path).get("rc"))
        except Exception:
            rc_value = None

    triage = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "job_id": job_id,
        "job_status": str(job_report.get("status") or ""),
        "job_kind": str(job_report.get("kind") or ""),
        "job_failure_class": str(job_report.get("failure_class") or ""),
        "recommended_class": recommended_class,
        "signature_hash": signature_hash,
        "rc": rc_value,
        "advisor_suggestions": {
            "expected_path": str(advisor_expected_path),
            "exists": bool(advisor_exists),
            "json_valid": advisor_json_valid if advisor_exists else None,
            "job_artifact_path": str(advisor_artifact_path) if advisor_artifact_path else "",
            "job_artifact_exists": bool(advisor_artifact_exists),
            "job_artifact_json_valid": advisor_artifact_json_valid if advisor_artifact_exists else None,
        },
        "catalog_parse": {
            "detected": bool(catalog_path),
            "catalog_path": catalog_path,
            "catalog_exists": bool(catalog_exists),
            "parse_error": parse_error,
            "error_line": error_line,
            "error_column": error_column,
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
        "# Smoke Full Triage",
        "",
        f"- job_id: {job_id}",
        f"- status: {triage.get('job_status')}",
        f"- failure_class: {triage.get('job_failure_class')}",
        f"- recommended_class: {recommended_class}",
    ]
    if advisor_expected_path:
        md_lines.append(f"- advisor_expected_path: {advisor_expected_path}")
        md_lines.append(f"- advisor_exists: {str(bool(advisor_exists)).lower()}")
    if advisor_artifact_path:
        md_lines.append(f"- advisor_job_artifact_path: {advisor_artifact_path}")
        md_lines.append(f"- advisor_job_artifact_exists: {str(bool(advisor_artifact_exists)).lower()}")
    if catalog_path:
        md_lines.append(f"- catalog_path: {catalog_path}")
        if parse_error:
            md_lines.append(f"- parse_error: {parse_error}")
    md_lines.append(f"- report_path: {triage_rel}")
    (workspace_root / ".cache" / "reports" / "smoke_full_triage.v1.md").write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )

    if catalog_path:
        catalog_rel = str(Path(".cache") / "reports" / "catalog_parse_triage.v1.json")
        catalog_payload = {
            "version": "v1",
            "job_id": job_id,
            "catalog_path": catalog_path,
            "catalog_exists": bool(catalog_exists),
            "parse_error": parse_error,
            "error_line": error_line,
            "error_column": error_column,
            "recommended_class": recommended_class,
            "evidence_paths": sorted(
                {
                    str(_rel_from_workspace(report_path, workspace_root)),
                    str(_rel_from_workspace(stderr_path, workspace_root)),
                    str(_rel_from_workspace(rc_path, workspace_root)),
                }
            ),
            "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
        }
        catalog_path_out = workspace_root / catalog_rel
        catalog_path_out.parent.mkdir(parents=True, exist_ok=True)
        catalog_path_out.write_text(_dump_json(catalog_payload), encoding="utf-8")
        (workspace_root / ".cache" / "reports" / "catalog_parse_triage.v1.md").write_text(
            "\n".join(
                [
                    "# Catalog Parse Triage",
                    "",
                    f"- job_id: {job_id}",
                    f"- catalog_path: {catalog_path}",
                    f"- catalog_exists: {str(bool(catalog_exists)).lower()}",
                    f"- parse_error: {parse_error or 'n/a'}",
                    f"- report_path: {catalog_rel}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    advisor_rel = str(Path(".cache") / "reports" / "advisor_expected_paths.v1.json")
    advisor_payload = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "expected_path": str(advisor_expected_path),
        "exists": bool(advisor_exists),
        "json_valid": advisor_json_valid if advisor_exists else None,
        "job_artifact_path": str(advisor_artifact_path) if advisor_artifact_path else "",
        "job_artifact_exists": bool(advisor_artifact_exists),
        "job_artifact_json_valid": advisor_artifact_json_valid if advisor_artifact_exists else None,
        "evidence_paths": sorted({str(_rel_from_workspace(report_path, workspace_root))} | set(evidence_paths)),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    advisor_path_out = workspace_root / advisor_rel
    advisor_path_out.parent.mkdir(parents=True, exist_ok=True)
    advisor_path_out.write_text(_dump_json(advisor_payload), encoding="utf-8")

    return {
        "status": "OK",
        "job_id": job_id,
        "recommended_class": recommended_class,
        "signature_hash": signature_hash,
        "report_path": triage_rel,
        "catalog_parse_path": catalog_rel if catalog_path else "",
        "advisor_expected_paths_path": advisor_rel,
    }
