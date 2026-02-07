from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.ops.commands.common import repo_root, warn
from src.prj_kernel_api.api_guardrails import load_guardrails_policy
from src.prj_kernel_api.adapter_llm_actions import maybe_handle_llm_actions
from src.prj_kernel_api.provider_guardrails import load_guardrails, provider_settings


PURPOSE_SCHEMA = "WORK_INTAKE_PURPOSES_V1"
PURPOSE_VERSION = "v1"
PURPOSE_INDEX_REL = ".cache/index/work_intake_purpose.v1.json"
WORK_INTAKE_REL = ".cache/index/work_intake.v1.json"
REPORT_REL = ".cache/reports/work_intake_purpose_generate.v0.1.md"
REPORT_JSON_REL = ".cache/reports/work_intake_purpose_generate.v0.1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _short_intake_id(intake_id: str) -> str:
    raw = str(intake_id or "").strip()
    if raw.startswith("INTAKE-"):
        raw = raw[len("INTAKE-") :]
    return raw[:8].upper() if raw else ""


def _summarize_topic(item: dict[str, Any]) -> str:
    source_type = str(item.get("source_type") or "").strip()
    source_ref = str(item.get("source_ref") or "").strip()
    if source_type and source_ref:
        return f"{source_type}: {source_ref}"
    if source_type:
        return source_type
    if source_ref:
        return source_ref
    title = str(item.get("title") or "").strip()
    return title or "intake item"


def _summarize_why(item: dict[str, Any]) -> str:
    notes = item.get("autopilot_notes")
    if isinstance(notes, list) and notes:
        return " | ".join(str(n) for n in notes if n)
    if item.get("source_ref"):
        return f"Derived from {item.get('source_ref')}"
    if item.get("source_type"):
        return f"Derived from {item.get('source_type')}"
    return "No explicit rationale provided."


def _fallback_fields(item: dict[str, Any]) -> dict[str, str]:
    topic = _summarize_topic(item)
    why = _summarize_why(item)
    return {
        "purpose_tr": f"Bu işin amacı: {topic}.",
        "purpose_en": f"Purpose: {topic}.",
        "necessity_tr": "Gereklilik: Belirtilmemiş (düzenleme gerekli).",
        "necessity_en": "Necessity: Not set (curation needed).",
        "compatibility_tr": "Uyumluluk: İncelenmeli (otomatik üretim).",
        "compatibility_en": "Compatibility: Needs review (auto-generated).",
        "why_required_tr": f"Neden gerekli: {why}",
        "why_required_en": f"Why needed: {why}",
        "implementation_note_tr": "Uygulama notu: Kapsam/AC netleşince planlanır.",
        "implementation_note_en": "Implementation note: Plan once scope/AC are defined.",
        "system_impact_tr": "Sistem etkisi: TBD (plan aşamasında netleşir).",
        "system_impact_en": "System impact: TBD (defined in plan stage).",
        "benefit_tr": "Getiri/Fayda: TBD.",
        "benefit_en": "Benefit: TBD.",
        "roi_tr": "ROI: TBD.",
        "roi_en": "ROI: TBD.",
    }


def _build_prompt(item: dict[str, Any]) -> Tuple[str, str]:
    topic = _summarize_topic(item)
    why = _summarize_why(item)
    evidence_paths = item.get("evidence_paths")
    if not isinstance(evidence_paths, list):
        evidence_paths = []
    payload = {
        "title": str(item.get("title") or "").strip(),
        "topic": topic,
        "bucket": str(item.get("bucket") or "").strip(),
        "priority": str(item.get("priority") or "").strip(),
        "severity": str(item.get("severity") or "").strip(),
        "source_type": str(item.get("source_type") or "").strip(),
        "source_ref": str(item.get("source_ref") or "").strip(),
        "why": why,
        "evidence_paths": [str(p) for p in evidence_paths[:12]],
    }
    system = (
        "You are an operations analyst. Return STRICT JSON only (no markdown). "
        "Output keys: purpose_tr, purpose_en, necessity_tr, necessity_en, compatibility_tr, compatibility_en, "
        "why_required_tr, why_required_en, implementation_note_tr, implementation_note_en, system_impact_tr, "
        "system_impact_en, benefit_tr, benefit_en, roi_tr, roi_en. "
        "Each value <= 240 chars. Be neutral and evidence-based; if uncertain say 'Belirtilmemiş'/'Unknown'."
    )
    user = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return system, user


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None


