from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


def _resolve_workspace_path(workspace_root: Path, rel: str) -> Path | None:
    path = (workspace_root / rel).resolve()
    return path if _is_within_root(path, workspace_root) else None


@dataclass(frozen=True)
class SystemStatusPolicy:
    enabled: bool
    out_json: str
    out_md: str
    max_actions: int
    max_suggestions: int
    include_repo_hygiene_suggestions: bool
    on_fail: str


def _load_policy(core_root: Path, workspace_root: Path) -> SystemStatusPolicy:
    defaults = SystemStatusPolicy(
        enabled=True,
        out_json=".cache/reports/system_status.v1.json",
        out_md=".cache/reports/system_status.v1.md",
        max_actions=10,
        max_suggestions=10,
        include_repo_hygiene_suggestions=False,
        on_fail="warn",
    )

    ws_policy = workspace_root / "policies" / "policy_system_status.v1.json"
    core_policy = core_root / "policies" / "policy_system_status.v1.json"
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
    out_json = obj.get("out_json", defaults.out_json)
    if not isinstance(out_json, str) or not out_json.strip():
        out_json = defaults.out_json

    out_md = obj.get("out_md", defaults.out_md)
    if not isinstance(out_md, str) or not out_md.strip():
        out_md = defaults.out_md

    def _int_or_default(val: Any, dflt: int) -> int:
        try:
            return max(0, int(val))
        except Exception:
            return dflt

    max_actions = _int_or_default(obj.get("max_actions", defaults.max_actions), defaults.max_actions)
    max_suggestions = _int_or_default(obj.get("max_suggestions", defaults.max_suggestions), defaults.max_suggestions)

    include_repo_hygiene_suggestions = bool(
        obj.get("include_repo_hygiene_suggestions", defaults.include_repo_hygiene_suggestions)
    )

    on_fail = obj.get("on_fail", defaults.on_fail)
    if on_fail not in {"warn", "block"}:
        on_fail = defaults.on_fail

    return SystemStatusPolicy(
        enabled=enabled,
        out_json=str(out_json),
        out_md=str(out_md),
        max_actions=max_actions,
        max_suggestions=max_suggestions,
        include_repo_hygiene_suggestions=include_repo_hygiene_suggestions,
        on_fail=str(on_fail),
    )


def _validate_schema(core_root: Path, obj: dict[str, Any]) -> list[str]:
    schema_path = core_root / "schemas" / "system-status.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING"]
    try:
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(obj)
        return []
    except Exception as e:
        return [str(e)[:200]]


def _iso_core_status(workspace_root: Path) -> tuple[str, list[str], list[str]]:
    base = workspace_root / "tenant" / "TENANT-DEFAULT"
    names = ["context.v1.md", "stakeholders.v1.md", "scope.v1.md", "criteria.v1.md"]
    paths = [str(Path("tenant") / "TENANT-DEFAULT" / n) for n in names]
    missing = [p for p, n in zip(paths, names) if not (base / n).exists()]
    status = "OK" if not missing else "WARN"
    return (status, missing, paths)


def _catalog_status(workspace_root: Path) -> tuple[str, list[str]]:
    path = workspace_root / ".cache" / "index" / "catalog.v1.json"
    if not path.exists():
        return ("WARN", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [])
    packs = obj.get("packs") if isinstance(obj, dict) else None
    ids: list[str] = []
    if isinstance(packs, list):
        for p in packs:
            if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
                ids.append(p["pack_id"])
    ids = sorted(set(ids))
    return ("OK", ids)

def _pack_index_status(workspace_root: Path) -> tuple[str, list[str], int, int, str, str, list[str], str]:
    path = workspace_root / ".cache" / "index" / "pack_capability_index.v1.json"
    rel_path = str(Path(".cache") / "index" / "pack_capability_index.v1.json")
    if not path.exists():
        return ("WARN", [], 0, 0, rel_path, "", ["missing"], "")
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [], 0, 0, rel_path, "", ["invalid_json"], "")
    packs = obj.get("packs") if isinstance(obj, dict) else None
    pack_ids: list[str] = []
    if isinstance(packs, list):
        for p in packs:
            if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
                pack_ids.append(p["pack_id"])
    pack_ids = sorted(set(pack_ids))
    hard_conflicts = obj.get("hard_conflicts") if isinstance(obj, dict) else None
    soft_conflicts = obj.get("soft_conflicts") if isinstance(obj, dict) else None
    hard_count = len(hard_conflicts) if isinstance(hard_conflicts, list) else 0
    soft_count = len(soft_conflicts) if isinstance(soft_conflicts, list) else 0
    hashes = obj.get("hashes") if isinstance(obj, dict) else None
    index_hash = hashes.get("index_sha256") if isinstance(hashes, dict) else ""
    status = "OK"
    if hard_count:
        status = "FAIL"
    elif soft_count:
        status = "WARN"
    return (status, pack_ids, hard_count, soft_count, rel_path, str(index_hash), [], "")


def _pack_validation_report(workspace_root: Path) -> tuple[str | None, int, int, str, list[str]]:
    path = workspace_root / ".cache" / "index" / "pack_validation_report.json"
    rel_path = str(Path(".cache") / "index" / "pack_validation_report.json")
    if not path.exists():
        return (None, 0, 0, "", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", 0, 0, rel_path, ["invalid_pack_validation_report"])
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"OK", "WARN", "FAIL"}:
        status = "WARN"
    hard_conflicts = obj.get("hard_conflicts") if isinstance(obj, dict) else None
    soft_conflicts = obj.get("soft_conflicts") if isinstance(obj, dict) else None
    hard_count = len(hard_conflicts) if isinstance(hard_conflicts, list) else 0
    soft_count = len(soft_conflicts) if isinstance(soft_conflicts, list) else 0
    warnings = obj.get("warnings") if isinstance(obj, dict) else None
    notes = [str(w) for w in warnings if isinstance(w, str)] if isinstance(warnings, list) else []
    return (str(status), hard_count, soft_count, rel_path, notes)


def _pack_selection_trace(workspace_root: Path) -> tuple[list[str], str, list[str]]:
    path = workspace_root / ".cache" / "index" / "pack_selection_trace.v1.json"
    rel_path = str(Path(".cache") / "index" / "pack_selection_trace.v1.json")
    if not path.exists():
        return ([], rel_path, ["missing_selection_trace"])
    try:
        obj = _load_json(path)
    except Exception:
        return ([], rel_path, ["invalid_selection_trace"])
    selected = obj.get("selected_pack_ids") if isinstance(obj, dict) else None
    selected_ids = [x for x in selected if isinstance(x, str)] if isinstance(selected, list) else []
    return (sorted(set(selected_ids)), rel_path, [])


