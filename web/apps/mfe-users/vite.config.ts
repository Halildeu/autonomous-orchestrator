/// <reference types="vite/client" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { federation } from '@module-federation/vite';
import path from 'node:path';
import { readFileSync, existsSync } from 'node:fs';

/* ------------------------------------------------------------------ */
/*  Env helpers — replaces webpack's DefinePlugin                      */
/* ------------------------------------------------------------------ */

function loadShellDotEnvLocal(): Record<string, string> {
  const envPath = path.resolve(__dirname, '../mfe-shell/.env.local');
  if (!existsSync(envPath)) return {};
  const result: Record<string, string> = {};
  for (const line of readFileSync(envPath, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq > 0) {
      result[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
    }
  }
  return result;
}

function buildRuntimeEnv(mode: string): Record<string, string> {
  const dotEnv = loadShellDotEnvLocal();
  const merged = { ...dotEnv, ...process.env };
  const allowlist = new Set(['NODE_ENV', 'AUTH_MODE', 'AG_GRID_LICENSE_KEY', 'VITE_AG_GRID_LICENSE_KEY']);
  const payload: Record<string, string> = {};
  for (const [key, value] of Object.entries(merged)) {
    if (!allowlist.has(key) && !key.startsWith('VITE_')) continue;
    if (typeof value === 'string') payload[key] = value;
  }
  payload.NODE_ENV ??= mode;
  return payload;
}

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

/* ------------------------------------------------------------------ */
/*  Read package.json deps for MF shared config                        */
/* ------------------------------------------------------------------ */

const pkg = JSON.parse(readFileSync(path.resolve(__dirname, 'package.json'), 'utf8'));
const deps = pkg.dependencies as Record<string, string>;
const singleton = (
  shareKey: string,
  versionKey: string = shareKey,
  fallback: string | boolean = false,
  extra: Record<string, boolean | string> = {},
) => ({
  singleton: true,
  requiredVersion: deps[versionKey] ?? fallback,
  ...extra,
});
const sharedCore = {
  react: singleton('react'),
  'react-dom': singleton('react-dom'),
  'react-router': singleton('react-router'),
  'react-router-dom': singleton('react-router-dom'),
  'react-redux': singleton('react-redux'),
  '@reduxjs/toolkit': singleton('@reduxjs/toolkit'),
  '@tanstack/react-query': singleton('@tanstack/react-query'),
};
const sharedProdOnly = {
  'ag-grid-react': singleton('ag-grid-react'),
  'ag-grid-community': singleton('ag-grid-community'),
  'ag-grid-enterprise': singleton('ag-grid-enterprise'),
  '@mfe/design-system': singleton('@mfe/design-system', '@mfe/design-system', false),
  '@mfe/shared-http': singleton('@mfe/shared-http', '@mfe/shared-http', false),
  '@mfe/i18n-dicts': singleton('@mfe/i18n-dicts', '@mfe/i18n-dicts', false),
};

const isTest = !!process.env['VITEST'];

/* ------------------------------------------------------------------ */
/*  Vite Config                                                         */
/* ------------------------------------------------------------------ */

export default defineConfig(({ mode }) => {
  const runtimeEnv = buildRuntimeEnv(mode);
  const appBasePath = normalizeBasePath(readEnvString(['APP_BASE_PATH', 'VITE_APP_BASE_PATH'], '/'));
  const shellRemoteEntry = readEnvString(['MFE_SHELL_URL', 'VITE_MFE_SHELL_URL'], 'http://localhost:3000/remoteEntry.js');
  const reportingRemoteEntry = readEnvString(
    ['MFE_REPORTING_URL', 'VITE_MFE_REPORTING_URL'],
    'http://localhost:3007/remoteEntry.js',
  );

  return {
    base: appBasePath,
    root: __dirname,
    publicDir: 'public',

    plugins: [
      react(),
      ...(isTest ? [] : [federation({
        name: 'mfe_users',
        filename: 'remoteEntry.js',
        dts: false,
        remotes: {
          mfe_shell: { type: 'module', name: 'mfe_shell', entry: shellRemoteEntry },
          mfe_reporting: { type: 'module', name: 'mfe_reporting', entry: reportingRemoteEntry },
        },
        exposes: {
          './UsersApp': './src/app/UsersApp.ui.tsx',
          './shell-services': './src/app/services/shell-services.ts',
        },
        shared: {
          /* Always share the full set — remove isSingleDomainBuild conditional
           * to prevent duplicate React instances in single-domain builds. */
          ...sharedCore,
          ...(mode === 'production' ? sharedProdOnly : {}),
        },
      })]),
    ],

    resolve: {
      alias: [
        { find: '@mfe/design-system', replacement: path.resolve(__dirname, '../../packages/design-system/src') },
        { find: '@mfe/auth', replacement: path.resolve(__dirname, '../../packages/auth/src') },
        { find: '@mfe/shared-http', replacement: path.resolve(__dirname, '../../packages/shared-http/src') },
        // mfe_shell/i18n: only alias in test mode — in dev/prod, MF remote handles it
        ...(isTest ? [{ find: 'mfe_shell/i18n', replacement: path.resolve(__dirname, '__mocks__/mfe-shell-i18n.ts') }] : []),
        { find: /^mfe_reporting\/(.*)$/, replacement: path.resolve(__dirname, '__mocks__/mfe-reporting-$1.ts') },
        { find: '@tanstack/react-query', replacement: path.resolve(__dirname, 'node_modules/@tanstack/react-query/build/modern/index.js') },
      ],
    },

    define: {
      'process.env': JSON.stringify(runtimeEnv),
    },

    server: {
      host: '127.0.0.1',
      port: 3004,
      strictPort: true,
      headers: { 'Access-Control-Allow-Origin': '*' },
      proxy: {
        '/api/auth': { target: 'http://localhost:8088', changeOrigin: true, secure: false },
        '/api': { target: 'http://localhost:8080', changeOrigin: true, secure: false },
      },
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
        '@reduxjs/toolkit',
        'react-redux',
        'axios',
        'ag-grid-community',
        'ag-grid-enterprise',
        'ag-grid-react',
      ],
      exclude: ['mfe_shell', 'mfe_reporting', '@tanstack/react-query'],
    },

    build: {
      target: 'esnext',
      outDir: 'dist',
      sourcemap: mode === 'development',
    },

    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test-setup.ts'],
    },
  };
});
