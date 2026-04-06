#!/usr/bin/env node
/**
 * Component Scorecard System
 *
 * Her bileşen için 8 metrikli kalite puanı üretir.
 * Mevcut araçları (component-audit, test-quality-analyzer) birleştirir.
 *
 * Usage:
 *   node scripts/ci/component-scorecard.mjs              # Full report
 *   node scripts/ci/component-scorecard.mjs --ci          # CI gate (new component <40 fail)
 *   node scripts/ci/component-scorecard.mjs --json        # JSON to reports/scorecard.json
 *   node scripts/ci/component-scorecard.mjs --dir enterprise  # Specific directory
 *   node scripts/ci/component-scorecard.mjs --component Button  # Single component
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '../../src');
const REPORTS = path.resolve(__dirname, '../../reports');

// ── Weights ──
const WEIGHTS = {
  testDepth: 25,
  api: 20,
  a11y: 15,
  testCoverage: 10,
  accessControl: 10,
  storyCompleteness: 10,
  i18n: 5,
  documentation: 5,
};

const COMPONENT_DIRS = [
  'primitives', 'components', 'patterns', 'enterprise',
  'advanced', 'form', 'motion', 'internal', 'providers',
  'performance',
];

const SKIP_FILES = ['index.ts', 'index.tsx', 'types.ts', 'types.tsx', 'utils.ts', 'constants.ts'];
const SKIP_PATTERNS = [/__tests__/, /\.test\./, /\.stories\./, /\.figma\./, /setup\.ts/];

const ACCESS_REQUIRED = ['enterprise', 'components', 'patterns', 'advanced'];
const DISPLAY_NAME_REQUIRED = ['primitives', 'components', 'patterns'];

// ── Component Discovery ──
function findComponents(targetDir) {
  const results = [];
  const dirs = targetDir ? [targetDir] : COMPONENT_DIRS;
  for (const dir of dirs) {
    const fullDir = path.join(SRC, dir);
    if (!fs.existsSync(fullDir)) continue;
    walkDir(fullDir, dir, results);
  }
  return results;
}

function walkDir(d, topDir, results) {
  for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name !== '__tests__' && entry.name !== 'node_modules') {
      walkDir(path.join(d, entry.name), topDir, results);
    } else if (entry.name.endsWith('.tsx') && !SKIP_FILES.includes(entry.name)) {
      const fullPath = path.join(d, entry.name);
      const relPath = path.relative(SRC, fullPath);
      if (SKIP_PATTERNS.some(p => p.test(relPath))) continue;
      results.push({ fullPath, relPath, dir: topDir, name: entry.name.replace('.tsx', '') });
    }
  }
}

// ── Score: API Quality (0-100) ──
function scoreAPI(content, dir, _name) {
  let score = 0;
  const hasDisplayName = /\.displayName\s*=/.test(content);
  const hasForwardRef = /forwardRef|React\.forwardRef/.test(content);
  const hasPropsInterface = /interface\s+\w+Props/.test(content);
  const typeExports = (content.match(/export\s+(?:type|interface)\s+\w+/g) || []).length;
  const hasJSDoc = /\/\*\*[\s\S]*?\*\//.test(content);

  // displayName (20pts)
  if (hasDisplayName) score += 20;
  else if (!DISPLAY_NAME_REQUIRED.includes(dir)) score += 20; // Not required

  // forwardRef (15pts)
  if (hasForwardRef) score += 15;
  else if (!DISPLAY_NAME_REQUIRED.includes(dir)) score += 15;

  // Props interface (25pts)
  if (hasPropsInterface) score += 25;

  // Type exports (20pts)
  score += Math.min(20, typeExports * 5);

  // JSDoc on component (10pts)
  if (hasJSDoc) score += 10;

  // Clean imports — no circular (10pts)
  const hasSelfImport = new RegExp(`from\\s+['"]@mfe/design-system`).test(content);
  if (!hasSelfImport) score += 10;

  return Math.min(100, score);
}

// ── Score: Test Depth (0-100) ── (mirrors test-quality-analyzer logic)
function scoreTestDepth(componentName, componentDir) {
  // Find all test files for this component
  const testFiles = [];
  const searchDirs = [
    path.join(SRC, componentDir, '__tests__'),
    path.join(SRC, componentDir, componentName.toLowerCase(), '__tests__'),
    // kebab-case directory
    path.join(SRC, componentDir, componentName.replace(/([A-Z])/g, (_, c, i) => i ? `-${c.toLowerCase()}` : c.toLowerCase()), '__tests__'),
  ];

  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith('.test.tsx')) continue;
      if (f.includes(componentName)) {
        testFiles.push(path.join(dir, f));
        continue;
      }
      // Content-based discovery for aggregated test files
      try {
        const content = fs.readFileSync(path.join(dir, f), 'utf-8');
        const importPattern = new RegExp(`from\\s+['"][^'"]*[/]${componentName}['"]`);
        if (content.includes(`<${componentName}`) || importPattern.test(content)) {
          testFiles.push(path.join(dir, f));
        }
      } catch { /* skip */ }
    }
  }

  if (testFiles.length === 0) return 0;

  let totalScore = 0;
  for (const tf of testFiles) {
    const content = fs.readFileSync(tf, 'utf-8');
    const testCount = (content.match(/\b(?:it|test)\s*\(/g) || []).length;
    if (testCount === 0) continue;

    const strongAsserts = (content.match(/expect\s*\([^)]+\)\s*\.(?:toBe|toEqual|toHaveBeenCalled|toContain|toMatch|toThrow|toHaveLength|toHaveAttribute|toHaveClass|toHaveStyle|toHaveTextContent|toHaveValue|toBeInTheDocument|toBeVisible|toBeDisabled|toBeEnabled|toBeRequired|toBeChecked)/g) || []).length;
    const weakAsserts = (content.match(/expect\s*\([^)]+\)\s*\.(?:toBeTruthy|toBeFalsy|toBeDefined)/g) || []).length;
    const totalAsserts = strongAsserts + weakAsserts;
    const userEvents = (content.match(/userEvent\.\w+/g) || []).length;
    const fireEvents = (content.match(/fireEvent\.\w+/g) || []).length;
    const axeChecks = (content.match(/expectNoA11yViolations|toHaveNoViolations/g) || []).length;
    const roleQueries = (content.match(/getByRole|findByRole|queryByRole/g) || []).length;
    const disabledTests = /disabled|readonly/i.test(content) ? 1 : 0;
    const errorTests = /error|invalid/i.test(content) ? 1 : 0;
    const emptyTests = /empty|no.?data|null|undefined/i.test(content) ? 1 : 0;

    const assertRatio = Math.min(totalAsserts / testCount, 5) / 5;
    const strongRatio = totalAsserts > 0 ? strongAsserts / totalAsserts : 0;
    const assertDensity = Math.min(100, assertRatio * 60 + strongRatio * 40);
    const interactionCount = userEvents + fireEvents;
    const interaction = Math.min(100,
      (userEvents > 0 ? 35 : 0) +
      (fireEvents > 0 ? 20 : 0) +
      Math.min(interactionCount, 10) * 3 +
      (interactionCount >= 3 ? 15 : 0)
    );
    const edgeCases = Math.min(100, [disabledTests, errorTests, emptyTests].filter(Boolean).length * 33);
    const waitForPresent = /waitFor/.test(content) ? 1 : 0;
    const a11yScore = Math.min(100, (axeChecks > 0 ? 40 : 0) + Math.min(roleQueries, 10) * 6 + waitForPresent * 10);

    totalScore = Math.max(totalScore,
      assertDensity * 0.3 + interaction * 0.3 + edgeCases * 0.2 + a11yScore * 0.2
    );
  }

  return Math.round(totalScore);
}

