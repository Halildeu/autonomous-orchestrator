#!/usr/bin/env node
/**
 * Design System Doctor v1.0 — Unified health check for @mfe/design-system.
 *
 * Orchestrates existing CI tools into a single diagnostic report.
 * Each check delegates to an existing script or performs a targeted scan.
 *
 * Checks (8):
 *  1. fake-test-detection     Sahte / stub test dosyası tespiti
 *  2. a11y-errors             Erişilebilirlik hataları (a11y-guardian delegasyonu)
 *  3. hardcoded-colors        Hardcoded renk tespiti (token-audit delegasyonu)
 *  4. component-grades        Bileşen grade kontrolü (scorecard delegasyonu)
 *  5. unused-catalog          Kullanılmayan bileşen tespiti (adoption-report delegasyonu)
 *  6. keyboard-coverage       Keyboard navigation (keyboard-matrix delegasyonu)
 *  7. dark-mode-fallbacks     Dark mode uyumluluğu (dark-fallback-gate delegasyonu)
 *  8. test-quality            Test kalitesi / sığ test tespiti (test-quality-analyzer delegasyonu)
 *
 * Usage:
 *   node scripts/ci/design-system-doctor.mjs            # terminal report
 *   node scripts/ci/design-system-doctor.mjs --json      # JSON output
 *   node scripts/ci/design-system-doctor.mjs --ci        # CI mode (exit 1 on fail)
 *   node scripts/ci/design-system-doctor.mjs --save      # save report to reports/
 *
 * Exit: 0 = healthy, 1 = issues found (--ci mode only fails on 'fail' status)
 */

