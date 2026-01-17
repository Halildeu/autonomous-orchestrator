from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.system_status_sections_extensions_helpers_v2 import (
    _deep_merge,
    _job_time,
    _load_json,
    _parse_iso,
    _repo_root,
)

def _airunner_section(workspace_root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    lock_path = workspace_root / ".cache" / "airunner" / "airunner_lock.v1.json"
    heartbeat_path = workspace_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    jobs_index_path = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
    time_sinks_path = workspace_root / ".cache" / "reports" / "time_sinks.v1.json"

    notes: list[str] = []
    lock = {
        "status": "IDLE",
        "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
        "expires_at": "",
        "stale": False,
    }
    if lock_path.exists():
        try:
            obj = _load_json(lock_path)
        except Exception:
            notes.append("airunner_lock_invalid")
        else:
            expires_at = str(obj.get("expires_at") or "") if isinstance(obj, dict) else ""
            expires_dt = _parse_iso(expires_at)
            stale = bool(expires_dt and now >= expires_dt)
            lock = {
                "status": "OK" if not stale else "WARN",
                "lock_path": str(Path(".cache") / "airunner" / "airunner_lock.v1.json"),
                "expires_at": expires_at,
                "stale": stale,
            }
    else:
        notes.append("airunner_lock_missing")

    heartbeat = {
        "last_tick_id": "",
        "last_tick_at": "",
        "last_status": "",
        "age_seconds": 0,
        "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
    }
    if heartbeat_path.exists():
        try:
            hb = _load_json(heartbeat_path)
        except Exception:
            notes.append("airunner_heartbeat_invalid")
        else:
            last_tick_id = str(hb.get("last_tick_id") or "") if isinstance(hb, dict) else ""
            last_tick_at = str(hb.get("last_tick_at") or "") if isinstance(hb, dict) else ""
            last_status = str(hb.get("last_status") or "") if isinstance(hb, dict) else ""
            last_dt = _parse_iso(last_tick_at)
            age_seconds = int((now - last_dt).total_seconds()) if last_dt else 0
            heartbeat = {
                "last_tick_id": last_tick_id,
                "last_tick_at": last_tick_at,
                "last_status": last_status,
                "age_seconds": max(age_seconds, 0),
                "heartbeat_path": str(Path(".cache") / "airunner" / "airunner_heartbeat.v1.json"),
            }
    else:
        notes.append("airunner_heartbeat_missing")

    jobs_summary = {
        "total": 0,
        "by_status": {"QUEUED": 0, "RUNNING": 0, "PASS": 0, "FAIL": 0, "TIMEOUT": 0, "KILLED": 0, "SKIP": 0},
        "jobs_index_path": str(Path(".cache") / "airunner" / "jobs_index.v1.json"),
    }
    jobs_index_obj: dict[str, Any] | None = None
    if jobs_index_path.exists():
        try:
            idx = _load_json(jobs_index_path)
        except Exception:
            notes.append("airunner_jobs_index_invalid")
        else:
            jobs_index_obj = idx if isinstance(idx, dict) else None
            counts = idx.get("counts") if isinstance(idx, dict) else None
            if isinstance(counts, dict):
                jobs_summary = {
                    "total": int(counts.get("total", 0)),
                    "by_status": {
                        "QUEUED": int(counts.get("queued", 0)),
                        "RUNNING": int(counts.get("running", 0)),
                        "PASS": int(counts.get("pass", 0)),
                        "FAIL": int(counts.get("fail", 0)),
                        "TIMEOUT": int(counts.get("timeout", 0)),
                        "KILLED": int(counts.get("killed", 0)),
                        "SKIP": int(counts.get("skip", 0)),
                    },
                    "jobs_index_path": str(Path(".cache") / "airunner" / "jobs_index.v1.json"),
                }
    else:
        notes.append("airunner_jobs_index_missing")

    jobs_policy_summary = {
        "smoke_full": {
            "enabled": True,
            "timeout_seconds": 0,
            "poll_interval_seconds": 0,
            "max_concurrent": 1,
            "cooldown_seconds": 0,
        }
    }
    repo_root = Path(__file__).resolve().parents[2]
    policy_path_v2 = repo_root / "policies" / "policy_airunner_jobs.v2.json"
    policy_path_v1 = repo_root / "policies" / "policy_airunner_jobs.v1.json"
    override_path_v2 = workspace_root / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v2.json"
    override_path_v1 = workspace_root / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v1.json"

    policy_path = policy_path_v2 if policy_path_v2.exists() else policy_path_v1
    override_path = override_path_v2 if override_path_v2.exists() else override_path_v1
    policy_obj: dict[str, Any] = {}
    if policy_path.exists():
        try:
            policy_raw = _load_json(policy_path)
        except Exception:
            notes.append("airunner_jobs_policy_invalid")
        else:
            if isinstance(policy_raw, dict):
                policy_obj = _deep_merge(policy_obj, policy_raw)
                if policy_path == policy_path_v2:
                    notes.append("airunner_jobs_policy_v2_loaded")
    else:
        notes.append("airunner_jobs_policy_missing")
    if override_path.exists():
        try:
            override_raw = _load_json(override_path)
        except Exception:
            notes.append("airunner_jobs_policy_override_invalid")
        else:
            if isinstance(override_raw, dict):
                policy_obj = _deep_merge(policy_obj, override_raw)
                notes.append("airunner_jobs_policy_override_loaded")
    jobs_cfg = policy_obj.get("jobs") if isinstance(policy_obj.get("jobs"), dict) else {}
    smoke_cfg = jobs_cfg.get("smoke_full") if isinstance(jobs_cfg.get("smoke_full"), dict) else {}
    jobs_policy_summary = {
        "smoke_full": {
            "enabled": bool(smoke_cfg.get("enabled", True)),
            "timeout_seconds": int(smoke_cfg.get("timeout_seconds", jobs_cfg.get("timeout_seconds", 0) or 0) or 0),
            "poll_interval_seconds": int(
                smoke_cfg.get("poll_interval_seconds", jobs_cfg.get("poll_interval_seconds", 0) or 0) or 0
            ),
            "max_concurrent": int(smoke_cfg.get("max_concurrent", jobs_cfg.get("max_running", 1) or 1) or 1),
            "cooldown_seconds": int(smoke_cfg.get("cooldown_seconds", 0) or 0),
        }
    }

    last_smoke_full_job = {
        "job_id": "",
        "status": "",
        "failure_class": "",
        "signature_hash": "",
        "updated_at": "",
    }
    jobs_list = jobs_index_obj.get("jobs") if isinstance(jobs_index_obj, dict) else None
    if isinstance(jobs_list, list):
        candidates = []
        for job in jobs_list:
            if not isinstance(job, dict):
                continue
            if str(job.get("job_type") or job.get("kind") or "") != "SMOKE_FULL":
                continue
            updated_at = str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or "")
            updated_dt = _parse_iso(updated_at) or datetime.fromtimestamp(0, tz=timezone.utc)
            candidates.append((updated_dt, str(job.get("job_id") or ""), job))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            _, _, job = candidates[-1]
            last_smoke_full_job = {
                "job_id": str(job.get("job_id") or ""),
                "status": str(job.get("status") or ""),
                "failure_class": str(job.get("failure_class") or ""),
                "signature_hash": str(job.get("signature_hash") or ""),
                "updated_at": str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or ""),
            }

    cooldown_summary = {
        "entries": 0,
        "suppressed_count": 0,
        "cooldown_path": str(Path(".cache") / "index" / "intake_cooldowns.v1.json"),
    }
    cooldown_path = workspace_root / ".cache" / "index" / "intake_cooldowns.v1.json"
    if cooldown_path.exists():
        try:
            cooldown_obj = _load_json(cooldown_path)
        except Exception:
            notes.append("airunner_cooldown_invalid")
        else:
            entries = cooldown_obj.get("entries") if isinstance(cooldown_obj, dict) else None
            if isinstance(entries, dict):
                count = 0
                suppressed_total = 0
                for key, entry in entries.items():
                    if not isinstance(key, str) or not isinstance(entry, dict):
                        continue
                    job_type = str(entry.get("job_type") or "")
                    if job_type != "SMOKE_FULL" and not key.startswith("SMOKE_FULL|"):
                        continue
                    count += 1
                    suppressed_total += int(entry.get("suppressed_count", 0) or 0)
                cooldown_summary = {
                    "entries": count,
                    "suppressed_count": suppressed_total,
                    "cooldown_path": str(Path(".cache") / "index" / "intake_cooldowns.v1.json"),
                }
    else:
        notes.append("airunner_cooldown_missing")

    time_sinks_summary = {
        "count": 0,
        "top": [],
        "report_path": str(Path(".cache") / "reports" / "time_sinks.v1.json"),
    }
    time_sinks_recent = False
    if time_sinks_path.exists():
        try:
            ts = _load_json(time_sinks_path)
        except Exception:
            notes.append("airunner_time_sinks_invalid")
        else:
            sinks = ts.get("sinks") if isinstance(ts, dict) else None
            if isinstance(sinks, list):
                top = [
                    {
                        "event_key": str(s.get("event_key") or ""),
                        "op_name": str(s.get("op_name") or ""),
                        "count": int(s.get("count") or 0),
                        "p50_ms": int(s.get("p50_ms") or 0),
                        "p95_ms": int(s.get("p95_ms") or 0),
                        "threshold_ms": int(s.get("threshold_ms") or 0),
                        "breach_count": int(s.get("breach_count") or 0),
                        "last_seen": str(s.get("last_seen") or ""),
                    }
                    for s in sinks
                    if isinstance(s, dict) and str(s.get("event_key") or "")
                ]
                top.sort(key=lambda s: (-int(s.get("p95_ms", 0)), str(s.get("event_key"))))
                time_sinks_summary = {
                    "count": len(top),
                    "top": top[:3],
                    "report_path": str(Path(".cache") / "reports" / "time_sinks.v1.json"),
                }
                if time_sinks_summary.get("count", 0):
                    for sink in time_sinks_summary.get("top", []):
                        last_seen = _parse_iso(str(sink.get("last_seen") or ""))
                        if not last_seen:
                            time_sinks_recent = True
                            break
                        age_seconds = int((now - last_seen).total_seconds())
                        if age_seconds <= 86400:
                            time_sinks_recent = True
                            break
                    if not time_sinks_recent:
                        notes.append("airunner_time_sinks_stale")
    else:
        notes.append("airunner_time_sinks_missing")

    auto_mode = {
        "auto_mode_effective": False,
        "auto_select_enabled": False,
        "enabled": False,
        "last_selection_path": str(Path(".cache") / "index" / "work_intake_selection.v1.json"),
        "mode": "",
        "last_tick": {
            "tick_id": "",
            "selected_count": 0,
            "applied_count": 0,
            "planned_count": 0,
            "idle_count": 0,
        },
    }
    try:
        from src.ops.work_intake_from_sources import _load_autopilot_policy

        autopilot_policy, _, autopilot_notes = _load_autopilot_policy(
            core_root=repo_root, workspace_root=workspace_root
        )
        notes.extend(autopilot_notes)
        auto_select_cfg = (
            autopilot_policy.get("auto_select") if isinstance(autopilot_policy.get("auto_select"), dict) else {}
        )
        auto_select_enabled = bool(auto_select_cfg.get("enabled", False))
        auto_mode["auto_select_enabled"] = auto_select_enabled
    except Exception:
        notes.append("airunner_autopilot_policy_missing")

    try:
        from src.prj_airunner.auto_mode_dispatch import load_auto_mode_policy

        auto_policy, _, _, auto_notes = load_auto_mode_policy(workspace_root=workspace_root)
        notes.extend(auto_notes)
        auto_enabled = bool(auto_policy.get("enabled", False))
        auto_mode["enabled"] = auto_enabled
        auto_mode["mode"] = str(auto_policy.get("mode") or "")
        auto_mode["auto_mode_effective"] = bool(auto_select_enabled or auto_enabled)
    except Exception:
        notes.append("airunner_auto_mode_policy_missing")

    tick_path = workspace_root / ".cache" / "reports" / "airunner_tick.v1.json"
    if not tick_path.exists():
        tick_path = workspace_root / ".cache" / "reports" / "airunner_tick_1.v1.json"
    if tick_path.exists():
        try:
            tick_obj = _load_json(tick_path)
        except Exception:
            notes.append("airunner_tick_report_invalid")
        else:
            actions = tick_obj.get("actions") if isinstance(tick_obj, dict) else None
            if not isinstance(actions, dict):
                actions = {}
            auto_mode["last_tick"] = {
                "tick_id": str(tick_obj.get("tick_id") or ""),
                "selected_count": int(actions.get("selected") or 0),
                "applied_count": int(actions.get("applied") or 0),
                "planned_count": int(actions.get("planned") or 0),
                "idle_count": int(actions.get("idle") or 0),
            }
            dispatch_summary = tick_obj.get("dispatch_summary") if isinstance(tick_obj, dict) else None
            if isinstance(dispatch_summary, dict):
                auto_mode["last_dispatch_summary"] = dispatch_summary

    github_jobs_total = 0
    github_jobs_path = workspace_root / ".cache" / "github_ops" / "jobs_index.v1.json"
    if github_jobs_path.exists():
        try:
            github_obj = _load_json(github_jobs_path)
        except Exception:
            notes.append("github_jobs_index_invalid")
        else:
            jobs = github_obj.get("jobs") if isinstance(github_obj, dict) else None
            if isinstance(jobs, list):
                github_jobs_total = len([j for j in jobs if isinstance(j, dict)])
    auto_mode["last_jobs_summary"] = {
        "airunner_jobs_total": int(jobs_summary.get("total", 0) or 0),
        "github_jobs_total": int(github_jobs_total),
    }

    status = "IDLE"
    if heartbeat.get("last_tick_id") or jobs_summary.get("total") or time_sinks_summary.get("count"):
        status = "OK"
    if (
        lock.get("status") == "WARN"
        or jobs_summary.get("by_status", {}).get("FAIL", 0)
        or jobs_summary.get("by_status", {}).get("TIMEOUT", 0)
        or jobs_summary.get("by_status", {}).get("KILLED", 0)
        or time_sinks_recent
    ):
        status = "WARN"

    return {
        "status": status,
        "lock": lock,
        "heartbeat": heartbeat,
        "jobs": jobs_summary,
        "jobs_policy": jobs_policy_summary,
        "last_smoke_full_job": last_smoke_full_job,
        "cooldown_summary": cooldown_summary,
        "time_sinks": time_sinks_summary,
        "auto_mode": auto_mode,
        "notes": notes,
    }