// ── Score: A11y (0-100) ──
function scoreA11y(componentName, componentDir) {
  const testFiles = [
    ...findTestFilesFor(componentName, componentDir),
    ...findContractTestsFor(componentName, componentDir),
  ];
  if (testFiles.length === 0) return 0;

  let score = 0;
  for (const tf of testFiles) {
    const content = fs.readFileSync(tf, 'utf-8');
    if (/expectNoA11yViolations/.test(content)) score = Math.max(score, 40);
    if (/getByRole|findByRole/.test(content)) score = Math.max(score, score + 20);
    if (/getByLabelText|findByLabelText/.test(content)) score = Math.max(score, score + 15);
    if (/aria-/.test(content)) score = Math.max(score, score + 15);
    if (/toHaveAccessibleName|toHaveAccessibleDescription/.test(content)) score = Math.max(score, score + 10);
  }
  return Math.min(100, score);
}

// ── Score: Test Coverage (0-100) ──
function scoreTestCoverage(componentName, componentDir) {
  // Check if test files exist
  const testFiles = findTestFilesFor(componentName, componentDir);
  const contractTests = findContractTestsFor(componentName, componentDir);

  let score = 0;
  if (testFiles.length > 0) score += 40; // Has unit test
  if (contractTests.length > 0) score += 20; // Has contract test
  if (testFiles.length > 1) score += 20; // Multiple test files

  // Check visual test
  const visualDir = path.join(SRC, '__visual__');
  if (fs.existsSync(visualDir)) {
    const hasVisual = fs.readdirSync(visualDir, { recursive: true })
      .some(f => typeof f === 'string' && f.includes(componentName.replace(/([A-Z])/g, '-$1').toLowerCase().replace(/^-/, '')));
    if (hasVisual) score += 20;
  }

  return Math.min(100, score);
}

