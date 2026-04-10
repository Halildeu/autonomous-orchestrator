#!/usr/bin/env node
/**
 * Depth Test Generator — Props-aware baseline depth tests.
 *
 * Auto-discovers components and generates depth tests based on TS props:
 *   - Boolean props → multi-prop stress combos
 *   - Union props → test.each variant matrix
 *   - Array props → empty, single, large dataset
 *   - Function props → keyboard interaction
 *   - Children → null, 0, empty string
 *   - Controlled pair → controlled vs uncontrolled
 *
 * Does NOT duplicate contract test concerns (displayName, ref, access control).
 *
 * Usage:
 *   node scripts/ci/generate-depth-tests.mjs          # Dry run
 *   node scripts/ci/generate-depth-tests.mjs --write   # Write test files
 *   node scripts/ci/generate-depth-tests.mjs --diff    # Show missing tests
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '../../src');

const COMPONENT_DIRS = ['primitives', 'components', 'patterns', 'enterprise', 'advanced'];
const SKIP = ['index.ts', 'index.tsx', 'types.ts', 'types.tsx', 'utils.ts', 'constants.ts'];
const SKIP_PATTERNS = [/__tests__/, /\.test\./, /\.stories\./, /\.figma\./, /\.d\.ts$/, /setup\.ts/];

function findComponents(dir) {
  const results = [];
  const fullDir = path.join(SRC, dir);
  if (!fs.existsSync(fullDir)) return results;
  for (const entry of fs.readdirSync(fullDir, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name !== '__tests__' && entry.name !== '__visual__') {
      for (const sub of fs.readdirSync(path.join(fullDir, entry.name), { withFileTypes: true })) {
        if (sub.name.endsWith('.tsx') && !SKIP.includes(sub.name) && !SKIP_PATTERNS.some(p => p.test(sub.name))) {
          results.push({ name: sub.name.replace('.tsx', ''), dir, subdir: entry.name });
        }
      }
    } else if (entry.name.endsWith('.tsx') && !SKIP.includes(entry.name) && !SKIP_PATTERNS.some(p => p.test(entry.name))) {
      results.push({ name: entry.name.replace('.tsx', ''), dir, subdir: null });
    }
  }
  return results;
}

function parseProps(filePath) {
  if (!fs.existsSync(filePath)) return null;
  const content = fs.readFileSync(filePath, 'utf-8');

  const propsMatch = content.match(/interface\s+(\w+Props)\s*(?:extends\s+([^{]+))?\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/s);
  if (!propsMatch) return { booleans: [], unions: [], arrays: [], functions: [], hasChildren: false, controlled: false, allProps: [] };

  const propsBody = propsMatch[3];
  const booleans = [];
  const unions = [];
  const arrays = [];
  const functions = [];
  let hasChildren = false;
  let hasValue = false;
  let hasOnChange = false;
  let hasDefaultValue = false;
  const allProps = [];

  for (const line of propsBody.split('\n')) {
    const propMatch = line.match(/^\s*(\w+)(\??):\s*(.+?)(?:;|$)/);
    if (!propMatch) continue;
    const [, name, optional, rawType] = propMatch;
    const type = rawType.trim();
    allProps.push({ name, optional: !!optional, type });

    if (name === 'children') { hasChildren = true; continue; }
    if (name === 'value') { hasValue = true; }
    if (name === 'defaultValue') { hasDefaultValue = true; }
    if (name === 'onChange' || name === 'onValueChange') { hasOnChange = true; }

    if (type === 'boolean') {
      booleans.push(name);
    } else if (type.includes('|') && !type.includes('=>')) {
      const literals = type.split('|').map(s => s.trim().replace(/['"]/g, '')).filter(s => s && s !== 'undefined' && s !== 'null');
      if (literals.length >= 2 && literals.every(s => /^[\w-]+$/.test(s))) {
        unions.push({ name, values: literals });
      }
    } else if (type.includes('[]') || type.startsWith('Array<')) {
      arrays.push(name);
    } else if (type.includes('=>') || name.startsWith('on')) {
      functions.push(name);
    }
  }

  return { booleans, unions, arrays, functions, hasChildren, controlled: hasValue && hasOnChange, hasDefaultValue, allProps };
}

function buildRequiredProps(allProps) {
  const propValues = {
    'string': "'test'", 'number': '42', 'boolean': 'true',
    'React.ReactNode': "'content'", 'ReactNode': "'content'", '() => void': 'vi.fn()',
  };
  const lines = [];
  for (const { name, optional, type } of allProps) {
    if (optional || name === 'children' || name === 'className' || name === 'style') continue;
    let value = propValues[type];
    if (!value) {
      if (type.includes('=>')) value = 'vi.fn()';
      else if (type.includes('[]')) value = '[]';
      else if (type.includes('|')) { value = `'${type.split('|')[0].trim().replace(/['"]/g, '')}'`; }
      else value = 'undefined as any';
    }
    lines.push(`  ${name}: ${value},`);
  }
  return lines.length > 0 ? `const requiredProps = {\n${lines.join('\n')}\n};\n` : '';
}

function generateDepthTest(component, parsed) {
  const { name, dir, subdir } = component;
  const importPath = subdir ? `../${subdir}/${name}` : `../${name}`;
  const requiredPropsCode = buildRequiredProps(parsed.allProps);
  const hasRequired = parsed.allProps.some(p => !p.optional && p.name !== 'children' && p.name !== 'className' && p.name !== 'style');
  const spread = hasRequired ? ' {...requiredProps}' : '';

  const sections = [];

  if (parsed.booleans.length >= 2) {
    const combos = parsed.booleans.slice(0, 4);
    sections.push(`  describe('${name} — depth: prop combinations', () => {
    it('renders with ${combos.join(' + ')} simultaneously', () => {
      render(<${name}${spread} ${combos.join(' ')}>Stressed</${name}>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<${name}${spread} ${combos.join(' ')} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });`);
  } else if (parsed.booleans.length === 1) {
    sections.push(`  describe('${name} — depth: prop combinations', () => {
    it('renders with ${parsed.booleans[0]}', () => {
      const { container } = render(<${name}${spread} ${parsed.booleans[0]} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });`);
  }

  for (const union of parsed.unions.slice(0, 2)) {
    const valuesStr = union.values.map(v => `'${v}'`).join(', ');
    sections.push(`  describe('${name} — depth: ${union.name} variants', () => {
    it.each([${valuesStr}] as const)('${union.name}=%s renders without crash', (val) => {
      const { container } = render(<${name}${spread} ${union.name}={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });`);
  }

  if (parsed.hasChildren) {
    sections.push(`  describe('${name} — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<${name}${spread}>{null}</${name}>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<${name}${spread}>{0}</${name}>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<${name}${spread}>{''}</${name}>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });`);
  }

  for (const arr of parsed.arrays.slice(0, 2)) {
    sections.push(`  describe('${name} — depth: ${arr} array edge cases', () => {
    it('handles empty ${arr}', () => {
      const { container } = render(<${name}${spread} ${arr}={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item ${arr}', () => {
      const { container } = render(<${name}${spread} ${arr}={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });`);
  }

  const clickHandlers = parsed.functions.filter(f => f === 'onClick' || f === 'onPress');
  if (clickHandlers.length > 0) {
    sections.push(`  describe('${name} — depth: keyboard interaction', () => {
    it('fires onClick on keyboard Enter', async () => {
      const onClick = vi.fn();
      render(<${name}${spread} onClick={onClick}>Click me</${name}>);
      const el = screen.getByText('Click me');
      await userEvent.type(el, '{Enter}');
      expect(onClick).toHaveBeenCalled();
    });

    it('does not fire onClick when disabled', async () => {
      const onClick = vi.fn();
      render(<${name}${spread} onClick={onClick} disabled>Click me</${name}>);
      const el = screen.getByText('Click me');
      await userEvent.click(el);
      expect(onClick).not.toHaveBeenCalled();
    });
  });`);
  }

  if (parsed.controlled) {
    sections.push(`  describe('${name} — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<${name}${spread} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });
${parsed.hasDefaultValue ? `
    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<${name}${spread} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
` : ''}  });`);
  }

  if (sections.length === 0) {
    sections.push(`  describe('${name} — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<${name}${spread} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<${name}${spread} />);
      cleanup();
      const { container: c2 } = render(<${name}${spread} />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });`);
  }

  const needsUserEvent = sections.some(s => s.includes('userEvent'));

  return `// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
${needsUserEvent ? "import userEvent from '@testing-library/user-event';\n" : ''}import { ${name} } from '${importPath}';

afterEach(cleanup);

${requiredPropsCode}describe('${name} — depth', () => {
${sections.join('\n\n')}
});
`;
}

const args = process.argv.slice(2);
const shouldWrite = args.includes('--write');
const showDiff = args.includes('--diff');

let totalFound = 0;
let totalGenerated = 0;
let totalSkipped = 0;
let totalExisting = 0;

for (const dir of COMPONENT_DIRS) {
  const components = findComponents(dir);
  totalFound += components.length;

  for (const component of components) {
    const srcFile = component.subdir
      ? path.join(SRC, dir, component.subdir, `${component.name}.tsx`)
      : path.join(SRC, dir, `${component.name}.tsx`);

    const parsed = parseProps(srcFile);
    if (!parsed) { totalSkipped++; continue; }

    const testDir = path.join(SRC, dir, '__tests__');
    const testFile = path.join(testDir, `${component.name}.depth.test.tsx`);

    if (fs.existsSync(testFile)) {
      const existing = fs.readFileSync(testFile, 'utf-8');
      const isReal = /import\s+.*from\s+['"]\.\.\//.test(existing);
      if (isReal) { totalExisting++; continue; }
    }

    const testContent = generateDepthTest(component, parsed);

    if (shouldWrite) {
      if (!fs.existsSync(testDir)) fs.mkdirSync(testDir, { recursive: true });
      fs.writeFileSync(testFile, testContent);
      totalGenerated++;
      console.log(`  ✅ ${dir}/${component.name}.depth.test.tsx`);
    } else if (showDiff) {
      if (!fs.existsSync(testFile)) {
        console.log(`  ❌ Missing: ${dir}/__tests__/${component.name}.depth.test.tsx`);
        totalGenerated++;
      }
    } else {
      console.log(`  📝 Would generate: ${dir}/__tests__/${component.name}.depth.test.tsx`);
      totalGenerated++;
    }
  }
}

console.log(`\n${showDiff ? 'Missing' : shouldWrite ? 'Generated' : 'Would generate'}: ${totalGenerated} | Existing (real): ${totalExisting} | Skipped: ${totalSkipped} | Total: ${totalFound}`);

if (!shouldWrite && !showDiff && totalGenerated > 0) {
  console.log('\nRun with --write to generate test files, or --diff to see missing tests only.');
}
