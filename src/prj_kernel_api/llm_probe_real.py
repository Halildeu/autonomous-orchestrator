"""Real probe: runs llm_live_probe, then reconciles workspace probe state + catalog (no secrets)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.prj_kernel_api.llm_live_probe import run_live_probe
from src.prj_kernel_api.provider_guardrails import load_guardrails, provider_settings

PROVIDER_MAP_REPO_PATH = "docs/OPERATIONS/llm_provider_map.v1.json"
PROVIDER_MAP_WS_PATH = ".cache/index/llm_provider_map.v1.json"
CLASS_REGISTRY_REPO_PATH = "docs/OPERATIONS/llm_class_registry.v1.json"
CLASS_REGISTRY_WS_PATH = ".cache/index/llm_class_registry.v1.json"
STATE_PATH = ".cache/state/llm_probe_state.v1.json"
CATALOG_PATH = ".cache/index/llm_probe_catalog.v1.json"
LIVE_REPORT_PATH = ".cache/reports/llm_live_probe.v1.json"
ALLOWLIST_REPORT_PATH = ".cache/reports/llm_allowlist_probe.v0.1.json"
ALLOWLIST_LATEST_PATH = ".cache/reports/llm_allowlist_probe_run.latest.json"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _resolve_workspace_root(repo_root: Path, workspace_root: str | Path | None) -> Path:
    if isinstance(workspace_root, Path):
        ws_root = workspace_root
    elif isinstance(workspace_root, str) and workspace_root.strip():
        ws_root = Path(workspace_root)
    else:
        ws_root = repo_root / ".cache" / "ws_customer_default"
    if not ws_root.is_absolute():
        ws_root = (repo_root / ws_root).resolve()
    return ws_root


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_optional(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _deepcopy(obj: Any) -> Any:
    return json.loads(json.dumps(obj, ensure_ascii=False))


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _class_filter_rule_tokens() -> Dict[str, Dict[str, List[str]]]:
    common_text_exclude = [
        "embedding",
        "image",
        "dall-e",
        "sora",
        "audio",
        "realtime",
        "moderation",
        "vision",
        "ocr",
        "qvq",
        "video",
    ]
    return {
        "FAST_TEXT": {"include": [], "exclude": list(common_text_exclude)},
        "BALANCED_TEXT": {"include": [], "exclude": list(common_text_exclude)},
        "GOVERNANCE_ASSURANCE": {"include": [], "exclude": list(common_text_exclude)},
        "REASONING_TEXT": {"include": [], "exclude": list(common_text_exclude)},
        "IMAGE_GEN": {"include": ["image", "dall-e", "sora", "img"], "exclude": ["realtime", "audio", "embedding"]},
        "VIDEO_GEN": {"include": ["sora", "video"], "exclude": ["image", "audio", "embedding"]},
        "AUDIO": {"include": ["audio", "tts", "transcribe"], "exclude": ["image", "video", "embedding"]},
        "REALTIME_STREAMING": {"include": ["realtime", "stream"], "exclude": []},
        "OCR_DOC": {"include": ["ocr"], "exclude": []},
        "VISION_MM": {"include": ["vision", "vl"], "exclude": ["ocr"]},
        "VISION_REASONING": {"include": ["qvq", "vision", "reason"], "exclude": []},
        "EMBEDDINGS": {"include": ["embedding"], "exclude": []},
        "MODERATION_SAFETY": {"include": ["moderation"], "exclude": []},
        "DEEP_RESEARCH": {"include": ["deep-research", "research"], "exclude": []},
        "CODE_AGENTIC": {"include": ["codex", "code"], "exclude": []},
    }


def _filter_models_for_class(class_id: str, models: List[str]) -> List[str]:
    items = [m for m in models if isinstance(m, str) and m.strip()]
    if not items:
        return []

    rules = _class_filter_rule_tokens()
    rule = rules.get(str(class_id or "").strip().upper())
    if not rule:
        return items

    include_tokens = [t for t in rule.get("include", []) if isinstance(t, str) and t]
    exclude_tokens = [t for t in rule.get("exclude", []) if isinstance(t, str) and t]

    filtered: List[str] = []
    for model_id in items:
        name = model_id.lower()
        include_hit = (not include_tokens) or any(tok in name for tok in include_tokens)
        exclude_hit = any(tok in name for tok in exclude_tokens)
        if include_hit and not exclude_hit:
            filtered.append(model_id)

    if filtered:
        return filtered
    return [] if include_tokens else items


def _load_class_ids(*, repo_root: Path, ws_root: Path, provider_map: Dict[str, Any]) -> List[str]:
    ws_path = ws_root / CLASS_REGISTRY_WS_PATH
    repo_path = repo_root / CLASS_REGISTRY_REPO_PATH
    registry = _load_json_optional(ws_path) or (_load_json(repo_path) if repo_path.exists() else {})
    ids: List[str] = []
    classes = registry.get("classes", [])
    if isinstance(classes, list):
        for item in classes:
            if not isinstance(item, dict):
                continue
            cid = item.get("class_id")
            if isinstance(cid, str) and cid.strip():
                ids.append(cid.strip())
    pm_classes = provider_map.get("classes", {})
    if isinstance(pm_classes, dict):
        ids.extend([k for k in pm_classes.keys() if isinstance(k, str) and k.strip()])
    return _dedupe_keep_order(ids)


def _reset_stage_fail_closed(stage: Any) -> str:
    s = str(stage or "").strip().lower()
    if s in {"deprecated", "blocked"}:
        return s
    return "candidate"


def _model_obj_for_provider_map(*, model_id: str, base_obj: Dict[str, Any] | None) -> Dict[str, Any]:
    notes = base_obj.get("notes") if isinstance(base_obj, dict) else None
    stage = base_obj.get("stage") if isinstance(base_obj, dict) else None
    out: Dict[str, Any] = {
        "model_id": model_id,
        "stage": _reset_stage_fail_closed(stage),
        "verified_at": None,
        "probe_status": "unknown",
        "probe_last_at": None,
        "probe_latency_ms_p95": None,
        "probe_error_code": None,
    }
    if isinstance(notes, str) and notes.strip():
        out["notes"] = notes.strip()
    return out


def _expand_provider_map(
    *,
    base_provider_map: Dict[str, Any],
    guardrails: Dict[str, Any],
    class_ids: List[str],
    now: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "policy_version": base_provider_map.get("policy_version") or "v0.1",
        "generated_at": now,
        "probe": _deepcopy(base_provider_map.get("probe")) if isinstance(base_provider_map.get("probe"), dict) else {},
        "classes": {},
    }

    base_classes = base_provider_map.get("classes", {}) if isinstance(base_provider_map.get("classes"), dict) else {}
    guard_providers = guardrails.get("providers", {}) if isinstance(guardrails.get("providers"), dict) else {}
    provider_ids: List[str] = [pid for pid in guard_providers.keys() if isinstance(pid, str) and pid.strip()]
    for cls_data in base_classes.values():
        providers = cls_data.get("providers", {}) if isinstance(cls_data, dict) else {}
        if isinstance(providers, dict):
            provider_ids.extend([pid for pid in providers.keys() if isinstance(pid, str) and pid.strip()])
    provider_ids = _dedupe_keep_order(sorted(set(provider_ids)))

    for cls_id in class_ids:
        if not isinstance(cls_id, str) or not cls_id.strip():
            continue
        cls_id = cls_id.strip()

        base_cls = base_classes.get(cls_id, {}) if isinstance(base_classes.get(cls_id), dict) else {}
        base_providers = base_cls.get("providers", {}) if isinstance(base_cls.get("providers"), dict) else {}

        cls_out: Dict[str, Any] = {"providers": {}}
        for prov_id in provider_ids:
            settings = provider_settings(guardrails, prov_id)
            allow_models = settings.get("allow_models", [])
            if not isinstance(allow_models, list):
                allow_models = []
            allow_models = [str(m).strip() for m in allow_models if isinstance(m, str) and m.strip()]
            default_model = settings.get("default_model")
            default_model = default_model.strip() if isinstance(default_model, str) and default_model.strip() else None
            if "*" in allow_models:
                allow_models = [default_model] if default_model else []

            models_filtered = _filter_models_for_class(cls_id, allow_models)
            if not models_filtered:
                continue

            base_prov = base_providers.get(prov_id, {}) if isinstance(base_providers.get(prov_id), dict) else {}
            base_models = base_prov.get("models", []) if isinstance(base_prov.get("models"), list) else []
            base_by_id: Dict[str, Dict[str, Any]] = {}
            for it in base_models:
                if not isinstance(it, dict):
                    continue
                mid = it.get("model_id")
                if isinstance(mid, str) and mid:
                    base_by_id[mid] = it

            pinned = base_prov.get("pinned_model_id")
            pinned = pinned.strip() if isinstance(pinned, str) and pinned.strip() else None
            if pinned not in models_filtered:
                if default_model in models_filtered:
                    pinned = default_model
                else:
                    pinned = models_filtered[0]

            preferred = base_prov.get("preferred_candidate_model_id")
            preferred = preferred.strip() if isinstance(preferred, str) and preferred.strip() else None
            if preferred not in models_filtered or preferred == pinned:
                preferred = None

            ordered_models: List[str] = [pinned] + [m for m in models_filtered if m != pinned]
            ordered_models = _dedupe_keep_order(ordered_models)

            cls_out["providers"][prov_id] = {
                "pinned_model_id": pinned,
                "preferred_candidate_model_id": preferred,
                "models": [_model_obj_for_provider_map(model_id=m, base_obj=base_by_id.get(m)) for m in ordered_models],
            }

        out["classes"][cls_id] = cls_out

    return out


def _live_results_by_provider_model(probe_report: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for item in probe_report.get("providers", []):
        if not isinstance(item, dict):
            continue
        pid = item.get("provider_id")
        model_id = item.get("model")
        if not isinstance(pid, str) or not pid:
            continue
        if not isinstance(model_id, str) or not model_id:
            continue
        out.setdefault(pid, {})[model_id] = item
    return out


def _ensure_state_shape(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        state = {}
    if not isinstance(state.get("classes"), dict):
        state["classes"] = {}
    if not isinstance(state.get("state_version"), str) or not state.get("state_version"):
        state["state_version"] = "v0.1"
    return state


def _state_entry_from_live(
    *,
    live_item: Dict[str, Any],
    now: str,
    existing_verified_at: str | None,
) -> Dict[str, Any]:
    status = str(live_item.get("status") or "").upper()
    ok = status == "OK"
    latency = live_item.get("elapsed_ms")
    latency_val = int(latency) if isinstance(latency, (int, float)) else None
    err = live_item.get("error_code") or live_item.get("error_type")
    err_val = str(err) if isinstance(err, str) and err else None
    return {
        "probe_status": "ok" if ok else "fail",
        "probe_last_at": now,
        "probe_latency_ms_p95": latency_val,
        "probe_error_code": None if ok else err_val,
        "verified_at": (existing_verified_at or now) if ok else existing_verified_at,
        "probe_kind": "live_probe",
    }


def _reconcile_state_from_live_report(
    *,
    provider_map: Dict[str, Any],
    existing_state: Dict[str, Any],
    live_report: Dict[str, Any],
    now: str,
) -> Dict[str, Any]:
    state = _ensure_state_shape(_deepcopy(existing_state))
    state["generated_at"] = now
    live_index = _live_results_by_provider_model(live_report)

    classes = provider_map.get("classes", {})
    if not isinstance(classes, dict):
        return state

    for cls_id, cls_data in classes.items():
        if not isinstance(cls_id, str) or not cls_id:
            continue
        if not isinstance(cls_data, dict):
            continue
        providers = cls_data.get("providers", {})
        if not isinstance(providers, dict):
            continue
        cls_state = state.setdefault("classes", {}).setdefault(cls_id, {"providers": {}})
        if not isinstance(cls_state, dict):
            cls_state = {"providers": {}}
            state["classes"][cls_id] = cls_state
        cls_state.setdefault("providers", {})
        if not isinstance(cls_state.get("providers"), dict):
            cls_state["providers"] = {}

        for prov_id, prov_data in providers.items():
            if not isinstance(prov_id, str) or not prov_id:
                continue
            if not isinstance(prov_data, dict):
                continue
            models = prov_data.get("models", [])
            if not isinstance(models, list):
                continue
            prov_state = cls_state["providers"].setdefault(prov_id, {"models": {}})
            if not isinstance(prov_state, dict):
                prov_state = {"models": {}}
                cls_state["providers"][prov_id] = prov_state
            prov_state.setdefault("models", {})
            if not isinstance(prov_state.get("models"), dict):
                prov_state["models"] = {}

            for m in models:
                if not isinstance(m, dict):
                    continue
                model_id = m.get("model_id")
                if not isinstance(model_id, str) or not model_id:
                    continue
                live_item = live_index.get(prov_id, {}).get(model_id)
                if not isinstance(live_item, dict):
                    continue
                live_status = str(live_item.get("status") or "").upper()
                if live_status == "SKIPPED":
                    continue
                existing_entry = prov_state["models"].get(model_id)
                existing_verified_at = None
                if isinstance(existing_entry, dict):
                    v = existing_entry.get("verified_at")
                    existing_verified_at = v if isinstance(v, str) and v else None
                prov_state["models"][model_id] = _state_entry_from_live(
                    live_item=live_item,
                    now=now,
                    existing_verified_at=existing_verified_at,
                )

    return state


def _ui_status_tr_for_model(model: Dict[str, Any]) -> tuple[str, bool]:
    stage = str(model.get("stage") or "").strip().lower()
    probe = str(model.get("probe_status") or "").strip().lower()
    selectable = bool(stage == "verified" and probe == "ok")
    if selectable:
        return "Doğrulandı", True
    if stage == "candidate":
        return "Taslak (atlanır)", False
    return "Doğrulanmadı (atlanır)", False


def _reconcile_provider_map_from_state(
    *,
    provider_map: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    merged = _deepcopy(provider_map)
    state_classes = state.get("classes", {})
    if not isinstance(state_classes, dict):
        state_classes = {}

    classes = merged.get("classes", {})
    if not isinstance(classes, dict):
        return merged

    for cls_id, cls_data in classes.items():
        if not isinstance(cls_data, dict):
            continue
        providers = cls_data.get("providers", {})
        if not isinstance(providers, dict):
            continue
        cls_state = state_classes.get(cls_id, {})
        cls_state_providers = cls_state.get("providers", {}) if isinstance(cls_state, dict) else {}

        for prov_id, prov_data in providers.items():
            if not isinstance(prov_data, dict):
                continue
            models = prov_data.get("models", [])
            if not isinstance(models, list):
                continue
            prov_state = cls_state_providers.get(prov_id, {}) if isinstance(cls_state_providers, dict) else {}
            models_state = prov_state.get("models", {}) if isinstance(prov_state, dict) else {}

            for m in models:
                if not isinstance(m, dict):
                    continue
                model_id = m.get("model_id")
                if not isinstance(model_id, str) or not model_id:
                    continue
                st = models_state.get(model_id) if isinstance(models_state, dict) else None
                if isinstance(st, dict):
                    for key in (
                        "probe_status",
                        "probe_last_at",
                        "probe_latency_ms_p95",
                        "probe_error_code",
                        "verified_at",
                        "probe_kind",
                    ):
                        if key in st:
                            m[key] = st[key]

                    if str(m.get("probe_status") or "") == "ok":
                        m["stage"] = "verified"
                        if not m.get("verified_at") and isinstance(st.get("verified_at"), str):
                            m["verified_at"] = st.get("verified_at")
                    elif not isinstance(m.get("stage"), str) or not str(m.get("stage") or "").strip():
                        m["stage"] = "candidate"

                ui_status, selectable = _ui_status_tr_for_model(m)
                m["ui_status_tr"] = ui_status
                m["ui_selectable"] = selectable

    return merged


def _verified_by_class(provider_map: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    out: Dict[str, Dict[str, List[str]]] = {}
    classes = provider_map.get("classes", {})
    if not isinstance(classes, dict):
        return out
    for cls_id, cls_data in classes.items():
        if not isinstance(cls_id, str) or not isinstance(cls_data, dict):
            continue
        providers = cls_data.get("providers", {})
        if not isinstance(providers, dict):
            continue
        cls_out: Dict[str, List[str]] = {}
        for prov_id, prov_data in providers.items():
            if not isinstance(prov_id, str) or not isinstance(prov_data, dict):
                continue
            models = prov_data.get("models", [])
            if not isinstance(models, list):
                continue
            eligible: List[str] = []
            for m in models:
                if not isinstance(m, dict):
                    continue
                if m.get("stage") != "verified" or m.get("probe_status") != "ok":
                    continue
                mid = m.get("model_id")
                if isinstance(mid, str) and mid:
                    eligible.append(mid)
            if eligible:
                cls_out[prov_id] = eligible
        if cls_out:
            out[cls_id] = cls_out
    return out


def _summarize_allowlist_report(report: Dict[str, Any]) -> Dict[str, Any]:
    items = report.get("items", [])
    rows = [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []
    attempted = len(rows)
    ok = sum(1 for it in rows if str(it.get("status") or "").upper() == "OK")
    fail = sum(1 for it in rows if str(it.get("status") or "").upper() == "FAIL")
    skipped = sum(1 for it in rows if str(it.get("status") or "").upper() == "SKIPPED")
    status = "OK" if fail == 0 else "WARN"
    return {"status": status, "attempted": attempted, "ok": ok, "fail": fail, "skipped": skipped}


def _index_allowlist_items(report: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    items = report.get("items", [])
    rows = [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for it in rows:
        pid = it.get("provider_id")
        mid = it.get("model_id")
        if not isinstance(pid, str) or not pid:
            continue
        if not isinstance(mid, str) or not mid:
            continue
        out.setdefault(pid, {})[mid] = {
            "status": it.get("status"),
            "error_code": it.get("error_code"),
            "probe_kind": it.get("probe_kind"),
            "classes_target": it.get("classes_target"),
        }
    return out


def main(workspace_root: str | Path | None = None, *, run_live: bool = True) -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws_root = _resolve_workspace_root(repo_root, workspace_root)
    ws_root_str = str(ws_root)

    now = _now_iso()

    if run_live:
        status, _, live_report = run_live_probe(workspace_root=ws_root_str, detail=False, env_mode="dotenv")
    else:
        status = "OK"
        live_report = _load_json_optional(ws_root / LIVE_REPORT_PATH) or {}

    provider_map_ws_path = ws_root / PROVIDER_MAP_WS_PATH
    provider_map_repo_path = repo_root / PROVIDER_MAP_REPO_PATH
    provider_map_base = _load_json_optional(provider_map_ws_path) or _load_json(provider_map_repo_path)

    state_path = ws_root / STATE_PATH
    existing_state = _load_json_optional(state_path) or {"state_version": "v0.1", "classes": {}}

    allowlist_latest_path = ws_root / ALLOWLIST_LATEST_PATH
    allowlist_report_path = ws_root / ALLOWLIST_REPORT_PATH
    allowlist_report = _load_json_optional(allowlist_latest_path) or _load_json_optional(allowlist_report_path) or {}

    guardrails = load_guardrails(ws_root_str)
    class_ids = _load_class_ids(repo_root=repo_root, ws_root=ws_root, provider_map=provider_map_base)
    provider_map_expanded = _expand_provider_map(
        base_provider_map=provider_map_base,
        guardrails=guardrails,
        class_ids=class_ids,
        now=now,
    )

    new_state = _reconcile_state_from_live_report(
        provider_map=provider_map_expanded,
        existing_state=existing_state,
        live_report=live_report,
        now=now,
    )
    _write_json_atomic(state_path, new_state)

    merged_provider_map = _reconcile_provider_map_from_state(provider_map=provider_map_expanded, state=new_state)
    _write_json_atomic(provider_map_ws_path, merged_provider_map)

    allowlist_by_provider: Dict[str, List[str]] = {}
    providers_guard = guardrails.get("providers", {})
    if isinstance(providers_guard, dict):
        for pid, pdata in providers_guard.items():
            if not isinstance(pid, str) or not isinstance(pdata, dict):
                continue
            allow_models = pdata.get("allow_models")
            if isinstance(allow_models, list):
                allowlist_by_provider[pid] = [str(m) for m in allow_models if isinstance(m, str) and m]

    live_summary = {
        "status": live_report.get("status"),
        "attempted": live_report.get("attempted"),
        "ok": live_report.get("ok"),
        "fail": live_report.get("fail"),
        "skipped": live_report.get("skipped"),
        "report_path": str((ws_root / LIVE_REPORT_PATH).resolve()),
    }
    allow_summary = dict(_summarize_allowlist_report(allowlist_report))
    allow_summary["report_path"] = str(
        (allowlist_latest_path if allowlist_latest_path.exists() else allowlist_report_path).resolve()
    )

    catalog: Dict[str, Any] = {
        "catalog_version": "v1",
        "generated_at": now,
        "workspace_root": str(ws_root),
        "canonical_paths": {
            "provider_map": str(provider_map_ws_path.resolve()),
            "probe_state": str(state_path.resolve()),
            "live_probe": str((ws_root / LIVE_REPORT_PATH).resolve()),
            "allowlist_probe": str((ws_root / ALLOWLIST_REPORT_PATH).resolve()),
            "allowlist_latest": str((ws_root / ALLOWLIST_LATEST_PATH).resolve()),
        },
        "summary": {
            "live_probe": live_summary,
            "allowlist_probe": allow_summary,
            "probe_state": {
                "generated_at": new_state.get("generated_at"),
                "classes_count": len(new_state.get("classes", {})) if isinstance(new_state.get("classes"), dict) else 0,
                "state_path": str(state_path.resolve()),
            },
        },
        "notes": [
            "Verified=live probe OK (fail-closed).",
            "Allowlist probe is a policy scan; it does not guarantee runtime success.",
        ],
        "provider_map": merged_provider_map,
        "verified_by_class": _verified_by_class(merged_provider_map),
        "allowlist_by_provider": allowlist_by_provider,
        "allowlist_probe_index": {
            "by_provider_model": _index_allowlist_items(allowlist_report),
        },
    }
    _write_json_atomic(ws_root / CATALOG_PATH, catalog)

    print(
        f"Live probe status={status}, state/catalog updated: {state_path} {provider_map_ws_path} {ws_root / CATALOG_PATH}"
    )

if __name__ == "__main__":
    main()
