import { defineConfig } from 'vitest/config';

// Root-level config: provides global exclude patterns for the workspace.
// In Vitest workspace mode, this config is merged as the base for all projects.
// All patterns here are relative to this file's directory (monorepo root).
export default defineConfig({
  test: {
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      thresholds: {
        statements: 50,
        branches: 40,
        functions: 45,
        lines: 50,
      },
    },
    exclude: [
      // Standard exclusions
      '**/node_modules/**',
      '**/dist/**',
      '**/.git/**',
      // E2E / Playwright tests — run via playwright, not vitest
      '**/e2e/**',
      '**/tests/playwright/**',
      '**/docs/tests/**',
      '**/scripts/__tests__/**',
      // Packages not in the workspace
      '**/packages/i18n-dicts/**',
      // Apps not in the workspace
      '**/apps/mfe-reporting/**',
      '**/apps/mfe-ethic/**',
      // Script tests
      '**/scripts/lint/**',
      '**/scripts/tokens/**',
      // Design-system filtered test types (heavy/browser/visual/depth)
      '**/*.browser.test.{ts,tsx}',
      '**/*.visual.test.{ts,tsx}',
      '**/*depth*.test.{ts,tsx}',
      '**/*-depth.test.{ts,tsx}',
      '**/.stryker-tmp/**',
    ],
  },
});
