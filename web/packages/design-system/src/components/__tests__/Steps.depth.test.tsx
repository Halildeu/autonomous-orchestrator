// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Steps } from '../steps/Steps';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('Steps — depth', () => {
  describe('Steps — depth: prop combinations', () => {
    it('renders with dot', () => {
      const { container } = render(<Steps {...requiredProps} dot />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Steps — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Steps {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Steps {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