// ── Score: Access Control (0-100) ──
function scoreAccessControl(content, dir) {
  if (!ACCESS_REQUIRED.includes(dir)) return 100; // Not required = full score

  let score = 0;
  if (/AccessControlledProps/.test(content)) score += 30;
  if (/resolveAccessState/.test(content)) score += 30;
  if (/accessStyles/.test(content)) score += 20;
  if (/data-access-state/.test(content)) score += 10;
  if (/accessReason/.test(content)) score += 10;

  return Math.min(100, score);
}

// ── Score: Story Completeness (0-100) ──
function scoreStory(componentName, componentDir) {
  const kebab = componentName.replace(/([A-Z])/g, (_, c, i) => i ? `-${c.toLowerCase()}` : c.toLowerCase());
  // Find story files — check direct, kebab subdir, and all immediate subdirs
  const storyPatterns = [
    path.join(SRC, componentDir, `${componentName}.stories.tsx`),
    path.join(SRC, componentDir, kebab, `${componentName}.stories.tsx`),
  ];
  // Scan subdirs for story file (handles form/connected/ConnectedInput.stories.tsx etc)
  const topDir = path.join(SRC, componentDir);
  if (fs.existsSync(topDir)) {
    for (const entry of fs.readdirSync(topDir, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name !== '__tests__' && entry.name !== 'node_modules') {
        storyPatterns.push(path.join(topDir, entry.name, `${componentName}.stories.tsx`));
      }
    }
  }

  let storyFile = null;
  for (const p of storyPatterns) {
    if (fs.existsSync(p)) { storyFile = p; break; }
  }
  if (!storyFile) return 0;

  const content = fs.readFileSync(storyFile, 'utf-8');
  let score = 30; // Story exists

  // Count story exports
  const storyExports = (content.match(/export\s+const\s+\w+/g) || []).length - 1; // -1 for meta
  score += Math.min(30, storyExports * 6); // Up to 5 stories = 30pts

  // Has argTypes (interactive controls)
  if (/argTypes/.test(content)) score += 15;

  // Has decorators
  if (/decorators/.test(content)) score += 10;

  // Has play function (interaction test)
  if (/play\s*:/.test(content)) score += 15;

  return Math.min(100, score);
}