def _build_response(**kwargs: Any) -> dict[str, Any]:
    return {
        "status": kwargs.get("status"),
        "payload": kwargs.get("payload"),
        "notes": kwargs.get("notes", []),
        "request_id": kwargs.get("request_id"),
        "error_code": kwargs.get("error_code"),
        "message": kwargs.get("message"),
        "auth_checked": kwargs.get("auth_checked", False),
        "rate_limited": kwargs.get("rate_limited", False),
    }


def _attempt_llm_generate(
    *,
    workspace_root: Path,
    provider_id: str,
    model: str | None,
    item: dict[str, Any],
) -> Tuple[dict[str, Any] | None, dict[str, Any]]:
    system, user = _build_prompt(item)
    params = {
        "provider_id": provider_id,
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
        "dry_run": False,
        "request_id": f"intake-purpose-{_short_intake_id(item.get('intake_id', ''))}",
    }
    try:
        policy = load_guardrails_policy(str(workspace_root))
    except Exception as exc:
        return None, {"status": "FAIL", "error": f"POLICY_LOAD_FAILED:{exc}"}

    result = maybe_handle_llm_actions(
        action="llm_call_live",
        params=params,
        workspace_root=str(workspace_root),
        repo_root=repo_root(),
        env_mode="dotenv",
        request_id=str(params.get("request_id")),
        auth_checked=False,
        rate_limited=False,
        policy=policy,
        build_response=_build_response,
    )
    if not isinstance(result, dict):
        return None, {"status": "FAIL", "error": "LLM_ACTION_UNAVAILABLE"}
    if str(result.get("status")) != "OK":
        return None, {"status": str(result.get("status")), "error": result.get("error_code")}
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    output = payload.get("output_preview") if isinstance(payload, dict) else None
    parsed = _parse_llm_json(str(output) if output is not None else "")
    return parsed, result


