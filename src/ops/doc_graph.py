from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


@dataclass(frozen=True)
class DocGraphPolicy:
    enabled: bool
    mode: str
    broken_core: str
    broken_workspace: str
    workspace_bound_patterns: list[str]
    deprecated_patterns: list[str]
    wrong_path_patterns: list[str]
    max_broken_refs: int
    max_orphan_critical: int
    placeholder_warn_threshold: int
    placeholders_baseline_enabled: bool
    placeholders_warn_mode: str
    placeholders_warn_delta: int
    placeholders_fail: int
    strict_fail_on_broken: bool
    strict_fail_on_critical_nav_gaps: bool
    orphan_target: int


def _load_policy(core_root: Path, workspace_root: Path) -> DocGraphPolicy:
    defaults = DocGraphPolicy(
        enabled=True,
        mode="report",
        broken_core="fail",
        broken_workspace="warn",
        workspace_bound_patterns=[
            "${WORKSPACE_ROOT}/**",
            ".cache/**",
            "incubator/**",
            "tenant/**",
            "project/**",
            "roadmaps/PROJECTS/**",
        ],
        deprecated_patterns=["legacy", "deprecated", "ROADMAP_v2.7_legacy.md"],
        wrong_path_patterns=["schemas/policies", "policies/schemas"],
        max_broken_refs=1000,
        max_orphan_critical=1000,
        placeholder_warn_threshold=25,
        placeholders_baseline_enabled=False,
        placeholders_warn_mode="threshold",
        placeholders_warn_delta=0,
        placeholders_fail=200,
        strict_fail_on_broken=True,
        strict_fail_on_critical_nav_gaps=True,
        orphan_target=0,
    )

    ws_policy = workspace_root / "policies" / "policy_doc_graph.v1.json"
    core_policy = core_root / "policies" / "policy_doc_graph.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    mode = obj.get("mode", defaults.mode)
    if mode not in {"report", "strict"}:
        mode = defaults.mode

    broken_policy = obj.get("broken_ref_policy") if isinstance(obj.get("broken_ref_policy"), dict) else {}
    broken_core = broken_policy.get("core", defaults.broken_core)
    broken_workspace = broken_policy.get("workspace", defaults.broken_workspace)
    if broken_core not in {"fail", "warn"}:
        broken_core = defaults.broken_core
    if broken_workspace not in {"fail", "warn"}:
        broken_workspace = defaults.broken_workspace

    def _list_or_default(val: Any, dflt: list[str]) -> list[str]:
        if isinstance(val, list):
            items = [str(x) for x in val if isinstance(x, str) and x.strip()]
            return items if items else dflt
        return dflt

    workspace_bound_patterns = _list_or_default(obj.get("workspace_bound_patterns"), defaults.workspace_bound_patterns)
    deprecated_patterns = _list_or_default(obj.get("deprecated_patterns"), defaults.deprecated_patterns)
    wrong_path_patterns = _list_or_default(obj.get("wrong_path_patterns"), defaults.wrong_path_patterns)

    max_items = obj.get("max_items") if isinstance(obj.get("max_items"), dict) else {}
    try:
        max_broken = int(max_items.get("broken_refs", defaults.max_broken_refs))
    except Exception:
        max_broken = defaults.max_broken_refs
    try:
        max_orphan = int(max_items.get("orphan_critical", defaults.max_orphan_critical))
    except Exception:
        max_orphan = defaults.max_orphan_critical

    try:
        placeholder_warn_threshold = int(obj.get("placeholder_warn_threshold", defaults.placeholder_warn_threshold))
    except Exception:
        placeholder_warn_threshold = defaults.placeholder_warn_threshold
    placeholders_baseline_enabled = bool(obj.get("placeholders_baseline_enabled", defaults.placeholders_baseline_enabled))
    placeholders_warn_mode = str(obj.get("placeholders_warn_mode", defaults.placeholders_warn_mode))
    if placeholders_warn_mode not in {"delta", "threshold"}:
        placeholders_warn_mode = defaults.placeholders_warn_mode
    try:
        placeholders_warn_delta = int(obj.get("placeholders_warn_delta", defaults.placeholders_warn_delta))
    except Exception:
        placeholders_warn_delta = defaults.placeholders_warn_delta
    try:
        placeholders_fail = int(obj.get("placeholders_fail", defaults.placeholders_fail))
    except Exception:
        placeholders_fail = defaults.placeholders_fail

    strict_fail_on_broken = obj.get("strict_fail_on_broken", defaults.strict_fail_on_broken)
    strict_fail_on_critical_nav_gaps = obj.get(
        "strict_fail_on_critical_nav_gaps", defaults.strict_fail_on_critical_nav_gaps
    )
    orphan_target = obj.get("orphan_target", defaults.orphan_target)
    strict_fail_on_broken = bool(strict_fail_on_broken)
    strict_fail_on_critical_nav_gaps = bool(strict_fail_on_critical_nav_gaps)
    try:
        orphan_target = int(orphan_target)
    except Exception:
        orphan_target = defaults.orphan_target

    return DocGraphPolicy(
        enabled=enabled,
        mode=str(mode),
        broken_core=str(broken_core),
        broken_workspace=str(broken_workspace),
        workspace_bound_patterns=workspace_bound_patterns,
        deprecated_patterns=deprecated_patterns,
        wrong_path_patterns=wrong_path_patterns,
        max_broken_refs=max(0, max_broken),
        max_orphan_critical=max(0, max_orphan),
        placeholder_warn_threshold=max(0, placeholder_warn_threshold),
        placeholders_baseline_enabled=placeholders_baseline_enabled,
        placeholders_warn_mode=placeholders_warn_mode,
        placeholders_warn_delta=max(0, placeholders_warn_delta),
        placeholders_fail=max(0, placeholders_fail),
        strict_fail_on_broken=strict_fail_on_broken,
        strict_fail_on_critical_nav_gaps=strict_fail_on_critical_nav_gaps,
        orphan_target=max(0, orphan_target),
    )


