const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const SIDEBAR_STORAGE_KEY = "cockpit_lite_sidebar_collapsed_v1";
const SIDEBAR_COLLAPSED_CLASS = "sidebar-collapsed";
const NORTH_STAR_FINDINGS_ALL_LENSES_KEY = "__ALL_LENSES__";
const ADMIN_REQUIRED_OPS = new Set(["overrides-write"]);
const ADMIN_REQUIRED_ACTIONS = new Set(["run-card-set", "extension-toggle", "settings-set-override"]);
const ADMIN_REQUIRED_ELEMENT_IDS = new Set(["settings-save", "run-card-save"]);
const LANG_STORAGE_KEY = "cockpit_lang.v1";
const SUPPORTED_LANGS = ["en", "tr"];
const OP_JOB_POLLING = new Set();

const I18N = {
  en: {
    "ui.title": "Operator Console",
    "lang.label": "Language",
    "actions.refresh_all": "Refresh All",
    "sidebar.toggle": "Toggle sidebar",
    "nav.primary": "Primary",
    "nav.overview": "Overview",
    "nav.north_star": "North Star",
    "nav.inbox": "Inbox",
    "nav.intake": "Intake",
    "nav.decisions": "Decisions",
    "nav.extensions": "Extensions",
    "nav.overrides": "Overrides",
    "nav.auto_loop": "Auto-loop",
    "nav.jobs": "Jobs",
    "nav.locks": "Locks",
    "nav.run_card": "Run-Card",
    "nav.planner_chat": "Planner Chat",
    "nav.command_composer": "Command Composer",
    "nav.evidence": "Evidence",
    "h.system_status": "System Status",
    "h.work_intake": "Work Intake",
    "h.decisions": "Decisions",
    "h.loop_activity": "Loop Activity",
    "h.locks": "Locks",
    "h.script_budget": "Script Budget",
    "h.next_steps": "Next Steps",
    "h.action_log": "Action Log",
    "h.last_action": "Last Action",
    "h.system_status_raw": "System Status (raw)",
    "h.ui_snapshot_raw": "UI Snapshot (raw)",
    "h.north_star": "North Star",
    "h.lens_summary": "Lens Summary",
    "h.gap_summary": "Gap Summary",
    "h.top_gaps": "Top Gaps",
    "h.lens_details": "Lens Details",
    "h.lens_findings": "Lens Findings",
    "h.raw_json": "Raw JSON",
    "h.input_inbox": "Input Inbox",
    "h.intake_strict": "Intake (strict)",
    "h.decision_inbox": "Decision Inbox",
    "h.extensions": "Extensions",
    "h.extension_detail": "Extension Detail",
    "h.safe_overrides": "Safe Overrides",
    "h.edit_override": "Edit Override",
    "h.auto_loop": "Auto-loop",
    "h.airunner_jobs": "Airrunner Jobs",
    "h.github_ops_jobs": "GitHub Ops Jobs",
    "h.loop_lock": "Loop Lock",
    "h.run_card": "Run-Card",
    "h.planner_threads": "Planner Threads",
    "h.thread_messages": "Thread Messages",
    "h.compose_message": "Compose Message",
    "h.message_detail": "Message Detail",
    "h.evidence_browser": "Evidence Browser",
    "h.command_composer": "Command Composer",
    "h.last_response": "Last Response",
    "admin.mode_state": "Admin mode: {state}",
    "admin.on": "on",
    "admin.off": "off",
    "admin.required_op": "Admin mode required for this operation.",
    "admin.required_action": "Admin mode required for this action.",
    "admin.title_topbar": "Enables write actions and other dangerous operations",
    "admin.title_sidebar": "Enables dangerous actions like force release",
    "admin.save_override": "Save override (confirm required)",
    "admin.save_override_disabled": "Enable Admin mode to save overrides",
    "admin.save_run_card": "Save run-card (confirm required)",
    "admin.save_run_card_disabled": "Enable Admin mode to save run-card",
    "admin.toggle_extensions_disabled": "Enable Admin mode to toggle extensions",
    "modal.confirm_title": "Confirm action",
    "modal.confirm_yes": "Confirm",
    "modal.confirm_no": "Cancel",
    "modal.confirm_text": "Confirm action: {op} {preview}",
    "actions.copied": "Copied",
    "actions.copy_failed": "Copy failed",
    "actions.open": "Open",
    "actions.view": "View",
    "actions.copy": "Copy",
    "actions.edit": "Edit",
    "actions.enable": "Enable",
    "actions.disable": "Disable",
    "actions.remove_tag": "Remove tag",
    "common.on": "on",
    "common.off": "off",
    "common.sample_parens": " (sample)",
    "common.unknown": "(unknown)",
    "error.unknown": "unknown error",
    "state.enabled": "enabled",
    "state.disabled": "disabled",
    "state.present": "present",
    "state.missing": "missing",
    "table.name": "Name",
    "table.action": "Action",
    "table.actions": "Actions",
    "table.bucket": "Bucket",
    "table.status": "Status",
    "table.priority": "Priority",
    "table.severity": "Severity",
    "table.title": "Title",
    "table.created": "Created",
    "table.updated": "Updated",
    "table.extension": "Extension",
    "table.claim": "Claim",
    "table.recommended_action": "Recommendation",
    "table.confidence": "Confidence",
    "table.execution_mode": "Regime",
    "table.evidence_ready": "Evidence",
    "table.decision": "Decision",
    "table.intake": "Intake",
    "table.triage": "Triage",
    "table.request": "Request",
    "table.kind": "Kind",
    "table.domain": "Domain",
    "table.scope": "Scope",
    "table.preview": "Preview",
    "table.evidence": "Evidence",
    "table.question": "Question",
    "table.id": "ID",
    "table.intake_id": "Intake ID",
    "table.job_id": "Job ID",
    "table.failure": "Failure",
    "table.semver": "Semver",
    "table.lens": "Lens",
    "table.score": "Score",
    "table.coverage": "Coverage",
    "table.requirements": "Req OK/Total",
    "table.gap_id": "Gap ID",
    "table.control": "Control",
    "table.risk": "Risk",
    "table.effort": "Effort",
    "table.source": "Source",
    "table.note": "Note",
    "table.requirement": "Requirement",
    "table.ok": "OK",
    "table.key": "Key",
    "table.owner": "Owner",
    "table.expires": "Expires",
    "table.acquired": "Acquired",
    "meta.showing_items": "showing {count} items",
    "meta.showing_notes": "showing {count} notes",
    "locks.group_by_owner": "Group by owner: {state}",
    "locks.claims_meta": "Showing {shown} of {total} active claims{sample} · sorted by expires_at",
    "locks.force_release_disabled_hint": "Admin mode is off. “Force release” is disabled.",
    "evidence.open_in_evidence_title": "Open in Evidence",
    "evidence.pointers_title": "Evidence pointers (click to open)",
    "north_star.detail.summary_label": "summary:",
    "north_star.detail.trend_catalog": "Trend Catalog",
    "north_star.detail.bp_catalog": "BP Catalog",
    "north_star.detail.requirements": "Requirements",
    "north_star.detail.subscores": "Subscores",
    "north_star.detail.lens_json": "Lens JSON",
    "north_star.detail.lens_findings_hint": "Use “Lens Findings” below to browse per-item matches and evidence pointers (lens-by-lens, topic-by-topic).",
    "north_star.detail.evidence_expectations": "Evidence expectations",
    "north_star.detail.remediation_ideas": "Remediation ideas",
    "job.poll_failed": "Job poll failed: {error}",
    "job.poll_timeout": "Job polling timed out: {id}",
    "job.poll_timeout_short": "Job polling timed out: {id}",
    "job.started": "{op}: started (job {id})",
    "job.done": "{op}: {status}",
    "job.already_running": "{op}: already running (tracking {id})",
    "toast.refresh_failed": "Refresh failed ({name}): {error}",
    "toast.select_intake_first": "Select an intake item first.",
    "toast.notes_composer_unavailable": "Notes composer not available.",
    "toast.note_composer_prefilled": "Note composer prefilled for selected intake item.",
    "toast.decision_saved": "Decision saved.",
    "toast.decision_save_failed": "Failed to save decision: {error}",
    "toast.claim_failed": "Claim failed: {error}",
    "toast.admin_required_force_release": "Admin mode required for force release.",
    "prompt.force_release_confirm": "Type FORCE to confirm force release.\n\n- intake_id: {id}\n\nThis clears the claim even if owned by another session.",
    "toast.force_release_canceled": "Force release canceled.",
    "toast.force_release_failed": "Force release failed: {error}",
    "toast.close_manual_only": "Close is only supported for MANUAL_REQUEST tickets.",
    "prompt.close_confirm": "Type CLOSE to confirm closing this ticket.\n\n- intake_id: {id}\n- title: {title}",
    "toast.close_canceled": "Close canceled.",
    "prompt.close_reason": "Optional close reason (free text):",
    "toast.close_failed": "Close failed: {error}",
    "toast.evidence_preview_failed": "Evidence preview failed: {error}",
    "toast.note_load_failed": "Note load failed: {error}",
    "toast.invalid_json": "Invalid JSON: {error}",
    "toast.op_failed": "OP failed: {error}",
    "toast.action_failed": "Action failed: {error}",
    "toast.usage_op": "Usage: /op <name> <json>",
    "toast.invalid_json_op": "Invalid JSON for /op: {error}",
    "toast.usage_decision": "Usage: /decision <decision_id> <option_id>",
    "toast.usage_override": "Usage: /override <policy_*.override.v1.json> <json>",
    "toast.override_json_required": "Override JSON required.",
    "toast.invalid_json_override": "Invalid JSON for override: {error}",
    "toast.select_override_first": "Select an override first.",
    "toast.select_op_first": "Select an op first.",
    "toast.link_kind_required": "Link kind and id/path required.",
    "toast.title_or_body_required": "Title or body required.",
    "evidence.loading": "loading…",
    "evidence.load_failed": "Failed to load evidence: {error}",
    "evidence.none_selected": "no evidence selected",
    "common.no_selection": "no selection",
    "common.none": "none",
    "action.no_actions_status": "no actions yet",
    "action.last_action": "last action: {op} ({status})",
    "status.api": "API: {status}",
    "status.sse": "SSE: {status}",
    "status.disconnected": "DISCONNECTED",
    "sidebar.workspace": "workspace: {path}",
    "sidebar.last_change": "last change: {ts}",
    "intake.field.topic": "Topic",
    "intake.field.why": "Why",
    "intake.field.bucket": "Bucket",
    "intake.field.status": "Status",
    "intake.field.priority": "Priority",
    "intake.field.severity": "Severity",
    "intake.field.layer": "Layer",
    "intake.field.source_type": "Source type",
    "intake.field.source_ref": "Source ref",
    "intake.field.autopilot_allowed": "Autopilot allowed",
    "intake.field.autopilot_selected": "Autopilot selected",
    "intake.field.ingested_at": "Ingested at",
    "intake.field.evidence_paths": "Evidence paths",
    "intake.field.claim_status": "Claim status",
    "intake.field.claim_owner": "Claim owner",
    "intake.field.claim_expires": "Claim expires",
    "intake.field.exec_lease_status": "Exec lease status",
    "intake.field.exec_lease_owner": "Exec lease owner",
    "intake.field.exec_lease_expires": "Exec lease expires",
    "intake.item_fallback": "intake item",
    "intake.why.derived_from": "Derived from {source}",
    "intake.why.no_rationale": "No explicit rationale field; inspect evidence paths for provenance.",
    "intake.decision.banner_missing": "Decision data unavailable (missing decision artifacts). Intake still usable.",
    "intake.inline.tab_decision": "Decision",
    "intake.inline.tab_technical": "Technical",
    "intake.decision.save": "Save",
    "intake.decision.note_placeholder": "Optional note…",
    "intake.decision.no_overlay": "No decision card available for this item.",
    "notes.for_item.none": "Notes for this item: -",
    "notes.for_item.loading": "Notes for this item: loading…",
    "notes.for_item.error": "Notes for this item: error",
    "notes.for_item.count": "Notes for this item: {count}",
    "notes.linked.loading": "Loading notes linked to this intake item…",
    "notes.linked.failed": "Failed to load linked notes: {error}",
    "notes.linked.none": "No notes linked to this item yet. Use “Create note” to add context.",
    "notes.untitled": "(untitled)",
    "notes.item_meta": "updated: {updated} · id: {id}",
    "notes.thread_meta": "count={count} last={last}",
    "notes.open": "Open",
    "notes.links.none": "no links added",
    "notes.links.remove": "Remove",
    "notes.no_note_selected": "no note selected",
    "notes.prefill.context_header": "Context (from intake):",
    "notes.prefill.evidence_header": "Evidence paths:",
    "notes.prefill.next_header": "What do we want to do next?",
    "notes.prefill.next_placeholder": "- (write your plan / decision / rationale here)",
    "notes.prefill.none": "- (none)",
    "overview.banner.no_intake": "No actionable intake. You may add a request.",
    "overview.banner.ready": "Ready. Use safe defaults or run a bounded loop.",
    "overview.banner.decisions_pending": "Decisions pending ({count}). Open Decisions.",
    "overview.next.decision_pending": "Decision pending: open Decisions tab.",
    "overview.next.no_intake": "No intake items. Check sources.",
    "overview.next.no_blockers": "No immediate blockers. Consider auto-loop or new intake.",
    "north_star.all_lenses": "All lenses",
    "north_star.select_lens_hint": "Select a lens to explore findings.",
    "north_star.no_findings": "(no findings)",
    "north_star.unknown": "(unknown)",
    "north_star.table.lens": "Lens",
    "north_star.table.match": "Match",
    "north_star.table.topic": "Topic",
    "north_star.table.domain": "Domain",
    "north_star.table.title": "Title",
    "north_star.table.theme": "Tema (Theme)",
    "north_star.table.subtheme": "Alt Tema (Subtheme)",
    "north_star.table.catalog": "Catalog",
    "north_star.table.id": "ID",
    "north_star.table.reasons": "Reasons",
    "north_star.table.evidence": "Evidence",
    "north_star.join.banner": "Theme/Subtheme join missing for {miss} findings (title fallback {fallback}){reason}",
    "north_star.catalog.reference": "Referans (Reference)",
    "north_star.catalog.capability": "Yapı Taşı (Capability)",
    "north_star.catalog.criterion": "Kriter (Criterion)",
    "north_star.preset.custom": "Custom (manual selection)",
    "north_star.preset.all": "All (no topic filter)",
    "north_star.preset.ethics_compliance": "Ethics & Compliance",
    "north_star.preset.compliance_control": "Compliance / risk / assurance / control",
    "north_star.preset.context_alignment": "Context alignment",
    "north_star.preset.sustainability_ethics": "Sustainability & Ethics",
    "composer.run_confirm": "Run (confirm)",
    "composer.allowlist_hint": "Allowlist only. Responses are stored as system notes in the current thread.",
    "composer.no_response_yet": "no response yet",
    "intake.claim.meta_none": "Claim: -",
    "intake.claim.meta_claimed_you": "Claim: CLAIMED by you (expires {expires})",
    "intake.claim.meta_claimed_other": "Claim: CLAIMED by {owner} (expires {expires})",
    "intake.claim.meta_free": "Claim: FREE (click Claim to reserve)",
    "intake.claim.btn_claim": "Claim",
    "intake.claim.btn_renew": "Renew",
    "intake.claim.btn_release": "Release",
    "intake.claim.btn_force_release": "Force release",
    "intake.close.meta_none": "Close: -",
    "intake.close.meta_unavailable": "Close: (not available for this item)",
    "intake.close.meta_available": "Close: available (manual request)",
    "intake.close.meta_done": "Close: DONE{reason}",
    "intake.close.btn_close": "Close",
    "intake.close.btn_closed": "Closed",
    "empty.no_actions": "No actions yet.",
    "empty.no_items": "No items.",
    "empty.no_findings_match": "No findings match the current filters.",
    "empty.select_finding_row": "Select a finding row to inspect details.",
    "empty.no_lens_details": "No lens details.",
    "empty.no_active_claims": "No active claims.",
    "empty.no_extensions_found": "No extensions found.",
    "empty.no_overrides_found": "No overrides found.",
    "empty.no_chat_messages": "No chat messages yet.",
    "empty.no_notes": "No notes yet.",
    "empty.no_threads": "No threads yet.",
    "empty.no_evidence_found": "No evidence found.",
  },
  tr: {
    "ui.title": "Operatör Konsolu",
    "lang.label": "Dil",
    "actions.refresh_all": "Tümünü Yenile",
    "sidebar.toggle": "Sidebar’ı aç/kapat",
    "nav.primary": "Ana gezinme",
    "nav.overview": "Genel Bakış",
    "nav.north_star": "Kuzey Yıldızı",
    "nav.inbox": "Gelen Kutusu",
    "nav.intake": "İş Alımı",
    "nav.decisions": "Kararlar",
    "nav.extensions": "Eklentiler",
    "nav.overrides": "Override'lar",
    "nav.auto_loop": "Oto Döngü",
    "nav.jobs": "İşler",
    "nav.locks": "Kilitler",
    "nav.run_card": "Koşu Kartı",
    "nav.planner_chat": "Planlayıcı Sohbet",
    "nav.command_composer": "Komut Oluşturucu",
    "nav.evidence": "Kanıt",
    "h.system_status": "Sistem Durumu",
    "h.work_intake": "İş Alımı",
    "h.decisions": "Kararlar",
    "h.loop_activity": "Döngü Aktivitesi",
    "h.locks": "Kilitler",
    "h.script_budget": "Script Bütçesi",
    "h.next_steps": "Sonraki Adımlar",
    "h.action_log": "Aksiyon Günlüğü",
    "h.last_action": "Son Aksiyon",
    "h.system_status_raw": "Sistem Durumu (ham)",
    "h.ui_snapshot_raw": "UI Snapshot (ham)",
    "h.north_star": "Kuzey Yıldızı",
    "h.lens_summary": "Lens Özeti",
    "h.gap_summary": "Açık Özeti",
    "h.top_gaps": "En Büyük Açıklar",
    "h.lens_details": "Lens Detayları",
    "h.lens_findings": "Lens Bulguları",
    "h.raw_json": "Ham JSON",
    "h.input_inbox": "Girdi Kutusu",
    "h.intake_strict": "İş Alımı (sıkı)",
    "h.decision_inbox": "Karar Kutusu",
    "h.extensions": "Eklentiler",
    "h.extension_detail": "Eklenti Detayı",
    "h.safe_overrides": "Güvenli Override'lar",
    "h.edit_override": "Override Düzenle",
    "h.auto_loop": "Oto Döngü",
    "h.airunner_jobs": "Airrunner İşleri",
    "h.github_ops_jobs": "GitHub Ops İşleri",
    "h.loop_lock": "Döngü Kilidi",
    "h.run_card": "Koşu Kartı",
    "h.planner_threads": "Planlayıcı Thread'leri",
    "h.thread_messages": "Thread Mesajları",
    "h.compose_message": "Mesaj Yaz",
    "h.message_detail": "Mesaj Detayı",
    "h.evidence_browser": "Kanıt Tarayıcısı",
    "h.command_composer": "Komut Oluşturucu",
    "h.last_response": "Son Yanıt",
    "admin.mode_state": "Admin modu: {state}",
    "admin.on": "açık",
    "admin.off": "kapalı",
    "admin.required_op": "Bu işlem için Admin modu gerekli.",
    "admin.required_action": "Bu aksiyon için Admin modu gerekli.",
    "admin.title_topbar": "Yazma aksiyonlarını ve diğer riskli işlemleri açar",
    "admin.title_sidebar": "Force release gibi riskli aksiyonları açar",
    "admin.save_override": "Override kaydet (onay gerekir)",
    "admin.save_override_disabled": "Override kaydetmek için Admin modunu açın",
    "admin.save_run_card": "Run-card kaydet (onay gerekir)",
    "admin.save_run_card_disabled": "Run-card kaydetmek için Admin modunu açın",
    "admin.toggle_extensions_disabled": "Eklentileri aç/kapatmak için Admin modunu açın",
    "modal.confirm_title": "İşlemi onayla",
    "modal.confirm_yes": "Onayla",
    "modal.confirm_no": "Vazgeç",
    "modal.confirm_text": "İşlemi onayla: {op} {preview}",
    "actions.copied": "Kopyalandı",
    "actions.copy_failed": "Kopyalama başarısız",
    "actions.open": "Aç",
    "actions.view": "Görüntüle",
    "actions.copy": "Kopyala",
    "actions.edit": "Düzenle",
    "actions.enable": "Etkinleştir",
    "actions.disable": "Devre dışı bırak",
    "actions.remove_tag": "Etiketi kaldır",
    "common.on": "açık",
    "common.off": "kapalı",
    "common.sample_parens": " (örnek)",
    "common.unknown": "(bilinmiyor)",
    "error.unknown": "bilinmeyen hata",
    "state.enabled": "etkin",
    "state.disabled": "devre dışı",
    "state.present": "mevcut",
    "state.missing": "yok",
    "table.name": "Ad",
    "table.action": "Aksiyon",
    "table.actions": "Aksiyonlar",
    "table.bucket": "Kova",
    "table.status": "Durum",
    "table.priority": "Öncelik",
    "table.severity": "Şiddet",
    "table.title": "Başlık",
    "table.created": "Oluşturma",
    "table.updated": "Güncelleme",
    "table.extension": "Eklenti",
    "table.claim": "Claim",
    "table.recommended_action": "Öneri",
    "table.confidence": "Güven",
    "table.execution_mode": "Rejim",
    "table.evidence_ready": "Kanıt",
    "table.decision": "Karar",
    "table.intake": "İş Alımı",
    "table.triage": "Triage",
    "table.request": "İstek",
    "table.kind": "Tür",
    "table.domain": "Alan",
    "table.scope": "Kapsam",
    "table.preview": "Önizleme",
    "table.evidence": "Kanıt",
    "table.question": "Soru",
    "table.id": "ID",
    "table.intake_id": "İş Alımı ID",
    "table.job_id": "İş ID",
    "table.failure": "Hata",
    "table.semver": "Semver",
    "table.lens": "Lens",
    "table.score": "Skor",
    "table.coverage": "Kapsama",
    "table.requirements": "Gereksinim OK/Toplam",
    "table.gap_id": "Açık ID",
    "table.control": "Kontrol",
    "table.risk": "Risk",
    "table.effort": "Efor",
    "table.source": "Kaynak",
    "table.note": "Not",
    "table.requirement": "Gereksinim",
    "table.ok": "OK",
    "table.key": "Anahtar",
    "table.owner": "Sahip",
    "table.expires": "Bitiş",
    "table.acquired": "Alınma",
    "meta.showing_items": "{count} öğe gösteriliyor",
    "meta.showing_notes": "{count} not gösteriliyor",
    "locks.group_by_owner": "Sahibe göre grupla: {state}",
    "locks.claims_meta": "{shown}/{total} aktif claim gösteriliyor{sample} · expires_at sıralı",
    "locks.force_release_disabled_hint": "Admin modu kapalı. “Zorla bırak” devre dışı.",
    "evidence.open_in_evidence_title": "Kanıt'ta aç",
    "evidence.pointers_title": "Kanıt işaretçileri (açmak için tıkla)",
    "north_star.detail.summary_label": "özet:",
    "north_star.detail.trend_catalog": "Trend Kataloğu",
    "north_star.detail.bp_catalog": "BP Kataloğu",
    "north_star.detail.requirements": "Gereksinimler",
    "north_star.detail.subscores": "Alt skorlar",
    "north_star.detail.lens_json": "Lens JSON",
    "north_star.detail.lens_findings_hint": "Aşağıdaki “Lens Bulguları” ile bulgu eşleşmelerini ve kanıt işaretçilerini gezebilirsiniz (lens lens, konu konu).",
    "north_star.detail.evidence_expectations": "Kanıt beklentileri",
    "north_star.detail.remediation_ideas": "İyileştirme fikirleri",
    "job.poll_failed": "İş takibi başarısız: {error}",
    "job.poll_timeout": "İş takibi zaman aşımına uğradı: {id}",
    "job.poll_timeout_short": "İş takibi zaman aşımı: {id}",
    "job.started": "{op}: başlatıldı (iş {id})",
    "job.done": "{op}: {status}",
    "job.already_running": "{op}: zaten çalışıyor (takip: {id})",
    "toast.refresh_failed": "Yenileme başarısız ({name}): {error}",
    "toast.select_intake_first": "Önce bir iş alımı öğesi seçin.",
    "toast.notes_composer_unavailable": "Not editörü mevcut değil.",
    "toast.note_composer_prefilled": "Not editörü seçili öğeye göre dolduruldu.",
    "toast.decision_saved": "Karar kaydedildi.",
    "toast.decision_save_failed": "Karar kaydı başarısız: {error}",
    "toast.claim_failed": "Sahiplenme başarısız: {error}",
    "toast.admin_required_force_release": "Zorla bırakma için Admin modu gerekli.",
    "prompt.force_release_confirm": "Zorla bırakmayı onaylamak için FORCE yazın.\n\n- intake_id: {id}\n\nBu işlem, başka bir oturuma ait olsa bile claim'i temizler.",
    "toast.force_release_canceled": "Zorla bırakma iptal edildi.",
    "toast.force_release_failed": "Zorla bırakma başarısız: {error}",
    "toast.close_manual_only": "Kapatma sadece MANUAL_REQUEST ticket'ları için desteklenir.",
    "prompt.close_confirm": "Bu ticket'ı kapatmayı onaylamak için CLOSE yazın.\n\n- intake_id: {id}\n- başlık: {title}",
    "toast.close_canceled": "Kapatma iptal edildi.",
    "prompt.close_reason": "Opsiyonel kapanma nedeni (serbest metin):",
    "toast.close_failed": "Kapatma başarısız: {error}",
    "toast.evidence_preview_failed": "Kanıt önizleme başarısız: {error}",
    "toast.note_load_failed": "Not yükleme başarısız: {error}",
    "toast.invalid_json": "Geçersiz JSON: {error}",
    "toast.op_failed": "OP başarısız: {error}",
    "toast.action_failed": "Aksiyon başarısız: {error}",
    "toast.usage_op": "Kullanım: /op <ad> <json>",
    "toast.invalid_json_op": "/op için geçersiz JSON: {error}",
    "toast.usage_decision": "Kullanım: /decision <decision_id> <option_id>",
    "toast.usage_override": "Kullanım: /override <policy_*.override.v1.json> <json>",
    "toast.override_json_required": "Override JSON gerekli.",
    "toast.invalid_json_override": "Override için geçersiz JSON: {error}",
    "toast.select_override_first": "Önce bir override seçin.",
    "toast.select_op_first": "Önce bir op seçin.",
    "toast.link_kind_required": "Link türü ve id/yol gerekli.",
    "toast.title_or_body_required": "Başlık veya gövde gerekli.",
    "evidence.loading": "yükleniyor…",
    "evidence.load_failed": "Kanıt yüklenemedi: {error}",
    "evidence.none_selected": "kanıt seçilmedi",
    "common.no_selection": "seçim yok",
    "common.none": "yok",
    "action.no_actions_status": "henüz aksiyon yok",
    "action.last_action": "son işlem: {op} ({status})",
    "status.api": "API: {status}",
    "status.sse": "SSE: {status}",
    "status.disconnected": "BAĞLI DEĞİL",
    "sidebar.workspace": "çalışma alanı: {path}",
    "sidebar.last_change": "son değişiklik: {ts}",
    "intake.field.topic": "Konu",
    "intake.field.why": "Neden",
    "intake.field.bucket": "Kategori",
    "intake.field.status": "Durum",
    "intake.field.priority": "Öncelik",
    "intake.field.severity": "Şiddet",
    "intake.field.layer": "Katman",
    "intake.field.source_type": "Kaynak türü",
    "intake.field.source_ref": "Kaynak ref",
    "intake.field.autopilot_allowed": "Autopilot izinli",
    "intake.field.autopilot_selected": "Autopilot seçildi",
    "intake.field.ingested_at": "Alınma zamanı",
    "intake.field.evidence_paths": "Kanıt yolları",
    "intake.field.claim_status": "Claim durumu",
    "intake.field.claim_owner": "Claim sahibi",
    "intake.field.claim_expires": "Claim bitiş",
    "intake.field.exec_lease_status": "Exec lease durumu",
    "intake.field.exec_lease_owner": "Exec lease sahibi",
    "intake.field.exec_lease_expires": "Exec lease bitiş",
    "intake.item_fallback": "intake öğesi",
    "intake.why.derived_from": "Kaynak: {source}",
    "intake.why.no_rationale": "Açık bir gerekçe alanı yok; köken için kanıt yollarını inceleyin.",
    "intake.decision.banner_missing": "Karar verisi yüklenemedi (decision artefact'ları yok). Intake yine de kullanılabilir.",
    "intake.inline.tab_decision": "Karar",
    "intake.inline.tab_technical": "Teknik",
    "intake.decision.save": "Kaydet",
    "intake.decision.note_placeholder": "İsteğe bağlı not…",
    "intake.decision.no_overlay": "Bu öğe için karar kartı yok.",
    "notes.for_item.none": "Bu öğe için notlar: -",
    "notes.for_item.loading": "Bu öğe için notlar: yükleniyor…",
    "notes.for_item.error": "Bu öğe için notlar: hata",
    "notes.for_item.count": "Bu öğe için notlar: {count}",
    "notes.linked.loading": "Bu intake öğesine bağlı notlar yükleniyor…",
    "notes.linked.failed": "Bağlı notlar yüklenemedi: {error}",
    "notes.linked.none": "Bu öğeye bağlı not yok. Bağlam eklemek için “Not oluştur” kullanın.",
    "notes.untitled": "(başlıksız)",
    "notes.item_meta": "güncellendi: {updated} · id: {id}",
    "notes.thread_meta": "adet={count} son={last}",
    "notes.open": "Aç",
    "notes.links.none": "link eklenmedi",
    "notes.links.remove": "Kaldır",
    "notes.no_note_selected": "not seçilmedi",
    "notes.prefill.context_header": "Bağlam (intake'den):",
    "notes.prefill.evidence_header": "Kanıt yolları:",
    "notes.prefill.next_header": "Sonraki adım ne olsun?",
    "notes.prefill.next_placeholder": "- (buraya plan / karar / gerekçe yazın)",
    "notes.prefill.none": "- (yok)",
    "overview.banner.no_intake": "Aksiyonlanabilir intake yok. Yeni bir istek ekleyebilirsiniz.",
    "overview.banner.ready": "Hazır. Safe defaults kullanın veya sınırlı bir döngü çalıştırın.",
    "overview.banner.decisions_pending": "Bekleyen kararlar var ({count}). Kararlar sekmesini açın.",
    "overview.next.decision_pending": "Bekleyen karar: Kararlar sekmesini açın.",
    "overview.next.no_intake": "İş alımı öğesi yok. Kaynakları kontrol edin.",
    "overview.next.no_blockers": "Acil engel yok. Oto döngü veya yeni intake düşünebilirsiniz.",
    "north_star.all_lenses": "Tüm lensler",
    "north_star.select_lens_hint": "Bulgu keşfi için bir lens seçin.",
    "north_star.no_findings": "(bulgu yok)",
    "north_star.unknown": "(bilinmiyor)",
    "north_star.table.lens": "Lens",
    "north_star.table.match": "Eşleşme",
    "north_star.table.topic": "Konu",
    "north_star.table.domain": "Alan",
    "north_star.table.title": "Başlık",
    "north_star.table.theme": "Tema (Theme)",
    "north_star.table.subtheme": "Alt Tema (Subtheme)",
    "north_star.table.catalog": "Katalog",
    "north_star.table.id": "ID",
    "north_star.table.reasons": "Gerekçeler",
    "north_star.table.evidence": "Kanıt",
    "north_star.join.banner": "Tema/Alt tema eşleşmesi {miss} bulguda yok (başlık eşleşmesi: {fallback}){reason}",
    "north_star.catalog.reference": "Referans (Reference)",
    "north_star.catalog.capability": "Yapı Taşı (Capability)",
    "north_star.catalog.criterion": "Kriter (Criterion)",
    "north_star.preset.custom": "Özel (manuel seçim)",
    "north_star.preset.all": "Tümü (konu filtresi yok)",
    "north_star.preset.ethics_compliance": "Etik & Uyum",
    "north_star.preset.compliance_control": "Uyum / risk / güvence / kontrol",
    "north_star.preset.context_alignment": "Bağlam uyumu",
    "north_star.preset.sustainability_ethics": "Sürdürülebilirlik & Etik",
    "composer.run_confirm": "Çalıştır (onay)",
    "composer.allowlist_hint": "Sadece allowlist. Yanıtlar mevcut thread altında sistem notu olarak saklanır.",
    "composer.no_response_yet": "henüz yanıt yok",
    "intake.claim.meta_none": "Claim: -",
    "intake.claim.meta_claimed_you": "Claim: CLAIMED (sizde) (bitiş {expires})",
    "intake.claim.meta_claimed_other": "Claim: CLAIMED ({owner}) (bitiş {expires})",
    "intake.claim.meta_free": "Claim: FREE (Claim ile rezerve edin)",
    "intake.claim.btn_claim": "Sahiplen",
    "intake.claim.btn_renew": "Yenile",
    "intake.claim.btn_release": "Bırak",
    "intake.claim.btn_force_release": "Zorla bırak",
    "intake.close.meta_none": "Close: -",
    "intake.close.meta_unavailable": "Close: (bu öğe için kullanılamaz)",
    "intake.close.meta_available": "Close: kullanılabilir (manuel istek)",
    "intake.close.meta_done": "Close: DONE{reason}",
    "intake.close.btn_close": "Kapat",
    "intake.close.btn_closed": "Kapalı",
    "empty.no_actions": "Henüz aksiyon yok.",
    "empty.no_items": "Öğe yok.",
    "empty.no_findings_match": "Mevcut filtrelerle eşleşen bulgu yok.",
    "empty.select_finding_row": "Detay için bir bulgu satırı seçin.",
    "empty.no_lens_details": "Lens detayı yok.",
    "empty.no_active_claims": "Aktif claim yok.",
    "empty.no_extensions_found": "Eklenti bulunamadı.",
    "empty.no_overrides_found": "Override bulunamadı.",
    "empty.no_chat_messages": "Henüz chat mesajı yok.",
    "empty.no_notes": "Henüz not yok.",
    "empty.no_threads": "Henüz thread yok.",
    "empty.no_evidence_found": "Kanıt bulunamadı.",
  },
};

