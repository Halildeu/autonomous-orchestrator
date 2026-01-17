from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn
from src.ops.commands.extension_cmds_helpers_v2 import _resolve_workspace_root
from src.prj_github_ops.github_ops import _redact_message
from src.prj_github_ops.github_ops_support_v2 import (
    _dump_json,
    _job_report_path,
    _load_json,
    _now_iso,
    _rel_from_workspace,
    _hash_text,
)


def _read_text_tail(path: Path, max_bytes: int = 8192) -> str:
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


def _redact_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        redacted, _ = _redact_message(raw)
        if not redacted:
            continue
        lines.append(redacted)
    return lines


def _specificity_score(line: str) -> int:
    normalized = re.sub(r"\s+", " ", line).strip()
    tokens = [t for t in re.split(r"[^A-Za-z0-9_./:-]+", normalized) if t]
    return len(normalized) + 5 * len(tokens)


def _extract_candidates(lines_by_weight: list[tuple[int, list[str]]]) -> list[str]:
    patterns = [
        re.compile(r"m\d+\.\d+", re.IGNORECASE),
        re.compile(r"must write .*?\.v1\.json", re.IGNORECASE),
        re.compile(r"must write", re.IGNORECASE),
        re.compile(r"missing .*?\.v1\.json", re.IGNORECASE),
        re.compile(r"expected .*?\.v1\.json", re.IGNORECASE),
        re.compile(r"\.v1\.json", re.IGNORECASE),
        re.compile(r"pack_", re.IGNORECASE),
        re.compile(r"advisor", re.IGNORECASE),
        re.compile(r"selection", re.IGNORECASE),
        re.compile(r"index", re.IGNORECASE),
        re.compile(r"trace", re.IGNORECASE),
    ]
    scored: dict[str, int] = {}
    for weight, lines in lines_by_weight:
        for line in lines:
            for cre in patterns:
                if cre.search(line):
                    score = weight + _specificity_score(line)
                    current = scored.get(line.strip())
                    if current is None or score > current:
                        scored[line.strip()] = score
                    break
    deduped = sorted(scored.items(), key=lambda item: (-item[1], item[0]))
    return [line for line, _ in deduped[:25]]


def _derive_marker_substring(picked_marker: str) -> str:
    if not picked_marker:
        return ""
    match = re.search(r"m\d+\.\d+", picked_marker, re.IGNORECASE)
    if match:
        return match.group(0).lower()
    match = re.search(r"m\d+(?:\.\d+)?\s+apply\s+must\s+write", picked_marker, re.IGNORECASE)
    if match:
        return match.group(0).lower()
    fname = re.search(r"[A-Za-z0-9_.-]+\.v1\.json", picked_marker)
    if fname:
        return fname.group(0).lower()
    normalized = re.sub(r"\s+", " ", picked_marker).strip()
    return normalized[:80].lower()


def _derive_failure_class(picked_marker: str) -> str | None:
    if not picked_marker:
        return None
    lowered = picked_marker.lower()
    match = re.search(r"m(\d+)\.(\d+)", lowered)
    files = re.findall(r"[A-Za-z0-9_.-]+\.v1\.json", picked_marker)
    if match and "must write" in lowered and files:
        major, minor = match.group(1), match.group(2)
        filename = sorted({f for f in files}, key=lambda s: s.lower())[0]
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", filename).strip("_").upper()
        return f"DEMO_M{major}_{minor}_APPLY_MUST_WRITE_{cleaned}"
    suffix = _hash_text(picked_marker)[:12].upper()
    return f"DEMO_OTHER_MARKER_{suffix}"


def _resolve_candidate_path(raw: str, workspace_root: Path, root: Path) -> Path | None:
    raw_str = str(raw or "").strip()
    if not raw_str:
        return None
    path = Path(raw_str)
    roots = [workspace_root.resolve(), root.resolve()]
    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path.resolve())
    else:
        if ".." in path.parts:
            return None
        if path.parts and path.parts[0] == ".cache":
            candidates.append((workspace_root / path).resolve())
        else:
            candidates.append((workspace_root / ".cache" / path).resolve())
        candidates.append((workspace_root / path).resolve())
        candidates.append((root / path).resolve())
    allowed = []
    for cand in candidates:
        for base in roots:
            try:
                cand.relative_to(base)
                allowed.append(cand)
                break
            except Exception:
                continue
    if not allowed:
        return None
    for cand in allowed:
        if cand.exists():
            return cand
    return allowed[0]


