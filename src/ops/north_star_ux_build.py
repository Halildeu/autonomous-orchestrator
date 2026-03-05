from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return obj


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _to_rel(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _title(theme_or_sub: dict[str, Any], fallback_id: str) -> dict[str, str]:
    tr = str(theme_or_sub.get("title_tr") or "").strip() or fallback_id
    en = str(theme_or_sub.get("title_en") or "").strip() or fallback_id
    return {"tr": tr, "en": en}


def _find_subject(mechanisms: dict[str, Any], subject_id: str) -> dict[str, Any] | None:
    subjects = mechanisms.get("subjects") if isinstance(mechanisms.get("subjects"), list) else []
    target = str(subject_id).strip()
    for item in subjects:
        if not isinstance(item, dict):
            continue
        if str(item.get("subject_id") or "").strip() == target:
            return item
    return None


def _build_sections(subject: dict[str, Any]) -> list[dict[str, Any]]:
    themes = subject.get("themes") if isinstance(subject.get("themes"), list) else []
    sections: list[dict[str, Any]] = []
    for theme in themes:
        if not isinstance(theme, dict):
            continue
        section_id = str(theme.get("theme_id") or "").strip()
        if not section_id:
            continue
        subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        subsections: list[dict[str, Any]] = []
        for sub in subthemes:
            if not isinstance(sub, dict):
                continue
            sub_id = str(sub.get("subtheme_id") or "").strip()
            if not sub_id:
                continue
            subsections.append(
                {
                    "subsection_id": sub_id,
                    "title": _title(sub, sub_id),
                }
            )
        sections.append(
            {
                "section_id": section_id,
                "title": _title(theme, section_id),
                "item_count": len(subsections),
                "subsections": subsections,
            }
        )
    return sections


def _build_ux_catalog(
    *,
    workspace_root: Path,
    subject_id: str,
    subject: dict[str, Any],
    sections: list[dict[str, Any]],
    mechanisms_rel: str,
    north_star_rel: str,
    north_star_catalog: dict[str, Any],
) -> dict[str, Any]:
    packs = north_star_catalog.get("packs") if isinstance(north_star_catalog.get("packs"), list) else []
    pack_ids = sorted(
        {
            str(item.get("pack_id") or "").strip()
            for item in packs
            if isinstance(item, dict) and str(item.get("pack_id") or "").strip()
        }
    )
    controls = north_star_catalog.get("controls") if isinstance(north_star_catalog.get("controls"), list) else []
    metrics = north_star_catalog.get("metrics") if isinstance(north_star_catalog.get("metrics"), list) else []

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "subject_id": subject_id,
        "subject_title": {
            "tr": str(subject.get("subject_title_tr") or subject_id),
            "en": str(subject.get("subject_title_en") or subject_id),
        },
        "source": {
            "reference_mode": "north_star_reference",
            "mechanisms_registry_path": mechanisms_rel,
            "north_star_catalog_path": north_star_rel,
        },
        "sections": sections,
        "references": {
            "pack_ids": pack_ids,
            "controls_count": len(controls),
            "metrics_count": len(metrics),
        },
    }


