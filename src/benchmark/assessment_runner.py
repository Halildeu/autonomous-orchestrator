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


DOCS_DRIFT_DEFAULT_VIEW_ALLOWLIST = [
    "docs/ARCHITECTURE/**/*.md",
    "docs/DECISIONS/**/*.md",
    "docs/OPERATIONS/**/*.md",
    "fixtures/**/*.md",
    "modules/**/README.md",
    "roadmaps/PROJECTS/**/*.md",
    "templates/**/*.md",
]
DOCS_DRIFT_DEFAULT_MAPPING = {
    "include_extension_manifest_refs": True,
    "view_doc_allowlist_globs": DOCS_DRIFT_DEFAULT_VIEW_ALLOWLIST,
    "exclude_legacy_redirect_stubs": True,
    "exclude_archive_only_banners": True,
    "root_readme_mode": "mapped",
    "root_changelog_mode": "mapped",
}
DOCS_DRIFT_EXCLUDE_DIRS = {".cache", "evidence", ".codex", ".venv", ".git"}
DOCS_DRIFT_LEGACY_MARKERS = ("Legacy Redirect", "ARCHIVE ONLY")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _seconds_since(value: str | None) -> int:
    parsed = _parse_iso(value)
    if parsed is None:
        return 0
    delta = datetime.now(timezone.utc) - parsed
    return max(0, int(delta.total_seconds()))


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _resolve_output_path(workspace_root: Path, rel_path: str) -> Path:
    rel = Path(rel_path).as_posix()
    out = (workspace_root / rel).resolve()
    _ensure_inside_workspace(workspace_root, out)
    return out


def _fail(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "FAIL", "error_code": code}
    if message:
        payload["message"] = message
    if details:
        payload["details"] = details
    return payload


def _load_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_benchmark.v1.json"
    core_policy = core_root / "policies" / "policy_benchmark.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {
            "version": "v1",
            "enabled": True,
            "cursor_mode": "hash",
            "outputs": {
                "north_star_catalog": ".cache/index/north_star_catalog.v1.json",
                "assessment": ".cache/index/assessment.v1.json",
                "assessment_cursor": ".cache/index/assessment_cursor.v1.json",
                "scorecard_json": ".cache/reports/benchmark_scorecard.v1.json",
                "scorecard_md": ".cache/reports/benchmark_scorecard.v1.md",
                "gap_register": ".cache/index/gap_register.v1.json",
                "gap_summary_md": ".cache/reports/gap_summary.v1.md",
            },
            "max_controls": 2000,
        }
    return _load_json(path)


