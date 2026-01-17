from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.ops.trace_meta import build_run_id, build_trace_meta, date_bucket_from_iso

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _jobs_index_summary(workspace_root: Path, notes: list[str]) -> dict[str, Any]:
    path = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
    if not path.exists():
        notes.append("jobs_index_missing")
        return {"counts_by_status": {}, "total": 0}
    try:
        obj = _load_json(path)
    except Exception:
        notes.append("jobs_index_invalid")
        return {"counts_by_status": {}, "total": 0}
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list):
        notes.append("jobs_index_empty")
        return {"counts_by_status": {}, "total": 0}
    counts: dict[str, int] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return {"counts_by_status": {k: counts[k] for k in sorted(counts)}, "total": sum(counts.values())}


def _work_intake_summary(workspace_root: Path, notes: list[str]) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not path.exists():
        notes.append("work_intake_missing")
        return {"counts_by_bucket": {}, "items_count": 0, "top5_intake_ids": []}
    try:
        obj = _load_json(path)
    except Exception:
        notes.append("work_intake_invalid")
        return {"counts_by_bucket": {}, "items_count": 0, "top5_intake_ids": []}
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        notes.append("work_intake_items_missing")
        return {"counts_by_bucket": {}, "items_count": 0, "top5_intake_ids": []}
    counts: dict[str, int] = {}
    intake_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        bucket = str(item.get("bucket") or "")
        if bucket:
            counts[bucket] = counts.get(bucket, 0) + 1
        intake_id = item.get("intake_id")
        if isinstance(intake_id, str) and intake_id:
            intake_ids.append(intake_id)
    intake_ids = sorted(set(intake_ids))
    return {
        "counts_by_bucket": {k: counts[k] for k in sorted(counts)},
        "items_count": len(items),
        "top5_intake_ids": intake_ids[:5],
    }


def _cooldowns_summary(workspace_root: Path, notes: list[str]) -> dict[str, Any]:
    path = workspace_root / ".cache" / "index" / "intake_cooldowns.v1.json"
    if not path.exists():
        notes.append("cooldowns_missing")
        return {"suppressed_count_total": 0}
    try:
        obj = _load_json(path)
    except Exception:
        notes.append("cooldowns_invalid")
        return {"suppressed_count_total": 0}
    entries = obj.get("entries") if isinstance(obj, dict) else None
    if not isinstance(entries, dict):
        notes.append("cooldowns_entries_missing")
        return {"suppressed_count_total": 0}
    suppressed_total = 0
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        suppressed_total += int(entry.get("suppressed_count", 0) or 0)
    return {"suppressed_count_total": suppressed_total}


def _work_intake_closed_count(workspace_root: Path) -> int:
    path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not path.exists():
        return 0
    try:
        obj = _load_json(path)
    except Exception:
        return 0
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return 0
    closed = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "")
        if state == "CLOSED":
            closed += 1
    return closed


def _allowed_ops_snapshot(workspace_root: Path) -> list[str]:
    path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner.override.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    single_gate = obj.get("single_gate") if isinstance(obj, dict) else None
    if not isinstance(single_gate, dict):
        return []
    allowed_ops = single_gate.get("allowed_ops")
    if not isinstance(allowed_ops, list):
        return []
    return sorted({str(x) for x in allowed_ops if isinstance(x, str)})


