from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.prj_kernel_api.adapter_llm_actions import maybe_handle_llm_actions
from src.prj_kernel_api.api_guardrails import load_guardrails_policy
from src.prj_kernel_api.provider_guardrails import load_guardrails, provider_settings
from src.ops.commands.common import repo_root, warn

SUGGESTIONS_REL_PATH = Path(".cache") / "index" / "mechanisms.suggestions.v1.json"
MECHANISMS_REL_PATH = Path(".cache") / "index" / "mechanisms.registry.v1.json"


@dataclass
class ConsultResult:
    provider_id: str
    model: str
    status: str
    error_code: str | None
    output_text: str
    output_full_path: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_id(*parts: str) -> str:
    seed = "|".join(p.strip() for p in parts if p is not None)
    return "SUGG-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return default
    return default


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _extract_json(text: str) -> Dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1].strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except Exception:
        return None


def _normalize_id(value: str) -> str:
    return "".join(ch for ch in value.lower().replace(" ", "_") if ch.isalnum() or ch in {"_", "-"}).strip("_")


def _suggestions_path(ws: Path) -> Path:
    return (ws / SUGGESTIONS_REL_PATH).resolve()


def _mechanisms_path(ws: Path) -> Path:
    return (ws / MECHANISMS_REL_PATH).resolve()


def _load_mechanisms(ws: Path) -> dict:
    default = {"version": "v1", "generated_at": _now_iso(), "source": "manual", "subjects": []}
    return _load_json(_mechanisms_path(ws), default)


def _load_suggestions(ws: Path) -> dict:
    default = {"version": "v1", "generated_at": _now_iso(), "suggestions": []}
    return _load_json(_suggestions_path(ws), default)


def _append_suggestions(ws: Path, items: List[dict]) -> dict:
    store = _load_suggestions(ws)
    suggestions = store.get("suggestions")
    if not isinstance(suggestions, list):
        suggestions = []
    suggestions.extend(items)
    store["suggestions"] = suggestions
    store["generated_at"] = _now_iso()
    _write_json(_suggestions_path(ws), store)
    return store


