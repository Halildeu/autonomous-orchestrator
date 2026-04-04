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
