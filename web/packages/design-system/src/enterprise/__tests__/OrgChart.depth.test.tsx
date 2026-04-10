// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { OrgChart } from '../OrgChart';

afterEach(cleanup);

const requiredProps = {
  data: undefined as any,
};
describe('OrgChart — depth', () => {
  describe('OrgChart — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<OrgChart {...requiredProps} compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('OrgChart — depth: orientation variants', () => {
    it.each(['vertical', 'horizontal'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<OrgChart {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('OrgChart — depth: highlightPath array edge cases', () => {
    it('handles empty highlightPath', () => {
      const { container } = render(<OrgChart {...requiredProps} highlightPath={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item highlightPath', () => {
      const { container } = render(<OrgChart {...requiredProps} highlightPath={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
