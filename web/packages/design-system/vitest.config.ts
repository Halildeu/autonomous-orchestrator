import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  root: __dirname,
  resolve: {
    alias: {
      '@mfe/x-charts': path.resolve(__dirname, '../x-charts/src/index.ts'),
    },
  },
  test: {
    root: __dirname,
    include: ['src/**/*.{test,spec}.{ts,tsx,js,jsx}'],
    globals: true,
    environment: 'jsdom',
    css: false,
    setupFiles: ['./src/__tests__/setup.ts'],
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.stryker-tmp/**',
      '**/*.browser.test.{ts,tsx}',
      '**/*.visual.test.{ts,tsx}',
      '**/*depth*.test.{ts,tsx}',
      '**/*-depth.test.{ts,tsx}',
    ],
    coverage: {
      provider: 'v8',
      thresholds: {
        // Post-cleanup baselines (139 fake tests removed in PR #208).
        // Real coverage exposed after removing inflated edge stubs.
        // Temporarily adjusted to honest baselines; ratchet up as real tests added.
        statements: 70,
        branches: 65,
        functions: 64,
        lines: 72,
      },
    },
  },
});