function t(key, vars = null) {
  const lang = SUPPORTED_LANGS.includes(state.lang) ? state.lang : "en";
  const dict = I18N[lang] || I18N.en;
  let out = dict[key] ?? I18N.en[key] ?? String(key || "");
  if (vars && typeof vars === "object") {
    Object.entries(vars).forEach(([k, v]) => {
      out = out.replaceAll(`{${k}}`, String(v));
    });
  }
  return out;
}

function readSidebarCollapsedFromStorage() {
  try {
    const raw = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (!raw) return false;
    const v = String(raw).trim().toLowerCase();
    return v === "1" || v === "true" || v === "yes" || v === "on";
  } catch (_) {
    return false;
  }
}

function writeSidebarCollapsedToStorage(collapsed) {
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
  } catch (_) {
    // Best-effort only (e.g. private browsing).
  }
}

function isSidebarCollapsed() {
  return document.documentElement.classList.contains(SIDEBAR_COLLAPSED_CLASS);
}

function applySidebarCollapsedState(collapsed, { persist = true } = {}) {
  if (collapsed) document.documentElement.classList.add(SIDEBAR_COLLAPSED_CLASS);
  else document.documentElement.classList.remove(SIDEBAR_COLLAPSED_CLASS);
  if (persist) writeSidebarCollapsedToStorage(collapsed);
}

const endpoints = {
  ws: "/api/ws",
  overview: "/api/overview",
  northStar: "/api/north_star",
  status: "/api/status",
  snapshot: "/api/ui_snapshot",
  inbox: "/api/inbox",
  intake: "/api/intake",
  decisions: "/api/decisions",
  decisionMark: "/api/decision_mark",
  extensions: "/api/extensions",
  overridesList: "/api/overrides/list",
  overridesGet: "/api/overrides/get",
  jobs: "/api/jobs",
  airunnerJobs: "/api/airunner_jobs",
  locks: "/api/locks",
  runCard: "/api/run_card",
  runCardSet: "/api/run_card/set",
  budget: "/api/budget",
  plannerThreads: "/api/planner_chat/threads",
  plannerChat: "/api/planner_chat",
  notes: "/api/notes",
  notesSearch: "/api/notes/search",
  noteGet: "/api/notes/get",
  evidenceList: "/api/evidence/list",
  evidenceRead: "/api/evidence/read",
  evidenceRaw: "/api/evidence/raw",
  file: "/api/file",
  chat: "/api/chat",
  settingsSet: "/api/settings/set_override",
  extensionToggle: "/api/extensions/toggle",
};

const state = {
  lang: "tr",
  ws: null,
  overview: null,
  northStar: null,
  northStarFindings: null,
  northStarFindingsByLens: null,
  northStarFindingsLensName: "",
  northStarFindingSelected: null,
  northStarCatalogIndex: null,
  northStarFindingsJoinStats: null,
  status: null,
  snapshot: null,
  inbox: null,
  intake: null,
  intakeSelectedId: null,
  intakeSelected: null,
  intakeExpandedId: null,
  intakeInlineTab: {},
  intakeEvidencePath: null,
  intakeEvidencePreview: null,
  intakeLinkedNotes: null,
  intakeLinkedNotesLoading: false,
  intakeLinkedNotesError: null,
  intakeClaimPending: false,
  intakeClosePending: false,
  claimOwnerTag: null,
  decisions: null,
  extensions: null,
  extensionDetail: null,
  overrides: null,
  overridesDetail: null,
  overridesSelected: null,
  jobs: null,
  airunnerJobs: null,
  locks: null,
  cockpitDecisionArtifacts: {
    ok: false,
    loaded_at: null,
    index: null,
    queue: null,
    overlay: null,
    userMarks: null,
    error: null,
  },
  adminModeEnabled: false,
  lockClaimsLimit: 20,
  lockClaimsGroupByOwner: false,
  runCard: null,
  budget: null,
  plannerThreads: null,
  plannerThread: "default",
  notes: null,
  noteDetail: null,
  noteLinks: [],
  selectedNoteId: null,
  chatInput: "",
  evidenceList: null,
  evidenceSelected: null,
  lastAction: null,
  actionLog: [],
  sseConnected: false,
  actionPending: false,
  opJobsInProgress: {},
  activeTab: "overview",
  didInitialRefresh: false,
  tagSelectActiveIndex: {
    intake: {},
    northStarFindings: {},
  },
  sort: {
    inbox: { key: "created_at", dir: "desc" },
    intake: { key: "bucket", dir: "asc" },
    decisions: { key: "decision_kind", dir: "asc" },
    jobs: { key: "created_at", dir: "desc" },
    notes: { key: "updated_at", dir: "desc" },
  },
  filters: {
    intake: {
      bucket: [],
      status: [],
      source: [],
      extension: [],
    },
    northStarFindings: {
      search: "",
      preset: "CUSTOM",
      domain: [],
      topic: [],
      match: ["TRIGGERED"],
      catalog: [],
    },
  },
  filterOptions: {
    intake: {
      bucket: [],
      status: [],
      source: [],
      extension: [],
    },
    northStarFindings: {
      domain: [],
      topic: [],
      match: ["TRIGGERED", "NOT_TRIGGERED", "UNKNOWN"],
      catalog: ["trend", "bp", "lens"],
    },
  },
};

let northStarFindingsUiAttached = false;
let northStarFindingsControlsAttached = false;

function unwrap(payload) {
  return payload && payload.data ? payload.data : payload;
}

function formatError(err) {
  if (!err) return t("error.unknown");
  if (typeof err === "string") return err;
  const msg = err.message || String(err);
  return msg.length > 220 ? msg.slice(0, 220) + "..." : msg;
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const raw = await res.text();
  const trimmed = raw.trim();
  let data = null;
  try {
    data = trimmed ? JSON.parse(trimmed) : {};
  } catch (err) {
    const prefix = trimmed ? trimmed.slice(0, 180).replace(/\s+/g, " ").trim() : "";
    throw new Error(`Non-JSON response (${res.status}) from ${url}${prefix ? `: ${prefix}` : ""}`);
  }
  if (!res.ok) {
    const hint = typeof data === "object" && data && data.error ? `: ${data.error}` : "";
    throw new Error(`HTTP ${res.status} ${res.statusText} for ${url}${hint}`);
  }
  return data;
}

function setBadge(el, status) {
  if (!el) return;
  const norm = String(status || "UNKNOWN").toUpperCase();
  el.classList.remove("ok", "warn", "fail", "idle");
  if (norm.includes("FAIL")) el.classList.add("fail");
  else if (norm.includes("WARN")) el.classList.add("warn");
  else if (norm.includes("PENDING") || norm.includes("RUNNING")) el.classList.add("idle");
  else if (norm.includes("IDLE")) el.classList.add("idle");
  else el.classList.add("ok");
  el.textContent = norm;
}

function showToast(message, kind = "ok") {
  const container = $("#toast-container");
  if (!container) return;
  const div = document.createElement("div");
  div.className = `toast ${kind}`;
  div.textContent = message;
  container.appendChild(div);
  setTimeout(() => div.remove(), 3000);
}

function clampIndex(value, length) {
  const len = Number.isFinite(Number(length)) ? Math.max(0, parseInt(String(length), 10)) : 0;
  if (len <= 0) return 0;
  const idx = Number.isFinite(Number(value)) ? parseInt(String(value), 10) : 0;
  return Math.max(0, Math.min(idx, len - 1));
}

function setAriaExpanded(el, expanded) {
  if (!el) return;
  el.setAttribute("aria-expanded", expanded ? "true" : "false");
  if (!expanded) el.removeAttribute("aria-activedescendant");
}

function getTagSelectActiveIndex(scope, field, optionsLength) {
  const scopeKey = String(scope || "");
  const fieldKey = String(field || "");
  const map = state.tagSelectActiveIndex?.[scopeKey];
  const raw = map && typeof map === "object" ? map[fieldKey] : 0;
  return clampIndex(raw, optionsLength);
}

function setTagSelectActiveIndex(scope, field, idx, optionsLength = null) {
  const scopeKey = String(scope || "");
  const fieldKey = String(field || "");
  if (!state.tagSelectActiveIndex || typeof state.tagSelectActiveIndex !== "object") {
    state.tagSelectActiveIndex = {};
  }
  const map =
    state.tagSelectActiveIndex[scopeKey] && typeof state.tagSelectActiveIndex[scopeKey] === "object"
      ? state.tagSelectActiveIndex[scopeKey]
      : {};
  state.tagSelectActiveIndex[scopeKey] = map;
  map[fieldKey] = optionsLength === null ? idx : clampIndex(idx, optionsLength);
}

function scrollTagSelectActiveOptionIntoView(optionsEl) {
  if (!optionsEl) return;
  const active = optionsEl.querySelector(".tag-option.active");
  if (!active || typeof active.scrollIntoView !== "function") return;
  active.scrollIntoView({ block: "nearest" });
}

const _refreshQueue = {};

function scheduleRefresh(name, fn, delayMs = 220) {
  const key = String(name || "refresh");
  if (!_refreshQueue[key]) {
    _refreshQueue[key] = { timer: null, inFlight: false, pending: false, fn: null };
  }
  const entry = _refreshQueue[key];
  entry.fn = fn;
  entry.pending = true;
  if (entry.timer) clearTimeout(entry.timer);
  entry.timer = setTimeout(() => runScheduledRefresh(key), delayMs);
}

async function runScheduledRefresh(key) {
  const entry = _refreshQueue[String(key || "")];
  if (!entry) return;
  entry.timer = null;
  if (entry.inFlight) return;
  if (!entry.pending) return;
  entry.pending = false;
  entry.inFlight = true;
  try {
    await entry.fn?.();
  } catch (err) {
    showToast(t("toast.refresh_failed", { name: String(key), error: formatError(err) }), "warn");
  } finally {
    entry.inFlight = false;
    if (entry.pending) {
      entry.timer = setTimeout(() => runScheduledRefresh(key), 0);
    }
  }
}

function renderJson(el, data) {
  if (!el) return;
  const text = JSON.stringify(data || {}, null, 2);
  el.textContent = text.length > 8000 ? text.slice(0, 8000) + "\n..." : text;
}

function renderKeyValueGrid(container, rows) {
  if (!container) return;
  if (!Array.isArray(rows) || rows.length === 0) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = rows
    .map(([label, value]) => {
      const v = value === undefined || value === null || value === "" ? "-" : String(value);
      return `<div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(v)}</div>`;
    })
    .join("");
}

function getOrCreateClaimOwnerTag() {
  const key = "cockpit_claim_owner_tag.v1";
  try {
    const existing = localStorage.getItem(key);
    if (existing && existing.length >= 6) return existing;
  } catch (err) {
    // ignore (e.g., storage blocked)
  }
  const rand = Math.random().toString(16).slice(2, 10);
  const tag = `cockpit-${rand}`;
  try {
    localStorage.setItem(key, tag);
  } catch (err) {
    // ignore
  }
  return tag;
}

function readBoolFromStorage(key, defaultValue = false) {
  try {
    const raw = localStorage.getItem(String(key));
    if (raw === null || raw === undefined || raw === "") return Boolean(defaultValue);
    if (raw === "true") return true;
    if (raw === "false") return false;
    return Boolean(defaultValue);
  } catch (err) {
    return Boolean(defaultValue);
  }
}

function readIntFromStorage(key, defaultValue, allowed = null) {
  let v = defaultValue;
  try {
    const raw = localStorage.getItem(String(key));
    if (raw !== null && raw !== undefined && raw !== "") v = parseInt(raw, 10);
  } catch (err) {
    v = defaultValue;
  }
  if (!Number.isFinite(v)) v = defaultValue;
  if (Array.isArray(allowed) && allowed.length && !allowed.includes(v)) v = defaultValue;
  return v;
}

function writeToStorage(key, value) {
  try {
    localStorage.setItem(String(key), String(value));
    return true;
  } catch (err) {
    return false;
  }
}

function readLangFromStorage(key, defaultValue = "en") {
  let v = defaultValue;
  try {
    const raw = localStorage.getItem(String(key));
    if (raw !== null && raw !== undefined && raw !== "") v = String(raw);
  } catch (err) {
    v = defaultValue;
  }
  const norm = String(v || "").trim().toLowerCase();
  return SUPPORTED_LANGS.includes(norm) ? norm : String(defaultValue || "en");
}

function applyI18n() {
  try {
    document.documentElement.lang = state.lang;
  } catch (_) {
    // ignore
  }

  $$("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!key) return;
    el.textContent = t(key);
  });

  const attrMap = [
    ["data-i18n-title", "title"],
    ["data-i18n-aria-label", "aria-label"],
    ["data-i18n-placeholder", "placeholder"],
  ];
  attrMap.forEach(([dataAttr, targetAttr]) => {
    $$(`[${dataAttr}]`).forEach((el) => {
      const key = el.getAttribute(dataAttr);
      if (!key) return;
      el.setAttribute(targetAttr, t(key));
    });
  });

  updateAdminModeButtons();
  applyAdminModeToWriteControls();
  renderActionLog();
  renderActionResponse();
}

function rehydrateNorthStarTopicFilters() {
  const filters = state.filters?.northStarFindings;
  if (!filters || typeof filters !== "object") return;
  const topics = Array.isArray(filters.topic) ? filters.topic : [];
  if (!topics.length) return;
  const next = topics
    .map((value) => {
      const text = String(value || "");
      const norm = normalizeKey(text);
      const unknownEn = normalizeKey(I18N.en["north_star.unknown"] || "(unknown)");
      const unknownTr = normalizeKey(I18N.tr["north_star.unknown"] || "(bilinmiyor)");
      if (norm === unknownEn || norm === unknownTr) return t("north_star.unknown");
      const m = text.match(/\(([^()]+)\)\s*$/);
      const rawKey = m ? String(m[1] || "") : text;
      return normalizeNorthStarFindingTopic(rawKey);
    })
    .filter((v) => Boolean(String(v || "").trim()));
  if (!next.length) return;
  filters.topic = Array.from(new Set(next)).sort((a, b) => a.localeCompare(b));
}

function setLanguage(next, { persist = true } = {}) {
  const norm = String(next || "").trim().toLowerCase();
  state.lang = SUPPORTED_LANGS.includes(norm) ? norm : "en";
  if (persist) writeToStorage(LANG_STORAGE_KEY, state.lang);
  const select = $("#lang-select");
  if (select) select.value = state.lang;
  rehydrateNorthStarTopicFilters();
  applyI18n();
  scheduleRefresh("active_tab", refreshActiveTab, 80);
}

function setupLanguageSelector() {
  const select = $("#lang-select");
  if (!select) return;
  select.value = state.lang;
  select.addEventListener("change", () => setLanguage(select.value));
}

function isAdminModeEnabled() {
  return Boolean(state.adminModeEnabled);
}

function updateAdminModeButtons() {
  const ids = ["admin-mode-toggle", "admin-mode-toggle-topbar"];
  ids.forEach((id) => {
    const btn = $("#" + id);
    if (!btn) return;
    const stateLabel = state.adminModeEnabled ? t("admin.on") : t("admin.off");
    btn.textContent = t("admin.mode_state", { state: stateLabel });
    btn.classList.remove("danger", "warn");
    btn.classList.add(state.adminModeEnabled ? "danger" : "warn");
    btn.setAttribute("aria-pressed", state.adminModeEnabled ? "true" : "false");
  });
}

function applyAdminModeToWriteControls() {
  const admin = isAdminModeEnabled();
  const disabled = Boolean(state.actionPending) || !admin;

  const settingsSave = $("#settings-save");
  if (settingsSave) {
    settingsSave.disabled = disabled;
    settingsSave.title = admin ? t("admin.save_override") : t("admin.save_override_disabled");
  }

  const runCardSave = $("#run-card-save");
  if (runCardSave) {
    runCardSave.disabled = disabled;
    runCardSave.title = admin ? t("admin.save_run_card") : t("admin.save_run_card_disabled");
  }

  $$("[data-ext-toggle]").forEach((btn) => {
    btn.disabled = disabled;
    if (!admin) btn.title = t("admin.toggle_extensions_disabled");
    else btn.removeAttribute("title");
  });
}

function setAdminModeEnabled(enabled, { persist = true } = {}) {
  state.adminModeEnabled = Boolean(enabled);
  if (persist) writeToStorage("cockpit_admin_mode.v1", state.adminModeEnabled ? "true" : "false");
  updateAdminModeButtons();
  applyAdminModeToWriteControls();
  renderLocks();
  renderIntakeClaimControls(state.intakeSelected);
  renderIntakeCloseControls(state.intakeSelected);
}

function setLockClaimsLimit(limit, { persist = true } = {}) {
  const allowed = [10, 20, 50];
  const v = Number.isFinite(Number(limit)) ? parseInt(String(limit), 10) : 20;
  state.lockClaimsLimit = allowed.includes(v) ? v : 20;
  if (persist) writeToStorage("cockpit_lock_claims_limit.v1", String(state.lockClaimsLimit));
  renderLocks();
}

function setLockClaimsGroupByOwner(enabled, { persist = true } = {}) {
  state.lockClaimsGroupByOwner = Boolean(enabled);
  if (persist) writeToStorage("cockpit_lock_claims_group_owner.v1", state.lockClaimsGroupByOwner ? "true" : "false");
  renderLocks();
}

function summarizeIntakeTopic(item) {
  const sourceType = item?.source_type ? String(item.source_type) : "";
  const sourceRef = item?.source_ref ? String(item.source_ref) : "";
  if (sourceType && sourceRef) return `${sourceType}: ${sourceRef}`;
  if (sourceType) return sourceType;
  if (sourceRef) return sourceRef;
  return String(item?.title || "").trim() || t("intake.item_fallback");
}

function summarizeIntakeWhy(item) {
  const notes = item?.autopilot_notes;
  if (Array.isArray(notes) && notes.length) {
    return notes.map((n) => String(n)).join(" | ");
  }
  if (item?.source_ref) {
    return t("intake.why.derived_from", { source: item.source_ref });
  }
  if (item?.source_type) {
    return t("intake.why.derived_from", { source: item.source_type });
  }
  return t("intake.why.no_rationale");
}

function clearIntakeSelection() {
  state.intakeSelectedId = null;
  state.intakeSelected = null;
  state.intakeEvidencePath = null;
  state.intakeEvidencePreview = null;
  state.intakeLinkedNotes = null;
  state.intakeLinkedNotesLoading = false;
  state.intakeLinkedNotesError = null;
  renderIntakeDetail(null);
  renderIntakeTable((unwrap(state.intake || {}).items || []));
}

function navigateToTab(tab) {
  const raw = String(tab || "").trim();
  const aliases = {
    // UI has no dedicated "#notes" tab; notes live under Planner Chat.
    notes: "planner-chat",
  };
  const next = aliases[raw] || raw;
  if (!next) return;
  const targetHash = `#${next}`;
  const current = location.hash || "";
  location.hash = next;
  if (current === targetHash) {
    window.dispatchEvent(new Event("hashchange"));
  }
}

function isWorkspaceReportsPath(path) {
  const raw = String(path || "").replaceAll("\\", "/");
  return raw.includes(".cache/reports/");
}

function resolveEvidencePathForApi(rawPath) {
  const p = String(rawPath || "").trim();
  if (!p) return "";
  const pNoDot = p.startsWith("./") ? p.slice(2) : p;
  // Absolute paths (POSIX + basic Windows drive detection)
  if (pNoDot.startsWith("/") || /^[A-Za-z]:[\\/]/.test(pNoDot)) return pNoDot;

  // The server currently resolves relative paths against repo_root, not ws_root.
  // Many evidence pointers are emitted relative to workspace_root (e.g. ".cache/index/...").
  // For those, we rewrite into an absolute path under workspace_root so /api/file and
  // /api/evidence/read can safely resolve them (allow_roots enforced server-side).
  const wsRoot = String(state.ws?.workspace_root || "").trim();
  if (!wsRoot) return pNoDot;

  const normalized = pNoDot.replaceAll("\\", "/");
  if (normalized.startsWith(".cache/ws_")) return normalized; // already repo-root relative

  // Repo-root allow_root: keep as-is so server resolves it against repo_root.
  if (normalized.startsWith(".cache/script_budget/")) return normalized;

  // Workspace allow_roots: rewrite to absolute under ws_root.
  const wsPrefixes = [
    ".cache/reports/",
    ".cache/index/",
    ".cache/airunner/",
    ".cache/github_ops/",
    ".cache/policy_overrides/",
    ".cache/chat_console/",
  ];
  if (wsPrefixes.some((prefix) => normalized.startsWith(prefix))) {
    return `${wsRoot.replace(/\/$/, "")}/${normalized}`;
  }

  return pNoDot;
}

async function openEvidencePreview(path) {
  const p = resolveEvidencePathForApi(path);
  if (!p) return;

  navigateToTab("evidence");
  state.evidenceSelected = p;

  const viewer = $("#evidence-viewer");
  if (viewer) viewer.textContent = t("evidence.loading");

  try {
    const endpoint = isWorkspaceReportsPath(p) ? endpoints.evidenceRead : endpoints.file;
    const data = await fetchJson(`${endpoint}?path=${encodeURIComponent(p)}`);
    renderJson(viewer, data);
  } catch (err) {
    if (viewer) viewer.textContent = t("evidence.load_failed", { error: formatError(err) });
    showToast(t("toast.evidence_preview_failed", { error: formatError(err) }), "fail");
  }
}

async function previewIntakeEvidence(path) {
  const p = resolveEvidencePathForApi(path);
  if (!p) return;
  state.intakeEvidencePath = p;
  try {
    const payload = await fetchJson(`${endpoints.file}?path=${encodeURIComponent(p)}`);
    state.intakeEvidencePreview = payload;
    renderIntakeEvidencePreview();
  } catch (err) {
    state.intakeEvidencePreview = { status: "FAIL", error: formatError(err) };
    renderIntakeEvidencePreview();
    showToast(t("toast.evidence_preview_failed", { error: formatError(err) }), "fail");
  }
}

function renderIntakeEvidencePreview() {
  const panel = $("#intake-evidence-preview-panel");
  const meta = $("#intake-evidence-preview-meta");
  const pre = $("#intake-evidence-preview");
  if (!panel || !meta || !pre) return;
  const path = state.intakeEvidencePath;
  const payload = state.intakeEvidencePreview;
  if (!path || !payload) {
    meta.textContent = t("evidence.none_selected");
    pre.textContent = "";
    return;
  }
  panel.open = true;
  meta.textContent = `${path} | exists=${payload.exists ? "true" : "false"} json_valid=${payload.json_valid ? "true" : "false"}`;
  renderJson(pre, payload.data !== undefined ? payload.data : payload);
}

function noteLinksToIntake(note, intakeId) {
  if (!note || !intakeId) return false;
  const links = Array.isArray(note.links) ? note.links : [];
  return links.some((link) => {
    if (!link || typeof link !== "object") return false;
    const kind = String(link.kind || "").toLowerCase();
    const target = String(link.id_or_path || "");
    return kind === "intake" && target === String(intakeId);
  });
}

function normalizeNotesList(items) {
  const notes = Array.isArray(items) ? items.map(normalizeNote) : [];
  // stable deterministic ordering (updated_at desc, note_id desc)
  return notes.sort((a, b) => {
    const ua = String(a.updated_at || "");
    const ub = String(b.updated_at || "");
    if (ua !== ub) return ub.localeCompare(ua);
    return String(b.note_id || "").localeCompare(String(a.note_id || ""));
  });
}

