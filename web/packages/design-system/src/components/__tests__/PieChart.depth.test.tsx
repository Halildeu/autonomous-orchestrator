// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { PieChart } from '../charts/PieChart';

afterEach(cleanup);

const requiredProps = {
  data: [],
};
describe('PieChart — depth', () => {
  describe('PieChart — depth: prop combinations', () => {
    it('renders with showLegend', () => {
      const { container } = render(<PieChart {...requiredProps} showLegend />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('PieChart — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<PieChart {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<PieChart {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
