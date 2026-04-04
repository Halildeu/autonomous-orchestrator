# Frontend Domain Rules

- ALL UI components from @mfe/design-system ONLY — zero external UI deps
- Forbidden imports: antd, @ant-design/icons, @mui/material, @chakra-ui/react, recharts, @nivo, victory, chart.js, d3
- Bundler: Vite (via @vitejs/plugin-react) — NEVER webpack
- @mfe/i18n-dicts must NOT be in Vite optimizeDeps.include (causes cache staling)
- AG Grid 34.3.1: use ag-grid-community + ag-grid-enterprise + ag-grid-react
- Charts via @mfe/x-charts, data grids via @mfe/x-data-grid (design-system wrappers)
- Forms via @mfe/x-form-builder, rich text via @mfe/x-editor
- Module Federation via @module-federation/vite for micro-frontend shell
- Styling: Tailwind CSS via @tailwindcss/vite plugin — no separate CSS frameworks
- Component exports: PageLayout, DetailDrawer, FormDrawer patterns from design-system
- State management: @reduxjs/toolkit + react-redux for global, @tanstack/react-query for server
- Auth: keycloak-js for login only — authorization handled by permission-service (NOT in frontend)
- HTTP: @mfe/shared-http (axios wrapper) — never raw fetch() or axios directly
- TypeScript strict mode enabled, paths aliased via tsconfig (@mfe/* → packages/*)
- Testing: vitest + @testing-library/react — not jest
- Error boundary: @sentry/react for production error tracking
- Route-based code splitting for performance
- Monorepo structure: web/apps/mfe-shell (shell), web/packages/* (shared packages)
- Exposed logic: web/apps/mfe-shell/src/exposed-logic.ts (module federation exports)
- Features directory: web/apps/mfe-shell/src/features/ (feature-based organization)
- Pages directory: web/apps/mfe-shell/src/pages/ (route-based pages)
- Design Lab index: web/apps/mfe-shell/src/pages/admin/design-lab.index.json (component registry)
- Shared packages: auth, config, design-system, i18n-dicts, blocks (all under web/packages/)

## Pinned Versions (auto-updated from package.json)
- React: ~18.2.0 (NOT React 19 — migration not started)
- Vite: 8.0.3 (pnpm override enforced)
- TypeScript: ^5.8.3
- AG Grid: 34.3.1 (exact — pnpm override enforced)
- Tailwind CSS: 4.2.2 via @tailwindcss/vite
- Node.js: 20.x || 22.x
- @mfe/design-system: 1.1.0
- @tanstack/react-query: ^5.90.10
- keycloak-js: ^26.2.3
