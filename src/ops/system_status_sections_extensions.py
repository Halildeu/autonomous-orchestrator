from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _normalize_core_path(core_root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (core_root / path).resolve()
    else:
        path = path.resolve()
    return path if _is_within_root(path, core_root) else None


def _find_auto_heal_report(core_root: Path, workspace_root: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates: list[Path] = []
    hint_path = workspace_root / ".cache" / "last_finish_evidence.v1.txt"
    if hint_path.exists():
        try:
            for line in hint_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                resolved = _normalize_core_path(core_root, line)
                if resolved is not None:
                    candidates.append(resolved)
                break
        except Exception:
            pass

    evidence_root = core_root / "evidence" / "roadmap_finish"
    if evidence_root.exists():
        dirs = [d for d in evidence_root.iterdir() if d.is_dir()]
        dirs.sort(key=lambda p: p.name, reverse=True)
        candidates.extend(dirs[:50])

    seen: set[Path] = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        report_path = base / "artifact_completeness_report.json"
        if not report_path.exists():
            continue
        try:
            obj = _load_json(report_path)
        except Exception:
            continue
        if isinstance(obj, dict):
            return (obj, report_path)
    return (None, None)


def _extensions_section(workspace_root: Path) -> dict[str, Any]:
    rel_path = str(Path(".cache") / "index" / "extension_registry.v1.json")
    path = workspace_root / rel_path
    notes: list[str] = []
    help_rel = str(Path(".cache") / "reports" / "extension_help.v1.json")
    help_path = workspace_root / help_rel
    isolation_summary = {
        "status": "IDLE",
        "workspace_root_base": ".cache/extensions",
        "workspace_roots": [],
        "network_allowed": False,
        "last_run_path": "",
        "notes": ["extension_isolation_policy_missing"],
    }

    if not path.exists():
        return {
            "registry_status": "IDLE",
            "count_total": 0,
            "enabled_count": 0,
            "top_extensions": [],
            "last_registry_path": rel_path,
            "docs_coverage": {"total": 0, "with_docs_ref": 0, "with_ai_context_refs": 0},
            "tests_coverage": {"total": 0, "with_tests_entrypoints": 0, "with_tests_files": 0},
            "isolation_summary": isolation_summary,
            "last_extension_help_path": "",
            "notes": ["registry_missing"],
        }

    try:
        obj = _load_json(path)
    except Exception:
        return {
            "registry_status": "WARN",
            "count_total": 0,
            "enabled_count": 0,
            "top_extensions": [],
            "last_registry_path": rel_path,
            "docs_coverage": {"total": 0, "with_docs_ref": 0, "with_ai_context_refs": 0},
            "tests_coverage": {"total": 0, "with_tests_entrypoints": 0, "with_tests_files": 0},
            "isolation_summary": isolation_summary,
            "last_extension_help_path": "",
            "notes": ["invalid_registry_json"],
        }

    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"OK", "WARN", "IDLE", "FAIL"}:
        status = "WARN"

    extensions = obj.get("extensions") if isinstance(obj, dict) else None
    entries = [e for e in extensions if isinstance(e, dict)] if isinstance(extensions, list) else []
    ext_ids = [str(e.get("extension_id")) for e in entries if isinstance(e.get("extension_id"), str)]
    ext_ids = sorted(set(ext_ids))

    counts = obj.get("counts") if isinstance(obj, dict) else None
    total = int(counts.get("total", len(ext_ids))) if isinstance(counts, dict) else len(ext_ids)
    enabled_count = int(counts.get("enabled", 0)) if isinstance(counts, dict) else 0
    if enabled_count == 0 and entries:
        enabled_count = len([e for e in entries if e.get("enabled") is True])

    obj_notes = obj.get("notes") if isinstance(obj, dict) else None
    if isinstance(obj_notes, list):
        notes = [str(n) for n in obj_notes if isinstance(n, str)]

    docs_coverage = {"total": total, "with_docs_ref": 0, "with_ai_context_refs": 0}
    tests_coverage = {"total": total, "with_tests_entrypoints": 0, "with_tests_files": 0}
    last_help_path = ""
    if help_path.exists():
        try:
            help_obj = _load_json(help_path)
        except Exception:
            notes.append("extension_help_invalid")
        else:
            coverage = help_obj.get("docs_coverage") if isinstance(help_obj, dict) else None
            if isinstance(coverage, dict):
                docs_coverage = {
                    "total": int(coverage.get("total", total)),
                    "with_docs_ref": int(coverage.get("with_docs_ref", 0)),
                    "with_ai_context_refs": int(coverage.get("with_ai_context_refs", 0)),
                }
                help_tests = help_obj.get("tests_coverage") if isinstance(help_obj, dict) else None
                if isinstance(help_tests, dict):
                    tests_coverage = {
                        "total": int(help_tests.get("total", total)),
                        "with_tests_entrypoints": int(help_tests.get("with_tests_entrypoints", 0)),
                        "with_tests_files": int(help_tests.get("with_tests_files", 0)),
                    }
                last_help_path = help_rel
            else:
                notes.append("extension_help_missing_coverage")
    else:
        repo_root = Path(__file__).resolve().parents[2]
        with_docs = 0
        with_ai = 0
        with_tests_entrypoints = 0
        with_tests_files = 0
        for entry in entries:
            manifest_path = entry.get("manifest_path")
            if not isinstance(manifest_path, str) or not manifest_path:
                continue
            path_obj = repo_root / manifest_path
            if not path_obj.exists():
                continue
            try:
                manifest = _load_json(path_obj)
            except Exception:
                continue
            if isinstance(manifest.get("docs_ref"), str) and manifest.get("docs_ref"):
                with_docs += 1
            ai_refs = manifest.get("ai_context_refs")
            if isinstance(ai_refs, list) and any(isinstance(x, str) and x for x in ai_refs):
                with_ai += 1
            tests_entrypoints = manifest.get("tests_entrypoints")
            if not isinstance(tests_entrypoints, list) or not tests_entrypoints:
                entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
                tests_entrypoints = entrypoints.get("tests")
            tests_list = [t for t in tests_entrypoints if isinstance(t, str)] if isinstance(tests_entrypoints, list) else []
            if tests_list:
                with_tests_entrypoints += 1
                ext_root = path_obj.parent
                tests_ok = True
                for tpath in tests_list:
                    abs_path = repo_root / tpath
                    if not abs_path.exists():
                        tests_ok = False
                        break
                    rel_prefix = str(ext_root.relative_to(repo_root)).replace("\\\\", "/") + "/tests/"
                    if not str(tpath).startswith(rel_prefix):
                        tests_ok = False
                        break
                if tests_ok:
                    with_tests_files += 1
        docs_coverage = {"total": total, "with_docs_ref": with_docs, "with_ai_context_refs": with_ai}
        tests_coverage = {
            "total": total,
            "with_tests_entrypoints": with_tests_entrypoints,
            "with_tests_files": with_tests_files,
        }
        notes.append("extension_help_missing")

    policy_path = Path(__file__).resolve().parents[2] / "policies" / "policy_extension_isolation.v1.json"
    if policy_path.exists():
        try:
            policy_obj = _load_json(policy_path)
        except Exception:
            isolation_summary = {
                "status": "WARN",
                "workspace_root_base": ".cache/extensions",
                "workspace_roots": [],
                "network_allowed": False,
                "last_run_path": "",
                "notes": ["extension_isolation_policy_invalid"],
            }
        else:
            base = policy_obj.get("extension_workspace_root") if isinstance(policy_obj, dict) else ".cache/extensions"
            base = str(base) if isinstance(base, str) and base else ".cache/extensions"
            network_allowed = bool(policy_obj.get("network_allowed", False)) if isinstance(policy_obj, dict) else False
            workspace_roots = [str(Path(base) / ext_id) for ext_id in ext_ids]
            last_run_path = ""
            for ext_id in ext_ids:
                run_path = Path(".cache") / "reports" / f"extension_run.{ext_id}.v1.json"
                if (workspace_root / run_path).exists():
                    last_run_path = str(run_path)
                    break
            isolation_notes = []
            status = "OK"
            if network_allowed:
                status = "WARN"
                isolation_notes.append("network_allowed_true")
            isolation_summary = {
                "status": status,
                "workspace_root_base": base,
                "workspace_roots": workspace_roots,
                "network_allowed": False,
                "last_run_path": last_run_path,
                "notes": isolation_notes,
            }

    return {
        "registry_status": str(status),
        "count_total": total,
        "enabled_count": enabled_count,
        "top_extensions": ext_ids[:5],
        "last_registry_path": rel_path,
        "docs_coverage": docs_coverage,
        "tests_coverage": tests_coverage,
        "isolation_summary": isolation_summary,
        "last_extension_help_path": last_help_path,
        "notes": notes,
    }


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
    policy_path = repo_root / "policies" / "policy_airunner_jobs.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_airunner_jobs.override.v1.json"
    policy_obj: dict[str, Any] = {}
    if policy_path.exists():
        try:
            policy_raw = _load_json(policy_path)
        except Exception:
            notes.append("airunner_jobs_policy_invalid")
        else:
            if isinstance(policy_raw, dict):
                policy_obj = _deep_merge(policy_obj, policy_raw)
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
                        "p95_ms": int(s.get("p95_ms") or 0),
                        "threshold_ms": int(s.get("threshold_ms") or 0),
                        "breach_count": int(s.get("breach_count") or 0),
                    }
                    for s in sinks
                    if isinstance(s, dict) and str(s.get("event_key") or "")
                ]
                top.sort(key=lambda s: (-int(s.get("breach_count", 0)), str(s.get("event_key"))))
                time_sinks_summary = {
                    "count": len(top),
                    "top": top[:5],
                    "report_path": str(Path(".cache") / "reports" / "time_sinks.v1.json"),
                }
    else:
        notes.append("airunner_time_sinks_missing")

    status = "IDLE"
    if heartbeat.get("last_tick_id") or jobs_summary.get("total") or time_sinks_summary.get("count"):
        status = "OK"
    if lock.get("status") == "WARN" or jobs_summary.get("by_status", {}).get("FAIL", 0) or jobs_summary.get("by_status", {}).get("TIMEOUT", 0) or jobs_summary.get("by_status", {}).get("KILLED", 0) or time_sinks_summary.get("count", 0):
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
        "notes": notes,
    }


