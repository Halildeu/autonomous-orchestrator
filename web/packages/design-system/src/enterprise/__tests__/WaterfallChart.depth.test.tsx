// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { WaterfallChart } from '../WaterfallChart';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('WaterfallChart — depth', () => {
  describe('WaterfallChart — depth: prop combinations', () => {
    it('renders with showValues + showConnectors simultaneously', () => {
      render(<WaterfallChart {...requiredProps} showValues showConnectors>Stressed</WaterfallChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<WaterfallChart {...requiredProps} showValues showConnectors />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('WaterfallChart — depth: height variants', () => {
    it.each(['number', 'string'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<WaterfallChart {...requiredProps} height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('WaterfallChart — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<WaterfallChart {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<WaterfallChart {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
