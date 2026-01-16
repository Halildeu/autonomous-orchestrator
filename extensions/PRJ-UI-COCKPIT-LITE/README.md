# PRJ-UI-COCKPIT-LITE
<a id="prj-ui-cockpit-lite"></a>

Zero-deps local cockpit UI. Read-only JSON, program-led ops trigger, SSE updates, and local chat console.

## Run
- Program-led: `python -m src.ops.manage cockpit-serve --workspace-root .cache/ws_customer_default --port 8787`
- Healthcheck: `python -m src.ops.manage cockpit-healthcheck --workspace-root .cache/ws_customer_default --port 8787`
- Direct: `python extensions/PRJ-UI-COCKPIT-LITE/server.py --workspace-root .cache/ws_customer_default --port 8787`

## Security model
- Read-only file access with strict allowlist (no path traversal).
- Secrets/token values are redacted to presence-only.
- Network default OFF; ops are policy-gated via `src.ops.manage`.

## API (local only)
- `GET /api/ws`
- `GET /api/health`
- `GET /api/overview`
- `GET /api/status`
- `GET /api/ui_snapshot`
- `GET /api/intake`
- `GET /api/decisions`
- `GET /api/extensions`
- `GET /api/settings/overrides`
- `GET /api/settings/get?name=...`
- `GET /api/run_card`
- `GET /api/jobs`
- `GET /api/airunner_jobs`
- `GET /api/locks`
- `GET /api/budget`
- `GET /api/notes`
- `GET /api/notes/search?q=...`
- `GET /api/chat`
- `GET /api/reports?filter=closeout`
- `GET /api/evidence/list?filter=closeout`
- `GET /api/evidence/read?path=...`
- `GET /api/evidence/raw?path=...`
- `GET /api/stream` (SSE)
- `POST /api/op` (allowlisted ops only)
- `POST /api/settings/set_override` (workspace override; confirm required)
- `POST /api/run_card/set` (workspace run-card; confirm required)
- `POST /api/extensions/toggle` (workspace extension override; confirm required)
- `POST /api/chat` (NOTE/HELP; confirm required)

## Ops allowlist (POST /api/op)
- system-status
- ui-snapshot-bundle
- work-intake-check
- work-intake-autoselect
- decision-inbox-build
- decision-inbox-show
- decision-apply
- decision-apply-bulk
- auto-loop
- airrunner-run
- github-ops-job-start (SMOKE_FAST only)
- github-ops-job-poll
- smoke-fast-triage
- smoke-full-triage
- doer-loop-lock-status
- doer-loop-lock-clear
- cockpit-healthcheck
- planner-notes-create
- planner-notes-delete