def _release_section(workspace_root: Path) -> dict[str, Any]:
    plan_rel = str(Path(".cache") / "reports" / "release_plan.v1.json")
    manifest_rel = str(Path(".cache") / "reports" / "release_manifest.v1.json")
    notes_rel = str(Path(".cache") / "reports" / "release_notes.v1.md")
    plan_path = workspace_root / plan_rel
    manifest_path = workspace_root / manifest_rel
    notes_path = workspace_root / notes_rel

    status = "IDLE"
    next_channel = "rc"
    publish_allowed = False
    notes: list[str] = []
    dirty_tree = False
    channel = "rc"
    proposed_version = ""
    evidence_paths: list[str] = []
    publish_status = "SKIP"
    publish_reason = "NETWORK_PUBLISH_DISABLED"

    if plan_path.exists():
        try:
            plan = _load_json(plan_path)
        except Exception:
            status = "WARN"
            notes.append("plan_invalid_json")
            plan = {}
        if isinstance(plan, dict):
            plan_status = plan.get("status")
            if plan_status in {"OK", "WARN", "IDLE", "FAIL"}:
                status = str(plan_status)
            channel = str(plan.get("channel") or channel)
            if channel == "rc":
                next_channel = "final"
            elif channel == "final":
                next_channel = "rc"
            else:
                channel = "rc"
                next_channel = "rc"
            dirty_tree = bool(plan.get("dirty_tree", False))
            version_plan = plan.get("version_plan") if isinstance(plan.get("version_plan"), dict) else {}
            proposed_version = str(version_plan.get("channel_version", ""))
        evidence_paths.append(plan_rel)
    else:
        notes.append("plan_missing")

    if manifest_path.exists():
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            notes.append("manifest_invalid_json")
            manifest = {}
        if isinstance(manifest, dict):
            manifest_status = manifest.get("status")
            if manifest_status in {"OK", "WARN", "IDLE", "FAIL"}:
                status = str(manifest_status) if status != "FAIL" else status
            publish_allowed = bool(manifest.get("publish_allowed", False))
            dirty_tree = bool(manifest.get("dirty_tree", dirty_tree))
            channel = str(manifest.get("channel", channel) or channel)
            proposed_version = str(manifest.get("release_version", proposed_version) or proposed_version)
        evidence_paths.append(manifest_rel)
    else:
        notes.append("manifest_missing")

    if notes_path.exists():
        evidence_paths.append(notes_rel)

    try:
        from src.prj_release_automation.release_engine import publish_release

        publish = publish_release(workspace_root=workspace_root, channel=channel, allow_network=False, trusted_context=False)
        if isinstance(publish, dict):
            publish_status = str(publish.get("status", publish_status))
            publish_reason = str(publish.get("error_code") or publish_reason)
    except Exception:
        publish_status = "WARN"
        publish_reason = "PUBLISH_STATUS_UNAVAILABLE"

    return {
        "status": status,
        "last_plan_path": plan_rel,
        "last_manifest_path": manifest_rel,
        "next_channel_suggestion": next_channel,
        "channel": channel,
        "proposed_version": proposed_version,
        "dirty_tree": dirty_tree,
        "evidence_paths": sorted(set(evidence_paths)),
        "publish": {
            "status": publish_status,
            "reason": publish_reason,
        },
        "publish_allowed": publish_allowed,
        "notes": notes,
    }