async function refreshIntakeLinkedNotes(item) {
  const intakeId = item?.intake_id;
  if (!intakeId) {
    state.intakeLinkedNotes = [];
    state.intakeLinkedNotesLoading = false;
    state.intakeLinkedNotesError = null;
    renderIntakeLinkedNotes();
    return;
  }

  state.intakeLinkedNotesLoading = true;
  state.intakeLinkedNotesError = null;
  renderIntakeLinkedNotes();

  try {
    const q = `intake:${intakeId}`;
    const payload = await fetchJson(`${endpoints.notesSearch}?q=${encodeURIComponent(q)}`);
    const raw = Array.isArray(payload?.items) ? payload.items : [];
    const linked = raw.filter((note) => noteLinksToIntake(note, intakeId));
    state.intakeLinkedNotes = normalizeNotesList(linked);
    state.intakeLinkedNotesLoading = false;
    state.intakeLinkedNotesError = null;
    renderIntakeLinkedNotes();
  } catch (err) {
    state.intakeLinkedNotes = [];
    state.intakeLinkedNotesLoading = false;
    state.intakeLinkedNotesError = formatError(err);
    renderIntakeLinkedNotes();
  }
}

async function openNoteInNotesTab(noteId) {
  const id = String(noteId || "").trim();
  if (!id) return;
  navigateToTab("notes");
  try {
    const payload = await fetchJson(`${endpoints.noteGet}?note_id=${encodeURIComponent(id)}`);
    state.noteDetail = payload;
    renderNoteDetail(payload);
  } catch (err) {
    showToast(t("toast.note_load_failed", { error: formatError(err) }), "fail");
  }
}

function renderIntakeLinkedNotes() {
  const meta = $("#intake-notes-meta");
  const list = $("#intake-notes-list");
  if (!meta || !list) return;

  const item = state.intakeSelected;
  const intakeId = item?.intake_id;
  if (!item || !intakeId) {
    meta.textContent = t("notes.for_item.none");
    list.innerHTML = "";
    return;
  }

  if (state.intakeLinkedNotesLoading) {
    meta.textContent = t("notes.for_item.loading");
    list.innerHTML = `<div class="empty">${escapeHtml(t("notes.linked.loading"))}</div>`;
    return;
  }

  if (state.intakeLinkedNotesError) {
    meta.textContent = t("notes.for_item.error");
    list.innerHTML = `<div class="empty">${escapeHtml(t("notes.linked.failed", { error: state.intakeLinkedNotesError }))}</div>`;
    return;
  }

  const notes = Array.isArray(state.intakeLinkedNotes) ? state.intakeLinkedNotes : [];
  meta.textContent = t("notes.for_item.count", { count: String(notes.length) });
  if (!notes.length) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("notes.linked.none"))}</div>`;
    return;
  }

  list.innerHTML = notes
    .slice(0, 10)
    .map((note) => {
      const noteIdRaw = String(note.note_id || "");
      const noteIdAttr = encodeTag(noteIdRaw);
      const titleRaw = String(note.title || t("notes.untitled"));
      const updatedRaw = String(note.updated_at || note.created_at || "");
      const metaText = t("notes.item_meta", { updated: updatedRaw, id: noteIdRaw });
      const tags = Array.isArray(note.tags) ? note.tags.map((t) => `<span class="note-tag">${escapeHtml(t)}</span>`).join("") : "";
      const excerpt = escapeHtml(note.body_excerpt || "");
      return `
        <div class="note-item">
          <div class="note-title">${escapeHtml(titleRaw)}</div>
          <div class="note-meta">${escapeHtml(metaText)}</div>
          <div class="note-tags">${tags}</div>
          <div class="subtle">${excerpt}</div>
          <div class="note-actions">
            <button class="btn" data-intake-note-open="${noteIdAttr}">${escapeHtml(t("notes.open"))}</button>
          </div>
        </div>
      `;
    })
    .join("");

  $$("[data-intake-note-open]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const noteId = decodeTag(btn.dataset.intakeNoteOpen || "");
      if (!noteId) return;
      await openNoteInNotesTab(noteId);
    });
  });
}

function createNoteForSelectedIntake() {
  const item = state.intakeSelected;
  const intakeId = item?.intake_id;
  if (!item || !intakeId) {
    showToast(t("toast.select_intake_first"), "warn");
    return;
  }

  const titleEl = $("#note-title");
  const bodyEl = $("#note-body");
  const tagsEl = $("#note-tags");
  const threadEl = $("#planner-thread");
  if (!titleEl || !bodyEl || !tagsEl) {
    showToast(t("toast.notes_composer_unavailable"), "fail");
    return;
  }

  const title = `[INTAKE] ${String(item.title || summarizeIntakeTopic(item) || "").trim()}`.trim();
  const why = summarizeIntakeWhy(item);
  const evidencePaths = Array.isArray(item.evidence_paths) ? item.evidence_paths.map(String) : [];
  const body = [
    t("notes.prefill.context_header"),
    `- intake_id: ${item.intake_id || "-"}`,
    `- topic: ${summarizeIntakeTopic(item)}`,
    `- bucket/status: ${item.bucket || "-"} / ${item.status || "-"}`,
    `- priority/severity: ${item.priority || "-"} / ${item.severity || "-"}`,
    `- source: ${item.source_type || "-"} / ${item.source_ref || "-"}`,
    `- why: ${why}`,
    "",
    t("notes.prefill.evidence_header"),
    ...(evidencePaths.length ? evidencePaths.slice(0, 12).map((p) => `- ${p}`) : [t("notes.prefill.none")]),
    "",
    t("notes.prefill.next_header"),
    t("notes.prefill.next_placeholder"),
    "",
  ].join("\n");

  titleEl.value = title;
  bodyEl.value = body;
  const baseTags = ["intake", String(item.bucket || "").toLowerCase(), String(item.source_type || "").toLowerCase()].filter((t) => t && t !== "unknown");
  tagsEl.value = Array.from(new Set(baseTags)).join(", ");

  state.noteLinks = [{ kind: "intake", id_or_path: String(intakeId) }];
  renderNoteLinks();

  if (threadEl && !threadEl.value) {
    threadEl.value = state.plannerThread || "default";
  }

  navigateToTab("notes");
  titleEl.focus();
  showToast(t("toast.note_composer_prefilled"), "ok");
}

function renderIntakeClaimControls(item) {
  const meta = $("#intake-claim-meta");
  const claimBtn = $("#intake-claim");
  const releaseBtn = $("#intake-claim-release");
  const forceReleaseBtn = $("#intake-claim-force-release");
  if (!meta || !claimBtn || !releaseBtn || !forceReleaseBtn) return;

  if (!item) {
    meta.textContent = t("intake.claim.meta_none");
    claimBtn.disabled = true;
    releaseBtn.disabled = true;
    forceReleaseBtn.disabled = true;
    claimBtn.textContent = t("intake.claim.btn_claim");
    releaseBtn.textContent = t("intake.claim.btn_release");
    forceReleaseBtn.textContent = t("intake.claim.btn_force_release");
    return;
  }

  const claimStatus = String(item.claim_status || "").toUpperCase();
  const claim = item.claim || {};
  const owner = String(claim.owner_tag || claim.owner_session || "").trim();
  const expires = String(claim.expires_at || "").trim();
  const expiresFmt = expires ? formatTimestamp(expires) || expires : "-";

  const myTag = String(state.claimOwnerTag || "").trim();
  const isMine = Boolean(owner && myTag && owner === myTag);

  if (claimStatus === "CLAIMED") {
    meta.textContent = isMine
      ? t("intake.claim.meta_claimed_you", { expires: expiresFmt })
      : t("intake.claim.meta_claimed_other", { owner: owner || "-", expires: expiresFmt });
  } else {
    meta.textContent = t("intake.claim.meta_free");
  }

  claimBtn.textContent = isMine ? t("intake.claim.btn_renew") : t("intake.claim.btn_claim");
  releaseBtn.textContent = t("intake.claim.btn_release");
  forceReleaseBtn.textContent = t("intake.claim.btn_force_release");
  claimBtn.disabled = Boolean(state.intakeClaimPending) || (claimStatus === "CLAIMED" && !isMine);
  releaseBtn.disabled = Boolean(state.intakeClaimPending) || !isMine;
  forceReleaseBtn.disabled = Boolean(state.intakeClaimPending) || claimStatus !== "CLAIMED" || !isAdminModeEnabled();
}

async function claimIntakeItem(intakeId, mode) {
  const id = String(intakeId || "").trim();
  if (!id) return null;
  const opMode = String(mode || "claim").trim().toLowerCase();
  if (!["claim", "release"].includes(opMode)) return null;

  if (!state.claimOwnerTag) state.claimOwnerTag = getOrCreateClaimOwnerTag();
  const ownerTag = String(state.claimOwnerTag || "").trim() || "unknown";

  if (state.intakeClaimPending) return null;
  state.intakeClaimPending = true;
  renderIntakeClaimControls(state.intakeSelected);
  try {
    const args = {
      mode: opMode,
      intake_id: id,
      owner_tag: ownerTag,
    };
    if (opMode === "claim") {
      args.ttl_seconds = "3600";
    }
    const { res, data } = await postOpInternal("work-intake-claim", args);
    if (data) {
      state.lastAction = data;
      renderActionResponse();
      logAction(data);
      const ok = res.ok && String(data.status || "").toUpperCase() !== "FAIL";
      const status = String(data.status || (ok ? "OK" : "FAIL"));
      showToast(t("job.done", { op: "work-intake-claim", status }), ok ? "ok" : "fail");
    }
    await refreshIntake();
    await refreshLocks();
    return data;
  } catch (err) {
    showToast(t("toast.claim_failed", { error: formatError(err) }), "fail");
    return null;
  } finally {
    state.intakeClaimPending = false;
    renderIntakeClaimControls(state.intakeSelected);
  }
}

async function forceReleaseIntakeClaim(intakeId) {
  const id = String(intakeId || "").trim();
  if (!id) return null;

  if (!isAdminModeEnabled()) {
    showToast(t("toast.admin_required_force_release"), "warn");
    return null;
  }
  const typed = prompt(t("prompt.force_release_confirm", { id }));
  if (typed !== "FORCE") {
    showToast(t("toast.force_release_canceled"), "warn");
    return null;
  }

  if (!state.claimOwnerTag) state.claimOwnerTag = getOrCreateClaimOwnerTag();
  const ownerTag = String(state.claimOwnerTag || "").trim() || "unknown";

  if (state.intakeClaimPending) return null;
  state.intakeClaimPending = true;
  renderIntakeClaimControls(state.intakeSelected);
  try {
    const args = {
      mode: "release",
      intake_id: id,
      owner_tag: ownerTag,
      force: "true",
    };
    const { res, data } = await postOpInternal("work-intake-claim", args);
    if (data) {
      state.lastAction = data;
      renderActionResponse();
      logAction(data);
      const ok = res.ok && String(data.status || "").toUpperCase() !== "FAIL";
      const status = String(data.status || (ok ? "OK" : "FAIL"));
      showToast(t("job.done", { op: "work-intake-claim(force)", status }), ok ? "ok" : "fail");
    }
    await refreshIntake();
    await refreshLocks();
    return data;
  } catch (err) {
    showToast(t("toast.force_release_failed", { error: formatError(err) }), "fail");
    return null;
  } finally {
    state.intakeClaimPending = false;
    renderIntakeClaimControls(state.intakeSelected);
  }
}

function renderIntakeCloseControls(item) {
  const meta = $("#intake-close-meta");
  const closeBtn = $("#intake-close");
  if (!meta || !closeBtn) return;

  if (!item) {
    meta.textContent = t("intake.close.meta_none");
    closeBtn.disabled = true;
    closeBtn.textContent = t("intake.close.btn_close");
    return;
  }

  const bucket = String(item.bucket || "");
  const sourceType = String(item.source_type || "");
  const status = String(item.status || "").toUpperCase();
  const isEligible = bucket === "TICKET" && sourceType === "MANUAL_REQUEST";
  const isDone = status === "DONE";

  if (!isEligible) {
    meta.textContent = t("intake.close.meta_unavailable");
    closeBtn.disabled = true;
    closeBtn.textContent = t("intake.close.btn_close");
    return;
  }

  const closedReason = String(item.closed_reason || "").trim();
  const reasonSuffix = closedReason ? ` (${closedReason})` : "";
  meta.textContent = isDone ? t("intake.close.meta_done", { reason: reasonSuffix }) : t("intake.close.meta_available");
  closeBtn.textContent = isDone ? t("intake.close.btn_closed") : t("intake.close.btn_close");
  closeBtn.disabled = Boolean(state.intakeClosePending) || isDone;
}

async function closeSelectedIntakeItem() {
  const item = state.intakeSelected;
  const id = String(state.intakeSelectedId || "").trim();
  if (!item || !id) return null;

  const bucket = String(item.bucket || "");
  const sourceType = String(item.source_type || "");
  if (!(bucket === "TICKET" && sourceType === "MANUAL_REQUEST")) {
    showToast(t("toast.close_manual_only"), "warn");
    return null;
  }

  const title = String(item.title || "").slice(0, 120);
  const typed = prompt(t("prompt.close_confirm", { id, title }));
  if (typed !== "CLOSE") {
    showToast(t("toast.close_canceled"), "warn");
    return null;
  }

  const reason = String(prompt(t("prompt.close_reason"), "done") || "").trim();

  if (!state.claimOwnerTag) state.claimOwnerTag = getOrCreateClaimOwnerTag();
  const ownerTag = String(state.claimOwnerTag || "").trim() || "unknown";

  if (state.intakeClosePending) return null;
  state.intakeClosePending = true;
  renderIntakeCloseControls(item);
  try {
    const args = { mode: "close", intake_id: id, reason, owner_tag: ownerTag, force: "false" };
    const { res, data } = await postOpInternal("work-intake-close", args);
    if (data) {
      state.lastAction = data;
      renderActionResponse();
      logAction(data);
      const ok = res.ok && String(data.status || "").toUpperCase() !== "FAIL";
      const status = String(data.status || (ok ? "OK" : "FAIL"));
      showToast(t("job.done", { op: "work-intake-close", status }), ok ? "ok" : "fail");
    }

    // Ensure the intake index reflects the persistent close immediately.
    await postOpInternal("work-intake-check", { mode: "report", chat: "false", detail: "false" });
    await refreshIntake();
    await refreshLocks();
    return data;
  } catch (err) {
    showToast(t("toast.close_failed", { error: formatError(err) }), "fail");
    return null;
  } finally {
    state.intakeClosePending = false;
    renderIntakeCloseControls(state.intakeSelected);
  }
}

function renderIntakeDetail(item) {
  const panel = $("#intake-detail-panel");
  const meta = $("#intake-detail-meta");
  const fields = $("#intake-detail-fields");
  const evidence = $("#intake-evidence-paths");
  const raw = $("#intake-detail-json");
  if (!panel || !meta || !fields || !evidence || !raw) return;

  if (!item) {
    meta.textContent = t("common.no_selection");
    fields.innerHTML = "";
    evidence.innerHTML = "";
    raw.textContent = "";
    state.intakeEvidencePath = null;
    state.intakeEvidencePreview = null;
    state.intakeLinkedNotes = null;
    state.intakeLinkedNotesLoading = false;
    state.intakeLinkedNotesError = null;
    renderIntakeEvidencePreview();
    renderIntakeLinkedNotes();
    renderIntakeClaimControls(null);
    renderIntakeCloseControls(null);
    panel.open = false;
    return;
  }

  const topic = summarizeIntakeTopic(item);
  const why = summarizeIntakeWhy(item);
  const evidencePaths = Array.isArray(item.evidence_paths) ? item.evidence_paths.map(String) : [];

  meta.textContent = `${item.intake_id || "-"} | ${topic}`;
  renderKeyValueGrid(fields, [
    [t("intake.field.topic"), topic],
    [t("intake.field.why"), why],
    [t("intake.field.bucket"), item.bucket],
    [t("intake.field.status"), item.status],
    [t("intake.field.priority"), item.priority],
    [t("intake.field.severity"), item.severity],
    [t("intake.field.layer"), item.layer],
    [t("intake.field.source_type"), item.source_type],
    [t("intake.field.source_ref"), item.source_ref],
    [t("intake.field.autopilot_allowed"), item.autopilot_allowed],
    [t("intake.field.autopilot_selected"), item.autopilot_selected],
    [t("intake.field.ingested_at"), formatTimestamp(item.ingested_at) || item.ingested_at],
    [t("intake.field.evidence_paths"), evidencePaths.length],
    [t("intake.field.claim_status"), item.claim_status],
    [t("intake.field.claim_owner"), item?.claim?.owner_tag || item?.claim?.owner_session],
    [t("intake.field.claim_expires"), formatTimestamp(item?.claim?.expires_at) || item?.claim?.expires_at],
    [t("intake.field.exec_lease_status"), item.exec_lease_status],
    [t("intake.field.exec_lease_owner"), item?.exec_lease?.owner],
    [t("intake.field.exec_lease_expires"), formatTimestamp(item?.exec_lease?.expires_at) || item?.exec_lease?.expires_at],
  ]);

  raw.textContent = JSON.stringify(item || {}, null, 2);

  evidence.innerHTML =
    evidencePaths.length === 0
      ? `<span class="subtle">${escapeHtml(t("common.none"))}</span>`
      : evidencePaths
          .slice(0, 20)
          .map((p) => `<button class="btn small ghost" type="button" data-evidence-path="${encodeTag(p)}">${escapeHtml(p)}</button>`)
          .join("");

  evidence.querySelectorAll("[data-evidence-path]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const path = decodeTag(btn.dataset.evidencePath || "");
      previewIntakeEvidence(path);
    });
  });

  renderIntakeLinkedNotes();
  renderIntakeClaimControls(item);
  renderIntakeCloseControls(item);
  panel.open = true;
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatTimestamp(value) {
  if (!value) return "";
  let ts = value;
  if (typeof ts === "string" && /^\d+$/.test(ts)) {
    ts = Number(ts);
  }
  if (typeof ts === "number") {
    ts = ts < 1e12 ? ts * 1000 : ts;
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) return "";
    return date.toISOString().replace("T", " ").replace("Z", "");
  }
  if (typeof ts === "string") {
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) return ts;
    return date.toISOString().replace("T", " ").replace("Z", "");
  }
  return "";
}

function pickTimestamp(item, keys) {
  for (const key of keys) {
    const value = item ? item[key] : null;
    if (value) return value;
  }
  return "";
}

function normalizeKey(value) {
  return String(value || "").trim().toUpperCase();
}

function normalizeValue(value) {
  return String(value || "").trim();
}

function encodeTag(value) {
  return encodeURIComponent(String(value || ""));
}

function decodeTag(value) {
  return decodeURIComponent(value || "");
}

const DEFAULT_COCKPIT_DECISION_ARTIFACTS = {
  index: ".cache/ws_customer_default/.cache/index/cockpit_decisions_index.v1.json",
  queue: ".cache/ws_customer_default/.cache/reports/cockpit_decision_queue.v1.json",
  overlay: ".cache/ws_customer_default/.cache/index/cockpit_decision_overlay.v1.json",
  userMarks: ".cache/ws_customer_default/.cache/index/cockpit_decision_user_marks.v1.json",
};

function _extractFileData(payload) {
  if (payload && typeof payload === "object" && "data" in payload) return payload.data;
  return payload;
}

async function fetchWorkspaceFile(path) {
  const p = String(path || "").trim();
  if (!p) return null;
  return await fetchJson(`${endpoints.file}?path=${encodeURIComponent(p)}`);
}

function normalizeCockpitDecisionQueue(queuePayload) {
  const queue = unwrap(queuePayload || {});
  const items = Array.isArray(queue.items) ? queue.items : [];
  const byId = {};
  items.forEach((row) => {
    const id = String(row?.intake_id || "").trim();
    if (!id) return;
    byId[id] = row;
  });
  return { queue, items, byId };
}

function normalizeCockpitDecisionOverlay(overlayPayload) {
  const overlay = unwrap(overlayPayload || {});
  const items = overlay.items && typeof overlay.items === "object" ? overlay.items : {};
  return { overlay, byId: items };
}

function normalizeCockpitDecisionUserMarks(marksPayload) {
  const marks = unwrap(marksPayload || {});
  const items = marks.items && typeof marks.items === "object" ? marks.items : {};
  return { marks, byId: items };
}

async function refreshCockpitDecisionArtifacts() {
  const out = {
    ok: false,
    loaded_at: new Date().toISOString(),
    index: null,
    queue: null,
    overlay: null,
    userMarks: null,
    queueById: {},
    overlayById: {},
    userMarksById: {},
    error: null,
  };

  try {
    const indexPayload = await fetchWorkspaceFile(DEFAULT_COCKPIT_DECISION_ARTIFACTS.index);
    out.index = indexPayload;
    const indexData = _extractFileData(indexPayload);
    const artifacts = indexData && typeof indexData === "object" ? indexData.artifacts : null;
    const paths = artifacts && typeof artifacts === "object"
      ? {
          queue: String(artifacts.decision_queue_json || DEFAULT_COCKPIT_DECISION_ARTIFACTS.queue),
          overlay: String(artifacts.decision_overlay_json || DEFAULT_COCKPIT_DECISION_ARTIFACTS.overlay),
          userMarks: String(artifacts.decision_user_marks_json || DEFAULT_COCKPIT_DECISION_ARTIFACTS.userMarks),
        }
      : {
          queue: DEFAULT_COCKPIT_DECISION_ARTIFACTS.queue,
          overlay: DEFAULT_COCKPIT_DECISION_ARTIFACTS.overlay,
          userMarks: DEFAULT_COCKPIT_DECISION_ARTIFACTS.userMarks,
        };

    const [queuePayload, overlayPayload, marksPayload] = await Promise.all([
      fetchWorkspaceFile(paths.queue),
      fetchWorkspaceFile(paths.overlay),
      fetchWorkspaceFile(paths.userMarks),
    ]);

    out.queue = queuePayload;
    out.overlay = overlayPayload;
    out.userMarks = marksPayload;

    const q = normalizeCockpitDecisionQueue(_extractFileData(queuePayload));
    const o = normalizeCockpitDecisionOverlay(_extractFileData(overlayPayload));
    const m = normalizeCockpitDecisionUserMarks(_extractFileData(marksPayload));

    out.queueById = q.byId;
    out.overlayById = o.byId;
    out.userMarksById = m.byId;

    out.ok = Boolean(queuePayload && queuePayload.exists && queuePayload.json_valid);
  } catch (err) {
    out.ok = false;
    out.error = formatError(err);
  }

  state.cockpitDecisionArtifacts = out;
  renderIntakeDecisionBanner();
}

function renderIntakeDecisionBanner() {
  const el = $("#intake-decision-banner");
  if (!el) return;
  const meta = state.cockpitDecisionArtifacts || {};
  if (meta.ok) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  const err = meta.error ? ` (${meta.error})` : "";
  el.textContent = `${t("intake.decision.banner_missing")}${err}`;
  el.style.display = "block";
}

function getDecisionForIntake(intakeId) {
  const id = String(intakeId || "").trim();
  const meta = state.cockpitDecisionArtifacts || {};
  const queue = meta.queueById && typeof meta.queueById === "object" ? meta.queueById[id] : null;
  const overlay = meta.overlayById && typeof meta.overlayById === "object" ? meta.overlayById[id] : null;
  const mark = meta.userMarksById && typeof meta.userMarksById === "object" ? meta.userMarksById[id] : null;

  const recommended = String((overlay && overlay.recommended_action) || (queue && queue.recommended_action) || "").trim();
  const confidence = String((overlay && overlay.confidence) || (queue && queue.confidence) || "").trim();
  const executionMode = String((queue && queue.execution_mode) || "").trim();
  const evidenceReady = String((queue && queue.evidence_ready) || "").trim();
  const reasonCode = String((overlay && overlay.reason_code) || (queue && queue.reason_code) || "").trim();
  const selectedOption = String((mark && mark.selected_option) || "").trim().toUpperCase();

  return {
    intake_id: id,
    queue,
    overlay,
    mark,
    recommended_action: recommended,
    confidence,
    execution_mode: executionMode,
    evidence_ready: evidenceReady,
    reason_code: reasonCode,
    selected_option: selectedOption,
  };
}

function decisionBadgeClass(action) {
  const a = String(action || "").toUpperCase();
  if (!a) return "badge";
  if (a === "EXECUTE") return "badge ok";
  if (a === "KEEP") return "badge";
  if (a === "NOOP") return "badge";
  if (a === "REFRESH" || a === "REFRAME" || a === "DECISION_REQUIRED" || a === "NEEDS_INFO") return "badge warn";
  return "badge";
}

function renderIntakeInlineDecisionDetailHtml(item) {
  const intakeId = String(item?.intake_id || "").trim();
  const decision = getDecisionForIntake(intakeId);
  const title = String(decision.overlay?.user_title_tr || decision.queue?.user_title_tr || item?.title || "").trim();
  const titleEn = String(decision.overlay?.user_title_en || decision.queue?.user_title_en || "").trim();
  const summaryTr = String(decision.overlay?.summary_tr || "").trim();
  const summaryEn = String(decision.overlay?.summary_en || "").trim();
  const qTr = String(decision.overlay?.decision_question_tr || "").trim();
  const qEn = String(decision.overlay?.decision_question_en || "").trim();
  const options = Array.isArray(decision.overlay?.options) ? decision.overlay.options : [];

  const activeTab = state.intakeInlineTab && state.intakeInlineTab[intakeId] ? state.intakeInlineTab[intakeId] : "decision";

  const badgeRec = decision.recommended_action
    ? `<span class="${decisionBadgeClass(decision.recommended_action)}">${escapeHtml(decision.recommended_action)}</span>`
    : `<span class="subtle">-</span>`;
  const badgeConf = decision.confidence ? `<span class="badge">${escapeHtml(decision.confidence)}</span>` : `<span class="subtle">-</span>`;
  const badgeExec = decision.execution_mode ? `<span class="badge">${escapeHtml(decision.execution_mode)}</span>` : `<span class="subtle">-</span>`;
  const badgeEv = decision.evidence_ready
    ? `<span class="badge">${escapeHtml(decision.evidence_ready)}</span>`
    : `<span class="subtle">-</span>`;
  const badgeSel = decision.selected_option ? `<span class="badge ok">${escapeHtml(decision.selected_option)}</span>` : `<span class="subtle">-</span>`;

  const tabs = `
    <div class="inline-tabs">
      <button class="btn ${activeTab === "decision" ? "accent" : ""}" type="button" data-intake-inline-tab="${encodeTag(intakeId)}" data-tab="decision">${escapeHtml(t("intake.inline.tab_decision"))}</button>
      <button class="btn ${activeTab === "technical" ? "accent" : ""}" type="button" data-intake-inline-tab="${encodeTag(intakeId)}" data-tab="technical">${escapeHtml(t("intake.inline.tab_technical"))}</button>
    </div>
  `;

  const decisionCardMissing = `<div class="subtle">${escapeHtml(t("intake.decision.no_overlay"))}</div>`;

  const optionCards = options.length
    ? `<div class="decision-options">` +
      options
        .map((opt) => {
          const id = String(opt?.id || "").trim().toUpperCase();
          const titleTr = String(opt?.title_tr || "").trim();
          const titleEn = String(opt?.title_en || "").trim();
          const notesTr = String(opt?.notes_tr || "").trim();
          const notesEn = String(opt?.notes_en || "").trim();
          const isChecked = decision.selected_option && decision.selected_option === id;
          const checkedAttr = isChecked ? "checked" : "";
          const label = titleEn ? `${titleTr} (${titleEn})` : titleTr;
          const notes = notesEn ? `${notesTr} (${notesEn})` : notesTr;
          return `
            <label class="decision-option">
              <div class="row" style="justify-content: space-between; align-items: center;">
                <div class="opt-title">${escapeHtml(label || id)}</div>
                <input type="radio" name="decision-opt-${encodeTag(intakeId)}" value="${escapeHtml(id)}" ${checkedAttr} />
              </div>
              <div class="opt-notes">${escapeHtml(notes)}</div>
            </label>
          `;
        })
        .join("") +
      `</div>`
    : decisionCardMissing;

  const noteValue = decision.mark?.note ? String(decision.mark.note || "") : "";

  const decisionBody = `
    <div class="inline-section" style="${activeTab === "decision" ? "" : "display:none;"}">
      <div class="subtle">${escapeHtml(summaryEn ? `${summaryTr} (${summaryEn})` : (summaryTr || ""))}</div>
      <div style="margin-top: 8px; font-weight: 600;">${escapeHtml(qEn ? `${qTr} (${qEn})` : (qTr || ""))}</div>
      <div class="subtle" style="margin-top: 6px;">${escapeHtml(decision.reason_code ? `reason_code=${decision.reason_code}` : "")}</div>
      ${optionCards}
      <div style="margin-top: 10px;">
        <textarea class="input" data-decision-note="${encodeTag(intakeId)}" placeholder="${escapeHtml(t("intake.decision.note_placeholder"))}">${escapeHtml(noteValue)}</textarea>
      </div>
      <div class="row" style="margin-top: 10px;">
        <button class="btn accent" type="button" data-decision-save="${encodeTag(intakeId)}">${escapeHtml(t("intake.decision.save"))}</button>
        <div class="subtle">Öneri: ${badgeRec} ${badgeConf}</div>
      </div>
    </div>
  `;

  const evidencePaths = Array.isArray(item?.evidence_paths) ? item.evidence_paths.map(String) : [];
  const evidenceChips = evidencePaths.length
    ? `<div class="path-chips">` +
      evidencePaths
        .slice(0, 12)
        .map((p) => `<button class="path-chip" type="button" data-intake-evidence="${encodeTag(p)}">${escapeHtml(p)}</button>`)
        .join(" ") +
      `</div>`
    : `<span class="subtle">${escapeHtml(t("common.none"))}</span>`;

  const technicalBody = `
    <div class="inline-section" style="${activeTab === "technical" ? "" : "display:none;"}">
      <div class="subtle">Evidence paths (click to preview)</div>
      ${evidenceChips}
      <details style="margin-top: 10px;">
        <summary class="subtle">Raw intake item JSON (redacted)</summary>
        <pre>${escapeHtml(JSON.stringify(item || {}, null, 2))}</pre>
      </details>
    </div>
  `;

  return `
    <div class="intake-inline-detail" data-inline-intake="${encodeTag(intakeId)}">
      <div class="inline-header">
        <div class="inline-title">${escapeHtml(titleEn ? `${title} (${titleEn})` : title)}</div>
        <div class="row" style="gap: 8px;">
          ${badgeRec}
          ${badgeConf}
          ${badgeExec}
          ${badgeEv}
          ${badgeSel}
        </div>
      </div>
      ${tabs}
      ${decisionBody}
      ${technicalBody}
    </div>
  `;
}

async function saveCockpitDecisionMark(intakeId, selectedOption, note) {
  const id = String(intakeId || "").trim();
  const opt = String(selectedOption || "").trim().toUpperCase();
  const bodyNote = String(note || "").trim();
  if (!id || !opt) return null;
  const res = await fetch(endpoints.decisionMark, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm: true, intake_id: id, selected_option: opt, note: bodyNote }),
  });
  const data = await res.json();
  if (!res.ok) {
    const err = data?.error || data?.status || "UNKNOWN";
    throw new Error(String(err));
  }
  return data;
}

function updateIntakeFilterOptions(items) {
  const buckets = new Map();
  const statuses = new Map();
  const sources = new Map();
  const extensions = new Map();

  const addOption = (map, value) => {
    const raw = normalizeValue(value);
    if (!raw) return;
    const key = normalizeKey(raw);
    if (!map.has(key)) map.set(key, raw);
  };

  (Array.isArray(items) ? items : []).forEach((item) => {
    addOption(buckets, item.bucket);
    addOption(statuses, item.status);
    addOption(sources, item.source_type);
    const ext = item.suggested_extension;
    if (Array.isArray(ext)) {
      ext.forEach((value) => addOption(extensions, value));
    } else {
      addOption(extensions, ext);
    }
  });

  state.filterOptions.intake.bucket = Array.from(buckets.values()).sort((a, b) => a.localeCompare(b));
  state.filterOptions.intake.status = Array.from(statuses.values()).sort((a, b) => a.localeCompare(b));
  state.filterOptions.intake.source = Array.from(sources.values()).sort((a, b) => a.localeCompare(b));
  state.filterOptions.intake.extension = Array.from(extensions.values()).sort((a, b) => a.localeCompare(b));

  ["bucket", "status", "source", "extension"].forEach((field) => renderTagSelect(field));
}

function renderTagSelect(field) {
  const wrap = $(`#filter-${field}`);
  const tagsEl = $(`#filter-${field}-tags`);
  const input = $(`#filter-${field}-input`);
  const optionsEl = $(`#filter-${field}-options`);
  if (!wrap || !tagsEl || !input || !optionsEl) return;

  const selected = state.filters.intake[field] || [];
  const selectedKeys = new Set(selected.map((val) => normalizeKey(val)));
  const query = input.value.trim().toLowerCase();
  const options = (state.filterOptions.intake[field] || [])
    .filter((opt) => !selectedKeys.has(normalizeKey(opt)))
    .filter((opt) => (query ? opt.toLowerCase().includes(query) : true))
    .sort((a, b) => a.localeCompare(b));
  const activeIndex = getTagSelectActiveIndex("intake", field, options.length);
  setTagSelectActiveIndex("intake", field, activeIndex, options.length);
  const optionIdPrefix = `filter-${field}-opt-`;
  if (wrap.classList.contains("open")) {
    setAriaExpanded(input, true);
    if (options.length) {
      input.setAttribute("aria-activedescendant", `${optionIdPrefix}${activeIndex}`);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  } else {
    setAriaExpanded(input, false);
  }

  tagsEl.innerHTML = selected
    .map((value) => {
      const encoded = encodeTag(value);
      return `<span class="tag">${escapeHtml(value)}<button data-remove="${encoded}" aria-label="${escapeHtml(t("actions.remove_tag"))}">x</button></span>`;
    })
    .join("");

  optionsEl.innerHTML = options.length
    ? options
        .map((value, idx) => {
          const encoded = encodeTag(value);
          const isActive = idx === activeIndex;
          const cls = `tag-option${isActive ? " active" : ""}`;
          return `<div class="${cls}" role="option" id="${optionIdPrefix}${idx}" aria-selected="${isActive ? "true" : "false"}" data-value="${encoded}">${escapeHtml(value)}</div>`;
        })
        .join("")
    : `<div class="tag-option subtle" role="option" aria-selected="false">${escapeHtml(t("empty.no_items"))}</div>`;
}

