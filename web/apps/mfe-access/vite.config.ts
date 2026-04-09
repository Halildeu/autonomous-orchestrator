import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { federation } from '@module-federation/vite';
import path from 'node:path';
import { readFileSync } from 'node:fs';

function readEnvString(keys: string[], fallback: string): string {
  for (const key of keys) {
    const value = process.env[key];
    if (typeof value !== 'string') continue;
    const normalized = value.trim();
    if (normalized.length > 0) {
      return normalized;
    }
  }
  return fallback;
}

function normalizeBasePath(value: string): string {
  const normalized = value.trim();
  if (!normalized || normalized === '/') {
    return '/';
  }
  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`;
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`;
}

const pkg = JSON.parse(readFileSync(path.resolve(__dirname, 'package.json'), 'utf8'));
const deps = pkg.dependencies as Record<string, string>;
const singleton = (name: string, fallback: string | boolean = false) => ({
  singleton: true,
  requiredVersion: deps[name] ?? fallback,
});
const sharedCore = {
  react: singleton('react'),
  'react-dom': singleton('react-dom'),
  'react-router': singleton('react-router'),
  'react-router-dom': singleton('react-router-dom'),
  '@reduxjs/toolkit': singleton('@reduxjs/toolkit'),
  'react-redux': singleton('react-redux'),
  '@tanstack/react-query': singleton('@tanstack/react-query'),
};
const sharedProdOnly = {
  'ag-grid-react': singleton('ag-grid-react'),
  'ag-grid-community': singleton('ag-grid-community'),
  'ag-grid-enterprise': singleton('ag-grid-enterprise'),
  '@mfe/design-system': singleton('@mfe/design-system', false),
  '@mfe/shared-http': singleton('@mfe/shared-http', false),
};

const isTest = !!process.env['VITEST'];
const isSingleDomainBuild =
  process.env['SINGLE_DOMAIN_BUILD'] === '1' || process.env['CLOUDFLARE_SINGLE_DOMAIN_BUILD'] === '1';

export default defineConfig(({ mode }) => {
  const appBasePath = normalizeBasePath(readEnvString(['APP_BASE_PATH', 'VITE_APP_BASE_PATH'], '/'));
  const shellRemoteEntry = readEnvString(['MFE_SHELL_URL', 'VITE_MFE_SHELL_URL'], 'http://localhost:3000/remoteEntry.js');

  return ({
    base: appBasePath,
    plugins: [
      react(),
      tailwindcss(),
      ...(isTest ? [] : [federation({
        name: 'mfe_access',
        filename: 'remoteEntry.js',
        dts: false,
        remotes: {
          mfe_shell: {
            type: 'module',
            name: 'mfe_shell',
            entry: shellRemoteEntry,
          },
        },
        exposes: {
          './AccessApp': './src/app/AccessApp.ui.tsx',
          './shell-services': './src/app/services/shell-services.ts',
        },
        shared: {
          ...(isSingleDomainBuild
            ? {
                react: sharedCore.react,
                'react-dom': sharedCore['react-dom'],
                'react-router': sharedCore['react-router'],
                'react-router-dom': sharedCore['react-router-dom'],
                '@reduxjs/toolkit': sharedCore['@reduxjs/toolkit'],
                'react-redux': sharedCore['react-redux'],
              }
            : {
                ...sharedCore,
                ...(mode === 'production' ? sharedProdOnly : {}),
              }),
        },
      })]),
    ],

  resolve: {
    alias: [
      { find: '@mfe/design-system', replacement: path.resolve(__dirname, '../../packages/design-system/src') },
      { find: '@mfe/shared-http', replacement: path.resolve(__dirname, '../../packages/shared-http/src') },
      // mfe_shell/i18n: only alias in test mode — in dev/prod, MF remote handles it.
      // Alias + MF plugin conflict: plugin rewrites to __moduleExports (enforce: pre)
      // then alias resolves to raw TS file that doesn't have __moduleExports → crash.
      ...(isTest ? [{ find: 'mfe_shell/i18n', replacement: path.resolve(__dirname, '../mfe-shell/src/app/i18n/index.ts') }] : []),
      { find: '@tanstack/react-query', replacement: path.resolve(__dirname, 'node_modules/@tanstack/react-query/build/modern/index.js') },
    ],
  },

  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'react/jsx-runtime',
      'react/jsx-dev-runtime',
      'react-router',
      'react-router-dom',
      'axios',
      'ag-grid-community',
      'ag-grid-enterprise',
      'ag-grid-react',
    ],
    exclude: ['mfe_shell', '@tanstack/react-query'],
  },

  server: {
    host: '127.0.0.1',
    port: 3005,
    strictPort: true,
    cors: true,
    headers: { 'Access-Control-Allow-Origin': '*' },
    proxy: {
      '/api/v1/users': { target: 'http://localhost:8089', changeOrigin: true, secure: false },
      '/api/v1/roles': { target: 'http://localhost:8090', changeOrigin: true, secure: false },
      '/api/v1/authz': { target: 'http://localhost:8090', changeOrigin: true, secure: false },
    },
  },

  build: {
    target: 'esnext',
    outDir: 'dist',
    rolldownOptions: {
      external: [/^mfe_shell\//],
    },
  },

  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    },
  });
});
