import { defineConfig } from 'vitest/config';
import path from 'path';

// Root-level config: provides global exclude patterns for the workspace.
// In Vitest workspace mode, this config is merged as the base for all projects.
// All patterns here are relative to this file's directory (monorepo root).
export default defineConfig({
  resolve: {
    alias: {
      '@mfe/design-system': path.resolve(__dirname, 'packages/design-system/src'),
      '@mfe/i18n-dicts': path.resolve(__dirname, 'packages/i18n-dicts/src'),
      '@mfe/shared-http': path.resolve(__dirname, 'packages/shared-http/src'),
      '@mfe/auth': path.resolve(__dirname, 'packages/auth/src'),
      '@platform/capabilities': path.resolve(__dirname, 'packages/platform-capabilities/src'),
      'mfe_shell/i18n': path.resolve(__dirname, 'apps/mfe-shell/src/app/i18n/index.ts'),
    },
  },
  test: {
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      // Thresholds enforced per-project in workspace configs, not at root.
      // Root --changed mode covers only touched files — global thresholds
      // are misleading and cause false failures in CI.
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
