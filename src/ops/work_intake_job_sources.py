from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _rel_to_workspace(path: Path, workspace_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return None


def _load_doc_nav_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    report_path = workspace_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    if not report_path.exists():
        notes.append("doc_nav_strict_missing")
        return []
    try:
        obj = _load_json(report_path)
    except Exception:
        notes.append("doc_nav_strict_invalid")
        return []
    counts = obj.get("counts") if isinstance(obj, dict) else None
    critical = int(counts.get("critical_nav_gaps", 0)) if isinstance(counts, dict) else 0
    broken_refs = int(counts.get("broken_refs", 0)) if isinstance(counts, dict) else 0
    if critical <= 0 and broken_refs <= 0:
        return []
    evidence = [str(Path(".cache") / "reports" / "doc_graph_report.strict.v1.json")]
    return [
        {
            "source_type": "DOC_NAV",
            "source_ref": f"critical_nav_gaps={critical};broken_refs={broken_refs}",
            "title": "Doc nav critical gaps",
            "critical_nav_gaps": critical,
            "broken_refs": broken_refs,
            "evidence_paths": evidence,
        }
    ]


def _github_ops_source(signal: str, *, title: str, evidence: list[str]) -> dict[str, Any]:
    return {
        "source_type": "GITHUB_OPS",
        "source_ref": f"github_ops:{signal}",
        "title": title,
        "github_ops_signal": signal,
        "evidence_paths": evidence,
    }


def _load_github_ops_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    report_rel = str(Path(".cache") / "reports" / "github_ops_report.v1.json")
    report_path = workspace_root / report_rel
    if not report_path.exists():
        notes.append("github_ops_report_missing")
        return []
    try:
        report = _load_json(report_path)
    except Exception:
        notes.append("github_ops_report_invalid")
        return []
    evidence_base = [report_rel]

    signals = report.get("signals") if isinstance(report, dict) else None
    signals = [str(s) for s in signals if isinstance(s, str) and s] if isinstance(signals, list) else []
    sources: list[dict[str, Any]] = []
    for signal in sorted(set(signals)):
        title = f"GitHub ops signal: {signal}"
        sources.append(_github_ops_source(signal, title=title, evidence=evidence_base))

    index_rel = str(report.get("jobs_index_path") or str(Path(".cache") / "github_ops" / "jobs_index.v1.json"))
    index_path = workspace_root / index_rel
    if not index_path.exists():
        notes.append("github_ops_jobs_index_missing")
        return sources
    try:
        index_obj = _load_json(index_path)
    except Exception:
        notes.append("github_ops_jobs_index_invalid")
        return sources
    jobs = index_obj.get("jobs") if isinstance(index_obj, dict) else None
    if not isinstance(jobs, list):
        notes.append("github_ops_jobs_index_empty")
        return sources

    for job in sorted([j for j in jobs if isinstance(j, dict)], key=lambda j: str(j.get("job_id") or "")):
        status = str(job.get("status") or "")
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            continue
        job_id = str(job.get("job_id") or "")
        job_kind = str(job.get("kind") or "")
        if not job_id or not job_kind:
            continue
        evidence = list(evidence_base)
        for p in job.get("evidence_paths") if isinstance(job.get("evidence_paths"), list) else []:
            if isinstance(p, str):
                evidence.append(p)
        for p in job.get("result_paths") if isinstance(job.get("result_paths"), list) else []:
            if isinstance(p, str):
                evidence.append(p)
        sources.append(
            {
                "source_type": "GITHUB_OPS",
                "source_ref": job_id,
                "title": f"GitHub ops job {status}: {job_kind}",
                "github_ops_job_status": status,
                "github_ops_job_kind": job_kind,
                "github_ops_job_skip_reason": str(job.get("skip_reason") or ""),
                "github_ops_job_failure_class": str(job.get("failure_class") or ""),
                "github_ops_signature_hash": str(job.get("signature_hash") or ""),
                "evidence_paths": evidence,
            }
        )

    if not sources:
        notes.append("github_ops_sources_empty")
    return sources


def _load_job_status_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    index_path = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
    if not index_path.exists():
        notes.append("jobs_index_missing")
        return []
    try:
        obj = _load_json(index_path)
    except Exception:
        notes.append("jobs_index_invalid")
        return []
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list):
        notes.append("jobs_index_empty")
        return []
    sources: list[dict[str, Any]] = []
    evidence_base = [str(Path(".cache") / "airunner" / "jobs_index.v1.json")]
    for job in sorted([j for j in jobs if isinstance(j, dict)], key=lambda j: str(j.get("job_id") or "")):
        status = str(job.get("status") or "")
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            continue
        job_id = str(job.get("job_id") or "")
        job_type = str(job.get("job_type") or "")
        if not job_id or not job_type:
            continue
        evidence = list(evidence_base)
        job_evidence = job.get("evidence_paths") if isinstance(job.get("evidence_paths"), list) else []
        for p in job_evidence:
            if isinstance(p, str):
                evidence.append(p)
        result_paths = job.get("result_paths") if isinstance(job.get("result_paths"), list) else []
        for p in result_paths:
            if isinstance(p, str):
                evidence.append(p)
        sources.append(
            {
                "source_type": "JOB_STATUS",
                "source_ref": job_id,
                "title": f"Job {status}: {job_type}",
                "job_status": status,
                "job_type": job_type,
                "job_skip_reason": str(job.get("skip_reason") or ""),
                "job_error_code": str(job.get("error_code") or ""),
                "job_failure_class": str(job.get("failure_class") or ""),
                "job_signature_hash": str(job.get("signature_hash") or ""),
                "evidence_paths": evidence,
            }
        )
    return sources


