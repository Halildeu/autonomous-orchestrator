from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.benchmark.assessment_signals import _load_pdca_cursor_signal

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


