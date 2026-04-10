// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ComparisonTable } from '../ComparisonTable';

afterEach(cleanup);

const requiredProps = {
  rows: [],
};
describe('ComparisonTable — depth', () => {
  describe('ComparisonTable — depth: prop combinations', () => {
    it('renders with invertVarianceColors', () => {
      const { container } = render(<ComparisonTable {...requiredProps} invertVarianceColors />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ComparisonTable — depth: rows array edge cases', () => {
    it('handles empty rows', () => {
      const { container } = render(<ComparisonTable {...requiredProps} rows={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item rows', () => {
      const { container } = render(<ComparisonTable {...requiredProps} rows={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ComparisonTable — depth: defaultExpandedIds array edge cases', () => {
    it('handles empty defaultExpandedIds', () => {
      const { container } = render(<ComparisonTable {...requiredProps} defaultExpandedIds={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item defaultExpandedIds', () => {
      const { container } = render(<ComparisonTable {...requiredProps} defaultExpandedIds={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