def _load_time_sink_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    report_path = workspace_root / ".cache" / "reports" / "time_sinks.v1.json"
    if not report_path.exists():
        notes.append("time_sinks_missing")
        return []
    try:
        obj = _load_json(report_path)
    except Exception:
        notes.append("time_sinks_invalid")
        return []
    sinks = obj.get("sinks") if isinstance(obj, dict) else None
    if not isinstance(sinks, list):
        notes.append("time_sinks_empty")
        return []
    sources: list[dict[str, Any]] = []
    evidence = [str(Path(".cache") / "reports" / "time_sinks.v1.json")]
    for sink in sorted([s for s in sinks if isinstance(s, dict)], key=lambda s: str(s.get("event_key") or "")):
        event_key = str(sink.get("event_key") or "")
        if not event_key:
            continue
        breach_count = int(sink.get("breach_count", 0) or 0)
        if breach_count <= 0:
            continue
        sources.append(
            {
                "source_type": "TIME_SINK",
                "source_ref": event_key,
                "title": f"Time sink: {event_key}",
                "time_sink_breach_count": breach_count,
                "evidence_paths": evidence,
            }
        )
    return sources


def _cooldown_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "intake_cooldowns.v1.json"


def _load_cooldowns(workspace_root: Path) -> dict[str, Any]:
    path = _cooldown_path(workspace_root)
    if not path.exists():
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "entries": {},
            "notes": [],
        }
    try:
        obj = _load_json(path)
    except Exception:
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "entries": {},
            "notes": ["cooldown_invalid"],
        }
    if not isinstance(obj, dict):
        return {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "entries": {},
            "notes": ["cooldown_invalid"],
        }
    if not isinstance(obj.get("entries"), dict):
        obj["entries"] = {}
    return obj


def _save_cooldowns(workspace_root: Path, cooldowns: dict[str, Any]) -> str:
    cooldowns["version"] = "v1"
    cooldowns["generated_at"] = _now_iso()
    cooldowns["workspace_root"] = str(workspace_root)
    path = _cooldown_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cooldowns, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    rel = _rel_to_workspace(path, workspace_root)
    return rel or str(path)