def _pm_suite_section() -> dict[str, Any]:
    extension_id = "PRJ-PM-SUITE"
    manifest_path = Path("extensions") / "PRJ-PM-SUITE" / "extension.manifest.v1.json"
    schema_paths = [
        Path("schemas") / "pm-project.schema.v1.json",
        Path("schemas") / "pm-work-item.schema.v1.json",
        Path("schemas") / "pm-workflow.schema.v1.json",
        Path("schemas") / "pm-board.schema.v1.json",
    ]
    policy_paths = [
        Path("policies") / "policy_pm_suite.v1.json",
        Path("schemas") / "policy-pm-suite.schema.v1.json",
    ]
    repo_root = Path(__file__).resolve().parents[2]
    notes: list[str] = []

    missing = []
    if not (repo_root / manifest_path).exists():
        missing.append("manifest_missing")
    for sp in schema_paths:
        if not (repo_root / sp).exists():
            missing.append(f"schema_missing:{sp}")
    for pp in policy_paths:
        if not (repo_root / pp).exists():
            missing.append(f"policy_missing:{pp}")

    if len(missing) == len(schema_paths) + len(policy_paths) + 1:
        status = "IDLE"
    elif missing:
        status = "WARN"
    else:
        status = "OK"

    notes.extend(missing)
    return {
        "status": status,
        "extension_id": extension_id,
        "manifest_path": str(manifest_path),
        "schema_paths": [str(p) for p in schema_paths],
        "policy_paths": [str(p) for p in policy_paths],
        "notes": notes,
    }