function addTag(field, value) {
  const list = state.filters.intake[field] || [];
  const key = normalizeKey(value);
  if (!key) return;
  const exists = list.some((item) => normalizeKey(item) === key);
  if (exists) return;
  list.push(normalizeValue(value));
  list.sort((a, b) => a.localeCompare(b));
  state.filters.intake[field] = list;
  renderTagSelect(field);
}

function removeTag(field, value) {
  const list = state.filters.intake[field] || [];
  const key = normalizeKey(value);
  state.filters.intake[field] = list.filter((item) => normalizeKey(item) !== key);
  renderTagSelect(field);
}

function normalizeNorthStarFindingTopic(value) {
  const raw = String(value || "").trim();
  if (!raw) return t("north_star.unknown");
  const labels = state.lang === "tr" ? NORTH_STAR_TOPIC_LABELS.tr : NORTH_STAR_TOPIC_LABELS.en;
  const label = labels[raw];
  if (!label) return raw;
  // Include the raw key to keep it deterministic and debuggable.
  return `${label} (${raw})`;
}

function normalizeNorthStarFindingDomains(domains) {
  if (!Array.isArray(domains) || domains.length === 0) return [t("common.none")];
  const cleaned = domains.map((d) => String(d || "").trim()).filter((d) => Boolean(d));
  return cleaned.length ? cleaned : [t("common.none")];
}

const NORTH_STAR_TOPIC_LABELS = {
  en: {
    ai_otomasyon: "AI automation potential",
    baglam_uyum: "Context management and alignment",
    deterministiklik_tekrarlanabilirlik: "Determinism and repeatability",
    entegrasyon_birlikte_calisabilirlik: "Integration and interoperability",
    gozlemlenebilirlik_izleme_olcme: "Observability / monitoring / measurement",
    kalite_dogruluk: "Quality / accuracy",
    maliyet_verimlilik_kaynak: "Cost / efficiency / resource usage",
    olceklenebilirlik: "Scalability",
    paydas_memnuniyeti_deger: "Stakeholder satisfaction / value",
    surdurulebilirlik_esg_isg_etik: "Sustainability – ESG / HSE / Ethics",
    surec_etkinligi_olgunluk: "Process effectiveness / maturity",
    sureklilik_dayaniklilik: "Continuity / resilience",
    uygunluk_risk_guvence_kontrol: "Compliance / risk / assurance / control",
    zaman_hiz_ceviklik: "Time / speed / agility",
  },
  tr: {
    ai_otomasyon: "Yapay zekâ ile yapılabilecekler / otomasyon potansiyeli",
    baglam_uyum: "Bağlam yönetimi ve uyum",
    deterministiklik_tekrarlanabilirlik: "Deterministiklik ve tekrarlanabilirlik",
    entegrasyon_birlikte_calisabilirlik: "Entegrasyon ve birlikte çalışabilirlik",
    gozlemlenebilirlik_izleme_olcme: "Gözlemlenebilirlik / izleme / ölçme",
    kalite_dogruluk: "Kalite / doğruluk",
    maliyet_verimlilik_kaynak: "Maliyet / verimlilik / kaynak kullanımı",
    olceklenebilirlik: "Ölçeklenebilirlik",
    paydas_memnuniyeti_deger: "Paydaş memnuniyeti / değer katkısı",
    surdurulebilirlik_esg_isg_etik: "Sürdürülebilirlik – ESG / İSG / Etik",
    surec_etkinligi_olgunluk: "Süreç etkinliği / olgunluk",
    sureklilik_dayaniklilik: "Süreklilik / dayanıklılık",
    uygunluk_risk_guvence_kontrol: "Uyum / risk / güvence / kontrol",
    zaman_hiz_ceviklik: "Zaman / hız / çeviklik",
  },
};

const NORTH_STAR_FINDINGS_PRESETS = [
  { key: "CUSTOM", labelKey: "north_star.preset.custom" },
  { key: "ALL", labelKey: "north_star.preset.all", topics: [] },
  {
    key: "ETHICS_COMPLIANCE",
    labelKey: "north_star.preset.ethics_compliance",
    topics: ["uygunluk_risk_guvence_kontrol", "surdurulebilirlik_esg_isg_etik", "baglam_uyum"],
  },
  {
    key: "COMPLIANCE_CONTROL",
    labelKey: "north_star.preset.compliance_control",
    topics: ["uygunluk_risk_guvence_kontrol"],
  },
  { key: "CONTEXT_ALIGNMENT", labelKey: "north_star.preset.context_alignment", topics: ["baglam_uyum"] },
  { key: "SUSTAINABILITY_ETHICS", labelKey: "north_star.preset.sustainability_ethics", topics: ["surdurulebilirlik_esg_isg_etik"] },
];

function setNorthStarFindingsPresetKey(next) {
  state.filters.northStarFindings.preset = String(next || "CUSTOM");
  const presetSelect = $("#ns-findings-preset");
  if (presetSelect) presetSelect.value = state.filters.northStarFindings.preset;
}

function applyNorthStarFindingsPreset(next) {
  const key = String(next || "CUSTOM");
  const preset = NORTH_STAR_FINDINGS_PRESETS.find((p) => p.key === key) || null;
  setNorthStarFindingsPresetKey(key);
  if (!preset || !Array.isArray(preset.topics)) return;

  const topics = preset.topics.map((t) => normalizeNorthStarFindingTopic(t));
  state.filters.northStarFindings.topic = topics
    .map((t) => String(t || "").trim())
    .filter((t) => Boolean(t))
    .sort((a, b) => a.localeCompare(b));

  // Presets are intended for exploration; do not hide NOT_TRIGGERED/UNKNOWN by default.
  // Findings are already sorted with TRIGGERED first.
  state.filters.northStarFindings.match = [];
  state.northStarFindingSelected = null;

  const topicInput = $("#ns-findings-filter-topic-input");
  if (topicInput) topicInput.value = "";
  renderNorthStarFindingsTagSelect("topic");
  renderNorthStarFindingsTagSelect("match");
  renderNorthStarFindings();
}

function updateNorthStarFindingsFilterOptions(items) {
  const domains = new Map();
  const topics = new Map();
  const catalogs = new Map();

  const addOption = (map, value) => {
    const raw = normalizeValue(value);
    if (!raw) return;
    const key = normalizeKey(raw);
    if (!map.has(key)) map.set(key, raw);
  };

  (Array.isArray(items) ? items : []).forEach((item) => {
    normalizeNorthStarFindingDomains(item?.domains).forEach((d) => addOption(domains, d));
    addOption(topics, normalizeNorthStarFindingTopic(item?.topic));
    addOption(catalogs, String(item?.catalog || ""));
  });

  state.filterOptions.northStarFindings.domain = Array.from(domains.values()).sort((a, b) => a.localeCompare(b));
  state.filterOptions.northStarFindings.topic = Array.from(topics.values()).sort((a, b) => a.localeCompare(b));
  const nextCatalogs = Array.from(catalogs.values())
    .map((c) => String(c || "").trim())
    .filter((c) => Boolean(c))
    .sort((a, b) => a.localeCompare(b));
  state.filterOptions.northStarFindings.catalog = nextCatalogs.length ? nextCatalogs : state.filterOptions.northStarFindings.catalog;

  // Prune selections that no longer exist (fail-closed).
  ["domain", "topic", "match", "catalog"].forEach((field) => {
    const selected = state.filters.northStarFindings[field] || [];
    const options = state.filterOptions.northStarFindings[field] || [];
    const optionKeys = new Set(options.map((opt) => normalizeKey(opt)));
    state.filters.northStarFindings[field] = selected.filter((opt) => optionKeys.has(normalizeKey(opt)));
  });
}

function renderNorthStarFindingsTagSelect(field) {
  const wrap = $(`#ns-findings-filter-${field}`);
  const tagsEl = $(`#ns-findings-filter-${field}-tags`);
  const input = $(`#ns-findings-filter-${field}-input`);
  const optionsEl = $(`#ns-findings-filter-${field}-options`);
  if (!wrap || !tagsEl || !input || !optionsEl) return;

  const selected = state.filters.northStarFindings[field] || [];
  const selectedKeys = new Set(selected.map((val) => normalizeKey(val)));
  const query = input.value.trim().toLowerCase();
  const options = (state.filterOptions.northStarFindings[field] || [])
    .filter((opt) => !selectedKeys.has(normalizeKey(opt)))
    .filter((opt) => (query ? opt.toLowerCase().includes(query) : true))
    .sort((a, b) => a.localeCompare(b));
  const activeIndex = getTagSelectActiveIndex("northStarFindings", field, options.length);
  setTagSelectActiveIndex("northStarFindings", field, activeIndex, options.length);
  const optionIdPrefix = `ns-findings-${field}-opt-`;
  if (wrap.classList.contains("open")) {
    setAriaExpanded(input, true);
    if (options.length) {
      input.setAttribute("aria-activedescendant", `${optionIdPrefix}${activeIndex}`);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  } else {
    setAriaExpanded(input, false);
  }

  tagsEl.innerHTML = selected
    .map((value) => {
      const encoded = encodeTag(value);
      return `<span class="tag">${escapeHtml(value)}<button data-remove="${encoded}" aria-label="${escapeHtml(t("actions.remove_tag"))}">x</button></span>`;
    })
    .join("");

  optionsEl.innerHTML = options.length
    ? options
        .map((value, idx) => {
          const encoded = encodeTag(value);
          const isActive = idx === activeIndex;
          const cls = `tag-option${isActive ? " active" : ""}`;
          return `<div class="${cls}" role="option" id="${optionIdPrefix}${idx}" aria-selected="${isActive ? "true" : "false"}" data-value="${encoded}">${escapeHtml(value)}</div>`;
        })
        .join("")
    : `<div class="tag-option subtle" role="option" aria-selected="false">${escapeHtml(t("empty.no_items"))}</div>`;
}

function addNorthStarFindingTag(field, value) {
  const list = state.filters.northStarFindings[field] || [];
  const key = normalizeKey(value);
  if (!key) return;
  const exists = list.some((item) => normalizeKey(item) === key);
  if (exists) return;
  list.push(normalizeValue(value));
  list.sort((a, b) => a.localeCompare(b));
  state.filters.northStarFindings[field] = list;
  renderNorthStarFindingsTagSelect(field);
}

function removeNorthStarFindingTag(field, value) {
  const list = state.filters.northStarFindings[field] || [];
  const key = normalizeKey(value);
  state.filters.northStarFindings[field] = list.filter((item) => normalizeKey(item) !== key);
  renderNorthStarFindingsTagSelect(field);
}

function findingsMatchRank(value) {
  const norm = String(value || "").toUpperCase();
  if (norm === "TRIGGERED") return 0;
  if (norm === "NOT_TRIGGERED") return 1;
  return 2;
}

function renderNorthStarFindingsBadge(status) {
  const norm = String(status || "UNKNOWN").toUpperCase();
  const cls = norm === "TRIGGERED" ? "ok" : norm === "NOT_TRIGGERED" ? "idle" : "warn";
  return `<span class="badge ${cls}">${escapeHtml(norm)}</span>`;
}

function formatNorthStarCatalogLabel(raw) {
  const norm = normalizeKey(raw);
  if (["REFERENCE", "TREND", "TREND_CATALOG", "TREND_CATALOG_V1"].includes(norm)) return t("north_star.catalog.reference");
  if (["CAPABILITY", "BP", "BEST_PRACTICE", "BP_CATALOG", "BP_CATALOG_V1"].includes(norm)) return t("north_star.catalog.capability");
  if (["CRITERION", "LENS", "LENS_REQUIREMENT"].includes(norm)) return t("north_star.catalog.criterion");
  return String(raw || "");
}

function pickCatalogField(item, keys) {
  for (const key of keys) {
    const value = item ? item[key] : null;
    if (value) return String(value).trim();
  }
  return "";
}

function buildNorthStarCatalogIndex(payload) {
  const trend = unwrap(payload?.trend_catalog || {});
  const bp = unwrap(payload?.bp_catalog || {});
  const trendItems = Array.isArray(trend?.items) ? trend.items : [];
  const bpItems = Array.isArray(bp?.items) ? bp.items : [];
  const byId = {};
  const byTitle = {};

  const addItem = (item, source) => {
    if (!item || typeof item !== "object") return;
    const id = pickCatalogField(item, ["id", "item_id", "itemId"]);
    const title = pickCatalogField(item, ["title"]);
    const theme_tr = pickCatalogField(item, ["theme_title_tr", "theme_tr", "theme_title", "theme"]);
    const subtheme_tr = pickCatalogField(item, ["subtheme_title_tr", "subtheme_tr", "subtheme_title", "subtheme"]);
    const theme_en = pickCatalogField(item, ["theme_title_en", "theme_en"]);
    const subtheme_en = pickCatalogField(item, ["subtheme_title_en", "subtheme_en"]);
    const entry = { id, title, theme_tr, theme_en, subtheme_tr, subtheme_en, source };
    if (id && !byId[id]) byId[id] = entry;
    if (title) {
      const key = normalizeKey(title);
      if (key && !byTitle[key]) byTitle[key] = entry;
    }
  };

  trendItems.forEach((item) => addItem(item, "trend_catalog"));
  bpItems.forEach((item) => addItem(item, "bp_catalog"));

  return {
    byId,
    byTitle,
    sources: {
      trend_count: trendItems.length,
      bp_count: bpItems.length,
    },
    available: trendItems.length + bpItems.length > 0,
  };
}

function formatThemeSubthemeLabel(entry, kind) {
  if (!entry) return "—";
  const tr = kind === "theme" ? entry.theme_tr : entry.subtheme_tr;
  const en = kind === "theme" ? entry.theme_en : entry.subtheme_en;
  if (tr && en && tr !== en) return `${tr} (${en})`;
  return tr || en || "—";
}

function getNorthStarJoinForItem(item) {
  const index = state.northStarCatalogIndex || { byId: {}, byTitle: {}, available: false };
  const id = String(item?.id || "").trim();
  const title = String(item?.title || "").trim();
  let entry = id ? index.byId?.[id] : null;
  let fallback = false;
  if (!entry && title) {
    const key = normalizeKey(title);
    entry = key ? index.byTitle?.[key] : null;
    fallback = Boolean(entry);
  }
  const miss = !entry;
  return {
    entry,
    theme_label: formatThemeSubthemeLabel(entry, "theme"),
    subtheme_label: formatThemeSubthemeLabel(entry, "subtheme"),
    miss,
    fallback,
  };
}

function renderNorthStarJoinBanner(stats) {
  const el = $("#ns-findings-join-banner");
  if (!el) return;
  if (!stats || !stats.miss_count) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  const reason = stats.reason ? ` reason_code=${stats.reason}` : "";
  el.textContent = t("north_star.join.banner", { miss: String(stats.miss_count), fallback: String(stats.fallback_count || 0), reason });
  el.style.display = "block";
}

function getNorthStarFindingKey(item) {
  const lens = String(item?.lens || "");
  const catalog = String(item?.catalog || "");
  const id = String(item?.id || "");
  // Some views (e.g. ALL lenses) may include multiple items with the same catalog+id.
  // Include lens in the key when available to keep selection deterministic.
  return lens ? `${lens}:${catalog}:${id}` : `${catalog}:${id}`;
}

function renderNorthStarFindings() {
  const findings = state.northStarFindings;
  const itemsRaw = Array.isArray(findings?.items) ? findings.items : [];
  const includeLens = itemsRaw.some((item) => Boolean(item && item.lens));
  const catalogIndex = state.northStarCatalogIndex || { available: false };

  const summaryEl = $("#ns-findings-summary");
  const tableEl = $("#ns-findings-table");
  const detailEl = $("#ns-findings-detail");
  if (!tableEl) return;

  const searchInput = $("#ns-findings-search");
  const search = searchInput ? searchInput.value.trim() : state.filters.northStarFindings.search || "";
  state.filters.northStarFindings.search = search;

  const domain = state.filters.northStarFindings.domain || [];
  const topic = state.filters.northStarFindings.topic || [];
  const match = state.filters.northStarFindings.match || [];
  const catalog = state.filters.northStarFindings.catalog || [];

  let items = itemsRaw.map((item) => {
    const domains = normalizeNorthStarFindingDomains(item?.domains);
    const topicNorm = normalizeNorthStarFindingTopic(item?.topic);
    const join = getNorthStarJoinForItem(item);
    const catalogLabel = formatNorthStarCatalogLabel(item?.catalog);
    return {
      ...item,
      _domains_norm: domains,
      _domains_joined: domains.join(", "),
      _topic_norm: topicNorm,
      _match_rank: findingsMatchRank(item?.match_status),
      _reasons_count: Array.isArray(item?.reasons) ? item.reasons.length : 0,
      _evidence_count: Array.isArray(item?.evidence_pointers) ? item.evidence_pointers.length : 0,
      _theme_label: join.theme_label,
      _subtheme_label: join.subtheme_label,
      _join_miss: join.miss,
      _join_fallback: join.fallback,
      _catalog_label: catalogLabel,
    };
  });

  if (domain.length) {
    const domainKeys = new Set(domain.map((val) => normalizeKey(val)));
    items = items.filter((item) => item._domains_norm.some((d) => domainKeys.has(normalizeKey(d))));
  }
  if (topic.length) {
    const topicKeys = new Set(topic.map((val) => normalizeKey(val)));
    items = items.filter((item) => topicKeys.has(normalizeKey(item._topic_norm)));
  }
  if (match.length) {
    const matchKeys = new Set(match.map((val) => normalizeKey(val)));
    items = items.filter((item) => matchKeys.has(normalizeKey(item.match_status)));
  }
  if (catalog.length) {
    const catalogKeys = new Set(catalog.map((val) => normalizeKey(val)));
    items = items.filter((item) => catalogKeys.has(normalizeKey(item.catalog)));
  }
  if (search) {
    const q = search.toUpperCase();
    items = items.filter((item) => {
      const hay = [
        item.catalog,
        item._catalog_label,
        item.id,
        item.title,
        item._topic_norm,
        item._domains_joined,
        item._theme_label,
        item._subtheme_label,
        Array.isArray(item.tags) ? item.tags.join(" ") : "",
        Array.isArray(item.reasons) ? item.reasons.join(" ") : "",
        includeLens ? String(item.lens || "") : "",
      ]
        .map((x) => String(x || ""))
        .join(" ")
        .toUpperCase();
      return hay.includes(q);
    });
  }

  items = stableSort(items, (a, b) => {
    const mr = (a._match_rank || 9) - (b._match_rank || 9);
    if (mr !== 0) return mr;
    if (includeLens) {
      const l = String(a.lens || "").localeCompare(String(b.lens || ""));
      if (l !== 0) return l;
    }
    const t = String(a._topic_norm || "").localeCompare(String(b._topic_norm || ""));
    if (t !== 0) return t;
    const d = String(a._domains_joined || "").localeCompare(String(b._domains_joined || ""));
    if (d !== 0) return d;
    const c = String(a.catalog || "").localeCompare(String(b.catalog || ""));
    if (c !== 0) return c;
    return String(a.id || "").localeCompare(String(b.id || ""));
  });

  const total = itemsRaw.length;
  const filtered = items.length;
  const counts = {
    triggered: itemsRaw.filter((x) => String(x?.match_status || "").toUpperCase() === "TRIGGERED").length,
    not_triggered: itemsRaw.filter((x) => String(x?.match_status || "").toUpperCase() === "NOT_TRIGGERED").length,
    unknown: itemsRaw.filter((x) => String(x?.match_status || "").toUpperCase() === "UNKNOWN").length,
  };
  if (summaryEl) {
    let extra = "";
    if (includeLens) {
      const byLens = new Map();
      items.forEach((it) => {
        const name = String(it.lens || t("common.unknown"));
        byLens.set(name, (byLens.get(name) || 0) + 1);
      });
      const lensParts = Array.from(byLens.entries())
        .sort((a, b) => (b[1] - a[1] !== 0 ? b[1] - a[1] : String(a[0]).localeCompare(String(b[0]))))
        .slice(0, 8)
        .map(([k, v]) => `${k}:${v}`)
        .join(", ");
      extra = lensParts ? ` | by_lens=${lensParts}` : "";
    }
    summaryEl.textContent = `items_total=${total} filtered=${filtered} triggered=${counts.triggered} not_triggered=${counts.not_triggered} unknown=${counts.unknown}${extra}`;
  }

  const joinStats = {
    total: items.length,
    miss_count: items.filter((x) => x._join_miss).length,
    fallback_count: items.filter((x) => x._join_fallback).length,
    reason: catalogIndex.available ? "" : "CATALOG_MISSING",
  };
  state.northStarFindingsJoinStats = joinStats;
  renderNorthStarJoinBanner(joinStats);

  if (items.length === 0) {
    tableEl.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_findings_match"))}</div>`;
  } else {
    const headers = [
      includeLens ? t("north_star.table.lens") : null,
      t("north_star.table.match"),
      t("north_star.table.topic"),
      t("north_star.table.domain"),
      t("north_star.table.title"),
      t("north_star.table.theme"),
      t("north_star.table.subtheme"),
      t("north_star.table.catalog"),
      t("north_star.table.id"),
      t("north_star.table.reasons"),
      t("north_star.table.evidence"),
    ]
      .filter((h) => h !== null)
      .map((h) => `<th>${escapeHtml(h)}</th>`)
      .join("");
    const rows = items
      .slice(0, 250)
      .map((item) => {
        const key = encodeTag(getNorthStarFindingKey(item));
        return `
          <tr class="clickable" data-finding="${key}">
            ${includeLens ? `<td>${escapeHtml(String(item.lens || ""))}</td>` : ""}
            <td>${renderNorthStarFindingsBadge(item.match_status)}</td>
            <td>${escapeHtml(item._topic_norm)}</td>
            <td>${escapeHtml(item._domains_joined)}</td>
            <td>${escapeHtml(String(item.title || ""))}</td>
            <td>${escapeHtml(String(item._theme_label || "—"))}</td>
            <td>${escapeHtml(String(item._subtheme_label || "—"))}</td>
            <td>${escapeHtml(String(item._catalog_label || item.catalog || ""))}</td>
            <td>${escapeHtml(String(item.id || ""))}</td>
            <td>${escapeHtml(String(item._reasons_count))}</td>
            <td>${escapeHtml(String(item._evidence_count))}</td>
          </tr>
        `;
      })
      .join("");

    tableEl.innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr>${headers}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;

    tableEl.querySelectorAll("[data-finding]").forEach((row) => {
      row.addEventListener("click", () => {
        const key = decodeTag(row.dataset.finding || "");
        const picked = items.find((it) => getNorthStarFindingKey(it) === key) || null;
        state.northStarFindingSelected = picked;
        renderNorthStarFindingsDetail();
      });
    });
  }

  renderNorthStarFindingsDetail();
  if (detailEl && state.northStarFindingSelected == null) {
    detailEl.innerHTML = `<div class="empty">${escapeHtml(t("empty.select_finding_row"))}</div>`;
  }
}

function renderNorthStarFindingsDetail() {
  const detailEl = $("#ns-findings-detail");
  if (!detailEl) return;

  const item = state.northStarFindingSelected;
  if (!item) {
    detailEl.innerHTML = "";
    return;
  }

  const domains = normalizeNorthStarFindingDomains(item.domains);
  const topic = normalizeNorthStarFindingTopic(item.topic);
  const tags = Array.isArray(item.tags) ? item.tags.map((t) => String(t || "")).filter((t) => Boolean(t)) : [];
  const reasons = Array.isArray(item.reasons) ? item.reasons.map((r) => String(r || "")).filter((r) => Boolean(r)) : [];
  const evidence = Array.isArray(item.evidence_pointers)
    ? item.evidence_pointers.map((p) => String(p || "")).filter((p) => Boolean(p))
    : [];
  const summary = typeof item.summary === "string" ? item.summary.trim() : "";
  const expectations = Array.isArray(item.evidence_expectations)
    ? item.evidence_expectations.map((x) => String(x || "").trim()).filter((x) => Boolean(x))
    : [];
  const remediation = Array.isArray(item.remediation)
    ? item.remediation.map((x) => String(x || "").trim()).filter((x) => Boolean(x))
    : [];
  const themeLabel = String(item._theme_label || "");
  const subthemeLabel = String(item._subtheme_label || "");
  const catalogLabel = String(item._catalog_label || formatNorthStarCatalogLabel(item.catalog || "") || "");

  const evidenceButtons = evidence.length
    ? evidence
        .slice(0, 25)
        .map(
          (p) =>
            `<button class="btn small ghost" type="button" data-evidence-open="${encodeTag(p)}" title="${escapeHtml(t("evidence.open_in_evidence_title"))}">${escapeHtml(p)}</button>`
        )
        .join("")
    : `<span class="subtle">${escapeHtml(t("common.none"))}</span>`;

  const openExtra = String(item.match_status || "").toUpperCase() === "TRIGGERED";

  detailEl.innerHTML = `
    <div class="note-item">
      <div class="note-title">${escapeHtml(String(item.title || ""))}</div>
      <div class="note-meta">${renderNorthStarFindingsBadge(item.match_status)}${item.lens ? ` | lens=${escapeHtml(String(item.lens || ""))}` : ""} | topic=${escapeHtml(topic)} | domains=${escapeHtml(domains.join(", "))} | theme=${escapeHtml(themeLabel || "—")} | subtheme=${escapeHtml(subthemeLabel || "—")} | catalog=${escapeHtml(catalogLabel)} | id=${escapeHtml(String(item.id || ""))}</div>
      <div class="note-tags">${tags.slice(0, 18).map((t) => `<span class="note-tag">${escapeHtml(t)}</span>`).join("")}</div>
      ${
        summary
          ? `<div class="note-body">${escapeHtml(summary)}</div>`
          : `<div class="subtle">${escapeHtml(t("north_star.detail.summary_label"))} <span class="subtle">${escapeHtml(t("common.none"))}</span></div>`
      }
      <div class="subtle">reasons=${escapeHtml(String(reasons.length))} evidence_pointers=${escapeHtml(String(evidence.length))} evidence_expectations=${escapeHtml(String(expectations.length))} remediation=${escapeHtml(String(remediation.length))}</div>
      ${
        reasons.length
          ? `<details open><summary class="subtle">${escapeHtml(t("north_star.table.reasons"))}</summary><ul class="subtle">${reasons
              .map((r) => `<li>${escapeHtml(r)}</li>`)
              .join("")}</ul></details>`
          : ""
      }
      ${
        expectations.length
          ? `<details ${openExtra ? "open" : ""}><summary class="subtle">${escapeHtml(t("north_star.detail.evidence_expectations"))}</summary><ul class="subtle">${expectations
              .map((x) => `<li>${escapeHtml(x)}</li>`)
              .join("")}</ul></details>`
          : ""
      }
      ${
        remediation.length
          ? `<details ${openExtra ? "open" : ""}><summary class="subtle">${escapeHtml(t("north_star.detail.remediation_ideas"))}</summary><ul class="subtle">${remediation
              .map((x) => `<li>${escapeHtml(x)}</li>`)
              .join("")}</ul></details>`
          : ""
      }
      <details>
        <summary class="subtle">${escapeHtml(t("evidence.pointers_title"))}</summary>
        <div class="path-chips">${evidenceButtons}</div>
      </details>
    </div>
  `;

  detailEl.querySelectorAll("[data-evidence-open]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const path = decodeTag(btn.dataset.evidenceOpen || "");
      openEvidencePreview(path);
    });
  });
}

