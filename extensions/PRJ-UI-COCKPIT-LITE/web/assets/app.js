const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const endpoints = {
  ws: "/api/ws",
  overview: "/api/overview",
  northStar: "/api/north_star",
  status: "/api/status",
  snapshot: "/api/ui_snapshot",
  intake: "/api/intake",
  decisions: "/api/decisions",
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
  extensionToggle: "/api/extensions/toggle",
};

const state = {
  ws: null,
  overview: null,
  northStar: null,
  status: null,
  snapshot: null,
  intake: null,
  decisions: null,
  extensions: null,
  extensionDetail: null,
  overrides: null,
  overridesDetail: null,
  overridesSelected: null,
  jobs: null,
  airunnerJobs: null,
  locks: null,
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
  sort: {
    intake: { key: "bucket", dir: "asc" },
    decisions: { key: "decision_kind", dir: "asc" },
    jobs: { key: "created_at", dir: "desc" },
    notes: { key: "updated_at", dir: "desc" },
  },
};

function unwrap(payload) {
  return payload && payload.data ? payload.data : payload;
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  return res.json();
}

function setBadge(el, status) {
  if (!el) return;
  const norm = String(status || "UNKNOWN").toUpperCase();
  el.classList.remove("ok", "warn", "fail", "idle");
  if (norm.includes("FAIL")) el.classList.add("fail");
  else if (norm.includes("WARN")) el.classList.add("warn");
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

function renderJson(el, data) {
  if (!el) return;
  const text = JSON.stringify(data || {}, null, 2);
  el.textContent = text.length > 8000 ? text.slice(0, 8000) + "\n..." : text;
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
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
    container.innerHTML = `<div class="empty">No actions yet.</div>`;
    return;
  }
  container.innerHTML = state.actionLog
    .slice(0, 20)
    .map((entry) => {
      return `<div class="entry">${entry.ts} | ${entry.op} | ${entry.status} | run_id=${entry.run_id || "-"} | evid=${entry.evidence_count}</div>`;
    })
    .join("");
}

function logAction(data) {
  const trace = data?.trace_meta || {};
  const runId = trace.run_id || "";
  const evidence = Array.isArray(data?.evidence_paths) ? data.evidence_paths.length : 0;
  state.actionLog.unshift({
    ts: new Date().toISOString(),
    op: data?.op || "",
    status: data?.status || "",
    run_id: runId,
    evidence_count: evidence,
  });
  if (state.actionLog.length > 50) state.actionLog.pop();
  renderActionLog();
}

function renderActionResponse() {
  const target = $("#action-response");
  const status = $("#action-status");
  const meta = $("#action-meta");
  if (!state.lastAction) {
    if (status) status.textContent = "no actions yet";
    if (meta) meta.textContent = "";
    if (target) target.textContent = "";
    return;
  }
  const last = state.lastAction;
  if (status) status.textContent = `last action: ${last.op || ""} (${last.status || ""})`;
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
  el.textContent = `API: ${status}`;
}

function setSseStatus(connected) {
  const el = $("#sse-status");
  if (!el) return;
  const status = connected ? "OK" : "DISCONNECTED";
  el.classList.remove("ok", "warn", "fail", "idle");
  el.classList.add(connected ? "ok" : "warn");
  el.textContent = `SSE: ${status}`;
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
  if (decisionPending > 0) next.push("Decision pending: open Decisions tab.");
  if (intakeTotal === 0) next.push("No intake items. Check sources.");
  if (!next.length) next.push("No immediate blockers. Consider auto-loop or new intake.");
  $("#next-steps").textContent = next.join(" ");

  const banner = $("#next-banner");
  if (banner) {
    if (decisionPending > 0) {
      banner.className = "status-banner warn";
      banner.textContent = `Decisions pending (${decisionPending}). Open Decisions.`;
    } else if (intakeTotal === 0) {
      banner.className = "status-banner idle";
      banner.textContent = "No actionable intake. You may add a request.";
    } else {
      banner.className = "status-banner ok";
      banner.textContent = "Ready. Use safe defaults or run a bounded loop.";
    }
  }

  renderJson($("#status-json"), statusData || {});
  renderJson($("#snapshot-json"), snapshotData || {});
  renderJson($("#budget-json"), unwrap(state.budget || {}));

  renderActionResponse();
  renderActionLog();
}

