from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NORTH_STAR_SOURCE_REFERENCE_KEYS = {"REFERENCE", "TREND", "TREND_CATALOG", "TREND_CATALOG_V1"}
NORTH_STAR_SOURCE_BP_KEYS = {"CAPABILITY", "BP", "BEST_PRACTICE", "BP_CATALOG", "BP_CATALOG_V1"}
NORTH_STAR_SOURCE_ASSESSMENT_KEYS = {"CRITERION", "LENS", "LENS_REQUIREMENT"}
NORTH_STAR_GAP_MATCH_KEYS = {"NOT_TRIGGERED", "UNKNOWN", "FAIL", "FAILED", "WARN", "WARNING"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return _load_json(path)
    except Exception:
        return default


def _normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-", "."})


def _build_label(tr_val: Any, en_val: Any, fallback: Any = "") -> str:
    tr = str(tr_val or "").strip()
    en = str(en_val or "").strip()
    fb = str(fallback or "").strip()
    if tr and en and tr != en:
        return f"{tr} ({en})"
    return tr or en or fb


def _extract_tag_value(tags: Any, prefix: str) -> str:
    if not isinstance(tags, list):
        return ""
    pref = prefix.lower() + ":"
    for tag in tags:
        text = str(tag or "").strip()
        if text.lower().startswith(pref):
            return text.split(":", 1)[1].strip()
    return ""


def _derive_stage(item: dict[str, Any]) -> str:
    explicit_raw = (
        item.get("workflow_stage")
        or item.get("workflowStage")
        or item.get("stage")
        or item.get("phase")
        or item.get("process_stage")
        or item.get("processStage")
    )
    explicit = _normalize_key(explicit_raw).upper()
    if explicit in {"REFERENCE", "REF"}:
        return "reference"
    if explicit in {"ASSESSMENT", "ASSESS", "EVALUATION", "EVAL"}:
        return "assessment"
    if explicit in {"GAP", "DEVIATION"}:
        return "gap"

    match_norm = _normalize_key(item.get("match_status")).upper()
    if match_norm in NORTH_STAR_GAP_MATCH_KEYS:
        return "gap"

    catalog_norm = _normalize_key(item.get("catalog")).upper()
    if catalog_norm in NORTH_STAR_SOURCE_REFERENCE_KEYS or catalog_norm in NORTH_STAR_SOURCE_BP_KEYS:
        return "reference"
    if catalog_norm in NORTH_STAR_SOURCE_ASSESSMENT_KEYS:
        return "assessment"
    return "assessment"


def _topic_value(item: dict[str, Any]) -> str:
    topic = str(item.get("topic") or "").strip()
    if topic:
        return topic
    return _extract_tag_value(item.get("tags"), "topic")


def _subject_value(item: dict[str, Any]) -> str:
    subject = str(item.get("subject_id") or item.get("subject") or "").strip()
    if subject:
        return subject
    return _extract_tag_value(item.get("tags"), "subject")


def _values_to_keyset(*values: Any) -> set[str]:
    keys: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            for part in value:
                key = _normalize_key(part)
                if key:
                    keys.add(key)
            continue
        key = _normalize_key(value)
        if key:
            keys.add(key)
    return keys


def _record_from_item(item: dict[str, Any], *, stage_hint: str | None = None) -> dict[str, Any]:
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    subject_id = _subject_value(item)
    theme_id = str(item.get("theme_id") or "").strip()
    theme_title_tr = str(item.get("theme_title_tr") or item.get("theme_tr") or item.get("theme_title") or item.get("theme") or "").strip()
    theme_title_en = str(item.get("theme_title_en") or item.get("theme_en") or "").strip()
    subtheme_id = str(item.get("subtheme_id") or "").strip()
    subtheme_title_tr = str(item.get("subtheme_title_tr") or item.get("subtheme_tr") or item.get("subtheme_title") or item.get("subtheme") or "").strip()
    subtheme_title_en = str(item.get("subtheme_title_en") or item.get("subtheme_en") or "").strip()
    criterion_id = _topic_value(item)

    return {
        "id": str(item.get("id") or "").strip(),
        "title": str(item.get("title") or "").strip(),
        "summary": str(item.get("summary") or "").strip(),
        "match_status": str(item.get("match_status") or "").strip().upper(),
        "stage": stage_hint or _derive_stage(item),
        "subject_id": subject_id,
        "theme_id": theme_id,
        "theme_title": _build_label(theme_title_tr, theme_title_en, theme_id),
        "subtheme_id": subtheme_id,
        "subtheme_title": _build_label(subtheme_title_tr, subtheme_title_en, subtheme_id),
        "criterion_id": criterion_id,
        "criterion_key": _normalize_key(criterion_id),
        "subject_keys": _values_to_keyset(subject_id),
        "theme_keys": _values_to_keyset(theme_id, theme_title_tr, theme_title_en),
        "subtheme_keys": _values_to_keyset(subtheme_id, subtheme_title_tr, subtheme_title_en),
        "evidence_pointers": [str(x).strip() for x in (item.get("evidence_pointers") if isinstance(item.get("evidence_pointers"), list) else []) if str(x).strip()],
        "tags": [str(x).strip() for x in tags if str(x).strip()],
    }


def _load_eval_findings(eval_obj: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lenses = eval_obj.get("lenses")
    if not isinstance(lenses, dict):
        return out
    for lens_name in sorted(lenses.keys()):
        lens = lenses.get(lens_name)
        if not isinstance(lens, dict):
            continue
        findings = lens.get("findings")
        if not isinstance(findings, dict):
            continue
        items = findings.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("lens", lens_name)
                out.append(row)
    return out


def _load_mechanism_contexts(mechanisms_registry: dict[str, Any]) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    subjects = mechanisms_registry.get("subjects") if isinstance(mechanisms_registry.get("subjects"), list) else []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        subject_id = str(subject.get("subject_id") or "").strip()
        subject_label = _build_label(subject.get("subject_title_tr"), subject.get("subject_title_en"), subject_id)
        themes = subject.get("themes") if isinstance(subject.get("themes"), list) else []
        for theme in themes:
            if not isinstance(theme, dict):
                continue
            theme_id = str(theme.get("theme_id") or "").strip()
            theme_label = _build_label(theme.get("title_tr"), theme.get("title_en"), theme_id)
            subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
            for subtheme in subthemes:
                if not isinstance(subtheme, dict):
                    continue
                subtheme_id = str(subtheme.get("subtheme_id") or "").strip()
                subtheme_label = _build_label(subtheme.get("title_tr"), subtheme.get("title_en"), subtheme_id)
                contexts.append(
                    {
                        "subject_id": subject_id,
                        "subject_label": subject_label or subject_id or "unknown",
                        "theme_id": theme_id,
                        "theme_label": theme_label or theme_id or "unknown",
                        "subtheme_id": subtheme_id,
                        "subtheme_label": subtheme_label or subtheme_id or "unknown",
                        "subject_keys": _values_to_keyset(subject_id, subject_label),
                        "theme_keys": _values_to_keyset(theme_id, theme_label),
                        "subtheme_keys": _values_to_keyset(subtheme_id, subtheme_label),
                    }
                )
    return contexts


def _fallback_contexts_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    contexts: list[dict[str, Any]] = []
    for record in records:
        subtheme_keys = record.get("subtheme_keys") if isinstance(record.get("subtheme_keys"), set) else set()
        if not subtheme_keys:
            continue
        subject_id = str(record.get("subject_id") or "").strip()
        subject_label = subject_id or "unknown"
        theme_id = str(record.get("theme_id") or "").strip()
        theme_label = str(record.get("theme_title") or "").strip() or theme_id or "unknown"
        subtheme_id = str(record.get("subtheme_id") or "").strip()
        subtheme_label = str(record.get("subtheme_title") or "").strip() or subtheme_id or "unknown"
        key = "|".join(
            [
                _normalize_key(subject_id),
                _normalize_key(theme_id or theme_label),
                _normalize_key(subtheme_id or subtheme_label),
            ]
        )
        if not key or key in seen:
            continue
        seen.add(key)
        contexts.append(
            {
                "subject_id": subject_id,
                "subject_label": subject_label,
                "theme_id": theme_id,
                "theme_label": theme_label,
                "subtheme_id": subtheme_id,
                "subtheme_label": subtheme_label,
                "subject_keys": _values_to_keyset(subject_id, subject_label),
                "theme_keys": _values_to_keyset(theme_id, theme_label),
                "subtheme_keys": _values_to_keyset(subtheme_id, subtheme_label),
            }
        )
    return contexts


def _criteria_profile(criteria_packs: dict[str, Any]) -> dict[str, Any]:
    core_8 = criteria_packs.get("core_8") if isinstance(criteria_packs.get("core_8"), list) else []
    perspective_packs = (
        criteria_packs.get("perspective_packs") if isinstance(criteria_packs.get("perspective_packs"), dict) else {}
    )
    perspective_id = "BUSINESS_PROCESS" if "BUSINESS_PROCESS" in perspective_packs else ""
    if not perspective_id and perspective_packs:
        perspective_id = sorted(perspective_packs.keys())[0]
    perspective_entry = perspective_packs.get(perspective_id) if perspective_id else {}
    perspective_criteria = (
        perspective_entry.get("criteria") if isinstance(perspective_entry, dict) and isinstance(perspective_entry.get("criteria"), list) else []
    )

    merged: list[str] = []
    seen: set[str] = set()
    for criterion in [*core_8, *perspective_criteria]:
        value = str(criterion or "").strip()
        key = _normalize_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(value)

    labels: dict[str, str] = {}
    axis_registry = criteria_packs.get("axis_registry") if isinstance(criteria_packs.get("axis_registry"), list) else []
    for axis in axis_registry:
        if not isinstance(axis, dict):
            continue
        axis_id = str(axis.get("axis_id") or "").strip()
        if not axis_id:
            continue
        labels[_normalize_key(axis_id)] = _build_label(axis.get("label_tr"), axis.get("label_en"), axis_id)

    criteria_out = [
        {
            "criterion_id": criterion,
            "criterion_key": _normalize_key(criterion),
            "criterion_label": labels.get(_normalize_key(criterion), criterion),
        }
        for criterion in merged
    ]
    return {
        "perspective_id": perspective_id,
        "criteria": criteria_out,
    }


def _row_id(context: dict[str, Any], criterion_key: str) -> str:
    parts = [
        _normalize_key(context.get("subject_id") or context.get("subject_label") or "subject"),
        _normalize_key(context.get("theme_id") or context.get("theme_label") or "theme"),
        _normalize_key(context.get("subtheme_id") or context.get("subtheme_label") or "subtheme"),
        criterion_key or "criterion",
    ]
    return "|".join(parts)


def _build_base_rows(
    *, contexts: list[dict[str, Any]], criteria: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for context in contexts:
        for criterion in criteria:
            criterion_id = str(criterion.get("criterion_id") or "").strip()
            criterion_key = str(criterion.get("criterion_key") or "").strip()
            criterion_label = str(criterion.get("criterion_label") or criterion_id).strip()
            if not criterion_key:
                continue
            rows.append(
                {
                    "row_id": _row_id(context, criterion_key),
                    "subject_id": str(context.get("subject_id") or "").strip(),
                    "subject_label": str(context.get("subject_label") or "").strip(),
                    "theme_id": str(context.get("theme_id") or "").strip(),
                    "theme_label": str(context.get("theme_label") or "").strip(),
                    "subtheme_id": str(context.get("subtheme_id") or "").strip(),
                    "subtheme_label": str(context.get("subtheme_label") or "").strip(),
                    "criterion_id": criterion_id,
                    "criterion_key": criterion_key,
                    "criterion_label": criterion_label,
                    "subject_keys": context.get("subject_keys") if isinstance(context.get("subject_keys"), set) else set(),
                    "theme_keys": context.get("theme_keys") if isinstance(context.get("theme_keys"), set) else set(),
                    "subtheme_keys": context.get("subtheme_keys") if isinstance(context.get("subtheme_keys"), set) else set(),
                }
            )
    return rows


def _record_matches_row(record: dict[str, Any], row: dict[str, Any]) -> bool:
    if str(record.get("criterion_key") or "") != str(row.get("criterion_key") or ""):
        return False

    row_subtheme_keys = row.get("subtheme_keys") if isinstance(row.get("subtheme_keys"), set) else set()
    rec_subtheme_keys = record.get("subtheme_keys") if isinstance(record.get("subtheme_keys"), set) else set()
    if row_subtheme_keys:
        if not rec_subtheme_keys:
            return False
        if not row_subtheme_keys.intersection(rec_subtheme_keys):
            return False

    row_theme_keys = row.get("theme_keys") if isinstance(row.get("theme_keys"), set) else set()
    rec_theme_keys = record.get("theme_keys") if isinstance(record.get("theme_keys"), set) else set()
    if row_theme_keys and rec_theme_keys and not row_theme_keys.intersection(rec_theme_keys):
        return False

    row_subject_keys = row.get("subject_keys") if isinstance(row.get("subject_keys"), set) else set()
    rec_subject_keys = record.get("subject_keys") if isinstance(record.get("subject_keys"), set) else set()
    if row_subject_keys and rec_subject_keys and not row_subject_keys.intersection(rec_subject_keys):
        return False

    return True


def _summarize_stage_items(stage: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    item_count = len(records)
    triggered = 0
    not_triggered = 0
    unknown = 0
    titles: list[str] = []
    refs: list[str] = []
    pointers: list[str] = []

    seen_titles: set[str] = set()
    seen_refs: set[str] = set()
    seen_ptrs: set[str] = set()

    for record in records:
        match_status = str(record.get("match_status") or "").upper()
        if match_status == "TRIGGERED":
            triggered += 1
        elif match_status == "NOT_TRIGGERED":
            not_triggered += 1
        elif match_status:
            unknown += 1
        title = str(record.get("title") or "").strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            titles.append(title)
        item_ref = str(record.get("id") or "").strip()
        if item_ref and item_ref not in seen_refs:
            seen_refs.add(item_ref)
            refs.append(item_ref)
        for pointer in record.get("evidence_pointers") if isinstance(record.get("evidence_pointers"), list) else []:
            ptr = str(pointer or "").strip()
            if ptr and ptr not in seen_ptrs:
                seen_ptrs.add(ptr)
                pointers.append(ptr)

    if stage == "reference":
        status = "HAS_DATA" if item_count > 0 else "NO_DATA"
        summary = (
            f"reference_items={item_count}"
            if item_count > 0
            else "reference_items=0 (no matched reference yet)"
        )
    elif stage == "assessment":
        status = "HAS_DATA" if item_count > 0 else "NO_DATA"
        summary = (
            f"assessment_items={item_count} triggered={triggered} not_triggered={not_triggered} unknown={unknown}"
            if item_count > 0
            else "assessment_items=0 (no matched assessment yet)"
        )
    else:
        status = "OPEN" if item_count > 0 else "NO_GAP"
        summary = (
            f"gap_items={item_count} triggered={triggered} not_triggered={not_triggered} unknown={unknown}"
            if item_count > 0
            else "gap_items=0"
        )

    return {
        "item_count": item_count,
        "triggered_count": triggered,
        "not_triggered_count": not_triggered,
        "unknown_count": unknown,
        "status": status,
        "summary": summary,
        "titles": titles[:8],
        "item_refs": refs[:30],
        "evidence_pointers": pointers[:30],
    }


def _stage_matrix_payload(
    *,
    stage: str,
    base_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    generated_at: str,
    workspace_root: Path,
    profile: dict[str, Any],
) -> dict[str, Any]:
    out_items: list[dict[str, Any]] = []
    rows_with_data = 0
    items_total = 0

    for row in base_rows:
        matched = [record for record in records if _record_matches_row(record, row)]
        summary = _summarize_stage_items(stage, matched)
        items_total += int(summary["item_count"])
        if int(summary["item_count"]) > 0:
            rows_with_data += 1
        out_items.append(
            {
                "row_id": row["row_id"],
                "stage": stage,
                "subject_id": row["subject_id"],
                "subject_label": row["subject_label"],
                "theme_id": row["theme_id"],
                "theme_label": row["theme_label"],
                "subtheme_id": row["subtheme_id"],
                "subtheme_label": row["subtheme_label"],
                "criterion_id": row["criterion_id"],
                "criterion_label": row["criterion_label"],
                "item_count": summary["item_count"],
                "triggered_count": summary["triggered_count"],
                "not_triggered_count": summary["not_triggered_count"],
                "unknown_count": summary["unknown_count"],
                "status": summary["status"],
                "summary": summary["summary"],
                "titles": summary["titles"],
                "item_refs": summary["item_refs"],
                "evidence_pointers": summary["evidence_pointers"],
                "lens_findings_filter": {
                    "catalog": stage,
                    "subject": row["subject_id"],
                    "theme": row["theme_label"],
                    "subtheme": row["subtheme_label"],
                    "topic": row["criterion_id"],
                },
            }
        )

    subtheme_keys = {
        _normalize_key(item.get("subtheme_id") or item.get("subtheme_label"))
        for item in out_items
        if _normalize_key(item.get("subtheme_id") or item.get("subtheme_label"))
    }
    criteria_total = len(profile.get("criteria") if isinstance(profile.get("criteria"), list) else [])
    summary = {
        "rows_total": len(out_items),
        "rows_with_data": rows_with_data,
        "items_total": items_total,
        "subthemes_total": len(subtheme_keys),
        "criteria_total": criteria_total,
        "perspective_id": str(profile.get("perspective_id") or ""),
    }
    return {
        "version": "v1",
        "stage": stage,
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "criteria_profile": {
            "perspective_id": str(profile.get("perspective_id") or ""),
            "criteria": [
                {
                    "criterion_id": str(c.get("criterion_id") or ""),
                    "criterion_label": str(c.get("criterion_label") or ""),
                }
                for c in (profile.get("criteria") if isinstance(profile.get("criteria"), list) else [])
            ],
        },
        "summary": summary,
        "items": out_items,
    }


def build_north_star_stage_matrices(*, workspace_root: Path, core_root: Path) -> dict[str, dict[str, Any]]:
    trend_path = workspace_root / ".cache" / "index" / "trend_catalog.v1.json"
    bp_path = workspace_root / ".cache" / "index" / "bp_catalog.v1.json"
    eval_path = workspace_root / ".cache" / "index" / "assessment_eval.v1.json"
    gap_path = workspace_root / ".cache" / "index" / "gap_register.v1.json"
    ws_registry_path = workspace_root / ".cache" / "index" / "mechanisms.registry.v1.json"
    core_registry_path = workspace_root / "registry" / "north_star" / "mechanisms.registry.v1.json"
    criteria_path = workspace_root / "docs" / "OPERATIONS" / "north_star_criteria_packs.v1.json"
    if not criteria_path.exists():
        criteria_path = core_root / "docs" / "OPERATIONS" / "north_star_criteria_packs.v1.json"

    trend_obj = _load_json_or_default(trend_path, {"version": "v1", "items": []})
    bp_obj = _load_json_or_default(bp_path, {"version": "v1", "items": []})
    eval_obj = _load_json_or_default(eval_path, {"version": "v1", "lenses": {}})
    gap_obj = _load_json_or_default(gap_path, {"version": "v1", "gaps": []})
    criteria_obj = _load_json_or_default(criteria_path, {"version": "v1", "core_8": [], "perspective_packs": {}})

    registry_obj = _load_json_or_default(ws_registry_path, {})
    if not isinstance(registry_obj, dict) or not registry_obj.get("subjects"):
        registry_obj = _load_json_or_default(core_registry_path, {})

    trend_items = trend_obj.get("items") if isinstance(trend_obj, dict) and isinstance(trend_obj.get("items"), list) else []
    bp_items = bp_obj.get("items") if isinstance(bp_obj, dict) and isinstance(bp_obj.get("items"), list) else []
    eval_findings = _load_eval_findings(eval_obj if isinstance(eval_obj, dict) else {})
    gap_items = gap_obj.get("gaps") if isinstance(gap_obj, dict) and isinstance(gap_obj.get("gaps"), list) else []

    reference_records = [
        _record_from_item(item, stage_hint="reference") for item in [*trend_items, *bp_items] if isinstance(item, dict)
    ]
    assessment_gap_records = [
        _record_from_item(item, stage_hint=None) for item in eval_findings if isinstance(item, dict)
    ]
    assessment_records = [rec for rec in assessment_gap_records if rec.get("stage") == "assessment"]
    gap_records = [rec for rec in assessment_gap_records if rec.get("stage") == "gap"]

    # Keep non-axis gap signals visible at summary level even when they don't map to a criterion row.
    unmatched_gap_count = 0
    for gap in gap_items:
        if not isinstance(gap, dict):
            continue
        topic = _topic_value(gap)
        if not topic:
            unmatched_gap_count += 1

    contexts = _load_mechanism_contexts(registry_obj if isinstance(registry_obj, dict) else {})
    if not contexts:
        contexts = _fallback_contexts_from_records([*reference_records, *assessment_records, *gap_records])

    profile = _criteria_profile(criteria_obj if isinstance(criteria_obj, dict) else {})
    criteria = profile.get("criteria") if isinstance(profile.get("criteria"), list) else []
    if not criteria:
        fallback_criteria = sorted(
            {
                str(rec.get("criterion_id") or "").strip()
                for rec in [*reference_records, *assessment_records, *gap_records]
                if str(rec.get("criterion_id") or "").strip()
            }
        )
        criteria = [
            {
                "criterion_id": item,
                "criterion_key": _normalize_key(item),
                "criterion_label": item,
            }
            for item in fallback_criteria
        ]
        profile = {"perspective_id": str(profile.get("perspective_id") if isinstance(profile, dict) else ""), "criteria": criteria}

    base_rows = _build_base_rows(contexts=contexts, criteria=criteria)
    if not base_rows:
        generated_at = _now_iso()
        empty_payload = {
            "version": "v1",
            "stage": "reference",
            "generated_at": generated_at,
            "workspace_root": str(workspace_root),
            "criteria_profile": {"perspective_id": str(profile.get("perspective_id") or ""), "criteria": []},
            "summary": {
                "rows_total": 0,
                "rows_with_data": 0,
                "items_total": 0,
                "subthemes_total": 0,
                "criteria_total": 0,
                "perspective_id": str(profile.get("perspective_id") or ""),
            },
            "items": [],
        }
        return {
            "reference": dict(empty_payload, stage="reference"),
            "assessment": dict(empty_payload, stage="assessment"),
            "gap": dict(empty_payload, stage="gap"),
        }

    generated_at = _now_iso()
    reference_payload = _stage_matrix_payload(
        stage="reference",
        base_rows=base_rows,
        records=reference_records,
        generated_at=generated_at,
        workspace_root=workspace_root,
        profile=profile,
    )
    assessment_payload = _stage_matrix_payload(
        stage="assessment",
        base_rows=base_rows,
        records=assessment_records,
        generated_at=generated_at,
        workspace_root=workspace_root,
        profile=profile,
    )
    gap_payload = _stage_matrix_payload(
        stage="gap",
        base_rows=base_rows,
        records=gap_records,
        generated_at=generated_at,
        workspace_root=workspace_root,
        profile=profile,
    )
    gap_summary = gap_payload.get("summary")
    if isinstance(gap_summary, dict):
        gap_summary["gap_register_items_unmapped"] = unmatched_gap_count
        gap_summary["gap_register_items_total"] = len(gap_items)

    return {
        "reference": reference_payload,
        "assessment": assessment_payload,
        "gap": gap_payload,
    }