// ── Score: i18n (0-100) ──
function scoreI18n(content) {
  const trPatterns = /['"`](?:Kaydet|Vazgeç|İptal|Sil|Düzenle|Ekle|Kapat|Tamam|Evet|Hayır|Gönder|Onayla|Reddet|Henüz|Sonuç bulunamadı|Veri yok|Hata oluştu|Yükleniyor|Bildirim)['"`]/g;
  const enPatterns = /['"`](?:Save|Cancel|Delete|Edit|Add|Close|Submit|Approve|Reject|No data|No results|Loading|Error occurred|Not found|Click to edit|Show more)['"`]/g;

  const trMatches = (content.match(trPatterns) || []).length;
  const enMatches = (content.match(enPatterns) || []).length;
  const total = trMatches + enMatches;

  if (total === 0) return 100;
  return Math.max(0, 100 - total * 15);
}

// ── Score: Documentation (0-100) ──
function scoreDocumentation(content, componentName, componentDir) {
  let score = 0;

  // JSDoc on component
  if (/\/\*\*[\s\S]*?\*\/\s*(?:export|const|function)/.test(content)) score += 30;

  // Props have JSDoc
  const propsWithDoc = (content.match(/\/\*\*[\s\S]*?\*\/\s*\w+\??:/g) || []).length;
  score += Math.min(30, propsWithDoc * 5);

  // @example tag in JSDoc (+20)
  if (/@example/.test(content)) score += 20;

  // @since tag in JSDoc (+5)
  if (/@since/.test(content)) score += 5;

  // @see tag in JSDoc (+5)
  if (/@see/.test(content)) score += 5;

  // API reference exists (check main + all part files)
  const catalogDir = path.join(SRC, 'catalog');
  if (fs.existsSync(catalogDir)) {
    const catalogFiles = fs.readdirSync(catalogDir).filter(f => f.startsWith('component-api-catalog') && f.endsWith('.json'));
    for (const cf of catalogFiles) {
      const apiContent = fs.readFileSync(path.join(catalogDir, cf), 'utf-8');
      if (apiContent.includes(`"${componentName}"`)) { score += 20; break; }
    }
  }

  // Authoring metadata exists
  const authoringPath = path.join(SRC, componentDir, componentName.replace(/([A-Z])/g, (_, c, i) => i ? `-${c.toLowerCase()}` : c.toLowerCase()), 'component.authoring.v1.json');
  if (fs.existsSync(authoringPath)) score += 20;

  return Math.min(100, score);
}

// ── Helpers ──
function findTestFilesFor(componentName, componentDir) {
  const results = [];
  const kebab = componentName.replace(/([A-Z])/g, (_, c, i) => i ? `-${c.toLowerCase()}` : c.toLowerCase());

  // Collect all __tests__ dirs (including nested subdirs)
  const searchDirs = new Set();
  const topDir = path.join(SRC, componentDir);
  searchDirs.add(path.join(topDir, '__tests__'));
  searchDirs.add(path.join(topDir, kebab, '__tests__'));
  // Scan one level of subdirs for __tests__
  if (fs.existsSync(topDir)) {
    for (const entry of fs.readdirSync(topDir, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name !== '__tests__' && entry.name !== 'node_modules') {
        const sub = path.join(topDir, entry.name, '__tests__');
        if (fs.existsSync(sub)) searchDirs.add(sub);
      }
    }
  }

  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith('.test.tsx') || f.includes('.contract.') || f.includes('.visual.') || f.includes('.browser.')) continue;
      const fullPath = path.join(dir, f);

      // Match by filename
      if (f.includes(componentName) || f.includes(kebab)) {
        results.push(fullPath);
        continue;
      }

      // Match by file content (for aggregated test files like enterprise.test.tsx, viz.test.tsx, utilities.test.tsx)
      try {
        const content = fs.readFileSync(fullPath, 'utf-8');
        const importPattern = new RegExp(`from\\s+['"][^'"]*[/]${componentName}['"]`);
        if (content.includes(`<${componentName}`) || importPattern.test(content)) {
          results.push(fullPath);
        }
      } catch { /* skip unreadable */ }
    }
  }
  return results;
}

function findContractTestsFor(componentName, componentDir) {
  const results = [];
  const kebab = componentName.replace(/([A-Z])/g, (_, c, i) => i ? `-${c.toLowerCase()}` : c.toLowerCase());
  const topDir = path.join(SRC, componentDir);

  const searchDirs = new Set([
    path.join(topDir, '__tests__'),
    path.join(topDir, kebab, '__tests__'),
  ]);
  // Scan subdirs
  if (fs.existsSync(topDir)) {
    for (const entry of fs.readdirSync(topDir, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name !== '__tests__' && entry.name !== 'node_modules') {
        const sub = path.join(topDir, entry.name, '__tests__');
        if (fs.existsSync(sub)) searchDirs.add(sub);
      }
    }
  }

  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) {
      if ((f.includes(componentName) || f.includes(kebab)) && f.includes('.contract.')) {
        results.push(path.join(dir, f));
      }
    }
  }
  return results;
}

function getGrade(score) {
  if (score >= 70) return 'A';
  if (score >= 50) return 'B';
  if (score >= 30) return 'C';
  if (score >= 15) return 'D';
  return 'F';
}

function getImprovements(scores) {
  const improvements = [];
  if (scores.testDepth < 40) improvements.push(`Add userEvent interaction tests (+${Math.min(15, 40 - scores.testDepth)} pts)`);
  if (scores.a11y < 40) improvements.push(`Add expectNoA11yViolations + role queries (+${Math.min(15, 40 - scores.a11y)} pts)`);
  if (scores.storyCompleteness === 0) improvements.push('Create Storybook story (+10 pts)');
  if (scores.storyCompleteness > 0 && scores.storyCompleteness < 50) improvements.push('Add more story variants (+5 pts)');
  if (scores.documentation < 30) improvements.push(`Add JSDoc to component/props (+${Math.min(10, 30 - scores.documentation)} pts)`);
  if (scores.testCoverage < 60) improvements.push('Add contract test or visual test (+5 pts)');
  if (scores.i18n < 80) improvements.push('Extract hardcoded strings to props (+3 pts)');
  if (scores.accessControl < 50) improvements.push('Implement AccessControlledProps (+10 pts)');
  return improvements;
}

