from __future__ import annotations

from pathlib import Path
from typing import Any

from server_utils import _load_json_dict, _safe_preview, _sanitize_text


def _draft_templates(bucket: str, *, requires_core: bool) -> tuple[list[str], list[str]]:
    b = str(bucket or "").strip().upper()
    if b == "ROADMAP":
        ac = [
            "Problem/need net: kim/neyi/niçin (kapsam dışı dahil).",
            "Milestone + tema (theme_id) teyitli; kapsam bu çerçevede sınırlı.",
            "Plan-only mı, execute mu: karar ve gerekçe yazılı.",
            "Doğrulama adımları (UI/ops/policy) tanımlı.",
        ]
        if requires_core:
            ac.append("CORE değişikliği gerekiyorsa CHG + allow_paths + gate sonuçları mevcut.")
        dv = [
            "Roadmap girdisi: başlık + açıklama + milestone + tema + başarı ölçütü.",
            "Uygulama planı: adımlar + riskler + rollback yaklaşımı.",
        ]
        if requires_core:
            dv.append("Gerekiyorsa: ilgili core değişikliği + closeout kanıtları.")
        return ac, dv
    if b == "PROJECT":
        ac = [
            "Proje amacı ve kapsamı net (non-goals dahil).",
            "Kabul kriterleri ve deliverable listesi onaylı.",
            "Owner project (PRJ-*) ve ilk milestone planı belirli.",
            "İlk çalışma paketi (backlog/ticket) projeye bağlanmış.",
        ]
        if requires_core:
            ac.append("CORE değişikliği gerekiyorsa CHG + allow_paths + gate sonuçları mevcut.")
        dv = [
            "Project roadmap: milestone’lar + deliverable’lar + acceptance criteria.",
            "İlk uygulama backlog’u: yapılacaklar + riskler + doğrulama.",
        ]
        if requires_core:
            dv.append("Gerekiyorsa: core değişikliği + closeout kanıtları.")
        return ac, dv
    ac = [
        "İstek kapsamı netleştirildi (problem + hedef + sınırlar).",
        "Kabul kriterleri yazılı ve doğrulanabilir.",
        "Uygulama/plan çıktıları kanıtlandı.",
    ]
    dv = ["Açıklama + kabul kriteri + deliverable listesi üretildi."]
    if requires_core:
        ac.append("CORE değişikliği gerekiyorsa CHG + allow_paths + gate sonuçları mevcut.")
        dv.append("Gerekiyorsa: core değişikliği + closeout kanıtları.")
    return ac, dv


def _build_inbox_draft_v0_2(
    ws_root: Path,
    request_id: str,
    *,
    inbox_index: dict[str, Any] | None = None,
    triage_index: dict[str, Any] | None = None,
) -> tuple[str, str]:
    def _find_by_request_id(obj: dict[str, Any], request_id_value: str) -> dict[str, Any]:
        items = obj.get("items") if isinstance(obj.get("items"), list) else []
        for item in items:
            if isinstance(item, dict) and str(item.get("request_id") or "").strip() == request_id_value:
                return item
        return {}

    inbox_index = (
        inbox_index
        if isinstance(inbox_index, dict)
        else _load_json_dict(ws_root / ".cache" / "index" / "input_inbox.v0.1.json")
    )
    triage_index = (
        triage_index
        if isinstance(triage_index, dict)
        else _load_json_dict(ws_root / ".cache" / "index" / "manual_request_triage.v0.1.json")
    )

    inbox_item = _find_by_request_id(inbox_index, request_id)
    triage_item = _find_by_request_id(triage_index, request_id)

    intake = inbox_item.get("intake") if isinstance(inbox_item.get("intake"), dict) else {}
    suggested = inbox_item.get("suggested_route") if isinstance(inbox_item.get("suggested_route"), dict) else {}
    classification = triage_item.get("classification") if isinstance(triage_item.get("classification"), dict) else {}

    triage_state = str(triage_item.get("state") or "").strip().upper()
    route_bucket = (
        str(classification.get("route_bucket") or "").strip()
        or str(intake.get("bucket") or "").strip()
        or str(suggested.get("bucket") or "").strip()
    )
    milestone = str(classification.get("milestone") or "").strip()
    theme_id = str(classification.get("theme_id") or "").strip()
    owner_project = str(classification.get("owner_project") or "").strip()
    rationale = str(triage_item.get("rationale") or "").strip()

    evidence_rel = str(inbox_item.get("evidence_path") or "").strip()
    evidence_path = ws_root / evidence_rel.replace("./", "") if evidence_rel else None
    evidence_obj: dict[str, Any] = _load_json_dict(evidence_path) if evidence_path else {}

    raw_text = _sanitize_text(str(evidence_obj.get("text") or "").strip())
    preview = _safe_preview(raw_text, 900) if raw_text else ""

    requires_core = bool(inbox_item.get("requires_core_change") or evidence_obj.get("requires_core_change") or False)
    acceptance, deliverables = _draft_templates(route_bucket, requires_core=requires_core)

    title = str(intake.get("title") or "").strip() or f"Manual request: {request_id}"
    intake_id = str(intake.get("intake_id") or "").strip()

    lines: list[str] = [
        f"# Inbox Taslak: {request_id}",
        "",
        f"- triage_state: {triage_state or '-'}",
        f"- route_bucket: {route_bucket or '-'}",
        f"- milestone: {milestone or '-'}",
        f"- theme_id: {theme_id or '-'}",
        f"- owner_project: {owner_project or '-'}",
        f"- intake_id: {intake_id or '-'}",
        f"- intake_title: {title}",
        f"- evidence_path: {evidence_rel or '-'}",
        "",
    ]
    if preview:
        lines += ["## Kısa Özet (kanıt metninden)", preview, ""]

    lines += ["## Kabul Kriterleri (taslak)"]
    lines += [f"- {x}" for x in acceptance]
    lines += ["", "## Deliverables (taslak)"]
    lines += [f"- {x}" for x in deliverables]
    if rationale:
        lines += ["", "## Notlar", f"- rationale: {rationale}"]

    rel_out = f".cache/reports/inbox_drafts/{request_id}.v0.2.md"
    content = "\n".join(lines).rstrip() + "\n"
    return rel_out, content

