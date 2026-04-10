// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { LineChart } from '../charts/LineChart';

afterEach(cleanup);

const requiredProps = {
  series: [],
};
describe('LineChart — depth', () => {
  describe('LineChart — depth: prop combinations', () => {
    it('renders with showGrid', () => {
      const { container } = render(<LineChart {...requiredProps} showGrid />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('LineChart — depth: series array edge cases', () => {
    it('handles empty series', () => {
      const { container } = render(<LineChart {...requiredProps} series={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item series', () => {
      const { container } = render(<LineChart {...requiredProps} series={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
