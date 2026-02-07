from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.prj_kernel_api.adapter_llm_actions import maybe_handle_llm_actions
from src.prj_kernel_api.api_guardrails import load_guardrails_policy
from src.prj_kernel_api.dotenv_loader import resolve_env_value
from src.prj_kernel_api.provider_guardrails import load_guardrails, provider_settings
from src.ops.commands.common import repo_root, warn


@dataclass
class ConsultResult:
    provider_id: str
    model: str
    status: str
    error_code: str | None
    output_text: str
    output_full_path: str | None
    output_full_paths: List[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_response(**kwargs: Any) -> Dict[str, Any]:
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


def _extract_json(text: str) -> Dict[str, Any] | None:
    if not text:
        return None
    # Best-effort JSON extraction
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1].strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, list):
            return {"themes": obj}
        if isinstance(obj, dict) and isinstance(obj.get("themes"), list):
            return obj
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start : end + 1])
        if isinstance(obj, list):
            return {"themes": obj}
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _normalize_theme_id(value: str) -> str:
    return "".join(ch for ch in value.lower().replace(" ", "_") if ch.isalnum() or ch in {"_", "-"}).strip("_")


def _is_valid_theme_id(theme_id: str) -> bool:
    if not theme_id:
        return False
    if len(theme_id) < 4 and "_" not in theme_id:
        return False
    if theme_id in {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"}:
        return False
    if theme_id.startswith("theme_") and theme_id[6:].isdigit():
        return False
    if theme_id.startswith("ethics_program_") and theme_id[15:].isdigit():
        return False
    return True


def _consolidate_theme_sets(theme_sets: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    consolidated: Dict[str, Dict[str, Any]] = {}
    conflicts: List[str] = []
    for data in theme_sets:
        for theme in data.get("themes", []) if isinstance(data, dict) else []:
            theme_id = str(theme.get("theme_id") or theme.get("title_en") or theme.get("title_tr") or "").strip()
            if not theme_id:
                continue
            theme_key = _normalize_theme_id(theme_id)
            if not _is_valid_theme_id(theme_key):
                continue
            entry = consolidated.get(theme_key)
            if entry is None:
                consolidated[theme_key] = {
                    "theme_id": theme_key,
                    "title_tr": theme.get("title_tr") or theme.get("title_en") or theme_id,
                    "title_en": theme.get("title_en") or theme.get("title_tr") or theme_id,
                    "definition_tr": theme.get("definition_tr") or "",
                    "definition_en": theme.get("definition_en") or "",
                    "subthemes": [],
                }
                entry = consolidated[theme_key]
            # Merge subthemes
            sub_seen = {s.get("subtheme_id") for s in entry.get("subthemes", []) if isinstance(s, dict)}
            for sub in theme.get("subthemes", []) if isinstance(theme.get("subthemes"), list) else []:
                sub_id_raw = str(sub.get("subtheme_id") or sub.get("title_en") or sub.get("title_tr") or "").strip()
                if not sub_id_raw:
                    continue
                sub_id = _normalize_theme_id(sub_id_raw)
                if sub_id in sub_seen:
                    continue
                entry["subthemes"].append(
                    {
                        "subtheme_id": sub_id,
                        "title_tr": sub.get("title_tr") or sub.get("title_en") or sub_id_raw,
                        "title_en": sub.get("title_en") or sub.get("title_tr") or sub_id_raw,
                        "definition_tr": sub.get("definition_tr") or "",
                        "definition_en": sub.get("definition_en") or "",
                    }
                )
                sub_seen.add(sub_id)
            # Detect conflicts
            if theme.get("title_tr") and entry.get("title_tr") and theme.get("title_tr") != entry.get("title_tr"):
                conflicts.append(f"theme_id={theme_key}: title_tr conflict ({entry.get('title_tr')} vs {theme.get('title_tr')})")
            if theme.get("title_en") and entry.get("title_en") and theme.get("title_en") != entry.get("title_en"):
                conflicts.append(f"theme_id={theme_key}: title_en conflict ({entry.get('title_en')} vs {theme.get('title_en')})")
    return list(consolidated.values()), conflicts


def _preview_text(text: str, limit: int = 4000) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[TRUNCATED]"


def _consult_provider(
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
            {
                "role": "system",
                "content": "You are a product analyst. Return strict JSON only.",
            },
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
        build_response=_build_response,
    )
    if not isinstance(res, dict):
        return ConsultResult(provider_id, model, "FAIL", "NO_RESPONSE", "", None, [])
    payload = res.get("payload") if isinstance(res.get("payload"), dict) else {}
    status = res.get("status") or "FAIL"
    output_text = ""
    full_path = payload.get("output_full_path")
    if isinstance(full_path, str) and full_path:
        try:
            output_text = Path(full_path).read_text()
        except Exception:
            output_text = ""
    if not output_text and isinstance(payload.get("output_preview"), str):
        output_text = payload.get("output_preview") or ""
    return ConsultResult(
        provider_id,
        model,
        status,
        res.get("error_code"),
        output_text,
        full_path if isinstance(full_path, str) else None,
        [full_path] if isinstance(full_path, str) else [],
    )


def run_bootstrap(
    *,
    workspace_root: Path,
    subject_id: str,
    approve: bool,
    providers: List[str],
) -> Dict[str, Any]:
    repo_root_path = repo_root()
    guardrails = load_guardrails(str(workspace_root))
    auto_approve = False
    present, value = resolve_env_value("NORTH_STAR_BOOTSTRAP_AUTO_APPROVE", str(workspace_root), env_mode="dotenv")
    if present and isinstance(value, str) and value.strip() == "1":
        auto_approve = True
    approve_effective = bool(approve or auto_approve)
    base_prompt = (
        "ROL:\n"
        "Sen, kurumsal uyum ve süreç mimarisi tasarlayan kıdemli bir “Program Taxonomy Architect”sin.\n\n"
        "GÖREV:\n"
        "Kullanıcı yalnızca bir KONU adı verecek. Hiçbir ek soru sormadan o konu için Theme/Subtheme Taksonomisi üret.\n\n"
        "KAPSAM & SEVİYE (ZORUNLU):\n"
        "- SEVİYE: [program / süreç / modül / özellik]\n"
        "- KAPSAM: Dahil: […]; Hariç: […]\n"
        "- BAĞLAM: Ülke/Regülasyon/Sektör/Organizasyon varsayımları: […]\n\n"
        "ÜRETİM AKIŞI (DETERMINISTIC):\n"
        "1) Konu için bağımsız temaları çıkar (tema sayısı sabit değil).\n"
        "2) Her tema için uygulanabilir modül/iş paketi seviyesinde subtheme üret.\n"
        "3) Anlamsızsa subtheme üretme: “N/A (gerekçe: …)” yaz.\n"
        "4) 12‑kova kontrolünü Var/Yok/N/A olarak işaretle; “Yok” ise gap öner.\n"
        "5) “Dışarıda bırakılanlar” listesini ver (bilinçli dışlama).\n"
        "6) Minimum KPI seti üret (sayı uydurma YASAK; ölçüm türleri cümlesi yaz).\n\n"
        "KAPSAM KURALLARI:\n"
        "- Tema sayısı sabit değildir; rehber aralık: Dar 4–6, Orta 6–10, Program 8–14.\n"
        "- Subtheme sayısı sabit değildir; tema başına 4–12 önerilir.\n"
        "- Temalar birbirine bağlı olmak zorunda değildir.\n"
        "- Subtheme seviyesi: ne çok genel ne de aşırı mikro.\n"
        "- Örtüşme kontrolü: Aynı subtheme birden fazla temada tekrar edemez.\n\n"
        "12‑KOVA KONTROL (ZORUNLU):\n"
        "1 Amaç&tanım, 2 Kapsam, 3 Roller(RACI), 4 İş akışı, 5 Girdi/çıktı,\n"
        "6 Standartlar, 7 Risk&kontrol, 8 Veri&kayıt, 9 İstisna&escalation,\n"
        "10 Ölçüm&raporlama, 11 Eğitim&iletişim, 12 Sürekli iyileştirme.\n\n"
        "ÇIKTI KURALI:\n"
        "- JSON döndür; yorum/markdown yok.\n"
        "- Zorunlu alan: themes[] (theme_id, title_tr, title_en, subthemes[]).\n"
        "- subthemes[]: subtheme_id, title_tr, title_en.\n"
        "- SADECE themes[] döndür (gaps/exclusions/kpis YOK).\n"
        "- Tanım alanlarını (definition_*) boş bırak veya gönderme (çıktı kısa olsun).\n"
        "- ID formatı gerekiyorsa: snake_case İngilizce; başlıklar Türkçe.\n\n"
        f"KONU: {subject_id}\n"
        "ŞİMDİ ÇIKTIYI ÜRET."
    )

    def chunk_prompt(chunk_index: int, chunk_total: int) -> str:
        return (
            base_prompt
            + "\n\nCHUNK KURALI:\n"
            + f"- Bu çağrı parça {chunk_index}/{chunk_total}.\n"
            + "- theme_id baş harfine göre böl.\n"
            + (
                "- Bu parçada SADECE theme_id ilk harfi A–M olan temaları üret (başka tema üretme).\n"
                if chunk_index == 1
                else "- Bu parçada SADECE theme_id ilk harfi N–Z olan temaları üret (başka tema üretme).\n"
            )
        )

    consult_results: List[ConsultResult] = []
    parsed_sets: List[Dict[str, Any]] = []
    now = _now_iso()
    reports_dir = Path(workspace_root) / ".cache" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    provider_caps = {
        "claude": 3500,
    }
    for provider_id in providers:
        settings = provider_settings(guardrails, provider_id)
        if not settings.get("enabled"):
            consult_results.append(
                ConsultResult(provider_id, settings.get("default_model") or "", "SKIP", "DISABLED", "", None, [])
            )
            continue
        model = settings.get("default_model") or (settings.get("allow_models") or [""])[0]
        if not model:
            consult_results.append(ConsultResult(provider_id, "", "SKIP", "MODEL_MISSING", "", None, []))
            continue
        max_tokens = provider_caps.get(provider_id, 5000)
        chunk_results: List[ConsultResult] = []
        merged = {"themes": []}
        seen_theme_ids = set()
        for chunk_index in (1, 2):
            result = _consult_provider(
                provider_id=provider_id,
                model=model,
                prompt=chunk_prompt(chunk_index, 2),
                max_tokens=max_tokens,
                request_id=f"north_star_theme_bootstrap_{provider_id}_chunk{chunk_index}",
                workspace_root=workspace_root,
                repo_root_path=repo_root_path,
            )
            chunk_results.append(result)
            parsed = _extract_json(result.output_text)
            if parsed and isinstance(parsed, dict):
                for theme in parsed.get("themes", []) if isinstance(parsed.get("themes"), list) else []:
                    theme_id = str(theme.get("theme_id") or theme.get("title_en") or theme.get("title_tr") or "").strip()
                    if not theme_id:
                        continue
                    key = _normalize_theme_id(theme_id)
                    if key in seen_theme_ids:
                        continue
                    seen_theme_ids.add(key)
                    merged["themes"].append(theme)
        merged_ok = len(merged["themes"]) > 0
        combined_output = "\n\n".join([c.output_text for c in chunk_results if c.output_text])
        combined_paths = [p for c in chunk_results for p in c.output_full_paths if p]
        combined = ConsultResult(
            provider_id=provider_id,
            model=model,
            status="OK" if merged_ok else "FAIL",
            error_code=None if merged_ok else "NO_VALID_JSON",
            output_text=combined_output,
            output_full_path=combined_paths[0] if combined_paths else None,
            output_full_paths=combined_paths,
        )
        consult_results.append(combined)
        if merged_ok:
            parsed_sets.append(merged)
        # write per-provider report
        out = {
            "version": "v0.1",
            "generated_at": now,
            "provider_id": provider_id,
            "model": model,
            "status": combined.status,
            "error_code": combined.error_code,
            "output_preview": _preview_text(combined.output_text),
            "output_full_path": combined.output_full_path,
            "output_full_paths": combined.output_full_paths,
        }
        (reports_dir / f"north_star_consult_{provider_id}.v0.1.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False)
        )

    consolidated, conflicts = _consolidate_theme_sets(parsed_sets)

    mechanisms_path = Path(workspace_root) / ".cache" / "index" / "mechanisms.registry.v1.json"
    mechanisms_path.parent.mkdir(parents=True, exist_ok=True)
    mechanisms = {"version": "v1", "generated_at": now, "source": "llm_consult_6", "subjects": []}
    if mechanisms_path.exists():
        try:
            mechanisms = json.loads(mechanisms_path.read_text())
            if "subjects" not in mechanisms:
                mechanisms["subjects"] = []
        except Exception:
            mechanisms = {"version": "v1", "generated_at": now, "source": "llm_consult_6", "subjects": []}

    subject_title_tr = "Etik Programı" if subject_id == "ethics_program" else subject_id
    subject_title_en = "Ethics Program" if subject_id == "ethics_program" else subject_id
    subject_entry = {
        "subject_id": subject_id,
        "subject_title_tr": subject_title_tr,
        "subject_title_en": subject_title_en,
        "status": "ACTIVE" if approve_effective else "PROPOSED",
        "approval_required": True,
        "approved_at": now if approve_effective else None,
        "approval_mode": "auto_env" if auto_approve else ("manual_flag" if approve else "none"),
        "themes": consolidated,
    }
    # replace existing subject
    mechanisms["subjects"] = [s for s in mechanisms.get("subjects", []) if s.get("subject_id") != subject_id]
    mechanisms["subjects"].append(subject_entry)
    mechanisms["generated_at"] = now
    mechanisms_path.write_text(json.dumps(mechanisms, indent=2, ensure_ascii=False))

    # consolidation report
    consolidation_md = reports_dir / "theme_subtheme_consolidation.v0.1.md"
    consolidation_md.write_text(
        "# Theme/Subtheme Consolidation\n\n"
        f"- subject_id: {subject_id}\n"
        f"- providers: {', '.join(providers)}\n"
        f"- status: {'ACTIVE' if approve else 'PROPOSED'}\n\n"
        "## Conflicts\n"
        + ("\n".join(f"- {c}" for c in conflicts) if conflicts else "- none") + "\n"
    )

    closeout = reports_dir / "closeout_theme_subtheme_bootstrap.v0.1.md"
    closeout.write_text(
        "# Closeout — Theme/Subtheme Bootstrap\n\n"
        f"- subject_id: {subject_id}\n"
        f"- status: {'ACTIVE' if approve else 'PROPOSED'}\n"
        f"- providers: {', '.join(providers)}\n"
        f"- mechanisms.registry path: {mechanisms_path}\n"
        f"- consolidation report: {consolidation_md}\n"
    )

    return {
        "status": "OK",
        "subject_id": subject_id,
        "providers": [r.provider_id for r in consult_results],
        "mechanisms_path": str(mechanisms_path),
        "consolidation_report": str(consolidation_md),
        "closeout": str(closeout),
    }


def cmd_north_star_theme_bootstrap(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2
    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2
    subject_id = str(args.subject_id or "").strip()
    if not subject_id:
        warn("FAIL error=SUBJECT_ID_REQUIRED")
        return 2
    providers = [p.strip() for p in (args.providers or "").split(",") if p.strip()]
    if not providers:
        providers = ["openai", "google", "claude", "deepseek", "qwen", "xai"]

    res = run_bootstrap(
        workspace_root=ws,
        subject_id=subject_id,
        approve=bool(args.approve),
        providers=providers,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") == "OK" else 2
