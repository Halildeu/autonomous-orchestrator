from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_FOLD_TR = str.maketrans(
    {
        "c": "c",
        "g": "g",
        "i": "i",
        "o": "o",
        "s": "s",
        "u": "u",
        "C": "c",
        "G": "g",
        "I": "i",
        "O": "o",
        "S": "s",
        "U": "u",
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "c",
        "Ğ": "g",
        "İ": "i",
        "Ö": "o",
        "Ş": "s",
        "Ü": "u",
    }
)


_DEFAULT_POLICY: dict[str, Any] = {
    "version": "v1",
    "synthesis": {
        "mode": "holistic_module_pack.v1",
        "stopwords": [
            "ve",
            "ile",
            "icin",
            "for",
            "the",
            "and",
            "of",
            "to",
            "in",
            "a",
            "an",
            "modul",
            "module",
            "theme",
            "subtheme",
        ],
        "module_blueprints": [
            {
                "module_id": "intake_scope_flow",
                "title_tr": "Talep ve Kapsam Akisi",
                "title_en": "Intake and Scope Flow",
                "module_kind": "intake_scope",
                "keywords": [
                    "intake",
                    "request",
                    "talep",
                    "scope",
                    "kapsam",
                    "acceptance",
                    "requirements",
                    "girdi",
                    "brief",
                ],
                "flow": {
                    "inputs": ["request_text", "constraints", "acceptance_criteria"],
                    "process": ["normalize_intake", "scope_alignment", "priority_seed"],
                    "outputs": ["structured_work_item", "accepted_scope"],
                },
            },
            {
                "module_id": "context_memory_layer",
                "title_tr": "Baglam ve Hafiza Katmani",
                "title_en": "Context and Memory Layer",
                "module_kind": "context_memory",
                "keywords": [
                    "context",
                    "baglam",
                    "memory",
                    "hafiza",
                    "session",
                    "state",
                    "knowledge",
                    "long",
                    "history",
                    "trace",
                    "sync",
                ],
                "flow": {
                    "inputs": ["session_events", "project_context", "subject_catalog"],
                    "process": ["context_pack", "memory_sync", "resume_anchor"],
                    "outputs": ["active_context_pack", "resume_checkpoint"],
                },
            },
            {
                "module_id": "execution_orchestration",
                "title_tr": "Yurutme ve Orkestrasyon",
                "title_en": "Execution and Orchestration",
                "module_kind": "execution_control",
                "keywords": [
                    "execution",
                    "yurutme",
                    "orchestration",
                    "dispatch",
                    "control",
                    "approval",
                    "gate",
                    "workflow",
                    "apply",
                    "run",
                    "otomasyon",
                    "otomat",
                    "onay",
                ],
                "flow": {
                    "inputs": ["approved_work_items", "module_plan", "policy_state"],
                    "process": ["dispatch", "single_gate_checks", "apply_or_skip"],
                    "outputs": ["execution_trace", "operation_status"],
                },
            },
            {
                "module_id": "quality_observability",
                "title_tr": "Kalite ve Gozlemlenebilirlik",
                "title_en": "Quality and Observability",
                "module_kind": "quality_metrics",
                "keywords": [
                    "quality",
                    "metric",
                    "metrics",
                    "kpi",
                    "report",
                    "observability",
                    "monitor",
                    "telemetry",
                    "audit",
                    "risk",
                    "validation",
                ],
                "flow": {
                    "inputs": ["execution_trace", "coverage_data", "quality_rules"],
                    "process": ["contract_checks", "status_report", "evidence_bundle"],
                    "outputs": ["quality_gate_status", "manager_summary"],
                },
            },
            {
                "module_id": "general_delivery_backlog",
                "title_tr": "Genel Teslimat Backlogu",
                "title_en": "General Delivery Backlog",
                "module_kind": "general_delivery",
                "keywords": [],
                "flow": {
                    "inputs": ["subject_catalog", "work_items"],
                    "process": ["modularization", "backlog_ranking", "implementation_plan"],
                    "outputs": ["delivery_backlog", "implementation_sequence"],
                },
            },
        ],
    },
    "quality_gate": {
        "enforce": True,
        "max_module_count": 8,
        "min_coverage_quality": 0.9,
        "require_full_coverage": True,
        "scoring_weights": {
            "pair_weight": 0.55,
            "theme_weight": 0.35,
            "completeness_weight": 0.10,
        },
    },
    "limits": {
        "max_steps": 16,
        "max_plan_bytes": 131072,
        "plan_bytes_over_limit_action": "warn",
    },
}


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()).as_posix())
    except Exception:
        return str(path.resolve().as_posix())


