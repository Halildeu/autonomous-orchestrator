#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDir, '..', '..');
const distRoot = path.join(webRoot, 'dist', 'ubuntu-single-domain');
const host = '127.0.0.1';
const port = Number(process.env.SINGLE_DOMAIN_SMOKE_PORT ?? '4173');
const baseUrl = `http://${host}:${port}`;
const defaultSpec = 'tests/playwright/single-domain.preauth.runtime.spec.ts';

const args = process.argv.slice(2);
const skipBuild = args.includes('--skip-build');
const specArgIndex = args.indexOf('--spec');
const specPath = specArgIndex >= 0 ? (args[specArgIndex + 1] ?? '').trim() || defaultSpec : defaultSpec;

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function fail(message) {
  console.error(`[single-domain-runtime-smoke] FAIL: ${message}`);
  process.exit(1);
}

function contentTypeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return contentTypes[ext] || 'application/octet-stream';
}

function resolveRequestPath(urlPath) {
  const requestUrl = new URL(urlPath, `${baseUrl}/`);
  const pathname = decodeURIComponent(requestUrl.pathname);
  const normalized = pathname === '/' ? '/index.html' : pathname;
  const candidate = path.normalize(path.join(distRoot, normalized));

  if (!candidate.startsWith(distRoot)) {
    return null;
  }

  if (existsSync(candidate) && statSync(candidate).isFile()) {
    return candidate;
  }

  if (existsSync(candidate) && statSync(candidate).isDirectory()) {
    const nestedIndex = path.join(candidate, 'index.html');
    if (existsSync(nestedIndex)) {
      return nestedIndex;
    }
  }

  if (path.extname(candidate)) {
    return null;
  }

  const spaFallback = path.join(distRoot, 'index.html');
  return existsSync(spaFallback) ? spaFallback : null;
}

function run(command, commandArgs, envOverrides = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, commandArgs, {
      cwd: webRoot,
      env: {
        ...process.env,
        ...envOverrides,
      },
      stdio: 'inherit',
    });

    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${commandArgs.join(' ')} exited with code ${code ?? 1}`));
    });
  });
}

async function buildSingleDomainBundle() {
  console.log(`[single-domain-runtime-smoke] build single-domain bundle origin=${baseUrl}`);
  await run(process.execPath, ['./scripts/deploy/build-single-domain.mjs'], {
    WEB_PUBLIC_ORIGIN: baseUrl,
    FRONTEND_PUBLIC_ORIGIN: baseUrl,
    VITE_FRONTEND_PUBLIC_ORIGIN: baseUrl,
  });
}

function startServer() {
  const indexPath = path.join(distRoot, 'index.html');
  if (!existsSync(indexPath)) {
    fail(`single-domain bundle bulunamadi: ${indexPath}`);
  }

  const server = createServer((req, res) => {
    const filePath = resolveRequestPath(req.url || '/');
    if (!filePath || !existsSync(filePath)) {
      res.statusCode = 404;
      res.end('Not Found');
      return;
    }

    res.statusCode = 200;
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Type', contentTypeFor(filePath));
    res.end(readFileSync(filePath));
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => resolve(server));
  });
}

async function runSmoke() {
  await run(
    'npx',
    [
      'playwright',
      'test',
      specPath,
      '--config',
      'tests/playwright/playwright.config.ts',
      '--project=chromium',
      '--workers=1',
    ],
    {
      PLAYWRIGHT_BASE_URL: baseUrl,
      PLAYWRIGHT_TREAT_INSECURE_AS_SECURE_ORIGIN: baseUrl,
      PW_LOCAL_SINGLE_DOMAIN_RUNTIME: '1',
    },
  );
}

let activeServer;

const shutdown = () =>
  new Promise((resolve) => {
    if (!activeServer) {
      resolve();
      return;
    }

    activeServer.close(() => {
      activeServer = undefined;
      resolve();
    });
  });

process.on('SIGINT', async () => {
  await shutdown();
  process.exit(130);
});

process.on('SIGTERM', async () => {
  await shutdown();
  process.exit(143);
});

try {
  if (!skipBuild) {
    await buildSingleDomainBundle();
  }

  activeServer = await startServer();
  console.log(`[single-domain-runtime-smoke] serving ${distRoot} at ${baseUrl}`);
  await runSmoke();
  await shutdown();
} catch (error) {
  await shutdown();
  fail(error instanceof Error ? error.message : String(error));
}
