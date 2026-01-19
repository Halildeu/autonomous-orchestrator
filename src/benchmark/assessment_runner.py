from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.benchmark.assessment_signals import (
    _load_control_statuses,
    _load_integration_coherence_signals,
    _load_pdca_cursor_signal,
)
from src.benchmark.eval_runner import run_eval
from src.benchmark.gap_engine import build_gap_register, build_gap_summary_md
from src.benchmark.integrity_utils import build_integrity_snapshot, load_policy_integrity


from src.benchmark.assessment_runner_support import (
    DOCS_DRIFT_DEFAULT_MAPPING,
    DOCS_DRIFT_DEFAULT_VIEW_ALLOWLIST,
    DOCS_DRIFT_EXCLUDE_DIRS,
    DOCS_DRIFT_LEGACY_MARKERS,
    _collect_extension_manifest_paths,
    _collect_extension_manifest_refs,
    _collect_view_allowlist,
    _ensure_inside_workspace,
    _extract_md_links,
    _fail,
    _hash_bytes,
    _is_legacy_excluded,
    _iter_md_paths,
    _load_doc_nav_signal,
    _load_docs_drift_mapping,
    _load_docs_drift_signal,
    _load_docs_hygiene_signal,
    _load_json,
    _load_operability_policy,
    _load_policy,
    _load_script_budget_signal,
    _maybe_auto_pdca_recheck,
    _now_iso,
    _parse_iso,
    _repo_root,
    _resolve_manifest_ref,
    _resolve_output_path,
    _seconds_since,
    compute_docs_drift_signal,
)


def _load_jobs_signal(*, workspace_root: Path) -> dict[str, Any]:
    jobs_path = workspace_root / ".cache" / "airunner" / "jobs_index.v1.json"
    if not jobs_path.exists():
        return {
            "queued": 0,
            "running": 0,
            "fail": 0,
            "pass": 0,
            "stuck": 0,
            "last_job_age_seconds": 0,
            "jobs_index_path": "",
        }
    try:
        obj = _load_json(jobs_path)
    except Exception:
        return {
            "queued": 0,
            "running": 0,
            "fail": 0,
            "pass": 0,
            "stuck": 0,
            "last_job_age_seconds": 0,
            "jobs_index_path": str(jobs_path),
        }

    counts = obj.get("counts") if isinstance(obj, dict) else None
    queued = int(counts.get("queued", 0) or 0) if isinstance(counts, dict) else 0
    running = int(counts.get("running", 0) or 0) if isinstance(counts, dict) else 0
    fail = int(counts.get("fail", 0) or 0) if isinstance(counts, dict) else 0
    passed = int(counts.get("pass", 0) or 0) if isinstance(counts, dict) else 0

    jobs = obj.get("jobs") if isinstance(obj, dict) else None
    jobs_list = jobs if isinstance(jobs, list) else []
    stuck = 0
    max_age = 0
    for job in jobs_list:
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or "")
        if status in {"QUEUED", "RUNNING"}:
            polls_without = int(job.get("polls_without_progress", 0) or 0)
            stale_reason = job.get("stale_reason")
            if polls_without > 0 or stale_reason:
                stuck += 1
        started_at = str(job.get("started_at") or job.get("last_poll_at") or "")
        age = _seconds_since(started_at)
        if age > max_age:
            max_age = age

    return {
        "queued": queued,
        "running": running,
        "fail": fail,
        "pass": passed,
        "stuck": int(stuck),
        "last_job_age_seconds": int(max_age),
        "jobs_index_path": str(jobs_path),
    }


def _load_heartbeat_signal(*, workspace_root: Path) -> dict[str, Any]:
    hb_path = workspace_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json"
    if not hb_path.exists():
        return {"stale_seconds": 0, "lock_state": "UNKNOWN", "heartbeat_path": ""}
    try:
        obj = _load_json(hb_path)
    except Exception:
        return {"stale_seconds": 0, "lock_state": "UNKNOWN", "heartbeat_path": str(hb_path)}
    last_tick_at = obj.get("last_tick_at") if isinstance(obj, dict) else None
    ended_at = obj.get("ended_at") if isinstance(obj, dict) else None
    source_key = "ended_at" if isinstance(ended_at, str) and ended_at else "last_tick_at"
    source_value = ended_at if source_key == "ended_at" else last_tick_at
    stale_seconds = _seconds_since(source_value if isinstance(source_value, str) else None)
    lock_state = str(obj.get("last_status") or "UNKNOWN") if isinstance(obj, dict) else "UNKNOWN"
    return {
        "stale_seconds": int(stale_seconds),
        "stale_source_key": source_key,
        "stale_source_value": source_value if isinstance(source_value, str) else "",
        "lock_state": lock_state,
        "heartbeat_path": str(hb_path),
    }