def _iter_files(repo_root: Path, *, suffixes: tuple[str, ...]) -> list[Path]:
    exclude = {".git", ".venv", ".cache", "evidence", "dlq", "dist", "__pycache__"}
    paths: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(repo_root).parts
        if any(part in exclude for part in rel_parts):
            continue
        if path.suffix in suffixes:
            paths.append(path)
    return sorted(paths, key=lambda p: p.as_posix())


def _normalize_ref(ref: str) -> str:
    ref = ref.strip().strip("\"").strip("'")
    ref = ref.split("#", 1)[0].split("?", 1)[0]
    if ref.startswith("./"):
        ref = ref[2:]
    return ref


def _load_placeholders_baseline(workspace_root: Path) -> int | None:
    path = workspace_root / ".cache" / "index" / "placeholders_baseline.v1.json"
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    baseline = obj.get("placeholders_baseline")
    if isinstance(baseline, int) and baseline >= 0:
        return baseline
    return None


def _is_external_ref(ref: str) -> bool:
    return ref.startswith(("http://", "https://", "mailto:"))


def _match_any(patterns: list[str], target: str) -> bool:
    return any(fnmatch.fnmatch(target, pat) for pat in patterns)


def _classify_ref(
    ref: str,
    *,
    repo_root: Path,
    policy: DocGraphPolicy,
) -> tuple[str, str]:
    if _is_external_ref(ref):
        return ("external_pointer", "external")

    if "${" in ref or "}" in ref:
        return ("workspace_bound", "workspace")

    if ref.startswith("${WORKSPACE_ROOT}") or ref.startswith("${EXTERNAL_ROOT}"):
        return ("workspace_bound", "workspace")

    if _match_any(policy.workspace_bound_patterns, ref):
        return ("workspace_bound", "workspace")

    # Deprecation must be policy-driven; avoid hardcoding substring heuristics.
    if _match_any(policy.deprecated_patterns, ref):
        return ("deprecated", "core")

    if _match_any(policy.wrong_path_patterns, ref):
        return ("wrong_path", "core")

    target = repo_root / ref
    if target.exists():
        return ("ok", "core")
    return ("missing_file", "core")


