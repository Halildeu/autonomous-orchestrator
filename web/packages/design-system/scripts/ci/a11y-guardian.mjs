#!/usr/bin/env node
/**
 * a11y-guardian.mjs — Accessibility Guardian
 *
 * Scans all component source files for a11y best practices.
 * Reports missing ARIA, keyboard, focus management patterns.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '../../src');
const CI_MODE = process.argv.includes('--ci');

const RULES = [
  {
    id: 'interactive-role',
    test: (content) => {
      // Strategy: find lines with onClick=, then look backwards for the nearest opening tag.
      // Only flag if that tag is non-semantic (div, span, li, td, tr, etc.).
      const NON_SEMANTIC_TAGS = new Set([
        'div', 'span', 'li', 'td', 'tr', 'section', 'article', 'aside',
        'header', 'footer', 'nav', 'main', 'p', 'g', 'rect', 'circle', 'path',
      ]);
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // Line must contain onClick as a JSX attribute (not a type def or prop name)
        if (!/\bonClick[=({]/.test(line)) continue;
        // Skip if this line also has role=
        if (line.includes('role=')) continue;
        // Look at this line and up to 5 lines above for the opening tag
        const contextLines = lines.slice(Math.max(0, i - 5), i + 1).join('\n');
        // Find the LAST opening tag in context
        const tagMatches = [...contextLines.matchAll(/<(\w+)\b/g)];
        if (tagMatches.length === 0) continue;
        const lastTag = tagMatches[tagMatches.length - 1][1];
        if (!NON_SEMANTIC_TAGS.has(lastTag)) continue;
        // Skip backdrop/overlay patterns
        if (contextLines.includes('fixed inset-0') || contextLines.includes('absolute inset-0') || contextLines.includes('backdrop') || contextLines.includes('overlay') || contextLines.includes('aria-hidden')) continue;
        // Skip if context has role= already
        if (/role=/.test(contextLines.slice(contextLines.lastIndexOf('<' + lastTag)))) continue;
        return true;
      }
      return false;
    },
    severity: 'error',
    message: 'onClick handler on non-semantic element without role attribute',
  },
  {
    id: 'keyboard-support',
    test: (content) => {
      const NON_SEMANTIC_TAGS = new Set([
        'div', 'span', 'li', 'td', 'tr', 'section', 'article', 'aside',
        'header', 'footer', 'nav', 'main', 'g',
      ]);
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (!/\bonClick[=({]/.test(line)) continue;
        const contextLines = lines.slice(Math.max(0, i - 5), i + 1).join('\n');
        const tagMatches = [...contextLines.matchAll(/<(\w+)\b/g)];
        if (tagMatches.length === 0) continue;
        const lastTag = tagMatches[tagMatches.length - 1][1];
        if (!NON_SEMANTIC_TAGS.has(lastTag)) continue;
        if (contextLines.includes('fixed inset-0') || contextLines.includes('absolute inset-0') || contextLines.includes('backdrop') || contextLines.includes('aria-hidden')) continue;
        if (contextLines.includes('onKeyDown') || contextLines.includes('onKeyUp')) continue;
        if (contextLines.includes('role=')) continue;
        return true;
      }
      return false;
    },
    severity: 'warning',
    message: 'Click handler without keyboard equivalent (onKeyDown)',
  },
  {
    id: 'focus-visible',
    test: (content) => {
      const hasTabIndex = content.includes('tabIndex') || content.includes('tabindex');
      const hasFocusStyle = content.includes('focus-visible') || content.includes('focus:') || content.includes('focus-ring');
      return hasTabIndex && !hasFocusStyle;
    },
    severity: 'warning',
    message: 'tabIndex set without visible focus styles',
  },
  {
    id: 'image-alt',
    test: (content) => {
      const hasImg = content.includes('<img');
      const hasAlt = content.includes('alt=') || content.includes('aria-label');
      return hasImg && !hasAlt;
    },
    severity: 'error',
    message: 'Image element without alt text or aria-label',
  },
  {
    id: 'form-label',
    test: (content) => {
      const hasInput = content.includes('<input') || content.includes('<textarea') || content.includes('<select');
      const hasLabel = content.includes('aria-label') || content.includes('aria-labelledby')
        || content.includes('htmlFor') || content.includes('<label');
      // Components that wrap inputs with FieldControlShell (which provides label association)
      const hasFieldShell = content.includes('FieldControlShell') || content.includes('FormField');
      return hasInput && !hasLabel && !hasFieldShell;
    },
    severity: 'error',
    message: 'Form element without label (aria-label, aria-labelledby, or htmlFor)',
  },
  {
    id: 'color-contrast',
    test: (content) => {
      // Check for text on colored backgrounds without semantic tokens
      const hasHardcodedBg = /bg-\w+-\d+/.test(content) && /text-\w+-\d+/.test(content);
      const hasSemanticTokens = content.includes('var(--text-') || content.includes('var(--surface-');
      return hasHardcodedBg && !hasSemanticTokens;
    },
    severity: 'info',
    message: 'Hardcoded Tailwind colors \u2014 consider semantic tokens for theme support',
  },
];

// Scan components
function findComponents() {
  const files = [];
  const DIRS = ['primitives', 'components', 'enterprise', 'patterns', 'advanced'];
  for (const dir of DIRS) {
    const fullDir = path.join(SRC, dir);
    if (!fs.existsSync(fullDir)) continue;
    walkDir(fullDir, files);
  }
  return files;
}

function walkDir(d, results) {
  for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name !== '__tests__' && entry.name !== 'node_modules') {
      walkDir(path.join(d, entry.name), results);
    } else if (entry.name.endsWith('.tsx') && !entry.name.includes('.stories.') && !entry.name.includes('.test.')) {
      results.push(path.join(d, entry.name));
    }
  }
}

const files = findComponents();
let totalIssues = 0;
let errors = 0;
let warnings = 0;

console.log(`\n\ud83d\udee1\ufe0f  Accessibility Guardian \u2014 ${files.length} components\n`);

for (const file of files) {
  const content = fs.readFileSync(file, 'utf-8');
  const fileIssues = [];

  for (const rule of RULES) {
    if (rule.test(content)) {
      fileIssues.push(rule);
      totalIssues++;
      if (rule.severity === 'error') errors++;
      if (rule.severity === 'warning') warnings++;
    }
  }

  if (fileIssues.length > 0) {
    const rel = path.relative(SRC, file);
    console.log(`  \ud83d\udcc4 ${rel}`);
    for (const issue of fileIssues) {
      const icon = issue.severity === 'error' ? '\u274c' : issue.severity === 'warning' ? '\u26a0\ufe0f' : '\u2139\ufe0f';
      console.log(`     ${icon} [${issue.id}] ${issue.message}`);
    }
  }
}

console.log(`\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500`);
console.log(`${files.length} components scanned`);
console.log(`${totalIssues} issues: ${errors} errors, ${warnings} warnings`);

const score = Math.max(0, 100 - Math.round((totalIssues / files.length) * 100));
console.log(`A11y Score: ${score}/100\n`);

if (CI_MODE && errors > 0) {
  console.log('\u274c A11Y GUARDIAN FAILED: Critical issues found\n');
  process.exit(1);
}
console.log('\u2705 A11Y GUARDIAN PASSED\n');