import { readFileSync, readdirSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DS_ROOT = join(__dirname, '..', '..');
const SRC = join(DS_ROOT, 'src');

const args = process.argv.slice(2);
const flags = new Set(args);
const JSON_MODE = flags.has('--json');
const CI_MODE = flags.has('--ci');
const SAVE_MODE = flags.has('--save');
const GATE_CHECK = args.find(a => a.startsWith('--gate='))?.split('=')[1] || null;

/* ------------------------------------------------------------------ */
/*  Check infrastructure (same pattern as deps-doctor / federation-doctor) */
/* ------------------------------------------------------------------ */

const results = [];
let passCount = 0;
let warnCount = 0;
let failCount = 0;

function check(id, label, fn) {
  try {
    const result = fn();
    const status = result.status;
    if (status === 'pass') passCount++;
    else if (status === 'warn') warnCount++;
    else failCount++;
    results.push({ id, label, ...result });
  } catch (err) {
    failCount++;
    results.push({ id, label, status: 'fail', message: `Exception: ${err.message}` });
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Recursively find files matching a test. */
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

/** Run a sibling CI script and capture raw stdout. Returns string or null. */
function runSiblingScriptRaw(scriptName, extraArgs = '') {
  const scriptPath = join(__dirname, scriptName);
  if (!existsSync(scriptPath)) return null;
  try {
    return execSync(`node "${scriptPath}" ${extraArgs}`, {
      cwd: DS_ROOT,
      encoding: 'utf-8',
      timeout: 120_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } catch (err) {
    return err.stdout || null;
  }
}

/** Read a JSON report file written by a sibling script. */
function readReportFile(relativePath) {
  const full = join(DS_ROOT, relativePath);
  if (!existsSync(full)) return null;
  try { return JSON.parse(readFileSync(full, 'utf-8')); } catch { return null; }
}

/** Read file content, return empty string on error. */
function readSafe(filePath) {
  try { return readFileSync(filePath, 'utf-8'); } catch { return ''; }
}

/* ------------------------------------------------------------------ */
/*  Check 1: fake-test-detection                                       */
/* ------------------------------------------------------------------ */

check('fake-test-detection', 'Sahte / stub test dosyası tespiti', () => {
  // Pattern 1: Files with "quality-edge-boost" or "quality-depth-boost" marker
  const markerFiles = findFiles(SRC, (name, full) => {
    if (!name.endsWith('.test.tsx') && !name.endsWith('.test.ts')) return false;
    const content = readSafe(full);
    return content.includes('quality-edge-boost') || content.includes('quality-depth-boost');
  });

  // Pattern 2: .edge.test or .depth.test files that render <div data-testid> without importing real component
  const stubFiles = findFiles(SRC, (name, full) => {
    if (!name.includes('.edge.test.') && !name.includes('.depth.test.')) return false;
    const content = readSafe(full);
    const hasDiv = content.includes('<div data-testid=');
    const hasRealImport = content.includes(`from '../`) || content.includes(`from "../`);
    return hasDiv && !hasRealImport;
  });

  // Pattern 3: .depth.test files that never import from parent directory
  // Files with "// depth-keep" directive are exempt (allowlist mechanism)
  const noImportDepthFiles = findFiles(SRC, (name, full) => {
    if (!name.endsWith('.depth.test.tsx') && !name.endsWith('.depth.test.ts')) return false;
    const content = readSafe(full);
    if (content.includes('// depth-keep')) return false;
    const hasParentImport = /import\s+.*from\s+['"]\.\.\//.test(content);
    return !hasParentImport;
  });

  const allFakes = new Set([...markerFiles, ...stubFiles, ...noImportDepthFiles]);
  const total = allFakes.size;

  if (total === 0) {
    return { status: 'pass', message: 'Sahte test dosyası bulunamadı' };
  }

  return {
    status: 'fail',
    message: `${total} sahte test dosyası bulundu (${markerFiles.length} marker, ${stubFiles.length} stub, ${noImportDepthFiles.length} no-import)`,
    details: [...allFakes].map(f =>
      f.replace(DS_ROOT + '/', '')
    ).slice(0, 15),
    fix: 'Sahte test dosyalarını silin veya gerçek bileşen import edin. Özel durumlar için // depth-keep direktifi ekleyin.',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 2: a11y-errors                                               */
/* ------------------------------------------------------------------ */

check('a11y-errors', 'Erişilebilirlik hataları', () => {
  const raw = runSiblingScriptRaw('a11y-guardian.mjs', '--ci');

  if (!raw) {
    return { status: 'warn', message: 'a11y-guardian çalıştırılamadı — script bulunamadı veya hata oluştu' };
  }

  // Parse terminal output: "77 issues: 23 errors, 53 warnings" and "A11y Score: 77/100"
  const issueMatch = raw.match(/(\d+) issues:\s*(\d+) errors?,\s*(\d+) warnings?/);
  const scoreMatch = raw.match(/A11y Score:\s*(\d+)\/100/);
  const errorLines = [...raw.matchAll(/❌\s*\[([^\]]+)\]\s*(.+)/g)].map(m => ({
    rule: m[1],
    message: m[2],
  }));
  // Extract file context for errors
  const fileErrors = [];
  const lines = raw.split('\n');
  let currentFile = '';
  for (const line of lines) {
    const fileMatch = line.match(/📄\s+(.+)/);
    if (fileMatch) currentFile = fileMatch[1].trim();
    const errMatch = line.match(/❌\s*\[([^\]]+)\]\s*(.+)/);
    if (errMatch && currentFile) {
      fileErrors.push(`${currentFile}: [${errMatch[1]}] ${errMatch[2]}`);
    }
  }

  const errors = parseInt(issueMatch?.[2] || '0', 10);
  const warnings = parseInt(issueMatch?.[3] || '0', 10);
  const score = parseInt(scoreMatch?.[1] || '0', 10);

  if (errors === 0) {
    return {
      status: 'pass',
      message: `A11y score: ${score}/100, 0 error, ${warnings} warning`,
    };
  }

  // Score ≥ 85 with few errors = warn (remaining are likely enterprise/unused components)
  const severity = score >= 85 && errors <= 10 ? 'warn' : 'fail';

  return {
    status: severity,
    message: `A11y score: ${score}/100, ${errors} error, ${warnings} warning`,
    details: fileErrors.slice(0, 10),
    fix: 'onClick olan elementlere role + onKeyDown ekleyin, form elementlerine label ekleyin',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 3: hardcoded-colors                                          */
/* ------------------------------------------------------------------ */

check('hardcoded-colors', 'Hardcoded renk tespiti', () => {
  const raw = runSiblingScriptRaw('token-audit.mjs');

  if (!raw) {
    return { status: 'warn', message: 'token-audit çalıştırılamadı' };
  }

  // Strip ANSI
  const clean = raw.replace(/\x1b\[[0-9;]*m/g, '');

  // Parse: "Issues found: 49"
  const issueMatch = clean.match(/Issues found:\s*(\d+)/);
  const cleanMatch = clean.match(/Clean files:\s*(\d+)\s*\((\d+)%\)/);

  // Extract file-level issues: "    1 components/autocomplete/Autocomplete.tsx"
  const fileLines = [...clean.matchAll(/^\s+\d+\s+([\w/.-]+\.tsx?)\s*$/gm)].map(m => m[1].trim());

  const issueCount = parseInt(issueMatch?.[1] || '0', 10);
  const cleanPct = parseInt(cleanMatch?.[2] || '100', 10);

  if (issueCount === 0) {
    return { status: 'pass', message: `Hardcoded renk bulunamadı — ${cleanPct}% token kullanımı` };
  }

  return {
    status: cleanPct >= 99 ? 'warn' : 'fail',
    message: `${issueCount} hardcoded renk, ${fileLines.length} dosyada (${cleanPct}% temiz)`,
    details: fileLines.slice(0, 12),
    fix: 'Hardcoded hex/rgb değerleri CSS variable ile değiştirin: var(--semantic-token)',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 4: component-grades                                          */
/* ------------------------------------------------------------------ */

check('component-grades', 'Bileşen grade kontrolü (D/F = fail)', () => {
  // Scorecard writes to reports/scorecard.json — run it first, then read
  runSiblingScriptRaw('component-scorecard.mjs');
  const components = readReportFile('reports/scorecard.json');

  if (!components || !Array.isArray(components)) {
    return { status: 'warn', message: 'component-scorecard çalıştırılamadı veya rapor okunamadı' };
  }

  const lowGrades = components.filter(c => c.grade === 'D' || c.grade === 'F');

  if (lowGrades.length === 0) {
    return {
      status: 'pass',
      message: `${components.length} bileşen tarandı, D/F grade yok`,
    };
  }

  return {
    status: 'fail',
    message: `${lowGrades.length} bileşen D/F grade`,
    details: lowGrades.map(c => `${c.grade} (${c.totalScore}): ${c.name} — weakest: ${
      Object.entries(c.scores || {}).sort((a, b) => a[1] - b[1])[0]?.[0] || '?'
    }`),
    fix: 'AccessControlledProps, aria, Props interface, i18n ekleyin',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 5: unused-catalog                                            */
/* ------------------------------------------------------------------ */

check('unused-catalog', 'Kullanılmayan bileşen tespiti', () => {
  // Run adoption report and check if it writes to a file, or parse stdout
  const raw = runSiblingScriptRaw('adoption-report.mjs');

  if (!raw) {
    return {
      status: 'warn',
      message: 'adoption-report çalıştırılamadı — kullanım verisi yok',
      fix: 'node scripts/ci/adoption-report.mjs çalıştırarak kullanım verisini güncelleyin',
    };
  }

  // Parse "0 imports" lines from terminal output
  const zeroImportLines = [...raw.matchAll(/(\S+)\s+│\s*0\s*│/g)].map(m => m[1]);

  // Also check adoption-report.json if written
  const reportFile = readReportFile('reports/adoption-report.json');
  let unused = zeroImportLines;
  if (reportFile && Array.isArray(reportFile)) {
    unused = reportFile.filter(c => (c.importCount || 0) === 0).map(c => c.name || c.component || 'unknown');
  }

  if (unused.length <= 10) {
    return { status: 'pass', message: `${unused.length} kullanılmayan bileşen (kabul edilebilir)` };
  }

  return {
    status: 'warn',
    message: `${unused.length} bileşen üretimde kullanılmıyor`,
    details: unused.slice(0, 15),
    fix: 'CATALOG-STATUS.md oluşturun: her bileşen ACTIVE/SHOWCASE/EXPERIMENTAL/DEPRECATED olarak etiketlensin',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 6: keyboard-coverage                                         */
/* ------------------------------------------------------------------ */

check('keyboard-coverage', 'Keyboard navigation coverage', () => {
  const raw = runSiblingScriptRaw('keyboard-matrix.mjs');

  if (!raw) {
    return { status: 'warn', message: 'keyboard-matrix çalıştırılamadı' };
  }

  // Parse: "Coverage: 36/36 (100%)" or "Keyboard matrix: 100% (threshold: 70%)"
  const coverageMatch = raw.match(/(\d+)\/(\d+)\s+\((\d+)%\)/);
  const pctMatch = raw.match(/Keyboard matrix:\s*(\d+)%/);
  const passed = raw.includes('PASSED') || raw.includes('✅ Keyboard matrix');
  const coverage = parseInt(pctMatch?.[1] || coverageMatch?.[3] || '0', 10);
  const threshold = 70;

  if (passed || coverage >= threshold) {
    return { status: 'pass', message: `Keyboard coverage: ${coverage}% (${coverageMatch?.[1] || '?'}/${coverageMatch?.[2] || '?'} components)` };
  }

  return {
    status: 'fail',
    message: `Keyboard coverage: ${coverage}% (threshold: ${threshold}%)`,
    fix: 'Interactive bileşenlere onKeyDown handler ekleyin',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 7: dark-mode-fallbacks                                       */
/* ------------------------------------------------------------------ */

check('dark-mode-fallbacks', 'Dark mode uyumluluğu', () => {
  const raw = runSiblingScriptRaw('dark-fallback-gate.mjs');

  if (!raw) {
    return { status: 'warn', message: 'dark-fallback-gate çalıştırılamadı' };
  }

  // Parse: "Hardcoded fallbacks found: 0" and "PASSED" / "FAILED"
  const issueMatch = raw.match(/Hardcoded fallbacks found:\s*(\d+)/);
  const passed = raw.includes('PASSED') || raw.includes('pass');
  const issues = parseInt(issueMatch?.[1] || '0', 10);

  if (passed || issues === 0) {
    return { status: 'pass', message: 'Dark mode: 0 hardcoded fallback' };
  }

  return {
    status: 'fail',
    message: `${issues} dark mode fallback ihlali`,
    fix: 'CSS var fallback değerlerinde hardcoded renk kullanmayın',
  };
});

/* ------------------------------------------------------------------ */
/*  Check 8: test-quality                                              */
/* ------------------------------------------------------------------ */

check('test-quality', 'Test kalitesi (sığ test tespiti)', () => {
  const raw = runSiblingScriptRaw('test-quality-analyzer.mjs');

  if (!raw) {
    return { status: 'warn', message: 'test-quality-analyzer çalıştırılamadı' };
  }

  // Strip ANSI escape codes for reliable parsing
  const clean = raw.replace(/\x1b\[[0-9;]*m/g, '');

  // Parse F-grade entries: "  F  13% │ path/to/file.test.tsx"
  const fGradeLines = [...clean.matchAll(/^\s*F\s+(\d+)%\s*│\s*(.+?)$/gm)].map(m => ({
    score: parseInt(m[1], 10),
    file: m[2].trim(),
  }));

  // Parse D-grade entries for info
  const dGradeLines = [...clean.matchAll(/^\s*D\s+(\d+)%\s*│\s*(.+?)$/gm)].length;

  // Count total analyzed
  const totalMatch = clean.match(/(\d+)\s+test\s+(?:files?|dosya)/i);

  if (fGradeLines.length === 0) {
    return { status: 'pass', message: `F-grade test yok (${dGradeLines} D-grade)` };
  }

  return {
    status: 'warn',
    message: `${fGradeLines.length} test dosyası F-grade, ${dGradeLines} D-grade`,
    details: fGradeLines.slice(0, 10).map(f => `F (${f.score}%): ${f.file}`),
    fix: 'Sığ testlere assertion, interaction, semantic query ekleyin',
  };
});

/* ------------------------------------------------------------------ */
/*  Output                                                             */
/* ------------------------------------------------------------------ */

const report = {
  tool: 'design-system-doctor',
  version: '1.0.0',
  timestamp: new Date().toISOString(),
  summary: { pass: passCount, warn: warnCount, fail: failCount, total: results.length },
  checks: results,
};

if (JSON_MODE) {
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
} else {
  const icon = (s) => s === 'pass' ? '\x1b[32m✓\x1b[0m' : s === 'warn' ? '\x1b[33m⚠\x1b[0m' : '\x1b[31m✗\x1b[0m';

  console.log('\n\x1b[1mDesign System Doctor v1.0\x1b[0m\n');

  for (const r of results) {
    console.log(`  ${icon(r.status)}  ${r.label}`);
    console.log(`     ${r.message}`);
    if (r.details && r.details.length > 0) {
      for (const d of r.details.slice(0, 8)) {
        console.log(`       → ${d}`);
      }
      if (r.details.length > 8) console.log(`       … and ${r.details.length - 8} more`);
    }
    if (r.fix) console.log(`     \x1b[36mFix:\x1b[0m ${r.fix}`);
    console.log();
  }

  const total = passCount + warnCount + failCount;
  console.log(`  \x1b[1mSummary:\x1b[0m ${passCount}/${total} pass, ${warnCount} warn, ${failCount} fail\n`);
}

/* ------------------------------------------------------------------ */
/*  Save report                                                        */
/* ------------------------------------------------------------------ */

if (SAVE_MODE) {
  const outDir = join(DS_ROOT, 'reports');
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, 'design-system-doctor.v1.json'), JSON.stringify(report, null, 2) + '\n');
  writeFileSync(join(outDir, 'design-system-doctor.v1.md'), formatMarkdown(report));
  if (!JSON_MODE) {
    console.log(`  Report saved to: reports/design-system-doctor.v1.*\n`);
  }
}

function formatMarkdown(rpt) {
  const icon = (s) => s === 'pass' ? '✅' : s === 'warn' ? '⚠️' : '❌';
  let md = `# Design System Doctor Report\n\n`;
  md += `**Date:** ${rpt.timestamp}\n`;
  md += `**Summary:** ${rpt.summary.pass} pass, ${rpt.summary.warn} warn, ${rpt.summary.fail} fail\n\n`;
  for (const r of rpt.checks) {
    md += `## ${icon(r.status)} ${r.label}\n\n`;
    md += `${r.message}\n\n`;
    if (r.details?.length) {
      for (const d of r.details) md += `- ${d}\n`;
      md += '\n';
    }
    if (r.fix) md += `**Fix:** ${r.fix}\n\n`;
  }
  return md;
}

/* ------------------------------------------------------------------ */
/*  Exit                                                               */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Gate mode: run single check and exit                               */
/* ------------------------------------------------------------------ */

if (GATE_CHECK) {
  const gateResult = results.find(r => r.id === GATE_CHECK);
  if (!gateResult) {
    console.error(`Gate check '${GATE_CHECK}' not found. Available: ${results.map(r => r.id).join(', ')}`);
    process.exit(2);
  }
  if (gateResult.status === 'fail') {
    if (!JSON_MODE) {
      console.error(`\n\x1b[31m✗ Gate BLOCKED:\x1b[0m ${gateResult.label}\n  ${gateResult.message}\n`);
      if (gateResult.details) gateResult.details.slice(0, 10).forEach(d => console.error(`  → ${d}`));
      if (gateResult.fix) console.error(`  \x1b[36mFix:\x1b[0m ${gateResult.fix}\n`);
    }
    process.exit(1);
  }
  if (!JSON_MODE) console.log(`\n\x1b[32m✓ Gate PASSED:\x1b[0m ${gateResult.label}\n`);
  process.exit(0);
}

if (CI_MODE && failCount > 0) process.exit(1);