def _is_archive_ref(*, source: str, target_ref: str, repo_root: Path) -> bool:
    if source != "AGENTS.md":
        return False
    target_path = repo_root / target_ref
    if not target_path.exists() or not target_path.is_file():
        return False
    text = _read_text(target_path)
    return _has_banner(text, keywords=("ARCHIVE ONLY",))


def _has_banner(text: str, *, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _roadmap_ambiguities(repo_root: Path) -> list[dict[str, Any]]:
    canonical = repo_root / "docs" / "ROADMAP.md"
    legacy = repo_root / "docs" / "ROADMAP_v2.7_legacy.md"
    if not canonical.exists() or not legacy.exists():
        return []

    canonical_text = _read_text(canonical)
    legacy_text = _read_text(legacy)
    canonical_ok = _has_banner(canonical_text, keywords=("CANONICAL",))
    legacy_ok = _has_banner(legacy_text, keywords=("ARCHIVE", "LEGACY"))
    if canonical_ok and legacy_ok:
        return []

    return [
        {
            "kind": "ROADMAP",
            "paths": ["docs/ROADMAP.md", "docs/ROADMAP_v2.7_legacy.md"],
        }
    ]


def _critical_nav_gaps(
    *,
    repo_root: Path,
    refs_by_source: dict[str, set[str]],
) -> list[str]:
    required = [
        "docs/OPERATIONS/CODEX-UX.md",
        "docs/LAYER-MODEL-LOCK.v1.md",
        "docs/ROADMAP.md",
        "docs/ROADMAP_v2.7_legacy.md",
        "docs/OPERATIONS/repo-layout.md",
        "docs/OPERATIONS/repo-layout.v1.json",
        "docs/OPERATIONS/spec-core.md",
        "docs/OPERATIONS/tags-registry.md",
        "docs/OPERATIONS/SSOT-MAP.md",
        "roadmaps/SSOT/roadmap.v1.json",
        "roadmaps/PROJECTS/README.md",
        "roadmaps/PROJECTS/project-roadmap.template.v1.json",
        "schemas/system-status.schema.json",
        "policies/policy_system_status.v1.json",
        "src/ops/system_status_report.py",
        "src/ops/manage.py",
        "src/ops/roadmap_cli.py",
    ]
    agents_refs = refs_by_source.get("AGENTS.md", set())
    missing: list[str] = []
    for path in required:
        if (repo_root / path).exists() and path not in agents_refs:
            missing.append(path)
    return missing


def _extract_md_refs(text: str) -> list[str]:
    refs: list[str] = []
    md_link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    md_refdef_re = re.compile(r"^\[[^\]]+\]:\s*(\S+)")
    raw_path_re = re.compile(
        r"(?:docs|schemas|policies|roadmaps|packs|capabilities|formats|workflows|registry|orchestrator|src|ci|templates|governor|modules|supply_chain|examples|fixtures|scripts|tenant|project|incubator)/[A-Za-z0-9._{}\\/-]+"
    )
    entrypoint_hint_re = re.compile(r"\b(?:bkz|see|ssot|source of truth)\b", re.IGNORECASE)

    for match in md_link_re.findall(text):
        refs.append(match)
    for line in text.splitlines():
        refdef = md_refdef_re.match(line)
        if refdef:
            refs.append(refdef.group(1))
        if entrypoint_hint_re.search(line):
            refs.extend(raw_path_re.findall(line))
        refs.extend(raw_path_re.findall(line))
    return refs


def _extract_plan_only_placeholders(roadmap_path: Path) -> set[str]:
    if not roadmap_path.exists():
        return set()
    text = _read_text(roadmap_path)
    placeholders: set[str] = set()
    for line in text.splitlines():
        lowered = line.lower()
        if "plan-only" not in lowered and "placeholder" not in lowered:
            continue
        for ref in _extract_md_refs(line):
            norm = _normalize_ref(ref)
            if norm:
                placeholders.add(norm)
    return placeholders


def _extract_json_refs(obj: Any, refs: list[str]) -> None:
    ref_keys = {
        "$ref",
        "schema",
        "schema_ref",
        "policy_ref",
        "manifest_ref",
        "format_ref",
        "capability_ref",
        "implementation_ref",
        "doc_ref",
        "roadmap_path",
        "change_path",
        "format_refs",
        "capability_refs",
    }
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            if key in ref_keys or key.endswith("_ref") or key.endswith("_refs"):
                if isinstance(v, str):
                    refs.append(v)
                elif isinstance(v, list):
                    refs.extend([x for x in v if isinstance(x, str)])
            _extract_json_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            _extract_json_refs(item, refs)


def _extract_roadmap_paths(roadmap_obj: Any) -> list[str]:
    refs: list[str] = []
    milestones = []
    if isinstance(roadmap_obj, dict):
        milestones = roadmap_obj.get("milestones", [])
    if not isinstance(milestones, list):
        return refs

    def _handle_step(step: Any) -> None:
        if not isinstance(step, dict):
            return
        for key in ("path", "pointer_path", "change_path", "roadmap_path"):
            if isinstance(step.get(key), str):
                refs.append(step[key])
        for key in ("paths", "allowed_paths", "required_files"):
            items = step.get(key)
            if isinstance(items, list):
                refs.extend([x for x in items if isinstance(x, str)])

    for ms in milestones:
        if not isinstance(ms, dict):
            continue
        for step in ms.get("steps", []):
            _handle_step(step)
        for step in ms.get("deliverables", []):
            _handle_step(step)
        for step in ms.get("gates", []):
            _handle_step(step)
    return refs


def _critical_paths(repo_root: Path) -> list[str]:
    critical: list[str] = []
    for p in (repo_root / "schemas").rglob("*.schema.json"):
        critical.append(p.relative_to(repo_root).as_posix())
    for p in (repo_root / "schemas").rglob("*.schema.v1.json"):
        critical.append(p.relative_to(repo_root).as_posix())
    for p in (repo_root / "policies").glob("policy_*.v1.json"):
        critical.append(p.relative_to(repo_root).as_posix())
    ssot_dir = repo_root / "roadmaps" / "SSOT"
    if ssot_dir.exists():
        for p in ssot_dir.rglob("*"):
            if p.is_file():
                critical.append(p.relative_to(repo_root).as_posix())
    cap_dir = repo_root / "capabilities"
    if cap_dir.exists():
        for p in cap_dir.rglob("*.json"):
            critical.append(p.relative_to(repo_root).as_posix())
    pack_dir = repo_root / "packs" / "standards"
    if pack_dir.exists():
        for p in pack_dir.rglob("*.json"):
            critical.append(p.relative_to(repo_root).as_posix())
    return sorted(set(critical))


def generate_doc_graph_report(
    *,
    repo_root: Path,
    workspace_root: Path,
    policy: DocGraphPolicy,
) -> dict[str, Any]:
    md_files = _iter_files(repo_root, suffixes=(".md",))
    json_files = _iter_files(repo_root, suffixes=(".json",))

    refs_by_source: dict[str, set[str]] = {}

    for path in md_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        src = path.relative_to(repo_root).as_posix()
        for ref in _extract_md_refs(text):
            refs_by_source.setdefault(src, set()).add(_normalize_ref(ref))

    for path in json_files:
        src = path.relative_to(repo_root).as_posix()
        try:
            obj = _load_json(path)
        except Exception:
            continue
        refs: list[str] = []
        _extract_json_refs(obj, refs)
        for ref in refs:
            refs_by_source.setdefault(src, set()).add(_normalize_ref(ref))
        if path.name.startswith("roadmap.") and path.suffix == ".json":
            roadmap_refs = _extract_roadmap_paths(obj)
            for ref in roadmap_refs:
                refs_by_source.setdefault(src, set()).add(_normalize_ref(ref))

    placeholder_refs = _extract_plan_only_placeholders(repo_root / "docs" / "ROADMAP.md")

    entrypoints = [
        "AGENTS.md",
        "docs/OPERATIONS/CODEX-UX.md",
        "docs/ROADMAP.md",
        "docs/OPERATIONS/repo-layout.md",
        "docs/OPERATIONS/repo-layout.v1.json",
        "docs/LAYER-MODEL-LOCK.v1.md",
        "docs/OPERATIONS/spec-core.md",
        "docs/OPERATIONS/tags-registry.md",
        "roadmaps/SSOT/roadmap.v1.json",
        "roadmaps/PROJECTS/README.md",
        "roadmaps/PROJECTS/project-roadmap.template.v1.json",
        "README.md",
        "schemas/system-status.schema.json",
        "policies/policy_system_status.v1.json",
        "src/ops/system_status_report.py",
    ]
    entrypoints_present = [p for p in entrypoints if (repo_root / p).exists()]

    ref_summary = {
        "missing_file": 0,
        "wrong_path": 0,
        "deprecated": 0,
        "archive_ref": 0,
        "workspace_bound": 0,
        "external_pointer": 0,
        "plan_only_placeholder": 0,
    }
    broken_refs: list[dict[str, str]] = []
    placeholder_items: list[dict[str, str]] = []
    archive_items: list[dict[str, str]] = []
    broken_core = 0
    broken_workspace = 0
    deprecated_refs = 0

    referenced_paths: set[str] = set()
    for src in sorted(refs_by_source.keys()):
        for ref in sorted(refs_by_source[src]):
            if not ref:
                continue
            if _is_archive_ref(source=src, target_ref=ref, repo_root=repo_root):
                ref_summary["archive_ref"] += 1
                archive_items.append({"source": src, "target": ref, "kind": "archive_ref"})
                continue
            if ref in placeholder_refs:
                ref_summary["plan_only_placeholder"] += 1
                placeholder_items.append({"source": src, "target": ref, "kind": "plan_only_placeholder"})
                continue
            kind, scope = _classify_ref(ref, repo_root=repo_root, policy=policy)
            if kind in ref_summary:
                ref_summary[kind] += 1
            if kind in {"missing_file", "wrong_path", "deprecated"}:
                broken_refs.append({"source": src, "target": ref, "kind": kind})
                if kind == "deprecated":
                    deprecated_refs += 1
                elif scope == "core":
                    broken_core += 1
                else:
                    broken_workspace += 1
            if kind == "ok" and not ref.startswith("/") and ref:
                referenced_paths.add(ref)
            if kind == "deprecated" and (repo_root / ref).exists():
                referenced_paths.add(ref)

    broken_refs = sorted(
        broken_refs,
        key=lambda r: (r.get("source", ""), r.get("target", "")),
    )
    if policy.max_broken_refs >= 0:
        broken_refs = broken_refs[: policy.max_broken_refs]
    placeholder_items = sorted(
        placeholder_items,
        key=lambda r: (r.get("source", ""), r.get("target", "")),
    )
    if policy.max_broken_refs >= 0:
        placeholder_items = placeholder_items[: policy.max_broken_refs]
    archive_items = sorted(
        archive_items,
        key=lambda r: (r.get("source", ""), r.get("target", "")),
    )

    critical = _critical_paths(repo_root)
    orphan_critical = []
    for path in critical:
        if path not in referenced_paths:
            orphan_critical.append({"path": path, "reason": "UNREFERENCED_CRITICAL_SSOT"})
    orphan_critical = sorted(orphan_critical, key=lambda r: r.get("path", ""))
    if policy.max_orphan_critical >= 0:
        orphan_critical = orphan_critical[: policy.max_orphan_critical]

    ambiguities = _roadmap_ambiguities(repo_root)
    critical_nav_missing = _critical_nav_gaps(repo_root=repo_root, refs_by_source=refs_by_source)

    placeholders_count = ref_summary["plan_only_placeholder"]
    placeholders_baseline = None
    placeholders_delta = 0
    placeholders_warn_mode = policy.placeholders_warn_mode
    if policy.placeholders_baseline_enabled:
        placeholders_baseline = _load_placeholders_baseline(workspace_root)
        if placeholders_baseline is None:
            placeholders_baseline = placeholders_count
            report_note = "placeholders_baseline_missing=true"
        else:
            report_note = None
        placeholders_delta = max(0, placeholders_count - placeholders_baseline)
    else:
        placeholders_baseline = placeholders_count
        placeholders_delta = 0
        placeholders_warn_mode = "threshold"
        report_note = None

    warn_on_placeholders = False
    if policy.placeholders_baseline_enabled and placeholders_warn_mode == "delta":
        warn_on_placeholders = placeholders_delta > policy.placeholders_warn_delta
    else:
        warn_on_placeholders = placeholders_count > policy.placeholder_warn_threshold

    status = "OK"
    if critical_nav_missing and policy.strict_fail_on_critical_nav_gaps:
        status = "FAIL"
    elif placeholders_count > policy.placeholders_fail:
        status = "FAIL"
    elif policy.mode == "strict" and policy.strict_fail_on_broken and broken_core > 0 and policy.broken_core == "fail":
        status = "FAIL"
    elif broken_core > 0 or broken_workspace > 0:
        status = "WARN"
    elif deprecated_refs > 0 or ambiguities:
        status = "WARN"
    elif len(orphan_critical) > policy.orphan_target:
        status = "WARN"
    elif warn_on_placeholders:
        status = "WARN"

    notes = [f"critical_nav_missing:{path}" for path in critical_nav_missing]
    if report_note:
        notes.append(report_note)

    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "repo_root": str(repo_root),
        "workspace_root": str(workspace_root),
        "status": status,
        "counts": {
            "scanned_files": len(md_files) + len(json_files),
            "reference_count": sum(len(v) for v in refs_by_source.values()),
            "broken_refs": len(broken_refs),
            "orphan_critical": len(orphan_critical),
            "ambiguity": len(ambiguities),
            "ambiguity_count": len(ambiguities),
            "critical_nav_gaps": len(critical_nav_missing),
            "workspace_bound_refs_count": ref_summary["workspace_bound"],
            "external_pointer_refs_count": ref_summary["external_pointer"],
            "placeholder_refs_count": ref_summary["plan_only_placeholder"],
            "archive_refs_count": ref_summary["archive_ref"],
        },
        "placeholders_baseline_enabled": policy.placeholders_baseline_enabled,
        "placeholders_baseline": placeholders_baseline,
        "placeholders_delta": placeholders_delta,
        "placeholders_warn_mode": placeholders_warn_mode,
        "placeholders_warn_delta": policy.placeholders_warn_delta,
        "placeholders_fail": policy.placeholders_fail,
        "ref_summary": ref_summary,
        "broken_refs": broken_refs,
        "top_placeholders": placeholder_items,
        "orphan_critical": orphan_critical,
        "ambiguities": ambiguities,
        "entrypoints": entrypoints_present,
        "notes": notes,
    }
    return report