def _gather_paths(job_report: dict[str, Any], workspace_root: Path, root: Path) -> list[Path]:
    paths: list[str] = []
    for field in ("stderr_path", "stdout_path", "rc_path", "log_path", "rc_file", "stderr_file", "stdout_file", "log_file"):
        value = job_report.get(field)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    result_paths = job_report.get("result_paths")
    if isinstance(result_paths, list):
        paths.extend([str(p) for p in result_paths if isinstance(p, str) and str(p).strip()])
    for field in ("artifacts", "files"):
        items = job_report.get(field)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                value = item.get("path") or item.get("file") or item.get("filepath")
                if isinstance(value, str) and value.strip():
                    paths.append(value.strip())
            elif isinstance(item, str) and item.strip():
                paths.append(item.strip())

    resolved: list[Path] = []
    for raw in paths:
        resolved_path = _resolve_candidate_path(raw, workspace_root, root)
        if resolved_path is not None:
            resolved.append(resolved_path)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def run_smoke_fast_marker_extract(
    *, workspace_root: Path, job_id: str, out_path: Path
) -> dict[str, Any]:
    report_path = _job_report_path(workspace_root, job_id)
    if not report_path.exists():
        return {"status": "FAIL", "error_code": "JOB_REPORT_MISSING", "job_id": job_id}
    try:
        job_report = _load_json(report_path)
    except Exception:
        return {"status": "FAIL", "error_code": "JOB_REPORT_INVALID", "job_id": job_id}

    embedded_fields = []
    stderr_texts: list[str] = []
    stdout_texts: list[str] = []
    other_texts: list[str] = []
    for field in ("stderr", "stdout", "rc", "log", "error", "message", "summary"):
        value = job_report.get(field)
        if isinstance(value, str) and value.strip():
            embedded_fields.append(field)
            if field == "stderr":
                stderr_texts.append(value)
            elif field == "stdout":
                stdout_texts.append(value)
            else:
                other_texts.append(value)

    root = repo_root()
    paths = _gather_paths(job_report, workspace_root, root)
    missing_paths: list[str] = []
    file_texts: list[str] = []
    for path in paths:
        if path.exists() and path.is_file():
            text = _read_text_tail(path)
            file_texts.append(text)
            name = path.name.lower()
            if "stderr" in name:
                stderr_texts.append(text)
            elif "stdout" in name:
                stdout_texts.append(text)
            else:
                other_texts.append(text)
        else:
            missing_paths.append(str(path))

    stderr_lines = _redact_lines("\n".join(stderr_texts))
    stdout_lines = _redact_lines("\n".join(stdout_texts))
    other_lines = _redact_lines("\n".join(other_texts))
    candidates = _extract_candidates(
        [
            (2_000_000, stderr_lines),
            (1_000_000, stdout_lines),
            (0, other_lines),
        ]
    )
    picked_marker = candidates[0] if candidates else None
    marker_substring = _derive_marker_substring(picked_marker) if picked_marker else ""
    derived_class = _derive_failure_class(picked_marker) if picked_marker else None

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "job_id": job_id,
        "job_report_path": _rel_from_workspace(report_path, workspace_root),
        "status": "OK",
        "error_code": None,
        "embedded_fields": sorted(set(embedded_fields)),
        "artifact_paths": {
            "resolved": sorted({str(p) for p in paths}),
            "missing": sorted({p for p in missing_paths}),
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "picked_marker": picked_marker,
        "marker_substring": marker_substring,
        "derived_failure_class": derived_class,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "TRAVERSAL_BLOCKED=true"],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_dump_json(payload), encoding="utf-8")
    return {"status": "OK", "report_path": _rel_from_workspace(out_path, workspace_root)}


def _resolve_out_path(workspace_root: Path, out_arg: str) -> Path | None:
    raw = Path(str(out_arg or "").strip())
    if not str(raw):
        return None
    repo = repo_root().resolve()
    ws_abs = workspace_root.resolve()
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        raw_posix = raw.as_posix()
        ws_rel = ""
        try:
            ws_rel = ws_abs.relative_to(repo).as_posix()
        except Exception:
            ws_rel = ""
        if ws_rel and raw_posix.startswith(ws_rel.rstrip("/") + "/"):
            candidate = (repo / raw).resolve()
        else:
            candidate = (ws_abs / raw).resolve()
    reports_root = (ws_abs / ".cache" / "reports").resolve()
    try:
        candidate.relative_to(reports_root)
    except Exception:
        return None
    return candidate


def cmd_smoke_fast_marker_extract(args: argparse.Namespace) -> int:
    ws = _resolve_workspace_root(args)
    if ws is None:
        return 2
    job_id = str(getattr(args, "job_id", "") or "").strip()
    if not job_id:
        warn("FAIL error=JOB_ID_REQUIRED")
        return 2
    out_arg = str(getattr(args, "out", "") or "").strip()
    out_path = _resolve_out_path(ws, out_arg)
    if out_path is None:
        warn("FAIL error=OUT_PATH_INVALID")
        return 2
    payload = run_smoke_fast_marker_extract(workspace_root=ws, job_id=job_id, out_path=out_path)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else "WARN"
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def register_smoke_fast_marker_extract_subcommand(
    parent: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    ap = parent.add_parser(
        "smoke-fast-marker-extract",
        help="Extract deterministic marker candidates from smoke fast job artifacts (program-led).",
    )
    ap.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap.add_argument("--job-id", required=True, help="Job id.")
    ap.add_argument("--out", required=True, help="Output report path under workspace .cache/reports.")
    ap.set_defaults(func=cmd_smoke_fast_marker_extract)