def _policy_rel_label(workspace_root: Path, path: Path) -> str:
    root = _repo_root()
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()).as_posix())
    except Exception:
        try:
            return str(path.resolve().relative_to(root.resolve()).as_posix())
        except Exception:
            return str(path.resolve().as_posix())


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    if parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _safe_float(value: Any, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    if parsed < minimum:
        parsed = minimum
    if parsed > maximum:
        parsed = maximum
    return float(parsed)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _sanitize_token(raw: str, *, fallback: str) -> str:
    text = str(raw or "").strip().lower().translate(_FOLD_TR)
    candidate = re.sub(r"[^a-z0-9_-]+", "_", text).strip("_")
    return candidate or fallback


def _sanitize_plan_id(raw: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "-", str(raw or "").strip()).strip("-")
    if not candidate:
        return "NSP-subject"
    return candidate[:120]


def _policy_paths(workspace_root: Path) -> list[Path]:
    return [
        _repo_root() / "policies" / "policy_north_star_subject_plan.v1.json",
        workspace_root / "policies" / "policy_north_star_subject_plan.v1.json",
        workspace_root / ".cache" / "policy_overrides" / "policy_north_star_subject_plan.override.v1.json",
        workspace_root / ".cache" / "policy_overrides" / "policy_north_star_subject_plan_scoring.override.v1.json",
    ]


def _subject_plan_policy(workspace_root: Path) -> tuple[dict[str, Any], str]:
    policy_obj = deepcopy(_DEFAULT_POLICY)
    applied_sources: list[str] = []
    for path in _policy_paths(workspace_root):
        if not path.exists():
            continue
        try:
            loaded = _load_json(path)
        except Exception:
            continue
        if not isinstance(loaded, dict):
            continue
        policy_obj = _deep_merge(policy_obj, loaded)
        applied_sources.append(_policy_rel_label(workspace_root, path))
    source = ",".join(applied_sources) if applied_sources else "defaults"
    return policy_obj, source


def _effective_limits(policy_obj: dict[str, Any]) -> dict[str, Any]:
    limits = policy_obj.get("limits") if isinstance(policy_obj.get("limits"), dict) else {}
    action_raw = _safe_str(limits.get("plan_bytes_over_limit_action")).lower()
    if action_raw not in {"warn", "fail"}:
        action_raw = "warn"
    return {
        "max_steps": _safe_int(limits.get("max_steps"), 16, minimum=2),
        "max_plan_bytes": _safe_int(limits.get("max_plan_bytes"), 131072, minimum=4096),
        "plan_bytes_over_limit_action": action_raw,
    }


def _effective_quality_gate(policy_obj: dict[str, Any]) -> dict[str, Any]:
    gate = policy_obj.get("quality_gate") if isinstance(policy_obj.get("quality_gate"), dict) else {}
    return {
        "enforce": _safe_bool(gate.get("enforce"), True),
        "max_module_count": _safe_int(gate.get("max_module_count"), 8, minimum=1),
        "min_coverage_quality": _safe_float(gate.get("min_coverage_quality"), 0.9, minimum=0.0, maximum=1.0),
        "require_full_coverage": _safe_bool(gate.get("require_full_coverage"), True),
        "scoring_weights": _effective_scoring_weights(policy_obj),
    }


def _effective_scoring_weights(policy_obj: dict[str, Any]) -> dict[str, float]:
    gate = policy_obj.get("quality_gate") if isinstance(policy_obj.get("quality_gate"), dict) else {}
    raw = gate.get("scoring_weights") if isinstance(gate.get("scoring_weights"), dict) else {}
    pair_weight = _safe_float(raw.get("pair_weight"), 0.55, minimum=0.0, maximum=10.0)
    theme_weight = _safe_float(raw.get("theme_weight"), 0.35, minimum=0.0, maximum=10.0)
    completeness_weight = _safe_float(raw.get("completeness_weight"), 0.10, minimum=0.0, maximum=10.0)

    weight_sum = pair_weight + theme_weight + completeness_weight
    if weight_sum <= 0.0:
        pair_weight, theme_weight, completeness_weight = 0.55, 0.35, 0.10
        weight_sum = 1.0

    return {
        "pair_weight": round(pair_weight / weight_sum, 6),
        "theme_weight": round(theme_weight / weight_sum, 6),
        "completeness_weight": round(completeness_weight / weight_sum, 6),
    }


def _effective_synthesis_mode(policy_obj: dict[str, Any]) -> str:
    synthesis = policy_obj.get("synthesis") if isinstance(policy_obj.get("synthesis"), dict) else {}
    value = _safe_str(synthesis.get("mode"))
    return value or "holistic_module_pack.v1"


def _effective_stopwords(policy_obj: dict[str, Any]) -> set[str]:
    defaults = _DEFAULT_POLICY.get("synthesis", {}).get("stopwords", [])
    synthesis = policy_obj.get("synthesis") if isinstance(policy_obj.get("synthesis"), dict) else {}
    raw = synthesis.get("stopwords")
    source = raw if isinstance(raw, list) else defaults
    out: set[str] = set()
    for item in source:
        text = _safe_str(item).lower().translate(_FOLD_TR)
        if text:
            out.add(text)
    if not out:
        out.update({str(item).strip().lower() for item in defaults if str(item).strip()})
    return out


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _safe_str(item)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _normalize_blueprint(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    module_id = _sanitize_token(raw.get("module_id") or raw.get("id") or f"module_{index:02d}", fallback="")
    if not module_id:
        return None
    title_tr = _safe_str(raw.get("title_tr")) or module_id
    title_en = _safe_str(raw.get("title_en")) or title_tr
    module_kind = _safe_str(raw.get("module_kind")) or "general_delivery"
    keywords = [str(item).strip().lower().translate(_FOLD_TR) for item in _normalize_str_list(raw.get("keywords"))]
    flow = raw.get("flow") if isinstance(raw.get("flow"), dict) else {}
    return {
        "module_id": module_id,
        "title_tr": title_tr,
        "title_en": title_en,
        "module_kind": module_kind,
        "keywords": [item for item in keywords if item],
        "flow": {
            "inputs": _normalize_str_list(flow.get("inputs")),
            "process": _normalize_str_list(flow.get("process")),
            "outputs": _normalize_str_list(flow.get("outputs")),
        },
    }


def _effective_module_blueprints(policy_obj: dict[str, Any]) -> list[dict[str, Any]]:
    synthesis = policy_obj.get("synthesis") if isinstance(policy_obj.get("synthesis"), dict) else {}
    raw_blueprints = synthesis.get("module_blueprints")
    source = raw_blueprints if isinstance(raw_blueprints, list) else _DEFAULT_POLICY.get("synthesis", {}).get("module_blueprints", [])
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(source, start=1):
        if not isinstance(item, dict):
            continue
        normalized = _normalize_blueprint(item, index)
        if normalized is None:
            continue
        module_id = normalized["module_id"]
        if module_id in seen_ids:
            continue
        seen_ids.add(module_id)
        out.append(normalized)

    if "general_delivery_backlog" not in seen_ids:
        fallback = _normalize_blueprint(
            {
                "module_id": "general_delivery_backlog",
                "title_tr": "Genel Teslimat Backlogu",
                "title_en": "General Delivery Backlog",
                "module_kind": "general_delivery",
                "keywords": [],
                "flow": {
                    "inputs": ["subject_catalog", "work_items"],
                    "process": ["modularization", "backlog_ranking", "implementation_plan"],
                    "outputs": ["delivery_backlog", "implementation_sequence"],
                },
            },
            len(out) + 1,
        )
        if isinstance(fallback, dict):
            out.append(fallback)
    return out


def _tokenize(stopwords: set[str], *values: Any) -> set[str]:
    out: set[str] = set()
    for value in values:
        text = _safe_str(value).lower().translate(_FOLD_TR)
        for token in re.findall(r"[a-z0-9]+", text):
            if len(token) < 2:
                continue
            if token in stopwords:
                continue
            out.add(token)
    return out


def _registry_candidates(workspace_root: Path) -> list[Path]:
    return [
        workspace_root / ".cache" / "index" / "mechanisms.registry.v1.json",
        _repo_root() / "registry" / "north_star" / "mechanisms.registry.v1.json",
    ]


def _find_subject(mechanisms: dict[str, Any], subject_id: str) -> dict[str, Any] | None:
    target_raw = _safe_str(subject_id)
    target_key = _sanitize_token(target_raw, fallback="subject")
    subjects = mechanisms.get("subjects") if isinstance(mechanisms.get("subjects"), list) else []
    for item in subjects:
        if not isinstance(item, dict):
            continue
        sid = _safe_str(item.get("subject_id"))
        if sid == target_raw:
            return item
    for item in subjects:
        if not isinstance(item, dict):
            continue
        sid = _safe_str(item.get("subject_id"))
        if _sanitize_token(sid, fallback="subject") == target_key:
            return item
    return None


def _normalize_theme_id(raw_id: Any, *, fallback_prefix: str, index: int) -> str:
    base = _safe_str(raw_id)
    normalized = _sanitize_token(base, fallback="")
    if normalized:
        return normalized
    return f"{fallback_prefix}_{index:02d}"


def _collect_theme_map(subject_obj: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    themes_raw = subject_obj.get("themes") if isinstance(subject_obj.get("themes"), list) else []
    themes: list[dict[str, Any]] = []
    notes: list[str] = []
    seen_theme_ids: set[str] = set()

    for theme_index, theme in enumerate(themes_raw, start=1):
        if not isinstance(theme, dict):
            notes.append(f"theme_invalid_object:{theme_index}")
            continue
        theme_id = _normalize_theme_id(
            theme.get("theme_id") or theme.get("title_en") or theme.get("title_tr"),
            fallback_prefix="theme",
            index=theme_index,
        )
        if theme_id in seen_theme_ids:
            notes.append(f"theme_duplicate_skipped:{theme_id}")
            continue
        seen_theme_ids.add(theme_id)

        subthemes_raw = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        subthemes: list[dict[str, Any]] = []
        seen_sub_ids: set[str] = set()
        for sub_index, subtheme in enumerate(subthemes_raw, start=1):
            if not isinstance(subtheme, dict):
                notes.append(f"subtheme_invalid_object:{theme_id}:{sub_index}")
                continue
            sub_id = _normalize_theme_id(
                subtheme.get("subtheme_id") or subtheme.get("title_en") or subtheme.get("title_tr"),
                fallback_prefix=f"{theme_id}_subtheme",
                index=sub_index,
            )
            if sub_id in seen_sub_ids:
                notes.append(f"subtheme_duplicate_skipped:{theme_id}:{sub_id}")
                continue
            seen_sub_ids.add(sub_id)
            subthemes.append(
                {
                    "subtheme_id": sub_id,
                    "title_tr": _safe_str(subtheme.get("title_tr")) or sub_id,
                    "title_en": _safe_str(subtheme.get("title_en")) or _safe_str(subtheme.get("title_tr")) or sub_id,
                }
            )

        themes.append(
            {
                "theme_id": theme_id,
                "title_tr": _safe_str(theme.get("title_tr")) or theme_id,
                "title_en": _safe_str(theme.get("title_en")) or _safe_str(theme.get("title_tr")) or theme_id,
                "subthemes": subthemes,
            }
        )

    return themes, notes


def _blueprint_maps(blueprints: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    by_id: dict[str, dict[str, Any]] = {}
    order: dict[str, int] = {}
    for index, item in enumerate(blueprints):
        module_id = _safe_str(item.get("module_id"))
        if not module_id:
            continue
        by_id[module_id] = item
        order[module_id] = index
    if "general_delivery_backlog" not in by_id:
        fallback = _normalize_blueprint(
            {
                "module_id": "general_delivery_backlog",
                "title_tr": "Genel Teslimat Backlogu",
                "title_en": "General Delivery Backlog",
                "module_kind": "general_delivery",
                "keywords": [],
                "flow": {"inputs": [], "process": [], "outputs": []},
            },
            len(by_id) + 1,
        )
        if isinstance(fallback, dict):
            by_id["general_delivery_backlog"] = fallback
            order["general_delivery_backlog"] = len(order)
    return by_id, order


def _choose_module(
    *,
    theme: dict[str, Any],
    subtheme: dict[str, Any] | None,
    blueprints: list[dict[str, Any]],
    module_order: dict[str, int],
    stopwords: set[str],
) -> tuple[str, str]:
    theme_tokens = _tokenize(stopwords, theme.get("theme_id"), theme.get("title_tr"), theme.get("title_en"))
    sub_tokens = set()
    if isinstance(subtheme, dict):
        sub_tokens = _tokenize(stopwords, subtheme.get("subtheme_id"), subtheme.get("title_tr"), subtheme.get("title_en"))

    best_module_id = "general_delivery_backlog"
    best_score = -1
    best_order = 10**9
    best_matches: list[str] = []
    for blueprint in blueprints:
        module_id = _safe_str(blueprint.get("module_id"))
        keywords = blueprint.get("keywords") if isinstance(blueprint.get("keywords"), list) else []
        keyword_set = {str(item).strip().lower().translate(_FOLD_TR) for item in keywords if str(item).strip()}
        theme_hits = sorted(theme_tokens & keyword_set)
        sub_hits = sorted(sub_tokens & keyword_set)
        score = len(theme_hits) + (2 * len(sub_hits))
        order = module_order.get(module_id, 10**6)
        if score > best_score or (score == best_score and order < best_order):
            best_module_id = module_id
            best_score = score
            best_order = order
            best_matches = sorted(set(theme_hits + sub_hits))

    if best_score <= 0:
        return "general_delivery_backlog", "fallback_general_module"
    return best_module_id, "keyword_match:" + ",".join(best_matches[:5])


def _ensure_module(
    *,
    module_pool: dict[str, dict[str, Any]],
    module_id: str,
    blueprint_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    existing = module_pool.get(module_id)
    if existing is not None:
        return existing

    blueprint = blueprint_by_id.get(module_id) or blueprint_by_id.get("general_delivery_backlog") or {}
    flow = blueprint.get("flow") if isinstance(blueprint.get("flow"), dict) else {}
    item = {
        "module_id": module_id,
        "module_title_tr": _safe_str(blueprint.get("title_tr")) or module_id,
        "module_title_en": _safe_str(blueprint.get("title_en")) or module_id,
        "module_kind": _safe_str(blueprint.get("module_kind")) or "general_delivery",
        "flow": {
            "inputs": _normalize_str_list(flow.get("inputs")),
            "process": _normalize_str_list(flow.get("process")),
            "outputs": _normalize_str_list(flow.get("outputs")),
        },
        "covered_theme_ids": [],
        "covered_subtheme_pairs": [],
        "source_refs": [],
        "_theme_set": set(),
        "_pair_set": set(),
        "_source_set": set(),
    }
    module_pool[module_id] = item
    return item


def _synthesize_modules(
    *,
    themes: list[dict[str, Any]],
    blueprints: list[dict[str, Any]],
    stopwords: set[str],
    scoring_weights: dict[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    blueprint_by_id, module_order = _blueprint_maps(blueprints)
    module_pool: dict[str, dict[str, Any]] = {}
    assignments: list[dict[str, Any]] = []
    synthesis_notes: list[str] = []
    all_theme_ids: set[str] = set()
    all_pairs: set[tuple[str, str]] = set()
    fallback_count = 0

    for theme in themes:
        theme_id = _safe_str(theme.get("theme_id"))
        if not theme_id:
            continue
        all_theme_ids.add(theme_id)
        subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        if not subthemes:
            module_id, reason = _choose_module(
                theme=theme,
                subtheme=None,
                blueprints=blueprints,
                module_order=module_order,
                stopwords=stopwords,
            )
            if reason == "fallback_general_module":
                fallback_count += 1
            module = _ensure_module(module_pool=module_pool, module_id=module_id, blueprint_by_id=blueprint_by_id)
            module["_theme_set"].add(theme_id)
            source_key = f"{theme_id}::"
            if source_key not in module["_source_set"]:
                module["source_refs"].append(
                    {
                        "theme_id": theme_id,
                        "subtheme_id": "",
                        "theme_title_tr": _safe_str(theme.get("title_tr")),
                        "subtheme_title_tr": "",
                        "assignment_reason": reason,
                    }
                )
                module["_source_set"].add(source_key)
            assignments.append(
                {
                    "module_id": module_id,
                    "theme_id": theme_id,
                    "subtheme_id": "",
                    "reason": reason,
                }
            )
            continue

        for subtheme in subthemes:
            if not isinstance(subtheme, dict):
                continue
            subtheme_id = _safe_str(subtheme.get("subtheme_id"))
            if not subtheme_id:
                continue
            all_pairs.add((theme_id, subtheme_id))
            module_id, reason = _choose_module(
                theme=theme,
                subtheme=subtheme,
                blueprints=blueprints,
                module_order=module_order,
                stopwords=stopwords,
            )
            if reason == "fallback_general_module":
                fallback_count += 1
            module = _ensure_module(module_pool=module_pool, module_id=module_id, blueprint_by_id=blueprint_by_id)
            module["_theme_set"].add(theme_id)
            pair_key = f"{theme_id}::{subtheme_id}"
            if pair_key not in module["_pair_set"]:
                module["covered_subtheme_pairs"].append({"theme_id": theme_id, "subtheme_id": subtheme_id})
                module["_pair_set"].add(pair_key)
            if pair_key not in module["_source_set"]:
                module["source_refs"].append(
                    {
                        "theme_id": theme_id,
                        "subtheme_id": subtheme_id,
                        "theme_title_tr": _safe_str(theme.get("title_tr")),
                        "subtheme_title_tr": _safe_str(subtheme.get("title_tr")),
                        "assignment_reason": reason,
                    }
                )
                module["_source_set"].add(pair_key)
            assignments.append(
                {
                    "module_id": module_id,
                    "theme_id": theme_id,
                    "subtheme_id": subtheme_id,
                    "reason": reason,
                }
            )

    modules: list[dict[str, Any]] = []
    for module_id in sorted(module_pool.keys(), key=lambda item: (module_order.get(item, 10**6), item)):
        module = module_pool.get(module_id)
        if module is None:
            continue
        module["covered_theme_ids"] = sorted(module.pop("_theme_set"))
        module["covered_subtheme_pairs"] = sorted(
            module.get("covered_subtheme_pairs", []),
            key=lambda item: (str(item.get("theme_id") or ""), str(item.get("subtheme_id") or "")),
        )
        module["source_refs"] = sorted(
            module.get("source_refs", []),
            key=lambda item: (str(item.get("theme_id") or ""), str(item.get("subtheme_id") or "")),
        )
        module["coverage"] = {
            "theme_count": len(module["covered_theme_ids"]),
            "subtheme_pair_count": len(module["covered_subtheme_pairs"]),
        }
        module.pop("_pair_set", None)
        module.pop("_source_set", None)
        modules.append(module)

    assignments = sorted(
        assignments,
        key=lambda item: (
            str(item.get("module_id") or ""),
            str(item.get("theme_id") or ""),
            str(item.get("subtheme_id") or ""),
        ),
    )

    covered_theme_ids: set[str] = set()
    covered_pairs: set[tuple[str, str]] = set()
    for assignment in assignments:
        theme_id = _safe_str(assignment.get("theme_id"))
        subtheme_id = _safe_str(assignment.get("subtheme_id"))
        if theme_id:
            covered_theme_ids.add(theme_id)
        if theme_id and subtheme_id:
            covered_pairs.add((theme_id, subtheme_id))

    total_theme_count = len(all_theme_ids)
    total_pair_count = len(all_pairs)
    covered_theme_count = len(covered_theme_ids)
    covered_pair_count = len(covered_pairs)
    theme_ratio = 1.0 if total_theme_count == 0 else (covered_theme_count / max(1, total_theme_count))
    pair_ratio = 1.0 if total_pair_count == 0 else (covered_pair_count / max(1, total_pair_count))
    completeness = 1.0 if (covered_theme_count == total_theme_count and covered_pair_count == total_pair_count) else 0.0
    pair_weight = _safe_float(scoring_weights.get("pair_weight"), 0.55, minimum=0.0, maximum=1.0)
    theme_weight = _safe_float(scoring_weights.get("theme_weight"), 0.35, minimum=0.0, maximum=1.0)
    completeness_weight = _safe_float(scoring_weights.get("completeness_weight"), 0.10, minimum=0.0, maximum=1.0)
    quality_score = (pair_weight * pair_ratio) + (theme_weight * theme_ratio) + (completeness_weight * completeness)

    uncovered_theme_ids = sorted(all_theme_ids - covered_theme_ids)
    uncovered_pairs = sorted(all_pairs - covered_pairs)
    coverage = {
        "theme_count": total_theme_count,
        "subtheme_count": total_pair_count,
        "theme_subtheme_pair_count": total_pair_count,
        "covered_theme_ids": sorted(covered_theme_ids),
        "covered_theme_subtheme_pairs": [
            {"theme_id": theme_id, "subtheme_id": subtheme_id} for theme_id, subtheme_id in sorted(covered_pairs)
        ],
        "uncovered_theme_ids": uncovered_theme_ids,
        "uncovered_theme_subtheme_pairs": [
            {"theme_id": theme_id, "subtheme_id": subtheme_id} for theme_id, subtheme_id in uncovered_pairs
        ],
        "coverage_theme_ratio": round(theme_ratio, 6),
        "coverage_subtheme_ratio": round(pair_ratio, 6),
        "coverage_quality_score": round(quality_score, 6),
        "scoring_weights": {
            "pair_weight": pair_weight,
            "theme_weight": theme_weight,
            "completeness_weight": completeness_weight,
        },
        "is_complete": (not uncovered_theme_ids and not uncovered_pairs),
    }

    if fallback_count > 0:
        synthesis_notes.append(f"module_fallback_count={fallback_count}")
    if len(modules) == 0:
        synthesis_notes.append("module_synthesis_empty")
    return modules, assignments, coverage, synthesis_notes


def _evaluate_quality_gate(
    *,
    coverage: dict[str, Any],
    module_count: int,
    quality_gate_policy: dict[str, Any],
) -> dict[str, Any]:
    enforce = _safe_bool(quality_gate_policy.get("enforce"), True)
    max_module_count = _safe_int(quality_gate_policy.get("max_module_count"), 8, minimum=1)
    min_quality = _safe_float(quality_gate_policy.get("min_coverage_quality"), 0.9, minimum=0.0, maximum=1.0)
    require_full = _safe_bool(quality_gate_policy.get("require_full_coverage"), True)
    scoring_weights = (
        quality_gate_policy.get("scoring_weights")
        if isinstance(quality_gate_policy.get("scoring_weights"), dict)
        else {}
    )

    score = _safe_float(coverage.get("coverage_quality_score"), 0.0, minimum=0.0, maximum=1.0)
    is_complete = _safe_bool(coverage.get("is_complete"), False)
    reasons: list[str] = []
    if module_count > max_module_count:
        reasons.append(f"module_count_exceeded:{module_count}>{max_module_count}")
    if score < min_quality:
        reasons.append(f"coverage_quality_below_min:{score:.4f}<{min_quality:.4f}")
    if require_full and not is_complete:
        reasons.append("full_coverage_required")

    status = "PASS" if not reasons else "FAIL"
    enforced_result = status == "PASS" or not enforce
    run_status = "OK" if enforced_result else "WARN"
    return {
        "status": status,
        "enforced": enforce,
        "enforced_result": enforced_result,
        "run_status": run_status,
        "thresholds": {
            "max_module_count": max_module_count,
            "min_coverage_quality": min_quality,
            "require_full_coverage": require_full,
            "scoring_weights": {
                "pair_weight": _safe_float(scoring_weights.get("pair_weight"), 0.55, minimum=0.0, maximum=1.0),
                "theme_weight": _safe_float(scoring_weights.get("theme_weight"), 0.35, minimum=0.0, maximum=1.0),
                "completeness_weight": _safe_float(
                    scoring_weights.get("completeness_weight"), 0.10, minimum=0.0, maximum=1.0
                ),
            },
        },
        "actuals": {
            "module_count": module_count,
            "coverage_quality_score": score,
            "coverage_complete": is_complete,
        },
        "reasons": reasons,
    }


def _build_steps(
    *,
    subject_id: str,
    modules: list[dict[str, Any]],
    max_steps: int,
) -> tuple[list[dict[str, Any]], bool]:
    steps: list[dict[str, Any]] = [
        {
            "step_id": "S01",
            "type": "subject_snapshot",
            "ops": [
                f"north-star-theme-bootstrap --subject-id {subject_id} --approve",
                f"north-star-theme-consult --subject-id {subject_id}",
            ],
            "expected_outputs": [
                ".cache/index/mechanisms.registry.v1.json",
                ".cache/index/mechanisms.suggestions.v1.json",
            ],
            "notes": ["bridge=north_star_subject_to_plan", "program_led"],
        }
    ]
    truncated = False
    step_no = 2
    for module in modules:
        if len(steps) >= max_steps:
            truncated = True
            break
        module_id = _safe_str(module.get("module_id"))
        module_kind = _safe_str(module.get("module_kind"))
        coverage = module.get("coverage") if isinstance(module.get("coverage"), dict) else {}
        theme_count = int(coverage.get("theme_count") or 0)
        sub_count = int(coverage.get("subtheme_pair_count") or 0)
        holistic_merge = "true" if (theme_count > 1 or sub_count > 1) else "false"
        steps.append(
            {
                "step_id": f"S{step_no:02d}",
                "type": "module_delivery",
                "ops": [
                    (
                        "context-router-check --kind feature --impact-scope workspace-only "
                        f"--mode report --text module:{module_id}"
                    ),
                    "work-intake-build",
                    "work-intake-check",
                    "planner-build-plan --mode plan_first --out latest",
                ],
                "expected_outputs": [
                    ".cache/index/work_intake.v1.json",
                    ".cache/reports/system_status.v1.json",
                    ".cache/index/plans/latest.v1.json",
                ],
                "notes": [
                    f"module_id={module_id}",
                    f"module_kind={module_kind}",
                    f"theme_count={theme_count}",
                    f"subtheme_pair_count={sub_count}",
                    f"holistic_merge={holistic_merge}",
                ],
            }
        )
        step_no += 1

    return steps, truncated


def _write_summary(
    *,
    workspace_root: Path,
    plan: dict[str, Any],
    plan_rel: str,
    subject_id: str,
    themes: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> str:
    summary_path = workspace_root / ".cache" / "reports" / "north_star_subject_plan_summary.v1.md"
    decision = plan.get("decision") if isinstance(plan.get("decision"), dict) else {}
    coverage = decision.get("coverage") if isinstance(decision.get("coverage"), dict) else {}
    quality_gate = decision.get("quality_gate") if isinstance(decision.get("quality_gate"), dict) else {}
    thresholds = quality_gate.get("thresholds") if isinstance(quality_gate.get("thresholds"), dict) else {}
    actuals = quality_gate.get("actuals") if isinstance(quality_gate.get("actuals"), dict) else {}
    scoring_weights = thresholds.get("scoring_weights") if isinstance(thresholds.get("scoring_weights"), dict) else {}

    lines: list[str] = [
        "# North Star Subject Plan Summary",
        "",
        f"- plan_id: {plan.get('plan_id', '')}",
        f"- created_at: {plan.get('created_at', '')}",
        f"- subject_id: {subject_id}",
        f"- plan_path: {plan_rel}",
        f"- theme_count: {coverage.get('theme_count', 0)}",
        f"- subtheme_count: {coverage.get('subtheme_count', 0)}",
        f"- module_count: {decision.get('module_count', 0)}",
        f"- coverage_complete: {coverage.get('is_complete', False)}",
        f"- coverage_quality_score: {coverage.get('coverage_quality_score', 0)}",
        "",
        "## Quality Gate",
        f"- status: {quality_gate.get('status', 'UNKNOWN')}",
        f"- enforced: {quality_gate.get('enforced', False)}",
        f"- enforced_result: {quality_gate.get('enforced_result', False)}",
        f"- max_module_count: {thresholds.get('max_module_count', '')}",
        f"- min_coverage_quality: {thresholds.get('min_coverage_quality', '')}",
        f"- require_full_coverage: {thresholds.get('require_full_coverage', '')}",
        f"- scoring_pair_weight: {scoring_weights.get('pair_weight', '')}",
        f"- scoring_theme_weight: {scoring_weights.get('theme_weight', '')}",
        f"- scoring_completeness_weight: {scoring_weights.get('completeness_weight', '')}",
        f"- actual_module_count: {actuals.get('module_count', '')}",
        f"- actual_coverage_quality_score: {actuals.get('coverage_quality_score', '')}",
        "",
        "## Theme/Subtheme Catalog",
    ]

    if not themes:
        lines.append("- (none)")
    for theme in themes:
        theme_id = _safe_str(theme.get("theme_id"))
        subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        sub_ids = ", ".join(_safe_str(item.get("subtheme_id")) for item in subthemes if isinstance(item, dict)) or "-"
        lines.append(f"- {theme_id}: {sub_ids}")

    lines.append("")
    lines.append("## Module Plan")
    if not modules:
        lines.append("- (none)")
    for module in modules:
        module_id = _safe_str(module.get("module_id"))
        coverage_item = module.get("coverage") if isinstance(module.get("coverage"), dict) else {}
        theme_ids = module.get("covered_theme_ids") if isinstance(module.get("covered_theme_ids"), list) else []
        pairs = module.get("covered_subtheme_pairs") if isinstance(module.get("covered_subtheme_pairs"), list) else []
        pair_labels = ", ".join(
            f"{_safe_str(item.get('theme_id'))}/{_safe_str(item.get('subtheme_id'))}"
            for item in pairs
            if isinstance(item, dict)
        )
        lines.append(
            (
                f"- {module_id}: themes={','.join(str(x) for x in theme_ids)} "
                f"subtheme_pairs={coverage_item.get('subtheme_pair_count', 0)} "
                f"[{pair_labels or '-'}]"
            )
        )

    lines.append("")
    lines.append("## Coverage")
    lines.append(f"- covered_theme_ids: {', '.join(coverage.get('covered_theme_ids', [])) or '-'}")
    uncovered_themes = coverage.get("uncovered_theme_ids") if isinstance(coverage.get("uncovered_theme_ids"), list) else []
    lines.append(f"- uncovered_theme_ids: {', '.join(str(x) for x in uncovered_themes) or '-'}")
    uncovered_pairs = (
        coverage.get("uncovered_theme_subtheme_pairs")
        if isinstance(coverage.get("uncovered_theme_subtheme_pairs"), list)
        else []
    )
    if uncovered_pairs:
        pair_text = ", ".join(
            f"{_safe_str(item.get('theme_id'))}/{_safe_str(item.get('subtheme_id'))}"
            for item in uncovered_pairs
            if isinstance(item, dict)
        )
    else:
        pair_text = "-"
    lines.append(f"- uncovered_theme_subtheme_pairs: {pair_text}")

    lines.append("")
    lines.append("## Steps")
    for step in plan.get("steps", []) if isinstance(plan.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        ops = step.get("ops") if isinstance(step.get("ops"), list) else []
        lines.append(f"- {step.get('step_id', '')}: {step.get('type', '')} -> {', '.join(str(op) for op in ops)}")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _rel_path(workspace_root, summary_path)


def _validate_subject_plan_contract(
    *,
    workspace_root: Path,
    plan_obj: dict[str, Any],
) -> tuple[bool, list[str], str]:
    schema_path = _repo_root() / "schemas" / "north-star-subject-plan.schema.v1.json"
    schema_label = _policy_rel_label(workspace_root, schema_path)
    if not schema_path.exists():
        return False, ["contract_schema_missing"], schema_label

    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return False, ["contract_validator_missing:jsonschema"], schema_label

    try:
        schema_obj = _load_json(schema_path)
    except Exception:
        return False, ["contract_schema_invalid_json"], schema_label
    if not isinstance(schema_obj, dict):
        return False, ["contract_schema_invalid_object"], schema_label

    try:
        validator = Draft202012Validator(schema_obj)
    except Exception:
        return False, ["contract_schema_invalid_definition"], schema_label

    errors = sorted(validator.iter_errors(plan_obj), key=lambda err: list(err.path))
    if not errors:
        return True, ["contract_validation=pass"], schema_label

    notes: list[str] = []
    for err in errors[:10]:
        path = "/".join(str(part) for part in err.path) or "$"
        message = str(err.message).replace("\n", " ").strip()
        notes.append(f"contract_error:{path}:{message}")
    if len(errors) > 10:
        notes.append(f"contract_error_truncated:{len(errors)}")
    return False, notes, schema_label


def run_north_star_subject_to_plan(
    *,
    workspace_root: Path,
    subject_id: str,
    out: str = "latest",
    mode: str = "plan_first",
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    normalized_subject = _safe_str(subject_id)
    if not normalized_subject:
        return {
            "status": "WARN",
            "error_code": "SUBJECT_ID_REQUIRED",
            "plan_id": "",
            "plan_path": "",
            "summary_path": "",
            "notes": ["subject_id_missing"],
        }

    policy_obj, policy_source = _subject_plan_policy(workspace_root)
    limits = _effective_limits(policy_obj)
    quality_gate_policy = _effective_quality_gate(policy_obj)
    synthesis_mode = _effective_synthesis_mode(policy_obj)
    stopwords = _effective_stopwords(policy_obj)
    blueprints = _effective_module_blueprints(policy_obj)

    registry_obj: dict[str, Any] | None = None
    registry_path: Path | None = None
    invalid_candidates: list[str] = []
    for candidate in _registry_candidates(workspace_root):
        if not candidate.exists():
            continue
        try:
            loaded = _load_json(candidate)
        except Exception:
            invalid_candidates.append(str(candidate))
            continue
        if not isinstance(loaded, dict):
            invalid_candidates.append(str(candidate))
            continue
        registry_obj = loaded
        registry_path = candidate
        break

    if registry_obj is None or registry_path is None:
        notes = ["mechanisms_registry_not_found"] + [f"invalid_registry_candidate={p}" for p in invalid_candidates]
        return {
            "status": "IDLE",
            "error_code": "MECHANISMS_REGISTRY_NOT_FOUND",
            "plan_id": "",
            "plan_path": "",
            "summary_path": "",
            "notes": notes,
        }

    subject_obj = _find_subject(registry_obj, normalized_subject)
    if subject_obj is None:
        subjects = registry_obj.get("subjects") if isinstance(registry_obj.get("subjects"), list) else []
        available = sorted(
            {
                _safe_str(item.get("subject_id"))
                for item in subjects
                if isinstance(item, dict) and _safe_str(item.get("subject_id"))
            }
        )
        return {
            "status": "IDLE",
            "error_code": "SUBJECT_NOT_FOUND",
            "plan_id": "",
            "plan_path": "",
            "summary_path": "",
            "notes": [
                f"registry_path={_rel_path(workspace_root, registry_path)}",
                f"subject_id={normalized_subject}",
                "available_subject_ids=" + ",".join(available[:20]),
            ],
        }

    themes, collect_notes = _collect_theme_map(subject_obj)
    theme_ids: list[str] = []
    subtheme_ids: list[str] = []
    theme_subtheme_pairs: list[dict[str, str]] = []
    for theme in themes:
        theme_id = _safe_str(theme.get("theme_id"))
        if theme_id:
            theme_ids.append(theme_id)
        subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        for sub in subthemes:
            if not isinstance(sub, dict):
                continue
            sub_id = _safe_str(sub.get("subtheme_id"))
            if sub_id:
                subtheme_ids.append(sub_id)
                theme_subtheme_pairs.append({"theme_id": theme_id, "subtheme_id": sub_id})

    modules, module_assignments, coverage, synthesis_notes = _synthesize_modules(
        themes=themes,
        blueprints=blueprints,
        stopwords=stopwords,
        scoring_weights=quality_gate_policy.get("scoring_weights", {}),
    )
    quality_gate_result = _evaluate_quality_gate(
        coverage=coverage,
        module_count=len(modules),
        quality_gate_policy=quality_gate_policy,
    )

    requested_out = _safe_str(out).lower()
    if requested_out in {"", "latest"}:
        plan_id = f"NSP-{_sanitize_token(normalized_subject, fallback='subject')}"
    else:
        plan_id = _sanitize_plan_id(out)

    plan_dir = workspace_root / ".cache" / "index" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{plan_id}.v1.json"
    latest_path = plan_dir / "latest.v1.json"

    steps, truncated = _build_steps(
        subject_id=normalized_subject,
        modules=modules,
        max_steps=limits["max_steps"],
    )
    subject_title_tr = _safe_str(subject_obj.get("subject_title_tr"))
    subject_title_en = _safe_str(subject_obj.get("subject_title_en"))
    module_ids = [_safe_str(module.get("module_id")) for module in modules if _safe_str(module.get("module_id"))]
    plan_obj: dict[str, Any] = {
        "version": "v1",
        "plan_id": plan_id,
        "created_at": _now_iso8601(),
        "scope": {
            "workspace_root": str(workspace_root),
            "mode": _safe_str(mode) or "plan_first",
            "subject_id": normalized_subject,
            "subject_title_tr": subject_title_tr,
            "subject_title_en": subject_title_en,
            "synthesis_mode": synthesis_mode,
        },
        "inputs": {
            "mechanisms_registry_path": _rel_path(workspace_root, registry_path),
            "subject_id": normalized_subject,
            "theme_count": len(theme_ids),
            "subtheme_count": len(subtheme_ids),
        },
        "decision": {
            "why": [
                "north_star_subject_selected",
                "all_theme_subtheme_catalog_considered",
                "holistic_module_synthesis_applied",
                "standardized_plan_json_generated",
            ],
            "synthesis_mode": synthesis_mode,
            "selected_subject_id": normalized_subject,
            "selected_theme_ids": theme_ids,
            "selected_subtheme_ids": subtheme_ids,
            "selected_theme_subtheme_pairs": theme_subtheme_pairs,
            "module_count": len(module_ids),
            "module_ids": module_ids,
            "module_assignments": module_assignments,
            "coverage": coverage,
            "quality_gate": quality_gate_result,
        },
        "steps": steps,
        "modules": modules,
        "evidence_paths": [
            _rel_path(workspace_root, plan_path),
            _rel_path(workspace_root, latest_path),
            ".cache/reports/north_star_subject_plan_summary.v1.md",
        ],
        "notes": [
            "PROGRAM_LED=true",
            "bridge=north_star_subject_to_plan",
            f"mode={_safe_str(mode) or 'plan_first'}",
            f"synthesis_mode={synthesis_mode}",
            f"theme_count={len(theme_ids)}",
            f"subtheme_count={len(subtheme_ids)}",
            f"module_count={len(module_ids)}",
            f"coverage_complete={coverage.get('is_complete', False)}",
            f"coverage_quality_score={coverage.get('coverage_quality_score', 0)}",
            f"quality_gate_status={quality_gate_result.get('status', 'UNKNOWN')}",
            f"policy_source={policy_source}",
        ]
        + collect_notes
        + synthesis_notes,
        "subject_catalog": {
            "subject_id": normalized_subject,
            "subject_title_tr": subject_title_tr,
            "subject_title_en": subject_title_en,
            "themes": themes,
        },
    }
    if truncated:
        plan_obj["notes"].append("step_limit_applied")

    contract_ok, contract_notes, contract_schema = _validate_subject_plan_contract(
        workspace_root=workspace_root,
        plan_obj=plan_obj,
    )
    plan_obj["notes"].append(f"contract_schema={contract_schema}")
    if contract_ok:
        plan_obj["notes"].extend(contract_notes)
    else:
        fail_notes = (
            [str(item) for item in plan_obj.get("notes", []) if isinstance(item, str)]
            + ["contract_validation=fail"]
            + contract_notes
        )
        return {
            "status": "WARN",
            "error_code": "CONTRACT_VALIDATION_FAILED",
            "plan_id": plan_id,
            "plan_path": "",
            "summary_path": "",
            "theme_count": len(theme_ids),
            "subtheme_count": len(subtheme_ids),
            "module_count": len(module_ids),
            "coverage_complete": bool(coverage.get("is_complete")),
            "coverage_quality_score": coverage.get("coverage_quality_score"),
            "quality_gate_status": quality_gate_result.get("status") if isinstance(quality_gate_result, dict) else "UNKNOWN",
            "contract_validation_status": "FAIL",
            "notes": sorted({item for item in fail_notes if item}),
        }

    dumped = _dump_json(plan_obj)
    max_bytes = limits["max_plan_bytes"]
    dumped_bytes = len(dumped.encode("utf-8"))
    if dumped_bytes > max_bytes:
        bytes_action = _safe_str(limits.get("plan_bytes_over_limit_action")).lower() or "warn"
        plan_obj["notes"].append("plan_bytes_over_limit")
        plan_obj["notes"].append(f"plan_bytes={dumped_bytes}")
        plan_obj["notes"].append(f"plan_bytes_limit={max_bytes}")
        plan_obj["notes"].append(f"plan_bytes_over_limit_action={bytes_action}")
        if bytes_action == "fail":
            return {
                "status": "WARN",
                "error_code": "PLAN_BYTES_OVER_LIMIT",
                "plan_id": plan_id,
                "plan_path": "",
                "summary_path": "",
                "theme_count": len(theme_ids),
                "subtheme_count": len(subtheme_ids),
                "module_count": len(module_ids),
                "coverage_complete": bool(coverage.get("is_complete")),
                "coverage_quality_score": coverage.get("coverage_quality_score"),
                "quality_gate_status": (
                    quality_gate_result.get("status") if isinstance(quality_gate_result, dict) else "UNKNOWN"
                ),
                "contract_validation_status": "PASS",
                "notes": sorted({str(item) for item in plan_obj.get("notes", []) if isinstance(item, str) and item}),
            }
        dumped = _dump_json(plan_obj)

    plan_path.write_text(dumped, encoding="utf-8")
    latest_path.write_text(dumped, encoding="utf-8")
    plan_rel = _rel_path(workspace_root, plan_path)
    summary_rel = _write_summary(
        workspace_root=workspace_root,
        plan=plan_obj,
        plan_rel=plan_rel,
        subject_id=normalized_subject,
        themes=themes,
        modules=modules,
    )

    final_status = quality_gate_result.get("run_status") if isinstance(quality_gate_result, dict) else "WARN"
    final_error = None
    if final_status != "OK":
        final_error = "QUALITY_BAR_NOT_MET"
    return {
        "status": final_status,
        "error_code": final_error,
        "plan_id": plan_id,
        "plan_path": plan_rel,
        "summary_path": summary_rel,
        "theme_count": len(theme_ids),
        "subtheme_count": len(subtheme_ids),
        "module_count": len(module_ids),
        "coverage_complete": bool(coverage.get("is_complete")),
        "coverage_quality_score": coverage.get("coverage_quality_score"),
        "quality_gate_status": quality_gate_result.get("status") if isinstance(quality_gate_result, dict) else "UNKNOWN",
        "contract_validation_status": "PASS",
        "notes": sorted({str(item) for item in plan_obj.get("notes", []) if isinstance(item, str) and item}),
    }
