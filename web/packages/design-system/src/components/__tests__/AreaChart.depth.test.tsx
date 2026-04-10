// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AreaChart } from '../charts/AreaChart';

afterEach(cleanup);

const requiredProps = {
  series: [],
};
describe('AreaChart — depth', () => {
  describe('AreaChart — depth: prop combinations', () => {
    it('renders with showDots + curved simultaneously', () => {
      render(<AreaChart {...requiredProps} showDots curved>Stressed</AreaChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<AreaChart {...requiredProps} showDots curved />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AreaChart — depth: series array edge cases', () => {
    it('handles empty series', () => {
      const { container } = render(<AreaChart {...requiredProps} series={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item series', () => {
      const { container } = render(<AreaChart {...requiredProps} series={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
