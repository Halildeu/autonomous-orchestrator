#!/usr/bin/env node
/**
 * cleanup-fake-tests.mjs — Detect and remove fake depth tests.
 *
 * Scans all .depth.test.tsx files and flags those that:
 *   1. Contain "quality-depth-boost" or "quality-edge-boost" markers
 *   2. Render <div data-testid> without importing real component
 *   3. Never import from parent directory (no real component)
 *
 * Files with "// depth-keep" directive are always exempt.
 *
 * Usage:
 *   node scripts/ci/cleanup-fake-tests.mjs              # Report only (default)
 *   node scripts/ci/cleanup-fake-tests.mjs --report      # Same as default
 *   node scripts/ci/cleanup-fake-tests.mjs --delete      # Delete fake files
 *   node scripts/ci/cleanup-fake-tests.mjs --json        # JSON output
 */

import { readFileSync, readdirSync, existsSync, unlinkSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DS_ROOT = join(__dirname, '..', '..');
const SRC = join(DS_ROOT, 'src');

const flags = new Set(process.argv.slice(2));
const DELETE_MODE = flags.has('--delete');
const JSON_MODE = flags.has('--json');

function readSafe(filePath) {
  try { return readFileSync(filePath, 'utf-8'); } catch { return ''; }
}

function findFiles(dir, testFn, collected = []) {
  if (!existsSync(dir)) return collected;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist' || entry.name === '.stryker-cache') continue;
      findFiles(full, testFn, collected);
    } else if (testFn(entry.name, full)) {
      collected.push(full);
    }
  }
  return collected;
}

function classifyDepthTest(filePath) {
  const content = readSafe(filePath);
  const reasons = [];

  if (content.includes('// depth-keep')) return null; // exempt

  if (content.includes('quality-depth-boost') || content.includes('quality-edge-boost')) {
    reasons.push('marker');
  }

  const hasDiv = content.includes('<div data-testid=');
  const hasRealImport = /import\s+.*from\s+['"]\.\.\//.test(content);

  if (hasDiv && !hasRealImport) {
    reasons.push('stub-div');
  }

  if (!hasRealImport) {
    reasons.push('no-import');
  }

  return reasons.length > 0 ? reasons : null;
}

// Scan
const allDepthTests = findFiles(SRC, (name) =>
  name.endsWith('.depth.test.tsx') || name.endsWith('.depth.test.ts')
);

const fakes = [];
const real = [];

for (const filePath of allDepthTests) {
  const reasons = classifyDepthTest(filePath);
  if (reasons) {
    fakes.push({ path: relative(DS_ROOT, filePath), reasons, fullPath: filePath });
  } else {
    real.push(relative(DS_ROOT, filePath));
  }
}

// Layer breakdown
const layers = {};
for (const f of fakes) {
  const parts = f.path.split('/');
  const layer = parts[1] || 'unknown'; // src/<layer>/...
  layers[layer] = (layers[layer] || 0) + 1;
}

const report = {
  tool: 'cleanup-fake-tests',
  timestamp: new Date().toISOString(),
  total_depth_tests: allDepthTests.length,
  fake_count: fakes.length,
  real_count: real.length,
  layers,
  fakes: fakes.map(f => ({ path: f.path, reasons: f.reasons })),
  real,
};

if (JSON_MODE) {
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
} else {
  console.log(`\n\x1b[1mFake Test Cleanup Report\x1b[0m\n`);
  console.log(`  Total depth tests: ${allDepthTests.length}`);
  console.log(`  \x1b[31mFake: ${fakes.length}\x1b[0m`);
  console.log(`  \x1b[32mReal: ${real.length}\x1b[0m\n`);

  console.log(`  \x1b[1mPer layer:\x1b[0m`);
  for (const [layer, count] of Object.entries(layers).sort((a, b) => b[1] - a[1])) {
    console.log(`    ${layer}: ${count}`);
  }
  console.log();

  if (!DELETE_MODE) {
    console.log(`  \x1b[1mFake files (first 20):\x1b[0m`);
    for (const f of fakes.slice(0, 20)) {
      console.log(`    \x1b[31m✗\x1b[0m ${f.path}  [${f.reasons.join(', ')}]`);
    }
    if (fakes.length > 20) console.log(`    … and ${fakes.length - 20} more\n`);
    console.log(`  To delete: node scripts/ci/cleanup-fake-tests.mjs --delete\n`);
  }
}

// Delete mode
if (DELETE_MODE) {
  if (fakes.length === 0) {
    console.log('  Nothing to delete.\n');
    process.exit(0);
  }

  let deleted = 0;
  let failed = 0;
  for (const f of fakes) {
    try {
      unlinkSync(f.fullPath);
      deleted++;
    } catch (err) {
      console.error(`  Failed to delete ${f.path}: ${err.message}`);
      failed++;
    }
  }

  console.log(`  \x1b[32mDeleted: ${deleted}\x1b[0m`);
  if (failed > 0) console.log(`  \x1b[31mFailed: ${failed}\x1b[0m`);
  console.log();
}
