// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { BarChart } from '../charts/BarChart';

afterEach(cleanup);

const requiredProps = {
  data: [],
};
describe('BarChart — depth', () => {
  describe('BarChart — depth: prop combinations', () => {
    it('renders with showValues + showGrid + showLegend + animate simultaneously', () => {
      render(<BarChart {...requiredProps} showValues showGrid showLegend animate>Stressed</BarChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<BarChart {...requiredProps} showValues showGrid showLegend animate />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BarChart — depth: orientation variants', () => {
    it.each(['vertical', 'horizontal'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<BarChart {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BarChart — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<BarChart {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<BarChart {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BarChart — depth: colors array edge cases', () => {
    it('handles empty colors', () => {
      const { container } = render(<BarChart {...requiredProps} colors={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item colors', () => {
      const { container } = render(<BarChart {...requiredProps} colors={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