def _auto_heal_section(core_root: Path, workspace_root: Path) -> dict[str, Any] | None:
    report, report_path = _find_auto_heal_report(core_root, workspace_root)
    if report is None or report_path is None:
        return None

    missing = report.get("missing") if isinstance(report, dict) else None
    still_missing = report.get("still_missing") if isinstance(report, dict) else None
    healed = report.get("healed") if isinstance(report, dict) else None
    attempted = report.get("attempted_milestones") if isinstance(report, dict) else None

    missing_list = missing if isinstance(missing, list) else []
    still_list = still_missing if isinstance(still_missing, list) else []
    healed_list = healed if isinstance(healed, list) else []
    attempted_list = [str(x) for x in attempted] if isinstance(attempted, list) else []

    healed_ids = {str(x) for x in healed_list if isinstance(x, str)}
    top_healed: list[dict[str, str]] = []
    for item in missing_list:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if not item_id or item_id not in healed_ids:
            continue
        top_healed.append(
            {
                "id": item_id,
                "path": str(item.get("path") or ""),
                "owner_milestone": str(item.get("owner_milestone") or ""),
            }
        )
    top_healed.sort(key=lambda x: x.get("id") or "")
    top_healed = top_healed[:3]

    try:
        rel_path = str(report_path.relative_to(core_root))
    except Exception:
        rel_path = str(report_path)

    missing_count = len(missing_list)
    healed_count = len([x for x in healed_list if isinstance(x, str)])
    still_missing_count = len(still_list)
    status = "WARN" if still_missing_count > 0 else "OK"

    return {
        "status": status,
        "last_report_path": rel_path,
        "missing_count": missing_count,
        "healed_count": healed_count,
        "still_missing_count": still_missing_count,
        "attempted_milestones": attempted_list,
        "top_healed": top_healed,
        "notes": [],
    }