function clearNorthStarFindingsFilters() {
  state.filters.northStarFindings.search = "";
  state.filters.northStarFindings.domain = [];
  state.filters.northStarFindings.topic = [];
  state.filters.northStarFindings.match = ["TRIGGERED"];
  state.filters.northStarFindings.catalog = [];
  setNorthStarFindingsPresetKey("CUSTOM");
  state.northStarFindingSelected = null;

  const searchInput = $("#ns-findings-search");
  if (searchInput) searchInput.value = "";

  ["domain", "topic", "match", "catalog"].forEach((field) => {
    const input = $(`#ns-findings-filter-${field}-input`);
    if (input) input.value = "";
    renderNorthStarFindingsTagSelect(field);
  });
}

function setupNorthStarFindingsTagSelects() {
  if (northStarFindingsUiAttached) return;
  const fields = ["domain", "topic", "match", "catalog"];
  const closeAll = (except) => {
    fields.forEach((field) => {
      if (field === except) return;
      const wrap = $(`#ns-findings-filter-${field}`);
      if (wrap) wrap.classList.remove("open");
      const input = $(`#ns-findings-filter-${field}-input`);
      if (input) setAriaExpanded(input, false);
    });
  };

  fields.forEach((field) => {
    const wrap = $(`#ns-findings-filter-${field}`);
    const input = $(`#ns-findings-filter-${field}-input`);
    const options = $(`#ns-findings-filter-${field}-options`);
    if (!wrap || !input || !options) return;
    const toggle = wrap.querySelector(".tag-toggle");

    const openSelect = () => {
      closeAll(field);
      wrap.classList.add("open");
      setTagSelectActiveIndex("northStarFindings", field, 0);
      renderNorthStarFindingsTagSelect(field);
      requestAnimationFrame(() => scrollTagSelectActiveOptionIntoView(options));
    };

    input.addEventListener("focus", () => {
      openSelect();
    });
    input.addEventListener("input", () => renderNorthStarFindingsTagSelect(field));
    input.addEventListener("keydown", (event) => {
      const key = event.key;
      if (key === "Escape") {
        wrap.classList.remove("open");
        setAriaExpanded(input, false);
        return;
      }
      if (key !== "ArrowDown" && key !== "ArrowUp" && key !== "Enter") return;
      if (!wrap.classList.contains("open") && (key === "ArrowDown" || key === "ArrowUp")) {
        openSelect();
      }
      if (!wrap.classList.contains("open")) return;

      const optionEls = Array.from(options.querySelectorAll(".tag-option[data-value]"));
      if (!optionEls.length) return;
      const current = getTagSelectActiveIndex("northStarFindings", field, optionEls.length);

      if (key === "ArrowDown" || key === "ArrowUp") {
        event.preventDefault();
        const delta = key === "ArrowDown" ? 1 : -1;
        setTagSelectActiveIndex("northStarFindings", field, clampIndex(current + delta, optionEls.length), optionEls.length);
        renderNorthStarFindingsTagSelect(field);
        requestAnimationFrame(() => scrollTagSelectActiveOptionIntoView(options));
        return;
      }

      if (key === "Enter") {
        event.preventDefault();
        const target = optionEls[current];
        const rawValue = target?.dataset?.value;
        if (!rawValue) return;
        addNorthStarFindingTag(field, decodeTag(rawValue));
        if (field === "topic") setNorthStarFindingsPresetKey("CUSTOM");
        input.value = "";
        openSelect();
        input.focus();
        renderNorthStarFindings();
      }
    });
    input.addEventListener("blur", () => {
      setTimeout(() => {
        if (wrap.contains(document.activeElement)) return;
        wrap.classList.remove("open");
        setAriaExpanded(input, false);
      }, 150);
    });
    options.addEventListener("mousedown", (event) => event.preventDefault());
    if (toggle) {
      toggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (wrap.classList.contains("open")) {
          wrap.classList.remove("open");
          setAriaExpanded(input, false);
        } else {
          openSelect();
        }
        input.focus();
      });
    }
    wrap.addEventListener("click", (event) => {
      const target = event.target;
      if (target?.classList?.contains("tag-toggle")) return;
      const rawValue = target?.dataset?.value;
      const rawRemove = target?.dataset?.remove;
      if (rawValue) {
        addNorthStarFindingTag(field, decodeTag(rawValue));
        if (field === "topic") setNorthStarFindingsPresetKey("CUSTOM");
        input.value = "";
        openSelect();
        input.focus();
        renderNorthStarFindings();
      }
      if (rawRemove) {
        removeNorthStarFindingTag(field, decodeTag(rawRemove));
        if (field === "topic") setNorthStarFindingsPresetKey("CUSTOM");
        renderNorthStarFindings();
      }
      if (target && (target.classList?.contains("tag-select-input") || target.classList?.contains("tag-input"))) {
        openSelect();
        input.focus();
      }
    });
  });

  document.addEventListener("click", (event) => {
    fields.forEach((field) => {
      const wrap = $(`#ns-findings-filter-${field}`);
      if (!wrap) return;
      if (!wrap.contains(event.target)) {
        wrap.classList.remove("open");
        const input = $(`#ns-findings-filter-${field}-input`);
        if (input) setAriaExpanded(input, false);
      }
    });
  });
  northStarFindingsUiAttached = true;
}

function setupNorthStarFindingsUi(findings, { lensKey = null, lensLabel = null } = {}) {
  const meta = $("#ns-findings-meta");
  const normalizedLensKey = lensKey === null ? state.northStarFindingsLensName : String(lensKey || "");
  state.northStarFindingsLensName = normalizedLensKey;
  const normalizedLensLabel = lensLabel === null ? normalizedLensKey : String(lensLabel || "");

  const itemsRaw = Array.isArray(findings?.items) ? findings.items : [];
  state.northStarFindings =
    findings && typeof findings === "object"
      ? findings
      : { version: "v1", summary: { total: 0, triggered: 0, not_triggered: 0, unknown: 0 }, items: [] };

  updateNorthStarFindingsFilterOptions(itemsRaw);
  state.northStarFindingSelected = null;

  if (meta) {
    const summary = state.northStarFindings?.summary && typeof state.northStarFindings.summary === "object" ? state.northStarFindings.summary : {};
    meta.textContent = normalizedLensKey
      ? `lens=${normalizedLensLabel} | total=${summary.total ?? itemsRaw.length} triggered=${summary.triggered ?? "-"} not_triggered=${summary.not_triggered ?? "-"} unknown=${summary.unknown ?? "-"}`
      : t("north_star.select_lens_hint");
  }

  if (!northStarFindingsControlsAttached) {
    const presetSelect = $("#ns-findings-preset");
    if (presetSelect) {
      presetSelect.innerHTML = NORTH_STAR_FINDINGS_PRESETS.map((p) => {
        const label = t(String(p.labelKey || "")) || String(p.key || "");
        return `<option value="${escapeHtml(p.key)}">${escapeHtml(label)}</option>`;
      }).join("");
      const preferredPreset = String(state.filters.northStarFindings.preset || "CUSTOM");
      presetSelect.value = preferredPreset;
      presetSelect.addEventListener("change", () => applyNorthStarFindingsPreset(presetSelect.value));
    }

    const lensSelect = $("#ns-findings-lens");
    if (lensSelect) {
      lensSelect.addEventListener("change", () => {
        const selectedKey = String(lensSelect.value || "");
        const byLens = state.northStarFindingsByLens && typeof state.northStarFindingsByLens === "object" ? state.northStarFindingsByLens : {};
        const next = byLens[selectedKey];
        const label = selectedKey === NORTH_STAR_FINDINGS_ALL_LENSES_KEY ? t("north_star.all_lenses") : selectedKey;
        setupNorthStarFindingsUi(next, { lensKey: selectedKey, lensLabel: label });
      });
    }

    const searchInput = $("#ns-findings-search");
    if (searchInput) {
      searchInput.addEventListener("input", () => renderNorthStarFindings());
    }

    const clearBtn = $("#ns-findings-clear");
    if (clearBtn) {
      clearBtn.addEventListener("click", (event) => {
        event.preventDefault();
        clearNorthStarFindingsFilters();
        renderNorthStarFindings();
      });
    }

    setupNorthStarFindingsTagSelects();
    northStarFindingsControlsAttached = true;
  }

  const searchInput = $("#ns-findings-search");
  if (searchInput) {
    searchInput.value = state.filters.northStarFindings.search || "";
  }

  ["domain", "topic", "match", "catalog"].forEach((field) => {
    renderNorthStarFindingsTagSelect(field);
  });
  renderNorthStarFindings();
}

function stableSort(items, compareFn) {
  return items
    .map((item, idx) => ({ item, idx }))
    .sort((a, b) => {
      const res = compareFn(a.item, b.item);
      if (res !== 0) return res;
      return a.idx - b.idx;
    })
    .map((entry) => entry.item);
}

function compareBy(key, dir = "asc") {
  const mult = dir === "desc" ? -1 : 1;
  return (a, b) => {
    const av = String(a?.[key] ?? "");
    const bv = String(b?.[key] ?? "");
    return av.localeCompare(bv) * mult;
  };
}

function formatNumber(value, digits = 2) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(digits);
  }
  return value === 0 ? "0" : String(value || "-");
}

function renderActionLog() {
  const container = $("#action-log");
  if (!container) return;
  if (!state.actionLog.length) {
    container.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_actions"))}</div>`;
    return;
  }
  container.innerHTML = state.actionLog
    .slice(0, 20)
    .map((entry) => {
      const ts = escapeHtml(entry.ts);
      const op = escapeHtml(entry.op);
      const status = escapeHtml(entry.status);
      const runId = escapeHtml(entry.run_id || "-");
      const jobId = escapeHtml(entry.job_id || "");
      const evid = escapeHtml(entry.evidence_count);
      const idPart = jobId ? `job_id=${jobId}` : `run_id=${runId}`;
      return `<div class="entry">${ts} | ${op} | ${status} | ${idPart} | evid=${evid}</div>`;
    })
    .join("");
}

function actionKey(data) {
  const jobId = String(data?.job_id || "").trim();
  const runId = String(data?.trace_meta?.run_id || "").trim();
  if (jobId) return `job:${jobId}`;
  if (runId) return `run:${runId}`;
  return `ts:${Date.now()}`;
}

function logAction(data) {
  const trace = data?.trace_meta || {};
  const runId = trace.run_id || "";
  const jobId = data?.job_id || "";
  const evidence = Array.isArray(data?.evidence_paths) ? data.evidence_paths.length : 0;
  const key = actionKey(data);
  const entry = {
    key,
    ts: new Date().toISOString(),
    op: data?.op || "",
    status: data?.status || "",
    job_id: jobId,
    run_id: runId,
    evidence_count: evidence,
  };
  const idx = state.actionLog.findIndex((item) => item && item.key === key);
  if (idx >= 0) {
    state.actionLog[idx] = { ...state.actionLog[idx], ...entry };
  } else {
    state.actionLog.unshift(entry);
  }
  if (state.actionLog.length > 50) state.actionLog.pop();
  renderActionLog();
}

function renderActionResponse() {
  const target = $("#action-response");
  const status = $("#action-status");
  const meta = $("#action-meta");
  if (!state.lastAction) {
    if (status) status.textContent = t("action.no_actions_status");
    if (meta) meta.textContent = "";
    if (target) target.textContent = "";
    return;
  }
  const last = state.lastAction;
  if (status) status.textContent = t("action.last_action", { op: last.op || "", status: last.status || "" });
  const trace = last.trace_meta || {};
  const evidence = Array.isArray(last.evidence_paths) ? last.evidence_paths.length : 0;
  if (meta) {
    meta.textContent = `status=${last.status || ""} error=${last.error || last.error_code || ""} run_id=${trace.run_id || ""} work_item_id=${trace.work_item_id || ""} evidence_paths=${evidence}`;
  }
  renderJson(target, last);
}

function setConnectionStatus(ok) {
  const el = $("#conn-status");
  if (!el) return;
  const status = ok ? "OK" : "FAIL";
  setBadge(el, status);
  el.textContent = t("status.api", { status });
}

function setSseStatus(connected) {
  const el = $("#sse-status");
  if (!el) return;
  const status = connected ? "OK" : t("status.disconnected");
  el.classList.remove("ok", "warn", "fail", "idle");
  el.classList.add(connected ? "ok" : "warn");
  el.textContent = t("status.sse", { status });
}

function pickStatus(data) {
  return data?.overall_status || data?.status || "UNKNOWN";
}

function renderOverview() {
  const overview = state.overview || {};
  const summary = overview.summary || {};
  const statusData = unwrap((overview.system_status || state.status) || {});
  const snapshotData = unwrap((overview.ui_snapshot || state.snapshot) || {});

  const overall = summary.overall_status || pickStatus(statusData || {});
  setBadge($("#status-pill"), overall);
  $("#status-summary").textContent = `overall=${overall}`;

  const intakeSummary = summary.work_intake_counts || {};
  const intakeTotal = summary.work_intake_total || 0;
  $("#intake-summary").textContent = `total=${intakeTotal} buckets=${JSON.stringify(intakeSummary)}`;

  const decisionPending = summary.decision_pending || 0;
  const decisionSeeds = summary.decision_seed_pending || 0;
  $("#decision-summary").textContent = `pending=${decisionPending} seeds=${decisionSeeds}`;

  const loopSummary = {
    last_auto_loop: summary.last_auto_loop_path || "",
    last_airrunner_run: summary.last_airrunner_run_path || "",
    last_exec_ticket: summary.last_exec_ticket_path || "",
  };
  $("#loop-summary").textContent = JSON.stringify(loopSummary);

  const lockState = summary.lock_state || "unknown";
  $("#lock-summary").textContent = `lock_state=${lockState}`;

  const next = [];
  if (decisionPending > 0) next.push(t("overview.next.decision_pending"));
  if (intakeTotal === 0) next.push(t("overview.next.no_intake"));
  if (!next.length) next.push(t("overview.next.no_blockers"));
  $("#next-steps").textContent = next.join(" ");

  const banner = $("#next-banner");
  if (banner) {
    if (decisionPending > 0) {
      banner.className = "status-banner warn";
      banner.textContent = t("overview.banner.decisions_pending", { count: decisionPending });
    } else if (intakeTotal === 0) {
      banner.className = "status-banner idle";
      banner.textContent = t("overview.banner.no_intake");
    } else {
      banner.className = "status-banner ok";
      banner.textContent = t("overview.banner.ready");
    }
  }

  renderJson($("#status-json"), statusData || {});
  renderJson($("#snapshot-json"), snapshotData || {});
  renderJson($("#budget-json"), unwrap(state.budget || {}));

  renderActionResponse();
  renderActionLog();
}

function renderNorthStarRunnerBadges(meta) {
  if (!meta || typeof meta !== "object") return "";

  const boolBadge = (label, value, title) => {
    const v = value === true ? "ON" : value === false ? "OFF" : "UNKNOWN";
    const cls = value === true ? "ok" : value === false ? "warn" : "idle";
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : "";
    return `<span class="badge ${cls}"${titleAttr}>${escapeHtml(label)}=${escapeHtml(v)}</span>`;
  };

  const yesNoBadge = (label, value, title) => {
    const v = value === true ? "YES" : value === false ? "NO" : "UNKNOWN";
    const cls = value === true ? "ok" : value === false ? "idle" : "warn";
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : "";
    return `<span class="badge ${cls}"${titleAttr}>${escapeHtml(label)}=${escapeHtml(v)}</span>`;
  };

  const fmtSecondsShort = (seconds) => {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "";
    const s = Math.max(0, Math.floor(seconds));
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
    return `${(s / 86400).toFixed(1)}d`;
  };

  const pieces = [];
  pieces.push(boolBadge("AIRUNNER", meta.enabled_effective, "capability.enabled_effective (airunner enabled flag)"));
  pieces.push(
    boolBadge(
      "AUTO_MODE",
      meta.auto_mode_enabled_effective,
      "capability.auto_mode_enabled_effective (auto mode enabled flag)"
    )
  );

  const mode = String(meta.heartbeat_expectation_mode || "UNKNOWN").trim().toUpperCase();
  const source = String(meta.heartbeat_expectation_source || "").trim();
  const modeCls = mode === "NONE" ? "idle" : mode === "UNKNOWN" ? "warn" : "ok";
  const modeTitle = `monitoring.heartbeat_expectation_mode=${mode}${source ? ` source=${source}` : ""}`;
  pieces.push(`<span class="badge ${modeCls}" title="${escapeHtml(modeTitle)}">HEARTBEAT_EXPECT=${escapeHtml(mode)}</span>`);

  // Monitoring “expected now?” + “stale right now?” in a single row
  pieces.push(
    yesNoBadge(
      "HB_EXPECTED_NOW",
      meta.heartbeat_expected_now,
      "Derived from capability + heartbeat_expectation_mode (+ active hours if configured)."
    )
  );
  pieces.push(yesNoBadge("ACTIVE_HOURS_NOW", meta.active_hours_is_now, "Schedule: whether current time is within active hours."));

  const staleSeconds =
    typeof meta.heartbeat_stale_seconds === "number"
      ? meta.heartbeat_stale_seconds
      : meta.heartbeat_stale_seconds === null || meta.heartbeat_stale_seconds === undefined
        ? null
        : Number(meta.heartbeat_stale_seconds);
  const staleLevel = String(meta.heartbeat_stale_level || "UNKNOWN").trim().toUpperCase();
  const staleWarn = meta.heartbeat_stale_warn_seconds;
  const staleFail = meta.heartbeat_stale_fail_seconds;

  let staleCls = "warn";
  if (staleLevel === "FAIL") staleCls = "fail";
  else if (staleLevel === "WARN") staleCls = "warn";
  else if (staleLevel === "OK") staleCls = "ok";
  else if (staleLevel === "NOT_EXPECTED") staleCls = "idle";
  else staleCls = "warn";

  const staleLabelValue =
    typeof staleSeconds === "number" && Number.isFinite(staleSeconds) ? `${Math.max(0, Math.floor(staleSeconds))}s` : "unknown";
  const staleHint =
    typeof staleSeconds === "number" && Number.isFinite(staleSeconds)
      ? ` (${fmtSecondsShort(staleSeconds)})`
      : "";
  const staleTitle = `heartbeat_stale_seconds=${staleLabelValue}${staleHint}${staleWarn ? ` warn>=${staleWarn}s` : ""}${staleFail ? ` fail>=${staleFail}s` : ""} level=${staleLevel}`;
  pieces.push(`<span class="badge ${staleCls}" title="${escapeHtml(staleTitle)}">HB_STALE=${escapeHtml(staleLabelValue)}</span>`);

  return pieces.join("");
}

function renderNorthStar() {
  const payload = state.northStar || {};
  const summary = payload.summary || {};
  const scores = summary.scores || {};
  const status = summary.status || "UNKNOWN";
  const evalData = unwrap(payload.assessment_eval || {});

  state.northStarCatalogIndex = buildNorthStarCatalogIndex(payload);
  state.northStarFindingsJoinStats = null;

  setBadge($("#north-star-status"), status);
  const summaryEl = $("#north-star-summary");
  if (summaryEl) {
    summaryEl.textContent = `generated_at=${summary.generated_at || ""} gaps=${summary.gap_count || 0} lenses=${summary.lens_count || 0}`;
  }
  const coverageEl = $("#north-star-coverage");
  if (coverageEl) coverageEl.textContent = `coverage=${formatNumber(scores.coverage)}`;
  const maturityEl = $("#north-star-maturity");
  if (maturityEl) maturityEl.textContent = `maturity_avg=${formatNumber(scores.maturity_avg)}`;

  const runnerBadgesEl = $("#north-star-runner-badges");
  if (runnerBadgesEl) {
    runnerBadgesEl.innerHTML = renderNorthStarRunnerBadges(payload.runner_meta || {});
  }

  const evalLenses = evalData && typeof evalData === "object" ? evalData.lenses : null;
  const evalLensMap = evalLenses && typeof evalLenses === "object" ? evalLenses : {};

  const evalLensNames = Object.keys(evalLensMap).sort((a, b) => a.localeCompare(b));
  const lensItems = evalLensNames.length
    ? evalLensNames.map((name) => {
        const lens = evalLensMap?.[name] || {};
        const requirements = lens?.requirements;
        let reqTotal = 0;
        let reqOk = 0;

        if (Array.isArray(requirements)) {
          reqTotal = requirements.length;
          reqOk = requirements.filter((req) => String(req?.status || "").toUpperCase() === "OK" || req === true).length;
        } else if (requirements && typeof requirements === "object") {
          const entries = Object.entries(requirements);
          reqTotal = entries.length;
          reqOk = entries.filter(([_, val]) => Boolean(val) || String(val || "").toUpperCase() === "OK").length;
        }

        return {
          name,
          status: String(lens?.status || ""),
          score: formatNumber(lens?.score),
          coverage: formatNumber(lens?.coverage),
          requirements: reqTotal ? `${reqOk}/${reqTotal}` : "-",
        };
      })
    : Object.entries(payload.lenses || {}).map(([name, lens]) => {
        const reqTotal = lens?.requirements_total || 0;
        const reqOk = lens?.requirements_ok || 0;
        return {
          name,
          status: String(lens?.status || ""),
          score: formatNumber(lens?.score),
          coverage: formatNumber(lens?.coverage),
          requirements: reqTotal ? `${reqOk}/${reqTotal}` : "-",
        };
      });
  renderStaticTable("#north-star-lenses-table", lensItems, [
    { key: "name", label: t("table.lens") },
    { key: "status", label: t("table.status") },
    { key: "score", label: t("table.score") },
    { key: "coverage", label: t("table.coverage") },
    { key: "requirements", label: t("table.requirements") },
  ]);

  const gapBreakdownEl = $("#north-star-gap-breakdown");
  const gapCountEl = $("#north-star-gap-count");
  if (gapBreakdownEl) {
    gapBreakdownEl.textContent = `severity=${JSON.stringify(summary.gap_by_severity || {})} risk=${JSON.stringify(summary.gap_by_risk_class || {})} effort=${JSON.stringify(summary.gap_by_effort || {})}`;
  }
  if (gapCountEl) {
    gapCountEl.textContent = `total_gaps=${summary.gap_count || 0}`;
  }

  const gapItems = Array.isArray(payload.top_gaps) ? payload.top_gaps : [];
  renderStaticTable("#north-star-gap-table", gapItems, [
    { key: "id", label: t("table.gap_id") },
    { key: "control_id", label: t("table.control") },
    { key: "severity", label: t("table.severity") },
    { key: "risk_class", label: t("table.risk") },
    { key: "effort", label: t("table.effort") },
    { key: "status", label: t("table.status") },
  ]);

  renderNorthStarLensDetails(payload, evalData);

  // Lens Findings (lens-by-lens explorer)
  const findingsByLens = {};
  evalLensNames.forEach((name) => {
    const lens = evalLensMap?.[name];
    const findings = lens?.findings;
    if (findings && typeof findings === "object" && Array.isArray(findings.items)) {
      findingsByLens[name] = findings;
    }
  });
  // Add an aggregated view across all lenses.
  const allItems = [];
  Object.keys(findingsByLens)
    .sort((a, b) => a.localeCompare(b))
    .forEach((lensName) => {
      const items = Array.isArray(findingsByLens[lensName]?.items) ? findingsByLens[lensName].items : [];
      items.forEach((item) => {
        if (!item || typeof item !== "object") return;
        allItems.push({ ...item, lens: lensName });
      });
    });

  const summaryCounts = (items) => {
    const norm = (x) => String(x || "").toUpperCase();
    return {
      total: items.length,
      triggered: items.filter((x) => norm(x?.match_status) === "TRIGGERED").length,
      not_triggered: items.filter((x) => norm(x?.match_status) === "NOT_TRIGGERED").length,
      unknown: items.filter((x) => norm(x?.match_status) === "UNKNOWN").length,
    };
  };

  findingsByLens[NORTH_STAR_FINDINGS_ALL_LENSES_KEY] = {
    version: "v1",
    summary: summaryCounts(allItems),
    items: allItems,
  };

  state.northStarFindingsByLens = findingsByLens;

  const findingsLensSelect = $("#ns-findings-lens");
  const availableFindingsLenses = Object.keys(findingsByLens)
    .filter((name) => name !== NORTH_STAR_FINDINGS_ALL_LENSES_KEY)
    .sort((a, b) => a.localeCompare(b));
  if (findingsLensSelect) {
    const options = [
      { key: NORTH_STAR_FINDINGS_ALL_LENSES_KEY, label: t("north_star.all_lenses") },
      ...availableFindingsLenses.map((name) => ({ key: name, label: name })),
    ];
    findingsLensSelect.innerHTML = options.length
      ? options.map((opt) => `<option value="${escapeHtml(opt.key)}">${escapeHtml(opt.label)}</option>`).join("")
      : `<option value="">${escapeHtml(t("north_star.no_findings"))}</option>`;

    const preferredKey = options.some((opt) => opt.key === state.northStarFindingsLensName)
      ? state.northStarFindingsLensName
      : options.some((opt) => opt.key === NORTH_STAR_FINDINGS_ALL_LENSES_KEY)
        ? NORTH_STAR_FINDINGS_ALL_LENSES_KEY
        : (availableFindingsLenses.includes("trend_best_practice") ? "trend_best_practice" : (availableFindingsLenses[0] || ""));

    findingsLensSelect.value = preferredKey;
    const preferredLabel = preferredKey === NORTH_STAR_FINDINGS_ALL_LENSES_KEY ? t("north_star.all_lenses") : preferredKey;
    const selectedFindings = preferredKey ? findingsByLens[preferredKey] : null;
    setupNorthStarFindingsUi(selectedFindings, { lensKey: preferredKey, lensLabel: preferredLabel });
  }

  renderJson($("#north-star-eval-json"), payload.assessment_eval || {});
  renderJson($("#north-star-trend-catalog-json"), payload.trend_catalog || {});
  renderJson($("#north-star-bp-catalog-json"), payload.bp_catalog || {});
  renderJson($("#north-star-catalog-json"), payload.north_star_catalog || {});
  renderJson($("#north-star-gap-json"), payload.gap_register || {});
  renderJson($("#north-star-scorecard-json"), payload.scorecard || {});
}