def _time_sinks_top3(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / ".cache" / "reports" / "time_sinks.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    sinks = obj.get("sinks") if isinstance(obj, dict) else None
    if not isinstance(sinks, list):
        return []
    top: list[dict[str, Any]] = []
    for sink in sinks:
        if not isinstance(sink, dict):
            continue
        event_key = str(sink.get("event_key") or "")
        if not event_key:
            continue
        top.append(
            {
                "event_key": event_key,
                "op_name": str(sink.get("op_name") or ""),
                "count": int(sink.get("count", 0) or 0),
                "p50_ms": int(sink.get("p50_ms", 0) or 0),
                "p95_ms": int(sink.get("p95_ms", 0) or 0),
                "threshold_ms": int(sink.get("threshold_ms", 0) or 0),
                "breach_count": int(sink.get("breach_count", 0) or 0),
                "last_seen": str(sink.get("last_seen") or ""),
            }
        )
    top.sort(key=lambda s: (-int(s.get("p95_ms", 0)), str(s.get("event_key"))))
    return top[:3]


def run_airunner_baseline(*, workspace_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    jobs_summary = _jobs_index_summary(workspace_root, notes)
    intake_summary = _work_intake_summary(workspace_root, notes)
    cooldowns_summary = _cooldowns_summary(workspace_root, notes)

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "jobs_index": jobs_summary,
        "work_intake": intake_summary,
        "cooldowns": cooldowns_summary,
        "notes": sorted(set(notes + ["PROGRAM_LED=true", "NETWORK=false"])),
    }
    rel_path = Path(".cache") / "reports" / "airunner_baseline.v1.json"
    _write_json(workspace_root / rel_path, report)
    return {
        "status": "OK" if not notes else "WARN",
        "report_path": str(rel_path),
    }


def _write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_tick_report(workspace_root: Path, index: int) -> dict[str, Any]:
    path = workspace_root / ".cache" / "reports" / f"airunner_tick_{index}.v1.json"
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception:
        return {}


def _copy_tick_report(workspace_root: Path, index: int) -> None:
    base_json = workspace_root / ".cache" / "reports" / "airunner_tick.v1.json"
    base_md = workspace_root / ".cache" / "reports" / "airunner_tick.v1.md"
    out_json = workspace_root / ".cache" / "reports" / f"airunner_tick_{index}.v1.json"
    out_md = workspace_root / ".cache" / "reports" / f"airunner_tick_{index}.v1.md"
    if base_json.exists():
        out_json.write_text(base_json.read_text(encoding="utf-8"), encoding="utf-8")
    if base_md.exists():
        out_md.write_text(base_md.read_text(encoding="utf-8"), encoding="utf-8")


def _tick_action_summary(report: dict[str, Any]) -> dict[str, Any]:
    actions = report.get("actions") if isinstance(report.get("actions"), dict) else {}
    applied = int(actions.get("applied", 0) or 0)
    planned = int(actions.get("planned", 0) or 0)
    idle = int(actions.get("idle", 0) or 0)
    skipped_count = int(report.get("skipped_count", 0) or 0)
    skipped_by_reason = report.get("skipped_by_reason") if isinstance(report.get("skipped_by_reason"), dict) else {}
    cleaned_skipped = {
        str(k): int(v)
        for k, v in skipped_by_reason.items()
        if isinstance(k, str) and isinstance(v, int) and v >= 0
    }
    return {
        "applied": applied,
        "planned": planned,
        "idle": idle,
        "skipped": skipped_count,
        "skipped_by_reason": cleaned_skipped,
    }


def _normalize_skipped_histogram(skipped_count: int, histogram: dict[str, Any] | None) -> dict[str, int]:
    cleaned = {
        str(k): int(v)
        for k, v in (histogram or {}).items()
        if isinstance(k, str) and isinstance(v, int) and v >= 0
    }
    total = sum(cleaned.values())
    if skipped_count > 0:
        if total == 0:
            return {"UNKNOWN": skipped_count}
        if total < skipped_count:
            cleaned["UNKNOWN"] = cleaned.get("UNKNOWN", 0) + (skipped_count - total)
        elif total > skipped_count:
            return {"UNKNOWN": skipped_count}
    return {k: cleaned[k] for k in sorted(cleaned)}


def _load_exec_skipped_histogram(workspace_root: Path) -> tuple[int, dict[str, int]]:
    path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    if not path.exists():
        return (0, {})
    try:
        obj = _load_json(path)
    except Exception:
        return (0, {})
    skipped_count = int(obj.get("skipped_count", 0) or 0) if isinstance(obj, dict) else 0
    raw_hist = obj.get("skipped_by_reason") if isinstance(obj, dict) else None
    return (skipped_count, _normalize_skipped_histogram(skipped_count, raw_hist if isinstance(raw_hist, dict) else {}))


def _has_actionable_items(report: dict[str, Any]) -> bool:
    summary = _tick_action_summary(report)
    jobs_started = int(report.get("jobs_started", 0) or 0)
    jobs_polled = int(report.get("jobs_polled", 0) or 0)
    return (
        summary["applied"] + summary["planned"] + summary["idle"] + jobs_started + jobs_polled
    ) > 0


def run_airunner_run(
    *,
    workspace_root: Path,
    ticks: int,
    mode: str,
    budget_seconds: int | None = None,
    force_active_hours: bool = False,
    tick_runner: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ticks = max(1, int(ticks or 1))
    mode = str(mode or "no_wait").strip().lower()
    budget_seconds = int(budget_seconds) if isinstance(budget_seconds, int) and budget_seconds > 0 else None
    start_ts = time.monotonic()

    if tick_runner is None:
        from src.prj_airunner.airunner_tick import run_airunner_tick

        def _runner(*, workspace_root: Path) -> dict[str, Any]:
            return run_airunner_tick(workspace_root=workspace_root, force_active_hours=force_active_hours)

        tick_runner = _runner

    baseline_res = run_airunner_baseline(workspace_root=workspace_root)
    baseline_path = workspace_root / (baseline_res.get("report_path") or "")
    baseline = _load_json(baseline_path) if baseline_path.exists() else {}

    tick_results: list[dict[str, Any]] = []
    actions_total = {"applied": 0, "planned": 0, "idle": 0, "skipped": 0, "skipped_by_reason": {}}
    stop_reason = ""
    doer_actionability_path = ""
    doer_actionability_md_path = ""
    autoselect_attempted = False
    fallback_executed = False
    idx = 0
    while True:
        idx += 1
        tick_results.append(tick_runner(workspace_root=workspace_root))
        _copy_tick_report(workspace_root, idx)
        tick_report = _load_tick_report(workspace_root, idx)
        summary = _tick_action_summary(tick_report)
        actions_total["applied"] += summary["applied"]
        actions_total["planned"] += summary["planned"]
        actions_total["idle"] += summary["idle"]
        actions_total["skipped"] += summary["skipped"]
        for reason, count in summary["skipped_by_reason"].items():
            actions_total["skipped_by_reason"][reason] = actions_total["skipped_by_reason"].get(reason, 0) + int(count)

        if mode != "no_wait":
            stop_reason = "MODE_NOT_NO_WAIT"
            break
        if budget_seconds is not None:
            if (time.monotonic() - start_ts) >= budget_seconds:
                stop_reason = "BUDGET_EXHAUSTED"
                break
            if not _has_actionable_items(tick_report):
                try:
                    from src.ops.doer_actionability import run_doer_actionability
                except Exception:
                    run_doer_actionability = None
                actionability_payload: dict[str, Any] = {}
                if run_doer_actionability is not None:
                    actionability_payload = run_doer_actionability(workspace_root=workspace_root, out="auto")
                    doer_actionability_path = str(actionability_payload.get("report_path") or "")
                    doer_actionability_md_path = str(actionability_payload.get("report_md_path") or "")
                counts = (
                    actionability_payload.get("counts") if isinstance(actionability_payload.get("counts"), dict) else {}
                )
                mode_info = (
                    actionability_payload.get("mode") if isinstance(actionability_payload.get("mode"), dict) else {}
                )
                selected_count = int(counts.get("selected", 0) or 0)
                candidate_total = int(counts.get("candidate_total", 0) or 0)
                auto_mode_mode = str(mode_info.get("auto_mode") or "")
                auto_mode_enabled = False
                max_actions_fallback = 1
                try:
                    from src.prj_airunner.auto_mode_dispatch import load_auto_mode_policy

                    auto_mode_policy, _, _, _ = load_auto_mode_policy(workspace_root=workspace_root)
                    auto_mode_enabled = bool(auto_mode_policy.get("enabled", False))
                    limits = auto_mode_policy.get("limits") if isinstance(auto_mode_policy.get("limits"), dict) else {}
                    if isinstance(limits.get("max_actions_per_tick"), int):
                        max_actions_fallback = max(1, int(limits.get("max_actions_per_tick") or 1))
                except Exception:
                    auto_mode_enabled = False
                if (
                    not autoselect_attempted
                    and auto_mode_enabled
                    and auto_mode_mode == "selected_only"
                    and selected_count == 0
                ):
                    try:
                        from src.ops.work_intake_autoselect import run_work_intake_autoselect
                    except Exception:
                        run_work_intake_autoselect = None
                    if run_work_intake_autoselect is not None:
                        run_work_intake_autoselect(workspace_root=workspace_root, limit=10, mode="safe_first")
                        autoselect_attempted = True
                        continue
                if candidate_total > 0 and not fallback_executed:
                    fast_gate = tick_report.get("fast_gate") if isinstance(tick_report.get("fast_gate"), dict) else {}
                    preflight_overall = str(fast_gate.get("preflight_overall") or "")
                    require_pass = bool(fast_gate.get("require_pass_for_apply", True))
                    allow_apply = preflight_overall == "PASS" or not require_pass
                    if allow_apply:
                        try:
                            from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket
                        except Exception:
                            run_work_intake_exec_ticket = None
                        if run_work_intake_exec_ticket is not None:
                            exec_payload = run_work_intake_exec_ticket(
                                workspace_root=workspace_root, limit=max_actions_fallback
                            )
                            if isinstance(exec_payload, dict):
                                actions_total["applied"] += int(exec_payload.get("applied_count", 0) or 0)
                                actions_total["planned"] += int(exec_payload.get("planned_count", 0) or 0)
                                actions_total["idle"] += int(exec_payload.get("idle_count", 0) or 0)
                                actions_total["skipped"] += int(exec_payload.get("skipped_count", 0) or 0)
                                raw_skipped = exec_payload.get("skipped_by_reason")
                                if isinstance(raw_skipped, dict):
                                    for reason, count in raw_skipped.items():
                                        if not isinstance(reason, str) or not isinstance(count, int):
                                            continue
                                        actions_total["skipped_by_reason"][reason] = actions_total["skipped_by_reason"].get(
                                            reason, 0
                                        ) + int(count)
                            fallback_executed = True
                            stop_reason = "DOER_FALLBACK_EXEC"
                            break
                stop_reason = "NO_ACTIONABLE_ITEMS"
                break
        else:
            if idx >= ticks:
                stop_reason = "TICKS_COMPLETE"
                break

    ticks_run = len(tick_results)
    tick1 = _load_tick_report(workspace_root, 1)
    tick2 = _load_tick_report(workspace_root, 2) if ticks_run >= 2 else {}

    after_jobs = _jobs_index_summary(workspace_root, [])
    after_intake = _work_intake_summary(workspace_root, [])
    after_cooldowns = _cooldowns_summary(workspace_root, [])

    base_jobs = baseline.get("jobs_index", {})
    base_intake = baseline.get("work_intake", {})
    base_cooldowns = baseline.get("cooldowns", {})

    jobs_polled_delta = int(tick1.get("jobs_polled", 0) or 0) + int(tick2.get("jobs_polled", 0) or 0)
    jobs_started_delta = int(tick1.get("jobs_started", 0) or 0) + int(tick2.get("jobs_started", 0) or 0)
    intake_new_items_delta = int(after_intake.get("items_count", 0) or 0) - int(base_intake.get("items_count", 0) or 0)
    suppressed_delta = int(after_cooldowns.get("suppressed_count_total", 0) or 0) - int(
        base_cooldowns.get("suppressed_count_total", 0) or 0
    )

    deltas = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "baseline_missing_for_deltas": False,
        "jobs_polled_delta": jobs_polled_delta,
        "jobs_started_delta": jobs_started_delta,
        "intake_new_items_delta": intake_new_items_delta,
        "suppressed_delta": suppressed_delta,
        "tick1": {"ops_called": tick1.get("ops_called", []), "status": tick1.get("status")},
        "tick2": {"ops_called": tick2.get("ops_called", []), "status": tick2.get("status")},
        "baseline": {
            "jobs_index": base_jobs,
            "work_intake": base_intake,
            "cooldowns": base_cooldowns,
        },
        "after": {
            "jobs_index": after_jobs,
            "work_intake": after_intake,
            "cooldowns": after_cooldowns,
        },
        "notes": ["PROGRAM_LED=true", "NETWORK=false"],
    }

    deltas_rel = Path(".cache") / "reports" / "airunner_deltas.v1.json"
    _write_json(workspace_root / deltas_rel, deltas)

    md_rel = Path(".cache") / "reports" / "airunner_deltas.v1.md"
    md_lines = [
        "# Airunner Deltas",
        f"- generated_at: {deltas['generated_at']}",
        f"- jobs_polled_delta: {jobs_polled_delta}",
        f"- jobs_started_delta: {jobs_started_delta}",
        f"- intake_new_items_delta: {intake_new_items_delta}",
        f"- suppressed_delta: {suppressed_delta}",
        f"- tick1 ops_called: {deltas['tick1']['ops_called']}",
        f"- tick2 ops_called: {deltas['tick2']['ops_called']}",
    ]
    _write_md(workspace_root / md_rel, md_lines)

    doer_processed_count = {
        "applied": int(actions_total.get("applied", 0)),
        "planned": int(actions_total.get("planned", 0)),
        "idle": int(actions_total.get("idle", 0)),
        "skipped": int(actions_total.get("skipped", 0)),
        "skipped_by_reason": {
            k: int(actions_total["skipped_by_reason"][k]) for k in sorted(actions_total["skipped_by_reason"])
        },
    }
    doer_counts = {
        "applied": int(actions_total.get("applied", 0)),
        "planned": int(actions_total.get("planned", 0)),
        "skipped": int(actions_total.get("skipped", 0)),
        "skipped_by_reason": {
            k: int(actions_total["skipped_by_reason"][k]) for k in sorted(actions_total["skipped_by_reason"])
        },
    }
    if doer_counts["skipped"] > 0 and not doer_counts["skipped_by_reason"]:
        exec_skipped_count, exec_skipped_hist = _load_exec_skipped_histogram(workspace_root)
        if exec_skipped_hist:
            doer_counts["skipped"] = exec_skipped_count if exec_skipped_count > 0 else doer_counts["skipped"]
            doer_counts["skipped_by_reason"] = exec_skipped_hist
        else:
            doer_counts["skipped_by_reason"] = _normalize_skipped_histogram(
                doer_counts["skipped"], doer_counts["skipped_by_reason"]
            )

    run_generated_at = _now_iso()
    policy_hash = None
    if isinstance(tick1.get("policy_hash"), str) and tick1.get("policy_hash"):
        policy_hash = str(tick1.get("policy_hash"))
    elif isinstance(tick2.get("policy_hash"), str) and tick2.get("policy_hash"):
        policy_hash = str(tick2.get("policy_hash"))
    run_id = build_run_id(
        workspace_root=workspace_root,
        op_name="airunner-run",
        inputs={
            "ticks": ticks,
            "mode": mode,
            "budget_seconds": budget_seconds,
            "force_active_hours": force_active_hours,
        },
        date_bucket=date_bucket_from_iso(run_generated_at),
    )

    run_rel = Path(".cache") / "reports" / "airunner_run.v1.json"
    run_md_rel = Path(".cache") / "reports" / "airunner_run.v1.md"
    run_evidence_paths = [
        str(run_rel),
        str(deltas_rel),
        str(baseline_res.get("report_path") or ""),
    ]
    for idx in range(1, ticks_run + 1):
        run_evidence_paths.append(str(Path(".cache") / "reports" / f"airunner_tick_{idx}.v1.json"))
    run_evidence_paths = sorted({p for p in run_evidence_paths if p})

    run_report = {
        "version": "v1",
        "generated_at": run_generated_at,
        "workspace_root": str(workspace_root),
        "policy_hash": policy_hash,
        "ticks_run": ticks_run,
        "jobs_started": jobs_started_delta,
        "jobs_polled": jobs_polled_delta,
        "intake_closed": _work_intake_closed_count(workspace_root),
        "suppressed_count": int(after_cooldowns.get("suppressed_count_total", 0) or 0),
        "time_sinks_top3": _time_sinks_top3(workspace_root),
        "elapsed_ms": int((time.monotonic() - start_ts) * 1000),
        "baseline_missing_for_deltas": bool(deltas.get("baseline_missing_for_deltas")),
        "stop_reason": stop_reason or None,
        "doer_processed_count": doer_processed_count,
        "doer_counts": doer_counts,
        "evidence_paths": run_evidence_paths,
        "notes": ["PROGRAM_LED=true", "NETWORK=false"],
    }
    if doer_actionability_path:
        run_report["doer_actionability_path"] = doer_actionability_path
    if doer_actionability_md_path:
        run_report["doer_actionability_md_path"] = doer_actionability_md_path
    run_report["trace_meta"] = build_trace_meta(
        work_item_id=run_id,
        work_item_kind="RUN",
        run_id=run_id,
        policy_hash=policy_hash,
        evidence_paths=run_evidence_paths,
        workspace_root=workspace_root,
    )
    _write_json(workspace_root / run_rel, run_report)
    run_md_lines = [
        "# Airunner Run",
        f"- generated_at: {run_report['generated_at']}",
        f"- ticks_run: {run_report['ticks_run']}",
        f"- jobs_started: {run_report['jobs_started']}",
        f"- jobs_polled: {run_report['jobs_polled']}",
        f"- intake_closed: {run_report['intake_closed']}",
        f"- suppressed_count: {run_report['suppressed_count']}",
        f"- elapsed_ms: {run_report['elapsed_ms']}",
    ]
    for sink in run_report["time_sinks_top3"]:
        run_md_lines.append(
            f"- {sink.get('event_key')} p95_ms={sink.get('p95_ms')} threshold_ms={sink.get('threshold_ms')} count={sink.get('count')} last_seen={sink.get('last_seen')}"
        )
    _write_md(workspace_root / run_md_rel, run_md_lines)

    tick1_ops = tick1.get("ops_called", [])
    tick2_ops = tick2.get("ops_called", [])
    tick1_queued_before = int(tick1.get("queued_before", 0) or 0)
    tick1_running_before = int(tick1.get("running_before", 0) or 0)
    tick1_queued_after = int(tick1.get("queued_after", tick1_queued_before) or 0)
    tick1_running_after = int(tick1.get("running_after", tick1_running_before) or 0)
    tick2_queued_before = int(tick2.get("queued_before", 0) or 0)
    tick2_running_before = int(tick2.get("running_before", 0) or 0)
    tick2_queued_after = int(tick2.get("queued_after", tick2_queued_before) or 0)
    tick2_running_after = int(tick2.get("running_after", tick2_running_before) or 0)
    poll_only_observed = bool(tick1_ops) and (
        tick1_ops == ["airunner-jobs-poll"] or "github-ops-job-poll" in tick1_ops
    )
    start_only_observed = "github-ops-job-start" in tick2_ops
    reason = ""
    if not start_only_observed:
        if tick2_queued_before + tick2_running_before > 0:
            reason = "ACTIVE_JOBS_REMAIN"
        elif "github-ops-job-start" not in _allowed_ops_snapshot(workspace_root):
            reason = "OP_NOT_ALLOWED"
        else:
            reason = "NO_SUGGESTION"

    proof = {
        "version": "v2",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "poll_only_observed": poll_only_observed,
        "start_only_observed": start_only_observed,
        "reason": reason,
        "tick1": {
            "queued_before": tick1_queued_before,
            "running_before": tick1_running_before,
            "queued_after": tick1_queued_after,
            "running_after": tick1_running_after,
            "ops_called": tick1_ops,
            "status": tick1.get("status"),
        },
        "tick2": {
            "queued_before": tick2_queued_before,
            "running_before": tick2_running_before,
            "queued_after": tick2_queued_after,
            "running_after": tick2_running_after,
            "ops_called": tick2_ops,
            "status": tick2.get("status"),
        },
        "deltas": {
            "jobs_polled_delta": jobs_polled_delta,
            "jobs_started_delta": jobs_started_delta,
            "intake_new_items_delta": intake_new_items_delta,
            "suppressed_delta": suppressed_delta,
        },
        "allowed_ops_snapshot": _allowed_ops_snapshot(workspace_root),
        "notes": ["PROGRAM_LED=true", "NETWORK=false"],
    }
    proof_rel = Path(".cache") / "reports" / "github_ops_no_wait_proof.v2.json"
    _write_json(workspace_root / proof_rel, proof)

    return {
        "status": "OK",
        "baseline_path": str(baseline_res.get("report_path") or ""),
        "tick_reports": [str(Path(".cache") / "reports" / f"airunner_tick_{i}.v1.json") for i in range(1, ticks_run + 1)],
        "deltas_path": str(deltas_rel),
        "deltas_md_path": str(md_rel),
        "run_path": str(run_rel),
        "run_md_path": str(run_md_rel),
        "doer_processed_count": doer_processed_count,
        "doer_counts": doer_counts,
        "stop_reason": stop_reason or None,
        "doer_actionability_path": doer_actionability_path or None,
    }