def _load_airrunner_state(*, workspace_root: Path, heartbeat_stale_seconds: int) -> dict[str, Any]:
    enabled_effective = False
    auto_mode_enabled = False
    active_hours_enabled = False
    active_hours_is_now = True

    try:
        from src.prj_airunner.airunner_tick_support import _load_policy as _load_airunner_policy

        airunner_policy, _, _, _ = _load_airunner_policy(workspace_root)
        enabled_effective = bool(airunner_policy.get("enabled", False))
        schedule = airunner_policy.get("schedule") if isinstance(airunner_policy.get("schedule"), dict) else {}
        active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
        active_hours_enabled = bool(active_hours.get("enabled", False))
        try:
            from src.prj_airunner.airunner_tick_utils import _within_active_hours

            active_hours_is_now, _ = _within_active_hours(schedule, datetime.now(timezone.utc))
        except Exception:
            active_hours_is_now = True
    except Exception:
        enabled_effective = False
        active_hours_enabled = False
        active_hours_is_now = True

    try:
        from src.prj_airunner.auto_mode_dispatch import load_auto_mode_policy

        auto_mode_policy, _, _, _ = load_auto_mode_policy(workspace_root=workspace_root)
        auto_mode_enabled = bool(auto_mode_policy.get("enabled", False))
    except Exception:
        auto_mode_enabled = False

    return {
        "enabled_effective": bool(enabled_effective),
        "auto_mode_enabled_effective": bool(auto_mode_enabled),
        "active_hours_enabled": bool(active_hours_enabled),
        "active_hours_is_now": bool(active_hours_is_now),
        "heartbeat_stale_seconds": int(heartbeat_stale_seconds),
    }


def _load_intake_noise_signal(*, workspace_root: Path) -> dict[str, Any]:
    intake_path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    cooldown_path = workspace_root / ".cache" / "index" / "intake_cooldowns.v1.json"
    now = datetime.now(timezone.utc)
    new_items_24h = 0
    if intake_path.exists():
        try:
            obj = _load_json(intake_path)
            items = obj.get("items") if isinstance(obj, dict) else None
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    last_seen = item.get("last_seen")
                    if isinstance(last_seen, str):
                        seen_dt = _parse_iso(last_seen)
                        if seen_dt and (now - seen_dt).total_seconds() <= 86400:
                            new_items_24h += 1
        except Exception:
            new_items_24h = 0
    suppressed_24h = 0
    if cooldown_path.exists():
        try:
            obj = _load_json(cooldown_path)
            entries = obj.get("entries") if isinstance(obj, dict) else None
            if isinstance(entries, dict):
                for entry in entries.values():
                    if not isinstance(entry, dict):
                        continue
                    last_seen = entry.get("last_seen")
                    seen_dt = _parse_iso(last_seen if isinstance(last_seen, str) else None)
                    if seen_dt and (now - seen_dt).total_seconds() <= 86400:
                        try:
                            suppressed_count = int(entry.get("suppressed_count", 0) or 0)
                        except Exception:
                            suppressed_count = 0
                        if suppressed_count > 0:
                            suppressed_24h += 1
        except Exception:
            suppressed_24h = 0
    return {"new_items_24h": int(new_items_24h), "suppressed_24h": int(suppressed_24h)}


def _collect_standard_packs(*, core_root: Path, workspace_root: Path) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    sources = [("core", core_root / "packs" / "standards"), ("workspace", workspace_root / "packs" / "standards")]
    for source, base in sources:
        if not base.exists():
            continue
        for manifest in sorted(base.rglob("pack.manifest.v1.json")):
            try:
                obj = _load_json(manifest)
            except Exception:
                continue
            pack_id = obj.get("pack_id") if isinstance(obj, dict) else None
            if not isinstance(pack_id, str):
                continue
            record = {
                "pack_id": pack_id,
                "version": obj.get("version"),
                "source": source,
                "manifest_path": manifest,
            }
            if pack_id in records and source == "workspace":
                records[pack_id] = record
            elif pack_id not in records:
                records[pack_id] = record
    return [records[k] for k in sorted(records)]