function normalizeTagList(value) {
  if (!Array.isArray(value)) return [];
  return value.map((tag) => String(tag || "").trim()).filter((tag) => Boolean(tag));
}

function extractTopicTag(tags) {
  for (const tag of tags) {
    if (tag.toLowerCase().startsWith("topic:")) {
      return tag.slice(tag.indexOf(":") + 1);
    }
  }
  return "";
}

function extractDomainTags(tags) {
  const domains = [];
  for (const tag of tags) {
    const norm = tag.toLowerCase();
    if (norm === "core") domains.push("core");
    if (norm.startsWith("domain_")) domains.push(tag);
  }
  return domains;
}

function rankDomain(domains) {
  const rank = {
    core: 0,
    domain_ai: 1,
    domain_management: 2,
    domain_software: 3,
  };
  if (!domains.length) return 9;
  let best = 9;
  for (const domain of domains) {
    const key = String(domain || "").toLowerCase();
    best = Math.min(best, rank[key] ?? 8);
  }
  return best;
}

function renderHtmlTable(items, columns) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<div class="empty">${escapeHtml(t("empty.no_items"))}</div>`;
  }
  const headers = columns.map((col) => `<th>${escapeHtml(col.label)}</th>`).join("");
  const rows = items
    .map((item) => {
      const tds = columns
        .map((col) => {
          const raw = col.render ? col.render(item) : item?.[col.key] ?? "";
          return `<td>${escapeHtml(raw)}</td>`;
        })
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderPrettyJson(obj, limit = 4000) {
  let text = "{}";
  try {
    text = JSON.stringify(obj || {}, null, 2);
  } catch {
    text = String(obj || "");
  }
  if (text.length > limit) text = text.slice(0, limit) + "\n...";
  return `<pre>${escapeHtml(text)}</pre>`;
}

function renderNorthStarLensDetails(payload, evalData) {
  const container = $("#north-star-lens-details");
  if (!container) return;

  const evalObj = evalData && typeof evalData === "object" ? evalData : unwrap(payload.assessment_eval || {});
  const lensMap = evalObj && typeof evalObj === "object" ? evalObj.lenses : null;
  const lenses = lensMap && typeof lensMap === "object" ? lensMap : {};

  const trendCatalog = unwrap(payload.trend_catalog || {});
  const bpCatalog = unwrap(payload.bp_catalog || {});
  const trendItems = Array.isArray(trendCatalog?.items) ? trendCatalog.items : [];
  const bpItems = Array.isArray(bpCatalog?.items) ? bpCatalog.items : [];

  const lensNames = Object.keys(lenses).sort((a, b) => a.localeCompare(b));
  if (!lensNames.length) {
    container.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_lens_details"))}</div>`;
    return;
  }

  const sections = lensNames.map((name) => {
    const lens = lenses[name] || {};
    const status = String(lens.status || "UNKNOWN").toUpperCase();
    const score = formatNumber(lens.score);
    const coverage = formatNumber(lens.coverage);
    const classification = String(lens.classification || "");
    const reasons = Array.isArray(lens.reasons) ? lens.reasons.map((r) => String(r || "")) : [];
    const requirements = lens.requirements;
    const subscores = lens.subscores && typeof lens.subscores === "object" ? lens.subscores : null;

    let body = "";
    const metaRows = [
      `status=${status}`,
      `score=${score}`,
      `coverage=${coverage}`,
      classification ? `classification=${classification}` : "",
      reasons.length ? `reasons=${reasons.join(", ")}` : "",
    ].filter((x) => Boolean(x));
    body += `<div class="subtle">${escapeHtml(metaRows.join(" | "))}</div>`;

    if (name === "trend_best_practice") {
      const trendRef = String(evalObj?.trend_catalog_ref || "");
      const bpRef = String(evalObj?.bp_catalog_ref || "");
      body += `<div class="subtle">trend_catalog_ref=${escapeHtml(trendRef || "-")} | bp_catalog_ref=${escapeHtml(bpRef || "-")}</div>`;

      const findings = lens?.findings && typeof lens.findings === "object" ? lens.findings : null;
      const findingsItems = Array.isArray(findings?.items) ? findings.items : null;
        if (findingsItems) {
          const summary = findings?.summary && typeof findings.summary === "object" ? findings.summary : {};
          body += `<div class="subtle">findings_total=${escapeHtml(summary.total ?? "-")} triggered=${escapeHtml(summary.triggered ?? "-")} not_triggered=${escapeHtml(summary.not_triggered ?? "-")} unknown=${escapeHtml(summary.unknown ?? "-")}</div>`;
          body += `<div class="subtle">${escapeHtml(t("north_star.detail.lens_findings_hint"))}</div>`;
        }

      const toRows = (items) => {
        const rows = [];
        for (const item of Array.isArray(items) ? items : []) {
          if (!item || typeof item !== "object") continue;
          const tags = normalizeTagList(item.tags);
          const topic = extractTopicTag(tags);
          const domains = extractDomainTags(tags);
          rows.push({
            domain_rank: rankDomain(domains),
            domains: domains.length ? domains.join(", ") : "-",
            topic: topic || "-",
            id: String(item.id || ""),
            title: String(item.title || ""),
            source: String(item.source || ""),
            tags: tags.join(", "),
          });
        }
        return stableSort(rows, (a, b) => {
          const dr = (a.domain_rank || 9) - (b.domain_rank || 9);
          if (dr !== 0) return dr;
          const t = String(a.topic || "").localeCompare(String(b.topic || ""));
          if (t !== 0) return t;
          return String(a.id || "").localeCompare(String(b.id || ""));
        });
      };

      const trendRows = toRows(trendItems);
      const bpRows = toRows(bpItems);
      const cols = [
        { key: "domains", label: t("north_star.table.domain") },
        { key: "topic", label: t("north_star.table.topic") },
        { key: "title", label: t("north_star.table.title") },
        { key: "id", label: t("north_star.table.id") },
        { key: "source", label: t("table.source") },
      ];

      body += `<details open><summary class="subtle">${escapeHtml(t("north_star.detail.trend_catalog"))} (${trendRows.length})</summary>${renderHtmlTable(trendRows, cols)}</details>`;
      body += `<details><summary class="subtle">${escapeHtml(t("north_star.detail.bp_catalog"))} (${bpRows.length})</summary>${renderHtmlTable(bpRows, cols)}</details>`;
      body += `<details><summary class="subtle">${escapeHtml(t("north_star.detail.lens_json"))}</summary>${renderPrettyJson(lens)}</details>`;
      return `<details><summary>${escapeHtml(name)} | ${escapeHtml(status)} | score=${escapeHtml(score)}</summary>${body}</details>`;
    }

    if (requirements && typeof requirements === "object") {
      if (Array.isArray(requirements)) {
        const reqRows = requirements
          .filter((req) => req && typeof req === "object")
          .map((req) => ({
            id: String(req.id || req.name || ""),
            status: String(req.status || ""),
            note: String(req.note || req.message || ""),
          }));
        if (reqRows.length) {
          body += `<details open><summary class="subtle">${escapeHtml(t("north_star.detail.requirements"))} (${reqRows.length})</summary>${renderHtmlTable(reqRows, [
            { key: "id", label: t("table.id") },
            { key: "status", label: t("table.status") },
            { key: "note", label: t("table.note") },
          ])}</details>`;
        }
      } else {
        const entries = Object.entries(requirements)
          .map(([k, v]) => ({ requirement: String(k || ""), ok: Boolean(v) ? "OK" : "FAIL" }))
          .sort((a, b) => a.requirement.localeCompare(b.requirement));
        if (entries.length) {
          body += `<details open><summary class="subtle">${escapeHtml(t("north_star.detail.requirements"))} (${entries.length})</summary>${renderHtmlTable(entries, [
            { key: "requirement", label: t("table.requirement") },
            { key: "ok", label: t("table.ok") },
          ])}</details>`;
        }
      }
    }

    if (subscores) {
      const entries = Object.entries(subscores)
        .map(([k, v]) => ({ key: String(k || ""), score: formatNumber(v) }))
        .sort((a, b) => a.key.localeCompare(b.key));
      if (entries.length) {
        body += `<details><summary class="subtle">${escapeHtml(t("north_star.detail.subscores"))} (${entries.length})</summary>${renderHtmlTable(entries, [
          { key: "key", label: t("table.key") },
          { key: "score", label: t("table.score") },
        ])}</details>`;
      }
    }

    if (reasons.length) {
      const reasonList = reasons
        .map((r) => `<li>${escapeHtml(r)}</li>`)
        .join("");
      body += `<details open><summary class="subtle">${escapeHtml(t("north_star.table.reasons"))} (${reasons.length})</summary><ul class="subtle">${reasonList}</ul></details>`;
    }

    body += `<details><summary class="subtle">${escapeHtml(t("north_star.detail.lens_json"))}</summary>${renderPrettyJson(lens)}</details>`;
    return `<details><summary>${escapeHtml(name)} | ${escapeHtml(status)} | score=${escapeHtml(score)}</summary>${body}</details>`;
  });

  container.innerHTML = sections.join("");
}

function filterBySearch(items, text, keys) {
  if (!text) return items;
  const q = text.toUpperCase();
  return items.filter((item) => {
    return keys.some((key) => String(item?.[key] ?? "").toUpperCase().includes(q));
  });
}

function renderTable(containerId, items, columns, sortKey, sortDir, onSort, opts = null) {
  const container = $(containerId);
  if (!container) return;
  if (!Array.isArray(items) || items.length === 0) {
    container.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_items"))}</div>`;
    return;
  }

  const sorted = stableSort(items, compareBy(sortKey, sortDir));
  const headers = columns
    .map((col) => {
      const indicator = col.key === sortKey ? (sortDir === "asc" ? " \u2191" : " \u2193") : "";
      return `<th><button data-sort="${col.key}">${escapeHtml(col.label)}${indicator}</button></th>`;
    })
    .join("");

  const options = opts && typeof opts === "object" ? opts : {};
  const onRowClick = typeof options.onRowClick === "function" ? options.onRowClick : null;
  const rowClassName = typeof options.rowClassName === "function" ? options.rowClassName : null;
  const expandedRow = typeof options.expandedRow === "function" ? options.expandedRow : null;
  const isExpanded = typeof options.isExpanded === "function" ? options.isExpanded : null;

  const rows = sorted
    .slice(0, 120)
    .map((item, idx) => {
      const tds = columns
        .map((col) => {
          const raw = col.render ? col.render(item) : item?.[col.key] ?? "";
          const val = raw === undefined || raw === null ? "" : String(raw);
          if (col.html) return `<td>${val}</td>`;
          return `<td>${escapeHtml(val)}</td>`;
        })
        .join("");
      const cls = rowClassName ? String(rowClassName(item) || "").trim() : "";
      const clsAttr = cls ? ` class="${cls}"` : "";
      const clickAttr = onRowClick ? ` data-row-index="${idx}"` : "";
      let html = `<tr${clsAttr}${clickAttr}>${tds}</tr>`;
      if (expandedRow && isExpanded && isExpanded(item)) {
        const inner = String(expandedRow(item) || "");
        html += `<tr class="expanded-row"><td colspan="${columns.length}">${inner}</td></tr>`;
      }
      return html;
    })
    .join("");

  container.innerHTML = `
    <table>
      <thead><tr>${headers}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  container.querySelectorAll("[data-sort]").forEach((btn) => {
    btn.addEventListener("click", () => onSort(btn.dataset.sort));
  });

  if (onRowClick) {
    container.querySelectorAll("tbody tr[data-row-index]").forEach((row) => {
      row.addEventListener("click", () => {
        const idx = Number(row.dataset.rowIndex || "0");
        const item = sorted[idx];
        onRowClick(item);
      });
    });
  }
}

function renderStaticTable(containerId, items, columns) {
  const container = $(containerId);
  if (!container) return;
  if (!Array.isArray(items) || items.length === 0) {
    container.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_items"))}</div>`;
    return;
  }
  const headers = columns.map((col) => `<th>${escapeHtml(col.label)}</th>`).join("");
  const rows = items
    .map((item) => {
      const tds = columns
        .map((col) => {
          const raw = col.render ? col.render(item) : item?.[col.key] ?? "";
          return `<td>${escapeHtml(raw)}</td>`;
        })
        .join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  container.innerHTML = `
    <table>
      <thead><tr>${headers}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderIntakeTable(items) {
  const search = $("#intake-search").value.trim();
  const bucket = state.filters.intake.bucket || [];
  const status = state.filters.intake.status || [];
  const source = state.filters.intake.source || [];
  const ext = state.filters.intake.extension || [];
  const hideDone = $("#filter-hide-done") ? $("#filter-hide-done").checked : false;

  renderIntakeDecisionBanner();

  let filtered = Array.isArray(items) ? items : [];
  if (bucket.length) {
    const bucketKeys = new Set(bucket.map((val) => normalizeKey(val)));
    filtered = filtered.filter((item) => bucketKeys.has(normalizeKey(item.bucket)));
  }
  if (status.length) {
    const statusKeys = new Set(status.map((val) => normalizeKey(val)));
    filtered = filtered.filter((item) => statusKeys.has(normalizeKey(item.status)));
  }
  if (source.length) {
    const sourceKeys = new Set(source.map((val) => normalizeKey(val)));
    filtered = filtered.filter((item) => sourceKeys.has(normalizeKey(item.source_type)));
  }
  if (ext.length) {
    const extKeys = new Set(ext.map((val) => normalizeKey(val)));
    filtered = filtered.filter((item) => {
      const val = item.suggested_extension || [];
      if (Array.isArray(val)) {
        return val.some((entry) => extKeys.has(normalizeKey(entry)));
      }
      return extKeys.has(normalizeKey(val));
    });
  }
  if (hideDone) {
    const doneKeys = new Set(["DONE", "CLOSED", "RESOLVED"]);
    filtered = filtered.filter((item) => !doneKeys.has(normalizeKey(item.status)));
  }
  filtered = filterBySearch(filtered, search, ["title", "bucket", "status", "priority", "severity", "source_type"]);

  $("#intake-count").textContent = t("meta.showing_items", { count: String(filtered.length) });

  const decisionCell = (intakeId, field, fallback = "-") => {
    const d = getDecisionForIntake(intakeId);
    const v = String(d?.[field] || "").trim();
    if (!v) return `<span class="subtle">${escapeHtml(fallback)}</span>`;
    if (field === "recommended_action") {
      return `<span class="${decisionBadgeClass(v)}">${escapeHtml(v)}</span>`;
    }
    if (field === "evidence_ready") {
      const cls = v.toUpperCase() === "YES" ? "badge ok" : "badge warn";
      return `<span class="${cls}">${escapeHtml(v)}</span>`;
    }
    if (field === "selected_option") {
      return `<span class="badge ok">${escapeHtml(v)}</span>`;
    }
    return `<span class="badge">${escapeHtml(v)}</span>`;
  };

  const columns = [
    { key: "bucket", label: t("table.bucket") },
    { key: "status", label: t("table.status") },
    { key: "priority", label: t("table.priority") },
    { key: "severity", label: t("table.severity") },
    { key: "title", label: t("table.title") },
    { key: "recommended_action", label: t("table.recommended_action"), html: true, render: (item) => decisionCell(item?.intake_id, "recommended_action") },
    { key: "confidence", label: t("table.confidence"), html: true, render: (item) => decisionCell(item?.intake_id, "confidence") },
    { key: "execution_mode", label: t("table.execution_mode"), html: true, render: (item) => decisionCell(item?.intake_id, "execution_mode") },
    { key: "evidence_ready", label: t("table.evidence_ready"), html: true, render: (item) => decisionCell(item?.intake_id, "evidence_ready") },
    { key: "selected_option", label: t("table.decision"), html: true, render: (item) => decisionCell(item?.intake_id, "selected_option") },
    { key: "created_at", label: t("table.created"), render: (item) => {
        const keys = ["created_at", "created", "created_ts", "ts", "timestamp", "ingested_at"];
        return formatTimestamp(pickTimestamp(item, keys)) || "-";
      } },
    { key: "updated_at", label: t("table.updated"), render: (item) => {
        const keys = ["updated_at", "updated", "modified_at", "modified", "last_updated", "last_update"];
        return formatTimestamp(pickTimestamp(item, keys)) || "-";
      } },
    { key: "suggested_extension", label: t("table.extension"), render: (item) => {
        const v = item.suggested_extension;
        return Array.isArray(v) ? v.join(",") : (v || "");
      } },
    { key: "claim_status", label: t("table.claim"), render: (item) => {
        const status = String(item?.claim_status || "").toUpperCase();
        if (status !== "CLAIMED") return "";
        const owner = String(item?.claim?.owner_tag || item?.claim?.owner_session || "").trim();
        return owner ? `CLAIMED (${owner})` : "CLAIMED";
      } },
  ];

  renderTable(
    "#intake-table",
    filtered,
    columns,
    state.sort.intake.key,
    state.sort.intake.dir,
    (key) => {
      const dir = state.sort.intake.key === key && state.sort.intake.dir === "asc" ? "desc" : "asc";
      state.sort.intake = { key, dir };
      renderIntakeTable(filtered);
    },
    {
      rowClassName: (item) => {
        const classes = ["clickable"];
        const status = String(item?.claim_status || "").toUpperCase();
        const owner = String(item?.claim?.owner_tag || item?.claim?.owner_session || "").trim();
        const myTag = String(state.claimOwnerTag || "").trim();
        if (status === "CLAIMED" && owner && myTag && owner !== myTag) classes.push("blocked");
        if (state.intakeSelectedId && item?.intake_id === state.intakeSelectedId) classes.push("selected");
        if (state.intakeExpandedId && item?.intake_id === state.intakeExpandedId) classes.push("selected");
        return classes.join(" ");
      },
      isExpanded: (item) => {
        return Boolean(state.intakeExpandedId && item?.intake_id === state.intakeExpandedId);
      },
      expandedRow: (item) => {
        return renderIntakeInlineDecisionDetailHtml(item);
      },
      onRowClick: (item) => {
        if (!item) return;
        const id = item.intake_id || null;
        state.intakeSelectedId = id;
        state.intakeSelected = item;
        if (state.intakeExpandedId && id && state.intakeExpandedId === id) state.intakeExpandedId = null;
        else state.intakeExpandedId = id;
        if (id && !state.intakeInlineTab[id]) state.intakeInlineTab[id] = "decision";
        state.intakeEvidencePath = null;
        state.intakeEvidencePreview = null;
        state.intakeLinkedNotes = null;
        state.intakeLinkedNotesLoading = false;
        state.intakeLinkedNotesError = null;
        renderIntakeDetail(item);
        renderIntakeTable((unwrap(state.intake || {}).items || []));
        refreshIntakeLinkedNotes(item);
        renderIntakeClaimControls(item);
      },
    }
  );

  // Inline handlers (decision tab)
  $$("[data-intake-inline-tab]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const intakeId = decodeTag(btn.dataset.intakeInlineTab || "");
      const tab = String(btn.dataset.tab || "").trim();
      if (!intakeId || !tab) return;
      state.intakeInlineTab[intakeId] = tab;
      renderIntakeTable((unwrap(state.intake || {}).items || []));
    });
  });

  $$("[data-decision-save]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const intakeId = decodeTag(btn.dataset.decisionSave || "");
      if (!intakeId) return;
      const name = `decision-opt-${encodeTag(intakeId)}`;
      const selected = document.querySelector(`input[name=\"${CSS.escape(name)}\"]:checked`);
      const option = selected ? String(selected.value || "").trim() : "";
      const noteEl = document.querySelector(`[data-decision-note=\"${CSS.escape(encodeTag(intakeId))}\"]`);
      const note = noteEl ? String(noteEl.value || "") : "";
      if (!option) {
        showToast(t("toast.action_failed", { error: "OPTION_REQUIRED" }), "warn");
        return;
      }
      try {
        await saveCockpitDecisionMark(intakeId, option, note);
        if (!state.cockpitDecisionArtifacts.userMarksById || typeof state.cockpitDecisionArtifacts.userMarksById !== "object") {
          state.cockpitDecisionArtifacts.userMarksById = {};
        }
        state.cockpitDecisionArtifacts.userMarksById[intakeId] = {
          selected_option: option,
          note,
          at: new Date().toISOString(),
          user: "local",
        };
        showToast(t("toast.decision_saved"), "ok");
        renderIntakeTable((unwrap(state.intake || {}).items || []));
      } catch (err) {
        showToast(t("toast.decision_save_failed", { error: formatError(err) }), "fail");
      }
    });
  });

  $$("[data-intake-evidence]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const path = decodeTag(btn.dataset.intakeEvidence || "");
      if (!path) return;
      previewIntakeEvidence(path);
    });
  });
}

function renderInboxTable(items) {
  const search = $("#inbox-search") ? $("#inbox-search").value.trim() : "";
  const bucket = $("#inbox-filter-bucket") ? $("#inbox-filter-bucket").value.trim() : "";
  const status = $("#inbox-filter-status") ? $("#inbox-filter-status").value.trim() : "";
  const triage = $("#inbox-filter-triage") ? $("#inbox-filter-triage").value.trim() : "";

  let filtered = Array.isArray(items) ? items : [];

  filtered = filtered.map((item) => {
    const effectiveBucket = String(item?.intake?.bucket || item?.suggested_route?.bucket || "").trim();
    const intakeStatus = String(item?.intake?.status || "").trim();
    const triageState = String(item?.triage?.state || "").trim();
    const milestone = String(item?.triage?.classification?.milestone || "").trim();
    const ownerProject = String(item?.triage?.classification?.owner_project || "").trim();
    return {
      ...item,
      effective_bucket: effectiveBucket,
      intake_status: intakeStatus,
      triage_state: triageState,
      milestone,
      owner_project: ownerProject,
    };
  });

  if (bucket) {
    const key = normalizeKey(bucket);
    filtered = filtered.filter((item) => normalizeKey(item.effective_bucket) === key);
  }
  if (status) {
    const key = normalizeKey(status);
    filtered = filtered.filter((item) => normalizeKey(item.intake_status) === key);
  }
  if (triage) {
    const key = normalizeKey(triage);
    filtered = filtered.filter((item) => normalizeKey(item.triage_state) === key);
  }

  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter((item) => {
      const parts = [
        item?.request_id,
        item?.kind,
        item?.domain,
        item?.impact_scope,
        item?.requires_core_change,
        item?.effective_bucket,
        item?.intake_status,
        item?.triage_state,
        item?.milestone,
        item?.owner_project,
        item?.intake?.title,
        item?.intake?.intake_id,
        item?.suggested_route?.reason,
        Array.isArray(item?.suggested_route?.tags) ? item.suggested_route.tags.join(" ") : item?.suggested_route?.tags,
        item?.text_preview,
      ]
        .map((p) => String(p || "").toLowerCase())
        .join(" | ");
      return parts.includes(q);
    });
  }

  const countEl = $("#inbox-count");
  if (countEl) countEl.textContent = t("meta.showing_items", { count: String(filtered.length) });

  const columns = [
    { key: "created_at", label: t("table.created"), render: (item) => formatTimestamp(item.created_at) || item.created_at || "-" },
    { key: "effective_bucket", label: t("table.bucket"), render: (item) => item.effective_bucket || "" },
    { key: "intake_status", label: t("table.intake"), render: (item) => item.intake_status || "" },
    { key: "triage_state", label: t("table.triage"), render: (item) => {
        const s = String(item.triage_state || "").trim();
        const milestone = String(item.milestone || "").trim();
        const extra = milestone ? ` · ${milestone}` : "";
        return `${s}${extra}`;
      } },
    { key: "request_id", label: t("table.request"), render: (item) => String(item.request_id || "") },
    { key: "kind", label: t("table.kind"), render: (item) => String(item.kind || "") },
    { key: "domain", label: t("table.domain"), render: (item) => String(item.domain || "") },
    { key: "impact_scope", label: t("table.scope"), render: (item) => String(item.impact_scope || "") },
    { key: "text_preview", label: t("table.preview"), render: (item) => {
        const raw = String(item.text_preview || "").trim();
        const short = raw.length > 140 ? raw.slice(0, 140) + "…" : raw;
        return short;
      } },
    { key: "_actions", label: t("table.evidence"), html: true, render: (item) => {
        const path = String(item.evidence_path || "").trim();
        if (!path) return "";
        return `<button class="btn small ghost" type="button" data-inbox-evidence="${encodeTag(path)}">${escapeHtml(t("actions.open"))}</button>`;
      } },
  ];

  renderTable("#inbox-table", filtered, columns, state.sort.inbox.key, state.sort.inbox.dir, (key) => {
    const dir = state.sort.inbox.key === key && state.sort.inbox.dir === "asc" ? "desc" : "asc";
    state.sort.inbox = { key, dir };
    renderInboxTable(filtered);
  });

  const tableEl = $("#inbox-table");
  if (tableEl) {
    tableEl.querySelectorAll("[data-inbox-evidence]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const path = decodeTag(btn.dataset.inboxEvidence || "");
        if (path) openEvidencePreview(path);
      });
    });
  }
}

function renderDecisionTable(items) {
  const search = $("#decision-search").value.trim();
  let filtered = filterBySearch(items, search, ["decision_kind", "status", "question", "title", "decision_id"]);

  const inboxGeneratedAt = pickTimestamp(unwrap(state.decisions || {}), ["generated_at", "ts", "timestamp"]);
  const intakeIndex = new Map();
  const intakeItems = unwrap(state.intake || {}).items;
  if (Array.isArray(intakeItems)) {
    intakeItems.forEach((item) => {
      const id = item?.intake_id;
      if (id) intakeIndex.set(id, item);
    });
  }

  const decisionCreatedKeys = ["created_at", "created", "created_ts", "ts", "timestamp"];
  const decisionUpdatedKeys = ["updated_at", "updated", "modified_at", "modified", "last_updated", "last_update"];
  const intakeCreatedKeys = ["created_at", "created", "created_ts", "ts", "timestamp", "ingested_at"];
  const intakeUpdatedKeys = ["updated_at", "updated", "modified_at", "modified", "last_updated", "last_update"];

  filtered = filtered.map((item) => {
    const source = intakeIndex.get(item?.source_intake_id) || null;
    const created =
      pickTimestamp(item, decisionCreatedKeys) || pickTimestamp(source, intakeCreatedKeys) || inboxGeneratedAt || "";
    const updated =
      pickTimestamp(item, decisionUpdatedKeys) || pickTimestamp(source, intakeUpdatedKeys) || inboxGeneratedAt || created;
    return { ...item, created_at: created, updated_at: updated };
  });

  const columns = [
    { key: "decision_kind", label: t("table.kind") },
    { key: "status", label: t("table.status") },
    { key: "question", label: t("table.question"), render: (item) => item.question || item.title || "" },
    { key: "decision_id", label: t("table.id") },
    { key: "created_at", label: t("table.created"), render: (item) => formatTimestamp(item.created_at) || "-" },
    { key: "updated_at", label: t("table.updated"), render: (item) => formatTimestamp(item.updated_at) || "-" },
  ];

  renderTable("#decision-table", filtered, columns, state.sort.decisions.key, state.sort.decisions.dir, (key) => {
    const dir = state.sort.decisions.key === key && state.sort.decisions.dir === "asc" ? "desc" : "asc";
    state.sort.decisions = { key, dir };
    renderDecisionTable(filtered);
  });
}