def _apply_job_status_cooldown(
    sources: list[dict[str, Any]],
    workspace_root: Path,
    notes: list[str],
    *,
    window_seconds: int = 86400,
) -> list[dict[str, Any]]:
    cooldowns = _load_cooldowns(workspace_root)
    entries = cooldowns.get("entries") if isinstance(cooldowns.get("entries"), dict) else {}
    now = datetime.now(timezone.utc)
    suppressed = 0
    filtered: list[dict[str, Any]] = []

    for source in sources:
        if source.get("source_type") != "JOB_STATUS":
            filtered.append(source)
            continue
        job_type = str(source.get("job_type") or "")
        failure_class = str(source.get("job_failure_class") or "")
        signature_hash = str(source.get("job_signature_hash") or "")
        if not job_type or not failure_class or not signature_hash:
            filtered.append(source)
            continue
        key = f"{job_type}|{failure_class}|{signature_hash}"
        entry = entries.get(key) if isinstance(entries.get(key), dict) else {}
        last_seen = _parse_iso(str(entry.get("last_seen") or ""))
        if last_seen and now - last_seen < timedelta(seconds=window_seconds):
            entry["suppressed_count"] = int(entry.get("suppressed_count", 0)) + 1
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last_seen"] = _now_iso()
            entry["job_type"] = job_type
            entry["failure_class"] = failure_class
            entry["signature_hash"] = signature_hash
            entries[key] = entry
            suppressed += 1
            continue
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = _now_iso()
        entry["job_type"] = job_type
        entry["failure_class"] = failure_class
        entry["signature_hash"] = signature_hash
        entries[key] = entry
        filtered.append(source)

    cooldowns["entries"] = entries
    cooldowns["notes"] = sorted({*(cooldowns.get("notes") or []), f"suppressed={suppressed}"})
    _save_cooldowns(workspace_root, cooldowns)
    if suppressed:
        notes.append(f"job_status_suppressed={suppressed}")
    return filtered


def _apply_github_ops_cooldown(
    sources: list[dict[str, Any]],
    workspace_root: Path,
    notes: list[str],
    *,
    window_seconds: int = 86400,
) -> list[dict[str, Any]]:
    cooldowns = _load_cooldowns(workspace_root)
    entries = cooldowns.get("entries") if isinstance(cooldowns.get("entries"), dict) else {}
    now = datetime.now(timezone.utc)
    suppressed = 0
    filtered: list[dict[str, Any]] = []

    for source in sources:
        if source.get("source_type") != "GITHUB_OPS":
            filtered.append(source)
            continue
        status = str(source.get("github_ops_job_status") or "")
        if status not in {"FAIL", "TIMEOUT", "KILLED"}:
            filtered.append(source)
            continue
        failure_class = str(source.get("github_ops_job_failure_class") or "")
        signature_hash = str(source.get("github_ops_signature_hash") or "")
        job_kind = str(source.get("github_ops_job_kind") or "")
        if not failure_class or not signature_hash or not job_kind:
            filtered.append(source)
            continue
        key = f"github_ops|{job_kind}|{failure_class}|{signature_hash}"
        entry = entries.get(key) if isinstance(entries.get(key), dict) else {}
        last_seen = _parse_iso(str(entry.get("last_seen") or ""))
        if last_seen and now - last_seen < timedelta(seconds=window_seconds):
            entry["suppressed_count"] = int(entry.get("suppressed_count", 0)) + 1
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last_seen"] = _now_iso()
            entry["job_kind"] = job_kind
            entry["failure_class"] = failure_class
            entry["signature_hash"] = signature_hash
            entries[key] = entry
            suppressed += 1
            continue
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = _now_iso()
        entry["job_kind"] = job_kind
        entry["failure_class"] = failure_class
        entry["signature_hash"] = signature_hash
        entries[key] = entry
        filtered.append(source)

    cooldowns["entries"] = entries
    cooldowns["notes"] = sorted({*(cooldowns.get("notes") or []), f"github_ops_suppressed={suppressed}"})
    _save_cooldowns(workspace_root, cooldowns)
    if suppressed:
        notes.append(f"github_ops_suppressed={suppressed}")
    return filtered