def write_doc_graph_report(
    *,
    report: dict[str, Any],
    out_json: Path,
    out_md: Path,
) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Doc Graph Report (v1)")
    lines.append("")
    lines.append(f"Generated at: {report.get('generated_at', '')}")
    lines.append(f"Repo root: {report.get('repo_root', '')}")
    lines.append(f"Workspace root: {report.get('workspace_root', '')}")
    lines.append(f"Status: {report.get('status', '')}")
    lines.append("")

    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    lines.append("## Summary")
    lines.append(f"Scanned files: {counts.get('scanned_files', 0)}")
    lines.append(f"References: {counts.get('reference_count', 0)}")
    lines.append(f"Broken refs: {counts.get('broken_refs', 0)}")
    lines.append(f"Archive refs: {counts.get('archive_refs_count', 0)}")
    lines.append(f"Orphan critical: {counts.get('orphan_critical', 0)}")
    lines.append(f"Ambiguity: {counts.get('ambiguity', 0)}")
    lines.append(f"Critical nav gaps: {counts.get('critical_nav_gaps', 0)}")
    lines.append(f"Workspace-bound refs: {counts.get('workspace_bound_refs_count', 0)}")
    lines.append(f"External pointers: {counts.get('external_pointer_refs_count', 0)}")
    lines.append(f"Plan-only placeholders: {counts.get('placeholder_refs_count', 0)}")
    if "placeholders_baseline" in report:
        lines.append(f"Placeholders baseline: {report.get('placeholders_baseline', 0)}")
        lines.append(f"Placeholders delta: {report.get('placeholders_delta', 0)}")
        lines.append(f"Placeholders warn mode: {report.get('placeholders_warn_mode', '')}")
    lines.append("")

    ref_summary = report.get("ref_summary") if isinstance(report.get("ref_summary"), dict) else {}
    lines.append("## Ref summary")
    for key in [
        "missing_file",
        "wrong_path",
        "deprecated",
        "archive_ref",
        "workspace_bound",
        "external_pointer",
        "plan_only_placeholder",
    ]:
        lines.append(f"{key}: {ref_summary.get(key, 0)}")
    lines.append("")

    lines.append("## Broken refs (top 10)")
    broken = report.get("broken_refs") if isinstance(report.get("broken_refs"), list) else []
    for item in broken[:10]:
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('source', '')} -> {item.get('target', '')} ({item.get('kind', '')})")
    lines.append("")

    lines.append("## Orphan critical (top 10)")
    orphans = report.get("orphan_critical") if isinstance(report.get("orphan_critical"), list) else []
    for item in orphans[:10]:
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('path', '')} ({item.get('reason', '')})")
    lines.append("")

    lines.append("## Ambiguities")
    ambiguities = report.get("ambiguities") if isinstance(report.get("ambiguities"), list) else []
    if ambiguities:
        for item in ambiguities:
            if not isinstance(item, dict):
                continue
            paths = item.get("paths", [])
            if isinstance(paths, list):
                lines.append(f"- {item.get('kind', '')}: " + ", ".join(str(p) for p in paths))
    else:
        lines.append("None")
    lines.append("")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_doc_graph(
    *,
    repo_root: Path,
    workspace_root: Path,
    out_json: Path,
    mode: str,
) -> dict[str, Any]:
    policy = _load_policy(repo_root, workspace_root)
    if mode == "strict" and policy.mode != "strict":
        policy = DocGraphPolicy(
            enabled=policy.enabled,
            mode="strict",
            broken_core=policy.broken_core,
            broken_workspace=policy.broken_workspace,
            workspace_bound_patterns=policy.workspace_bound_patterns,
            deprecated_patterns=policy.deprecated_patterns,
            wrong_path_patterns=policy.wrong_path_patterns,
            max_broken_refs=policy.max_broken_refs,
            max_orphan_critical=policy.max_orphan_critical,
            placeholder_warn_threshold=policy.placeholder_warn_threshold,
            placeholders_baseline_enabled=policy.placeholders_baseline_enabled,
            placeholders_warn_mode=policy.placeholders_warn_mode,
            placeholders_warn_delta=policy.placeholders_warn_delta,
            placeholders_fail=policy.placeholders_fail,
            strict_fail_on_broken=policy.strict_fail_on_broken,
            strict_fail_on_critical_nav_gaps=policy.strict_fail_on_critical_nav_gaps,
            orphan_target=policy.orphan_target,
        )
    report = generate_doc_graph_report(repo_root=repo_root, workspace_root=workspace_root, policy=policy)
    out_md = out_json.with_suffix(".v1.md") if out_json.name.endswith(".v1.json") else out_json.with_suffix(".md")
    write_doc_graph_report(report=report, out_json=out_json, out_md=out_md)

    if mode == "strict" and report.get("status") == "FAIL":
        report["status"] = "FAIL"
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Doc graph scanner (deterministic, offline).")
    parser.add_argument("--workspace-root", required=True, help="Workspace root path.")
    parser.add_argument("--mode", default="report", choices=["report", "strict"])
    parser.add_argument("--out", default=".cache/reports/doc_graph_report.v1.json")
    args = parser.parse_args()

    repo_root = _repo_root()
    ws_path = Path(str(args.workspace_root))
    if not ws_path.is_absolute():
        ws_path = (repo_root / ws_path).resolve()
    out_arg = str(args.out)
    if args.mode == "strict" and out_arg == ".cache/reports/doc_graph_report.v1.json":
        out_arg = ".cache/reports/doc_graph_report.strict.v1.json"
    out_path = Path(out_arg)
    if not out_path.is_absolute():
        out_path = (ws_path / out_path).resolve()

    report = run_doc_graph(
        repo_root=repo_root,
        workspace_root=ws_path,
        out_json=out_path,
        mode=str(args.mode),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if str(args.mode) == "strict" and report.get("status") == "FAIL":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
