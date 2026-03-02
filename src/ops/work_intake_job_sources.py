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


def _job_failure_bucket(failure_class: str) -> str:
    if failure_class == "CORE_BREAK":
        return "INCIDENT"
    if failure_class.startswith("DEMO_") or failure_class.startswith("POLICY_"):
        return "TICKET"
    return "TICKET"


def _job_dedup_key(job_type: str, failure_class: str, signature_hash: str, fallback: str) -> str:
    bucket = _job_failure_bucket(failure_class)
    sig = signature_hash or fallback
    return f"{job_type}|{bucket}|{sig}"


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


def _github_ops_job_source_ref(
    *,
    job_id: str,
    job_kind: str,
    status: str,
    failure_class: str,
    skip_reason: str,
    signature_hash: str,
) -> str:
    if signature_hash:
        reason = failure_class or skip_reason or status
        return f"github_ops_sig:{job_kind}|{status}|{reason}|{signature_hash}"
    if job_id:
        return f"github_ops_job:{job_id}"
    return f"github_ops:{job_kind}:{status}"


def _deploy_job_source_ref(
    *,
    job_id: str,
    job_kind: str,
    status: str,
    failure_class: str,
    skip_reason: str,
    signature_hash: str,
) -> str:
    if signature_hash:
        reason = failure_class or skip_reason or status
        return f"deploy_job_sig:{job_kind}|{status}|{reason}|{signature_hash}"
    if job_id:
        return f"deploy_job:{job_id}"
    return f"deploy_job:{job_kind}:{status}"


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

    latest_by_key: dict[str, dict[str, Any]] = {}
    latest_key_meta: dict[str, tuple[datetime, str]] = {}
    latest_pass_meta_by_kind: dict[str, tuple[datetime, str]] = {}
    terminal_statuses = {"PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"}
    for job in [j for j in jobs if isinstance(j, dict)]:
        status = str(job.get("status") or "")
        if status not in terminal_statuses:
            continue
        job_id = str(job.get("job_id") or "")
        job_kind = str(job.get("kind") or "")
        if not job_id or not job_kind:
            continue
        signature_hash = str(job.get("signature_hash") or "")
        key = f"{job_kind}|{signature_hash}" if signature_hash else f"id:{job_id}"
        ts = _parse_iso(
            str(job.get("updated_at") or job.get("last_poll_at") or job.get("started_at") or job.get("created_at") or "")
        ) or datetime.fromtimestamp(0, tz=timezone.utc)
        meta = (ts, job_id)
        if status == "PASS":
            prev_pass_meta = latest_pass_meta_by_kind.get(job_kind)
            if prev_pass_meta is None or meta > prev_pass_meta:
                latest_pass_meta_by_kind[job_kind] = meta
        prev_meta = latest_key_meta.get(key)
        if prev_meta is None or meta > prev_meta:
            latest_key_meta[key] = meta
            latest_by_key[key] = job

    pruned_by_pass = 0
    for key in sorted(latest_by_key):
        job = latest_by_key[key]
        status = str(job.get("status") or "")
        job_id = str(job.get("job_id") or "")
        job_kind = str(job.get("kind") or "")
        failure_class = str(job.get("failure_class") or "")
        skip_reason = str(job.get("skip_reason") or "")
        signature_hash = str(job.get("signature_hash") or "")
        ts = _parse_iso(
            str(job.get("updated_at") or job.get("last_poll_at") or job.get("started_at") or job.get("created_at") or "")
        ) or datetime.fromtimestamp(0, tz=timezone.utc)
        job_meta = (ts, job_id)
        pass_meta = latest_pass_meta_by_kind.get(job_kind)
        if pass_meta and pass_meta > job_meta and status in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            pruned_by_pass += 1
            continue
        last_seen = str(
            job.get("updated_at") or job.get("last_poll_at") or job.get("started_at") or job.get("created_at") or ""
        )
        source_ref = _github_ops_job_source_ref(
            job_id=job_id,
            job_kind=job_kind,
            status=status,
            failure_class=failure_class,
            skip_reason=skip_reason,
            signature_hash=signature_hash,
        )
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
                "source_ref": source_ref,
                "title": f"GitHub ops job {status}: {job_kind}",
                "github_ops_job_status": status,
                "github_ops_job_kind": job_kind,
                "github_ops_job_skip_reason": skip_reason,
                "github_ops_job_failure_class": failure_class,
                "github_ops_signature_hash": signature_hash,
                "last_seen": last_seen,
                "last_status": status,
                "evidence_paths": evidence,
            }
        )

    if pruned_by_pass:
        notes.append(f"github_ops_pruned_by_pass={pruned_by_pass}")
    return sources