def _load_script_budget_signal(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_report = workspace_root / ".cache" / "script_budget" / "report.json"
    report_path = ws_report if ws_report.exists() else core_root / ".cache" / "script_budget" / "report.json"
    if not report_path.exists():
        return {"hard_exceeded": 0, "soft_exceeded": 0, "top_offenders": [], "report_path": ""}
    try:
        obj = _load_json(report_path)
    except Exception:
        return {"hard_exceeded": 0, "soft_exceeded": 0, "top_offenders": [], "report_path": str(report_path)}

    exceeded_hard = obj.get("exceeded_hard") if isinstance(obj, dict) else None
    exceeded_soft = obj.get("exceeded_soft") if isinstance(obj, dict) else None
    function_hard = obj.get("function_hard") if isinstance(obj, dict) else None
    function_soft = obj.get("function_soft") if isinstance(obj, dict) else None

    hard_count = len(exceeded_hard) if isinstance(exceeded_hard, list) else 0
    hard_count += len(function_hard) if isinstance(function_hard, list) else 0
    soft_count = len(exceeded_soft) if isinstance(exceeded_soft, list) else 0
    soft_count += len(function_soft) if isinstance(function_soft, list) else 0

    offenders: list[str] = []
    for entry in (exceeded_hard or []) + (exceeded_soft or []) + (function_hard or []) + (function_soft or []):
        if isinstance(entry, dict):
            for key in ("path", "file", "filename"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip():
                    offenders.append(val)
                    break
        elif isinstance(entry, str):
            offenders.append(entry)

    return {
        "hard_exceeded": int(hard_count),
        "soft_exceeded": int(soft_count),
        "top_offenders": sorted({p for p in offenders if p}),
        "report_path": str(report_path),
    }


def _load_doc_nav_signal(*, workspace_root: Path) -> dict[str, Any]:
    strict_path = workspace_root / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    summary_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    report_path = strict_path if strict_path.exists() else summary_path
    if not report_path.exists():
        return {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0, "report_path": ""}
    try:
        obj = _load_json(report_path)
    except Exception:
        return {"placeholders_count": 0, "broken_refs": 0, "orphan_critical": 0, "report_path": str(report_path)}
    counts = obj.get("counts") if isinstance(obj, dict) else None
    if isinstance(counts, dict):
        placeholders = int(counts.get("placeholder_refs_count", 0) or 0)
        broken_refs = int(counts.get("broken_refs", 0) or 0)
        orphan_critical = int(counts.get("orphan_critical", 0) or 0)
    else:
        placeholders = int(obj.get("placeholder_refs_count", 0) or 0) if isinstance(obj, dict) else 0
        broken_refs = int(obj.get("broken_refs", 0) or 0) if isinstance(obj, dict) else 0
        orphan_critical = int(obj.get("orphan_critical", 0) or 0) if isinstance(obj, dict) else 0
    return {
        "placeholders_count": placeholders,
        "broken_refs": broken_refs,
        "orphan_critical": orphan_critical,
        "report_path": str(report_path),
    }


def _iter_md_paths(root: Path, *, exclude_dirs: set[str]) -> list[Path]:
    if not root.exists():
        return []
    paths: list[Path] = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def _load_docs_hygiene_signal(*, core_root: Path) -> dict[str, Any]:
    repo_root = core_root
    ops_root = repo_root / "docs" / "OPERATIONS"
    ops_files = _iter_md_paths(ops_root, exclude_dirs=set())
    docs_ops_md_count = len(ops_files)
    docs_ops_md_bytes = sum(p.stat().st_size for p in ops_files)
    repo_files = _iter_md_paths(repo_root, exclude_dirs=DOCS_DRIFT_EXCLUDE_DIRS)
    repo_md_total_count = len(repo_files)
    return {
        "docs_ops_md_count": int(docs_ops_md_count),
        "docs_ops_md_bytes": int(docs_ops_md_bytes),
        "repo_md_total_count": int(repo_md_total_count),
    }

def _load_operability_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_north_star_operability.v1.json"
    core_policy = core_root / "policies" / "policy_north_star_operability.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {}
    try:
        obj = _load_json(path)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _maybe_auto_pdca_recheck(
    *, core_root: Path, workspace_root: Path, script_budget_signal: dict[str, Any], dry_run: bool
) -> None:
    if dry_run:
        return
    report_path = str(script_budget_signal.get("report_path") or "")
    if not report_path:
        return
    hard_exceeded = int(script_budget_signal.get("hard_exceeded", 0) or 0)
    if hard_exceeded > 0:
        return

    operability_policy = _load_operability_policy(core_root=core_root, workspace_root=workspace_root)
    thresholds = (
        operability_policy.get("thresholds")
        if isinstance(operability_policy.get("thresholds"), dict)
        else {}
    )
    try:
        stale_warn = float(thresholds.get("pdca_cursor_stale_hours_warn", 0) or 0)
    except Exception:
        stale_warn = 0.0
    if stale_warn <= 0:
        return

    cursor_signal = _load_pdca_cursor_signal(workspace_root=workspace_root)
    try:
        stale_hours = float(cursor_signal.get("stale_hours", 0.0) or 0.0)
    except Exception:
        stale_hours = 0.0
    if stale_hours <= stale_warn:
        return

    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    if not gap_path.exists():
        return

    try:
        from src.benchmark.pdca_runner import run_pdca

        run_pdca(workspace_root=workspace_root, dry_run=False)
    except Exception:
        return


def _load_docs_drift_mapping(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    mapping = dict(DOCS_DRIFT_DEFAULT_MAPPING)
    mapping["view_doc_allowlist_globs"] = list(DOCS_DRIFT_DEFAULT_VIEW_ALLOWLIST)
    policy = _load_operability_policy(core_root=core_root, workspace_root=workspace_root)
    raw = policy.get("docs_drift_mapping") if isinstance(policy, dict) else None
    if not isinstance(raw, dict):
        return mapping
    if isinstance(raw.get("include_extension_manifest_refs"), bool):
        mapping["include_extension_manifest_refs"] = raw.get("include_extension_manifest_refs")
    if isinstance(raw.get("exclude_legacy_redirect_stubs"), bool):
        mapping["exclude_legacy_redirect_stubs"] = raw.get("exclude_legacy_redirect_stubs")
    if isinstance(raw.get("exclude_archive_only_banners"), bool):
        mapping["exclude_archive_only_banners"] = raw.get("exclude_archive_only_banners")
    globs = raw.get("view_doc_allowlist_globs")
    if isinstance(globs, list):
        cleaned = sorted({str(x) for x in globs if isinstance(x, str) and x.strip()})
        if cleaned:
            mapping["view_doc_allowlist_globs"] = cleaned
    for key in ("root_readme_mode", "root_changelog_mode"):
        value = raw.get(key)
        if value in ("mapped", "unmapped"):
            mapping[key] = value
    return mapping


def _collect_extension_manifest_paths(core_root: Path) -> list[Path]:
    ext_root = core_root / "extensions"
    if not ext_root.exists():
        return []
    return sorted(ext_root.rglob("extension.manifest*.json"))


def _extract_md_links(*, text: str, core_root: Path) -> set[str]:
    md_pattern = re.compile(r"([A-Za-z0-9_./-]+\.md)")
    hits: set[str] = set()
    core_root = core_root.resolve()
    for match in md_pattern.findall(text or ""):
        token = match.strip()
        if token.startswith("./"):
            token = token[2:]
        if token.startswith("/"):
            token = token[1:]
        if not token:
            continue
        rel = Path(token).as_posix()
        candidate = (core_root / rel).resolve()
        try:
            candidate.relative_to(core_root)
        except Exception:
            continue
        if candidate.exists() and candidate.is_file():
            hits.add(candidate.relative_to(core_root).as_posix())
    return hits


def _resolve_manifest_ref(*, core_root: Path, manifest_path: Path, ref: str) -> str | None:
    if not isinstance(ref, str) or not ref.strip():
        return None
    ref_path = Path(ref)
    candidates: list[Path] = []
    if ref_path.is_absolute():
        candidates.append(ref_path)
    else:
        candidates.append((core_root / ref_path).resolve())
        candidates.append((manifest_path.parent / ref_path).resolve())
    core_root = core_root.resolve()
    for candidate in candidates:
        try:
            candidate.relative_to(core_root)
        except Exception:
            continue
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".md":
            return candidate.relative_to(core_root).as_posix()
    return None


def _collect_extension_manifest_refs(*, core_root: Path, manifest_paths: list[Path]) -> set[str]:
    refs: set[str] = set()
    for manifest_path in manifest_paths:
        try:
            obj = _load_json(manifest_path)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        doc_ref = obj.get("docs_ref")
        if isinstance(doc_ref, str):
            resolved = _resolve_manifest_ref(core_root=core_root, manifest_path=manifest_path, ref=doc_ref)
            if resolved:
                refs.add(resolved)
        ai_refs = obj.get("ai_context_refs")
        if isinstance(ai_refs, list):
            for item in ai_refs:
                if isinstance(item, str):
                    resolved = _resolve_manifest_ref(core_root=core_root, manifest_path=manifest_path, ref=item)
                    if resolved:
                        refs.add(resolved)
    return refs


def _collect_view_allowlist(*, core_root: Path, globs: list[str]) -> set[str]:
    allowlist: set[str] = set()
    core_root = core_root.resolve()
    for pattern in globs:
        for path in core_root.glob(pattern):
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            if any(part in DOCS_DRIFT_EXCLUDE_DIRS for part in path.parts):
                continue
            try:
                rel = path.relative_to(core_root).as_posix()
            except Exception:
                continue
            allowlist.add(rel)
    return allowlist


def _is_legacy_excluded(
    *, path: Path, exclude_legacy_redirect: bool, exclude_archive_only: bool, max_lines: int = 30
) -> bool:
    if not exclude_legacy_redirect and not exclude_archive_only:
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:max_lines]
    except Exception:
        return False
    head = "\n".join(lines)
    if exclude_legacy_redirect and DOCS_DRIFT_LEGACY_MARKERS[0] in head:
        return True
    if exclude_archive_only and DOCS_DRIFT_LEGACY_MARKERS[1] in head:
        return True
    return False


def compute_docs_drift_signal(*, core_root: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    all_md_paths = _iter_md_paths(core_root, exclude_dirs=DOCS_DRIFT_EXCLUDE_DIRS)
    all_md = {p.relative_to(core_root).as_posix() for p in all_md_paths}
    archive_md = {p for p in all_md if p.startswith("docs/ARCHIVE/")}

    ssot_linked: set[str] = set()
    ssot_map_path = core_root / "docs" / "OPERATIONS" / "SSOT-MAP.md"
    agents_path = core_root / "AGENTS.md"
    if ssot_map_path.exists():
        ssot_linked |= _extract_md_links(text=ssot_map_path.read_text(encoding="utf-8"), core_root=core_root)
    if agents_path.exists():
        ssot_linked |= _extract_md_links(text=agents_path.read_text(encoding="utf-8"), core_root=core_root)

    view_globs = mapping.get("view_doc_allowlist_globs")
    view_globs = view_globs if isinstance(view_globs, list) else []
    view_allowlist = _collect_view_allowlist(core_root=core_root, globs=view_globs)

    manifest_paths = _collect_extension_manifest_paths(core_root)
    if mapping.get("include_extension_manifest_refs", True):
        manifest_refs = _collect_extension_manifest_refs(core_root=core_root, manifest_paths=manifest_paths)
    else:
        manifest_refs = set()

    root_mapped: set[str] = set()
    if mapping.get("root_readme_mode") == "mapped" and (core_root / "README.md").exists():
        root_mapped.add("README.md")
    if mapping.get("root_changelog_mode") == "mapped" and (core_root / "CHANGELOG.md").exists():
        root_mapped.add("CHANGELOG.md")

    mapped = ssot_linked | view_allowlist | manifest_refs | root_mapped

    legacy_excluded: set[str] = set()
    exclude_legacy = bool(mapping.get("exclude_legacy_redirect_stubs", True))
    exclude_archive_only = bool(mapping.get("exclude_archive_only_banners", True))
    if exclude_legacy or exclude_archive_only:
        for rel in sorted(all_md - archive_md):
            path = core_root / rel
            if _is_legacy_excluded(
                path=path,
                exclude_legacy_redirect=exclude_legacy,
                exclude_archive_only=exclude_archive_only,
            ):
                legacy_excluded.add(rel)

    unmapped = sorted(all_md - mapped - archive_md - legacy_excluded)
    return {
        "unmapped_md_count": len(unmapped),
        "unmapped_md_sample": unmapped[:20],
        "mapped_sources": {
            "ssot_router_count": len(ssot_linked),
            "extension_manifest_ref_count": len(manifest_refs),
            "view_doc_allowlist_count": len(view_allowlist),
            "excluded_legacy_count": len(legacy_excluded),
            "excluded_archive_count": len(archive_md),
        },
    }


def _load_docs_drift_signal(
    *, core_root: Path, workspace_root: Path, mapping: dict[str, Any] | None = None
) -> dict[str, Any]:
    docs_mapping = mapping or _load_docs_drift_mapping(core_root=core_root, workspace_root=workspace_root)
    return compute_docs_drift_signal(core_root=core_root, mapping=docs_mapping)


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

    try:
        from src.prj_airunner.airunner_tick_support import _load_policy as _load_airunner_policy

        airunner_policy, _, _, _ = _load_airunner_policy(workspace_root)
        enabled_effective = bool(airunner_policy.get("enabled", False))
        schedule = airunner_policy.get("schedule") if isinstance(airunner_policy.get("schedule"), dict) else {}
        active_hours = schedule.get("active_hours") if isinstance(schedule.get("active_hours"), dict) else {}
        active_hours_enabled = bool(active_hours.get("enabled", False))
    except Exception:
        enabled_effective = False
        active_hours_enabled = False

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
        normalized.append(
            {
                "id": item_id,
                "title": title,
                "source": source,
                "tags": sorted(set(tags)),
            }
        )
    normalized.sort(key=lambda entry: entry["id"])
    generated_at = str(obj.get("generated_at") or _now_iso())
    return {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "items": normalized,
    }


def _write_seed_catalogs(*, workspace_root: Path, out_bp_catalog: Path, out_trend_catalog: Path) -> dict[str, Any]:
    bp_seed = workspace_root / ".cache" / "inputs" / "bp_catalog.seed.v1.json"
    trend_seed = workspace_root / ".cache" / "inputs" / "trend_catalog.seed.v1.json"
    bp_payload = _load_catalog_seed(bp_seed, workspace_root)
    trend_payload = _load_catalog_seed(trend_seed, workspace_root)
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
    input_files.append(Path(__file__).resolve())

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
    ]
    for candidate in policy_candidates:
        if candidate.exists():
            input_files.append(candidate)

    if docs_drift_mapping.get("include_extension_manifest_refs", True):
        input_files.extend(_collect_extension_manifest_paths(core_root))
    input_files.extend(_iter_md_paths(core_root, exclude_dirs=DOCS_DRIFT_EXCLUDE_DIRS))
    for seed_path in [
        workspace_root / ".cache" / "inputs" / "bp_catalog.seed.v1.json",
        workspace_root / ".cache" / "inputs" / "trend_catalog.seed.v1.json",
    ]:
        if seed_path.exists():
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