def _doc_graph_section(core_root: Path, workspace_root: Path, *, allow_write: bool) -> dict[str, Any] | None:
    report_path = workspace_root / ".cache" / "reports" / "doc_graph_report.v1.json"
    rel_path = str(Path(".cache") / "reports" / "doc_graph_report.v1.json")

    report_obj: dict[str, Any] | None = None
    if report_path.exists():
        try:
            report_obj = _load_json(report_path)
        except Exception:
            report_obj = None
    elif allow_write:
        try:
            from src.ops.doc_graph import run_doc_graph

            report_obj = run_doc_graph(
                repo_root=core_root,
                workspace_root=workspace_root,
                out_json=report_path,
                mode="report",
            )
        except Exception:
            report_obj = None
    else:
        try:
            from src.ops.doc_graph import generate_doc_graph_report, _load_policy

            policy = _load_policy(core_root, workspace_root)
            report_obj = generate_doc_graph_report(
                repo_root=core_root,
                workspace_root=workspace_root,
                policy=policy,
            )
        except Exception:
            report_obj = None

    if not isinstance(report_obj, dict):
        return None

    counts = report_obj.get("counts") if isinstance(report_obj.get("counts"), dict) else {}
    broken_count = int(counts.get("broken_refs", 0))
    orphan_count = int(counts.get("orphan_critical", 0))
    ambiguity_count = int(counts.get("ambiguity", counts.get("ambiguity_count", 0)))
    critical_nav_gaps = int(counts.get("critical_nav_gaps", 0))
    placeholder_count = int(counts.get("placeholder_refs_count", 0))
    status = report_obj.get("status") if isinstance(report_obj.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "FAIL"}:
        status = "WARN"

    broken = report_obj.get("broken_refs") if isinstance(report_obj.get("broken_refs"), list) else []
    orphans = report_obj.get("orphan_critical") if isinstance(report_obj.get("orphan_critical"), list) else []

    top_broken: list[dict[str, Any]] = []
    for item in broken[:10]:
        if isinstance(item, dict):
            top_broken.append(
                {
                    "source": str(item.get("source", "")),
                    "target": str(item.get("target", "")),
                    "kind": str(item.get("kind", "")),
                }
            )

    top_orphan: list[dict[str, Any]] = []
    for item in orphans[:10]:
        if isinstance(item, dict):
            top_orphan.append(
                {
                    "path": str(item.get("path", "")),
                    "reason": str(item.get("reason", "")),
                }
            )

    return {
        "status": status,
        "report_path": rel_path,
        "broken_refs": broken_count,
        "placeholder_refs_count": placeholder_count,
        "orphan_critical": orphan_count,
        "ambiguity": ambiguity_count,
        "critical_nav_gaps": critical_nav_gaps,
        "top_broken": top_broken,
        "top_orphan": top_orphan,
        "notes": [],
    }