function renderJobsTable(items, targetId) {
  const columns = [
    { key: "kind", label: t("table.kind"), render: (job) => job.kind || job.job_type || "" },
    { key: "status", label: t("table.status") },
    { key: "job_id", label: t("table.job_id") },
    { key: "failure_class", label: t("table.failure"), render: (job) => job.failure_class || job.error_code || "" },
  ];

  renderTable(targetId, items, columns, state.sort.jobs.key, state.sort.jobs.dir, (key) => {
    const dir = state.sort.jobs.key === key && state.sort.jobs.dir === "asc" ? "desc" : "asc";
    state.sort.jobs = { key, dir };
    renderJobsTable(items, targetId);
  });
}

function renderLocks() {
  const data = state.locks || {};
  const summary = `state=${data.lock_state || ""} owner=${data.owner_tag || data.owner_session || ""} expires=${data.expires_at || ""}`;
  $("#lock-detail").textContent = summary;
  const leases = data.leases_summary || {};
  const leaseSummary = `leases=${leases.lease_count || 0} active=${leases.active_count || 0} owners=${(leases.owners_sample || []).join(",")}`;
  const leaseEl = $("#lock-leases");
  if (leaseEl) leaseEl.textContent = leaseSummary;
  const claims = data.claims_summary || {};
  const claimSummary = `claims=${claims.claim_count || 0} active=${claims.active_count || 0} owners=${(claims.owners_sample || []).join(",")}`;
  const claimEl = $("#lock-claims");
  if (claimEl) claimEl.textContent = claimSummary;

  const limitEl = $("#lock-claims-limit");
  if (limitEl) limitEl.value = String(state.lockClaimsLimit || 20);
  const groupBtn = $("#lock-claims-group-owner");
  if (groupBtn) {
    const stateLabel = state.lockClaimsGroupByOwner ? t("common.on") : t("common.off");
    groupBtn.textContent = t("locks.group_by_owner", { state: stateLabel });
  }
  updateAdminModeButtons();
  applyAdminModeToWriteControls();

  renderLockClaimsList(data.claims_active_sample || []);
  renderJson($("#lock-json"), data || {});
}

function renderLockClaimsList(claims) {
  const container = $("#lock-claims-list");
  const meta = $("#lock-claims-list-meta");
  if (!container) return;
  const items = Array.isArray(claims) ? claims : [];
  const activeTotal = Number(state.locks?.claims_summary?.active_count || items.length || 0);
  const limit = Number(state.lockClaimsLimit || 20);
  const showCount = Number.isFinite(limit) ? Math.max(1, Math.min(limit, 50)) : 20;
  const visible = items.slice(0, showCount);
  if (meta) {
    const sampleHint = activeTotal > items.length ? t("common.sample_parens") : "";
    meta.textContent = t("locks.claims_meta", {
      shown: String(visible.length),
      total: String(activeTotal),
      sample: sampleHint,
    });
  }
  if (!visible.length) {
    container.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_active_claims"))}</div>`;
    return;
  }

  const forceDisabled = !isAdminModeEnabled();

  const renderClaimsTable = (rowsItems) => {
    const rows = rowsItems.map((item) => {
      const intakeId = String(item?.work_item_id || "").trim();
      const owner = String(item?.owner_tag || item?.owner_session || "").trim();
      const expires = String(item?.expires_at || "").trim();
      const acquired = String(item?.acquired_at || "").trim();
      const expiresFmt = formatTimestamp(expires) || expires || "-";
      const acquiredFmt = formatTimestamp(acquired) || acquired || "-";
      const encoded = encodeTag(intakeId);
      return `
        <tr>
          <td>${escapeHtml(intakeId)}</td>
          <td>${escapeHtml(owner || "-")}</td>
          <td>${escapeHtml(expiresFmt)}</td>
          <td>${escapeHtml(acquiredFmt)}</td>
          <td>
            <button class="btn danger small" type="button" data-claim-force-release="${encoded}" ${forceDisabled ? "disabled" : ""}>${escapeHtml(t("intake.claim.btn_force_release"))}</button>
          </td>
        </tr>
      `;
    }).join("");

    return `
    <table>
      <thead>
        <tr>
          <th>${escapeHtml(t("table.intake_id"))}</th>
          <th>${escapeHtml(t("table.owner"))}</th>
          <th>${escapeHtml(t("table.expires"))}</th>
          <th>${escapeHtml(t("table.acquired"))}</th>
          <th>${escapeHtml(t("table.actions"))}</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  };

  const noteHtml = !state.adminModeEnabled
    ? `<div class="subtle">${escapeHtml(t("locks.force_release_disabled_hint"))}</div>`
    : "";
  if (state.lockClaimsGroupByOwner) {
    const unknownOwner = t("common.unknown");
    const groups = new Map();
    visible.forEach((item) => {
      const owner = String(item?.owner_tag || item?.owner_session || "").trim();
      const key = owner || unknownOwner;
      const list = groups.get(key) || [];
      list.push(item);
      groups.set(key, list);
    });
    const owners = Array.from(groups.keys()).sort((a, b) => {
      if (a === unknownOwner && b !== unknownOwner) return 1;
      if (b === unknownOwner && a !== unknownOwner) return -1;
      return a.localeCompare(b);
    });
    container.innerHTML = noteHtml + owners
      .map((owner) => {
        const rowsItems = groups.get(owner) || [];
        return `
          <details open>
            <summary class="subtle">${escapeHtml(owner)} (${rowsItems.length})</summary>
            <div class="table-wrap" style="margin-top: 8px;">${renderClaimsTable(rowsItems)}</div>
          </details>
        `;
      })
      .join("");
  } else {
    container.innerHTML = noteHtml + renderClaimsTable(visible);
  }

  container.querySelectorAll("[data-claim-force-release]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const intakeId = decodeTag(btn.dataset.claimForceRelease || "");
      if (!intakeId) return;
      await forceReleaseIntakeClaim(intakeId);
    });
  });
}

function renderRunCard() {
  const data = state.runCard || {};
  const exists = data.exists ? t("state.present") : t("state.missing");
  $("#run-card-summary").textContent = `run-card: ${exists} path=${data.path || ""}`;
  renderJson($("#run-card-json"), data || {});
  const editor = $("#run-card-editor");
  if (editor && data.data) {
    editor.value = JSON.stringify(data.data || {}, null, 2);
  }
}

function renderExtensionsList(items) {
  const list = $("#extensions-list");
  if (!list) return;
  if (!Array.isArray(items) || items.length === 0) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_extensions_found"))}</div>`;
    return;
  }
  const overrides = state.extensions?.overrides?.overrides || {};
  const rows = items
    .map((item) => {
      const extId = String(item.extension_id || "");
      const semver = String(item.semver || "");
      const extAttr = encodeTag(extId);
      const enabled = item.enabled === true;
      const override = overrides?.[extId]?.enabled;
      const effective = typeof override === "boolean" ? override : enabled;
      const badgeLabel = effective ? t("state.enabled") : t("state.disabled");
      const badge = effective
        ? `<span class="badge ok">${escapeHtml(badgeLabel)}</span>`
        : `<span class="badge warn">${escapeHtml(badgeLabel)}</span>`;
      const toggleLabel = effective ? t("actions.disable") : t("actions.enable");
      const toggleTarget = effective ? "false" : "true";
      return `
        <tr>
          <td>${escapeHtml(extId)}</td>
          <td>${escapeHtml(semver)}</td>
          <td>${badge}</td>
          <td>
            <button class="btn" data-ext-view="${extAttr}">${escapeHtml(t("actions.view"))}</button>
            <button class="btn warn" data-ext-toggle="${extAttr}" data-ext-enable="${toggleTarget}">${escapeHtml(toggleLabel)}</button>
          </td>
        </tr>
      `;
    })
    .join("");
  list.innerHTML = `
    <table>
      <thead><tr><th>${escapeHtml(t("table.id"))}</th><th>${escapeHtml(t("table.semver"))}</th><th>${escapeHtml(t("table.status"))}</th><th>${escapeHtml(t("table.actions"))}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  $$("[data-ext-view]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const extId = decodeTag(btn.dataset.extView || "");
      if (!extId) return;
      state.extensionDetail = await fetchJson(`${endpoints.extensions}?extension_id=${encodeURIComponent(extId)}`);
      renderExtensionDetail();
    });
  });
  $$("[data-ext-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const extId = decodeTag(btn.dataset.extToggle || "");
      const enable = btn.dataset.extEnable === "true";
      if (!extId) return;
      postAction("extension-toggle", endpoints.extensionToggle, { extension_id: extId, enabled: enable });
    });
  });
  applyAdminModeToWriteControls();
}

function renderExtensionDetail() {
  const meta = $("#extension-meta");
  const viewer = $("#extension-json");
  const detail = state.extensionDetail || {};
  if (meta) {
    const extId = detail.extension_id || "";
    const path = detail.manifest_path || "";
    meta.textContent = `extension_id=${extId} manifest=${path}`;
  }
  renderJson(viewer, detail.manifest || {});
}

function renderSettingsList(items) {
  const list = $("#overrides-list");
  if (!list) return;
  if (!Array.isArray(items) || items.length === 0) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_overrides_found"))}</div>`;
    return;
  }
  const rows = items
    .map((item) => {
      const name = String(item.name || "");
      const nameAttr = encodeTag(name);
      const mtime = item.mtime ? new Date(item.mtime * 1000).toISOString() : "";
      return `
        <tr>
          <td>${escapeHtml(name)}</td>
          <td>${escapeHtml(mtime)}</td>
          <td><button class="btn" data-setting-edit="${nameAttr}">${escapeHtml(t("actions.edit"))}</button></td>
        </tr>
      `;
    })
    .join("");
  list.innerHTML = `
    <table>
      <thead><tr><th>${escapeHtml(t("table.name"))}</th><th>${escapeHtml(t("table.updated"))}</th><th>${escapeHtml(t("table.action"))}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  $$("[data-setting-edit]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = decodeTag(btn.dataset.settingEdit || "");
      if (!name) return;
      state.overridesSelected = name;
      state.overridesDetail = await fetchJson(`${endpoints.overridesGet}?name=${encodeURIComponent(name)}`);
      renderSettingsEditor();
    });
  });
}

function renderSettingsEditor() {
  const meta = $("#settings-meta");
  const editor = $("#settings-editor");
  const detail = state.overridesDetail || {};
  if (meta) {
    meta.textContent = `name=${detail.name || ""} schema=${detail.schema_path || ""}`;
  }
  if (editor && detail.data) {
    editor.value = JSON.stringify(detail.data || {}, null, 2);
  }
}

function renderChatLog() {
  const list = $("#chat-log");
  if (!list) return;
  const items = Array.isArray(state.chat?.items) ? state.chat.items : [];
  if (!items.length) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_chat_messages"))}</div>`;
    return;
  }
  list.innerHTML = items
    .map((entry) => {
      const kind = String(entry.type || "NOTE");
      const kindClass = kind.toLowerCase();
      const ts = String(entry.ts || "");
      const op = String(entry.op || "");
      const status = String(entry.status || "");
      const text = String(entry.text || "");
      const args = entry.args ? JSON.stringify(entry.args) : "";
      const meta = `${kind} ${ts}`.trim();
      let body = text;
      if (!body && op) {
        body = `${op} ${args}`;
      }
      if (!body && status) {
        body = `status=${status}`;
      }
      return `
        <div class="chat-message ${kindClass}">
          <div class="chat-meta">${escapeHtml(meta)}</div>
          <div class="chat-body">${escapeHtml(body)}</div>
        </div>
      `;
    })
    .join("");
}

function renderNoteLinks() {
  const container = $("#note-links-list");
  if (!container) return;
  if (!state.noteLinks.length) {
    container.textContent = t("notes.links.none");
    return;
  }
  container.innerHTML = state.noteLinks
    .map((link, idx) => {
      const label = `${escapeHtml(link.kind)}:${escapeHtml(link.id_or_path)}`;
      return `<span class="note-tag">${label}</span><button class="btn ghost" data-link-remove="${idx}">${escapeHtml(t("notes.links.remove"))}</button>`;
    })
    .join(" ");
  $$('[data-link-remove]').forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.linkRemove || "-1");
      if (Number.isInteger(idx) && idx >= 0) {
        state.noteLinks.splice(idx, 1);
        renderNoteLinks();
      }
    });
  });
}

function renderNoteDetail(notePayload) {
  const metaEl = $("#note-view-meta");
  const bodyEl = $("#note-view-body");
  if (!notePayload || !notePayload.data) {
    if (metaEl) metaEl.textContent = t("notes.no_note_selected");
    if (bodyEl) bodyEl.textContent = "";
    return;
  }
  const note = notePayload.data || {};
  const tags = Array.isArray(note.tags) ? note.tags.join(", ") : "";
  const links = Array.isArray(note.links) ? note.links.length : 0;
  if (metaEl) {
    metaEl.textContent = `note_id=${note.note_id || ""} updated_at=${note.updated_at || ""} tags=${tags} links=${links}`;
  }
  if (bodyEl) {
    bodyEl.textContent = note.body || "";
  }
}

function normalizeNote(item) {
  const note = { ...(item || {}) };
  if (!note.body_excerpt && note.body) {
    const raw = String(note.body || "");
    note.body_excerpt = raw.length > 160 ? raw.slice(0, 160) + "..." : raw;
  }
  if (!note.updated_at && note.created_at) {
    note.updated_at = note.created_at;
  }
  return note;
}

function renderNotesList(items) {
  const list = $("#notes-list");
  if (!list) return;
  const search = ($("#notes-search").value || "").trim().toLowerCase();
  const tagFilter = ($("#notes-tag-filter").value || "").trim().toLowerCase();
  let filtered = Array.isArray(items) ? items.map(normalizeNote) : [];
  if (search) {
    filtered = filtered.filter((item) => {
      const title = String(item.title || "").toLowerCase();
      const body = String(item.body_excerpt || "").toLowerCase();
      const tags = Array.isArray(item.tags) ? item.tags.join(" ").toLowerCase() : "";
      const links = Array.isArray(item.links) ? item.links.map((l) => `${l.kind}:${l.id_or_path}`).join(" ").toLowerCase() : "";
      return title.includes(search) || body.includes(search) || tags.includes(search) || links.includes(search);
    });
  }
  if (tagFilter) {
    filtered = filtered.filter((item) => {
      const tags = Array.isArray(item.tags) ? item.tags.map((t) => String(t).toLowerCase()) : [];
      return tags.some((t) => t.includes(tagFilter));
    });
  }
  filtered = stableSort(filtered, compareBy(state.sort.notes.key, state.sort.notes.dir));
  $("#notes-count").textContent = t("meta.showing_notes", { count: String(filtered.length) });
  if (!filtered.length) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_notes"))}</div>`;
    return;
  }
  list.innerHTML = filtered
    .map((item) => {
      const noteIdRaw = String(item.note_id || "");
      const noteIdAttr = encodeTag(noteIdRaw);
      const title = escapeHtml(item.title || t("notes.untitled"));
      const updatedRaw = String(item.updated_at || "");
      const metaText = t("notes.item_meta", { updated: updatedRaw, id: noteIdRaw });
      const tags = Array.isArray(item.tags) ? item.tags.map((t) => `<span class="note-tag">${escapeHtml(t)}</span>`).join("") : "";
      const excerpt = escapeHtml(item.body_excerpt || "");
      return `
        <div class="note-item">
          <div class="note-title">${title}</div>
          <div class="note-meta">${escapeHtml(metaText)}</div>
          <div class="note-tags">${tags}</div>
          <div class="subtle">${excerpt}</div>
          <div class="note-actions">
            <button class="btn" data-note-view="${noteIdAttr}">${escapeHtml(t("actions.view"))}</button>
          </div>
        </div>
      `;
    })
    .join("");
  $$("[data-note-view]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (state.actionPending) return;
      const noteId = decodeTag(btn.dataset.noteView || "");
      if (!noteId) return;
      state.selectedNoteId = noteId;
      const data = await fetchJson(`${endpoints.noteGet}?note_id=${encodeURIComponent(noteId)}`);
      state.noteDetail = data;
      renderNoteDetail(data);
    });
  });
}

function renderPlannerThreads() {
  const container = $("#planner-thread-list");
  if (!container) return;
  const threads = Array.isArray(state.plannerThreads?.threads) ? state.plannerThreads.threads : [];
  if (!threads.length) {
    container.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_threads"))}</div>`;
    return;
  }
  container.innerHTML = threads
    .map((thread) => {
      const id = String(thread.thread_id || "default");
      const idAttr = encodeTag(id);
      const active = id === state.plannerThread ? "active" : "";
      const count = Number(thread.count || 0);
      const last = String(thread.last_ts || "");
      return `
        <button class="thread-item ${active}" data-thread="${idAttr}">
          <div class="thread-title">${escapeHtml(id)}</div>
          <div class="subtle">${escapeHtml(t("notes.thread_meta", { count: String(count), last }))}</div>
        </button>
      `;
    })
    .join("");
  $$("[data-thread]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = decodeTag(btn.dataset.thread || "") || "default";
      state.plannerThread = id;
      const input = $("#planner-thread");
      if (input) input.value = id;
      refreshNotes();
    });
  });
}

function renderAutoLoopSummary() {
  const statusData = unwrap(state.status || {});
  const sections = statusData.sections || {};
  const autoLoop = sections.auto_loop || {};
  renderJson($("#auto-loop-json"), autoLoop);
}

function latestSmokeJobId() {
  const jobs = (state.jobs || {}).jobs || [];
  const smoke = jobs
    .filter((job) => {
      const kind = String(job.kind || job.job_type || "").toUpperCase();
      return kind === "SMOKE_FAST" || kind === "SMOKE_FULL";
    })
    .sort((a, b) => {
      const ca = String(a.created_at || "");
      const cb = String(b.created_at || "");
      if (ca !== cb) return ca.localeCompare(cb);
      return String(a.job_id || "").localeCompare(String(b.job_id || ""));
    });
  const last = smoke[smoke.length - 1];
  return last && last.job_id ? String(last.job_id) : "";
}

function parseTagsInput(raw) {
  const text = String(raw || "");
  return text
    .replace(/\n/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item);
}

function clearNoteComposer() {
  $("#note-title").value = "";
  $("#note-body").value = "";
  $("#note-tags").value = "";
  $("#note-link-id").value = "";
  state.noteLinks = [];
  renderNoteLinks();
}

function buildEvidenceTree(items) {
  const root = {};
  items.forEach((item) => {
    const rel = item.relative_path || item.name || "";
    const parts = rel.split("/");
    let node = root;
    parts.forEach((part, idx) => {
      if (!node[part]) node[part] = { __files: [], __children: {} };
      if (idx === parts.length - 1) {
        node[part].__file = item;
      } else {
        node = node[part].__children;
      }
    });
  });
  return root;
}

function renderEvidenceTreeNode(node, depth = 0) {
  const entries = Object.keys(node).sort();
  return entries
    .map((key) => {
      const value = node[key];
      if (value.__file) {
        const file = value.__file;
        const label = escapeHtml(file.relative_path || file.name || "");
        return `
          <div class="evidence-item">
            <div>${label}</div>
            <div class="row">
              <button class="btn" data-evidence="${encodeURIComponent(file.path || "")}">${escapeHtml(t("actions.view"))}</button>
              <button class="btn" data-copy-path="${encodeURIComponent(file.path || "")}">${escapeHtml(t("actions.copy"))}</button>
            </div>
          </div>`;
      }
      const inner = renderEvidenceTreeNode(value.__children, depth + 1);
      return `
        <details>
          <summary>${escapeHtml(key)}</summary>
          ${inner}
        </details>`;
    })
    .join("");
}

function renderEvidenceList(items) {
  const treeContainer = $("#evidence-tree");
  if (!Array.isArray(items) || items.length === 0) {
    treeContainer.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_evidence_found"))}</div>`;
    return;
  }
  const tree = buildEvidenceTree(items);
  treeContainer.innerHTML = renderEvidenceTreeNode(tree);
  $$('[data-evidence]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const path = decodeURIComponent(btn.dataset.evidence || "");
      if (!path) return;
      state.evidenceSelected = path;
      const data = await fetchJson(`${endpoints.evidenceRead}?path=${encodeURIComponent(path)}`);
      renderJson($("#evidence-viewer"), data);
    });
  });
  $$('[data-copy-path]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const path = decodeURIComponent(btn.dataset.copyPath || "");
      if (path) copyText(path);
    });
  });
}

async function refreshEvidence() {
  const filter = $("#evidence-filter").value.trim() || "closeout";
  const search = $("#evidence-search").value.trim();
  state.evidenceList = await fetchJson(`${endpoints.evidenceList}?filter=${encodeURIComponent(filter)}`);
  let items = (state.evidenceList || {}).items || [];
  if (search) {
    const q = search.toLowerCase();
    items = items.filter((item) => {
      const rel = (item.relative_path || item.name || "").toLowerCase();
      return rel.includes(q);
    });
  }
  renderEvidenceList(items);
}

async function refreshOverview() {
  state.overview = await fetchJson(endpoints.overview);
  renderOverview();
}

async function refreshNorthStar() {
  state.northStar = await fetchJson(endpoints.northStar);
  renderNorthStar();
}

async function refreshInbox() {
  state.inbox = await fetchJson(endpoints.inbox);
  const items = Array.isArray(state.inbox.items)
    ? state.inbox.items
    : (unwrap(state.inbox || {}).items || []);
  const inbox = unwrap(state.inbox || {});
  const meta = $("#inbox-meta");
  if (meta) {
    const generated = formatTimestamp(pickTimestamp(inbox, ["generated_at", "ts", "timestamp"])) || "-";
    const total = inbox?.summary?.items_count ?? items.length;
    const open = inbox?.summary?.by_intake_status?.OPEN;
    const done = inbox?.summary?.by_intake_status?.DONE;
    const openHint = open !== undefined ? ` open=${open}` : "";
    const doneHint = done !== undefined ? ` done=${done}` : "";
    meta.textContent = `generated_at=${generated} total=${total}${openHint}${doneHint}`;
  }
  renderInboxTable(items);
}

async function refreshIntake() {
  await refreshCockpitDecisionArtifacts();
  state.intake = await fetchJson(endpoints.intake);
  const items = Array.isArray(state.intake.items)
    ? state.intake.items
    : (unwrap(state.intake || {}).items || []);
  updateIntakeFilterOptions(items);
  renderIntakeTable(items);
  if (state.intakeSelectedId) {
    const selected = Array.isArray(items) ? items.find((it) => it?.intake_id === state.intakeSelectedId) : null;
    state.intakeSelected = selected || null;
    renderIntakeDetail(selected || null);
    if (selected) {
      refreshIntakeLinkedNotes(selected);
    }
  } else {
    renderIntakeDetail(null);
  }
  if (state.decisions) {
    const decisionItems = Array.isArray(state.decisions.items)
      ? state.decisions.items
      : (unwrap(state.decisions || {}).items || []);
    renderDecisionTable(decisionItems);
  }
}

async function refreshDecisions() {
  state.decisions = await fetchJson(endpoints.decisions);
  const items = Array.isArray(state.decisions.items)
    ? state.decisions.items
    : (unwrap(state.decisions || {}).items || []);
  const inbox = unwrap(state.decisions || {});
  const meta = $("#decision-meta");
  if (meta) {
    const generated = formatTimestamp(pickTimestamp(inbox, ["generated_at", "ts", "timestamp"])) || "-";
    const total = inbox?.counts?.total ?? items.length;
    meta.textContent = `generated_at=${generated} total=${total}`;
  }
  renderDecisionTable(items);
}

async function refreshExtensions() {
  state.extensions = await fetchJson(endpoints.extensions);
  const items = Array.isArray(state.extensions.items) ? state.extensions.items : [];
  renderExtensionsList(items);
  renderExtensionDetail();
}

async function refreshSettings() {
  state.overrides = await fetchJson(endpoints.overridesList);
  const items = Array.isArray(state.overrides.items) ? state.overrides.items : [];
  renderSettingsList(items);
  renderSettingsEditor();
}

async function refreshJobs() {
  state.jobs = await fetchJson(endpoints.jobs);
  state.airunnerJobs = await fetchJson(endpoints.airunnerJobs);
  renderJobsTable((state.jobs || {}).jobs || [], "#github-jobs-table");
  renderJobsTable((state.airunnerJobs || {}).jobs || [], "#airunner-jobs-table");
  const smokeId = latestSmokeJobId();
  const smokeEl = $("#smoke-fast-last");
  if (smokeEl) {
    smokeEl.textContent = smokeId ? `last smoke job: ${smokeId}` : "last smoke job: -";
  }
}

async function refreshLocks() {
  state.locks = await fetchJson(endpoints.locks);
  renderLocks();
}

async function refreshRunCard() {
  state.runCard = await fetchJson(endpoints.runCard);
  renderRunCard();
}

async function refreshNotes() {
  state.plannerThreads = await fetchJson(endpoints.plannerThreads);
  renderPlannerThreads();
  const threadInput = $("#planner-thread");
  if (threadInput && !threadInput.value) {
    threadInput.value = state.plannerThread || "default";
  }
  const thread = state.plannerThread || "default";
  state.notes = await fetchJson(`${endpoints.plannerChat}?thread=${encodeURIComponent(thread)}`);
  const items = Array.isArray(state.notes.items) ? state.notes.items : [];
  renderNotesList(items);
}


async function refreshBudget() {
  state.budget = await fetchJson(endpoints.budget);
  renderJson($("#budget-json"), unwrap(state.budget || {}));
}

async function refreshWsMeta() {
  try {
    state.ws = await fetchJson(endpoints.ws);
    $("#ws-root").textContent = t("sidebar.workspace", { path: state.ws.workspace_root });
    $("#last-change").textContent = t("sidebar.last_change", { ts: state.ws.last_modified_at });
    setConnectionStatus(true);
  } catch (_) {
    setConnectionStatus(false);
  }
}

async function refreshAutoLoop() {
  state.status = await fetchJson(endpoints.status);
  state.snapshot = await fetchJson(endpoints.snapshot);
  renderAutoLoopSummary();
}

async function refreshActiveTab() {
  await refreshWsMeta();
  const tab = String(state.activeTab || "overview").trim();
  if (tab === "overview") return refreshOverview();
  if (tab === "north-star") return refreshNorthStar();
  if (tab === "inbox") return refreshInbox();
  if (tab === "intake") return refreshIntake();
  if (tab === "decisions") return refreshDecisions();
  if (tab === "extensions") return refreshExtensions();
  if (tab === "overrides") return refreshSettings();
  if (tab === "auto-loop") return refreshAutoLoop();
  if (tab === "jobs") return refreshJobs();
  if (tab === "locks") return refreshLocks();
  if (tab === "run-card") return refreshRunCard();
  if (tab === "planner-chat") return refreshNotes();
  if (tab === "evidence") return refreshEvidence();
}

async function refreshAll() {
  await refreshWsMeta();

  const tasks = [
    ["overview", refreshOverview],
    ["north_star", refreshNorthStar],
    ["inbox", refreshInbox],
    ["intake", refreshIntake],
    ["decisions", refreshDecisions],
    ["extensions", refreshExtensions],
    ["settings", refreshSettings],
    ["jobs", refreshJobs],
    ["locks", refreshLocks],
    ["run_card", refreshRunCard],
    ["notes", refreshNotes],
    ["budget", refreshBudget],
    ["auto_loop", refreshAutoLoop],
  ];

  const results = await Promise.allSettled(tasks.map(([, fn]) => fn()));
  results.forEach((res, idx) => {
    if (res.status !== "rejected") return;
    const name = tasks[idx][0];
    showToast(t("toast.refresh_failed", { name, error: formatError(res.reason) }), "warn");
  });
  state.didInitialRefresh = true;
}

function confirmAction(op, args) {
  const modal = $("#confirm-modal");
  const text = $("#confirm-text");
  const yes = $("#confirm-yes");
  const no = $("#confirm-no");
  if (!modal || !text || !yes || !no) {
    const raw = JSON.stringify(args || {});
    const preview = raw.length > 260 ? raw.slice(0, 260) + "..." : raw;
    return Promise.resolve(window.confirm(t("modal.confirm_text", { op, preview })));
  }

  const raw = JSON.stringify(args || {});
  const preview = raw.length > 260 ? raw.slice(0, 260) + "..." : raw;
  text.textContent = t("modal.confirm_text", { op, preview });
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  const lastFocus = document.activeElement;
  requestAnimationFrame(() => {
    try {
      no.focus();
    } catch (_) {
      // ignore
    }
  });

  return new Promise((resolve) => {
    const cleanup = (result) => {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      modal.removeEventListener("keydown", onKeyDown);
      modal.removeEventListener("mousedown", onBackdropMouseDown);
      yes.onclick = null;
      no.onclick = null;
      if (lastFocus && typeof lastFocus.focus === "function") {
        try {
          lastFocus.focus();
        } catch (_) {
          // ignore
        }
      }
      resolve(result);
    };

    const focusables = [no, yes].filter((el) => el && typeof el.focus === "function");
    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        cleanup(false);
        return;
      }
      if (event.key !== "Tab" || focusables.length < 2) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
        return;
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    const onBackdropMouseDown = (event) => {
      if (event.target !== modal) return;
      event.preventDefault();
      cleanup(false);
    };

    modal.addEventListener("keydown", onKeyDown);
    modal.addEventListener("mousedown", onBackdropMouseDown);

    yes.onclick = () => cleanup(true);
    no.onclick = () => cleanup(false);
  });
}

