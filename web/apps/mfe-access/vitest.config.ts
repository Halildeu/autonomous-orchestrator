import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  root: __dirname,
  plugins: [react()],
  resolve: {
    alias: [
      { find: 'mfe_shell/i18n', replacement: path.resolve(__dirname, '../mfe-shell/src/app/i18n/index.ts') },
      { find: '@mfe/auth', replacement: path.resolve(__dirname, '../../packages/auth/src/index.ts') },
      { find: '@mfe/design-system', replacement: path.resolve(__dirname, '../../packages/design-system/src') },
      { find: '@mfe/shared-http', replacement: path.resolve(__dirname, '../../packages/shared-http/src') },
      { find: '@mfe/i18n-dicts', replacement: path.resolve(__dirname, '../../packages/i18n-dicts/src') },
    ],
  },
  test: {
    root: __dirname,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
});
