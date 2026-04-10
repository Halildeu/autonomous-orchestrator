// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FunnelChart } from '../FunnelChart';

afterEach(cleanup);

const requiredProps = {
  stages: [],
};
describe('FunnelChart — depth', () => {
  describe('FunnelChart — depth: prop combinations', () => {
    it('renders with animated', () => {
      const { container } = render(<FunnelChart {...requiredProps} animated />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FunnelChart — depth: orientation variants', () => {
    it.each(['vertical', 'horizontal'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<FunnelChart {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FunnelChart — depth: stages array edge cases', () => {
    it('handles empty stages', () => {
      const { container } = render(<FunnelChart {...requiredProps} stages={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item stages', () => {
      const { container } = render(<FunnelChart {...requiredProps} stages={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