function renderNorthStar() {
  const payload = state.northStar || {};
  const summary = payload.summary || {};
  const scores = summary.scores || {};
  const status = summary.status || "UNKNOWN";

  setBadge($("#north-star-status"), status);
  const summaryEl = $("#north-star-summary");
  if (summaryEl) {
    summaryEl.textContent = `generated_at=${summary.generated_at || ""} gaps=${summary.gap_count || 0} lenses=${summary.lens_count || 0}`;
  }
  const coverageEl = $("#north-star-coverage");
  if (coverageEl) coverageEl.textContent = `coverage=${formatNumber(scores.coverage)}`;
  const maturityEl = $("#north-star-maturity");
  if (maturityEl) maturityEl.textContent = `maturity_avg=${formatNumber(scores.maturity_avg)}`;

  const lenses = payload.lenses || {};
  const lensItems = Object.entries(lenses).map(([name, lens]) => {
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
    { key: "name", label: "Lens" },
    { key: "status", label: "Status" },
    { key: "score", label: "Score" },
    { key: "coverage", label: "Coverage" },
    { key: "requirements", label: "Req OK/Total" },
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
    { key: "id", label: "Gap ID" },
    { key: "control_id", label: "Control" },
    { key: "severity", label: "Severity" },
    { key: "risk_class", label: "Risk" },
    { key: "effort", label: "Effort" },
    { key: "status", label: "Status" },
  ]);

  renderJson($("#north-star-eval-json"), payload.assessment_eval || {});
  renderJson($("#north-star-gap-json"), payload.gap_register || {});
}

function filterBySearch(items, text, keys) {
  if (!text) return items;
  const q = text.toUpperCase();
  return items.filter((item) => {
    return keys.some((key) => String(item?.[key] ?? "").toUpperCase().includes(q));
  });
}