def _load_deploy_job_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    index_rel = str(Path(".cache") / "deploy" / "jobs_index.v1.json")
    index_path = workspace_root / index_rel
    if not index_path.exists():
        notes.append("deploy_jobs_index_missing")
        return []
    try:
        index_obj = _load_json(index_path)
    except Exception:
        notes.append("deploy_jobs_index_invalid")
        return []
    jobs = index_obj.get("jobs") if isinstance(index_obj, dict) else None
    if not isinstance(jobs, list):
        notes.append("deploy_jobs_index_empty")
        return []

    latest_by_key: dict[str, dict[str, Any]] = {}
    latest_key_meta: dict[str, tuple[datetime, str]] = {}
    terminal_statuses = {"PASS", "FAIL", "TIMEOUT", "KILLED", "SKIP"}
    for job in [j for j in jobs if isinstance(j, dict)]:
        status = str(job.get("status") or "")
        if status not in terminal_statuses:
            continue
        job_id = str(job.get("job_id") or "")
        job_kind = str(job.get("kind") or "")
        if not job_id or not job_kind:
            continue
        signature_hash = str(job.get("signature_hash") or "")
        key = f"{job_kind}|{signature_hash}" if signature_hash else f"id:{job_id}"
        ts = _parse_iso(
            str(job.get("updated_at") or job.get("last_poll_at") or job.get("started_at") or job.get("created_at") or "")
        ) or datetime.fromtimestamp(0, tz=timezone.utc)
        meta = (ts, job_id)
        prev_meta = latest_key_meta.get(key)
        if prev_meta is None or meta > prev_meta:
            latest_key_meta[key] = meta
            latest_by_key[key] = job

    sources: list[dict[str, Any]] = []
    evidence_base = [index_rel]
    for key in sorted(latest_by_key):
        job = latest_by_key[key]
        status = str(job.get("status") or "")
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            continue
        job_id = str(job.get("job_id") or "")
        job_kind = str(job.get("kind") or "")
        failure_class = str(job.get("failure_class") or "")
        skip_reason = str(job.get("skip_reason") or "")
        signature_hash = str(job.get("signature_hash") or "")
        last_seen = str(
            job.get("updated_at") or job.get("last_poll_at") or job.get("started_at") or job.get("created_at") or ""
        )
        source_ref = _deploy_job_source_ref(
            job_id=job_id,
            job_kind=job_kind,
            status=status,
            failure_class=failure_class,
            skip_reason=skip_reason,
            signature_hash=signature_hash,
        )
        evidence = list(evidence_base)
        for p in job.get("evidence_paths") if isinstance(job.get("evidence_paths"), list) else []:
            if isinstance(p, str):
                evidence.append(p)
        for p in job.get("result_paths") if isinstance(job.get("result_paths"), list) else []:
            if isinstance(p, str):
                evidence.append(p)
        source: dict[str, Any] = {
            "source_type": "DEPLOY_JOB",
            "source_ref": source_ref,
            "title": f"Deploy job {status}: {job_kind}",
            "deploy_job_status": status,
            "deploy_job_kind": job_kind,
            "deploy_job_skip_reason": skip_reason,
            "deploy_job_error_code": str(job.get("error_code") or ""),
            "deploy_job_failure_class": failure_class,
            "deploy_job_signature_hash": signature_hash,
            "last_seen": last_seen,
            "last_status": status,
            "evidence_paths": evidence,
        }
        if str(job.get("error_code") or "") == "POLICY_BLOCKED":
            source["override_bucket"] = "ROADMAP"
        sources.append(source)

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
        if job.get("archived") or status == "ARCHIVED":
            continue
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP", "PASS"}:
            continue
        skip_reason = str(job.get("skip_reason") or "")
        if status == "SKIP" and skip_reason == "STUCK_JOB":
            continue
        job_id = str(job.get("job_id") or "")
        job_type = str(job.get("job_type") or "")
        if not job_id or not job_type:
            continue
        failure_class = str(job.get("failure_class") or "")
        signature_hash = str(job.get("signature_hash") or "")
        dedup_key = _job_dedup_key(job_type, failure_class, signature_hash, job_id)
        updated_at = str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or "")
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
                "source_ref": dedup_key,
                "title": f"Job {status}: {job_type}",
                "job_status": status,
                "job_type": job_type,
                "job_skip_reason": str(job.get("skip_reason") or ""),
                "job_error_code": str(job.get("error_code") or ""),
                "job_failure_class": failure_class,
                "job_signature_hash": signature_hash,
                "job_last_seen": updated_at,
                "job_last_status": status,
                "job_severity_bucket": _job_failure_bucket(failure_class),
                "job_dedup_key": dedup_key,
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
    candidates: list[dict[str, Any]] = []
    for sink in [s for s in sinks if isinstance(s, dict)]:
        event_key = str(sink.get("op_name") or sink.get("event_key") or "")
        if not event_key:
            continue
        p95 = int(sink.get("p95_ms", 0) or 0)
        threshold = int(sink.get("threshold_ms", 0) or 0)
        breach_count = int(sink.get("breach_count", 0) or 0)
        p50 = int(sink.get("p50_ms", 0) or 0)
        count = int(sink.get("count", 0) or 0)
        last_seen = str(sink.get("last_seen") or "")
        if p95 <= 0:
            continue
        candidates.append(
            {
                "event_key": event_key,
                "p95_ms": p95,
                "threshold_ms": threshold,
                "breach_count": breach_count,
                "p50_ms": p50,
                "count": count,
                "last_seen": last_seen,
                "over_threshold": bool(threshold and p95 >= threshold),
            }
        )
    candidates.sort(key=lambda s: (-int(s.get("p95_ms", 0)), str(s.get("event_key"))))
    for rank, sink in enumerate(candidates[:3], start=1):
        event_key = str(sink.get("event_key") or "")
        sources.append(
            {
                "source_type": "TIME_SINK",
                "source_ref": event_key,
                "title": f"Time sink: {event_key}",
                "time_sink_count": int(sink.get("count", 0)),
                "time_sink_p50_ms": int(sink.get("p50_ms", 0)),
                "time_sink_p95_ms": int(sink.get("p95_ms", 0)),
                "time_sink_threshold_ms": int(sink.get("threshold_ms", 0)),
                "time_sink_breach_count": int(sink.get("breach_count", 0)),
                "time_sink_over_threshold": bool(sink.get("over_threshold", False)),
                "time_sink_rank": int(rank),
                "time_sink_last_seen": str(sink.get("last_seen") or ""),
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


def _update_index_notes(index_path: Path, note: str) -> None:
    if not note:
        return
    if not index_path.exists():
        return
    try:
        obj = _load_json(index_path)
    except Exception:
        return
    if not isinstance(obj, dict):
        return
    notes = obj.get("notes") if isinstance(obj.get("notes"), list) else []
    notes_set = {str(x) for x in notes if isinstance(x, str)}
    notes_set.add(note)
    obj["notes"] = sorted(notes_set)
    index_path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


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
    job_sources: dict[str, dict[str, Any]] = {}

    for source in sources:
        if source.get("source_type") != "JOB_STATUS":
            filtered.append(source)
            continue
        job_type = str(source.get("job_type") or "")
        failure_class = str(source.get("job_failure_class") or "")
        signature_hash = str(source.get("job_signature_hash") or "")
        dedup_key = str(source.get("job_dedup_key") or "")
        if not dedup_key:
            dedup_key = _job_dedup_key(job_type, failure_class, signature_hash, str(source.get("source_ref") or ""))
        last_seen_raw = str(source.get("job_last_seen") or "")
        last_seen = _parse_iso(last_seen_raw) or now
        entry = entries.get(dedup_key) if isinstance(entries.get(dedup_key), dict) else {}
        entry_last_seen = _parse_iso(str(entry.get("last_seen") or ""))
        within_window = bool(entry_last_seen and now - entry_last_seen < timedelta(seconds=window_seconds))
        was_suppressed = False

        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = last_seen.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        entry["last_status"] = str(source.get("job_status") or "")
        entry["job_type"] = job_type
        entry["severity_bucket"] = _job_failure_bucket(failure_class)
        entry["signature_hash"] = signature_hash
        if within_window:
            entry["suppressed_count"] = int(entry.get("suppressed_count", 0)) + 1
            suppressed += 1
            source["job_update_only"] = True
            was_suppressed = True
        entries[dedup_key] = entry

        existing = job_sources.get(dedup_key)
        if existing is None:
            job_sources[dedup_key] = source
        else:
            if not was_suppressed:
                suppressed += 1
            existing_seen = _parse_iso(str(existing.get("job_last_seen") or ""))
            if last_seen and (existing_seen is None or last_seen > existing_seen):
                job_sources[dedup_key] = source

    if job_sources:
        for key in sorted(job_sources):
            filtered.append(job_sources[key])

    cooldowns["entries"] = entries
    cooldowns["notes"] = sorted({*(cooldowns.get("notes") or []), f"suppressed={suppressed}"})
    _save_cooldowns(workspace_root, cooldowns)
    if suppressed:
        notes.append(f"job_status_suppressed={suppressed}")
        _update_index_notes(
            workspace_root / ".cache" / "airunner" / "jobs_index.v1.json",
            f"job_status_suppressed={suppressed}",
        )
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
    emitted: set[str] = set()
    emitted_index: dict[str, int] = {}

    for source in sources:
        if source.get("source_type") != "GITHUB_OPS":
            filtered.append(source)
            continue
        status = str(source.get("github_ops_job_status") or "")
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            filtered.append(source)
            continue
        failure_class = str(source.get("github_ops_job_failure_class") or "")
        signature_hash = str(source.get("github_ops_signature_hash") or "")
        job_kind = str(source.get("github_ops_job_kind") or "")
        skip_reason = str(source.get("github_ops_job_skip_reason") or "")
        if not signature_hash or not job_kind:
            filtered.append(source)
            continue
        reason = failure_class or skip_reason or status
        key = f"github_ops|{job_kind}|{reason}|{signature_hash}"
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
            if key in emitted:
                idx = emitted_index.get(key)
                if isinstance(idx, int) and 0 <= idx < len(filtered):
                    latest_seen = str(source.get("last_seen") or "")
                    if latest_seen:
                        filtered[idx]["last_seen"] = latest_seen
                        filtered[idx]["last_status"] = status
                continue
            source["github_ops_suppressed"] = True
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = _now_iso()
        entry["job_kind"] = job_kind
        entry["failure_class"] = failure_class
        entry["signature_hash"] = signature_hash
        entries[key] = entry
        emitted.add(key)
        emitted_index[key] = len(filtered)
        filtered.append(source)

    cooldowns["entries"] = entries
    cooldowns["notes"] = sorted({*(cooldowns.get("notes") or []), f"github_ops_suppressed={suppressed}"})
    _save_cooldowns(workspace_root, cooldowns)
    if suppressed:
        notes.append(f"github_ops_suppressed={suppressed}")
        _update_index_notes(
            workspace_root / ".cache" / "github_ops" / "jobs_index.v1.json",
            f"github_ops_suppressed={suppressed}",
        )
    return filtered


def _apply_deploy_job_cooldown(
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
    emitted: set[str] = set()
    emitted_index: dict[str, int] = {}

    for source in sources:
        if source.get("source_type") != "DEPLOY_JOB":
            filtered.append(source)
            continue
        status = str(source.get("deploy_job_status") or "")
        if status not in {"FAIL", "TIMEOUT", "KILLED", "SKIP"}:
            filtered.append(source)
            continue
        failure_class = str(source.get("deploy_job_failure_class") or "")
        signature_hash = str(source.get("deploy_job_signature_hash") or "")
        job_kind = str(source.get("deploy_job_kind") or "")
        skip_reason = str(source.get("deploy_job_skip_reason") or "")
        if not signature_hash or not job_kind:
            filtered.append(source)
            continue
        reason = failure_class or skip_reason or status
        key = f"deploy_job|{job_kind}|{reason}|{signature_hash}"
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
            if key in emitted:
                idx = emitted_index.get(key)
                if isinstance(idx, int) and 0 <= idx < len(filtered):
                    latest_seen = str(source.get("last_seen") or "")
                    if latest_seen:
                        filtered[idx]["last_seen"] = latest_seen
                        filtered[idx]["last_status"] = status
                continue
            source["deploy_job_suppressed"] = True
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = _now_iso()
        entry["job_kind"] = job_kind
        entry["failure_class"] = failure_class
        entry["signature_hash"] = signature_hash
        entries[key] = entry
        emitted.add(key)
        emitted_index[key] = len(filtered)
        filtered.append(source)

    cooldowns["entries"] = entries
    cooldowns["notes"] = sorted({*(cooldowns.get("notes") or []), f"deploy_job_suppressed={suppressed}"})
    _save_cooldowns(workspace_root, cooldowns)
    if suppressed:
        notes.append(f"deploy_job_suppressed={suppressed}")
        _update_index_notes(
            workspace_root / ".cache" / "deploy" / "jobs_index.v1.json",
            f"deploy_job_suppressed={suppressed}",
        )
    return filtered