def _build_ux_blueprint(*, workspace_root: Path, subject_id: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    flow_steps = [
        {
            "step_id": "open_subject",
            "action": "Open subject catalog view",
            "outcome": "Header + sections rendered",
        },
        {
            "step_id": "expand_section",
            "action": "Expand a section row",
            "outcome": "Subsections become visible",
        },
        {
            "step_id": "trigger_action",
            "action": "Run Lens or AI suggestion action",
            "outcome": "Action feedback state shown",
        },
    ]

    components = [
        {
            "component_id": "program_header_card",
            "source": "mfe-ui-kit",
            "role": "header",
            "props_contract": ["title", "subject_id", "status", "snapshot_label"],
        },
        {
            "component_id": "catalog_tree_row",
            "source": "mfe-ui-kit",
            "role": "navigation",
            "props_contract": ["section_id", "title", "count", "expanded"],
        },
        {
            "component_id": "row_action_chips",
            "source": "mfe-ui-kit",
            "role": "actions",
            "props_contract": ["lens_action", "ai_action", "disabled", "loading"],
        },
        {
            "component_id": "status_pill",
            "source": "mfe-ui-kit",
            "role": "status",
            "props_contract": ["value", "tone"],
        },
    ]

    section_fields = ["section_id", "title.tr", "title.en", "item_count"]
    subsection_fields = ["subsection_id", "title.tr", "title.en"]
    data_contracts = [
        {
            "contract_id": "ux_catalog_section",
            "source": "ux_catalog.sections",
            "fields": section_fields,
        },
        {
            "contract_id": "ux_catalog_subsection",
            "source": "ux_catalog.sections[].subsections",
            "fields": subsection_fields,
        },
    ]

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "subject_id": subject_id,
        "blueprint_id": f"uxbp_{_slug(subject_id)}",
        "information_architecture": {
            "page_id": f"ux_{_slug(subject_id)}",
            "layout": "catalog_tree",
            "navigation_model": "tree_with_details",
            "regions": ["header", "toolbar", "content", "status"],
        },
        "flows": [
            {
                "flow_id": "explore_catalog",
                "actor": "user",
                "steps": flow_steps,
            }
        ],
        "components": components,
        "data_contracts": data_contracts,
        "quality_gates": [
            "single_ui_library",
            "design_token_chain",
            "a11y_keyboard_support",
            "state_feedback_consistency",
            "contract_lane_green",
        ],
        "stats": {
            "section_count": len(sections),
            "subsection_count": sum(int(item.get("item_count") or 0) for item in sections if isinstance(item, dict)),
        },
    }


def _build_ux_interaction_matrix(
    *,
    workspace_root: Path,
    subject_id: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = [
        {
            "interaction_id": "catalog_row_toggle",
            "component_id": "catalog_tree_row",
            "trigger": "click",
            "event": "toggle",
            "states": ["collapsed", "expanded", "hover", "focus"],
            "accessibility": ["Enter", "Space", "ArrowRight", "ArrowLeft"],
            "expected_result": "Row toggles and subsection visibility updates.",
            "telemetry_event": "ux.catalog.row.toggle",
        },
        {
            "interaction_id": "lens_transfer",
            "component_id": "row_action_chips",
            "trigger": "click",
            "event": "lens_transfer",
            "states": ["idle", "loading", "success", "error"],
            "accessibility": ["Tab", "Enter", "Space"],
            "expected_result": "Lens transfer starts and feedback badge is shown.",
            "telemetry_event": "ux.catalog.action.lens_transfer",
        },
        {
            "interaction_id": "ai_suggestion_request",
            "component_id": "row_action_chips",
            "trigger": "click",
            "event": "ai_suggestion",
            "states": ["idle", "loading", "success", "error"],
            "accessibility": ["Tab", "Enter", "Space"],
            "expected_result": "AI suggestion request executes under policy guardrails.",
            "telemetry_event": "ux.catalog.action.ai_suggestion",
        },
    ]

    for section in sections[:20]:
        if not isinstance(section, dict):
            continue
        sid = str(section.get("section_id") or "").strip()
        if not sid:
            continue
        rows.append(
            {
                "interaction_id": f"section_focus_{_slug(sid)}",
                "component_id": "catalog_tree_row",
                "trigger": "keyboard",
                "event": "focus",
                "states": ["focus", "blur"],
                "accessibility": ["Tab", "Shift+Tab", "ArrowDown", "ArrowUp"],
                "expected_result": f"Keyboard focus moves predictably on section {sid}.",
                "telemetry_event": "ux.catalog.keyboard.focus",
            }
        )

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "subject_id": subject_id,
        "rows": rows,
    }