function applyOpButtonsDisabledState() {
  $$("[data-op]").forEach((btn) => {
    const opName = String(btn?.dataset?.op || "").trim();
    const locked = Boolean(opName && state.opJobsInProgress && state.opJobsInProgress[opName]);
    btn.disabled = Boolean(state.actionPending) || locked;
    if (locked) btn.setAttribute("aria-busy", "true");
    else btn.removeAttribute("aria-busy");
  });
}

function markOpJobInProgress(opName, jobId) {
  const op = String(opName || "").trim();
  const id = String(jobId || "").trim();
  if (!op || !id) return;
  if (!state.opJobsInProgress || typeof state.opJobsInProgress !== "object") state.opJobsInProgress = {};
  state.opJobsInProgress[op] = id;
  applyOpButtonsDisabledState();
}

function clearOpJobInProgress(opName, jobId = "") {
  const op = String(opName || "").trim();
  if (!op) return;
  if (!state.opJobsInProgress || typeof state.opJobsInProgress !== "object") state.opJobsInProgress = {};
  const expected = String(jobId || "").trim();
  if (expected && state.opJobsInProgress[op] && state.opJobsInProgress[op] !== expected) return;
  delete state.opJobsInProgress[op];
  applyOpButtonsDisabledState();
}

function setActionDisabled(disabled) {
  state.actionPending = disabled;
  applyOpButtonsDisabledState();
  [
    "lock-refresh",
    "extensions-refresh",
    "settings-refresh",
    "settings-save",
    "settings-clear",
    "run-card-save",
    "run-card-refresh",
    "notes-refresh",
    "note-save",
    "note-clear",
    "note-link-add",
    "note-link-clear",
    "planner-thread-refresh",
    "planner-send",
    "composer-run",
    "download-evidence",
  ].forEach((id) => {
    const el = $("#" + id);
    if (el) el.disabled = disabled;
  });
  applyAdminModeToWriteControls();
}

function isOpJobInProgress(payload) {
  const jobId = String(payload?.job_id || "").trim();
  if (!jobId) return false;
  const jobStatus = String(payload?.job_status || payload?.status || "").toUpperCase();
  return jobStatus === "RUNNING" || jobStatus === "PENDING";
}

function pollOpJob(jobId, pollUrl = "", opHint = "") {
  const id = String(jobId || "").trim();
  if (!id) return;
  if (OP_JOB_POLLING.has(id)) return;
  OP_JOB_POLLING.add(id);
  const url = String(pollUrl || "").trim() || `/api/op_job?job_id=${encodeURIComponent(id)}`;
  const startedAt = Date.now();
  const maxMs = 10 * 60 * 1000;
  let opName = String(opHint || "").trim();
  if (opName) markOpJobInProgress(opName, id);
  let errors = 0;

  const cleanup = () => {
    OP_JOB_POLLING.delete(id);
    if (opName) clearOpJobInProgress(opName, id);
  };

  const tick = async () => {
    let data = null;
    try {
      data = await fetchJson(url);
      errors = 0;
    } catch (err) {
      showToast(t("job.poll_failed", { error: formatError(err) }), "warn");
      errors += 1;
      if (Date.now() - startedAt > maxMs || errors >= 3) {
        cleanup();
        return;
      }
      setTimeout(tick, 1200);
      return;
    }
    if (!data) {
      cleanup();
      return;
    }
    if (!opName && data.op) {
      opName = String(data.op || "").trim();
      if (opName) markOpJobInProgress(opName, id);
    }
    state.lastAction = data;
    renderActionResponse();
    logAction(data);

    const status = String(data.status || data.job_status || "").toUpperCase();
    const inProgress = status === "RUNNING" || status === "PENDING";
    if (inProgress) {
      if (Date.now() - startedAt > maxMs) {
        showToast(t("job.poll_timeout", { id }), "warn");
        cleanup();
        return;
      }
      setTimeout(tick, 650);
      return;
    }

    const kind = status.includes("FAIL") ? "fail" : status.includes("WARN") ? "warn" : "ok";
    showToast(t("job.done", { op: data.op || "op", status: status || "DONE" }), kind);
    scheduleRefresh("active_tab", refreshActiveTab, 140);
    cleanup();
  };

  setTimeout(tick, 400);
}

async function postOp(op, args = {}) {
  if (state.actionPending) return null;
  const opName = String(op || "").trim();
  const existingJobId =
    opName && state.opJobsInProgress && typeof state.opJobsInProgress === "object"
      ? String(state.opJobsInProgress[opName] || "").trim()
      : "";
  if (existingJobId) {
    showToast(t("job.already_running", { op: opName, id: existingJobId }), "warn");
    pollOpJob(existingJobId, "", opName);
    return null;
  }
  if (ADMIN_REQUIRED_OPS.has(opName) && !isAdminModeEnabled()) {
    showToast(t("admin.required_op"), "warn");
    return null;
  }
  const ok = await confirmAction(op, args);
  if (!ok) return null;
  setActionDisabled(true);
  let data = null;
  try {
    const res = await fetch("/api/op", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op, args, confirm: true }),
    });
    data = await res.json();
    state.lastAction = data;
    renderActionResponse();
    logAction(data);
    if (!res.ok) {
      showToast(t("toast.op_failed", { error: data.error || data.status || "UNKNOWN" }), "fail");
      return data;
    }
    if (isOpJobInProgress(data)) {
      const jobId = String(data.job_id || "").trim();
      const effectiveOp = String(data.op || opName || op).trim() || "op";
      const notes = Array.isArray(data.notes) ? data.notes.map((x) => String(x)) : [];
      const reused = notes.some((n) => n.includes("JOB_REUSED=true"));
      showToast(
        t(reused ? "job.already_running" : "job.started", { op: effectiveOp, id: jobId || "-" }),
        "warn"
      );
      if (jobId) markOpJobInProgress(effectiveOp, jobId);
      pollOpJob(jobId, data.poll_url || "", effectiveOp);
      return data;
    }
    const status = String(data?.status || "UNKNOWN").toUpperCase();
    const toastKind = status.includes("FAIL") ? "fail" : status.includes("WARN") ? "warn" : "ok";
    showToast(t("job.done", { op, status: data.status || "UNKNOWN" }), toastKind);
    if (op === "planner-chat-send" && data.status !== "FAIL") {
      clearNoteComposer();
    }
    await refreshAll();
  } finally {
    setActionDisabled(false);
  }
  return data;
}

async function postOpInternal(op, args = {}) {
  const res = await fetch("/api/op", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ op, args, confirm: true }),
  });
  const data = await res.json();
  return { res, data };
}

async function postAction(action, url, payload = {}) {
  if (state.actionPending) return;
  const actionName = String(action || "").trim();
  if (ADMIN_REQUIRED_ACTIONS.has(actionName) && !isAdminModeEnabled()) {
    showToast(t("admin.required_action"), "warn");
    return null;
  }
  const ok = await confirmAction(action, payload);
  if (!ok) return;
  setActionDisabled(true);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, confirm: true }),
    });
    const data = await res.json();
    if (!data.op) data.op = action;
    state.lastAction = data;
    renderActionResponse();
    logAction(data);
    const status = String(data.status || "UNKNOWN");
    const kind = status === "FAIL" ? "fail" : status === "WARN" ? "warn" : "ok";
    showToast(t("job.done", { op: action, status }), kind);
    if (!res.ok) {
      showToast(t("toast.action_failed", { error: data.error || data.status || "UNKNOWN" }), "fail");
      return data;
    }
    await refreshAll();
  } finally {
    setActionDisabled(false);
  }
  return data;
}

async function postChat(type, text) {
  const payload = { type, text };
  await postAction("chat-note", endpoints.chat, payload);
}

function handleChatCommand(rawText) {
  const text = String(rawText || "").trim();
  if (!text) return;
  const parts = text.split(/\s+/);
  if (text.startsWith("/op")) {
    const op = parts[1];
    if (!op) {
      showToast(t("toast.usage_op"), "warn");
      return;
    }
    const jsonText = text.slice(text.indexOf(op) + op.length).trim();
    let args = {};
    if (jsonText) {
      try {
        args = JSON.parse(jsonText);
      } catch (err) {
        showToast(t("toast.invalid_json_op", { error: formatError(err) }), "fail");
        return;
      }
    }
    postOp(op, args);
    return;
  }
  if (text.startsWith("/decision")) {
    const decisionId = parts[1];
    const optionId = parts[2];
    if (!decisionId || !optionId) {
      showToast(t("toast.usage_decision"), "warn");
      return;
    }
    postOp("decision-apply", { decision_id: decisionId, option_id: optionId });
    return;
  }
  if (text.startsWith("/bulk")) {
    postOp("decision-apply-bulk", { mode: "safe_defaults" });
    return;
  }
  if (text.startsWith("/override")) {
    const filename = parts[1];
    if (!filename) {
      showToast(t("toast.usage_override"), "warn");
      return;
    }
    const jsonText = text.slice(text.indexOf(filename) + filename.length).trim();
    if (!jsonText) {
      showToast(t("toast.override_json_required"), "warn");
      return;
    }
    let obj = null;
    try {
      obj = JSON.parse(jsonText);
    } catch (err) {
      showToast(t("toast.invalid_json_override", { error: formatError(err) }), "fail");
      return;
    }
    postAction("settings-set-override", endpoints.settingsSet, { filename, json: obj });
    return;
  }
  if (text.startsWith("/help")) {
    const helpText = [
      "/op <name> <json>",
      "/decision <decision_id> <option_id>",
      "/bulk safe_defaults",
      "/override <policy_*.override.v1.json> <json>",
      "/help",
    ].join("\n");
    postChat("HELP", helpText);
    return;
  }
  postChat("NOTE", text);
}

function setupNav() {
  const applyRoute = () => {
    const raw = (location.hash || "#overview").replace("#", "");
    const aliases = {
      // Backwards-compatible: older links may point to "#notes".
      notes: "planner-chat",
    };
    const tab = aliases[raw] || raw;
    if (tab !== raw) {
      location.hash = tab;
      return;
    }
    const prev = String(state.activeTab || "");
    state.activeTab = tab;
    $$('nav button').forEach((b) => {
      const isActive = String(b?.dataset?.tab || "") === tab;
      b.classList.toggle("active", isActive);
      if (isActive) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    $$(".tab").forEach((t) => {
      const isActive = t?.id === `tab-${tab}`;
      t.classList.toggle("active", isActive);
      t.setAttribute("aria-hidden", isActive ? "false" : "true");
    });
    if (prev && prev !== tab && state.didInitialRefresh) {
      scheduleRefresh("active_tab", refreshActiveTab, 120);
    }
  };

  $$('nav button').forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      location.hash = tab;
      applyRoute();
    });
  });

  window.addEventListener("hashchange", applyRoute);
  applyRoute();
}

function setupTagSelects() {
  const fields = ["bucket", "status", "source", "extension"];
  const closeAll = (except) => {
    fields.forEach((field) => {
      if (field === except) return;
      const wrap = $(`#filter-${field}`);
      if (wrap) wrap.classList.remove("open");
      const input = $(`#filter-${field}-input`);
      if (input) setAriaExpanded(input, false);
    });
  };
  fields.forEach((field) => {
    const wrap = $(`#filter-${field}`);
    const input = $(`#filter-${field}-input`);
    const options = $(`#filter-${field}-options`);
    if (!wrap || !input || !options) return;
    const toggle = wrap.querySelector(".tag-toggle");

    const openSelect = () => {
      closeAll(field);
      wrap.classList.add("open");
      setTagSelectActiveIndex("intake", field, 0);
      renderTagSelect(field);
      requestAnimationFrame(() => scrollTagSelectActiveOptionIntoView(options));
    };

    input.addEventListener("focus", () => {
      openSelect();
    });
    input.addEventListener("input", () => renderTagSelect(field));
    input.addEventListener("keydown", (event) => {
      const key = event.key;
      if (key === "Escape") {
        wrap.classList.remove("open");
        setAriaExpanded(input, false);
        return;
      }
      if (key !== "ArrowDown" && key !== "ArrowUp" && key !== "Enter") return;
      if (!wrap.classList.contains("open") && (key === "ArrowDown" || key === "ArrowUp")) {
        openSelect();
      }
      if (!wrap.classList.contains("open")) return;

      const optionEls = Array.from(options.querySelectorAll(".tag-option[data-value]"));
      if (!optionEls.length) return;
      const current = getTagSelectActiveIndex("intake", field, optionEls.length);

      if (key === "ArrowDown" || key === "ArrowUp") {
        event.preventDefault();
        const delta = key === "ArrowDown" ? 1 : -1;
        setTagSelectActiveIndex("intake", field, clampIndex(current + delta, optionEls.length), optionEls.length);
        renderTagSelect(field);
        requestAnimationFrame(() => scrollTagSelectActiveOptionIntoView(options));
        return;
      }

      if (key === "Enter") {
        event.preventDefault();
        const target = optionEls[current];
        const rawValue = target?.dataset?.value;
        if (!rawValue) return;
        addTag(field, decodeTag(rawValue));
        input.value = "";
        openSelect();
        input.focus();
        renderIntakeTable((unwrap(state.intake || {}).items || []));
      }
    });
    input.addEventListener("blur", () => {
      setTimeout(() => {
        if (wrap.contains(document.activeElement)) return;
        wrap.classList.remove("open");
        setAriaExpanded(input, false);
      }, 150);
    });
    options.addEventListener("mousedown", (event) => event.preventDefault());
    if (toggle) {
      toggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (wrap.classList.contains("open")) {
          wrap.classList.remove("open");
          setAriaExpanded(input, false);
        } else {
          openSelect();
        }
        input.focus();
      });
    }
    wrap.addEventListener("click", (event) => {
      const target = event.target;
      if (target?.classList?.contains("tag-toggle")) return;
      const rawValue = target?.dataset?.value;
      const rawRemove = target?.dataset?.remove;
      if (rawValue) {
        addTag(field, decodeTag(rawValue));
        input.value = "";
        openSelect();
        input.focus();
        renderIntakeTable((unwrap(state.intake || {}).items || []));
      }
      if (rawRemove) {
        removeTag(field, decodeTag(rawRemove));
        renderIntakeTable((unwrap(state.intake || {}).items || []));
      }
      if (target && (target.classList?.contains("tag-select-input") || target.classList?.contains("tag-input"))) {
        openSelect();
        input.focus();
      }
    });
  });

  document.addEventListener("click", (event) => {
    fields.forEach((field) => {
      const wrap = $(`#filter-${field}`);
      if (!wrap) return;
      if (!wrap.contains(event.target)) {
        wrap.classList.remove("open");
        const input = $(`#filter-${field}-input`);
        if (input) setAriaExpanded(input, false);
      }
    });
  });
}

function setupOps() {
  setupTagSelects();

  $("#refresh-all").addEventListener("click", () => {
    refreshAll();
    refreshEvidence();
  });

  const inlineToggle = $("#toggle-sidebar-inline");
  if (inlineToggle) {
    inlineToggle.setAttribute("aria-pressed", isSidebarCollapsed() ? "true" : "false");
    inlineToggle.addEventListener("click", () => {
      const next = !isSidebarCollapsed();
      applySidebarCollapsedState(next, { persist: true });
      inlineToggle.setAttribute("aria-pressed", next ? "true" : "false");
    });
  }

  $$('[data-op]').forEach((btn) => {
    btn.addEventListener("click", () => postOp(btn.dataset.op));
  });

  $("#apply-intake-filter").addEventListener("click", () => {
    const items = Array.isArray(state.intake?.items)
      ? state.intake.items
      : (unwrap(state.intake || {}).items || []);
    renderIntakeTable(items);
  });
  $("#clear-intake-filter").addEventListener("click", () => {
    state.filters.intake = { bucket: [], status: [], source: [], extension: [] };
    ["bucket", "status", "source", "extension"].forEach((field) => {
      const input = $(`#filter-${field}-input`);
      if (input) input.value = "";
      renderTagSelect(field);
    });
    const hideDone = $("#filter-hide-done");
    if (hideDone) hideDone.checked = true;
    $("#intake-search").value = "";
    renderIntakeTable((unwrap(state.intake || {}).items || []));
  });
  $("#intake-search").addEventListener("input", () => {
    renderIntakeTable((unwrap(state.intake || {}).items || []));
  });
  const clearSelection = $("#intake-clear-selection");
  if (clearSelection) {
    clearSelection.addEventListener("click", (event) => {
      event.preventDefault();
      clearIntakeSelection();
    });
  }
  const createNoteBtn = $("#intake-create-note");
  if (createNoteBtn) {
    createNoteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      createNoteForSelectedIntake();
    });
  }
  const openNotesBtn = $("#intake-open-notes");
  if (openNotesBtn) {
    openNotesBtn.addEventListener("click", (event) => {
      event.preventDefault();
      navigateToTab("notes");
    });
  }
  const claimBtn = $("#intake-claim");
  if (claimBtn) {
    claimBtn.addEventListener("click", (event) => {
      event.preventDefault();
      claimIntakeItem(state.intakeSelectedId, "claim");
    });
  }
  const claimReleaseBtn = $("#intake-claim-release");
  if (claimReleaseBtn) {
    claimReleaseBtn.addEventListener("click", (event) => {
      event.preventDefault();
      claimIntakeItem(state.intakeSelectedId, "release");
    });
  }
  const claimForceReleaseBtn = $("#intake-claim-force-release");
  if (claimForceReleaseBtn) {
    claimForceReleaseBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      const id = String(state.intakeSelectedId || "").trim();
      if (!id) return;
      await forceReleaseIntakeClaim(id);
    });
  }
  const closeBtn = $("#intake-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await closeSelectedIntakeItem();
    });
  }
  const hideDone = $("#filter-hide-done");
  if (hideDone) {
    hideDone.addEventListener("change", () => {
      renderIntakeTable((unwrap(state.intake || {}).items || []));
    });
  }
  $("#decision-search").addEventListener("input", () => {
    renderDecisionTable((unwrap(state.decisions || {}).items || []));
  });

  const inboxRefresh = $("#inbox-refresh");
  if (inboxRefresh) {
    inboxRefresh.addEventListener("click", () => refreshInbox());
  }
  const inboxSearch = $("#inbox-search");
  if (inboxSearch) {
    inboxSearch.addEventListener("input", () => {
      const items = Array.isArray(state.inbox?.items)
        ? state.inbox.items
        : (unwrap(state.inbox || {}).items || []);
      renderInboxTable(items);
    });
  }
  ["inbox-filter-bucket", "inbox-filter-status", "inbox-filter-triage"].forEach((id) => {
    const el = $(`#${id}`);
    if (!el) return;
    el.addEventListener("change", () => {
      const items = Array.isArray(state.inbox?.items)
        ? state.inbox.items
        : (unwrap(state.inbox || {}).items || []);
      renderInboxTable(items);
    });
  });

  const lockRefresh = $("#lock-refresh");
  if (lockRefresh) {
    lockRefresh.addEventListener("click", () => refreshLocks());
  }
  const lockClaimsLimit = $("#lock-claims-limit");
  if (lockClaimsLimit) {
    lockClaimsLimit.addEventListener("change", () => {
      setLockClaimsLimit(lockClaimsLimit.value, { persist: true });
    });
  }
  const lockClaimsGroupOwner = $("#lock-claims-group-owner");
  if (lockClaimsGroupOwner) {
    lockClaimsGroupOwner.addEventListener("click", (event) => {
      event.preventDefault();
      setLockClaimsGroupByOwner(!state.lockClaimsGroupByOwner, { persist: true });
    });
  }
  const adminToggle = $("#admin-mode-toggle");
  if (adminToggle) {
    adminToggle.addEventListener("click", (event) => {
      event.preventDefault();
      setAdminModeEnabled(!state.adminModeEnabled, { persist: true });
    });
  }
  const adminToggleTopbar = $("#admin-mode-toggle-topbar");
  if (adminToggleTopbar) {
    adminToggleTopbar.addEventListener("click", (event) => {
      event.preventDefault();
      setAdminModeEnabled(!state.adminModeEnabled, { persist: true });
    });
  }

  $("#extensions-refresh").addEventListener("click", () => refreshExtensions());

  $("#settings-refresh").addEventListener("click", () => refreshSettings());
  $("#settings-save").addEventListener("click", () => {
    const name = state.overridesSelected || "";
    if (!name) {
      showToast(t("toast.select_override_first"), "warn");
      return;
    }
    const raw = $("#settings-editor").value || "";
    let obj = null;
    try {
      obj = JSON.parse(raw);
    } catch (err) {
      showToast(t("toast.invalid_json", { error: formatError(err) }), "fail");
      return;
    }
    postOp("overrides-write", { name, json: obj });
  });
  $("#settings-clear").addEventListener("click", () => {
    $("#settings-editor").value = JSON.stringify({ version: "v1" }, null, 2);
  });

  $("#run-card-refresh").addEventListener("click", () => refreshRunCard());
  $("#run-card-save").addEventListener("click", () => {
    const raw = $("#run-card-editor").value || "";
    let obj = null;
    try {
      obj = JSON.parse(raw);
    } catch (err) {
      showToast(t("toast.invalid_json", { error: formatError(err) }), "fail");
      return;
    }
    postAction("run-card-set", endpoints.runCardSet, { json: obj });
  });

  const threadRefresh = $("#planner-thread-refresh");
  if (threadRefresh) {
    threadRefresh.addEventListener("click", () => refreshNotes());
  }
  const threadInput = $("#planner-thread");
  if (threadInput) {
    threadInput.addEventListener("change", () => {
      state.plannerThread = threadInput.value.trim().toLowerCase() || "default";
      refreshNotes();
    });
  }
  const composerRun = $("#composer-run");
  if (composerRun) {
    composerRun.addEventListener("click", async () => {
      const opSelect = $("#composer-op");
      const argsField = $("#composer-args");
      const op = opSelect ? opSelect.value : "";
      if (!op) {
        showToast(t("toast.select_op_first"), "warn");
        return;
      }
      let args = {};
      const rawArgs = argsField ? argsField.value.trim() : "";
      if (rawArgs) {
        try {
          args = JSON.parse(rawArgs);
        } catch (err) {
          showToast(t("toast.invalid_json", { error: formatError(err) }), "fail");
          return;
        }
      }
      const result = await postOp(op, args);
      if (result) {
        const meta = $("#composer-meta");
        if (meta) {
          meta.textContent = `status=${result.status || ""} error=${result.error || result.error_code || ""}`;
        }
        renderJson($("#composer-response"), result);
      }
      if (result && result.status && (state.plannerThread || "default")) {
        const thread = state.plannerThread || "default";
        const summary = {
          status: result.status,
          op: result.op,
          error: result.error || result.error_code || "",
          trace_meta: result.trace_meta || {},
          evidence_paths: result.evidence_paths || [],
        };
        await postOpInternal("planner-chat-send", {
          thread,
          title: `OP: ${op}`,
          body: JSON.stringify(summary, null, 2),
          tags: "system,op",
          links_json: "[]",
        });
        refreshNotes();
      }
    });
  }

  $("#notes-refresh").addEventListener("click", () => refreshNotes());
  $("#notes-search").addEventListener("input", () => {
    const items = Array.isArray(state.notes?.items) ? state.notes.items : [];
    renderNotesList(items);
  });
  $("#notes-tag-filter").addEventListener("input", () => {
    const items = Array.isArray(state.notes?.items) ? state.notes.items : [];
    renderNotesList(items);
  });

  $("#note-link-add").addEventListener("click", () => {
    const kind = $("#note-link-kind").value.trim();
    const target = $("#note-link-id").value.trim();
    if (!kind || !target) {
      showToast(t("toast.link_kind_required"), "warn");
      return;
    }
    state.noteLinks.push({ kind, id_or_path: target });
    $("#note-link-id").value = "";
    renderNoteLinks();
  });

  $("#note-link-clear").addEventListener("click", () => {
    state.noteLinks = [];
    renderNoteLinks();
  });

  $("#note-save").addEventListener("click", () => {
    const title = $("#note-title").value.trim();
    const body = $("#note-body").value || "";
    const tags = parseTagsInput($("#note-tags").value);
    if (!title && !body.trim()) {
      showToast(t("toast.title_or_body_required"), "warn");
      return;
    }
    const threadInput = $("#planner-thread");
    const threadRaw = threadInput ? threadInput.value.trim().toLowerCase() : "";
    const thread = threadRaw || state.plannerThread || "default";
    const linksJson = JSON.stringify(state.noteLinks || []);
    postOp("planner-chat-send", {
      thread,
      title,
      body,
      tags: tags.join(","),
      links_json: linksJson,
    });
  });

  $("#note-clear").addEventListener("click", () => {
    clearNoteComposer();
  });

  renderNoteLinks();

  $("#evidence-refresh").addEventListener("click", refreshEvidence);
  $("#evidence-search").addEventListener("input", () => scheduleRefresh("evidence", refreshEvidence, 240));
  const evidenceFilter = $("#evidence-filter");
  if (evidenceFilter) {
    evidenceFilter.addEventListener("input", () => scheduleRefresh("evidence", refreshEvidence, 240));
  }

  $("#copy-evidence-path").addEventListener("click", () => {
    if (state.evidenceSelected) copyText(state.evidenceSelected);
  });
  $("#copy-evidence-json").addEventListener("click", () => {
    const text = $("#evidence-viewer").textContent || "";
    if (text) copyText(text);
  });
  $("#download-evidence").addEventListener("click", () => {
    if (!state.evidenceSelected) return;
    const url = `${endpoints.evidenceRaw}?path=${encodeURIComponent(state.evidenceSelected)}`;
    window.open(url, "_blank");
  });
}

function copyText(text) {
  if (!text) return;
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(
      () => showToast(t("actions.copied"), "ok"),
      () => showToast(t("actions.copy_failed"), "warn")
    );
  } else {
    const el = document.createElement("textarea");
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    showToast(t("actions.copied"), "ok");
  }
}

function setupStream() {
  const stream = new EventSource("/api/stream");
  stream.addEventListener("overview_tick", () => {
    if (state.activeTab === "overview") scheduleRefresh("overview", refreshOverview, 180);
  });
  stream.addEventListener("inbox_tick", () => {
    if (state.activeTab === "inbox") scheduleRefresh("inbox", refreshInbox, 220);
  });
  stream.addEventListener("intake_tick", () => {
    if (state.activeTab === "intake") scheduleRefresh("intake", refreshIntake, 220);
  });
  stream.addEventListener("decisions_tick", () => {
    if (state.activeTab === "decisions") scheduleRefresh("decisions", refreshDecisions, 220);
  });
  stream.addEventListener("jobs_tick", () => {
    if (state.activeTab === "jobs" || state.activeTab === "auto-loop") scheduleRefresh("jobs", refreshJobs, 260);
  });
  stream.addEventListener("locks_tick", () => {
    if (state.activeTab === "locks") scheduleRefresh("locks", refreshLocks, 260);
  });
  stream.addEventListener("notes_tick", () => {
    if (state.activeTab === "planner-chat") scheduleRefresh("notes", refreshNotes, 260);
  });
  stream.addEventListener("chat_tick", () => {
    if (state.activeTab === "planner-chat") scheduleRefresh("notes", refreshNotes, 260);
  });
  stream.addEventListener("settings_tick", () => {
    if (state.activeTab === "overrides") scheduleRefresh("settings", refreshSettings, 260);
    if (state.activeTab === "run-card") scheduleRefresh("run_card", refreshRunCard, 260);
    if (state.activeTab === "extensions") scheduleRefresh("extensions", refreshExtensions, 260);
  });
  stream.addEventListener("changed", () => {
    scheduleRefresh("active_tab", refreshActiveTab, 260);
  });
  stream.onopen = () => {
    state.sseConnected = true;
    setSseStatus(true);
  };
  stream.onerror = () => {
    state.sseConnected = false;
    setSseStatus(false);
  };
}

applySidebarCollapsedState(readSidebarCollapsedFromStorage(), { persist: false });
state.claimOwnerTag = getOrCreateClaimOwnerTag();
state.lang = readLangFromStorage(LANG_STORAGE_KEY, "tr");
state.adminModeEnabled = readBoolFromStorage("cockpit_admin_mode.v1", false);
state.lockClaimsLimit = readIntFromStorage("cockpit_lock_claims_limit.v1", 20, [10, 20, 50]);
state.lockClaimsGroupByOwner = readBoolFromStorage("cockpit_lock_claims_group_owner.v1", false);
setupLanguageSelector();
applyI18n();
setupNav();
setupOps();
setupStream();
refreshAll();
refreshEvidence();
