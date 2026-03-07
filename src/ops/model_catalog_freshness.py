from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_provider_map_models(provider_map: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    classes = provider_map.get("classes")
    if not isinstance(classes, dict):
        return out
    for class_data in classes.values():
        if not isinstance(class_data, dict):
            continue
        providers = class_data.get("providers")
        if not isinstance(providers, dict):
            continue
        for provider_id, provider_data in providers.items():
            if not isinstance(provider_id, str) or not provider_id.strip():
                continue
            if not isinstance(provider_data, dict):
                continue
            models = provider_data.get("models")
            if not isinstance(models, list):
                continue
            for item in models:
                if not isinstance(item, dict):
                    continue
                model_id = item.get("model_id")
                if not isinstance(model_id, str) or not model_id.strip():
                    continue
                out.setdefault(provider_id.strip(), set()).add(model_id.strip())
    return out


def _collect_guardrails_models(guardrails: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    providers = guardrails.get("providers")
    if not isinstance(providers, dict):
        return out
    for provider_id, provider_data in providers.items():
        if not isinstance(provider_id, str) or not provider_id.strip():
            continue
        if not isinstance(provider_data, dict):
            continue
        allow_models = provider_data.get("allow_models")
        if not isinstance(allow_models, list):
            continue
        models = {str(x).strip() for x in allow_models if isinstance(x, str) and str(x).strip()}
        out[provider_id.strip()] = models
    return out


def run_model_catalog_freshness(
    *,
    repo_root: Path,
    out_path: Path | None = None,
) -> dict[str, Any]:
    provider_map_path = repo_root / "docs" / "OPERATIONS" / "llm_provider_map.v1.json"
    guardrails_path = repo_root / "policies" / "policy_llm_providers_guardrails.v1.json"
    out = out_path or (repo_root / ".cache" / "reports" / "model_catalog_freshness.v1.json")
    out = out.resolve()

    if not provider_map_path.exists() or not guardrails_path.exists():
        payload = {
            "status": "FAIL",
            "error_code": "SOURCE_MISSING",
            "generated_at": _now_iso(),
            "repo_root": str(repo_root),
            "sources": {
                "provider_map": provider_map_path.relative_to(repo_root).as_posix(),
                "guardrails_policy": guardrails_path.relative_to(repo_root).as_posix(),
            },
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["report_path"] = out.relative_to(repo_root).as_posix()
        return payload

    try:
        provider_map_obj = _load_json(provider_map_path)
        guardrails_obj = _load_json(guardrails_path)
    except Exception:
        payload = {
            "status": "FAIL",
            "error_code": "SOURCE_INVALID",
            "generated_at": _now_iso(),
            "repo_root": str(repo_root),
            "sources": {
                "provider_map": provider_map_path.relative_to(repo_root).as_posix(),
                "guardrails_policy": guardrails_path.relative_to(repo_root).as_posix(),
            },
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["report_path"] = out.relative_to(repo_root).as_posix()
        return payload

    provider_map_models = _collect_provider_map_models(
        provider_map_obj if isinstance(provider_map_obj, dict) else {}
    )
    guardrails_models = _collect_guardrails_models(
        guardrails_obj if isinstance(guardrails_obj, dict) else {}
    )
    provider_ids = sorted(set(provider_map_models.keys()) | set(guardrails_models.keys()))

    providers: list[dict[str, Any]] = []
    for provider_id in provider_ids:
        map_models = sorted(provider_map_models.get(provider_id, set()))
        policy_models = sorted(guardrails_models.get(provider_id, set()))
        missing_in_guardrails = sorted(set(map_models) - set(policy_models))
        missing_in_map = sorted(set(policy_models) - set(map_models))
        provider_status = "SYNCED" if not missing_in_guardrails and not missing_in_map else "MISMATCH"
        providers.append(
            {
                "provider_id": provider_id,
                "status": provider_status,
                "map_model_count": len(map_models),
                "guardrails_model_count": len(policy_models),
                "models_in_map": map_models,
                "models_in_guardrails": policy_models,
                "missing_in_guardrails": missing_in_guardrails,
                "missing_in_map": missing_in_map,
            }
        )

    mismatch_count = sum(1 for item in providers if item.get("status") != "SYNCED")
    overall_status = "SYNCED" if mismatch_count == 0 else "MISMATCH"
    report_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "repo_root": str(repo_root),
        "overall_status": overall_status,
        "sources": {
            "provider_map": provider_map_path.relative_to(repo_root).as_posix(),
            "guardrails_policy": guardrails_path.relative_to(repo_root).as_posix(),
            "external_review_mode": "manual_docs_review",
        },
        "providers": providers,
        "summary": {
            "providers_total": len(providers),
            "synced_count": len(providers) - mismatch_count,
            "mismatch_count": mismatch_count,
        },
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "status": "OK",
        "overall_status": overall_status,
        "providers_total": len(providers),
        "mismatch_count": mismatch_count,
        "report_path": out.relative_to(repo_root).as_posix(),
    }

