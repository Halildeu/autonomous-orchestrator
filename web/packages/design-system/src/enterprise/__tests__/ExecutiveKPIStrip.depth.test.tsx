// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ExecutiveKPIStrip } from '../ExecutiveKPIStrip';

afterEach(cleanup);

const requiredProps = {
  metrics: [],
};
describe('ExecutiveKPIStrip — depth', () => {
  describe('ExecutiveKPIStrip — depth: prop combinations', () => {
    it('renders with loading', () => {
      const { container } = render(<ExecutiveKPIStrip {...requiredProps} loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ExecutiveKPIStrip — depth: columns variants', () => {
    it.each(['2', '3', '4', '5', '6'] as const)('columns=%s renders without crash', (val) => {
      const { container } = render(<ExecutiveKPIStrip {...requiredProps} columns={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ExecutiveKPIStrip — depth: metrics array edge cases', () => {
    it('handles empty metrics', () => {
      const { container } = render(<ExecutiveKPIStrip {...requiredProps} metrics={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item metrics', () => {
      const { container } = render(<ExecutiveKPIStrip {...requiredProps} metrics={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
