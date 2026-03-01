const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const SIDEBAR_STORAGE_KEY = "cockpit_lite_sidebar_collapsed_v1";
const SIDEBAR_COLLAPSED_CLASS = "sidebar-collapsed";
const NORTH_STAR_FINDINGS_ALL_LENSES_KEY = "__ALL_LENSES__";
const ADMIN_REQUIRED_OPS = new Set(["overrides-write", "work-intake-purpose-generate", "planner-chat-send-llm"]);
const ADMIN_REQUIRED_ACTIONS = new Set(["run-card-set", "extension-toggle", "settings-set-override"]);
const ADMIN_REQUIRED_ELEMENT_IDS = new Set(["settings-save", "run-card-save"]);
const AI_SUGGEST_THREAD_STORAGE_KEY = "cockpit.ai_suggest_threads.v1";
const LANG_STORAGE_KEY = "cockpit_lang.v1";
const THEME_STORAGE_KEY = "cockpit_theme.v1";
const CHAT_SELECTION_STORAGE_KEY = "cockpit_planner_chat_selection.v1";
const SUPPORTED_LANGS = ["en", "tr"];
const OP_JOB_POLLING = new Set();
const GITHUB_OPS_POLL_ACTIVE_MS = 15000;
const GITHUB_OPS_POLL_IDLE_MS = 60000;
const GITHUB_OPS_STALE_MS = 3 * 60 * 1000;
const SEARCH_INDEX_AUTO_REFRESH_MS = 24 * 60 * 60 * 1000;
const SEARCH_INDEX_POLL_MS = 15 * 60 * 1000;
const TIMELINE_ALERT_NON_TOOL_RATIO = 0.6;
const TIMELINE_ALERT_P95_MS = 10 * 60 * 1000;
const TIMELINE_TREND_WINDOW = 5;
const INTAKE_GROUP_TABS = {
  summary: ["summary"],
  decision: ["decision"],
  evidence: ["evidence", "notes"],
  raw: ["raw"],
};
const CHAT_MODEL_GROUPS = {
  FAST_TEXT: { label: "FAST_TEXT", provider_order: ["openai", "google", "claude", "deepseek", "qwen", "xai"] },
  BALANCED_TEXT: { label: "BALANCED_TEXT", provider_order: ["qwen", "deepseek", "openai", "google", "claude", "xai"] },
  REASONING_TEXT: { label: "REASONING_TEXT", provider_order: ["xai", "openai", "google", "claude", "deepseek", "qwen"] },
  CODE_AGENTIC: { label: "CODE_AGENTIC", provider_order: ["openai", "xai", "qwen", "deepseek"] },
  GOVERNANCE_ASSURANCE: { label: "GOVERNANCE_ASSURANCE", provider_order: ["claude", "openai", "google", "qwen", "deepseek"] },
  VISION_MM: { label: "VISION_MM", provider_order: ["openai", "google", "claude", "qwen", "xai"] },
  OCR_DOC: { label: "OCR_DOC", provider_order: ["qwen", "google", "openai"] },
  VISION_REASONING: { label: "VISION_REASONING", provider_order: ["qwen", "openai", "google", "claude"] },
  IMAGE_GEN: { label: "IMAGE_GEN", provider_order: ["openai", "google", "xai", "qwen"] },
  VIDEO_GEN: { label: "VIDEO_GEN", provider_order: ["openai", "google", "xai"] },
  AUDIO: { label: "AUDIO", provider_order: ["openai", "google", "xai"] },
  REALTIME_STREAMING: { label: "REALTIME_STREAMING", provider_order: ["openai", "google", "xai"] },
  EMBEDDINGS: { label: "EMBEDDINGS", provider_order: ["openai", "google", "qwen", "xai"] },
  MODERATION_SAFETY: { label: "MODERATION_SAFETY", provider_order: ["openai", "google"] },
  DEEP_RESEARCH: { label: "DEEP_RESEARCH", provider_order: ["openai", "google"] },
};

const EXTENSION_DESCRIPTIONS_TR = {
  "PRJ-AIRUNNER": {
    summary: "Arka planda otomatik iş döngülerini çalıştırır.",
    value: "Tekrarlayan işleri otomatikleştirir ve akışları düzenli işletir.",
    when: "Zamanlanmış veya tetiklenen döngülerde.",
    output: "Job durumu ve çalışma logları.",
  },
  "PRJ-DEPLOY": {
    summary: "Dağıtım (deploy) akışını ve hedeflerini yönetir.",
    value: "Dağıtım süreçlerini standartlaştırır, kontrol noktaları sağlar.",
    when: "Deploy işleri çalıştırıldığında.",
    output: "Deploy durumu ve sonuçlar.",
  },
  "PRJ-ENFORCEMENT-PACK": {
    summary: "Uyum ve kalite kurallarını otomatik kontrol eder.",
    value: "Hatalı değişikliklerin sisteme girmesini engeller, riskleri görünür kılar.",
    when: "Policy-check / enforcement akışlarında.",
    output: "Uyarı–ihlal raporu ve gerekiyorsa bloklama.",
  },
  "PRJ-EXECUTORPORT": {
    summary: "Güvenli komut/iş yürütme kapısı sağlar.",
    value: "Komut çalıştırmayı kontrollü ve izlenebilir hale getirir.",
    when: "Runner/executor çağrılarında.",
    output: "Çalıştırma çıktısı ve durum.",
  },
  "PRJ-KERNEL-API": {
    summary: "Çekirdek API ve ortak sözleşmeleri sağlar.",
    value: "Modüller arası uyumu korur, standart davranış üretir.",
    when: "Ortak API kullanımlarında.",
    output: "API yanıtları ve sözleşme uyumu.",
  },
  "PRJ-M0-MAINTAINABILITY": {
    summary: "Bakım/kalite odaklı temel kuralları uygular.",
    value: "Uzun vadeli sürdürülebilirliği güçlendirir.",
    when: "Kontrol/denetim aşamalarında.",
    output: "Uyarılar ve bakım raporları.",
  },
  "PRJ-MEMORYPORT": {
    summary: "Semantik arama/bellek katmanına bağlantı sağlar.",
    value: "Benzerlik aramalarını ve bilgi geri çağırmayı mümkün kılar.",
    when: "Semantic search ve memory işlemlerinde.",
    output: "Arama sonuçları ve eşleşmeler.",
  },
  "PRJ-OBSERVABILITY-OTEL": {
    summary: "Telemetry ve izleme verilerini toplar.",
    value: "Sistem sağlığını görünür kılar, sorun takibini kolaylaştırır.",
    when: "Sistem çalışırken.",
    output: "Log/trace/metric verileri.",
  },
  "PRJ-PLANNER": {
    summary: "İşleri plan adımlarına çevirir.",
    value: "Ne yapılacağını netleştirir, önerileri yapılandırır.",
    when: "Planlama/istişare çağrılarında.",
    output: "Plan adımları ve öneriler.",
  },
  "PRJ-PM-SUITE": {
    summary: "Proje/portföy yönetimi bileşenlerini sağlar.",
    value: "Projeleri yapılandırılmış biçimde takip etmeyi sağlar.",
    when: "PM modülleri kullanıldığında.",
    output: "PM kayıtları ve durumlar.",
  },
  "PRJ-UI-COCKPIT-LITE": {
    summary: "Operatör konsolu arayüzünü sağlar.",
    value: "Durumları ve aksiyonları tek ekranda toplar.",
    when: "Cockpit açıldığında.",
    output: "UI görünümü.",
  },
  "PRJ-WORK-INTAKE": {
    summary: "Gelen işleri toplar ve sınıflandırır.",
    value: "İşlerin kaybolmasını engeller, net bir iş kuyruğu sağlar.",
    when: "Yeni istek geldiğinde ve intake yenilemede.",
    output: "İş listesi, amaç ve etiketler.",
  },
  "prj-github-ops": {
    summary: "GitHub operasyonlarını yönetir.",
    value: "Repo içi otomasyonu standartlaştırır.",
    when: "GitHub ops çağrılarında.",
    output: "Job durumları ve sonuçlar.",
  },
  "release-automation": {
    summary: "Sürümleme ve yayın akışlarını otomatikler.",
    value: "Yayın sürecini hızlandırır, hataları azaltır.",
    when: "Release işleri tetiklendiğinde.",
    output: "Release durumu ve çıktılar.",
  },
};

const I18N = {
  en: {
    "ui.title": "Operator Console",
    "lang.label": "Language",
    "theme.label": "Theme",
    "theme.dark": "Dark",
    "theme.light": "Light",
    "actions.refresh_all": "Refresh All",
    "actions.multi_repo_refresh": "Managed repos status",
    "actions.snapshot_page": "Snapshot this page",
    "sidebar.toggle": "Toggle sidebar",
    "nav.primary": "Primary",
    "nav.overview": "Overview",
    "nav.north_star": "North Star",
    "nav.timeline": "Timeline",
    "nav.inbox": "Inbox",
    "nav.intake": "Intake",
    "nav.decisions": "Decisions",
    "nav.extensions": "Extensions",
    "nav.overrides": "Overrides",
    "nav.auto_loop": "Auto-loop",
    "nav.jobs": "Jobs",
    "nav.locks": "Locks",
    "nav.run_card": "Run-Card",
    "nav.search": "Search",
    "nav.planner_chat": "Planner Chat",
    "nav.command_composer": "Command Composer",
    "nav.evidence": "Evidence",
    "h.system_status": "System Status",
    "h.multi_repo_status": "Managed Repositories",
    "h.work_intake": "Work Intake",
    "h.decisions": "Decisions",
    "h.loop_activity": "Loop Activity",
    "h.locks": "Locks",
    "h.script_budget": "Script Budget",
    "h.timeline_dashboard": "Time Sink Dashboard",
    "h.search": "Search",
    "h.next_steps": "Next Steps",
    "h.action_log": "Action Log",
    "h.last_action": "Last Action",
    "h.system_status_raw": "System Status (raw)",
    "h.ui_snapshot_raw": "UI Snapshot (raw)",
    "search.placeholder": "Search (auto)",
    "search.scope.label": "Scope",
    "search.scope.ssot": "SSOT (fast)",
    "search.scope.repo": "Repo (full)",
    "search.mode.label": "Search mode",
    "search.mode.auto": "Auto",
    "search.mode.keyword": "Keyword (rg)",
    "search.mode.semantic": "Semantic (pgvector)",
    "search.run": "Search",
    "search.rebuild": "Update index",
    "search.status.idle": "Waiting for query.",
    "search.status.running": "Searching…",
    "search.status.done": "Results: {count} • mode={mode}",
    "search.status.error": "Search failed: {error}",
    "search.engine.none": "Engine: -",
    "search.engine.value": "Engine: {engine}",
    "search.engine.badge.none": "SRCH: -",
    "search.engine.badge.value": "SRCH: {engine}",
    "search.no_results": "No results.",
    "search.index.none": "Index: missing",
    "search.index.ready": "Index: {indexed_at} • files={files} • records={records} • adapter={adapter}",
    "search.index.building": "Index building: {done}/{total} • ETA={eta}",
    "search.index.building_scan": "Index building: scanning files…",
    "search.index.predicted": "Estimated build: {eta}",
    "search.index.refreshing": "Index update running…",
    "search.index.error": "Index update failed: {error}",
    "search.index.age": "Last update: {age}",
    "search.index.remaining": "Next refresh in: {remaining}",
    "search.capabilities.title": "Adapter Contract",
    "search.capabilities.status": "Contract: {contract} • scope={scope} • index={index}",
    "search.capabilities.routing": "Routing: auto={auto} • keyword={keyword} • semantic={semantic}",
    "search.capabilities.selection": "Fallback: keyword={keyword} • semantic={semantic}",
    "search.capabilities.loading": "Capabilities loading…",
    "search.capabilities.error": "Capabilities failed: {error}",
    "search.capabilities.adapters.none": "No adapter data.",
    "search.capabilities.adapters.header": "Adapter | Engine | Status | Tooling | Reason",
    "search.capabilities.semantic.none": "SEM: -",
    "search.capabilities.semantic.pending": "SEM: …",
    "search.capabilities.semantic.ready": "SEM: READY",
    "search.capabilities.semantic.unavailable": "SEM: UNAVAILABLE",
    "search.capabilities.semantic.failed": "SEM: ERROR",
    "search.capabilities.semantic.reason": "Semantic reason: {reason}",
    "timeline.refresh": "Refresh",
    "timeline.total_tool_time": "Total tool time",
    "timeline.process_count": "Process count",
    "timeline.process_p95": "Process p95",
    "timeline.non_tool_ratio": "Non-tool ratio",
    "timeline.slowest_processes": "Slowest processes",
    "timeline.tool_breakdown": "Tool breakdown",
    "timeline.meta": "generated={generated} • range={range} • events={events}",
    "timeline.pending": "Timeline report is loading…",
    "timeline.empty": "Timeline report is not available yet.",
    "timeline.group.dashboard": "Dashboard",
    "timeline.group.trend": "Trend",
    "timeline.tab.summary": "Summary",
    "timeline.tab.processes": "Processes",
    "timeline.tab.tools": "Tools",
    "timeline.tab.pctl": "P50 / P95",
    "timeline.tab.alerts": "Alerts",
    "timeline.process.meta": "Rows: {count} • Click a row to expand details",
    "timeline.tools.meta": "Rows: {count} • Aggregated by tool",
    "timeline.trend.meta": "Rolling window: last {window} cycles • points={count}",
    "timeline.trend.empty": "Not enough cycle data for trend chart.",
    "timeline.alert.idle": "TIME: -",
    "timeline.alert.ok": "TIME: OK",
    "timeline.alert.warn": "TIME: WARN",
    "timeline.alert.fail": "TIME: ALARM",
    "timeline.alert.details.none": "No threshold breach in current report.",
    "timeline.alert.details.non_tool": "Non-tool ratio {actual}% > {threshold}%",
    "timeline.alert.details.p95": "Process p95 {actual} > {threshold}",
    "timeline.table.started": "Started",
    "timeline.table.ended": "Ended",
    "timeline.table.duration": "Duration",
    "timeline.table.tool_total": "Tool",
    "timeline.table.non_tool": "Non-tool",
    "timeline.table.tool_calls": "Calls",
    "timeline.table.top_tool": "Top tool",
    "timeline.table.closed_by": "Closed by",
    "timeline.table.p50": "P50",
    "timeline.table.p95": "P95",
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
    "h.extension_usage": "Extension Usage",
    "extensions.detail.manifest": "Manifest",
    "extensions.detail.meta": "Meta",
    "extensions.detail.overrides": "Overrides",
    "extensions.detail.readme": "README",
    "extensions.detail.policies": "Policies",
    "extensions.detail.ops": "Ops metrics",
    "extensions.detail.about": "What it does",
    "extensions.detail.loading": "Loading…",
    "extensions.detail.empty": "No detail available.",
    "h.safe_overrides": "Safe Overrides",
    "h.edit_override": "Edit Override",
    "h.auto_loop": "Auto-loop",
    "h.airunner_jobs": "Airrunner Jobs",
    "h.github_ops_jobs": "GitHub Ops Jobs",
    "jobs.freshness_fresh": "GitHub Ops updated {age} ago",
    "jobs.freshness_stale": "GitHub Ops stale ({age} ago)",
    "jobs.freshness_missing": "GitHub Ops freshness unknown",
    "jobs.freshness_unknown": "unknown",
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
    "actions.chat_view": "Chat view",
    "actions.list_view": "List view",
    "actions.copy": "Copy",
    "actions.edit": "Edit",
    "actions.enable": "Enable",
    "actions.disable": "Disable",
    "actions.remove_tag": "Remove tag",
    "common.on": "on",
    "common.off": "off",
    "common.sample_parens": " (sample)",
    "common.unknown": "(unknown)",
    "chat.role.user": "You",
    "chat.role.assistant": "Assistant",
    "chat.thinking": "Assistant is typing...",
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
    "table.time": "Time",
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
    "table.path": "Path",
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
    "north_star.detail.lens_findings_hint": "Use “Lens Findings” to browse per-item matches; Workflow Stage shows Reference/Assessment/Gap.",
    "north_star.detail.evidence_expectations": "Evidence expectations",
    "north_star.detail.remediation_ideas": "Remediation ideas",
    "job.poll_failed": "Job poll failed: {error}",
    "job.poll_timeout": "Job polling timed out: {id}",
    "job.poll_timeout_short": "Job polling timed out: {id}",
    "job.started": "{op}: started (job {id})",
    "job.done": "{op}: {status}",
    "job.already_running": "{op}: already running (tracking {id})",
    "snapshot.started": "Snapshot is being prepared (job {id}). It will open in Notes when ready.",
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
    "status.memory": "MEM: {status}",
    "status.disconnected": "DISCONNECTED",
    "sidebar.workspace": "workspace: {path}",
    "sidebar.last_change": "last change: {ts}",
    "intake.field.topic": "Topic",
    "intake.field.why": "Why",
    "intake.field.purpose": "Purpose",
    "intake.field.necessity": "Necessity",
    "intake.field.compatibility": "Compatibility",
    "intake.field.why_required": "Why needed",
    "intake.field.implementation_note": "Implementation note",
    "intake.field.system_impact": "System impact",
    "intake.field.benefit": "Benefit",
    "intake.field.roi": "ROI",
    "intake.purpose.fallback_missing": "Not set (curation needed)",
    "intake.purpose.fallback_unknown": "Unknown",
    "intake.purpose.generate": "Generate purposes (AI)",
    "intake.purpose.generate_hint": "Missing only · OPEN scope · OpenAI",
    "intake.purpose.generate_selected": "Generate for selected",
    "intake.purpose.generate_selected_hint": "Selected item only",
    "intake.purpose.report.title": "Purpose generation report",
    "intake.purpose.report.none": "No report yet.",
    "intake.purpose.report.view": "View report",
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
    "intake.detail.tab_summary": "Summary",
    "intake.detail.tab_decision": "Decision",
    "intake.detail.tab_evidence": "Evidence",
    "intake.detail.tab_notes": "Notes",
    "intake.detail.tab_raw": "Raw JSON",
    "intake.group.summary": "Overview",
    "intake.group.decision": "Decision",
    "intake.group.evidence": "Evidence",
    "intake.group.raw": "Raw",
    "intake.decision.save": "Save",
    "intake.decision.note_placeholder": "Optional note…",
    "intake.decision.no_overlay": "No decision card available for this item.",
    "intake.compat.title": "Compatibility Summary",
    "intake.compat.banner_missing": "Compatibility summary unavailable (missing compat artifacts).",
    "intake.compat.blockers": "Top blockers",
    "intake.compat.none": "No blockers.",
    "intake.compat.meta": "Last updated: {ts} · Source: {source} · Loaded: {loaded}",
    "intake.compat.status_badge": "Status: {status}",
    "intake.compat.source_badge": "Source: {source}",
    "intake.compat.updated_badge": "Updated: {ts}",
    "intake.compat.loaded_badge": "Loaded: {ts}",
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
    "notes.links.header": "Evidence & Attachments",
    "notes.title_placeholder": "Title (optional)",
    "notes.tags_placeholder": "Tags (comma separated)",
    "select.none": "none",
    "select.no_verified_model": "no model",
    "chat.model.unverified": "doğrulanmadı",
    "chat.model.skeleton": "taslak/atlanır",
    "chat.allowlist_warn": "Allowlist UYARI: {fail} başarısız → doğrulanmayan modeller taslak/atlanır.",
    "notes.links.remove": "Remove",
    "notes.no_note_selected": "no note selected",
    "notes.prefill.context_header": "Context (from intake):",
    "notes.prefill.evidence_header": "Evidence paths:",
    "notes.prefill.next_header": "What do we want to do next?",
    "notes.prefill.next_placeholder": "- (write your plan / decision / rationale here)",
    "notes.prefill.none": "- (none)",
    "notes.snapshot.title": "[SNAPSHOT] {page}",
    "notes.snapshot.context_header": "Snapshot context:",
    "notes.snapshot.context_page": "- page: {page}",
    "notes.snapshot.context_hash": "- url: {hash}",
    "notes.snapshot.context_time": "- captured_at: {ts}",
    "notes.snapshot.evidence_header": "Snapshot evidence:",
    "overview.banner.no_intake": "No actionable intake. You may add a request.",
    "overview.banner.ready": "Ready. Use safe defaults or run a bounded loop.",
    "overview.banner.decisions_pending": "Decisions pending ({count}). Open Decisions.",
    "overview.multi_repo.summary": "Managed repos: {selected}/{total}, critical={critical}",
    "overview.multi_repo.critical_only": "Only critical",
    "overview.multi_repo.risk_line": "Risk: {value}",
    "overview.multi_repo.none": "No managed repositories configured.",
    "overview.multi_repo.error": "Managed repo status unavailable: {error}",
    "overview.multi_repo.refreshing": "Refreshing managed repository status…",
    "overview.multi_repo.status": "Repo status: {status}",
    "overview.next.decision_pending": "Decision pending: open Decisions tab.",
    "overview.next.no_intake": "No intake items. Check sources.",
    "overview.next.no_blockers": "No immediate blockers. Consider auto-loop or new intake.",
    "north_star.all_lenses": "All lenses",
    "north_star.lens_details_hint": "Expand a lens to see its details. Use “Lens Findings” below to explore per-item findings (match + evidence pointers) across lenses.",
    "north_star.select_lens_hint": "Select a lens to explore findings.",
    "north_star.mechanisms.title": "Theme / Subtheme Catalog",
    "north_star.mechanisms.empty": "No mechanisms registry loaded.",
    "north_star.mechanisms.meta": "subjects={count}",
    "north_star.mechanisms.filter.subject.placeholder": "Filter subject",
    "north_star.mechanisms.filter.subject_aria": "Filter mechanisms by subject",
    "north_star.mechanisms.filter.status.placeholder": "Filter status",
    "north_star.mechanisms.filter.status_aria": "Filter mechanisms by status",
    "north_star.mechanisms.filter.search.placeholder": "Search subject/theme/subtheme",
    "north_star.mechanisms.filter.search_aria": "Search mechanisms",
    "north_star.mechanisms.filter.version_aria": "Select version",
    "north_star.mechanisms.version.active": "Active (latest)",
    "north_star.mechanisms.status.active": "Active",
    "north_star.mechanisms.status.deprecated": "Deprecated",
    "north_star.mechanisms.status.hidden": "Hidden",
    "north_star.mechanisms.transfer_btn": "Send to findings",
    "north_star.mechanisms.transfer_title": "Apply as Lens Findings filter",
    "north_star.mechanisms.transfer_done": "Lens Findings scope added: {target}",
    "north_star.mechanisms.transfer_blocked_hint": "Lens transfer requires subject to be ACTIVE and approved.",
    "north_star.mechanisms.transfer_blocked_detail": "Lens transfer disabled: {reasons}",
    "north_star.mechanisms.transfer_reason_not_active": "Not active",
    "north_star.mechanisms.transfer_reason_not_approved": "Not approved",
    "north_star.mechanisms.matrix_toggle": "Show matrix",
    "north_star.mechanisms.matrix_title": "Subtheme Matrix (Reference/Assessment/Gap)",
    "north_star.mechanisms.matrix_meta": "criteria={count}",
    "north_star.mechanisms.matrix_empty": "No matrix rows found for this subtheme.",
    "north_star.mechanisms.matrix_col_criterion": "Criterion/Axis",
    "north_star.mechanisms.matrix_open_findings": "Open in findings",
    "north_star.mechanisms.matrix_open_title": "Apply Lens Findings filters for this stage and criterion.",
    "north_star.mechanisms.matrix_open_disabled": "Lens transfer requires subject to be ACTIVE and approved.",
    "north_star.mechanisms.matrix_focus_done": "Lens Findings filters updated from matrix.",
    "north_star.mechanisms.matrix_cell_counts": "items={items} trig={triggered} not={not_triggered} unk={unknown}",
    "north_star.export_mechanisms": "Export theme catalog (Excel)",
    "north_star.suggestions.title": "AI Suggestions",
    "north_star.suggestions.seed_btn": "Seed (GPT-5.2)",
    "north_star.suggestions.consult_btn": "Consult (LLM)",
    "north_star.suggestions.empty": "No suggestions available.",
    "north_star.suggestions.meta": "proposed={count}",
    "north_star.suggestions.accept": "Accept",
    "north_star.suggestions.reject": "Reject",
    "north_star.suggestions.merge": "Merge",
    "north_star.suggestions.modal_title": "AI note",
    "north_star.suggestions.modal_hint": "Optional context for AI suggestions.",
    "north_star.suggestions.modal_intent": "Intent",
    "north_star.suggestions.modal_intent_seed": "Seed → PROPOSED (no direct registry write)",
    "north_star.suggestions.modal_intent_consult": "Consult → PROPOSED (no direct registry write)",
    "north_star.suggestions.modal_intent_discuss": "Discuss → PROPOSED (no direct registry write)",
    "north_star.suggestions.modal_context_label": "Selection",
    "north_star.suggestions.modal_context_subject": "Subject",
    "north_star.suggestions.modal_context_theme": "Theme",
    "north_star.suggestions.modal_context_subtheme": "Subtheme",
    "north_star.suggestions.modal_comment": "Comment",
    "north_star.suggestions.modal_placeholder": "Add context or constraints for the AI suggestion (optional).",
    "north_star.suggestions.modal_profile": "Profile",
    "north_star.suggestions.modal_provider": "Provider",
    "north_star.suggestions.modal_model": "Model",
    "north_star.suggestions.modal_model_hint": "",
    "north_star.suggestions.modal_history_empty": "No messages yet.",
    "north_star.suggestions.modal_status_idle": "",
    "north_star.suggestions.modal_status_started": "Request sent. Waiting for response...",
    "north_star.suggestions.modal_status_done": "Consult completed.",
    "north_star.suggestions.modal_status_error": "Consult failed.",
    "north_star.suggestions.modal_merge_label": "Merge target theme_id",
    "north_star.suggestions.modal_cancel": "Cancel",
    "north_star.suggestions.modal_submit": "Submit",
    "north_star.suggestions.modal_open_chat": "Open chat",
    "north_star.catalog_create.title": "Catalog Builder",
    "north_star.catalog_create.hint": "Prompt: v0.4.8 (prompt_refine_consolidated)",
    "north_star.catalog_create.subject_label": "Topic",
    "north_star.catalog_create.subject_placeholder": "e.g., Internal Audit",
    "north_star.catalog_create.save": "Save",
    "north_star.catalog_create.create": "Create catalog",
    "north_star.catalog_create.meta_saved": "Saved topic: {subject} · thread: {thread}",
    "north_star.catalog_create.status_ready": "ready",
    "north_star.catalog_create.status_loading": "loading prompt…",
    "north_star.catalog_create.status_missing": "prompt not found",
    "north_star.catalog_create.modal_title": "Create Catalog",
    "north_star.catalog_create.modal_hint": "Edit the prompt if needed, then send via Planner Chat.",
    "north_star.catalog_create.modal_subject_label": "Topic",
    "north_star.catalog_create.modal_thread_label": "Thread",
    "north_star.catalog_create.modal_open_chat": "Open chat",
    "north_star.catalog_create.modal_send": "Send (LLM)",
    "north_star.catalog_create.modal_cancel": "Cancel",
    "planner_chat.suggestions.title": "Suggested next steps",
    "toast.catalog_subject_required": "Topic required.",
    "toast.catalog_prompt_missing": "Prompt template not found.",
    "toast.catalog_prompt_ready": "Catalog prompt prepared.",
    "toast.catalog_sent": "Catalog request sent.",
    "toast.catalog_prefilled": "Catalog prompt moved to chat.",

    "north_star.suggestions.comment_prompt": "Optional comment (why/what to adjust)",
    "north_star.suggestions.merge_prompt": "Merge target theme_id (optional)",
    "extensions.usage.search": "Search path/kind/extension",
    "extensions.usage.summary": "{matched}/{total} matched · unknown {unknown}",
    "extensions.usage.top": "Top extensions",
    "extensions.usage.trend": "7d usage trend",
    "extensions.usage.by_day": "Daily usage",
    "extensions.usage.by_day_empty": "No daily usage data.",
    "extensions.usage.select_placeholder": "Select",
    "extensions.usage.empty_hint": "No usage data yet. Try Refresh or run ops that emit logs.",
    "extensions.usage.no_data": "No usage data yet.",
    "extensions.usage.unknown_title": "Unknown samples",
    "extensions.usage.unused": "Unused extensions: {list}",
    "north_star.suggestions.ai_prompt": "AI comment (context for suggestions)",
    "north_star.suggestions.seed_confirm": "Seed themes with GPT-5.2? Output goes to PROPOSED only.",
    "north_star.suggestions.filter.search": "Search suggestions",
    "north_star.suggestions.filter.subject": "Subject",
    "north_star.suggestions.filter.theme": "Theme",
    "north_star.suggestions.filter.subtheme": "Subtheme",
    "north_star.suggestions.filter.multi_hint": "Use comma for multi-select",
    "north_star.suggestions.filter.type": "Suggestion type (missing/merge/too_many)",
    "north_star.suggestions.filter.date_from": "From",
    "north_star.suggestions.filter.date_to": "To",
    "north_star.suggestions.filter.quick.today": "Today",
    "north_star.suggestions.filter.quick.week": "Last 7 days",
    "north_star.suggestions.filter.quick.month": "Last 30 days",
    "north_star.suggestions.filter.quick.all": "All",
    "north_star.suggestions.discuss": "Discuss",
    "toast.export_mechanisms_ok": "Theme catalog exported to Excel ({count} rows).",
    "toast.export_mechanisms_empty": "Theme catalog has no rows to export.",
    "toast.export_mechanisms_failed": "Theme catalog export failed: {error}",
    "north_star.export.subject_id": "Subject ID",
    "north_star.export.subject_title_tr": "Subject (TR)",
    "north_star.export.subject_title_en": "Subject (EN)",
    "north_star.export.subject_status": "Subject Status",
    "north_star.export.subject_approval_required": "Approval Required",
    "north_star.export.subject_approval_mode": "Approval Mode",
    "north_star.export.subject_approved_at": "Approved At",
    "north_star.export.theme_id": "Theme ID",
    "north_star.export.theme_title_tr": "Theme (TR)",
    "north_star.export.theme_title_en": "Theme (EN)",
    "north_star.export.theme_definition_tr": "Theme Definition (TR)",
    "north_star.export.theme_definition_en": "Theme Definition (EN)",
    "north_star.export.subtheme_id": "Subtheme ID",
    "north_star.export.subtheme_title_tr": "Subtheme (TR)",
    "north_star.export.subtheme_title_en": "Subtheme (EN)",
    "north_star.export.subtheme_definition_tr": "Subtheme Definition (TR)",
    "north_star.export.subtheme_definition_en": "Subtheme Definition (EN)",
    "north_star.findings.search_placeholder": "Search findings (id/title/criterion/tag/reason)",
    "north_star.filter.subject.label": "Subject",
    "north_star.filter.subject.placeholder": "Select subject",
    "north_star.filter.perspective.label": "Perspective",
    "north_star.filter.perspective.placeholder": "Select perspective",
    "north_star.filter.theme.label": "Theme",
    "north_star.filter.theme.placeholder": "Select theme",
    "north_star.filter.subtheme.label": "Subtheme",
    "north_star.filter.subtheme.placeholder": "Select subtheme",
    "north_star.filter.topic.label": "Criterion/Axis",
    "north_star.filter.topic.placeholder": "Select criterion",
    "north_star.filter.catalog.label": "Workflow Stage (Reference/Assessment/Gap)",
    "north_star.filter.catalog.placeholder": "(optional)",
    "north_star.filter.match.label": "Trigger Status",
    "north_star.filter.match.placeholder": "Select match status",
    "north_star.findings.transfer_scopes.title": "Active transfer scopes",
    "north_star.findings.transfer_scopes.empty": "none",
    "north_star.findings.transfer_scopes.remove_title": "Remove scope",
    "north_star.findings.transfer_scopes.removed": "Transfer scope removed.",
    "actions.reset_filters": "Reset",
    "north_star.no_findings": "(no findings)",
    "north_star.unknown": "(unknown)",
    "north_star.table.lens": "Lens (Evaluation pack)",
    "north_star.table.match": "Match",
    "north_star.table.subject": "Subject",
    "north_star.table.topic": "Criterion/Axis",
    "north_star.table.domain": "Domain",
    "north_star.table.title": "Title",
    "north_star.table.theme": "Tema (Theme)",
    "north_star.table.subtheme": "Alt Tema (Subtheme)",
    "north_star.table.catalog": "Workflow Stage",
    "north_star.table.id": "ID",
    "north_star.table.reasons": "Reasons",
    "north_star.table.evidence": "Evidence",
    "north_star.join.banner": "Theme/Subtheme join missing for {miss} findings (title fallback {fallback}){reason}",
    "north_star.stage.reference": "Reference",
    "north_star.stage.assessment": "Assessment",
    "north_star.stage.gap": "Gap",
    "north_star.findings.scope_hint": "Reference / Assessment / Gap are workflow stages. Use the stage filter to classify findings.",
    "north_star.workflow.title": "North Star Workflow v1",
    "north_star.workflow.subtitle": "Canonical flow: Reference -> Assessment -> Gap -> PDCA",
    "north_star.workflow.step1": "Reference scope: Theme/Subtheme set is approved (ACTIVE).",
    "north_star.workflow.step2": "Criteria match: bind selected subtheme to default perspective criteria set.",
    "north_star.workflow.step3": "Reference synthesis: per criterion, collect world trends/best practices and write readable summary.",
    "north_star.workflow.step4": "Assessment synthesis: per criterion, map current-state evidence for the same subtheme.",
    "north_star.workflow.step5": "Gap synthesis: derive deterministic differences (reference vs current state) per criterion.",
    "north_star.workflow.step6": "Reading mode: use Lens Findings filters (stage + subject + theme + subtheme + criterion).",
    "north_star.workflow.step7": "PDCA: prioritize closure actions, recheck, and track regression.",
    "north_star.workflow.note": "Note: Workflow Stage is the single primary reading axis in Lens Findings.",
    "north_star.flow2.title": "Flow 2 Status",
    "north_star.flow2.subtitle": "Assessment chain health (Assessment + Policy + Status).",
    "north_star.flow2.assessment": "Assessment",
    "north_star.flow2.policy": "Policy-check",
    "north_star.flow2.system": "System-status",
    "north_star.flow2.project": "Project-status",
    "north_star.flow2.summary": "assessment_at={assessment_at} | system_at={system_at} | policy_inputs={policy_inputs}",
    "north_star.flow2.summary_missing": "Flow 2 telemetry files are missing.",
    "north_star.flow2.line.assessment": "Assessment: controls={controls} metrics={metrics} packs={packs}",
    "north_star.flow2.line.policy": "Policy-check: allow={allow} suspend={suspend} invalid={invalid} diff_nonzero={diff}",
    "north_star.flow2.line.system": "System-status: actions={actions} script_budget_fail={sb_fail} script_budget_warn={sb_warn}",
    "north_star.flow2.line.project": "Project-status: next_milestone={next_milestone} core_lock={core_lock}",
    "north_star.flow2.invalid_expected": "invalid_envelope expected: negative fixture sample ({file}).",
    "north_star.flow2.invalid_unexpected": "invalid_envelope detected outside known negative fixtures. Review examples before production runs.",
    "north_star.flow2.invalid_none": "invalid_envelope count is 0.",
    "north_star.perspective.locked_topics": "Perspective pack locked",
    "north_star.perspective.locked_hint": "Perspective pack is locked; topics are fixed.",
    "north_star.preset.custom": "Filter set (manual selection)",
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
    "empty.no_findings_transfer_scope": "No transferred catalog scope yet. Review catalog first, then transfer ACTIVE + approved entries to Lens Findings.",
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
    "theme.label": "Tema",
    "theme.dark": "Koyu",
    "theme.light": "Açık",
    "actions.refresh_all": "Tümünü Yenile",
    "actions.multi_repo_refresh": "Yönetilen repo durumu",
    "actions.snapshot_page": "Bu sayfayı snapshot al",
    "sidebar.toggle": "Sidebar’ı aç/kapat",
    "nav.primary": "Ana gezinme",
    "nav.overview": "Genel Bakış",
    "nav.north_star": "Kuzey Yıldızı",
    "nav.timeline": "Timeline",
    "nav.inbox": "Gelen Kutusu",
    "nav.intake": "İş Alımı",
    "nav.decisions": "Kararlar",
    "nav.extensions": "Eklentiler",
    "nav.overrides": "Override'lar",
    "nav.auto_loop": "Oto Döngü",
    "nav.jobs": "İşler",
    "nav.locks": "Kilitler",
    "nav.run_card": "Koşu Kartı",
    "nav.search": "Arama",
    "nav.planner_chat": "Planlayıcı Sohbet",
    "nav.command_composer": "Komut Oluşturucu",
    "nav.evidence": "Kanıt",
    "h.system_status": "Sistem Durumu",
    "h.multi_repo_status": "Yönetilen Reposu",
    "h.work_intake": "İş Alımı",
    "h.decisions": "Kararlar",
    "h.loop_activity": "Döngü Aktivitesi",
    "h.locks": "Kilitler",
    "h.script_budget": "Script Bütçesi",
    "h.timeline_dashboard": "Zaman Kaybı Panosu",
    "h.search": "Arama",
    "h.next_steps": "Sonraki Adımlar",
    "h.action_log": "Aksiyon Günlüğü",
    "h.last_action": "Son Aksiyon",
    "h.system_status_raw": "Sistem Durumu (ham)",
    "h.ui_snapshot_raw": "UI Snapshot (ham)",
    "search.placeholder": "Arama (otomatik)",
    "search.scope.label": "Kapsam",
    "search.scope.ssot": "SSOT (hızlı)",
    "search.scope.repo": "Tüm repo",
    "search.mode.label": "Arama modu",
    "search.mode.auto": "Oto",
    "search.mode.keyword": "Anahtar kelime (rg)",
    "search.mode.semantic": "Anlamsal (pgvector)",
    "search.run": "Ara",
    "search.rebuild": "Index güncelle",
    "search.status.idle": "Sorgu bekleniyor.",
    "search.status.running": "Aranıyor…",
    "search.status.done": "Sonuç: {count} • mod={mode}",
    "search.status.error": "Arama başarısız: {error}",
    "search.engine.none": "Motor: -",
    "search.engine.value": "Motor: {engine}",
    "search.engine.badge.none": "SRCH: -",
    "search.engine.badge.value": "SRCH: {engine}",
    "search.no_results": "Sonuç yok.",
    "search.index.none": "Index: yok",
    "search.index.ready": "Index: {indexed_at} • dosya={files} • kayıt={records} • adapter={adapter}",
    "search.index.building": "Index hazırlanıyor: {done}/{total} • ETA={eta}",
    "search.index.building_scan": "Index hazırlanıyor: dosyalar taranıyor…",
    "search.index.predicted": "Tahmini hazırlama: {eta}",
    "search.index.refreshing": "Index güncelleniyor…",
    "search.index.error": "Index güncelleme hatası: {error}",
    "search.index.age": "Son güncelleme: {age}",
    "search.index.remaining": "Kalan süre: {remaining}",
    "search.capabilities.title": "Adapter Kontratı",
    "search.capabilities.status": "Kontrat: {contract} • kapsam={scope} • index={index}",
    "search.capabilities.routing": "Yönlendirme: oto={auto} • keyword={keyword} • semantic={semantic}",
    "search.capabilities.selection": "Fallback: keyword={keyword} • semantic={semantic}",
    "search.capabilities.loading": "Capabilities yükleniyor…",
    "search.capabilities.error": "Capabilities hatası: {error}",
    "search.capabilities.adapters.none": "Adapter verisi yok.",
    "search.capabilities.adapters.header": "Adapter | Motor | Durum | Araç | Neden",
    "search.capabilities.semantic.none": "SEM: -",
    "search.capabilities.semantic.pending": "SEM: …",
    "search.capabilities.semantic.ready": "SEM: HAZIR",
    "search.capabilities.semantic.unavailable": "SEM: YOK",
    "search.capabilities.semantic.failed": "SEM: HATA",
    "search.capabilities.semantic.reason": "Semantic nedeni: {reason}",
    "timeline.refresh": "Yenile",
    "timeline.total_tool_time": "Toplam araç süresi",
    "timeline.process_count": "İşlem sayısı",
    "timeline.process_p95": "İşlem p95",
    "timeline.non_tool_ratio": "Araç dışı oran",
    "timeline.slowest_processes": "En yavaş işlemler",
    "timeline.tool_breakdown": "Araç kırılımı",
    "timeline.meta": "üretim={generated} • aralık={range} • olay={events}",
    "timeline.pending": "Timeline raporu hazırlanıyor…",
    "timeline.empty": "Timeline raporu henüz yok.",
    "timeline.group.dashboard": "Dashboard",
    "timeline.group.trend": "Trend",
    "timeline.tab.summary": "Özet",
    "timeline.tab.processes": "İşlemler",
    "timeline.tab.tools": "Araçlar",
    "timeline.tab.pctl": "P50 / P95",
    "timeline.tab.alerts": "Alarmlar",
    "timeline.process.meta": "Satır: {count} • Detay için satıra tıkla",
    "timeline.tools.meta": "Satır: {count} • Araç bazlı toplam",
    "timeline.trend.meta": "Hareketli pencere: son {window} işlem • nokta={count}",
    "timeline.trend.empty": "Trend grafiği için yeterli işlem verisi yok.",
    "timeline.alert.idle": "TIME: -",
    "timeline.alert.ok": "TIME: OK",
    "timeline.alert.warn": "TIME: WARN",
    "timeline.alert.fail": "TIME: ALARM",
    "timeline.alert.details.none": "Mevcut raporda eşik ihlali yok.",
    "timeline.alert.details.non_tool": "Araç dışı oran {actual}% > {threshold}%",
    "timeline.alert.details.p95": "İşlem p95 {actual} > {threshold}",
    "timeline.table.started": "Başlangıç",
    "timeline.table.ended": "Bitiş",
    "timeline.table.duration": "Süre",
    "timeline.table.tool_total": "Araç",
    "timeline.table.non_tool": "Araç dışı",
    "timeline.table.tool_calls": "Çağrı",
    "timeline.table.top_tool": "Ana araç",
    "timeline.table.closed_by": "Kapanış",
    "timeline.table.p50": "P50",
    "timeline.table.p95": "P95",
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
    "h.extension_usage": "Eklenti Kullanımı",
    "extensions.detail.manifest": "Manifest",
    "extensions.detail.meta": "Meta",
    "extensions.detail.overrides": "Override'lar",
    "extensions.detail.readme": "README",
    "extensions.detail.policies": "Policy",
    "extensions.detail.ops": "Ops metrikleri",
    "extensions.detail.about": "Ne işe yarar",
    "extensions.detail.loading": "Yükleniyor…",
    "extensions.detail.empty": "Detay yok.",
    "extensions.usage.search": "Yol/tür/eklenti ara",
    "extensions.usage.summary": "{matched}/{total} eşleşti · bilinmeyen {unknown}",
    "extensions.usage.top": "En çok kullanılanlar",
    "extensions.usage.trend": "7g kullanım trendi",
    "extensions.usage.by_day": "Günlük kullanım",
    "extensions.usage.by_day_empty": "Günlük kullanım verisi yok.",
    "extensions.usage.select_placeholder": "Seç",
    "extensions.usage.empty_hint": "Henüz kullanım verisi yok. Yenile veya ops çalıştır.",
    "extensions.usage.no_data": "Henüz kullanım verisi yok.",
    "extensions.usage.unknown_title": "Bilinmeyen örnekler",
    "extensions.usage.unused": "Kullanılmayan eklentiler: {list}",
    "h.safe_overrides": "Güvenli Override'lar",
    "h.edit_override": "Override Düzenle",
    "h.auto_loop": "Oto Döngü",
    "h.airunner_jobs": "Airrunner İşleri",
    "h.github_ops_jobs": "GitHub Ops İşleri",
    "jobs.freshness_fresh": "GitHub Ops güncellendi: {age} önce",
    "jobs.freshness_stale": "GitHub Ops eski ({age} önce)",
    "jobs.freshness_missing": "GitHub Ops güncellik bilgisi yok",
    "jobs.freshness_unknown": "bilinmiyor",
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
    "actions.chat_view": "Sohbet görünümü",
    "actions.list_view": "Liste görünümü",
    "actions.copy": "Kopyala",
    "actions.edit": "Düzenle",
    "actions.enable": "Etkinleştir",
    "actions.disable": "Devre dışı bırak",
    "actions.remove_tag": "Etiketi kaldır",
    "common.on": "açık",
    "common.off": "kapalı",
    "common.sample_parens": " (örnek)",
    "common.unknown": "(bilinmiyor)",
    "chat.role.user": "Sen",
    "chat.role.assistant": "Asistan",
    "chat.thinking": "Asistan yazıyor...",
    "chat.model.unverified": "doğrulanmadı",
    "chat.model.skeleton": "taslak/atlanır",
    "chat.allowlist_warn": "Allowlist UYARI: {fail} başarısız → doğrulanmayan modeller taslak/atlanır.",
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
    "table.time": "Zaman",
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
    "table.path": "Yol",
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
    "north_star.detail.lens_findings_hint": "“Lens Bulguları” ile bulguları incele; İş Akışı Aşaması sütunu Reference/Assessment/Gap gösterir.",
    "north_star.detail.evidence_expectations": "Kanıt beklentileri",
    "north_star.detail.remediation_ideas": "İyileştirme fikirleri",
    "job.poll_failed": "İş takibi başarısız: {error}",
    "job.poll_timeout": "İş takibi zaman aşımına uğradı: {id}",
    "job.poll_timeout_short": "İş takibi zaman aşımı: {id}",
    "job.started": "{op}: başlatıldı (iş {id})",
    "job.done": "{op}: {status}",
    "job.already_running": "{op}: zaten çalışıyor (takip: {id})",
    "snapshot.started": "Snapshot hazırlanıyor (iş {id}). Hazır olunca Notlar’da açılacak.",
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
    "status.memory": "MEM: {status}",
    "status.disconnected": "BAĞLI DEĞİL",
    "sidebar.workspace": "çalışma alanı: {path}",
    "sidebar.last_change": "son değişiklik: {ts}",
    "intake.field.topic": "Konu",
    "intake.field.why": "Neden",
    "intake.field.purpose": "Amaç",
    "intake.field.necessity": "Gereklilik",
    "intake.field.compatibility": "Uyumluluk",
    "intake.field.why_required": "Neden gerekli",
    "intake.field.implementation_note": "Uygulama notu",
    "intake.field.system_impact": "Sistem etkisi",
    "intake.field.benefit": "Getiri / Fayda",
    "intake.field.roi": "ROI (geri dönüş)",
    "intake.purpose.fallback_missing": "Belirtilmemiş (düzenleme gerekli)",
    "intake.purpose.fallback_unknown": "Bilinmiyor",
    "intake.purpose.generate": "Amaçları üret (AI)",
    "intake.purpose.generate_hint": "Yalnız eksikler · OPEN scope · OpenAI",
    "intake.purpose.generate_selected": "Seçili iş için üret",
    "intake.purpose.generate_selected_hint": "Yalnızca seçili iş",
    "intake.purpose.report.title": "Amaç üretim raporu",
    "intake.purpose.report.none": "Henüz rapor yok.",
    "intake.purpose.report.view": "Raporu görüntüle",
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
    "intake.detail.tab_summary": "Özet",
    "intake.detail.tab_decision": "Karar",
    "intake.detail.tab_evidence": "Kanıt",
    "intake.detail.tab_notes": "Notlar",
    "intake.detail.tab_raw": "Ham JSON",
    "intake.group.summary": "Genel",
    "intake.group.decision": "Karar",
    "intake.group.evidence": "Kanıt/Not",
    "intake.group.raw": "Ham",
    "intake.decision.save": "Kaydet",
    "intake.decision.note_placeholder": "İsteğe bağlı not…",
    "intake.decision.no_overlay": "Bu öğe için karar kartı yok.",
    "intake.compat.title": "Uyumluluk Özeti",
    "intake.compat.banner_missing": "Uyumluluk özeti alınamadı (compat artefaktları eksik).",
    "intake.compat.blockers": "En sık engeller",
    "intake.compat.none": "Engel yok.",
    "intake.compat.meta": "Son güncelleme: {ts} · Kaynak: {source} · Yüklendi: {loaded}",
    "intake.compat.status_badge": "Durum: {status}",
    "intake.compat.source_badge": "Kaynak: {source}",
    "intake.compat.updated_badge": "Güncellendi: {ts}",
    "intake.compat.loaded_badge": "Yüklendi: {ts}",
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
    "notes.links.header": "Kanıtlar & Ekler",
    "notes.title_placeholder": "Başlık (opsiyonel)",
    "notes.tags_placeholder": "Etiketler (virgülle)",
    "select.none": "yok",
    "select.no_verified_model": "model yok",
    "notes.links.remove": "Kaldır",
    "notes.no_note_selected": "not seçilmedi",
    "notes.prefill.context_header": "Bağlam (intake'den):",
    "notes.prefill.evidence_header": "Kanıt yolları:",
    "notes.prefill.next_header": "Sonraki adım ne olsun?",
    "notes.prefill.next_placeholder": "- (buraya plan / karar / gerekçe yazın)",
    "notes.prefill.none": "- (yok)",
    "notes.snapshot.title": "[SNAPSHOT] {page}",
    "notes.snapshot.context_header": "Snapshot bağlamı:",
    "notes.snapshot.context_page": "- sayfa: {page}",
    "notes.snapshot.context_hash": "- url: {hash}",
    "notes.snapshot.context_time": "- yakalama_zamanı: {ts}",
    "notes.snapshot.evidence_header": "Snapshot kanıtları:",
    "overview.banner.no_intake": "Aksiyonlanabilir intake yok. Yeni bir istek ekleyebilirsiniz.",
    "overview.banner.ready": "Hazır. Safe defaults kullanın veya sınırlı bir döngü çalıştırın.",
    "overview.banner.decisions_pending": "Bekleyen kararlar var ({count}). Kararlar sekmesini açın.",
    "overview.multi_repo.summary": "Yönetilen repo: {selected}/{total}, kritik={critical}",
    "overview.multi_repo.critical_only": "Sadece kritik",
    "overview.multi_repo.risk_line": "Risk: {value}",
    "overview.multi_repo.none": "Yönetilen repo tanımlı değil.",
    "overview.multi_repo.error": "Yönetilen repo durumu alınamadı: {error}",
    "overview.multi_repo.refreshing": "Yönetilen repo durumu yenileniyor…",
    "overview.multi_repo.status": "Repo durumu: {status}",
    "overview.next.decision_pending": "Bekleyen karar: Kararlar sekmesini açın.",
    "overview.next.no_intake": "İş alımı öğesi yok. Kaynakları kontrol edin.",
    "overview.next.no_blockers": "Acil engel yok. Oto döngü veya yeni intake düşünebilirsiniz.",
    "north_star.all_lenses": "Tüm lensler",
    "north_star.lens_details_hint": "Detayları görmek için bir lensi genişletin. Aşağıdaki “Lens Bulguları” ile lensler arasında bulguları (eşleşme + kanıt işaretçileri) keşfedin.",
    "north_star.select_lens_hint": "Bulgu keşfi için bir lens seçin.",
    "north_star.mechanisms.title": "Tema / Alt Tema Kataloğu",
    "north_star.mechanisms.empty": "Mekanizma kaydı yüklenmedi.",
    "north_star.mechanisms.meta": "konu_sayısı={count}",
    "north_star.mechanisms.filter.subject.placeholder": "Konu filtrele",
    "north_star.mechanisms.filter.subject_aria": "Konuya göre filtrele",
    "north_star.mechanisms.filter.status.placeholder": "Durum filtrele",
    "north_star.mechanisms.filter.status_aria": "Duruma göre filtrele",
    "north_star.mechanisms.filter.search.placeholder": "Konu/tema/alt tema ara",
    "north_star.mechanisms.filter.search_aria": "Mekanizma ara",
    "north_star.mechanisms.filter.version_aria": "Sürüm seç",
    "north_star.mechanisms.version.active": "Aktif (en güncel)",
    "north_star.mechanisms.status.active": "Aktif",
    "north_star.mechanisms.status.deprecated": "Arşiv (Deprecated)",
    "north_star.mechanisms.status.hidden": "Gizli",
    "north_star.mechanisms.transfer_btn": "Lens'e aktar",
    "north_star.mechanisms.transfer_title": "Lens Bulguları filtresine aktar",
    "north_star.mechanisms.transfer_done": "Lens Bulguları kapsamına eklendi: {target}",
    "north_star.mechanisms.transfer_blocked_hint": "Lens aktarımı için konu ACTIVE ve onaylı olmalı.",
    "north_star.mechanisms.transfer_blocked_detail": "Lens aktarımı devre dışı: {reasons}",
    "north_star.mechanisms.transfer_reason_not_active": "Aktif değil",
    "north_star.mechanisms.transfer_reason_not_approved": "Onaylı değil",
    "north_star.mechanisms.matrix_toggle": "Matrisi göster",
    "north_star.mechanisms.matrix_title": "Alt Tema Matrisi (Reference/Assessment/Gap)",
    "north_star.mechanisms.matrix_meta": "kriter={count}",
    "north_star.mechanisms.matrix_empty": "Bu alt tema için matrix satırı bulunamadı.",
    "north_star.mechanisms.matrix_col_criterion": "Kriter/Eksen",
    "north_star.mechanisms.matrix_open_findings": "Lens'te aç",
    "north_star.mechanisms.matrix_open_title": "Bu aşama ve kriter için Lens Bulguları filtrelerini uygula.",
    "north_star.mechanisms.matrix_open_disabled": "Lens aktarımı için konu ACTIVE ve onaylı olmalı.",
    "north_star.mechanisms.matrix_focus_done": "Lens Bulguları filtreleri matrixten güncellendi.",
    "north_star.mechanisms.matrix_cell_counts": "öğe={items} tetiklenen={triggered} tetiklenmeyen={not_triggered} bilinmeyen={unknown}",
    "north_star.export_mechanisms": "Tema kataloğunu dışa aktar (Excel)",
    "north_star.suggestions.title": "AI Önerileri",
    "north_star.suggestions.seed_btn": "Seed (GPT-5.2)",
    "north_star.suggestions.consult_btn": "İstişare (LLM)",
    "north_star.suggestions.empty": "Öneri yok.",
    "north_star.suggestions.meta": "öneri={count}",
    "north_star.suggestions.accept": "Kabul",
    "north_star.suggestions.reject": "Reddet",
    "north_star.suggestions.merge": "Birleştir",
    "north_star.suggestions.modal_title": "AI yorumu",
    "north_star.suggestions.modal_hint": "Öneri için opsiyonel bağlam.",
    "north_star.suggestions.modal_intent": "Niyet",
    "north_star.suggestions.modal_intent_seed": "Seed → PROPOSED (registry'ye doğrudan yazılmaz)",
    "north_star.suggestions.modal_intent_consult": "İstişare → PROPOSED (registry'ye doğrudan yazılmaz)",
    "north_star.suggestions.modal_intent_discuss": "İstişare → PROPOSED (registry'ye doğrudan yazılmaz)",
    "north_star.suggestions.modal_context_label": "Seçim",
    "north_star.suggestions.modal_context_subject": "Konu",
    "north_star.suggestions.modal_context_theme": "Tema",
    "north_star.suggestions.modal_context_subtheme": "Alt tema",
    "north_star.suggestions.modal_comment": "Yorum",
    "north_star.suggestions.modal_placeholder": "Öneri için ek bağlam/konstraint ekleyin (opsiyonel).",
    "north_star.suggestions.modal_profile": "Profil",
    "north_star.suggestions.modal_provider": "Sağlayıcı",
    "north_star.suggestions.modal_model": "Model",
    "north_star.suggestions.modal_model_hint": "",
    "north_star.suggestions.modal_history_empty": "Henüz mesaj yok.",
    "north_star.suggestions.modal_status_idle": "",
    "north_star.suggestions.modal_status_started": "İstek gönderildi. Yanıt bekleniyor...",
    "north_star.suggestions.modal_status_done": "İstişare tamamlandı.",
    "north_star.suggestions.modal_status_error": "İstişare başarısız.",
    "north_star.suggestions.modal_merge_label": "Birleştirme hedef theme_id",
    "north_star.suggestions.modal_cancel": "Vazgeç",
    "north_star.suggestions.modal_submit": "Gönder",
    "north_star.suggestions.modal_open_chat": "Sohbete git",
    "north_star.catalog_create.title": "Yeni Katalog Oluştur",
    "north_star.catalog_create.hint": "Prompt: v0.4.8 (prompt_refine_consolidated)",
    "north_star.catalog_create.subject_label": "Konu",
    "north_star.catalog_create.subject_placeholder": "Örn: İç Denetim",
    "north_star.catalog_create.save": "Kaydet",
    "north_star.catalog_create.create": "Katalog oluştur",
    "north_star.catalog_create.meta_saved": "Kayıtlı konu: {subject} · thread: {thread}",
    "north_star.catalog_create.status_ready": "hazır",
    "north_star.catalog_create.status_loading": "prompt yükleniyor…",
    "north_star.catalog_create.status_missing": "prompt bulunamadı",
    "north_star.catalog_create.modal_title": "Katalog Oluştur",
    "north_star.catalog_create.modal_hint": "Prompt metnini gerekirse düzenle, sonra Planner Chat ile gönder.",
    "north_star.catalog_create.modal_subject_label": "Konu",
    "north_star.catalog_create.modal_thread_label": "Thread",
    "north_star.catalog_create.modal_open_chat": "Sohbete taşı",
    "north_star.catalog_create.modal_send": "Gönder (LLM)",
    "north_star.catalog_create.modal_cancel": "Vazgeç",
    "planner_chat.suggestions.title": "Önerilen adımlar",
    "toast.catalog_subject_required": "Konu gerekli.",
    "toast.catalog_prompt_missing": "Prompt şablonu bulunamadı.",
    "toast.catalog_prompt_ready": "Katalog promptu hazır.",
    "toast.catalog_sent": "Katalog isteği gönderildi.",
    "toast.catalog_prefilled": "Katalog promptu sohbete taşındı.",
    "north_star.suggestions.comment_prompt": "Opsiyonel yorum (neden / nasıl)",
    "north_star.suggestions.merge_prompt": "Birleştirme hedef theme_id (opsiyonel)",
    "north_star.suggestions.ai_prompt": "AI yorumu (öneri için bağlam)",
    "north_star.suggestions.seed_confirm": "GPT-5.2 ile seed üretilsin mi? Çıktı sadece PROPOSED olur.",
    "north_star.suggestions.filter.search": "Öneri ara",
    "north_star.suggestions.filter.subject": "Konu",
    "north_star.suggestions.filter.theme": "Tema",
    "north_star.suggestions.filter.subtheme": "Alt tema",
    "north_star.suggestions.filter.multi_hint": "Çoklu seçim için virgül kullanın",
    "north_star.suggestions.filter.type": "Öneri türü (eksik/birleştir/çok)",
    "north_star.suggestions.filter.date_from": "Başlangıç",
    "north_star.suggestions.filter.date_to": "Bitiş",
    "north_star.suggestions.filter.quick.today": "Bugün",
    "north_star.suggestions.filter.quick.week": "Son 1 hafta",
    "north_star.suggestions.filter.quick.month": "Son 1 ay",
    "north_star.suggestions.filter.quick.all": "Tümü",
    "north_star.suggestions.discuss": "İstişare",
    "toast.export_mechanisms_ok": "Tema kataloğu Excel’e aktarıldı ({count} satır).",
    "toast.export_mechanisms_empty": "Tema kataloğunda dışa aktarılacak satır yok.",
    "toast.export_mechanisms_failed": "Tema kataloğu dışa aktarılamadı: {error}",
    "north_star.export.subject_id": "Konu ID",
    "north_star.export.subject_title_tr": "Konu (TR)",
    "north_star.export.subject_title_en": "Konu (EN)",
    "north_star.export.subject_status": "Konu Durumu",
    "north_star.export.subject_approval_required": "Onay Gerekli",
    "north_star.export.subject_approval_mode": "Onay Modu",
    "north_star.export.subject_approved_at": "Onay Tarihi",
    "north_star.export.theme_id": "Tema ID",
    "north_star.export.theme_title_tr": "Tema (TR)",
    "north_star.export.theme_title_en": "Tema (EN)",
    "north_star.export.theme_definition_tr": "Tema Tanımı (TR)",
    "north_star.export.theme_definition_en": "Tema Tanımı (EN)",
    "north_star.export.subtheme_id": "Alt Tema ID",
    "north_star.export.subtheme_title_tr": "Alt Tema (TR)",
    "north_star.export.subtheme_title_en": "Alt Tema (EN)",
    "north_star.export.subtheme_definition_tr": "Alt Tema Tanımı (TR)",
    "north_star.export.subtheme_definition_en": "Alt Tema Tanımı (EN)",
    "north_star.findings.search_placeholder": "Bulgu ara (id/başlık/kriter/etiket/gerekçe)",
    "north_star.filter.subject.label": "Konu",
    "north_star.filter.subject.placeholder": "Konu seç",
    "north_star.filter.perspective.label": "Bakış",
    "north_star.filter.perspective.placeholder": "Bakış seç",
    "north_star.filter.theme.label": "Tema",
    "north_star.filter.theme.placeholder": "Tema seç",
    "north_star.filter.subtheme.label": "Alt tema",
    "north_star.filter.subtheme.placeholder": "Alt tema seç",
    "north_star.filter.topic.label": "Kriter/Eksen",
    "north_star.filter.topic.placeholder": "Kriter seç",
    "north_star.filter.catalog.label": "İş Akışı Aşaması (Reference/Assessment/Gap)",
    "north_star.filter.catalog.placeholder": "(opsiyonel)",
    "north_star.filter.match.label": "Tetiklenme",
    "north_star.filter.match.placeholder": "Match durumu seç",
    "north_star.findings.transfer_scopes.title": "Aktif kapsamlar",
    "north_star.findings.transfer_scopes.empty": "yok",
    "north_star.findings.transfer_scopes.remove_title": "Kapsamı kaldır",
    "north_star.findings.transfer_scopes.removed": "Aktarım kapsamı kaldırıldı.",
    "north_star.no_findings": "(bulgu yok)",
    "north_star.unknown": "(bilinmiyor)",
    "north_star.table.lens": "Lens (Değerlendirme paketi)",
    "north_star.table.match": "Eşleşme",
    "north_star.table.subject": "Konu/Subject",
    "north_star.table.topic": "Kriter/Eksen",
    "north_star.table.domain": "Alan",
    "north_star.table.title": "Başlık",
    "north_star.table.theme": "Tema (Theme)",
    "north_star.table.subtheme": "Alt Tema (Subtheme)",
    "north_star.table.catalog": "İş Akışı Aşaması",
    "north_star.table.id": "ID",
    "north_star.table.reasons": "Gerekçeler",
    "north_star.table.evidence": "Kanıt",
    "north_star.join.banner": "Tema/Alt tema eşleşmesi {miss} bulguda yok (başlık eşleşmesi: {fallback}){reason}",
    "north_star.stage.reference": "Reference",
    "north_star.stage.assessment": "Assessment",
    "north_star.stage.gap": "Gap",
    "north_star.findings.scope_hint": "Referans / Assessment / Gap süreç aşamalarıdır. Aşağıdaki aşama filtresi bulguyu süreç aşamasına göre sınıflar.",
    "north_star.workflow.title": "North Star Workflow v1",
    "north_star.workflow.subtitle": "Canonical akış: Reference -> Assessment -> Gap -> PDCA",
    "north_star.workflow.step1": "Reference kapsamı: Theme/Subtheme setini onayla (ACTIVE).",
    "north_star.workflow.step2": "Kriter eşleştirme: Seçilen subtheme'i varsayılan bakış kriter setine bağla.",
    "north_star.workflow.step3": "Reference sentezi: Her kriter için dünyadaki trend/en iyi uygulama referanslarını topla ve okunabilir özet üret.",
    "north_star.workflow.step4": "Assessment sentezi: Aynı subtheme için her kriterde mevcut durum kanıtını haritala.",
    "north_star.workflow.step5": "Gap sentezi: Her kriterde referans ve mevcut durum farkını deterministik çıkar.",
    "north_star.workflow.step6": "Okuma modu: Lens Bulguları filtrelerini kullan (aşama + konu + tema + alt tema + kriter).",
    "north_star.workflow.step7": "PDCA: Kapatma aksiyonlarını önceliklendir, recheck çalıştır, regresyonu izle.",
    "north_star.workflow.note": "Not: Lens Bulguları'nda tek ana okuma ekseni İş Akışı Aşaması'dır.",
    "north_star.flow2.title": "2. Akış Durumu",
    "north_star.flow2.subtitle": "Assessment zinciri sağlığı (Assessment + Policy + Status).",
    "north_star.flow2.assessment": "Assessment",
    "north_star.flow2.policy": "Policy-check",
    "north_star.flow2.system": "System-status",
    "north_star.flow2.project": "Project-status",
    "north_star.flow2.summary": "assessment_at={assessment_at} | system_at={system_at} | policy_inputs={policy_inputs}",
    "north_star.flow2.summary_missing": "2. akış telemetri dosyaları bulunamadı.",
    "north_star.flow2.line.assessment": "Assessment: controls={controls} metrics={metrics} packs={packs}",
    "north_star.flow2.line.policy": "Policy-check: allow={allow} suspend={suspend} invalid={invalid} diff_nonzero={diff}",
    "north_star.flow2.line.system": "System-status: actions={actions} script_budget_fail={sb_fail} script_budget_warn={sb_warn}",
    "north_star.flow2.line.project": "Project-status: next_milestone={next_milestone} core_lock={core_lock}",
    "north_star.flow2.invalid_expected": "invalid_envelope beklenen durum: negatif fixture örneği ({file}).",
    "north_star.flow2.invalid_unexpected": "invalid_envelope bilinen negatif fixture dışında görünüyor. Üretim öncesi örnekleri inceleyin.",
    "north_star.flow2.invalid_none": "invalid_envelope sayısı 0.",
    "north_star.perspective.locked_topics": "Bakış seti kilitli",
    "north_star.perspective.locked_hint": "Bakış seti kilitli; kriterler sabittir.",
    "north_star.preset.custom": "Filtre seti (manuel seçim)",
    "north_star.preset.all": "Tümü (konu filtresi yok)",
    "north_star.preset.ethics_compliance": "Etik & Uyum",
    "north_star.preset.compliance_control": "Uyum / risk / güvence / kontrol",
    "north_star.preset.context_alignment": "Bağlam uyumu",
    "north_star.preset.sustainability_ethics": "Sürdürülebilirlik & Etik",
    "actions.reset_filters": "Sıfırla",
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
    "empty.no_findings_transfer_scope": "Henüz aktarılmış katalog kapsamı yok. Önce katalogu değerlendirin, sonra ACTIVE + onaylı kayıtları Lens Bulguları'na aktarın.",
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
  multiRepoStatus: "/api/multi-repo-status",
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
  search: "/api/search",
  searchIndex: "/api/search/index",
  searchCapabilities: "/api/search/capabilities",
  evidenceList: "/api/evidence/list",
  evidenceRead: "/api/evidence/read",
  evidenceRaw: "/api/evidence/raw",
  timeline: "/api/timeline",
  file: "/api/file",
  report: "/api/report",
  chat: "/api/chat",
  settingsSet: "/api/settings/set_override",
  extensionToggle: "/api/extensions/toggle",
};

const intakePurposePath = ".cache/ws_customer_default/.cache/index/work_intake_purpose.v1.json";
const intakePurposeReportPath = ".cache/ws_customer_default/.cache/reports/work_intake_purpose_generate.v0.1.json";
const intakePurposeReportMdPath = ".cache/ws_customer_default/.cache/reports/work_intake_purpose_generate.v0.1.md";
const chatProvidersRegistryPath = ".cache/ws_customer_default/.cache/providers/providers.v1.json";
const chatProviderAllowlistPath = ".cache/ws_customer_default/.cache/providers/provider_policy.v1.json";
const chatProviderPolicyWorkspacePath = ".cache/ws_customer_default/policies/policy_llm_providers_guardrails.v1.json";
const chatProviderPolicyRepoPath = "policies/policy_llm_providers_guardrails.v1.json";
const chatClassRegistryWorkspacePath = ".cache/ws_customer_default/.cache/index/llm_class_registry.v1.json";
const chatClassRegistryPath = "docs/OPERATIONS/llm_class_registry.v1.json";
const chatProviderMapWorkspacePath = ".cache/ws_customer_default/.cache/index/llm_provider_map.v1.json";
const chatProviderMapPath = "docs/OPERATIONS/llm_provider_map.v1.json";
const chatProbeCatalogPath = ".cache/ws_customer_default/.cache/index/llm_probe_catalog.v1.json";
const chatProbeStatePath = ".cache/ws_customer_default/.cache/state/llm_probe_state.v1.json";
const memoryHealthReportPath = ".cache/ws_customer_default/.cache/reports/memory_health.v1.json";
const northStarCriteriaPacksPath = "docs/OPERATIONS/north_star_criteria_packs.v1.json";
const northStarMechanismsRegistryPath = ".cache/ws_customer_default/.cache/index/mechanisms.registry.v1.json";
const northStarMechanismsSuggestionsPath = ".cache/ws_customer_default/.cache/index/mechanisms.suggestions.v1.json";
const northStarMechanismsHistoryPath = ".cache/ws_customer_default/.cache/index/mechanisms.registry.history.v1.json";
const northStarFlow2AssessmentPath = ".cache/ws_customer_default/.cache/index/assessment.v1.json";
const northStarFlow2PolicySimPath = ".cache/policy_check/sim_report.json";
const northStarFlow2PolicyDiffPath = ".cache/policy_check/policy_diff_report.json";
const northStarFlow2SystemStatusPath = ".cache/ws_customer_default/.cache/reports/system_status.v1.json";
const northStarFlow2ProjectStatusPath = ".cache/ws_customer_default/.cache/reports/project_status.v1.txt";
const extensionUsageReportPath = ".cache/reports/extension_usage_from_ops_log.v1.json";
const opsLogIndexPointerPath = ".cache/reports/ops_log_index_canonical_pointer.v0.3.json";
const promptRegistryPath = "registry/prompt_registry.v1.json";
const northStarPromptReportPath = ".cache/ws_customer_default/.cache/reports/prompt_refine_consolidated.v0.4.8.draft.md";
const CATALOG_DRAFT_STORAGE_KEY = "cockpit_north_star_catalog_draft.v1";

const state = {
  lang: "tr",
  theme: "dark",
  ws: null,
  overview: null,
  northStar: null,
  northStarFindings: null,
  northStarFindingsByLens: null,
  northStarFindingsSourceByLens: null,
  northStarFindingsTransferScopes: [],
  northStarFindingsLensName: "",
  northStarFindingSelected: null,
  northStarCatalogIndex: null,
  northStarCriteriaPacks: null,
  northStarMechanismsRegistry: null,
  northStarMechanismsSuggestions: null,
  northStarMechanismsHistory: null,
  northStarFlow2Status: null,
  northStarMatrices: {
    reference: null,
    assessment: null,
    gap: null,
  },
  catalogDraft: null,
  catalogPromptTemplate: null,
  catalogPromptSource: "",
  northStarFindingsJoinStats: null,
  status: null,
  snapshot: null,
  multiRepoStatus: null,
  multiRepoStatusError: "",
  multiRepoCriticalOnly: false,
  multiRepoStatusPending: false,
  inbox: null,
  intake: null,
  intakeSelectedId: null,
  intakeSelected: null,
  intakeExpandedId: null,
  intakeInlineTab: {},
  intakeInlineGroup: {},
  intakeEvidencePath: null,
  intakeEvidencePreview: null,
  intakePurposeIndex: null,
  intakePurposeIndexError: null,
  intakePurposeLoadedAt: null,
  intakePurposeReport: null,
  intakePurposeReportError: null,
  intakePurposeReportLoadedAt: null,
  intakeLinkedNotes: null,
  intakeLinkedNotesLoading: false,
  intakeLinkedNotesError: null,
  intakeClaimPending: false,
  intakeClosePending: false,
  notesView: "chat",
  chatProfile: "",
  chatProfileOptions: null,
  chatProvider: "",
  chatModel: "",
  chatProviderRegistry: null,
  chatProviderRegistryError: null,
  chatProviderClassMap: null,
  chatProviderClassMeta: null,
  memoryHealth: null,
  searchQuery: "",
  searchMode: "auto",
  searchScope: "ssot",
  searchLastMode: "",
  searchEngineDebug: "",
  searchResults: [],
  searchStatus: "",
  searchError: "",
  searchPending: false,
  searchIndex: null,
  searchIndexStatus: "",
  searchIndexError: "",
  searchIndexPending: false,
  searchCapabilities: null,
  searchCapabilitiesError: "",
  searchCapabilitiesPending: false,
  searchIndexAutoTimer: null,
  searchIndexPollTimer: null,
  searchIndexPollUntil: 0,
  searchRerunAfterIndex: false,
  timeline: null,
  timelineError: "",
  timelinePending: false,
  timelineViewGroup: "dashboard",
  timelineViewTab: {
    dashboard: "summary",
    trend: "trend_pctl",
  },
  timelineExpandedCycleKey: "",
  chatAllowlistSummary: null,
  aiSuggestProfile: "",
  aiSuggestProvider: "",
  aiSuggestModel: "",
  chatPending: null,
  chatStreamNoteId: null,
  chatStreamText: "",
  chatStreamIndex: 0,
  chatStreamTimer: null,
  chatStreamThread: "",
  chatLastAssistantNoteId: null,
  chatStreamItems: null,
  claimOwnerTag: null,
  decisions: null,
  extensions: null,
  extensionUsage: null,
  opsLogIndex: null,
  extensionUsageFilters: {
    search: "",
    extension: "",
    kind: "",
  },
  extensionDetail: null,
  extensionDetailExpanded: "",
  extensionDetailExtras: {},
  extensionDetailExtrasLoading: "",
  overrides: null,
  overridesDetail: null,
  overridesSelected: null,
  jobs: null,
  airunnerJobs: null,
  githubOpsPollInFlight: false,
  githubOpsPollFailures: 0,
  githubOpsAutoPollTimer: null,
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
  intakeCompatSummary: {
    ok: false,
    loaded_at: null,
    counts: null,
    top_blockers: [],
    updated_at_iso: null,
    source_name: null,
    loaded_at_iso: null,
    error: null,
    source: null,
  },
  intakeCompatSummaryLoading: false,
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
    northStarMechanisms: {},
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
      perspective: [],
      subject: [],
      topic: [],
      theme: [],
      subtheme: [],
      match: [],
      catalog: [],
      topic_locked_by_perspective: false,
    },
    northStarMechanisms: {
      search: "",
      subject: [],
      status: [],
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
      perspective: [],
      subject: [],
      topic: [],
      theme: [],
      subtheme: [],
      match: ["TRIGGERED", "NOT_TRIGGERED", "UNKNOWN"],
      catalog: ["reference", "assessment", "gap"],
    },
    northStarMechanisms: {
      subject: [],
      status: ["ACTIVE", "DEPRECATED", "HIDDEN"],
    },
  },
};

let northStarFindingsUiAttached = false;
let northStarFindingsControlsAttached = false;
let northStarMechanismsControlsAttached = false;

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

async function fetchNorthStarCriteriaPacks() {
  try {
    const data = await fetchOptionalJson(northStarCriteriaPacksPath);
    return unwrap(data || {});
  } catch (err) {
    showToast(t("toast.refresh_failed", { name: "north_star_criteria_packs", error: formatError(err) }), "warn");
    return null;
  }
}

async function fetchNorthStarMechanismsRegistry() {
  try {
    const data = await fetchOptionalJson(northStarMechanismsRegistryPath);
    return unwrap(data || {});
  } catch (err) {
    showToast(t("toast.refresh_failed", { name: "north_star_mechanisms_registry", error: formatError(err) }), "warn");
    return null;
  }
}

async function fetchNorthStarMechanismsSuggestions() {
  try {
    const data = await fetchOptionalJson(northStarMechanismsSuggestionsPath);
    return unwrap(data || {});
  } catch (err) {
    showToast(t("toast.refresh_failed", { name: "north_star_mechanisms_suggestions", error: formatError(err) }), "warn");
    return null;
  }
}

async function fetchNorthStarMechanismsHistory() {
  try {
    const data = await fetchOptionalJson(northStarMechanismsHistoryPath);
    return unwrap(data || {});
  } catch (err) {
    showToast(t("toast.refresh_failed", { name: "north_star_mechanisms_history", error: formatError(err) }), "warn");
    return null;
  }
}

function normalizeNorthStarStatusToken(raw, fallback = "UNKNOWN") {
  const norm = String(raw || "").trim().toUpperCase();
  if (!norm) return String(fallback || "UNKNOWN").trim().toUpperCase() || "UNKNOWN";
  if (norm.includes("FAIL")) return "FAIL";
  if (norm.includes("WARN")) return "WARN";
  if (norm.includes("OK") || norm.includes("PASS")) return "OK";
  if (norm.includes("PENDING") || norm.includes("RUNNING")) return "PENDING";
  if (norm.includes("IDLE")) return "IDLE";
  return norm;
}

function mergeNorthStarStatuses(statuses) {
  const normalized = (Array.isArray(statuses) ? statuses : [])
    .map((item) => normalizeNorthStarStatusToken(item, "UNKNOWN"))
    .filter((item) => item !== "UNKNOWN");
  if (!normalized.length) return "UNKNOWN";
  if (normalized.some((item) => item === "FAIL")) return "FAIL";
  if (normalized.some((item) => item === "WARN")) return "WARN";
  if (normalized.some((item) => item === "PENDING")) return "PENDING";
  if (normalized.some((item) => item === "IDLE")) return "IDLE";
  if (normalized.some((item) => item === "OK")) return "OK";
  return normalized[0] || "UNKNOWN";
}

function toSafeInt(value, fallback = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return Math.trunc(num);
}

function parseNorthStarProjectStatusText(rawText) {
  const out = {
    status: "UNKNOWN",
    overall: "UNKNOWN",
    next_milestone: "",
    core_lock: "",
    parsed: false,
  };
  const text = String(rawText || "");
  if (!text.trim()) return out;
  const lines = text
    .split(/\r?\n/)
    .map((line) => String(line || "").trim())
    .filter(Boolean);

  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i];
    if (!line.startsWith("{")) continue;
    try {
      const obj = JSON.parse(line);
      out.status = normalizeNorthStarStatusToken(obj?.status || out.status);
      out.overall = normalizeNorthStarStatusToken(obj?.overall || obj?.overall_status || out.overall);
      out.next_milestone = String(obj?.next_milestone || "");
      out.core_lock = String(obj?.core_lock || "");
      out.parsed = true;
      return out;
    } catch (_) {
      // Continue to line-based parsing.
    }
  }

  const resultLine = lines.find((line) => line.startsWith("status=")) || "";
  const previewLine = lines.find((line) => line.startsWith("next_milestone=")) || "";
  const statusMatch = resultLine.match(/\bstatus=([^\s]+)/i);
  const overallMatch = resultLine.match(/\boverall=([^\s]+)/i);
  const milestoneMatch = previewLine.match(/\bnext_milestone=([^\s]+)/i);
  const coreLockMatch = resultLine.match(/\bcore_lock=([^\s]+)/i);
  if (statusMatch) out.status = normalizeNorthStarStatusToken(statusMatch[1]);
  if (overallMatch) out.overall = normalizeNorthStarStatusToken(overallMatch[1]);
  if (milestoneMatch) out.next_milestone = String(milestoneMatch[1] || "");
  if (coreLockMatch) out.core_lock = String(coreLockMatch[1] || "");
  out.parsed = Boolean(statusMatch || overallMatch || milestoneMatch || coreLockMatch);
  return out;
}

async function fetchNorthStarFlow2Status() {
  const [assessmentPayload, policySimPayload, policyDiffPayload, systemStatusPayload, projectStatusText] = await Promise.all([
    fetchOptionalJson(northStarFlow2AssessmentPath),
    fetchOptionalJson(northStarFlow2PolicySimPath),
    fetchOptionalJson(northStarFlow2PolicyDiffPath),
    fetchOptionalJson(northStarFlow2SystemStatusPath),
    fetchReportText(northStarFlow2ProjectStatusPath),
  ]);

  const assessment = unwrap(assessmentPayload || {}) || {};
  const policySim = unwrap(policySimPayload || {}) || {};
  const policyDiff = unwrap(policyDiffPayload || {}) || {};
  const systemStatus = unwrap(systemStatusPayload || {}) || {};
  const projectStatus = parseNorthStarProjectStatusText(projectStatusText || "");

  const assessmentStatus = normalizeNorthStarStatusToken(assessment?.status || "UNKNOWN");
  const assessmentControls = toSafeInt(assessment?.controls, 0);
  const assessmentMetrics = toSafeInt(assessment?.metrics, 0);
  const assessmentPacks = toSafeInt(assessment?.packs, 0);
  const assessmentGeneratedAt = String(assessment?.generated_at || "");

  const counts = policySim && typeof policySim.counts === "object" ? policySim.counts : {};
  const allowCount = toSafeInt(counts?.allow, 0);
  const suspendCount = toSafeInt(counts?.suspend, 0);
  const blockUnknownCount = toSafeInt(counts?.block_unknown_intent, 0);
  const invalidEnvelopeCount = toSafeInt(counts?.invalid_envelope, 0);
  const diffNonzero = toSafeInt(policyDiff?.diff_nonzero, 0);
  const policyStatus = normalizeNorthStarStatusToken(
    policySim?.status ||
      (invalidEnvelopeCount > 0 || suspendCount > 0 || blockUnknownCount > 0 || diffNonzero > 0 ? "WARN" : "OK"),
    "UNKNOWN"
  );
  const thresholdUsed = Number.isFinite(Number(policySim?.threshold_used)) ? Number(policySim.threshold_used) : null;
  const totalInputs = toSafeInt(policySim?.total_inputs, 0);

  const actionsTop =
    systemStatus && typeof systemStatus === "object" && Array.isArray(systemStatus?.sections?.actions?.top)
      ? systemStatus.sections.actions.top
      : [];
  const scriptBudgetActions = actionsTop.filter(
    (item) => item && typeof item === "object" && String(item.kind || "").trim().toUpperCase() === "SCRIPT_BUDGET"
  );
  const scriptBudgetFailCount = scriptBudgetActions.filter((item) =>
    normalizeNorthStarStatusToken(item?.severity || "") === "FAIL"
  ).length;
  const scriptBudgetWarnCount = scriptBudgetActions.filter((item) =>
    normalizeNorthStarStatusToken(item?.severity || "") === "WARN"
  ).length;
  const systemOverall = normalizeNorthStarStatusToken(systemStatus?.overall_status || systemStatus?.status || "UNKNOWN");
  const systemGeneratedAt = String(systemStatus?.generated_at || "");
  const systemActionsCount = toSafeInt(systemStatus?.sections?.actions?.actions_count, actionsTop.length);

  const projectOverall = normalizeNorthStarStatusToken(projectStatus.overall || projectStatus.status || "UNKNOWN");
  const nextMilestone = String(projectStatus.next_milestone || "");
  const coreLock = String(projectStatus.core_lock || "");

  const invalidExamples =
    policySim && typeof policySim === "object" && Array.isArray(policySim?.examples?.invalid_envelope)
      ? policySim.examples.invalid_envelope
      : [];
  const invalidSampleFile = invalidExamples.length ? String(invalidExamples[0]?.file || "") : "";
  const invalidExpectedFixture =
    invalidEnvelopeCount > 0 &&
    invalidExamples.length > 0 &&
    invalidExamples.every((row) => {
      const file = String(row?.file || "");
      return file.startsWith("fixtures/envelopes/") && file.includes("_invalid");
    });

  const overallStatus = mergeNorthStarStatuses([assessmentStatus, policyStatus, systemOverall, projectOverall]);
  const available = Boolean(assessmentPayload || policySimPayload || systemStatusPayload || (projectStatusText || "").trim());

  return {
    available,
    refreshed_at: new Date().toISOString(),
    overall_status: overallStatus,
    assessment: {
      status: assessmentStatus,
      controls: assessmentControls,
      metrics: assessmentMetrics,
      packs: assessmentPacks,
      generated_at: assessmentGeneratedAt,
    },
    policy: {
      status: policyStatus,
      allow: allowCount,
      suspend: suspendCount,
      block_unknown_intent: blockUnknownCount,
      invalid_envelope: invalidEnvelopeCount,
      diff_nonzero: diffNonzero,
      threshold_used: thresholdUsed,
      total_inputs: totalInputs,
    },
    system: {
      status: systemOverall,
      generated_at: systemGeneratedAt,
      actions_count: systemActionsCount,
      script_budget_fail_count: scriptBudgetFailCount,
      script_budget_warn_count: scriptBudgetWarnCount,
    },
    project: {
      status: projectOverall,
      next_milestone: nextMilestone,
      core_lock: coreLock,
      parsed: projectStatus.parsed,
    },
    invalid_envelope: {
      count: invalidEnvelopeCount,
      expected_fixture: invalidExpectedFixture,
      sample_file: invalidSampleFile,
    },
  };
}

function xmlEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function encodeUtf8(text) {
  return new TextEncoder().encode(String(text ?? ""));
}

function crc32(buf) {
  let crc = -1;
  for (let i = 0; i < buf.length; i += 1) {
    crc = (crc >>> 8) ^ CRC32_TABLE[(crc ^ buf[i]) & 0xff];
  }
  return (crc ^ -1) >>> 0;
}

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c >>> 0;
  }
  return table;
})();

function toDosDateTime(date = new Date()) {
  const d = date;
  const dosTime = ((d.getHours() & 0x1f) << 11) | ((d.getMinutes() & 0x3f) << 5) | ((d.getSeconds() / 2) & 0x1f);
  const dosDate = (((d.getFullYear() - 1980) & 0x7f) << 9) | (((d.getMonth() + 1) & 0xf) << 5) | (d.getDate() & 0x1f);
  return { dosTime: dosTime & 0xffff, dosDate: dosDate & 0xffff };
}

function buildZip(files) {
  const fileRecords = [];
  let offset = 0;
  const parts = [];
  const { dosDate, dosTime } = toDosDateTime();

  files.forEach((file) => {
    const nameBytes = encodeUtf8(file.name);
    const dataBytes = typeof file.data === "string" ? encodeUtf8(file.data) : new Uint8Array(file.data);
    const crc = crc32(dataBytes);
    const localHeader = new Uint8Array(30 + nameBytes.length);
    const view = new DataView(localHeader.buffer);
    view.setUint32(0, 0x04034b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 0, true);
    view.setUint16(8, 0, true);
    view.setUint16(10, dosTime, true);
    view.setUint16(12, dosDate, true);
    view.setUint32(14, crc, true);
    view.setUint32(18, dataBytes.length, true);
    view.setUint32(22, dataBytes.length, true);
    view.setUint16(26, nameBytes.length, true);
    view.setUint16(28, 0, true);
    localHeader.set(nameBytes, 30);
    parts.push(localHeader, dataBytes);
    fileRecords.push({
      nameBytes,
      crc,
      size: dataBytes.length,
      offset,
      dosDate,
      dosTime,
    });
    offset += localHeader.length + dataBytes.length;
  });

  const centralParts = [];
  let centralSize = 0;
  fileRecords.forEach((rec) => {
    const header = new Uint8Array(46 + rec.nameBytes.length);
    const view = new DataView(header.buffer);
    view.setUint32(0, 0x02014b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 20, true);
    view.setUint16(8, 0, true);
    view.setUint16(10, 0, true);
    view.setUint16(12, rec.dosTime, true);
    view.setUint16(14, rec.dosDate, true);
    view.setUint32(16, rec.crc, true);
    view.setUint32(20, rec.size, true);
    view.setUint32(24, rec.size, true);
    view.setUint16(28, rec.nameBytes.length, true);
    view.setUint16(30, 0, true);
    view.setUint16(32, 0, true);
    view.setUint16(34, 0, true);
    view.setUint16(36, 0, true);
    view.setUint32(38, 0, true);
    view.setUint32(42, rec.offset, true);
    header.set(rec.nameBytes, 46);
    centralParts.push(header);
    centralSize += header.length;
  });

  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, fileRecords.length, true);
  endView.setUint16(10, fileRecords.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, offset, true);
  endView.setUint16(20, 0, true);

  const blobParts = [...parts, ...centralParts, end];
  return new Blob(blobParts, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
}

function buildXlsx(rows, columns) {
  const sheetRows = [];
  const headerCells = columns.map((col, idx) => {
    const cellRef = String.fromCharCode(65 + idx) + "1";
    return `<c r="${cellRef}" t="inlineStr"><is><t>${xmlEscape(col.label)}</t></is></c>`;
  });
  sheetRows.push(`<row r="1">${headerCells.join("")}</row>`);
  rows.forEach((row, rowIdx) => {
    const r = rowIdx + 2;
    const cells = columns.map((col, colIdx) => {
      const cellRef = String.fromCharCode(65 + colIdx) + String(r);
      return `<c r="${cellRef}" t="inlineStr"><is><t>${xmlEscape(row[col.key])}</t></is></c>`;
    });
    sheetRows.push(`<row r="${r}">${cells.join("")}</row>`);
  });

  const sheetXml = `<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    ${sheetRows.join("")}
  </sheetData>
</worksheet>`;

  const workbookXml = `<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="ThemeCatalog" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>`;

  const contentTypesXml = `<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`;

  const relsXml = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;

  const workbookRelsXml = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`;

  const files = [
    { name: "[Content_Types].xml", data: contentTypesXml },
    { name: "_rels/.rels", data: relsXml },
    { name: "xl/workbook.xml", data: workbookXml },
    { name: "xl/_rels/workbook.xml.rels", data: workbookRelsXml },
    { name: "xl/worksheets/sheet1.xml", data: sheetXml },
  ];

  return buildZip(files);
}

function downloadBlobFile(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
    link.remove();
  }, 0);
}

function flattenMechanismsRegistry(registry) {
  const rows = [];
  const subjects = Array.isArray(registry?.subjects) ? registry.subjects : [];
  subjects.forEach((subject) => {
    const subjectId = String(subject?.subject_id || "");
    const subjectTitleTr = String(subject?.subject_title_tr || "");
    const subjectTitleEn = String(subject?.subject_title_en || "");
    const subjectStatus = String(subject?.status || "");
    const subjectApprovalRequired = String(subject?.approval_required ?? "");
    const subjectApprovalMode = String(subject?.approval_mode || "");
    const subjectApprovedAt = String(subject?.approved_at || "");
    const themes = Array.isArray(subject?.themes) ? subject.themes : [];
    if (!themes.length) {
      rows.push({
        subject_id: subjectId,
        subject_title_tr: subjectTitleTr,
        subject_title_en: subjectTitleEn,
        subject_status: subjectStatus,
        subject_approval_required: subjectApprovalRequired,
        subject_approval_mode: subjectApprovalMode,
        subject_approved_at: subjectApprovedAt,
        theme_id: "",
        theme_title_tr: "",
        theme_title_en: "",
        theme_definition_tr: "",
        theme_definition_en: "",
        subtheme_id: "",
        subtheme_title_tr: "",
        subtheme_title_en: "",
        subtheme_definition_tr: "",
        subtheme_definition_en: "",
      });
      return;
    }
    themes.forEach((theme) => {
      const themeId = String(theme?.theme_id || "");
      const themeTitleTr = String(theme?.title_tr || "");
      const themeTitleEn = String(theme?.title_en || "");
      const themeDefTr = String(theme?.definition_tr || "");
      const themeDefEn = String(theme?.definition_en || "");
      const subthemes = Array.isArray(theme?.subthemes) ? theme.subthemes : [];
      if (!subthemes.length) {
        rows.push({
          subject_id: subjectId,
          subject_title_tr: subjectTitleTr,
          subject_title_en: subjectTitleEn,
          subject_status: subjectStatus,
          subject_approval_required: subjectApprovalRequired,
          subject_approval_mode: subjectApprovalMode,
          subject_approved_at: subjectApprovedAt,
          theme_id: themeId,
          theme_title_tr: themeTitleTr,
          theme_title_en: themeTitleEn,
          theme_definition_tr: themeDefTr,
          theme_definition_en: themeDefEn,
          subtheme_id: "",
          subtheme_title_tr: "",
          subtheme_title_en: "",
          subtheme_definition_tr: "",
          subtheme_definition_en: "",
        });
        return;
      }
      subthemes.forEach((subtheme) => {
        rows.push({
          subject_id: subjectId,
          subject_title_tr: subjectTitleTr,
          subject_title_en: subjectTitleEn,
          subject_status: subjectStatus,
          subject_approval_required: subjectApprovalRequired,
          subject_approval_mode: subjectApprovalMode,
          subject_approved_at: subjectApprovedAt,
          theme_id: themeId,
          theme_title_tr: themeTitleTr,
          theme_title_en: themeTitleEn,
          theme_definition_tr: themeDefTr,
          theme_definition_en: themeDefEn,
          subtheme_id: String(subtheme?.subtheme_id || ""),
          subtheme_title_tr: String(subtheme?.title_tr || ""),
          subtheme_title_en: String(subtheme?.title_en || ""),
          subtheme_definition_tr: String(subtheme?.definition_tr || ""),
          subtheme_definition_en: String(subtheme?.definition_en || ""),
        });
      });
    });
  });
  return rows;
}

async function exportMechanismsCatalog() {
  try {
    let registry = unwrap(state.northStarMechanismsRegistry || {});
    if (!registry || !Array.isArray(registry.subjects)) {
      registry = await fetchNorthStarMechanismsRegistry();
      if (registry) state.northStarMechanismsRegistry = registry;
    }
    registry = unwrap(registry || {});
    updateNorthStarMechanismsFilterOptions(registry, state.northStarMechanismsHistory);
    const filteredSubjects = getFilteredMechanismsSubjects(registry);
    const rows = flattenMechanismsRegistry({ ...registry, subjects: filteredSubjects });
    if (!rows.length) {
      showToast(t("toast.export_mechanisms_empty"), "warn");
      return;
    }
    const baseColumns = [
      { key: "subject_id", label: t("north_star.export.subject_id") },
      { key: "subject_status", label: t("north_star.export.subject_status") },
      { key: "subject_approval_required", label: t("north_star.export.subject_approval_required") },
      { key: "subject_approval_mode", label: t("north_star.export.subject_approval_mode") },
      { key: "subject_approved_at", label: t("north_star.export.subject_approved_at") },
      { key: "theme_id", label: t("north_star.export.theme_id") },
      { key: "subtheme_id", label: t("north_star.export.subtheme_id") },
    ];
    const lang = state.lang === "en" ? "en" : "tr";
    const langColumns =
      lang === "tr"
        ? [
            { key: "subject_title_tr", label: t("north_star.export.subject_title_tr") },
            { key: "theme_title_tr", label: t("north_star.export.theme_title_tr") },
            { key: "theme_definition_tr", label: t("north_star.export.theme_definition_tr") },
            { key: "subtheme_title_tr", label: t("north_star.export.subtheme_title_tr") },
            { key: "subtheme_definition_tr", label: t("north_star.export.subtheme_definition_tr") },
          ]
        : [
            { key: "subject_title_en", label: t("north_star.export.subject_title_en") },
            { key: "theme_title_en", label: t("north_star.export.theme_title_en") },
            { key: "theme_definition_en", label: t("north_star.export.theme_definition_en") },
            { key: "subtheme_title_en", label: t("north_star.export.subtheme_title_en") },
            { key: "subtheme_definition_en", label: t("north_star.export.subtheme_definition_en") },
          ];
    const columns = [...baseColumns.slice(0, 1), ...langColumns, ...baseColumns.slice(1)];
    const stamp = formatTimestamp(registry?.generated_at || "") || new Date().toISOString().slice(0, 10);
    const safeStamp = String(stamp).replace(/[:\\s]/g, "-");
    const xlsxBlob = buildXlsx(rows, columns);
    downloadBlobFile(`theme_subtheme_catalog_${safeStamp}.xlsx`, xlsxBlob);
    showToast(t("toast.export_mechanisms_ok", { count: String(rows.length) }), "ok");
  } catch (err) {
    showToast(t("toast.export_mechanisms_failed", { error: formatError(err) }), "fail");
  }
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

function renderPlainText(el, text) {
  if (!el) return;
  const raw = String(text || "");
  el.textContent = raw.length > 8000 ? raw.slice(0, 8000) + "\n..." : raw;
}

function normalizeAboutSummary(text) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  if (raw.toLowerCase() === "skeleton_only") return "İskelet/şablon; üretim fonksiyonu sınırlı.";
  return raw.replace(/_/g, " ");
}

function buildPolicyLabelList(policies, limit = 3) {
  const list = Array.isArray(policies) ? policies : [];
  const names = list.map((p) => String(p || "").split("/").slice(-1)[0]).filter(Boolean);
  if (!names.length) return "Yok";
  const shown = names.slice(0, limit).join(", ");
  return names.length > limit ? `${shown} +${names.length - limit}` : shown;
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

function readThemeFromStorage(key, defaultValue = "dark") {
  let v = defaultValue;
  try {
    const raw = localStorage.getItem(String(key));
    if (raw !== null && raw !== undefined && raw !== "") v = String(raw);
  } catch (err) {
    v = defaultValue;
  }
  const norm = String(v || "").trim().toLowerCase();
  return ["dark", "light"].includes(norm) ? norm : String(defaultValue || "dark");
}

function normalizeCatalogSubject(value) {
  return String(value || "").trim();
}

function readCatalogDraftFromStorage() {
  try {
    const raw = localStorage.getItem(CATALOG_DRAFT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const subject = normalizeCatalogSubject(parsed.subject || "");
    if (!subject) return null;
    const thread = String(parsed.thread || "").trim();
    return { subject, thread };
  } catch (err) {
    return null;
  }
}

function writeCatalogDraftToStorage(draft) {
  try {
    if (!draft || !draft.subject) return false;
    localStorage.setItem(CATALOG_DRAFT_STORAGE_KEY, JSON.stringify(draft));
    return true;
  } catch (err) {
    return false;
  }
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
  updateNorthStarMechanismsFilterOptions(state.northStarMechanismsRegistry, state.northStarMechanismsHistory);
  ["subject", "status"].forEach((field) => renderNorthStarMechanismsTagSelect(field));
  renderActionLog();
  renderActionResponse();
  updateGithubOpsFreshnessIndicator();
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

function applyTheme(theme) {
  const next = ["dark", "light"].includes(theme) ? theme : "dark";
  document.documentElement.setAttribute("data-theme", next);
}

function setTheme(next, { persist = true } = {}) {
  const norm = String(next || "").trim().toLowerCase();
  state.theme = ["dark", "light"].includes(norm) ? norm : "dark";
  if (persist) writeToStorage(THEME_STORAGE_KEY, state.theme);
  const select = $("#theme-select");
  if (select) select.value = state.theme;
  applyTheme(state.theme);
}

function setupLanguageSelector() {
  const select = $("#lang-select");
  if (!select) return;
  select.value = state.lang;
  select.addEventListener("change", () => setLanguage(select.value));
}

function setupThemeSelector() {
  const select = $("#theme-select");
  if (!select) return;
  select.value = state.theme || "dark";
  select.addEventListener("change", () => setTheme(select.value));
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

  const purposeGenerate = $("#intake-purpose-generate");
  if (purposeGenerate) {
    purposeGenerate.disabled = disabled;
    purposeGenerate.title = admin ? t("intake.purpose.generate") : t("admin.required_op");
  }
  const purposeGenerateSelected = $("#intake-purpose-generate-selected");
  if (purposeGenerateSelected) {
    purposeGenerateSelected.disabled = disabled;
    purposeGenerateSelected.title = admin ? t("intake.purpose.generate_selected") : t("admin.required_op");
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

function normalizeIntakePurposeIndex(payload) {
  const raw = unwrap(payload || {});
  const items = Array.isArray(raw.items) ? raw.items : [];
  const byId = {};
  const byShort = {};
  items.forEach((item) => {
    const id = String(item?.intake_id || "").trim();
    const shortId = String(item?.intake_short_id || "").trim();
    if (id) byId[id] = item;
    if (shortId) byShort[shortId] = item;
  });
  return {
    items,
    byId,
    byShort,
    loaded_at: new Date().toISOString(),
    source_path: intakePurposePath,
  };
}

function pickLocalizedField(record, baseKey) {
  if (!record) return "";
  const direct = record[baseKey];
  if (direct) return String(direct);
  const lang = state.lang === "en" ? "en" : "tr";
  const localized = record[`${baseKey}_${lang}`] || record[`${baseKey}_tr`] || record[`${baseKey}_en`];
  return localized ? String(localized) : "";
}

function getIntakePurposeRecord(intakeId) {
  const id = String(intakeId || "").trim();
  if (!id) return null;
  const index = state.intakePurposeIndex || {};
  if (index.byId && index.byId[id]) return index.byId[id];
  const shortId = shortIntakeId(id);
  if (shortId && index.byShort && index.byShort[shortId]) return index.byShort[shortId];
  return null;
}

function buildPurposeFallback(item) {
  const topic = summarizeIntakeTopic(item);
  const why = summarizeIntakeWhy(item);
  const missing = t("intake.purpose.fallback_missing");
  const unknown = t("intake.purpose.fallback_unknown");
  return {
    purpose: String(item?.title || topic || "-").trim() || missing,
    necessity: missing,
    compatibility: missing,
    why_required: why || unknown,
    implementation_note: missing,
    system_impact: unknown,
    benefit: unknown,
    roi: unknown,
  };
}

function formatPurposeField(record, baseKey) {
  const value = pickLocalizedField(record, baseKey);
  return value ? value : "-";
}

async function refreshIntakePurposeIndex() {
  try {
    const payload = await fetchJson(`${endpoints.file}?path=${encodeURIComponent(intakePurposePath)}`);
    state.intakePurposeIndex = normalizeIntakePurposeIndex(payload);
    state.intakePurposeIndexError = null;
    state.intakePurposeLoadedAt = state.intakePurposeIndex.loaded_at;
  } catch (err) {
    state.intakePurposeIndex = null;
    state.intakePurposeIndexError = err;
    state.intakePurposeLoadedAt = new Date().toISOString();
  }
}

async function refreshIntakePurposeReport() {
  try {
    const payload = await fetchJson(`${endpoints.file}?path=${encodeURIComponent(intakePurposeReportPath)}`);
    state.intakePurposeReport = unwrap(payload || {});
    state.intakePurposeReportError = null;
    state.intakePurposeReportLoadedAt = state.intakePurposeReport.generated_at || new Date().toISOString();
  } catch (err) {
    state.intakePurposeReport = null;
    state.intakePurposeReportError = err;
    state.intakePurposeReportLoadedAt = new Date().toISOString();
  }
}

function renderIntakePurposeMeta() {
  const meta = $("#intake-purpose-generate-meta");
  if (!meta) return;
  const hint = t("intake.purpose.generate_hint");
  const loadedAt = formatTimestamp(state.intakePurposeLoadedAt) || "-";
  const total = state.intakePurposeIndex?.items?.length ?? 0;
  const errorFlag = state.intakePurposeIndexError ? " | error" : "";
  meta.textContent = `${hint} | loaded_at=${loadedAt} | items=${total}${errorFlag}`;
}

function renderIntakePurposeReport() {
  const titleEl = $("#intake-purpose-report-title");
  const metaEl = $("#intake-purpose-report-meta");
  const summaryEl = $("#intake-purpose-report-summary");
  if (titleEl) titleEl.textContent = t("intake.purpose.report.title");
  if (!metaEl || !summaryEl) return;

  const report = state.intakePurposeReport;
  if (!report || typeof report !== "object") {
    metaEl.textContent = t("intake.purpose.report.none");
    summaryEl.textContent = "";
    return;
  }

  const generatedAt = formatTimestamp(report.generated_at) || "-";
  const status = String(report.status || "UNKNOWN").toUpperCase();
  const processed = Number.isFinite(Number(report.processed)) ? Number(report.processed) : 0;
  const created = Number.isFinite(Number(report.created)) ? Number(report.created) : 0;
  const skipped = Number.isFinite(Number(report.skipped)) ? Number(report.skipped) : 0;
  const failures = Array.isArray(report.failures) ? report.failures.length : 0;
  const provider = String(report.provider_id || "-");
  const model = String(report.model || "-");

  metaEl.textContent = `status=${status} generated_at=${generatedAt}`;
  summaryEl.textContent = `processed=${processed} created=${created} skipped=${skipped} failures=${failures} provider=${provider} model=${model}`;
}

async function generateIntakePurposeAll() {
  if (state.actionPending) return;
  if (!isAdminModeEnabled()) {
    showToast(t("admin.required_op"), "warn");
    return;
  }
  const args = {
    mode: "missing_only",
    status: "OPEN",
    provider_id: "openai",
    model: "",
    limit: "50",
    dry_run: "false",
  };
  await postOp("work-intake-purpose-generate", args);
}

async function generateIntakePurposeSelected() {
  if (state.actionPending) return;
  if (!isAdminModeEnabled()) {
    showToast(t("admin.required_op"), "warn");
    return;
  }
  const intakeId = String(state.intakeSelectedId || "").trim();
  if (!intakeId) {
    showToast(t("toast.select_intake_first"), "warn");
    return;
  }
  const args = {
    intake_id: intakeId,
    mode: "single",
    status: "",
    provider_id: "openai",
    model: "",
    limit: "1",
    dry_run: "false",
  };
  await postOp("work-intake-purpose-generate", args);
}

function clearIntakeSelection() {
  state.intakeSelectedId = null;
  state.intakeSelected = null;
  state.intakeExpandedId = null;
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

function getIntakeInlineRoot(intakeId) {
  const id = String(intakeId || "").trim();
  if (!id) return null;
  const selector = `.intake-inline-detail[data-inline-intake="${encodeTag(id)}"]`;
  return document.querySelector(selector);
}

function renderIntakeEvidencePreview() {
  const root = getIntakeInlineRoot(state.intakeSelectedId);
  const panel = root ? root.querySelector("[data-intake-evidence-preview-panel]") : null;
  const meta = root ? root.querySelector("[data-intake-evidence-preview-meta]") : null;
  const pre = root ? root.querySelector("[data-intake-evidence-preview]") : null;
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
  const root = getIntakeInlineRoot(state.intakeSelectedId);
  const meta = root ? root.querySelector("[data-intake-notes-meta]") : null;
  const list = root ? root.querySelector("[data-intake-notes-list]") : null;
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

  list.querySelectorAll("[data-intake-note-open]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
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

function prefillNoteForSnapshot(payload, attempt = 0) {
  const titleEl = $("#note-title");
  const bodyEl = $("#note-body");
  const tagsEl = $("#note-tags");
  const threadEl = $("#planner-thread");
  if (!titleEl || !bodyEl || !tagsEl) {
    if (attempt === 0) {
      navigateToTab("notes");
    }
    if (attempt < 12) {
      setTimeout(() => prefillNoteForSnapshot(payload, attempt + 1), 220);
      return;
    }
    showToast(t("toast.notes_composer_unavailable"), "fail");
    return;
  }

  const tabKeyMap = {
    "overview": "nav.overview",
    "north-star": "nav.north_star",
    "timeline": "nav.timeline",
    "inbox": "nav.inbox",
    "intake": "nav.intake",
    "decisions": "nav.decisions",
    "extensions": "nav.extensions",
    "overrides": "nav.overrides",
    "auto-loop": "nav.auto_loop",
    "jobs": "nav.jobs",
    "locks": "nav.locks",
    "run-card": "nav.run_card",
    "search": "nav.search",
    "planner-chat": "nav.planner_chat",
    "command-composer": "nav.command_composer",
    "evidence": "nav.evidence",
  };
  const snapshotContext = state.snapshotContext || {};
  const activeTab = String(snapshotContext.activeTab || state.activeTab || "overview");
  const tabLabel = t(tabKeyMap[activeTab] || "nav.overview");
  const hash = String(snapshotContext.hash || window.location.hash || "");
  const ts = String(payload?.generated_at || new Date().toISOString());

  const evidencePaths = [];
  const reportPath = String(payload?.report_path || "").trim();
  if (reportPath) evidencePaths.push(reportPath);
  const snapshotPath = String(payload?.ui_snapshot_path || "").trim();
  if (snapshotPath) evidencePaths.push(snapshotPath);
  const evidenceList = Array.isArray(payload?.evidence_paths) ? payload.evidence_paths : [];
  evidenceList.forEach((p) => {
    const v = String(p || "").trim();
    if (v) evidencePaths.push(v);
  });
  const pathsObj = payload && typeof payload.paths === "object" && payload.paths ? payload.paths : {};
  Object.values(pathsObj).forEach((val) => {
    const v = String(val || "").trim();
    if (v) evidencePaths.push(v);
  });
  const dedupedEvidencePaths = Array.from(new Set(evidencePaths.filter(Boolean)));
  if (!dedupedEvidencePaths.length) {
    dedupedEvidencePaths.push(".cache/reports/ui_snapshot_bundle.v1.json");
  }

  const body = [
    t("notes.snapshot.context_header"),
    t("notes.snapshot.context_page", { page: tabLabel }),
    t("notes.snapshot.context_hash", { hash: hash || "-" }),
    t("notes.snapshot.context_time", { ts }),
    "",
    t("notes.snapshot.evidence_header"),
    ...(dedupedEvidencePaths.length ? dedupedEvidencePaths.map((p) => `- ${p}`) : [t("notes.prefill.none")]),
    "",
    t("notes.prefill.next_header"),
    t("notes.prefill.next_placeholder"),
    "",
  ].join("\n");

  titleEl.value = t("notes.snapshot.title", { page: tabLabel });
  bodyEl.value = body;
  const baseTags = ["snapshot", "ui", activeTab.replace(/[^a-z0-9_\\-]/gi, "_")].filter(Boolean);
  tagsEl.value = Array.from(new Set(baseTags)).join(", ");

  state.noteLinks = dedupedEvidencePaths.map((p) => ({ kind: "evidence", id_or_path: p }));
  renderNoteLinks();

  if (threadEl && !threadEl.value) {
    threadEl.value = state.plannerThread || "default";
  }

  state.snapshotContext = null;
  navigateToTab("notes");
  titleEl.focus();
  showToast(t("toast.note_composer_prefilled"), "ok");
}

function renderIntakeClaimControls(item) {
  const root = getIntakeInlineRoot(state.intakeSelectedId);
  const meta = root ? root.querySelector("[data-intake-claim-meta]") : null;
  const claimBtn = root ? root.querySelector("[data-intake-claim]") : null;
  const releaseBtn = root ? root.querySelector("[data-intake-claim-release]") : null;
  const forceReleaseBtn = root ? root.querySelector("[data-intake-claim-force-release]") : null;
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
  const root = getIntakeInlineRoot(state.intakeSelectedId);
  const meta = root ? root.querySelector("[data-intake-close-meta]") : null;
  const closeBtn = root ? root.querySelector("[data-intake-close]") : null;
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
  const root = getIntakeInlineRoot(item?.intake_id);
  const meta = root ? root.querySelector("[data-intake-detail-meta]") : null;
  const fields = root ? root.querySelector("[data-intake-detail-fields]") : null;
  const evidence = root ? root.querySelector("[data-intake-evidence-paths]") : null;
  const raw = root ? root.querySelector("[data-intake-detail-json]") : null;
  if (!root || !meta || !fields || !evidence || !raw) return;

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
    const decisionPanel = root.querySelector("[data-intake-decision-panel]");
    if (decisionPanel) decisionPanel.innerHTML = "";
    renderIntakeEvidencePreview();
    renderIntakeLinkedNotes();
    renderIntakeClaimControls(null);
    renderIntakeCloseControls(null);
    return;
  }

  const topic = summarizeIntakeTopic(item);
  const why = summarizeIntakeWhy(item);
  const evidencePaths = Array.isArray(item.evidence_paths) ? item.evidence_paths.map(String) : [];
  const shortId = shortIntakeId(item.intake_id);
  const purposeRecord = getIntakePurposeRecord(item.intake_id) || buildPurposeFallback(item);
  const purpose = formatPurposeField(purposeRecord, "purpose");
  const necessity = formatPurposeField(purposeRecord, "necessity");
  const compatibility = formatPurposeField(purposeRecord, "compatibility");
  const whyRequired = formatPurposeField(purposeRecord, "why_required");
  const implementationNote = formatPurposeField(purposeRecord, "implementation_note");
  const systemImpact = formatPurposeField(purposeRecord, "system_impact");
  const benefit = formatPurposeField(purposeRecord, "benefit");
  const roi = formatPurposeField(purposeRecord, "roi");

  meta.innerHTML = `${`<span class="intake-short-id">ID: ${escapeHtml(shortId || "-")}</span>`} | ${`<span class="intake-short-id">intake_id: ${escapeHtml(item.intake_id || "-")}</span>`} | ${escapeHtml(topic)}`;
  renderKeyValueGrid(fields, [
    [t("intake.field.topic"), topic],
    [t("intake.field.why"), why],
    [t("intake.field.purpose"), purpose],
    [t("intake.field.necessity"), necessity],
    [t("intake.field.compatibility"), compatibility],
    [t("intake.field.why_required"), whyRequired],
    [t("intake.field.implementation_note"), implementationNote],
    [t("intake.field.system_impact"), systemImpact],
    [t("intake.field.benefit"), benefit],
    [t("intake.field.roi"), roi],
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
  renderIntakeDecisionPanel(item);
  const intakeId = String(item?.intake_id || "").trim();
  if (intakeId && !state.intakeInlineGroup[intakeId]) state.intakeInlineGroup[intakeId] = "summary";
  if (intakeId && !state.intakeInlineTab[intakeId]) state.intakeInlineTab[intakeId] = "summary";
  applyIntakeDetailTab(intakeId);
  bindIntakeInlineActions(root);
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

function parseTimestampMs(value) {
  if (!value) return null;
  if (typeof value === "number" && Number.isFinite(value)) {
    return value < 1e12 ? value * 1000 : value;
  }
  const asString = String(value || "");
  if (/^\d+$/.test(asString)) {
    const num = Number(asString);
    return Number.isFinite(num) ? (num < 1e12 ? num * 1000 : num) : null;
  }
  const date = new Date(asString);
  const ms = date.getTime();
  return Number.isNaN(ms) ? null : ms;
}

function formatAgeShort(ms) {
  if (!Number.isFinite(ms) || ms < 0) return t("jobs.freshness_unknown");
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  return `${hr}h`;
}

function formatSecondsShort(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return "-";
  const sec = Math.max(0, Math.floor(s));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  if (min < 60) return rem ? `${min}m ${rem}s` : `${min}m`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  if (hr < 24) return remMin ? `${hr}h ${remMin}m` : `${hr}h`;
  const day = Math.floor(hr / 24);
  const remHr = hr % 24;
  return remHr ? `${day}d ${remHr}h` : `${day}d`;
}

function formatDurationMs(ms) {
  const value = Number(ms);
  if (!Number.isFinite(value) || value < 0) return "-";
  if (value < 1000) return `${Math.round(value)}ms`;
  return formatSecondsShort(value / 1000);
}

function getGithubOpsFreshness() {
  const data = unwrap(state.jobs || {});
  const raw = pickTimestamp(data, ["generated_at", "updated_at", "ts", "timestamp"]);
  const ms = parseTimestampMs(raw);
  const now = Date.now();
  if (!ms) return { status: "missing", ageMs: null };
  const ageMs = Math.max(0, now - ms);
  const status = ageMs > GITHUB_OPS_STALE_MS ? "stale" : "fresh";
  return { status, ageMs };
}

function updateGithubOpsFreshnessIndicator() {
  const el = $("#github-jobs-freshness");
  if (!el) return;
  const { status, ageMs } = getGithubOpsFreshness();
  el.dataset.status = status;
  const ageText = ageMs === null ? t("jobs.freshness_unknown") : formatAgeShort(ageMs);
  let title = "";
  if (status === "fresh") title = t("jobs.freshness_fresh", { age: ageText });
  else if (status === "stale") title = t("jobs.freshness_stale", { age: ageText });
  else title = t("jobs.freshness_missing");
  el.setAttribute("title", title);
  el.setAttribute("aria-label", title);
}

function normalizeKey(value) {
  return String(value || "").trim().toUpperCase();
}

function normalizeValue(value) {
  return String(value || "").trim();
}

function shortIntakeId(intakeId) {
  const raw = String(intakeId || "").trim();
  if (!raw) return "";
  const match = raw.match(/^INTAKE-([a-f0-9]+)$/i);
  if (match) return match[1].slice(0, 8).toUpperCase();
  const cleaned = raw.replace(/[^a-z0-9]/gi, "");
  if (cleaned.length >= 8) return cleaned.slice(-8).toUpperCase();
  return cleaned ? cleaned.toUpperCase() : raw.slice(-8).toUpperCase();
}

function applyIntakeDetailTab(intakeId) {
  const id = String(intakeId || "").trim();
  const group = id && state.intakeInlineGroup[id] ? state.intakeInlineGroup[id] : "summary";
  const tabs = INTAKE_GROUP_TABS[group] || INTAKE_GROUP_TABS.summary;
  let active = id && state.intakeInlineTab[id] ? state.intakeInlineTab[id] : tabs[0];
  if (!tabs.includes(active)) active = tabs[0];
  const root = getIntakeInlineRoot(id);
  if (!root) return;
  root.querySelectorAll("[data-intake-group-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.intakeGroupTab === group);
  });
  root.querySelectorAll("[data-intake-detail-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.intakeDetailTab === active);
  });
  root.querySelectorAll("[data-intake-detail-pane]").forEach((pane) => {
    pane.classList.toggle("active", pane.dataset.intakeDetailPane === active);
  });
}

function renderIntakeDecisionPanel(item) {
  const root = getIntakeInlineRoot(state.intakeSelectedId);
  const container = root ? root.querySelector("[data-intake-decision-panel]") : null;
  if (!container) return;
  if (!item) {
    container.innerHTML = `<div class="subtle">${escapeHtml(t("common.no_selection"))}</div>`;
    return;
  }
  const intakeId = String(item?.intake_id || "").trim();
  const decision = getDecisionForIntake(intakeId);
  const summaryTr = String(decision.overlay?.summary_tr || "").trim();
  const summaryEn = String(decision.overlay?.summary_en || "").trim();
  const qTr = String(decision.overlay?.decision_question_tr || "").trim();
  const qEn = String(decision.overlay?.decision_question_en || "").trim();
  const options = Array.isArray(decision.overlay?.options) ? decision.overlay.options : [];

  const badgeRec = decision.recommended_action
    ? `<span class="${decisionBadgeClass(decision.recommended_action)}">${escapeHtml(decision.recommended_action)}</span>`
    : `<span class="subtle">-</span>`;
  const badgeConf = decision.confidence ? `<span class="badge">${escapeHtml(decision.confidence)}</span>` : `<span class="subtle">-</span>`;
  const badgeExec = decision.execution_mode ? `<span class="badge">${escapeHtml(decision.execution_mode)}</span>` : `<span class="subtle">-</span>`;
  const badgeEv = decision.evidence_ready
    ? `<span class="badge">${escapeHtml(decision.evidence_ready)}</span>`
    : `<span class="subtle">-</span>`;
  const badgeSel = decision.selected_option ? `<span class="badge ok">${escapeHtml(decision.selected_option)}</span>` : `<span class="subtle">-</span>`;

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
    : `<div class="subtle">${escapeHtml(t("intake.decision.no_overlay"))}</div>`;

  const noteValue = decision.mark?.note ? String(decision.mark.note || "") : "";

  container.innerHTML = `
    <div class="row" style="gap: 8px; flex-wrap: wrap;">
      ${badgeRec}
      ${badgeConf}
      ${badgeExec}
      ${badgeEv}
      ${badgeSel}
    </div>
    <div class="subtle" style="margin-top: 8px;">${escapeHtml(summaryEn ? `${summaryTr} (${summaryEn})` : (summaryTr || ""))}</div>
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
  `;
}

function bindIntakeInlineActions(root) {
  if (!root) return;
  const clearBtn = root.querySelector("[data-intake-clear]");
  if (clearBtn && !clearBtn.dataset.bound) {
    clearBtn.addEventListener("click", (event) => {
      event.preventDefault();
      clearIntakeSelection();
    });
    clearBtn.dataset.bound = "true";
  }
  root.querySelectorAll("[data-intake-group-tab]").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      const intakeId = String(state.intakeSelectedId || "").trim();
      const group = String(btn.dataset.intakeGroupTab || "").trim();
      if (!intakeId || !group) return;
      state.intakeInlineGroup[intakeId] = group;
      const tabs = INTAKE_GROUP_TABS[group] || INTAKE_GROUP_TABS.summary;
      state.intakeInlineTab[intakeId] = tabs[0];
      renderIntakeTable((unwrap(state.intake || {}).items || []));
      if (state.intakeExpandedId === intakeId && state.intakeSelected) {
        renderIntakeDetail(state.intakeSelected);
      }
    });
    btn.dataset.bound = "true";
  });
  root.querySelectorAll("[data-intake-detail-tab]").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      const intakeId = String(state.intakeSelectedId || "").trim();
      const tab = String(btn.dataset.intakeDetailTab || "").trim();
      if (!intakeId || !tab) return;
      state.intakeInlineTab[intakeId] = tab;
      applyIntakeDetailTab(intakeId);
    });
    btn.dataset.bound = "true";
  });
  const createNoteBtn = root.querySelector("[data-intake-create-note]");
  if (createNoteBtn && !createNoteBtn.dataset.bound) {
    createNoteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      createNoteForSelectedIntake();
    });
    createNoteBtn.dataset.bound = "true";
  }
  const openNotesBtn = root.querySelector("[data-intake-open-notes]");
  if (openNotesBtn && !openNotesBtn.dataset.bound) {
    openNotesBtn.addEventListener("click", (event) => {
      event.preventDefault();
      navigateToTab("notes");
    });
    openNotesBtn.dataset.bound = "true";
  }
  const claimBtn = root.querySelector("[data-intake-claim]");
  if (claimBtn && !claimBtn.dataset.bound) {
    claimBtn.addEventListener("click", (event) => {
      event.preventDefault();
      claimIntakeItem(state.intakeSelectedId, "claim");
    });
    claimBtn.dataset.bound = "true";
  }
  const claimReleaseBtn = root.querySelector("[data-intake-claim-release]");
  if (claimReleaseBtn && !claimReleaseBtn.dataset.bound) {
    claimReleaseBtn.addEventListener("click", (event) => {
      event.preventDefault();
      claimIntakeItem(state.intakeSelectedId, "release");
    });
    claimReleaseBtn.dataset.bound = "true";
  }
  const claimForceBtn = root.querySelector("[data-intake-claim-force-release]");
  if (claimForceBtn && !claimForceBtn.dataset.bound) {
    claimForceBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      const id = String(state.intakeSelectedId || "").trim();
      if (!id) return;
      await forceReleaseIntakeClaim(id);
    });
    claimForceBtn.dataset.bound = "true";
  }
  const closeBtn = root.querySelector("[data-intake-close]");
  if (closeBtn && !closeBtn.dataset.bound) {
    closeBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await closeSelectedIntakeItem();
    });
    closeBtn.dataset.bound = "true";
  }
  const purposeGenerateSelectedBtn = root.querySelector("[data-intake-purpose-generate-selected]");
  if (purposeGenerateSelectedBtn && !purposeGenerateSelectedBtn.dataset.bound) {
    purposeGenerateSelectedBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await generateIntakePurposeSelected();
    });
    purposeGenerateSelectedBtn.dataset.bound = "true";
  }
  root.querySelectorAll("[data-decision-save]").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const intakeId = decodeTag(btn.dataset.decisionSave || "");
      if (!intakeId) return;
      const name = `decision-opt-${encodeTag(intakeId)}`;
      const selected = root.querySelector(`input[name=\"${CSS.escape(name)}\"]:checked`);
      const option = selected ? String(selected.value || "").trim() : "";
      const noteEl = root.querySelector(`[data-decision-note=\"${CSS.escape(encodeTag(intakeId))}\"]`);
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
    btn.dataset.bound = "true";
  });
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
const DEFAULT_COCKPIT_COMPAT_ARTIFACTS = {
  overlay: ".cache/ws_customer_default/.cache/index/cockpit_decision_overlay.compat.v1.json",
  reproof: ".cache/ws_customer_default/.cache/reports/all_open_compat_reproof.v1.json",
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

function computeCompatCounts(items) {
  const counts = {
    OK: 0,
    REFRESH_REQUIRED: 0,
    NEEDS_EXEC_PACK: 0,
    BLOCKED_BY_REGIME: 0,
  };
  if (!items || typeof items !== "object") return counts;
  Object.values(items).forEach((row) => {
    const status = String(row?.compat_status || "").trim().toUpperCase();
    if (status && counts[status] !== undefined) counts[status] += 1;
  });
  return counts;
}

function computeCompatTopBlockers(items) {
  const counts = {};
  if (!items || typeof items !== "object") return [];
  Object.values(items).forEach((row) => {
    const blockers = Array.isArray(row?.blockers) ? row.blockers : [];
    blockers.forEach((b) => {
      const key = String(b || "").trim();
      if (!key) return;
      counts[key] = (counts[key] || 0) + 1;
    });
  });
  return Object.entries(counts)
    .sort((a, b) => (b[1] - a[1] !== 0 ? b[1] - a[1] : String(a[0]).localeCompare(String(b[0]))))
    .slice(0, 5)
    .map(([reason, count]) => ({ reason, count }));
}

function deriveCompatOverallStatus(counts) {
  if (!counts || typeof counts !== "object") return "MISSING";
  const blocked = Number(counts.BLOCKED_BY_REGIME || 0);
  const refresh = Number(counts.REFRESH_REQUIRED || 0);
  const needs = Number(counts.NEEDS_EXEC_PACK || 0);
  const ok = Number(counts.OK || 0);
  if (blocked > 0) return "BLOCKED";
  if (refresh > 0 || needs > 0) return "WARN";
  if (ok > 0) return "OK";
  return "MISSING";
}

function normalizeCompatSummaryFromOverlay(payload) {
  const overlay = unwrap(payload || {});
  const items = overlay.items && typeof overlay.items === "object" ? overlay.items : {};
  const counts = computeCompatCounts(items);
  const topBlockers = computeCompatTopBlockers(items);
  const updatedAt = pickTimestamp(overlay, ["updated_at", "generated_at", "created_at", "ts", "timestamp"]);
  return {
    ok: true,
    loaded_at: new Date().toISOString(),
    counts,
    top_blockers: topBlockers,
    source: "overlay",
    source_name: "overlay",
    updated_at_iso: updatedAt || "unknown",
    loaded_at_iso: new Date().toISOString(),
    overall_status: deriveCompatOverallStatus(counts),
    error: null,
  };
}

function normalizeCompatSummaryFromReproof(payload) {
  const reproof = unwrap(payload || {});
  const summary = reproof.summary && typeof reproof.summary === "object" ? reproof.summary : {};
  const counts = summary.status_counts && typeof summary.status_counts === "object" ? summary.status_counts : {};
  let topBlockers = [];
  const raw = summary.top_blockers;
  if (Array.isArray(raw)) {
    topBlockers = raw
      .map((row) => {
        if (Array.isArray(row) && row.length >= 2) return { reason: String(row[0]), count: Number(row[1]) || 0 };
        if (row && typeof row === "object") return { reason: String(row.reason || row[0] || ""), count: Number(row.count || row[1]) || 0 };
        return null;
      })
      .filter(Boolean)
      .slice(0, 5);
  }
  return {
    ok: Boolean(Object.keys(counts).length || topBlockers.length),
    loaded_at: new Date().toISOString(),
    counts,
    top_blockers: topBlockers,
    source: "reproof",
    source_name: "reproof",
    updated_at_iso: pickTimestamp(reproof, ["updated_at", "generated_at", "created_at", "ts", "timestamp"]) || "unknown",
    loaded_at_iso: new Date().toISOString(),
    overall_status: deriveCompatOverallStatus(counts),
    error: null,
  };
}

function renderIntakeCompatSummaryCard() {
  const cardEl = $("#intake-compat-summary");
  const warnEl = $("#intake-compat-summary-warn");
  if (!cardEl || !warnEl) return;

  const meta = state.intakeCompatSummary || {};
  if (!meta.ok) {
    const statusBadge = `<span class="pill miss">${escapeHtml(t("intake.compat.status_badge", { status: "MISSING" }))}</span>`;
    cardEl.innerHTML = `
      <div class="note-item">
        <div class="note-title">${escapeHtml(t("intake.compat.title"))}</div>
        <div class="row" style="gap:6px; flex-wrap:wrap;">${statusBadge}</div>
      </div>
    `;
    cardEl.style.display = "block";
    const err = meta.error ? ` (${meta.error})` : "";
    warnEl.textContent = `${t("intake.compat.banner_missing")}${err}`;
    warnEl.style.display = "block";
    return;
  }

  const counts = meta.counts || {};
  const statuses = ["OK", "REFRESH_REQUIRED", "NEEDS_EXEC_PACK", "BLOCKED_BY_REGIME"];
  const pills = statuses
    .map((status) => `<div class="pill">${escapeHtml(status)}=${escapeHtml(String(counts[status] || 0))}</div>`)
    .join("");
  const blockers = Array.isArray(meta.top_blockers) ? meta.top_blockers : [];
  const sourceName = meta.source_name || meta.source || "unknown";
  const updatedRaw = meta.updated_at_iso || "unknown";
  const updatedLabel = formatTimestamp(updatedRaw) || String(updatedRaw || "unknown");
  const loadedRaw = meta.loaded_at_iso || meta.loaded_at || "unknown";
  const loadedLabel = formatTimestamp(loadedRaw) || String(loadedRaw || "unknown");
  const overallStatus = String(meta.overall_status || "MISSING").toUpperCase();
  const statusClass =
    overallStatus === "OK"
      ? "ok"
      : overallStatus === "WARN"
        ? "warn"
        : overallStatus === "BLOCKED"
          ? "block"
          : "miss";
  const metaBadges = `
    <span class="pill ${statusClass}">${escapeHtml(t("intake.compat.status_badge", { status: overallStatus }))}</span>
    <span class="pill muted">${escapeHtml(t("intake.compat.source_badge", { source: sourceName || "unknown" }))}</span>
    <span class="pill muted">${escapeHtml(t("intake.compat.updated_badge", { ts: updatedLabel || "unknown" }))}</span>
    <span class="pill muted">${escapeHtml(t("intake.compat.loaded_badge", { ts: loadedLabel || "unknown" }))}</span>
  `;
  const blockersList = blockers.length
    ? blockers
        .map((row) => `<li>${escapeHtml(String(row.reason || ""))} (${escapeHtml(String(row.count || 0))})</li>`)
        .join("")
    : `<li class="subtle">${escapeHtml(t("intake.compat.none"))}</li>`;

  cardEl.innerHTML = `
    <div class="note-item">
      <div class="note-title">${escapeHtml(t("intake.compat.title"))}</div>
      <div class="row" style="gap:6px; flex-wrap:wrap;">${pills}</div>
      <div class="subtle" style="margin-top:6px;">${escapeHtml(t("intake.compat.blockers"))}</div>
      <ul class="subtle" style="margin:4px 0 0 16px;">${blockersList}</ul>
      <div class="subtle" style="margin-top:6px;">${metaBadges}</div>
    </div>
  `;
  cardEl.style.display = "block";
  warnEl.style.display = "none";
  warnEl.textContent = "";
}

async function refreshIntakeCompatSummary() {
  if (state.intakeCompatSummaryLoading) return;
  state.intakeCompatSummaryLoading = true;
  const out = {
    ok: false,
    loaded_at: new Date().toISOString(),
    counts: null,
    top_blockers: [],
    updated_at_iso: null,
    source_name: null,
    loaded_at_iso: null,
    overall_status: "MISSING",
    error: null,
    source: null,
  };
  try {
    const overlayPayload = await fetchWorkspaceFile(DEFAULT_COCKPIT_COMPAT_ARTIFACTS.overlay);
    if (overlayPayload && overlayPayload.exists && overlayPayload.json_valid) {
      Object.assign(out, normalizeCompatSummaryFromOverlay(_extractFileData(overlayPayload)));
    } else {
      const reproofPayload = await fetchWorkspaceFile(DEFAULT_COCKPIT_COMPAT_ARTIFACTS.reproof);
      if (reproofPayload && reproofPayload.exists && reproofPayload.json_valid) {
        Object.assign(out, normalizeCompatSummaryFromReproof(_extractFileData(reproofPayload)));
      } else {
        out.ok = false;
      }
    }
  } catch (err) {
    out.ok = false;
    out.error = formatError(err);
  }
  state.intakeCompatSummary = out;
  renderIntakeCompatSummaryCard();
  state.intakeCompatSummaryLoading = false;
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

  const activeGroup = state.intakeInlineGroup && state.intakeInlineGroup[intakeId]
    ? state.intakeInlineGroup[intakeId]
    : "summary";
  const groupTabs = INTAKE_GROUP_TABS[activeGroup] || INTAKE_GROUP_TABS.summary;
  let activeTab = state.intakeInlineTab && state.intakeInlineTab[intakeId]
    ? state.intakeInlineTab[intakeId]
    : groupTabs[0];
  if (!groupTabs.includes(activeTab)) activeTab = groupTabs[0];

  const badgeRec = decision.recommended_action
    ? `<span class="${decisionBadgeClass(decision.recommended_action)}">${escapeHtml(decision.recommended_action)}</span>`
    : `<span class="subtle">-</span>`;
  const badgeConf = decision.confidence ? `<span class="badge">${escapeHtml(decision.confidence)}</span>` : `<span class="subtle">-</span>`;
  const badgeExec = decision.execution_mode ? `<span class="badge">${escapeHtml(decision.execution_mode)}</span>` : `<span class="subtle">-</span>`;
  const badgeEv = decision.evidence_ready
    ? `<span class="badge">${escapeHtml(decision.evidence_ready)}</span>`
    : `<span class="subtle">-</span>`;
  const badgeSel = decision.selected_option ? `<span class="badge ok">${escapeHtml(decision.selected_option)}</span>` : `<span class="subtle">-</span>`;
  const shortId = shortIntakeId(intakeId);

  const groupButtons = [
    { id: "summary", label: t("intake.group.summary") },
    { id: "decision", label: t("intake.group.decision") },
    { id: "evidence", label: t("intake.group.evidence") },
    { id: "raw", label: t("intake.group.raw") },
  ];
  const groupTabsHtml = groupButtons
    .map(
      (g) =>
        `<button class="intake-group-tab${activeGroup === g.id ? " active" : ""}" type="button" data-intake-group-tab="${g.id}">${escapeHtml(g.label)}</button>`
    )
    .join("");
  const tabs = `
    <div class="intake-detail-tabs">
      ${groupTabs
        .map((tabId) => {
          const labelKey = `intake.detail.tab_${tabId}`;
          const label = t(labelKey);
          return `<button class="intake-detail-tab${activeTab === tabId ? " active" : ""}" type="button" data-intake-detail-tab="${tabId}">${escapeHtml(label)}</button>`;
        })
        .join("")}
    </div>
  `;

  return `
    <div class="intake-inline-detail" data-inline-intake="${encodeTag(intakeId)}">
      <div class="inline-header">
        <div class="inline-title">${escapeHtml(titleEn ? `${title} (${titleEn})` : title)}</div>
        <div class="row" style="gap: 8px; flex-wrap: wrap;">
          ${badgeRec}
          ${badgeConf}
          ${badgeExec}
          ${badgeEv}
          ${badgeSel}
          <button class="btn ghost" type="button" data-intake-clear>Clear</button>
        </div>
      </div>
      <div class="subtle intake-short-id" data-intake-detail-meta>ID: ${escapeHtml(shortId || "-")} | intake_id: ${escapeHtml(intakeId || "-")}</div>
      <div class="intake-inline-body">
        <div class="intake-group-tabs">${groupTabsHtml}</div>
        <div class="intake-inline-content">
          ${tabs}
          <div class="intake-detail-pane${activeTab === "summary" ? " active" : ""}" data-intake-detail-pane="summary">
            <div class="row" style="margin-top: 8px;">
              <button class="btn" type="button" data-intake-purpose-generate-selected>${escapeHtml(t("intake.purpose.generate_selected"))}</button>
              <div class="subtle" data-intake-purpose-generate-selected-meta>${escapeHtml(t("intake.purpose.generate_selected_hint"))}</div>
            </div>
            <div class="intake-detail-grid" data-intake-detail-fields></div>
            <div class="row" style="margin-top: 10px;">
              <div class="subtle" data-intake-claim-meta>${escapeHtml(t("intake.claim.meta_none"))}</div>
              <button class="btn" type="button" data-intake-claim>${escapeHtml(t("intake.claim.btn_claim"))}</button>
              <button class="btn ghost" type="button" data-intake-claim-release>${escapeHtml(t("intake.claim.btn_release"))}</button>
              <button class="btn danger" type="button" data-intake-claim-force-release>${escapeHtml(t("intake.claim.btn_force_release"))}</button>
            </div>
            <div class="row" style="margin-top: 10px;">
              <div class="subtle" data-intake-close-meta>${escapeHtml(t("intake.close.meta_none"))}</div>
              <button class="btn warn" type="button" data-intake-close>${escapeHtml(t("intake.close.btn_close"))}</button>
            </div>
          </div>
          <div class="intake-detail-pane${activeTab === "decision" ? " active" : ""}" data-intake-detail-pane="decision">
            <div data-intake-decision-panel></div>
          </div>
          <div class="intake-detail-pane${activeTab === "notes" ? " active" : ""}" data-intake-detail-pane="notes">
            <div class="row" style="margin-top: 10px;">
              <div class="subtle" data-intake-notes-meta>Notes for this item: -</div>
              <button class="btn accent" type="button" data-intake-create-note>Create note</button>
              <button class="btn ghost" type="button" data-intake-open-notes>Open Notes tab</button>
            </div>
            <div class="note-list" data-intake-notes-list></div>
          </div>
          <div class="intake-detail-pane${activeTab === "evidence" ? " active" : ""}" data-intake-detail-pane="evidence">
            <div class="subtle" style="margin-top: 10px;">Evidence paths (click to preview)</div>
            <div class="path-chips" data-intake-evidence-paths></div>
            <details style="margin-top: 10px;" data-intake-evidence-preview-panel>
              <summary class="subtle">Evidence preview</summary>
              <div class="subtle" data-intake-evidence-preview-meta></div>
              <pre data-intake-evidence-preview></pre>
            </details>
          </div>
          <div class="intake-detail-pane${activeTab === "raw" ? " active" : ""}" data-intake-detail-pane="raw">
            <details style="margin-top: 10px;">
              <summary class="subtle">Raw intake item JSON (redacted)</summary>
              <pre data-intake-detail-json></pre>
            </details>
          </div>
        </div>
      </div>
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

function getNorthStarCriteriaPack() {
  const pack = state.northStarCriteriaPacks;
  return pack && typeof pack === "object" ? pack : null;
}

function getNorthStarPerspectiveSet(perspectiveId) {
  const pack = getNorthStarCriteriaPack();
  if (!pack) return null;
  const core = Array.isArray(pack.core_8) ? pack.core_8 : [];
  const packs = pack.perspective_packs && typeof pack.perspective_packs === "object" ? pack.perspective_packs : {};
  const entry = packs[String(perspectiveId || "")] || null;
  const extra = entry && Array.isArray(entry.criteria) ? entry.criteria : [];
  const merged = [];
  const seen = new Set();
  [...core, ...extra].forEach((axis) => {
    const key = normalizeKey(axis);
    if (!key || seen.has(key)) return;
    seen.add(key);
    merged.push(String(axis));
  });
  return { criteria: merged, meta: entry || null };
}

function getNorthStarPerspectiveOptions() {
  const pack = getNorthStarCriteriaPack();
  const packs = pack && typeof pack.perspective_packs === "object" ? pack.perspective_packs : {};
  const keys = NORTH_STAR_PERSPECTIVE_ORDER.filter((key) => packs[key]);
  const fallbackKeys = Object.keys(packs || {}).filter((k) => !keys.includes(k)).sort((a, b) => a.localeCompare(b));
  const allKeys = [...keys, ...fallbackKeys];
  return allKeys.map((key) => {
    const entry = packs[key] || {};
    const tr = String(entry.label_tr || key);
    const en = String(entry.label_en || tr);
    const label = tr && en && tr !== en ? `${tr} (${en})` : tr;
    return { id: String(key), label };
  });
}

function getNorthStarPerspectiveCriteriaUnion(perspectives) {
  const list = Array.isArray(perspectives) ? perspectives : [];
  const merged = [];
  const seen = new Set();
  list.forEach((id) => {
    const set = getNorthStarPerspectiveSet(id);
    if (!set || !Array.isArray(set.criteria)) return;
    set.criteria.forEach((axis) => {
      const key = normalizeKey(axis);
      if (!key || seen.has(key)) return;
      seen.add(key);
      merged.push(String(axis));
    });
  });
  return merged;
}

function applyNorthStarPerspectiveCriteria(perspectiveIds) {
  const selected = Array.isArray(perspectiveIds)
    ? perspectiveIds.map((p) => String(p || "").trim()).filter((p) => p)
    : [];
  state.filters.northStarFindings.perspective = selected;
  if (!selected.length) {
    state.filters.northStarFindings.topic_locked_by_perspective = false;
    if (Array.isArray(state.filterOptions.northStarFindings.topic_unlocked)) {
      state.filterOptions.northStarFindings.topic = state.filterOptions.northStarFindings.topic_unlocked.slice();
    }
    return;
  }
  const criteria = getNorthStarPerspectiveCriteriaUnion(selected);
  const normalized = criteria
    .map((axis) => normalizeNorthStarFindingTopic(axis))
    .map((axis) => String(axis || "").trim())
    .filter((axis) => Boolean(axis));
  state.filterOptions.northStarFindings.topic = normalized;
  state.filters.northStarFindings.topic_locked_by_perspective = true;
}

function normalizeNorthStarFindingSubject(value) {
  const raw = String(value || "").trim();
  if (!raw) return t("north_star.unknown");
  return raw;
}

function getMechanismsSubjectLabel(subjectId) {
  const registry = unwrap(state.northStarMechanismsRegistry || {}) || {};
  const subjects = Array.isArray(registry.subjects) ? registry.subjects : [];
  const target = subjects.find((entry) => String(entry?.subject_id || "").trim() === String(subjectId || "").trim());
  if (!target) return "";
  if (String(subjectId) === "ethics_program") return "Etik Programı (ethics_program)";
  return formatTrEnLabel(target?.subject_title_tr, target?.subject_title_en, subjectId);
}

function getMechanismsHistorySubject(historyPayload, subjectId) {
  if (!subjectId) return null;
  const history = unwrap(historyPayload || {}) || {};
  const subjects = Array.isArray(history.subjects) ? history.subjects : [];
  return subjects.find((entry) => String(entry?.subject_id || "").trim() === String(subjectId || "").trim()) || null;
}

function getMechanismsHistoryVersions(historySubject) {
  if (!historySubject) return [];
  const versions = Array.isArray(historySubject.versions) ? historySubject.versions : [];
  return versions
    .map((version) => ({
      version_id: String(version?.version_id || "").trim(),
      label: String(version?.label || version?.version_title || "").trim(),
      created_at: String(version?.created_at || version?.generated_at || "").trim(),
      status: String(version?.status || "").trim(),
      themes: Array.isArray(version?.themes) ? version.themes : [],
    }))
    .filter((version) => version.version_id);
}

function getMechanismsHistoryVersion(historySubject, versionId) {
  if (!historySubject || !versionId) return null;
  const versions = getMechanismsHistoryVersions(historySubject);
  return versions.find((version) => normalizeKey(version.version_id) === normalizeKey(versionId)) || null;
}

function getLatestMechanismsVersionLabel(historySubject) {
  const versions = getMechanismsHistoryVersions(historySubject);
  if (!versions.length) return "";
  const scored = versions
    .map((version) => ({
      ...version,
      ts: Date.parse(version.created_at || "") || 0,
    }))
    .sort((a, b) => (b.ts - a.ts) || String(b.version_id).localeCompare(String(a.version_id)));
  const pick = scored[0];
  return pick.label || pick.created_at || pick.version_id || "";
}

function getPrimaryMechanismsSubjectFilter() {
  const selected = state.filters?.northStarMechanisms?.subject || [];
  if (Array.isArray(selected)) return String(selected[0] || "");
  return String(selected || "");
}

function getVisibleMechanismsSubjects(registryPayload) {
  const registry = unwrap(registryPayload || {}) || {};
  const subjects = Array.isArray(registry.subjects) ? registry.subjects : [];
  return subjects.filter((subject) => !["DEPRECATED", "HIDDEN"].includes(String(subject?.status || "").toUpperCase()));
}

function getFilteredMechanismsSubjects(registryPayload) {
  const registry = unwrap(registryPayload || {}) || {};
  const subjects = Array.isArray(registry.subjects) ? registry.subjects : [];
  const selectedSubjects = state.filters?.northStarMechanisms?.subject || [];
  const selectedStatuses = state.filters?.northStarMechanisms?.status || [];
  const search = String(state.filters?.northStarMechanisms?.search || "").trim().toLowerCase();

  const subjectKeys = new Set((Array.isArray(selectedSubjects) ? selectedSubjects : []).map((val) => normalizeKey(val)));
  const statusKeys = new Set((Array.isArray(selectedStatuses) ? selectedStatuses : []).map((val) => normalizeKey(val)));
  const effectiveStatuses = statusKeys.size ? statusKeys : null;

  return subjects.filter((subject) => {
    const subjectId = String(subject?.subject_id || "").trim();
    const subjectStatus = String(subject?.status || "").toUpperCase() || "UNKNOWN";
    if (effectiveStatuses && !effectiveStatuses.has(normalizeKey(subjectStatus))) return false;
    if (subjectKeys.size && !subjectKeys.has(normalizeKey(subjectId))) return false;
    if (!search) return true;
    return mechanismSubjectMatchesSearch(subject, search);
  });
}

function getMechanismsSubjectLabelLocalized(subject) {
  const subjectId = String(subject?.subject_id || "").trim();
  if (subjectId === "ethics_case_management") return "Etik Programı";
  if (subjectId === "ethics_program") return "Etik Programı";
  return localizeTrEnLabel(subject?.subject_title_tr, subject?.subject_title_en, subjectId);
}

function formatVersionLabel(raw) {
  const label = String(raw || "").trim();
  if (!label) return "";
  const matchDate = label.match(/(\d{4}-\d{2}-\d{2})/);
  if (matchDate) return `v${matchDate[1]}`;
  if (/^v\d{4}-\d{2}-\d{2}$/i.test(label)) return label;
  return label;
}

function updateNorthStarMechanismsFilterOptions(registryPayload, historyPayload) {
  const registry = unwrap(registryPayload || {}) || {};
  const history = unwrap(historyPayload || {}) || {};
  const subjects = Array.isArray(registry.subjects) ? registry.subjects : [];
  const subjectOptions = subjects
    .map((subject) => {
      const subjectId = String(subject?.subject_id || "").trim();
      const historySubject = getMechanismsHistorySubject(history, subjectId);
      const latestVersionLabel = formatVersionLabel(getLatestMechanismsVersionLabel(historySubject));
      const labelTitle = getMechanismsSubjectLabelLocalized(subject) || subjectId;
      const labelBase = `${labelTitle} · ID: ${subjectId}`;
      const label = latestVersionLabel ? `${labelBase} · Güncel ${latestVersionLabel}` : labelBase;
      return { id: subjectId, label };
    })
    .filter((opt) => opt.id)
    .sort((a, b) => a.label.localeCompare(b.label));

  const statusValues = new Set(state.filterOptions?.northStarMechanisms?.status || []);
  subjects.forEach((subject) => {
    const status = String(subject?.status || "").toUpperCase();
    if (status) statusValues.add(status);
  });
  const statusOptions = Array.from(statusValues.values())
    .map((status) => String(status || "").toUpperCase())
    .filter((status) => status)
    .sort((a, b) => a.localeCompare(b));

  state.filterOptions.northStarMechanisms.subject = subjectOptions;
  state.filterOptions.northStarMechanisms.status = statusOptions;

  const selectedSubjects = state.filters?.northStarMechanisms?.subject || [];
  const subjectKeys = new Set(subjectOptions.map((opt) => normalizeKey(opt.id)));
  state.filters.northStarMechanisms.subject = (Array.isArray(selectedSubjects) ? selectedSubjects : []).filter((opt) =>
    subjectKeys.has(normalizeKey(opt))
  );

  const selectedStatuses = state.filters?.northStarMechanisms?.status || [];
  const statusKeys = new Set(statusOptions.map((opt) => normalizeKey(opt)));
  const prunedStatuses = (Array.isArray(selectedStatuses) ? selectedStatuses : []).filter((opt) => statusKeys.has(normalizeKey(opt)));
  state.filters.northStarMechanisms.status = prunedStatuses;
}

function renderNorthStarMechanismsTagSelect(field) {
  const wrap = $(`#ns-mechanisms-filter-${field}`);
  const tagsEl = $(`#ns-mechanisms-filter-${field}-tags`);
  const input = $(`#ns-mechanisms-filter-${field}-input`);
  const optionsEl = $(`#ns-mechanisms-filter-${field}-options`);
  if (!wrap || !tagsEl || !input || !optionsEl) return;

  const selected = state.filters.northStarMechanisms[field] || [];
  const selectedKeys = new Set(selected.map((val) => normalizeKey(val)));
  const query = input.value.trim().toLowerCase();
  const rawOptions = state.filterOptions.northStarMechanisms[field] || [];
  const labelMap = new Map(
    rawOptions
      .map((opt) => {
        if (opt && typeof opt === "object") {
          const id = String(opt.id || "").trim();
          const label = String(opt.label || opt.name || opt.title || id).trim();
          return [id, label];
        }
        const value = String(opt || "").trim();
        return [value, value];
      })
      .filter((pair) => pair[0])
  );
  const options = rawOptions
    .map((opt) => {
      if (opt && typeof opt === "object") {
        const id = String(opt.id || "").trim();
        const label = String(opt.label || opt.name || opt.title || id).trim();
        return { value: id, label };
      }
      const value = String(opt || "").trim();
      const label = field === "status" ? getMechanismsStatusLabel(value) : value;
      return { value, label };
    })
    .filter((opt) => opt.value && !selectedKeys.has(normalizeKey(opt.value)))
    .filter((opt) => (query ? opt.label.toLowerCase().includes(query) : true))
    .sort((a, b) => a.label.localeCompare(b.label));
  const activeIndex = getTagSelectActiveIndex("northStarMechanisms", field, options.length);
  setTagSelectActiveIndex("northStarMechanisms", field, activeIndex, options.length);
  const optionIdPrefix = `ns-mechanisms-${field}-opt-`;
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
      const label =
        field === "status" ? getMechanismsStatusLabel(value) : labelMap.get(String(value || "")) || String(value || "");
      return `<span class="tag">${escapeHtml(label)}<button data-remove="${encoded}" aria-label="${escapeHtml(t("actions.remove_tag"))}">x</button></span>`;
    })
    .join("");

  optionsEl.innerHTML = options.length
    ? options
        .map((opt, idx) => {
          const encoded = encodeTag(opt.value);
          const isActive = idx === activeIndex;
          const cls = `tag-option${isActive ? " active" : ""}`;
          return `<div class="${cls}" role="option" id="${optionIdPrefix}${idx}" aria-selected="${isActive ? "true" : "false"}" data-value="${encoded}">${escapeHtml(opt.label)}</div>`;
        })
        .join("")
    : `<div class="tag-option subtle" role="option" aria-selected="false">${escapeHtml(t("empty.no_items"))}</div>`;
}

function addNorthStarMechanismsTag(field, value) {
  const list = state.filters.northStarMechanisms[field] || [];
  const key = normalizeKey(value);
  if (!key) return;
  const exists = list.some((item) => normalizeKey(item) === key);
  if (exists) return;
  list.push(normalizeValue(value));
  list.sort((a, b) => a.localeCompare(b));
  state.filters.northStarMechanisms[field] = list;
  renderNorthStarMechanismsTagSelect(field);
}

function removeNorthStarMechanismsTag(field, value) {
  const list = state.filters.northStarMechanisms[field] || [];
  const key = normalizeKey(value);
  state.filters.northStarMechanisms[field] = list.filter((item) => normalizeKey(item) !== key);
  renderNorthStarMechanismsTagSelect(field);
}

function setupNorthStarMechanismsTagSelects() {
  const fields = ["subject", "status"];
  const closeAll = (except) => {
    fields.forEach((field) => {
      if (field === except) return;
      const wrap = $(`#ns-mechanisms-filter-${field}`);
      if (wrap) wrap.classList.remove("open");
      const input = $(`#ns-mechanisms-filter-${field}-input`);
      if (input) setAriaExpanded(input, false);
    });
  };

  fields.forEach((field) => {
    const wrap = $(`#ns-mechanisms-filter-${field}`);
    const input = $(`#ns-mechanisms-filter-${field}-input`);
    const options = $(`#ns-mechanisms-filter-${field}-options`);
    if (!wrap || !input || !options) return;
    const toggle = wrap.querySelector(".tag-toggle");

    const openSelect = () => {
      closeAll(field);
      wrap.classList.add("open");
      setTagSelectActiveIndex("northStarMechanisms", field, 0);
      renderNorthStarMechanismsTagSelect(field);
      requestAnimationFrame(() => scrollTagSelectActiveOptionIntoView(options));
    };

    input.addEventListener("focus", () => {
      openSelect();
    });
    input.addEventListener("input", () => renderNorthStarMechanismsTagSelect(field));
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
      const current = getTagSelectActiveIndex("northStarMechanisms", field, optionEls.length);

      if (key === "ArrowDown" || key === "ArrowUp") {
        event.preventDefault();
        const delta = key === "ArrowDown" ? 1 : -1;
        setTagSelectActiveIndex("northStarMechanisms", field, clampIndex(current + delta, optionEls.length), optionEls.length);
        renderNorthStarMechanismsTagSelect(field);
        requestAnimationFrame(() => scrollTagSelectActiveOptionIntoView(options));
        return;
      }

      if (key === "Enter") {
        event.preventDefault();
        const target = optionEls[current];
        const rawValue = target?.dataset?.value;
        if (!rawValue) return;
        addNorthStarMechanismsTag(field, decodeTag(rawValue));
        input.value = "";
        openSelect();
        input.focus();
        renderNorthStarMechanisms();
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
        addNorthStarMechanismsTag(field, decodeTag(rawValue));
        input.value = "";
        openSelect();
        input.focus();
        renderNorthStarMechanisms();
      }
      if (rawRemove) {
        removeNorthStarMechanismsTag(field, decodeTag(rawRemove));
        renderNorthStarMechanisms();
      }
      if (target && (target.classList?.contains("tag-select-input") || target.classList?.contains("tag-input"))) {
        openSelect();
        input.focus();
      }
    });
  });

  document.addEventListener("click", (event) => {
    fields.forEach((field) => {
      const wrap = $(`#ns-mechanisms-filter-${field}`);
      if (!wrap) return;
      if (!wrap.contains(event.target)) {
        wrap.classList.remove("open");
        const input = $(`#ns-mechanisms-filter-${field}-input`);
        if (input) setAriaExpanded(input, false);
      }
    });
  });
}

function setupNorthStarMechanismsControls() {
  if (northStarMechanismsControlsAttached) return;
  const searchInput = $("#ns-mechanisms-search");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.filters.northStarMechanisms.search = searchInput.value.trim();
      renderNorthStarMechanisms();
    });
  }
  setupNorthStarMechanismsTagSelects();
  northStarMechanismsControlsAttached = true;
}

function renderNorthStarMechanisms() {
  const container = $("#north-star-mechanisms");
  const meta = $("#north-star-mechanisms-meta");
  if (!container) return;
  const registry = unwrap(state.northStarMechanismsRegistry || {}) || {};
  const history = unwrap(state.northStarMechanismsHistory || {}) || {};
  updateNorthStarMechanismsFilterOptions(registry, history);
  setupNorthStarMechanismsControls();
  const searchInput = $("#ns-mechanisms-search");
  if (searchInput) searchInput.value = state.filters.northStarMechanisms.search || "";
  ["subject", "status"].forEach((field) => renderNorthStarMechanismsTagSelect(field));
  const selectedSubjects = state.filters?.northStarMechanisms?.subject || [];
  const subjectId = Array.isArray(selectedSubjects) ? (selectedSubjects.length === 1 ? String(selectedSubjects[0] || "") : "") : String(selectedSubjects || "");
  const filteredSubjects = getFilteredMechanismsSubjects(registry).map((subject) => {
    const currentId = String(subject?.subject_id || "").trim();
    return subject;
  });
  if (meta) meta.textContent = t("north_star.mechanisms.meta", { count: String(filteredSubjects.length) });
  if (!filteredSubjects.length) {
    container.innerHTML = `<div class="subtle">${escapeHtml(t("north_star.mechanisms.empty"))}</div>`;
    return;
  }
  const blocks = filteredSubjects
    .map((subject) => {
      const subjectId = String(subject?.subject_id || "").trim();
      const historySubject = getMechanismsHistorySubject(history, subjectId);
      const latestLabel = formatVersionLabel(getLatestMechanismsVersionLabel(historySubject));
      const selectedVersionLabel = latestLabel ? `Güncel ${latestLabel}` : "";
      const subjectLabel = localizeTrEnLabel(subject?.subject_title_tr, subject?.subject_title_en, subjectId || t("north_star.unknown"));
      const status = String(subject?.status || "").toUpperCase() || "UNKNOWN";
      const statusLabel = getMechanismsStatusLabel(status);
      const versionBadge = selectedVersionLabel
        ? `<span class="badge version" title="${escapeHtml(selectedVersionLabel)}">Güncel ${escapeHtml(latestLabel)}</span>`
        : "";
      const themes = Array.isArray(subject?.themes) ? subject.themes : [];
      const transferState = getMechanismsSubjectTransferState(subject);
      const transferEnabled = transferState.enabled;
      const transferBtnLabel = t("north_star.mechanisms.transfer_btn");
      const transferBtnTitle = t("north_star.mechanisms.transfer_title");
      const transferBtnDisabledTitle = transferState.blockedTitle || t("north_star.mechanisms.transfer_blocked_hint");
      const transferSubjectBtn = renderFindingsTransferButton({
        enabled: transferEnabled,
        subjectId,
        themeLabel: "",
        subthemeLabel: "",
        targetLabel: subjectLabel || subjectId || t("north_star.unknown"),
        buttonLabel: transferBtnLabel,
        enabledTitle: transferBtnTitle,
        disabledTitle: transferBtnDisabledTitle,
      });
      const themeBlocks = themes
        .map((theme) => {
          const themeId = String(theme?.theme_id || "").trim();
          const themeLabel = localizeTrEnLabel(
            theme?.title_tr || theme?.theme_title_tr,
            theme?.title_en || theme?.theme_title_en,
            theme?.theme_id
          );
          const themeFilterLabel = formatTrEnLabel(
            theme?.title_tr || theme?.theme_title_tr,
            theme?.title_en || theme?.theme_title_en,
            theme?.theme_id || ""
          );
          const subthemes = Array.isArray(theme?.subthemes) ? theme.subthemes : [];
          const subList = subthemes
            .map((sub) => {
              const subLabel = localizeTrEnLabel(
                sub?.title_tr || sub?.subtheme_title_tr,
                sub?.title_en || sub?.subtheme_title_en,
                sub?.subtheme_id
              );
              const subFilterLabel = formatTrEnLabel(
                sub?.title_tr || sub?.subtheme_title_tr,
                sub?.title_en || sub?.subtheme_title_en,
                sub?.subtheme_id || ""
              );
              const subId = String(sub?.subtheme_id || "").trim();
              const aiId = subId || `${themeId || "sub"}:${subLabel}`;
              const subIdHtml = subId
                ? `<span class="meta-id">ID: <span class="meta-id__value">${escapeHtml(subId)}</span></span>`
                : `<span class="meta-id">ID: <span class="meta-id__value">-</span></span>`;
              const transferSubBtn = (themeFilterLabel || subFilterLabel)
                ? renderFindingsTransferButton({
                    enabled: transferEnabled,
                    subjectId,
                    themeLabel: themeFilterLabel || "",
                    subthemeLabel: subFilterLabel || "",
                    targetLabel: subLabel || t("north_star.unknown"),
                    buttonLabel: transferBtnLabel,
                    enabledTitle: transferBtnTitle,
                    disabledTitle: transferBtnDisabledTitle,
                  })
                : "";
              const matrixPanel = renderNorthStarSubthemeMatrixPanel({
                subjectId,
                themeId,
                themeLabel: themeFilterLabel || themeLabel || "",
                subthemeId: subId,
                subthemeLabel: subFilterLabel || subLabel || "",
                transferEnabled,
                transferDisabledTitle: transferBtnDisabledTitle,
              });
              return `<li>
                <details>
                  <summary style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                    <strong>${escapeHtml(subLabel || t("north_star.unknown"))}</strong>
                    ${subIdHtml}
                    ${transferSubBtn}
                    <button class="btn ghost tiny ai-icon" data-ai-suggest="1" data-ai-subject="${escapeHtml(subjectId)}" data-ai-type="subtheme" data-ai-id="${escapeHtml(aiId)}" data-ai-label="${escapeHtml(subLabel || "")}" data-ai-subject-label="${escapeHtml(subjectLabel || "")}" data-ai-theme="${escapeHtml(themeLabel || "")}" data-ai-subtheme="${escapeHtml(subLabel || "")}" title="AI"><span class="ai-icon-glyph" aria-hidden="true"><svg viewBox="6 6 52 52"><path d="M26 10.2l3.9 10.8L40.7 25l-10.8 3.9L26 39.7l-3.9-10.8L11.3 25l10.8-3.9L26 10.2z"></path><path d="M44.7 33l2.2 6.5 6.8 2.2-6.8 2.2-2.2 6.5-2.2-6.5-6.5-2.2 6.5-2.2 2.2-6.5z"></path><path d="M51.5 10.2l1.6 4.8 4.8 1.6-4.8 1.6-1.6 4.8-1.6-4.8-4.8-1.6 4.8-1.6 1.6-4.8z"></path><text x="8" y="59" font-size="29" font-weight="600" font-family="Arial, sans-serif">AI</text></svg></span></button>
                    <span class="badge">${escapeHtml(t("north_star.mechanisms.matrix_toggle"))}</span>
                  </summary>
                  ${matrixPanel}
                </details>
              </li>`;
            })
            .join("");
          const def = localizeTrEnLabel(
            theme?.definition_tr || theme?.theme_definition_tr,
            theme?.definition_en || theme?.theme_definition_en,
            ""
          );
          const themeIdHtml = themeId
            ? `<span class="meta-id">ID: <span class="meta-id__value">${escapeHtml(themeId)}</span></span>`
            : `<span class="meta-id">ID: <span class="meta-id__value">-</span></span>`;
          const transferThemeBtn = themeFilterLabel
            ? renderFindingsTransferButton({
                enabled: transferEnabled,
                subjectId,
                themeLabel: themeFilterLabel,
                subthemeLabel: "",
                targetLabel: themeLabel || t("north_star.unknown"),
                buttonLabel: transferBtnLabel,
                enabledTitle: transferBtnTitle,
                disabledTitle: transferBtnDisabledTitle,
              })
            : "";
          return `<details><summary><strong>${escapeHtml(themeLabel || t("north_star.unknown"))}</strong> <span class="subtle">(${subthemes.length})</span> ${themeIdHtml} ${transferThemeBtn} <button class="btn ghost tiny ai-icon" data-ai-suggest="1" data-ai-subject="${escapeHtml(subjectId)}" data-ai-type="theme" data-ai-id="${escapeHtml(themeId || subjectId)}" data-ai-label="${escapeHtml(themeLabel || "")}" data-ai-subject-label="${escapeHtml(subjectLabel || "")}" data-ai-theme="${escapeHtml(themeLabel || "")}" title="AI"><span class="ai-icon-glyph" aria-hidden="true"><svg viewBox="6 6 52 52"><path d="M26 10.2l3.9 10.8L40.7 25l-10.8 3.9L26 39.7l-3.9-10.8L11.3 25l10.8-3.9L26 10.2z"></path><path d="M44.7 33l2.2 6.5 6.8 2.2-6.8 2.2-2.2 6.5-2.2-6.5-6.5-2.2 6.5-2.2 2.2-6.5z"></path><path d="M51.5 10.2l1.6 4.8 4.8 1.6-4.8 1.6-1.6 4.8-1.6-4.8-4.8-1.6 4.8-1.6 1.6-4.8z"></path><text x="8" y="59" font-size="29" font-weight="600" font-family="Arial, sans-serif">AI</text></svg></span></button></summary>${def ? `<div class="subtle">${escapeHtml(def)}</div>` : ""}${subList ? `<ul class="subtle">${subList}</ul>` : `<div class="subtle">${escapeHtml(t("north_star.unknown"))}</div>`}</details>`;
        })
        .join("");
      const aiSubjectBadge = `<button type="button" class="btn ghost tiny ai-icon" data-ai-suggest="1" data-ai-subject="${escapeHtml(subjectId)}" data-ai-type="subject" data-ai-id="${escapeHtml(subjectId)}" data-ai-label="${escapeHtml(subjectLabel || "")}" data-ai-subject-label="${escapeHtml(subjectLabel || "")}" title="AI öneri"><span class="ai-icon-glyph" aria-hidden="true"><svg viewBox="6 6 52 52"><path d="M26 10.2l3.9 10.8L40.7 25l-10.8 3.9L26 39.7l-3.9-10.8L11.3 25l10.8-3.9L26 10.2z"></path><path d="M44.7 33l2.2 6.5 6.8 2.2-6.8 2.2-2.2 6.5-2.2-6.5-6.5-2.2 6.5-2.2 2.2-6.5z"></path><path d="M51.5 10.2l1.6 4.8 4.8 1.6-4.8 1.6-1.6 4.8-1.6-4.8-4.8-1.6 4.8-1.6 1.6-4.8z"></path><text x="8" y="59" font-size="29" font-weight="600" font-family="Arial, sans-serif">AI</text></svg></span><span style="margin-left:4px;">AI öneri</span></button>`;
      const subjectIdHtml = subjectId ? `<span class="meta-id">ID: <span class="meta-id__value">${escapeHtml(subjectId)}</span></span>` : "";
      return `<div class="card" style="margin-bottom:12px;">
        <div class="row" style="justify-content:space-between;gap:8px;align-items:center;">
          <div><strong>${escapeHtml(subjectLabel)}</strong> ${subjectIdHtml} ${transferSubjectBtn} ${aiSubjectBadge}</div>
          <div class="row" style="gap:6px;align-items:center;">${versionBadge}<div class="badge">${escapeHtml(statusLabel)}</div></div>
        </div>
        ${themeBlocks || `<div class="subtle">${escapeHtml(t("north_star.unknown"))}</div>`}
      </div>`;
    })
    .join("");
  container.innerHTML = blocks;
  attachNorthStarSuggestionHandlers();
}

function renderNorthStarSuggestions() {
  const container = $("#north-star-suggestions");
  const meta = $("#north-star-suggestions-meta");
  if (!container) return;
  const store = unwrap(state.northStarMechanismsSuggestions || {}) || {};
  const items = Array.isArray(store.suggestions) ? store.suggestions : [];
  const filters = state.northStarSuggestionsFilters || {
    search: "",
    subject: "",
    theme: "",
    subtheme: "",
    type: "",
    date_from: "",
    date_to: "",
  };
  state.northStarSuggestionsFilters = filters;
  const formatDateInput = (date) => {
    if (!date) return "";
    const tzOffset = date.getTimezoneOffset() * 60000;
    const local = new Date(date.getTime() - tzOffset);
    return local.toISOString().slice(0, 10);
  };
  if (!filters._initialized) {
    const selectedSubjects = state.filters?.northStarMechanisms?.subject || [];
    if (!filters.subject && Array.isArray(selectedSubjects) && selectedSubjects.length) {
      filters.subject = String(selectedSubjects[0] || "");
    }
    const ctx = state.aiSuggestSelectionContext || {};
    if (!filters.subject && ctx.subject) filters.subject = String(ctx.subject);
    if (!filters.theme && ctx.theme) filters.theme = String(ctx.theme);
    if (!filters.subtheme && ctx.subtheme) filters.subtheme = String(ctx.subtheme);
    if (!filters.date_from && !filters.date_to) {
      const today = formatDateInput(new Date());
      filters.date_from = today;
      filters.date_to = today;
    }
    filters._initialized = true;
  }

  const normalize = (val) => String(val || "").toLowerCase();
  const parseMulti = (val) =>
    String(val || "")
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .map((v) => normalize(v));
  const formatLocalDate = (value) => {
    const ts = Date.parse(String(value || ""));
    if (!Number.isFinite(ts)) return "";
    const date = new Date(ts);
    const tzOffset = date.getTimezoneOffset() * 60000;
    const local = new Date(date.getTime() - tzOffset);
    return local.toISOString().slice(0, 10);
  };
  const formatLocalDateTime = (value) => {
    const ts = Date.parse(String(value || ""));
    if (!Number.isFinite(ts)) return "";
    const date = new Date(ts);
    const tzOffset = date.getTimezoneOffset() * 60000;
    const local = new Date(date.getTime() - tzOffset);
    return `${local.toISOString().slice(0, 10)} ${local.toISOString().slice(11, 19)}`;
  };

  const filteredItems = items.filter((s) => {
    const searchTerm = normalize(filters.search);
    const subjList = parseMulti(filters.subject);
    const themeList = parseMulti(filters.theme);
    const subthemeList = parseMulti(filters.subtheme);
    const typeList = parseMulti(filters.type);
    if (subjList.length && !subjList.includes(normalize(s?.subject_id))) return false;
    if (themeList.length && !themeList.includes(normalize(s?.target_id))) return false;
    if (subthemeList.length && !subthemeList.includes(normalize(s?.target_id))) return false;
    if (typeList.length && !typeList.includes(normalize(s?.suggestion_type))) return false;
    const createdAt = String(s?.created_at || "");
    const createdLocal = formatLocalDate(createdAt);
    if (searchTerm) {
      const hay = [
        s?.suggestion_id,
        s?.subject_id,
        s?.target_id,
        s?.suggestion_type,
        s?.target_type,
        s?.status,
        createdAt,
        createdLocal,
        s?.payload ? JSON.stringify(s.payload) : "",
      ]
        .map((v) => String(v || ""))
        .join(" ")
        .toLowerCase();
      if (!hay.includes(searchTerm)) return false;
    }
    const fromDate = String(filters.date_from || "").trim();
    const toDate = String(filters.date_to || "").trim();
    if ((fromDate || toDate) && !createdLocal) return false;
    if (fromDate && createdLocal < fromDate) return false;
    if (toDate && createdLocal > toDate) return false;
    return true;
  });

  const proposed = items.filter((s) => String(s?.status || "").toUpperCase() === "PROPOSED");
  if (meta) meta.textContent = t("north_star.suggestions.meta", { count: String(proposed.length) });
  const filterBar = `<div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:8px;">
      <input class="input" style="min-width:180px" placeholder="${escapeHtml(t("north_star.suggestions.filter.search"))}" value="${escapeHtml(filters.search || "")}" data-suggest-filter="search"/>
      <input class="input" style="min-width:180px" placeholder="${escapeHtml(t("north_star.suggestions.filter.subject"))}" value="${escapeHtml(filters.subject || "")}" data-suggest-filter="subject"/>
      <input class="input" style="min-width:180px" placeholder="${escapeHtml(t("north_star.suggestions.filter.theme"))}" value="${escapeHtml(filters.theme || "")}" data-suggest-filter="theme"/>
      <input class="input" style="min-width:180px" placeholder="${escapeHtml(t("north_star.suggestions.filter.subtheme"))}" value="${escapeHtml(filters.subtheme || "")}" data-suggest-filter="subtheme"/>
      <input class="input" style="min-width:160px" placeholder="${escapeHtml(t("north_star.suggestions.filter.type"))}" value="${escapeHtml(filters.type || "")}" data-suggest-filter="type"/>
      <label class="subtle" style="align-self:center;">${escapeHtml(t("north_star.suggestions.filter.date_from"))}</label>
      <input class="input" type="date" style="min-width:150px" value="${escapeHtml(filters.date_from || "")}" data-suggest-filter="date_from"/>
      <label class="subtle" style="align-self:center;">${escapeHtml(t("north_star.suggestions.filter.date_to"))}</label>
      <input class="input" type="date" style="min-width:150px" value="${escapeHtml(filters.date_to || "")}" data-suggest-filter="date_to"/>
      <div class="row" style="gap:6px;align-items:center;">
        <button class="btn ghost small" type="button" data-suggest-range="today">${escapeHtml(t("north_star.suggestions.filter.quick.today"))}</button>
        <button class="btn ghost small" type="button" data-suggest-range="7d">${escapeHtml(t("north_star.suggestions.filter.quick.week"))}</button>
        <button class="btn ghost small" type="button" data-suggest-range="30d">${escapeHtml(t("north_star.suggestions.filter.quick.month"))}</button>
        <button class="btn ghost small" type="button" data-suggest-range="all">${escapeHtml(t("north_star.suggestions.filter.quick.all"))}</button>
      </div>
      <div class="subtle" style="align-self:center;">${escapeHtml(t("north_star.suggestions.filter.multi_hint") || "Çoklu değer için virgül kullanın.")}</div>
    </div>`;

  const bindSuggestionFilters = () => {
    $$("[data-suggest-filter]").forEach((el) => {
      const handler = () => {
        state.northStarSuggestionsFilters = {
          ...state.northStarSuggestionsFilters,
          [el.dataset.suggestFilter]: el.value,
        };
        renderNorthStarSuggestions();
      };
      el.oninput = handler;
      el.onchange = handler;
    });
    $$("[data-suggest-range]").forEach((btn) => {
      btn.onclick = () => {
        const range = btn.dataset.suggestRange || "";
        if (range === "all") {
          state.northStarSuggestionsFilters = {
            ...state.northStarSuggestionsFilters,
            date_from: "",
            date_to: "",
          };
          renderNorthStarSuggestions();
          return;
        }
        const now = new Date();
        let from = new Date(now.getTime());
        if (range === "7d") {
          from = new Date(now.getTime() - 6 * 86400000);
        } else if (range === "30d") {
          from = new Date(now.getTime() - 29 * 86400000);
        }
        const fromStr = formatDateInput(from);
        const toStr = formatDateInput(now);
        state.northStarSuggestionsFilters = {
          ...state.northStarSuggestionsFilters,
          date_from: fromStr,
          date_to: toStr,
        };
        renderNorthStarSuggestions();
      };
    });
  };

  if (!filteredItems.length) {
    container.innerHTML = `${filterBar}<div class="subtle">${escapeHtml(t("north_star.suggestions.empty"))}</div>`;
    attachNorthStarSuggestionHandlers();
    bindSuggestionFilters();
    return;
  }

  const rows = filteredItems
    .map((s) => {
      const id = String(s?.suggestion_id || "");
      const subjectId = String(s?.subject_id || "");
      const sType = String(s?.suggestion_type || "");
      const target = String(s?.target_id || "");
      const payload = s?.payload ? JSON.stringify(s.payload) : "";
      const targetType = String(s?.target_type || "");
      const createdAt = String(s?.created_at || "");
      const createdLocal = formatLocalDateTime(createdAt);
      const createdLabel = createdLocal || createdAt;
      return `<div class="card" style="margin-bottom:8px;">
        <div class="row" style="justify-content:space-between;gap:8px;align-items:center;">
          <div>
            <div><strong>${escapeHtml(sType)}</strong> <span class="subtle">(${escapeHtml(target)})</span></div>
            <div class="subtle" title="${escapeHtml(createdAt)}">${escapeHtml(subjectId)} • ${escapeHtml(id)} • ${escapeHtml(createdLabel)}</div>
          </div>
          <div class="row" style="gap:6px;">
            <button class="btn small ghost" data-suggest-action="ACCEPT" data-suggest-id="${escapeHtml(id)}">${escapeHtml(t("north_star.suggestions.accept"))}</button>
            <button class="btn small ghost" data-suggest-action="REJECT" data-suggest-id="${escapeHtml(id)}">${escapeHtml(t("north_star.suggestions.reject"))}</button>
            <button class="btn small ghost" data-suggest-action="MERGE" data-suggest-id="${escapeHtml(id)}">${escapeHtml(t("north_star.suggestions.merge"))}</button>
            <button class="btn small ghost" data-suggest-discuss="1" data-ai-subject="${escapeHtml(subjectId)}" data-ai-type="${escapeHtml(targetType)}" data-ai-id="${escapeHtml(target)}" data-ai-label="${escapeHtml(target)}" title="${escapeHtml(t("north_star.suggestions.discuss"))}">${escapeHtml(t("north_star.suggestions.discuss"))}</button>
          </div>
        </div>
        ${payload ? `<div class="subtle" style="margin-top:6px;">${escapeHtml(payload)}</div>` : ""}
      </div>`;
    })
    .join("");
  container.innerHTML = `${filterBar}${rows}`;
  attachNorthStarSuggestionHandlers();
  bindSuggestionFilters();
}

function loadAiSuggestThreadStorage() {
  try {
    const raw = localStorage.getItem(AI_SUGGEST_THREAD_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    return parsed;
  } catch (_) {
    return {};
  }
}

function saveAiSuggestThreadStorage(map) {
  try {
    localStorage.setItem(AI_SUGGEST_THREAD_STORAGE_KEY, JSON.stringify(map || {}));
  } catch (_) {
    // ignore storage errors
  }
}

function getAiSuggestThreadsByKey() {
  if (!state.aiSuggestThreadsByKey) state.aiSuggestThreadsByKey = loadAiSuggestThreadStorage();
  return state.aiSuggestThreadsByKey;
}

function rememberAiSuggestThread(threadKey, threadId) {
  if (!threadKey || !threadId) return;
  const map = getAiSuggestThreadsByKey();
  map[threadKey] = threadId;
  saveAiSuggestThreadStorage(map);
}

function pickAiSuggestThread(threadKey, fallback) {
  const map = getAiSuggestThreadsByKey();
  return map[threadKey] || fallback || "";
}

function ensureOpOk(result, opName) {
  if (!result) {
    throw new Error(`${opName || "op"}: NO_RESPONSE`);
  }
  const status = String(result?.status || "").toUpperCase();
  if (status.includes("FAIL") || result?.error) {
    throw new Error(`${opName || "op"}: ${result?.error || result?.status || "FAIL"}`);
  }
  return result;
}

function collectSuggestionsForSelection(subjectId, focusType, focusId, sinceTs) {
  const store = unwrap(state.northStarMechanismsSuggestions || {}) || {};
  const items = Array.isArray(store.suggestions) ? store.suggestions : [];
  const since = Number.isFinite(sinceTs) ? sinceTs : 0;
  return items.filter((s) => {
    if (subjectId && String(s?.subject_id || "") !== String(subjectId)) return false;
    if (focusType && String(s?.target_type || "") !== String(focusType)) return false;
    if (focusId && String(s?.target_id || "") !== String(focusId)) return false;
    if (!since) return true;
    const ts = Date.parse(String(s?.created_at || ""));
    return Number.isFinite(ts) ? ts >= since : true;
  });
}

function summarizeSuggestions(items) {
  if (!items.length) return "";
  const lines = items.slice(0, 6).map((s) => {
    const sType = String(s?.suggestion_type || "");
    const target = String(s?.target_id || "");
    const reason = String(s?.payload?.reason_tr || s?.payload?.reason_en || "");
    return `• ${sType} → ${target}${reason ? ` — ${reason}` : ""}`;
  });
  const suffix = items.length > 6 ? `\n… +${items.length - 6} more` : "";
  return `${lines.join("\n")}${suffix}`;
}

async function waitForSuggestions({ subjectId, focusType, focusId, sinceTs, attempts = 6, delayMs = 1500 }) {
  let found = [];
  for (let i = 0; i < attempts; i += 1) {
    await refreshNorthStar();
    found = collectSuggestionsForSelection(subjectId, focusType, focusId, sinceTs);
    if (found.length) break;
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return found;
}

function _threadSafePart(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function _threadHash(value) {
  const text = String(value || "");
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

function _trimThreadId(value, max = 64) {
  const text = String(value || "");
  if (text.length <= max) return text;
  const suffix = _threadHash(text);
  const keep = Math.max(8, max - suffix.length - 1);
  return `${text.slice(0, keep)}_${suffix}`;
}

function getAiSuggestThreadPrefix(subjectId, focusType, focusId) {
  if (!subjectId) return "";
  const type = _threadSafePart(focusType || "subject") || "subject";
  const id = _threadSafePart(focusId || subjectId) || "subject";
  const subject = _threadSafePart(subjectId) || "subject";
  return _trimThreadId(`ns_ai.${subject}.${type}.${id}`);
}

async function ensurePlannerThreadsLoaded(force = false) {
  if (state.plannerThreads && !force) return state.plannerThreads;
  try {
    state.plannerThreads = await fetchJson(endpoints.plannerThreads);
  } catch (_) {
    state.plannerThreads = { threads: [] };
  }
  return state.plannerThreads;
}

function filterAiSuggestThreads(prefix) {
  const items = Array.isArray(state.plannerThreads?.threads) ? state.plannerThreads.threads : [];
  if (!prefix) return [];
  return items
    .map((t) => ({ thread: String(t.thread || ""), count: t.count, last: t.last }))
    .filter((t) => t.thread.startsWith(prefix));
}

function buildAiSuggestThreadId(prefix, suffix = "") {
  const stamp = new Date().toISOString().replace(/[:.]/g, "").toLowerCase();
  const safeSuffix = _threadSafePart(suffix);
  const base = safeSuffix ? `${prefix}.${safeSuffix}` : `${prefix}.${stamp}`;
  return _trimThreadId(base);
}

function formatAiSuggestThreadLabel(threadId) {
  const parts = String(threadId || "").split(":");
  const suffix = parts.slice(-1)[0] || threadId;
  return suffix;
}

function sanitizeOpArgValue(value, { maxLen = 1200, allowNewlines = false } = {}) {
  let text = String(value ?? "");
  if (allowNewlines) {
    text = text.replace(/\r\n?/g, "\n");
  }
  text = text.replace(/[\u0000-\u0008\u000B-\u001F\u007F]+/g, "");
  text = text.trim();
  if (!allowNewlines) {
    text = text.replace(/\s+/g, " ");
  }
  if (text.length > maxLen) text = text.slice(0, maxLen);
  return text;
}

function buildAiSuggestPromptContext({ subjectLabel, subjectId, themeLabel, subthemeLabel } = {}) {
  const topic = (subjectLabel || subjectId || "").trim();
  const level = subthemeLabel ? "modül" : themeLabel ? "süreç" : "program";
  const scopeParts = [topic, themeLabel, subthemeLabel].filter((part) => part && String(part).trim());
  const scopeText = scopeParts.length ? scopeParts.join(" > ") : "belirtilmedi";
  const topicText = topic || "belirtilmedi";
  return `KONU: ${topicText}\nSEVİYE: ${level}\nKAPSAM: Dahil: ${scopeText}; Hariç: belirtilmedi\nBAĞLAM: varsayılan`;
}

function mergeAiSuggestPromptContext(comment, autoContext) {
  const base = String(comment || "").trim();
  const context = String(autoContext || "").trim();
  if (!context) return base;
  if (base && /KONU\s*:/i.test(base)) return base;
  if (!base) return context;
  return `${context}\n\n${base}`;
}

async function loadAiSuggestThreadMessages(threadId) {
  if (!threadId) return [];
  try {
    const payload = await fetchJson(`${endpoints.plannerChat}?thread=${encodeURIComponent(threadId)}`);
    return Array.isArray(payload?.items) ? payload.items.map(normalizeNote) : [];
  } catch (_) {
    return [];
  }
}

function renderAiSuggestHistory(container, items) {
  if (!container) return;
  if (!Array.isArray(items) || items.length === 0) {
    container.innerHTML = `<div class="subtle">${escapeHtml(t("north_star.suggestions.modal_history_empty") || "Henüz mesaj yok.")}</div>`;
    return;
  }
  container.innerHTML = items
    .map((item) => {
      const role = noteRole(item);
      const title = escapeHtml(String(item.title || ""));
      const body = escapeHtml(String(item.body || ""));
      const meta = escapeHtml(String(item.updated_at || item.created_at || ""));
      const header = title ? `${title} · ${meta}` : meta;
      return `<div class="msg ${role}"><span class="meta">${header}</span><div>${body}</div></div>`;
    })
    .join("");
  container.scrollTop = container.scrollHeight;
}

async function openNorthStarSuggestModal({
  title,
  hint,
  promptIntent,
  selectionLabel,
  showMergeTarget,
  showModelSelect,
  profileDefault,
  threadKey,
  threadLabel,
  defaultComment,
  autoPromptContext,
  disableEnterSubmit,
  commentMaxLen,
  skipSuggestionWait,
  openChatLabel,
  onOpenChat,
  keepOpenOnSubmit,
  onSubmit,
}) {
  const modal = $("#ai-suggest-modal");
  const titleEl = $("#ai-suggest-title");
  const hintEl = $("#ai-suggest-hint");
  const intentEl = $("#ai-suggest-intent");
  const commentEl = $("#ai-suggest-comment");
  const selectsWrap = $("#ai-suggest-selects");
  const historyEl = $("#ai-suggest-history");
  const threadEl = $("#ai-suggest-thread");
  const contextEl = $("#ai-suggest-context");
  const statusEl = $("#ai-suggest-status");
  const openChatBtn = $("#ai-suggest-open-chat");
  const threadSelect = $("#ai-suggest-thread-select");
  const threadNewBtn = $("#ai-suggest-thread-new");
  const mergeWrap = $("#ai-suggest-merge-wrap");
  const mergeEl = $("#ai-suggest-merge");
  const submitBtn = $("#ai-suggest-submit");
  const cancelBtn = $("#ai-suggest-cancel");
  const closeBtn = $("#ai-suggest-close");
  if (!modal || !titleEl || !hintEl || !commentEl || !mergeWrap || !mergeEl || !submitBtn || !cancelBtn) {
    return Promise.resolve({ comment: "", mergeTarget: "", provider: "", model: "", profile: "" });
  }

  titleEl.textContent = title || t("north_star.suggestions.modal_title");
  hintEl.textContent = hint || t("north_star.suggestions.modal_hint");
  if (intentEl) {
    const intentText = String(promptIntent || "").trim();
    if (intentText) {
      intentEl.textContent = `${t("north_star.suggestions.modal_intent")}: ${intentText}`;
      intentEl.style.display = "block";
    } else {
      intentEl.textContent = "";
      intentEl.style.display = "none";
    }
  }
  const commentDefault = String(defaultComment || "");
  const promptContext = String(autoPromptContext || "");
  commentEl.dataset.autoPromptContext = promptContext;
  commentEl.value = mergeAiSuggestPromptContext(commentDefault, promptContext);
  if (disableEnterSubmit) {
    commentEl.dataset.disableEnterSubmit = "1";
  } else {
    commentEl.dataset.disableEnterSubmit = "";
  }
  mergeEl.value = "";
  if (statusEl) {
    statusEl.textContent = t("north_star.suggestions.modal_status_idle") || "";
    statusEl.classList.remove("warn");
  }
  state.aiSuggestSelectionLabel = selectionLabel || "";
  if (threadEl) {
    threadEl.textContent = "";
    threadEl.style.display = "none";
  }
  if (contextEl) {
    const label = selectionLabel ? `<strong>${escapeHtml(t("north_star.suggestions.modal_context_label"))}:</strong> ${escapeHtml(selectionLabel)}` : "";
    contextEl.innerHTML = label || `<span class="subtle">${escapeHtml(t("north_star.unknown"))}</span>`;
  }
  await ensurePlannerThreadsLoaded(true);
  const prefix = threadKey || "";
  let availableThreads = filterAiSuggestThreads(prefix);
  const rememberedThread = prefix ? pickAiSuggestThread(prefix, "") : "";
  if (rememberedThread && !availableThreads.some((t) => t.thread === rememberedThread)) {
    availableThreads = [{ thread: rememberedThread, count: 0, last: "" }].concat(availableThreads);
  }
  if (!availableThreads.length && prefix) {
    const created = buildAiSuggestThreadId(prefix, "default");
    availableThreads = [{ thread: created, count: 0, last: "" }];
  }
  if (threadSelect) {
    threadSelect.innerHTML = availableThreads
      .map((t) => `<option value="${escapeHtml(t.thread)}">${escapeHtml(formatAiSuggestThreadLabel(t.thread))}</option>`)
      .join("");
    threadSelect.value = pickAiSuggestThread(prefix, availableThreads[0]?.thread || "");
  }
  let activeThread = threadSelect ? threadSelect.value : availableThreads[0]?.thread || "";
  rememberAiSuggestThread(prefix, activeThread);
  if (openChatBtn) {
    if (openChatLabel) {
      openChatBtn.textContent = String(openChatLabel);
    } else {
      openChatBtn.textContent = t("north_star.suggestions.modal_open_chat");
    }
    openChatBtn.onclick = () => {
      if (!activeThread) return;
      if (typeof onOpenChat === "function") {
        onOpenChat({
          thread: activeThread,
          comment: mergeAiSuggestPromptContext(commentEl.value || "", commentEl.dataset.autoPromptContext || ""),
          selectionLabel: selectionLabel || "",
        });
        close(null);
        return;
      }
      state.plannerThread = activeThread;
      const threadInput = $("#planner-thread");
      if (threadInput) threadInput.value = activeThread;
      navigateToTab("planner-chat");
      refreshNotes();
      close(null);
    };
  }
  if (historyEl) {
    const items = await loadAiSuggestThreadMessages(activeThread);
    renderAiSuggestHistory(historyEl, items);
  }
  if (threadSelect) {
    threadSelect.onchange = async () => {
      activeThread = threadSelect.value || "";
      rememberAiSuggestThread(prefix, activeThread);
      const items = await loadAiSuggestThreadMessages(activeThread);
      renderAiSuggestHistory(historyEl, items);
    };
  }
  if (threadNewBtn) {
    threadNewBtn.onclick = async () => {
      if (!prefix) return;
      const fresh = buildAiSuggestThreadId(prefix, "");
      const nextList = [{ thread: fresh, count: 0, last: "" }].concat(availableThreads);
      availableThreads = nextList;
      if (threadSelect) {
        threadSelect.innerHTML = availableThreads
          .map((t) => `<option value="${escapeHtml(t.thread)}">${escapeHtml(formatAiSuggestThreadLabel(t.thread))}</option>`)
          .join("");
        threadSelect.value = fresh;
      }
      activeThread = fresh;
      rememberAiSuggestThread(prefix, activeThread);
      const items = await loadAiSuggestThreadMessages(activeThread);
      renderAiSuggestHistory(historyEl, items);
    };
  }
  mergeWrap.style.display = showMergeTarget ? "block" : "none";
  if (selectsWrap) {
    selectsWrap.style.display = showModelSelect ? "grid" : "none";
  }
  if (showModelSelect) {
    await ensureChatProviderRegistryLoaded();
    const profileHint = profileDefault || resolveSuggestProfileDefault("consult");
    renderAiSuggestModelSelectors(profileHint);
  } else {
    state.aiSuggestProfile = "";
    state.aiSuggestProvider = "";
    state.aiSuggestModel = "";
  }

  let resolve;
  const promise = new Promise((res) => {
    resolve = res;
  });

  const onBackdrop = (event) => {
    if (event.target !== modal) return;
    close(null);
  };

  const onKeydown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close(null);
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      submitBtn.click();
    }
  };
  const onCommentKeydown = (event) => {
    if (event.key !== "Enter") return;
    if (commentEl.dataset.disableEnterSubmit === "1") return;
    if (event.shiftKey || event.altKey) return;
    if (event.isComposing) return;
    event.preventDefault();
    submitBtn.click();
  };

  const close = (result) => {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    submitBtn.onclick = null;
    cancelBtn.onclick = null;
    if (closeBtn) closeBtn.onclick = null;
    modal.removeEventListener("mousedown", onBackdrop);
    document.removeEventListener("keydown", onKeydown);
    commentEl.removeEventListener("keydown", onCommentKeydown);
    resolve(result);
  };

  submitBtn.onclick = async () => {
    const commentRaw = commentEl.value || "";
    const autoContext = commentEl.dataset.autoPromptContext || "";
    const mergedComment = mergeAiSuggestPromptContext(commentRaw, autoContext);
    const maxLen = Number.isFinite(Number(commentMaxLen)) ? Number(commentMaxLen) : 1200;
    const commentOpBase = sanitizeOpArgValue(mergedComment, { maxLen, allowNewlines: false });
    const commentChatBase = sanitizeOpArgValue(mergedComment, { maxLen, allowNewlines: true });
    const mergeTarget = sanitizeOpArgValue(mergeEl.value, { maxLen: 120 });
    const provider = showModelSelect ? sanitizeOpArgValue(state.aiSuggestProvider || "", { maxLen: 80 }) : "";
    const model = showModelSelect ? sanitizeOpArgValue(state.aiSuggestModel || "", { maxLen: 120 }) : "";
    const profile = showModelSelect ? sanitizeOpArgValue(state.aiSuggestProfile || "", { maxLen: 80 }) : "";
    if (showModelSelect && (!provider || !model)) {
      showToast("Provider/model required.", "warn");
      return;
    }
    const modelHint = provider && model ? `[model_hint=${provider}/${model}]` : "";
    const commentForOp = sanitizeOpArgValue(modelHint ? `${commentOpBase} ${modelHint}`.trim() : commentOpBase, {
      maxLen: 1200,
      allowNewlines: false,
    });
    const commentWithModel = sanitizeOpArgValue(modelHint ? `${commentChatBase} ${modelHint}`.trim() : commentChatBase, {
      maxLen: 1200,
      allowNewlines: true,
    });
    const payload = { comment: commentForOp, comment_chat: commentWithModel, mergeTarget, provider, model, profile };
    const threadId = activeThread || (threadSelect ? threadSelect.value : "");
    payload.thread = threadId;
    const submitTs = Date.now();
    if (threadId) {
      const chatRes = await postOpInternal("planner-chat-send", {
        thread: threadId,
        title: "User",
        body: commentWithModel || "(boş)",
        tags: "user,ns_ai",
        links_json: "[]",
      });
      if (!chatRes?.res?.ok) {
        showToast(t("toast.op_failed", { error: chatRes?.data?.error || "CHAT_WRITE_FAILED" }), "warn");
      }
      const items = await loadAiSuggestThreadMessages(threadId);
      renderAiSuggestHistory(historyEl, items);
    }
    if (typeof onSubmit === "function") {
      submitBtn.disabled = true;
      if (statusEl) {
        statusEl.textContent = t("north_star.suggestions.modal_status_started") || "";
        statusEl.classList.remove("warn");
      }
      try {
        const result = await onSubmit(payload);
        if (statusEl) {
          statusEl.textContent = t("north_star.suggestions.modal_status_done") || "";
          statusEl.classList.remove("warn");
        }
        if (skipSuggestionWait) {
          if (threadId && result && result.note) {
            await postOpInternal("planner-chat-send", {
              thread: threadId,
              title: "Assistant",
              body: String(result.note),
              tags: "assistant,ns_ai",
              links_json: "[]",
            });
            const items = await loadAiSuggestThreadMessages(threadId);
            renderAiSuggestHistory(historyEl, items);
          }
        } else {
          const selection = {
            subjectId: result?.subject_id || "",
            focusType: result?.focus_type || "",
            focusId: result?.focus_id || "",
            sinceTs: submitTs - 2000,
          };
          const found = await waitForSuggestions({ ...selection });
          const suggestionSummary = summarizeSuggestions(found);
          if (threadId) {
            await postOpInternal("planner-chat-send", {
              thread: threadId,
              title: "Assistant",
              body:
                suggestionSummary ||
                (result && result.note ? String(result.note) : t("north_star.suggestions.thread_sent") || "İstek gönderildi."),
              tags: "assistant,ns_ai",
              links_json: "[]",
            });
            const items = await loadAiSuggestThreadMessages(threadId);
            renderAiSuggestHistory(historyEl, items);
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = t("north_star.suggestions.modal_status_error") || "İstişare başarısız.";
          statusEl.classList.add("warn");
        }
        if (threadId) {
          await postOpInternal("planner-chat-send", {
            thread: threadId,
            title: t("common.error") || "Hata",
            body: formatError(err),
            tags: "system,ns_ai",
            links_json: "[]",
          });
          const items = await loadAiSuggestThreadMessages(threadId);
          renderAiSuggestHistory(historyEl, items);
        }
        showToast(formatError(err), "warn");
      } finally {
        submitBtn.disabled = false;
      }
      commentEl.value = "";
      if (keepOpenOnSubmit) {
        commentEl.focus();
        return;
      }
      close(payload);
      return;
    }
    close(payload);
  };
  cancelBtn.onclick = () => close(null);
  if (closeBtn) closeBtn.onclick = () => close(null);

  modal.addEventListener("mousedown", onBackdrop);
  document.addEventListener("keydown", onKeydown);
  commentEl.addEventListener("keydown", onCommentKeydown);
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  commentEl.focus();

  return promise;
}

function attachNorthStarSuggestionHandlers() {
  const seedBtn = $("#ns-seed-btn");
  if (seedBtn) {
    seedBtn.onclick = async () => {
      const subjectId = String(getPrimaryMechanismsSubjectFilter() || "").trim();
      const subjectLabel = subjectId ? getMechanismsSubjectLabel(subjectId) || subjectId : "";
      const autoPromptContext = buildAiSuggestPromptContext({ subjectLabel, subjectId });
      const selectionLabel = subjectLabel
        ? `${t("north_star.suggestions.modal_context_subject")}: ${subjectLabel}`
        : "";
      const modalResult = await openNorthStarSuggestModal({
        title: t("north_star.suggestions.seed_btn"),
        hint: t("north_star.suggestions.seed_confirm"),
        promptIntent: t("north_star.suggestions.modal_intent_seed"),
        selectionLabel,
        showMergeTarget: false,
        showModelSelect: true,
        profileDefault: resolveSuggestProfileDefault("seed"),
        threadKey: getAiSuggestThreadPrefix(subjectId, "subject", subjectId),
        threadLabel: subjectId ? `${subjectId} · seed` : "",
        autoPromptContext,
        keepOpenOnSubmit: true,
        onSubmit: async (payload) => {
          ensureOpOk(
            await postOp("north-star-theme-seed", {
              subject_id: subjectId,
              provider_id: sanitizeOpArgValue(payload.provider || "", { maxLen: 80 }),
              model: sanitizeOpArgValue(payload.model || "", { maxLen: 120 }),
            }),
            "north-star-theme-seed",
          );
          await refreshNorthStar();
          return {
            note: t("north_star.suggestions.thread_sent") || "İstek gönderildi.",
            subject_id: subjectId,
            focus_type: "subject",
            focus_id: subjectId,
          };
        },
      });
      if (!modalResult) return;
    };
  }
  const consultBtn = $("#ns-consult-btn");
  if (consultBtn) {
    consultBtn.onclick = async () => {
      const subjectId = String(getPrimaryMechanismsSubjectFilter() || "").trim();
      const subjectLabel = subjectId ? getMechanismsSubjectLabel(subjectId) || subjectId : "";
      const autoPromptContext = buildAiSuggestPromptContext({ subjectLabel, subjectId });
      const selectionLabel = subjectLabel
        ? `${t("north_star.suggestions.modal_context_subject")}: ${subjectLabel}`
        : "";
      const modalResult = await openNorthStarSuggestModal({
        title: t("north_star.suggestions.consult_btn"),
        hint: t("north_star.suggestions.modal_hint"),
        promptIntent: t("north_star.suggestions.modal_intent_consult"),
        selectionLabel,
        showMergeTarget: false,
        showModelSelect: true,
        profileDefault: resolveSuggestProfileDefault("consult"),
        threadKey: getAiSuggestThreadPrefix(subjectId, "subject", subjectId),
        threadLabel: subjectId ? `${subjectId} · consult` : "",
        autoPromptContext,
        keepOpenOnSubmit: true,
        onSubmit: async (payload) => {
          ensureOpOk(
            await postOp("north-star-theme-consult", {
              subject_id: subjectId,
              providers: sanitizeOpArgValue(payload.provider || "", { maxLen: 120 }),
              comment: payload.comment || "",
            }),
            "north-star-theme-consult",
          );
          await refreshNorthStar();
          return {
            note: t("north_star.suggestions.thread_sent") || "İstek gönderildi.",
            subject_id: subjectId,
            focus_type: "subject",
            focus_id: subjectId,
          };
        },
      });
      if (!modalResult) return;
    };
  }
  $$("[data-ai-suggest]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      const subjectId = btn.dataset.aiSubject || "";
      const focusType = btn.dataset.aiType || "";
      const focusId = btn.dataset.aiId || "";
      state.aiSuggestSelectionContext = {
        subject: subjectId || "",
        theme: focusType === "theme" ? focusId : "",
        subtheme: focusType === "subtheme" ? focusId : "",
      };
      const subjectLabel = btn.dataset.aiSubjectLabel || btn.dataset.aiLabel || subjectId;
      const themeLabel = btn.dataset.aiTheme || "";
      const subthemeLabel = btn.dataset.aiSubtheme || "";
      const autoPromptContext = buildAiSuggestPromptContext({
        subjectLabel,
        subjectId,
        themeLabel,
        subthemeLabel,
      });
      let selectionLabel = "";
      if (focusType === "subtheme") {
        selectionLabel = `${t("north_star.suggestions.modal_context_subject")}: ${subjectLabel}`;
        if (themeLabel) selectionLabel += ` · ${t("north_star.suggestions.modal_context_theme")}: ${themeLabel}`;
        if (subthemeLabel) selectionLabel += ` · ${t("north_star.suggestions.modal_context_subtheme")}: ${subthemeLabel}`;
      } else if (focusType === "theme") {
        selectionLabel = `${t("north_star.suggestions.modal_context_subject")}: ${subjectLabel}`;
        if (themeLabel) selectionLabel += ` · ${t("north_star.suggestions.modal_context_theme")}: ${themeLabel}`;
      } else {
        selectionLabel = `${t("north_star.suggestions.modal_context_subject")}: ${subjectLabel}`;
      }
      const modalResult = await openNorthStarSuggestModal({
        title: t("north_star.suggestions.modal_title"),
        hint: t("north_star.suggestions.modal_hint"),
        promptIntent: t("north_star.suggestions.modal_intent_consult"),
        selectionLabel,
        showMergeTarget: false,
        showModelSelect: true,
        profileDefault: resolveSuggestProfileDefault(focusType || "consult"),
        threadKey: getAiSuggestThreadPrefix(subjectId, focusType, focusId),
        threadLabel: selectionLabel,
        autoPromptContext,
        keepOpenOnSubmit: true,
        onSubmit: async (payload) => {
          ensureOpOk(
            await postOp("north-star-theme-consult", {
              subject_id: subjectId,
              providers: sanitizeOpArgValue(payload.provider || "", { maxLen: 120 }),
              focus_type: sanitizeOpArgValue(focusType, { maxLen: 80 }),
              focus_id: sanitizeOpArgValue(focusId, { maxLen: 120 }),
              comment: payload.comment || "",
            }),
            "north-star-theme-consult",
          );
          await refreshNorthStar();
          return {
            note: t("north_star.suggestions.thread_sent") || "İstek gönderildi.",
            subject_id: subjectId,
            focus_type: focusType,
            focus_id: focusId,
          };
        },
      });
      if (!modalResult) return;
    });
  });
  $$("[data-findings-transfer]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (String(btn.dataset.findingsTransferDisabled || "") === "1" || btn.classList.contains("is-disabled")) return;
      const subjectId = String(btn.dataset.findingsSubjectId || "").trim();
      const themeLabel = String(btn.dataset.findingsTheme || "").trim();
      const subthemeLabel = String(btn.dataset.findingsSubtheme || "").trim();
      const targetLabel = String(
        btn.dataset.findingsTargetLabel || subthemeLabel || themeLabel || subjectId || t("north_star.unknown")
      ).trim();
      applyMechanismTransferToFindings({ subjectId, themeLabel, subthemeLabel });
      showToast(t("north_star.mechanisms.transfer_done", { target: targetLabel || t("north_star.unknown") }), "ok");
    });
  });
  $$("[data-matrix-focus]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (String(btn.dataset.matrixFocusDisabled || "") === "1" || btn.classList.contains("is-disabled")) return;
      const subjectId = String(btn.dataset.matrixSubjectId || "").trim();
      const themeLabel = String(btn.dataset.matrixTheme || "").trim();
      const subthemeLabel = String(btn.dataset.matrixSubtheme || "").trim();
      const catalog = String(btn.dataset.matrixStage || "").trim();
      const topic = String(btn.dataset.matrixTopic || "").trim();
      applyNorthStarMatrixFocusToFindings({
        subjectId,
        themeLabel,
        subthemeLabel,
        catalog,
        topic,
      });
      showToast(t("north_star.mechanisms.matrix_focus_done"), "ok");
    });
  });
  $$("[data-suggest-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const suggestionId = btn.dataset.suggestId || "";
      const action = btn.dataset.suggestAction || "";
      const modalResult = await openNorthStarSuggestModal({
        title: action,
        hint: t("north_star.suggestions.modal_hint"),
        showMergeTarget: String(action).toUpperCase() === "MERGE",
        showModelSelect: false,
      });
      if (!modalResult) return;
      const comment = modalResult.comment || "";
      const mergeTarget = modalResult.mergeTarget || "";
      if (String(action).toUpperCase() === "MERGE" && !mergeTarget) {
        showToast(t("north_star.suggestions.merge_prompt"), "warn");
        return;
      }
      ensureOpOk(
        await postOp("north-star-theme-suggestion-apply", {
          suggestion_id: suggestionId,
          action,
          comment,
          merge_target: mergeTarget,
        }),
        "north-star-theme-suggestion-apply",
      );
      await refreshNorthStar();
    });
  });
  $$("[data-suggest-discuss]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const subjectId = btn.dataset.aiSubject || "";
      const focusType = btn.dataset.aiType || "";
      const focusId = btn.dataset.aiId || "";
      const targetLabel = btn.dataset.aiLabel || focusId;
      const subjectLabel = subjectId ? getMechanismsSubjectLabel(subjectId) || subjectId : "";
      const autoPromptContext = buildAiSuggestPromptContext({
        subjectLabel,
        subjectId,
        themeLabel: focusType === "theme" ? targetLabel : "",
        subthemeLabel: focusType === "subtheme" ? targetLabel : "",
      });
      let selectionLabel = "";
      if (subjectId) selectionLabel = `${t("north_star.suggestions.modal_context_subject")}: ${subjectId}`;
      if (focusType) selectionLabel += ` · ${t("north_star.suggestions.modal_context_theme")}: ${targetLabel}`;
      const modalResult = await openNorthStarSuggestModal({
        title: t("north_star.suggestions.discuss"),
        hint: t("north_star.suggestions.modal_hint"),
        promptIntent: t("north_star.suggestions.modal_intent_discuss"),
        selectionLabel,
        showMergeTarget: false,
        showModelSelect: true,
        profileDefault: resolveSuggestProfileDefault("consult"),
        threadKey: getAiSuggestThreadPrefix(subjectId, focusType || "theme", focusId || targetLabel),
        autoPromptContext,
        keepOpenOnSubmit: true,
        onSubmit: async (payload) => {
          ensureOpOk(
            await postOp("north-star-theme-consult", {
              subject_id: subjectId,
              providers: sanitizeOpArgValue(payload.provider || "", { maxLen: 120 }),
              focus_type: sanitizeOpArgValue(focusType || "theme", { maxLen: 80 }),
              focus_id: sanitizeOpArgValue(focusId || targetLabel, { maxLen: 120 }),
              comment: payload.comment || "",
            }),
            "north-star-theme-consult",
          );
          await refreshNorthStar();
          return {
            note: t("north_star.suggestions.thread_sent") || "İstek gönderildi.",
            subject_id: subjectId,
            focus_type: focusType || "theme",
            focus_id: focusId || targetLabel,
          };
        },
      });
      if (!modalResult) return;
    });
  });
}


function buildCatalogThreadId(subject) {
  const safe = _threadSafePart(subject || "");
  const base = safe ? `catalog.${safe}` : "catalog";
  return _trimThreadId(base);
}

function applySubjectToPrompt(template, subject) {
  const subjectText = normalizeCatalogSubject(subject);
  if (!template) return "";
  return String(template)
    .replace(/\$\{subject_id\}/g, subjectText)
    .replace(/\{subject_id\}/g, subjectText);
}

function extractPromptFromReport(text) {
  const raw = String(text || "");
  if (!raw) return "";
  const start = raw.indexOf("```");
  if (start === -1) return raw.trim();
  const end = raw.indexOf("```", start + 3);
  if (end === -1) return raw.trim();
  return raw.slice(start + 3, end).trim();
}

function pickPromptFromRegistry(payload, promptId) {
  const registry = unwrap(payload || {}) || {};
  const versions = Array.isArray(registry.versions) ? registry.versions : [];
  const activeId = String(registry.active_version_id || "").trim();
  const version = versions.find((v) => String(v?.version_id || "") === activeId) || versions[0] || {};
  const prompts = version.prompts || {};
  const entry = prompts[promptId] || null;
  return entry && entry.user_template ? String(entry.user_template) : "";
}

async function loadCatalogPromptTemplate() {
  if (state.catalogPromptTemplate) {
    return { template: state.catalogPromptTemplate, source: state.catalogPromptSource };
  }
  const reportPayload = await fetchOptionalJson(northStarPromptReportPath);
  const reportText = String(reportPayload?.data?.text || reportPayload?.text || "");
  if (reportText) {
    const extracted = extractPromptFromReport(reportText) || reportText.trim();
    if (extracted) {
      state.catalogPromptTemplate = extracted;
      state.catalogPromptSource = "report:v0.4.8";
      return { template: extracted, source: state.catalogPromptSource };
    }
  }
  const reportRaw = await fetchReportText(northStarPromptReportPath);
  if (reportRaw) {
    const extracted = extractPromptFromReport(reportRaw) || reportRaw.trim();
    if (extracted) {
      state.catalogPromptTemplate = extracted;
      state.catalogPromptSource = "report:v0.4.8";
      return { template: extracted, source: state.catalogPromptSource };
    }
  }
  const registry = await fetchOptionalJson(promptRegistryPath);
  const registryPrompt = pickPromptFromRegistry(registry, "north_star.seed");
  if (registryPrompt) {
    state.catalogPromptTemplate = registryPrompt;
    state.catalogPromptSource = "prompt_registry:north_star.seed";
    return { template: registryPrompt, source: state.catalogPromptSource };
  }
  return { template: "", source: "" };
}

async function buildCatalogPrompt(subject) {
  const subjectText = normalizeCatalogSubject(subject);
  const info = await loadCatalogPromptTemplate();
  if (!info.template) return { text: "", source: info.source || "" };
  return { text: applySubjectToPrompt(info.template, subjectText), source: info.source || "" };
}

function renderCatalogDraft() {
  const input = $("#ns-catalog-subject");
  const statusEl = $("#ns-catalog-status");
  const metaEl = $("#ns-catalog-meta");
  const subject = state.catalogDraft?.subject || "";
  const thread = subject ? buildCatalogThreadId(subject) : "";
  if (input && document.activeElement !== input) input.value = subject;
  if (statusEl) statusEl.textContent = t("north_star.catalog_create.status_ready");
  if (metaEl) {
    metaEl.textContent = subject ? t("north_star.catalog_create.meta_saved", { subject, thread }) : "";
  }
}

function saveCatalogDraft(subject) {
  const subjectText = normalizeCatalogSubject(subject);
  if (!subjectText) return null;
  const thread = buildCatalogThreadId(subjectText);
  const draft = { subject: subjectText, thread };
  state.catalogDraft = draft;
  writeCatalogDraftToStorage(draft);
  renderCatalogDraft();
  renderPlannerChatSuggestions();
  return draft;
}

function prefillPlannerChatComposer({ title, body, tags, thread }) {
  const titleEl = $("#note-title");
  const bodyEl = $("#note-body");
  const tagsEl = $("#note-tags");
  const threadEl = $("#planner-thread");
  if (!titleEl || !bodyEl || !tagsEl) {
    showToast(t("toast.notes_composer_unavailable"), "fail");
    return;
  }
  titleEl.value = title || "";
  bodyEl.value = body || "";
  tagsEl.value = tags || "";
  state.noteLinks = [];
  renderNoteLinks();
  if (threadEl) {
    threadEl.value = thread || state.plannerThread || "default";
    state.plannerThread = threadEl.value;
  }
  navigateToTab("planner-chat");
  bodyEl.focus();
  showToast(t("toast.catalog_prefilled"), "ok");
}

const CATALOG_CHAT_SUGGESTIONS = [
  {
    id: "seed_first",
    label: "1) Reference: ilk üretim (detaylı seed)",
    prompt: "{{subject}}\nPrompt v0.4.8'e göre ilk tema/subtheme setini DETAYLI ve kapsamlı üret. Gerekirse tema yoğunluğunu \"maksimal\" seç ve kısa gerekçe ekle.",
  },
  {
    id: "consult_all",
    label: "2) Reference: 6 sağlayıcı istişare",
    prompt: "{{subject}}\n6 sağlayıcı (openai, google, claude, deepseek, qwen, xai) ile istişare başlat. Her sağlayıcı için ayrı özet çıkar.",
  },
  {
    id: "consolidate_review",
    label: "3) Reference: konsolidasyon & çakışma",
    prompt: "{{subject}}\nMüzakere çıktılarını birleştir; çakışmaları/tekrarları çıkar ve konsolidasyon önerisi yaz.",
  },
  {
    id: "merge_review",
    label: "4) Reference: kabul/ret/merge",
    prompt: "{{subject}}\nKabul/ret/merge karar listesi üret. Her karar için kısa gerekçe ekle.",
  },
  {
    id: "apply_active",
    label: "5) Reference: ACTIVE güncelle",
    prompt: "{{subject}}\nOnaylanan katalogu ACTIVE set olarak registry'ye bağla; versiyon notu yaz.",
  },
  {
    id: "ui_sync",
    label: "6) Reference: UI doğrulama/yayın",
    prompt: "{{subject}}\nUI'da aktif katalog görünümünü güncelle ve doğrula.",
  },
  {
    id: "assessment_run",
    label: "7) Assessment: mevcut durumu ölç",
    prompt: "{{subject}}\nMevcut sistemi referansa göre ölç. Hangi konu/tema/alt tema karşılanıyor, hangileri eksik net ve izlenebilir bir özet üret.",
  },
  {
    id: "gap_extract",
    label: "8) Gap: sapmaları çıkar",
    prompt: "{{subject}}\nAssessment sonucundan sapmaları (gap) çıkar. Her gap için etki, risk sınıfı, efor ve kısa gerekçe yaz.",
  },
  {
    id: "closure_plan",
    label: "9) Gap->PDCA: kapatma planı",
    prompt: "{{subject}}\nGap listesinden deterministik Top 5 aksiyon çıkar. Her aksiyon için owner, sıra, kapanış kanıtı ve recheck adımını yaz.",
  },
];

function renderPlannerChatSuggestions() {
  const container = $("#planner-chat-suggestions");
  const titleEl = $("#planner-chat-suggestions-title");
  if (!container) return;
  if (titleEl) titleEl.style.display = CATALOG_CHAT_SUGGESTIONS.length ? "block" : "none";
  const subject = state.catalogDraft?.subject || "";
  const subjectLine = subject ? `Konu: ${subject}` : "Konu: (belirtilmedi)";
  const items = CATALOG_CHAT_SUGGESTIONS.map((item) => {
    const prompt = String(item.prompt || "").replace(/\{\{subject\}\}/g, subjectLine);
    return `<button class="btn ghost small" type="button" data-chat-suggest="${escapeHtml(item.id)}" data-chat-prompt="${encodeTag(prompt)}">${escapeHtml(item.label)}</button>`;
  });
  container.innerHTML = items.join(" ");
  $$('[data-chat-suggest]').forEach((btn) => {
    btn.addEventListener("click", () => {
      const bodyEl = $("#note-body");
      const titleEl = $("#note-title");
      const prompt = decodeTag(btn.dataset.chatPrompt || "");
      if (!bodyEl) return;
      bodyEl.value = prompt;
      if (titleEl && !titleEl.value.trim()) {
        const firstLine = prompt.split(/\r?\n/)[0] || "";
        titleEl.value = firstLine.slice(0, 80);
      }
      bodyEl.focus();
    });
  });
}

async function openCatalogModal(subjectValue) {
  const subjectText = normalizeCatalogSubject(subjectValue);
  if (!subjectText) {
    showToast(t("toast.catalog_subject_required"), "warn");
    return;
  }
  saveCatalogDraft(subjectText);
  const promptInfo = await buildCatalogPrompt(subjectText);
  if (!promptInfo.text) {
    showToast(t("toast.catalog_prompt_missing"), "warn");
    return;
  }

  const threadPrefix = buildCatalogThreadId(subjectText);
  const selectionLabel = `${t("north_star.catalog_create.subject_label")}: ${subjectText}`;
  const sourceNote = promptInfo.source ? ` • ${promptInfo.source}` : "";
  const preferredProfile = "REASONING_TEXT";
  state.aiSuggestProfile = preferredProfile;
  state.aiSuggestProvider = "";
  state.aiSuggestModel = "";

  await openNorthStarSuggestModal({
    title: t("north_star.catalog_create.modal_title"),
    hint: `${t("north_star.catalog_create.modal_hint")}${sourceNote}`,
    promptIntent: "Katalog üretimi",
    selectionLabel,
    showMergeTarget: false,
    showModelSelect: true,
    profileDefault: preferredProfile,
    threadKey: threadPrefix,
    defaultComment: promptInfo.text,
    disableEnterSubmit: true,
    commentMaxLen: 12000,
    skipSuggestionWait: true,
    openChatLabel: t("north_star.catalog_create.modal_open_chat"),
    onOpenChat: ({ thread, comment }) => {
      const tags = ["catalog", "north_star", "seed"];
      const slug = _threadSafePart(subjectText);
      if (slug) tags.push(`subject:${slug}`);
      prefillPlannerChatComposer({
        title: `[CATALOG] ${subjectText}`,
        body: comment || "",
        tags: tags.join(","),
        thread,
      });
    },
    onSubmit: async (payload) => {
      await ensureChatProviderRegistryLoaded();
      if (!payload.provider || !payload.model) {
        showToast("Provider/model required.", "warn");
        return { note: t("toast.catalog_prompt_ready") || "" };
      }
      const prompt = payload.comment_chat || payload.comment || "";
      if (!prompt.trim()) {
        showToast(t("toast.title_or_body_required"), "warn");
        return { note: t("toast.catalog_prompt_ready") || "" };
      }
      const thread = String(payload.thread || state.plannerThread || "default");
      state.plannerThread = thread;
      const tags = ["catalog", "north_star", "seed"];
      const slug = _threadSafePart(subjectText);
      if (slug) tags.push(`subject:${slug}`);
      const autoTags = buildChatAutoTags();
      const mergedTags = Array.from(new Set([...tags, ...autoTags]));
      await postOp("planner-chat-send-llm", {
        thread,
        title: `[CATALOG] ${subjectText}`,
        body: prompt,
        tags: mergedTags.join(","),
        provider_id: payload.provider || "",
        model: payload.model || "",
        profile: payload.profile || "",
      });
      navigateToTab("planner-chat");
      refreshNotes();
      showToast(t("toast.catalog_sent"), "ok");
      return { note: t("toast.catalog_sent") || "İstek gönderildi." };
    },
  });
}

function setupNorthStarCatalogControls() {
  const subjectInput = $("#ns-catalog-subject");
  const saveBtn = $("#ns-catalog-save");
  const createBtn = $("#ns-catalog-create");
  renderCatalogDraft();
  if (subjectInput) {
    subjectInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const subject = normalizeCatalogSubject(subjectInput.value || "");
      if (!subject) {
        showToast(t("toast.catalog_subject_required"), "warn");
        return;
      }
      saveCatalogDraft(subject);
    });
  }
  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      const subject = normalizeCatalogSubject(subjectInput ? subjectInput.value : "");
      if (!subject) {
        showToast(t("toast.catalog_subject_required"), "warn");
        return;
      }
      saveCatalogDraft(subject);
    });
  }
  if (createBtn) {
    createBtn.addEventListener("click", () => {
      const subject = normalizeCatalogSubject(subjectInput ? subjectInput.value : "") || state.catalogDraft?.subject || "";
      if (!subject) {
        showToast(t("toast.catalog_subject_required"), "warn");
        return;
      }
      openCatalogModal(subject);
    });
  }
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
    guvenlik: "Security",
    gizlilik: "Privacy",
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
    guvenlik: "Güvenlik",
    gizlilik: "Gizlilik",
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
  if (state.filters?.northStarFindings?.topic_locked_by_perspective) {
    setNorthStarFindingsPresetKey("CUSTOM");
    renderNorthStarFindingsTagSelect("topic");
    renderNorthStarFindings();
    return;
  }
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

const NORTH_STAR_PERSPECTIVE_ORDER = ["BUSINESS_PROCESS", "PRODUCT", "ENGINEERING", "GOVERNANCE"];

function updateNorthStarFindingsFilterOptions(items) {
  const subjects = new Map();
  const topics = new Map();
  const themes = new Map();
  const subthemes = new Map();
  const catalogs = new Map();
  const topicLocked = Boolean(state.filters?.northStarFindings?.topic_locked_by_perspective);
  const perspectiveOptions = getNorthStarPerspectiveOptions();

  const addOption = (map, value) => {
    const raw = normalizeValue(value);
    if (!raw) return;
    const key = normalizeKey(raw);
    if (!map.has(key)) map.set(key, raw);
  };

  (Array.isArray(items) ? items : []).forEach((item) => {
    const subjectRaw =
      item?.subject ||
      item?.subject_id ||
      (Array.isArray(item?.tags)
        ? item.tags.find((t) => String(t || "").toLowerCase().startsWith("subject:"))?.split(":").slice(1).join(":")
        : "");
    addOption(subjects, normalizeNorthStarFindingSubject(subjectRaw));
    addOption(topics, normalizeNorthStarFindingTopic(item?.topic));
    const join = getNorthStarJoinForItem(item);
    addOption(themes, join.theme_label);
    addOption(subthemes, join.subtheme_label);
    addOption(catalogs, deriveNorthStarWorkflowStage(item));
  });

  const registryOptions = extractMechanismsRegistryOptions(state.northStarMechanismsRegistry);
  registryOptions.subjects.forEach((entry) => {
    if (!entry?.id) return;
    addOption(subjects, entry.id);
  });
  registryOptions.themes.forEach((label) => addOption(themes, label));
  registryOptions.subthemes.forEach((label) => addOption(subthemes, label));

  const subjectValues = Array.from(subjects.values()).sort((a, b) => a.localeCompare(b));
  const subjectOptionMap = new Map();
  registryOptions.subjects.forEach((entry) => {
    if (!entry?.id) return;
    subjectOptionMap.set(String(entry.id), { id: String(entry.id), label: String(entry.label || entry.id) });
  });
  subjectValues.forEach((id) => {
    if (!subjectOptionMap.has(id)) subjectOptionMap.set(id, { id, label: id });
  });
  state.filterOptions.northStarFindings.subject = Array.from(subjectOptionMap.values()).sort((a, b) => a.label.localeCompare(b.label));
  state.filterOptions.northStarFindings.perspective = perspectiveOptions;
  const topicOptions = Array.from(topics.values()).sort((a, b) => a.localeCompare(b));
  state.filterOptions.northStarFindings.topic_unlocked = topicOptions.slice();
  if (topicLocked) {
    const selectedPerspectives = state.filters?.northStarFindings?.perspective || [];
    const criteria = getNorthStarPerspectiveCriteriaUnion(selectedPerspectives);
    if (criteria && criteria.length) {
      state.filterOptions.northStarFindings.topic = criteria
        .map((axis) => normalizeNorthStarFindingTopic(axis))
        .map((axis) => String(axis || "").trim())
        .filter((axis) => Boolean(axis));
    } else {
      state.filterOptions.northStarFindings.topic = topicOptions;
    }
  } else {
    state.filterOptions.northStarFindings.topic = topicOptions;
  }
  state.filterOptions.northStarFindings.theme = Array.from(themes.values()).sort((a, b) => a.localeCompare(b));
  state.filterOptions.northStarFindings.subtheme = Array.from(subthemes.values()).sort((a, b) => a.localeCompare(b));
  const stageDefaults = ["reference", "assessment", "gap"];
  const nextCatalogs = Array.from(
    new Set([
      ...stageDefaults,
      ...Array.from(catalogs.values())
        .map((c) => String(c || "").trim())
        .filter((c) => Boolean(c)),
    ])
  ).sort((a, b) => a.localeCompare(b));
  state.filterOptions.northStarFindings.catalog = nextCatalogs;

  // Prune selections that no longer exist (fail-closed).
  ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"].forEach((field) => {
    const selected = state.filters.northStarFindings[field] || [];
    const options = state.filterOptions.northStarFindings[field] || [];
    const optionKeys = new Set(options.map((opt) => normalizeKey(opt?.id ?? opt)));
    state.filters.northStarFindings[field] = selected.filter((opt) => optionKeys.has(normalizeKey(opt)));
  });
}

function renderNorthStarFindingsTagSelect(field) {
  const wrap = $(`#ns-findings-filter-${field}`);
  const tagsEl = $(`#ns-findings-filter-${field}-tags`);
  const input = $(`#ns-findings-filter-${field}-input`);
  const optionsEl = $(`#ns-findings-filter-${field}-options`);
  if (!wrap || !tagsEl || !input || !optionsEl) return;

  const topicLocked = field === "topic" && state.filters?.northStarFindings?.topic_locked_by_perspective;
  if (topicLocked) {
    input.disabled = false;
    if (!input.value) input.placeholder = t("north_star.perspective.locked_topics");
  } else {
    input.disabled = false;
  }

  const selected = state.filters.northStarFindings[field] || [];
  const selectedKeys = new Set(selected.map((val) => normalizeKey(val)));
  const query = input.value.trim().toLowerCase();
  const rawOptions = state.filterOptions.northStarFindings[field] || [];
  const options = rawOptions
    .map((opt) => {
      if (opt && typeof opt === "object") {
        const id = String(opt.id || "").trim();
        const label = String(opt.label || opt.name || opt.title || id).trim();
        return { value: id, label };
      }
      const value = String(opt || "").trim();
      const label = field === "catalog" ? formatNorthStarWorkflowStageLabel(value) : value;
      return { value, label };
    })
    .filter((opt) => opt.value && !selectedKeys.has(normalizeKey(opt.value)))
    .filter((opt) => (query ? opt.label.toLowerCase().includes(query) : true))
    .sort((a, b) => a.label.localeCompare(b.label));
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

  const labelLookup = field === "perspective"
    ? new Map((state.filterOptions.northStarFindings.perspective || []).map((opt) => [String(opt.id || ""), String(opt.label || opt.id || "")]))
    : null;
  tagsEl.innerHTML = selected
    .map((value) => {
      const encoded = encodeTag(value);
      const fallback = field === "catalog" ? formatNorthStarWorkflowStageLabel(value) : String(value || "");
      const label = labelLookup?.get(String(value || "")) || fallback;
      return `<span class="tag">${escapeHtml(label)}<button data-remove="${encoded}" aria-label="${escapeHtml(t("actions.remove_tag"))}">x</button></span>`;
    })
    .join("");

  optionsEl.innerHTML = options.length
    ? options
        .map((opt, idx) => {
          const encoded = encodeTag(opt.value);
          const isActive = idx === activeIndex;
          const cls = `tag-option${isActive ? " active" : ""}`;
          return `<div class="${cls}" role="option" id="${optionIdPrefix}${idx}" aria-selected="${isActive ? "true" : "false"}" data-value="${encoded}">${escapeHtml(opt.label)}</div>`;
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
  if (field === "perspective") {
    applyNorthStarPerspectiveCriteria(state.filters.northStarFindings.perspective);
    renderNorthStarFindingsTagSelect("topic");
  }
}

function removeNorthStarFindingTag(field, value) {
  const list = state.filters.northStarFindings[field] || [];
  const key = normalizeKey(value);
  state.filters.northStarFindings[field] = list.filter((item) => normalizeKey(item) !== key);
  renderNorthStarFindingsTagSelect(field);
  if (field === "perspective") {
    applyNorthStarPerspectiveCriteria(state.filters.northStarFindings.perspective);
    renderNorthStarFindingsTagSelect("topic");
  }
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

const NORTH_STAR_SOURCE_REFERENCE_KEYS = new Set(["REFERENCE", "TREND", "TREND_CATALOG", "TREND_CATALOG_V1"]);
const NORTH_STAR_SOURCE_BP_KEYS = new Set(["CAPABILITY", "BP", "BEST_PRACTICE", "BP_CATALOG", "BP_CATALOG_V1"]);
const NORTH_STAR_SOURCE_ASSESSMENT_KEYS = new Set(["CRITERION", "LENS", "LENS_REQUIREMENT"]);
const NORTH_STAR_MATRIX_STAGES = ["reference", "assessment", "gap"];

function normalizeNorthStarWorkflowStage(value) {
  const norm = normalizeKey(value);
  if (["REFERENCE", "REF"].includes(norm)) return "reference";
  if (["ASSESSMENT", "ASSESS", "EVALUATION", "EVAL"].includes(norm)) return "assessment";
  if (["GAP", "DEVIATION"].includes(norm)) return "gap";
  return "";
}

function deriveNorthStarWorkflowStage(item) {
  const explicit = normalizeNorthStarWorkflowStage(
    item?.workflow_stage || item?.workflowStage || item?.stage || item?.phase || item?.process_stage || item?.processStage
  );
  if (explicit) return explicit;

  const matchNorm = normalizeKey(item?.match_status);
  if (["NOT_TRIGGERED", "UNKNOWN", "FAIL", "FAILED", "WARN", "WARNING"].includes(matchNorm)) return "gap";

  const catalogNorm = normalizeKey(item?.catalog);
  if (NORTH_STAR_SOURCE_REFERENCE_KEYS.has(catalogNorm) || NORTH_STAR_SOURCE_BP_KEYS.has(catalogNorm)) return "reference";
  if (NORTH_STAR_SOURCE_ASSESSMENT_KEYS.has(catalogNorm)) return "assessment";
  return "assessment";
}

function formatNorthStarWorkflowStageLabel(raw) {
  const stage = normalizeNorthStarWorkflowStage(raw);
  if (stage === "reference") return t("north_star.stage.reference");
  if (stage === "assessment") return t("north_star.stage.assessment");
  if (stage === "gap") return t("north_star.stage.gap");
  return String(raw || "");
}

function normalizeNorthStarMatrixStage(value) {
  const stage = normalizeNorthStarWorkflowStage(value);
  if (NORTH_STAR_MATRIX_STAGES.includes(stage)) return stage;
  return "";
}

function getNorthStarMatrixPayload(stage) {
  const stageKey = normalizeNorthStarMatrixStage(stage);
  const matrices = state.northStarMatrices && typeof state.northStarMatrices === "object"
    ? state.northStarMatrices
    : {};
  const payload = stageKey ? matrices[stageKey] : null;
  return payload && typeof payload === "object" ? payload : {};
}

function getNorthStarMatrixItems(stage) {
  const payload = getNorthStarMatrixPayload(stage);
  return Array.isArray(payload.items) ? payload.items : [];
}

function buildNorthStarKeySet(values) {
  const set = new Set();
  (Array.isArray(values) ? values : [values]).forEach((value) => {
    const key = normalizeKey(value);
    if (key) set.add(key);
  });
  return set;
}

function keySetIntersects(left, right) {
  if (!(left instanceof Set) || !(right instanceof Set)) return false;
  for (const key of left.values()) {
    if (right.has(key)) return true;
  }
  return false;
}

function northStarMatrixEntryMatchesScope(entry, scope = {}) {
  if (!entry || typeof entry !== "object") return false;
  const subjectId = normalizeValue(scope.subjectId || "");
  if (subjectId && normalizeKey(entry.subject_id) !== normalizeKey(subjectId)) return false;

  const themeNeed = buildNorthStarKeySet([scope.themeId, scope.themeLabel]);
  if (themeNeed.size) {
    const themeHave = buildNorthStarKeySet([
      entry.theme_id,
      entry.theme_label,
      entry?.lens_findings_filter?.theme,
    ]);
    if (!keySetIntersects(themeNeed, themeHave)) return false;
  }

  const subthemeNeed = buildNorthStarKeySet([scope.subthemeId, scope.subthemeLabel]);
  if (subthemeNeed.size) {
    const subthemeHave = buildNorthStarKeySet([
      entry.subtheme_id,
      entry.subtheme_label,
      entry?.lens_findings_filter?.subtheme,
    ]);
    if (!keySetIntersects(subthemeNeed, subthemeHave)) return false;
  }

  return true;
}

function toNorthStarCount(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return Math.floor(parsed);
}

function buildNorthStarSubthemeMatrixRows(scope = {}) {
  const byCriterion = new Map();
  NORTH_STAR_MATRIX_STAGES.forEach((stage) => {
    const rows = getNorthStarMatrixItems(stage).filter((entry) => northStarMatrixEntryMatchesScope(entry, scope));
    rows.forEach((entry) => {
      const criterionId = String(entry?.criterion_id || "").trim();
      const criterionLabel = String(entry?.criterion_label || criterionId || "").trim();
      const criterionKey = normalizeKey(criterionId || criterionLabel || entry?.row_id || "");
      if (!criterionKey) return;
      if (!byCriterion.has(criterionKey)) {
        byCriterion.set(criterionKey, {
          criterion_id: criterionId,
          criterion_label: criterionLabel || criterionId || t("north_star.unknown"),
          stages: {},
        });
      }
      const current = byCriterion.get(criterionKey);
      if (!current) return;
      if (!current.criterion_id && criterionId) current.criterion_id = criterionId;
      if ((!current.criterion_label || current.criterion_label === t("north_star.unknown")) && criterionLabel) {
        current.criterion_label = criterionLabel;
      }
      current.stages[stage] = {
        item_count: toNorthStarCount(entry?.item_count),
        triggered_count: toNorthStarCount(entry?.triggered_count),
        not_triggered_count: toNorthStarCount(entry?.not_triggered_count),
        unknown_count: toNorthStarCount(entry?.unknown_count),
        status: String(entry?.status || "").trim().toUpperCase(),
        summary: String(entry?.summary || "").trim(),
        lens_filter: entry?.lens_findings_filter && typeof entry.lens_findings_filter === "object"
          ? entry.lens_findings_filter
          : {},
      };
    });
  });

  return Array.from(byCriterion.values()).sort((a, b) => {
    const left = String(a.criterion_label || a.criterion_id || "");
    const right = String(b.criterion_label || b.criterion_id || "");
    return left.localeCompare(right);
  });
}

function getNorthStarMatrixCellClass(stage, status) {
  const normalizedStage = normalizeNorthStarMatrixStage(stage);
  const normalizedStatus = normalizeKey(status);
  if (normalizedStage === "gap") {
    if (normalizedStatus === "OPEN") return "warn";
    if (normalizedStatus === "NO_GAP") return "ok";
    return "idle";
  }
  if (normalizedStatus === "HAS_DATA") return "ok";
  if (normalizedStatus === "NO_DATA") return "idle";
  return "warn";
}

function buildNorthStarMatrixCellFilter({ row = {}, stage = "", scope = {}, cell = {} } = {}) {
  const lensFilter = cell?.lens_filter && typeof cell.lens_filter === "object" ? cell.lens_filter : {};
  const catalog = normalizeNorthStarWorkflowStage(lensFilter.catalog || stage) || normalizeNorthStarMatrixStage(stage);
  return {
    catalog,
    subject_id: normalizeValue(lensFilter.subject || scope.subjectId || ""),
    theme_label: normalizeValue(lensFilter.theme || scope.themeLabel || ""),
    subtheme_label: normalizeValue(lensFilter.subtheme || scope.subthemeLabel || ""),
    topic: normalizeNorthStarFindingTopic(lensFilter.topic || row.criterion_id || row.criterion_label || ""),
  };
}

function renderNorthStarMatrixCell({
  row = {},
  stage = "",
  scope = {},
  transferEnabled = false,
  transferDisabledTitle = "",
} = {}) {
  const normalizedStage = normalizeNorthStarMatrixStage(stage);
  if (!normalizedStage) return `<div class="subtle">${escapeHtml(t("empty.no_items"))}</div>`;
  const cell = row?.stages?.[normalizedStage] || {};
  const status = String(cell?.status || (normalizedStage === "gap" ? "NO_GAP" : "NO_DATA")).trim().toUpperCase();
  const itemCount = toNorthStarCount(cell?.item_count);
  const triggered = toNorthStarCount(cell?.triggered_count);
  const notTriggered = toNorthStarCount(cell?.not_triggered_count);
  const unknown = toNorthStarCount(cell?.unknown_count);
  const countsText = t("north_star.mechanisms.matrix_cell_counts", {
    items: String(itemCount),
    triggered: String(triggered),
    not_triggered: String(notTriggered),
    unknown: String(unknown),
  });
  const filter = buildNorthStarMatrixCellFilter({ row, stage: normalizedStage, scope, cell });
  const canFocus = Boolean(transferEnabled);
  const title = canFocus
    ? t("north_star.mechanisms.matrix_open_title")
    : transferDisabledTitle || t("north_star.mechanisms.matrix_open_disabled");
  const buttonClass = `btn ghost tiny${canFocus ? "" : " is-disabled"}`;
  const disabledAttrs = canFocus ? "" : ` data-matrix-focus-disabled="1" aria-disabled="true"`;
  const lockIcon = canFocus
    ? ""
    : '<span class="transfer-lock-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 1a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V11a2 2 0 0 0-2-2h-1V6a5 5 0 0 0-5-5zm-3 8V6a3 3 0 0 1 6 0v3H9zm3 4a2 2 0 0 1 1 3.732V19h-2v-2.268A2 2 0 0 1 12 13z"></path></svg></span>';
  return `<div style="display:flex;flex-direction:column;gap:6px;">
    <span class="badge ${getNorthStarMatrixCellClass(normalizedStage, status)}">${escapeHtml(status)}</span>
    <div class="subtle">${escapeHtml(countsText)}</div>
    <button class="${buttonClass}" type="button" data-matrix-focus="1" data-matrix-subject-id="${escapeHtml(filter.subject_id)}" data-matrix-theme="${escapeHtml(filter.theme_label)}" data-matrix-subtheme="${escapeHtml(filter.subtheme_label)}" data-matrix-stage="${escapeHtml(filter.catalog)}" data-matrix-topic="${escapeHtml(filter.topic)}" title="${escapeHtml(title)}"${disabledAttrs}>${lockIcon}${escapeHtml(t("north_star.mechanisms.matrix_open_findings"))}</button>
  </div>`;
}

function renderNorthStarSubthemeMatrixPanel({
  subjectId = "",
  themeId = "",
  themeLabel = "",
  subthemeId = "",
  subthemeLabel = "",
  transferEnabled = false,
  transferDisabledTitle = "",
} = {}) {
  const scope = {
    subjectId: normalizeValue(subjectId),
    themeId: normalizeValue(themeId),
    themeLabel: normalizeValue(themeLabel),
    subthemeId: normalizeValue(subthemeId),
    subthemeLabel: normalizeValue(subthemeLabel),
  };
  const rows = buildNorthStarSubthemeMatrixRows(scope);
  const title = t("north_star.mechanisms.matrix_title");
  const meta = t("north_star.mechanisms.matrix_meta", { count: String(rows.length) });
  if (!rows.length) {
    return `<div class="subtle" style="margin-top:8px;">
      <div><strong>${escapeHtml(title)}</strong> · ${escapeHtml(meta)}</div>
      <div class="empty" style="margin-top:8px;">${escapeHtml(t("north_star.mechanisms.matrix_empty"))}</div>
    </div>`;
  }
  const headerCells = [
    t("north_star.mechanisms.matrix_col_criterion"),
    formatNorthStarWorkflowStageLabel("reference"),
    formatNorthStarWorkflowStageLabel("assessment"),
    formatNorthStarWorkflowStageLabel("gap"),
  ];
  const headerHtml = headerCells.map((label) => `<th>${escapeHtml(label)}</th>`).join("");
  const bodyHtml = rows
    .map((row) => {
      const criterionLabel = String(row?.criterion_label || row?.criterion_id || t("north_star.unknown"));
      const criterionId = String(row?.criterion_id || "");
      const criterionIdHint = criterionId && criterionId !== criterionLabel
        ? `<div class="subtle">${escapeHtml(criterionId)}</div>`
        : "";
      return `<tr>
        <td><strong>${escapeHtml(criterionLabel)}</strong>${criterionIdHint}</td>
        <td>${renderNorthStarMatrixCell({
          row,
          stage: "reference",
          scope,
          transferEnabled,
          transferDisabledTitle,
        })}</td>
        <td>${renderNorthStarMatrixCell({
          row,
          stage: "assessment",
          scope,
          transferEnabled,
          transferDisabledTitle,
        })}</td>
        <td>${renderNorthStarMatrixCell({
          row,
          stage: "gap",
          scope,
          transferEnabled,
          transferDisabledTitle,
        })}</td>
      </tr>`;
    })
    .join("");
  return `<div class="subtle" style="margin-top:8px;">
    <div><strong>${escapeHtml(title)}</strong> · ${escapeHtml(meta)}</div>
    <div class="table-wrap" style="margin-top:8px;">
      <table>
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${bodyHtml}</tbody>
      </table>
    </div>
  </div>`;
}

function applyNorthStarMatrixFocusToFindings({
  subjectId = "",
  themeLabel = "",
  subthemeLabel = "",
  catalog = "",
  topic = "",
} = {}) {
  const normalizedSubject = normalizeValue(subjectId);
  const normalizedTheme = normalizeValue(themeLabel);
  const normalizedSubtheme = normalizeValue(subthemeLabel);
  const normalizedStage = normalizeNorthStarWorkflowStage(catalog);
  const normalizedTopic = normalizeNorthStarFindingTopic(topic);
  applyMechanismTransferToFindings({
    subjectId: normalizedSubject,
    themeLabel: normalizedTheme,
    subthemeLabel: normalizedSubtheme,
  });
  state.filters.northStarFindings.search = "";
  state.filters.northStarFindings.preset = "CUSTOM";
  state.filters.northStarFindings.perspective = [];
  state.filters.northStarFindings.topic_locked_by_perspective = false;
  state.filters.northStarFindings.topic = normalizedTopic ? [normalizedTopic] : [];
  state.filters.northStarFindings.catalog = normalizedStage ? [normalizedStage] : [];
  state.filters.northStarFindings.match = [];
  state.northStarFindingSelected = null;
  setNorthStarFindingsPresetKey("CUSTOM");

  const searchInput = $("#ns-findings-search");
  if (searchInput) searchInput.value = "";

  ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"].forEach((field) => {
    const input = $(`#ns-findings-filter-${field}-input`);
    if (input) input.value = "";
    renderNorthStarFindingsTagSelect(field);
  });
  renderNorthStarFindings();
  const findingsAnchor = $("#ns-findings-meta") || $("#ns-findings-table");
  if (findingsAnchor && typeof findingsAnchor.scrollIntoView === "function") {
    findingsAnchor.scrollIntoView({ behavior: "smooth", block: "start" });
  }
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

function formatTrEnLabel(tr, en, fallback = "") {
  const trClean = String(tr || "").trim();
  const enClean = String(en || "").trim();
  if (trClean && enClean && trClean !== enClean) return `${trClean} (${enClean})`;
  return trClean || enClean || fallback || "";
}

function localizeTrEnLabel(tr, en, fallback = "") {
  const lang = state.lang === "en" ? "en" : "tr";
  const trClean = String(tr || "").trim();
  const enClean = String(en || "").trim();
  if (lang === "tr") return trClean || enClean || fallback || "";
  return enClean || trClean || fallback || "";
}

function getMechanismsStatusLabel(status) {
  const norm = String(status || "").toUpperCase();
  if (norm === "DEPRECATED") return t("north_star.mechanisms.status.deprecated");
  if (norm === "HIDDEN") return t("north_star.mechanisms.status.hidden");
  if (norm === "ACTIVE") return t("north_star.mechanisms.status.active");
  return norm || t("north_star.unknown");
}

function getMechanismsSubjectById(subjectId) {
  const targetId = String(subjectId || "").trim();
  if (!targetId) return null;
  const registry = unwrap(state.northStarMechanismsRegistry || {}) || {};
  const subjects = Array.isArray(registry.subjects) ? registry.subjects : [];
  return subjects.find((entry) => String(entry?.subject_id || "").trim() === targetId) || null;
}

function getMechanismsSubjectTransferState(subject) {
  const status = String(subject?.status || "").toUpperCase();
  const isActive = status === "ACTIVE";
  const approvedAt = String(subject?.approved_at || "").trim();
  const isApproved = Boolean(approvedAt);
  const reasons = [];
  if (!isActive) reasons.push(t("north_star.mechanisms.transfer_reason_not_active"));
  if (!isApproved) reasons.push(t("north_star.mechanisms.transfer_reason_not_approved"));
  const blockedTitle = reasons.length
    ? t("north_star.mechanisms.transfer_blocked_detail", { reasons: reasons.join(" · ") })
    : "";
  return { enabled: isActive && isApproved, blockedTitle, isActive, isApproved };
}

function renderFindingsTransferButton({
  enabled = false,
  subjectId = "",
  themeLabel = "",
  subthemeLabel = "",
  targetLabel = "",
  buttonLabel = "",
  enabledTitle = "",
  disabledTitle = "",
} = {}) {
  const subjectNorm = String(subjectId || "").trim();
  if (!subjectNorm) return "";
  const cls = `btn ghost tiny${enabled ? "" : " is-disabled"}`;
  const title = enabled ? String(enabledTitle || "") : String(disabledTitle || enabledTitle || "");
  const disabledAttrs = enabled ? "" : ` data-findings-transfer-disabled="1" aria-disabled="true"`;
  const target = String(targetLabel || "").trim() || t("north_star.unknown");
  const lockIcon = enabled
    ? ""
    : '<span class="transfer-lock-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 1a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V11a2 2 0 0 0-2-2h-1V6a5 5 0 0 0-5-5zm-3 8V6a3 3 0 0 1 6 0v3H9zm3 4a2 2 0 0 1 1 3.732V19h-2v-2.268A2 2 0 0 1 12 13z"></path></svg></span>';
  return `<button class="${cls}" type="button" data-findings-transfer="1" data-findings-subject-id="${escapeHtml(subjectNorm)}" data-findings-theme="${escapeHtml(String(themeLabel || "").trim())}" data-findings-subtheme="${escapeHtml(String(subthemeLabel || "").trim())}" data-findings-target-label="${escapeHtml(target)}" title="${escapeHtml(title)}"${disabledAttrs}>${lockIcon}${escapeHtml(buttonLabel || t("north_star.mechanisms.transfer_btn"))}</button>`;
}

function mechanismSubjectMatchesSearch(subject, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return true;
  const tokens = [];
  const add = (value) => {
    const text = String(value || "").trim();
    if (text) tokens.push(text.toLowerCase());
  };
  add(subject?.subject_id);
  add(localizeTrEnLabel(subject?.subject_title_tr, subject?.subject_title_en, ""));

  const themes = Array.isArray(subject?.themes) ? subject.themes : [];
  themes.forEach((theme) => {
    add(theme?.theme_id);
    add(localizeTrEnLabel(theme?.title_tr || theme?.theme_title_tr, theme?.title_en || theme?.theme_title_en, ""));
    add(localizeTrEnLabel(theme?.definition_tr || theme?.theme_definition_tr, theme?.definition_en || theme?.theme_definition_en, ""));
    const subthemes = Array.isArray(theme?.subthemes) ? theme.subthemes : [];
    subthemes.forEach((sub) => {
      add(sub?.subtheme_id);
      add(localizeTrEnLabel(sub?.title_tr || sub?.subtheme_title_tr, sub?.title_en || sub?.subtheme_title_en, ""));
      add(localizeTrEnLabel(sub?.definition_tr || sub?.subtheme_definition_tr, sub?.definition_en || sub?.subtheme_definition_en, ""));
    });
  });

  return tokens.some((text) => text.includes(q));
}

function extractMechanismsRegistryOptions(registryPayload) {
  const registry = unwrap(registryPayload || {}) || {};
  const subjects = Array.isArray(registry.subjects) ? registry.subjects : [];
  const subjectOptions = [];
  const themeOptions = [];
  const subthemeOptions = [];

  subjects.forEach((subject) => {
    const subjectId = String(subject?.subject_id || "").trim();
    let subjectLabel = formatTrEnLabel(subject?.subject_title_tr, subject?.subject_title_en, subjectId);
    if (subjectId === "ethics_case_management") subjectLabel = "Etik Programı (ethics_case_management)";
    if (subjectId) subjectOptions.push({ id: subjectId, label: subjectLabel || subjectId });
    const themes = Array.isArray(subject?.themes) ? subject.themes : [];
    themes.forEach((theme) => {
      const themeLabel = formatTrEnLabel(
        theme?.title_tr || theme?.theme_title_tr,
        theme?.title_en || theme?.theme_title_en
      );
      if (themeLabel) themeOptions.push(themeLabel);
      const subthemes = Array.isArray(theme?.subthemes) ? theme.subthemes : [];
      subthemes.forEach((subtheme) => {
        const subLabel = formatTrEnLabel(
          subtheme?.title_tr || subtheme?.subtheme_title_tr,
          subtheme?.title_en || subtheme?.subtheme_title_en
        );
        if (subLabel) subthemeOptions.push(subLabel);
      });
    });
  });

  return {
    subjects: subjectOptions,
    themes: dedupeList(themeOptions),
    subthemes: dedupeList(subthemeOptions),
  };
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

function extractNorthStarFindingSubjectRaw(item) {
  return (
    item?.subject ||
    item?.subject_id ||
    (Array.isArray(item?.tags)
      ? item.tags.find((t) => String(t || "").toLowerCase().startsWith("subject:"))?.split(":").slice(1).join(":")
      : "")
  );
}

function extractNorthStarFindingSubjectNorm(item) {
  return normalizeNorthStarFindingSubject(extractNorthStarFindingSubjectRaw(item));
}

function normalizeNorthStarFindingsTransferScope(scope = {}) {
  return {
    subject_id: normalizeValue(scope.subject_id || scope.subjectId || ""),
    theme_label: normalizeValue(scope.theme_label || scope.themeLabel || ""),
    subtheme_label: normalizeValue(scope.subtheme_label || scope.subthemeLabel || ""),
  };
}

function getNorthStarFindingsTransferScopeKey(scope = {}) {
  const normalized = normalizeNorthStarFindingsTransferScope(scope);
  return [normalized.subject_id, normalized.theme_label, normalized.subtheme_label].map((value) => normalizeKey(value)).join("|");
}

function getNorthStarFindingsTransferScopes() {
  const scopes = Array.isArray(state.northStarFindingsTransferScopes) ? state.northStarFindingsTransferScopes : [];
  const seen = new Set();
  const normalized = [];
  scopes.forEach((scope) => {
    const current = normalizeNorthStarFindingsTransferScope(scope);
    if (!current.subject_id) return;
    const subject = getMechanismsSubjectById(current.subject_id);
    const transferState = getMechanismsSubjectTransferState(subject || {});
    if (!subject || !transferState.enabled) return;
    const key = getNorthStarFindingsTransferScopeKey(current);
    if (!key || seen.has(key)) return;
    seen.add(key);
    normalized.push(current);
  });
  state.northStarFindingsTransferScopes = normalized;
  return normalized;
}

function addNorthStarFindingsTransferScope(scope = {}) {
  const normalized = normalizeNorthStarFindingsTransferScope(scope);
  if (!normalized.subject_id) return false;
  const existing = getNorthStarFindingsTransferScopes();
  const key = getNorthStarFindingsTransferScopeKey(normalized);
  if (existing.some((entry) => getNorthStarFindingsTransferScopeKey(entry) === key)) {
    state.northStarFindingsTransferScopes = existing;
    return false;
  }
  state.northStarFindingsTransferScopes = [...existing, normalized];
  return true;
}

function removeNorthStarFindingsTransferScope(scopeKey) {
  const target = String(scopeKey || "").trim();
  if (!target) return false;
  const existing = getNorthStarFindingsTransferScopes();
  const next = existing.filter((scope) => getNorthStarFindingsTransferScopeKey(scope) !== target);
  if (next.length === existing.length) {
    state.northStarFindingsTransferScopes = existing;
    return false;
  }
  state.northStarFindingsTransferScopes = next;
  return true;
}

function formatNorthStarFindingsTransferScopeLabel(scope) {
  const current = normalizeNorthStarFindingsTransferScope(scope);
  const subjectLabel = getMechanismsSubjectLabel(current.subject_id) || current.subject_id || t("north_star.unknown");
  const parts = [subjectLabel];
  if (current.theme_label) parts.push(current.theme_label);
  if (current.subtheme_label) parts.push(current.subtheme_label);
  return parts.join(" > ");
}

function renderNorthStarFindingsTransferScopes() {
  const container = $("#ns-findings-transfer-scopes");
  if (!container) return;
  const scopes = getNorthStarFindingsTransferScopes();
  const title = t("north_star.findings.transfer_scopes.title");
  if (!scopes.length) {
    container.innerHTML = `<span class="subtle">${escapeHtml(title)}: ${escapeHtml(t("north_star.findings.transfer_scopes.empty"))}</span>`;
    return;
  }
  const removeTitle = t("north_star.findings.transfer_scopes.remove_title");
  const chips = scopes
    .map((scope) => {
      const key = encodeTag(getNorthStarFindingsTransferScopeKey(scope));
      const label = formatNorthStarFindingsTransferScopeLabel(scope);
      return `<span class="badge" style="display:inline-flex;align-items:center;gap:6px;">${escapeHtml(label)}<button type="button" data-findings-scope-remove="${key}" title="${escapeHtml(removeTitle)}" aria-label="${escapeHtml(removeTitle)}" style="border:0;background:transparent;color:inherit;cursor:pointer;padding:0;line-height:1;font-size:12px;">x</button></span>`;
    })
    .join(" ");
  container.innerHTML = `<span class="subtle">${escapeHtml(`${title} (${scopes.length})`)}:</span> <span class="row" style="display:inline-flex;gap:6px;flex-wrap:wrap;vertical-align:middle;">${chips}</span>`;
  container.querySelectorAll("[data-findings-scope-remove]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const key = decodeTag(btn.dataset.findingsScopeRemove || "");
      if (!removeNorthStarFindingsTransferScope(key)) return;
      const findingsByLens = buildNorthStarFindingsByLensFromSource();
      mountNorthStarFindingsByLens(findingsByLens, {
        preferredKey: state.northStarFindingsLensName || NORTH_STAR_FINDINGS_ALL_LENSES_KEY,
      });
      showToast(t("north_star.findings.transfer_scopes.removed"), "ok");
    });
  });
}

function findingMatchesNorthStarTransferScope(item, scope) {
  const current = normalizeNorthStarFindingsTransferScope(scope);
  if (!current.subject_id) return false;
  const subjectNorm = extractNorthStarFindingSubjectNorm(item);
  if (normalizeKey(subjectNorm) !== normalizeKey(current.subject_id)) return false;

  if (!current.theme_label && !current.subtheme_label) return true;

  const join = getNorthStarJoinForItem(item);
  if (current.theme_label && normalizeKey(join.theme_label) !== normalizeKey(current.theme_label)) return false;
  if (current.subtheme_label && normalizeKey(join.subtheme_label) !== normalizeKey(current.subtheme_label)) return false;
  return true;
}

function summarizeNorthStarFindingsItems(items) {
  const rows = Array.isArray(items) ? items : [];
  const norm = (x) => String(x || "").toUpperCase();
  return {
    total: rows.length,
    triggered: rows.filter((x) => norm(x?.match_status) === "TRIGGERED").length,
    not_triggered: rows.filter((x) => norm(x?.match_status) === "NOT_TRIGGERED").length,
    unknown: rows.filter((x) => norm(x?.match_status) === "UNKNOWN").length,
  };
}

function applyNorthStarFindingsTransferGate(sourceByLens) {
  const source = sourceByLens && typeof sourceByLens === "object" ? sourceByLens : {};
  const scopes = getNorthStarFindingsTransferScopes();
  const hasScopes = scopes.length > 0;
  const gated = {};
  Object.entries(source).forEach(([lensName, findings]) => {
    if (lensName === NORTH_STAR_FINDINGS_ALL_LENSES_KEY) return;
    const sourceItems = Array.isArray(findings?.items) ? findings.items : [];
    const items = hasScopes
      ? sourceItems.filter((item) => scopes.some((scope) => findingMatchesNorthStarTransferScope(item, scope)))
      : [];
    gated[lensName] = {
      ...(findings && typeof findings === "object" ? findings : {}),
      summary: summarizeNorthStarFindingsItems(items),
      items,
    };
  });
  return gated;
}

function buildNorthStarFindingsByLensFromSource() {
  const sourceByLens = state.northStarFindingsSourceByLens && typeof state.northStarFindingsSourceByLens === "object"
    ? state.northStarFindingsSourceByLens
    : {};
  const byLens = applyNorthStarFindingsTransferGate(sourceByLens);
  const allItems = [];
  Object.keys(byLens)
    .sort((a, b) => a.localeCompare(b))
    .forEach((lensName) => {
      const items = Array.isArray(byLens[lensName]?.items) ? byLens[lensName].items : [];
      items.forEach((item) => {
        if (!item || typeof item !== "object") return;
        allItems.push({ ...item, lens: lensName });
      });
    });
  byLens[NORTH_STAR_FINDINGS_ALL_LENSES_KEY] = {
    version: "v1",
    summary: summarizeNorthStarFindingsItems(allItems),
    items: allItems,
  };
  return byLens;
}

function mountNorthStarFindingsByLens(findingsByLens, { preferredKey = null } = {}) {
  const byLens = findingsByLens && typeof findingsByLens === "object" ? findingsByLens : {};
  state.northStarFindingsByLens = byLens;
  renderNorthStarFindingsTransferScopes();

  const findingsLensSelect = $("#ns-findings-lens");
  const availableFindingsLenses = Object.keys(byLens)
    .filter((name) => name !== NORTH_STAR_FINDINGS_ALL_LENSES_KEY)
    .sort((a, b) => a.localeCompare(b));
  const options = [
    { key: NORTH_STAR_FINDINGS_ALL_LENSES_KEY, label: t("north_star.all_lenses") },
    ...availableFindingsLenses.map((name) => ({ key: name, label: name })),
  ];
  const explicitPreferred = String(preferredKey || "").trim();
  const preferredFromState = String(state.northStarFindingsLensName || "").trim();
  const selectedKey = options.some((opt) => opt.key === explicitPreferred)
    ? explicitPreferred
    : options.some((opt) => opt.key === preferredFromState)
      ? preferredFromState
      : NORTH_STAR_FINDINGS_ALL_LENSES_KEY;
  const selectedLabel = selectedKey === NORTH_STAR_FINDINGS_ALL_LENSES_KEY ? t("north_star.all_lenses") : selectedKey;
  const selectedFindings = byLens[selectedKey] || byLens[NORTH_STAR_FINDINGS_ALL_LENSES_KEY] || null;

  if (findingsLensSelect) {
    findingsLensSelect.innerHTML = options.length
      ? options.map((opt) => `<option value="${escapeHtml(opt.key)}">${escapeHtml(opt.label)}</option>`).join("")
      : `<option value="">${escapeHtml(t("north_star.no_findings"))}</option>`;
    findingsLensSelect.value = selectedKey;
    if (!findingsLensSelect.dataset.bound) {
      findingsLensSelect.addEventListener("change", () => {
        const key = String(findingsLensSelect.value || "");
        const label = key === NORTH_STAR_FINDINGS_ALL_LENSES_KEY ? t("north_star.all_lenses") : key;
        const picked = key ? state.northStarFindingsByLens?.[key] : null;
        setupNorthStarFindingsUi(picked, { lensKey: key, lensLabel: label });
      });
      findingsLensSelect.dataset.bound = "1";
    }
  }

  setupNorthStarFindingsUi(selectedFindings, { lensKey: selectedKey, lensLabel: selectedLabel });
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

  const topic = state.filters.northStarFindings.topic || [];
  const subject = state.filters.northStarFindings.subject || [];
  const theme = state.filters.northStarFindings.theme || [];
  const subtheme = state.filters.northStarFindings.subtheme || [];
  const match = state.filters.northStarFindings.match || [];
  const catalog = state.filters.northStarFindings.catalog || [];

  let items = itemsRaw.map((item) => {
    const topicNorm = normalizeNorthStarFindingTopic(item?.topic);
    const subjectNorm = extractNorthStarFindingSubjectNorm(item);
    const subjectLabelFromRegistry = getMechanismsSubjectLabel(subjectNorm);
    const join = getNorthStarJoinForItem(item);
    const workflowStage = deriveNorthStarWorkflowStage(item);
    const workflowStageLabel = formatNorthStarWorkflowStageLabel(workflowStage);
    return {
      ...item,
      _topic_norm: topicNorm,
      _subject_norm: subjectNorm,
      _subject_label: subjectLabelFromRegistry || subjectNorm || "—",
      _match_rank: findingsMatchRank(item?.match_status),
      _reasons_count: Array.isArray(item?.reasons) ? item.reasons.length : 0,
      _evidence_count: Array.isArray(item?.evidence_pointers) ? item.evidence_pointers.length : 0,
      _theme_label: join.theme_label,
      _subtheme_label: join.subtheme_label,
      _join_miss: join.miss,
      _join_fallback: join.fallback,
      _catalog_value: workflowStage,
      _catalog_label: workflowStageLabel,
    };
  });

  if (subject.length) {
    const subjectKeys = new Set(subject.map((val) => normalizeKey(val)));
    items = items.filter((item) => subjectKeys.has(normalizeKey(item._subject_norm)));
  }
  if (topic.length) {
    const topicKeys = new Set(topic.map((val) => normalizeKey(val)));
    items = items.filter((item) => topicKeys.has(normalizeKey(item._topic_norm)));
  }
  if (theme.length) {
    const themeKeys = new Set(theme.map((val) => normalizeKey(val)));
    items = items.filter((item) => themeKeys.has(normalizeKey(item._theme_label)));
  }
  if (subtheme.length) {
    const subthemeKeys = new Set(subtheme.map((val) => normalizeKey(val)));
    items = items.filter((item) => subthemeKeys.has(normalizeKey(item._subtheme_label)));
  }
  if (match.length) {
    const matchKeys = new Set(match.map((val) => normalizeKey(val)));
    items = items.filter((item) => matchKeys.has(normalizeKey(item.match_status)));
  }
  if (catalog.length) {
    const catalogKeys = new Set(catalog.map((val) => normalizeKey(val)));
    items = items.filter((item) => catalogKeys.has(normalizeKey(item._catalog_value)));
  }
  if (search) {
    const q = search.toUpperCase();
    items = items.filter((item) => {
      const hay = [
        item.catalog,
        item._catalog_label,
        item._catalog_value,
        item.id,
        item.title,
        item._topic_norm,
        item._theme_label,
        item._subtheme_label,
        item._subject_norm,
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
    const c = String(a._catalog_value || "").localeCompare(String(b._catalog_value || ""));
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
    const hasTransferScope = getNorthStarFindingsTransferScopes().length > 0;
    const sourceByLens = state.northStarFindingsSourceByLens && typeof state.northStarFindingsSourceByLens === "object"
      ? state.northStarFindingsSourceByLens
      : {};
    const sourceHasAny = Object.keys(sourceByLens).some((lensName) => {
      if (lensName === NORTH_STAR_FINDINGS_ALL_LENSES_KEY) return false;
      const lensItems = Array.isArray(sourceByLens[lensName]?.items) ? sourceByLens[lensName].items : [];
      return lensItems.length > 0;
    });
    const emptyKey = !hasTransferScope && sourceHasAny ? "empty.no_findings_transfer_scope" : "empty.no_findings_match";
    tableEl.innerHTML = `<div class="empty">${escapeHtml(t(emptyKey))}</div>`;
  } else {
    const headers = [
      includeLens ? t("north_star.table.lens") : null,
      t("north_star.table.match"),
      t("north_star.table.subject"),
      t("north_star.table.topic"),
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
            <td>${escapeHtml(String(item._subject_label || "—"))}</td>
            <td>${escapeHtml(item._topic_norm)}</td>
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
  const stageLabel = String(item._catalog_label || formatNorthStarWorkflowStageLabel(item._catalog_value || deriveNorthStarWorkflowStage(item)) || "");
  const subjectLabel = String(item._subject_label || item._subject_norm || "");

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
      <div class="note-meta">${renderNorthStarFindingsBadge(item.match_status)}${item.lens ? ` | lens=${escapeHtml(String(item.lens || ""))}` : ""} | subject=${escapeHtml(subjectLabel || "—")} | topic=${escapeHtml(topic)} | theme=${escapeHtml(themeLabel || "—")} | subtheme=${escapeHtml(subthemeLabel || "—")} | stage=${escapeHtml(stageLabel)} | id=${escapeHtml(String(item.id || ""))}</div>
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

function clearNorthStarFindingsFilters({ clearData = false } = {}) {
  state.filters.northStarFindings.search = "";
  state.filters.northStarFindings.subject = [];
  state.filters.northStarFindings.topic = [];
  state.filters.northStarFindings.perspective = [];
  state.filters.northStarFindings.topic_locked_by_perspective = false;
  state.filters.northStarFindings.theme = [];
  state.filters.northStarFindings.subtheme = [];
  state.filters.northStarFindings.match = [];
  state.filters.northStarFindings.catalog = [];
  setNorthStarFindingsPresetKey("CUSTOM");
  state.northStarFindingSelected = null;

  const searchInput = $("#ns-findings-search");
  if (searchInput) searchInput.value = "";

  ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"].forEach((field) => {
    const input = $(`#ns-findings-filter-${field}-input`);
    if (input) input.value = "";
    renderNorthStarFindingsTagSelect(field);
  });
  applyNorthStarPerspectiveCriteria(state.filters.northStarFindings.perspective);
  renderNorthStarFindingsTagSelect("topic");
  if (clearData) {
    state.northStarFindingsTransferScopes = [];
    const findingsByLens = buildNorthStarFindingsByLensFromSource();
    mountNorthStarFindingsByLens(findingsByLens, { preferredKey: NORTH_STAR_FINDINGS_ALL_LENSES_KEY });
    // Enforce empty tag state after UI setup to avoid stale chip remnants.
    state.filters.northStarFindings.search = "";
    state.filters.northStarFindings.preset = "CUSTOM";
    state.filters.northStarFindings.perspective = [];
    state.filters.northStarFindings.topic = [];
    state.filters.northStarFindings.subject = [];
    state.filters.northStarFindings.theme = [];
    state.filters.northStarFindings.subtheme = [];
    state.filters.northStarFindings.match = [];
    state.filters.northStarFindings.catalog = [];
    state.filters.northStarFindings.topic_locked_by_perspective = false;
    ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"].forEach((field) => {
      const wrap = $(`#ns-findings-filter-${field}`);
      if (wrap) wrap.classList.remove("open");
      const tagsEl = $(`#ns-findings-filter-${field}-tags`);
      if (tagsEl) tagsEl.innerHTML = "";
      const input = $(`#ns-findings-filter-${field}-input`);
      if (input) {
        input.value = "";
        setAriaExpanded(input, false);
      }
      renderNorthStarFindingsTagSelect(field);
    });
    renderNorthStarFindings();
  }
}

function applyMechanismTransferToFindings({ subjectId = "", themeLabel = "", subthemeLabel = "" } = {}) {
  const normalizedSubjectId = normalizeValue(subjectId);
  if (!normalizedSubjectId) return;
  const subject = getMechanismsSubjectById(normalizedSubjectId);
  const transferState = getMechanismsSubjectTransferState(subject || {});
  if (!subject || !transferState.enabled) {
    const hint = transferState.blockedTitle || t("north_star.mechanisms.transfer_blocked_hint");
    if (hint) showToast(hint, "warn");
    return;
  }

  addNorthStarFindingsTransferScope({
    subject_id: normalizedSubjectId,
    theme_label: normalizeValue(themeLabel),
    subtheme_label: normalizeValue(subthemeLabel),
  });
  const findingsByLens = buildNorthStarFindingsByLensFromSource();
  mountNorthStarFindingsByLens(findingsByLens, { preferredKey: NORTH_STAR_FINDINGS_ALL_LENSES_KEY });

  const currentItems = Array.isArray(state.northStarFindings?.items) ? state.northStarFindings.items : [];
  updateNorthStarFindingsFilterOptions(currentItems);

  state.filters.northStarFindings.search = "";
  state.filters.northStarFindings.preset = "CUSTOM";
  state.filters.northStarFindings.perspective = [];
  state.filters.northStarFindings.topic = [];
  state.filters.northStarFindings.topic_locked_by_perspective = false;
  state.filters.northStarFindings.subject = normalizedSubjectId ? [normalizedSubjectId] : [];
  state.filters.northStarFindings.theme = themeLabel ? [normalizeValue(themeLabel)] : [];
  state.filters.northStarFindings.subtheme = subthemeLabel ? [normalizeValue(subthemeLabel)] : [];
  state.filters.northStarFindings.match = [];
  state.filters.northStarFindings.catalog = [];
  state.northStarFindingSelected = null;
  setNorthStarFindingsPresetKey("CUSTOM");

  const searchInput = $("#ns-findings-search");
  if (searchInput) searchInput.value = "";

  ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"].forEach((field) => {
    const input = $(`#ns-findings-filter-${field}-input`);
    if (input) input.value = "";
    renderNorthStarFindingsTagSelect(field);
  });

  renderNorthStarFindings();

  const findingsAnchor = $("#ns-findings-meta") || $("#ns-findings-table");
  if (findingsAnchor && typeof findingsAnchor.scrollIntoView === "function") {
    findingsAnchor.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function setupNorthStarFindingsTagSelects() {
  if (northStarFindingsUiAttached) return;
  const fields = ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"];
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
    const hasTransferScope = getNorthStarFindingsTransferScopes().length > 0;
    const sourceByLens = state.northStarFindingsSourceByLens && typeof state.northStarFindingsSourceByLens === "object"
      ? state.northStarFindingsSourceByLens
      : {};
    const sourceHasAny = Object.keys(sourceByLens).some((lensName) => {
      if (lensName === NORTH_STAR_FINDINGS_ALL_LENSES_KEY) return false;
      const lensItems = Array.isArray(sourceByLens[lensName]?.items) ? sourceByLens[lensName].items : [];
      return lensItems.length > 0;
    });
    const lensMeta = normalizedLensKey
      ? `lens=${normalizedLensLabel} | total=${summary.total ?? itemsRaw.length} triggered=${summary.triggered ?? "-"} not_triggered=${summary.not_triggered ?? "-"} unknown=${summary.unknown ?? "-"}`
      : t("north_star.select_lens_hint");
    meta.textContent = !hasTransferScope && sourceHasAny
      ? `${lensMeta} | ${t("empty.no_findings_transfer_scope")}`
      : lensMeta;
  }
  renderNorthStarFindingsTransferScopes();

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

    const searchInput = $("#ns-findings-search");
    if (searchInput) {
      searchInput.addEventListener("input", () => renderNorthStarFindings());
    }

    setupNorthStarFindingsTagSelects();
    northStarFindingsControlsAttached = true;
  }

  const searchInput = $("#ns-findings-search");
  if (searchInput) {
    searchInput.value = state.filters.northStarFindings.search || "";
  }

  ["perspective", "subject", "topic", "theme", "subtheme", "match", "catalog"].forEach((field) => {
    renderNorthStarFindingsTagSelect(field);
  });
  const clearBtn = $("#ns-findings-clear");
  if (clearBtn && !clearBtn.dataset.bound) {
    clearBtn.addEventListener("click", (event) => {
      event.preventDefault();
      clearNorthStarFindingsFilters({ clearData: true });
    });
    clearBtn.dataset.bound = "1";
  }
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

function setMemoryStatus(payload) {
  const el = $("#memory-status");
  if (!el) return;
  const statusRaw = String(payload?.status || "").trim().toUpperCase();
  const status = statusRaw || "WARN";
  setBadge(el, status);
  el.textContent = t("status.memory", { status });
  const reason = payload?.availability?.reason || payload?.reason || "";
  const generatedAt = payload?.generated_at || "";
  el.title = [generatedAt ? `generated_at=${generatedAt}` : "", reason ? `reason=${reason}` : ""]
    .filter(Boolean)
    .join(" • ");
}

function pickStatus(data) {
  return data?.overall_status || data?.status || "UNKNOWN";
}

function renderTimelineDashboard() {
  const metaEl = $("#timeline-meta");
  const errorEl = $("#timeline-error");
  const totalToolEl = $("#timeline-total-tool");
  const processCountEl = $("#timeline-process-count");
  const processP95El = $("#timeline-process-p95");
  const nonToolRatioEl = $("#timeline-non-tool-ratio");
  const slowListEl = $("#timeline-slowest-list");
  const toolListEl = $("#timeline-tool-list");
  const refreshBtn = $("#timeline-refresh");

  if (refreshBtn) refreshBtn.disabled = Boolean(state.timelinePending);
  if (errorEl) {
    errorEl.textContent = state.timelineError || "";
    errorEl.style.display = state.timelineError ? "block" : "none";
  }
  if (state.timelinePending) {
    if (metaEl) metaEl.textContent = t("timeline.pending");
    return;
  }

  const payload = state.timeline && typeof state.timeline === "object" ? state.timeline : {};
  const dashboard = payload.dashboard && typeof payload.dashboard === "object" ? payload.dashboard : {};
  const rawReport = payload.report && typeof payload.report === "object" ? payload.report : {};
  const rangeSeconds = Number(rawReport?.detail?.time_range?.duration_seconds ?? 0);
  const rangeLabel = rangeSeconds > 0 ? formatSecondsShort(rangeSeconds) : "-";
  const generated = formatTimestamp(dashboard.generated_at) || dashboard.generated_at || "-";
  const eventsCount = Number(dashboard?.stats?.events_in_window ?? 0);

  if (!dashboard || !Object.keys(dashboard).length) {
    if (metaEl) metaEl.textContent = t("timeline.empty");
    if (totalToolEl) totalToolEl.textContent = "-";
    if (processCountEl) processCountEl.textContent = "-";
    if (processP95El) processP95El.textContent = "-";
    if (nonToolRatioEl) nonToolRatioEl.textContent = "-";
    if (slowListEl) slowListEl.innerHTML = "";
    if (toolListEl) toolListEl.innerHTML = "";
    return;
  }

  if (metaEl) {
    metaEl.textContent = t("timeline.meta", {
      generated: generated || "-",
      range: rangeLabel,
      events: Number.isFinite(eventsCount) ? String(eventsCount) : "-",
    });
  }
  if (totalToolEl) totalToolEl.textContent = formatDurationMs(dashboard?.tool_summary?.completed_total_ms ?? 0);
  if (processCountEl) processCountEl.textContent = String(Number(dashboard?.cycle_summary?.count ?? 0));
  if (processP95El) processP95El.textContent = formatDurationMs(dashboard?.cycle_summary?.p95_ms ?? 0);
  if (nonToolRatioEl) {
    const ratio = Number(dashboard?.cycle_summary?.non_tool_ratio ?? 0);
    nonToolRatioEl.textContent = Number.isFinite(ratio) ? `${Math.round(ratio * 100)}%` : "-";
  }

  const slowCycles = Array.isArray(dashboard?.slow_cycles) ? dashboard.slow_cycles : [];
  if (slowListEl) {
    if (!slowCycles.length) {
      slowListEl.innerHTML = `<div class="entry subtle">${escapeHtml(t("empty.no_items"))}</div>`;
    } else {
      slowListEl.innerHTML = slowCycles
        .slice(0, 8)
        .map((item, idx) => {
          const hint = escapeHtml(_shortenText(String(item?.user_hint || "-"), 140));
          const dur = formatDurationMs(item?.duration_ms ?? 0);
          const toolDur = formatDurationMs(item?.tool_total_ms ?? 0);
          const nonTool = formatDurationMs(item?.non_tool_ms ?? 0);
          const topTool = escapeHtml(String(item?.top_tool || "-"));
          return `<div class="entry">
            <div><strong>#${idx + 1}</strong> ${hint}</div>
            <div class="subtle">toplam=${dur} • tool=${toolDur} • non_tool=${nonTool} • top_tool=${topTool}</div>
          </div>`;
        })
        .join("");
    }
  }

  const tools = Array.isArray(dashboard?.tool_summary?.completed_by_tool) ? dashboard.tool_summary.completed_by_tool : [];
  if (toolListEl) {
    if (!tools.length) {
      toolListEl.innerHTML = `<div class="entry subtle">${escapeHtml(t("empty.no_items"))}</div>`;
    } else {
      toolListEl.innerHTML = tools
        .slice(0, 8)
        .map((item) => {
          const tool = escapeHtml(String(item?.tool || "-"));
          const total = formatDurationMs(item?.total_ms ?? 0);
          const p95 = formatDurationMs(item?.p95_ms ?? 0);
          const count = Number(item?.count ?? 0);
          return `<div class="entry">
            <div><strong>${tool}</strong></div>
            <div class="subtle">count=${count} • total=${total} • p95=${p95}</div>
          </div>`;
        })
        .join("");
    }
  }
}

function managedRepoRiskBadgeClass(level) {
  const norm = String(level || "LOW").trim().toUpperCase();
  if (norm === "CRITICAL") return "fail";
  if (norm === "HIGH" || norm === "MEDIUM") return "warn";
  return "ok";
}

function renderManagedReposPanel() {
  const multiRepoData = state.multiRepoStatus || {};
  const summary = multiRepoData.summary || {};
  const entries = Array.isArray(multiRepoData.entries) ? multiRepoData.entries : [];
  const summaryEl = $("#managed-repos-summary");
  const riskLineEl = $("#managed-repos-risk-line");
  const listEl = $("#managed-repos-list");
  const errorEl = $("#managed-repos-error");

  const totalRepos = Number(summary.all_entries_count || 0);
  const selectedRepos = Number(summary.selected_entries_count || entries.length);
  const criticalRepos = Number(summary.selected_critical_count || 0);

  if (summaryEl) {
    const totalText = totalRepos || selectedRepos;
    summaryEl.textContent = t("overview.multi_repo.summary", {
      selected: selectedRepos,
      total: totalText,
      critical: criticalRepos,
    });
  }

  if (riskLineEl) {
    const riskLine = String(summary.risk_line || "").trim();
    riskLineEl.textContent = riskLine ? t("overview.multi_repo.risk_line", { value: riskLine }) : "";
  }

  if (errorEl) {
    errorEl.textContent = state.multiRepoStatusError ? t("overview.multi_repo.error", { error: state.multiRepoStatusError }) : "";
    errorEl.style.color = state.multiRepoStatusError ? "var(--danger)" : "var(--muted)";
  }

  if (state.multiRepoStatusPending) {
    if (listEl) listEl.innerHTML = `<div class="subtle">${escapeHtml(t("overview.multi_repo.refreshing"))}</div>`;
    return;
  }

  if (!entries.length) {
    if (listEl) listEl.innerHTML = `<div class="entry subtle">${escapeHtml(t("overview.multi_repo.none"))}</div>`;
    return;
  }

  listEl.innerHTML = entries
    .map((entry) => {
      const slug = escapeHtml(String(entry?.repo_slug || entry?.repo_id || entry?.repo_root || "-"));
      const ws = escapeHtml(String(entry?.workspace_root || "-"));
      const root = escapeHtml(String(entry?.repo_root || "-"));
      const riskLevel = String(entry?.risk_level || "LOW");
      const riskScore = String(entry?.risk_score ?? 0);
      const statusText = [
        `overall=${escapeHtml(String(entry?.overall_status || "MISSING"))}`,
        `ext_single=${escapeHtml(String(entry?.extensions_single_gate_status || "MISSING"))}`,
        `ext_registry=${escapeHtml(String(entry?.extensions_registry_status || "MISSING"))}`,
        `ext_isolation=${escapeHtml(String(entry?.extensions_isolation_status || "MISSING"))}`,
        `quality=${escapeHtml(String(entry?.quality_gate_status || "MISSING"))}`,
        `readiness=${escapeHtml(String(entry?.readiness_status || "MISSING"))}`,
      ].join(" • ");
      const statusPath = escapeHtml(String(entry?.status_path || ""));
      const evidenceCount = Number(Array.isArray(entry?.evidence) ? entry.evidence.length : 0);
      const notes = Array.isArray(entry?.notes) ? entry.notes.slice(0, 2) : [];
      const notesText = notes.map((note) => String(note || "")).filter(Boolean).join(" • ");
      const badgeClass = managedRepoRiskBadgeClass(riskLevel);

      return `
        <div class="entry">
          <div class="row" style="justify-content: space-between; align-items: center; gap: 8px;">
            <strong>${slug}</strong>
            <span class="badge ${badgeClass}">${escapeHtml(riskLevel)} / ${escapeHtml(riskScore)}</span>
          </div>
          <div class="subtle">id=${escapeHtml(String(entry?.repo_id || "-"))} · ws=${ws}</div>
          <div class="subtle">root=${root}</div>
          <div class="subtle">${statusText}</div>
          <div class="subtle">path=${statusPath}</div>
          <div class="subtle">evidence=${evidenceCount}</div>
          ${notesText ? `<div class="subtle">${escapeHtml(`notes=${notesText}`)}</div>` : ""}
        </div>
      `;
    })
    .join("");
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

  renderManagedReposPanel();
  renderActionResponse();
  renderActionLog();
  renderSearchPanel();
  renderTimelineDashboard();
}

function renderSearchPanel() {
  const queryInput = $("#search-query");
  if (queryInput && queryInput.value !== state.searchQuery) {
    queryInput.value = state.searchQuery || "";
  }
  const globalInput = $("#global-search-query");
  if (globalInput && globalInput.value !== state.searchQuery) {
    globalInput.value = state.searchQuery || "";
  }
  const modeSelect = $("#search-mode");
  if (modeSelect && modeSelect.value !== state.searchMode) {
    modeSelect.value = state.searchMode || "auto";
  }
  const scopeSelect = $("#search-scope");
  if (scopeSelect && scopeSelect.value !== state.searchScope) {
    scopeSelect.value = state.searchScope || "ssot";
  }

  const statusEl = $("#search-status");
  if (statusEl) {
    if (state.searchPending) {
      statusEl.textContent = t("search.status.running");
    } else if (state.searchError) {
      statusEl.textContent = t("search.status.error", { error: state.searchError });
    } else if (state.searchQuery) {
      const modeLabel = state.searchLastMode || state.searchMode || "auto";
      statusEl.textContent = t("search.status.done", {
        count: Array.isArray(state.searchResults) ? state.searchResults.length : 0,
        mode: modeLabel,
      });
    } else {
      statusEl.textContent = t("search.status.idle");
    }
  }

  const engineEl = $("#search-engine-debug");
  const engineBadgeEl = $("#search-engine-badge");
  const engineText = String(state.searchEngineDebug || "").trim();
  const capForEngine = state.searchCapabilities && typeof state.searchCapabilities === "object" ? state.searchCapabilities : null;
  let semResolvedForEngine = "";
  let semStatusForEngine = "";
  let semReasonForEngine = "";
  if (capForEngine && Array.isArray(capForEngine.adapters)) {
    const semPrimary = String(capForEngine?.selection?.semantic_primary || "").trim().toLowerCase();
    const semAdapters = capForEngine.adapters.filter((item) => String(item?.engine || "").toLowerCase() === "semantic");
    const semAdapter =
      semAdapters.find((item) => String(item?.adapter_id || "").toLowerCase() === semPrimary) ||
      semAdapters[0] ||
      null;
    if (semAdapter) {
      semResolvedForEngine = String(semAdapter?.tooling?.resolved_adapter || "").trim();
      semStatusForEngine = String(semAdapter?.status || "").trim().toUpperCase();
      semReasonForEngine = String(semAdapter?.reason || "").trim();
    }
  }
  if (engineEl) {
    engineEl.textContent = engineText ? t("search.engine.value", { engine: engineText }) : t("search.engine.none");
  }
  if (engineBadgeEl) {
    engineBadgeEl.classList.remove("ok", "warn", "fail", "idle");
    if (engineText) {
      engineBadgeEl.classList.add("ok");
      engineBadgeEl.textContent = t("search.engine.badge.value", { engine: engineText });
      const titleParts = [
        t("search.engine.value", { engine: engineText }),
        t("search.status.done", {
          count: Array.isArray(state.searchResults) ? state.searchResults.length : 0,
          mode: state.searchLastMode || state.searchMode || "auto",
        }),
      ];
      if (semStatusForEngine || semResolvedForEngine || semReasonForEngine) {
        titleParts.push(`semantic_status=${semStatusForEngine || "-"}`);
        titleParts.push(`semantic_adapter=${semResolvedForEngine || "-"}`);
        if (semReasonForEngine) titleParts.push(`semantic_reason=${semReasonForEngine}`);
      }
      engineBadgeEl.title = titleParts.join(" • ");
    } else {
      engineBadgeEl.classList.add("idle");
      engineBadgeEl.textContent = t("search.engine.badge.none");
      engineBadgeEl.title = t("search.engine.none");
    }
  }

  const indexEl = $("#search-index-status");
  const spinnerEl = $("#search-index-spinner");
  if (indexEl) {
    const idx = state.searchIndex && typeof state.searchIndex === "object" ? state.searchIndex : null;
    const buildStatus = String(idx?.build_status || "").trim().toUpperCase();
    const isBuilding = String(state.searchIndexStatus || "").trim().toUpperCase() === "BUILDING" || buildStatus === "BUILDING";
    const st = String(state.searchIndexStatus || "").trim().toUpperCase();

    if (state.searchIndexPending) {
      indexEl.textContent = t("search.index.refreshing");
    } else if (state.searchIndexError) {
      indexEl.textContent = t("search.index.error", { error: state.searchIndexError });
    } else if (isBuilding) {
      const done = Number(idx?.build_progress?.processed_files ?? 0);
      const total = Number(idx?.build_progress?.total_files ?? 0);
      const eta = Number(idx?.build_eta_seconds ?? idx?.predicted_eta_seconds ?? 0);
      const etaLabel = eta > 0 ? formatSecondsShort(eta) : "-";
      if (total > 0) {
        indexEl.textContent = t("search.index.building", { done: String(done), total: String(total), eta: etaLabel });
      } else {
        indexEl.textContent = t("search.index.building_scan");
      }
    } else if (st === "MISSING") {
      indexEl.textContent = t("search.index.none");
    } else if (idx) {
      indexEl.textContent = t("search.index.ready", {
        indexed_at: formatTimestamp(idx.indexed_at) || idx.indexed_at || "-",
        files: idx.file_count ?? "-",
        records: idx.record_count ?? "-",
        adapter: idx.adapter_id || "-",
      });
    } else {
      indexEl.textContent = t("search.index.none");
    }
  }
  if (spinnerEl) {
    const idx = state.searchIndex && typeof state.searchIndex === "object" ? state.searchIndex : null;
    const buildStatus = String(idx?.build_status || "").trim().toUpperCase();
    const isBuilding = String(state.searchIndexStatus || "").trim().toUpperCase() === "BUILDING" || buildStatus === "BUILDING";
    spinnerEl.style.display = state.searchIndexPending || isBuilding ? "block" : "none";
  }

  const etaEl = $("#search-index-eta");
  if (etaEl) {
    const idx = state.searchIndex && typeof state.searchIndex === "object" ? state.searchIndex : null;
    const buildStatus = String(idx?.build_status || "").trim().toUpperCase();
    const isBuilding = String(state.searchIndexStatus || "").trim().toUpperCase() === "BUILDING" || buildStatus === "BUILDING";

    if (isBuilding) {
      const eta = Number(idx?.build_eta_seconds ?? idx?.predicted_eta_seconds ?? 0);
      etaEl.textContent = eta > 0 ? t("search.index.predicted", { eta: formatSecondsShort(eta) }) : "";
    } else if (idx) {
      const indexedAt = parseTimestampMs(idx.indexed_at);
      const pieces = [];
      if (indexedAt) {
        const ageMs = Math.max(0, Date.now() - indexedAt);
        const remainingMs = Math.max(0, SEARCH_INDEX_AUTO_REFRESH_MS - ageMs);
        const ageLabel = formatAgeShort(ageMs);
        const remainingLabel = formatAgeShort(remainingMs);
        pieces.push(t("search.index.age", { age: ageLabel }));
        pieces.push(t("search.index.remaining", { remaining: remainingLabel }));
      }
      const predicted = Number(idx.predicted_eta_seconds ?? 0);
      if (predicted > 0) {
        pieces.push(t("search.index.predicted", { eta: formatSecondsShort(predicted) }));
      }
      etaEl.textContent = pieces.filter(Boolean).join(" • ");
    } else {
      etaEl.textContent = "";
    }
  }

  const cap = state.searchCapabilities && typeof state.searchCapabilities === "object" ? state.searchCapabilities : null;
  const capStatusEl = $("#search-capabilities-status");
  const capRoutingEl = $("#search-capabilities-routing");
  const capSelectionEl = $("#search-capabilities-selection");
  const capAdaptersEl = $("#search-capabilities-adapters");
  const semanticBadgeEl = $("#search-semantic-badge");

  const setSemanticBadge = (tone, textKey, titleText = "") => {
    if (!semanticBadgeEl) return;
    semanticBadgeEl.classList.remove("ok", "warn", "fail", "idle");
    semanticBadgeEl.classList.add(tone);
    semanticBadgeEl.textContent = t(textKey);
    semanticBadgeEl.title = titleText || "";
  };

  if (semanticBadgeEl) {
    if (state.searchCapabilitiesPending) {
      setSemanticBadge("idle", "search.capabilities.semantic.pending", t("search.capabilities.loading"));
    } else if (state.searchCapabilitiesError) {
      setSemanticBadge(
        "fail",
        "search.capabilities.semantic.failed",
        t("search.capabilities.error", { error: state.searchCapabilitiesError })
      );
    } else if (cap) {
      const adapters = Array.isArray(cap?.adapters) ? cap.adapters : [];
      const semanticPrimary = String(cap?.selection?.semantic_primary || "").trim().toLowerCase();
      const semanticAdapters = adapters.filter((item) => String(item?.engine || "").toLowerCase() === "semantic");
      let semanticAdapter =
        semanticAdapters.find((item) => String(item?.adapter_id || "").toLowerCase() === semanticPrimary) ||
        semanticAdapters[0] ||
        null;
      if (!semanticAdapter && semanticPrimary) {
        semanticAdapter = adapters.find((item) => String(item?.adapter_id || "").toLowerCase() === semanticPrimary) || null;
      }
      if (!semanticAdapter) {
        setSemanticBadge("idle", "search.capabilities.semantic.none");
      } else {
        const adapterId = String(semanticAdapter?.adapter_id || "-");
        const status = String(semanticAdapter?.status || "").trim().toUpperCase();
        const reason = String(semanticAdapter?.reason || "").trim();
        const titleParts = [`${adapterId} • ${status || "-"}`];
        if (reason) {
          titleParts.push(t("search.capabilities.semantic.reason", { reason }));
        }
        if (status === "READY") {
          setSemanticBadge("ok", "search.capabilities.semantic.ready", titleParts.join(" • "));
        } else if (status === "UNAVAILABLE") {
          setSemanticBadge("warn", "search.capabilities.semantic.unavailable", titleParts.join(" • "));
        } else {
          setSemanticBadge("fail", "search.capabilities.semantic.failed", titleParts.join(" • "));
        }
      }
    } else {
      setSemanticBadge("idle", "search.capabilities.semantic.none");
    }
  }

  if (capStatusEl) {
    if (state.searchCapabilitiesPending) {
      capStatusEl.textContent = t("search.capabilities.loading");
    } else if (state.searchCapabilitiesError) {
      capStatusEl.textContent = t("search.capabilities.error", { error: state.searchCapabilitiesError });
    } else if (cap) {
      capStatusEl.textContent = t("search.capabilities.status", {
        contract: String(cap.contract_id || "-"),
        scope: String(cap.scope || state.searchScope || "ssot"),
        index: String(cap.index?.status || "-"),
      });
    } else {
      capStatusEl.textContent = "";
    }
  }
  if (capRoutingEl) {
    if (cap && !state.searchCapabilitiesPending && !state.searchCapabilitiesError) {
      capRoutingEl.textContent = t("search.capabilities.routing", {
        auto: String(cap.routing?.auto_mode_primary || "-"),
        keyword: String(cap.selection?.keyword_primary || "-"),
        semantic: String(cap.selection?.semantic_primary || "-"),
      });
    } else {
      capRoutingEl.textContent = "";
    }
  }
  if (capSelectionEl) {
    if (cap && !state.searchCapabilitiesPending && !state.searchCapabilitiesError) {
      capSelectionEl.textContent = t("search.capabilities.selection", {
        keyword: String(cap.fallback_chain?.keyword || []),
        semantic: String(cap.fallback_chain?.semantic || []),
      });
    } else {
      capSelectionEl.textContent = "";
    }
  }
  if (capAdaptersEl) {
    if (state.searchCapabilitiesPending) {
      capAdaptersEl.innerHTML = `<div class="entry subtle">${escapeHtml(t("search.capabilities.loading"))}</div>`;
    } else if (state.searchCapabilitiesError) {
      capAdaptersEl.innerHTML = `<div class="entry subtle">${escapeHtml(
        t("search.capabilities.error", { error: state.searchCapabilitiesError })
      )}</div>`;
    } else {
      const adapters = Array.isArray(cap?.adapters) ? cap.adapters : [];
      if (!adapters.length) {
        capAdaptersEl.innerHTML = `<div class="entry subtle">${escapeHtml(t("search.capabilities.adapters.none"))}</div>`;
      } else {
        const rows = adapters.map((item) => {
          const adapterId = String(item?.adapter_id || "-");
          const engine = String(item?.engine || "-");
          const status = String(item?.status || "-");
          const reason = String(item?.reason || "-");
          const tooling = String(item?.tooling?.primary || "-");
          return `<div class="entry"><div class="row" style="justify-content: space-between; gap: 8px; align-items: center;"><div><b>${escapeHtml(
            adapterId
          )}</b> • ${escapeHtml(engine)}</div><div class="subtle">${escapeHtml(status)}</div></div><div class="subtle">${escapeHtml(
            tooling
          )} • ${escapeHtml(reason)}</div></div>`;
        });
        capAdaptersEl.innerHTML = rows.join("");
      }
    }
  }

  const resultsEl = $("#search-results");
  if (!resultsEl) return;
  const results = Array.isArray(state.searchResults) ? state.searchResults : [];
  if (!results.length) {
    if (state.searchQuery && !state.searchPending && !state.searchError) {
      resultsEl.innerHTML = `<div class="entry subtle">${escapeHtml(t("search.no_results"))}</div>`;
    } else {
      resultsEl.innerHTML = "";
    }
    return;
  }
  const rows = results.map((hit) => {
    const path = String(hit?.path || "");
    const line = Number.isFinite(Number(hit?.line)) ? `:${hit.line}` : "";
    const score = Number.isFinite(Number(hit?.score)) ? ` score=${Number(hit.score).toFixed(4)}` : "";
    const meta = `${path}${line}${score}`.trim();
    const preview = _shortenText(String(hit?.preview || ""), 320);
    const openPath = path ? `${path}${line}` : "";
    const openBtn = openPath
      ? `<button class="btn ghost btn-mini" data-search-open="${escapeHtml(openPath)}">${escapeHtml(
          t("actions.open")
        )}</button>`
      : "";
    return `<div class="entry"><div class="row" style="justify-content: space-between; align-items: center; gap: 8px;"><div class="subtle">${escapeHtml(
      meta || "-"
    )}</div>${openBtn}</div><div>${escapeHtml(preview)}</div></div>`;
  });
  resultsEl.innerHTML = rows.join("");
}

function _shortenText(text, limit) {
  const raw = String(text || "");
  if (raw.length <= limit) return raw;
  return raw.slice(0, Math.max(0, limit - 3)) + "...";
}

function normalizeSearchMode(mode) {
  const raw = String(mode || "").trim().toLowerCase();
  if (raw === "semantic" || raw === "keyword" || raw === "auto") return raw;
  return "auto";
}

function normalizeSearchScope(scope) {
  const raw = String(scope || "").trim().toLowerCase();
  if (raw === "repo" || raw === "ssot") return raw;
  return "ssot";
}

function deriveSearchEngineDebug(payload, requestedMode) {
  const payloadObj = payload && typeof payload === "object" ? payload : null;
  const explicitEngine = String(payloadObj?.engine || "").trim();
  if (explicitEngine) return explicitEngine;
  const mode = String(payloadObj?.mode || requestedMode || "auto").trim().toLowerCase();
  const adapter = String(payloadObj?.index?.adapter_id || "").trim();
  const patternMode = String(payloadObj?.pattern_mode || "").trim().toLowerCase();

  if (mode === "semantic") {
    return adapter ? `semantic/${adapter}` : "semantic";
  }
  if (mode === "keyword") {
    const base = adapter || "keyword";
    return patternMode ? `${base} • rg:${patternMode}` : base;
  }
  return mode || "";
}

function isSearchIndexBuilding() {
  const status = String(state.searchIndexStatus || "").trim().toUpperCase();
  const buildStatus = String(state.searchIndex?.build_status || "").trim().toUpperCase();
  return status === "BUILDING" || buildStatus === "BUILDING";
}

function stopSearchIndexPolling() {
  if (state.searchIndexPollTimer) clearInterval(state.searchIndexPollTimer);
  state.searchIndexPollTimer = null;
  state.searchIndexPollUntil = 0;
}

function startSearchIndexPolling({ rerunSearch = false } = {}) {
  state.searchRerunAfterIndex = rerunSearch ? true : state.searchRerunAfterIndex;
  if (state.searchIndexPollTimer) return;
  state.searchIndexPollUntil = Date.now() + 5 * 60 * 1000; // 5 min hard stop
  state.searchIndexPollTimer = setInterval(async () => {
    await refreshSearchIndexStatus();
    const building = isSearchIndexBuilding();
    const timedOut = state.searchIndexPollUntil && Date.now() > state.searchIndexPollUntil;
    if (!building || timedOut) {
      stopSearchIndexPolling();
      if (!building && state.searchRerunAfterIndex) {
        state.searchRerunAfterIndex = false;
        runSearch();
      }
    }
  }, 900);
}

async function refreshSearchIndexStatus() {
  try {
    const scope = normalizeSearchScope(state.searchScope);
    const payload = await fetchJson(`${endpoints.searchIndex}?action=status&scope=${encodeURIComponent(scope)}`);
    state.searchIndexStatus = String(payload?.status || "");
    state.searchIndex = payload?.index || null;
    state.searchIndexError = "";
  } catch (err) {
    state.searchIndexStatus = "FAIL";
    state.searchIndexError = formatError(err);
  }
  renderSearchPanel();
}

async function refreshSearchCapabilities() {
  state.searchCapabilitiesPending = true;
  state.searchCapabilitiesError = "";
  renderSearchPanel();
  try {
    const scope = normalizeSearchScope(state.searchScope);
    const payload = await fetchJson(`${endpoints.searchCapabilities}?scope=${encodeURIComponent(scope)}`);
    state.searchCapabilities = payload && typeof payload === "object" ? payload : null;
    state.searchCapabilitiesError = "";
  } catch (err) {
    state.searchCapabilities = null;
    state.searchCapabilitiesError = formatError(err);
  } finally {
    state.searchCapabilitiesPending = false;
    renderSearchPanel();
  }
}

async function refreshSearchContext() {
  await Promise.all([refreshSearchIndexStatus(), refreshSearchCapabilities()]);
}

async function updateSearchIndex({ rebuild = true } = {}) {
  if (state.searchIndexPending) return;
  state.searchIndexPending = true;
  state.searchIndexError = "";
  renderSearchPanel();
  try {
    const scope = normalizeSearchScope(state.searchScope);
    const url = `${endpoints.searchIndex}?action=build&scope=${encodeURIComponent(scope)}&rebuild=${rebuild ? "true" : "false"}`;
    const payload = await fetchJson(url);
    state.searchIndexStatus = String(payload?.status || "");
    state.searchIndex = payload?.index || null;
    const st = String(payload?.status || "").trim().toUpperCase();
    if (st === "BUILDING") {
      state.searchIndexError = "";
      startSearchIndexPolling({ rerunSearch: true });
    } else {
      state.searchIndexError = payload?.error ? String(payload.error) : "";
      if (payload?.status !== "OK" && payload?.status !== "STALE" && payload?.status !== "MISSING" && !state.searchIndexError) {
        state.searchIndexError = t("error.unknown");
      }
    }
  } catch (err) {
    state.searchIndexStatus = "FAIL";
    state.searchIndexError = formatError(err);
  } finally {
    state.searchIndexPending = false;
    renderSearchPanel();
  }
}

async function runSearch() {
  const query = String(state.searchQuery || "").trim();
  if (!query) {
    state.searchResults = [];
    state.searchError = "";
    state.searchLastMode = "";
    state.searchEngineDebug = "";
    renderSearchPanel();
    return;
  }
  if (state.searchPending) return;
  state.searchPending = true;
  state.searchError = "";
  renderSearchPanel();
  const mode = normalizeSearchMode(state.searchMode);
  const scope = normalizeSearchScope(state.searchScope);
  const url =
    mode === "auto"
      ? `${endpoints.search}?q=${encodeURIComponent(query)}&scope=${encodeURIComponent(scope)}`
      : `${endpoints.search}?q=${encodeURIComponent(query)}&scope=${encodeURIComponent(scope)}&mode=${encodeURIComponent(mode)}`;
  try {
    const payload = await fetchJson(url);
    const st = String(payload?.status || "").trim().toUpperCase();
    state.searchLastMode = String(payload?.mode || mode || "");
    state.searchEngineDebug = deriveSearchEngineDebug(payload, mode);

    if (st === "INDEX_BUILDING") {
      state.searchResults = [];
      state.searchError = "";
      if (payload?.index && typeof payload.index === "object") {
        state.searchIndex = payload.index;
        state.searchIndexStatus = "BUILDING";
      }
      startSearchIndexPolling({ rerunSearch: true });
    } else if (st === "OK" || !payload?.status) {
      state.searchResults = Array.isArray(payload?.hits) ? payload.hits : [];
      state.searchError = "";
      if (payload?.index && typeof payload.index === "object") {
        state.searchIndex = payload.index;
      }
    } else {
      state.searchResults = Array.isArray(payload?.hits) ? payload.hits : [];
      state.searchError = payload?.error ? String(payload.error) : t("error.unknown");
      if (payload?.index && typeof payload.index === "object") {
        state.searchIndex = payload.index;
      }
    }
  } catch (err) {
    state.searchError = formatError(err);
    state.searchResults = [];
    state.searchEngineDebug = "";
  } finally {
    state.searchPending = false;
    renderSearchPanel();
  }
}

function maybeAutoRefreshSearchIndex(reason = "") {
  if (state.searchIndexPending) return;
  const indexedAt = parseTimestampMs(state.searchIndex?.indexed_at);
  const now = Date.now();
  if (!indexedAt) return;
  if (now - indexedAt >= SEARCH_INDEX_AUTO_REFRESH_MS) {
    updateSearchIndex({ rebuild: true });
  }
}

function scheduleSearchIndexAutoRefresh() {
  if (state.searchIndexAutoTimer) clearInterval(state.searchIndexAutoTimer);
  state.searchIndexAutoTimer = setInterval(() => {
    maybeAutoRefreshSearchIndex("timer");
  }, SEARCH_INDEX_POLL_MS);
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

function renderNorthStarFlow2Status() {
  const payload = state.northStarFlow2Status || {};
  const badgeEl = $("#north-star-flow2-status");
  const summaryEl = $("#north-star-flow2-summary");
  const badgesEl = $("#north-star-flow2-badges");
  const linesEl = $("#north-star-flow2-lines");
  const invalidNoteEl = $("#north-star-flow2-invalid-note");

  const assessment = payload.assessment || {};
  const policy = payload.policy || {};
  const system = payload.system || {};
  const project = payload.project || {};
  const invalidEnvelope = payload.invalid_envelope || {};
  const overall = normalizeNorthStarStatusToken(payload.overall_status || "UNKNOWN");
  const available = Boolean(payload.available);

  setBadge(badgeEl, overall);

  const assessmentAt = formatTimestamp(assessment.generated_at || "") || "-";
  const systemAt = formatTimestamp(system.generated_at || "") || "-";
  const policyInputs = Number.isFinite(Number(policy.total_inputs)) ? String(toSafeInt(policy.total_inputs, 0)) : "-";

  if (summaryEl) {
    summaryEl.textContent = available
      ? t("north_star.flow2.summary", {
          assessment_at: assessmentAt,
          system_at: systemAt,
          policy_inputs: policyInputs,
        })
      : t("north_star.flow2.summary_missing");
  }

  if (badgesEl) {
    const chips = [
      {
        label: t("north_star.flow2.assessment"),
        status: normalizeNorthStarStatusToken(assessment.status || "UNKNOWN"),
      },
      {
        label: t("north_star.flow2.policy"),
        status: normalizeNorthStarStatusToken(policy.status || "UNKNOWN"),
      },
      {
        label: t("north_star.flow2.system"),
        status: normalizeNorthStarStatusToken(system.status || "UNKNOWN"),
      },
      {
        label: t("north_star.flow2.project"),
        status: normalizeNorthStarStatusToken(project.status || "UNKNOWN"),
      },
    ];
    badgesEl.innerHTML = chips
      .map((chip) => `<span class="badge ${chip.status === "FAIL" ? "fail" : chip.status === "WARN" ? "warn" : chip.status === "OK" ? "ok" : "idle"}">${escapeHtml(chip.label)}=${escapeHtml(chip.status)}</span>`)
      .join("");
  }

  if (linesEl) {
    const details = [
      t("north_star.flow2.line.assessment", {
        controls: String(toSafeInt(assessment.controls, 0)),
        metrics: String(toSafeInt(assessment.metrics, 0)),
        packs: String(toSafeInt(assessment.packs, 0)),
      }),
      t("north_star.flow2.line.policy", {
        allow: String(toSafeInt(policy.allow, 0)),
        suspend: String(toSafeInt(policy.suspend, 0)),
        invalid: String(toSafeInt(policy.invalid_envelope, 0)),
        diff: String(toSafeInt(policy.diff_nonzero, 0)),
      }),
      t("north_star.flow2.line.system", {
        actions: String(toSafeInt(system.actions_count, 0)),
        sb_fail: String(toSafeInt(system.script_budget_fail_count, 0)),
        sb_warn: String(toSafeInt(system.script_budget_warn_count, 0)),
      }),
      t("north_star.flow2.line.project", {
        next_milestone: String(project.next_milestone || "-"),
        core_lock: String(project.core_lock || "-"),
      }),
    ];
    linesEl.innerHTML = details.map((line) => `<div>${escapeHtml(line)}</div>`).join("");
  }

  if (invalidNoteEl) {
    const invalidCount = toSafeInt(invalidEnvelope.count, 0);
    if (invalidCount <= 0) {
      invalidNoteEl.textContent = t("north_star.flow2.invalid_none");
    } else if (invalidEnvelope.expected_fixture) {
      invalidNoteEl.textContent = t("north_star.flow2.invalid_expected", {
        file: String(invalidEnvelope.sample_file || "fixtures/envelopes/0999_invalid.json"),
      });
    } else {
      invalidNoteEl.textContent = t("north_star.flow2.invalid_unexpected");
    }
  }
}

function renderNorthStar() {
  const payload = state.northStar || {};
  const summary = payload.summary || {};
  const scores = summary.scores || {};
  const status = summary.status || "UNKNOWN";
  const evalData = unwrap(payload.assessment_eval || {});

  state.northStarCatalogIndex = buildNorthStarCatalogIndex(payload);
  state.northStarMatrices = {
    reference: unwrap(payload.reference_matrix || {}) || {},
    assessment: unwrap(payload.assessment_matrix || {}) || {},
    gap: unwrap(payload.gap_matrix || {}) || {},
  };
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
  renderNorthStarFlow2Status();

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
  renderNorthStarMechanisms();
  renderNorthStarSuggestions();

  // Lens Findings source comes from eval; visible rows are fail-closed behind manual transfer scopes.
  const sourceFindingsByLens = {};
  evalLensNames.forEach((name) => {
    const lens = evalLensMap?.[name];
    const findings = lens?.findings;
    if (findings && typeof findings === "object" && Array.isArray(findings.items)) {
      sourceFindingsByLens[name] = findings;
    }
  });
  state.northStarFindingsSourceByLens = sourceFindingsByLens;
  const findingsByLens = buildNorthStarFindingsByLensFromSource();
  mountNorthStarFindingsByLens(findingsByLens);

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
    { key: "short_id", label: "ID", html: true, render: (item) => {
        const full = String(item?.intake_id || "").trim();
        const short = shortIntakeId(full);
        if (!full) return `<span class="subtle">-</span>`;
        return `<button class="btn small ghost intake-short-id" type="button" data-copy-intake-id="${encodeTag(full)}" title="Copy full intake_id">${escapeHtml(short || full)}</button>`;
      } },
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
        if (id && !state.intakeInlineGroup[id]) state.intakeInlineGroup[id] = "summary";
        if (id && !state.intakeInlineTab[id]) state.intakeInlineTab[id] = "summary";
        state.intakeEvidencePath = null;
        state.intakeEvidencePreview = null;
        state.intakeLinkedNotes = null;
        state.intakeLinkedNotesLoading = false;
        state.intakeLinkedNotesError = null;
        renderIntakeTable((unwrap(state.intake || {}).items || []));
        if (state.intakeExpandedId) {
          renderIntakeDetail(item);
          refreshIntakeLinkedNotes(item);
          renderIntakeClaimControls(item);
        }
      },
    }
  );

  const tableEl = $("#intake-table");
  if (tableEl) {
    tableEl.querySelectorAll("[data-copy-intake-id]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const full = decodeTag(btn.dataset.copyIntakeId || "");
        if (full) copyText(full);
      });
    });
  }

  if (state.intakeExpandedId && state.intakeSelected && state.intakeSelected.intake_id === state.intakeExpandedId) {
    renderIntakeDetail(state.intakeSelected);
  }

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

function deriveExtensionAbout(detail) {
  const manifest = detail?.manifest || {};
  const notes = Array.isArray(manifest.notes) ? manifest.notes.map((item) => String(item)) : [];
  const entrypoints = manifest.entrypoints || {};
  const policies = Array.isArray(manifest.policies) ? manifest.policies : [];
  const docsRef = String(manifest.docs_ref || "");
  return {
    summary: notes[0] || "",
    notes,
    entrypoints,
    policies,
    docs_ref: docsRef,
  };
}

function buildExtensionAbout(detail, overrideEntry, extras) {
  const extId = String(detail?.extension_id || "");
  const manifest = detail?.manifest || {};
  const entrypoints = manifest.entrypoints || {};
  const ops = Array.isArray(entrypoints.ops) ? entrypoints.ops : [];
  const cockpitSections = Array.isArray(entrypoints.cockpit_sections) ? entrypoints.cockpit_sections : [];
  const policies = Array.isArray(manifest.policies) ? manifest.policies : [];
  const docsRef = String(manifest.docs_ref || "");
  const enabled = typeof detail?.enabled === "boolean" ? detail.enabled : manifest.enabled;
  const overrideEnabled = overrideEntry?.enabled;
  const effectiveEnabled = typeof overrideEnabled === "boolean" ? overrideEnabled : enabled;
  const notes = Array.isArray(manifest.notes) ? manifest.notes.map((item) => String(item)) : [];
  const derived = extras?.about || deriveExtensionAbout(detail);
  const mapped = EXTENSION_DESCRIPTIONS_TR[extId] || {};
  const summary = normalizeAboutSummary(mapped.summary || derived.summary || notes[0] || "") ||
    `${extId} eklentisi için kısa açıklama bulunamadı.`;
  const policyLabel = buildPolicyLabelList(policies, 3);
  const bullets = [];
  if (mapped.value) bullets.push({ label: "Ne sağlar", value: mapped.value });
  if (mapped.when) bullets.push({ label: "Ne zaman", value: mapped.when });
  if (mapped.output) bullets.push({ label: "Çıktı", value: mapped.output });
  bullets.push({ label: "Durum", value: effectiveEnabled ? "Etkin" : "Devre dışı" });
  if (docsRef) bullets.push({ label: "Doküman", value: docsRef });
  if (ops.length) bullets.push({ label: "Ops komutları", value: ops.join(", ") });
  if (cockpitSections.length) bullets.push({ label: "Cockpit yüzeyi", value: cockpitSections.join(", ") });
  if (policies.length) bullets.push({ label: "Policy’ler", value: policyLabel });
  return { summary, bullets };
}

function buildExtensionDetailSections(detail, overrideEntry, extras, loading) {
  const sections = [];
  const about = buildExtensionAbout(detail, overrideEntry, extras);
  sections.push({ id: "about", label: t("extensions.detail.about"), kind: "about", data: about });
  const manifest = detail?.manifest && Object.keys(detail.manifest || {}).length ? detail.manifest : null;
  if (manifest) {
    sections.push({ id: "manifest", label: t("extensions.detail.manifest"), kind: "json", data: manifest });
  }
  const readmeText = extras?.readme?.text || "";
  sections.push({
    id: "readme",
    label: t("extensions.detail.readme"),
    kind: "readme",
    text: readmeText || (loading ? t("extensions.detail.loading") : t("extensions.detail.empty")),
    path: extras?.readme?.path || "",
  });
  const policyItems = Array.isArray(extras?.policies) ? extras.policies : [];
  sections.push({
    id: "policies",
    label: t("extensions.detail.policies"),
    kind: "policy",
    items: policyItems,
    loading,
  });
  const opsMetrics = extras?.opsMetrics || (loading ? { status: t("extensions.detail.loading") } : {});
  sections.push({ id: "ops", label: t("extensions.detail.ops"), kind: "json", data: opsMetrics });
  const meta = {
    extension_id: detail?.extension_id || "",
    manifest_path: detail?.manifest_path || "",
    registry_path: state.extensions?.registry_path || "",
    registry_exists: state.extensions?.registry_exists ?? null,
    registry_json_valid: state.extensions?.registry_json_valid ?? null,
  };
  sections.push({ id: "meta", label: t("extensions.detail.meta"), kind: "json", data: meta });
  if (overrideEntry && Object.keys(overrideEntry || {}).length) {
    sections.push({ id: "overrides", label: t("extensions.detail.overrides"), kind: "json", data: overrideEntry });
  }
  return sections;
}

function buildExtensionDetailHtml(extId, sections) {
  if (!Array.isArray(sections) || sections.length === 0) {
    return `<div class="ext-detail-panel"><div class="subtle">${escapeHtml(t("extensions.detail.empty"))}</div></div>`;
  }
  const showTabs = sections.length > 1;
  const tabsHtml = showTabs
    ? `<div class="ext-detail-tabs">
        ${sections
          .map(
            (section, idx) =>
              `<button class="ext-detail-tab${idx === 0 ? " active" : ""}" data-ext-tab="${escapeHtml(section.id)}">${escapeHtml(
                section.label
              )}</button>`
          )
          .join("")}
      </div>`
    : "";
  const panesHtml = sections
    .map((section, idx) => {
      const paneClass = `ext-detail-pane${idx === 0 ? " active" : ""}`;
      if (section.kind === "policy") {
        const items = Array.isArray(section.items) ? section.items : [];
        if (!items.length) {
          const emptyLabel = section.loading ? t("extensions.detail.loading") : t("extensions.detail.empty");
          return `<div class="${paneClass}" data-ext-pane="${escapeHtml(section.id)}">
              <div class="subtle">${escapeHtml(emptyLabel)}</div>
            </div>`;
        }
        const tabs = items
          .map(
            (item, itemIndex) =>
              `<button class="ext-subtab${itemIndex === 0 ? " active" : ""}" data-ext-subtab="${escapeHtml(
                item.policy_id
              )}">${escapeHtml(item.label)}</button>`
          )
          .join("");
        const panes = items
          .map(
            (item, itemIndex) =>
              `<div class="ext-subpane${itemIndex === 0 ? " active" : ""}" data-ext-subpane="${escapeHtml(
                item.policy_id
              )}">
                <pre data-ext-policy="${escapeHtml(item.policy_id)}"></pre>
              </div>`
          )
          .join("");
        return `<div class="${paneClass}" data-ext-pane="${escapeHtml(section.id)}">
            <div class="ext-subtabs">${tabs}</div>
            <div class="ext-subpanes">${panes}</div>
          </div>`;
      }
      if (section.kind === "readme") {
        return `<div class="${paneClass}" data-ext-pane="${escapeHtml(section.id)}">
            <pre data-ext-text="${escapeHtml(section.id)}"></pre>
          </div>`;
      }
      if (section.kind === "about") {
        const data = section.data || {};
        const bullets = Array.isArray(data.bullets) ? data.bullets : [];
        const bulletHtml = bullets
          .map(
            (item) =>
              `<div class="ext-about-item"><span class="ext-about-label">${escapeHtml(
                item.label
              )}</span><span class="ext-about-value">${escapeHtml(item.value)}</span></div>`
          )
          .join("");
        return `<div class="${paneClass}" data-ext-pane="${escapeHtml(section.id)}">
            <div class="ext-about">
              <div class="ext-about-summary">${escapeHtml(String(data.summary || ""))}</div>
              <div class="ext-about-list">${bulletHtml}</div>
            </div>
          </div>`;
      }
      return `<div class="${paneClass}" data-ext-pane="${escapeHtml(section.id)}">
          <pre data-ext-json="${escapeHtml(section.id)}"></pre>
        </div>`;
    })
    .join("");
  return `
    <div class="ext-detail-panel">
      <div class="ext-detail-header">
        <div class="ext-detail-title">${escapeHtml(extId)}</div>
        ${tabsHtml}
      </div>
      <div class="ext-detail-body">
        ${panesHtml}
      </div>
    </div>
  `;
}

function hydrateExtensionDetailPanel(list, extId, sections) {
  const row = list.querySelector(`[data-ext-detail="${encodeTag(extId)}"]`);
  if (!row) return;
  sections.forEach((section) => {
    if (section.kind === "readme") {
      const pre = row.querySelector(`[data-ext-text="${section.id}"]`);
      renderPlainText(pre, section.text || "");
      return;
    }
    if (section.kind === "policy") {
      const items = Array.isArray(section.items) ? section.items : [];
      items.forEach((item) => {
        const pre = row.querySelector(`[data-ext-policy="${item.policy_id}"]`);
        renderJson(pre, item.data || {});
      });
      return;
    }
    const pre = row.querySelector(`[data-ext-json="${section.id}"]`);
    renderJson(pre, section.data);
  });
  row.querySelectorAll(".ext-detail-panel").forEach((panel) => {
    panel.querySelectorAll("[data-ext-tab]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const target = btn.dataset.extTab || "";
        if (!target) return;
        panel.querySelectorAll(".ext-detail-tab").forEach((tab) => tab.classList.remove("active"));
        btn.classList.add("active");
        panel.querySelectorAll(".ext-detail-pane").forEach((pane) => {
          pane.classList.toggle("active", pane.dataset.extPane === target);
        });
      });
    });
    panel.querySelectorAll("[data-ext-subtab]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const target = btn.dataset.extSubtab || "";
        if (!target) return;
        const container = btn.closest(".ext-detail-pane");
        if (!container) return;
        container.querySelectorAll(".ext-subtab").forEach((tab) => tab.classList.remove("active"));
        btn.classList.add("active");
        container.querySelectorAll(".ext-subpane").forEach((pane) => {
          pane.classList.toggle("active", pane.dataset.extSubpane === target);
        });
      });
    });
  });
}

async function loadExtensionDetailExtras(extId, detail) {
  const extras = {
    about: deriveExtensionAbout(detail),
    readme: null,
    policies: [],
    opsMetrics: null,
  };
  const manifestPath = String(detail?.manifest_path || "");
  if (manifestPath) {
    const parts = manifestPath.split("/");
    const extDir = parts.slice(0, -1).join("/");
    const candidates = ["README.md", "README.v1.md", "README.v2.md", "README.txt"];
    for (const name of candidates) {
      const path = `${extDir}/${name}`;
      try {
        const payload = await fetchJson(`${endpoints.file}?path=${encodeURIComponent(path)}`);
        if (payload?.exists && payload?.data?.text) {
          extras.readme = { path, text: payload.data.text };
          break;
        }
      } catch (err) {
        continue;
      }
    }
  }
  const policyPaths = Array.isArray(detail?.manifest?.policies) ? detail.manifest.policies : [];
  const uniquePolicies = Array.from(new Set(policyPaths.map((p) => String(p || "").trim()).filter(Boolean)));
  for (const path of uniquePolicies) {
    let payload = null;
    try {
      payload = await fetchJson(`${endpoints.file}?path=${encodeURIComponent(path)}`);
    } catch (err) {
      payload = null;
    }
    extras.policies.push({
      path,
      label: path.split("/").slice(-1)[0] || path,
      policy_id: `pol_${extras.policies.length + 1}`,
      data: payload?.data || {},
      exists: payload?.exists ?? false,
    });
  }
  const usage = state.extensionUsage || {};
  const byExt = usage.by_extension || {};
  const count = Number(byExt?.[extId] || 0);
  const matched = Number(usage.matched_entries || 0);
  const total = Number(usage.total_entries || 0);
  const share = matched ? Math.round((count / matched) * 1000) / 10 : 0;
  extras.opsMetrics = {
    usage_count: count,
    matched_entries: matched,
    total_entries: total,
    share_percent: share,
    generated_at: usage.generated_at || "",
  };
  return extras;
}

async function toggleExtensionDetail(extId) {
  if (!extId) return;
  if (state.extensionDetailExpanded === extId) {
    state.extensionDetailExpanded = "";
    renderExtensionsList(state.extensions?.items || []);
    return;
  }
  state.extensionDetailExpanded = extId;
  if (!state.extensionDetail || state.extensionDetail.extension_id !== extId) {
    try {
      state.extensionDetail = await fetchJson(`${endpoints.extensions}?extension_id=${encodeURIComponent(extId)}`);
    } catch (err) {
      showToast(t("toast.refresh_failed", { name: t("h.extension_detail"), error: formatError(err) }), "warn");
      state.extensionDetail = null;
    }
  }
  renderExtensionsList(state.extensions?.items || []);
  if (!state.extensionDetail) return;
  if (!state.extensionDetailExtras[extId]) {
    state.extensionDetailExtrasLoading = extId;
    renderExtensionsList(state.extensions?.items || []);
    try {
      state.extensionDetailExtras[extId] = await loadExtensionDetailExtras(extId, state.extensionDetail);
    } finally {
      state.extensionDetailExtrasLoading = "";
      renderExtensionsList(state.extensions?.items || []);
    }
  }
  const row = $("#extensions-list")?.querySelector(`[data-ext-row="${encodeTag(extId)}"]`);
  row?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderExtensionsList(items) {
  const list = $("#extensions-list");
  if (!list) return;
  if (!Array.isArray(items) || items.length === 0) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_extensions_found"))}</div>`;
    return;
  }
  const overrides = state.extensions?.overrides?.overrides || {};
  const openId = state.extensionDetailExpanded;
  const detail = state.extensionDetail;
  const extras = openId ? state.extensionDetailExtras?.[openId] : null;
  const loading = state.extensionDetailExtrasLoading === openId;
  const openSections =
    openId && detail?.extension_id === openId
      ? buildExtensionDetailSections(detail, overrides?.[openId], extras, loading)
      : [];
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
      const isOpen = openId === extId;
      const detailHtml = isOpen ? buildExtensionDetailHtml(extId, openSections) : `<div class="ext-detail-panel"></div>`;
      return `
        <tr class="ext-row" data-ext-row="${extAttr}">
          <td>${escapeHtml(extId)}</td>
          <td>${escapeHtml(semver)}</td>
          <td>${badge}</td>
          <td>
            <button class="btn" data-ext-view="${extAttr}">${escapeHtml(t("actions.view"))}</button>
            <button class="btn warn" data-ext-toggle="${extAttr}" data-ext-enable="${toggleTarget}">${escapeHtml(toggleLabel)}</button>
          </td>
        </tr>
        <tr class="ext-detail-row${isOpen ? " open" : ""}" data-ext-detail="${extAttr}">
          <td colspan="4">${detailHtml}</td>
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
  list.querySelectorAll("[data-ext-row]").forEach((row) => {
    row.addEventListener("click", async (event) => {
      if (event.target.closest("button")) return;
      const extId = decodeTag(row.dataset.extRow || "");
      await toggleExtensionDetail(extId);
    });
  });
  list.querySelectorAll("[data-ext-view]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const extId = decodeTag(btn.dataset.extView || "");
      await toggleExtensionDetail(extId);
    });
  });
  $$("[data-ext-toggle]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const extId = decodeTag(btn.dataset.extToggle || "");
      const enable = btn.dataset.extEnable === "true";
      if (!extId) return;
      postAction("extension-toggle", endpoints.extensionToggle, { extension_id: extId, enabled: enable });
    });
  });
  applyAdminModeToWriteControls();
  if (openId && openSections.length) {
    hydrateExtensionDetailPanel(list, openId, openSections);
  }
}

function renderExtensionDetail() {
  renderExtensionsList(state.extensions?.items || []);
}

function inferTimestampFromPath(path) {
  const text = String(path || "");
  const match = text.match(/(20\d{2})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/);
  if (match) {
    const iso = `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}Z`;
    const ts = Date.parse(iso);
    if (Number.isFinite(ts)) return ts;
  }
  const matchDate = text.match(/(20\d{2}-\d{2}-\d{2})/);
  if (matchDate) {
    const ts = Date.parse(`${matchDate[1]}T00:00:00Z`);
    if (Number.isFinite(ts)) return ts;
  }
  return 0;
}

function buildExtensionKeywordMap(extIds) {
  const map = {};
  extIds.forEach((extId) => {
    const raw = String(extId || "");
    const lower = raw.toLowerCase();
    const clean = lower.replace(/^prj-/, "");
    const slug = clean.replace(/[^a-z0-9]+/g, "_");
    map[raw] = [lower, clean, slug, clean.replace(/_/g, "-")];
  });
  return map;
}

function inferExtensionFromPath(path, extIds, keywordMap) {
  const lower = String(path || "").toLowerCase();
  for (const extId of extIds) {
    if (!extId) continue;
    const extLower = String(extId || "").toLowerCase();
    if (extLower && lower.includes(extLower)) return extId;
    const keywords = keywordMap[extId] || [];
    for (const token of keywords) {
      if (token && lower.includes(token)) return extId;
    }
  }
  return "";
}

function normalizeWorkspaceAbsolutePath(path) {
  const raw = String(path || "").trim();
  if (!raw || !raw.startsWith("/")) return raw;
  const wsRoot = String(state.ws?.workspace_root || "").trim();
  if (!wsRoot) return raw;
  if (!raw.startsWith(wsRoot)) return raw;
  const suffix = raw.slice(wsRoot.length);
  const normalized = suffix.startsWith("/") ? suffix : `/${suffix}`;
  return `.cache/ws_customer_default${normalized}`;
}

function renderExtensionUsage() {
  const table = $("#extensions-usage-table");
  if (!table) return;
  const report = state.extensionUsage || {};
  const entries = Array.isArray(state.opsLogIndex?.entries) ? state.opsLogIndex.entries : [];

  const extensionItems = Array.isArray(state.extensions?.items) ? state.extensions.items : [];
  const extIds = extensionItems.map((item) => String(item.extension_id || "")).filter((x) => x);
  const keywordMap = buildExtensionKeywordMap(extIds);

  const rowsRaw = entries.map((entry, idx) => {
    const path = String(entry.path || "");
    const kind = String(entry.kind || entry.type || "");
    const ext = String(entry.extension_id || entry?.meta?.extension_id || inferExtensionFromPath(path, extIds, keywordMap) || "UNKNOWN");
    const ts = entry.created_at ? Date.parse(String(entry.created_at || "")) : inferTimestampFromPath(path);
    const time = Number.isFinite(ts) && ts > 0 ? new Date(ts).toISOString() : "";
    return { idx, time, ts: Number.isFinite(ts) ? ts : 0, kind, extension: ext, path };
  });

  const extFilter = String(state.extensionUsageFilters.extension || "");
  const kindFilter = String(state.extensionUsageFilters.kind || "");
  const search = String(state.extensionUsageFilters.search || "").trim().toLowerCase();

  let rows = rowsRaw.filter((row) => {
    if (extFilter && row.extension !== extFilter) return false;
    if (kindFilter && row.kind !== kindFilter) return false;
    if (search) {
      const hay = `${row.time} ${row.kind} ${row.extension} ${row.path}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });

  rows.sort((a, b) => (b.ts || 0) - (a.ts || 0) || a.idx - b.idx);

  const total = rowsRaw.length || Number(report.total_entries || 0);
  const matched = rows.length || Number(report.matched_entries || 0);
  const unknownCount = rowsRaw.length
    ? rowsRaw.filter((row) => row.extension === "UNKNOWN").length
    : Number(report.unknown_entries || 0);
  const pills = $("#extensions-usage-pills");
  if (pills) {
    const byExtension = report.by_extension && typeof report.by_extension === "object" ? report.by_extension : {};
    const topEntries = Object.entries(byExtension)
      .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
      .slice(0, 5);
    const usedTotal = Object.values(byExtension).reduce((acc, v) => acc + Number(v || 0), 0);
    const sumTop = topEntries.reduce((acc, [, count]) => acc + Number(count || 0), 0);
    const extSegments = [];
    topEntries.forEach(([id, count]) => {
      extSegments.push({ id: String(id), count: Number(count || 0) });
    });
    if (unknownCount) extSegments.push({ id: "UNKNOWN", count: Number(unknownCount || 0) });
    if (usedTotal > sumTop) extSegments.push({ id: "OTHER", count: Math.max(0, usedTotal - sumTop) });
    const palette = ["#2fdbAA", "#8aa6ff", "#f0b25c", "#ff7aa2", "#9ad0f5", "#b388ff", "#7bd389"];
    const maxTop = topEntries.length ? Math.max(...topEntries.map(([, count]) => Number(count) || 0)) : 0;
    const topBars = topEntries
      .map(([id, count]) => {
        const pct = maxTop ? Math.round((Number(count) || 0) / maxTop * 100) : 0;
        return `
          <div class="mini-bar" style="--w:${pct}%">
            <span class="label">${escapeHtml(String(id))}</span>
            <span class="count">${escapeHtml(String(count))}</span>
          </div>
        `;
      })
      .join("");
    const dailyBuckets = (() => {
      const now = new Date();
      const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
      const windowDays = 14;
      const buckets = [];
      const byDay = new Map();
      rowsRaw.forEach((row) => {
        const ts = Number(row.ts || 0);
        if (!ts) return;
        const dayKey = new Date(ts).toISOString().slice(0, 10);
        const ext = String(row.extension || "UNKNOWN");
        if (!byDay.has(dayKey)) byDay.set(dayKey, new Map());
        const extMap = byDay.get(dayKey);
        extMap.set(ext, (extMap.get(ext) || 0) + 1);
      });
      for (let offset = windowDays - 1; offset >= 0; offset -= 1) {
        const day = new Date(end.getTime() - offset * 86400000);
        const key = day.toISOString().slice(0, 10);
        const extMap = byDay.get(key) || new Map();
        const totalCount = Array.from(extMap.values()).reduce((acc, v) => acc + Number(v || 0), 0);
        buckets.push({ key, count: totalCount, extMap });
      }
      return buckets;
    })();
    const maxDaily = dailyBuckets.reduce((acc, bucket) => Math.max(acc, Number(bucket.count) || 0), 0);
    const topIds = topEntries.map(([id]) => String(id));
    const dailyBars = dailyBuckets
      .map((bucket) => {
        const height = maxDaily ? Math.max(6, Math.round((Number(bucket.count) || 0) / maxDaily * 64)) : 6;
        const dim = bucket.count ? "" : " dim";
        const label = bucket.key.slice(5);
        const extMap = bucket.extMap || new Map();
        const segs = [];
        let otherCount = 0;
        const keys = Array.from(extMap.keys());
        keys.forEach((ext) => {
          const count = Number(extMap.get(ext) || 0);
          if (!count) return;
          if (topIds.includes(ext)) {
            segs.push({ id: ext, count });
          } else {
            otherCount += count;
          }
        });
        if (otherCount) segs.push({ id: "OTHER", count: otherCount });
        if (!segs.length && bucket.count) segs.push({ id: "UNKNOWN", count: bucket.count });
        const segHtml = segs
          .map((seg) => {
            const segPct = bucket.count ? Math.max(5, Math.round((seg.count / bucket.count) * 100)) : 0;
            const colorIdx = extSegments.findIndex((s) => s.id === seg.id);
            const color = palette[(colorIdx >= 0 ? colorIdx : segs.indexOf(seg)) % palette.length];
            return `<span class="bar-seg" style="--seg:${segPct}%; --c:${color}"></span>`;
          })
          .join("");
        return `
          <div class="usage-day${dim}" title="${escapeHtml(`${bucket.key}: ${bucket.count}`)}">
            <div class="bar-stack" style="--h:${height}px">${segHtml}</div>
            <span class="label">${escapeHtml(label)}</span>
          </div>
        `;
      })
      .join("");
    const summary = t("extensions.usage.summary", { matched, total, unknown: unknownCount });
    let accPct = 0;
    const donutStops = extSegments.length
      ? extSegments.map((seg, idx) => {
        const pct = usedTotal ? (seg.count / usedTotal) * 100 : 0;
        const start = accPct;
        accPct += pct;
        const color = palette[idx % palette.length];
        return `${color} ${start.toFixed(2)}% ${accPct.toFixed(2)}%`;
      }).join(", ")
      : "";
    const legendItems = extSegments.length
      ? extSegments.map((seg, idx) => {
        const pct = usedTotal ? Math.round((seg.count / usedTotal) * 100) : 0;
        const color = palette[idx % palette.length];
        return `
          <div class="legend-item">
            <span class="legend-swatch" style="background:${color}"></span>
            <span class="legend-label">${escapeHtml(String(seg.id))}</span>
            <span class="legend-value">${escapeHtml(String(seg.count))} (${pct}%)</span>
          </div>
        `;
      }).join("")
      : "";
    const topBlock = topBars
      ? `<div class="mini-bars" title="${escapeHtml(t("extensions.usage.top"))}">${topBars}</div>`
      : "";
    const dailyBlock = dailyBars
      ? `
        <div class="usage-chart">
          <div class="chart-title">${escapeHtml(t("extensions.usage.by_day"))}</div>
          <div class="chart-bars">${dailyBars}</div>
        </div>
      `
      : `
        <div class="usage-chart empty">
          <div class="chart-title">${escapeHtml(t("extensions.usage.by_day"))}</div>
          <div class="empty-note">${escapeHtml(t("extensions.usage.by_day_empty"))}</div>
        </div>
      `;
    const donutBlock = extSegments.length
      ? `
        <div class="donut-card">
          <div class="donut" style="--donut:${donutStops}"></div>
          <div class="donut-legend">${legendItems}</div>
        </div>
      `
      : "";
    pills.innerHTML = `
      <div class="row" style="gap:6px; flex-wrap:wrap; align-items:center;">
        <span class="badge">${escapeHtml(summary)}</span>
        ${topEntries.length ? `<span class="badge subtle">${escapeHtml(t("extensions.usage.top"))}</span>` : ""}
      </div>
      <div class="row mini-usage-row">
        ${donutBlock}
        ${topBlock}
        ${dailyBlock}
      </div>
    `;
  }

  const extSelect = $("#extensions-usage-extension");
  if (extSelect) {
    const extOptions = Array.from(new Set(rowsRaw.map((row) => row.extension).filter((x) => x))).sort((a, b) => a.localeCompare(b));
    if (extOptions.length === 0) {
      extSelect.innerHTML = `<option value="">${escapeHtml(t("extensions.usage.select_placeholder"))}</option>`;
      extSelect.value = "";
      extSelect.disabled = true;
    } else {
      extSelect.innerHTML = `<option value="">${escapeHtml(t("extensions.usage.select_placeholder"))}</option>` +
        extOptions.map((ext) => `<option value="${escapeHtml(ext)}">${escapeHtml(ext)}</option>`).join("");
      extSelect.disabled = false;
      if (extFilter && extOptions.includes(extFilter)) extSelect.value = extFilter;
      else extSelect.value = "";
    }
  }

  const kindSelect = $("#extensions-usage-kind");
  if (kindSelect) {
    const kindOptions = Array.from(new Set(rowsRaw.map((row) => row.kind).filter((x) => x))).sort((a, b) => a.localeCompare(b));
    if (kindOptions.length === 0) {
      kindSelect.innerHTML = `<option value="">${escapeHtml(t("extensions.usage.select_placeholder"))}</option>`;
      kindSelect.value = "";
      kindSelect.disabled = true;
    } else {
      kindSelect.innerHTML = `<option value="">${escapeHtml(t("extensions.usage.select_placeholder"))}</option>` +
        kindOptions.map((kind) => `<option value="${escapeHtml(kind)}">${escapeHtml(kind)}</option>`).join("");
      kindSelect.disabled = false;
      if (kindFilter && kindOptions.includes(kindFilter)) kindSelect.value = kindFilter;
      else kindSelect.value = "";
    }
  }

  const rowsHtml = rows
    .map((row) => {
      const pathAttr = encodeTag(row.path || "");
      const openBtn = row.path
        ? `<button class="btn small ghost" data-ext-usage-open="${pathAttr}" title="${escapeHtml(t("actions.view"))}">${escapeHtml(t("actions.view"))}</button>`
        : "";
      return `
        <tr>
          <td>${escapeHtml(row.time || "")}</td>
          <td>${escapeHtml(row.kind || "")}</td>
          <td>${escapeHtml(row.extension || "")}</td>
          <td class="subtle" style="word-break: break-all;">${escapeHtml(row.path || "")} ${openBtn}</td>
        </tr>
      `;
    })
    .join("");

  if (!entries.length) {
    table.innerHTML = `<div class="empty">${escapeHtml(t("extensions.usage.empty_hint"))}</div>`;
  } else {
    table.innerHTML = `
      <table>
        <thead><tr>
          <th>${escapeHtml(t("table.time"))}</th>
          <th>${escapeHtml(t("table.kind"))}</th>
          <th>${escapeHtml(t("table.extension"))}</th>
          <th>${escapeHtml(t("table.path"))}</th>
        </tr></thead>
        <tbody>${rowsHtml || `<tr><td colspan="4">${escapeHtml(t("empty.no_items"))}</td></tr>`}</tbody>
      </table>
    `;
  }

  table.querySelectorAll("[data-ext-usage-open]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const path = decodeTag(btn.dataset.extUsageOpen || "");
      if (!path) return;
      openEvidencePreview(path);
      navigateToTab("evidence");
    });
  });

  const unknownDetails = $("#extensions-usage-unknown");
  const unknownList = $("#extensions-usage-unknown-list");
  if (unknownList && unknownDetails) {
    const unknownSample = Array.isArray(report.unknown_sample) ? report.unknown_sample : [];
    if (!unknownSample.length) {
      unknownDetails.style.display = "none";
    } else {
      unknownDetails.style.display = "";
      unknownList.innerHTML = unknownSample.map((path) => `<div class="subtle">${escapeHtml(path)}</div>`).join("");
    }
  }

  const unusedEl = $("#extensions-usage-unused");
  if (unusedEl) {
    if (!rowsRaw.length) {
      unusedEl.textContent = t("extensions.usage.no_data");
    } else {
      const usedSet = new Set(rowsRaw.map((row) => row.extension).filter((x) => x && x !== "UNKNOWN"));
      const unused = extIds.filter((ext) => !usedSet.has(ext));
      if (!unused.length) {
        unusedEl.textContent = "";
      } else {
        unusedEl.textContent = t("extensions.usage.unused", { list: unused.join(", ") });
      }
    }
  }
}

async function refreshExtensionUsage() {
  const reportPath = resolveEvidencePathForApi(extensionUsageReportPath);
  const reportPayload = await fetchOptionalJson(reportPath);
  state.extensionUsage = unwrap(reportPayload || {});
  let opsLogPath = state.extensionUsage?.canonical_ops_log || "";
  if (!opsLogPath) {
    const ptrPayload = await fetchOptionalJson(resolveEvidencePathForApi(opsLogIndexPointerPath));
    const ptr = unwrap(ptrPayload || {});
    opsLogPath = ptr?.canonical_path || "";
  }
  if (opsLogPath) {
    const candidates = [
      opsLogPath,
      normalizeWorkspaceAbsolutePath(opsLogPath),
      resolveEvidencePathForApi(opsLogPath),
    ].filter((val, idx, arr) => val && arr.indexOf(val) === idx);
    let payload = null;
    for (const candidate of candidates) {
      payload = await fetchOptionalJson(candidate);
      if (payload) break;
    }
    state.opsLogIndex = unwrap(payload || {});
  } else {
    state.opsLogIndex = null;
  }
  renderExtensionUsage();
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
      const kind = String(link.kind || "").trim() || "link";
      const path = String(link.id_or_path || "").trim();
      const label = `${escapeHtml(kind)}:${escapeHtml(path)}`;
      const canOpen = kind === "evidence" && path;
      const openBtn = canOpen
        ? `<button class="btn small ghost" type="button" data-note-link-open="${encodeTag(path)}" title="${escapeHtml(t("evidence.open_in_evidence_title"))}">${escapeHtml(t("actions.view"))}</button>`
        : "";
      return `<div class="note-link-row"><span class="note-tag">${label}</span>${openBtn}<button class="btn ghost" data-link-remove="${idx}">${escapeHtml(t("notes.links.remove"))}</button></div>`;
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
  $$('[data-note-link-open]').forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const path = decodeTag(btn.dataset.noteLinkOpen || "");
      if (!path) return;
      previewIntakeEvidence(path);
      navigateToTab("evidence");
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

function filterNotes(items) {
  const searchEl = $("#notes-search");
  const tagEl = $("#notes-tag-filter");
  const search = ((searchEl ? searchEl.value : "") || "").trim().toLowerCase();
  const tagFilter = ((tagEl ? tagEl.value : "") || "").trim().toLowerCase();
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
  return filtered;
}

function noteRole(note) {
  const tags = normalizeNoteTags(note).map((t) => String(t).toLowerCase());
  const title = String(note.title || "").toLowerCase();
  if (tags.some((t) => t.includes("system") || t.includes("op") || t.includes("assistant") || t.includes("bot"))) {
    return "assistant";
  }
  if (tags.some((t) => t.includes("user") || t.includes("human"))) return "user";
  if (title.startsWith("op:") || title.startsWith("auto:") || title.startsWith("system")) return "assistant";
  return "user";
}

function noteTokenMeta(note) {
  const tags = normalizeNoteTags(note).map((t) => String(t));
  let tokens = null;
  let truncated = false;
  tags.forEach((tag) => {
    const raw = String(tag || "");
    if (raw.toLowerCase().startsWith("tokens_estimate:")) {
      const value = raw.split(":").slice(1).join(":").trim();
      const parsed = parseInt(value, 10);
      if (Number.isFinite(parsed)) tokens = parsed;
    }
    if (raw.toLowerCase() === "output_truncated:true") {
      truncated = true;
    }
  });
  return { tokens, truncated };
}

function noteModelMeta(note) {
  const tags = normalizeNoteTags(note).map((t) => String(t));
  let provider = "";
  let model = "";
  tags.forEach((tag) => {
    const raw = String(tag || "");
    if (raw.toLowerCase().startsWith("provider:")) {
      provider = raw.split(":").slice(1).join(":").trim();
    }
    if (raw.toLowerCase().startsWith("model:")) {
      model = raw.split(":").slice(1).join(":").trim();
    }
  });
  return { provider, model };
}

function normalizeNoteTags(note) {
  if (Array.isArray(note?.tags)) return note.tags;
  const raw = String(note?.tags || "").trim();
  if (!raw) return [];
  return raw.split(",").map((t) => t.trim()).filter((t) => t);
}

function formatChatBody(raw) {
  const text = String(raw || "");
  if (!text.trim()) return "";
  const lines = text.split(/\r?\n/);
  return lines
    .map((line) => {
      const trimmed = line.trim();
      const match = trimmed.match(/^[-–—\s]*\[?(PREVIEW|RESULT|EVIDENCE|ACTIONS|NEXT)\]?[-–—\s]*$/i);
      if (match) {
        return `<div class="chat-section">${escapeHtml(match[1].toUpperCase())}</div>`;
      }
      return `<div class="chat-line">${escapeHtml(line)}</div>`;
    })
    .join("");
}

function parseNoteTimestamp(note) {
  const raw = String(note?.created_at || note?.updated_at || "");
  const ts = Date.parse(raw);
  return Number.isFinite(ts) ? ts : 0;
}

function stopChatStreaming() {
  if (state.chatStreamTimer) clearInterval(state.chatStreamTimer);
  state.chatStreamTimer = null;
  state.chatStreamNoteId = null;
  state.chatStreamText = "";
  state.chatStreamIndex = 0;
  state.chatStreamThread = "";
  state.chatStreamItems = null;
}

function startChatStreaming(note, items) {
  if (!note || !note.note_id) return;
  stopChatStreaming();
  const text = String(note.body || note.body_excerpt || "");
  if (!text.trim()) return;
  state.chatStreamNoteId = note.note_id;
  state.chatLastAssistantNoteId = note.note_id;
  state.chatStreamText = text;
  state.chatStreamIndex = 0;
  state.chatStreamThread = state.plannerThread || "default";
  state.chatStreamItems = items;
  const step = Math.max(8, Math.ceil(text.length / 120));
  state.chatStreamTimer = setInterval(() => {
    state.chatStreamIndex = Math.min(text.length, state.chatStreamIndex + step);
    renderPlannerChat(state.chatStreamItems || []);
    if (state.chatStreamIndex >= text.length) {
      stopChatStreaming();
      renderPlannerChat(state.chatStreamItems || []);
    }
  }, 30);
}

function maybeStartStreamingLatestAssistant(items) {
  const activeThread = state.plannerThread || "default";
  if (!items.length || state.chatStreamNoteId) return;
  const assistantNotes = items.filter((item) => noteRole(item) === "assistant");
  if (!assistantNotes.length) return;
  const latest = assistantNotes
    .slice()
    .sort((a, b) => parseNoteTimestamp(a) - parseNoteTimestamp(b))
    .pop();
  if (!latest || !latest.note_id) return;
  if (state.chatLastAssistantNoteId && String(state.chatLastAssistantNoteId) === String(latest.note_id)) return;
  startChatStreaming(latest, items);
}

function startChatPending(thread) {
  const token = `pending_${Date.now()}`;
  state.chatPending = {
    token,
    thread: thread || "default",
    started_at_ms: Date.now(),
    started_at_iso: new Date().toISOString(),
  };
  return token;
}

function clearChatPending(token) {
  if (!state.chatPending) return;
  if (token && state.chatPending.token !== token) return;
  state.chatPending = null;
}

function maybeResolveChatPending(items) {
  const pending = state.chatPending;
  const thread = state.plannerThread || "default";
  if (!pending || pending.thread !== thread) return;
  const pendingTs = pending.started_at_ms || 0;
  const assistantNotes = items.filter((item) => noteRole(item) === "assistant");
  if (!assistantNotes.length) return;
  const candidate = assistantNotes
    .filter((item) => parseNoteTimestamp(item) >= pendingTs - 1500)
    .sort((a, b) => parseNoteTimestamp(a) - parseNoteTimestamp(b))
    .pop();
  if (!candidate) return;
  clearChatPending(pending.token);
  startChatStreaming(candidate, items);
}

function renderPlannerChat(items) {
  const list = $("#chat-log");
  if (!list) return;
  if (!items.length) {
    list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_chat_messages"))}</div>`;
    return;
  }
  const sorted = stableSort(items, compareBy("created_at", "asc"));
  const activeThread = state.plannerThread || "default";
  const streamingId = state.chatStreamThread === activeThread ? state.chatStreamNoteId : null;
  const streamText = state.chatStreamText || "";
  const streamIndex = state.chatStreamIndex || 0;
  const bodyMarkup = sorted
    .map((item) => {
      const role = noteRole(item);
      const roleLabel = role === "assistant" ? t("chat.role.assistant") : t("chat.role.user");
      const ts = String(item.created_at || item.updated_at || "");
      const title = String(item.title || "");
      const metaParts = [roleLabel];
      if (ts) metaParts.push(ts);
      if (title) metaParts.push(title);
      const rawBody = String(item.body || item.body_excerpt || "");
      if (role === "assistant") {
        const modelMeta = noteModelMeta(item);
        if (modelMeta.provider || modelMeta.model) {
          const label = modelMeta.provider && modelMeta.model
            ? `${modelMeta.provider}/${modelMeta.model}`
            : modelMeta.model || modelMeta.provider;
          metaParts.push(label);
        }
        const tokenMeta = noteTokenMeta(item);
        if (tokenMeta.tokens) {
          metaParts.push(`≈${tokenMeta.tokens} tok`);
        }
        if (tokenMeta.truncated) {
          metaParts.push("truncated");
        }
        if (rawBody) metaParts.push(`${rawBody.length} ch`);
      } else if (rawBody) {
        const approxTokens = Math.max(1, Math.ceil(rawBody.length / 4));
        metaParts.push(`≈${approxTokens} tok`);
        metaParts.push(`${rawBody.length} ch`);
      }
      const meta = metaParts.join(" • ");
      const isStreaming = streamingId && item.note_id === streamingId;
      let bodyText = rawBody;
      if (isStreaming) {
        const slice = streamText ? streamText.slice(0, Math.max(0, Math.min(streamIndex, streamText.length))) : bodyText;
        bodyText = slice + (streamIndex < streamText.length ? "\n|" : "");
      }
      const body = formatChatBody(bodyText);
      return `
        <div class="chat-message ${role}${isStreaming ? " typing" : ""}">
          <div class="chat-meta">${escapeHtml(meta)}</div>
          <div class="chat-body">${body}</div>
        </div>
      `;
    })
    .join("");
  let pendingMarkup = "";
  if (state.chatPending && state.chatPending.thread === activeThread) {
    const meta = `${t("chat.role.assistant")} • ${state.chatPending.started_at_iso || ""}`.trim();
    pendingMarkup = `
      <div class="chat-message assistant typing">
        <div class="chat-meta">${escapeHtml(meta)}</div>
        <div class="chat-body">${escapeHtml(t("chat.thinking"))}</div>
      </div>
    `;
  }
  list.innerHTML = `${bodyMarkup}${pendingMarkup}`;
}

function renderNotesList(items) {
  const list = $("#notes-list");
  let filtered = filterNotes(items);
  filtered = stableSort(filtered, compareBy(state.sort.notes.key, state.sort.notes.dir));
  const countEl = $("#notes-count");
  if (countEl) {
    countEl.textContent = t("meta.showing_notes", { count: String(filtered.length) });
  }
  if (list) {
    if (!filtered.length) {
      list.innerHTML = `<div class="empty">${escapeHtml(t("empty.no_notes"))}</div>`;
      return filtered;
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
  return filtered;
}

function renderNotes(items) {
  const filtered = renderNotesList(items);
  renderPlannerChat(filtered || []);
}

function setNotesView(view) {
  state.notesView = view === "list" ? "list" : "chat";
  const chat = $("#planner-chat-view");
  const list = $("#planner-list-view");
  if (chat) chat.style.display = state.notesView === "chat" ? "grid" : "none";
  if (list) list.style.display = state.notesView === "list" ? "block" : "none";
  const btnChat = $("#notes-view-chat");
  const btnList = $("#notes-view-list");
  if (btnChat) {
    btnChat.classList.toggle("accent", state.notesView === "chat");
    btnChat.classList.toggle("ghost", state.notesView !== "chat");
  }
  if (btnList) {
    btnList.classList.toggle("accent", state.notesView === "list");
    btnList.classList.toggle("ghost", state.notesView !== "list");
  }
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

function dedupeList(items) {
  const seen = new Set();
  return (items || []).filter((item) => {
    if (!item) return false;
    if (seen.has(item)) return false;
    seen.add(item);
    return true;
  });
}

async function fetchOptionalJson(path) {
  try {
    const endpoint = isWorkspaceReportsPath(path) ? endpoints.evidenceRead : endpoints.file;
    return await fetchJson(`${endpoint}?path=${encodeURIComponent(path)}`);
  } catch (_) {
    return null;
  }
}

async function fetchReportText(path) {
  try {
    const res = await fetch(`${endpoints.report}?path=${encodeURIComponent(path)}`);
    if (!res.ok) return null;
    return await res.text();
  } catch (_) {
    return null;
  }
}

function buildChatProviderMap(registryPayload, policyPayload) {
  const registry = unwrap(registryPayload || {}) || {};
  const policy = unwrap(policyPayload || {}) || {};
  const providers = Array.isArray(registry.providers) ? registry.providers : [];
  const policyProviders = policy.providers || {};
  const map = {};
  providers.forEach((entry) => {
    const id = String(entry?.id || "").trim();
    if (!id) return;
    const policyEntry = policyProviders[id] || {};
    let models = Array.isArray(policyEntry.allow_models) ? policyEntry.allow_models.slice() : [];
    const defaultModel = String(policyEntry.default_model || entry?.default_model || "").trim();
    if (models.includes("*")) models = defaultModel ? [defaultModel] : [];
    if (!models.length && defaultModel) models = [defaultModel];
    models = dedupeList(models);
    if (defaultModel && models.length && models[0] !== defaultModel) {
      models = [defaultModel, ...models.filter((m) => m !== defaultModel)];
    }
    map[id] = {
      enabled: policyEntry.enabled ?? entry?.enabled ?? true,
      defaultModel: defaultModel || (models[0] || ""),
      models,
    };
  });
  Object.keys(policyProviders || {}).forEach((id) => {
    if (map[id]) return;
    const policyEntry = policyProviders[id] || {};
    let models = Array.isArray(policyEntry.allow_models) ? policyEntry.allow_models.slice() : [];
    const defaultModel = String(policyEntry.default_model || "").trim();
    if (models.includes("*")) models = defaultModel ? [defaultModel] : [];
    if (!models.length && defaultModel) models = [defaultModel];
    models = dedupeList(models);
    map[id] = {
      enabled: policyEntry.enabled ?? true,
      defaultModel: defaultModel || (models[0] || ""),
      models,
    };
  });
  return map;
}

function buildProviderAllowlist(allowPayload) {
  const raw = unwrap(allowPayload || {}) || {};
  const allow = Array.isArray(raw.allow_providers) ? raw.allow_providers.map((x) => String(x).toLowerCase()) : [];
  const set = new Set(allow);
  const alias = {
    google: ["gemini"],
    gemini: ["google"],
    xai: ["grok"],
    grok: ["xai"],
  };
  return {
    allow_set: set,
    isAllowed(id) {
      const pid = String(id || "").toLowerCase();
      if (!set.size) return true;
      if (set.has(pid)) return true;
      const aliases = alias[pid] || [];
      return aliases.some((a) => set.has(a));
    },
  };
}

function buildChatProfileOptions(classPayload) {
  const registry = unwrap(classPayload || {}) || {};
  const classes = Array.isArray(registry.classes) ? registry.classes : [];
  if (!classes.length) return null;
  const active = [];
  const optional = [];
  classes.forEach((entry) => {
    const id = String(entry?.class_id || "").trim();
    if (!id) return;
    if (entry?.active_core === false) optional.push(id);
    else active.push(id);
  });
  const merged = dedupeList([...active, ...optional]);
  const fallback = Object.keys(CHAT_MODEL_GROUPS || {});
  return dedupeList([...merged, ...fallback]);
}

function resolveChatProfileLabel(profileId) {
  const label = CHAT_MODEL_GROUPS[profileId]?.label;
  if (label) return label;
  return profileId;
}


function saveChatSelection() {
  try {
    const payload = {
      profile: state.chatProfile || "",
      provider: state.chatProvider || "",
      model: state.chatModel || "",
    };
    localStorage.setItem(CHAT_SELECTION_STORAGE_KEY, JSON.stringify(payload));
  } catch (_) {
    // ignore storage errors
  }
}

function restoreChatSelection() {
  try {
    const raw = localStorage.getItem(CHAT_SELECTION_STORAGE_KEY);
    if (!raw) return;
    const payload = JSON.parse(raw);
    if (payload && typeof payload === "object") {
      if (payload.profile) state.chatProfile = String(payload.profile);
      if (payload.provider) state.chatProvider = String(payload.provider);
      if (payload.model) state.chatModel = String(payload.model);
    }
  } catch (_) {
    // ignore storage errors
  }
}

function buildChatProviderClassMap(providerMapPayload) {
  const registry = unwrap(providerMapPayload || {}) || {};
  const classes = registry.classes && typeof registry.classes === "object" ? registry.classes : {};
  const result = {};
  Object.keys(classes).forEach((classId) => {
    const entry = classes[classId] || {};
    const providers = entry.providers && typeof entry.providers === "object" ? entry.providers : {};
    const providerMap = {};
    Object.keys(providers).forEach((providerId) => {
      const p = providers[providerId] || {};
      let models = [];
      if (Array.isArray(p.models)) {
        models = p.models
          .map((item) => String(item?.model_id || "").trim())
          .filter((item) => item);
      }
      const pinned = String(p.pinned_model_id || "").trim();
      if (pinned) {
        models = [pinned, ...models.filter((m) => m !== pinned)];
      }
      models = dedupeList(models);
      providerMap[providerId] = models;
    });
    result[classId] = providerMap;
  });
  return result;
}

function buildAllowlistModelStatus(allowPayload) {
  const payload = unwrap(allowPayload || {}) || {};
  const items = Array.isArray(payload.items) ? payload.items : [];
  const generatedAt = payload.generated_at ? String(payload.generated_at) : null;
  const result = {};
  items.forEach((item) => {
    const providerId = String(item?.provider_id || "").trim();
    const modelId = String(item?.model_id || "").trim();
    if (!providerId || !modelId) return;
    const classes = Array.isArray(item?.classes_target) ? item.classes_target : [];
    const status = String(item?.status || "").toUpperCase();
    classes.forEach((classIdRaw) => {
      const classId = String(classIdRaw || "").trim().toUpperCase();
      if (!classId) return;
      if (!result[classId]) result[classId] = {};
      if (!result[classId][providerId]) result[classId][providerId] = {};
      result[classId][providerId][modelId] = {
        status,
        generated_at: generatedAt,
        error_code: item?.error_code || null,
        http_status: Number.isFinite(item?.http_status) ? Number(item.http_status) : null,
      };
    });
  });
  return result;
}

function buildChatProviderClassMeta(providerMapPayload, allowlistByClass) {
  const registry = unwrap(providerMapPayload || {}) || {};
  const classes = registry.classes && typeof registry.classes === "object" ? registry.classes : {};
  const result = {};
  Object.keys(classes).forEach((classId) => {
    const entry = classes[classId] || {};
    const providers = entry.providers && typeof entry.providers === "object" ? entry.providers : {};
    const providerMeta = {};
    Object.keys(providers).forEach((providerId) => {
      const p = providers[providerId] || {};
      const eligible = [];
      const status = {};
      const allowlistProvider =
        allowlistByClass && allowlistByClass[classId] && allowlistByClass[classId][providerId]
          ? allowlistByClass[classId][providerId]
          : null;
      if (Array.isArray(p.models)) {
        p.models.forEach((item) => {
          const modelId = String(item?.model_id || "").trim();
          if (!modelId) return;
          const stage = String(item?.stage || "").trim().toLowerCase();
          const probe = String(item?.probe_status || "").trim().toLowerCase();
          const latency = Number.isFinite(item?.probe_latency_ms_p95) ? Number(item.probe_latency_ms_p95) : null;
          const verifiedAt = item?.verified_at ? String(item.verified_at) : null;
          status[modelId] = {
            stage: stage || null,
            probe_status: probe || null,
            latency_ms_p95: latency,
            verified_at: verifiedAt,
          };
          if (stage === "verified" && probe === "ok") eligible.push(modelId);
          if (allowlistProvider && allowlistProvider[modelId] && !status[modelId].probe_status) {
            const allowEntry = allowlistProvider[modelId] || {};
            const allowStatus = String(allowEntry.status || "").toUpperCase();
            status[modelId].probe_status = allowStatus === "OK" ? "ok" : "fail";
            status[modelId].stage = allowStatus === "OK" ? "verified" : "unverified";
            if (!status[modelId].verified_at && allowEntry.generated_at) {
              status[modelId].verified_at = String(allowEntry.generated_at);
            }
            if (allowStatus === "OK") eligible.push(modelId);
          }
        });
      }
      if (allowlistProvider) {
        Object.keys(allowlistProvider).forEach((modelId) => {
          if (status[modelId]) return;
          const allowEntry = allowlistProvider[modelId] || {};
          const allowStatus = String(allowEntry.status || "").toUpperCase();
          status[modelId] = {
            stage: allowStatus === "OK" ? "verified" : "unverified",
            probe_status: allowStatus === "OK" ? "ok" : "fail",
            latency_ms_p95: null,
            verified_at: allowEntry.generated_at ? String(allowEntry.generated_at) : null,
          };
          if (allowStatus === "OK") eligible.push(modelId);
        });
      }
      const pinnedModelId = String(p?.pinned_model_id || "").trim();
      const preferredCandidateModelId = String(p?.preferred_candidate_model_id || "").trim();
      providerMeta[providerId] = {
        eligible: dedupeList(eligible),
        status,
        pinned_model_id: pinnedModelId || null,
        preferred_candidate_model_id: preferredCandidateModelId || null,
      };
    });
    result[classId] = providerMeta;
  });
  return result;
}

function mergeProviderMapWithProbeState(providerMapPayload, probeStatePayload) {
  const baseRegistry = unwrap(providerMapPayload || {}) || {};
  const probeRegistry = unwrap(probeStatePayload || {}) || {};
  const merged = { ...baseRegistry };
  const baseClasses =
    baseRegistry.classes && typeof baseRegistry.classes === "object" ? { ...baseRegistry.classes } : {};
  const probeClasses = probeRegistry.classes && typeof probeRegistry.classes === "object" ? probeRegistry.classes : {};
  const ensureProviders = (entry) => (entry && typeof entry.providers === "object" ? entry.providers : {});
  const normalizeProbeModels = (providerEntry) => {
    if (!providerEntry || typeof providerEntry !== "object") return [];
    const raw = providerEntry.models;
    if (Array.isArray(raw)) return raw;
    if (raw && typeof raw === "object") {
      return Object.keys(raw).map((modelId) => ({
        model_id: modelId,
        ...(raw[modelId] || {}),
      }));
    }
    return [];
  };

  Object.keys(probeClasses).forEach((classId) => {
    const baseEntry = baseClasses[classId] || {};
    const probeEntry = probeClasses[classId] || {};
    const baseProviders = { ...ensureProviders(baseEntry) };
    const probeProviders = ensureProviders(probeEntry);
    Object.keys(probeProviders).forEach((providerId) => {
      const baseProvider = baseProviders[providerId] || {};
      const baseModels = Array.isArray(baseProvider.models) ? baseProvider.models : [];
      const modelMap = {};
      baseModels.forEach((item) => {
        const modelId = String(item?.model_id || "").trim();
        if (!modelId) return;
        modelMap[modelId] = { ...item, model_id: modelId };
      });
      const probeModels = normalizeProbeModels(probeProviders[providerId]);
      probeModels.forEach((item) => {
        const modelId = String(item?.model_id || "").trim();
        if (!modelId) return;
        const existing = modelMap[modelId] || { model_id: modelId };
        const probeStatus = String(item?.probe_status || existing.probe_status || "").trim();
        const stageRaw = String(item?.stage || existing.stage || "").trim();
        const stage = stageRaw || (probeStatus.toLowerCase() === "ok" ? "verified" : existing.stage);
        modelMap[modelId] = {
          ...existing,
          ...item,
          stage,
          probe_status: probeStatus || existing.probe_status,
        };
      });
      const mergedProvider = { ...baseProvider, ...probeProviders[providerId] };
      const mergedModels = Object.values(modelMap);
      mergedProvider.models = mergedModels.length ? mergedModels : probeModels.slice();
      baseProviders[providerId] = mergedProvider;
    });
    baseClasses[classId] = { ...baseEntry, ...probeEntry, providers: baseProviders };
  });

  merged.classes = baseClasses;
  const path = providerMapPayload?.path || probeStatePayload?.path || "";
  return { path, data: merged };
}

function isAllowlistWarn() {
  const summary = state.chatAllowlistSummary || {};
  const status = String(summary.status || "").toUpperCase();
  const fail = Number(summary.fail || summary.fail_count || summary.failed || 0);
  return status === "WARN" && fail > 0;
}

function renderChatAllowlistHint(targetId) {
  const el = targetId ? document.getElementById(targetId) : null;
  if (!el) return;
  if (!isAllowlistWarn()) {
    el.textContent = "";
    el.style.display = "none";
    return;
  }
  const summary = state.chatAllowlistSummary || {};
  const fail = Number(summary.fail || summary.fail_count || summary.failed || 0);
  el.textContent = t("chat.allowlist_warn", { fail: Number.isFinite(fail) ? fail : "-" });
  el.style.display = "block";
}

function filterModelsForProfile(profileId, models) {
  const items = Array.isArray(models) ? models.slice() : [];
  if (!items.length) return items;
  const id = String(profileId || "").toUpperCase();
  const rules = {
    FAST_TEXT: { include: [], exclude: ["embedding", "image", "dall-e", "sora", "audio", "realtime", "moderation", "vision", "ocr", "qvq", "video"] },
    BALANCED_TEXT: { include: [], exclude: ["embedding", "image", "dall-e", "sora", "audio", "realtime", "moderation", "vision", "ocr", "qvq", "video"] },
    GOVERNANCE_ASSURANCE: { include: [], exclude: ["embedding", "image", "dall-e", "sora", "audio", "realtime", "moderation", "vision", "ocr", "qvq", "video"] },
    IMAGE_GEN: { include: ["image", "dall-e", "sora", "img"], exclude: ["realtime", "audio", "embedding"] },
    VIDEO_GEN: { include: ["sora", "video"], exclude: ["image", "audio", "embedding"] },
    AUDIO: { include: ["audio", "tts", "transcribe"], exclude: ["image", "video", "embedding"] },
    REALTIME_STREAMING: { include: ["realtime", "stream"], exclude: [] },
    OCR_DOC: { include: ["ocr"], exclude: [] },
    VISION_MM: { include: ["vision", "vl"], exclude: ["ocr"] },
    VISION_REASONING: { include: ["qvq", "vision", "reason"], exclude: [] },
    EMBEDDINGS: { include: ["embedding"], exclude: [] },
    MODERATION_SAFETY: { include: ["moderation"], exclude: [] },
    DEEP_RESEARCH: { include: ["deep-research", "research"], exclude: [] },
    CODE_AGENTIC: { include: ["codex", "code"], exclude: [] },
    REASONING_TEXT: {
      include: [],
      exclude: ["embedding", "image", "dall-e", "sora", "audio", "realtime", "moderation", "vision", "ocr", "qvq", "video"],
    },
  };
  const rule = rules[id];
  if (!rule) return items;
  const filtered = items.filter((model) => {
    const name = String(model || "").toLowerCase();
    const includeHit = !rule.include.length || rule.include.some((token) => name.includes(token));
    const excludeHit = rule.exclude.some((token) => name.includes(token));
    return includeHit && !excludeHit;
  });
  if (filtered.length) return filtered;
  return rule.include.length ? [] : items;
}

function resolveProfileSelectionPolicy(profileId) {
  const id = String(profileId || "").toUpperCase();
  const map = {
    GOVERNANCE_ASSURANCE: "SECURITY",
    MODERATION_SAFETY: "SECURITY",
    REALTIME_STREAMING: "STABILITY",
    CODE_AGENTIC: "STABILITY",
    REASONING_TEXT: "STABILITY",
  };
  return map[id] || "PRICE_PERF";
}

function resolveTimestamp(value) {
  if (!value) return null;
  const ts = Date.parse(String(value));
  return Number.isFinite(ts) ? ts : null;
}

function pickPreferredModel(snapshot, policy) {
  const candidates = Array.isArray(snapshot.availableModels) && snapshot.availableModels.length
    ? snapshot.availableModels.slice()
    : Array.isArray(snapshot.models)
      ? snapshot.models.slice()
      : [];
  if (!candidates.length) return "";
  const defaultModel = String(snapshot.defaultModel || "").trim();
  if (defaultModel && candidates.includes(defaultModel)) return defaultModel;
  const pinnedModelId = String(snapshot.pinnedModelId || "").trim();
  if (pinnedModelId && candidates.includes(pinnedModelId)) return pinnedModelId;
  const preferredCandidateModelId = String(snapshot.preferredCandidateModelId || "").trim();
  if (preferredCandidateModelId && candidates.includes(preferredCandidateModelId)) return preferredCandidateModelId;

  if (policy === "PRICE_PERF") {
    let best = "";
    let bestLatency = Infinity;
    candidates.forEach((model) => {
      const latency = snapshot.latencyByModel?.[model];
      if (Number.isFinite(latency) && latency < bestLatency) {
        bestLatency = latency;
        best = model;
      }
    });
    if (best) return best;
  }

  if (policy === "STABILITY" || policy === "SECURITY") {
    let best = "";
    let bestTs = Infinity;
    candidates.forEach((model) => {
      const ts = resolveTimestamp(snapshot.verifiedAtByModel?.[model]);
      if (Number.isFinite(ts) && ts < bestTs) {
        bestTs = ts;
        best = model;
      }
    });
    if (best) return best;
  }

  return candidates[0];
}

function pickDefaultSelection(providers, getSnapshot, policy, providerOrder) {
  if (!providers.length) return { provider: "", model: "" };
  const orderIndex = new Map((providerOrder || []).map((id, idx) => [id, idx]));
  let best = null;
  providers.forEach((providerId) => {
    const snapshot = getSnapshot(providerId);
    const model = pickPreferredModel(snapshot, policy);
    if (!model) return;
    let primary = 0;
    let secondary = 0;
    if (policy === "PRICE_PERF") {
      const latency = snapshot.latencyByModel?.[model];
      primary = Number.isFinite(latency) ? latency : 1e12;
      secondary = orderIndex.has(providerId) ? orderIndex.get(providerId) : 999;
    } else {
      primary = snapshot.pinnedModelId && model === snapshot.pinnedModelId ? 0 : 1;
      const ts = resolveTimestamp(snapshot.verifiedAtByModel?.[model]);
      secondary = Number.isFinite(ts) ? ts : 9e15;
    }
    const order = orderIndex.has(providerId) ? orderIndex.get(providerId) : 999;
    const candidate = { provider: providerId, model, primary, secondary, order };
    if (
      !best ||
      candidate.primary < best.primary ||
      (candidate.primary === best.primary && candidate.secondary < best.secondary) ||
      (candidate.primary === best.primary && candidate.secondary === best.secondary && candidate.order < best.order)
    ) {
      best = candidate;
    }
  });
  if (best) return { provider: best.provider, model: best.model };
  const fallbackProvider = providers[0];
  return { provider: fallbackProvider, model: pickPreferredModel(getSnapshot(fallbackProvider), policy) };
}

function resolveChatProviderMap() {
  if (state.chatProviderRegistry && state.chatProviderRegistry.providers) {
    return state.chatProviderRegistry.providers;
  }
  const fallback = {};
  Object.values(CHAT_MODEL_GROUPS).forEach((group) => {
    (group.provider_order || []).forEach((provider) => {
      if (!fallback[provider]) {
        fallback[provider] = { enabled: true, models: [], defaultModel: "" };
      }
    });
  });
  return fallback;
}

function renderChatModelSelectors() {
  const profileEl = $("#chat-profile");
  const providerEl = $("#chat-provider");
  const modelEl = $("#chat-model");
  if (!profileEl || !providerEl || !modelEl) return;

  const registryProfiles = Array.isArray(state.chatProfileOptions) ? state.chatProfileOptions : [];
  const baseProfiles = registryProfiles.length ? registryProfiles : Object.keys(CHAT_MODEL_GROUPS);
  const profiles = dedupeList([...baseProfiles, ...Object.keys(CHAT_MODEL_GROUPS)]);
  profileEl.innerHTML = profiles
    .map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(resolveChatProfileLabel(key))}</option>`)
    .join("");
  const activeProfile = profiles.includes(state.chatProfile) ? state.chatProfile : profiles[0];
  state.chatProfile = activeProfile || "FAST_TEXT";
  profileEl.value = state.chatProfile;

  const providerMap = resolveChatProviderMap();
  const group = CHAT_MODEL_GROUPS[state.chatProfile] || CHAT_MODEL_GROUPS[profiles[0]] || {};
  const providerOrder = group.provider_order || [];
  const classProviderMap = state.chatProviderClassMap || {};
  const classProviders = classProviderMap[state.chatProfile] || {};
  const classProviderKeys = Object.keys(classProviders || {});
  const classHasProviderData = classProviderKeys.length > 0;
  const classMetaMap = state.chatProviderClassMeta || {};
  const classMeta = classMetaMap[state.chatProfile] || {};
  const providerSnapshots = {};

  const buildProviderSnapshot = (providerId) => {
    const modelInfo = providerMap[providerId] || {};
    const classModels = Array.isArray(classProviders?.[providerId])
      ? classProviders[providerId].slice()
      : [];
    const policyModels = Array.isArray(modelInfo.models) ? modelInfo.models.slice() : [];
    let models = dedupeList([...classModels, ...policyModels]);
    models = filterModelsForProfile(state.chatProfile, models);
    const defaultModel = modelInfo.defaultModel;
    if (defaultModel && models.includes(defaultModel) && models[0] !== defaultModel) {
      models = [defaultModel, ...models.filter((m) => m !== defaultModel)];
    }
    const providerMeta = classMeta[providerId] || {};
    const eligibleModels = Array.isArray(providerMeta.eligible) ? providerMeta.eligible.slice() : [];
    const eligibleSet = new Set(eligibleModels);
    const hasVerificationMeta =
      eligibleModels.length || (providerMeta.status && Object.keys(providerMeta.status).length);
    const verifiedModels = hasVerificationMeta ? models.filter((m) => eligibleSet.has(m)) : [];
    const availableModels = verifiedModels.length ? verifiedModels : models;
    const latencyByModel = {};
    const verifiedAtByModel = {};
    const status = providerMeta.status || {};
    Object.keys(status).forEach((modelId) => {
      const item = status[modelId] || {};
      if (Number.isFinite(item.latency_ms_p95)) latencyByModel[modelId] = Number(item.latency_ms_p95);
      if (item.verified_at) verifiedAtByModel[modelId] = String(item.verified_at);
    });
    return {
      models,
      verifiedModels,
      hasVerificationMeta,
      availableModels,
      eligibleSet,
      defaultModel: defaultModel || "",
      pinnedModelId: providerMeta.pinned_model_id || "",
      preferredCandidateModelId: providerMeta.preferred_candidate_model_id || "",
      latencyByModel,
      verifiedAtByModel,
      statusByModel: status,
    };
  };

  const getSnapshot = (providerId) => {
    if (!providerSnapshots[providerId]) {
      providerSnapshots[providerId] = buildProviderSnapshot(providerId);
    }
    return providerSnapshots[providerId];
  };
  let providers = providerOrder.filter((p) => providerMap[p] && providerMap[p].enabled !== false);
  if (classHasProviderData) {
    providers = providers.filter((p) => classProviderKeys.includes(p));
  } else {
    providers = [];
  }
  if (!providers.length) {
    providers = Object.keys(providerMap).filter((p) => providerMap[p]?.enabled !== false);
    if (classHasProviderData) {
      providers = providers.filter((p) => classProviderKeys.includes(p));
    }
  }
  if (!providers.length && !classHasProviderData) {
    providerEl.innerHTML = `<option value="">${escapeHtml(t("select.none"))}</option>`;
    modelEl.innerHTML = `<option value="">${escapeHtml(t("select.no_verified_model"))}</option>`;
    state.chatProvider = "";
    state.chatModel = "";
    return;
  }

  if (!providers.length) {
    providerEl.innerHTML = `<option value="">${escapeHtml(t("select.none"))}</option>`;
    modelEl.innerHTML = `<option value="">(no model)</option>`;
    state.chatProvider = "";
    state.chatModel = "";
    return;
  }

  providers = providers.filter((p) => getSnapshot(p).models.length > 0);
  if (!providers.length) {
    providerEl.innerHTML = `<option value="">${escapeHtml(t("select.none"))}</option>`;
    modelEl.innerHTML = `<option value="">${escapeHtml(t("select.no_verified_model"))}</option>`;
    state.chatProvider = "";
    state.chatModel = "";
    return;
  }

  const selectionPolicy = resolveProfileSelectionPolicy(state.chatProfile);
  const recommended = pickDefaultSelection(providers, getSnapshot, selectionPolicy, providerOrder);
  state.chatProvider = providers.includes(state.chatProvider) ? state.chatProvider : recommended.provider || providers[0];
  providerEl.innerHTML = providers.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("");
  providerEl.value = state.chatProvider;

  const snapshot = getSnapshot(state.chatProvider);
  const models = snapshot.models.slice();
  const hasVerificationMeta = snapshot.hasVerificationMeta;
  const eligibleSet = snapshot.eligibleSet || new Set();
  const recommendedModel = recommended.provider === state.chatProvider ? recommended.model : "";
  const displayModels = models;

  if (displayModels.length) {
    if (displayModels.includes(state.chatModel)) {
      state.chatModel = state.chatModel;
    } else if (recommendedModel && displayModels.includes(recommendedModel)) {
      state.chatModel = recommendedModel;
    } else {
      state.chatModel = displayModels[0] || "";
    }
  } else if (hasVerificationMeta) {
    state.chatModel = "";
  } else {
    state.chatModel = "";
  }

  const options = [];
  if (!displayModels.length) {
    options.push(`<option value="" disabled selected>${escapeHtml(t("select.no_verified_model"))}</option>`);
  }
  displayModels.forEach((m) => {
    const statusByModel = snapshot.statusByModel || {};
    const meta = statusByModel && statusByModel[m] ? statusByModel[m] : {};
    const metaStage = String(meta.stage || "").toLowerCase();
    const metaProbe = String(meta.probe_status || "").toLowerCase();
    const verified = hasVerificationMeta
      ? eligibleSet.has(m) || metaStage === "verified" || metaProbe === "ok"
      : true;
    const showAsUnverified = hasVerificationMeta && !verified;
    const label = showAsUnverified
      ? `${m} (${t(isAllowlistWarn() ? "chat.model.skeleton" : "chat.model.unverified")})`
      : m;
    options.push(
      `<option value="${escapeHtml(m)}" ${
        showAsUnverified ? 'data-unverified="1" style="color:#6b7a7a;opacity:0.6"' : ""
      }>${escapeHtml(label)}</option>`
    );
  });
  modelEl.innerHTML = options.join("");
  modelEl.value = state.chatModel;
  saveChatSelection();
  renderChatAllowlistHint("chat-model-verified-hint");
}

function resolveSuggestProfileDefault(kind) {
  const key = String(kind || "").toUpperCase();
  const map = {
    SEED: "REASONING_TEXT",
    CONSULT: "BALANCED_TEXT",
    THEME: "BALANCED_TEXT",
    SUBTHEME: "BALANCED_TEXT",
  };
  return map[key] || "BALANCED_TEXT";
}

function renderAiSuggestModelSelectors(profileDefault) {
  const profileEl = $("#ai-suggest-profile");
  const providerEl = $("#ai-suggest-provider");
  const modelEl = $("#ai-suggest-model");
  const wrapEl = $("#ai-suggest-selects");
  if (!profileEl || !providerEl || !modelEl || !wrapEl) return { profile: "", provider: "", model: "" };

  wrapEl.style.display = "grid";
  const registryProfiles = Array.isArray(state.chatProfileOptions) ? state.chatProfileOptions : [];
  const baseProfiles = registryProfiles.length ? registryProfiles : Object.keys(CHAT_MODEL_GROUPS);
  const profiles = dedupeList([...baseProfiles, ...Object.keys(CHAT_MODEL_GROUPS)]);
  const preferredProfile = profiles.includes(profileDefault) ? profileDefault : profiles[0];
  state.aiSuggestProfile = profiles.includes(state.aiSuggestProfile)
    ? state.aiSuggestProfile
    : preferredProfile || "BALANCED_TEXT";
  profileEl.innerHTML = profiles
    .map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(resolveChatProfileLabel(key))}</option>`)
    .join("");
  profileEl.value = state.aiSuggestProfile;

  const providerMap = resolveChatProviderMap();
  const group = CHAT_MODEL_GROUPS[state.aiSuggestProfile] || CHAT_MODEL_GROUPS[profiles[0]] || {};
  const providerOrder = group.provider_order || [];
  const classProviderMap = state.chatProviderClassMap || {};
  const classProviders = classProviderMap[state.aiSuggestProfile] || {};
  const classProviderKeys = Object.keys(classProviders || {});
  const classHasProviderData = classProviderKeys.length > 0;
  const classMetaMap = state.chatProviderClassMeta || {};
  const classMeta = classMetaMap[state.aiSuggestProfile] || {};
  const providerSnapshots = {};

  const buildProviderSnapshot = (providerId) => {
    const modelInfo = providerMap[providerId] || {};
    const classModels = Array.isArray(classProviders?.[providerId])
      ? classProviders[providerId].slice()
      : [];
    const policyModels = Array.isArray(modelInfo.models) ? modelInfo.models.slice() : [];
    let models = dedupeList([...classModels, ...policyModels]);
    models = filterModelsForProfile(state.aiSuggestProfile, models);
    const defaultModel = modelInfo.defaultModel;
    if (defaultModel && models.includes(defaultModel) && models[0] !== defaultModel) {
      models = [defaultModel, ...models.filter((m) => m !== defaultModel)];
    }
    const providerMeta = classMeta[providerId] || {};
    const eligibleModels = Array.isArray(providerMeta.eligible) ? providerMeta.eligible.slice() : [];
    const eligibleSet = new Set(eligibleModels);
    const hasVerificationMeta =
      eligibleModels.length || (providerMeta.status && Object.keys(providerMeta.status).length);
    const verifiedModels = hasVerificationMeta ? models.filter((m) => eligibleSet.has(m)) : [];
    const availableModels = verifiedModels.length ? verifiedModels : models;
    const latencyByModel = {};
    const verifiedAtByModel = {};
    const status = providerMeta.status || {};
    Object.keys(status).forEach((modelId) => {
      const item = status[modelId] || {};
      if (Number.isFinite(item.latency_ms_p95)) latencyByModel[modelId] = Number(item.latency_ms_p95);
      if (item.verified_at) verifiedAtByModel[modelId] = String(item.verified_at);
    });
    return {
      models,
      verifiedModels,
      hasVerificationMeta,
      availableModels,
      eligibleSet,
      defaultModel: defaultModel || "",
      pinnedModelId: providerMeta.pinned_model_id || "",
      preferredCandidateModelId: providerMeta.preferred_candidate_model_id || "",
      latencyByModel,
      verifiedAtByModel,
      statusByModel: status,
    };
  };

  const getSnapshot = (providerId) => {
    if (!providerSnapshots[providerId]) {
      providerSnapshots[providerId] = buildProviderSnapshot(providerId);
    }
    return providerSnapshots[providerId];
  };
  let providers = providerOrder.filter((p) => providerMap[p] && providerMap[p].enabled !== false);
  if (classHasProviderData) {
    providers = providers.filter((p) => classProviderKeys.includes(p));
  } else {
    providers = [];
  }
  if (!providers.length) {
    providers = Object.keys(providerMap).filter((p) => providerMap[p]?.enabled !== false);
    if (classHasProviderData) {
      providers = providers.filter((p) => classProviderKeys.includes(p));
    }
  }
  providers = providers.filter((p) => getSnapshot(p).models.length > 0);
  if (!providers.length) {
    providerEl.innerHTML = `<option value="">${escapeHtml(t("select.none"))}</option>`;
    modelEl.innerHTML = `<option value="">${escapeHtml(t("select.no_verified_model"))}</option>`;
    state.aiSuggestProvider = "";
    state.aiSuggestModel = "";
    return { profile: state.aiSuggestProfile, provider: "", model: "" };
  }

  const selectionPolicy = resolveProfileSelectionPolicy(state.aiSuggestProfile);
  const recommended = pickDefaultSelection(providers, getSnapshot, selectionPolicy, providerOrder);
  state.aiSuggestProvider = providers.includes(state.aiSuggestProvider)
    ? state.aiSuggestProvider
    : recommended.provider || providers[0];
  providerEl.innerHTML = providers.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("");
  providerEl.value = state.aiSuggestProvider;

  const snapshot = getSnapshot(state.aiSuggestProvider);
  const models = snapshot.models.slice();
  const hasVerificationMeta = snapshot.hasVerificationMeta;
  const eligibleSet = snapshot.eligibleSet || new Set();
  const recommendedModel = recommended.provider === state.aiSuggestProvider ? recommended.model : "";

  const displayModels = models;
  if (displayModels.length) {
    if (displayModels.includes(state.aiSuggestModel)) {
      state.aiSuggestModel = state.aiSuggestModel;
    } else if (recommendedModel && displayModels.includes(recommendedModel)) {
      state.aiSuggestModel = recommendedModel;
    } else {
      state.aiSuggestModel = displayModels[0] || "";
    }
  } else if (hasVerificationMeta) {
    state.aiSuggestModel = "";
  } else {
    state.aiSuggestModel = "";
  }

  const options = [];
  if (!displayModels.length) {
    options.push(`<option value="" disabled selected>${escapeHtml(t("select.no_verified_model"))}</option>`);
  }
  displayModels.forEach((m) => {
    const statusByModel = snapshot.statusByModel || {};
    const meta = statusByModel && statusByModel[m] ? statusByModel[m] : {};
    const metaStage = String(meta.stage || "").toLowerCase();
    const metaProbe = String(meta.probe_status || "").toLowerCase();
    const verified = hasVerificationMeta
      ? eligibleSet.has(m) || metaStage === "verified" || metaProbe === "ok"
      : true;
    const showAsUnverified = hasVerificationMeta && !verified;
    const label = showAsUnverified
      ? `${m} (${t(isAllowlistWarn() ? "chat.model.skeleton" : "chat.model.unverified")})`
      : m;
    options.push(
      `<option value="${escapeHtml(m)}" ${
        showAsUnverified ? 'data-unverified="1" style="color:#6b7a7a;opacity:0.6"' : ""
      }>${escapeHtml(label)}</option>`
    );
  });
  modelEl.innerHTML = options.join("");
  modelEl.value = state.aiSuggestModel;
  renderChatAllowlistHint("ai-suggest-verified-hint");

  profileEl.onchange = () => {
    state.aiSuggestProfile = profileEl.value;
    state.aiSuggestProvider = "";
    state.aiSuggestModel = "";
    renderAiSuggestModelSelectors(state.aiSuggestProfile);
  };
  providerEl.onchange = () => {
    state.aiSuggestProvider = providerEl.value;
    state.aiSuggestModel = "";
    renderAiSuggestModelSelectors(state.aiSuggestProfile);
  };
  modelEl.onchange = () => {
    state.aiSuggestModel = modelEl.value;
  };

  return { profile: state.aiSuggestProfile, provider: state.aiSuggestProvider, model: state.aiSuggestModel };
}

async function ensureChatProviderRegistryLoaded() {
  if (state.chatProviderRegistry) return;
  await refreshChatModelSelectors();
}

async function refreshChatModelSelectors() {
  const profileEl = $("#chat-profile");
  const providerEl = $("#chat-provider");
  const modelEl = $("#chat-model");
  if (!profileEl || !providerEl || !modelEl) return;
  profileEl.disabled = true;
  providerEl.disabled = true;
  modelEl.disabled = true;
  try {
    let classPayload = await fetchOptionalJson(chatClassRegistryWorkspacePath);
    if (!classPayload) classPayload = await fetchOptionalJson(chatClassRegistryPath);
    let providerMapPayload = await fetchOptionalJson(chatProviderMapWorkspacePath);
    if (!providerMapPayload) providerMapPayload = await fetchOptionalJson(chatProviderMapPath);
    const probeCatalogPayload = await fetchOptionalJson(chatProbeCatalogPath);
    const probeStatePayload = await fetchOptionalJson(chatProbeStatePath);
    const probeSummary = probeCatalogPayload?.summary || probeCatalogPayload?.data?.summary || null;
    if (probeSummary?.allowlist_probe) {
      state.chatAllowlistSummary = probeSummary.allowlist_probe;
    } else {
      state.chatAllowlistSummary = null;
    }
    const probeProviderMap =
      probeCatalogPayload?.provider_map ||
      probeCatalogPayload?.data?.provider_map ||
      null;
    if (probeProviderMap && typeof probeProviderMap === "object" && probeProviderMap.classes) {
      providerMapPayload = {
        path: probeCatalogPayload.path || chatProbeCatalogPath,
        data: probeProviderMap,
      };
    }
    providerMapPayload = mergeProviderMapWithProbeState(providerMapPayload, probeStatePayload);
    const registryPayload = await fetchOptionalJson(chatProvidersRegistryPath);
    const allowPayload = await fetchOptionalJson(chatProviderAllowlistPath);
    let policyPayload = await fetchOptionalJson(chatProviderPolicyWorkspacePath);
    if (!policyPayload) {
      policyPayload = await fetchOptionalJson(chatProviderPolicyRepoPath);
    }
    const profileOptions = buildChatProfileOptions(classPayload);
    state.chatProfileOptions = profileOptions;
    state.chatProviderClassMap = buildChatProviderClassMap(providerMapPayload);
    const allowlistByClass = buildAllowlistModelStatus(allowPayload);
    state.chatProviderClassMeta = buildChatProviderClassMeta(providerMapPayload, allowlistByClass);
    const providerMap = buildChatProviderMap(registryPayload, policyPayload);
    const allowlist = buildProviderAllowlist(allowPayload);
    Object.keys(providerMap).forEach((id) => {
      providerMap[id].enabled = providerMap[id].enabled !== false && allowlist.isAllowed(id);
    });
    if (!Object.keys(providerMap).length) {
      state.chatProviderRegistryError = "NO_PROVIDER_REGISTRY";
    } else {
      state.chatProviderRegistryError = null;
    }
    state.chatProviderRegistry = {
      providers: providerMap,
      loaded_at: new Date().toISOString(),
      registry_path: registryPayload?.path || chatProvidersRegistryPath,
      policy_path: policyPayload?.path || chatProviderPolicyWorkspacePath,
      allowlist_path: allowPayload?.path || chatProviderAllowlistPath,
    };
    renderChatModelSelectors();
  } catch (err) {
    state.chatProviderRegistryError = "PROVIDER_SELECTOR_RENDER_FAILED";
    console.error("refreshChatModelSelectors failed", err);
  } finally {
    profileEl.disabled = false;
    providerEl.disabled = false;
    modelEl.disabled = false;
  }
}

let chatSelectorsInitialized = false;
function initChatModelSelectors() {
  if (chatSelectorsInitialized) return;
  const profileEl = $("#chat-profile");
  const providerEl = $("#chat-provider");
  const modelEl = $("#chat-model");
  if (!profileEl || !providerEl || !modelEl) return;
  chatSelectorsInitialized = true;

  restoreChatSelection();

  profileEl.addEventListener("change", () => {
    state.chatProfile = profileEl.value;
    renderChatModelSelectors();
  });
  providerEl.addEventListener("change", () => {
    state.chatProvider = providerEl.value;
    renderChatModelSelectors();
  });
  modelEl.addEventListener("change", () => {
    state.chatModel = modelEl.value;
  });

  renderChatModelSelectors();
  refreshChatModelSelectors();
}

function buildChatAutoTags() {
  const tags = [];
  if (state.chatProfile) tags.push(`profile:${state.chatProfile}`);
  if (state.chatProvider) tags.push(`provider:${state.chatProvider}`);
  if (state.chatModel) tags.push(`model:${state.chatModel}`);
  tags.push("role:user");
  return tags;
}

function clearNoteComposer() {
  const titleEl = $("#note-title");
  if (titleEl) titleEl.value = "";
  const bodyEl = $("#note-body");
  if (bodyEl) bodyEl.value = "";
  const tagsEl = $("#note-tags");
  if (tagsEl) tagsEl.value = "";
  const linkId = $("#note-link-id");
  if (linkId) linkId.value = "";
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

async function refreshTimeline({ run = false } = {}) {
  state.timelinePending = true;
  renderTimelineDashboard();
  try {
    const url = `${endpoints.timeline}?run=${run ? "true" : "false"}`;
    state.timeline = await fetchJson(url);
    state.timelineError = "";
  } catch (err) {
    state.timelineError = formatError(err);
    if (run) {
      showToast(t("toast.refresh_failed", { name: "timeline", error: state.timelineError }), "warn");
    }
  } finally {
    state.timelinePending = false;
    renderTimelineDashboard();
  }
}

function multiRepoStatusUrl() {
  const qs = new URLSearchParams();
  if (state.multiRepoCriticalOnly) qs.set("critical_only", "true");
  const query = qs.toString();
  return query ? `${endpoints.multiRepoStatus}?${query}` : endpoints.multiRepoStatus;
}

async function refreshMultiRepoStatus({ silent = false } = {}) {
  const url = multiRepoStatusUrl();
  state.multiRepoStatusPending = true;
  state.multiRepoStatusError = "";
  if (!silent) renderOverview();
  try {
    state.multiRepoStatus = await fetchJson(url);
    state.multiRepoStatusError = "";
  } catch (err) {
    state.multiRepoStatusError = formatError(err);
    if (!silent) {
      showToast(t("overview.multi_repo.error", { error: state.multiRepoStatusError }), "warn");
    }
    throw err;
  } finally {
    state.multiRepoStatusPending = false;
    if (!silent) renderOverview();
  }
}

async function refreshOverview() {
  const [overviewRes, timelineRes, multiRepoRes] = await Promise.allSettled([
    fetchJson(endpoints.overview),
    fetchJson(endpoints.timeline),
    refreshMultiRepoStatus({ silent: true }),
  ]);
  if (overviewRes.status === "rejected") throw overviewRes.reason;
  state.overview = overviewRes.value;
  if (timelineRes.status === "fulfilled") {
    state.timeline = timelineRes.value;
    state.timelineError = "";
  } else {
    state.timelineError = formatError(timelineRes.reason);
  }
  if (multiRepoRes.status === "fulfilled") {
    state.multiRepoStatusError = "";
  } else {
    state.multiRepoStatusError = formatError(multiRepoRes.reason);
  }
  renderOverview();
}

async function refreshNorthStar() {
  const [northStar, criteriaPacks, mechanismsRegistry, mechanismsSuggestions, mechanismsHistory, flow2Status] = await Promise.all([
    fetchJson(endpoints.northStar),
    fetchNorthStarCriteriaPacks(),
    fetchNorthStarMechanismsRegistry(),
    fetchNorthStarMechanismsSuggestions(),
    fetchNorthStarMechanismsHistory(),
    fetchNorthStarFlow2Status(),
  ]);
  state.northStar = northStar;
  if (criteriaPacks) state.northStarCriteriaPacks = criteriaPacks;
  if (mechanismsRegistry) state.northStarMechanismsRegistry = mechanismsRegistry;
  if (mechanismsSuggestions) state.northStarMechanismsSuggestions = mechanismsSuggestions;
  if (mechanismsHistory) state.northStarMechanismsHistory = mechanismsHistory;
  state.northStarFlow2Status = flow2Status || null;
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
  scheduleRefresh("intake_compat", refreshIntakeCompatSummary, 160);
  await refreshIntakePurposeIndex();
  await refreshIntakePurposeReport();
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
  renderIntakePurposeMeta();
  renderIntakePurposeReport();
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
  await refreshExtensionUsage();
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
  updateGithubOpsFreshnessIndicator();
  scheduleGithubOpsAutoPoll("refresh_jobs");
}

function computeGithubOpsPollIntervalMs() {
  const summary = (state.jobs || {}).summary || {};
  const running = Number(summary.running || 0);
  const queued = Number(summary.queued || 0);
  if (state.activeTab === "jobs" || running > 0 || queued > 0) return GITHUB_OPS_POLL_ACTIVE_MS;
  return GITHUB_OPS_POLL_IDLE_MS;
}

function shouldAutoPollGithubOps() {
  if (state.githubOpsPollInFlight) return false;
  const summary = (state.jobs || {}).summary || {};
  const running = Number(summary.running || 0);
  const queued = Number(summary.queued || 0);
  const freshness = getGithubOpsFreshness();
  const stale = freshness.status !== "fresh";
  return state.activeTab === "jobs" || running > 0 || queued > 0 || stale;
}

function scheduleGithubOpsAutoPoll(reason = "") {
  if (state.githubOpsAutoPollTimer) {
    clearTimeout(state.githubOpsAutoPollTimer);
  }
  const delay = computeGithubOpsPollIntervalMs();
  state.githubOpsAutoPollTimer = setTimeout(() => runGithubOpsAutoPoll(reason), delay);
}

async function runGithubOpsAutoPoll(reason = "") {
  if (!shouldAutoPollGithubOps()) {
    scheduleGithubOpsAutoPoll("idle");
    return;
  }
  state.githubOpsPollInFlight = true;
  try {
    const { data } = await postOpInternal("github-ops-job-poll", { max: 3 });
    if (data && isOpJobInProgress(data)) {
      // Async job started; rely on /api/op_job polling elsewhere.
    }
    state.githubOpsPollFailures = 0;
    scheduleRefresh("jobs", refreshJobs, 180);
  } catch (_) {
    state.githubOpsPollFailures = (state.githubOpsPollFailures || 0) + 1;
  } finally {
    state.githubOpsPollInFlight = false;
    const base = computeGithubOpsPollIntervalMs();
    const backoff = Math.min(GITHUB_OPS_POLL_IDLE_MS * 3, base * (1 + state.githubOpsPollFailures));
    if (state.githubOpsAutoPollTimer) clearTimeout(state.githubOpsAutoPollTimer);
    state.githubOpsAutoPollTimer = setTimeout(() => runGithubOpsAutoPoll(reason), backoff);
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
  if (state.chatStreamNoteId) {
    const hasStreamNote = items.some((item) => String(item.note_id || "") === String(state.chatStreamNoteId || ""));
    if (!hasStreamNote) {
      stopChatStreaming();
    } else {
      state.chatStreamItems = items;
    }
  }
  maybeResolveChatPending(items);
  renderNotes(items);
  setNotesView(state.notesView);
  if (!state.chatPending) {
    maybeStartStreamingLatestAssistant(items);
  }
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
  try {
    const memPayload = await fetchOptionalJson(memoryHealthReportPath);
    state.memoryHealth = unwrap(memPayload || {}) || null;
    setMemoryStatus(state.memoryHealth);
  } catch (_) {
    setMemoryStatus(null);
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
  if (tab === "timeline") return refreshTimeline();
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
  if (tab === "search") return refreshSearchContext();
  if (tab === "planner-chat") return refreshNotes();
  if (tab === "evidence") return refreshEvidence();
}

async function refreshAll() {
  await refreshWsMeta();

  const tasks = [
    ["overview", refreshOverview],
    ["timeline", refreshTimeline],
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
    ["search_index", refreshSearchIndexStatus],
    ["search_capabilities", refreshSearchCapabilities],
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
  const opName = String(op || "").trim();
  if (opName === "planner-chat-send" || opName === "planner-chat-send-llm") {
    return Promise.resolve(true);
  }
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
    "extensions-usage-refresh",
    "settings-refresh",
    "settings-save",
    "settings-clear",
    "run-card-save",
    "run-card-refresh",
    "multi-repo-refresh",
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
  const multiRepoCriticalOnly = $("#multi-repo-critical-only");
  if (multiRepoCriticalOnly) multiRepoCriticalOnly.disabled = disabled;
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
    if (
      !status.includes("FAIL") &&
      (opName === "ui-snapshot-bundle" || String(data.op || "").trim() === "ui-snapshot-bundle")
    ) {
      prefillNoteForSnapshot(data);
    }
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
  const confirmBypassOps = new Set([
    "planner-chat-send",
    "planner-chat-send-llm",
    "north-star-theme-seed",
    "north-star-theme-consult",
    "north-star-theme-suggestion-apply",
  ]);
  if (!confirmBypassOps.has(opName)) {
    const ok = await confirmAction(op, args);
    if (!ok) return null;
  }
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
      if (effectiveOp === "ui-snapshot-bundle" && !reused) {
        showToast(t("snapshot.started", { id: jobId || "-" }), "ok");
      } else {
        showToast(
          t(reused ? "job.already_running" : "job.started", { op: effectiveOp, id: jobId || "-" }),
          "warn"
        );
      }
      if (jobId) markOpJobInProgress(effectiveOp, jobId);
      pollOpJob(jobId, data.poll_url || "", effectiveOp);
      return data;
    }
    const status = String(data?.status || "UNKNOWN").toUpperCase();
    const toastKind = status.includes("FAIL") ? "fail" : status.includes("WARN") ? "warn" : "ok";
    showToast(t("job.done", { op, status: data.status || "UNKNOWN" }), toastKind);
    if (opName === "ui-snapshot-bundle") {
      prefillNoteForSnapshot(data);
      return data;
    }
    if (op === "planner-chat-send" || op === "planner-chat-send-llm") {
      clearNoteComposer();
      await refreshNotes();
    } else {
      await refreshAll();
    }
  } catch (err) {
    const errorText = formatError(err);
    showToast(t("toast.op_failed", { error: errorText }), "fail");
    return {
      status: "FAIL",
      op: opName || op,
      error: errorText,
      error_code: "UI_POST_OP_EXCEPTION",
    };
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

  setupNorthStarCatalogControls();
  renderPlannerChatSuggestions();

  $("#refresh-all").addEventListener("click", () => {
    refreshAll();
    refreshEvidence();
  });
  const multiRepoRefresh = $("#multi-repo-refresh");
  if (multiRepoRefresh) {
    multiRepoRefresh.addEventListener("click", () => refreshMultiRepoStatus());
  }
  const multiRepoCriticalOnly = $("#multi-repo-critical-only");
  if (multiRepoCriticalOnly) {
    multiRepoCriticalOnly.checked = Boolean(state.multiRepoCriticalOnly);
    multiRepoCriticalOnly.addEventListener("change", (event) => {
      state.multiRepoCriticalOnly = Boolean(event.target && event.target.checked);
      refreshMultiRepoStatus();
    });
  }
  const timelineRefresh = $("#timeline-refresh");
  if (timelineRefresh) {
    timelineRefresh.addEventListener("click", () => refreshTimeline({ run: true }));
  }

  const searchInput = $("#search-query");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.searchQuery = searchInput.value || "";
      renderSearchPanel();
    });
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") runSearch();
    });
  }
  const globalSearchInput = $("#global-search-query");
  if (globalSearchInput) {
    globalSearchInput.addEventListener("input", () => {
      state.searchQuery = globalSearchInput.value || "";
      renderSearchPanel();
    });
    globalSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        state.searchScope = "ssot";
        const scopeSelect = $("#search-scope");
        if (scopeSelect) scopeSelect.value = state.searchScope;
        refreshSearchIndexStatus();
        runSearch().then(() => navigateToTab("search"));
      }
    });
  }
  const globalSearchRun = $("#global-search-run");
  if (globalSearchRun) {
    globalSearchRun.addEventListener("click", () => {
      state.searchScope = "ssot";
      const scopeSelect = $("#search-scope");
      if (scopeSelect) scopeSelect.value = state.searchScope;
      refreshSearchIndexStatus();
      runSearch().then(() => navigateToTab("search"));
    });
  }
  const searchScope = $("#search-scope");
  if (searchScope) {
    searchScope.addEventListener("change", () => {
      state.searchScope = normalizeSearchScope(searchScope.value);
      refreshSearchContext();
      renderSearchPanel();
    });
  }
  const searchMode = $("#search-mode");
  if (searchMode) {
    searchMode.addEventListener("change", () => {
      state.searchMode = normalizeSearchMode(searchMode.value);
      renderSearchPanel();
    });
  }
  const searchRun = $("#search-run");
  if (searchRun) {
    searchRun.addEventListener("click", () => runSearch());
  }
  const searchRebuild = $("#search-rebuild");
  if (searchRebuild) {
    searchRebuild.addEventListener("click", () => updateSearchIndex({ rebuild: true }));
  }
  const searchResults = $("#search-results");
  if (searchResults) {
    searchResults.addEventListener("click", (event) => {
      const target = event.target;
      if (!target || !target.dataset) return;
      const raw = target.dataset.searchOpen;
      if (!raw) return;
      event.preventDefault();
      openEvidencePreview(raw);
    });
  }
  refreshSearchContext();
  scheduleSearchIndexAutoRefresh();

  const snapshotTopbar = $("#snapshot-page");
  if (snapshotTopbar) {
    snapshotTopbar.addEventListener("click", () => {
      state.snapshotContext = {
        activeTab: state.activeTab || "overview",
        hash: String(window.location.hash || ""),
      };
      postOp("ui-snapshot-bundle");
    });
  }

  const exportMechanismsBtn = $("#export-mechanisms");
  if (exportMechanismsBtn) {
    exportMechanismsBtn.addEventListener("click", (event) => {
      event.preventDefault();
      exportMechanismsCatalog();
    });
  }

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
  const purposeGenerateBtn = $("#intake-purpose-generate");
  if (purposeGenerateBtn) {
    purposeGenerateBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await generateIntakePurposeAll();
    });
  }
  const purposeGenerateSelectedBtn = $("#intake-purpose-generate-selected");
  if (purposeGenerateSelectedBtn) {
    purposeGenerateSelectedBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await generateIntakePurposeSelected();
    });
  }
  const purposeReportBtn = $("#intake-purpose-report-open");
  if (purposeReportBtn) {
    purposeReportBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      await openEvidencePreview(intakePurposeReportMdPath);
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
  const usageRefresh = $("#extensions-usage-refresh");
  if (usageRefresh) {
    usageRefresh.addEventListener("click", () => refreshExtensionUsage());
  }
  const usageSearch = $("#extensions-usage-search");
  if (usageSearch) {
    usageSearch.addEventListener("input", () => {
      state.extensionUsageFilters.search = usageSearch.value || "";
      renderExtensionUsage();
    });
  }
  const usageExt = $("#extensions-usage-extension");
  if (usageExt) {
    usageExt.addEventListener("change", () => {
      state.extensionUsageFilters.extension = usageExt.value || "";
      renderExtensionUsage();
    });
  }
  const usageKind = $("#extensions-usage-kind");
  if (usageKind) {
    usageKind.addEventListener("change", () => {
      state.extensionUsageFilters.kind = usageKind.value || "";
      renderExtensionUsage();
    });
  }

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
  const threadNew = $("#planner-thread-new");
  if (threadNew) {
    threadNew.addEventListener("click", () => {
      const id = `chat-${new Date().toISOString().replace(/[:.]/g, "").toLowerCase()}`;
      state.plannerThread = id;
      const input = $("#planner-thread");
      if (input) input.value = id;
      refreshNotes();
    });
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

  const notesRefresh = $("#notes-refresh");
  if (notesRefresh) notesRefresh.addEventListener("click", () => refreshNotes());
  const notesViewChat = $("#notes-view-chat");
  if (notesViewChat) {
    notesViewChat.addEventListener("click", () => {
      setNotesView("chat");
      const items = Array.isArray(state.notes?.items) ? state.notes.items : [];
      renderNotes(items);
    });
  }
  const notesViewList = $("#notes-view-list");
  if (notesViewList) {
    notesViewList.addEventListener("click", () => {
      setNotesView("list");
      const items = Array.isArray(state.notes?.items) ? state.notes.items : [];
      renderNotes(items);
    });
  }
  const notesSearch = $("#notes-search");
  if (notesSearch) {
    notesSearch.addEventListener("input", () => {
      const items = Array.isArray(state.notes?.items) ? state.notes.items : [];
      renderNotes(items);
    });
  }
  const notesTagFilter = $("#notes-tag-filter");
  if (notesTagFilter) {
    notesTagFilter.addEventListener("input", () => {
      const items = Array.isArray(state.notes?.items) ? state.notes.items : [];
      renderNotes(items);
    });
  }

  const noteLinkAdd = $("#note-link-add");
  if (noteLinkAdd) {
    noteLinkAdd.addEventListener("click", () => {
      const kindEl = $("#note-link-kind");
      const targetEl = $("#note-link-id");
      const kind = kindEl ? kindEl.value.trim() : "";
      const target = targetEl ? targetEl.value.trim() : "";
      if (!kind || !target) {
        showToast(t("toast.link_kind_required"), "warn");
        return;
      }
      state.noteLinks.push({ kind, id_or_path: target });
      if (targetEl) targetEl.value = "";
      renderNoteLinks();
    });
  }

  const noteLinkClear = $("#note-link-clear");
  if (noteLinkClear) {
    noteLinkClear.addEventListener("click", () => {
      state.noteLinks = [];
      renderNoteLinks();
    });
  }

  $("#note-save").addEventListener("click", async () => {
    const titleEl = $("#note-title");
    const bodyEl = $("#note-body");
    const tagsEl = $("#note-tags");
    let title = titleEl ? titleEl.value.trim() : "";
    const body = bodyEl ? bodyEl.value || "" : "";
    const tags = parseTagsInput(tagsEl ? tagsEl.value : "");
    if (!title && !body.trim()) {
      showToast(t("toast.title_or_body_required"), "warn");
      return;
    }
    if (!title) {
      const firstLine = body.trim().split(/\r?\n/)[0] || "";
      title = firstLine.slice(0, 80) || t("notes.untitled");
    }
    const threadInput = $("#planner-thread");
    const threadRaw = threadInput ? threadInput.value.trim().toLowerCase() : "";
    const thread = threadRaw || state.plannerThread || "default";
    const linksJson = JSON.stringify(state.noteLinks || []);
    const autoTags = buildChatAutoTags();
    const mergedTags = Array.from(new Set([...tags, ...autoTags]));
    if (!state.chatProvider || !state.chatModel) {
      showToast("Provider/model required.", "warn");
      return;
    }
    const pendingToken = startChatPending(thread);
    clearNoteComposer();
    renderNotes(Array.isArray(state.notes?.items) ? state.notes.items : []);
    let result = null;
    try {
      result = await postOp("planner-chat-send-llm", {
        thread,
        title,
        body,
        tags: mergedTags.join(","),
        provider_id: state.chatProvider || "",
        model: state.chatModel || "",
        profile: state.chatProfile || "",
      });
    } finally {
      const status = String(result?.status || "").toUpperCase();
      if (!result || status.includes("FAIL")) {
        clearChatPending(pendingToken);
        try {
          await refreshNotes();
        } catch (_) {
          renderNotes(Array.isArray(state.notes?.items) ? state.notes.items : []);
        }
      }
    }
  });

  const noteBodyInput = $("#note-body");
  if (noteBodyInput) {
    noteBodyInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
      const titleEl = $("#note-title");
      const titleVal = titleEl ? titleEl.value.trim() : "";
      const bodyVal = noteBodyInput.value || "";
      if (!titleVal && !bodyVal.trim()) return;
      event.preventDefault();
      const saveBtn = $("#note-save");
      if (saveBtn) saveBtn.click();
    });
  }

  $("#note-clear").addEventListener("click", () => {
    clearNoteComposer();
  });

  renderNoteLinks();
  initChatModelSelectors();
  setNotesView("chat");

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
    if (state.activeTab === "timeline") scheduleRefresh("timeline", refreshTimeline, 180);
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
state.theme = readThemeFromStorage(THEME_STORAGE_KEY, "dark");
state.adminModeEnabled = readBoolFromStorage("cockpit_admin_mode.v1", false);
state.lockClaimsLimit = readIntFromStorage("cockpit_lock_claims_limit.v1", 20, [10, 20, 50]);
state.lockClaimsGroupByOwner = readBoolFromStorage("cockpit_lock_claims_group_owner.v1", false);
state.catalogDraft = readCatalogDraftFromStorage();
setupLanguageSelector();
setupThemeSelector();
applyTheme(state.theme);
applyI18n();
setupNav();
setupOps();
setupStream();
refreshAll();
refreshEvidence();
