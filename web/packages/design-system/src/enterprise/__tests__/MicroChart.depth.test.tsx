// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MicroChart } from '../MicroChart';

afterEach(cleanup);

const requiredProps = {
  type: undefined as any,
  data: [],
};
describe('MicroChart — depth', () => {
  describe('MicroChart — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<MicroChart {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<MicroChart {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