def _normalize_llm_fields(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in (
        "purpose_tr",
        "purpose_en",
        "necessity_tr",
        "necessity_en",
        "compatibility_tr",
        "compatibility_en",
        "why_required_tr",
        "why_required_en",
        "implementation_note_tr",
        "implementation_note_en",
        "system_impact_tr",
        "system_impact_en",
        "benefit_tr",
        "benefit_en",
        "roi_tr",
        "roi_en",
    ):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def cmd_work_intake_purpose_generate(args: argparse.Namespace) -> int:
    root = repo_root()
    ws_arg = str(args.workspace_root).strip()
    if not ws_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2
    ws_root = Path(ws_arg)
    ws_root = (root / ws_root).resolve() if not ws_root.is_absolute() else ws_root.resolve()
    if not ws_root.exists() or not ws_root.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    mode = str(getattr(args, "mode", "missing_only") or "missing_only").strip().lower()
    status_filter = str(getattr(args, "status", "OPEN") or "").strip().upper()
    provider_id = str(getattr(args, "provider_id", "openai") or "openai").strip().lower()
    model_arg = str(getattr(args, "model", "") or "").strip()
    target_raw = str(getattr(args, "intake_id", "") or "").strip()
    limit_raw = str(getattr(args, "limit", "50") or "50").strip()
    dry_run = str(getattr(args, "dry_run", "false") or "false").strip().lower() == "true"
    try:
        limit = max(1, int(limit_raw))
    except Exception:
        limit = 50

    intake_path = ws_root / WORK_INTAKE_REL
    if not intake_path.exists():
        warn("FAIL error=WORK_INTAKE_MISSING")
        return 2

    intake_obj = _load_json(intake_path)
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    target_id = target_raw
    target_short = target_raw.upper() if target_raw and len(target_raw) <= 12 else _short_intake_id(target_raw)
    if target_id:
        items = [
            item
            for item in items
            if str(item.get("intake_id") or "").strip() == target_id
            or _short_intake_id(str(item.get("intake_id") or "")) == target_short
        ]
        if not items:
            report = {
                "status": "FAIL",
                "mode": "single",
                "status_filter": status_filter,
                "provider_id": provider_id,
                "model": model_arg,
                "dry_run": dry_run,
                "processed": 0,
                "created": 0,
                "skipped": 0,
                "failures": [],
                "purpose_index": str(ws_root / PURPOSE_INDEX_REL),
                "generated_at": _now_iso(),
                "error": "INTAKE_NOT_FOUND",
                "intake_id": target_id,
            }
            report_path = ws_root / REPORT_JSON_REL
            _write_json(report_path, report)
            report_md_path = ws_root / REPORT_REL
            report_md_path.parent.mkdir(parents=True, exist_ok=True)
            report_md_path.write_text(
                "\n".join(
                    [
                        "# Work Intake Purpose Generate (AI)",
                        "",
                        "Status: FAIL",
                        f"Error: INTAKE_NOT_FOUND ({target_id})",
                        f"Generated at: {report['generated_at']}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 2

    purpose_path = ws_root / PURPOSE_INDEX_REL
    purpose_obj = _load_json(purpose_path)
    if not isinstance(purpose_obj, dict) or not purpose_obj.get("items"):
        purpose_obj = {
            "schema": PURPOSE_SCHEMA,
            "version": PURPOSE_VERSION,
            "generated_at": _now_iso(),
            "items": [],
        }

    existing_items = purpose_obj.get("items") if isinstance(purpose_obj.get("items"), list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for entry in existing_items:
        if not isinstance(entry, dict):
            continue
        intake_id = str(entry.get("intake_id") or "").strip()
        if intake_id:
            by_id[intake_id] = entry

    guardrails = None
    if provider_id:
        try:
            guardrails = load_guardrails(str(ws_root))
        except Exception:
            guardrails = None
    model = model_arg or None
    if guardrails is not None and provider_id and not model:
        settings = provider_settings(guardrails, provider_id)
        model = settings.get("default_model") if isinstance(settings.get("default_model"), str) else None

    if target_id:
        mode = "single"
        limit = 1

    processed = 0
    created = 0
    skipped = 0
    failures: list[dict[str, Any]] = []

    for item in items:
        if processed >= limit:
            break
        if not isinstance(item, dict):
            continue
        intake_id = str(item.get("intake_id") or "").strip()
        if not intake_id:
            continue
        if status_filter and str(item.get("status") or "").upper() != status_filter:
            continue
        if mode == "missing_only" and intake_id in by_id:
            skipped += 1
            continue

        processed += 1
        output_fields: dict[str, Any] = {}
        llm_result_meta: dict[str, Any] = {"status": "SKIPPED"}
        if provider_id and not dry_run:
            llm_payload, llm_result_meta = _attempt_llm_generate(
                workspace_root=ws_root,
                provider_id=provider_id,
                model=model,
                item=item,
            )
            if isinstance(llm_payload, dict):
                output_fields = _normalize_llm_fields(llm_payload)

        if not output_fields:
            output_fields = _fallback_fields(item)

        record = {
            "intake_id": intake_id,
            "intake_short_id": _short_intake_id(intake_id),
            "updated_at": _now_iso(),
            **output_fields,
        }
        if intake_id in by_id:
            by_id[intake_id].update(record)
        else:
            by_id[intake_id] = record
            created += 1

        if llm_result_meta.get("status") not in {"OK", "SKIPPED"}:
            failures.append({"intake_id": intake_id, "error": llm_result_meta})

    if not dry_run:
        purpose_obj["generated_at"] = _now_iso()
        purpose_obj["items"] = list(by_id.values())
        _write_json(purpose_path, purpose_obj)

    report = {
        "status": "OK",
        "mode": mode,
        "status_filter": status_filter,
        "provider_id": provider_id,
        "model": model or "",
        "dry_run": dry_run,
        "processed": processed,
        "created": created,
        "skipped": skipped,
        "failures": failures,
        "purpose_index": str(purpose_path),
        "generated_at": _now_iso(),
        "intake_id": target_id or "",
    }

    report_path = ws_root / REPORT_JSON_REL
    _write_json(report_path, report)

    md_lines = [
        "# Work Intake Purpose Generate (AI)",
        "",
        f"Status: {report['status']}",
        f"Mode: {mode}",
        f"Status filter: {status_filter}",
        f"Provider: {provider_id}",
        f"Model: {model or '-'}",
        f"Dry run: {dry_run}",
        f"Processed: {processed}",
        f"Created: {created}",
        f"Skipped: {skipped}",
        f"Failures: {len(failures)}",
        f"Purpose index: {purpose_path}",
        "",
    ]
    if failures:
        md_lines.append("## Failures")
        for entry in failures[:12]:
            md_lines.append(f"- {entry.get('intake_id')}: {entry.get('error')}")
    report_md_path = ws_root / REPORT_REL
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0
