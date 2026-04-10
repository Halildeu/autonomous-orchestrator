// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MetricComparisonCard } from '../MetricComparisonCard';

afterEach(cleanup);

const requiredProps = {
  title: 'test',
  currentValue: 42,
  previousValue: 42,
};
describe('MetricComparisonCard — depth', () => {
  describe('MetricComparisonCard — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<MetricComparisonCard {...requiredProps} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<MetricComparisonCard {...requiredProps} />);
      cleanup();
      const { container: c2 } = render(<MetricComparisonCard {...requiredProps} />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
