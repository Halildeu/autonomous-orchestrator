---
globs: backend/*-service/**
---
# Backend Service Rules
Follow AGENT-CODEX.backend.md (§Spring Boot Pattern: Controller → Service → Repository → Model → DTO).
Claude-only: run `cd backend && mvn test -pl <service-name>` before committing service changes.

## Decision Registry (MUST READ FIRST)
Before modifying auth-related code, read `decisions/topics/zanzibar-openfga.v1.json` and `decisions/topics/security-local-dev.v1.json`. Decisions marked FINAL cannot be reverted. Run `backend/scripts/doctor-zanzibar.sh --quick` before committing.

## Auth Architecture Rules (CRITICAL — DO NOT CHANGE)

### Authorization Stack (D-001, D-002, D-003 FINAL)
- **Authentication:** Keycloak — identity JWT only (sub, email, realm_role). NO permission claims.
- **Authorization Engine:** OpenFGA (Zanzibar) — tuple store, runs on port 4000.
- **Authorization Hub:** `permission-service` — port 8090 (D-003 TRANSFORMED, 2026-04-11).
  - **NOT removed** (legacy aspirational label). Actively runs as OpenFGA Hub.
  - TupleSyncService (role → OpenFGA tuple sync, deny-wins resolution)
  - AuthzVersionService (cache invalidation version management)
  - AuthorizationControllerV1 (`/authz/me`, `/authz/check`, `/authz/batch-check`, `/authz/explain`, `/authz/version`, `/authz/catalog`)
  - AccessControllerV1 (roles CRUD)
  - TupleSyncOutboxPoller (durable retry, SELECT FOR UPDATE SKIP LOCKED)
- **Direct OpenFGA access:** Other services (user, variant, core-data, report) call `OpenFgaAuthzService` directly — they do NOT HTTP-call permission-service for check operations.

### Security Profiles
- `SecurityConfigLocal` (`@Profile("local","dev")`) provides permitAll
- Production `SecurityConfig` must have `@Profile("!local & !dev")` with `anyRequest().authenticated()` catch-all
- **NEVER use `permitAll()` catch-all in production profiles** (C-007)

### Filter Ordering
- `ScopeContextFilter` order: **`LOWEST_PRECEDENCE - 10`** (AFTER Spring Security — D-005)
  - DO NOT change to HIGHEST_PRECEDENCE — userId will be null

### Service Profiles (report-service specifics)
- `MockPermissionServiceClient` `@Profile("conntest","local","dev")`
- `PermissionServiceClient` `@Profile("!conntest & !local & !dev")`
- `SecurityConfig` `@Profile("!local & !dev")`

### Hard Constraints
- **NEVER modify SPRING_PROFILES_ACTIVE or .env files** without user approval
- **NEVER remove permission-service** — it is the OpenFGA Hub (C-005)
- **NEVER duplicate TupleSyncService or AuthzVersionService** in other services