def _airunner_proof_section(workspace_root: Path) -> dict[str, Any]:
    rel_path = str(Path(".cache") / "reports" / "airunner_proof_bundle.v1.json")
    proof_path = workspace_root / rel_path
    status = "IDLE"
    notes: list[str] = []
    timestamp = ""

    if proof_path.exists():
        try:
            _load_json(proof_path)
        except Exception:
            status = "WARN"
            notes.append("airunner_proof_invalid")
        else:
            status = "OK"
            try:
                ts = datetime.fromtimestamp(proof_path.stat().st_mtime, tz=timezone.utc)
                timestamp = ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            except Exception:
                notes.append("airunner_proof_timestamp_unavailable")
    else:
        notes.append("airunner_proof_missing")

    return {
        "status": status,
        "last_proof_bundle_path": rel_path,
        "last_proof_bundle_timestamp": timestamp,
        "notes": notes,
    }


def _airunner_auto_run_section(workspace_root: Path) -> dict[str, Any] | None:
    rel_path = Path(".cache") / "airunner" / "auto_run_jobs" / "index.v1.json"
    index_path = workspace_root / rel_path
    if not index_path.exists():
        return None
    try:
        obj = _load_json(index_path)
    except Exception:
        return {
            "last_job_id": "",
            "status": "WARN",
            "stop_at": "",
            "timezone": "",
            "last_poll_path": str(rel_path),
        }
    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(jobs, list) or not jobs:
        return None
    candidates = [j for j in jobs if isinstance(j, dict)]
    if not candidates:
        return None
    candidates.sort(key=lambda j: (_job_time(j), str(j.get("job_id") or "")))
    job = candidates[-1]
    section = {
        "last_job_id": str(job.get("job_id") or ""),
        "status": str(job.get("status") or ""),
        "stop_at": str(job.get("stop_at_local") or ""),
        "timezone": str(job.get("timezone") or ""),
    }
    if isinstance(job.get("last_poll_at"), str):
        section["last_poll_at"] = str(job.get("last_poll_at") or "")
    if isinstance(job.get("last_poll_path"), str):
        section["last_poll_path"] = str(job.get("last_poll_path") or "")
    if isinstance(job.get("last_closeout_path"), str):
        section["last_closeout_path"] = str(job.get("last_closeout_path") or "")
    return section


