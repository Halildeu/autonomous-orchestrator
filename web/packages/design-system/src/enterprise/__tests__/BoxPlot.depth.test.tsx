// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { BoxPlot } from '../BoxPlot';

afterEach(cleanup);

const requiredProps = {
  data: [],
};
describe('BoxPlot — depth', () => {
  describe('BoxPlot — depth: prop combinations', () => {
    it('renders with showOutliers + showMean simultaneously', () => {
      render(<BoxPlot {...requiredProps} showOutliers showMean>Stressed</BoxPlot>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<BoxPlot {...requiredProps} showOutliers showMean />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BoxPlot — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<BoxPlot {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BoxPlot — depth: width variants', () => {
    it.each(['number', 'string'] as const)('width=%s renders without crash', (val) => {
      const { container } = render(<BoxPlot {...requiredProps} width={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BoxPlot — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<BoxPlot {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<BoxPlot {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