def run_north_star_ux_build(*, workspace_root: Path, subject_id: str, out_dir: str) -> dict[str, Any]:
    ws = workspace_root.resolve()
    if not ws.exists() or not ws.is_dir():
        return {"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}

    mechanisms_path = ws / ".cache" / "index" / "mechanisms.registry.v1.json"
    if not mechanisms_path.exists():
        return {
            "status": "FAIL",
            "error_code": "MECHANISMS_REGISTRY_MISSING",
            "missing": [".cache/index/mechanisms.registry.v1.json"],
        }

    mechanisms = _load_json(mechanisms_path)
    subject = _find_subject(mechanisms, subject_id)
    if not isinstance(subject, dict):
        subjects = mechanisms.get("subjects") if isinstance(mechanisms.get("subjects"), list) else []
        available = [
            str(item.get("subject_id") or "")
            for item in subjects
            if isinstance(item, dict) and str(item.get("subject_id") or "")
        ]
        return {
            "status": "FAIL",
            "error_code": "SUBJECT_NOT_FOUND",
            "subject_id": subject_id,
            "available_subject_ids": sorted(available)[:200],
        }

    north_star_path = ws / ".cache" / "index" / "north_star_catalog.v1.json"
    north_star_catalog = _load_json(north_star_path) if north_star_path.exists() else {}

    out_dir_path = Path(str(out_dir).strip() or ".cache/index/ux")
    out_dir_abs = (ws / out_dir_path).resolve() if not out_dir_path.is_absolute() else out_dir_path.resolve()
    try:
        out_dir_abs.relative_to(ws)
    except Exception:
        return {"status": "FAIL", "error_code": "OUT_DIR_OUTSIDE_WORKSPACE"}
    out_dir_abs.mkdir(parents=True, exist_ok=True)

    sections = _build_sections(subject)
    if not sections:
        return {
            "status": "FAIL",
            "error_code": "SUBJECT_THEMES_EMPTY",
            "subject_id": subject_id,
        }

    mechanisms_rel = _to_rel(ws, mechanisms_path)
    north_star_rel = _to_rel(ws, north_star_path) if north_star_path.exists() else ""

    ux_catalog = _build_ux_catalog(
        workspace_root=ws,
        subject_id=subject_id,
        subject=subject,
        sections=sections,
        mechanisms_rel=mechanisms_rel,
        north_star_rel=north_star_rel,
        north_star_catalog=north_star_catalog,
    )
    ux_blueprint = _build_ux_blueprint(workspace_root=ws, subject_id=subject_id, sections=sections)
    ux_matrix = _build_ux_interaction_matrix(workspace_root=ws, subject_id=subject_id, sections=sections)

    subject_slug = _slug(subject_id)
    catalog_path = out_dir_abs / f"{subject_slug}.ux_catalog.v1.json"
    blueprint_path = out_dir_abs / f"{subject_slug}.ux_blueprint.v1.json"
    matrix_path = out_dir_abs / f"{subject_slug}.ux_interaction_matrix.v1.json"

    catalog_path.write_text(json.dumps(ux_catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    blueprint_path.write_text(json.dumps(ux_blueprint, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    matrix_path.write_text(json.dumps(ux_matrix, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "OK",
        "subject_id": subject_id,
        "out_dir": _to_rel(ws, out_dir_abs),
        "ux_catalog_path": _to_rel(ws, catalog_path),
        "ux_blueprint_path": _to_rel(ws, blueprint_path),
        "ux_interaction_matrix_path": _to_rel(ws, matrix_path),
        "section_count": len(sections),
        "subsection_count": sum(int(item.get("item_count") or 0) for item in sections if isinstance(item, dict)),
    }


def cmd_north_star_ux_build(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(getattr(args, "workspace_root", "") or "").strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()

    subject_id = str(getattr(args, "subject_id", "") or "").strip()
    if not subject_id:
        warn("FAIL error=SUBJECT_ID_REQUIRED")
        return 2

    out_dir = str(getattr(args, "out_dir", ".cache/index/ux") or ".cache/index/ux").strip()

    result = run_north_star_ux_build(workspace_root=ws, subject_id=subject_id, out_dir=out_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if str(result.get("status") or "") == "OK" else 2


__all__ = ["run_north_star_ux_build", "cmd_north_star_ux_build"]
