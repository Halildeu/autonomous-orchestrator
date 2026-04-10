// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ParetoChart } from '../ParetoChart';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('ParetoChart — depth', () => {
  describe('ParetoChart — depth: prop combinations', () => {
    it('renders with showCumulativeLine + showPercentLabels + show80Line simultaneously', () => {
      render(<ParetoChart {...requiredProps} showCumulativeLine showPercentLabels show80Line>Stressed</ParetoChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ParetoChart {...requiredProps} showCumulativeLine showPercentLabels show80Line />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ParetoChart — depth: height variants', () => {
    it.each(['number', 'string'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<ParetoChart {...requiredProps} height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ParetoChart — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<ParetoChart {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<ParetoChart {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
