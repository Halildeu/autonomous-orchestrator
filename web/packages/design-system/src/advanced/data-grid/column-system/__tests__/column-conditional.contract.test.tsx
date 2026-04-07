// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { findMatchingRule, withConditionalFormatting } from '../conditional';
import type { ConditionalRule } from '../types';

afterEach(() => {
  cleanup();
});

describe('column-conditional — contract', () => {
  describe('findMatchingRule', () => {
    const rules: ConditionalRule[] = [
      { condition: 'eq', value: 'ACTIVE', style: { textColor: 'green' } },
      { condition: 'gt', value: 100, style: { bgColor: 'yellow' } },
      { condition: 'contains', value: 'world', style: { textColor: 'blue' } },
    ];

    it('returns matching rule for eq condition', () => {
      const match = findMatchingRule(rules, 'ACTIVE');
      expect(match).not.toBeNull();
      expect(match!.condition).toBe('eq');
    });

    it('returns matching rule for gt condition', () => {
      const match = findMatchingRule(rules, 150);
      expect(match).not.toBeNull();
      expect(match!.condition).toBe('gt');
    });

    it('returns matching rule for contains condition', () => {
      const match = findMatchingRule(rules, 'hello world');
      expect(match).not.toBeNull();
      expect(match!.condition).toBe('contains');
    });

    it('returns null when no rules match', () => {
      const match = findMatchingRule(rules, 'INACTIVE');
      expect(match).toBeNull();
    });

    it('returns null for null value (null safety)', () => {
      const match = findMatchingRule(rules, null);
      expect(match).toBeNull();
    });

    it('returns null for undefined value', () => {
      const match = findMatchingRule(rules, undefined);
      expect(match).toBeNull();
    });

    it('returns first matching rule (first-match-wins)', () => {
      const overlapping: ConditionalRule[] = [
        { condition: 'gt', value: 50, style: { textColor: 'red' } },
        { condition: 'gt', value: 10, style: { textColor: 'green' } },
      ];
      const match = findMatchingRule(overlapping, 75);
      expect(match!.style.textColor).toBe('red');
    });
  });

  describe('individual condition evaluations via findMatchingRule', () => {
    it('eq: matches when values are equal', () => {
      const rules: ConditionalRule[] = [{ condition: 'eq', value: 'A', style: {} }];
      expect(findMatchingRule(rules, 'A')).not.toBeNull();
      expect(findMatchingRule(rules, 'B')).toBeNull();
    });

    it('neq: matches when values are not equal', () => {
      const rules: ConditionalRule[] = [{ condition: 'neq', value: 'A', style: {} }];
      expect(findMatchingRule(rules, 'B')).not.toBeNull();
      expect(findMatchingRule(rules, 'A')).toBeNull();
    });

    it('contains: case-insensitive substring match', () => {
      const rules: ConditionalRule[] = [{ condition: 'contains', value: 'world', style: {} }];
      expect(findMatchingRule(rules, 'Hello World')).not.toBeNull();
      expect(findMatchingRule(rules, 'hello')).toBeNull();
    });

    it('gt: greater than comparison', () => {
      const rules: ConditionalRule[] = [{ condition: 'gt', value: 5, style: {} }];
      expect(findMatchingRule(rules, 10)).not.toBeNull();
      expect(findMatchingRule(rules, 5)).toBeNull();
      expect(findMatchingRule(rules, 3)).toBeNull();
    });

    it('lt: less than comparison', () => {
      const rules: ConditionalRule[] = [{ condition: 'lt', value: 10, style: {} }];
      expect(findMatchingRule(rules, 5)).not.toBeNull();
      expect(findMatchingRule(rules, 10)).toBeNull();
      expect(findMatchingRule(rules, 15)).toBeNull();
    });

    it('gte: greater than or equal', () => {
      const rules: ConditionalRule[] = [{ condition: 'gte', value: 10, style: {} }];
      expect(findMatchingRule(rules, 10)).not.toBeNull();
      expect(findMatchingRule(rules, 15)).not.toBeNull();
      expect(findMatchingRule(rules, 9)).toBeNull();
    });

    it('lte: less than or equal', () => {
      const rules: ConditionalRule[] = [{ condition: 'lte', value: 10, style: {} }];
      expect(findMatchingRule(rules, 10)).not.toBeNull();
      expect(findMatchingRule(rules, 5)).not.toBeNull();
      expect(findMatchingRule(rules, 11)).toBeNull();
    });

    it('gt: handles string-to-number coercion', () => {
      const rules: ConditionalRule[] = [{ condition: 'gt', value: 5, style: {} }];
      expect(findMatchingRule(rules, '10')).not.toBeNull();
      expect(findMatchingRule(rules, '3')).toBeNull();
    });

    it('gt: returns null for non-numeric string', () => {
      const rules: ConditionalRule[] = [{ condition: 'gt', value: 5, style: {} }];
      expect(findMatchingRule(rules, 'abc')).toBeNull();
    });
  });

  describe('withConditionalFormatting', () => {
    it('wraps base renderer with matching style (textColor)', () => {
      const rules: ConditionalRule[] = [
        { condition: 'eq', value: 'CRITICAL', style: { textColor: 'red' } },
      ];

      const wrapped = withConditionalFormatting(undefined, rules);
      const result = wrapped({ value: 'CRITICAL', data: {} });
      const { container } = render(<>{result}</>);

      const span = container.querySelector('span[style]');
      expect(span).toBeTruthy();
      expect(span!.style.color).toBe('red');
    });

    it('wraps with bgColor and adds border-radius', () => {
      const rules: ConditionalRule[] = [
        { condition: 'gt', value: 90, style: { bgColor: 'green' } },
      ];

      const wrapped = withConditionalFormatting(undefined, rules);
      const result = wrapped({ value: 95, data: {} });
      const { container } = render(<>{result}</>);

      const span = container.querySelector('span[style]');
      expect(span).toBeTruthy();
      expect(span!.style.backgroundColor).toBe('green');
      expect(span!.style.borderRadius).toBe('4px');
    });

    it('wraps with badge variant when specified', () => {
      const rules: ConditionalRule[] = [
        { condition: 'eq', value: 'WARNING', style: { badgeVariant: 'warning' } },
      ];

      const wrapped = withConditionalFormatting(undefined, rules);
      const result = wrapped({ value: 'WARNING', data: {} });
      const { container } = render(<>{result}</>);

      // Badge component should be rendered
      expect(container.textContent).toBe('WARNING');
    });

    it('returns base content unchanged when no rule matches', () => {
      const rules: ConditionalRule[] = [
        { condition: 'eq', value: 'CRITICAL', style: { textColor: 'red' } },
      ];

      const base = (params: { value: unknown }) => <span>{String(params.value)}</span>;
      const wrapped = withConditionalFormatting(base, rules);
      const result = wrapped({ value: 'NORMAL', data: {} });
      const { container } = render(<>{result}</>);

      expect(container.textContent).toBe('NORMAL');
      // No style wrapper applied
      expect(container.querySelector('[style]')).toBeNull();
    });
  });
});
