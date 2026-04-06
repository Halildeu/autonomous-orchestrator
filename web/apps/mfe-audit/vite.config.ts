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
  '@mfe/design-system': singleton('@mfe/design-system', false),
  'ag-grid-react': singleton('ag-grid-react'),
  'ag-grid-community': singleton('ag-grid-community'),
  'ag-grid-enterprise': singleton('ag-grid-enterprise'),
  '@mfe/shared-http': singleton('@mfe/shared-http', false),
};

const isTest = !!process.env['VITEST'];
const isQualityBuild = process.env['QUALITY_AUDIT_BUILD'] === '1';
const isQualityRemoteBuild = process.env['QUALITY_AUDIT_BUILD_REMOTE'] === '1';
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
      ...((isTest || isQualityBuild) ? [] : [federation({
        name: 'mfe_audit',
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
          './AuditApp': './src/app/components/AuditApp.tsx',
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
    alias: {
      '@tanstack/react-query': path.resolve(__dirname, 'node_modules/@tanstack/react-query/build/modern/index.js'),
      ...(isQualityRemoteBuild
        ? {}
        : {
            '@mfe/design-system': path.resolve(__dirname, '../../packages/design-system/src'),
            '@mfe/shared-http': path.resolve(__dirname, '../../packages/shared-http/src'),
          }),
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
      'clsx',
      'ag-grid-community',
      'ag-grid-enterprise',
      'ag-grid-react',
    ],
    exclude: ['mfe_shell', '@tanstack/react-query'],
  },

  server: {
    host: '127.0.0.1',
    port: 3006,
    strictPort: true,
    cors: true,
    headers: { 'Access-Control-Allow-Origin': '*' },
  },

  build: {
    target: 'esnext',
    outDir: isQualityBuild ? 'dist-quality' : 'dist',
    chunkSizeWarningLimit: 3072,
  },

  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    },
  });
});
