import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  root: __dirname,
  resolve: {
    alias: {
      '@mfe/auth': path.resolve(__dirname, '../../packages/auth/src/index.ts'),
      '@mfe/x-charts': path.resolve(__dirname, '../../packages/x-charts/src/index.ts'),
      '@mfe/design-system': path.resolve(__dirname, '../../packages/design-system/src/index.ts'),
    },
  },
  test: {
    root: __dirname,
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