def _formats_status(workspace_root: Path) -> tuple[str, list[str]]:
    path = workspace_root / ".cache" / "index" / "formats.v1.json"
    if not path.exists():
        return ("WARN", [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", [])
    formats = obj.get("formats") if isinstance(obj, dict) else None
    ids: list[str] = []
    if isinstance(formats, list):
        for f in formats:
            if isinstance(f, dict) and isinstance(f.get("id"), str):
                ids.append(f["id"])
    ids = sorted(set(ids))
    return ("OK", ids)


def _session_status(workspace_root: Path) -> tuple[str, dict[str, Any]]:
    path = workspace_root / ".cache" / "sessions" / "default" / "session_context.v1.json"
    if not path.exists():
        return (
            "WARN",
            {"session_id": "default", "ttl_seconds": 0, "expires_at": "", "session_context_hash": ""},
        )
    try:
        obj = _load_json(path)
    except Exception:
        return (
            "WARN",
            {"session_id": "default", "ttl_seconds": 0, "expires_at": "", "session_context_hash": ""},
        )

    ttl = obj.get("ttl_seconds") if isinstance(obj, dict) else None
    expires_at = obj.get("expires_at") if isinstance(obj, dict) else None
    hashes = obj.get("hashes") if isinstance(obj, dict) else None
    sha = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None

    ttl_i = int(ttl) if isinstance(ttl, int) else 0
    expires_s = str(expires_at) if isinstance(expires_at, str) else ""
    sha_s = str(sha) if isinstance(sha, str) else ""
    return ("OK", {"session_id": "default", "ttl_seconds": ttl_i, "expires_at": expires_s, "session_context_hash": sha_s})


def _quality_status(workspace_root: Path) -> tuple[str, str]:
    path = workspace_root / ".cache" / "index" / "quality_gate_report.v1.json"
    if not path.exists():
        return ("WARN", "missing")
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", "invalid_json")
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"OK", "WARN", "FAIL"}:
        status = "WARN"
    summary = f"status={status}"
    return (str(status), summary)


def _benchmark_status(workspace_root: Path) -> dict[str, Any]:
    catalog_path = workspace_root / ".cache" / "index" / "north_star_catalog.v1.json"
    assessment_path = workspace_root / ".cache" / "index" / "assessment.v1.json"
    scorecard_path = workspace_root / ".cache" / "reports" / "benchmark_scorecard.v1.json"
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    rel_catalog = str(Path(".cache") / "index" / "north_star_catalog.v1.json")
    rel_assessment = str(Path(".cache") / "index" / "assessment.v1.json")
    rel_scorecard = str(Path(".cache") / "reports" / "benchmark_scorecard.v1.json")
    rel_gap = str(Path(".cache") / "index" / "gap_register.v1.json")

    status = "OK"
    notes: list[str] = []
    controls_count = 0
    metrics_count = 0
    gaps_count = 0
    maturity_avg = 0.0
    gaps_by_severity = {"low": 0, "medium": 0, "high": 0}
    top_next_actions: list[dict[str, str]] = []

    if not catalog_path.exists():
        status = "WARN"
        notes.append("missing_north_star_catalog")
    else:
        try:
            obj = _load_json(catalog_path)
            controls = obj.get("controls") if isinstance(obj, dict) else None
            metrics = obj.get("metrics") if isinstance(obj, dict) else None
            controls_count = len(controls) if isinstance(controls, list) else 0
            metrics_count = len(metrics) if isinstance(metrics, list) else 0
        except Exception:
            status = "FAIL"
            notes.append("invalid_north_star_catalog")

    if not assessment_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_assessment")

    if not scorecard_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_scorecard")

    gap_list: list[dict[str, Any]] = []
    if not gap_path.exists():
        status = "WARN" if status != "FAIL" else status
        notes.append("missing_gap_register")
    else:
        try:
            obj = _load_json(gap_path)
            gaps = obj.get("gaps") if isinstance(obj, dict) else None
            gaps_count = len(gaps) if isinstance(gaps, list) else 0
            if isinstance(gaps, list):
                for g in gaps:
                    if isinstance(g, dict):
                        gap_list.append(g)
        except Exception:
            status = "FAIL"
            notes.append("invalid_gap_register")

    total_items = controls_count + metrics_count
    if total_items > 0:
        maturity_avg = max(0.0, 1.0 - (gaps_count / float(total_items)))
    else:
        notes.append("no_controls_or_metrics")

    def _priority(value: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(value, 1)

    def _effort_priority(value: str) -> int:
        return {"low": 0, "medium": 1, "high": 2}.get(value, 1)

    actions: list[tuple[int, int, int, str, dict[str, str]]] = []
    for g in gap_list:
        gap_id = g.get("id") if isinstance(g.get("id"), str) else ""
        severity = g.get("severity") if isinstance(g.get("severity"), str) else "medium"
        risk_class = g.get("risk_class") if isinstance(g.get("risk_class"), str) else severity
        effort = g.get("effort") if isinstance(g.get("effort"), str) else "medium"
        if severity in gaps_by_severity:
            gaps_by_severity[severity] += 1
        else:
            gaps_by_severity["medium"] += 1
        actions.append(
            (
                _priority(severity),
                _priority(risk_class),
                _effort_priority(effort),
                gap_id,
                {"gap_id": gap_id, "severity": severity, "risk_class": risk_class, "effort": effort},
            )
        )

    actions.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    top_next_actions = [a[4] for a in actions[:5] if a[4].get("gap_id")]

    return {
        "status": status,
        "controls_count": controls_count,
        "metrics_count": metrics_count,
        "gaps_count": gaps_count,
        "maturity_avg": round(maturity_avg, 4),
        "gaps_by_severity": gaps_by_severity,
        "top_next_actions": top_next_actions,
        "catalog_path": rel_catalog,
        "assessment_path": rel_assessment,
        "scorecard_path": rel_scorecard,
        "gap_register_path": rel_gap,
        "notes": notes,
    }


def _spec_core_status(core_root: Path) -> tuple[str, list[str], list[str], list[str]]:
    required_paths = [
        "schemas/spec-core.schema.json",
        "schemas/spec-capability.schema.json",
    ]
    example_paths = ["capabilities/CAP-PR-PACKAGER.v1.json"]
    missing: list[str] = []
    notes: list[str] = []

    for rel in required_paths:
        if not (core_root / rel).exists():
            missing.append(rel)
    for rel in example_paths:
        if not (core_root / rel).exists():
            missing.append(rel)

    # Lightweight validation: ensure capability example declares meta.kind == CAPABILITY.
    example_path = core_root / "capabilities" / "CAP-PR-PACKAGER.v1.json"
    if example_path.exists():
        try:
            obj = _load_json(example_path)
            meta = obj.get("meta") if isinstance(obj, dict) else None
            kind = meta.get("kind") if isinstance(meta, dict) else None
            if kind != "CAPABILITY":
                notes.append("CAPABILITY_KIND_MISMATCH")
        except Exception:
            notes.append("CAPABILITY_EXAMPLE_INVALID_JSON")

    status = "OK" if not missing and not notes else "WARN"
    return (status, required_paths, example_paths, notes)


def _harvest_status(workspace_root: Path) -> tuple[str, int, list[str]]:
    path = workspace_root / ".cache" / "learning" / "public_candidates.v1.json"
    if not path.exists():
        return ("WARN", 0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", 0, [])
    candidates = obj.get("candidates") if isinstance(obj, dict) else None
    if not isinstance(candidates, list):
        return ("FAIL", 0, [])
    kinds_set: set[str] = set()
    for c in candidates:
        if isinstance(c, dict):
            k = c.get("kind")
            if isinstance(k, str):
                kinds_set.add(k)
    kinds = sorted(kinds_set)
    return ("OK", len(candidates), kinds)


def _advisor_status(workspace_root: Path, max_suggestions: int) -> tuple[str, int, list[str]]:
    path = workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
    if not path.exists():
        return ("WARN", 0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", 0, [])
    suggestions = obj.get("suggestions") if isinstance(obj, dict) else None
    if not isinstance(suggestions, list):
        return ("FAIL", 0, [])
    kinds_set: set[str] = set()
    for s in suggestions[: max_suggestions if max_suggestions > 0 else len(suggestions)]:
        if isinstance(s, dict):
            k = s.get("kind")
            if isinstance(k, str):
                kinds_set.add(k)
    kinds = sorted(kinds_set)
    return ("OK", len(suggestions), kinds)


def _pack_advisor_status(workspace_root: Path, max_suggestions: int) -> tuple[str, int, list[str], list[str]]:
    path = workspace_root / ".cache" / "learning" / "pack_advisor_suggestions.v1.json"
    if not path.exists():
        return ("WARN", 0, [], [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("FAIL", 0, [], [])
    suggestions = obj.get("suggestions") if isinstance(obj, dict) else None
    if not isinstance(suggestions, list):
        return ("FAIL", 0, [], [])
    kinds_set: set[str] = set()
    pack_ids_set: set[str] = set()
    limit = max_suggestions if max_suggestions > 0 else len(suggestions)
    for s in suggestions[:limit]:
        if isinstance(s, dict):
            k = s.get("kind")
            pid = s.get("pack_id")
            if isinstance(k, str):
                kinds_set.add(k)
            if isinstance(pid, str):
                pack_ids_set.add(pid)
    return ("OK", len(suggestions), sorted(kinds_set), sorted(pack_ids_set))


def _readiness_status(workspace_root: Path) -> tuple[str, int, int]:
    path = workspace_root / ".cache" / "ops" / "autopilot_readiness.v1.json"
    if not path.exists():
        return ("NOT_READY", 1, 0)
    try:
        obj = _load_json(path)
    except Exception:
        return ("NOT_READY", 1, 0)
    status = obj.get("status") if isinstance(obj, dict) else None
    if status not in {"READY", "NOT_READY"}:
        status = "NOT_READY"
    checks = obj.get("checks") if isinstance(obj, dict) else None
    fails = len([c for c in checks if isinstance(c, dict) and c.get("status") == "FAIL"]) if isinstance(checks, list) else 0
    warns = len([c for c in checks if isinstance(c, dict) and c.get("status") == "WARN"]) if isinstance(checks, list) else 0
    return (str(status), int(fails), int(warns))


def _actions_status(workspace_root: Path, max_actions: int) -> tuple[str, int, list[dict[str, Any]]]:
    path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    if not path.exists():
        return ("OK", 0, [])
    try:
        obj = _load_json(path)
    except Exception:
        return ("WARN", 0, [])
    actions = obj.get("actions") if isinstance(obj, dict) else None
    if not isinstance(actions, list):
        return ("WARN", 0, [])
    unresolved = [a for a in actions if isinstance(a, dict) and a.get("resolved") is not True]
    unresolved.sort(key=lambda a: str(a.get("action_id") or ""))
    top = []
    for a in unresolved[: max_actions if max_actions > 0 else len(unresolved)]:
        top.append(
            {
                "kind": a.get("kind"),
                "milestone_hint": a.get("milestone_hint") or a.get("target_milestone") or "",
                "severity": a.get("severity") or "",
                "message": a.get("message") or "",
                "resolved": bool(a.get("resolved") is True),
            }
        )
    status = "OK" if not unresolved else "WARN"
    return (status, len(unresolved), top)


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


def _git_status_lines(core_root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=core_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _find_core_dirty_report(core_root: Path, workspace_root: Path) -> tuple[list[str] | None, Path | None]:
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
        report_path = base / "core_dirty_files.json"
        if not report_path.exists():
            continue
        try:
            obj = _load_json(report_path)
        except Exception:
            continue
        if isinstance(obj, list):
            return (obj, report_path)
    return (None, None)


def _core_integrity_section(core_root: Path, workspace_root: Path) -> dict[str, Any]:
    report, report_path = _find_core_dirty_report(core_root, workspace_root)
    if report_path is not None:
        dirty_lines = [str(x) for x in report if isinstance(x, str) and str(x).strip()]
        rel = report_path.relative_to(core_root).as_posix()
        status = "OK" if not dirty_lines else "FAIL"
        return {
            "status": status,
            "git_clean": not dirty_lines,
            "dirty_files_count": len(dirty_lines),
            "notes": [f"report_path={rel}"],
        }

    lines = _git_status_lines(core_root)
    if lines is None:
        return {
            "status": "WARN",
            "git_clean": False,
            "dirty_files_count": 0,
            "notes": ["git_unavailable"],
        }
    if lines:
        return {
            "status": "FAIL",
            "git_clean": False,
            "dirty_files_count": len(lines),
            "notes": ["git_dirty"],
        }
    return {
        "status": "OK",
        "git_clean": True,
        "dirty_files_count": 0,
        "notes": [],
    }


def _core_lock_section(core_root: Path, workspace_root: Path) -> dict[str, Any]:
    policy_path = workspace_root / "policies" / "policy_core_immutability.v1.json"
    if not policy_path.exists():
        policy_path = core_root / "policies" / "policy_core_immutability.v1.json"
    obj: dict[str, Any] = {}
    if policy_path.exists():
        try:
            loaded = _load_json(policy_path)
            if isinstance(loaded, dict):
                obj = loaded
        except Exception:
            obj = {}
    enabled = bool(obj.get("enabled", True))
    default_mode = str(obj.get("default_mode", "locked"))
    allow = obj.get("allow_core_writes_only_when", {}) if isinstance(obj.get("allow_core_writes_only_when"), dict) else {}
    env_var = str(allow.get("env_var", "CORE_UNLOCK"))
    env_value = str(allow.get("env_value", "1"))
    core_unlock_requested = str(os.environ.get(env_var, "")).strip() == env_value
    core_unlock_allowed = enabled and default_mode == "locked" and core_unlock_requested
    actions_path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    blocked: list[dict[str, Any]] = []
    if actions_path.exists():
        try:
            obj = _load_json(actions_path)
        except Exception:
            obj = None
        actions = obj.get("actions") if isinstance(obj, dict) else None
        if isinstance(actions, list):
            blocked = [
                a
                for a in actions
                if isinstance(a, dict) and str(a.get("kind") or "") == "CORE_TOUCHED" and not a.get("resolved")
            ]
    status = "WARN" if (not enabled or core_unlock_requested) else "OK"
    return {
        "status": status,
        "enabled": bool(enabled),
        "core_unlock_allowed": bool(core_unlock_allowed),
        "last_blocked_attempts": len(blocked),
    }


def _project_boundary_section(workspace_root: Path) -> dict[str, Any]:
    project_root = workspace_root / "project" / "default"
    manifest = project_root / "project.manifest.v1.json"
    notes: list[str] = []
    if not project_root.exists():
        notes.append("project_root_missing")
    if not manifest.exists():
        notes.append("manifest_missing")
    status = "OK" if manifest.exists() else "WARN"
    return {
        "status": status,
        "project_root": _rel_to_workspace(project_root, workspace_root),
        "manifest_present": bool(manifest.exists()),
        "notes": notes,
    }


def _load_project_manifests(core_root: Path) -> list[dict[str, Any]]:
    projects_root = core_root / "roadmaps" / "PROJECTS"
    if not projects_root.exists():
        return []
    manifests = sorted(projects_root.rglob("project.manifest.v1.json"))
    results: list[dict[str, Any]] = []
    for path in manifests:
        rel = path.relative_to(core_root).as_posix()
        data: dict[str, Any] = {}
        try:
            obj = _load_json(path)
            if isinstance(obj, dict):
                data = obj
        except Exception:
            data = {}
        project_id = data.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            project_id = path.parent.name
        results.append(
            {
                "project_id": str(project_id),
                "title": data.get("title"),
                "version": data.get("version"),
                "manifest_path": rel,
            }
        )
    results.sort(key=lambda x: str(x.get("project_id") or ""))
    return results


def _project_focus(bench_status: str, actions_top: list[dict[str, Any]]) -> str:
    if bench_status != "OK":
        return "M10_CLOSEOUT"
    for a in actions_top:
        if isinstance(a, dict) and str(a.get("kind") or "") == "SCRIPT_BUDGET":
            return "PRJ-M0-MAINTAINABILITY"
    return "PRJ-KERNEL-API"


def _projects_section(
    core_root: Path,
    workspace_root: Path,
    *,
    bench_status: str,
    actions_top: list[dict[str, Any]],
    actions_count: int,
) -> dict[str, Any]:
    notes: list[str] = []
    projects = _load_project_manifests(core_root)
    active_projects = [p.get("project_id") for p in projects if isinstance(p.get("project_id"), str)]
    active_projects = [str(x) for x in active_projects if x]
    active_projects.sort()

    top_debts: list[dict[str, Any]] = []
    for a in actions_top:
        if not isinstance(a, dict):
            continue
        top_debts.append(
            {
                "kind": str(a.get("kind") or ""),
                "milestone_hint": str(a.get("milestone_hint") or ""),
                "severity": str(a.get("severity") or ""),
                "message": str(a.get("message") or ""),
            }
        )

    next_focus = _project_focus(bench_status, actions_top)

    report_path = workspace_root / ".cache" / "reports" / "portfolio_status.v1.json"
    if report_path.exists():
        try:
            obj = _load_json(report_path)
        except Exception:
            obj = {}
        if isinstance(obj, dict):
            rep_active = obj.get("active_projects")
            if isinstance(rep_active, list) and all(isinstance(x, str) for x in rep_active):
                active_projects = sorted(rep_active)
            rep_debts = obj.get("top_project_debts")
            if isinstance(rep_debts, list):
                top_debts = [
                    {
                        "kind": str(d.get("kind") or ""),
                        "milestone_hint": str(d.get("milestone_hint") or ""),
                        "severity": str(d.get("severity") or ""),
                        "message": str(d.get("message") or ""),
                    }
                    for d in rep_debts
                    if isinstance(d, dict)
                ]
            rep_focus = obj.get("next_project_focus")
            if isinstance(rep_focus, str) and rep_focus:
                next_focus = rep_focus
            rep_notes = obj.get("notes")
            if isinstance(rep_notes, list):
                notes = [str(n) for n in rep_notes if isinstance(n, str)]
    else:
        notes.append("portfolio_status_missing")

    projects_count = len(active_projects) if active_projects else len(projects)
    status = "OK" if projects_count > 0 and actions_count == 0 else "WARN"
    return {
        "status": status,
        "projects_count": projects_count,
        "active_projects": active_projects,
        "top_project_debts": top_debts,
        "next_project_focus": next_focus,
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


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except Exception:
        return str(path)


def _repo_hygiene_section(
    *,
    core_root: Path,
    workspace_root: Path,
    include_suggestions: bool,
    allow_write: bool,
) -> dict[str, Any] | None:
    report_path = workspace_root / ".cache" / "repo_hygiene" / "report.json"
    report_obj: dict[str, Any] | None = None
    notes: list[str] = []

    if include_suggestions and allow_write:
        from src.ops.repo_hygiene import run_repo_hygiene

        report_obj = run_repo_hygiene(
            repo_root=core_root,
            layout_path=core_root / "docs" / "OPERATIONS" / "repo-layout.v1.json",
            out_path=report_path,
            mode="suggest",
        )
        notes.append("CHG_DRAFTS_ENABLED")
    elif report_path.exists():
        try:
            obj = _load_json(report_path)
            report_obj = obj if isinstance(obj, dict) else None
        except Exception:
            report_obj = None
            notes.append("REPORT_INVALID_JSON")
    else:
        if include_suggestions and not allow_write:
            notes.append("SUGGESTIONS_DISABLED_DRY_RUN")
        if allow_write:
            from src.ops.repo_hygiene import run_repo_hygiene

            report_obj = run_repo_hygiene(
                repo_root=core_root,
                layout_path=core_root / "docs" / "OPERATIONS" / "repo-layout.v1.json",
                out_path=report_path,
                mode="report",
            )
        else:
            from src.ops.repo_hygiene import run_repo_hygiene

            report_obj = run_repo_hygiene(
                repo_root=core_root,
                layout_path=core_root / "docs" / "OPERATIONS" / "repo-layout.v1.json",
                out_path=None,
                mode="report",
            )
            notes.append("REPORT_NOT_WRITTEN_DRY_RUN")

    if not isinstance(report_obj, dict):
        return None

    summary = report_obj.get("summary") if isinstance(report_obj.get("summary"), dict) else {}
    findings = report_obj.get("findings") if isinstance(report_obj.get("findings"), list) else []
    top_findings: list[dict[str, str]] = []
    for f in findings[:5]:
        if not isinstance(f, dict):
            continue
        top_findings.append(
            {
                "kind": str(f.get("kind") or ""),
                "path": str(f.get("path") or ""),
                "severity": str(f.get("severity") or ""),
            }
        )

    status = report_obj.get("status") if isinstance(report_obj.get("status"), str) else "WARN"
    report_rel = _rel_to_workspace(report_path, workspace_root)

    return {
        "status": status if status in {"OK", "WARN"} else "WARN",
        "report_path": report_rel,
        "unexpected_top_level_dirs": int(summary.get("unexpected_top_level_dirs", 0)),
        "tracked_generated_files": int(summary.get("tracked_generated_files", 0)),
        "top_findings": top_findings,
        "notes": notes,
    }


def build_system_status(
    *,
    workspace_root: Path,
    core_root: Path,
    policy: SystemStatusPolicy,
    dry_run: bool,
) -> dict[str, Any]:
    iso_status, iso_missing, iso_paths = _iso_core_status(workspace_root)
    spec_status, spec_paths, spec_examples, spec_notes = _spec_core_status(core_root)
    core_integrity = _core_integrity_section(core_root, workspace_root)
    core_lock = _core_lock_section(core_root, workspace_root)
    project_boundary = _project_boundary_section(workspace_root)
    cat_status, pack_ids = _catalog_status(workspace_root)
    pack_status, pack_index_ids, hard_conflicts_count, soft_conflicts_count, pack_index_path, pack_index_hash, pack_notes, pack_report_path = _pack_index_status(workspace_root)
    pack_val_status, pack_val_hard, pack_val_soft, pack_val_path, pack_val_notes = _pack_validation_report(workspace_root)
    selected_pack_ids, selection_trace_path, selection_notes = _pack_selection_trace(workspace_root)
    fmt_status, format_ids = _formats_status(workspace_root)
    sess_status, sess_details = _session_status(workspace_root)
    qual_status, qual_summary = _quality_status(workspace_root)
    bench = _benchmark_status(workspace_root)
    bench_status = str(bench.get("status") or "WARN")
    harvest_status, candidates_count, harvest_kinds = _harvest_status(workspace_root)
    adv_status, suggestions_count, adv_kinds = _advisor_status(workspace_root, policy.max_suggestions)
    pack_adv_status, pack_adv_count, pack_adv_kinds, pack_adv_pack_ids = _pack_advisor_status(
        workspace_root, policy.max_suggestions
    )
    read_status, read_fails, read_warns = _readiness_status(workspace_root)
    act_status, act_count, act_top = _actions_status(workspace_root, policy.max_actions)
    projects_section = _projects_section(
        core_root,
        workspace_root,
        bench_status=bench_status,
        actions_top=act_top,
        actions_count=int(act_count),
    )
    auto_heal = _auto_heal_section(core_root, workspace_root)
    repo_hygiene = _repo_hygiene_section(
        core_root=core_root,
        workspace_root=workspace_root,
        include_suggestions=policy.include_repo_hygiene_suggestions,
        allow_write=not dry_run,
    )
    doc_graph = _doc_graph_section(core_root, workspace_root, allow_write=not dry_run)

    overall = "OK"
    if pack_val_status in {"OK", "WARN", "FAIL"}:
        pack_status = str(pack_val_status)
        hard_conflicts_count = int(pack_val_hard)
        soft_conflicts_count = int(pack_val_soft)
        pack_report_path = pack_val_path
        pack_notes = sorted(set(pack_notes + pack_val_notes))

    section_statuses = [
        iso_status,
        spec_status,
        str(core_integrity.get("status") or "WARN"),
        str(core_lock.get("status") or "WARN"),
        str(projects_section.get("status") or "WARN"),
        cat_status,
        pack_status,
        fmt_status,
        sess_status,
        qual_status,
        bench_status,
        harvest_status,
        adv_status,
        pack_adv_status,
        act_status,
    ]
    section_statuses.append(str(project_boundary.get("status") or "WARN"))
    if isinstance(auto_heal, dict):
        section_statuses.append(str(auto_heal.get("status") or "WARN"))
    if isinstance(repo_hygiene, dict):
        section_statuses.append(str(repo_hygiene.get("status") or "WARN"))
    if isinstance(doc_graph, dict):
        section_statuses.append(str(doc_graph.get("status") or "WARN"))
    if read_status == "NOT_READY" or any(s == "FAIL" for s in section_statuses):
        overall = "NOT_READY"
    elif any(s == "WARN" for s in section_statuses) or read_warns > 0:
        overall = "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "overall_status": overall,
        "sections": {
            "iso_core": {
                "status": iso_status,
                "missing": iso_missing,
                "paths": iso_paths,
            },
            "spec_core": {
                "status": spec_status,
                "paths": spec_paths,
                "examples": spec_examples,
                "notes": spec_notes,
            },
            "core_integrity": core_integrity,
            "core_lock": core_lock,
            "project_boundary": project_boundary,
            "projects": projects_section,
            "catalog": {
                "status": cat_status,
                "packs_found": len(pack_ids),
                "pack_ids": pack_ids,
            },
            "packs": {
                "status": pack_status,
                "packs_found": len(pack_index_ids),
                "pack_ids": pack_index_ids,
                "selected_pack_ids": selected_pack_ids,
                "hard_conflicts_count": int(hard_conflicts_count),
                "soft_conflicts_count": int(soft_conflicts_count),
                "index_path": pack_index_path,
                "selection_trace_path": selection_trace_path,
                "report_path": pack_report_path,
                "index_hash": str(pack_index_hash),
                "notes": sorted(set(pack_notes + selection_notes)),
            },
            "formats": {
                "status": fmt_status,
                "formats_found": len(format_ids),
                "format_ids": format_ids,
            },
            "session": {
                "status": sess_status,
                "session_id": "default",
                "ttl_seconds": int(sess_details.get("ttl_seconds", 0)),
                "expires_at": str(sess_details.get("expires_at", "")),
                "session_context_hash": str(sess_details.get("session_context_hash", "")),
            },
            "quality_gate": {
                "status": qual_status,
                "report_path": str(Path(".cache") / "index" / "quality_gate_report.v1.json"),
                "summary": qual_summary,
            },
            "benchmark": {
                "status": bench_status,
                "catalog_path": str(bench.get("catalog_path") or ""),
                "assessment_path": str(bench.get("assessment_path") or ""),
                "scorecard_path": str(bench.get("scorecard_path") or ""),
                "gap_register_path": str(bench.get("gap_register_path") or ""),
                "maturity_avg": float(bench.get("maturity_avg") or 0.0),
                "controls_count": int(bench.get("controls_count") or 0),
                "metrics_count": int(bench.get("metrics_count") or 0),
                "gaps_count": int(bench.get("gaps_count") or 0),
                "gaps_by_severity": bench.get("gaps_by_severity") or {"low": 0, "medium": 0, "high": 0},
                "top_next_actions": bench.get("top_next_actions") or [],
                "notes": bench.get("notes") or [],
            },
            "harvest": {
                "status": harvest_status,
                "candidates": int(candidates_count),
                "kinds": harvest_kinds,
                "report_path": str(Path(".cache") / "learning" / "public_candidates.v1.json"),
            },
            "advisor": {
                "status": adv_status,
                "suggestions": int(suggestions_count),
                "top_kinds": adv_kinds,
                "report_path": str(Path(".cache") / "learning" / "advisor_suggestions.v1.json"),
            },
            "pack_advisor": {
                "status": pack_adv_status,
                "suggestions": int(pack_adv_count),
                "top_kinds": pack_adv_kinds,
                "top_pack_ids": pack_adv_pack_ids,
                "report_path": str(Path(".cache") / "learning" / "pack_advisor_suggestions.v1.json"),
            },
            "readiness": {
                "status": read_status,
                "fails": int(read_fails),
                "warns": int(read_warns),
                "report_path": str(Path(".cache") / "ops" / "autopilot_readiness.v1.json"),
            },
            "actions": {
                "status": act_status,
                "actions_count": int(act_count),
                "top": act_top,
            },
        },
        "notes": [],
    }
    if isinstance(auto_heal, dict):
        report["sections"]["auto_heal"] = auto_heal
    if isinstance(repo_hygiene, dict):
        report["sections"]["repo_hygiene"] = repo_hygiene
    if isinstance(doc_graph, dict):
        report["sections"]["doc_graph"] = doc_graph
    return report


def _render_md(report: dict[str, Any]) -> str:
    sections = report.get("sections") if isinstance(report, dict) else {}
    lines: list[str] = []
    lines.append("# System Status Report (v1)")
    lines.append("")
    lines.append(f"Generated at: {report.get('generated_at', '')}")
    lines.append(f"Workspace: {report.get('workspace_root', '')}")
    lines.append(f"Overall: {report.get('overall_status', '')}")
    lines.append("")

    def _section_title(title: str) -> None:
        lines.append(f"## {title}")

    iso = sections.get("iso_core") if isinstance(sections, dict) else {}
    _section_title("ISO Core")
    lines.append(f"Status: {iso.get('status', '')}")
    missing = iso.get("missing") if isinstance(iso, dict) else None
    if isinstance(missing, list) and missing:
        lines.append("Missing: " + ", ".join(str(x) for x in missing))
    lines.append("")

    spec = sections.get("spec_core") if isinstance(sections, dict) else {}
    _section_title("Spec Core")
    lines.append(f"Status: {spec.get('status', '')}")
    notes = spec.get("notes") if isinstance(spec, dict) else None
    if isinstance(notes, list) and notes:
        lines.append("Notes: " + ", ".join(str(x) for x in notes))
    lines.append("")

    core_int = sections.get("core_integrity") if isinstance(sections, dict) else {}
    _section_title("Core integrity")
    lines.append(f"Status: {core_int.get('status', '')}")
    lines.append(f"Git clean: {core_int.get('git_clean', False)}")
    lines.append(f"Dirty files: {core_int.get('dirty_files_count', 0)}")
    core_notes = core_int.get("notes") if isinstance(core_int, dict) else None
    if isinstance(core_notes, list) and core_notes:
        lines.append("Notes: " + ", ".join(str(x) for x in core_notes))
    lines.append("")

    core_lock = sections.get("core_lock") if isinstance(sections, dict) else {}
    _section_title("Core lock")
    lines.append(f"Status: {core_lock.get('status', '')}")
    lines.append(f"Enabled: {core_lock.get('enabled', False)}")
    lines.append(f"Core unlock allowed: {core_lock.get('core_unlock_allowed', False)}")
    lines.append(f"Blocked attempts: {core_lock.get('last_blocked_attempts', 0)}")
    lines.append("")

    proj = sections.get("project_boundary") if isinstance(sections, dict) else {}
    _section_title("Project boundary")
    lines.append(f"Status: {proj.get('status', '')}")
    lines.append(f"Project root: {proj.get('project_root', '')}")
    lines.append(f"Manifest present: {proj.get('manifest_present', False)}")
    proj_notes = proj.get("notes") if isinstance(proj, dict) else None
    if isinstance(proj_notes, list) and proj_notes:
        lines.append("Notes: " + ", ".join(str(x) for x in proj_notes))
    lines.append("")

    projects = sections.get("projects") if isinstance(sections, dict) else {}
    _section_title("Projects")
    lines.append(f"Status: {projects.get('status', '')}")
    lines.append(f"Projects count: {projects.get('projects_count', 0)}")
    lines.append(f"Next focus: {projects.get('next_project_focus', '')}")
    top_debts = projects.get("top_project_debts") if isinstance(projects, dict) else None
    if isinstance(top_debts, list) and top_debts:
        lines.append("Top debts:")
        for d in top_debts[:5]:
            if not isinstance(d, dict):
                continue
            lines.append(
                f"- {d.get('kind', '')} milestone={d.get('milestone_hint', '')} "
                f"severity={d.get('severity', '')}"
            )
    notes = projects.get("notes") if isinstance(projects, dict) else None
    if isinstance(notes, list) and notes:
        lines.append("Notes: " + ", ".join(str(x) for x in notes))
    lines.append("")

    cat = sections.get("catalog") if isinstance(sections, dict) else {}
    _section_title("Catalog")
    lines.append(f"Status: {cat.get('status', '')}")
    lines.append(f"Packs found: {cat.get('packs_found', 0)}")
    lines.append("")

    packs = sections.get("packs") if isinstance(sections, dict) else {}
    _section_title("Packs")
    lines.append(f"Status: {packs.get('status', '')}")
    lines.append(f"Packs found: {packs.get('packs_found', 0)}")
    selected_pack_ids = packs.get("selected_pack_ids") if isinstance(packs, dict) else None
    if isinstance(selected_pack_ids, list) and selected_pack_ids:
        lines.append("Selected: " + ", ".join(str(x) for x in selected_pack_ids))
    selection_trace = packs.get("selection_trace_path") if isinstance(packs, dict) else None
    if isinstance(selection_trace, str) and selection_trace:
        lines.append(f"Selection trace: {selection_trace}")
    lines.append(f"Hard conflicts: {packs.get('hard_conflicts_count', 0)}")
    lines.append(f"Soft conflicts: {packs.get('soft_conflicts_count', 0)}")
    report_path = packs.get("report_path") if isinstance(packs, dict) else None
    if isinstance(report_path, str) and report_path:
        lines.append(f"Validation report: {report_path}")
    lines.append("")

    fmt = sections.get("formats") if isinstance(sections, dict) else {}
    _section_title("Formats")
    lines.append(f"Status: {fmt.get('status', '')}")
    lines.append(f"Formats found: {fmt.get('formats_found', 0)}")
    lines.append("")

    sess = sections.get("session") if isinstance(sections, dict) else {}
    _section_title("Session")
    lines.append(f"Status: {sess.get('status', '')}")
    lines.append(f"Session ID: {sess.get('session_id', '')}")
    lines.append("")

    qual = sections.get("quality_gate") if isinstance(sections, dict) else {}
    _section_title("Quality")
    lines.append(f"Status: {qual.get('status', '')}")
    lines.append("")

    bench = sections.get("benchmark") if isinstance(sections, dict) else {}
    _section_title("Benchmark")
    lines.append(f"Status: {bench.get('status', '')}")
    lines.append(f"Controls: {bench.get('controls_count', 0)}")
    lines.append(f"Metrics: {bench.get('metrics_count', 0)}")
    lines.append(f"Gaps: {bench.get('gaps_count', 0)}")
    lines.append(f"Maturity avg: {bench.get('maturity_avg', 0)}")
    gaps_by_sev = bench.get("gaps_by_severity") if isinstance(bench, dict) else None
    if isinstance(gaps_by_sev, dict):
        lines.append(
            "Gaps by severity: "
            + ", ".join(
                f"{k}={gaps_by_sev.get(k, 0)}" for k in ["high", "medium", "low"]
            )
        )
    top_actions = bench.get("top_next_actions") if isinstance(bench, dict) else None
    if isinstance(top_actions, list) and top_actions:
        lines.append("Top next actions:")
        for a in top_actions[:5]:
            if not isinstance(a, dict):
                continue
            lines.append(
                f"- {a.get('gap_id', '')} severity={a.get('severity', '')} "
                f"risk={a.get('risk_class', '')} effort={a.get('effort', '')}"
            )
    lines.append("")

    harv = sections.get("harvest") if isinstance(sections, dict) else {}
    _section_title("Harvest")
    lines.append(f"Status: {harv.get('status', '')}")
    lines.append(f"Candidates: {harv.get('candidates', 0)}")
    lines.append("")

    adv = sections.get("advisor") if isinstance(sections, dict) else {}
    _section_title("Advisor")
    lines.append(f"Status: {adv.get('status', '')}")
    lines.append(f"Suggestions: {adv.get('suggestions', 0)}")
    lines.append("")

    pack_adv = sections.get("pack_advisor") if isinstance(sections, dict) else {}
    _section_title("Pack Advisor")
    lines.append(f"Status: {pack_adv.get('status', '')}")
    lines.append(f"Suggestions: {pack_adv.get('suggestions', 0)}")
    lines.append("")

    readiness = sections.get("readiness") if isinstance(sections, dict) else {}
    _section_title("Readiness")
    lines.append(f"Status: {readiness.get('status', '')}")
    lines.append("")

    actions = sections.get("actions") if isinstance(sections, dict) else {}
    _section_title("Actions")
    lines.append(f"Status: {actions.get('status', '')}")
    lines.append(f"Unresolved actions: {actions.get('actions_count', 0)}")
    lines.append("")

    repo_hygiene = sections.get("repo_hygiene") if isinstance(sections, dict) else None
    _section_title("Repo hygiene")
    if isinstance(repo_hygiene, dict):
        lines.append(f"Status: {repo_hygiene.get('status', '')}")
        lines.append(f"Unexpected dirs: {repo_hygiene.get('unexpected_top_level_dirs', 0)}")
        lines.append(f"Tracked generated files: {repo_hygiene.get('tracked_generated_files', 0)}")
        top_findings = repo_hygiene.get("top_findings") if isinstance(repo_hygiene.get("top_findings"), list) else []
        if top_findings:
            top_lines = []
            for item in top_findings[:3]:
                if not isinstance(item, dict):
                    continue
                top_lines.append(f"{item.get('kind')}:{item.get('path')}")
            if top_lines:
                lines.append("Top findings: " + ", ".join(top_lines))
        notes = repo_hygiene.get("notes") if isinstance(repo_hygiene.get("notes"), list) else []
        if notes:
            lines.append("Notes: " + ", ".join(str(x) for x in notes))
    else:
        lines.append("No repo hygiene report found.")
    lines.append("")

    doc_graph = sections.get("doc_graph") if isinstance(sections, dict) else None
    _section_title("Doc graph")
    if isinstance(doc_graph, dict):
        lines.append(f"Status: {doc_graph.get('status', '')}")
        lines.append(f"Broken refs: {doc_graph.get('broken_refs', 0)}")
        lines.append(f"Placeholders: {doc_graph.get('placeholder_refs_count', 0)}")
        lines.append(f"Orphan critical: {doc_graph.get('orphan_critical', 0)}")
        lines.append(f"Ambiguity: {doc_graph.get('ambiguity', 0)}")
        lines.append(f"Critical nav gaps: {doc_graph.get('critical_nav_gaps', 0)}")
        report_path = doc_graph.get("report_path")
        if isinstance(report_path, str) and report_path:
            lines.append(f"Report: {report_path}")
        notes = doc_graph.get("notes") if isinstance(doc_graph.get("notes"), list) else []
        if notes:
            lines.append("Notes: " + ", ".join(str(x) for x in notes))
    else:
        lines.append("No doc graph report found.")
    lines.append("")

    auto_heal = sections.get("auto_heal") if isinstance(sections, dict) else None
    _section_title("Auto-heal")
    if isinstance(auto_heal, dict):
        lines.append(f"Status: {auto_heal.get('status', '')}")
        lines.append(f"Missing: {auto_heal.get('missing_count', 0)}")
        lines.append(f"Healed: {auto_heal.get('healed_count', 0)}")
        lines.append(f"Still missing: {auto_heal.get('still_missing_count', 0)}")
        attempted = auto_heal.get("attempted_milestones")
        if isinstance(attempted, list) and attempted:
            lines.append("Attempted milestones: " + ", ".join(str(x) for x in attempted))
        top_healed = auto_heal.get("top_healed")
        if isinstance(top_healed, list) and top_healed:
            lines.append("Top healed: " + ", ".join(str(x.get("id")) for x in top_healed if isinstance(x, dict)))
    else:
        lines.append("No recent auto-heal report found.")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def run_system_status(*, workspace_root: Path, core_root: Path, dry_run: bool) -> dict[str, Any]:
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        return {"status": "OK", "note": "POLICY_DISABLED", "on_fail": policy.on_fail}

    out_json = _resolve_workspace_path(workspace_root, policy.out_json)
    out_md = _resolve_workspace_path(workspace_root, policy.out_md)
    if out_json is None or out_md is None:
        return {"status": "FAIL", "error_code": "OUTPUT_PATH_INVALID", "on_fail": policy.on_fail}

    report = build_system_status(
        workspace_root=workspace_root,
        core_root=core_root,
        policy=policy,
        dry_run=dry_run,
    )
    errors = _validate_schema(core_root, report)
    if errors:
        return {"status": "FAIL", "error_code": "SCHEMA_INVALID", "errors": errors[:10], "out_json": str(out_json), "out_md": str(out_md), "on_fail": policy.on_fail}

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "overall_status": report.get("overall_status"),
            "out_json": str(out_json),
            "out_md": str(out_md),
            "on_fail": policy.on_fail,
        }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(_dump_json(report), encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")

    return {
        "status": "OK",
        "overall_status": report.get("overall_status"),
        "out_json": str(out_json),
        "out_md": str(out_md),
        "on_fail": policy.on_fail,
    }


def action_from_system_status_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    overall = result.get("overall_status")
    out_json = result.get("out_json") if isinstance(result.get("out_json"), str) else None
    title = "System status report generated"
    if status == "FAIL":
        title = "System status report failed"
    severity = "INFO" if status in {"OK", "WOULD_WRITE"} else "WARN"
    action_kind = "SYSTEM_STATUS" if status in {"OK", "WOULD_WRITE"} else "SYSTEM_STATUS_FAIL"
    msg = f"System status: {overall}" if overall else "System status report generated"
    action_id = sha256(f"SYSTEM_STATUS|{status}|{out_json}".encode("utf-8")).hexdigest()[:16]
    return {
        "action_id": action_id,
        "severity": severity,
        "kind": action_kind,
        "milestone_hint": "M8.1",
        "source": "SYSTEM_STATUS",
        "title": title,
        "details": {
            "status": status,
            "overall_status": overall,
            "out_json": out_json,
            "out_md": result.get("out_md"),
            "error_code": result.get("error_code"),
        },
        "message": msg,
        "resolved": status in {"OK", "WOULD_WRITE"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.system_status_report", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        dry_run = _parse_bool(str(args.dry_run))
    except Exception:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_DRY_RUN"}, ensure_ascii=False, sort_keys=True))
        return 2

    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        print(json.dumps({"status": "OK", "note": "POLICY_DISABLED"}, ensure_ascii=False, sort_keys=True))
        return 0

    res = run_system_status(workspace_root=workspace_root, core_root=core_root, dry_run=dry_run)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