// ── Main ──
const args = process.argv.slice(2);
const isCI = args.includes('--ci');
const isJSON = args.includes('--json');
const dirIdx = args.indexOf('--dir');
const compIdx = args.indexOf('--component');
const targetDir = dirIdx >= 0 ? args[dirIdx + 1] : null;
const targetComponent = compIdx >= 0 ? args[compIdx + 1] : null;

console.log('📊 Component Scorecard System\n');

const allComponents = findComponents(targetDir);
const scorecards = [];

for (const { fullPath, relPath, dir, name } of allComponents) {
  if (targetComponent && name !== targetComponent) continue;

  const content = fs.readFileSync(fullPath, 'utf-8');
  const lineCount = content.split('\n').length;
  if (lineCount < 15) continue; // Skip tiny files

  const scores = {
    api: scoreAPI(content, dir, name),
    testDepth: scoreTestDepth(name, dir),
    a11y: scoreA11y(name, dir),
    testCoverage: scoreTestCoverage(name, dir),
    accessControl: scoreAccessControl(content, dir),
    storyCompleteness: scoreStory(name, dir),
    i18n: scoreI18n(content),
    documentation: scoreDocumentation(content, name, dir),
  };

  let totalScore = 0;
  for (const [key, weight] of Object.entries(WEIGHTS)) {
    totalScore += (scores[key] / 100) * weight;
  }
  totalScore = Math.round(totalScore);

  const grade = getGrade(totalScore);
  const improvements = getImprovements(scores);

  scorecards.push({
    name, path: relPath, dir, lineCount,
    scores, totalScore, grade, improvements,
  });
}

// Sort by score ascending (worst first for attention)
scorecards.sort((a, b) => a.totalScore - b.totalScore);

// ── Output ──
if (isJSON) {
  if (!fs.existsSync(REPORTS)) fs.mkdirSync(REPORTS, { recursive: true });
  const outPath = path.join(REPORTS, 'scorecard.json');
  fs.writeFileSync(outPath, JSON.stringify(scorecards, null, 2));
  console.log(`Written to ${outPath}`);
  process.exit(0);
}

// Single component detail
if (targetComponent && scorecards.length === 1) {
  const sc = scorecards[0];
  const bar = (v) => '█'.repeat(Math.round(v / 5)) + '░'.repeat(20 - Math.round(v / 5));
  console.log(`┌${'─'.repeat(57)}┐`);
  console.log(`│ ${sc.name.padEnd(40)} Grade: ${sc.grade} (${sc.totalScore}) │`);
  console.log(`├${'─'.repeat(18)}┬${'─'.repeat(6)}┬${'─'.repeat(30)}┤`);
  for (const [key, val] of Object.entries(sc.scores)) {
    const label = key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()).padEnd(18);
    const color = val >= 60 ? '\x1b[32m' : val >= 30 ? '\x1b[33m' : '\x1b[31m';
    console.log(`│ ${label}│ ${color}${String(val).padStart(4)}\x1b[0m │ ${bar(val)} │`);
  }
  console.log(`├${'─'.repeat(18)}┴${'─'.repeat(6)}┴${'─'.repeat(30)}┤`);
  if (sc.improvements.length > 0) {
    console.log(`│ Improvements:${' '.repeat(42)} │`);
    for (const imp of sc.improvements) {
      console.log(`│ → ${imp.padEnd(53)} │`);
    }
  }
  console.log(`└${'─'.repeat(57)}┘`);
  process.exit(0);
}

// Grade distribution
const grades = { A: 0, B: 0, C: 0, D: 0, F: 0 };
for (const sc of scorecards) grades[sc.grade]++;
const avgScore = Math.round(scorecards.reduce((s, sc) => s + sc.totalScore, 0) / scorecards.length);

console.log(`Total: ${scorecards.length} components | Avg: ${avgScore}/100\n`);

const gradeColors = { A: '\x1b[32m', B: '\x1b[36m', C: '\x1b[33m', D: '\x1b[31m', F: '\x1b[35m' };
const gradeLabels = { A: 'Excellent', B: 'Good', C: 'Fair', D: 'Poor', F: 'Critical' };
console.log('Grade Distribution:');
for (const [g, count] of Object.entries(grades)) {
  const bar = '█'.repeat(Math.round((count / scorecards.length) * 40));
  const pct = Math.round((count / scorecards.length) * 100);
  console.log(`  ${gradeColors[g]}${g} (${gradeLabels[g]})\x1b[0m ${bar} ${count} (${pct}%)`);
}