function renderTable(containerId, items, columns, sortKey, sortDir, onSort) {
  const container = $(containerId);
  if (!container) return;
  if (!Array.isArray(items) || items.length === 0) {
    container.innerHTML = `<div class="empty">No items.</div>`;
    return;
  }

  const sorted = stableSort(items, compareBy(sortKey, sortDir));
  const headers = columns
    .map((col) => {
      const indicator = col.key === sortKey ? (sortDir === "asc" ? " \u2191" : " \u2193") : "";
      return `<th><button data-sort="${col.key}">${col.label}${indicator}</button></th>`;
    })
    .join("");

  const rows = sorted
    .slice(0, 120)
    .map((item) => {
      const tds = columns
        .map((col) => {
          const val = col.render ? col.render(item) : item?.[col.key] ?? "";
          return `<td>${val}</td>`;
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

  container.querySelectorAll("[data-sort]").forEach((btn) => {
    btn.addEventListener("click", () => onSort(btn.dataset.sort));
  });
}

function renderStaticTable(containerId, items, columns) {
  const container = $(containerId);
  if (!container) return;
  if (!Array.isArray(items) || items.length === 0) {
    container.innerHTML = `<div class="empty">No items.</div>`;
    return;
  }
  const headers = columns.map((col) => `<th>${col.label}</th>`).join("");
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
  const bucket = $("#filter-bucket").value.trim().toUpperCase();
  const status = $("#filter-status").value.trim().toUpperCase();
  const source = $("#filter-source").value.trim().toUpperCase();
  const ext = $("#filter-extension").value.trim().toUpperCase();

  let filtered = Array.isArray(items) ? items : [];
  if (bucket) filtered = filtered.filter((item) => String(item.bucket || "").toUpperCase() === bucket);
  if (status) filtered = filtered.filter((item) => String(item.status || "").toUpperCase() === status);
  if (source) filtered = filtered.filter((item) => String(item.source_type || "").toUpperCase() === source);
  if (ext) {
    filtered = filtered.filter((item) => {
      const val = item.suggested_extension || [];
      const joined = Array.isArray(val) ? val.join(",") : String(val || "");
      return joined.toUpperCase().includes(ext);
    });
  }
  filtered = filterBySearch(filtered, search, ["title", "bucket", "status", "priority", "severity", "source_type"]);

  $("#intake-count").textContent = `showing ${filtered.length} items`;

  const columns = [
    { key: "bucket", label: "Bucket" },
    { key: "status", label: "Status" },
    { key: "priority", label: "Priority" },
    { key: "severity", label: "Severity" },
    { key: "title", label: "Title" },
    { key: "suggested_extension", label: "Extension", render: (item) => {
        const v = item.suggested_extension;
        return Array.isArray(v) ? v.join(",") : (v || "");
      } },
  ];

  renderTable("#intake-table", filtered, columns, state.sort.intake.key, state.sort.intake.dir, (key) => {
    const dir = state.sort.intake.key === key && state.sort.intake.dir === "asc" ? "desc" : "asc";
    state.sort.intake = { key, dir };
    renderIntakeTable(filtered);
  });
}

function renderDecisionTable(items) {
  const search = $("#decision-search").value.trim();
  let filtered = filterBySearch(items, search, ["decision_kind", "status", "question", "title", "decision_id"]);

  const columns = [
    { key: "decision_kind", label: "Kind" },
    { key: "status", label: "Status" },
    { key: "question", label: "Question", render: (item) => item.question || item.title || "" },
    { key: "decision_id", label: "ID" },
  ];

  renderTable("#decision-table", filtered, columns, state.sort.decisions.key, state.sort.decisions.dir, (key) => {
    const dir = state.sort.decisions.key === key && state.sort.decisions.dir === "asc" ? "desc" : "asc";
    state.sort.decisions = { key, dir };
    renderDecisionTable(filtered);
  });
}

function renderJobsTable(items, targetId) {
  const columns = [
    { key: "kind", label: "Kind", render: (job) => job.kind || job.job_type || "" },
    { key: "status", label: "Status" },
    { key: "job_id", label: "Job ID" },
    { key: "failure_class", label: "Failure", render: (job) => job.failure_class || job.error_code || "" },
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
  renderJson($("#lock-json"), data || {});
}

function renderRunCard() {
  const data = state.runCard || {};
  const exists = data.exists ? "present" : "missing";
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
    list.innerHTML = `<div class="empty">No extensions found.</div>`;
    return;
  }
  const overrides = state.extensions?.overrides?.overrides || {};
  const rows = items
    .map((item) => {
      const extId = String(item.extension_id || "");
      const semver = String(item.semver || "");
      const enabled = item.enabled === true;
      const override = overrides?.[extId]?.enabled;
      const effective = typeof override === "boolean" ? override : enabled;
      const badge = effective ? `<span class="badge ok">enabled</span>` : `<span class="badge warn">disabled</span>`;
      const toggleLabel = effective ? "Disable" : "Enable";
      const toggleTarget = effective ? "false" : "true";
      return `
        <tr>
          <td>${escapeHtml(extId)}</td>
          <td>${escapeHtml(semver)}</td>
          <td>${badge}</td>
          <td>
            <button class="btn" data-ext-view="${escapeHtml(extId)}">View</button>
            <button class="btn warn" data-ext-toggle="${escapeHtml(extId)}" data-ext-enable="${toggleTarget}">${toggleLabel}</button>
          </td>
        </tr>
      `;
    })
    .join("");
  list.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Semver</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  $$("[data-ext-view]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const extId = btn.dataset.extView;
      if (!extId) return;
      state.extensionDetail = await fetchJson(`${endpoints.extensions}?extension_id=${encodeURIComponent(extId)}`);
      renderExtensionDetail();
    });
  });
  $$("[data-ext-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const extId = btn.dataset.extToggle;
      const enable = btn.dataset.extEnable === "true";
      if (!extId) return;
      postAction("extension-toggle", endpoints.extensionToggle, { extension_id: extId, enabled: enable });
    });
  });
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
    list.innerHTML = `<div class="empty">No overrides found.</div>`;
    return;
  }
  const rows = items
    .map((item) => {
      const name = String(item.name || "");
      const mtime = item.mtime ? new Date(item.mtime * 1000).toISOString() : "";
      return `
        <tr>
          <td>${escapeHtml(name)}</td>
          <td>${escapeHtml(mtime)}</td>
          <td><button class="btn" data-setting-edit="${escapeHtml(name)}">Edit</button></td>
        </tr>
      `;
    })
    .join("");
  list.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Updated</th><th>Action</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  $$("[data-setting-edit]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.dataset.settingEdit;
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
    list.innerHTML = `<div class="empty">No chat messages yet.</div>`;
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
    container.textContent = "no links added";
    return;
  }
  container.innerHTML = state.noteLinks
    .map((link, idx) => {
      const label = `${escapeHtml(link.kind)}:${escapeHtml(link.id_or_path)}`;
      return `<span class="note-tag">${label}</span><button class="btn ghost" data-link-remove="${idx}">Remove</button>`;
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
    if (metaEl) metaEl.textContent = "no note selected";
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
  $("#notes-count").textContent = `showing ${filtered.length} notes`;
  if (!filtered.length) {
    list.innerHTML = `<div class="empty">No notes yet.</div>`;
    return;
  }
  list.innerHTML = filtered
    .map((item) => {
      const noteId = escapeHtml(item.note_id || "");
      const title = escapeHtml(item.title || "(untitled)");
      const updated = escapeHtml(item.updated_at || "");
      const tags = Array.isArray(item.tags) ? item.tags.map((t) => `<span class="note-tag">${escapeHtml(t)}</span>`).join("") : "";
      const excerpt = escapeHtml(item.body_excerpt || "");
      return `
        <div class="note-item">
          <div class="note-title">${title}</div>
          <div class="note-meta">updated: ${updated} · id: ${noteId}</div>
          <div class="note-tags">${tags}</div>
          <div class="subtle">${excerpt}</div>
          <div class="note-actions">
            <button class="btn" data-note-view="${noteId}">View</button>
          </div>
        </div>
      `;
    })
    .join("");
  $$("[data-note-view]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (state.actionPending) return;
      const noteId = btn.dataset.noteView;
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
    container.innerHTML = `<div class="empty">No threads yet.</div>`;
    return;
  }
  container.innerHTML = threads
    .map((thread) => {
      const id = String(thread.thread_id || "default");
      const active = id === state.plannerThread ? "active" : "";
      const count = Number(thread.count || 0);
      const last = String(thread.last_ts || "");
      return `
        <button class="thread-item ${active}" data-thread="${escapeHtml(id)}">
          <div class="thread-title">${escapeHtml(id)}</div>
          <div class="subtle">count=${count} last=${escapeHtml(last)}</div>
        </button>
      `;
    })
    .join("");
  $$("[data-thread]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.thread || "default";
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
        return `
          <div class="evidence-item">
            <div>${file.relative_path || file.name}</div>
            <div class="row">
              <button class="btn" data-evidence="${encodeURIComponent(file.path || "")}">View</button>
              <button class="btn" data-copy-path="${encodeURIComponent(file.path || "")}">Copy</button>
            </div>
          </div>`;
      }
      const inner = renderEvidenceTreeNode(value.__children, depth + 1);
      return `
        <details>
          <summary>${key}</summary>
          ${inner}
        </details>`;
    })
    .join("");
}

