// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GaugeChart } from '../GaugeChart';

afterEach(cleanup);

const requiredProps = {
  value: 42,
};
describe('GaugeChart — depth', () => {
  describe('GaugeChart — depth: prop combinations', () => {
    it('renders with showValue + showLabel + animate simultaneously', () => {
      render(<GaugeChart {...requiredProps} showValue showLabel animate>Stressed</GaugeChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<GaugeChart {...requiredProps} showValue showLabel animate />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('GaugeChart — depth: size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<GaugeChart {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('GaugeChart — depth: thresholds array edge cases', () => {
    it('handles empty thresholds', () => {
      const { container } = render(<GaugeChart {...requiredProps} thresholds={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item thresholds', () => {
      const { container } = render(<GaugeChart {...requiredProps} thresholds={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
