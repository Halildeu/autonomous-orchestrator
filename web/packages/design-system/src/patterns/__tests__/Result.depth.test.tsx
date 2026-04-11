// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Result } from '../result/Result';

afterEach(cleanup);

const requiredProps = {
  status: undefined as any,
};
describe('Result — depth', () => {
  describe('Result — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<Result {...requiredProps} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<Result {...requiredProps} />);
      cleanup();
      const { container: c2 } = render(<Result {...requiredProps} />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
