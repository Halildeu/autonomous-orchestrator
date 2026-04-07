![Tests](https://img.shields.io/badge/tests-5910%20pass-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-85%25-green)
![TypeScript](https://img.shields.io/badge/typescript-strict-blue)
![Components](https://img.shields.io/badge/components-232-blue)
![Stories](https://img.shields.io/badge/stories-139-blue)
![Bundle](https://img.shields.io/badge/bundle-gated-green)
![A11y](https://img.shields.io/badge/a11y-axe--core-purple)
![Tokens](https://img.shields.io/badge/tokens-DTCG-orange)
![License](https://img.shields.io/badge/license-UNLICENSED-red)
![Node](https://img.shields.io/badge/node-20%20%7C%2022-green)
![React](https://img.shields.io/badge/react-18.2%20%7C%2018.3-blue)

# @mfe Platform

Micro-frontend platform with shared design system, X-suite component packages, and module federation architecture.

## Packages

| Package | Description |
|---------|-------------|
| `@mfe/design-system` | Core design system — tokens, primitives, components |
| `@mfe/x-data-grid` | AG Grid enterprise wrapper |
| `@mfe/x-charts` | AG Charts wrapper with ChartContainer |
| `@mfe/x-form-builder` | JSON Schema-driven form generator |
| `@mfe/x-editor` | Rich text editor |
| `@mfe/x-kanban` | Kanban board |
| `@mfe/x-scheduler` | Calendar/scheduler |
| `@mfe/shared-http` | HTTP client with interceptors |
| `@mfe/shared-types` | Shared TypeScript types |
| `@mfe/i18n-dicts` | Internationalization dictionaries |
| `@mfe/platform-capabilities` | Auth, permissions, feature flags |
| `@mfe/create-app` | Project scaffolding CLI |

## Apps

| App | Description |
|-----|-------------|
| `mfe-shell` | Host shell — routing, MF orchestration, Design Lab |
| `mfe-access` | Access management micro-frontend |
| `mfe-audit` | Audit log micro-frontend |
| `mfe-users` | User management micro-frontend |
| `mfe-reporting` | Reporting micro-frontend |

## Quick Start

```bash
pnpm install

# Canonical local stack
cd ../backend
./scripts/run-compose-stack.sh

cd ../web
pnpm start
```

Canonical entrypoint memory:
- `../docs/04-operations/RUNBOOKS/RB-local-dev-stack.md`

## Verification

```bash
pnpm run verify
```

## Production Runtime

`mfe-shell` production build'i artik remote MFE adreslerini env'den alabilir.

- `VITE_GATEWAY_URL` veya same-origin `/api` proxy
- `MFE_USERS_URL`
- `MFE_ACCESS_URL`
- `MFE_AUDIT_URL`
- `MFE_REPORTING_URL`
- `MFE_SUGGESTIONS_URL`
- `MFE_ETHIC_URL`
- `MFE_SCHEMA_EXPLORER_URL`

Ornek:

```bash
MFE_USERS_URL=https://users.ai.acik.com/remoteEntry.js
MFE_ACCESS_URL=https://access.ai.acik.com/remoteEntry.js
MFE_AUDIT_URL=https://audit.ai.acik.com/remoteEntry.js
MFE_REPORTING_URL=https://reporting.ai.acik.com/remoteEntry.js
VITE_GATEWAY_URL=https://ai.acik.com/api
```

`VITE_MFE_*` varyantlari da desteklenir; runtime inject tarafinda `MFE_*` anahtarlari da `window.__env__` icine yazilir.

## Documentation

- [Architecture Overview](./docs/architecture-overview.md)
- [Certified Compatibility Matrix](./docs/certified-compatibility.md)
- [Contributing Guide](./CONTRIBUTING.md)
- [Security Policy](./SECURITY.md)