// Directory breakdown
const dirStats = {};
for (const sc of scorecards) {
  if (!dirStats[sc.dir]) dirStats[sc.dir] = { count: 0, total: 0, grades: { A: 0, B: 0, C: 0, D: 0, F: 0 } };
  dirStats[sc.dir].count++;
  dirStats[sc.dir].total += sc.totalScore;
  dirStats[sc.dir].grades[sc.grade]++;
}

console.log('\nDirectory Breakdown:');
console.log('┌──────────────────┬───────┬────────┬────┬────┬────┬────┬────┐');
console.log('│ Directory        │ Count │  Avg   │  A │  B │  C │  D │  F │');
console.log('├──────────────────┼───────┼────────┼────┼────┼────┼────┼────┤');
for (const [dir, s] of Object.entries(dirStats).sort((a, b) => (a[1].total / a[1].count) - (b[1].total / b[1].count))) {
  const avg = Math.round(s.total / s.count);
  const color = avg >= 50 ? '\x1b[32m' : avg >= 30 ? '\x1b[33m' : '\x1b[31m';
  console.log(`│ ${dir.padEnd(16)} │ ${String(s.count).padStart(5)} │ ${color}${String(avg).padStart(5)}\x1b[0m% │ ${String(s.grades.A).padStart(2)} │ ${String(s.grades.B).padStart(2)} │ ${String(s.grades.C).padStart(2)} │ ${String(s.grades.D).padStart(2)} │ ${String(s.grades.F).padStart(2)} │`);
}
console.log('└──────────────────┴───────┴────────┴────┴────┴────┴────┴────┘');

// Bottom 15
const worst = scorecards.slice(0, 15);
console.log(`\n⚠️  Lowest scored components (showing 15/${scorecards.length}):`);
for (const sc of worst) {
  const weakest = Object.entries(sc.scores).sort((a, b) => a[1] - b[1]).slice(0, 2).map(([k, v]) => `${k}:${v}`).join(', ');
  console.log(`  ${sc.grade} ${String(sc.totalScore).padStart(3)} │ ${sc.path} │ ${weakest}`);
}

// Top 5
const best = [...scorecards].sort((a, b) => b.totalScore - a.totalScore).slice(0, 5);
console.log('\n✅ Highest scored components:');
for (const sc of best) {
  console.log(`  ${sc.grade} ${String(sc.totalScore).padStart(3)} │ ${sc.path}`);
}

// Metric averages
console.log('\nMetric Averages:');
const metricLabels = {
  testDepth: 'Test Depth', api: 'API Quality', a11y: 'Accessibility',
  testCoverage: 'Test Coverage', accessControl: 'Access Control',
  storyCompleteness: 'Story Complete', i18n: 'i18n Ready', documentation: 'Documentation',
};
for (const [key, label] of Object.entries(metricLabels)) {
  const avg = Math.round(scorecards.reduce((s, sc) => s + sc.scores[key], 0) / scorecards.length);
  const bar = '█'.repeat(Math.round(avg / 5));
  const color = avg >= 60 ? '\x1b[32m' : avg >= 40 ? '\x1b[33m' : '\x1b[31m';
  console.log(`  ${label.padEnd(18)} ${color}${bar}\x1b[0m ${avg}/100`);
}

// CI gate
if (isCI) {
  const critical = scorecards.filter(sc => sc.grade === 'F');
  if (critical.length > 0) {
    console.error(`\n❌ SCORECARD GATE FAILED: ${critical.length} component(s) at F grade`);
    for (const sc of critical) {
      console.error(`  ${sc.totalScore} │ ${sc.path}`);
    }
    process.exit(1);
  }

  // D-grade warning (will become blocking in M5 escalation)
  const poor = scorecards.filter(sc => sc.grade === 'D');
  if (poor.length > 0) {
    console.warn(`\n⚠️  SCORECARD WARNING: ${poor.length} component(s) at D grade`);
    for (const sc of poor) {
      console.warn(`  ${sc.totalScore} │ ${sc.path} │ ${sc.improvements[0] || ''}`);
    }
  }

  console.log(`\n✅ SCORECARD GATE PASSED: No F-grade components. ${poor.length} D-grade warnings. Avg: ${avgScore}/100`);
}