def _load_controls_metrics(pack_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    controls: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    controls_path = pack_dir / "controls.v1.json"
    metrics_path = pack_dir / "metrics.v1.json"
    if controls_path.exists():
        try:
            obj = _load_json(controls_path)
            items = obj.get("controls") if isinstance(obj, dict) else None
            if isinstance(items, list):
                for c in items:
                    if isinstance(c, dict) and isinstance(c.get("id"), str):
                        controls.append(c)
        except Exception:
            pass
    if metrics_path.exists():
        try:
            obj = _load_json(metrics_path)
            items = obj.get("metrics") if isinstance(obj, dict) else None
            if isinstance(items, list):
                for m in items:
                    if isinstance(m, dict) and isinstance(m.get("id"), str):
                        metrics.append(m)
        except Exception:
            pass
    return (controls, metrics)


def _inputs_sha256(files: list[Path], *, core_root: Path, workspace_root: Path) -> str:
    parts: list[str] = []
    for path in sorted(files, key=lambda p: p.as_posix()):
        if not path.exists() or not path.is_file():
            continue
        data = path.read_bytes()
        try:
            rel = path.relative_to(core_root)
        except Exception:
            try:
                rel = path.relative_to(workspace_root)
            except Exception:
                rel = path
        parts.append(f"{rel.as_posix()}:{_hash_bytes(data)}")
    payload = "\n".join(parts).encode("utf-8")
    return _hash_bytes(payload)


def _load_integrity_status(path: Path) -> str:
    try:
        obj = _load_json(path)
    except Exception:
        return ""
    if isinstance(obj, dict):
        return str(obj.get("verify_on_read_result") or "")
    return ""


def _load_assessment_raw_integrity_status(path: Path) -> str:
    try:
        obj = _load_json(path)
    except Exception:
        return ""
    if isinstance(obj, dict):
        signals = obj.get("signals")
        if isinstance(signals, dict):
            integrity = signals.get("integrity")
            if isinstance(integrity, dict):
                return str(integrity.get("status") or "")
            if integrity is not None:
                return str(integrity)
    return ""


def _write_if_missing_or_same(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        raise ValueError(f"CHG_CONTENT_MISMATCH:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _load_catalog_seed(seed_path: Path, workspace_root: Path) -> dict[str, Any] | None:
    if not seed_path.exists():
        return None
    try:
        obj = _load_json(seed_path)
    except Exception:
        return None

    def _normalize_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            s = item.strip()
            if s:
                out.append(s)
        return out

    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        items = []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not item_id or not title:
            continue
        source = str(item.get("source") or "seed").strip()
        tags_raw = item.get("tags") if isinstance(item.get("tags"), list) else []
        tags = [str(t).strip() for t in tags_raw if isinstance(t, str) and t.strip()]
        theme_id = str(item.get("theme_id") or "").strip()
        theme_title_tr = str(item.get("theme_title_tr") or "").strip()
        subtheme_id = str(item.get("subtheme_id") or "").strip()
        subtheme_title_tr = str(item.get("subtheme_title_tr") or "").strip()
        summary = str(item.get("summary") or "").strip()
        evidence_expectations = _normalize_str_list(item.get("evidence_expectations"))
        remediation = _normalize_str_list(item.get("remediation"))

        payload: dict[str, Any] = {
            "id": item_id,
            "title": title,
            "source": source,
            "tags": sorted(set(tags)),
        }
        if theme_id:
            payload["theme_id"] = theme_id
        if theme_title_tr:
            payload["theme_title_tr"] = theme_title_tr
        if subtheme_id:
            payload["subtheme_id"] = subtheme_id
        if subtheme_title_tr:
            payload["subtheme_title_tr"] = subtheme_title_tr
        if summary:
            payload["summary"] = summary
        if evidence_expectations:
            payload["evidence_expectations"] = evidence_expectations
        if remediation:
            payload["remediation"] = remediation

        normalized.append(payload)
    normalized.sort(key=lambda entry: entry["id"])
    generated_at = str(obj.get("generated_at") or _now_iso())
    return {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "items": normalized,
    }


def _pick_first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _seed_candidates(*, workspace_root: Path, core_root: Path) -> dict[str, list[Path]]:
    return {
        "bp": [
            workspace_root / ".cache" / "inputs" / "bp_catalog.seed.v1.json",
            core_root / "docs" / "OPERATIONS" / "north_star_bp_catalog.seed.v1.json",
        ],
        "trend": [
            workspace_root / ".cache" / "inputs" / "trend_catalog.seed.v1.json",
            core_root / "docs" / "OPERATIONS" / "north_star_trend_catalog.seed.v1.json",
        ],
    }


def _write_seed_catalogs(
    *, workspace_root: Path, out_bp_catalog: Path, out_trend_catalog: Path, core_root: Path | None = None
) -> dict[str, Any]:
    core_root = core_root or _repo_root()

    candidates = _seed_candidates(workspace_root=workspace_root, core_root=core_root)
    bp_seed = _pick_first_existing(candidates.get("bp", [])) or candidates.get("bp", [None])[0]
    trend_seed = _pick_first_existing(candidates.get("trend", [])) or candidates.get("trend", [None])[0]

    bp_payload = _load_catalog_seed(bp_seed, workspace_root) if isinstance(bp_seed, Path) else None
    trend_payload = _load_catalog_seed(trend_seed, workspace_root) if isinstance(trend_seed, Path) else None
    written: list[str] = []
    if bp_payload and bp_payload.get("items"):
        _atomic_write_json(out_bp_catalog, bp_payload)
        written.append(str(out_bp_catalog))
    if trend_payload and trend_payload.get("items"):
        _atomic_write_json(out_trend_catalog, trend_payload)
        written.append(str(out_trend_catalog))
    return {
        "bp_items": len(bp_payload.get("items", [])) if bp_payload else 0,
        "trend_items": len(trend_payload.get("items", [])) if trend_payload else 0,
        "seed_paths_used": sorted(
            set(
                [
                    str(p)
                    for p in [
                        bp_seed if isinstance(bp_seed, Path) else None,
                        trend_seed if isinstance(trend_seed, Path) else None,
                    ]
                    if p
                ]
            )
        ),
        "written": sorted(set(written)),
    }


def _write_integrity_md(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Integrity Verify Report",
        "",
        f"Generated at: {snapshot.get('generated_at', '')}",
        f"Workspace: {snapshot.get('workspace_root', '')}",
        f"Verify result: {snapshot.get('verify_on_read_result', '')}",
        f"Mismatch count: {snapshot.get('mismatch_count', 0)}",
        "",
        "Mismatches:",
    ]
    mismatches = snapshot.get("mismatches") if isinstance(snapshot, dict) else None
    if isinstance(mismatches, list) and mismatches:
        for item in mismatches:
            if isinstance(item, str) and item.strip():
                lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _draft_gap_chgs(*, workspace_root: Path, gap_register: dict[str, Any]) -> list[str]:
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    if not isinstance(gaps, list):
        return []

    safe_ids: list[str] = []
    plan_ids: list[str] = []
    for g in gaps:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        severity = g.get("severity")
        if not isinstance(gid, str):
            continue
        if severity == "low":
            safe_ids.append(gid)
        else:
            plan_ids.append(gid)

    safe_ids = sorted(set(safe_ids))
    plan_ids = sorted(set(plan_ids))
    drafted: list[str] = []
    chg_dir = workspace_root / ".cache" / "debt_chg"

    def _build_payload(chg_id: str, *, action_kind: str, file_relpath: str, note_text: str) -> dict[str, Any]:
        return {
            "id": chg_id,
            "version": "v1",
            "source": "SYSTEM_STATUS",
            "target_debt_kind": "BENCHMARK_GAP",
            "actions": [
                {
                    "kind": action_kind,
                    "file_relpath": file_relpath,
                    "note": {"text": note_text},
                }
            ],
            "safety": {"apply_scope": "INCUBATOR_ONLY", "destructive": False, "requires_review": True},
        }

    if safe_ids:
        chg_hash = _hash_bytes(("safe:" + ",".join(safe_ids)).encode("utf-8"))[:8]
        chg_id = f"CHG-GAP-SAFE-{chg_hash}"
        payload = _build_payload(
            chg_id,
            action_kind="DOC_NOTE",
            file_relpath="incubator/plans/benchmark_gap_safe.md",
            note_text="Safe-only gaps: " + ", ".join(safe_ids),
        )
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path = chg_dir / f"{chg_id}.json"
        _write_if_missing_or_same(path, content)
        drafted.append(str(path))

    if plan_ids:
        chg_hash = _hash_bytes(("plan:" + ",".join(plan_ids)).encode("utf-8"))[:8]
        chg_id = f"CHG-GAP-PLAN-{chg_hash}"
        payload = _build_payload(
            chg_id,
            action_kind="REFACTOR_HINT",
            file_relpath="incubator/plans/benchmark_gap_plan.md",
            note_text="Plan-only gaps: " + ", ".join(plan_ids),
        )
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path = chg_dir / f"{chg_id}.json"
        _write_if_missing_or_same(path, content)
        drafted.append(str(path))

    return drafted


def run_assessment(*, workspace_root: Path, dry_run: bool) -> dict[str, Any]:
    core_root = _repo_root()
    docs_drift_mapping = _load_docs_drift_mapping(core_root=core_root, workspace_root=workspace_root)
    policy = _load_policy(core_root=core_root, workspace_root=workspace_root)
    if not isinstance(policy, dict) or not policy.get("enabled", True):
        return {"status": "SKIPPED", "reason": "policy_disabled"}

    outputs = policy.get("outputs") if isinstance(policy, dict) else None
    if not isinstance(outputs, dict):
        return _fail("BENCHMARK_SCHEMA_INVALID", "policy.outputs missing or invalid")

    try:
        out_catalog = _resolve_output_path(workspace_root, str(outputs.get("north_star_catalog")))
        out_assessment = _resolve_output_path(workspace_root, str(outputs.get("assessment")))
        out_cursor = _resolve_output_path(workspace_root, str(outputs.get("assessment_cursor")))
        out_scorecard_json = _resolve_output_path(workspace_root, str(outputs.get("scorecard_json")))
        out_scorecard_md = _resolve_output_path(workspace_root, str(outputs.get("scorecard_md")))
        out_gap_register = _resolve_output_path(workspace_root, str(outputs.get("gap_register")))
        out_gap_md = _resolve_output_path(workspace_root, str(outputs.get("gap_summary_md")))
        out_assessment_raw = _resolve_output_path(workspace_root, ".cache/index/assessment_raw.v1.json")
        out_bp_catalog = _resolve_output_path(workspace_root, ".cache/index/bp_catalog.v1.json")
        out_trend_catalog = _resolve_output_path(workspace_root, ".cache/index/trend_catalog.v1.json")
        out_assessment_eval = _resolve_output_path(workspace_root, ".cache/index/assessment_eval.v1.json")
        out_integrity_json = _resolve_output_path(workspace_root, ".cache/reports/integrity_verify.v1.json")
        out_integrity_md = _resolve_output_path(workspace_root, ".cache/reports/integrity_verify.v1.md")
    except Exception as e:
        return _fail("BENCHMARK_WRITE_VIOLATION", "output path escapes workspace_root", {"error": str(e)[:200]})

    core_standards = list((core_root / "packs" / "standards").rglob("pack.manifest.v1.json"))
    if not core_standards:
        return _fail("BENCHMARK_INPUT_MISSING", "no standard packs found", {"path": "packs/standards"})

    packs = _collect_standard_packs(core_root=core_root, workspace_root=workspace_root)
    controls: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    warnings: list[str] = []
    input_files: list[Path] = []
    self_path = Path(__file__).resolve()
    input_files.append(self_path)
    eval_runner_path = self_path.with_name("eval_runner.py")
    if eval_runner_path.exists():
        input_files.append(eval_runner_path)

    for pack in packs:
        manifest_path = pack.get("manifest_path")
        if isinstance(manifest_path, Path):
            input_files.append(manifest_path)
            pack_dir = manifest_path.parent
            c_list, m_list = _load_controls_metrics(pack_dir)
            for c in c_list:
                c_item = dict(c)
                c_item["pack_id"] = pack.get("pack_id")
                controls.append(c_item)
            for m in m_list:
                m_item = dict(m)
                m_item["pack_id"] = pack.get("pack_id")
                metrics.append(m_item)
            if not c_list and not m_list:
                warnings.append(f"pack_missing_controls_or_metrics:{pack.get('pack_id')}")
            controls_path = pack_dir / "controls.v1.json"
            metrics_path = pack_dir / "metrics.v1.json"
            if controls_path.exists():
                input_files.append(controls_path)
            if metrics_path.exists():
                input_files.append(metrics_path)

    policy_candidates = [
        workspace_root / "policies" / "policy_north_star_eval_lenses.v1.json",
        core_root / "policies" / "policy_north_star_eval_lenses.v1.json",
        workspace_root / "policies" / "policy_north_star_operability.v1.json",
        core_root / "policies" / "policy_north_star_operability.v1.json",
        workspace_root / ".cache" / "policy_overrides" / "policy_north_star_operability.override.v1.json",
    ]
    for candidate in policy_candidates:
        if candidate.exists():
            input_files.append(candidate)

    if docs_drift_mapping.get("include_extension_manifest_refs", True):
        input_files.extend(_collect_extension_manifest_paths(core_root))
    input_files.extend(_iter_md_paths(core_root, exclude_dirs=DOCS_DRIFT_EXCLUDE_DIRS))
    for seed_path in [
        _pick_first_existing(_seed_candidates(workspace_root=workspace_root, core_root=core_root).get("bp", [])),
        _pick_first_existing(_seed_candidates(workspace_root=workspace_root, core_root=core_root).get("trend", [])),
    ]:
        if seed_path and seed_path.exists():
            input_files.append(seed_path)

    input_files.append(workspace_root / ".cache" / "airunner" / "airunner_heartbeat.v1.json")

    controls = sorted(controls, key=lambda x: str(x.get("id") or ""))
    metrics = sorted(metrics, key=lambda x: str(x.get("id") or ""))

    control_statuses = _load_control_statuses(core_root=core_root, workspace_root=workspace_root)
    filtered_control_ids: list[str] = []
    controls_for_gaps = controls
    if control_statuses:
        controls_for_gaps = []
        for control in controls:
            cid = control.get("id") if isinstance(control, dict) else None
            if isinstance(cid, str) and control_statuses.get(cid):
                filtered_control_ids.append(cid)
                continue
            controls_for_gaps.append(control)
        filtered_control_ids = sorted(set(filtered_control_ids))

    inputs_sha = _inputs_sha256(input_files, core_root=core_root, workspace_root=workspace_root)
    cursor_obj = None
    if out_cursor.exists():
        try:
            cursor_obj = _load_json(out_cursor)
        except Exception:
            cursor_obj = None

    if isinstance(cursor_obj, dict) and cursor_obj.get("inputs_sha256") == inputs_sha:
        if (
            out_catalog.exists()
            and out_assessment.exists()
            and out_scorecard_json.exists()
            and out_gap_register.exists()
            and out_assessment_raw.exists()
            and out_assessment_eval.exists()
            and out_integrity_json.exists()
        ):
            raw_status = _load_assessment_raw_integrity_status(out_assessment_raw)
            verify_status = _load_integrity_status(out_integrity_json)
            if raw_status and verify_status and raw_status != verify_status:
                pass
            else:
                return {
                    "status": "OK",
                    "unchanged": True,
                    "out": str(out_assessment),
                    "packs": len(packs),
                    "controls": len(controls),
                    "metrics": len(metrics),
                }

    catalog = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "packs": [
            {
                "pack_id": p.get("pack_id"),
                "version": p.get("version"),
                "source": p.get("source"),
                "control_count": len([c for c in controls if c.get("pack_id") == p.get("pack_id")]),
                "metric_count": len([m for m in metrics if m.get("pack_id") == p.get("pack_id")]),
            }
            for p in packs
        ],
        "controls": controls,
        "metrics": metrics,
        "warnings": sorted(set(warnings)),
    }

    assessment = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "packs": len(packs),
        "controls": len(controls),
        "metrics": len(metrics),
        "status": "OK" if controls else "WARN",
        "warnings": sorted(set(warnings)),
    }

    integrity_policy = load_policy_integrity(core_root=core_root, workspace_root=workspace_root)
    integrity_snapshot = build_integrity_snapshot(
        workspace_root=workspace_root,
        core_root=core_root,
        policy=integrity_policy,
        previous_snapshot=None,
    )
    integrity_ref = str(Path(".cache") / "reports" / "integrity_verify.v1.json")
    integrity_result = str(integrity_snapshot.get("verify_on_read_result") or "WARN")
    allow_report_only = bool(integrity_policy.get("allow_report_only_when_missing_sources", True))

    integrity_schema_path = core_root / "schemas" / "integrity-snapshot.schema.v1.json"
    if integrity_schema_path.exists():
        try:
            schema = _load_json(integrity_schema_path)
            Draft202012Validator(schema).validate(integrity_snapshot)
        except Exception as e:
            return _fail("BENCHMARK_SCHEMA_INVALID", "integrity snapshot schema validation failed", {"error": str(e)[:200]})

    script_budget_signal = _load_script_budget_signal(core_root=core_root, workspace_root=workspace_root)
    doc_nav_signal = _load_doc_nav_signal(workspace_root=workspace_root)
    jobs_signal = _load_jobs_signal(workspace_root=workspace_root)
    _maybe_auto_pdca_recheck(
        core_root=core_root,
        workspace_root=workspace_root,
        script_budget_signal=script_budget_signal,
        dry_run=dry_run,
    )
    pdca_cursor_signal = _load_pdca_cursor_signal(workspace_root=workspace_root)
    heartbeat_signal = _load_heartbeat_signal(workspace_root=workspace_root)
    airrunner_state_signal = _load_airrunner_state(
        workspace_root=workspace_root,
        heartbeat_stale_seconds=int(heartbeat_signal.get("stale_seconds", 0) or 0),
    )
    intake_noise_signal = _load_intake_noise_signal(workspace_root=workspace_root)
    integrity_signal = {"status": str(integrity_result or "UNKNOWN")}
    docs_hygiene_signal = _load_docs_hygiene_signal(core_root=core_root)
    docs_drift_signal = _load_docs_drift_signal(
        core_root=core_root, workspace_root=workspace_root, mapping=docs_drift_mapping
    )
    integration_coherence_signals = _load_integration_coherence_signals(workspace_root=workspace_root)

    assessment_raw = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": assessment.get("status"),
        "integrity_snapshot_ref": integrity_ref,
        "source_hashes": integrity_snapshot.get("input_hashes") or {},
        "inputs": {
            "packs": len(packs),
            "controls": len(controls),
            "metrics": len(metrics),
            "warnings": sorted(set(warnings)),
        },
        "signals": {
            "script_budget": script_budget_signal,
            "doc_nav": doc_nav_signal,
            "airunner_jobs": jobs_signal,
            "pdca_cursor": pdca_cursor_signal,
            "airunner_heartbeat": heartbeat_signal,
            "airrunner_state": airrunner_state_signal,
            "work_intake_noise": intake_noise_signal,
            "integrity": integrity_signal,
            "docs_hygiene": docs_hygiene_signal,
            "docs_drift": docs_drift_signal,
        },
        "integration_coherence_signals": integration_coherence_signals,
        "notes": (
            [f"controls_satisfied_by_policy:{','.join(filtered_control_ids)}"] if filtered_control_ids else []
        ),
    }

    raw_schema_path = core_root / "schemas" / "assessment-raw.schema.v1.json"
    if raw_schema_path.exists():
        try:
            schema = _load_json(raw_schema_path)
            Draft202012Validator(schema).validate(assessment_raw)
        except Exception as e:
            return _fail("BENCHMARK_SCHEMA_INVALID", "assessment_raw schema validation failed", {"error": str(e)[:200]})

    scorecard = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "packs": len(packs),
        "controls": len(controls),
        "metrics": len(metrics),
        "status": assessment.get("status"),
    }
    scorecard_md = "\n".join(
        [
            "# Benchmark Scorecard",
            "",
            f"Packs: {len(packs)}",
            f"Controls: {len(controls)}",
            f"Metrics: {len(metrics)}",
            f"Status: {assessment.get('status')}",
        ]
    ) + "\n"

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "out": str(out_assessment),
            "packs": len(packs),
            "controls": len(controls),
            "metrics": len(metrics),
            "inputs_sha256": inputs_sha,
            "outputs": [
                str(out_catalog),
                str(out_assessment),
                str(out_assessment_raw),
                str(out_cursor),
                str(out_assessment_eval),
                str(out_bp_catalog),
                str(out_trend_catalog),
                str(out_integrity_json),
                str(out_integrity_md),
                str(out_scorecard_json),
                str(out_scorecard_md),
                str(out_gap_register),
                str(out_gap_md),
            ],
        }

    for path in [
        out_catalog,
        out_assessment,
        out_cursor,
        out_scorecard_json,
        out_scorecard_md,
        out_gap_register,
        out_gap_md,
        out_assessment_raw,
        out_assessment_eval,
        out_bp_catalog,
        out_trend_catalog,
        out_integrity_json,
        out_integrity_md,
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)

    out_integrity_json.write_text(
        json.dumps(integrity_snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_integrity_md(out_integrity_md, integrity_snapshot)

    out_assessment_raw.write_text(
        json.dumps(assessment_raw, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    out_catalog.write_text(json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_assessment.write_text(json.dumps(assessment, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_scorecard_json.write_text(json.dumps(scorecard, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_scorecard_md.write_text(scorecard_md, encoding="utf-8")

    if integrity_result == "FAIL" and not allow_report_only:
        return _fail("INTEGRITY_BLOCKED", "integrity verify failed", {"integrity_ref": integrity_ref})

    _write_seed_catalogs(workspace_root=workspace_root, out_bp_catalog=out_bp_catalog, out_trend_catalog=out_trend_catalog)

    eval_res = run_eval(workspace_root=workspace_root, dry_run=False)
    eval_report_only = bool(eval_res.get("report_only")) if isinstance(eval_res, dict) else False

    source_eval_hash = _hash_bytes(out_assessment_eval.read_bytes()) if out_assessment_eval.exists() else None
    source_raw_hash = _hash_bytes(out_assessment_raw.read_bytes()) if out_assessment_raw.exists() else None
    evidence_pointers = [str(Path(".cache") / "index" / "assessment_raw.v1.json"), integrity_ref]
    if out_assessment_eval.exists():
        evidence_pointers.append(str(Path(".cache") / "index" / "assessment_eval.v1.json"))
    evidence_pointers = sorted(set(evidence_pointers))

    lens_signals: list[dict[str, Any]] = []
    if out_assessment_eval.exists():
        try:
            eval_obj = _load_json(out_assessment_eval)
        except Exception:
            eval_obj = {}
        lenses = eval_obj.get("lenses") if isinstance(eval_obj, dict) else None
        if isinstance(lenses, dict):
            for lens_id, lens in lenses.items():
                if not isinstance(lens_id, str) or not lens_id:
                    continue
                if not isinstance(lens, dict):
                    continue
                status = lens.get("status")
                if isinstance(status, str) and status:
                    reasons = lens.get("reasons") if isinstance(lens, dict) else None
                    reasons_list = (
                        [str(r) for r in reasons if isinstance(r, str) and r.strip()] if isinstance(reasons, list) else []
                    )
                    lens_signals.append(
                        {
                            "lens_id": lens_id,
                            "status": status,
                            "score": lens.get("score"),
                            "reasons": reasons_list,
                        }
                    )
            lens_signals.sort(key=lambda item: str(item.get("lens_id") or ""))

    report_only = eval_report_only or integrity_result == "FAIL"
    previous_gap_register = None
    previous_gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    if previous_gap_path.exists():
        try:
            previous_gap_register = _load_json(previous_gap_path)
        except Exception:
            previous_gap_register = None
    gap_register = build_gap_register(
        controls=controls_for_gaps,
        metrics=metrics,
        lens_signals=lens_signals,
        integrity_snapshot_ref=integrity_ref,
        source_eval_hash=source_eval_hash,
        source_raw_hash=source_raw_hash,
        evidence_pointers=evidence_pointers,
        report_only=report_only,
        previous_gap_register=previous_gap_register,
        cooldown_seconds=86400,
    )
    gap_summary_md = build_gap_summary_md(gap_register=gap_register)

    schema_path = core_root / "schemas" / "gap.record.schema.json"
    if schema_path.exists():
        try:
            schema = _load_json(schema_path)
            Draft202012Validator(schema).validate(gap_register)
        except Exception as e:
            return _fail("BENCHMARK_SCHEMA_INVALID", "gap register schema validation failed", {"error": str(e)[:200]})

    out_gap_register.write_text(json.dumps(gap_register, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_gap_md.write_text(gap_summary_md, encoding="utf-8")

    outputs_sha = _hash_bytes(json.dumps(assessment, sort_keys=True).encode("utf-8"))
    cursor = {
        "version": "v1",
        "inputs_sha256": inputs_sha,
        "outputs_sha256": outputs_sha,
        "generated_at": _now_iso(),
    }
    out_cursor.write_text(json.dumps(cursor, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    drafted = _draft_gap_chgs(workspace_root=workspace_root, gap_register=gap_register)

    return {
        "status": "OK",
        "out": str(out_assessment),
        "packs": len(packs),
        "controls": len(controls),
        "metrics": len(metrics),
        "gap_chg_drafts": len(drafted),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    dry_run = str(args.dry_run).lower() == "true"
    workspace_root = Path(args.workspace_root).resolve()

    try:
        payload = run_assessment(workspace_root=workspace_root, dry_run=dry_run)
    except Exception as e:
        payload = _fail("BENCHMARK_INTERNAL_ERROR", "unexpected error", {"error": str(e)[:200]})

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else None
    return 0 if status in {"OK", "WOULD_WRITE", "SKIPPED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
