/// <reference types="vite/client" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { federation } from '@module-federation/vite';
import path from 'node:path';
import { readFileSync, existsSync } from 'node:fs';
import { serviceHealthApi } from './vite-plugins/service-health-api';

/* ------------------------------------------------------------------ */
/*  Env helpers — replaces webpack's DefinePlugin + InjectRuntimeEnv   */
/* ------------------------------------------------------------------ */

/** Load .env.local manually (Vite's loadEnv only reads VITE_ prefixed) */
function loadDotEnvLocal(): Record<string, string> {
  const envPath = path.resolve(__dirname, '.env.local');
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

/** Build runtime env payload (same allowlist as webpack.common.js) */
function buildRuntimeEnv(mode: string): Record<string, string> {
  const dotEnv = loadDotEnvLocal();
  // process.env takes priority over .env.local (same as webpack.common.js)
  const merged = { ...dotEnv, ...process.env };
  const allowlist = new Set([
    'NODE_ENV', 'AUTH_MODE', 'AG_GRID_LICENSE_KEY',
    'SHELL_SKIP_REMOTE_SERVICES',
    'SHELL_ENABLE_SUGGESTIONS_REMOTE', 'SHELL_ENABLE_ETHIC_REMOTE',
  ]);
  const payload: Record<string, string> = {};
  for (const [key, value] of Object.entries(merged)) {
    if (!allowlist.has(key) && !key.startsWith('VITE_') && !key.startsWith('MFE_')) continue;
    if (typeof value === 'string') payload[key] = value;
  }
  payload.NODE_ENV ??= mode;
  return payload;
}

/* ------------------------------------------------------------------ */
/*  Remote helpers — replaces webpack.remotes.js                       */
/* ------------------------------------------------------------------ */

function readEnvBoolean(keys: string[], fallback = true): boolean {
  const dotEnv = loadDotEnvLocal();
  for (const key of keys) {
    const value = dotEnv[key] ?? process.env[key];
    if (typeof value !== 'string' || value.length === 0) continue;
    const n = value.trim().toLowerCase();
    return n === '1' || n === 'true' || n === 'yes' || n === 'on';
  }
  return fallback;
}

function readEnvString(keys: string[], fallback: string): string {
  const dotEnv = loadDotEnvLocal();
  for (const key of keys) {
    const value = dotEnv[key] ?? process.env[key];
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

function buildRemotes() {
  const enabled = {
    suggestions: readEnvBoolean(['VITE_SHELL_ENABLE_SUGGESTIONS_REMOTE', 'SHELL_ENABLE_SUGGESTIONS_REMOTE']),
    ethic: readEnvBoolean(['VITE_SHELL_ENABLE_ETHIC_REMOTE', 'SHELL_ENABLE_ETHIC_REMOTE']),
    access: readEnvBoolean(['VITE_SHELL_ENABLE_ACCESS_REMOTE', 'SHELL_ENABLE_ACCESS_REMOTE']),
    audit: readEnvBoolean(['VITE_SHELL_ENABLE_AUDIT_REMOTE', 'SHELL_ENABLE_AUDIT_REMOTE']),
    users: readEnvBoolean(['VITE_SHELL_ENABLE_USERS_REMOTE', 'SHELL_ENABLE_USERS_REMOTE']),
    reporting: readEnvBoolean(['VITE_SHELL_ENABLE_REPORTING_REMOTE', 'SHELL_ENABLE_REPORTING_REMOTE']),
    schemaExplorer: readEnvBoolean(['VITE_SHELL_ENABLE_SCHEMA_EXPLORER_REMOTE', 'SHELL_ENABLE_SCHEMA_EXPLORER_REMOTE']),
  };

  // All remotes must be declared so MF plugin can resolve their imports
  // at static analysis time. Disabled remotes use a stub entry that returns
  // empty modules — the dynamic import() in shell-services-wiring.ts
  // will catch the error and gracefully skip.
  const STUB = 'data:text/javascript,export default {}; export function configureShellServices(){}';
  const remoteEntries = {
    suggestions: readEnvString(['MFE_SUGGESTIONS_URL', 'VITE_MFE_SUGGESTIONS_URL'], 'http://localhost:3001/remoteEntry.js'),
    ethic: readEnvString(['MFE_ETHIC_URL', 'VITE_MFE_ETHIC_URL'], 'http://localhost:3002/remoteEntry.js'),
    users: readEnvString(['MFE_USERS_URL', 'VITE_MFE_USERS_URL'], 'http://localhost:3004/remoteEntry.js'),
    access: readEnvString(['MFE_ACCESS_URL', 'VITE_MFE_ACCESS_URL'], 'http://localhost:3005/remoteEntry.js'),
    audit: readEnvString(['MFE_AUDIT_URL', 'VITE_MFE_AUDIT_URL'], 'http://localhost:3006/remoteEntry.js'),
    reporting: readEnvString(['MFE_REPORTING_URL', 'VITE_MFE_REPORTING_URL'], 'http://localhost:3007/remoteEntry.js'),
    schemaExplorer: readEnvString(
      ['MFE_SCHEMA_EXPLORER_URL', 'VITE_MFE_SCHEMA_EXPLORER_URL'],
      'http://localhost:3008/remoteEntry.js',
    ),
  };

  return {
    mfe_suggestions: {
      type: 'module',
      name: 'mfe_suggestions',
      entry: enabled.suggestions ? remoteEntries.suggestions : STUB,
    },
    mfe_ethic: {
      type: 'module',
      name: 'mfe_ethic',
      entry: enabled.ethic ? remoteEntries.ethic : STUB,
    },
    mfe_access: {
      type: 'module',
      name: 'mfe_access',
      entry: enabled.access ? remoteEntries.access : STUB,
    },
    mfe_audit: {
      type: 'module',
      name: 'mfe_audit',
      entry: enabled.audit ? remoteEntries.audit : STUB,
    },
    mfe_users: {
      type: 'module',
      name: 'mfe_users',
      entry: enabled.users ? remoteEntries.users : STUB,
    },
    mfe_reporting: {
      type: 'module',
      name: 'mfe_reporting',
      entry: enabled.reporting ? remoteEntries.reporting : STUB,
    },
    mfe_schema_explorer: {
      type: 'module',
      name: 'mfe_schema_explorer',
      entry: enabled.schemaExplorer ? remoteEntries.schemaExplorer : STUB,
    },
  };
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
) => ({
  singleton: true,
  requiredVersion: deps[versionKey] ?? fallback,
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
  clsx: singleton('clsx'),
  'tailwind-merge': singleton('tailwind-merge'),
  'ag-grid-community': singleton('ag-grid-community'),
  'ag-grid-enterprise': singleton('ag-grid-enterprise'),
  'ag-grid-react': singleton('ag-grid-react'),
};
const isSingleDomainBuild =
  process.env['SINGLE_DOMAIN_BUILD'] === '1' || process.env['CLOUDFLARE_SINGLE_DOMAIN_BUILD'] === '1';

/* ------------------------------------------------------------------ */
/*  Vite Config                                                         */
/* ------------------------------------------------------------------ */

export default defineConfig(({ mode }) => {
  const runtimeEnv = buildRuntimeEnv(mode);
  const appBasePath = normalizeBasePath(readEnvString(['APP_BASE_PATH', 'VITE_APP_BASE_PATH'], '/'));

  return {
    base: appBasePath,
    root: __dirname,
    publicDir: 'public',

    plugins: [
      /* Live service health API — serves /api/services without backend */
      serviceHealthApi(),
      /* Inject runtime env into HTML */
      {
        name: 'inject-runtime-env',
        transformIndexHtml(html) {
          return html.replace(
            'window.__env__ = window.__env__ || {};',
            `window.__env__ = Object.assign({}, ${JSON.stringify(runtimeEnv)});`,
          );
        },
      },
      react(),
      tailwindcss(),
      federation({
        name: 'mfe_shell',
        filename: 'remoteEntry.js',
        dts: false,
        remotes: buildRemotes(),
        exposes: {
          './logic': './src/exposed-logic.ts',
          './services': './src/app/services/shell-services.ts',
          './i18n': './src/app/i18n/index.ts',
        },
        /* Dev mode also needs core singleton sharing.
         * Without this, remotes load their own React runtime and routes white-screen with invalid hook calls. */
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
      }),
    ],

    resolve: {
      alias: [
        { find: '@platform/capabilities', replacement: path.resolve(__dirname, '../../packages/platform-capabilities/src') },
        { find: '@mfe/design-system', replacement: path.resolve(__dirname, '../../packages/design-system/src') },
        { find: '@mfe/i18n-dicts', replacement: path.resolve(__dirname, '../../packages/i18n-dicts/src') },
        { find: '@mfe/shared-http', replacement: path.resolve(__dirname, '../../packages/shared-http/src') },
        // Bypass MF loadShare wrapper for @tanstack/react-query — prevents
        // "QueryCache is not a constructor" caused by async TLA in Vite 8.
        // Direct resolve to node_modules ESM entry, skipping MF's virtual module.
        { find: '@tanstack/react-query', replacement: path.resolve(__dirname, 'node_modules/@tanstack/react-query/build/modern/index.js') },
      ],
    },

    /* Env injection — replaces DefinePlugin + InjectRuntimeEnv */
    define: {
      'process.env': JSON.stringify(runtimeEnv),
    },

    server: {
      host: '127.0.0.1',
      port: 3000,
      strictPort: true,
      proxy: {
        '/auth/realms': {
          target: 'http://localhost:8081',
          changeOrigin: true,
          secure: false,
          rewrite: (p) => p.replace(/^\/auth/, ''),
        },
        // Direct service routes — bypass gateway (avoids Vault/Eureka issues)
        '/api/v1/reports': { target: 'http://localhost:8095', changeOrigin: true, secure: false },
        '/api/v1/dashboards': { target: 'http://localhost:8095', changeOrigin: true, secure: false },
        // Access/authz plane permission-service uzerinde yasiyor; local dev
        // proxy'leri stage gateway sahipligiyle ayni tutulur.
        '/api/v1/context-health': { target: 'http://localhost:8095', changeOrigin: true, secure: false },
        '/api/v1/roles': { target: 'http://localhost:8090', changeOrigin: true, secure: false },
        '/api/v1/permissions': { target: 'http://localhost:8090', changeOrigin: true, secure: false },
        '/api/v1/authz': { target: 'http://localhost:8090', changeOrigin: true, secure: false },
        '/api/v1/users': { target: 'http://localhost:8089', changeOrigin: true, secure: false },
        '/api/v1/companies': { target: 'http://localhost:8092', changeOrigin: true, secure: false },
        '/api/v1/themes': { target: 'http://localhost:8091', changeOrigin: true, secure: false },
        '/api/v1/theme-registry': { target: 'http://localhost:8091', changeOrigin: true, secure: false },
        '/api/v1/me/theme': { target: 'http://localhost:8091', changeOrigin: true, secure: false },
        '/api/v1/variants': { target: 'http://localhost:8091', changeOrigin: true, secure: false },
        // /api/audit → gateway (route'lar permission-service DB'sine bağlı, henüz migrate edilmedi)
        '/api/v1/schema': { target: 'http://localhost:8096', changeOrigin: true, secure: false },
        // '/api/services' handled by serviceHealthApi() Vite plugin
        '/cockpit-api': {
          target: 'http://localhost:8790',
          changeOrigin: true,
          secure: false,
          rewrite: (p) => p.replace(/^\/cockpit-api/, '/api'),
        },
        '/api': { target: 'http://localhost:8080', changeOrigin: true, secure: false },
      },
    },

    /* Pre-bundle ALL deps including monorepo packages — critical for cold-load speed.
     * Without this, Vite serves 250+ individual HTTP requests (one per module).
     * With this, monorepo sources get bundled into optimized chunks like node_modules. */
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
        '@reduxjs/toolkit/query',
        '@reduxjs/toolkit/query/react',
        'react-redux',
        'clsx',
        'tailwind-merge',
        'axios',
        'zod',
        'keycloak-js',
        'ag-grid-community',
        'ag-grid-enterprise',
        'ag-grid-react',
        '@sentry/react',
        'lucide-react',
        // Monorepo packages — stable, rarely change → pre-bundle for speed
        '@mfe/shared-http',
        '@platform/capabilities',
      ],
      exclude: [
        // @tanstack/react-query: MF loadShare wrapper causes "QueryCache is not a constructor"
        '@tanstack/react-query',
        '@tanstack/react-query-devtools',
        // @mfe/design-system: actively developed → exclude for HMR
        '@mfe/design-system',
        // MF remotes + heavy lazy deps
        'shiki',
        'mfe_suggestions',
        'mfe_ethic',
        'mfe_access',
        'mfe_audit',
        'mfe_users',
        'mfe_reporting',
      ],
    },

    /* Warm up critical modules at server start — eliminates first-load delay */
    warmup: {
      clientFiles: [
        './src/index.tsx',
        './src/app/bootstrap.tsx',
        './src/app/ShellApp.tsx',
        './src/app/layout/ShellLayout.tsx',
        './src/app/router/AppRouter.tsx',
        './src/app/providers/AuthBootstrapper.tsx',
        './src/app/store/store.ts',
        './src/app/theme/theme-context.provider.tsx',
        './src/app/config/query-config.ts',
        './src/app/config/shell-services-wiring.ts',
        './src/app/config/http-config.ts',
        './src/app/i18n/index.ts',
        './src/app/auth/auth-config.ts',
        './src/pages/home/*.tsx',
        '../../packages/design-system/src/index.ts',
        '../../packages/design-system/src/components/index.ts',
        '../../packages/design-system/src/primitives/index.ts',
      ],
    },

    build: {
      target: 'esnext',
      outDir: 'dist',
      sourcemap: mode === 'development',
    },
  };
});