def _auto_loop_section(workspace_root: Path) -> dict[str, Any] | None:
    rel_path = str(Path(".cache") / "reports" / "auto_loop.v1.json")
    report_path = workspace_root / rel_path
    if not report_path.exists():
        return None
    try:
        obj = _load_json(report_path)
    except Exception:
        obj = {}
    counts = obj.get("counts") if isinstance(obj, dict) else {}
    if not isinstance(counts, dict):
        counts = {}
    doer_counts = counts.get("doer_counts") if isinstance(counts.get("doer_counts"), dict) else {}
    skipped_by_reason = doer_counts.get("skipped_by_reason") if isinstance(doer_counts.get("skipped_by_reason"), dict) else {}
    last_counts = {
        "decision_pending_before": int(counts.get("decision_pending_before") or 0),
        "decision_pending_after": int(counts.get("decision_pending_after") or 0),
        "bulk_applied_count": int(counts.get("bulk_applied_count") or 0),
        "selected_count": int(counts.get("selected_count") or 0),
        "doer_counts": {
            "applied": int(doer_counts.get("applied") or 0),
            "planned": int(doer_counts.get("planned") or 0),
            "skipped": int(doer_counts.get("skipped") or 0),
            "skipped_by_reason": {
                k: int(skipped_by_reason[k])
                for k in sorted(skipped_by_reason)
                if isinstance(skipped_by_reason.get(k), int)
            },
        },
    }
    apply_details_rel = str(Path(".cache") / "reports" / "auto_loop_apply_details.v1.json")
    apply_details_path = workspace_root / apply_details_rel
    apply_counts: dict[str, int] | None = None
    if apply_details_path.exists():
        try:
            apply_obj = _load_json(apply_details_path)
        except Exception:
            apply_obj = {}
        raw_counts = apply_obj.get("counts") if isinstance(apply_obj, dict) else {}
        if not isinstance(raw_counts, dict):
            raw_counts = {}
        applied_ids = raw_counts.get("applied_intake_ids")
        planned_ids = raw_counts.get("planned_intake_ids")
        limit_ids = raw_counts.get("limit_reached_intake_ids")
        if not isinstance(applied_ids, list):
            applied_ids = apply_obj.get("applied_intake_ids") if isinstance(apply_obj, dict) else []
        if not isinstance(planned_ids, list):
            planned_ids = apply_obj.get("planned_intake_ids") if isinstance(apply_obj, dict) else []
        if not isinstance(limit_ids, list):
            limit_ids = apply_obj.get("limit_reached_intake_ids") if isinstance(apply_obj, dict) else []
        if not isinstance(applied_ids, list):
            applied_ids = []
        if not isinstance(planned_ids, list):
            planned_ids = []
        if not isinstance(limit_ids, list):
            limit_ids = []
        applied_ids = sorted({str(x) for x in applied_ids if isinstance(x, str) and x.strip()})
        planned_ids = sorted({str(x) for x in planned_ids if isinstance(x, str) and x.strip()})
        limit_ids = sorted({str(x) for x in limit_ids if isinstance(x, str) and x.strip()})
        apply_counts = {
            "applied": int(raw_counts.get("applied") or len(applied_ids)),
            "planned": int(raw_counts.get("planned") or len(planned_ids)),
            "skipped": int(raw_counts.get("skipped") or 0),
            "limit_reached": int(raw_counts.get("limit_reached") or len(limit_ids)),
            "applied_intake_ids": applied_ids,
            "planned_intake_ids": planned_ids,
            "limit_reached_intake_ids": limit_ids,
        }
    section = {
        "last_auto_loop_path": rel_path,
        "last_auto_loop_counts": last_counts,
    }
    if apply_counts is not None:
        section["last_apply_details_path"] = apply_details_rel
        section["last_counts"] = apply_counts
    return section
