---
globs: web/apps/**
---
# MFE App Rules
Follow AGENT-CODEX.web.md (§MFE conventions: Module Federation, routing, state, auth).
Claude-only: run `cd web && npm run lint && npm test` before committing app changes.

## Decision Registry (MUST READ FIRST)
Before modifying auth/proxy code, read `decisions/topics/zanzibar-openfga.v1.json`. Decisions marked FINAL cannot be reverted. Constraints are HARD RULES.

## Auth & Vite Config Rules (CRITICAL — DO NOT CHANGE)

### Environment
- **NEVER modify `web/apps/mfe-shell/.env.local`** — developer's personal config (C-001)
- **NEVER change AUTH_MODE** — it is `keycloak` (sektör standardı, D-007)

### Vite Proxy Targets (vite.config.ts — DO NOT CHANGE without explicit user approval)

**Permission-service (OpenFGA Hub, D-003 FINAL) — port 8090:**
  - `/api/v1/authz` → `http://localhost:8090` (authz/me, check, batch-check, explain, version, catalog)
  - `/api/v1/roles` → `http://localhost:8090` (role CRUD)
  - `/api/v1/permissions` → `http://localhost:8090` (permission catalog)

**Other services:**
  - `/api/v1/users` → `http://localhost:8089` (user-service)
  - `/api/v1/reports` → `http://localhost:8095` (report-service)
  - `/api/v1/companies` → `http://localhost:8092` (core-data-service)
  - `/api/v1/themes` → `http://localhost:8091` (variant-service)
  - `/api/v1/variants` → `http://localhost:8091` (variant-service)
  - `/api/v1/schema` → `http://localhost:8096` (schema-service)

### Permission-Service Role (D-003 TRANSFORMED)
- Port 8090 is ACTIVE — permission-service runs as the OpenFGA synchronization hub
- "permission-service is REMOVED" claim is OUTDATED (pre-D-003 language)
- Frontend `@mfe/auth` package hits `/api/v1/authz/*` endpoints which land on permission-service
- `useAuthorization` legacy hook has been cleaned up; use `usePermissions` + `useZanzibarAccess` from `@mfe/auth`

### Hard Constraints
- **NEVER route `/api/v1/authz|/roles|/permissions` through gateway or anywhere other than 8090** (C-004)
- **NEVER create direct connections to OpenFGA (port 4000) from frontend** — all authz queries go through permission-service hub
