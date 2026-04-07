#!/usr/bin/env node
/**
 * Test Quality Analyzer
 *
 * Sığ testleri tespit eder. "Test var" ile "gerçek test" arasındaki farkı ölçer.
 *
 * Her test dosyası için 7 metrik hesaplar:
 *   1. Assertion Density    — test başına kaç assertion? (≥3 iyi, 1 sığ)
 *   2. Interaction Depth    — userEvent/fireEvent kullanımı (0 = static-only test)
 *   3. A11y Coverage        — axe/role query kullanımı
 *   4. Edge Case Coverage   — error/empty/disabled/null senaryoları
 *   5. Async Testing        — waitFor/findBy kullanımı
 *   6. Semantic Queries      — getByRole/getByLabelText vs getByTestId
 *   7. Mock Sophistication   — vi.fn callback verification vs sadece tanımlama
 *
 * Çıktı: Her test dosyası için 0-100 kalite skoru + "sığ test" etiketleri
 *
 * Usage:
 *   node scripts/ci/test-quality-analyzer.mjs              # Full report
 *   node scripts/ci/test-quality-analyzer.mjs --shallow     # Only show shallow tests
 *   node scripts/ci/test-quality-analyzer.mjs --ci          # CI gate (fail if avg < 40)
 *   node scripts/ci/test-quality-analyzer.mjs --json        # JSON output
 *   node scripts/ci/test-quality-analyzer.mjs --dir enterprise  # Specific directory
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '../../src');

// ── Metrics Configuration ──
const WEIGHTS = {
  assertionDensity: 25,    // En önemli: assert yoksa test değil
  interactionDepth: 20,    // userEvent = gerçek kullanıcı simülasyonu
  edgeCaseCoverage: 15,    // Disabled, error, empty, null handling
  a11yCoverage: 15,        // Accessibility testing
  semanticQueries: 10,     // getByRole vs getByTestId
  asyncTesting: 10,        // waitFor, findBy
  mockSophistication: 5,   // Mock verification depth
};

// ── Pattern Matchers ──
const PATTERNS = {
  // Test structure
  testCase: /\b(?:it|test)\s*\(/g,
  describe: /\bdescribe\s*\(/g,

  // Assertions (strong)
  strongAssert: /expect\s*\([^)]+\)\s*\.(?:toBe|toEqual|toHaveBeenCalled|toContain|toMatch|toThrow|toHaveLength|toHaveAttribute|toHaveClass|toHaveStyle|toHaveTextContent|toHaveValue|toBeInTheDocument|toBeVisible|toBeDisabled|toBeEnabled|toBeRequired|toBeChecked|toHaveAccessibleName|toHaveAccessibleDescription|toBeInvalid|toBeValid)/g,
  // Assertions (weak — often smoke tests)
  weakAssert: /expect\s*\([^)]+\)\s*\.(?:toBeTruthy|toBeFalsy|toBeDefined|not\.toBeNull)/g,
  // Snapshot (weakest — no behavioral verification)
  snapshotAssert: /expect\s*\([^)]+\)\s*\.toMatchSnapshot/g,

  // Interaction
  userEvent: /userEvent\.\w+/g,
  fireEvent: /fireEvent\.\w+/g,
  keyboard: /userEvent\.keyboard|userEvent\.type|fireEvent\.keyDown|fireEvent\.keyUp|fireEvent\.keyPress/g,

  // A11y
  axeCheck: /expectNoA11yViolations|axe|toHaveNoViolations/g,
  roleQuery: /getByRole|findByRole|queryByRole|getAllByRole/g,
  labelQuery: /getByLabelText|findByLabelText|queryByLabelText/g,
  ariaAssert: /toHaveAccessibleName|toHaveAccessibleDescription|aria-/g,

  // Edge cases
  disabledTest: /disabled|readonly|readOnly/g,
  errorTest: /error|invalid|fail|reject|throw/gi,
  emptyTest: /empty|no.?data|null|undefined|missing|\[\s*\]|\.length\s*===?\s*0/gi,
  boundaryTest: /overflow|max|min|limit|boundary|edge|large|zero/gi,

  // Async
  waitFor: /waitFor\s*\(/g,
  findBy: /findBy\w+/g,
  actWrap: /\bact\s*\(/g,

  // Semantic vs implementation queries
  semanticQuery: /getByRole|getByLabelText|getByText|getByAltText|getByTitle|getByDisplayValue/g,
  implementationQuery: /getByTestId|querySelector|querySelectorAll|\.innerHTML|\.textContent(?!\s*\))/g,

  // Mock depth
  mockDefined: /vi\.fn\(\)|jest\.fn\(\)/g,
  mockVerified: /toHaveBeenCalledWith|toHaveBeenCalledTimes|toHaveBeenLastCalledWith|toHaveBeenNthCalledWith/g,
  mockSpyOn: /vi\.spyOn|jest\.spyOn/g,
};

function countMatches(content, pattern) {
  const cloned = new RegExp(pattern.source, pattern.flags);
  return (content.match(cloned) || []).length;
}

function analyzeTestFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const relPath = path.relative(SRC, filePath);
  const lines = content.split('\n');
  const lineCount = lines.length;

  // ── Raw Counts ──
  const testCount = countMatches(content, PATTERNS.testCase);
  if (testCount === 0) return null; // Not a test file

  const strongAsserts = countMatches(content, PATTERNS.strongAssert);
  const weakAsserts = countMatches(content, PATTERNS.weakAssert);
  const snapshotAsserts = countMatches(content, PATTERNS.snapshotAssert);
  const totalAsserts = strongAsserts + weakAsserts + snapshotAsserts;

  const userEvents = countMatches(content, PATTERNS.userEvent);
  const fireEvents = countMatches(content, PATTERNS.fireEvent);
  const keyboardEvents = countMatches(content, PATTERNS.keyboard);

  const axeChecks = countMatches(content, PATTERNS.axeCheck);
  const roleQueries = countMatches(content, PATTERNS.roleQuery);
  const labelQueries = countMatches(content, PATTERNS.labelQuery);
  const ariaAsserts = countMatches(content, PATTERNS.ariaAssert);

  const disabledTests = countMatches(content, PATTERNS.disabledTest);
  const errorTests = countMatches(content, PATTERNS.errorTest);
  const emptyTests = countMatches(content, PATTERNS.emptyTest);
  const boundaryTests = countMatches(content, PATTERNS.boundaryTest);

  const waitFors = countMatches(content, PATTERNS.waitFor);
  const findBys = countMatches(content, PATTERNS.findBy);
  const actWraps = countMatches(content, PATTERNS.actWrap);

  const semanticQueries = countMatches(content, PATTERNS.semanticQuery);
  const implQueries = countMatches(content, PATTERNS.implementationQuery);

  const mocksDefined = countMatches(content, PATTERNS.mockDefined);
  const mocksVerified = countMatches(content, PATTERNS.mockVerified);
  const mockSpyOns = countMatches(content, PATTERNS.mockSpyOn);

  // ── Score Calculation ──
  const scores = {};

  // 1. Assertion Density (0-100)
  const assertsPerTest = totalAsserts / testCount;
  const strongRatio = totalAsserts > 0 ? strongAsserts / totalAsserts : 0;
  scores.assertionDensity = Math.min(100,
    (Math.min(assertsPerTest, 5) / 5) * 60 +  // Up to 5 asserts/test = 60pts
    strongRatio * 30 +                           // Strong assert ratio = 30pts
    (snapshotAsserts === 0 ? 10 : 0)             // No snapshots = 10pts bonus
  );

  // 2. Interaction Depth (0-100)
  const totalInteractions = userEvents + fireEvents;
  const interactionsPerTest = totalInteractions / testCount;
  scores.interactionDepth = Math.min(100,
    (Math.min(interactionsPerTest, 3) / 3) * 70 + // Up to 3 interactions/test = 70pts
    (userEvents > fireEvents ? 20 : 0) +            // Prefer userEvent over fireEvent
    (keyboardEvents > 0 ? 10 : 0)                   // Keyboard testing bonus
  );

  // 3. Edge Case Coverage (0-100)
  const edgeCaseTypes = [disabledTests > 0, errorTests > 0, emptyTests > 0, boundaryTests > 0].filter(Boolean).length;
  scores.edgeCaseCoverage = Math.min(100, edgeCaseTypes * 25);

  // 4. A11y Coverage (0-100)
  scores.a11yCoverage = Math.min(100,
    (axeChecks > 0 ? 40 : 0) +
    (Math.min(roleQueries, 10) / 10) * 30 +
    (labelQueries > 0 ? 15 : 0) +
    (ariaAsserts > 0 ? 15 : 0)
  );

  // 5. Semantic Queries (0-100)
  const totalQueries = semanticQueries + implQueries;
  scores.semanticQueries = totalQueries > 0
    ? Math.round((semanticQueries / totalQueries) * 100)
    : 50; // No queries = neutral

  // 6. Async Testing (0-100)
  const asyncOps = waitFors + findBys + actWraps;
  scores.asyncTesting = Math.min(100,
    (asyncOps > 0 ? 50 : 0) +
    (Math.min(asyncOps, 5) / 5) * 50
  );

  // 7. Mock Sophistication (0-100)
  scores.mockSophistication = mocksDefined === 0 ? 50 : // No mocks needed = neutral
    Math.min(100,
      (mocksVerified / Math.max(mocksDefined, 1)) * 70 +
      (mockSpyOns > 0 ? 30 : 0)
    );

  // ── Weighted Total ──
  let totalScore = 0;
  for (const [key, weight] of Object.entries(WEIGHTS)) {
    totalScore += (scores[key] / 100) * weight;
  }
  totalScore = Math.round(totalScore);

  // ── Shallow Test Detection ──
  const shallowFlags = [];
  if (assertsPerTest < 1.5) shallowFlags.push('LOW_ASSERTIONS');
  if (totalInteractions === 0 && testCount > 1) shallowFlags.push('NO_INTERACTION');
  if (strongAsserts === 0 && totalAsserts > 0) shallowFlags.push('WEAK_ASSERTIONS_ONLY');
  if (snapshotAsserts > strongAsserts) shallowFlags.push('SNAPSHOT_HEAVY');
  if (roleQueries === 0 && semanticQueries === 0) shallowFlags.push('NO_SEMANTIC_QUERIES');
  if (totalScore < 25) shallowFlags.push('CRITICALLY_SHALLOW');

  // ── Contract Test Profile ──
  // Contract tests verify API surface (render, exports, types), not behavior.
  // They are intentionally shallow by design — grading them on interaction
  // depth or a11y would produce false negatives. Apply adjusted thresholds.
  const isContractTest = relPath.includes('.contract.test.');

  if (isContractTest) {
    // Contract tests: only assertion density and API coverage matter
    // Recalculate with contract-specific weights
    const contractScore = Math.round(
      (scores.assertionDensity / 100) * 50 +   // Assertions are king
      (scores.semanticQueries / 100) * 20 +      // Semantic queries nice-to-have
      (scores.mockSophistication / 100) * 15 +   // Mock usage if needed
      (scores.asyncTesting / 100) * 15            // Async if needed
    );
    totalScore = contractScore;
    // Clear shallow flags that don't apply to contract tests
    const contractExempt = ['NO_INTERACTION', 'NO_SEMANTIC_QUERIES', 'CRITICALLY_SHALLOW'];
    for (const flag of contractExempt) {
      const idx = shallowFlags.indexOf(flag);
      if (idx >= 0) shallowFlags.splice(idx, 1);
    }
  }

  // ── Classification ──
  let grade;
  if (totalScore >= 70) grade = 'A';      // Derin, güvenilir test
  else if (totalScore >= 50) grade = 'B';  // İyi ama geliştirilebilir
  else if (totalScore >= 30) grade = 'C';  // Yüzeysel
  else if (totalScore >= 15) grade = 'D';  // Sığ — adı test, işi yok
  else grade = 'F';                         // Anlamsız

  return {
    path: relPath,
    lineCount,
    testCount,
    totalScore,
    grade,
    scores,
    shallowFlags,
    raw: {
      strongAsserts, weakAsserts, snapshotAsserts, totalAsserts,
      userEvents, fireEvents, keyboardEvents,
      axeChecks, roleQueries, labelQueries, ariaAsserts,
      disabledTests, errorTests, emptyTests, boundaryTests,
      waitFors, findBys,
      semanticQueries, implQueries,
      mocksDefined, mocksVerified,
    },
  };
}

function findTestFiles(targetDir) {
  const results = [];
  function walk(d) {
    if (!fs.existsSync(d)) return;
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory() && entry.name !== 'node_modules' && entry.name !== 'dist') {
        walk(full);
      } else if (/\.test\.tsx?$/.test(entry.name) && !entry.name.includes('.visual.') && !entry.name.includes('.browser.')) {
        results.push(full);
      }
    }
  }
  walk(targetDir ? path.join(SRC, targetDir) : SRC);
  return results;
}

// ── Main ──
const args = process.argv.slice(2);
const showShallowOnly = args.includes('--shallow');
const isCI = args.includes('--ci');
const isJSON = args.includes('--json');
const dirIdx = args.indexOf('--dir');
const targetDir = dirIdx >= 0 ? args[dirIdx + 1] : null;

const testFiles = findTestFiles(targetDir);
const results = testFiles.map(f => analyzeTestFile(f)).filter(Boolean);

if (isJSON) {
  console.log(JSON.stringify(results, null, 2));
  process.exit(0);
}

// ── Grade Distribution ──
const grades = { A: 0, B: 0, C: 0, D: 0, F: 0 };
for (const r of results) grades[r.grade]++;

const shallowCount = results.filter(r => r.shallowFlags.length > 0).length;
const avgScore = Math.round(results.reduce((s, r) => s + r.totalScore, 0) / results.length);
const totalTests = results.reduce((s, r) => s + r.testCount, 0);

console.log('🔬 Test Quality Analyzer\n');
console.log(`Analyzed: ${results.length} test files | ${totalTests} test cases | Avg quality: ${avgScore}/100\n`);

// Grade distribution bar
const gradeColors = { A: '\x1b[32m', B: '\x1b[36m', C: '\x1b[33m', D: '\x1b[31m', F: '\x1b[35m' };
const gradeLabels = { A: 'Derin', B: 'İyi', C: 'Yüzeysel', D: 'Sığ', F: 'Anlamsız' };
console.log('Grade Distribution:');
for (const [grade, count] of Object.entries(grades)) {
  const bar = '█'.repeat(Math.round((count / results.length) * 40));
  const pct = Math.round((count / results.length) * 100);
  console.log(`  ${gradeColors[grade]}${grade} (${gradeLabels[grade]})\x1b[0m ${bar} ${count} (${pct}%)`);
}

// Metric averages
console.log('\nMetric Averages:');
const metricNames = {
  assertionDensity: 'Assertion Density',
  interactionDepth: 'Interaction Depth',
  edgeCaseCoverage: 'Edge Case Coverage',
  a11yCoverage: 'A11y Coverage',
  semanticQueries: 'Semantic Queries',
  asyncTesting: 'Async Testing',
  mockSophistication: 'Mock Sophistication',
};
for (const [key, label] of Object.entries(metricNames)) {
  const avg = Math.round(results.reduce((s, r) => s + r.scores[key], 0) / results.length);
  const bar = '█'.repeat(Math.round(avg / 5));
  const color = avg >= 60 ? '\x1b[32m' : avg >= 40 ? '\x1b[33m' : '\x1b[31m';
  console.log(`  ${label.padEnd(22)} ${color}${bar}\x1b[0m ${avg}/100`);
}

// Directory breakdown
if (!targetDir) {
  const dirStats = {};
  for (const r of results) {
    const dir = r.path.split('/')[0];
    if (!dirStats[dir]) dirStats[dir] = { count: 0, totalScore: 0, shallow: 0 };
    dirStats[dir].count++;
    dirStats[dir].totalScore += r.totalScore;
    if (r.shallowFlags.length > 0) dirStats[dir].shallow++;
  }
  console.log('\nDirectory Breakdown:');
  console.log('┌──────────────────┬───────┬────────┬─────────┐');
  console.log('│ Directory        │ Files │ AvgScr │ Shallow │');
  console.log('├──────────────────┼───────┼────────┼─────────┤');
  for (const [dir, s] of Object.entries(dirStats).sort((a, b) => (a[1].totalScore / a[1].count) - (b[1].totalScore / b[1].count))) {
    const avg = Math.round(s.totalScore / s.count);
    const color = avg >= 50 ? '\x1b[32m' : avg >= 30 ? '\x1b[33m' : '\x1b[31m';
    console.log(`│ ${dir.padEnd(16)} │ ${String(s.count).padStart(5)} │ ${color}${String(avg).padStart(5)}\x1b[0m% │ ${String(s.shallow).padStart(7)} │`);
  }
  console.log('└──────────────────┴───────┴────────┴─────────┘');
}

// Shallow tests detail
const shallowTests = results
  .filter(r => showShallowOnly ? r.shallowFlags.length > 0 : r.totalScore < 30)
  .sort((a, b) => a.totalScore - b.totalScore);

if (shallowTests.length > 0) {
  const limit = showShallowOnly ? shallowTests.length : Math.min(20, shallowTests.length);
  console.log(`\n⚠️  ${showShallowOnly ? 'Shallow' : 'Lowest quality'} tests (${shallowTests.length} total, showing ${limit}):`);
  for (const r of shallowTests.slice(0, limit)) {
    const flags = r.shallowFlags.map(f => `\x1b[31m${f}\x1b[0m`).join(' ');
    console.log(`  ${r.grade} ${String(r.totalScore).padStart(3)}% │ ${r.path}`);
    if (flags) console.log(`         │ ${flags}`);
    // Show specific recommendations
    if (r.scores.assertionDensity < 30) console.log(`         │ → Assertion ekle: ${r.raw.totalAsserts} assert / ${r.testCount} test = ${(r.raw.totalAsserts / r.testCount).toFixed(1)}/test`);
    if (r.scores.interactionDepth === 0) console.log(`         │ → userEvent ekle: kullanıcı etkileşimi test edilmiyor`);
    if (r.scores.a11yCoverage === 0) console.log(`         │ → A11y ekle: role query veya axe check yok`);
    if (r.scores.edgeCaseCoverage < 25) console.log(`         │ → Edge case ekle: disabled/error/empty senaryoları yok`);
  }
}

// Top quality tests (examples to follow)
if (!showShallowOnly) {
  const topTests = results.filter(r => r.totalScore >= 70).sort((a, b) => b.totalScore - a.totalScore).slice(0, 5);
  if (topTests.length > 0) {
    console.log('\n✅ En iyi test dosyaları (örnek alınacak):');
    for (const r of topTests) {
      console.log(`  ${r.grade} ${String(r.totalScore).padStart(3)}% │ ${r.path} (${r.testCount} test, ${r.raw.totalAsserts} assert, ${r.raw.userEvents + r.raw.fireEvents} interaction)`);
    }
  }
}

// CI gate
if (isCI) {
  const criticallyShallow = results.filter(r => r.totalScore < 15);
  if (criticallyShallow.length > 0) {
    console.error(`\n❌ CI GATE FAILED: ${criticallyShallow.length} test file(s) critically shallow (score < 15)`);
    for (const r of criticallyShallow.slice(0, 10)) {
      console.error(`  ${r.totalScore}% │ ${r.path} │ ${r.shallowFlags.join(', ')}`);
    }
    process.exit(1);
  }
  // Baseline: 32% (March 2026). Raise to 40% as tests are deepened.
  const AVG_THRESHOLD = 30;
  if (avgScore < AVG_THRESHOLD) {
    console.error(`\n❌ CI GATE FAILED: Average test quality ${avgScore}% < ${AVG_THRESHOLD}% threshold`);
    process.exit(1);
  }
  console.log(`\n✅ CI GATE PASSED: Avg quality ${avgScore}%, no critically shallow tests`);
}