function renderEvidenceList(items) {
  const treeContainer = $("#evidence-tree");
  if (!Array.isArray(items) || items.length === 0) {
    treeContainer.innerHTML = `<div class="empty">No evidence found.</div>`;
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

async function refreshIntake() {
  state.intake = await fetchJson(endpoints.intake);
  const items = Array.isArray(state.intake.items)
    ? state.intake.items
    : (unwrap(state.intake || {}).items || []);
  renderIntakeTable(items);
}

async function refreshDecisions() {
  state.decisions = await fetchJson(endpoints.decisions);
  const items = Array.isArray(state.decisions.items)
    ? state.decisions.items
    : (unwrap(state.decisions || {}).items || []);
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
  $("#smoke-fast-last").textContent = smokeId ? `last smoke job: ${smokeId}` : "last smoke job: -";
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

async function refreshAll() {
  try {
    state.ws = await fetchJson(endpoints.ws);
    $("#ws-root").textContent = `workspace: ${state.ws.workspace_root}`;
    $("#last-change").textContent = `last change: ${state.ws.last_modified_at}`;
    setConnectionStatus(true);
  } catch (_) {
    setConnectionStatus(false);
  }

  const promises = [
    refreshOverview(),
    refreshNorthStar(),
    refreshIntake(),
    refreshDecisions(),
    refreshExtensions(),
    refreshSettings(),
    refreshJobs(),
    refreshLocks(),
    refreshRunCard(),
    refreshNotes(),
    refreshBudget(),
    (async () => {
      state.status = await fetchJson(endpoints.status);
      state.snapshot = await fetchJson(endpoints.snapshot);
      renderAutoLoopSummary();
    })(),
  ];

  await Promise.all(promises);
}

function confirmAction(op, args) {
  const modal = $("#confirm-modal");
  const text = $("#confirm-text");
  const yes = $("#confirm-yes");
  const no = $("#confirm-no");

  const raw = JSON.stringify(args || {});
  const preview = raw.length > 260 ? raw.slice(0, 260) + "..." : raw;
  text.textContent = `Confirm action: ${op} ${preview}`;
  modal.classList.add("open");

  return new Promise((resolve) => {
    const cleanup = () => {
      modal.classList.remove("open");
      yes.onclick = null;
      no.onclick = null;
    };
    yes.onclick = () => {
      cleanup();
      resolve(true);
    };
    no.onclick = () => {
      cleanup();
      resolve(false);
    };
  });
}

function setActionDisabled(disabled) {
  state.actionPending = disabled;
  $$('[data-op]').forEach((btn) => (btn.disabled = disabled));
  $$('[data-ext-toggle]').forEach((btn) => (btn.disabled = disabled));
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
}

async function postOp(op, args = {}) {
  if (state.actionPending) return null;
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
    showToast(`${op}: ${data.status || "UNKNOWN"}`, data.status === "FAIL" ? "fail" : data.status === "WARN" ? "warn" : "ok");
    if (op === "planner-chat-send" && data.status !== "FAIL") {
      clearNoteComposer();
    }
    if (!res.ok) {
      alert(`OP FAILED: ${data.error || data.status}`);
      return data;
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
    showToast(`${action}: ${data.status || "UNKNOWN"}`, data.status === "FAIL" ? "fail" : data.status === "WARN" ? "warn" : "ok");
    if (!res.ok) {
      alert(`ACTION FAILED: ${data.error || data.status}`);
      return;
    }
    await refreshAll();
  } finally {
    setActionDisabled(false);
  }
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
      alert("Usage: /op <name> <json>");
      return;
    }
    const jsonText = text.slice(text.indexOf(op) + op.length).trim();
    let args = {};
    if (jsonText) {
      try {
        args = JSON.parse(jsonText);
      } catch (err) {
        alert(`Invalid JSON for /op: ${err}`);
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
      alert("Usage: /decision <decision_id> <option_id>");
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
      alert("Usage: /override <policy_*.override.v1.json> <json>");
      return;
    }
    const jsonText = text.slice(text.indexOf(filename) + filename.length).trim();
    if (!jsonText) {
      alert("Override JSON required.");
      return;
    }
    let obj = null;
    try {
      obj = JSON.parse(jsonText);
    } catch (err) {
      alert(`Invalid JSON for override: ${err}`);
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
    const tab = (location.hash || "#overview").replace("#", "");
    $$('nav button').forEach((b) => b.classList.remove("active"));
    const btn = $(`nav button[data-tab="${tab}"]`);
    if (btn) btn.classList.add("active");
    $$('.tab').forEach((t) => t.classList.remove("active"));
    const panel = $("#tab-" + tab);
    if (panel) panel.classList.add("active");
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

function setupOps() {
  $("#refresh-all").addEventListener("click", () => {
    refreshAll();
    refreshEvidence();
  });

  $("#toggle-sidebar").addEventListener("click", () => {
    document.body.classList.toggle("sidebar-collapsed");
  });

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
    $("#filter-bucket").value = "";
    $("#filter-status").value = "";
    $("#filter-source").value = "";
    $("#filter-extension").value = "";
    $("#intake-search").value = "";
    renderIntakeTable((unwrap(state.intake || {}).items || []));
  });
  $("#intake-search").addEventListener("input", () => {
    renderIntakeTable((unwrap(state.intake || {}).items || []));
  });
  $("#decision-search").addEventListener("input", () => {
    renderDecisionTable((unwrap(state.decisions || {}).items || []));
  });

  const lockRefresh = $("#lock-refresh");
  if (lockRefresh) {
    lockRefresh.addEventListener("click", () => refreshLocks());
  }

  $("#extensions-refresh").addEventListener("click", () => refreshExtensions());

  $("#settings-refresh").addEventListener("click", () => refreshSettings());
  $("#settings-save").addEventListener("click", () => {
    const name = state.overridesSelected || "";
    if (!name) {
      alert("Select an override first.");
      return;
    }
    const raw = $("#settings-editor").value || "";
    let obj = null;
    try {
      obj = JSON.parse(raw);
    } catch (err) {
      alert(`Invalid JSON: ${err}`);
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
      alert(`Invalid JSON: ${err}`);
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
        alert("select an op");
        return;
      }
      let args = {};
      const rawArgs = argsField ? argsField.value.trim() : "";
      if (rawArgs) {
        try {
          args = JSON.parse(rawArgs);
        } catch (err) {
          alert(`invalid JSON: ${err}`);
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
      alert("link kind and id/path required");
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
      alert("title or body required");
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
  $("#evidence-search").addEventListener("input", refreshEvidence);

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
      () => showToast("Copied", "ok"),
      () => showToast("Copy failed", "warn")
    );
  } else {
    const el = document.createElement("textarea");
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    showToast("Copied", "ok");
  }
}

function setupStream() {
  const stream = new EventSource("/api/stream");
  stream.addEventListener("overview_tick", () => refreshOverview());
  stream.addEventListener("intake_tick", () => refreshIntake());
  stream.addEventListener("decisions_tick", () => refreshDecisions());
  stream.addEventListener("jobs_tick", () => refreshJobs());
  stream.addEventListener("locks_tick", () => refreshLocks());
  stream.addEventListener("notes_tick", () => refreshNotes());
  stream.addEventListener("chat_tick", () => refreshNotes());
  stream.addEventListener("settings_tick", () => {
    refreshSettings();
    refreshRunCard();
    refreshExtensions();
  });
  stream.addEventListener("changed", () => refreshAll());
  stream.onopen = () => {
    state.sseConnected = true;
    setSseStatus(true);
  };
  stream.onerror = () => {
    state.sseConnected = false;
    setSseStatus(false);
  };
}

setupNav();
setupOps();
setupStream();
refreshAll();
refreshEvidence();