def _call_llm(
    *,
    provider_id: str,
    model: str,
    prompt: str,
    max_tokens: int,
    request_id: str,
    workspace_root: Path,
    repo_root_path: Path,
) -> ConsultResult:
    guardrails_policy = load_guardrails_policy(str(workspace_root))
    params = {
        "provider_id": provider_id,
        "model": model,
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    res = maybe_handle_llm_actions(
        action="llm_call_live",
        params=params,
        workspace_root=str(workspace_root),
        repo_root=repo_root_path,
        env_mode="dotenv",
        request_id=request_id,
        auth_checked=True,
        rate_limited=False,
        policy=guardrails_policy,
        build_response=lambda **kwargs: {
            "status": kwargs.get("status"),
            "payload": kwargs.get("payload"),
            "notes": kwargs.get("notes", []),
            "request_id": kwargs.get("request_id"),
            "error_code": kwargs.get("error_code"),
            "message": kwargs.get("message"),
            "auth_checked": kwargs.get("auth_checked", False),
            "rate_limited": kwargs.get("rate_limited", False),
        },
    )
    if not isinstance(res, dict):
        return ConsultResult(provider_id, model, "FAIL", "NO_RESPONSE", "", None)
    payload = res.get("payload") if isinstance(res.get("payload"), dict) else {}
    output_text = ""
    full_path = payload.get("output_full_path")
    if isinstance(full_path, str) and full_path:
        try:
            output_text = Path(full_path).read_text(encoding="utf-8")
        except Exception:
            output_text = ""
    if not output_text and isinstance(payload.get("output_preview"), str):
        output_text = payload.get("output_preview") or ""
    return ConsultResult(
        provider_id=provider_id,
        model=model,
        status=str(res.get("status") or "FAIL"),
        error_code=str(res.get("error_code") or "") or None,
        output_text=output_text,
        output_full_path=full_path if isinstance(full_path, str) else None,
    )


def _seed_prompt(subject_id: str) -> str:
    return (
        "ROL:\n"
        "Sen, kurumsal uyum ve süreç mimarisi tasarlayan kıdemli bir “Program Taxonomy Architect”sin.\n\n"
        "GÖREV:\n"
        "Kullanıcı yalnızca bir KONU adı verecek. Hiçbir ek soru sormadan o konu için Theme/Subtheme Taksonomisi üret.\n\n"
        "KAPSAM & SEVİYE (ZORUNLU):\n"
        "- SEVİYE: [program / süreç / modül / özellik]\n"
        "- KAPSAM: Dahil: […]; Hariç: […]\n"
        "- BAĞLAM: Ülke/Regülasyon/Sektör/Organizasyon varsayımları: […]\n\n"
        "ÜRETİM AKIŞI:\n"
        "1) Konu için bağımsız temaları çıkar (tema sayısı sabit değil).\n"
        "2) Her tema için uygulanabilir modül/iş paketi seviyesinde subtheme üret.\n\n"
        "ÇIKTI KURALI:\n"
        "- JSON döndür; yorum/markdown yok.\n"
        "- Zorunlu alan: themes[] (theme_id, title_tr, title_en, subthemes[]).\n"
        "- subthemes[]: subtheme_id, title_tr, title_en.\n"
        "- ID formatı: snake_case İngilizce; başlıklar Türkçe.\n\n"
        f"KONU: {subject_id}\n"
        "ŞİMDİ ÇIKTIYI ÜRET."
    )


def _consult_prompt(subject_id: str, themes_snapshot: dict, focus_type: str, focus_id: str, comment: str) -> str:
    focus_block = ""
    if focus_type and focus_id:
        focus_block = f"\nODAK: {focus_type} = {focus_id}\n"
    if comment:
        focus_block += f"KULLANICI_NOTU: {comment}\n"
    return (
        "ROL:\n"
        "Sen, kurumsal uyum ve süreç mimarisi tasarlayan kıdemli bir “Program Taxonomy Architect”sin.\n\n"
        "GÖREV:\n"
        "Tema/Subtheme listesi üzerinde SADECE öneri üret.\n"
        "YENİ tema yaratma; sadece 'eksik olabilir', 'birleştirilebilir', 'fazla/az' önerisi yap.\n\n"
        "MEVCUT_TEMALAR_JSON:\n"
        f"{json.dumps(themes_snapshot, ensure_ascii=False)}\n"
        f"{focus_block}\n"
        "ÇIKTI KURALI:\n"
        "- JSON döndür; yorum yok.\n"
        "- suggestions[] listesi ver.\n"
        "- suggestion.type sadece: missing_theme | missing_subtheme | merge_themes | subtheme_too_few | subtheme_too_many\n"
        "- missing_theme: theme_id,title_tr,title_en,reason_tr\n"
        "- missing_subtheme: theme_id,subtheme_id,title_tr,title_en,reason_tr\n"
        "- merge_themes: from_theme_id,to_theme_id,reason_tr\n"
        "- subtheme_too_few/subtheme_too_many: theme_id,reason_tr\n"
        f"\nKONU: {subject_id}\n"
        "ŞİMDİ ÇIKTIYI ÜRET."
    )


def _themes_snapshot(mechanisms: dict, subject_id: str) -> dict:
    subjects = mechanisms.get("subjects")
    if not isinstance(subjects, list):
        return {"themes": []}
    target = next((s for s in subjects if str(s.get("subject_id") or "").strip() == subject_id), None)
    themes = target.get("themes") if isinstance(target, dict) else []
    if not isinstance(themes, list):
        themes = []
    return {"themes": themes}


def _seed_to_suggestions(subject_id: str, provider_id: str, model: str, payload: dict) -> List[dict]:
    suggestions: List[dict] = []
    themes = payload.get("themes") if isinstance(payload, dict) else []
    if not isinstance(themes, list):
        return suggestions
    for theme in themes:
        theme_id_raw = str(theme.get("theme_id") or theme.get("title_en") or theme.get("title_tr") or "").strip()
        if not theme_id_raw:
            continue
        theme_id = _normalize_id(theme_id_raw)
        suggestion_id = _hash_id(subject_id, "theme", theme_id, provider_id, model)
        suggestions.append(
            {
                "suggestion_id": suggestion_id,
                "subject_id": subject_id,
                "target_type": "theme",
                "target_id": theme_id,
                "suggestion_type": "add_theme",
                "payload": {
                    "theme_id": theme_id,
                    "title_tr": theme.get("title_tr") or theme.get("title_en") or theme_id_raw,
                    "title_en": theme.get("title_en") or theme.get("title_tr") or theme_id_raw,
                    "definition_tr": theme.get("definition_tr") or "",
                    "definition_en": theme.get("definition_en") or "",
                },
                "status": "PROPOSED",
                "created_at": _now_iso(),
                "created_by": f"llm:{provider_id}",
                "source_model": model,
                "user_comment": "",
                "evidence_paths": [],
            }
        )
        subthemes = theme.get("subthemes") if isinstance(theme.get("subthemes"), list) else []
        for sub in subthemes:
            sub_id_raw = str(sub.get("subtheme_id") or sub.get("title_en") or sub.get("title_tr") or "").strip()
            if not sub_id_raw:
                continue
            sub_id = _normalize_id(sub_id_raw)
            sub_suggestion_id = _hash_id(subject_id, "subtheme", theme_id, sub_id, provider_id, model)
            suggestions.append(
                {
                    "suggestion_id": sub_suggestion_id,
                    "subject_id": subject_id,
                    "target_type": "subtheme",
                    "target_id": sub_id,
                    "suggestion_type": "add_subtheme",
                    "payload": {
                        "theme_id": theme_id,
                        "subtheme_id": sub_id,
                        "title_tr": sub.get("title_tr") or sub.get("title_en") or sub_id_raw,
                        "title_en": sub.get("title_en") or sub.get("title_tr") or sub_id_raw,
                        "definition_tr": sub.get("definition_tr") or "",
                        "definition_en": sub.get("definition_en") or "",
                    },
                    "status": "PROPOSED",
                    "created_at": _now_iso(),
                    "created_by": f"llm:{provider_id}",
                    "source_model": model,
                    "user_comment": "",
                    "evidence_paths": [],
                }
            )
    return suggestions


def _consult_to_suggestions(subject_id: str, provider_id: str, model: str, payload: dict, user_comment: str) -> List[dict]:
    out: List[dict] = []
    suggestions = payload.get("suggestions") if isinstance(payload, dict) else []
    if not isinstance(suggestions, list):
        return out
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        s_type = str(item.get("type") or "").strip()
        suggestion_id = _hash_id(subject_id, s_type, json.dumps(item, ensure_ascii=False), provider_id, model)
        out.append(
            {
                "suggestion_id": suggestion_id,
                "subject_id": subject_id,
                "target_type": "theme" if "theme" in s_type else "subtheme",
                "target_id": str(item.get("theme_id") or item.get("subtheme_id") or ""),
                "suggestion_type": s_type,
                "payload": item,
                "status": "PROPOSED",
                "created_at": _now_iso(),
                "created_by": f"llm:{provider_id}",
                "source_model": model,
                "user_comment": user_comment or "",
                "evidence_paths": [],
            }
        )
    return out


def _apply_suggestion_to_registry(mechanisms: dict, suggestion: dict, action: str, merge_target: str) -> None:
    subject_id = str(suggestion.get("subject_id") or "").strip()
    subjects = mechanisms.get("subjects")
    if not isinstance(subjects, list):
        subjects = []
        mechanisms["subjects"] = subjects
    subject = next((s for s in subjects if str(s.get("subject_id") or "").strip() == subject_id), None)
    if subject is None:
        subject = {
            "subject_id": subject_id,
            "subject_title_tr": subject_id,
            "subject_title_en": subject_id,
            "status": "PROPOSED",
            "approval_required": True,
            "approved_at": None,
            "approval_mode": "review",
            "themes": [],
        }
        subjects.append(subject)
    themes = subject.get("themes")
    if not isinstance(themes, list):
        themes = []
        subject["themes"] = themes

    s_type = str(suggestion.get("suggestion_type") or "")
    payload = suggestion.get("payload") if isinstance(suggestion.get("payload"), dict) else {}
    if action == "ACCEPT":
        if s_type == "add_theme":
            theme_id = str(payload.get("theme_id") or "").strip()
            if not theme_id:
                return
            if any(str(t.get("theme_id") or "").strip() == theme_id for t in themes if isinstance(t, dict)):
                return
            themes.append(
                {
                    "theme_id": theme_id,
                    "title_tr": payload.get("title_tr") or theme_id,
                    "title_en": payload.get("title_en") or theme_id,
                    "definition_tr": payload.get("definition_tr") or "",
                    "definition_en": payload.get("definition_en") or "",
                    "subthemes": [],
                }
            )
        elif s_type == "add_subtheme":
            theme_id = str(payload.get("theme_id") or "").strip()
            sub_id = str(payload.get("subtheme_id") or "").strip()
            if not theme_id or not sub_id:
                return
            theme = next((t for t in themes if str(t.get("theme_id") or "").strip() == theme_id), None)
            if theme is None:
                return
            subthemes = theme.get("subthemes")
            if not isinstance(subthemes, list):
                subthemes = []
                theme["subthemes"] = subthemes
            if any(str(s.get("subtheme_id") or "").strip() == sub_id for s in subthemes if isinstance(s, dict)):
                return
            subthemes.append(
                {
                    "subtheme_id": sub_id,
                    "title_tr": payload.get("title_tr") or sub_id,
                    "title_en": payload.get("title_en") or sub_id,
                    "definition_tr": payload.get("definition_tr") or "",
                    "definition_en": payload.get("definition_en") or "",
                }
            )
        elif s_type == "merge_themes":
            from_id = str(payload.get("from_theme_id") or "").strip()
            to_id = str(payload.get("to_theme_id") or merge_target or "").strip()
            if not from_id or not to_id or from_id == to_id:
                return
            from_theme = next((t for t in themes if str(t.get("theme_id") or "").strip() == from_id), None)
            to_theme = next((t for t in themes if str(t.get("theme_id") or "").strip() == to_id), None)
            if not from_theme or not to_theme:
                return
            from_subs = from_theme.get("subthemes") if isinstance(from_theme.get("subthemes"), list) else []
            to_subs = to_theme.get("subthemes") if isinstance(to_theme.get("subthemes"), list) else []
            existing = {str(s.get("subtheme_id") or "").strip() for s in to_subs if isinstance(s, dict)}
            for sub in from_subs:
                sub_id = str(sub.get("subtheme_id") or "").strip()
                if not sub_id or sub_id in existing:
                    continue
                to_subs.append(sub)
            to_theme["subthemes"] = to_subs
            themes[:] = [t for t in themes if str(t.get("theme_id") or "").strip() != from_id]
            subject["themes"] = themes


def cmd_north_star_theme_seed(args: argparse.Namespace) -> int:
    root = repo_root()
    ws = Path(str(args.workspace_root)).resolve()
    if not ws.exists():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    subject_id = str(args.subject_id or "").strip()
    if not subject_id:
        warn("FAIL error=SUBJECT_ID_REQUIRED")
        return 2
    provider_id = str(args.provider_id or "openai").strip().lower()
    model = str(args.model or "gpt-5.2").strip()
    max_tokens = int(str(args.max_tokens or "5000"))

    prompt = _seed_prompt(subject_id)
    res = _call_llm(
        provider_id=provider_id,
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
        request_id=f"north_star_theme_seed_{provider_id}",
        workspace_root=ws,
        repo_root_path=root,
    )
    payload = _extract_json(res.output_text) or {}
    suggestions = _seed_to_suggestions(subject_id, provider_id, model, payload)
    store = _append_suggestions(ws, suggestions)
    print(
        json.dumps(
            {
                "status": "OK" if suggestions else "WARN",
                "subject_id": subject_id,
                "provider_id": provider_id,
                "model": model,
                "suggestions_added": len(suggestions),
                "suggestions_path": str(_suggestions_path(ws)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if suggestions else 2


def cmd_north_star_theme_consult(args: argparse.Namespace) -> int:
    root = repo_root()
    ws = Path(str(args.workspace_root)).resolve()
    if not ws.exists():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    subject_id = str(args.subject_id or "").strip()
    if not subject_id:
        warn("FAIL error=SUBJECT_ID_REQUIRED")
        return 2
    providers = [p.strip() for p in str(args.providers or "").split(",") if p.strip()]
    if not providers:
        providers = ["openai", "google", "claude", "deepseek", "qwen", "xai"]
    focus_type = str(args.focus_type or "").strip()
    focus_id = str(args.focus_id or "").strip()
    comment = str(args.comment or "").strip()
    max_tokens = int(str(args.max_tokens or "2500"))

    guardrails = load_guardrails(str(ws))
    mechanisms = _load_mechanisms(ws)
    snapshot = _themes_snapshot(mechanisms, subject_id)

    all_suggestions: List[dict] = []
    for provider_id in providers:
        settings = provider_settings(guardrails, provider_id)
        if not settings.get("enabled"):
            continue
        model = settings.get("default_model") or (settings.get("allow_models") or [""])[0]
        if not model:
            continue
        prompt = _consult_prompt(subject_id, snapshot, focus_type, focus_id, comment)
        res = _call_llm(
            provider_id=provider_id,
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            request_id=f"north_star_theme_consult_{provider_id}",
            workspace_root=ws,
            repo_root_path=root,
        )
        payload = _extract_json(res.output_text) or {}
        all_suggestions.extend(_consult_to_suggestions(subject_id, provider_id, model, payload, comment))

    store = _append_suggestions(ws, all_suggestions)
    print(
        json.dumps(
            {
                "status": "OK" if all_suggestions else "WARN",
                "subject_id": subject_id,
                "providers": providers,
                "suggestions_added": len(all_suggestions),
                "suggestions_path": str(_suggestions_path(ws)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if all_suggestions else 2


def cmd_north_star_theme_suggestion_apply(args: argparse.Namespace) -> int:
    root = repo_root()
    ws = Path(str(args.workspace_root)).resolve()
    if not ws.exists():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    suggestion_id = str(args.suggestion_id or "").strip()
    if not suggestion_id:
        warn("FAIL error=SUGGESTION_ID_REQUIRED")
        return 2
    action = str(args.action or "").strip().upper()
    if action not in {"ACCEPT", "REJECT", "MERGE"}:
        warn("FAIL error=ACTION_INVALID")
        return 2
    comment = str(args.comment or "").strip()
    merge_target = str(args.merge_target or "").strip()

    store = _load_suggestions(ws)
    suggestions = store.get("suggestions")
    if not isinstance(suggestions, list):
        warn("FAIL error=SUGGESTIONS_STORE_INVALID")
        return 2
    suggestion = next((s for s in suggestions if str(s.get("suggestion_id") or "") == suggestion_id), None)
    if suggestion is None:
        warn("FAIL error=SUGGESTION_NOT_FOUND")
        return 2

    if action == "ACCEPT":
        mechanisms = _load_mechanisms(ws)
        _apply_suggestion_to_registry(mechanisms, suggestion, "ACCEPT", merge_target)
        mechanisms["generated_at"] = _now_iso()
        _write_json(_mechanisms_path(ws), mechanisms)

    if action == "MERGE":
        mechanisms = _load_mechanisms(ws)
        _apply_suggestion_to_registry(mechanisms, suggestion, "ACCEPT", merge_target)
        mechanisms["generated_at"] = _now_iso()
        _write_json(_mechanisms_path(ws), mechanisms)

    suggestion["status"] = "ACCEPTED" if action in {"ACCEPT", "MERGE"} else "REJECTED"
    suggestion["review_comment"] = comment
    suggestion["reviewed_at"] = _now_iso()
    store["generated_at"] = _now_iso()
    _write_json(_suggestions_path(ws), store)
    print(
        json.dumps(
            {
                "status": "OK",
                "suggestion_id": suggestion_id,
                "action": action,
                "suggestions_path": str(_suggestions_path(ws)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0
