// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { HistogramChart } from '../HistogramChart';

afterEach(cleanup);

const requiredProps = {
  data: [],
};
describe('HistogramChart — depth', () => {
  describe('HistogramChart — depth: prop combinations', () => {
    it('renders with showNormalCurve + showMean + showMedian simultaneously', () => {
      render(<HistogramChart {...requiredProps} showNormalCurve showMean showMedian>Stressed</HistogramChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<HistogramChart {...requiredProps} showNormalCurve showMean showMedian />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('HistogramChart — depth: width variants', () => {
    it.each(['number', 'string'] as const)('width=%s renders without crash', (val) => {
      const { container } = render(<HistogramChart {...requiredProps} width={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('HistogramChart — depth: height variants', () => {
    it.each(['number', 'string'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<HistogramChart {...requiredProps} height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('HistogramChart — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<HistogramChart {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<HistogramChart {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
